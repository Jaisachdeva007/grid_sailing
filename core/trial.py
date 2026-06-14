# ============================================================
#  GRID-SAILING TASK — Trial State Machine
#
#  Handles one complete trial from planning through to feedback.
#  States:
#    PLANNING  → grid shown, countdown ticking
#    INPUT     → participant types planned sequence
#    ACTION    → physical practice / motor imagery / control
#    FEEDBACK  → score shown briefly
#    ITI       → blank intertrial interval
#    DONE      → trial complete, data saved
#
#  All key press events are written to SQLite immediately.
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
BG         = (15,  15,  25)
CELL_DARK  = (35,  35,  55)
CELL_TRAIL = (50,  85, 155)
GRID_LINE  = (50,  50,  75)
START_COL  = (200,  55,  55)
GOAL_COL   = (210, 160,  30)
CURSOR_COL = (255, 255, 255)
WHITE      = (235, 235, 245)
DIM        = (110, 110, 145)
ACCENT     = ( 90, 150, 255)
GREEN      = ( 70, 190, 110)
ORANGE     = (230, 140,  50)
RED        = (210,  65,  65)

# ── Layout ───────────────────────────────────────────────────
GRID_SIZE  = 5
CELL       = 86
LEFT       = 55
TOP        = 140
RIGHT_X    = LEFT + CELL * GRID_SIZE + 45


@dataclass
class TrialData:
    """Holds all data collected during a single trial."""
    session_id:       int
    participant_id:   str
    trial_number:     int
    grid_type:        str          # "repeated" or "random"
    start:            tuple        # (row, col)
    goal:             tuple        # (row, col)
    optimal_sequence: list
    group:            str          # MI-High, PP-Low, CTRL-High, etc.

    # Filled during the trial
    planned_sequence:    list = field(default_factory=list)
    keypresses_log:      list = field(default_factory=list)
    reaction_time_ms:    Optional[float] = None
    movement_time_ms:    Optional[float] = None
    imagery_duration_ms: Optional[float] = None
    reward_score:        int = 0
    number_of_moves:     int = 0
    is_correct:          bool = False
    trial_start_time:    float = 0.0


def _is_mi_group(group: str) -> bool:
    return group.startswith("MI")

def _is_pp_group(group: str) -> bool:
    return group.startswith("PP")

def _is_ctrl_group(group: str) -> bool:
    return group.startswith("CTRL")


def _calculate_score(planned_seq, optimal_seq, cursor_end, goal):
    """
    Calculate the reward score for a completed trial.

    Returns:
        (int, int, bool): reward_score, number_of_moves, is_correct
    """
    n_moves   = len(planned_seq)
    n_optimal = len(optimal_seq)
    correct   = (cursor_end == goal)

    if not correct:
        return ERROR_SCORE, n_moves, False

    extra = max(0, n_moves - n_optimal)
    score = max(0, OPTIMAL_SCORE - extra * EXTRA_MOVE_PENALTY)
    return score, n_moves, True


