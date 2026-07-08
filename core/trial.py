# ============================================================
#  GRID-SAILING TASK — Trial State Machine
#
#  States:
#    PLANNING   → grid shown, countdown timer
#    INPUT      → participant enters planned sequence
#    COUNTDOWN  → 3-2-1 before action phase
#    ACTION     → physical / imagery / control execution (grid hidden for PP/MI)
#    FEEDBACK   → result + animated path replay
#    ITI        → jittered "Get Ready" inter-trial interval
#    DONE       → return to session
# ============================================================

import pygame
import math
import time
import random
from dataclasses import dataclass, field
from typing import Optional

from config import OPTIMAL_SCORE, EXTRA_MOVE_PENALTY, ERROR_SCORE
from core.grid import apply_key
from database.db import save_trial, save_keypress, update_session_progress

# ── States ────────────────────────────────────────────────────
PLANNING  = "planning"
INPUT     = "input"
COUNTDOWN = "countdown"
ACTION    = "action"
FEEDBACK  = "feedback"
ITI       = "iti"
DONE      = "done"
PAUSED    = "paused"

# ── Colorblind-safe palette ───────────────────────────────────
BG          = (8,    8,   16)
PANEL       = (20,  20,   36)
BORDER      = (48,  48,   76)
BORDER2     = (72,  72,  116)   # brighter divider in score card
WHITE       = (245, 245, 255)
DIM         = (118, 118, 158)
ACCENT      = (88,  148, 255)   # blue
CORRECT     = (0,   168, 175)   # teal   — colorblind-safe "correct"
WRONG       = (210,  95,  20)   # orange — colorblind-safe "incorrect"
AMBER       = (220, 162,  28)   # goal highlight
CELL_DARK   = (22,  22,   44)
CELL_TRAIL  = (30,  70,  150)
CELL_START  = (20,  80,  180)   # blue start cell
CELL_GOAL   = (180, 130,  18)   # amber goal cell
GRID_BORDER = (38,  38,   66)
CURSOR_W    = (248, 248, 255)
PROG_BG     = (12,  12,   24)
PROG_FG     = (50, 110, 220)

GRID_N = 5

TRAIL_FADE_SEC = 1.4              # seconds for a cell to fade from fresh to dim
TRAIL_FRESH    = (110, 170, 255)  # bright blue immediately after stepping on a cell

_COUNTDOWN_FONT = None   # cached to avoid per-frame SysFont allocation


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

    all_optimal_sequences: list = field(default_factory=list)

    planned_sequence:    list  = field(default_factory=list)
    keypresses_log:      list  = field(default_factory=list)
    reaction_time_ms:    Optional[float] = None
    movement_time_ms:    Optional[float] = None
    imagery_duration_ms: Optional[float] = None
    reward_score:        int   = 0
    number_of_moves:     int   = 0
    is_correct:          bool  = False
    oob_count:           int   = 0
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


# ── Layout ────────────────────────────────────────────────────

