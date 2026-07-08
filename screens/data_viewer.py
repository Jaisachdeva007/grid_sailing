# ============================================================
#  GRID-SAILING TASK — Data Viewer  (v5 — professional)
# ============================================================

import pygame
import sys
import os
from database.db import (
    get_participant_stats, get_session_breakdown,
    get_participant_trials
)
from export.exporter import export_participant, export_all, export_summary, export_reflections
from config import WINDOW_WIDTH, WINDOW_HEIGHT, FPS

# ── Palette ───────────────────────────────────────────────────
BG      = (8,    8,   16)
SURFACE = (12,  12,   22)
PANEL   = (18,  18,   32)
PANEL2  = (26,  26,   44)
PANEL3  = (34,  34,   56)
BORDER  = (44,  44,   72)
BORDER2 = (62,  62,   98)
WHITE   = (245, 245, 255)
DIM     = (120, 120, 160)
DIM2    = (70,   70, 108)
ACCENT  = (88,  148, 255)
GREEN   = (52,  200, 100)
AMBER   = (220, 162,  28)
ORANGE  = (228, 138,  48)
RED_C   = (220,  60,  60)
PURPLE  = (160,  90, 220)

GROUP_COLORS = {
    "MI-High":   (88,  148, 255),
    "MI-Low":    (56,  108, 210),
    "PP-High":   (52,  200, 100),
    "PP-Low":    (38,  148,  80),
    "CTRL-High": (220, 162,  28),
    "CTRL-Low":  (168, 118,  18),
}

W, H  = WINDOW_WIDTH, WINDOW_HEIGHT
PAD   = 48
ROW_H = 52


# ── Low-level drawing helpers ─────────────────────────────────

