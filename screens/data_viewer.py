# ============================================================
#  GRID-SAILING TASK — Data Viewer  (v2)
# ============================================================

import pygame
import sys
from database.db import get_participant_stats, get_session_breakdown
from config import WINDOW_WIDTH, WINDOW_HEIGHT, FPS

BG      = (12,  12,  22)
PANEL   = (20,  20,  36)
PANEL2  = (28,  28,  46)
BORDER  = (52,  52,  80)
WHITE   = (230, 230, 242)
DIM     = (100, 100, 138)
ACCENT  = ( 88, 148, 255)
GREEN   = ( 58, 196, 108)
AMBER   = (210, 158,  28)
ORANGE  = (228, 138,  48)
RED_C   = (212,  58,  58)
PURPLE  = (160,  90, 220)

GROUP_COLORS = {
    "MI-High":   ( 88, 148, 255),
    "MI-Low":    ( 60, 110, 210),
    "PP-High":   ( 58, 196, 108),
    "PP-Low":    ( 38, 148,  80),
    "CTRL-High": (210, 158,  28),
    "CTRL-Low":  (168, 118,  18),
}

PAD      = 36
SIDE_W   = 280
TABLE_X  = PAD
TABLE_W  = WINDOW_WIDTH - PAD * 2 - SIDE_W - 20
SIDE_X   = TABLE_X + TABLE_W + 16
ROW_H    = 48
CARD_H   = 80
CARDS_Y  = 70
TABLE_Y  = CARDS_Y + CARD_H + 18   # top of header row


# ── Helpers ───────────────────────────────────────────────────

