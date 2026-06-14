# ============================================================
#  GRID-SAILING TASK — Session Manager
#
#  Manages the full session flow: which blocks run in order,
#  which puzzles get assigned (repeated vs random),
#  and auto-resume after a crash.
#
#  A session contains an ordered list of blocks.
#  Each block contains a fixed number of trials.
#  Trial puzzles are drawn from the pre-generated puzzle pool.
# ============================================================

import pygame
import random
from config import (
    SESSION_STRUCTURE, TRIALS_PER_BLOCK, GRID_SIZE,
    PRACTICE_REPEATED_RATIO, TEST_REPEATED_RATIO,
    FAMILIARIZATION_REPEATED_RATIO, FPS
)
from core.grid import find_valid_paths, apply_key
from core.trial import TrialData, run_trial
from database.db import (
    create_session, complete_session,
    get_resume_point, initialise_database
)


# ── Puzzle pool ──────────────────────────────────────────────

def build_puzzle_pool():
    """
    Generate all valid puzzles from all 25 start positions.
    Returns a list of puzzle dicts filtered to optimal length <= MAX_OPTIMAL.

    Each puzzle dict has:
        start, goal, sequence (optimal), length (optimal)
    """
    from config import MAX_OPTIMAL_LENGTH
    pool = []
    for r in range(GRID_SIZE):
        for c in range(GRID_SIZE):
            puzzles = find_valid_paths(r, c)
            for p in puzzles:
                # Keep only puzzles where the optimal is at most MAX_OPTIMAL_LENGTH
                if p["length"] <= MAX_OPTIMAL_LENGTH:
                    pool.append(p)
    print(f"[SESSION] Puzzle pool built: {len(pool)} valid puzzles.")
    return pool


