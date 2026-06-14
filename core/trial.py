# ============================================================
#  GRID-SAILING TASK — Trial State Machine  (v2 redesign)
#
#  States:
#    PLANNING  → grid + countdown
#    INPUT     → type sequence  (1 / 2 / 3)
#    ACTION    → physical practice / motor imagery / control
#    FEEDBACK  → animated path replay + scores
#    ITI       → "Get Ready" pulse screen
#    DONE      → data saved, return to session
# ============================================================

import pygame
import math
import time
from dataclasses import dataclass, field
from typing import Optional

from config import OPTIMAL_SCORE, EXTRA_MOVE_PENALTY, ERROR_SCORE
from core.grid import apply_key
from database.db import save_trial, save_keypress, update_session_progress

# ── States ────────────────────────────────────────────────────
PLANNING = "planning"
INPUT    = "input"
ACTION   = "action"
FEEDBACK = "feedback"
ITI      = "iti"
DONE     = "done"

# ── Palette ───────────────────────────────────────────────────
BG          = (12,  12,  22)
PANEL       = (22,  22,  38)
BORDER      = (52,  52,  80)
WHITE       = (230, 230, 242)
DIM         = (100, 100, 138)
ACCENT      = ( 88, 148, 255)
GREEN       = ( 58, 196, 108)
AMBER       = (210, 158,  28)
ORANGE      = (228, 138,  48)
RED         = (212,  58,  58)
CELL_DARK   = (28,  28,  48)
CELL_TRAIL  = (42,  78, 148)
CELL_REPLAY = (62, 108, 195)
GRID_BORDER = (44,  44,  70)
CURSOR_W    = (245, 245, 255)
PROG_BG     = (20,  20,  36)
PROG_FG     = (58, 118, 228)

# ── Layout ────────────────────────────────────────────────────
GRID_N   = 5
CELL     = 96
GL       = 52           # grid left
GT       = 108          # grid top
GR       = GL + CELL * GRID_N + 48   # right panel start  (= 580)
GRW      = 460          # right panel width
PROG_H   = 36           # bottom bar height


@dataclass
class TrialData:
    session_id:       int
    participant_id:   str
    trial_number:     int
    grid_type:        str
    start:            tuple
    goal:             tuple
    optimal_sequence: list
    group:            str

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


def _score(planned, optimal, end, goal):
    n, opt = len(planned), len(optimal)
    if end != goal:
        return ERROR_SCORE, n, False
    extra = max(0, n - opt)
    return max(0, OPTIMAL_SCORE - extra * EXTRA_MOVE_PENALTY), n, True


def _build_path(start, seq):
    pos, path = start, [start]
    for k in seq:
        nxt = apply_key(pos[0], pos[1], k)
        pos = nxt if nxt else pos
        path.append(pos)
    return path


# ── Drawing helpers ───────────────────────────────────────────

def _t(screen, font, text, col, x, y):
    s = font.render(text, True, col)
    screen.blit(s, (x, y))
    return s

