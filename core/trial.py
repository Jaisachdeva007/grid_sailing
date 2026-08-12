# ============================================================
#  GRID-SAILING TASK — Trial Engine
#
#  You don't need to touch this file.
#
#  This file runs one trial from start to finish. Every time a
#  participant presses keys on the keypad, this is what's running.
#  Trials go through these stages in order:
#
#    PLANNING   — The grid appears with the start + goal positions.
#                 Participant studies it. Timer counts down.
#                 Duration set by PLANNING_TIME_SEC in config.py
#
#    INPUT      — Participant types their sequence (keys 1, 2, 3).
#                 They can watch the cursor move as they type.
#                 SPACE confirms early; timer runs out otherwise.
#                 Duration set by INPUT_TIME_SEC in config.py
#
#    COUNTDOWN  — A quick 3-2-1 visual before the action phase.
#
#    ACTION     — MI groups:   imagine doing the movement (grid hidden).
#                 PP groups:   physically press the keys again (grid hidden).
#                 CTRL groups: just wait, nothing required.
#                 Duration set by ACTION_TIME_SEC in config.py
#
#    FEEDBACK   — Shows CORRECT / MISSED, the score breakdown, and a
#                 slow-motion replay of their cursor path on the grid.
#                 Duration set by FEEDBACK_TIME_SEC in config.py
#
#    ITI        — "Get Ready" pause before the next trial starts.
#                 Duration set by INTERTRIAL_SEC in config.py
#
#    DONE       — Trial is complete; control returns to session manager.
#
#  Scoring:
#    Correct + exactly optimal moves → 100 pts (OPTIMAL_SCORE)
#    Correct + any deviation        → 100 − |deviation| × 5 pts (EXTRA_MOVE_PENALTY)
#    Did not reach goal             → 0 pts (ERROR_SCORE)
#  All scoring values are set in config.py.
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
    # All 3 keys must appear in the executed sequence — reaching the goal via
    # a path that skips one key type is treated as unsuccessful.
    if not {1, 2, 3}.issubset(set(planned)):
        return ERROR_SCORE, n, False
    extra = abs(n - opt)   # penalise both more AND fewer moves than optimal
    return max(0, OPTIMAL_SCORE - extra * EXTRA_MOVE_PENALTY), n, True


def _build_path(start, seq):
    pos, path = start, [start]
    for k in seq:
        nxt = apply_key(pos[0], pos[1], k)
        pos = nxt if nxt else pos
        path.append(pos)
    return path


# ── Layout ────────────────────────────────────────────────────

PROG_H = 36   # progress bar height — referenced inside _layout