def _pick_puzzles(pool, n_trials, repeated_ratio, repeated_puzzle=None):
    """
    Select n_trials puzzles with the correct repeated:random ratio.

    Args:
        pool (list):            Full puzzle pool.
        n_trials (int):         How many puzzles to return.
        repeated_ratio (float): Fraction of trials that should be the repeated puzzle.
        repeated_puzzle (dict): The fixed puzzle to reuse for repeated trials.
                                If None, one is chosen randomly from the pool.

    Returns:
        list of (puzzle_dict, grid_type_str) tuples, shuffled.
    """
    if repeated_puzzle is None:
        repeated_puzzle = random.choice(pool)

    n_repeated = round(n_trials * repeated_ratio)
    n_random   = n_trials - n_repeated

    # Repeated trials all use the same puzzle
    trials = [
        (repeated_puzzle, "repeated") for _ in range(n_repeated)
    ]

    # Random trials use random puzzles (different from the repeated one)
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

    trials_list, repeated_puzzle = _pick_puzzles(
        pool, n_trials, ratio, repeated_puzzle
    )

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

    for i, (puzzle, grid_type) in enumerate(trials_list):
        trial_number = i + 1
        if trial_number <= resume_from_trial:
            continue   # skip already-completed trials

        trial = TrialData(
            session_id       = session_id,
            participant_id   = participant_id,
            trial_number     = trial_number,
            grid_type        = grid_type,
            start            = tuple(puzzle["start"]),
            goal             = tuple(puzzle["goal"]),
            optimal_sequence = puzzle["sequence"],
            group            = group,
        )

        result = run_trial(
            screen, clock, fonts, trial, config,
            cumulative_score, session_id
        )
        cumulative_score = result["cumulative_score"]

    complete_session(session_id)
    return cumulative_score, repeated_puzzle


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

    block_sequence  = SESSION_STRUCTURE.get(session_number, [])
    cumulative_score = 0
    repeated_puzzle  = None   # fixed across the whole session

    for block_idx, block_type in enumerate(block_sequence):
        cumulative_score, repeated_puzzle = run_block(
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

        # Show break screen between blocks (not after the last one)
        if block_idx < len(block_sequence) - 1:
            _show_break(screen, clock, fonts, block_idx + 1, len(block_sequence))

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


def _show_block_intro(screen, clock, fonts, block_type, block_number,
                      session_number, group, config):
    """
    Show a brief intro card before each block starts.
    Researcher or participant presses SPACE to begin.
    """
    f_big, f_med, f_sm, f_xs = fonts
    cx = screen.get_width() // 2

    descriptions = {
        "familiarization": "Learn the key-finger mappings through physical practice.\nNo score will be shown during this block.",
        "pre_test":        "Baseline performance test.\nPhysically press your planned sequence. No score shown.",
        "practice":        "Practice block. Follow your assigned condition.\nFeedback will appear after each trial.",
        "post_test":       "Final performance test.\nPhysically press your planned sequence. No score shown.",
    }

    waiting = True
    while waiting:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); import sys; sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                waiting = False

        screen.fill((15, 15, 25))

        title = f_big.render(block_type.replace("_", " ").title(), True, (235, 235, 245))
        screen.blit(title, (cx - title.get_width() // 2, 180))

        sub = f_sm.render(f"Session {session_number}  |  Block {block_number}  |  Group: {group}",
                          True, (90, 150, 255))
        screen.blit(sub, (cx - sub.get_width() // 2, 235))

        desc_lines = descriptions.get(block_type, "").split("\n")
        y = 290
        for line in desc_lines:
            d = f_sm.render(line, True, (110, 110, 145))
            screen.blit(d, (cx - d.get_width() // 2, y))
            y += 28

        hint = f_sm.render("Press  SPACE  to begin", True, (90, 150, 255))
        screen.blit(hint, (cx - hint.get_width() // 2, 420))

        pygame.display.flip()
        clock.tick(FPS)


def _show_break(screen, clock, fonts, completed_blocks, total_blocks):
    """
    Show a break screen between blocks. Participant can rest.
    Press SPACE when ready to continue.
    """
    f_big, f_med, f_sm, f_xs = fonts
    cx = screen.get_width() // 2

    waiting = True
    while waiting:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); import sys; sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                waiting = False

        screen.fill((15, 15, 25))

        title = f_big.render("Take a Break", True, (235, 235, 245))
        screen.blit(title, (cx - title.get_width() // 2, 180))

        prog = f_sm.render(f"Block {completed_blocks} of {total_blocks} complete.",
                           True, (70, 190, 110))
        screen.blit(prog, (cx - prog.get_width() // 2, 250))

        hint = f_sm.render("Press  SPACE  when you are ready to continue.",
                            True, (90, 150, 255))
        screen.blit(hint, (cx - hint.get_width() // 2, 370))

        pygame.display.flip()
        clock.tick(FPS)


def _show_session_complete(screen, clock, fonts, session_number, total_score):
    """End-of-session screen shown after all blocks are done."""
    f_big, f_med, f_sm, f_xs = fonts
    cx = screen.get_width() // 2

    waiting = True
    while waiting:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); import sys; sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                waiting = False

        screen.fill((15, 15, 25))

        title = f_big.render(f"Session {session_number} Complete!", True, (70, 190, 110))
        screen.blit(title, (cx - title.get_width() // 2, 180))

        score_lbl = f_med.render(f"Total Score:  {total_score}", True, (210, 160, 30))
        screen.blit(score_lbl, (cx - score_lbl.get_width() // 2, 260))

        if session_number < 3:
            next_msg = f"Please return for Session {session_number + 1}."
        else:
            next_msg = "You have completed all 3 sessions. Thank you!"

        next_surf = f_sm.render(next_msg, True, (110, 110, 145))
        screen.blit(next_surf, (cx - next_surf.get_width() // 2, 330))

        esc = f_xs.render("Press ESC to exit", True, (60, 60, 90))
        screen.blit(esc, (cx - esc.get_width() // 2, screen.get_height() - 40))

        pygame.display.flip()
        clock.tick(FPS)
