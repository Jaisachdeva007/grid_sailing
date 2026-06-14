# ============================================================
#  GRID-SAILING TASK — Trial State Machine
#
#  States:
#    PLANNING  → grid shown, countdown ticking
#    INPUT     → participant types planned sequence (keys 1/2/3)
#    ACTION    → physical practice / motor imagery / control
#    FEEDBACK  → animated replay + score, SPACE to continue
#    ITI       → blank intertrial interval
#    DONE      → trial complete, data saved
#
#  All key press events (PP group) written to SQLite immediately.
# ============================================================

import pygame
import time
from dataclasses import dataclass, field
from typing import Optional

from config import OPTIMAL_SCORE, EXTRA_MOVE_PENALTY, ERROR_SCORE
from core.grid import apply_key
from database.db import save_trial, save_keypress, update_session_progress

# ── State constants ──────────────────────────────────────────
PLANNING = "planning"
INPUT    = "input"
ACTION   = "action"
FEEDBACK = "feedback"
ITI      = "iti"
DONE     = "done"

# ── Colours ──────────────────────────────────────────────────
BG          = (15,  15,  25)
PANEL_BG    = (22,  22,  38)
CELL_DARK   = (32,  32,  52)
CELL_TRAIL  = (45,  80, 150)
CELL_REPLAY = (70, 120, 200)
GRID_LINE   = (48,  48,  72)
START_COL   = (200,  50,  50)
GOAL_COL    = (210, 160,  30)
CURSOR_COL  = (255, 255, 255)
WHITE       = (235, 235, 245)
DIM         = (110, 110, 145)
ACCENT      = ( 90, 155, 255)
GREEN       = ( 65, 200, 110)
ORANGE      = (230, 140,  50)
RED         = (215,  60,  60)
PROGRESS_BG = (30,  30,  50)
PROGRESS_FG = (70, 130, 220)

# ── Layout ───────────────────────────────────────────────────
GRID_SIZE = 5
CELL      = 90
LEFT      = 60
TOP       = 175
RIGHT_X   = LEFT + CELL * GRID_SIZE + 55    # x start of right panel  (= 565)
RIGHT_W   = 480                              # right panel width


@dataclass
class TrialData:
    """All data collected during a single trial."""
    session_id:       int
    participant_id:   str
    trial_number:     int
    grid_type:        str        # "repeated" or "random"
    start:            tuple      # (row, col)
    goal:             tuple      # (row, col)
    optimal_sequence: list
    group:            str        # MI-High, PP-Low, CTRL-High …

    planned_sequence:    list  = field(default_factory=list)
    keypresses_log:      list  = field(default_factory=list)
    reaction_time_ms:    Optional[float] = None
    movement_time_ms:    Optional[float] = None
    imagery_duration_ms: Optional[float] = None
    reward_score:        int   = 0
    number_of_moves:     int   = 0
    is_correct:          bool  = False
    trial_start_time:    float = 0.0


def _is_mi(g):   return g.startswith("MI")
def _is_pp(g):   return g.startswith("PP")
def _is_ctrl(g): return g.startswith("CTRL")


def _calculate_score(planned_seq, optimal_seq, cursor_end, goal):
    n_moves   = len(planned_seq)
    n_optimal = len(optimal_seq)
    correct   = (cursor_end == goal)
    if not correct:
        return ERROR_SCORE, n_moves, False
    extra = max(0, n_moves - n_optimal)
    score = max(0, OPTIMAL_SCORE - extra * EXTRA_MOVE_PENALTY)
    return score, n_moves, True


# ── Helpers ──────────────────────────────────────────────────

def draw_text(screen, font, text, color, x, y):
    surf = font.render(text, True, color)
    screen.blit(surf, (x, y))
    return surf

