# ============================================================
#  GRID-SAILING TASK — Data Viewer
#
#  Accessible from the Researcher Setup screen.
#  Juliet can see a live dashboard of all collected data
#  without opening a terminal or spreadsheet.
#
#  Layout:
#    Top row  — 4 summary stat cards
#    Middle   — scrollable participant table with mini bar charts
#    Side panel (right) — session breakdown for selected participant
#    Bottom   — ESC / Back to return
# ============================================================

import pygame
import sys
from database.db import get_participant_stats, get_session_breakdown
from config import WINDOW_WIDTH, WINDOW_HEIGHT, FPS

# ── Palette (matches the rest of the app) ────────────────────
BG       = (12,  12,  22)
PANEL    = (20,  20,  36)
PANEL2   = (26,  26,  44)
BORDER   = (52,  52,  80)
WHITE    = (230, 230, 242)
DIM      = (100, 100, 138)
ACCENT   = ( 88, 148, 255)
GREEN    = ( 58, 196, 108)
AMBER    = (210, 158,  28)
ORANGE   = (228, 138,  48)
RED_C    = (212,  58,  58)
PURPLE   = (160,  90, 220)

GROUP_COLORS = {
    "MI-High":   ( 88, 148, 255),
    "MI-Low":    ( 60, 110, 210),
    "PP-High":   ( 58, 196, 108),
    "PP-Low":    ( 38, 148,  80),
    "CTRL-High": (210, 158,  28),
    "CTRL-Low":  (168, 118,  18),
}

PAD      = 40
TABLE_X  = PAD
TABLE_W  = WINDOW_WIDTH - PAD * 2 - 320   # leave room for side panel
SIDE_X   = TABLE_X + TABLE_W + 16
SIDE_W   = WINDOW_WIDTH - SIDE_X - PAD
ROW_H    = 52
HEADER_Y = 148    # y below summary cards