def _layout(W, H):
    """Compute grid + right-panel geometry scaled to the actual screen size."""
    _fs    = max(0.80, min(1.40, H / 900))
    HDR    = max(96, int(33 + 96 * _fs))   # fits pill + f_med title + f_xs subtitle at this _fs
    RPANEL = max(360, min(520, W // 4))     # right panel: 360–520 px
    GAP    = max(32, min(56, W // 36))      # grid↔panel gap
    avail_h = H - HDR - PROG_H - 8
    avail_w = W - 40 - RPANEL - GAP
    CELL   = max(100, min(170, min(avail_h // GRID_N, avail_w // GRID_N)))
    GRID_W = GRID_N * CELL
    TOTAL  = GRID_W + GAP + RPANEL
    GL     = max(20, (W - TOTAL) // 2)
    GT     = HDR + max(0, (H - HDR - PROG_H - GRID_W) // 2 - 4)
    GR     = GL + GRID_W + GAP
    GRW    = RPANEL
    return GL, GT, GR, GRW, CELL


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

    bname = block_type.replace("_", " ").title()
    bs = f_xs.render(bname, True, ACCENT)
    screen.blit(bs, (W // 2 - bs.get_width() // 2,
                     y + PROG_H // 2 - bs.get_height() // 2))

    # Size buttons from actual rendered text so they always contain it.
    btn_h = PROG_H - 8
    btn_y = y + PROG_H // 2 - btn_h // 2

    pl      = f_xs.render("II  Pause", True, DIM)
    p_bw    = pl.get_width() + 20
    pause_x = W - p_bw - 10
    pause_rect = pygame.Rect(pause_x, btn_y, p_bw, btn_h)
    pygame.draw.rect(screen, (38, 38, 62), pause_rect, border_radius=6)
    pygame.draw.rect(screen, BORDER,       pause_rect, width=1, border_radius=6)
    screen.blit(pl, (pause_rect.centerx - pl.get_width() // 2,
                     pause_rect.centery - pl.get_height() // 2))

    rl   = f_xs.render("RES", True, DIM)
    r_bw = rl.get_width() + 20
    res_x = pause_x - r_bw - 5
    res_r = pygame.Rect(res_x, btn_y, r_bw, btn_h)
    pygame.draw.rect(screen, (28, 28, 48), res_r, border_radius=6)
    pygame.draw.rect(screen, BORDER,       res_r, width=1, border_radius=6)
    screen.blit(rl, (res_r.centerx - rl.get_width() // 2,
                     res_r.centery - rl.get_height() // 2))

    ss = f_xs.render(f"Session {session_num}", True, DIM)
    screen.blit(ss, (res_x - ss.get_width() - 14,
                     y + PROG_H // 2 - ss.get_height() // 2))

    return pause_rect, res_r


def _draw_mouse_icon(surf, cx, cy, eyes_open=True):
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

    # Eyes — closed = thin horizontal line (eyelid), open = circle
    for ex in (cx - 10, cx + 10):
        if eyes_open:
            pygame.draw.circle(surf, dark, (ex, cy - 8), 4)
            pygame.draw.circle(surf, wht,  (ex - 1, cy - 10), 1)
        else:
            pygame.draw.line(surf, dark, (ex - 4, cy - 8), (ex + 4, cy - 8), 2)

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
    """Cheese fragment burst — yellow/amber wedge-shaped pieces scatter outward."""
    n = 18 if is_perfect else 12
    # Cheese colours: bright yellow, golden, amber, pale yellow
    cheese_cols = [
        (255, 216,  42),
        (255, 190,  30),
        (220, 162,  18),
        (255, 240, 120),
        (190, 130,  10),
    ]
    particles = []
    for i in range(n):
        # Spread evenly + slight jitter so pieces fan out cleanly
        base  = (2 * math.pi * i / n)
        angle = base + random.uniform(-0.25, 0.25)
        speed = random.uniform(120, 300)
        life  = random.uniform(0.35, 0.55)
        size  = random.randint(5, 11)
        color = random.choice(cheese_cols)
        particles.append({
            "x": float(cx), "y": float(cy),
            "vx": math.cos(angle) * speed,
            "vy": math.sin(angle) * speed,
            "life": life, "max_life": life,
            "r": color[0], "g": color[1], "b": color[2],
            "size": size,
        })
    # Add a few bright sparkle dots on perfect
    if is_perfect:
        for _ in range(8):
            angle = random.uniform(0, 2 * math.pi)
            particles.append({
                "x": float(cx), "y": float(cy),
                "vx": math.cos(angle) * random.uniform(200, 380),
                "vy": math.sin(angle) * random.uniform(200, 380),
                "life": 0.4, "max_life": 0.4,
                "r": 255, "g": 255, "b": 200,
                "size": 3,
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


def _draw_grid(screen, fonts, trial, trail, cursor, show_arrows=False, eyes_open=True):
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

            br = max(6, CELL // 14)
            pygame.draw.rect(screen, bg,          rect, border_radius=br)
            pygame.draw.rect(screen, GRID_BORDER, rect, width=1, border_radius=br)

            if (r, c) == goal:
                _draw_cheese_icon(screen, px + sz // 2, py + sz // 2)

    # Cursor — mouse icon travels through the grid
    if cursor:
        icx = GL + cursor[1] * CELL + CELL // 2
        icy = GT + cursor[0] * CELL + CELL // 2
        _draw_mouse_icon(screen, icx, icy, eyes_open=eyes_open)


def _stage_header(screen, fonts, tag, tag_col, title, subtitle):
    f_big, f_med, f_sm, f_xs = fonts
    W, H = screen.get_width(), screen.get_height()
    GL, GT, GR, GRW, CELL = _layout(W, H)
    _pill(screen, f_xs, tag, BG, tag_col, GL, 12)
    title_y  = 12 + f_xs.get_height() + 8
    _t(screen, f_med, title, WHITE, GL, title_y)
    sub_y    = title_y + f_med.get_height() + 5
    screen.set_clip(pygame.Rect(GL, sub_y, GR - GL - 8, f_xs.get_height() + 4))
    _t(screen, f_xs, subtitle, DIM, GL, sub_y)
    screen.set_clip(None)


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

    info_text = (f"{block_type.replace('_',' ').title()}  ·  Session {sn}")
    info_s  = f_xs.render(info_text, True, DIM)
    warn_s  = f_xs.render("Progress up to this trial is already saved.", True, DIM)
    hint_s  = f_xs.render("P or ESC to resume", True, DIM)

    f_big_h = f_big.get_height()
    f_sm_h  = f_sm.get_height()
    f_xs_h  = f_xs.get_height()
    btn_h   = max(46, f_sm_h + 16)

    # Card wide enough for the widest text line
    card_w = max(btn_h * 2 + btn_h, info_s.get_width() + 56,
                 warn_s.get_width() + 56)
    card_h = 18 + f_big_h + 10 + f_xs_h + 14 + btn_h + 12 + f_xs_h + 8 + f_xs_h + 14
    card_x = cx - card_w // 2
    card_y = cy - card_h // 2

    pygame.draw.rect(screen, (22, 22, 40), (card_x, card_y, card_w, card_h), border_radius=16)
    pygame.draw.rect(screen, BORDER,       (card_x, card_y, card_w, card_h), width=1, border_radius=16)

    y = card_y + 18

    ts = f_big.render("Paused", True, WHITE)
    screen.blit(ts, (cx - ts.get_width() // 2, y))
    y += f_big_h + 10

    screen.blit(info_s, (cx - info_s.get_width() // 2, y))
    y += f_xs_h + 10

    pygame.draw.line(screen, BORDER, (card_x + 24, y), (card_x + card_w - 24, y))
    y += 14

    btn_w    = 148
    btn_gap  = 16
    resume_r = pygame.Rect(cx - btn_w - btn_gap // 2, y, btn_w, btn_h)
    exit_r   = pygame.Rect(cx + btn_gap // 2,         y, btn_w, btn_h)

    mouse = pygame.mouse.get_pos()
    rc = tuple(min(255, c + 20) for c in CORRECT) if resume_r.collidepoint(mouse) else CORRECT
    pygame.draw.rect(screen, (8, 8, 16),
                     (resume_r.x + 2, resume_r.y + 3, resume_r.w, resume_r.h), border_radius=10)
    pygame.draw.rect(screen, rc, resume_r, border_radius=10)
    rl = f_sm.render("Resume", True, (10, 10, 20))
    screen.blit(rl, (resume_r.centerx - rl.get_width() // 2,
                     resume_r.centery - rl.get_height() // 2))

    DANGER = (180, 50, 50)
    ec = tuple(min(255, c + 20) for c in DANGER) if exit_r.collidepoint(mouse) else DANGER
    pygame.draw.rect(screen, (8, 8, 16),
                     (exit_r.x + 2, exit_r.y + 3, exit_r.w, exit_r.h), border_radius=10)
    pygame.draw.rect(screen, ec, exit_r, border_radius=10)
    el = f_sm.render("Save & Exit", True, WHITE)
    screen.blit(el, (exit_r.centerx - el.get_width() // 2,
                     exit_r.centery - el.get_height() // 2))

    y += btn_h + 12
    screen.blit(hint_s, (cx - hint_s.get_width() // 2, y))
    y += f_xs_h + 8
    screen.blit(warn_s, (cx - warn_s.get_width() // 2, y))

    return resume_r, exit_r


# ── Fam Block 1: free-exploration trial ──────────────────────

def run_explore_trial(screen, clock, fonts, trial: TrialData, config: dict,
                      cumulative_score: int, session_id: int,
                      total_trials: int = 20, block_type: str = "familiarization",
                      session_state: dict = None) -> dict:
    """
    Familiarization block 1 only.
    Grid stays visible. 1/2/3 moves the cursor live. Reaching the goal ends the trial.
    No planning stage, no sequence input, no feedback.
    """
    f_big, f_med, f_sm, f_xs = fonts
    W, H  = screen.get_width(), screen.get_height()
    sn    = config.get("session_number", 1)

    cursor = trial.start
    trail  = {}
    state  = "explore"
    pre_pause_state = "explore"
    iti_start  = None
    iti_dur    = random.uniform(3.0, 5.0)
    trial_id   = None
    pause_rect = None
    researcher_rect = None
    last_frame_t = time.time()

    first_key_t = None
    last_key_t  = None
    move_count  = 0
    keys_used   = set()   # which of 1/2/3 have been pressed at least once

    trial.trial_start_time = time.time()

    _kmap = {
        pygame.K_1: 1, pygame.K_KP1: 1,
        pygame.K_2: 2, pygame.K_KP2: 2,
        pygame.K_3: 3, pygame.K_KP3: 3,
    }

    while True:
        clock.tick(60)
        now_s        = time.time()
        dt           = now_s - last_frame_t
        last_frame_t = now_s

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); import sys; sys.exit()

            if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_p, pygame.K_ESCAPE):
                if state == PAUSED:
                    state = pre_pause_state
                elif state not in ("done",):
                    pre_pause_state = state; state = PAUSED

            if state == PAUSED and ev.type == pygame.MOUSEBUTTONDOWN:
                resume_r, exit_r = _draw_pause_overlay(
                    screen, fonts, trial, total_trials, block_type, sn)
                if resume_r.collidepoint(ev.pos):
                    state = pre_pause_state
                elif exit_r.collidepoint(ev.pos):
                    return {"paused_exit": True, "reward_score": 0,
                            "is_correct": False,
                            "cumulative_score": cumulative_score,
                            "trial_id": None, "streak": 0}

            if state == PAUSED:
                continue

            if ev.type == pygame.MOUSEBUTTONDOWN:
                if pause_rect and pause_rect.collidepoint(ev.pos):
                    pre_pause_state = state; state = PAUSED
                elif (researcher_rect and researcher_rect.collidepoint(ev.pos)
                      and session_state is not None):
                    from screens.researcher_panel import run_researcher_access
                    action, target = run_researcher_access(
                        screen, clock, fonts, session_state)
                    if action == "jump":
                        return {"researcher_jump": target, "reward_score": 0,
                                "is_correct": False,
                                "cumulative_score": cumulative_score,
                                "trial_id": None, "streak": 0}
                    elif action == "exit":
                        return {"paused_exit": True, "reward_score": 0,
                                "is_correct": False,
                                "cumulative_score": cumulative_score,
                                "trial_id": None, "streak": 0}

            if state == "explore" and ev.type == pygame.KEYDOWN:
                dk = _kmap.get(ev.key)
                if dk is not None:
                    now_t = time.time()
                    if first_key_t is None:
                        first_key_t = now_t
                        trial.reaction_time_ms = (now_t - trial.trial_start_time) * 1000
                    iki = (now_t - last_key_t) * 1000 if last_key_t else None
                    last_key_t = now_t
                    move_count += 1
                    before = cursor
                    nxt = apply_key(cursor[0], cursor[1], dk)
                    if nxt:
                        trail[cursor] = now_t
                        cursor = nxt
                        keys_used.add(dk)   # only counts if the cursor actually moved
                    trial.keypresses_log.append({
                        "key":    dk,
                        "before": before,
                        "after":  cursor,
                        "abs_ms": now_t * 1000,
                        "rel_ms": (now_t - trial.trial_start_time) * 1000,
                        "iki_ms": iki,
                    })
                    # Only complete the trial when cursor is on cheese AND all 3 keys used
                    if cursor == trial.goal and {1, 2, 3}.issubset(keys_used):
                        trial.movement_time_ms = (last_key_t - first_key_t) * 1000
                        trial.planned_sequence = []
                        trial.is_correct       = True
                        trial.reward_score     = 0
                        trial.number_of_moves  = move_count
                        trial_id = _save(trial, session_id)
                        update_session_progress(session_id, trial.trial_number)
                        state     = ITI
                        iti_start = now_t

        if state == ITI and iti_start and (now_s - iti_start) >= iti_dur:
            state = DONE

        if state == DONE:
            break

        # ── Draw ─────────────────────────────────────────────
        screen.fill(BG)
        draw_state = pre_pause_state if state == PAUSED else state

        if draw_state == "explore":
            if cursor == trial.goal and not {1, 2, 3}.issubset(keys_used):
                subtitle = "You found the cheese!  All 3 keys must be used to complete the trial"
            else:
                subtitle = "Press  1 / 2 / 3  on the keypad to move the mouse — use all 3 keys"
            _stage_header(screen, fonts,
                          "EXPLORE", ACCENT,
                          "Find the cheese!",
                          subtitle)
            _draw_grid(screen, fonts, trial, trail, cursor)
        elif draw_state == ITI:
            pause_rect, researcher_rect = _draw_stage_iti(
                screen, fonts, trial, iti_start, iti_dur,
                total_trials, block_type, sn, cum_score=cumulative_score)

        if state == PAUSED:
            _draw_pause_overlay(screen, fonts, trial, total_trials, block_type, sn)

        if draw_state != ITI:
            pause_rect, researcher_rect = _draw_progress(
                screen, fonts, trial, total_trials, block_type, sn,
                cum_score=cumulative_score)

        pygame.display.flip()

    return {
        "reward_score":     0,
        "is_correct":       True,
        "cumulative_score": cumulative_score,
        "trial_id":         trial_id,
        "streak":           0,
    }


# ── Main trial runner ─────────────────────────────────────────

def run_trial(screen, clock, fonts, trial: TrialData, config: dict,
              cumulative_score: int, session_id: int,
              total_trials: int = 20, block_type: str = "practice",
              streak: int = 0, show_timer: bool = True,
              show_score: bool = True,
              session_state: dict = None) -> dict:

    f_big, f_med, f_sm, f_xs = fonts
    W, H = screen.get_width(), screen.get_height()

    state           = PLANNING
    pre_pause_state = PLANNING
    planning_start  = time.time()
    first_key_time  = None
    last_key_time   = None
    typed_seq       = []
    action_path     = []
    feedback_start  = None
    iti_start       = None
    action_start    = None
    trial_id        = None
    blink_on        = True
    blink_t         = pygame.time.get_ticks()
    pause_rect      = None
    researcher_rect = None
    btns            = {}   # on-screen button rects; populated each draw frame

    particles         = []
    particles_spawned = False
    burst_start       = None   # time.time() when cheese burst was spawned

    # Ambient particles that drift toward the cheese during planning
    amb_particles = [
        {"x": 0.0, "y": 0.0, "vx": random.uniform(-0.8, 0.8),
         "vy": random.uniform(-0.8, 0.8)}
        for _ in range(22)
    ]
    # Positions initialised lazily on first draw (need screen layout)
    last_frame_t      = time.time()
    mi_space_held     = False
    mi_space_start    = None
    phys_first_key_t  = None   # first 1/2/3 press time during PP action stage
    phys_last_key_t   = None   # most recent 1/2/3 press time during PP action stage
    pp_typed_seq      = []     # sequence the participant physically types in ACTION

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
        state          = FEEDBACK
        feedback_start = time.time()
        rp_step = 0; rp_timer = pygame.time.get_ticks()
        rp_cursor = trial.start; rp_trail = {}; rp_done = False; rp_done_time = None

    def enter_action():
        nonlocal state, action_start, phys_first_key_t, phys_last_key_t, pp_typed_seq
        state             = ACTION
        action_start      = time.time()
        phys_first_key_t  = None
        phys_last_key_t   = None
        pp_typed_seq      = []

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

            # MI ACTION: hold SPACE to time imagery; release to submit
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

            # PP ACTION: participant physically re-types their sequence; SPACE ends trial
            if state == ACTION and is_pp and ev.type == pygame.KEYDOWN:
                _pkmap = {
                    pygame.K_1: 1, pygame.K_KP1: 1,
                    pygame.K_2: 2, pygame.K_KP2: 2,
                    pygame.K_3: 3, pygame.K_KP3: 3,
                }
                if ev.key in _pkmap:
                    _now_t = time.time()
                    if phys_first_key_t is None:
                        phys_first_key_t = _now_t
                    phys_last_key_t = _now_t
                    pp_typed_seq.append(_pkmap[ev.key])
                elif ev.key == pygame.K_SPACE and len(pp_typed_seq) >= 2:
                    if phys_first_key_t is not None and phys_last_key_t is not None:
                        trial.movement_time_ms = (
                            (phys_last_key_t - phys_first_key_t) * 1000)
                    _finalise(trial, pp_typed_seq, session_id)
                    trial_id = _save(trial, session_id)
                    update_session_progress(session_id, trial.trial_number)
                    # Replay animates actual physical sequence, not planned
                    action_path = _build_path(trial.start, pp_typed_seq)
                    enter_feedback() if show_feedback else enter_iti()

            if ev.type == pygame.MOUSEBUTTONDOWN and state != PAUSED:
                if pause_rect and pause_rect.collidepoint(ev.pos):
                    pre_pause_state = state; state = PAUSED

                elif (researcher_rect and researcher_rect.collidepoint(ev.pos)
                      and session_state is not None):
                    from screens.researcher_panel import run_researcher_access
                    mi_space_held = False   # clear any in-progress imagery hold
                    action, target = run_researcher_access(screen, clock, fonts, session_state)
                    if action == "jump":
                        return {"researcher_jump": target, "reward_score": 0,
                                "is_correct": False, "cumulative_score": cumulative_score,
                                "trial_id": None}
                    elif action == "exit":
                        return {"paused_exit": True, "reward_score": 0,
                                "is_correct": False, "cumulative_score": cumulative_score,
                                "trial_id": None}
                    # action == "resume": fall through, trial continues

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
                        if btns.get("backspace") and btns["backspace"].collidepoint(p) and typed_seq:
                            typed_seq.pop()
                        elif btns.get("confirm") and btns["confirm"].collidepoint(p) and typed_seq:
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
                                enter_action()

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

            # Direction keys during PLANNING — recorded but cursor stays at start
            if state == PLANNING and show_timer and ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_SPACE and typed_seq:
                    # Skip remaining timer and advance to INPUT immediately
                    state = INPUT
                elif ev.key == pygame.K_BACKSPACE and typed_seq:
                    typed_seq.pop()
                _pkmap_p = {
                    pygame.K_1: 1, pygame.K_KP1: 1,
                    pygame.K_2: 2, pygame.K_KP2: 2,
                    pygame.K_3: 3, pygame.K_KP3: 3,
                }
                _dk_p = _pkmap_p.get(ev.key)
                if _dk_p is not None:
                    _now_p = time.time()
                    if first_key_time is None:
                        first_key_time = _now_p
                    trial.keypresses_log.append({
                        "key":    _dk_p,
                        "before": list(trial.start),
                        "after":  list(trial.start),   # cursor does not move
                        "abs_ms": _now_p * 1000,
                        "rel_ms": (_now_p - planning_start) * 1000,
                        "iki_ms": ((_now_p - last_key_time) * 1000
                                   if last_key_time else None),
                        "phase":  "planning",
                    })
                    last_key_time = _now_p
                    typed_seq.append(_dk_p)

            # Direction keys via keyboard (1/2/3 and numpad) for INPUT phase
            if state == INPUT and ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_BACKSPACE and typed_seq:
                    typed_seq.pop()
                _kmap = {
                    pygame.K_1: 1, pygame.K_KP1: 1,
                    pygame.K_2: 2, pygame.K_KP2: 2,
                    pygame.K_3: 3, pygame.K_KP3: 3,
                }
                _dk = _kmap.get(ev.key)
                if _dk is not None:
                    _now_t = time.time()
                    if first_key_time is None: first_key_time = _now_t
                    _before = _build_path(trial.start, typed_seq)[-1]
                    _nxt    = apply_key(_before[0], _before[1], _dk)
                    _after  = _nxt if _nxt else _before
                    _iki    = ((_now_t - last_key_time) * 1000
                               if last_key_time else None)
                    trial.keypresses_log.append({
                        "key": _dk, "before": _before, "after": _after,
                        "abs_ms": _now_t * 1000,
                        "rel_ms": (_now_t - planning_start) * 1000,
                        "iki_ms": _iki,
                    })
                    last_key_time = _now_t
                    typed_seq.append(_dk)

            # ACTION: MI — no interaction; auto-advances via timer below

            # FEEDBACK: SPACE to continue once replay has finished
            if (state == FEEDBACK and rp_done
                    and ev.type == pygame.KEYDOWN and ev.key == pygame.K_SPACE):
                state = ITI; iti_start = now_s

        # Auto-transitions
        if state == PLANNING and show_timer and elapsed >= p_time:
            state = INPUT   # typed_seq and first_key_time carry over from planning

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

        # Blink: eyes open ~3.5 s, closed ~120 ms
        blink_elapsed = now_ms - blink_t
        if blink_on and blink_elapsed > 3500:
            blink_on = False; blink_t = now_ms
        elif not blink_on and blink_elapsed > 120:
            blink_on = True;  blink_t = now_ms

        # ── Draw ─────────────────────────────────────────────
        btns.clear()
        screen.fill(BG)
        draw_state = pre_pause_state if state == PAUSED else state

        if draw_state == PLANNING:
            # Lazy-init ambient particle positions inside the grid
            if amb_particles and amb_particles[0]["x"] == 0.0:
                _GL, _GT, _GR, _GRW, _CELL = _layout(W, H)
                for ap in amb_particles:
                    ap["x"] = float(_GL + random.randint(0, _CELL * 5))
                    ap["y"] = float(_GT + random.randint(0, _CELL * 5))
            pause_rect, researcher_rect = _draw_stage_planning(
                screen, fonts, trial, elapsed, p_time,
                total_trials, block_type, sn,
                cum_score=cumulative_score, show_timer=show_timer,
                eyes_open=blink_on, amb_particles=amb_particles,
                typed_seq=typed_seq)
        elif draw_state == INPUT:
            pause_rect, researcher_rect = _draw_stage_input(
                screen, fonts, trial, typed_seq, blink_on,
                total_trials, block_type, sn, btns,
                cum_score=cumulative_score, is_mi=is_mi)
        elif draw_state == ACTION:
            pause_rect, researcher_rect = _draw_stage_action(
                screen, fonts, trial,
                is_mi, is_pp,
                total_trials, block_type, sn,
                action_start, btns,
                mi_space_held=mi_space_held,
                mi_space_start=mi_space_start,
                cum_score=cumulative_score,
                show_score=show_score,
                pp_typed_seq=pp_typed_seq)
        elif draw_state == FEEDBACK:
            if not particles_spawned:
                _GL, _GT, _GR, _GRW, _CELL = _layout(W, H)
                goal_r, goal_c = trial.goal
                _pcx = _GL + goal_c * _CELL + _CELL // 2
                _pcy = _GT + goal_r * _CELL + _CELL // 2
                if trial.is_correct:
                    particles  = _spawn_particles(
                        _pcx, _pcy, trial.reward_score == OPTIMAL_SCORE)
                    burst_start = time.time()
                particles_spawned = True

            # On correct trials: show burst for 0.4 s before the feedback card.
            burst_done = (burst_start is None or
                          (time.time() - burst_start) >= 0.4)
            if burst_done:
                pause_rect, researcher_rect = _draw_stage_feedback(
                    screen, fonts, trial, cumulative_score,
                    rp_cursor, rp_trail, rp_done,
                    total_trials, block_type, sn,
                    streak=streak, show_score=show_score)
            if particles:
                _update_draw_particles(screen, particles, dt)
        elif draw_state == ITI:
            pause_rect, researcher_rect = _draw_stage_iti(
                screen, fonts, trial, iti_start, iti_dur,
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
    from core.sounds import play as play_sound
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
    play_sound("correct" if ok else "incorrect")
    if trial.movement_time_ms is None and len(trial.keypresses_log) >= 2:
        trial.movement_time_ms = (trial.keypresses_log[-1]["abs_ms"]
                                  - trial.keypresses_log[0]["abs_ms"])

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
    diff    = n_moves - opt_len   # positive = too many, negative = too few
    extra   = abs(diff)
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
        if diff > 0:
            rows.append(("Extra moves",
                         f"{n_moves} − {opt_len} = +{diff}",
                         DIM, WRONG))
        elif diff < 0:
            rows.append(("Fewer than optimal",
                         f"{n_moves} − {opt_len} = {diff}",
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
        oob_col  = (255, 160, 80)
        max_w    = RCOL - LCOL
        line1    = f"⚠  {trial.oob_count} move{'s' if trial.oob_count > 1 else ''} hit the boundary"
        line2    = "cursor stayed in place"
        full     = f"{line1} — {line2}"
        full_s   = f_xs.render(full, True, oob_col)
        if full_s.get_width() <= max_w:
            screen.blit(full_s, (LCOL, cy))
            cy += full_s.get_height() + 2
        else:
            s1 = f_xs.render(line1, True, oob_col)
            s2 = f_xs.render(line2, True, oob_col)
            screen.blit(s1, (LCOL, cy))
            cy += s1.get_height() + 2
            screen.blit(s2, (LCOL, cy))
            cy += s2.get_height() + 2

    return ry + card_h + 8


# ── Stage drawing ─────────────────────────────────────────────

def _draw_stage_planning(screen, fonts, trial, elapsed, p_time,
                         total_trials, block_type, sn, cum_score: int = 0,
                         show_timer: bool = True, eyes_open: bool = True,
                         amb_particles: list = None, typed_seq: list = None):
    f_big, f_med, f_sm, f_xs = fonts
    W, H = screen.get_width(), screen.get_height()
    GL, GT, GR, GRW, CELL = _layout(W, H)

    if show_timer:
        rem      = max(0, p_time - elapsed)
        tc       = WRONG if rem < 2 else (AMBER if rem < 4 else WHITE)
        subtitle = "Plan the shortest route — grid hides when the timer ends"
    else:
        subtitle = "Take your time — press  SPACE  when you're ready"

    _stage_header(screen, fonts,
                  "PLANNING", ACCENT,
                  "Study the grid",
                  subtitle)

    # Ambient magnetic particles drawn under the grid
    if amb_particles is not None:
        goal_c = trial.goal[1]; goal_r = trial.goal[0]
        gcx = GL + goal_c * CELL + CELL // 2
        gcy = GT + goal_r * CELL + CELL // 2
        for p in amb_particles:
            # Magnetic pull toward cheese cell
            dx, dy   = gcx - p["x"], gcy - p["y"]
            dist     = max(1, math.hypot(dx, dy))
            strength = 28.0 / dist
            p["vx"]  = p["vx"] * 0.97 + (dx / dist) * strength
            p["vy"]  = p["vy"] * 0.97 + (dy / dist) * strength
            p["x"]  += p["vx"]
            p["y"]  += p["vy"]
            # Reset particle that drifts too close to cheese or off grid
            if dist < 18 or not (GL < p["x"] < GR and GT < p["y"] < GT + CELL * 5):
                p["x"] = float(GL + random.randint(0, CELL * 5))
                p["y"] = float(GT + random.randint(0, CELL * 5))
                p["vx"] = random.uniform(-0.8, 0.8)
                p["vy"] = random.uniform(-0.8, 0.8)
            alpha = max(30, min(140, int(140 * (dist / (CELL * 3)))))
            col   = (220, 162, 28, alpha)
            s = pygame.Surface((4, 4), pygame.SRCALPHA)
            pygame.draw.circle(s, col, (2, 2), 2)
            screen.blit(s, (int(p["x"]) - 2, int(p["y"]) - 2))

    _draw_grid(screen, fonts, trial, {}, trial.start, eyes_open=eyes_open)

    rx, ry = GR, GT

    f_big_h = f_big.get_height()
    f_sm_h  = f_sm.get_height()
    f_xs_h  = f_xs.get_height()

    if show_timer:
        card_h = 12 + f_big_h + 8 + f_xs_h + 12
        _panel(screen, rx, ry, GRW, card_h, BORDER)
        ts = f_big.render(f"{rem:.1f}s", True, tc)
        screen.blit(ts, (rx + GRW // 2 - ts.get_width() // 2, ry + 12))
        tl = f_xs.render("Time remaining", True, DIM)
        screen.blit(tl, (rx + GRW // 2 - tl.get_width() // 2, ry + 12 + f_big_h + 8))
    else:
        card_h = 12 + f_sm_h + 8 + f_xs_h + 12
        _panel(screen, rx, ry, GRW, card_h, BORDER)
        rs = f_sm.render("No time limit", True, ACCENT)
        screen.blit(rs, (rx + GRW // 2 - rs.get_width() // 2, ry + 12))
        hs = f_xs.render("Press  SPACE  when ready", True, DIM)
        screen.blit(hs, (rx + GRW // 2 - hs.get_width() // 2, ry + 12 + f_sm_h + 8))
    ry += card_h + 16

    # ── Live sequence entered so far (during planning) ────────
    if typed_seq is not None:
        seq_str  = ", ".join(str(k) for k in typed_seq) if typed_seq else "—"
        seq_col  = WHITE if typed_seq else DIM
        lbl_h    = f_xs.get_height()
        val_h    = f_sm.get_height()
        s_card_h = 10 + lbl_h + 6 + val_h + 10
        _panel(screen, rx, ry, GRW, s_card_h, ACCENT)
        lbl_s = f_xs.render("Keys entered so far", True, DIM)
        screen.blit(lbl_s, (rx + 14, ry + 10))
        seq_s = f_sm.render(seq_str, True, seq_col)
        screen.blit(seq_s, (rx + 14, ry + 10 + lbl_h + 6))
        ry += s_card_h + 8

    return _draw_progress(screen, fonts, trial, total_trials, block_type, sn,
                          cum_score=cum_score)


def _draw_stage_input(screen, fonts, trial, typed_seq, blink_on,
                      total_trials, block_type, sn, btns, cum_score: int = 0,
                      is_mi=False):
    f_big, f_med, f_sm, f_xs = fonts
    W, H = screen.get_width(), screen.get_height()
    GL, GT, GR, GRW, CELL = _layout(W, H)

    if is_mi:
        sub = "Enter your sequence — you will imagine the movement in the next step"
    else:
        sub = "Click the direction buttons to build your sequence"
    _stage_header(screen, fonts,
                  "INPUT", WHITE,
                  "Enter your planned sequence — grid is hidden",
                  sub)

    # Grid hidden — ghost cell outlines + centre message
    ghost_br = max(6, CELL // 14)
    for r in range(GRID_N):
        for c in range(GRID_N):
            gr = pygame.Rect(GL + c * CELL + 4, GT + r * CELL + 4, CELL - 8, CELL - 8)
            pygame.draw.rect(screen, (16, 16, 32), gr, border_radius=ghost_br)
            pygame.draw.rect(screen, (32, 32, 54), gr, width=1, border_radius=ghost_br)

    grid_cx = GL + (GRID_N * CELL) // 2
    grid_cy = GT + (GRID_N * CELL) // 2
    mem_s = f_med.render("Recall from memory", True, (46, 46, 76))
    screen.blit(mem_s, (grid_cx - mem_s.get_width() // 2, grid_cy - 20))
    sub_s = f_xs.render("Grid is hidden — plan from memory", True, (34, 34, 58))
    screen.blit(sub_s, (grid_cx - sub_s.get_width() // 2, grid_cy + 14))

    rx, ry = GR, GT

    # ── Sequence display ──────────────────────────────────────
    seq_y  = 10 + f_xs.get_height() + 8
    cnt_y  = seq_y + f_sm.get_height() + 8
    card_h = cnt_y + f_xs.get_height() + 10
    _panel(screen, rx, ry, GRW, card_h, ACCENT)
    _t(screen, f_xs, "Your sequence", DIM, rx + 14, ry + 10)

    seq_str = ", ".join(str(k) for k in typed_seq) if typed_seq else "—"
    seq_col = WHITE if typed_seq else DIM
    ss = f_sm.render(seq_str, True, seq_col)
    screen.blit(ss, (rx + 14, ry + seq_y))

    if blink_on and typed_seq:
        bx = rx + 14 + ss.get_width() + 5
        pygame.draw.rect(screen, ACCENT, (bx, ry + seq_y, 2, ss.get_height()))

    cnt = f_xs.render(f"{len(typed_seq)} key(s) entered", True, DIM)
    screen.blit(cnt, (rx + 14, ry + cnt_y))
    ry += card_h + 10

    # ── Direction buttons (1 / 2 / 3) + backspace ────────────
    btn_w = (GRW - 36) // 4   # 4 slots: 1, 2, 3, ⌫
    btn_h = 68
    for i, k in enumerate((1, 2, 3)):
        _draw_key_button(screen, fonts,
                         pygame.Rect(rx + i * (btn_w + 12), ry, btn_w, btn_h),
                         k, btns, f"key{k}")
    # Backspace button
    bk_rect = pygame.Rect(rx + 3 * (btn_w + 12), ry, btn_w, btn_h)
    _draw_cmd_button(screen, fonts, bk_rect, "⌫", AMBER, bool(typed_seq), btns, "backspace")
    ry += btn_h + 10

    # ── Confirm button (all groups) ───────────────────────────
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

    seq_str = "   →   ".join(str(k) for k in trial.planned_sequence)
    seq_s   = f_sm.render(f"Sequence:  {seq_str}", True, ACCENT)
    screen.blit(seq_s, (cx - seq_s.get_width() // 2, cy + 80))

    return _draw_progress(screen, fonts, trial, total_trials, block_type, sn,
                          cum_score=cum_score)


def _draw_stage_action(screen, fonts, trial,
                       is_mi, is_pp,
                       total_trials, block_type, sn,
                       action_start=None, btns=None,
                       mi_space_held=False, mi_space_start=None,
                       cum_score: int = 0, show_score: bool = True,
                       pp_typed_seq: list = None):
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

    else:  # PP — physical key press stage
        _stage_header(screen, fonts,
                      "ACTION", CORRECT,
                      "Execute your sequence", "")

        pw     = min(700, W - 80)
        px     = W // 2 - pw // 2
        lbl_h  = f_sm.get_height()
        val_h  = f_big.get_height()
        inst_h = f_med.get_height()
        card_h = 16 + lbl_h + 10 + val_h + 16
        total_h = inst_h + 20 + card_h + 24 + f_med.get_height()
        py     = GT + max(0, (H - GT - PROG_H - total_h) // 2)

        # ── Big centred instruction above the panel ───────────────
        inst = f_med.render("Press your keys on the keypad, then press  SPACE  when done", True, WHITE)
        screen.blit(inst, (W // 2 - inst.get_width() // 2, py))
        py += inst_h + 20

        # ── Planned sequence panel ────────────────────────────────
        plan_str = ", ".join(str(k) for k in trial.planned_sequence)
        _panel(screen, px, py, pw, card_h, ACCENT)
        lbl = f_sm.render("Your planned sequence", True, DIM)
        screen.blit(lbl, (px + 20, py + 16))
        ps  = f_big.render(plan_str, True, WHITE)
        screen.blit(ps,  (px + 20, py + 16 + lbl_h + 10))
        py += card_h + 24

        # ── Static dim SPACE reminder below panel ─────────────────
        sp_surf = f_med.render("Press  SPACE  when done", True, DIM)
        screen.blit(sp_surf, (W // 2 - sp_surf.get_width() // 2, py))

    return _draw_progress(screen, fonts, trial, total_trials, block_type, sn,
                          cum_score=cum_score)


def _draw_stage_feedback(screen, fonts, trial, cum_score,
                         rp_cursor, rp_trail, rp_done,
                         total_trials, block_type, sn,
                         streak: int = 0, show_score: bool = True):
    f_big, f_med, f_sm, f_xs = fonts
    W, H = screen.get_width(), screen.get_height()
    GL, GT, GR, GRW, CELL = _layout(W, H)

    if trial.is_correct:
        result_label, rc = "CORRECT", CORRECT
    else:
        result_label, rc = "MISSED", WRONG

    new_total = cum_score + trial.reward_score

    # ── Animated replay of actual sequence ───────────────────
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

    if show_score:
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

        # Score breakdown card
        ry = _draw_score_card(screen, fonts, trial, rx, ry, GRW)

        # Session total
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
    gr_y = cy + r_outer + 16
    screen.blit(gr, (cx - gr.get_width() // 2, gr_y))

    next_lbl = f_xs.render("Next trial starting…", True, DIM)
    screen.blit(next_lbl, (cx - next_lbl.get_width() // 2,
                            gr_y + gr.get_height() + 8))

    return _draw_progress(screen, fonts, trial, total_trials, block_type, sn,
                          cum_score=cum_score)