def draw_centered(screen, font, text, color, y):
    surf = font.render(text, True, color)
    screen.blit(surf, (screen.get_width() // 2 - surf.get_width() // 2, y))
    return surf


def _build_path(start, sequence):
    """Simulate cursor positions for a key sequence."""
    pos  = start
    path = [pos]
    for k in sequence:
        nxt = apply_key(pos[0], pos[1], k)
        pos = nxt if nxt else pos
        path.append(pos)
    return path


def _draw_progress_bar(screen, fonts, trial, total_trials, block_type, session_number):
    """Top progress bar: trial counter + block info + session."""
    f_big, f_med, f_sm, f_xs = fonts
    W = screen.get_width()

    # Background strip
    pygame.draw.rect(screen, PROGRESS_BG, (0, 0, W, 44))

    # Progress fill
    pct  = (trial.trial_number - 1) / max(total_trials, 1)
    pygame.draw.rect(screen, PROGRESS_FG, (0, 0, int(W * pct), 44))
    pygame.draw.rect(screen, (60, 60, 90), (0, 43, W, 1))  # bottom border

    # Left: trial counter
    label = f_sm.render(f"Trial  {trial.trial_number}  /  {total_trials}", True, WHITE)
    screen.blit(label, (LEFT, 44 // 2 - label.get_height() // 2))

    # Centre: block name
    blk = f_sm.render(block_type.replace("_", " ").title(), True, ACCENT)
    screen.blit(blk, (W // 2 - blk.get_width() // 2, 44 // 2 - blk.get_height() // 2))

    # Right: session
    sess = f_sm.render(f"Session  {session_number}", True, DIM)
    screen.blit(sess, (W - LEFT - sess.get_width(), 44 // 2 - sess.get_height() // 2))

    # Grid-type badge
    badge_col = ACCENT if trial.grid_type == "repeated" else ORANGE
    badge = f_xs.render(f"  {trial.grid_type.upper()}  ", True, BG)
    bw = badge.get_width() + 4
    bx = W // 2 + blk.get_width() // 2 + 14
    pygame.draw.rect(screen, badge_col, (bx, 10, bw, 24), border_radius=4)
    screen.blit(badge, (bx + 2, 11))


def _draw_grid(screen, fonts, trial: TrialData, trail: set, cursor: tuple):
    """Render the 5×5 grid — no right-panel content here."""
    f_big, f_med, f_sm, f_xs = fonts
    start, goal = trial.start, trial.goal

    for r in range(GRID_SIZE):
        for c in range(GRID_SIZE):
            x    = LEFT + c * CELL + 4
            y    = TOP  + r * CELL + 4
            rect = pygame.Rect(x, y, CELL - 8, CELL - 8)

            if (r, c) == goal:
                col = GOAL_COL
            elif (r, c) in trail:
                col = CELL_TRAIL
            elif (r, c) == start:
                col = START_COL
            else:
                col = CELL_DARK

            pygame.draw.rect(screen, col, rect, border_radius=10)
            pygame.draw.rect(screen, GRID_LINE, rect, width=1, border_radius=10)

            # Labels on start and goal only
            if (r, c) == start:
                lbl = f_xs.render("MOUSE", True, WHITE)
                screen.blit(lbl, (x + (CELL-8)//2 - lbl.get_width()//2,
                                   y + (CELL-8)//2 - lbl.get_height()//2))
            elif (r, c) == goal:
                lbl = f_xs.render("CHEESE", True, (40, 30, 5))
                screen.blit(lbl, (x + (CELL-8)//2 - lbl.get_width()//2,
                                   y + (CELL-8)//2 - lbl.get_height()//2))

    # Cursor dot
    if cursor:
        cx = LEFT + cursor[1] * CELL + CELL // 2
        cy = TOP  + cursor[0] * CELL + CELL // 2
        pygame.draw.circle(screen, CURSOR_COL, (cx, cy), 18)
        pygame.draw.circle(screen, ACCENT,     (cx, cy), 18, 3)
        pygame.draw.circle(screen, BG,         (cx, cy), 7)


def _draw_key_legend(screen, fonts, y):
    """Key mapping legend drawn on the right panel."""
    f_big, f_med, f_sm, f_xs = fonts
    draw_text(screen, f_xs, "KEY  MAPPINGS", DIM, RIGHT_X, y);  y += 22
    pygame.draw.line(screen, GRID_LINE, (RIGHT_X, y), (RIGHT_X + RIGHT_W - 20, y)); y += 10
    for key, finger, move in [
        ("1", "Index",  "Up"),
        ("2", "Middle", "Down-Right"),
        ("3", "Ring",   "Down-Left"),
    ]:
        draw_text(screen, f_sm, f"Key {key}", ACCENT,  RIGHT_X,      y)
        draw_text(screen, f_xs, finger,       WHITE,   RIGHT_X + 68, y)
        draw_text(screen, f_xs, f"— {move}",  DIM,    RIGHT_X + 140, y)
        y += 26
    return y


# ── Main trial runner ────────────────────────────────────────

def run_trial(screen, clock, fonts, trial: TrialData, config: dict,
              cumulative_score: int, session_id: int,
              total_trials: int = 20, block_type: str = "practice") -> dict:
    """
    Run one complete trial and return the result.

    Returns:
        dict: reward_score, is_correct, cumulative_score, trial_id
    """
    f_big, f_med, f_sm, f_xs = fonts

    state            = PLANNING
    planning_start   = time.time()
    first_key_time   = None
    last_key_time    = None
    spacebar_down_t  = None
    cursor           = trial.start
    trail            = set()
    typed_seq        = []
    action_path      = []   # positions from typed sequence
    feedback_start   = None
    iti_start        = None
    trial_id         = None
    blink_visible    = True
    blink_timer      = pygame.time.get_ticks()

    # Feedback animated replay
    replay_step      = 0
    replay_timer     = 0
    replay_cursor    = trial.start
    replay_trail     = set()
    replay_done      = False

    trial.trial_start_time = time.time()

    group   = trial.group
    is_mi   = _is_mi(group)
    is_pp   = _is_pp(group)
    is_ctrl = _is_ctrl(group)

    planning_time   = config.get("planning_time",   6)
    action_time     = config.get("action_time",     10)
    feedback_time   = config.get("feedback_time",   4)    # minimum seconds before SPACE works
    intertrial_time = config.get("intertrial_time", 4)
    replay_delay_ms = 550   # ms between each replay step

    session_number  = config.get("session_number", 1)

    while True:
        now_ms  = pygame.time.get_ticks()
        now_s   = time.time()
        elapsed = now_s - planning_start
        events  = pygame.event.get()

        for event in events:
            if event.type == pygame.QUIT:
                pygame.quit()
                import sys; sys.exit()

            # ── PLANNING: SPACE to skip straight to input ────
            if state == PLANNING and event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    state = INPUT
                    typed_seq      = []
                    first_key_time = None

            # ── INPUT: type sequence with 1/2/3 ─────────────
            elif state == INPUT and event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_1, pygame.K_KP1):
                    if first_key_time is None:
                        first_key_time = time.time()
                    typed_seq.append(1)
                elif event.key in (pygame.K_2, pygame.K_KP2):
                    if first_key_time is None:
                        first_key_time = time.time()
                    typed_seq.append(2)
                elif event.key in (pygame.K_3, pygame.K_KP3):
                    if first_key_time is None:
                        first_key_time = time.time()
                    typed_seq.append(3)
                elif event.key == pygame.K_BACKSPACE and typed_seq:
                    typed_seq.pop()
                elif event.key == pygame.K_RETURN and typed_seq:
                    if first_key_time:
                        trial.reaction_time_ms = (first_key_time - planning_start) * 1000
                    trial.planned_sequence = list(typed_seq)
                    action_path = _build_path(trial.start, typed_seq)

                    if is_ctrl:
                        _finalise_trial(trial, typed_seq, session_id)
                        trial_id = _save_trial_to_db(trial, session_id)
                        update_session_progress(session_id, trial.trial_number)
                        state          = FEEDBACK
                        feedback_start = time.time()
                        replay_step    = 0
                        replay_timer   = now_ms
                        replay_cursor  = trial.start
                        replay_trail   = set()
                    else:
                        state        = ACTION
                        cursor       = trial.start
                        trail        = set()
                        if is_mi:
                            spacebar_down_t = None

            # ── ACTION: PP — each key press moves cursor ─────
            elif state == ACTION and is_pp and event.type == pygame.KEYDOWN:
                key_map = {pygame.K_1: 1, pygame.K_KP1: 1,
                           pygame.K_2: 2, pygame.K_KP2: 2,
                           pygame.K_3: 3, pygame.K_KP3: 3}
                if event.key in key_map:
                    key         = key_map[event.key]
                    prev_cursor = cursor
                    nxt         = apply_key(cursor[0], cursor[1], key)
                    if nxt:
                        trail.add(cursor)
                        cursor = nxt

                    t_now   = time.time()
                    abs_ms  = t_now * 1000
                    rel_ms  = (t_now - trial.trial_start_time) * 1000
                    iki_ms  = ((t_now - last_key_time) * 1000) if last_key_time else None
                    last_key_time = t_now
                    if first_key_time is None:
                        first_key_time = t_now

                    trial.keypresses_log.append({
                        "key":    key,
                        "before": prev_cursor,
                        "after":  cursor,
                        "abs_ms": abs_ms,
                        "rel_ms": rel_ms,
                        "iki_ms": iki_ms,
                    })

                elif event.key == pygame.K_SPACE:
                    if last_key_time and first_key_time:
                        trial.movement_time_ms = (last_key_time - first_key_time) * 1000
                    _finalise_trial(trial, trial.planned_sequence, session_id)
                    trial_id = _save_trial_to_db(trial, session_id)
                    update_session_progress(session_id, trial.trial_number)
                    state          = FEEDBACK
                    feedback_start = time.time()
                    replay_step    = 0
                    replay_timer   = now_ms
                    replay_cursor  = trial.start
                    replay_trail   = set()

            # ── ACTION: MI — hold SPACEBAR ───────────────────
            elif state == ACTION and is_mi:
                if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                    spacebar_down_t = time.time()
                if event.type == pygame.KEYUP and event.key == pygame.K_SPACE:
                    if spacebar_down_t:
                        trial.imagery_duration_ms = (time.time() - spacebar_down_t) * 1000
                    _finalise_trial(trial, trial.planned_sequence, session_id)
                    trial_id = _save_trial_to_db(trial, session_id)
                    update_session_progress(session_id, trial.trial_number)
                    state          = FEEDBACK
                    feedback_start = time.time()
                    replay_step    = 0
                    replay_timer   = now_ms
                    replay_cursor  = trial.start
                    replay_trail   = set()

            # ── FEEDBACK: SPACE to advance early ─────────────
            elif state == FEEDBACK and event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    elapsed_fb = time.time() - feedback_start
                    if elapsed_fb >= 1.5:   # at least 1.5s must have passed
                        state     = ITI
                        iti_start = time.time()

        # ── Auto-advance planning timer ──────────────────────
        if state == PLANNING and elapsed >= planning_time:
            state = INPUT
            typed_seq      = []
            first_key_time = None

        # ── MI timeout ───────────────────────────────────────
        if state == ACTION and is_mi:
            if (time.time() - planning_start) > planning_time + action_time + 5:
                trial.imagery_duration_ms = action_time * 1000
                _finalise_trial(trial, trial.planned_sequence, session_id)
                trial_id = _save_trial_to_db(trial, session_id)
                update_session_progress(session_id, trial.trial_number)
                state          = FEEDBACK
                feedback_start = time.time()
                replay_step    = 0
                replay_timer   = now_ms
                replay_cursor  = trial.start
                replay_trail   = set()

        # ── Animate replay during feedback ───────────────────
        if state == FEEDBACK and not replay_done:
            if now_ms - replay_timer >= replay_delay_ms:
                replay_timer = now_ms
                if replay_step < len(action_path) - 1:
                    replay_trail.add(replay_cursor)
                    replay_step += 1
                    replay_cursor = action_path[replay_step]
                else:
                    replay_done = True

        # ── Auto-advance feedback after minimum time ─────────
        if state == FEEDBACK and feedback_start:
            if time.time() - feedback_start >= feedback_time and replay_done:
                state     = ITI
                iti_start = time.time()

        # ── Auto-advance ITI ─────────────────────────────────
        if state == ITI and iti_start:
            if time.time() - iti_start >= intertrial_time:
                state = DONE

        if state == DONE:
            break

        # ── Blink cursor ─────────────────────────────────────
        if now_ms - blink_timer > 500:
            blink_visible = not blink_visible
            blink_timer   = now_ms

        # ── Draw ─────────────────────────────────────────────
        screen.fill(BG)

        if state == PLANNING:
            _draw_planning(screen, fonts, trial, elapsed, planning_time,
                           total_trials, block_type, session_number)

        elif state == INPUT:
            _draw_input(screen, fonts, trial, typed_seq, blink_visible,
                        total_trials, block_type, session_number)

        elif state == ACTION:
            _draw_action(screen, fonts, trial, cursor, trail,
                         typed_seq, is_mi, is_pp, spacebar_down_t,
                         total_trials, block_type, session_number)

        elif state == FEEDBACK:
            _draw_feedback(screen, fonts, trial, cumulative_score,
                           replay_cursor, replay_trail, replay_done,
                           total_trials, block_type, session_number)

        elif state == ITI:
            screen.fill(BG)

        pygame.display.flip()
        clock.tick(60)

    # ── Save PP keypresses to DB ─────────────────────────────
    if is_pp and trial_id and trial.keypresses_log:
        for kp in trial.keypresses_log:
            save_keypress(
                trial_id                  = trial_id,
                participant_id            = trial.participant_id,
                key_pressed               = kp["key"],
                cursor_row_before         = kp["before"][0],
                cursor_col_before         = kp["before"][1],
                cursor_row_after          = kp["after"][0],
                cursor_col_after          = kp["after"][1],
                timestamp_ms              = kp["abs_ms"],
                time_since_trial_start_ms = kp["rel_ms"],
                time_since_last_press_ms  = kp["iki_ms"],
            )

    return {
        "reward_score":     trial.reward_score,
        "is_correct":       trial.is_correct,
        "cumulative_score": cumulative_score + trial.reward_score,
        "trial_id":         trial_id,
    }


# ── Trial finalisation ────────────────────────────────────────

def _finalise_trial(trial: TrialData, used_seq, session_id):
    """Calculate score and fill final trial fields."""
    pos = trial.start
    for k in used_seq:
        nxt = apply_key(pos[0], pos[1], k)
        if nxt:
            pos = nxt
    score, n_moves, correct = _calculate_score(
        used_seq, trial.optimal_sequence, pos, trial.goal
    )
    trial.reward_score    = score
    trial.number_of_moves = n_moves
    trial.is_correct      = correct

    if trial.movement_time_ms is None and len(trial.keypresses_log) >= 2:
        trial.movement_time_ms = (
            trial.keypresses_log[-1]["abs_ms"] - trial.keypresses_log[0]["abs_ms"]
        )


def _save_trial_to_db(trial: TrialData, session_id: int) -> int:
    elapsed = time.time() - trial.trial_start_time
    return save_trial(
        session_id          = session_id,
        participant_id      = trial.participant_id,
        trial_number        = trial.trial_number,
        grid_type           = trial.grid_type,
        start_row           = trial.start[0],
        start_col           = trial.start[1],
        goal_row            = trial.goal[0],
        goal_col            = trial.goal[1],
        planned_sequence    = trial.planned_sequence,
        optimal_sequence    = trial.optimal_sequence,
        optimal_length      = len(trial.optimal_sequence),
        number_of_moves     = trial.number_of_moves,
        reward_score        = trial.reward_score,
        reaction_time_ms    = trial.reaction_time_ms,
        movement_time_ms    = trial.movement_time_ms,
        elapsed_time_s      = elapsed,
        imagery_duration_ms = trial.imagery_duration_ms,
        is_correct          = trial.is_correct,
    )


# ── Screen drawing functions ──────────────────────────────────

def _draw_planning(screen, fonts, trial, elapsed, planning_time,
                   total_trials, block_type, session_number):
    f_big, f_med, f_sm, f_xs = fonts
    remaining = max(0, planning_time - elapsed)
    timer_col = RED if remaining < 2 else (ORANGE if remaining < 4 else WHITE)

    _draw_progress_bar(screen, fonts, trial, total_trials, block_type, session_number)

    draw_text(screen, f_med, "PLANNING STAGE", ACCENT, LEFT, 56)
    draw_text(screen, f_xs,
              "Study the grid. Plan the shortest route from MOUSE to CHEESE.",
              DIM, LEFT, 88)
    draw_text(screen, f_xs, "Press SPACE when ready to enter sequence.", DIM, LEFT, 110)

    _draw_grid(screen, fonts, trial, set(), trial.start)

    # Right panel
    rx = RIGHT_X
    y  = TOP

    # Big countdown
    t_surf = f_big.render(f"{remaining:.1f}s", True, timer_col)
    screen.blit(t_surf, (rx, y))
    draw_text(screen, f_xs, "Time remaining", DIM, rx, y + t_surf.get_height() + 4)
    y += t_surf.get_height() + 36

    # Key legend
    _draw_key_legend(screen, fonts, y)


def _draw_input(screen, fonts, trial, typed_seq, blink_visible,
                total_trials, block_type, session_number):
    f_big, f_med, f_sm, f_xs = fonts

    _draw_progress_bar(screen, fonts, trial, total_trials, block_type, session_number)

    draw_text(screen, f_med, "ENTER YOUR SEQUENCE", WHITE, LEFT, 56)
    draw_text(screen, f_xs,
              "Press  1 / 2 / 3  to add keys.   BACKSPACE to undo.   ENTER to confirm.",
              DIM, LEFT, 88)

    _draw_grid(screen, fonts, trial, set(), trial.start)

    # ── Right panel — clearly separated from grid ────────────
    rx = RIGHT_X
    y  = TOP

    # Sequence display box
    box_h = 80
    pygame.draw.rect(screen, PANEL_BG, (rx, y, RIGHT_W - 20, box_h), border_radius=10)
    pygame.draw.rect(screen, ACCENT,   (rx, y, RIGHT_W - 20, box_h), width=1, border_radius=10)

    draw_text(screen, f_xs, "Your sequence", DIM, rx + 12, y + 8)

    seq_str  = "  →  ".join(str(k) for k in typed_seq) if typed_seq else ""
    seq_surf = f_sm.render(seq_str if seq_str else "—", True, WHITE if seq_str else DIM)
    screen.blit(seq_surf, (rx + 12, y + 30))

    if blink_visible and typed_seq:
        bx = rx + 12 + seq_surf.get_width() + 4
        pygame.draw.rect(screen, ACCENT, (bx, y + 30, 2, seq_surf.get_height()))

    draw_text(screen, f_xs, f"{len(typed_seq)} key(s)   ·   ENTER to confirm",
              DIM, rx + 12, y + box_h - 18)

    y += box_h + 28

    # Key legend
    _draw_key_legend(screen, fonts, y)


def _draw_action(screen, fonts, trial, cursor, trail,
                 typed_seq, is_mi, is_pp, spacebar_down_t,
                 total_trials, block_type, session_number):
    f_big, f_med, f_sm, f_xs = fonts

    _draw_progress_bar(screen, fonts, trial, total_trials, block_type, session_number)

    if is_mi:
        draw_text(screen, f_med, "ACTION STAGE — Motor Imagery", GREEN, LEFT, 56)
        draw_text(screen, f_xs,
                  "Hold SPACEBAR and vividly imagine pressing your sequence. Release when done.",
                  DIM, LEFT, 88)
        _draw_grid(screen, fonts, trial, set(), trial.start)

        rx = RIGHT_X
        y  = TOP
        held     = spacebar_down_t is not None
        held_dur = (time.time() - spacebar_down_t) if held else 0

        # Status indicator
        status_col = GREEN if held else DIM
        status_txt = f"Imagining...  {held_dur:.1f}s" if held else "Waiting for SPACEBAR"
        pygame.draw.rect(screen, PANEL_BG, (rx, y, RIGHT_W - 20, 60), border_radius=10)
        pygame.draw.rect(screen, status_col, (rx, y, RIGHT_W - 20, 60), width=1, border_radius=10)
        lbl = f_sm.render(status_txt, True, status_col)
        screen.blit(lbl, (rx + 12, y + 20))
        y += 80

        draw_text(screen, f_xs, "Hold SPACE  →  imagine sequence  →  release", DIM, rx, y)
        y += 44
        _draw_key_legend(screen, fonts, y)

    else:  # PP group
        draw_text(screen, f_med, "ACTION STAGE — Physical Practice", GREEN, LEFT, 56)
        draw_text(screen, f_xs,
                  "Press keys 1, 2, 3 to execute your sequence. SPACEBAR when done.",
                  DIM, LEFT, 88)
        _draw_grid(screen, fonts, trial, trail, cursor)

        rx = RIGHT_X
        y  = TOP
        draw_text(screen, f_sm, "LIVE SEQUENCE", ACCENT, rx, y); y += 28
        pygame.draw.line(screen, GRID_LINE, (rx, y), (rx + RIGHT_W - 20, y)); y += 12

        key_labels = {1: "^  Up", 2: "v>  Down-Right", 3: "v<  Down-Left"}
        for i, key in enumerate(typed_seq):
            draw_text(screen, f_xs, f"  {i+1}.  Key {key}  —  {key_labels[key]}",
                      ACCENT, rx, y)
            y += 24
        if not typed_seq:
            draw_text(screen, f_xs, "  (no sequence planned)", DIM, rx, y); y += 24
        y += 10
        draw_text(screen, f_xs, "SPACEBAR to finish", DIM, rx, y)


def _draw_feedback(screen, fonts, trial, cumulative_score,
                   replay_cursor, replay_trail, replay_done,
                   total_trials, block_type, session_number):
    f_big, f_med, f_sm, f_xs = fonts
    cx = screen.get_width() // 2
    W  = screen.get_width()

    _draw_progress_bar(screen, fonts, trial, total_trials, block_type, session_number)

    # Outcome title
    if trial.is_correct:
        title = "Reached the Cheese!"
        title_col = GOAL_COL
    else:
        title = "Missed the Goal"
        title_col = ORANGE

    t = f_big.render(title, True, title_col)
    screen.blit(t, (cx - t.get_width() // 2, 58))

    # ── Animated replay grid (left half) ─────────────────────
    _draw_grid(screen, fonts, trial, replay_trail, replay_cursor)

    # Replay label
    replay_lbl = f_xs.render(
        "Replaying your path..." if not replay_done else "Your path",
        True, DIM
    )
    screen.blit(replay_lbl, (LEFT, TOP + CELL * GRID_SIZE + 10))

    # Planned vs optimal sequences
    planned_str = "  →  ".join(str(k) for k in trial.planned_sequence) or "—"
    optimal_str = "  →  ".join(str(k) for k in trial.optimal_sequence)
    draw_text(screen, f_xs, f"Your sequence:    {planned_str}", DIM, LEFT, TOP + CELL * GRID_SIZE + 36)
    draw_text(screen, f_xs, f"Optimal:            {optimal_str}", DIM, LEFT, TOP + CELL * GRID_SIZE + 56)

    # ── Score stats (right half) ──────────────────────────────
    rx = RIGHT_X
    ry = TOP + 20

    new_total = cumulative_score + trial.reward_score

    stats = [
        ("Moves used",  str(trial.number_of_moves), WHITE),
        ("Optimal",     str(len(trial.optimal_sequence)), ACCENT),
        ("Trial score", str(trial.reward_score), title_col),
        ("Total score", str(new_total), GREEN),
    ]

    for label, val, col in stats:
        box = pygame.Rect(rx, ry, RIGHT_W - 20, 60)
        pygame.draw.rect(screen, PANEL_BG, box, border_radius=10)
        pygame.draw.rect(screen, col, box, width=1, border_radius=10)
        lbl_surf  = f_xs.render(label, True, DIM)
        val_surf  = f_med.render(val,   True, col)
        screen.blit(lbl_surf, (rx + 16, ry + 8))
        screen.blit(val_surf, (rx + 16, ry + 26))
        ry += 72

    # SPACE hint at bottom
    hint_col = WHITE if replay_done else DIM
    hint = f_xs.render("SPACE  —  next trial", True, hint_col)
    screen.blit(hint, (cx - hint.get_width() // 2, W - 36 if W > 700 else screen.get_height() - 36))
    # Actually use screen height
    hint_y = screen.get_height() - 38
    screen.blit(hint, (cx - hint.get_width() // 2, hint_y))