def _tc(screen, font, text, col, y):
    s = font.render(text, True, col)
    screen.blit(s, (screen.get_width()//2 - s.get_width()//2, y))
    return s

def _panel(screen, x, y, w, h, border_col=BORDER):
    pygame.draw.rect(screen, PANEL,      (x, y, w, h), border_radius=12)
    pygame.draw.rect(screen, border_col, (x, y, w, h), width=1, border_radius=12)

def _pill(screen, font, text, fg, bg, x, y):
    s  = font.render(text, True, fg)
    pw = s.get_width() + 20
    ph = s.get_height() + 8
    pygame.draw.rect(screen, bg, (x, y, pw, ph), border_radius=ph//2)
    screen.blit(s, (x + 10, y + 4))
    return pw


def _draw_progress(screen, fonts, trial, total, block_type, session_num):
    """Slim progress bar pinned to the bottom of the screen."""
    f_big, f_med, f_sm, f_xs = fonts
    W = screen.get_width()
    H = screen.get_height()
    y = H - PROG_H

    pygame.draw.rect(screen, PROG_BG, (0, y, W, PROG_H))
    pct = (trial.trial_number - 1) / max(total, 1)
    pygame.draw.rect(screen, PROG_FG, (0, y, int(W * pct), PROG_H))
    pygame.draw.line(screen, BORDER, (0, y), (W, y))

    # Left: trial X / Y
    _t(screen, f_xs, f"Trial  {trial.trial_number}  /  {total}", WHITE,
       14, y + PROG_H//2 - f_xs.get_height()//2)

    # Centre: block name
    bname = block_type.replace("_", " ").title()
    bs = f_xs.render(bname, True, ACCENT)
    screen.blit(bs, (W//2 - bs.get_width()//2, y + PROG_H//2 - bs.get_height()//2))

    # Right: session
    ss = f_xs.render(f"Session  {session_num}", True, DIM)
    screen.blit(ss, (W - 14 - ss.get_width(), y + PROG_H//2 - ss.get_height()//2))


def _draw_grid(screen, fonts, trial, trail, cursor, show_labels=True):
    f_big, f_med, f_sm, f_xs = fonts
    start, goal = trial.start, trial.goal

    for r in range(GRID_N):
        for c in range(GRID_N):
            px = GL + c * CELL + 5
            py = GT + r * CELL + 5
            sz = CELL - 10
            rect = pygame.Rect(px, py, sz, sz)

            if (r, c) == goal:
                bg = AMBER
            elif (r, c) in trail:
                bg = CELL_TRAIL
            elif (r, c) == start:
                bg = (175, 45, 45)
            else:
                bg = CELL_DARK

            pygame.draw.rect(screen, bg,          rect, border_radius=10)
            pygame.draw.rect(screen, GRID_BORDER, rect, width=1, border_radius=10)

            if show_labels:
                if (r, c) == start:
                    lbl = f_xs.render("MOUSE", True, (220, 180, 180))
                    screen.blit(lbl, (px + sz//2 - lbl.get_width()//2,
                                      py + sz//2 - lbl.get_height()//2))
                elif (r, c) == goal:
                    lbl = f_xs.render("CHEESE", True, (60, 44, 4))
                    screen.blit(lbl, (px + sz//2 - lbl.get_width()//2,
                                      py + sz//2 - lbl.get_height()//2))

    # Cursor
    if cursor:
        cx = GL + cursor[1] * CELL + CELL // 2
        cy = GT + cursor[0] * CELL + CELL // 2
        pygame.draw.circle(screen, CURSOR_W, (cx, cy), 20)
        pygame.draw.circle(screen, ACCENT,   (cx, cy), 20, 3)
        pygame.draw.circle(screen, BG,       (cx, cy),  7)


def _draw_key_legend(screen, fonts, rx, y):
    f_big, f_med, f_sm, f_xs = fonts
    _t(screen, f_xs, "KEY  MAPPINGS", DIM, rx, y);  y += 20
    pygame.draw.line(screen, BORDER, (rx, y), (rx + GRW - 10, y), 1);  y += 12
    for key, finger, move in [("1", "Index",  "Up"),
                               ("2", "Middle", "Down-Right"),
                               ("3", "Ring",   "Down-Left")]:
        _t(screen, f_sm, f"Key {key}", ACCENT,  rx,       y)
        _t(screen, f_xs, finger,       WHITE,   rx + 72,  y)
        _t(screen, f_xs, f"— {move}",  DIM,    rx + 150,  y)
        y += 28
    return y + 8


def _stage_header(screen, fonts, tag, tag_col, title, subtitle):
    """Top-left stage label + instruction."""
    f_big, f_med, f_sm, f_xs = fonts
    _pill(screen, f_xs, tag, BG, tag_col, GL, 14)
    _t(screen, f_med, title,    WHITE, GL, 48)
    _t(screen, f_xs,  subtitle, DIM,   GL, 76)


# ── Main trial runner ─────────────────────────────────────────

def run_trial(screen, clock, fonts, trial: TrialData, config: dict,
              cumulative_score: int, session_id: int,
              total_trials: int = 20, block_type: str = "practice") -> dict:

    f_big, f_med, f_sm, f_xs = fonts
    W, H = screen.get_width(), screen.get_height()

    state           = PLANNING
    planning_start  = time.time()
    first_key_time  = None
    last_key_time   = None
    sbar_down_t     = None    # spacebar held (MI)
    cursor          = trial.start
    trail           = set()
    typed_seq       = []
    action_path     = []
    feedback_start  = None
    iti_start       = None
    trial_id        = None
    blink_on        = True
    blink_t         = pygame.time.get_ticks()

    # Replay (feedback stage)
    rp_step    = 0
    rp_timer   = 0
    rp_cursor  = trial.start
    rp_trail   = set()
    rp_done    = False

    trial.trial_start_time = time.time()

    is_mi   = _is_mi(trial.group)
    is_pp   = _is_pp(trial.group)
    is_ctrl = _is_ctrl(trial.group)

    p_time  = config.get("planning_time",   6)
    a_time  = config.get("action_time",     10)
    fb_time = config.get("feedback_time",   4)
    iti_dur = config.get("intertrial_time", 3)
    sn      = config.get("session_number",  1)

    REPLAY_MS = 520

    def enter_feedback():
        nonlocal state, feedback_start, rp_step, rp_timer, rp_cursor, rp_trail, rp_done
        state = FEEDBACK
        feedback_start = time.time()
        rp_step = 0; rp_timer = pygame.time.get_ticks()
        rp_cursor = trial.start; rp_trail = set(); rp_done = False

    while True:
        now_ms = pygame.time.get_ticks()
        now_s  = time.time()
        elapsed = now_s - planning_start
        events = pygame.event.get()

        for ev in events:
            if ev.type == pygame.QUIT:
                pygame.quit(); import sys; sys.exit()

            # ── PLANNING ─────────────────────────────────────
            if state == PLANNING and ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_SPACE:
                    state = INPUT; typed_seq = []; first_key_time = None

            # ── INPUT ─────────────────────────────────────────
            elif state == INPUT and ev.type == pygame.KEYDOWN:
                km = {pygame.K_1:1, pygame.K_KP1:1,
                      pygame.K_2:2, pygame.K_KP2:2,
                      pygame.K_3:3, pygame.K_KP3:3}
                if ev.key in km:
                    if first_key_time is None: first_key_time = time.time()
                    typed_seq.append(km[ev.key])
                elif ev.key == pygame.K_BACKSPACE and typed_seq:
                    typed_seq.pop()
                elif ev.key == pygame.K_RETURN and typed_seq:
                    if first_key_time:
                        trial.reaction_time_ms = (first_key_time - planning_start) * 1000
                    trial.planned_sequence = list(typed_seq)
                    action_path = _build_path(trial.start, typed_seq)
                    if is_ctrl:
                        _finalise(trial, typed_seq, session_id)
                        trial_id = _save(trial, session_id)
                        update_session_progress(session_id, trial.trial_number)
                        enter_feedback()
                    else:
                        state  = ACTION
                        cursor = trial.start
                        trail  = set()
                        if is_mi: sbar_down_t = None

            # ── ACTION: PP ────────────────────────────────────
            elif state == ACTION and is_pp and ev.type == pygame.KEYDOWN:
                km = {pygame.K_1:1, pygame.K_KP1:1,
                      pygame.K_2:2, pygame.K_KP2:2,
                      pygame.K_3:3, pygame.K_KP3:3}
                if ev.key in km:
                    key = km[ev.key]
                    prev = cursor
                    nxt  = apply_key(cursor[0], cursor[1], key)
                    if nxt: trail.add(cursor); cursor = nxt
                    t_now = time.time()
                    iki   = ((t_now - last_key_time)*1000) if last_key_time else None
                    last_key_time = t_now
                    if first_key_time is None: first_key_time = t_now
                    trial.keypresses_log.append({
                        "key": key, "before": prev, "after": cursor,
                        "abs_ms": t_now*1000,
                        "rel_ms": (t_now - trial.trial_start_time)*1000,
                        "iki_ms": iki,
                    })
                elif ev.key == pygame.K_SPACE:
                    if last_key_time and first_key_time:
                        trial.movement_time_ms = (last_key_time - first_key_time)*1000
                    _finalise(trial, trial.planned_sequence, session_id)
                    trial_id = _save(trial, session_id)
                    update_session_progress(session_id, trial.trial_number)
                    enter_feedback()

            # ── ACTION: MI ────────────────────────────────────
            elif state == ACTION and is_mi:
                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_SPACE:
                    sbar_down_t = time.time()
                if ev.type == pygame.KEYUP and ev.key == pygame.K_SPACE:
                    if sbar_down_t:
                        trial.imagery_duration_ms = (time.time() - sbar_down_t)*1000
                    _finalise(trial, trial.planned_sequence, session_id)
                    trial_id = _save(trial, session_id)
                    update_session_progress(session_id, trial.trial_number)
                    enter_feedback()

            # ── FEEDBACK: SPACE to skip ───────────────────────
            elif state == FEEDBACK and ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_SPACE and (time.time()-feedback_start) >= 1.5:
                    state = ITI; iti_start = time.time()

        # ── Auto-transitions ──────────────────────────────────
        if state == PLANNING and elapsed >= p_time:
            state = INPUT; typed_seq = []; first_key_time = None

        if state == ACTION and is_mi:
            if (now_s - planning_start) > p_time + a_time + 5:
                trial.imagery_duration_ms = a_time * 1000
                _finalise(trial, trial.planned_sequence, session_id)
                trial_id = _save(trial, session_id)
                update_session_progress(session_id, trial.trial_number)
                enter_feedback()

        if state == FEEDBACK and not rp_done:
            if now_ms - rp_timer >= REPLAY_MS:
                rp_timer = now_ms
                if rp_step < len(action_path) - 1:
                    rp_trail.add(rp_cursor)
                    rp_step += 1
                    rp_cursor = action_path[rp_step]
                else:
                    rp_done = True

        if state == FEEDBACK and feedback_start:
            if rp_done and (now_s - feedback_start) >= fb_time:
                state = ITI; iti_start = now_s

        if state == ITI and iti_start:
            if (now_s - iti_start) >= iti_dur:
                state = DONE

        if state == DONE:
            break

        # Blink
        if now_ms - blink_t > 520:
            blink_on = not blink_on; blink_t = now_ms

        # ── DRAW ─────────────────────────────────────────────
        screen.fill(BG)

        if state == PLANNING:
            _draw_stage_planning(screen, fonts, trial, elapsed, p_time,
                                 total_trials, block_type, sn)
        elif state == INPUT:
            _draw_stage_input(screen, fonts, trial, typed_seq, blink_on,
                              total_trials, block_type, sn)
        elif state == ACTION:
            _draw_stage_action(screen, fonts, trial, cursor, trail,
                               typed_seq, is_mi, is_pp, sbar_down_t,
                               total_trials, block_type, sn)
        elif state == FEEDBACK:
            _draw_stage_feedback(screen, fonts, trial, cumulative_score,
                                 rp_cursor, rp_trail, rp_done,
                                 total_trials, block_type, sn)
        elif state == ITI:
            _draw_stage_iti(screen, fonts, trial, iti_start, iti_dur,
                            total_trials, block_type, sn)

        pygame.display.flip()
        clock.tick(60)

    # Save PP keypresses
    if is_pp and trial_id and trial.keypresses_log:
        for kp in trial.keypresses_log:
            save_keypress(
                trial_id=trial_id, participant_id=trial.participant_id,
                key_pressed=kp["key"],
                cursor_row_before=kp["before"][0], cursor_col_before=kp["before"][1],
                cursor_row_after=kp["after"][0],  cursor_col_after=kp["after"][1],
                timestamp_ms=kp["abs_ms"],
                time_since_trial_start_ms=kp["rel_ms"],
                time_since_last_press_ms=kp["iki_ms"],
            )

    return {
        "reward_score":     trial.reward_score,
        "is_correct":       trial.is_correct,
        "cumulative_score": cumulative_score + trial.reward_score,
        "trial_id":         trial_id,
    }


# ── Finalise & save ───────────────────────────────────────────

def _finalise(trial, used_seq, session_id):
    pos = trial.start
    for k in used_seq:
        nxt = apply_key(pos[0], pos[1], k)
        if nxt: pos = nxt
    score, n, ok = _score(used_seq, trial.optimal_sequence, pos, trial.goal)
    trial.reward_score = score; trial.number_of_moves = n; trial.is_correct = ok
    if trial.movement_time_ms is None and len(trial.keypresses_log) >= 2:
        trial.movement_time_ms = (trial.keypresses_log[-1]["abs_ms"]
                                  - trial.keypresses_log[0]["abs_ms"])

def _save(trial, session_id):
    return save_trial(
        session_id=session_id, participant_id=trial.participant_id,
        trial_number=trial.trial_number, grid_type=trial.grid_type,
        start_row=trial.start[0], start_col=trial.start[1],
        goal_row=trial.goal[0],   goal_col=trial.goal[1],
        planned_sequence=trial.planned_sequence,
        optimal_sequence=trial.optimal_sequence,
        optimal_length=len(trial.optimal_sequence),
        number_of_moves=trial.number_of_moves,
        reward_score=trial.reward_score,
        reaction_time_ms=trial.reaction_time_ms,
        movement_time_ms=trial.movement_time_ms,
        elapsed_time_s=time.time() - trial.trial_start_time,
        imagery_duration_ms=trial.imagery_duration_ms,
        is_correct=trial.is_correct,
    )


# ── Stage drawing ─────────────────────────────────────────────

def _draw_stage_planning(screen, fonts, trial, elapsed, p_time,
                         total_trials, block_type, sn):
    f_big, f_med, f_sm, f_xs = fonts
    rem = max(0, p_time - elapsed)
    tc  = RED if rem < 2 else (ORANGE if rem < 4 else WHITE)

    _stage_header(screen, fonts,
                  "PLANNING", ACCENT,
                  "Study the grid",
                  "Plan the shortest route from MOUSE to CHEESE   ·   SPACE to skip ahead")
    _draw_grid(screen, fonts, trial, set(), trial.start)

    # Right panel
    rx, ry = GR, GT

    # Timer box
    _panel(screen, rx, ry, GRW, 100, BORDER)
    ts = f_big.render(f"{rem:.1f}s", True, tc)
    screen.blit(ts, (rx + GRW//2 - ts.get_width()//2, ry + 12))
    tl = f_xs.render("Time remaining", True, DIM)
    screen.blit(tl, (rx + GRW//2 - tl.get_width()//2, ry + 72))
    ry += 116

    # Grid type badge
    badge_col = ACCENT if trial.grid_type == "repeated" else ORANGE
    _pill(screen, f_xs, f"  {trial.grid_type.upper()}  ", BG, badge_col, rx, ry)
    ry += 36

    _draw_key_legend(screen, fonts, rx, ry)
    _draw_progress(screen, fonts, trial, total_trials, block_type, sn)


def _draw_stage_input(screen, fonts, trial, typed_seq, blink_on,
                      total_trials, block_type, sn):
    f_big, f_med, f_sm, f_xs = fonts

    _stage_header(screen, fonts,
                  "INPUT", WHITE,
                  "Enter your planned sequence",
                  "Keys  1 / 2 / 3  to add   ·   BACKSPACE to undo   ·   ENTER to confirm")
    _draw_grid(screen, fonts, trial, set(), trial.start)

    rx, ry = GR, GT

    # Sequence box
    _panel(screen, rx, ry, GRW, 110, ACCENT)
    _t(screen, f_xs, "Your sequence", DIM, rx + 14, ry + 10)

    seq_str  = "   →   ".join(str(k) for k in typed_seq) if typed_seq else "—"
    seq_col  = WHITE if typed_seq else DIM
    ss = f_sm.render(seq_str, True, seq_col)
    screen.blit(ss, (rx + 14, ry + 36))

    if blink_on and typed_seq:
        bx = rx + 14 + ss.get_width() + 5
        pygame.draw.rect(screen, ACCENT, (bx, ry + 36, 2, ss.get_height()))

    cnt = f_xs.render(f"{len(typed_seq)} key(s)   ·   ENTER to confirm", True, DIM)
    screen.blit(cnt, (rx + 14, ry + 82))
    ry += 128

    _draw_key_legend(screen, fonts, rx, ry)
    _draw_progress(screen, fonts, trial, total_trials, block_type, sn)


def _draw_stage_action(screen, fonts, trial, cursor, trail,
                       typed_seq, is_mi, is_pp, sbar_down_t,
                       total_trials, block_type, sn):
    f_big, f_med, f_sm, f_xs = fonts
    rx, ry = GR, GT

    if is_mi:
        _stage_header(screen, fonts,
                      "IMAGERY", GREEN,
                      "Motor Imagery",
                      "Hold SPACEBAR and vividly imagine pressing your sequence · Release when done")
        _draw_grid(screen, fonts, trial, set(), trial.start)

        held     = sbar_down_t is not None
        held_dur = (time.time() - sbar_down_t) if held else 0
        sc       = GREEN if held else DIM

        _panel(screen, rx, ry, GRW, 80, sc)
        status = f"Imagining...  {held_dur:.1f}s" if held else "Hold SPACEBAR to begin"
        sl = f_sm.render(status, True, sc)
        screen.blit(sl, (rx + GRW//2 - sl.get_width()//2, ry + 28))
        ry += 96

        _draw_key_legend(screen, fonts, rx, ry)

    else:  # PP
        _stage_header(screen, fonts,
                      "ACTION", GREEN,
                      "Physical Practice",
                      "Press keys 1, 2, 3 to execute your sequence   ·   SPACEBAR when done")
        _draw_grid(screen, fonts, trial, trail, cursor)

        _t(screen, f_xs, "LIVE PATH", DIM, rx, ry); ry += 20
        pygame.draw.line(screen, BORDER, (rx, ry), (rx + GRW - 10, ry)); ry += 12
        key_labels = {1: "Up", 2: "Down-Right", 3: "Down-Left"}
        for i, k in enumerate(typed_seq):
            _t(screen, f_xs, f"  {i+1}.  Key {k}  —  {key_labels[k]}", ACCENT, rx, ry)
            ry += 24
        if not typed_seq:
            _t(screen, f_xs, "  (no keys pressed yet)", DIM, rx, ry); ry += 24
        ry += 8
        _t(screen, f_xs, "SPACEBAR  →  finish", DIM, rx, ry)

    _draw_progress(screen, fonts, trial, total_trials, block_type, sn)


def _draw_stage_feedback(screen, fonts, trial, cum_score,
                         rp_cursor, rp_trail, rp_done,
                         total_trials, block_type, sn):
    f_big, f_med, f_sm, f_xs = fonts
    W, H = screen.get_width(), screen.get_height()
    cx   = W // 2

    if trial.is_correct:
        title, tc = "Reached the Cheese!", AMBER
    else:
        title, tc = "Missed the Goal", ORANGE

    # Outcome title
    ts = f_big.render(title, True, tc)
    screen.blit(ts, (cx - ts.get_width()//2, 14))

    # Animated replay grid
    _draw_grid(screen, fonts, trial, rp_trail, rp_cursor)

    # Sequences below grid
    p_str = "  →  ".join(str(k) for k in trial.planned_sequence) or "—"
    o_str = "  →  ".join(str(k) for k in trial.optimal_sequence)
    gy = GT + GRID_N * CELL + 10
    _t(screen, f_xs, f"Your sequence :  {p_str}", DIM, GL, gy)
    _t(screen, f_xs, f"Optimal           :  {o_str}", DIM, GL, gy + 22)

    # Score cards (right panel)
    rx, ry = GR, GT
    new_total = cum_score + trial.reward_score

    cards = [
        ("Moves used",  str(trial.number_of_moves),        WHITE),
        ("Optimal",     str(len(trial.optimal_sequence)),  ACCENT),
        ("Trial score", str(trial.reward_score),           tc),
        ("Total score", str(new_total),                    GREEN),
    ]
    for label, val, col in cards:
        _panel(screen, rx, ry, GRW, 64, col)
        _t(screen, f_xs, label, DIM,  rx + 16, ry + 8)
        _t(screen, f_med, val,  col,  rx + 16, ry + 28)
        ry += 76

    # SPACE hint
    hint_col = WHITE if rp_done else DIM
    hs = f_xs.render("SPACE  —  next trial", True, hint_col)
    screen.blit(hs, (cx - hs.get_width()//2, H - PROG_H - 32))

    _draw_progress(screen, fonts, trial, total_trials, block_type, sn)


def _draw_stage_iti(screen, fonts, trial, iti_start, iti_dur,
                    total_trials, block_type, sn):
    """'Get Ready' pulse screen — no blank black."""
    f_big, f_med, f_sm, f_xs = fonts
    W, H = screen.get_width(), screen.get_height()
    cx, cy = W // 2, H // 2 - 30

    elapsed = time.time() - (iti_start or time.time())
    remaining = max(0, iti_dur - elapsed)

    # Pulsing ring
    pulse = 0.5 + 0.5 * math.sin(elapsed * math.pi * 1.6)
    r_inner = int(38 + 6  * pulse)
    r_outer = int(52 + 10 * pulse)
    alpha   = int(60 + 60 * pulse)

    ring_surf = pygame.Surface((r_outer*2+4, r_outer*2+4), pygame.SRCALPHA)
    pygame.draw.circle(ring_surf, (*ACCENT, alpha),
                       (r_outer+2, r_outer+2), r_outer)
    pygame.draw.circle(ring_surf, (*BG, 255),
                       (r_outer+2, r_outer+2), r_inner)
    screen.blit(ring_surf, (cx - r_outer - 2, cy - r_outer - 2))

    # Text
    gr = f_big.render("Get Ready", True, WHITE)
    screen.blit(gr, (cx - gr.get_width()//2, cy + r_outer + 16))

    next_lbl = f_xs.render(f"Trial  {trial.trial_number}  of  {total_trials}  starting…",
                            True, DIM)
    screen.blit(next_lbl, (cx - next_lbl.get_width()//2, cy + r_outer + 58))

    _draw_progress(screen, fonts, trial, total_trials, block_type, sn)