def _draw_grid(screen, fonts, trial: TrialData, trail: set,
               cursor: tuple, step_label: str = ""):
    """Render the 5x5 grid, cursor, trail, and right-panel info."""
    f_big, f_med, f_sm, f_xs = fonts
    start, goal = trial.start, trial.goal

    for r in range(GRID_SIZE):
        for c in range(GRID_SIZE):
            x = LEFT + c * CELL + 3
            y = TOP  + r * CELL + 3
            rect = pygame.Rect(x, y, CELL - 6, CELL - 6)

            if (r, c) == goal:
                col = GOAL_COL
            elif (r, c) == start:
                col = START_COL
            elif (r, c) in trail:
                col = CELL_TRAIL
            else:
                col = CELL_DARK

            pygame.draw.rect(screen, col, rect, border_radius=8)
            pygame.draw.rect(screen, GRID_LINE, rect, width=1, border_radius=8)

            # Labels
            if (r, c) == start:
                lbl = f_xs.render("MOUSE", True, WHITE)
                screen.blit(lbl, (x + (CELL - 6) // 2 - lbl.get_width() // 2,
                                   y + (CELL - 6) // 2 - lbl.get_height() // 2))
            elif (r, c) == goal:
                lbl = f_xs.render("CHEESE", True, (40, 30, 5))
                screen.blit(lbl, (x + (CELL - 6) // 2 - lbl.get_width() // 2,
                                   y + (CELL - 6) // 2 - lbl.get_height() // 2))

    # Cursor dot
    if cursor:
        cx = LEFT + cursor[1] * CELL + CELL // 2
        cy = TOP  + cursor[0] * CELL + CELL // 2
        pygame.draw.circle(screen, CURSOR_COL, (cx, cy), 16)
        pygame.draw.circle(screen, ACCENT,     (cx, cy), 16, 3)

    # Right panel — key legend
    y = TOP
    draw_text(screen, f_sm, "KEY MAPPINGS", ACCENT, RIGHT_X, y); y += 28
    pygame.draw.line(screen, GRID_LINE, (RIGHT_X, y), (RIGHT_X + 210, y)); y += 12
    for key, desc in [("1  ^", "Index — Up"),
                      ("2  v>", "Middle — Down-Right"),
                      ("3  v<", "Ring — Down-Left")]:
        draw_text(screen, f_xs, f"Key {key}", WHITE, RIGHT_X, y)
        draw_text(screen, f_xs, desc,         DIM,   RIGHT_X + 70, y)
        y += 22

    if step_label:
        draw_text(screen, f_xs, step_label, DIM, RIGHT_X, TOP + CELL * GRID_SIZE - 20)

    # Trial number badge
    draw_text(screen, f_xs,
              f"Trial  {trial.trial_number}   |   {trial.grid_type.capitalize()} grid",
              DIM, LEFT, TOP - 22)


def draw_text(screen, font, text, color, x, y):
    surf = font.render(text, True, color)
    screen.blit(surf, (x, y))
    return surf


def draw_centered(screen, font, text, color, y):
    surf = font.render(text, True, color)
    screen.blit(surf, (screen.get_width() // 2 - surf.get_width() // 2, y))
    return surf


# ── Main trial runner ────────────────────────────────────────

def run_trial(screen, clock, fonts, trial: TrialData, config: dict,
              cumulative_score: int, session_id: int) -> dict:
    """
    Run one complete trial and return the result.

    Args:
        screen:           Pygame display surface.
        clock:            Pygame clock.
        fonts:            Tuple of (f_big, f_med, f_sm, f_xs).
        trial:            TrialData object with puzzle info.
        config:           Session config dict from researcher setup.
        cumulative_score: Running total score before this trial.
        session_id:       DB session_id for this block.

    Returns:
        dict with keys: reward_score, is_correct, cumulative_score, trial_id
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
    action_step      = 0
    action_timer     = pygame.time.get_ticks()
    feedback_start   = None
    iti_start        = None
    trial_id         = None
    blink_visible    = True
    blink_timer      = pygame.time.get_ticks()

    trial.trial_start_time = time.time()

    group      = trial.group
    is_mi      = _is_mi_group(group)
    is_pp      = _is_pp_group(group)
    is_ctrl    = _is_ctrl_group(group)

    planning_time   = config.get("planning_time",   6)
    action_time     = config.get("action_time",     10)
    feedback_time   = config.get("feedback_time",   2)
    intertrial_time = config.get("intertrial_time", 4)
    anim_delay      = config.get("animation_delay_ms", 600)

    # ── Cursor path replay for action stage ─────────────────
    # Simulate where cursor goes if they typed a sequence
    action_path  = []

    while True:
        now_ms  = pygame.time.get_ticks()
        now_s   = time.time()
        elapsed = now_s - planning_start
        events  = pygame.event.get()

        for event in events:
            if event.type == pygame.QUIT:
                pygame.quit()
                import sys; sys.exit()

            # ── PLANNING: space to skip ahead ───────────────
            if state == PLANNING and event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    state = INPUT
                    typed_seq  = []
                    first_key_time = None

            # ── INPUT: type sequence ─────────────────────────
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
                    # Reaction time = grid shown → first key in input
                    if first_key_time:
                        trial.reaction_time_ms = (first_key_time - planning_start) * 1000
                    trial.planned_sequence = list(typed_seq)
                    # Build action path from typed sequence
                    pos = trial.start
                    action_path = [pos]
                    for k in typed_seq:
                        nxt = apply_key(pos[0], pos[1], k)
                        if nxt:
                            pos = nxt
                            action_path.append(pos)
                        else:
                            action_path.append(pos)  # stay if OOB
                    # CTRL skips action stage
                    if is_ctrl:
                        state = FEEDBACK
                        feedback_start = time.time()
                        _finalise_trial(trial, typed_seq, action_path, session_id)
                        trial_id = _save_trial_to_db(trial, session_id)
                        update_session_progress(session_id, trial.trial_number)
                    else:
                        state        = ACTION
                        action_step  = 0
                        action_timer = now_ms
                        cursor       = trial.start
                        trail        = set()
                        if is_mi:
                            spacebar_down_t = None

            # ── ACTION (PP): record each key press ──────────
            elif state == ACTION and is_pp and event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_1, pygame.K_KP1,
                                 pygame.K_2, pygame.K_KP2,
                                 pygame.K_3, pygame.K_KP3):
                    key_map = {pygame.K_1: 1, pygame.K_KP1: 1,
                               pygame.K_2: 2, pygame.K_KP2: 2,
                               pygame.K_3: 3, pygame.K_KP3: 3}
                    key = key_map[event.key]
                    prev_cursor = cursor
                    nxt = apply_key(cursor[0], cursor[1], key)
                    if nxt:
                        trail.add(cursor)
                        cursor = nxt

                    t_now    = time.time()
                    abs_ms   = t_now * 1000
                    rel_ms   = (t_now - trial.trial_start_time) * 1000
                    iki_ms   = ((t_now - last_key_time) * 1000
                                if last_key_time else None)
                    last_key_time = t_now

                    if first_key_time is None:
                        first_key_time = t_now

                    # Save keypress immediately — crash safe
                    trial.keypresses_log.append({
                        "key": key,
                        "before": prev_cursor,
                        "after":  cursor,
                        "abs_ms": abs_ms,
                        "rel_ms": rel_ms,
                        "iki_ms": iki_ms,
                    })

                elif event.key == pygame.K_SPACE:
                    # Spacebar = done with physical practice
                    if last_key_time:
                        trial.movement_time_ms = (last_key_time - first_key_time) * 1000
                    state          = FEEDBACK
                    feedback_start = time.time()
                    _finalise_trial(trial, trial.planned_sequence, action_path, session_id)
                    trial_id = _save_trial_to_db(trial, session_id)
                    update_session_progress(session_id, trial.trial_number)

            # ── ACTION (MI): spacebar hold for imagery ───────
            elif state == ACTION and is_mi:
                if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                    spacebar_down_t = time.time()
                if event.type == pygame.KEYUP and event.key == pygame.K_SPACE:
                    if spacebar_down_t:
                        trial.imagery_duration_ms = (time.time() - spacebar_down_t) * 1000
                    state          = FEEDBACK
                    feedback_start = time.time()
                    _finalise_trial(trial, trial.planned_sequence, action_path, session_id)
                    trial_id = _save_trial_to_db(trial, session_id)
                    update_session_progress(session_id, trial.trial_number)

        # ── Auto-advance planning timer ──────────────────────
        if state == PLANNING and elapsed >= planning_time:
            state      = INPUT
            typed_seq  = []
            first_key_time = None

        # ── Auto-advance MI action if they take too long ─────
        if state == ACTION and is_mi and (time.time() - planning_start) > planning_time + action_time + 5:
            trial.imagery_duration_ms = action_time * 1000
            state          = FEEDBACK
            feedback_start = time.time()
            _finalise_trial(trial, trial.planned_sequence, action_path, session_id)
            trial_id = _save_trial_to_db(trial, session_id)
            update_session_progress(session_id, trial.trial_number)

        # ── Auto-advance feedback ────────────────────────────
        if state == FEEDBACK and feedback_start:
            if time.time() - feedback_start >= feedback_time:
                state     = ITI
                iti_start = time.time()

        # ── Auto-advance ITI ─────────────────────────────────
        if state == ITI and iti_start:
            if time.time() - iti_start >= intertrial_time:
                state = DONE

        if state == DONE:
            break

        # ── Blink cursor in input box ────────────────────────
        if now_ms - blink_timer > 500:
            blink_visible = not blink_visible
            blink_timer   = now_ms

        # ── Draw ─────────────────────────────────────────────
        screen.fill(BG)

        if state == PLANNING:
            _draw_planning(screen, fonts, trial, elapsed, planning_time)

        elif state == INPUT:
            _draw_input(screen, fonts, trial, typed_seq, blink_visible)

        elif state == ACTION:
            _draw_action(screen, fonts, trial, cursor, trail,
                         typed_seq, action_step, is_mi, spacebar_down_t, is_ctrl)
            # Animate action path for PP group
            if is_pp and now_ms - action_timer >= anim_delay and action_step < len(action_path) - 1:
                action_step += 1
                action_timer = now_ms
                if action_step < len(action_path):
                    trail.add(cursor)
                    cursor = action_path[action_step]

        elif state == FEEDBACK:
            _draw_feedback(screen, fonts, trial, cumulative_score)

        elif state == ITI:
            screen.fill(BG)   # blank screen during intertrial interval

        pygame.display.flip()
        clock.tick(60)

    # Save keypresses to DB if PP group
    if is_pp and trial_id and trial.keypresses_log:
        for kp in trial.keypresses_log:
            save_keypress(
                trial_id        = trial_id,
                participant_id  = trial.participant_id,
                key_pressed     = kp["key"],
                cursor_row_before = kp["before"][0],
                cursor_col_before = kp["before"][1],
                cursor_row_after  = kp["after"][0],
                cursor_col_after  = kp["after"][1],
                timestamp_ms              = kp["abs_ms"],
                time_since_trial_start_ms = kp["rel_ms"],
                time_since_last_press_ms  = kp["iki_ms"],
            )

    new_cumulative = cumulative_score + trial.reward_score
    return {
        "reward_score":      trial.reward_score,
        "is_correct":        trial.is_correct,
        "cumulative_score":  new_cumulative,
        "trial_id":          trial_id,
    }


# ── Trial finalisation ───────────────────────────────────────

def _finalise_trial(trial: TrialData, used_seq, action_path, session_id):
    """Calculate score and set final trial fields before saving."""
    # Simulate final cursor position from the planned sequence
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
    """Write the completed trial to the database and return trial_id."""
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


# ── Screen drawing functions ─────────────────────────────────

def _draw_planning(screen, fonts, trial: TrialData, elapsed, planning_time):
    """Planning stage: grid shown with countdown timer."""
    f_big, f_med, f_sm, f_xs = fonts
    remaining = max(0, planning_time - elapsed)
    timer_col = ORANGE if remaining < 2 else WHITE

    draw_text(screen, f_med, "PLANNING  STAGE", ACCENT, LEFT, 28)
    draw_text(screen, f_xs,
              "Study the grid. Plan the shortest route from MOUSE to CHEESE.",
              DIM, LEFT, 62)

    _draw_grid(screen, fonts, trial, set(), trial.start,
               "Press SPACE when ready")

    # Countdown
    t_surf = f_big.render(f"{remaining:.1f}s", True, timer_col)
    screen.blit(t_surf, (RIGHT_X, TOP + CELL * GRID_SIZE - 70))
    draw_text(screen, f_xs, "Time remaining", DIM, RIGHT_X, TOP + CELL * GRID_SIZE - 30)


def _draw_input(screen, fonts, trial: TrialData, typed_seq, blink_visible):
    """Input stage: participant types their planned sequence."""
    f_big, f_med, f_sm, f_xs = fonts

    draw_text(screen, f_med, "ENTER YOUR SEQUENCE", WHITE, LEFT, 28)
    draw_text(screen, f_xs,
              "Press  1 / 2 / 3  to build your sequence. BACKSPACE to undo. ENTER to confirm.",
              DIM, LEFT, 62)

    _draw_grid(screen, fonts, trial, set(), trial.start)

    # Sequence display on right panel
    y = TOP + 10
    draw_text(screen, f_sm, "Your sequence:", ACCENT, RIGHT_X, y); y += 30

    seq_str  = "  ->  ".join(str(k) for k in typed_seq) if typed_seq else ""
    seq_surf = f_sm.render(seq_str, True, WHITE)
    screen.blit(seq_surf, (RIGHT_X, y))

    if blink_visible:
        bar_x = RIGHT_X + seq_surf.get_width() + 3
        pygame.draw.rect(screen, WHITE, (bar_x, y, 2, seq_surf.get_height()))

    y += 30
    draw_text(screen, f_xs, f"Keys: {len(typed_seq)}", DIM, RIGHT_X, y)
    draw_text(screen, f_xs, "ENTER to confirm", DIM, RIGHT_X,
              TOP + CELL * GRID_SIZE - 20)


def _draw_action(screen, fonts, trial: TrialData, cursor, trail,
                 typed_seq, action_step, is_mi, spacebar_down_t, is_ctrl):
    """Action stage: physical practice or motor imagery."""
    f_big, f_med, f_sm, f_xs = fonts

    if is_mi:
        draw_text(screen, f_med, "ACTION STAGE — Motor Imagery", GREEN, LEFT, 28)
        draw_text(screen, f_xs,
                  "Hold SPACEBAR while you imagine pressing your sequence. Release when done.",
                  DIM, LEFT, 62)
        _draw_grid(screen, fonts, trial, set(), trial.start)
        # Spacebar held indicator
        held = spacebar_down_t is not None
        held_dur = (time.time() - spacebar_down_t) if held else 0
        status   = f"Imagining...  {held_dur:.1f}s" if held else "Hold SPACEBAR to begin imagery"
        col      = GREEN if held else DIM
        draw_text(screen, f_sm, status, col, RIGHT_X, TOP + 20)
    else:
        draw_text(screen, f_med, "ACTION STAGE — Physical Practice", GREEN, LEFT, 28)
        draw_text(screen, f_xs,
                  "Press your sequence using keys 1, 2, 3. Press SPACEBAR when done.",
                  DIM, LEFT, 62)
        _draw_grid(screen, fonts, trial, trail, cursor)
        # Live sequence on right panel
        y = TOP + 10
        key_labels = {1: "^  Up", 2: "v>  Down-Right", 3: "v<  Down-Left"}
        draw_text(screen, f_sm, "SEQUENCE", ACCENT, RIGHT_X, y); y += 28
        for i, key in enumerate(typed_seq):
            c = GREEN if i < action_step else (DIM if i > action_step else ACCENT)
            draw_text(screen, f_xs,
                      f"{i+1}. Key {key}  {key_labels[key]}", c, RIGHT_X, y)
            y += 22


def _draw_feedback(screen, fonts, trial: TrialData, cumulative_score: int):
    """Feedback screen shown for feedback_time seconds after each trial."""
    f_big, f_med, f_sm, f_xs = fonts
    cx = screen.get_width() // 2

    if trial.is_correct:
        title = "Reached the Cheese!"
        col   = (210, 160, 30)
    else:
        title = "Missed the Goal"
        col   = ORANGE

    t = f_big.render(title, True, col)
    screen.blit(t, (cx - t.get_width() // 2, 160))

    # Stats row
    stats = [
        ("Moves used",   str(trial.number_of_moves)),
        ("Optimal",      str(len(trial.optimal_sequence))),
        ("Trial score",  str(trial.reward_score)),
        ("Total score",  str(cumulative_score + trial.reward_score)),
    ]
    sx = cx - 300
    for label, val in stats:
        box = pygame.Rect(sx, 260, 140, 70)
        pygame.draw.rect(screen, (28, 28, 45), box, border_radius=10)
        pygame.draw.rect(screen, col, box, width=1, border_radius=10)
        lbl  = f_xs.render(label, True, DIM)
        vsurf= f_med.render(val,   True, col)
        screen.blit(lbl,  (sx + 70 - lbl.get_width()  // 2, 268))
        screen.blit(vsurf,(sx + 70 - vsurf.get_width() // 2, 288))
        sx += 155

    # Optimal sequence hint
    opt_str = "  ->  ".join(str(k) for k in trial.optimal_sequence)
    draw_centered(screen, f_xs, f"Optimal sequence:  {opt_str}", DIM, 360)