def _layout(W, H):
    """Compute grid + right-panel geometry centred on screen."""
    CELL   = 128
    GRID_W = GRID_N * CELL       # 640
    RPANEL = 420
    GAP    = 44
    TOTAL  = GRID_W + GAP + RPANEL
    GL     = max(20, (W - TOTAL) // 2)
    GT     = 108                  # top of grid (below stage header)
    GR     = GL + GRID_W + GAP
    GRW    = RPANEL
    return GL, GT, GR, GRW, CELL


PROG_H = 36


# ── Drawing helpers ───────────────────────────────────────────

def _t(screen, font, text, col, x, y):
    s = font.render(text, True, col)
    screen.blit(s, (x, y))
    return s

def _tc(screen, font, text, col, y):
    s = font.render(text, True, col)
    W = screen.get_width()
    screen.blit(s, (W // 2 - s.get_width() // 2, y))
    return s

def _panel(screen, x, y, w, h, border_col=BORDER):
    pygame.draw.rect(screen, PANEL,      (x, y, w, h), border_radius=12)
    pygame.draw.rect(screen, border_col, (x, y, w, h), width=1, border_radius=12)

def _pill(screen, font, text, fg, bg, x, y):
    s  = font.render(text, True, fg)
    pw = s.get_width() + 20
    ph = s.get_height() + 8
    pygame.draw.rect(screen, bg, (x, y, pw, ph), border_radius=ph // 2)
    screen.blit(s, (x + 10, y + 4))
    return pw


PAUSE_BTN_W = 72
PAUSE_BTN_H = 24

def _draw_progress(screen, fonts, trial, total, block_type, session_num,
                   cum_score: int = 0):
    f_big, f_med, f_sm, f_xs = fonts
    W = screen.get_width()
    H = screen.get_height()
    y = H - PROG_H

    pygame.draw.rect(screen, PROG_BG, (0, y, W, PROG_H))
    pct = (trial.trial_number - 1) / max(total, 1)
    pygame.draw.rect(screen, PROG_FG, (0, y, int(W * pct), PROG_H))
    pygame.draw.line(screen, BORDER, (0, y), (W, y))

    _t(screen, f_xs, f"Trial  {trial.trial_number}  /  {total}", WHITE,
       14, y + PROG_H // 2 - f_xs.get_height() // 2)

    bname = block_type.replace("_", " ").title()
    bs = f_xs.render(bname, True, ACCENT)
    screen.blit(bs, (W // 2 - bs.get_width() // 2,
                     y + PROG_H // 2 - bs.get_height() // 2))

    pause_x = W - PAUSE_BTN_W - 14
    pause_y = y + PROG_H // 2 - PAUSE_BTN_H // 2
    pause_rect = pygame.Rect(pause_x, pause_y, PAUSE_BTN_W, PAUSE_BTN_H)
    pygame.draw.rect(screen, (38, 38, 62), pause_rect, border_radius=6)
    pygame.draw.rect(screen, BORDER,       pause_rect, width=1, border_radius=6)
    pl = f_xs.render("II  Pause", True, DIM)
    screen.blit(pl, (pause_rect.x + pause_rect.w // 2 - pl.get_width() // 2,
                     pause_rect.y + pause_rect.h // 2 - pl.get_height() // 2))

    ss = f_xs.render(f"Session {session_num}", True, DIM)
    screen.blit(ss, (pause_x - ss.get_width() - 18,
                     y + PROG_H // 2 - ss.get_height() // 2))

    return pause_rect


def _draw_mouse_icon(surf, cx, cy):
    """Cartoon mouse face drawn procedurally — replaces 'MOUSE' text label."""
    body = (195, 200, 220)   # blue-gray
    pink = (220, 145, 158)   # inner ear / nose
    dark = (18,  18,  36)    # eyes
    wht  = (245, 248, 255)   # eye shine

    # Ears (drawn first so head overlaps them)
    for ex in (cx - 22, cx + 22):
        pygame.draw.circle(surf, body, (ex, cy - 28), 16)
        pygame.draw.circle(surf, pink, (ex, cy - 28),  9)

    # Head
    pygame.draw.circle(surf, body, (cx, cy - 4), 30)

    # Body (ellipse below head)
    pygame.draw.ellipse(surf, body, pygame.Rect(cx - 24, cy + 20, 48, 26))

    # Eyes
    for ex in (cx - 10, cx + 10):
        pygame.draw.circle(surf, dark, (ex, cy - 8), 4)
        pygame.draw.circle(surf, wht,  (ex - 1, cy - 10), 1)

    # Nose
    pygame.draw.circle(surf, pink, (cx, cy + 4), 4)

    # Whiskers (3 per side)
    for side, sign in ((-1, -1), (1, 1)):
        for i, dy in enumerate((-2, 2, 6)):
            x0 = cx + sign * 5
            x1 = cx + sign * 26
            y0 = cy + 4 + dy
            y1 = cy + 4 + dy + i * sign * 1
            pygame.draw.line(surf, (150, 152, 168), (x0, y0), (x1, y1), 1)

    # Tail (short wavy line from body)
    pygame.draw.lines(surf, body, False,
                      [(cx + 24, cy + 30), (cx + 36, cy + 22),
                       (cx + 44, cy + 30), (cx + 50, cy + 24)], 2)


def _draw_cheese_icon(surf, cx, cy):
    """Cartoon cheese wedge drawn procedurally — replaces 'CHEESE' text label."""
    yellow  = (255, 216, 42)    # main cheese colour
    outline = (190, 148, 14)    # darker border
    hole    = (148, 100,  8)    # hole colour (dark amber)

    # Wedge (isoceles triangle)
    pts = [(cx, cy - 34), (cx - 40, cy + 30), (cx + 40, cy + 30)]
    pygame.draw.polygon(surf, yellow,  pts)
    pygame.draw.polygon(surf, outline, pts, 2)

    # Holes — positions inside the triangle
    pygame.draw.circle(surf, hole, (cx,      cy +  8), 8)
    pygame.draw.circle(surf, hole, (cx - 18, cy + 20), 6)
    pygame.draw.circle(surf, hole, (cx + 17, cy + 20), 5)


def _draw_flame(surf, cx, cy, h=22):
    """Simple two-layer flame polygon for the streak counter."""
    w = h * 2 // 3
    outer = [
        (cx,           cy - h),
        (cx - w // 2,  cy - h // 2),
        (cx - w // 2 - 3, cy),
        (cx + w // 2 + 3, cy),
        (cx + w // 2,  cy - h // 2),
    ]
    inner = [
        (cx,           cy - h // 2),
        (cx - w // 3,  cy - h // 6),
        (cx - w // 3,  cy),
        (cx + w // 3,  cy),
        (cx + w // 3,  cy - h // 6),
    ]
    pygame.draw.polygon(surf, (255, 110, 20), outer)
    pygame.draw.polygon(surf, (255, 215, 30), inner)


def _spawn_particles(cx, cy, is_perfect):
    """Create a burst of particles originating from the cheese cell."""
    n = 48 if is_perfect else 28
    particles = []
    for _ in range(n):
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(90, 270)
        life  = random.uniform(0.55, 1.1)
        size  = random.randint(3, 8)
        if is_perfect:
            color = random.choice([(255, 215, 0), (255, 180, 50), (255, 240, 110)])
        else:
            color = random.choice([(88, 148, 255), (52, 200, 100), (220, 162, 28)])
        particles.append({
            "x": float(cx), "y": float(cy),
            "vx": math.cos(angle) * speed,
            "vy": math.sin(angle) * speed,
            "life": life, "max_life": life,
            "r": color[0], "g": color[1], "b": color[2],
            "size": size,
        })
    return particles


def _update_draw_particles(screen, particles, dt):
    """Advance physics and draw; removes dead particles in-place."""
    alive = []
    for p in particles:
        p["life"] -= dt
        if p["life"] <= 0:
            continue
        p["x"]  += p["vx"] * dt
        p["y"]  += p["vy"] * dt
        p["vy"] += 320 * dt   # gravity
        p["vx"] *= 0.97        # air drag
        t    = p["life"] / p["max_life"]
        size = max(1, int(p["size"] * t))
        col  = (int(p["r"] * t), int(p["g"] * t), int(p["b"] * t))
        pygame.draw.circle(screen, col, (int(p["x"]), int(p["y"])), size)
        alive.append(p)
    particles[:] = alive


def _draw_grid(screen, fonts, trial, trail, cursor, show_arrows=False):
    f_big, f_med, f_sm, f_xs = fonts
    W, H = screen.get_width(), screen.get_height()
    GL, GT, GR, GRW, CELL = _layout(W, H)
    start, goal = trial.start, trial.goal

    for r in range(GRID_N):
        for c in range(GRID_N):
            px = GL + c * CELL + 4
            py = GT + r * CELL + 4
            sz = CELL - 8
            rect = pygame.Rect(px, py, sz, sz)

            if (r, c) == goal:
                bg = CELL_GOAL
            elif (r, c) in trail:
                age = time.time() - trail[(r, c)]
                t   = min(1.0, age / TRAIL_FADE_SEC)
                bg  = (
                    int(TRAIL_FRESH[0] + (CELL_TRAIL[0] - TRAIL_FRESH[0]) * t),
                    int(TRAIL_FRESH[1] + (CELL_TRAIL[1] - TRAIL_FRESH[1]) * t),
                    int(TRAIL_FRESH[2] + (CELL_TRAIL[2] - TRAIL_FRESH[2]) * t),
                )
            elif (r, c) == start:
                bg = CELL_START
            else:
                bg = CELL_DARK

            pygame.draw.rect(screen, bg,          rect, border_radius=10)
            pygame.draw.rect(screen, GRID_BORDER, rect, width=1, border_radius=10)

            if (r, c) == goal:
                _draw_cheese_icon(screen, px + sz // 2, py + sz // 2)

    # Cursor — mouse icon travels through the grid
    if cursor:
        icx = GL + cursor[1] * CELL + CELL // 2
        icy = GT + cursor[0] * CELL + CELL // 2
        _draw_mouse_icon(screen, icx, icy)


def _stage_header(screen, fonts, tag, tag_col, title, subtitle):
    f_big, f_med, f_sm, f_xs = fonts
    W, H = screen.get_width(), screen.get_height()
    GL, GT, GR, GRW, CELL = _layout(W, H)
    _pill(screen, f_xs, tag, BG, tag_col, GL, 14)
    _t(screen, f_med, title,    WHITE, GL, 48)
    _t(screen, f_xs,  subtitle, DIM,   GL, 76)


# ── On-screen click buttons ───────────────────────────────────

def _draw_key_button(screen, fonts, rect, key_num, btns, btns_key):
    """One of the three direction-key buttons. Registers its Rect in btns."""
    f_big, f_med, f_sm, f_xs = fonts
    hover  = rect.collidepoint(pygame.mouse.get_pos())
    bg     = (44, 62, 118) if hover else (26, 32, 68)
    border = ACCENT        if hover else BORDER
    pygame.draw.rect(screen, (4, 4, 12),
                     (rect.x + 2, rect.y + 3, rect.w, rect.h), border_radius=10)
    pygame.draw.rect(screen, bg, rect, border_radius=10)
    pygame.draw.rect(screen, border, rect, width=2, border_radius=10)
    ns = f_med.render(str(key_num), True, WHITE)
    screen.blit(ns, (rect.centerx - ns.get_width() // 2,
                     rect.centery - ns.get_height() // 2))
    btns[btns_key] = rect


def _draw_cmd_button(screen, fonts, rect, label, color, enabled, btns, btns_key):
    """Undo / Confirm button. Greyed out when not enabled."""
    f_big, f_med, f_sm, f_xs = fonts
    hover = enabled and rect.collidepoint(pygame.mouse.get_pos())
    if not enabled:
        bg = (16, 18, 34); border = (30, 30, 52); tc = (60, 60, 90)
    elif hover:
        r, g, b = color
        bg = (min(255, r + 30), min(255, g + 30), min(255, b + 30))
        border = color; tc = (8, 8, 16)
    else:
        r, g, b = color
        bg = (r // 3, g // 3, b // 3)
        border = color; tc = WHITE
    pygame.draw.rect(screen, (4, 4, 12),
                     (rect.x + 2, rect.y + 3, rect.w, rect.h), border_radius=10)
    pygame.draw.rect(screen, bg, rect, border_radius=10)
    pygame.draw.rect(screen, border, rect, width=2, border_radius=10)
    ls = f_sm.render(label, True, tc)
    screen.blit(ls, (rect.centerx - ls.get_width() // 2,
                     rect.centery - ls.get_height() // 2))
    btns[btns_key] = rect


# ── Pause overlay ─────────────────────────────────────────────

def _draw_pause_overlay(screen, fonts, trial, total, block_type, sn):
    f_big, f_med, f_sm, f_xs = fonts
    W, H = screen.get_width(), screen.get_height()
    cx, cy = W // 2, H // 2

    dim = pygame.Surface((W, H), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 160))
    screen.blit(dim, (0, 0))

    card_w, card_h = 380, 260
    card_x = cx - card_w // 2
    card_y = cy - card_h // 2
    pygame.draw.rect(screen, (22, 22, 40), (card_x, card_y, card_w, card_h), border_radius=16)
    pygame.draw.rect(screen, BORDER,       (card_x, card_y, card_w, card_h), width=1, border_radius=16)

    ts = f_big.render("Paused", True, WHITE)
    screen.blit(ts, (cx - ts.get_width() // 2, card_y + 22))

    info = f_xs.render(
        f"Trial {trial.trial_number} of {total}  ·  "
        f"{block_type.replace('_',' ').title()}  ·  Session {sn}",
        True, DIM)
    screen.blit(info, (cx - info.get_width() // 2, card_y + 66))

    pygame.draw.line(screen, BORDER,
                     (card_x + 24, card_y + 92), (card_x + card_w - 24, card_y + 92))

    resume_r = pygame.Rect(cx - 160, card_y + 110, 148, 46)
    mouse = pygame.mouse.get_pos()
    rc = tuple(min(255, c + 20) for c in CORRECT) if resume_r.collidepoint(mouse) else CORRECT
    pygame.draw.rect(screen, (8, 8, 16),
                     (resume_r.x + 2, resume_r.y + 3, resume_r.w, resume_r.h), border_radius=10)
    pygame.draw.rect(screen, rc, resume_r, border_radius=10)
    rl = f_sm.render("Resume", True, (10, 10, 20))
    screen.blit(rl, (resume_r.x + resume_r.w // 2 - rl.get_width() // 2,
                     resume_r.y + resume_r.h // 2 - rl.get_height() // 2))

    exit_r = pygame.Rect(cx + 12, card_y + 110, 148, 46)
    DANGER = (180, 50, 50)
    ec = tuple(min(255, c + 20) for c in DANGER) if exit_r.collidepoint(mouse) else DANGER
    pygame.draw.rect(screen, (8, 8, 16),
                     (exit_r.x + 2, exit_r.y + 3, exit_r.w, exit_r.h), border_radius=10)
    pygame.draw.rect(screen, ec, exit_r, border_radius=10)
    el = f_sm.render("Save & Exit", True, WHITE)
    screen.blit(el, (exit_r.x + exit_r.w // 2 - el.get_width() // 2,
                     exit_r.y + exit_r.h // 2 - el.get_height() // 2))

    hint = f_xs.render("P or ESC to resume", True, DIM)
    screen.blit(hint, (cx - hint.get_width() // 2, card_y + 178))
    warning = f_xs.render("Progress up to this trial is already saved.", True, DIM)
    screen.blit(warning, (cx - warning.get_width() // 2, card_y + 210))

    return resume_r, exit_r


# ── Main trial runner ─────────────────────────────────────────

def run_trial(screen, clock, fonts, trial: TrialData, config: dict,
              cumulative_score: int, session_id: int,
              total_trials: int = 20, block_type: str = "practice",
              streak: int = 0) -> dict:

    f_big, f_med, f_sm, f_xs = fonts
    W, H = screen.get_width(), screen.get_height()

    state           = PLANNING
    pre_pause_state = PLANNING
    planning_start  = time.time()
    first_key_time  = None
    last_key_time   = None
    sbar_down_t     = None
    cursor          = trial.start
    trail           = {}
    typed_seq       = []
    action_path     = []
    feedback_start  = None
    iti_start       = None
    countdown_start = None
    action_start    = None
    trial_id        = None
    blink_on        = True
    blink_t         = pygame.time.get_ticks()
    pause_rect      = None
    btns            = {}   # on-screen button rects; populated each draw frame

    particles         = []
    particles_spawned = False
    last_frame_t      = time.time()
    mi_space_held     = False
    mi_space_start    = None
    pp_anim_step      = 0
    pp_anim_timer     = 0
    pp_anim_done      = False
    pp_scored         = False   # True once _finalise called on anim complete

    # Replay
    rp_step      = 0
    rp_timer     = 0
    rp_cursor    = trial.start
    rp_trail     = {}
    rp_done      = False
    rp_done_time = None   # when replay finished; feedback lingers fb_time more seconds

    trial.trial_start_time = time.time()

    is_mi   = _is_mi(trial.group)
    is_pp   = _is_pp(trial.group)
    is_ctrl = _is_ctrl(trial.group)

    # Fam / pre-test / post-test always use PP action; feedback is suppressed
    if block_type in ("familiarization", "pre_test", "post_test"):
        is_mi   = False
        is_ctrl = False
        is_pp   = True
    show_feedback = block_type not in ("familiarization", "pre_test", "post_test")

    p_time  = config.get("planning_time",   6)
    a_time  = config.get("action_time",     10)
    fb_time = config.get("feedback_time",   4)
    # Jitter ITI between 3 and 5 seconds
    iti_dur = random.uniform(3.0, 5.0)
    sn      = config.get("session_number",  1)

    REPLAY_MS = 520

    def enter_feedback():
        nonlocal state, feedback_start, rp_step, rp_timer, rp_cursor, rp_trail, rp_done, rp_done_time
        state = FEEDBACK
        feedback_start = time.time()
        rp_step = 0; rp_timer = pygame.time.get_ticks()
        rp_cursor = trial.start; rp_trail = {}; rp_done = False; rp_done_time = None

    def enter_countdown():
        nonlocal state, countdown_start
        state = COUNTDOWN
        countdown_start = time.time()

    def enter_iti():
        nonlocal state, iti_start
        state = ITI
        iti_start = time.time()

    while True:
        now_ms       = pygame.time.get_ticks()
        now_s        = time.time()
        dt           = now_s - last_frame_t
        last_frame_t = now_s
        elapsed      = now_s - planning_start
        events  = pygame.event.get()

        for ev in events:
            if ev.type == pygame.QUIT:
                pygame.quit(); import sys; sys.exit()

            # Pause toggle
            if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_p, pygame.K_ESCAPE):
                if state == PAUSED:
                    state = pre_pause_state
                elif state not in (DONE,):
                    pre_pause_state = state; state = PAUSED

            # MI imagery: hold SPACE → release to record duration and advance
            if state == ACTION and is_mi:
                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_SPACE:
                    if not mi_space_held:
                        mi_space_held  = True
                        mi_space_start = time.time()
                elif ev.type == pygame.KEYUP and ev.key == pygame.K_SPACE:
                    if mi_space_held and mi_space_start:
                        trial.imagery_duration_ms = (time.time() - mi_space_start) * 1000
                        mi_space_held = False
                        _finalise(trial, trial.planned_sequence, session_id)
                        trial_id = _save(trial, session_id)
                        update_session_progress(session_id, trial.trial_number)
                        enter_feedback() if show_feedback else enter_iti()

            # PP: SPACE to confirm after auto-animation completes
            if (state == ACTION and is_pp and pp_anim_done
                    and ev.type == pygame.KEYDOWN and ev.key == pygame.K_SPACE):
                if not pp_scored:
                    _finalise(trial, trial.planned_sequence, session_id)
                trial_id = _save(trial, session_id)
                update_session_progress(session_id, trial.trial_number)
                enter_feedback() if show_feedback else enter_iti()

            if ev.type == pygame.MOUSEBUTTONDOWN and state != PAUSED:
                if pause_rect and pause_rect.collidepoint(ev.pos):
                    pre_pause_state = state; state = PAUSED

                elif state == INPUT and ev.button == 1:
                    p = ev.pos
                    for k in (1, 2, 3):
                        if btns.get(f"key{k}") and btns[f"key{k}"].collidepoint(p):
                            now_t  = time.time()
                            if first_key_time is None: first_key_time = now_t
                            before = _build_path(trial.start, typed_seq)[-1]
                            nxt    = apply_key(before[0], before[1], k)
                            after  = nxt if nxt else before
                            iki    = (now_t - last_key_time) * 1000 if last_key_time else None
                            trial.keypresses_log.append({
                                "key":    k,
                                "before": before,
                                "after":  after,
                                "abs_ms": now_t * 1000,
                                "rel_ms": (now_t - planning_start) * 1000,
                                "iki_ms": iki,
                            })
                            last_key_time = now_t
                            typed_seq.append(k)
                            break
                    else:
                        if btns.get("confirm") and btns["confirm"].collidepoint(p) and typed_seq:
                            if first_key_time:
                                trial.reaction_time_ms = (first_key_time - planning_start) * 1000
                            trial.planned_sequence = list(typed_seq)
                            action_path = _build_path(trial.start, typed_seq)
                            if is_ctrl:
                                _finalise(trial, typed_seq, session_id)
                                trial_id = _save(trial, session_id)
                                update_session_progress(session_id, trial.trial_number)
                                enter_feedback() if show_feedback else enter_iti()
                            else:
                                enter_countdown()

            if state == PAUSED and ev.type == pygame.MOUSEBUTTONDOWN:
                resume_r, exit_r = _draw_pause_overlay(screen, fonts, trial,
                                                        total_trials, block_type, sn)
                if resume_r.collidepoint(ev.pos):
                    state = pre_pause_state
                elif exit_r.collidepoint(ev.pos):
                    return {"paused_exit": True, "reward_score": 0,
                            "is_correct": False, "cumulative_score": cumulative_score,
                            "trial_id": None}

            if state == PAUSED:
                continue
            # ACTION: MI — no interaction; auto-advances via timer below

            # FEEDBACK: SPACE to continue once replay has finished
            if (state == FEEDBACK and rp_done
                    and ev.type == pygame.KEYDOWN and ev.key == pygame.K_SPACE):
                state = ITI; iti_start = now_s

        # Auto-transitions
        if state == PLANNING and elapsed >= p_time:
            state = INPUT; typed_seq = []; first_key_time = None

        if state == COUNTDOWN and countdown_start:
            if (now_s - countdown_start) >= 3.0:
                state        = ACTION
                action_start = now_s
                cursor       = trial.start
                trail        = {}
                if is_mi: sbar_down_t = None
                if is_pp:
                    pp_anim_step  = 0
                    pp_anim_timer = now_ms
                    pp_anim_done  = False

        if state == ACTION and is_pp and not pp_anim_done:
            if now_ms - pp_anim_timer >= REPLAY_MS:
                pp_anim_timer = now_ms
                if pp_anim_step < len(action_path) - 1:
                    trail[cursor] = time.time()
                    pp_anim_step += 1
                    cursor = action_path[pp_anim_step]
                else:
                    pp_anim_done = True
                    if not pp_scored:
                        _finalise(trial, trial.planned_sequence, session_id)
                        pp_scored = True

        if state == FEEDBACK and not rp_done:
            if now_ms - rp_timer >= REPLAY_MS:
                rp_timer = now_ms
                if rp_step < len(action_path) - 1:
                    rp_trail[rp_cursor] = time.time(); rp_step += 1
                    rp_cursor = action_path[rp_step]
                else:
                    rp_done = True
                    rp_done_time = now_s   # record when replay finished

        # Safety auto-advance if participant doesn't press SPACE within 30 s
        if state == FEEDBACK and rp_done and rp_done_time:
            if (now_s - rp_done_time) >= 30.0:
                state = ITI; iti_start = now_s

        if state == ITI and iti_start:
            if (now_s - iti_start) >= iti_dur:
                state = DONE

        if state == DONE:
            break

        if now_ms - blink_t > 520:
            blink_on = not blink_on; blink_t = now_ms

        # ── Draw ─────────────────────────────────────────────
        btns.clear()
        screen.fill(BG)
        draw_state = pre_pause_state if state == PAUSED else state

        if draw_state == PLANNING:
            pause_rect = _draw_stage_planning(screen, fonts, trial, elapsed, p_time,
                                              total_trials, block_type, sn,
                                              cum_score=cumulative_score)
        elif draw_state == INPUT:
            pause_rect = _draw_stage_input(screen, fonts, trial, typed_seq, blink_on,
                                           total_trials, block_type, sn, btns,
                                           cum_score=cumulative_score)
        elif draw_state == COUNTDOWN:
            pause_rect = _draw_stage_countdown(screen, fonts, trial, countdown_start,
                                               total_trials, block_type, sn,
                                               cum_score=cumulative_score)
        elif draw_state == ACTION:
            pause_rect = _draw_stage_action(screen, fonts, trial, cursor, trail,
                                            typed_seq, is_mi, is_pp, sbar_down_t,
                                            total_trials, block_type, sn,
                                            a_time, action_start, btns,
                                            mi_space_held=mi_space_held,
                                            mi_space_start=mi_space_start,
                                            pp_anim_done=pp_anim_done,
                                            cum_score=cumulative_score)
        elif draw_state == FEEDBACK:
            if not particles_spawned:
                _GL, _GT, _GR, _GRW, _CELL = _layout(W, H)
                goal_r, goal_c = trial.goal
                _pcx = _GL + goal_c * _CELL + _CELL // 2
                _pcy = _GT + goal_r * _CELL + _CELL // 2
                if trial.is_correct:
                    particles = _spawn_particles(
                        _pcx, _pcy, trial.reward_score == OPTIMAL_SCORE)
                particles_spawned = True
            pause_rect = _draw_stage_feedback(screen, fonts, trial, cumulative_score,
                                              rp_cursor, rp_trail, rp_done,
                                              total_trials, block_type, sn,
                                              streak=streak)
            if particles:
                _update_draw_particles(screen, particles, dt)
        elif draw_state == ITI:
            pause_rect = _draw_stage_iti(screen, fonts, trial, iti_start, iti_dur,
                                         total_trials, block_type, sn,
                                         cum_score=cumulative_score + trial.reward_score)

        if state == PAUSED:
            _draw_pause_overlay(screen, fonts, trial, total_trials, block_type, sn)

        pygame.display.flip()
        clock.tick(60)

    # Save INPUT-phase keypresses (logged for all groups)
    if trial_id and trial.keypresses_log:
        for kp in trial.keypresses_log:
            save_keypress(
                trial_id=trial_id, participant_id=trial.participant_id,
                key_pressed=kp["key"],
                cursor_row_before=kp["before"][0], cursor_col_before=kp["before"][1],
                cursor_row_after=kp["after"][0],   cursor_col_after=kp["after"][1],
                timestamp_ms=kp["abs_ms"],
                time_since_trial_start_ms=kp["rel_ms"],
                time_since_last_press_ms=kp["iki_ms"],
            )

    new_streak = (streak + 1) if trial.is_correct else 0
    return {
        "reward_score":     trial.reward_score,
        "is_correct":       trial.is_correct,
        "cumulative_score": cumulative_score + trial.reward_score,
        "trial_id":         trial_id,
        "streak":           new_streak,
    }


# ── Finalise & save ───────────────────────────────────────────

def _finalise(trial, used_seq, session_id):
    pos = trial.start
    oob = 0
    for k in used_seq:
        nxt = apply_key(pos[0], pos[1], k)
        if nxt:
            pos = nxt
        else:
            oob += 1
    trial.oob_count = oob
    score, n, ok = _score(used_seq, trial.optimal_sequence, pos, trial.goal)
    trial.reward_score = score; trial.number_of_moves = n; trial.is_correct = ok

def _save(trial, session_id):
    import json
    all_opt_json = (json.dumps(trial.all_optimal_sequences)
                    if trial.all_optimal_sequences else None)
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
        all_optimal_sequences=all_opt_json,
        oob_count=trial.oob_count,
    )


# ── Score breakdown card (shared by ACTION preview + FEEDBACK) ─

def _draw_score_card(screen, fonts, trial, rx, ry, GRW):
    """
    Draws a self-sizing score breakdown card.
    Returns new ry = bottom of card + 8.
    """
    f_big, f_med, f_sm, f_xs = fonts
    rc      = CORRECT if trial.is_correct else WRONG
    opt_len = len(trial.optimal_sequence)
    n_moves = trial.number_of_moves
    extra   = max(0, n_moves - opt_len)
    penalty = extra * EXTRA_MOVE_PENALTY

    PAD  = 14
    LH   = f_xs.get_height() + 10   # height of one data row
    LCOL = rx + PAD
    RCOL = rx + GRW - PAD

    # ── Build row list ─────────────────────────────────────────
    # Each entry: (label_str, value_str, lbl_col, val_col)  OR  "div" / "div2"
    rows = []
    if not trial.is_correct:
        rows = [
            ("Result",      "Goal not reached", DIM, WRONG),
            ("Your score",  "0 pts",            DIM, WRONG),
        ]
    else:
        mc = CORRECT if extra == 0 else (AMBER if extra <= 2 else WRONG)
        rows = [
            ("Moves you took",  str(n_moves),           DIM, mc),
            ("Optimal path",    f"{opt_len} moves",      DIM, ACCENT),
        ]
        if extra > 0:
            rows.append(("Extra moves",
                         f"{n_moves} − {opt_len} = {extra}",
                         DIM, WRONG))
        rows.append("div")
        rows.append(("Max possible score", f"{OPTIMAL_SCORE} pts", DIM, WHITE))
        if extra > 0:
            rows.append((f"Penalty  ({extra} × {EXTRA_MOVE_PENALTY} pts each)",
                         f"−{penalty} pts", DIM, WRONG))
        rows.append("div2")

    # ── Calculate card height ──────────────────────────────────
    hdr_h   = f_xs.get_height() + 10
    body_h  = sum(LH if isinstance(r, tuple) else (6 if r == "div" else 14)
                  for r in rows)
    score_h = f_med.get_height() + PAD + 8
    oob_h   = (f_xs.get_height() + 16) if trial.oob_count > 0 else 0
    card_h  = 4 + PAD + hdr_h + body_h + score_h + oob_h + PAD

    # ── Card background ────────────────────────────────────────
    pygame.draw.rect(screen, (10, 14, 32), (rx, ry, GRW, card_h), border_radius=12)
    pygame.draw.rect(screen, BORDER,       (rx, ry, GRW, card_h), width=1, border_radius=12)
    pygame.draw.rect(screen, rc,           (rx, ry, GRW, 4),      border_radius=12)

    cy = ry + 4 + PAD

    # Header
    hs = f_xs.render("SCORE BREAKDOWN", True, DIM)
    screen.blit(hs, (LCOL, cy));  cy += hs.get_height() + 10

    # Rows
    for row in rows:
        if row == "div":
            pygame.draw.line(screen, BORDER,
                             (LCOL, cy + 2), (RCOL, cy + 2));  cy += 6
        elif row == "div2":
            pygame.draw.line(screen, BORDER2,
                             (LCOL, cy + 4), (RCOL, cy + 4));  cy += 14
        else:
            lbl, val, lc, vc = row
            ls = f_xs.render(lbl, True, lc)
            vs = f_sm.render(val, True, vc)
            row_cy = cy + (LH - ls.get_height()) // 2
            screen.blit(ls, (LCOL, row_cy))
            screen.blit(vs, (RCOL - vs.get_width(),
                              cy + (LH - vs.get_height()) // 2))
            cy += LH

    # Big YOUR SCORE line
    lbl_s = f_xs.render("YOUR SCORE", True, DIM)
    scr_s = f_med.render(f"{trial.reward_score} pts", True, rc)
    mid_y  = cy + scr_s.get_height() // 2
    screen.blit(lbl_s, (LCOL, mid_y - lbl_s.get_height() // 2))
    screen.blit(scr_s, (RCOL - scr_s.get_width(), cy))
    cy += scr_s.get_height() + PAD

    # OOB warning (inside card at bottom)
    if trial.oob_count > 0:
        ob_s = f_xs.render(
            f"⚠  {trial.oob_count} move{'s' if trial.oob_count > 1 else ''} hit the boundary — cursor stayed",
            True, (255, 160, 80))
        screen.blit(ob_s, (LCOL, cy))
        cy += ob_s.get_height()

    return ry + card_h + 8


# ── Stage drawing ─────────────────────────────────────────────

def _draw_stage_planning(screen, fonts, trial, elapsed, p_time,
                         total_trials, block_type, sn, cum_score: int = 0):
    f_big, f_med, f_sm, f_xs = fonts
    W, H = screen.get_width(), screen.get_height()
    GL, GT, GR, GRW, CELL = _layout(W, H)

    rem = max(0, p_time - elapsed)
    tc  = WRONG if rem < 2 else (AMBER if rem < 4 else WHITE)

    _stage_header(screen, fonts,
                  "PLANNING", ACCENT,
                  "Study the grid",
                  "Plan the shortest route from MOUSE to CHEESE   ·   Grid hides when timer ends")
    _draw_grid(screen, fonts, trial, {}, trial.start)

    rx, ry = GR, GT

    _panel(screen, rx, ry, GRW, 100, BORDER)
    ts = f_big.render(f"{rem:.1f}s", True, tc)
    screen.blit(ts, (rx + GRW // 2 - ts.get_width() // 2, ry + 12))
    tl = f_xs.render("Time remaining", True, DIM)
    screen.blit(tl, (rx + GRW // 2 - tl.get_width() // 2, ry + 72))
    ry += 116

    if block_type != "familiarization":
        badge_col = ACCENT if trial.grid_type == "repeated" else AMBER
        _pill(screen, f_xs, f"  {trial.grid_type.upper()}  ", BG, badge_col, rx, ry)

    return _draw_progress(screen, fonts, trial, total_trials, block_type, sn,
                          cum_score=cum_score)


def _draw_stage_input(screen, fonts, trial, typed_seq, blink_on,
                      total_trials, block_type, sn, btns, cum_score: int = 0):
    f_big, f_med, f_sm, f_xs = fonts
    W, H = screen.get_width(), screen.get_height()
    GL, GT, GR, GRW, CELL = _layout(W, H)

    _stage_header(screen, fonts,
                  "INPUT", WHITE,
                  "Enter your planned sequence — grid is hidden",
                  "Click the direction buttons to build your sequence")

    # Grid hidden — ghost cell outlines + centre message
    for r in range(GRID_N):
        for c in range(GRID_N):
            gr = pygame.Rect(GL + c * CELL + 4, GT + r * CELL + 4, CELL - 8, CELL - 8)
            pygame.draw.rect(screen, (16, 16, 32), gr, border_radius=10)
            pygame.draw.rect(screen, (32, 32, 54), gr, width=1, border_radius=10)

    grid_cx = GL + (GRID_N * CELL) // 2
    grid_cy = GT + (GRID_N * CELL) // 2
    mem_s = f_med.render("Recall from memory", True, (46, 46, 76))
    screen.blit(mem_s, (grid_cx - mem_s.get_width() // 2, grid_cy - 20))
    sub_s = f_xs.render("Grid is hidden — plan from memory", True, (34, 34, 58))
    screen.blit(sub_s, (grid_cx - sub_s.get_width() // 2, grid_cy + 14))

    rx, ry = GR, GT

    # ── Sequence display ──────────────────────────────────────
    _panel(screen, rx, ry, GRW, 110, ACCENT)
    _t(screen, f_xs, "Your sequence", DIM, rx + 14, ry + 10)

    seq_str = ", ".join(str(k) for k in typed_seq) if typed_seq else "—"
    seq_col = WHITE if typed_seq else DIM
    ss = f_sm.render(seq_str, True, seq_col)
    screen.blit(ss, (rx + 14, ry + 36))

    if blink_on and typed_seq:
        bx = rx + 14 + ss.get_width() + 5
        pygame.draw.rect(screen, ACCENT, (bx, ry + 36, 2, ss.get_height()))

    cnt = f_xs.render(f"{len(typed_seq)} key(s) entered", True, DIM)
    screen.blit(cnt, (rx + 14, ry + 82))
    ry += 120

    # ── Direction buttons (1 / 2 / 3) ────────────────────────
    btn_w = (GRW - 24) // 3   # 3 buttons, 12px gaps
    btn_h = 68
    for i, k in enumerate((1, 2, 3)):
        _draw_key_button(screen, fonts,
                         pygame.Rect(rx + i * (btn_w + 12), ry, btn_w, btn_h),
                         k, btns, f"key{k}")
    ry += btn_h + 10

    # ── Confirm ───────────────────────────────────────────────
    has_seq = bool(typed_seq)
    _draw_cmd_button(screen, fonts,
                     pygame.Rect(rx, ry, GRW, 52),
                     "Confirm", CORRECT, has_seq, btns, "confirm")
    ry += 60

    return _draw_progress(screen, fonts, trial, total_trials, block_type, sn,
                          cum_score=cum_score)


def _draw_stage_countdown(screen, fonts, trial, countdown_start,
                          total_trials, block_type, sn, cum_score: int = 0):
    global _COUNTDOWN_FONT
    if _COUNTDOWN_FONT is None:
        _COUNTDOWN_FONT = pygame.font.SysFont("Helvetica Neue", 140, bold=True)

    f_big, f_med, f_sm, f_xs = fonts
    W, H = screen.get_width(), screen.get_height()
    cx, cy = W // 2, H // 2

    elapsed_cd = max(0.0, time.time() - (countdown_start or time.time()))
    cd_num     = max(1, 3 - int(elapsed_cd))    # 3, 2, 1

    # Pulsing ring around number
    pulse  = 0.5 + 0.5 * math.sin(elapsed_cd * math.pi * 2)
    radius = int(80 + 12 * pulse)
    alpha  = int(120 + 80 * pulse)
    ring   = pygame.Surface((radius * 2 + 4, radius * 2 + 4), pygame.SRCALPHA)
    pygame.draw.circle(ring, (*ACCENT, alpha),
                       (radius + 2, radius + 2), radius, 6)
    screen.blit(ring, (cx - radius - 2, cy - radius - 30 - 2))

    # Big number — use cached font
    ns = _COUNTDOWN_FONT.render(str(cd_num), True, WHITE)
    screen.blit(ns, (cx - ns.get_width() // 2, cy - ns.get_height() // 2 - 30))

    # Labels
    ready_s = f_med.render("Get ready to execute", True, DIM)
    screen.blit(ready_s, (cx - ready_s.get_width() // 2, cy + 80))

    seq_str = "   →   ".join(str(k) for k in trial.planned_sequence)
    seq_s   = f_sm.render(f"Sequence:  {seq_str}", True, ACCENT)
    screen.blit(seq_s, (cx - seq_s.get_width() // 2, cy + 118))

    return _draw_progress(screen, fonts, trial, total_trials, block_type, sn,
                          cum_score=cum_score)


def _draw_stage_action(screen, fonts, trial, cursor, trail,
                       typed_seq, is_mi, is_pp, sbar_down_t,
                       total_trials, block_type, sn,
                       a_time=10, action_start=None, btns=None,
                       mi_space_held=False, mi_space_start=None,
                       pp_anim_done=False, cum_score: int = 0):
    f_big, f_med, f_sm, f_xs = fonts
    W, H = screen.get_width(), screen.get_height()
    GL, GT, GR, GRW, CELL = _layout(W, H)
    cx = W // 2

    if is_mi:
        _stage_header(screen, fonts,
                      "IMAGERY", CORRECT,
                      "Motor Imagery",
                      "Vividly imagine pressing your planned sequence from MOUSE to CHEESE")

        seq_str = ", ".join(str(k) for k in trial.planned_sequence)
        _tc(screen, f_med, f"Your sequence:  {seq_str}", ACCENT, H // 2 - 100)

        if not mi_space_held:
            prompt = f_med.render("Press and hold  SPACE  to begin imagery", True, ACCENT)
            screen.blit(prompt, (cx - prompt.get_width() // 2, H // 2 - 20))
            hint = f_xs.render("Hold until your imagined movement is complete", True, DIM)
            screen.blit(hint, (cx - hint.get_width() // 2, H // 2 + 24))
        else:
            elapsed_img = time.time() - mi_space_start if mi_space_start else 0
            pulse  = 0.5 + 0.5 * math.sin(elapsed_img * math.pi * 1.8)
            tc     = tuple(int(CORRECT[i] * pulse + (1 - pulse) * 200) for i in range(3))
            status = f_med.render(f"Imagining…   {elapsed_img:.1f}s", True, tc)
            screen.blit(status, (cx - status.get_width() // 2, H // 2 - 20))
            rel = f_xs.render("Release  SPACE  when your imagery is complete", True, DIM)
            screen.blit(rel, (cx - rel.get_width() // 2, H // 2 + 24))

    else:  # PP — auto-animate planned sequence on grid
        _stage_header(screen, fonts,
                      "ACTION", CORRECT,
                      "Watch your planned sequence execute",
                      "The cursor follows your planned route automatically")
        _draw_grid(screen, fonts, trial, trail, cursor)

        rx, ry = GR, GT
        seq_str = ", ".join(str(k) for k in trial.planned_sequence)
        _panel(screen, rx, ry, GRW, 80, ACCENT)
        _t(screen, f_xs, "Your planned sequence", DIM, rx + 14, ry + 10)
        ss = f_sm.render(seq_str, True, WHITE)
        screen.blit(ss, (rx + 14, ry + 34))
        ry += 92

        if pp_anim_done:
            ry = _draw_score_card(screen, fonts, trial, rx, ry, GRW)
            pulse = 0.55 + 0.45 * math.sin(time.time() * math.pi * 1.6)
            pc = tuple(int(c * pulse) for c in ACCENT)
            hs = f_sm.render("Press  SPACE  to continue", True, pc)
            screen.blit(hs, (rx + GRW // 2 - hs.get_width() // 2, ry + 6))
        else:
            dot_n  = int(time.time() * 2) % 4
            anim_s = f_xs.render("Executing" + "." * dot_n, True, DIM)
            screen.blit(anim_s, (rx + GRW // 2 - anim_s.get_width() // 2, ry + 18))

    return _draw_progress(screen, fonts, trial, total_trials, block_type, sn,
                          cum_score=cum_score)


def _draw_stage_feedback(screen, fonts, trial, cum_score,
                         rp_cursor, rp_trail, rp_done,
                         total_trials, block_type, sn,
                         streak: int = 0):
    f_big, f_med, f_sm, f_xs = fonts
    W, H = screen.get_width(), screen.get_height()
    GL, GT, GR, GRW, CELL = _layout(W, H)

    if trial.is_correct:
        result_label, rc = "CORRECT", CORRECT
    else:
        result_label, rc = "MISSED", WRONG

    all_opt = trial.all_optimal_sequences or [trial.optimal_sequence]
    n_opt   = len(all_opt)
    opt_len = len(all_opt[0])
    n_moves = trial.number_of_moves
    extra   = max(0, n_moves - opt_len)
    new_total = cum_score + trial.reward_score

    if not trial.is_correct:
        formula = "0 pts  —  goal not reached"
    elif extra == 0:
        formula = f"{OPTIMAL_SCORE} pts  —  no extra moves!"
    else:
        formula = f"{OPTIMAL_SCORE} - {extra} x {EXTRA_MOVE_PENALTY} = {trial.reward_score} pts"

    # ── Animated replay grid (fills full left column) ─────────
    _draw_grid(screen, fonts, trial, rp_trail, rp_cursor)

    # ── Right panel ───────────────────────────────────────────
    rx, ry = GR, GT

    # Result banner — full panel width
    pygame.draw.rect(screen, (4, 4, 12),
                     (rx + 3, ry + 4, GRW, 62), border_radius=12)
    pygame.draw.rect(screen, rc, (rx, ry, GRW, 62), border_radius=12)
    rs = f_big.render(result_label, True, (8, 8, 16))
    screen.blit(rs, (rx + GRW // 2 - rs.get_width() // 2,
                     ry + 31 - rs.get_height() // 2))
    ry += 70

    # Streak indicator
    display_streak = (streak + 1) if trial.is_correct else 0
    if display_streak >= 2:
        sh = 44
        pygame.draw.rect(screen, (36, 18, 4),    (rx, ry, GRW, sh), border_radius=10)
        pygame.draw.rect(screen, (200, 100, 20), (rx, ry, GRW, sh), width=1, border_radius=10)
        _draw_flame(screen, rx + 26, ry + sh - 4, h=24)
        sl = f_sm.render(f"x{display_streak}  Streak!", True, (255, 165, 40))
        screen.blit(sl, (rx + 52, ry + sh // 2 - sl.get_height() // 2))
        ry += sh + 8

    # ── Score breakdown card ──────────────────────────────────
    ry = _draw_score_card(screen, fonts, trial, rx, ry, GRW)

    # ── Session total ─────────────────────────────────────────
    _panel(screen, rx, ry, GRW, 60, CORRECT)
    _t(screen, f_xs, "SESSION TOTAL", DIM, rx + 16, ry + 8)
    tot_s = f_med.render(f"{new_total} pts", True, CORRECT)
    screen.blit(tot_s, (rx + GRW - tot_s.get_width() - 16, ry + 12))
    ry += 68

    # ── Your sequence ─────────────────────────────────────────
    p_str = ", ".join(str(k) for k in trial.planned_sequence) or "—"
    _t(screen, f_xs, "Your sequence", DIM,   rx + 14, ry)
    _t(screen, f_sm, p_str,           WHITE, rx + 14, ry + 18)
    ry += 44

    # ── Press SPACE ───────────────────────────────────────────
    ry += 6
    if rp_done:
        pulse = 0.55 + 0.45 * math.sin(time.time() * math.pi * 1.6)
        pc = tuple(int(c * pulse) for c in ACCENT)
        hs = f_sm.render("Press  SPACE  to continue", True, pc)
        screen.blit(hs, (rx + GRW // 2 - hs.get_width() // 2, ry))

    return _draw_progress(screen, fonts, trial, total_trials, block_type, sn,
                          cum_score=new_total)


def _draw_stage_iti(screen, fonts, trial, iti_start, iti_dur,
                    total_trials, block_type, sn, cum_score: int = 0):
    f_big, f_med, f_sm, f_xs = fonts
    W, H = screen.get_width(), screen.get_height()
    cx, cy = W // 2, H // 2 - 30

    elapsed   = time.time() - (iti_start or time.time())
    remaining = max(0, iti_dur - elapsed)

    pulse   = 0.5 + 0.5 * math.sin(elapsed * math.pi * 1.6)
    r_inner = int(38 + 6  * pulse)
    r_outer = int(52 + 10 * pulse)
    alpha   = int(60 + 60 * pulse)

    ring_surf = pygame.Surface((r_outer * 2 + 4, r_outer * 2 + 4), pygame.SRCALPHA)
    pygame.draw.circle(ring_surf, (*ACCENT, alpha),
                       (r_outer + 2, r_outer + 2), r_outer)
    pygame.draw.circle(ring_surf, (*BG, 255),
                       (r_outer + 2, r_outer + 2), r_inner)
    screen.blit(ring_surf, (cx - r_outer - 2, cy - r_outer - 2))

    gr = f_big.render("Get Ready", True, WHITE)
    screen.blit(gr, (cx - gr.get_width() // 2, cy + r_outer + 16))

    next_lbl = f_xs.render(
        f"Trial  {trial.trial_number}  of  {total_trials}  starting…", True, DIM)
    screen.blit(next_lbl, (cx - next_lbl.get_width() // 2, cy + r_outer + 58))

    return _draw_progress(screen, fonts, trial, total_trials, block_type, sn,
                          cum_score=cum_score)
