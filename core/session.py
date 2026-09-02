# ============================================================
#  GRID-SAILING TASK — Session Manager
#
#  You don't need to touch this file.
#
#  This is the bit that ties everything together during a session.
#  Once you hit START on the setup screen, this takes over and:
#    - Runs the right blocks in the right order (from SESSION_STRUCTURE)
#    - Assigns puzzles to each trial (repeated vs random at the right ratio)
#    - Auto-resumes if the app crashes — it checks what's already saved
#      and picks up from the last completed trial, not the beginning
#    - Triggers the Firebase cloud backup every 5 trials in the background
#    - Shows the key tutorial before the very first familiarisation block
#    - Shows the 3E reflection form after MI practice sessions
#
#  Data flow per trial:
#    1. Puzzles are picked from the pool for this block
#    2. Trial runs (core/trial.py takes over for each one)
#    3. Result is saved to the database immediately after
#    4. Every 5 trials → data is backed up to Firebase
#    5. After the last trial → session is marked as complete
# ============================================================

import pygame
import random
import time as _time
import math
from config import (
    SESSION_STRUCTURE, TRIALS_PER_BLOCK, GRID_SIZE,
    PRACTICE_REPEATED_RATIO, TEST_REPEATED_RATIO,
    FAMILIARIZATION_REPEATED_RATIO, FPS,
    SYNC_EVERY_N_TRIALS, SYNC_TIME_SEC,
)
from sync.firebase_sync import sync_in_background
from core.grid import find_valid_paths, apply_key
from core.trial import TrialData, run_trial, run_explore_trial
from screens.tutorial import run_tutorial
from database.db import (
    create_session, complete_session,
    get_resume_point, get_completed_blocks, initialise_database,
    get_global_repeated_puzzle, set_global_repeated_puzzle,
)


# ── Puzzle pool ──────────────────────────────────────────────

def build_puzzle_pool():
    """
    Generate all valid puzzles from all 25 start positions, grouped by (start, goal).

    Each puzzle dict has:
        start, goal        — unique pair
        sequence           — one representative optimal sequence
        sequences          — ALL sequences of minimal length reaching goal
        length             — minimal path length (all sequences have this length)
    """
    from config import MAX_OPTIMAL_LENGTH
    from collections import defaultdict

    by_pair = defaultdict(list)
    for r in range(GRID_SIZE):
        for c in range(GRID_SIZE):
            for p in find_valid_paths(r, c):
                key = (tuple(p["start"]), tuple(p["goal"]))
                by_pair[key].append(p)

    pool = []
    for (start_t, goal_t), ps in by_pair.items():
        min_len = min(p["length"] for p in ps)
        if min_len > MAX_OPTIMAL_LENGTH:
            continue
        optimal_seqs = [p["sequence"] for p in ps if p["length"] == min_len]
        # Only keep puzzles where every optimal path uses all 3 keys, so
        # participants are never penalised for following the "correct" route.
        optimal_seqs = [s for s in optimal_seqs if {1, 2, 3}.issubset(set(s))]
        if not optimal_seqs:
            continue
        pool.append({
            "start":     list(start_t),
            "goal":      list(goal_t),
            "sequence":  optimal_seqs[0],
            "sequences": optimal_seqs,
            "length":    min_len,
        })

    n_paths = sum(len(p["sequences"]) for p in pool)
    print(f"[SESSION] Pool: {len(pool)} unique puzzles, {n_paths} total optimal paths.")
    return pool


def _pick_puzzles(pool, n_trials, repeated_ratio,
                  repeated_puzzle=None, repeated_start=None, repeated_goal=None):
    """
    Select n_trials puzzles with the correct repeated:random ratio.

    repeated_start / repeated_goal: (row, col) tuples or None.
    When set, the repeated puzzle is drawn only from puzzles matching those cells.
    """
    if repeated_puzzle is None:
        candidates = pool
        if repeated_start:
            candidates = [p for p in candidates
                          if tuple(p["start"]) == tuple(repeated_start)]
        if repeated_goal:
            candidates = [p for p in candidates
                          if tuple(p["goal"]) == tuple(repeated_goal)]
        repeated_puzzle = random.choice(candidates) if candidates else random.choice(pool)

    n_repeated = round(n_trials * repeated_ratio)
    n_random   = n_trials - n_repeated

    # Repeated trials all use the same puzzle
    trials = [
        (repeated_puzzle, "repeated") for _ in range(n_repeated)
    ]

    # Random trials: exclude any puzzle that shares an optimal sequence with the repeated puzzle
    rep_seqs = frozenset(
        tuple(s) for s in repeated_puzzle.get("sequences", [repeated_puzzle["sequence"]])
    )
    random_pool = [
        p for p in pool
        if p != repeated_puzzle
        and not any(tuple(s) in rep_seqs
                    for s in p.get("sequences", [p["sequence"]]))
    ]
    if not random_pool:
        random_pool = [p for p in pool if p != repeated_puzzle]
    random_picks = random.choices(random_pool, k=n_random)
    trials += [(p, "random") for p in random_picks]

    random.shuffle(trials)
    return trials, repeated_puzzle


# ── Block runner ─────────────────────────────────────────────

