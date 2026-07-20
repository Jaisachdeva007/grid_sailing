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
from config import (
    SESSION_STRUCTURE, TRIALS_PER_BLOCK, GRID_SIZE,
    PRACTICE_REPEATED_RATIO, TEST_REPEATED_RATIO,
    FAMILIARIZATION_REPEATED_RATIO, FPS,
    SYNC_EVERY_N_TRIALS, SYNC_TIME_SEC,
)
from sync.firebase_sync import sync_in_background
from core.grid import find_valid_paths, apply_key
from core.trial import TrialData, run_trial, run_explore_trial
from screens.reflection import run_reflection
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
              resume_from_trial=0):
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

    streak          = 0
    last_sync_time  = _time.time()
    last_sync_trial = resume_from_trial

    # Fam block 1 → free exploration mode (no timer, no planning, no sequence input).
    # Fam block 2 and all other blocks → 6-second planning timer.
    # Score shown only during practice blocks.
    is_explore = (block_type == "familiarization" and block_number == 1)
    show_timer = not is_explore
    show_score = (block_type == "practice")

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
            result = run_explore_trial(
                screen, clock, fonts, trial, config,
                cumulative_score, session_id,
                total_trials=n_trials,
                block_type=block_type,
                session_state=session_state,
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

    # Show reflection after practice blocks for MI groups
    is_mi       = group.startswith("MI")
    is_practice = block_type == "practice"
    if is_mi and is_practice:
        is_last = (session_number == 3)
        run_reflection(screen, clock, fonts, participant_id,
                       session_number, is_last_session=is_last)

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

    for block_idx, block_type in enumerate(block_sequence):
        if block_idx + 1 < start_from_block:
            continue   # already completed or researcher chose to skip
        result = run_block(
            screen         = screen,
            clock          = clock,
            fonts          = fonts,
            block_type     = block_type,
            block_number   = block_idx + 1,
            participant_id = participant_id,
            session_number = session_number,
            group          = group,
            config         = config,
            pool           = pool,
            repeated_puzzle= repeated_puzzle,
            cumulative_score = cumulative_score,
        )

        if result == "exited":
            return   # participant exited mid-session

        cumulative_score, repeated_puzzle = result

        # Show information slide between blocks (not after the last one)
        if block_idx < len(block_sequence) - 1:
            next_block = block_sequence[block_idx + 1]
            _show_break(screen, clock, fonts,
                        completed_block=block_type,
                        next_block=next_block,
                        block_num=block_idx + 1,
                        total_blocks=len(block_sequence))

    _show_session_complete(screen, clock, fonts, session_number, cumulative_score)


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

    # Card width — slightly wider than original to fit larger fonts
    CW = min(W - 80, 660)
    max_body_w = CW - 56

    # Word-wrap body text so long lines never overflow the card
    def _wrap(text):
        if not text:
            return [""]
        words, out, cur = text.split(), [], ""
        for w in words:
            test = (cur + " " + w).strip()
            if f_sm.size(test)[0] <= max_body_w:
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

    # Compute card height from actual font sizes
    f_big_h = f_big.get_height()
    f_sm_h  = f_sm.get_height()
    f_xs_h  = f_xs.get_height()
    line_h  = f_sm_h + 8
    badge_h = (f_xs_h + 10 + 10) if badge else 0
    CH = max(240, 16 + badge_h + f_big_h + 14 + 12 + len(wrapped) * line_h + f_sm_h + 24)

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

        # Title
        ts = f_big.render(title, True, WHITE)
        screen.blit(ts, (CX - ts.get_width() // 2, y))
        y += f_big_h + 14

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
    if block_type == "familiarization" and block_number == 1:
        desc = ("Explore the grid freely! Press 1, 2, or 3 on the keypad to move the mouse. "
                "When you reach the cheese the next trial starts automatically. "
                "No timer, no score — just learn how the keys move the cursor.")
    elif block_type == "familiarization":
        desc = ("Now you will plan first, then act. Study the grid for 6 seconds, enter your "
                "sequence, then physically press the keys on the keypad. "
                "Press SPACE when you are done. No score shown.")
    else:
        desc = {
            "pre_test":  ("Baseline test. 6-second planning timer. Enter your sequence, "
                          "then execute it on the keypad. No score shown."),
            "practice":  ("Practice block. 6-second planning timer. Enter your sequence, "
                          "execute it on the keypad, then see your score and replay."),
            "post_test": ("Final test. 6-second planning timer. Enter your sequence, "
                          "then execute it on the keypad. No score shown."),
        }.get(block_type, "")

    badge = f"Session {session_number}  ·  Block {block_number}  ·  {group}"
    lines = [(desc, DIM)]
    _card_screen(screen, clock, fonts,
                 title=block_type.replace("_", " ").title(),
                 title_col=ACCENT, badge=badge, lines=lines,
                 hint_text="Press  SPACE  to begin")


def _show_break(screen, clock, fonts,
                completed_block, next_block, block_num, total_blocks):
    """Information slide shown between blocks."""
    next_descriptions = {
        "familiarization": "The next block is another familiarization. Continue exploring at your own pace.",
        "pre_test":        "Next is a baseline test. Plan your route carefully — no score will be shown.",
        "practice":        "Next is a practice block. Follow your assigned condition. Score will be shown after each trial.",
        "post_test":       "Next is the final performance test. No score will be shown.",
    }
    completed_label = completed_block.replace("_", " ").title()
    next_label      = next_block.replace("_", " ").title()
    lines = [
        (f"{completed_label} complete.  Block {block_num} of {total_blocks}.", GREEN),
        ("", DIM),
        (next_descriptions.get(next_block, f"Next: {next_label}"), DIM),
    ]
    _card_screen(screen, clock, fonts,
                 title="Take a Short Break",
                 title_col=GREEN, badge=None, lines=lines,
                 hint_text="Press  SPACE  when you are ready to continue")


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
            ("MOUSE to a piece of CHEESE in as few steps as possible.", DIM),
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
            ("Plan the shortest path, then enter it using the keypad.", DIM),
        ],
    )

    # Slide 3 — Repeated vs Random
    _slide(
        "Two Types of Grid",
        AMBER, "Grid types",
        [
            ("REPEATED  —  the same puzzle appears many times.", WHITE),
            ("RANDOM    —  a new puzzle each time.", DIM),
            ("", DIM),
            ("Learning the repeated puzzle is part of the experiment.", DIM),
        ],
    )

    # Slide 4 — How to enter a sequence
    # ── EDIT INSTRUCTIONS HERE ──────────────────────────────────────────
    # This is the slide that explains how to enter a movement sequence.
    # Change the text strings in the list below to update what participants see.
    # ────────────────────────────────────────────────────────────────────
    _slide(
        "Entering Your Plan",
        ACCENT, None,
        [
            ("You have 6 seconds to study the grid and plan your route.", DIM),
            ("Then the grid hides — click  1 / 2 / 3  or press the keypad", DIM),
            ("to enter your sequence.", DIM),
            ("Press  Confirm  when done. You will then execute the plan.", DIM),
        ],
    )

    # Slide 5 — Scoring (only relevant for practice)
    _slide(
        "Scoring",
        GREEN, None,
        [
            ("You earn points for reaching the CHEESE.", DIM),
            ("Extra moves beyond the shortest path reduce your score.", DIM),
            ("Scores are shown during practice blocks only.", DIM),
            ("", DIM),
            (f"Your assigned condition:  {group}", WHITE),
        ],
        hint="Press  SPACE  to start",
    )


def _show_session_complete(screen, clock, fonts, session_number, total_score):
    next_msg = (f"Please return for Session {session_number + 1}."
                if session_number < 3
                else "You have completed all 3 sessions. Thank you!")
    lines = [
        (f"Total score:  {total_score}", AMBER),
        (next_msg,                       DIM),
    ]
    _card_screen(screen, clock, fonts,
                 title=f"Session {session_number} Complete!",
                 title_col=GREEN, badge=None, lines=lines,
                 hint_text="Press  ESC  to exit", hint_col=DIM)