def _t(screen, font, text, col, x, y, cw=0):
    """Blit text; if cw>0 centre within that column width."""
    s = font.render(str(text), True, col)
    screen.blit(s, (x + cw // 2 - s.get_width() // 2, y) if cw else (x, y))
    return s


def _panel(screen, x, y, w, h, border_col=BORDER, r=10, fill=PANEL):
    pygame.draw.rect(screen, fill,       (x, y, w, h), border_radius=r)
    pygame.draw.rect(screen, border_col, (x, y, w, h), width=1, border_radius=r)


def _shadow(screen, x, y, w, h, r=12):
    pygame.draw.rect(screen, (4, 4, 8), (x + 3, y + 5, w, h), border_radius=r)


def _bar(screen, x, y, w, h, pct, fg):
    pygame.draw.rect(screen, (20, 20, 40), (x, y, w, h), border_radius=3)
    if pct > 0:
        pygame.draw.rect(screen, fg,
                         (x, y, max(3, int(w * min(pct, 1.0))), h), border_radius=3)


def _pill(screen, font, text, fg, bg, x, y):
    s  = font.render(text, True, fg)
    pw = s.get_width() + 18
    ph = s.get_height() + 8
    pygame.draw.rect(screen, bg, (x, y, pw, ph), border_radius=ph // 2)
    screen.blit(s, (x + 9, y + 4))
    return pw


def _dot_grid(screen):
    for gx in range(0, W + 64, 64):
        for gy in range(0, H + 64, 64):
            pygame.draw.circle(screen, (18, 18, 36), (gx, gy), 1)


# ── Compound UI components ────────────────────────────────────

def _title_bar(screen, fonts, title, subtitle=""):
    _, f_med, _, f_xs = fonts
    pygame.draw.rect(screen, SURFACE, (0, 0, W, 68))
    pygame.draw.line(screen, BORDER, (0, 68), (W, 68))
    pygame.draw.rect(screen, ACCENT, (0, 0, 3, 68))          # left accent stripe
    _t(screen, f_med, title, WHITE, PAD + 8, 20)
    if subtitle:
        hs = f_xs.render(subtitle, True, DIM2)
        screen.blit(hs, (W - PAD - hs.get_width(), 26))


def _stat_card(screen, fonts, x, y, w, h, label, value, sub, col):
    f_big, _, f_sm, f_xs = fonts
    _shadow(screen, x, y, w, h, r=14)
    _panel(screen, x, y, w, h, border_col=BORDER, r=14, fill=PANEL)
    pygame.draw.rect(screen, col, (x + 1, y + 1, w - 2, 4), border_radius=14)   # top bar
    lbl_s = f_xs.render(label.upper(), True, DIM)
    screen.blit(lbl_s, (x + 18, y + 14))
    val_s = f_big.render(value, True, col)
    screen.blit(val_s, (x + 18, y + 34))
    if sub:
        sub_s = f_xs.render(sub, True, DIM2)
        screen.blit(sub_s, (x + 18, y + h - 20))


def _ghost_btn(screen, fonts, label, rect):
    _, _, _, f_xs = fonts
    hover = rect.collidepoint(pygame.mouse.get_pos())
    fill  = PANEL3 if hover else PANEL2
    col   = WHITE  if hover else DIM
    pygame.draw.rect(screen, fill,    rect, border_radius=8)
    pygame.draw.rect(screen, BORDER2, rect, width=1, border_radius=8)
    ls = f_xs.render(label, True, col)
    screen.blit(ls, (rect.centerx - ls.get_width() // 2,
                     rect.centery - ls.get_height() // 2))


def _action_btn(screen, fonts, label, sub, rect, color):
    _, _, f_sm, f_xs = fonts
    hover = rect.collidepoint(pygame.mouse.get_pos())
    col   = tuple(min(255, c + 28) for c in color) if hover else color
    pygame.draw.rect(screen, (4, 4, 10),
                     (rect.x + 2, rect.y + 3, rect.w, rect.h), border_radius=10)
    pygame.draw.rect(screen, col, rect, border_radius=10)
    offset = -8 if sub else 0
    ls = f_sm.render(label, True, (8, 8, 16))
    screen.blit(ls, (rect.centerx - ls.get_width() // 2,
                     rect.centery + offset - ls.get_height() // 2))
    if sub:
        ss = f_xs.render(sub, True, (30, 30, 50))
        screen.blit(ss, (rect.centerx - ss.get_width() // 2,
                         rect.centery + 8 - ss.get_height() // 2))


SB_W = 10   # scrollbar width

def _scrollbar(screen, x, clip_top, clip_bot, total, visible, scroll):
    """Draw scrollbar track + thumb. Returns thumb rect for drag detection."""
    if total <= visible:
        return None
    sb_h = clip_bot - clip_top
    th   = max(32, int(sb_h * visible / total))
    ty   = clip_top + int((sb_h - th) * scroll / max(1, total - visible))
    pygame.draw.rect(screen, (18, 18, 38),  (x, clip_top, SB_W, sb_h), border_radius=5)
    thumb_r = pygame.Rect(x, ty, SB_W, th)
    hover   = thumb_r.collidepoint(pygame.mouse.get_pos())
    col     = (130, 130, 200) if hover else (88, 88, 148)
    pygame.draw.rect(screen, col, thumb_r, border_radius=5)
    return thumb_r


def _scrollbar_click(ev_pos, thumb_r, clip_top, clip_bot, total, visible):
    """Returns new scroll value if clicking the scrollbar track (not thumb)."""
    if thumb_r is None:
        return None
    x = thumb_r.x
    if not (x <= ev_pos[0] <= x + SB_W and clip_top <= ev_pos[1] <= clip_bot):
        return None
    if thumb_r.collidepoint(ev_pos):
        return None   # thumb drag handled separately
    # Click on track: jump proportionally
    frac = (ev_pos[1] - clip_top) / max(1, clip_bot - clip_top)
    return max(0, min(int(frac * total), total - visible))


def _bottom_bar(screen):
    """Draw the bottom bar background + divider — call before drawing buttons."""
    pygame.draw.rect(screen, SURFACE, (0, H - 96, W, 96))
    pygame.draw.line(screen, BORDER, (0, H - 96), (W, H - 96))


# ── Column builders ───────────────────────────────────────────

def _cols_a(table_w):
    """View A column definitions. Last column fills the remainder."""
    fixed = [
        (164, "PARTICIPANT"),
        (148, "GROUP"),
        (68,  "AGE"),
        (96,  "SESSIONS"),
        (88,  "TRIALS"),
        (106, "AVG SCORE"),
    ]
    used = sum(w for w, _ in fixed)
    cols, x = [], 0
    for w, lbl in fixed:
        cols.append((x, w, lbl))
        x += w
    cols.append((x, max(80, table_w - used), "ACCURACY"))
    return cols


def _cols_b(tw):
    """View B column definitions. Last column fills the remainder."""
    fixed = [
        (50,  "S#"),
        (156, "BLOCK"),
        (50,  "TR"),
        (88,  "GRID"),
        (110, "RESULT"),
        (124, "MOVES / OPT"),
        (92,  "SCORE"),
        (120, "REACT (ms)"),
    ]
    used = sum(w for w, _ in fixed)
    cols, x = [], 0
    for w, lbl in fixed:
        cols.append((x, w, lbl))
        x += w
    cols.append((x, max(60, tw - used), "DURATION"))
    return cols


# ──────────────────────────────────────────────────────────────
#  VIEW A — Participant summary list
# ──────────────────────────────────────────────────────────────

def _view_a(screen, clock, fonts, on_select):
    f_big, f_med, f_sm, f_xs = fonts

    CARD_H   = 104
    CARDS_Y  = 80
    TABLE_Y  = CARDS_Y + CARD_H + 16          # 200
    SIDE_W   = 304
    GAP      = 24
    TABLE_W  = W - PAD * 2 - SIDE_W - GAP
    SIDE_X   = PAD + TABLE_W + GAP
    HDR_H    = 40
    CLIP_TOP = TABLE_Y + HDR_H                 # 240
    CLIP_BOT = H - 96
    VIS      = max(1, (CLIP_BOT - CLIP_TOP) // ROW_H)

    COLS = _cols_a(TABLE_W)

    stats        = []
    sessions     = []
    sel          = 0
    scroll       = 0
    refresh_t    = 0
    msg = ""; msg_col = GREEN
    sb_dragging  = False
    sb_drag_orig = (0, 0, 0)   # (mouse_y_start, scroll_start, total)

    BBAR_Y    = H - 76
    back_r    = pygame.Rect(PAD,            BBAR_Y, 110, 42)
    exp_all_r = pygame.Rect(PAD + 122,      BBAR_Y, 200, 42)
    exp_sum_r = pygame.Rect(PAD + 334,      BBAR_Y, 210, 42)
    exp_ref_r = pygame.Rect(PAD + 556,      BBAR_Y, 230, 42)
    thumb_r   = None

    SB_X = PAD + TABLE_W + SB_W + 2   # scrollbar x in view A

    pygame.display.set_caption("Grid-Sailing — Data Overview")

    while True:
        clock.tick(FPS)
        now = pygame.time.get_ticks()

        # Auto-refresh every 3 s
        if now - refresh_t > 3000:
            stats = get_participant_stats()
            if stats:
                sel = min(sel, len(stats) - 1)
                sessions = get_session_breakdown(stats[sel]["participant_id"])
            refresh_t = now

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit()

            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    return
                if ev.key == pygame.K_DOWN and stats:
                    sel = min(sel + 1, len(stats) - 1)
                    if sel >= scroll + VIS:
                        scroll += 1
                    sessions = get_session_breakdown(stats[sel]["participant_id"])
                if ev.key == pygame.K_UP and stats:
                    sel = max(sel - 1, 0)
                    if sel < scroll:
                        scroll -= 1
                    sessions = get_session_breakdown(stats[sel]["participant_id"])

            if ev.type == pygame.MOUSEBUTTONUP:
                sb_dragging = False

            if ev.type == pygame.MOUSEMOTION and sb_dragging:
                my0, sc0, tot = sb_drag_orig
                dy = ev.pos[1] - my0
                sb_h = CLIP_BOT - CLIP_TOP
                ratio = dy / max(1, sb_h)
                scroll = max(0, min(sc0 + int(ratio * tot), max(0, tot - VIS)))

            if ev.type == pygame.MOUSEBUTTONDOWN:
                mx, my = ev.pos
                # Scroll wheel via buttons 4/5 (compatibility fallback)
                if ev.button == 4:
                    scroll = max(0, scroll - 3)
                elif ev.button == 5:
                    scroll = min(scroll + 3, max(0, len(stats) - VIS))
                # Scrollbar thumb drag
                elif thumb_r and thumb_r.collidepoint(ev.pos):
                    sb_dragging  = True
                    sb_drag_orig = (my, scroll, len(stats))
                # Scrollbar track click (only when actually in the scrollbar column)
                elif thumb_r and SB_X <= mx <= SB_X + SB_W:
                    nv = _scrollbar_click(ev.pos, thumb_r, CLIP_TOP, CLIP_BOT,
                                          len(stats), VIS)
                    if nv is not None:
                        scroll = nv
                # Row click → drill-down
                elif PAD <= mx <= PAD + TABLE_W and CLIP_TOP <= my <= CLIP_BOT:
                    ri  = (my - CLIP_TOP) // ROW_H
                    idx = ri + scroll
                    if 0 <= idx < len(stats):
                        sel      = idx
                        sessions = get_session_breakdown(stats[sel]["participant_id"])
                        on_select(stats[sel]["participant_id"])
                        return
                if back_r.collidepoint(ev.pos):
                    return
                if exp_all_r.collidepoint(ev.pos):
                    path = export_all()
                    msg = f"Saved  {os.path.basename(path)}"; msg_col = GREEN
                if exp_sum_r.collidepoint(ev.pos):
                    path = export_summary()
                    msg = f"Saved  {os.path.basename(path)}"; msg_col = GREEN
                if exp_ref_r.collidepoint(ev.pos):
                    path = export_reflections()
                    msg = f"Saved  {os.path.basename(path)}"; msg_col = GREEN

            if ev.type == pygame.MOUSEWHEEL:
                scroll = max(0, min(scroll - ev.y * 3, max(0, len(stats) - VIS)))

        # ── Draw ─────────────────────────────────────────────
        screen.fill(BG)
        _dot_grid(screen)
        _title_bar(screen, fonts, "Data Overview",
                   "Click a row to drill down   |   ESC to go back")

        # Stat cards
        n_parts  = len(stats)
        n_trials = sum(int(s["total_trials"]) for s in stats)
        avg_acc  = (sum(s["accuracy_pct"] for s in stats) / n_parts) if n_parts else 0
        avg_rt   = (sum(s["avg_rt_ms"]    for s in stats) / n_parts) if n_parts else 0
        cw       = (W - PAD * 2 - 36) // 4
        for i, (lbl, val, sub, col) in enumerate([
            ("Participants",  str(n_parts),
             "registered",                         ACCENT),
            ("Total Trials",  str(n_trials),
             "across all participants",             GREEN),
            ("Avg Accuracy",  f"{avg_acc:.0f}%",
             "correct responses",                   AMBER),
            ("Avg Reaction",
             f"{avg_rt / 1000:.2f}s" if avg_rt else "—",
             "planning to first move",              PURPLE),
        ]):
            _stat_card(screen, fonts,
                       PAD + i * (cw + 12), CARDS_Y, cw, CARD_H,
                       lbl, val, sub, col)

        # Table header
        pygame.draw.rect(screen, PANEL2, (PAD, TABLE_Y, TABLE_W, HDR_H), border_radius=8)
        for cx2, cw2, lbl in COLS:
            _t(screen, f_xs, lbl, DIM, PAD + cx2 + 12, TABLE_Y + 12)
        pygame.draw.line(screen, BORDER,
                         (PAD, TABLE_Y + HDR_H), (PAD + TABLE_W, TABLE_Y + HDR_H))

        # Rows
        mx, my = pygame.mouse.get_pos()
        screen.set_clip(pygame.Rect(PAD, CLIP_TOP, TABLE_W + 60, CLIP_BOT - CLIP_TOP))
        for i, stat in enumerate(stats):
            ri = i - scroll
            if ri < 0 or ri >= VIS:
                continue
            ry     = CLIP_TOP + ri * ROW_H
            is_sel = (i == sel)
            is_hov = (PAD <= mx <= PAD + TABLE_W and ry <= my < ry + ROW_H)

            if is_sel:
                fill = (26, 36, 66)
            elif is_hov:
                fill = PANEL2
            else:
                fill = PANEL if i % 2 == 0 else SURFACE

            pygame.draw.rect(screen, fill,
                             (PAD, ry, TABLE_W, ROW_H - 2), border_radius=6)
            if is_sel:
                pygame.draw.rect(screen, ACCENT,
                                 (PAD, ry, TABLE_W, ROW_H - 2), width=1, border_radius=6)

            stripe = ACCENT if is_sel else (BORDER2 if is_hov else BORDER)
            pygame.draw.rect(screen, stripe, (PAD, ry, 3, ROW_H - 2), border_radius=3)

            cy2 = ry + (ROW_H - 2) // 2 - 9

            # Participant ID — always use f_sm so IDs never get cut off
            pid_col = ACCENT if (is_sel or is_hov) else WHITE
            _t(screen, f_sm, stat["participant_id"], pid_col, PAD + 12, cy2)

            # Group pill
            gcol = GROUP_COLORS.get(stat["group_name"], DIM)
            _pill(screen, f_xs, stat["group_name"], (8, 8, 16), gcol,
                  PAD + COLS[1][0] + 8, ry + (ROW_H - 2) // 2 - 11)

            # Numeric cells (Age, Sessions, Trials, Avg Score)
            for col_i, (key, fmt) in enumerate([
                ("age",           "{}"),
                ("sessions_done", "{}"),
                ("total_trials",  "{}"),
                ("avg_score",     "{:.0f}"),
            ]):
                cx2, _, _ = COLS[col_i + 2]
                v   = stat[key]
                txt = fmt.format(int(v)) if v else "—"
                _t(screen, f_xs, txt, DIM, PAD + cx2 + 12, cy2 + 2)

            # Accuracy bar + label
            ax, aw, _ = COLS[6]
            pct     = stat["accuracy_pct"] / 100.0
            bar_x   = PAD + ax + 12
            bar_w   = max(60, aw - 60)
            bar_col = (GREEN  if pct >= 0.75 else
                       AMBER  if pct >= 0.50 else
                       ORANGE if pct >= 0.35 else RED_C)
            _bar(screen, bar_x, ry + (ROW_H - 2) // 2 - 5, bar_w, 10, pct, bar_col)
            _t(screen, f_xs, f"{stat['accuracy_pct']:.0f}%", bar_col,
               bar_x + bar_w + 8, cy2 + 2)

        screen.set_clip(None)

        if not stats:
            _t(screen, f_sm, "No participants registered yet.",
               DIM, PAD + 24, CLIP_TOP + 24)

        thumb_r = _scrollbar(screen, SB_X,
                             CLIP_TOP, CLIP_BOT, len(stats), VIS, scroll)

        # Side panel
        ph = CLIP_BOT - TABLE_Y
        pygame.draw.rect(screen, PANEL,  (SIDE_X, TABLE_Y, SIDE_W, ph), border_radius=12)
        pygame.draw.rect(screen, BORDER, (SIDE_X, TABLE_Y, SIDE_W, ph), width=1,
                         border_radius=12)

        if stats:
            pid  = stats[sel]["participant_id"]
            grp  = stats[sel]["group_name"]
            gcol = GROUP_COLORS.get(grp, DIM)
            _t(screen, f_sm, pid, WHITE, SIDE_X + 16, TABLE_Y + 14)
            _pill(screen, f_xs, grp, (8, 8, 16), gcol, SIDE_X + 16, TABLE_Y + 44)
            pygame.draw.line(screen, BORDER,
                             (SIDE_X + 12, TABLE_Y + 74),
                             (SIDE_X + SIDE_W - 12, TABLE_Y + 74))
            hdr_s = f_xs.render("SESSIONS", True, DIM)
            screen.blit(hdr_s, (SIDE_X + 16, TABLE_Y + 82))

            ry2 = TABLE_Y + 108
            for s in sessions:
                if ry2 + 66 > TABLE_Y + ph - 10:
                    break
                done = bool(s["completed"])
                bc   = GREEN if done else BORDER
                _shadow(screen, SIDE_X + 10, ry2, SIDE_W - 20, 60, r=10)
                pygame.draw.rect(screen, PANEL2,
                                 (SIDE_X + 10, ry2, SIDE_W - 20, 60), border_radius=10)
                pygame.draw.rect(screen, bc,
                                 (SIDE_X + 10, ry2, SIDE_W - 20, 60), width=1,
                                 border_radius=10)
                if done:
                    pygame.draw.rect(screen, GREEN,
                                     (SIDE_X + 10, ry2, 3, 60), border_radius=3)
                lbl2 = (f"S{s['session_number']}  "
                        f"{s['block_type'].replace('_', ' ').title()}")
                _t(screen, f_sm, lbl2,
                   WHITE if done else DIM, SIDE_X + 20, ry2 + 8)
                _t(screen, f_xs,
                   f"Trials: {int(s['trials'])}    Acc: {s['accuracy_pct']:.0f}%",
                   DIM, SIDE_X + 20, ry2 + 32)
                _bar(screen, SIDE_X + 20, ry2 + 50, SIDE_W - 40, 4,
                     s["accuracy_pct"] / 100.0,
                     GREEN if s["accuracy_pct"] >= 70 else ORANGE)
                ry2 += 68

            if not sessions:
                _t(screen, f_xs, "No sessions yet.", DIM, SIDE_X + 16, TABLE_Y + 110)
        else:
            _t(screen, f_xs, "Select a participant to preview.",
               DIM, SIDE_X + 16, TABLE_Y + 24)

        # Bottom bar
        _bottom_bar(screen)
        _ghost_btn(screen,  fonts, "< Back",             back_r)
        _action_btn(screen, fonts, "Export All",        "all participants CSV",  exp_all_r, ORANGE)
        _action_btn(screen, fonts, "Export Summary",    "one row per trial",     exp_sum_r, PURPLE)
        _action_btn(screen, fonts, "Export Reflections","MI group 3E logs",      exp_ref_r, GREEN)

        if msg:
            ms = f_xs.render(msg, True, msg_col)
            screen.blit(ms, (W - PAD - ms.get_width(), H - 54))

        hint = (f"Auto-refreshes every 3 s  "
                f"·  {n_parts} participant(s)  ·  {n_trials} total trial(s)")
        hs = f_xs.render(hint, True, DIM2)
        screen.blit(hs, (W // 2 - hs.get_width() // 2, H - 20))

        pygame.display.flip()


# ──────────────────────────────────────────────────────────────
#  VIEW B — Per-participant trial breakdown
# ──────────────────────────────────────────────────────────────

def _view_b(screen, clock, fonts, pid):
    f_big, f_med, f_sm, f_xs = fonts

    trials   = get_participant_trials(pid)
    scroll   = 0
    msg = ""; msg_col = GREEN

    STATS_H  = 104
    STATS_Y  = 80
    HDR_Y    = STATS_Y + STATS_H + 14          # 198
    HDR_H    = 40
    CLIP_TOP = HDR_Y + HDR_H                   # 238
    CLIP_BOT = H - 96
    TW       = W - PAD * 2
    VIS      = max(1, (CLIP_BOT - CLIP_TOP) // ROW_H)

    COLS = _cols_b(TW)

    BBAR_Y      = H - 76
    back_r      = pygame.Rect(PAD,       BBAR_Y, 110, 42)
    exp_r       = pygame.Rect(PAD + 122, BBAR_Y, 250, 42)
    graphs_r    = pygame.Rect(PAD + 386, BBAR_Y, 150, 42)
    thumb_r     = None
    sb_dragging = False
    sb_drag_orig = (0, 0, 0)
    SB_X_B      = PAD + TW + SB_W + 2

    pygame.display.set_caption(f"Grid-Sailing — {pid}")

    while True:
        clock.tick(FPS)

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    return False
                if ev.key == pygame.K_DOWN:
                    scroll = min(scroll + 1, max(0, len(trials) - VIS))
                if ev.key == pygame.K_UP:
                    scroll = max(scroll - 1, 0)
            if ev.type == pygame.MOUSEBUTTONUP:
                sb_dragging = False
            if ev.type == pygame.MOUSEMOTION and sb_dragging:
                my0, sc0, tot = sb_drag_orig
                dy = ev.pos[1] - my0
                sb_h = CLIP_BOT - CLIP_TOP
                ratio = dy / max(1, sb_h)
                scroll = max(0, min(sc0 + int(ratio * tot), max(0, tot - VIS)))
            if ev.type == pygame.MOUSEBUTTONDOWN:
                if ev.button == 4:
                    scroll = max(0, scroll - 3)
                elif ev.button == 5:
                    scroll = min(scroll + 3, max(0, len(trials) - VIS))
                elif thumb_r and thumb_r.collidepoint(ev.pos):
                    sb_dragging  = True
                    sb_drag_orig = (ev.pos[1], scroll, len(trials))
                elif thumb_r and SB_X_B <= ev.pos[0] <= SB_X_B + SB_W:
                    nv = _scrollbar_click(ev.pos, thumb_r, CLIP_TOP, CLIP_BOT,
                                          len(trials), VIS)
                    if nv is not None:
                        scroll = nv
                if back_r.collidepoint(ev.pos):
                    return False
                if graphs_r.collidepoint(ev.pos):
                    return True
                if exp_r.collidepoint(ev.pos):
                    path = export_participant(pid)
                    msg = f"Saved  {os.path.basename(path)}"; msg_col = GREEN
            if ev.type == pygame.MOUSEWHEEL:
                scroll = max(0, min(scroll - ev.y * 3, max(0, len(trials) - VIS)))

        # ── Draw ─────────────────────────────────────────────
        screen.fill(BG)
        _dot_grid(screen)
        _title_bar(screen, fonts,
                   f"{pid}  —  All Trials",
                   f"{len(trials)} total  |  ESC to go back")

        # Stat strip
        if trials:
            n_corr = sum(1 for t in trials if t["is_correct"])
            rts    = [t["reaction_time_ms"] for t in trials if t["reaction_time_ms"]]
            avg_rt = sum(rts) / len(rts) if rts else 0
            avg_sc = sum(t["reward_score"] or 0 for t in trials) / len(trials)
            cw     = (TW - 36) // 4
            for i, (val, lbl, col) in enumerate([
                (f"{n_corr} / {len(trials)}", "CORRECT TRIALS", GREEN),
                (f"{n_corr / len(trials) * 100:.0f}%", "ACCURACY",     AMBER),
                (f"{avg_rt:.0f} ms",                   "AVG REACTION", ACCENT),
                (f"{avg_sc:.0f}",                      "AVG SCORE",    PURPLE),
            ]):
                _stat_card(screen, fonts,
                           PAD + i * (cw + 12), STATS_Y, cw, STATS_H,
                           lbl, val, "", col)

        # Table header
        pygame.draw.rect(screen, PANEL2, (PAD, HDR_Y, TW, HDR_H), border_radius=8)
        for cx2, cw2, lbl in COLS:
            _t(screen, f_xs, lbl, DIM, PAD + cx2 + 12, HDR_Y + 12)
        pygame.draw.line(screen, BORDER,
                         (PAD, HDR_Y + HDR_H), (PAD + TW, HDR_Y + HDR_H))

        # Rows
        screen.set_clip(pygame.Rect(PAD, CLIP_TOP, TW, CLIP_BOT - CLIP_TOP))
        for i, tr in enumerate(trials):
            ri = i - scroll
            if ri < 0 or ri >= VIS:
                continue
            ry      = CLIP_TOP + ri * ROW_H
            correct = bool(tr["is_correct"])
            fill    = PANEL if i % 2 == 0 else SURFACE

            pygame.draw.rect(screen, fill,
                             (PAD, ry, TW, ROW_H - 2), border_radius=6)
            pygame.draw.rect(screen, BORDER,
                             (PAD, ry, TW, ROW_H - 2), width=1, border_radius=6)
            pygame.draw.rect(screen, GREEN if correct else RED_C,
                             (PAD, ry, 3, ROW_H - 2), border_radius=3)

            cy2 = ry + (ROW_H - 2) // 2 - 9

            def cell(col_i, text, color=WHITE, _cy=cy2):
                cx2, _, _ = COLS[col_i]
                _t(screen, f_xs, str(text), color, PAD + cx2 + 12, _cy)

            cell(0, tr["session_number"], DIM)

            bt = (tr["block_type"]
                  .replace("familiarization", "Familiar.")
                  .replace("pre_test",  "Pre-Test")
                  .replace("post_test", "Post-Test")
                  .replace("practice",  "Practice")
                  .replace("_", " "))
            cell(1, f"B{tr['block_number']} {bt}", DIM)
            cell(2, tr["trial_number"], WHITE)

            # Grid type pill
            gx_col, _, _ = COLS[3]
            is_rep = tr["grid_type"] == "repeated"
            _pill(screen, f_xs,
                  "REP" if is_rep else "RAN",
                  (8, 8, 16),
                  ACCENT if is_rep else ORANGE,
                  PAD + gx_col + 8, ry + (ROW_H - 2) // 2 - 11)

            cell(4, "Correct" if correct else "Missed",
                 GREEN if correct else RED_C)

            moves = tr["number_of_moves"] or 0
            opt   = tr["optimal_length"]  or 0
            extra = moves - opt
            moves_col = GREEN if extra <= 0 else (AMBER if extra <= 2 else RED_C)
            cell(5, f"{moves}  /  {opt}", moves_col)

            cell(6, str(tr["reward_score"] or 0), AMBER)

            rt = tr["reaction_time_ms"]
            cell(7, f"{rt:.0f}" if rt else "—",
                 WHITE if rt and rt < 5000 else DIM)

            mt  = tr["movement_time_ms"]
            idt = tr["imagery_duration_ms"]
            et  = tr["elapsed_time_s"]
            if mt:
                dur = f"{mt / 1000:.2f} s"
            elif idt:
                dur = f"{idt / 1000:.2f} s (img)"
            elif et:
                dur = f"{et:.2f} s"
            else:
                dur = "—"
            cell(8, dur, DIM)

        screen.set_clip(None)

        if not trials:
            _t(screen, f_sm, "No trials recorded for this participant yet.",
               DIM, PAD + 24, CLIP_TOP + 24)

        thumb_r = _scrollbar(screen, SB_X_B,
                             CLIP_TOP, CLIP_BOT, len(trials), VIS, scroll)

        # Bottom bar
        _bottom_bar(screen)
        _ghost_btn(screen,  fonts, "< Back",             back_r)
        _action_btn(screen, fonts, f"Export  {pid}",
                    "full keypress CSV",                  exp_r,    ACCENT)
        _action_btn(screen, fonts, "Graphs",
                    "pre/post test charts",               graphs_r, PURPLE)

        if msg:
            ms = f_xs.render(msg, True, msg_col)
            screen.blit(ms, (W - PAD - ms.get_width(), H - 54))

        hint_s = f_xs.render(
            "Green stripe = correct  |  Red stripe = missed  |  Scroll or arrow keys to browse",
            True, DIM2)
        screen.blit(hint_s, (W // 2 - hint_s.get_width() // 2, H - 20))

        pygame.display.flip()


# ──────────────────────────────────────────────────────────────
#  VIEW C — Per-participant graphs (pre/post test)
# ──────────────────────────────────────────────────────────────

def _line_graph(screen, fonts, gx, gy, gw, gh, title,
                series_rep, series_ran, y_label):
    """
    Draw a simple line chart with two series (repeated=blue, random=amber).
    series_rep / series_ran: lists of (trial_num, value) — value may be None.
    """
    _, _, f_sm, f_xs = fonts

    # Background panel
    pygame.draw.rect(screen, PANEL, (gx, gy, gw, gh), border_radius=8)
    pygame.draw.rect(screen, BORDER, (gx, gy, gw, gh), width=1, border_radius=8)

    LPAD, RPAD, TPAD, BPAD = 52, 14, 28, 32
    ax  = gx + LPAD
    ay  = gy + TPAD
    aw  = gw - LPAD - RPAD
    ah  = gh - TPAD - BPAD

    # Title
    ts = f_xs.render(title, True, WHITE)
    screen.blit(ts, (gx + LPAD, gy + 6))

    # Gather all finite values for scale
    all_vals = [v for _, v in series_rep + series_ran if v is not None]
    if not all_vals:
        nd = f_xs.render("No data", True, DIM)
        screen.blit(nd, (ax + aw // 2 - nd.get_width() // 2, ay + ah // 2 - 9))
        return

    y_min = 0
    y_max = max(all_vals) * 1.1 or 1.0

    all_x = [x for x, _ in series_rep + series_ran]
    x_min = min(all_x) if all_x else 1
    x_max = max(all_x) if all_x else 1

    def to_px(tx, ty):
        px = ax + int((tx - x_min) / max(1, x_max - x_min) * aw)
        py = ay + ah - int((ty - y_min) / (y_max - y_min) * ah)
        return px, py

    # Axes
    pygame.draw.line(screen, BORDER2, (ax, ay), (ax, ay + ah))
    pygame.draw.line(screen, BORDER2, (ax, ay + ah), (ax + aw, ay + ah))

    # Y ticks (4 gridlines)
    for i in range(5):
        yv  = y_min + (y_max - y_min) * i / 4
        _, py = to_px(x_min, yv)
        pygame.draw.line(screen, (28, 28, 52), (ax, py), (ax + aw, py))
        lbl = f_xs.render(f"{yv:.0f}", True, DIM2)
        screen.blit(lbl, (ax - lbl.get_width() - 4, py - lbl.get_height() // 2))

    # X ticks (every 5 trials)
    for tx in range(x_min, x_max + 1, max(1, (x_max - x_min) // 5)):
        px, _ = to_px(tx, y_min)
        pygame.draw.line(screen, (28, 28, 52), (px, ay), (px, ay + ah))
        lbl = f_xs.render(str(tx), True, DIM2)
        screen.blit(lbl, (px - lbl.get_width() // 2, ay + ah + 4))

    # Draw series
    for series, col in ((series_rep, ACCENT), (series_ran, AMBER)):
        pts = [(to_px(x, y)) for x, y in series if y is not None]
        if len(pts) >= 2:
            pygame.draw.lines(screen, col, False, pts, 2)
        for pt in pts:
            pygame.draw.circle(screen, col, pt, 4)


def _view_c(screen, clock, fonts, pid):
    """Graph view: pre-test and post-test line charts for one participant."""
    f_big, f_med, f_sm, f_xs = fonts

    trials_all = get_participant_trials(pid)
    tab        = 0   # 0=pre_test, 1=post_test
    TABS       = ["Pre-Test", "Post-Test"]
    TAB_TYPES  = ["pre_test", "post_test"]

    BBAR_Y = H - 76
    back_r = pygame.Rect(PAD, BBAR_Y, 110, 42)

    pygame.display.set_caption(f"Grid-Sailing — {pid} Graphs")

    while True:
        clock.tick(FPS)
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                return
            if ev.type == pygame.MOUSEBUTTONDOWN:
                mx, my = ev.pos
                if back_r.collidepoint(ev.pos):
                    return
                # Tab clicks
                for ti in range(2):
                    tab_r = pygame.Rect(PAD + ti * 160, 76, 148, 36)
                    if tab_r.collidepoint(mx, my):
                        tab = ti

        # ── Build series ─────────────────────────────────────
        block_type = TAB_TYPES[tab]
        trials = [t for t in trials_all if t["block_type"] == block_type]

        def series(metric_fn, grid_type):
            pts = []
            for t in trials:
                if t["grid_type"] == grid_type:
                    v = metric_fn(t)
                    if v is not None:
                        pts.append((t["trial_number"], v))
            return pts

        def mt(t):
            v = t.get("movement_time_ms")
            return v / 1000.0 if v else None

        def nm(t):
            return t.get("number_of_moves")

        def rs(t):
            return t.get("reward_score")

        rep_mt = series(mt, "repeated");  ran_mt = series(mt, "random")
        rep_nm = series(nm, "repeated");  ran_nm = series(nm, "random")
        rep_rs = series(rs, "repeated");  ran_rs = series(rs, "random")

        # ── Draw ─────────────────────────────────────────────
        screen.fill(BG)
        _dot_grid(screen)
        _title_bar(screen, fonts, f"{pid}  —  Test Graphs",
                   "ESC or < Back to return")

        # Tabs
        for ti, label in enumerate(TABS):
            tr = pygame.Rect(PAD + ti * 160, 76, 148, 36)
            fill   = PANEL2 if ti == tab else PANEL
            border = ACCENT if ti == tab else BORDER
            pygame.draw.rect(screen, fill,   tr, border_radius=8)
            pygame.draw.rect(screen, border, tr, width=1, border_radius=8)
            ls = f_sm.render(label, True, WHITE if ti == tab else DIM)
            screen.blit(ls, (tr.centerx - ls.get_width() // 2,
                             tr.centery - ls.get_height() // 2))

        # Legend (top-right)
        lx = W - PAD - 200
        for col, lbl in ((ACCENT, "Repeated"), (AMBER, "Random")):
            pygame.draw.line(screen, col, (lx, 88), (lx + 24, 88), 2)
            pygame.draw.circle(screen, col, (lx + 12, 88), 4)
            ls = f_xs.render(lbl, True, col)
            screen.blit(ls, (lx + 30, 82))
            lx += 110

        if not trials:
            _t(screen, f_sm, f"No {TABS[tab]} data for this participant.",
               DIM, PAD, 140)
        else:
            GH = (H - 80 - 96 - 30) // 3   # height per graph
            GW = W - PAD * 2
            GY_START = 122

            _line_graph(screen, fonts,
                        PAD, GY_START,             GW, GH,
                        "Reward Score", rep_rs, ran_rs, "pts")
            _line_graph(screen, fonts,
                        PAD, GY_START + GH + 8,    GW, GH,
                        "Number of Moves", rep_nm, ran_nm, "moves")
            _line_graph(screen, fonts,
                        PAD, GY_START + (GH + 8)*2, GW, GH,
                        "Movement Time (s)", rep_mt, ran_mt, "s")

        _bottom_bar(screen)
        _ghost_btn(screen, fonts, "< Back", back_r)

        pygame.display.flip()


# ── Entry point ───────────────────────────────────────────────

def run_data_viewer(screen, clock, fonts):
    drill   = [None]
    graphs  = [False]

    def on_select(pid):
        drill[0] = pid

    while True:
        drill[0]  = None
        graphs[0] = False
        _view_a(screen, clock, fonts, on_select)
        if drill[0]:
            show_graphs = _view_b(screen, clock, fonts, drill[0])
            if show_graphs:
                _view_c(screen, clock, fonts, drill[0])
        else:
            return