def _t(screen, font, text, col, x, y, center_in_w=0):
    s = font.render(text, True, col)
    if center_in_w:
        screen.blit(s, (x + center_in_w // 2 - s.get_width() // 2, y))
    else:
        screen.blit(s, (x, y))
    return s

def _panel(screen, x, y, w, h, col=BORDER, radius=10):
    pygame.draw.rect(screen, PANEL,  (x, y, w, h), border_radius=radius)
    pygame.draw.rect(screen, col,    (x, y, w, h), width=1, border_radius=radius)

def _bar(screen, x, y, w, h, pct, fg):
    pygame.draw.rect(screen, (28, 28, 50), (x, y, w, h), border_radius=4)
    if pct > 0:
        pygame.draw.rect(screen, fg,
                         (x, y, max(4, int(w * min(pct, 1.0))), h), border_radius=4)

def _pill(screen, font, text, fg, bg, x, y):
    s  = font.render(text, True, fg)
    pw = s.get_width() + 14
    ph = s.get_height() + 6
    pygame.draw.rect(screen, bg, (x, y, pw, ph), border_radius=ph // 2)
    screen.blit(s, (x + 7, y + 3))
    return pw


# ── Summary cards ─────────────────────────────────────────────

def _summary_card(screen, fonts, x, y, w, label, value, sub, accent):
    _, f_med, f_sm, f_xs = fonts
    _panel(screen, x, y, w, CARD_H, accent, radius=12)
    # Top accent stripe
    pygame.draw.rect(screen, accent,
                     (x + 1, y + 1, w - 2, 5), border_radius=12)
    _t(screen, f_xs,  label, DIM,    x + 16, y + 14)
    _t(screen, f_med, value, accent, x + 16, y + 34)
    _t(screen, f_xs,  sub,   DIM,    x + 16, y + CARD_H - 20)


# ── Column layout ─────────────────────────────────────────────

def _cols():
    """(x_offset, width) for each column: ID, Group, Age, Sessions, Trials, Score, Accuracy"""
    # Accuracy column: remaining space minus space for the % label (38px)
    acc_x = 474
    acc_w = TABLE_W - acc_x - 44   # 44px reserved for "100%" label
    return [
        (0,     86),   # ID
        (86,   114),   # Group (pill)
        (200,   46),   # Age
        (246,   74),   # Sessions
        (320,   64),   # Trials
        (384,   90),   # Avg Score
        (acc_x, acc_w),# Accuracy bar
    ]


# ── Table header ──────────────────────────────────────────────

def _draw_header(screen, fonts, y):
    _, _, f_sm, f_xs = fonts
    labels = ["ID", "Group", "Age", "Sessions", "Trials", "Avg Score", "Accuracy"]
    pygame.draw.rect(screen, PANEL2, (TABLE_X, y, TABLE_W, 28), border_radius=6)
    for (cx, cw), lbl in zip(_cols(), labels):
        _t(screen, f_xs, lbl, DIM, TABLE_X + cx + 8, y + 6)
    pygame.draw.line(screen, BORDER,
                     (TABLE_X, y + 28), (TABLE_X + TABLE_W, y + 28))


# ── Participant row ───────────────────────────────────────────

def _draw_row(screen, fonts, stat, y, selected):
    _, _, f_sm, f_xs = fonts
    cols = _cols()

    bg = (32, 32, 58) if selected else PANEL
    bc = ACCENT        if selected else BORDER
    pygame.draw.rect(screen, bg, (TABLE_X, y, TABLE_W, ROW_H - 2), border_radius=8)
    if selected:
        pygame.draw.rect(screen, bc, (TABLE_X, y, TABLE_W, ROW_H - 2),
                         width=1, border_radius=8)

    cy = y + ROW_H // 2 - 8   # text baseline

    # Text columns (skip Group and Accuracy — drawn specially)
    text_vals = [
        stat["participant_id"],
        "",                               # Group — pill drawn below
        str(stat["age"] or "—"),
        str(int(stat["sessions_done"])),
        str(int(stat["total_trials"])),
        f"{stat['avg_score']:.0f}",
    ]
    for i, ((cx, cw), val) in enumerate(zip(cols[:6], text_vals)):
        if i == 0:
            color = ACCENT if selected else WHITE
            _t(screen, f_sm, val, color, TABLE_X + cx + 8, cy)
        elif i == 1:
            pass   # pill below
        else:
            _t(screen, f_xs, val, DIM, TABLE_X + cx + 8, cy)

    # Group pill
    gx, gw = cols[1]
    gcol = GROUP_COLORS.get(stat["group_name"], DIM)
    _pill(screen, f_xs, stat["group_name"], (10, 10, 20), gcol,
          TABLE_X + gx + 6, y + ROW_H // 2 - 11)

    # Accuracy bar + %
    ax, aw = cols[6]
    bar_x  = TABLE_X + ax + 8
    bar_w  = aw
    pct    = stat["accuracy_pct"] / 100.0
    bar_y  = y + ROW_H // 2 - 5
    _bar(screen, bar_x, bar_y, bar_w, 10, pct,
         fg=GREEN if pct >= 0.7 else (ORANGE if pct >= 0.4 else RED_C))
    pct_x = bar_x + bar_w + 6
    _t(screen, f_xs, f"{stat['accuracy_pct']:.0f}%", WHITE, pct_x, bar_y - 2)


# ── Side panel ────────────────────────────────────────────────

def _draw_side(screen, fonts, pid, sessions, panel_h):
    _, _, f_sm, f_xs = fonts
    x, y, w = SIDE_X, TABLE_Y, SIDE_W

    _panel(screen, x, y, w, panel_h, BORDER, radius=12)

    _t(screen, f_sm, pid, ACCENT, x + 16, y + 14)
    _t(screen, f_xs, "Session breakdown", DIM, x + 16, y + 36)
    pygame.draw.line(screen, BORDER, (x + 12, y + 56), (x + w - 12, y + 56))

    ry = y + 66
    for s in sessions:
        if ry + 58 > y + panel_h - 10:
            break
        done   = bool(s["completed"])
        bc     = GREEN if done else BORDER
        label  = f"S{s['session_number']} · {s['block_type'].replace('_', ' ')}"
        _panel(screen, x + 10, ry, w - 20, 52, bc, radius=8)
        _t(screen, f_xs, label,
           WHITE if done else DIM, x + 20, ry + 6)
        _t(screen, f_xs,
           f"Trials: {int(s['trials'])}   Acc: {s['accuracy_pct']:.0f}%",
           DIM, x + 20, ry + 26)
        _bar(screen, x + 20, ry + 44, w - 40, 5,
             s["accuracy_pct"] / 100.0,
             fg=GREEN if s["accuracy_pct"] >= 70 else ORANGE)
        ry += 60

    if not sessions:
        _t(screen, f_xs, "No sessions recorded yet.", DIM, x + 16, y + 74)


# ── Entry point ───────────────────────────────────────────────

def run_data_viewer(screen, clock, fonts):
    f_big, f_med, f_sm, f_xs = fonts
    W, H = screen.get_width(), screen.get_height()

    selected_idx  = 0
    scroll_offset = 0
    stats         = []
    sessions      = []
    refresh_t     = 0

    clip_top    = TABLE_Y + 30
    clip_bottom = H - 62
    visible_rows = (clip_bottom - clip_top) // ROW_H
    panel_h     = clip_bottom - TABLE_Y

    back_rect = pygame.Rect(PAD, H - 50, 110, 34)

    pygame.display.set_caption("Grid-Sailing — Data Overview")

    while True:
        clock.tick(FPS)
        now = pygame.time.get_ticks()

        if now - refresh_t > 3000:
            stats    = get_participant_stats()
            sessions = (get_session_breakdown(stats[selected_idx]["participant_id"])
                        if stats else [])
            refresh_t = now

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return
                if event.key == pygame.K_DOWN and stats:
                    selected_idx = min(selected_idx + 1, len(stats) - 1)
                    if selected_idx >= scroll_offset + visible_rows:
                        scroll_offset += 1
                    sessions = get_session_breakdown(
                        stats[selected_idx]["participant_id"])
                if event.key == pygame.K_UP and stats:
                    selected_idx = max(selected_idx - 1, 0)
                    if selected_idx < scroll_offset:
                        scroll_offset -= 1
                    sessions = get_session_breakdown(
                        stats[selected_idx]["participant_id"])
            if event.type == pygame.MOUSEBUTTONDOWN:
                if back_rect.collidepoint(event.pos):
                    return
                mx, my = event.pos
                for i in range(len(stats)):
                    row_i = i - scroll_offset
                    if 0 <= row_i < visible_rows:
                        ry = clip_top + row_i * ROW_H
                        if TABLE_X <= mx <= TABLE_X + TABLE_W and ry <= my <= ry + ROW_H:
                            selected_idx = i
                            sessions = get_session_breakdown(
                                stats[i]["participant_id"])
            if event.type == pygame.MOUSEWHEEL:
                scroll_offset = max(0, min(
                    scroll_offset - event.y,
                    max(0, len(stats) - visible_rows)
                ))

        # ── Draw ─────────────────────────────────────────────
        screen.fill(BG)

        # Title bar
        pygame.draw.rect(screen, (18, 18, 32), (0, 0, W, 58))
        pygame.draw.line(screen, BORDER, (0, 58), (W, 58))
        _t(screen, f_big, "Data Overview", WHITE, PAD, 16)
        _t(screen, f_xs,
           "Up/Down or click to select   |   Scroll to browse   |   ESC to go back",
           DIM, 0, 36, center_in_w=W)

        # ── Summary cards ─────────────────────────────────────
        n_parts  = len(stats)
        n_trials = sum(int(s["total_trials"]) for s in stats)
        avg_acc  = (sum(s["accuracy_pct"] for s in stats) / n_parts) if n_parts else 0
        avg_rt   = (sum(s["avg_rt_ms"]    for s in stats) / n_parts) if n_parts else 0

        card_w = (W - PAD * 2 - 36) // 4
        cx = PAD
        for label, val, sub, col in [
            ("Participants",    str(n_parts),               "registered",            ACCENT),
            ("Total Trials",    str(n_trials),              "across all participants", GREEN),
            ("Avg Accuracy",    f"{avg_acc:.0f}%",          "correct trials",         AMBER),
            ("Avg React. Time", f"{avg_rt/1000:.2f}s" if avg_rt else "—",
                                                            "planning to first key",  PURPLE),
        ]:
            _summary_card(screen, fonts, cx, CARDS_Y, card_w, label, val, sub, col)
            cx += card_w + 12

        # ── Table ─────────────────────────────────────────────
        _draw_header(screen, fonts, TABLE_Y)

        clip_rect = pygame.Rect(TABLE_X, clip_top, TABLE_W + 50, clip_bottom - clip_top)
        screen.set_clip(clip_rect)
        for i, stat in enumerate(stats):
            row_i = i - scroll_offset
            if row_i < 0 or row_i >= visible_rows:
                continue
            ry = clip_top + row_i * ROW_H
            _draw_row(screen, fonts, stat, ry, selected=(i == selected_idx))
        screen.set_clip(None)

        if not stats:
            _t(screen, f_sm, "No participants registered yet.", DIM,
               TABLE_X + 20, clip_top + 20)

        # Scrollbar
        if len(stats) > visible_rows:
            sb_h    = clip_bottom - clip_top
            th      = max(30, int(sb_h * visible_rows / len(stats)))
            ty      = clip_top + int((sb_h - th) * scroll_offset
                                     / max(1, len(stats) - visible_rows))
            pygame.draw.rect(screen, (36, 36, 60),
                             (TABLE_X + TABLE_W - 6, clip_top, 6, sb_h), border_radius=3)
            pygame.draw.rect(screen, BORDER,
                             (TABLE_X + TABLE_W - 6, ty, 6, th), border_radius=3)

        # ── Side panel ────────────────────────────────────────
        if stats:
            _draw_side(screen, fonts,
                       stats[selected_idx]["participant_id"], sessions, panel_h)
        else:
            _panel(screen, SIDE_X, TABLE_Y, SIDE_W, panel_h, BORDER)
            _t(screen, f_xs, "Select a participant", DIM, SIDE_X + 16, TABLE_Y + 20)

        # ── Bottom bar ────────────────────────────────────────
        pygame.draw.line(screen, BORDER, (0, H - 58), (W, H - 58))
        pygame.draw.rect(screen, PANEL2, back_rect, border_radius=8)
        pygame.draw.rect(screen, BORDER, back_rect, width=1, border_radius=8)
        _t(screen, f_xs, "< Back", DIM, back_rect.x + 14, back_rect.y + 10)

        _t(screen, f_xs,
           f"Auto-refreshes every 3s   |   {n_parts} participant(s)   |   {n_trials} trial(s)",
           DIM, 0, H - 40, center_in_w=W)

        pygame.display.flip()