def _t(screen, font, text, col, x, y, right=False, center_w=0):
    s = font.render(text, True, col)
    if right:
        screen.blit(s, (x - s.get_width(), y))
    elif center_w:
        screen.blit(s, (x + center_w//2 - s.get_width()//2, y))
    else:
        screen.blit(s, (x, y))
    return s

def _panel(screen, x, y, w, h, col=BORDER, radius=10):
    pygame.draw.rect(screen, PANEL,  (x, y, w, h), border_radius=radius)
    pygame.draw.rect(screen, col,    (x, y, w, h), width=1, border_radius=radius)

def _bar(screen, x, y, w, h, pct, fg, bg=(30, 30, 52)):
    """Horizontal fill bar — pct is 0.0–1.0."""
    pygame.draw.rect(screen, bg, (x, y, w, h), border_radius=4)
    if pct > 0:
        pygame.draw.rect(screen, fg, (x, y, int(w * min(pct, 1.0)), h), border_radius=4)

def _pill(screen, font, text, fg, bg, x, y):
    s  = font.render(text, True, fg)
    pw = s.get_width() + 14
    ph = s.get_height() + 6
    pygame.draw.rect(screen, bg, (x, y, pw, ph), border_radius=ph//2)
    screen.blit(s, (x + 7, y + 3))
    return pw


def _summary_card(screen, fonts, x, y, w, h, label, value, sub, accent):
    f_big, f_med, f_sm, f_xs = fonts
    _panel(screen, x, y, w, h, accent)
    _t(screen, f_xs,  label, DIM,    x + 18, y + 12)
    _t(screen, f_med, value, accent, x + 18, y + 32)
    if sub:
        _t(screen, f_xs, sub, DIM, x + 18, y + h - 22)


def _draw_table_header(screen, fonts, y):
    f_big, f_med, f_sm, f_xs = fonts
    cols = _col_positions()
    labels = ["ID", "Group", "Age", "Sessions", "Trials", "Avg Score", "Accuracy"]
    pygame.draw.rect(screen, PANEL2, (TABLE_X, y, TABLE_W, 30), border_radius=6)
    for (cx, cw), lbl in zip(cols, labels):
        _t(screen, f_xs, lbl, DIM, TABLE_X + cx + 8, y + 7)
    pygame.draw.line(screen, BORDER, (TABLE_X, y+30), (TABLE_X+TABLE_W, y+30))


def _col_positions():
    """(x_offset, col_width) for each column within the table."""
    return [
        (0,   80),   # ID
        (80,  110),  # Group
        (190,  50),  # Age
        (240,  80),  # Sessions
        (320,  70),  # Trials
        (390,  90),  # Avg Score
        (480, TABLE_W - 488),  # Accuracy bar
    ]


def _draw_participant_row(screen, fonts, stat, y, selected, scroll_clip):
    f_big, f_med, f_sm, f_xs = fonts
    cols = _col_positions()

    # Row background
    bg = (32, 32, 56) if selected else PANEL
    bc = ACCENT if selected else BORDER
    pygame.draw.rect(screen, bg,  (TABLE_X, y, TABLE_W, ROW_H - 2), border_radius=8)
    if selected:
        pygame.draw.rect(screen, bc, (TABLE_X, y, TABLE_W, ROW_H - 2), width=1, border_radius=8)

    cy = y + ROW_H//2 - 8   # vertical centre for text

    # Clip row to visible scroll area
    if y + ROW_H < scroll_clip[0] or y > scroll_clip[1]:
        return

    values = [
        stat["participant_id"],
        stat["group_name"],
        str(stat["age"] or "—"),
        str(int(stat["sessions_done"])),
        str(int(stat["total_trials"])),
        f"{stat['avg_score']:.0f}",
    ]

    for i, ((cx, cw), val) in enumerate(zip(cols, values)):
        col = WHITE if selected else (WHITE if i == 0 else DIM)
        if i == 0:
            col = ACCENT if selected else WHITE
        _t(screen, f_sm if i == 0 else f_xs, val, col, TABLE_X + cx + 8, cy)

    # Group badge
    gx, gw = cols[1]
    gcol = GROUP_COLORS.get(stat["group_name"], DIM)
    _pill(screen, f_xs, stat["group_name"], (12, 12, 22), gcol,
          TABLE_X + gx + 8, y + ROW_H//2 - 12)

    # Accuracy bar
    ax, aw = cols[6]
    bar_x = TABLE_X + ax + 8
    bar_w = aw - 16
    pct   = stat["accuracy_pct"] / 100.0
    bar_y = y + ROW_H//2 - 6
    _bar(screen, bar_x, bar_y, bar_w, 12, pct,
         fg=GREEN if pct >= 0.7 else (ORANGE if pct >= 0.4 else RED_C))
    _t(screen, f_xs, f"{stat['accuracy_pct']:.0f}%", WHITE,
       bar_x + bar_w + 6, bar_y - 2)


def _draw_side_panel(screen, fonts, pid, sessions):
    f_big, f_med, f_sm, f_xs = fonts
    x, y, w = SIDE_X, HEADER_Y, SIDE_W
    H = WINDOW_HEIGHT - HEADER_Y - 60

    _panel(screen, x, y, w, H, BORDER)
    _t(screen, f_sm, pid, ACCENT, x + 16, y + 14)
    _t(screen, f_xs, "Session breakdown", DIM, x + 16, y + 38)
    pygame.draw.line(screen, BORDER, (x + 12, y + 58), (x + w - 12, y + 58))

    ry = y + 68
    for s in sessions:
        if ry + 54 > y + H - 10:
            break
        done   = bool(s["completed"])
        bc     = GREEN if done else BORDER
        label  = f"S{s['session_number']}·{s['block_type'].replace('_',' ')[:8]}"
        _panel(screen, x + 10, ry, w - 20, 50, bc, radius=8)

        _t(screen, f_xs, label, WHITE if done else DIM, x + 18, ry + 6)
        _t(screen, f_xs,
           f"Trials: {int(s['trials'])}   Acc: {s['accuracy_pct']:.0f}%",
           DIM, x + 18, ry + 26)

        # Mini accuracy bar
        _bar(screen, x + 18, ry + 42, w - 36, 5,
             s["accuracy_pct"] / 100.0,
             fg=GREEN if s["accuracy_pct"] >= 70 else ORANGE)
        ry += 58

    if not sessions:
        _t(screen, f_xs, "No sessions recorded yet.", DIM, x + 16, y + 78)


# ── Main entry point ──────────────────────────────────────────

def run_data_viewer(screen, clock, fonts):
    """
    Display the live data dashboard.
    Returns when user presses ESC or Back.
    """
    f_big, f_med, f_sm, f_xs = fonts
    W, H = screen.get_width(), screen.get_height()

    selected_idx  = 0
    scroll_offset = 0     # rows scrolled down
    stats         = []
    sessions      = []
    refresh_t     = 0

    back_rect = pygame.Rect(PAD, H - 50, 100, 34)

    visible_rows = (H - HEADER_Y - 80) // ROW_H

    while True:
        clock.tick(FPS)
        now = pygame.time.get_ticks()

        # Refresh data every 3 seconds
        if now - refresh_t > 3000:
            stats     = get_participant_stats()
            sessions  = get_session_breakdown(
                stats[selected_idx]["participant_id"]
            ) if stats else []
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
                # Back button
                if back_rect.collidepoint(event.pos):
                    return
                # Click a row
                mx, my = event.pos
                for i in range(len(stats)):
                    row_i = i - scroll_offset
                    if 0 <= row_i < visible_rows:
                        ry = HEADER_Y + 32 + row_i * ROW_H
                        if (TABLE_X <= mx <= TABLE_X + TABLE_W
                                and ry <= my <= ry + ROW_H):
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

        # Title
        _t(screen, f_big, "Data Overview", WHITE, PAD, 18)
        _t(screen, f_xs, "↑ ↓ or click to select   ·   scroll to browse   ·   ESC to go back",
           DIM, PAD, 52)

        # ── Summary cards ─────────────────────────────────────
        n_parts  = len(stats)
        n_trials = sum(int(s["total_trials"]) for s in stats)
        avg_acc  = (sum(s["accuracy_pct"] for s in stats) / n_parts) if n_parts else 0
        avg_rt   = (sum(s["avg_rt_ms"] for s in stats) / n_parts) if n_parts else 0

        card_w = (W - PAD * 2 - 36) // 4
        cx = PAD
        for label, val, sub, col in [
            ("Participants",   str(n_parts),
             "registered",                    ACCENT),
            ("Total Trials",   str(n_trials),
             "across all participants",        GREEN),
            ("Avg Accuracy",   f"{avg_acc:.0f}%",
             "correct trials",                AMBER),
            ("Avg React. Time", f"{avg_rt/1000:.2f}s" if avg_rt else "—",
             "planning → first key",          PURPLE),
        ]:
            _summary_card(screen, fonts, cx, 74, card_w, 64,
                          label, val, sub, col)
            cx += card_w + 12

        # ── Table ─────────────────────────────────────────────
        _draw_table_header(screen, fonts, HEADER_Y)
        clip_top    = HEADER_Y + 32
        clip_bottom = H - 70
        clip_rect   = pygame.Rect(TABLE_X, clip_top, TABLE_W, clip_bottom - clip_top)

        screen.set_clip(clip_rect)
        for i, stat in enumerate(stats):
            row_i = i - scroll_offset
            if row_i < 0 or row_i >= visible_rows:
                continue
            ry = clip_top + row_i * ROW_H
            _draw_participant_row(screen, fonts, stat, ry,
                                  selected=(i == selected_idx),
                                  scroll_clip=(clip_top, clip_bottom))
        screen.set_clip(None)

        if not stats:
            _t(screen, f_sm, "No participants registered yet.", DIM,
               TABLE_X + 20, clip_top + 20)

        # Scrollbar
        if len(stats) > visible_rows:
            sb_h     = clip_bottom - clip_top
            thumb_h  = max(30, int(sb_h * visible_rows / len(stats)))
            thumb_y  = clip_top + int((sb_h - thumb_h) * scroll_offset
                                      / max(1, len(stats) - visible_rows))
            pygame.draw.rect(screen, (40, 40, 68),
                             (TABLE_X + TABLE_W - 6, clip_top, 6, sb_h), border_radius=3)
            pygame.draw.rect(screen, BORDER,
                             (TABLE_X + TABLE_W - 6, thumb_y, 6, thumb_h), border_radius=3)

        # ── Side panel ────────────────────────────────────────
        if stats:
            _draw_side_panel(screen, fonts,
                             stats[selected_idx]["participant_id"], sessions)
        else:
            _panel(screen, SIDE_X, HEADER_Y, SIDE_W,
                   H - HEADER_Y - 60, BORDER)
            _t(screen, f_xs, "Select a participant", DIM, SIDE_X + 16, HEADER_Y + 20)

        # ── Bottom bar ────────────────────────────────────────
        pygame.draw.line(screen, BORDER, (0, H - 58), (W, H - 58))
        pygame.draw.rect(screen, (30, 30, 52), back_rect, border_radius=8)
        pygame.draw.rect(screen, BORDER,       back_rect, width=1, border_radius=8)
        _t(screen, f_xs, "← Back", DIM, back_rect.x + 12, back_rect.y + 9)

        _t(screen, f_xs,
           f"Auto-refreshes every 3 s   ·   {n_parts} participant(s)   ·   {n_trials} trial(s) recorded",
           DIM, W // 2, H - 44, center_w=0)

        pygame.display.flip()