def run_block(screen, clock, fonts, block_type, block_number,
              participant_id, session_number, group, config,
              pool, repeated_puzzle, cumulative_score,
              resume_from_trial=0, guided_gate_trial=None):
    """
    Run one complete block of trials.

    Args:
        screen, clock, fonts:   Pygame objects.
        block_type (str):       familiarization / pre_test / practice / post_test.
        block_number (int):     Index within the session (for DB).
        participant_id (str):   Who is running this block.
        session_number (int):   Session 1, 2, or 3.
        group (str):            Participant's experimental group.
        config (dict):          Session config from researcher setup.
        pool (list):            Full puzzle pool.
        repeated_puzzle (dict): The fixed repeated puzzle for this session.
        cumulative_score (int): Score carried in from previous blocks.
        resume_from_trial (int): If resuming, skip trials <= this number.

    Returns:
        (cumulative_score, repeated_puzzle)
    """
    n_trials = config.get("trials_per_block", TRIALS_PER_BLOCK)

    # Determine grid ratio based on block type
    if block_type == "familiarization":
        ratio = FAMILIARIZATION_REPEATED_RATIO
    elif block_type in ("pre_test", "post_test"):
        ratio = config.get("test_ratio", TEST_REPEATED_RATIO)
    else:  # practice
        ratio = config.get("practice_ratio", PRACTICE_REPEATED_RATIO)

    # Ensure all participants share the same repeated puzzle.
    # On the very first block of the experiment, pick one (constrained by
    # repeated_start if Juliet set it) and save it to the DB.
    # Every subsequent participant re-uses that saved puzzle.
    if repeated_puzzle is None:
        stored = get_global_repeated_puzzle()
        if stored:
            # Find the full pool entry so we get all_optimal_sequences too
            stored_s = tuple(stored["start"])
            stored_g = tuple(stored["goal"])
            pool_match = next(
                (p for p in pool
                 if tuple(p["start"]) == stored_s and tuple(p["goal"]) == stored_g),
                stored
            )
            repeated_puzzle = pool_match

    first_pick = (repeated_puzzle is None)

    repeated_start = config.get("repeated_start", None)
    repeated_goal  = config.get("repeated_goal",  None)
    trials_list, repeated_puzzle = _pick_puzzles(
        pool, n_trials, ratio, repeated_puzzle, repeated_start, repeated_goal
    )

    if first_pick:
        set_global_repeated_puzzle(repeated_puzzle)

    # Create or find session record in DB
    resume = get_resume_point(participant_id, session_number, block_type, block_number)
    if resume:
        session_id         = resume["session_id"]
        resume_from_trial  = resume["last_trial_completed"]
        print(f"[SESSION] Resuming block from trial {resume_from_trial}")
    else:
        session_id = create_session(
            participant_id, session_number, block_type, block_number
        )

    # Show block intro screen
    _show_block_intro(screen, clock, fonts, block_type, block_number,
                      session_number, group, config)

    is_mi = group.startswith("MI")

    # Fam block 1: Pay Attention for MI groups before the exploration trials
    if block_type == "familiarization" and block_number == 1 and is_mi:
        _show_pay_attention(screen, clock, fonts)

    # Fam block 2: guided check-in before the planning trials
    if block_type == "familiarization" and block_number == 2:
        _show_try_it_yourself_intro(screen, clock, fonts)
        _run_try_it_yourself_trials(
            screen, clock, fonts, pool, config,
            participant_id, session_number, group
        )
        _show_researcher_gate(screen, clock, fonts,
                              "Ready to move on?",
                              ["Now that you have completed some practice trials,",
                               "please let your researcher know if you have any questions.",
                               "Otherwise, let the researcher know you are ready to proceed."])
        if is_mi:
            _show_pay_attention(screen, clock, fonts)

    # Practice block 1 of Session 1: Try it yourself before the guided trials
    if guided_gate_trial is not None:
        _show_try_it_yourself_practice_intro(screen, clock, fonts)

    streak          = 0
    last_sync_time  = _time.time()
    last_sync_trial = resume_from_trial

    # Fam block 1 → free exploration mode (no timer, no planning, no sequence input).
    # Fam block 2 and all other blocks → 6-second planning timer.
    # Score shown only during practice blocks.
    is_explore = (
        (block_type == "familiarization" and block_number == 1)
        or block_type in ("pre_test", "post_test")
    )
    show_timer = not is_explore
    show_score = block_type not in ("familiarization", "pre_test", "post_test")

    # Session state passed to the researcher panel so it can show trial status live.
    session_state = {
        "trials": [
            {
                "trial_number": idx + 1,
                "grid_type":    gt,
                "status":       "done" if (idx + 1) <= resume_from_trial else "pending",
                "result":       None,
            }
            for idx, (_, gt) in enumerate(trials_list)
        ],
        "block_type":     block_type,
        "block_number":   block_number,
        "session_number": session_number,
        "participant_id": participant_id,
        "group":          group,
    }
    completed_in_session = set()   # trial numbers saved to DB this run

    i = 0
    while i < len(trials_list):
        trial_number = i + 1

        # Skip trials already completed (from a prior crash/resume or a same-session jump)
        if trial_number <= resume_from_trial or trial_number in completed_in_session:
            i += 1
            continue

        puzzle, grid_type = trials_list[i]
        session_state["trials"][i]["status"] = "current"

        trial = TrialData(
            session_id            = session_id,
            participant_id        = participant_id,
            trial_number          = trial_number,
            grid_type             = grid_type,
            start                 = tuple(puzzle["start"]),
            goal                  = tuple(puzzle["goal"]),
            optimal_sequence      = puzzle["sequence"],
            all_optimal_sequences = puzzle.get("sequences", [puzzle["sequence"]]),
            group                 = group,
        )

        if is_explore:
            explore_time_limit = 6.0 if block_type in ("pre_test", "post_test") else None
            result = run_explore_trial(
                screen, clock, fonts, trial, config,
                cumulative_score, session_id,
                total_trials=n_trials,
                block_type=block_type,
                session_state=session_state,
                time_limit=explore_time_limit,
            )
        else:
            result = run_trial(
                screen, clock, fonts, trial, config,
                cumulative_score, session_id,
                total_trials=n_trials,
                block_type=block_type,
                streak=streak,
                show_timer=show_timer,
                show_score=show_score,
                session_state=session_state,
            )

        if result.get("paused_exit"):
            sync_in_background(session_id, trial_number - 1)
            _show_saved_exit(screen, clock, fonts)
            return "exited"

        # Researcher jumped to a different trial — abandon current, skip in-between.
        if "researcher_jump" in result:
            target = result["researcher_jump"]
            session_state["trials"][i]["status"] = "skipped"
            for skip_i in range(i + 1, target - 1):
                if skip_i < len(trials_list):
                    session_state["trials"][skip_i]["status"] = "skipped"
            i = target - 1   # jump; continue skips i += 1
            continue

        completed_in_session.add(trial_number)

        # Mid-block researcher gate after guided practice trials
        if guided_gate_trial and trial_number == guided_gate_trial:
            _show_researcher_gate(screen, clock, fonts,
                                  "Ready to move on?",
                                  ["Now that you have completed some practice trials,",
                                   "please let your researcher know if you have any questions.",
                                   "Otherwise, let the researcher know you are ready to proceed."])

        session_state["trials"][i]["status"] = "done"
        session_state["trials"][i]["result"] = {
            "reward_score":     trial.reward_score,
            "is_correct":       trial.is_correct,
            "cumulative_score": result["cumulative_score"],
            "start":            trial.start,
            "goal":             trial.goal,
            "planned_sequence": list(trial.planned_sequence),
            "optimal_sequence": list(trial.optimal_sequence),
            "number_of_moves":  trial.number_of_moves,
            "reaction_time_ms": trial.reaction_time_ms,
            "movement_time_ms": trial.movement_time_ms,
        }

        cumulative_score = result["cumulative_score"]
        streak           = result.get("streak", 0)

        # Sync every N trials OR every SYNC_TIME_SEC seconds — whichever first
        trials_due = (trial_number - last_sync_trial) >= SYNC_EVERY_N_TRIALS
        time_due   = (_time.time() - last_sync_time)  >= SYNC_TIME_SEC
        if trials_due or time_due:
            sync_in_background(session_id, trial_number)
            last_sync_time  = _time.time()
            last_sync_trial = trial_number

        i += 1

    complete_session(session_id)
    sync_in_background(session_id, n_trials)   # final sync on block complete

    # Reflection (3E) is done as an in-person interview after the experiment — no in-app form needed.

    return cumulative_score, repeated_puzzle


def _show_saved_exit(screen, clock, fonts):
    """Brief confirmation screen shown after Save & Exit."""
    f_big, f_med, f_sm, f_xs = fonts
    cx = screen.get_width()  // 2
    cy = screen.get_height() // 2

    waiting = True
    t0 = pygame.time.get_ticks()
    while waiting:
        clock.tick(FPS)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); import sys; sys.exit()
            if event.type == pygame.KEYDOWN:
                waiting = False

        # Auto-exit after 3 seconds
        if pygame.time.get_ticks() - t0 > 3000:
            waiting = False

        screen.fill((12, 12, 22))

        f_big_h = f_big.get_height()
        f_sm_h  = f_sm.get_height()
        f_xs_h  = f_xs.get_height()
        start_y = cy - (f_big_h + 14 + f_sm_h + 10 + f_xs_h) // 2

        ts = f_big.render("Progress Saved", True, (58, 196, 108))
        screen.blit(ts, (cx - ts.get_width() // 2, start_y))

        ms = f_sm.render("All completed trials have been recorded.", True, (100, 100, 138))
        screen.blit(ms, (cx - ms.get_width() // 2, start_y + f_big_h + 14))

        hs = f_xs.render("Returning to the start screen...", True, (60, 60, 90))
        screen.blit(hs, (cx - hs.get_width() // 2, start_y + f_big_h + 14 + f_sm_h + 10))

        pygame.display.flip()


# ── Session runner ────────────────────────────────────────────

def run_session(screen, clock, fonts, config: dict, participant: dict):
    """
    Run the full session for a participant based on SESSION_STRUCTURE.

    Args:
        screen, clock, fonts: Pygame objects.
        config (dict):        Researcher config from setup screen.
        participant (dict):   Verified participant row from DB.
    """
    participant_id = participant["participant_id"]
    group          = config.get("group", participant["group_name"])
    session_number = config["session_number"]

    print(f"[SESSION] Starting Session {session_number} for {participant_id} ({group})")

    initialise_database()

    # Build puzzle pool once at session start (takes a few seconds)
    _show_loading(screen, fonts)
    pool = build_puzzle_pool()

    block_sequence   = SESSION_STRUCTURE.get(session_number, [])
    cumulative_score = 0
    repeated_puzzle  = None   # fixed across the whole session
    start_from_block = config.get("start_from_block", 1)

    # Auto-advance past already-completed blocks so a restart never re-runs them.
    completed_blocks = get_completed_blocks(participant_id, session_number)
    if completed_blocks:
        auto_start = max(completed_blocks) + 1
        if auto_start > start_from_block:
            start_from_block = auto_start
            print(f"[SESSION] Auto-resuming from block {start_from_block} "
                  f"(blocks {sorted(completed_blocks)} already done)")

    # Skip instructions when jumping into the middle of a session
    if start_from_block <= 1:
        _show_instructions(screen, clock, fonts, group)

    is_mi = group.startswith("MI")

    # First practice block index — used for guided gate + reflection gate
    first_practice_idx = next(
        (i for i, bt in enumerate(block_sequence) if bt == "practice"), None
    )

    for block_idx, block_type in enumerate(block_sequence):
        if block_idx + 1 < start_from_block:
            continue   # already completed or researcher chose to skip

        # Guided practice gate: first 3 trials of the very first practice block
        # in Session 1 act as a confirmation run-through before the full block.
        guided_gate = (3
                       if session_number == 1 and block_idx == first_practice_idx
                       else None)

        # Reflection gate for MI groups (Session 1, before first practice block)
        if (session_number == 1
                and block_idx == first_practice_idx
                and is_mi):
            _show_researcher_gate(screen, clock, fonts,
                                  "Reflection",
                                  ["Discuss with the researcher how it felt to press the keys.",
                                   "What did you notice? How did the keys feel to press?",
                                   "What sounds (if any) did the keys make?"])

        result = run_block(
            screen            = screen,
            clock             = clock,
            fonts             = fonts,
            block_type        = block_type,
            block_number      = block_idx + 1,
            participant_id    = participant_id,
            session_number    = session_number,
            group             = group,
            config            = config,
            pool              = pool,
            repeated_puzzle   = repeated_puzzle,
            cumulative_score  = cumulative_score,
            guided_gate_trial = guided_gate,
        )

        if result == "exited":
            return   # participant exited mid-session

        cumulative_score, repeated_puzzle = result

        # ── Between-block extras ──────────────────────────────
        if block_idx < len(block_sequence) - 1:
            next_block = block_sequence[block_idx + 1]

            _show_break(screen, clock, fonts,
                        completed_block=block_type,
                        next_block=next_block,
                        block_num=block_idx + 1,
                        total_blocks=len(block_sequence))

    _show_session_complete(screen, clock, fonts, session_number, cumulative_score, group)


# ── Between-block screens ─────────────────────────────────────

def _show_loading(screen, fonts):
    """Brief loading screen while puzzles are generated."""
    f_big, f_med, f_sm, f_xs = fonts
    screen.fill((15, 15, 25))
    msg = f_med.render("Preparing experiment...", True, (90, 150, 255))
    screen.blit(msg, (screen.get_width() // 2 - msg.get_width() // 2,
                      screen.get_height() // 2))
    pygame.display.flip()


BG     = (8,   8,  16)
PANEL  = (20,  20, 36)
BORDER = (48,  48, 76)
WHITE  = (245, 245, 255)
DIM    = (118, 118, 158)
ACCENT = (88,  148, 255)
GREEN  = (52,  200, 100)
AMBER  = (220, 162, 28)


def _card_screen(screen, clock, fonts, title, title_col, badge, lines,
                 hint_text, hint_col=None):
    """Generic centred card screen. Returns when SPACE is pressed."""
    f_big, f_med, f_sm, f_xs = fonts
    W, H   = screen.get_width(), screen.get_height()
    CX, CY = W // 2, H // 2
    if hint_col is None:
        hint_col = ACCENT

    # Card width scales with screen so fonts don't overflow at high resolutions
    CW = min(W - 80, max(740, W * 2 // 5))
    max_body_w = CW - 56

    # Word-wrap body text so long lines never overflow the card
    def _wrap(text, font=None):
        fnt = font or f_sm
        if not text:
            return [""]
        words, out, cur = text.split(), [], ""
        for w in words:
            test = (cur + " " + w).strip()
            if fnt.size(test)[0] <= max_body_w:
                cur = test
            else:
                if cur:
                    out.append(cur)
                cur = w
        if cur:
            out.append(cur)
        return out or [""]

    wrapped = []
    for text, col in lines:
        if text:
            for sub in _wrap(text):
                wrapped.append((sub, col))
        else:
            wrapped.append(("", col))

    # Choose title font: fall back to f_med if f_big would overflow the card
    f_big_h   = f_big.get_height()
    f_sm_h    = f_sm.get_height()
    f_xs_h    = f_xs.get_height()
    line_h    = f_sm_h + 8
    badge_h   = (f_xs_h + 10 + 10) if badge else 0
    ts_probe  = f_big.render(title, True, WHITE)
    f_title   = f_med if ts_probe.get_width() > CW - 32 else f_big
    f_title_h = f_title.get_height()
    CH = max(240, 16 + badge_h + f_title_h + 14 + 12 + len(wrapped) * line_h + f_sm_h + 24)

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); import sys; sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_ESCAPE):
                    return

        screen.fill(BG)

        # Subtle dot grid
        for gx in range(0, W + 48, 48):
            for gy in range(0, H + 48, 48):
                pygame.draw.circle(screen, (18, 18, 36), (gx, gy), 1)

        # Card
        cx2 = CX - CW // 2
        cy2 = CY - CH // 2
        pygame.draw.rect(screen, (4, 4, 10),
                         (cx2 + 4, cy2 + 6, CW, CH), border_radius=20)
        pygame.draw.rect(screen, PANEL,  (cx2, cy2, CW, CH), border_radius=20)
        pygame.draw.rect(screen, BORDER, (cx2, cy2, CW, CH), width=1, border_radius=20)
        pygame.draw.rect(screen, title_col,
                         (cx2 + 1, cy2 + 1, CW - 2, 6), border_radius=20)

        y = cy2 + 16

        # Badge pill
        if badge:
            bs     = f_xs.render(badge, True, title_col)
            bw     = bs.get_width() + 24
            pill_h = f_xs_h + 10
            bx     = CX - bw // 2
            pygame.draw.rect(screen, (20, 20, 40),
                             (bx, y, bw, pill_h), border_radius=pill_h // 2)
            pygame.draw.rect(screen, title_col,
                             (bx, y, bw, pill_h), width=1, border_radius=pill_h // 2)
            screen.blit(bs, (CX - bs.get_width() // 2, y + 5))
            y += pill_h + 10

        # Title — uses f_med automatically when f_big would overflow the card
        ts = f_title.render(title, True, WHITE)
        screen.blit(ts, (CX - ts.get_width() // 2, y))
        y += f_title_h + 14

        # Divider
        pygame.draw.line(screen, BORDER, (cx2 + 32, y), (cx2 + CW - 32, y))
        y += 12

        # Body lines
        for text, col in wrapped:
            if text:
                ls = f_sm.render(text, True, col)
                screen.blit(ls, (CX - ls.get_width() // 2, y))
            y += line_h

        # Hint (anchored to card bottom)
        hs = f_sm.render(hint_text, True, hint_col)
        screen.blit(hs, (CX - hs.get_width() // 2, cy2 + CH - f_sm_h - 16))

        # Footer
        ft = f_xs.render("Press  SPACE  to continue", True, (44, 44, 72))
        screen.blit(ft, (CX - ft.get_width() // 2, H - 32))

        pygame.display.flip()
        clock.tick(FPS)


def _show_block_intro(screen, clock, fonts, block_type, block_number,
                      session_number, group, config):
    is_mi   = group.startswith("MI")
    is_pp   = group.startswith("PP")
    is_ctrl = group.startswith("CTRL")

    if block_type == "familiarization" and block_number == 1:
        title = "Familiarization Part One"
        desc  = ("Explore the grid freely! Press 1, 2, or 3 on the keypad to move the MOUSE. "
                 "When you reach the CHEESE, the next trial starts automatically. "
                 "No timer, no score – just learn how the keys move the MOUSE.")
    elif block_type == "familiarization":
        title = "Familiarization Part Two"
        desc  = ("In this block you will see the grid for 6 seconds. As you plan your sequence, "
                 "enter it into the provided space using the trackpad. After confirming your "
                 "sequence, you will then be asked to physically press the keys for your planned "
                 "sequence. Press SPACE when you are done.")
    elif block_type == "pre_test":
        title = "Baseline"
        desc  = ("In this block you will go back to FREE PLAY. Trials are NO LONGER split into "
                 "planning and action stages. You will have 6 seconds to navigate the MOUSE to "
                 "the CHEESE. Try to find the shortest sequence using all keys at least once.")
    elif block_type == "post_test":
        title = "Final Block"
        desc  = ("In this block you will go back to FREE PLAY. Trials are NO LONGER split into "
                 "planning and action stages. You will have 6 seconds to navigate the MOUSE to "
                 "the CHEESE. Try to find the shortest sequence using all keys at least once.")
    elif block_type == "practice":
        title = "Practice"
        if is_mi:
            desc = ("In this block you will see the grid for 6 seconds. As you plan your "
                    "sequence, enter it into the provided space using the trackpad. After "
                    "confirming your sequence, you will then be asked to IMAGINE pressing the "
                    "keys for your planned sequence. Focus on imagining the movements as you "
                    "just described them to the researcher.")
        elif is_pp:
            desc = ("In this block you will see the grid for 6 seconds. As you plan your "
                    "sequence, enter it into the provided space using the trackpad. After "
                    "confirming your sequence, you will then be asked to physically press the "
                    "keys for your planned sequence.")
        else:  # CTRL
            desc = ("In this block you will see the grid for 6 seconds. As you plan your "
                    "sequence, enter it into the provided space using the trackpad. After "
                    "confirming your sequence, you will immediately receive feedback on your "
                    "response.")
    else:
        title = block_type.replace("_", " ").title()
        desc  = ""

    badge = f"Session {session_number}  ·  Block {block_number}"
    lines = [(desc, DIM)]
    if block_type == "practice" and is_ctrl:
        lines += [
            ("", DIM),
            ("PLEASE DO NOT PRESS THE 3-KEY KEYPAD DURING THESE TRIALS.", WHITE),
        ]
    _card_screen(screen, clock, fonts,
                 title=title,
                 title_col=ACCENT, badge=badge, lines=lines,
                 hint_text="Press  SPACE  to begin")

    # Score explanation follows the block intro card for every practice block
    if block_type == "practice":
        _show_score_explanation(screen, clock, fonts)


def _show_break(screen, clock, fonts,
                completed_block, next_block, block_num, total_blocks):
    """Information slide shown between blocks."""
    lines = [
        ("Well done! Take a moment to rest before continuing.", DIM),
    ]
    _card_screen(screen, clock, fonts,
                 title=f"Take a Short Break  (block {block_num} of {total_blocks})",
                 title_col=GREEN, badge=None, lines=lines,
                 hint_text="Press  SPACE  when you are ready to continue")


# ── New between-block screens ─────────────────────────────────────────────

def _show_researcher_gate(screen, clock, fonts, title, participant_lines):
    """
    Full-screen gate showing participant-facing text, then requiring the researcher
    to enter ADMIN_PASSWORD to unlock. After unlock, participant presses SPACE.

    participant_lines: list of strings shown to the participant above the gate.
    """
    from config import ADMIN_PASSWORD
    f_big, f_med, f_sm, f_xs = fonts
    W, H = screen.get_width(), screen.get_height()
    cx = W // 2

    # Card width scales with screen (same logic as _card_screen)
    cw      = min(W - 80, max(740, W * 2 // 5))
    fw_body = cw - 48

    # Word-wrap each participant line to fit the card
    def _gate_wrap(text):
        if not text:
            return [""]
        words, out, cur = text.split(), [], ""
        for w in words:
            test = (cur + " " + w).strip()
            if f_sm.size(test)[0] <= fw_body:
                cur = test
            else:
                if cur:
                    out.append(cur)
                cur = w
        if cur:
            out.append(cur)
        return out or [""]

    wrapped_lines = []
    for ln in participant_lines:
        wrapped_lines.extend(_gate_wrap(ln))

    line_h  = f_sm.get_height() + 8
    title_h = f_big.get_height()
    xs_h    = f_xs.get_height()
    fh      = 52   # input field height
    btn_h   = 52   # unlock button height
    part_h  = len(wrapped_lines) * line_h + 12
    ch      = 22 + title_h + 14 + part_h + 12 + xs_h + 14 + fh + 12 + btn_h + 20

    cy2 = H // 2 - ch // 2
    cx2 = cx - cw // 2
    fx  = cx2 + 24
    fw  = cw - 48

    pw       = ""
    wrong    = False
    shake_t0 = 0.0
    unlocked = False

    while True:
        clock.tick(FPS)
        now = _time.time()

        # Recompute button rect each frame (depends on shake offset)
        sx = 0
        if shake_t0 and (now - shake_t0) < 0.5:
            t  = (now - shake_t0) / 0.5
            sx = int(10 * math.sin(t * 22) * (1 - t))

        fy      = cy2 + 22 + title_h + 14 + part_h + 12 + xs_h + 14
        btn_y   = fy + fh + 12
        btn_rect = pygame.Rect(cx - 100 + sx, btn_y, 200, btn_h)

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                import sys; pygame.quit(); sys.exit()
            if ev.type == pygame.KEYDOWN:
                if unlocked:
                    if ev.key in (pygame.K_SPACE, pygame.K_RETURN):
                        return
                else:
                    if ev.key == pygame.K_BACKSPACE:
                        pw = pw[:-1]; wrong = False
                    elif ev.key == pygame.K_RETURN:
                        if pw == ADMIN_PASSWORD:
                            unlocked = True
                        else:
                            pw = ""; wrong = True; shake_t0 = now
                    elif ev.unicode:
                        if len(pw) < 64:
                            pw += ev.unicode
            if ev.type == pygame.MOUSEBUTTONDOWN and not unlocked:
                if btn_rect.collidepoint(ev.pos):
                    if pw == ADMIN_PASSWORD:
                        unlocked = True
                    else:
                        pw = ""; wrong = True; shake_t0 = now

        screen.fill(BG)
        for gx in range(0, W + 48, 48):
            for gy in range(0, H + 48, 48):
                pygame.draw.circle(screen, (18, 18, 36), (gx, gy), 1)

        x2 = cx2 + sx
        pygame.draw.rect(screen, (4,  4, 10), (x2+4, cy2+6, cw, ch), border_radius=18)
        pygame.draw.rect(screen, PANEL,        (x2,   cy2,   cw, ch), border_radius=18)
        pygame.draw.rect(screen, BORDER,       (x2,   cy2,   cw, ch), width=1, border_radius=18)
        pygame.draw.rect(screen, AMBER,        (x2+1, cy2+1, cw-2, 5), border_radius=18)

        # Title
        ts = f_big.render(title, True, WHITE)
        screen.blit(ts, (cx - ts.get_width() // 2 + sx, cy2 + 22))

        # Participant-facing lines (word-wrapped to fit the card)
        py = cy2 + 22 + title_h + 14
        for line_text in wrapped_lines:
            ls = f_sm.render(line_text, True, DIM)
            screen.blit(ls, (cx - ls.get_width() // 2 + sx, py))
            py += line_h

        # Divider
        div_y = py + 12
        pygame.draw.line(screen, BORDER, (x2 + 28, div_y), (x2 + cw - 28, div_y))

        gate_y = div_y + 12
        if unlocked:
            # Post-unlock: pulsing "Press SPACE to continue" where the button was
            pulse = 0.55 + 0.45 * math.sin(now * math.pi * 1.6)
            pc    = tuple(int(c * pulse) for c in ACCENT)
            cont  = f_sm.render("Press  SPACE  to continue", True, pc)
            screen.blit(cont, (cx - cont.get_width() // 2, gate_y + xs_h + 14 + fh // 2))
        else:
            gate_lbl = f_xs.render("Researcher — enter the access code to continue", True, AMBER)
            screen.blit(gate_lbl, (cx - gate_lbl.get_width() // 2 + sx, gate_y))

            fc = (210, 95, 20) if wrong else ACCENT
            pygame.draw.rect(screen, (28, 28, 52), (fx + sx, fy, fw, fh), border_radius=10)
            pygame.draw.rect(screen, fc,            (fx + sx, fy, fw, fh), width=2, border_radius=10)
            disp = ("●" * len(pw)) if pw else "Code"
            dc   = WHITE if pw else (72, 72, 112)
            ds   = f_sm.render(disp, True, dc)
            screen.blit(ds, (fx + sx + 16, fy + fh // 2 - ds.get_height() // 2))

            if wrong and shake_t0 and (now - shake_t0) < 2.0:
                ws = f_xs.render("Incorrect — try again", True, (210, 95, 20))
                screen.blit(ws, (cx - ws.get_width() // 2 + sx, fy + fh + 6))

            bx = cx - 100 + sx
            hv = btn_rect.collidepoint(pygame.mouse.get_pos())
            bc = tuple(min(255, c + 28) for c in AMBER) if hv else AMBER
            pygame.draw.rect(screen, (4, 4, 12), (bx + 2, btn_y + 3, 200, btn_h), border_radius=10)
            pygame.draw.rect(screen, bc,         (bx,     btn_y,     200, btn_h), border_radius=10)
            bl = f_sm.render("Unlock", True, (8, 8, 16))
            screen.blit(bl, (bx + 100 - bl.get_width() // 2,
                             btn_y + btn_h // 2 - bl.get_height() // 2))

        pygame.display.flip()


def _show_pay_attention(screen, clock, fonts):
    """MI-only slide shown after each familiarization block."""
    _card_screen(screen, clock, fonts,
                 title="Pay Attention!",
                 title_col=AMBER, badge=None,
                 lines=[
                     ("Please pay attention to how it FEELS to press the keys.", DIM),
                     ("What does it feel like to press the keys?", DIM),
                     ("What sounds do the keys make when you press the keys?", DIM),
                 ],
                 hint_text="Press  SPACE  to continue")


def _show_try_it_yourself_intro(screen, clock, fonts):
    """Instruction slide shown before the 3 guided practice trials (after fam block 1)."""
    _card_screen(screen, clock, fonts,
                 title="Try it yourself!",
                 title_col=GREEN, badge=None,
                 lines=[
                     ("Practice a few trials.", DIM),
                     ("Please let your researcher know if you have any questions.", DIM),
                 ],
                 hint_text="Press  SPACE  to start")


def _show_try_it_yourself_practice_intro(screen, clock, fonts):
    """Shown at the start of the first practice block in Session 1 (all groups)."""
    _card_screen(screen, clock, fonts,
                 title="Try it yourself!",
                 title_col=GREEN, badge=None,
                 lines=[
                     ("Practice a few trials.", DIM),
                     ("Please let your researcher know if you have any questions.", DIM),
                 ],
                 hint_text="Press  SPACE  to begin")


def _show_score_explanation(screen, clock, fonts):
    """Score explanation slide shown before every practice block."""
    _card_screen(screen, clock, fonts,
                 title="Score",
                 title_col=GREEN, badge=None,
                 lines=[
                     ("During the practice blocks you will receive feedback on your", DIM),
                     ("planned sequences after each trial. You will receive a score", DIM),
                     ("for each trial AND a cumulative score.", DIM),
                     ("", DIM),
                     ("A sequence that successfully moves the MOUSE to the CHEESE", DIM),
                     ("using the shortest possible path and all three keys will", DIM),
                     ("receive 100 pts. Each additional move beyond the shortest path", DIM),
                     ("will result in a 10-pt deduction. If your sequence does not", DIM),
                     ("move the MOUSE to the CHEESE, you will receive 0 pts.", DIM),
                 ],
                 hint_text="Press  SPACE  to continue")


def _run_try_it_yourself_trials(screen, clock, fonts, pool, config,
                                participant_id, session_number, group):
    """Run 3 random practice trials so participants confirm they understand."""
    from database.db import create_session, complete_session as _complete_session
    session_id = create_session(participant_id, session_number, "guided_practice", 0)
    sample     = random.sample(pool, min(3, len(pool)))
    for i, puzzle in enumerate(sample):
        trial = TrialData(
            session_id            = session_id,
            participant_id        = participant_id,
            trial_number          = i + 1,
            grid_type             = "random",
            start                 = tuple(puzzle["start"]),
            goal                  = tuple(puzzle["goal"]),
            optimal_sequence      = puzzle["sequence"],
            all_optimal_sequences = puzzle.get("sequences", [puzzle["sequence"]]),
            group                 = group,
        )
        run_trial(
            screen, clock, fonts, trial, config,
            cumulative_score=0, session_id=session_id,
            total_trials=3, block_type="guided_practice",
            streak=0, show_timer=True, show_score=False,
        )
    _complete_session(session_id)


# ════════════════════════════════════════════════════════════════════════════
# JULIET — INSTRUCTION TEXT IS HERE
#
# _show_instructions()  →  the 5 slides shown once before Session 1 begins.
# _show_block_intro()   →  the short screen shown before every block.
# _show_break()         →  the "Take a short break" screen between blocks.
#
# To change what participants see, edit the string literals inside the
# _slide() / _card_screen() calls below.  Each line is a (text, colour) tuple.
# ════════════════════════════════════════════════════════════════════════════
def _show_instructions(screen, clock, fonts, group):
    """Multi-slide instruction sequence shown once before the first block."""

    def _slide(title, title_col, badge, lines, hint="Press  SPACE  to continue"):
        _card_screen(screen, clock, fonts,
                     title=title, title_col=title_col,
                     badge=badge, lines=lines, hint_text=hint)

    # Slide 1 — Welcome
    _slide(
        "Welcome",
        ACCENT, None,
        [
            ("In this task, you will navigate a grid to move a", DIM),
            ("MOUSE to a piece of CHEESE in as few moves as possible.", DIM),
            ("", DIM),
            ("There are three sessions in total.", DIM),
        ],
    )

    # Slide 2 — The grid
    _slide(
        "The Grid",
        ACCENT, None,
        [
            ("You will see a 5x5 grid.", DIM),
            ("The blue cell is the MOUSE (start).", DIM),
            ("The yellow cell is the CHEESE (goal).", DIM),
            ("Navigate the MOUSE to the CHEESE in as few moves as possible", DIM),
            ("using each key at least once.", DIM),
        ],
    )

    # Slide 3 — Repeated vs Random - Juliet: I would like this to be removed.
    #_slide(
    #    "Two Types of Grid",
    #    AMBER, "Grid types",
    #    [
    #        ("REPEATED  —  the same puzzle appears many times.", WHITE),
    #        ("RANDOM    —  a new puzzle each time.", DIM),
    #        ("", DIM),
    #        ("Learning the repeated puzzle is part of the experiment.", DIM),
    #    ],
    #)

    # Slide 4 — How to enter a sequence JULIET: I would like to move this slide to between Fam 1 and 2 blocks
    # ── EDIT INSTRUCTIONS HERE ──────────────────────────────────────────
    # This is the slide that explains how to enter a movement sequence.
    # Change the text strings in the list below to update what participants see.
    # ────────────────────────────────────────────────────────────────────
    #_slide(
    #    "Entering Your Plan",
    #    ACCENT, None,
    #    [
    #        ("You have 6 seconds to study the grid and plan your route.", DIM),
    #        ("Then the grid hides — click  1 / 2 / 3  or press the keypad", DIM),
    #        ("to enter your sequence.", DIM),
    #        ("Press  Confirm  when done. You will then execute the plan.", DIM),
    #    ],
    #)

    # Slide 5 — Ready
    _slide(
        "Let's Begin",
        GREEN, None,
        [
            ("The experiment will now begin.", DIM),
            ("", DIM),
            ("Follow the instructions on each screen.", DIM),
            ("Ask the researcher if you have any questions.", DIM),
        ],
        hint="Press  SPACE  to start",
    )


def _show_session_complete(screen, clock, fonts, session_number, total_score, group=""):
    next_msg = (f"Please return for Session {session_number + 1}."
                if session_number < 3
                else "You have completed all 3 sessions. Thank you!")
    is_mi = group.startswith("MI")
    lines = [
        (f"Total score:  {total_score}", AMBER),
        (next_msg,                       DIM),
    ]
    if is_mi:
        lines += [
            ("", DIM),
            ("Please notify the researcher. You will be provided with a report card", DIM),
            ("to complete about your imagery experiences. Once completed, you will", DIM),
            ("review your responses with the researcher, after which the session", DIM),
            ("will be complete.", DIM),
        ]
    _card_screen(screen, clock, fonts,
                 title=f"Session {session_number} Complete!",
                 title_col=GREEN, badge=None, lines=lines,
                 hint_text="Press  ESC  to exit", hint_col=DIM)
