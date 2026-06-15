# ============================================================
#  GRID-SAILING TASK — Data Viewer  (v3)
#
#  View A: Participant overview table  (summary cards + list)
#  View B: Trial drill-down           (every attempt, full detail)
#
#  Navigation:
#    Click participant row  → drill into their trials
#    ESC / Back             → return to previous view / home
#    Export button          → write CSV to exports/
# ============================================================

import pygame
import sys
import os
from database.db import (
    get_participant_stats, get_session_breakdown,
    get_participant_trials
)
from export.exporter import export_participant, export_all, export_summary
from config import WINDOW_WIDTH, WINDOW_HEIGHT, FPS

# ── Palette ───────────────────────────────────────────────────
BG      = (8,    8,  16)
SURFACE = (14,  14,  26)
PANEL   = (20,  20,  36)
PANEL2  = (26,  26,  44)
BORDER  = (48,  48,  76)
WHITE   = (245, 245, 255)
DIM     = (118, 118, 158)
ACCENT  = ( 88, 148, 255)
GREEN   = ( 52, 200, 100)
AMBER   = (220, 162,  28)
ORANGE  = (228, 138,  48)
RED_C   = (220,  60,  60)
PURPLE  = (160,  90, 220)

GROUP_COLORS = {
    "MI-High":   ( 88, 148, 255),
    "MI-Low":    ( 60, 110, 210),
    "PP-High":   ( 52, 200, 100),
    "PP-Low":    ( 38, 148,  80),
    "CTRL-High": (220, 162,  28),
    "CTRL-Low":  (168, 118,  18),
}

W, H   = WINDOW_WIDTH, WINDOW_HEIGHT
PAD    = 36
ROW_H  = 48
CARD_H = 82


# ── Tiny helpers ──────────────────────────────────────────────

def _t(screen, font, text, col, x, y, center_w=0):
    s = font.render(text, True, col)
    if center_w:
        screen.blit(s, (x + center_w // 2 - s.get_width() // 2, y))
    else:
        screen.blit(s, (x, y))
    return s

def _panel(screen, x, y, w, h, col=BORDER, r=10):
    pygame.draw.rect(screen, PANEL, (x, y, w, h), border_radius=r)
    pygame.draw.rect(screen, col,   (x, y, w, h), width=1, border_radius=r)

def _bar(screen, x, y, w, h, pct, fg):
    pygame.draw.rect(screen, (24, 24, 48), (x, y, w, h), border_radius=4)
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

def _btn(screen, fonts, label, rect, color, sub=""):
    _, f_med, f_sm, f_xs = fonts
    mouse = pygame.mouse.get_pos()
    hover = rect.collidepoint(mouse)
    col   = tuple(min(255, c + 22) for c in color) if hover else color
    pygame.draw.rect(screen, (4, 4, 10),
                     (rect.x + 2, rect.y + 3, rect.w, rect.h), border_radius=10)
    pygame.draw.rect(screen, col, rect, border_radius=10)
    ls = f_sm.render(label, True, (8, 8, 16))
    screen.blit(ls, (rect.x + rect.w // 2 - ls.get_width() // 2,
                     rect.y + (rect.h // 2 - ls.get_height() // 2) - (8 if sub else 0)))
    if sub:
        ss = f_xs.render(sub, True, (30, 30, 50))
        screen.blit(ss, (rect.x + rect.w // 2 - ss.get_width() // 2,
                         rect.y + rect.h // 2 + 4))
    return hover


# ── Title bar ─────────────────────────────────────────────────

def _title_bar(screen, fonts, title, hint="ESC to go back"):
    _, f_med, f_sm, f_xs = fonts
    pygame.draw.rect(screen, SURFACE, (0, 0, W, 58))
    pygame.draw.line(screen, BORDER, (0, 58), (W, 58))
    _t(screen, f_med, title, WHITE, PAD, 18)
    hr = f_xs.render(hint, True, DIM)
    screen.blit(hr, (W - PAD - hr.get_width(), 22))


# ── Summary cards (View A) ────────────────────────────────────

def _summary_cards(screen, fonts, stats):
    _, f_med, f_sm, f_xs = fonts
    n_parts  = len(stats)
    n_trials = sum(int(s["total_trials"]) for s in stats)
    avg_acc  = (sum(s["accuracy_pct"] for s in stats) / n_parts) if n_parts else 0
    avg_rt   = (sum(s["avg_rt_ms"]    for s in stats) / n_parts) if n_parts else 0

    card_w = (W - PAD * 2 - 36) // 4
    cx = PAD
    cards = [
        ("Participants",    str(n_parts),              "registered",             ACCENT),
        ("Total Trials",    str(n_trials),             "across all participants", GREEN),
        ("Avg Accuracy",    f"{avg_acc:.0f}%",         "correct trials",          AMBER),
        ("Avg React. Time", f"{avg_rt/1000:.2f}s" if avg_rt else "—",
                                                       "planning to first key",   PURPLE),
    ]
    for label, val, sub, col in cards:
        # shadow
        pygame.draw.rect(screen, (4, 4, 10),
                         (cx + 2, 70 + 3, card_w, CARD_H), border_radius=12)
        _panel(screen, cx, 70, card_w, CARD_H, col, r=12)
        pygame.draw.rect(screen, col, (cx + 1, 71, card_w - 2, 5), border_radius=12)
        _t(screen, f_xs,  label, DIM,   cx + 16, 86)
        _t(screen, f_med, val,   col,   cx + 16, 106)
        _t(screen, f_xs,  sub,   DIM,   cx + 16, 70 + CARD_H - 20)
        cx += card_w + 12


# ──────────────────────────────────────────────────────────────
#  VIEW A — Participant overview
# ──────────────────────────────────────────────────────────────

def _view_a(screen, clock, fonts, on_select):
    """
    Scrollable participant table.
    on_select(participant_id) is called when user clicks a row.
    Returns when user presses ESC.
    """
    f_big, f_med, f_sm, f_xs = fonts

    TABLE_Y   = 70 + CARD_H + 14
    SIDE_W    = 272
    TABLE_W   = W - PAD * 2 - SIDE_W - 16
    SIDE_X    = PAD + TABLE_W + 16
    HDR_H     = 30
    CLIP_TOP  = TABLE_Y + HDR_H
    CLIP_BOT  = H - 62
    VIS_ROWS  = (CLIP_BOT - CLIP_TOP) // ROW_H

    # Column layout: (x_offset, width)
    COLS = [(0,86),(86,114),(200,46),(246,74),(320,64),(384,90),(474, TABLE_W-474-44)]

    stats         = []
    sessions      = []
    sel           = 0
    scroll        = 0
    refresh_t     = 0
    msg           = ""
    msg_col       = GREEN

    back_r    = pygame.Rect(PAD,        H - 50, 110, 34)
    exp_all_r = pygame.Rect(PAD + 120,  H - 50, 170, 34)
    exp_sum_r = pygame.Rect(PAD + 300,  H - 50, 200, 34)

    pygame.display.set_caption("Grid-Sailing — Data Overview")

    while True:
        clock.tick(FPS)
        now_ms = pygame.time.get_ticks()

        if now_ms - refresh_t > 3000:
            stats     = get_participant_stats()
            sessions  = (get_session_breakdown(stats[sel]["participant_id"])
                         if stats else [])
            refresh_t = now_ms

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return
                if event.key == pygame.K_DOWN and stats:
                    sel = min(sel + 1, len(stats) - 1)
                    if sel >= scroll + VIS_ROWS: scroll += 1
                    sessions = get_session_breakdown(stats[sel]["participant_id"])
                if event.key == pygame.K_UP and stats:
                    sel = max(sel - 1, 0)
                    if sel < scroll: scroll -= 1
                    sessions = get_session_breakdown(stats[sel]["participant_id"])

            if event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                # Row click → drill down
                for i in range(len(stats)):
                    ri = i - scroll
                    if 0 <= ri < VIS_ROWS:
                        ry = CLIP_TOP + ri * ROW_H
                        if PAD <= mx <= PAD + TABLE_W and ry <= my <= ry + ROW_H:
                            sel = i
                            sessions = get_session_breakdown(
                                stats[i]["participant_id"])
                            on_select(stats[i]["participant_id"])
                            return
                # Buttons
                if back_r.collidepoint(event.pos):
                    return
                if exp_all_r.collidepoint(event.pos):
                    path = export_all()
                    msg = f"Saved: {os.path.basename(path)}"
                    msg_col = GREEN
                if exp_sum_r.collidepoint(event.pos):
                    path = export_summary()
                    msg = f"Saved: {os.path.basename(path)}"
                    msg_col = GREEN

            if event.type == pygame.MOUSEWHEEL:
                scroll = max(0, min(scroll - event.y,
                                    max(0, len(stats) - VIS_ROWS)))

        # ── Draw ─────────────────────────────────────────────
        screen.fill(BG)
        _title_bar(screen, fonts, "Data Overview",
                   "Click a participant to view every attempt   |   ESC to go back")
        _summary_cards(screen, fonts, stats)

        # Table header
        pygame.draw.rect(screen, PANEL2, (PAD, TABLE_Y, TABLE_W, HDR_H), border_radius=6)
        for (cx2, cw), lbl in zip(COLS, ["ID","Group","Age","Sessions","Trials","Avg Score","Accuracy"]):
            _t(screen, f_xs, lbl, DIM, PAD + cx2 + 8, TABLE_Y + 7)
        pygame.draw.line(screen, BORDER,
                         (PAD, TABLE_Y + HDR_H), (PAD + TABLE_W, TABLE_Y + HDR_H))

        # Rows
        clip = pygame.Rect(PAD, CLIP_TOP, TABLE_W + 48, CLIP_BOT - CLIP_TOP)
        screen.set_clip(clip)
        for i, stat in enumerate(stats):
            ri = i - scroll
            if ri < 0 or ri >= VIS_ROWS: continue
            ry = CLIP_TOP + ri * ROW_H
            is_sel = (i == sel)
            bg = (32, 32, 58) if is_sel else PANEL
            pygame.draw.rect(screen, bg,
                             (PAD, ry, TABLE_W, ROW_H - 2), border_radius=8)
            if is_sel:
                pygame.draw.rect(screen, ACCENT,
                                 (PAD, ry, TABLE_W, ROW_H - 2), width=1, border_radius=8)
            cy2 = ry + ROW_H // 2 - 8
            # ID
            _t(screen, f_sm, stat["participant_id"],
               ACCENT if is_sel else WHITE, PAD + 8, cy2)
            # Group pill
            gx, _ = COLS[1]
            gcol = GROUP_COLORS.get(stat["group_name"], DIM)
            _pill(screen, f_xs, stat["group_name"], (8,8,16), gcol,
                  PAD + gx + 6, ry + ROW_H // 2 - 11)
            # Other text cols
            for idx, (key, fmt) in enumerate([
                ("age", "{}"), ("sessions_done", "{:.0f}"),
                ("total_trials", "{:.0f}"), ("avg_score", "{:.0f}")
            ]):
                cx2, _ = COLS[idx + 2]
                val = stat[key]
                _t(screen, f_xs, fmt.format(val) if val else "—",
                   DIM, PAD + cx2 + 8, cy2)
            # Accuracy bar
            ax, aw = COLS[6]
            bx = PAD + ax + 8
            pct = stat["accuracy_pct"] / 100.0
            _bar(screen, bx, ry + ROW_H // 2 - 5, aw, 10, pct,
                 fg=GREEN if pct >= 0.7 else (ORANGE if pct >= 0.4 else RED_C))
            _t(screen, f_xs, f"{stat['accuracy_pct']:.0f}%", WHITE,
               bx + aw + 6, ry + ROW_H // 2 - 7)
        screen.set_clip(None)

        if not stats:
            _t(screen, f_sm, "No participants registered yet.", DIM, PAD + 20, CLIP_TOP + 20)

        # Scrollbar
        if len(stats) > VIS_ROWS:
            sb_h = CLIP_BOT - CLIP_TOP
            th   = max(30, int(sb_h * VIS_ROWS / len(stats)))
            ty2  = CLIP_TOP + int((sb_h - th) * scroll
                                  / max(1, len(stats) - VIS_ROWS))
            pygame.draw.rect(screen, (36, 36, 60),
                             (PAD + TABLE_W - 6, CLIP_TOP, 6, sb_h), border_radius=3)
            pygame.draw.rect(screen, BORDER,
                             (PAD + TABLE_W - 6, ty2, 6, th), border_radius=3)

        # Side panel — session breakdown
        ph = CLIP_BOT - TABLE_Y
        _panel(screen, SIDE_X, TABLE_Y, SIDE_W, ph, BORDER, r=12)
        if stats:
            pid = stats[sel]["participant_id"]
            _t(screen, f_sm, pid, ACCENT, SIDE_X + 14, TABLE_Y + 14)
            _t(screen, f_xs, "Session breakdown — click row for full trials",
               DIM, SIDE_X + 14, TABLE_Y + 36)
            pygame.draw.line(screen, BORDER,
                             (SIDE_X + 10, TABLE_Y + 56),
                             (SIDE_X + SIDE_W - 10, TABLE_Y + 56))
            ry2 = TABLE_Y + 64
            for s in sessions:
                if ry2 + 58 > TABLE_Y + ph - 8: break
                done  = bool(s["completed"])
                bc    = GREEN if done else BORDER
                label = f"S{s['session_number']} · {s['block_type'].replace('_',' ')}"
                _panel(screen, SIDE_X + 8, ry2, SIDE_W - 16, 52, bc, r=8)
                _t(screen, f_xs, label, WHITE if done else DIM, SIDE_X + 18, ry2 + 6)
                _t(screen, f_xs,
                   f"Trials: {int(s['trials'])}   Acc: {s['accuracy_pct']:.0f}%   Avg: {s['avg_score']:.0f}",
                   DIM, SIDE_X + 18, ry2 + 26)
                _bar(screen, SIDE_X + 18, ry2 + 44, SIDE_W - 36, 5,
                     s["accuracy_pct"] / 100.0,
                     GREEN if s["accuracy_pct"] >= 70 else ORANGE)
                ry2 += 60
            if not sessions:
                _t(screen, f_xs, "No sessions yet.", DIM, SIDE_X + 14, TABLE_Y + 74)
        else:
            _t(screen, f_xs, "Select a participant", DIM, SIDE_X + 14, TABLE_Y + 20)

        # Bottom bar
        pygame.draw.line(screen, BORDER, (0, H - 58), (W, H - 58))

        pygame.draw.rect(screen, PANEL2, back_r,    border_radius=8)
        pygame.draw.rect(screen, BORDER, back_r,    width=1, border_radius=8)
        _t(screen, f_xs, "< Back", DIM, back_r.x + 14, back_r.y + 10)

        _btn(screen, fonts, "Export All", exp_all_r, ORANGE,
             sub="Full keypresses CSV")
        _btn(screen, fonts, "Trial Summary", exp_sum_r, PURPLE,
             sub="One row per trial CSV")

        if msg:
            ms = f_xs.render(msg, True, msg_col)
            screen.blit(ms, (W - PAD - ms.get_width(), H - 44))

        _t(screen, f_xs,
           f"Auto-refreshes every 3s  |  {len(stats)} participant(s)  |  Click a row to drill in",
           DIM, 0, H - 40, center_w=W)

        pygame.display.flip()


# ──────────────────────────────────────────────────────────────
#  VIEW B — Trial drill-down for one participant
# ──────────────────────────────────────────────────────────────

def _view_b(screen, clock, fonts, participant_id):
    """
    Show every single trial for participant_id with full detail.
    ESC / Back → return to overview.
    """
    f_big, f_med, f_sm, f_xs = fonts

    trials   = get_participant_trials(participant_id)
    scroll   = 0
    msg      = ""
    msg_col  = GREEN

    HDR_Y    = 68
    HDR_H    = 30
    CLIP_TOP = HDR_Y + HDR_H
    CLIP_BOT = H - 62
    VIS_ROWS = (CLIP_BOT - CLIP_TOP) // ROW_H

    TW = W - PAD * 2
    # Columns: Session, Block, Trial#, Grid, Correct, Moves/Opt, Score, RT(ms), Move Time, Elapsed
    COLS = [
        (0,   44,  "Sn"),
        (44,  130, "Block"),
        (174,  40, "#"),
        (214,  72, "Grid"),
        (286,  62, "Result"),
        (348,  80, "Moves/Opt"),
        (428,  68, "Score"),
        (496, 100, "React.(ms)"),
        (596, 108, "Move Time"),
        (704, TW-704, "Elapsed(s)"),
    ]

    back_r   = pygame.Rect(PAD,       H - 50, 110, 34)
    exp_r    = pygame.Rect(PAD + 120, H - 50, 200, 34)

    pygame.display.set_caption(f"Grid-Sailing — {participant_id} Trials")

    while True:
        clock.tick(FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return
                if event.key == pygame.K_DOWN:
                    scroll = min(scroll + 1, max(0, len(trials) - VIS_ROWS))
                if event.key == pygame.K_UP:
                    scroll = max(scroll - 1, 0)
            if event.type == pygame.MOUSEBUTTONDOWN:
                if back_r.collidepoint(event.pos):
                    return
                if exp_r.collidepoint(event.pos):
                    path = export_participant(participant_id)
                    msg = f"Saved: {os.path.basename(path)}"
                    msg_col = GREEN
            if event.type == pygame.MOUSEWHEEL:
                scroll = max(0, min(scroll - event.y,
                                    max(0, len(trials) - VIS_ROWS)))

        # ── Draw ─────────────────────────────────────────────
        screen.fill(BG)
        _title_bar(screen, fonts,
                   f"{participant_id} — All Trials  ({len(trials)} total)",
                   "ESC to go back")

        # Stats strip
        if trials:
            n_corr  = sum(1 for t in trials if t["is_correct"])
            avg_rt  = sum(t["reaction_time_ms"] or 0 for t in trials) / len(trials)
            avg_sc  = sum(t["reward_score"] or 0 for t in trials) / len(trials)
            strip_items = [
                (f"{n_corr}/{len(trials)}", "Correct"),
                (f"{n_corr/len(trials)*100:.0f}%", "Accuracy"),
                (f"{avg_rt:.0f} ms", "Avg React."),
                (f"{avg_sc:.0f}", "Avg Score"),
            ]
            sw = (W - PAD * 2) // len(strip_items)
            for i, (val, lbl) in enumerate(strip_items):
                sx = PAD + i * sw
                _panel(screen, sx, 66, sw - 8, 54, BORDER, r=10)
                _t(screen, f_med, val, ACCENT, sx + 14, 74)
                _t(screen, f_xs,  lbl, DIM,    sx + 14, 100)

        # Table header
        pygame.draw.rect(screen, PANEL2, (PAD, HDR_Y + 62, TW, HDR_H), border_radius=6)
        for (cx2, cw, lbl) in COLS:
            _t(screen, f_xs, lbl, DIM, PAD + cx2 + 6, HDR_Y + 62 + 7)
        pygame.draw.line(screen, BORDER,
                         (PAD, HDR_Y + 62 + HDR_H), (PAD + TW, HDR_Y + 62 + HDR_H))

        CLIP_TOP2 = HDR_Y + 62 + HDR_H
        VIS2      = (CLIP_BOT - CLIP_TOP2) // ROW_H

        clip = pygame.Rect(PAD, CLIP_TOP2, TW, CLIP_BOT - CLIP_TOP2)
        screen.set_clip(clip)
        for i, tr in enumerate(trials):
            ri = i - scroll
            if ri < 0 or ri >= VIS2: continue
            ry = CLIP_TOP2 + ri * ROW_H

            correct = bool(tr["is_correct"])
            bg = (20, 36, 20) if correct else (36, 20, 20)
            pygame.draw.rect(screen, bg,     (PAD, ry, TW, ROW_H - 2), border_radius=7)
            pygame.draw.rect(screen, BORDER, (PAD, ry, TW, ROW_H - 2), width=1, border_radius=7)

            cy2 = ry + ROW_H // 2 - 8

            def cell(col_i, text, color=WHITE):
                cx2, _, _ = COLS[col_i]
                _t(screen, f_xs, str(text), color, PAD + cx2 + 6, cy2)

            cell(0, tr["session_number"], ACCENT)
            # Block type — shortened
            bt = tr["block_type"].replace("familiarization","fam").replace("_"," ")
            cell(1, f"B{tr['block_number']} {bt}", DIM)
            cell(2, tr["trial_number"], WHITE)
            # Grid type pill
            gx2, _, _ = COLS[3]
            gcol = ACCENT if tr["grid_type"] == "repeated" else ORANGE
            _pill(screen, f_xs, tr["grid_type"][:3].upper(), (8,8,16), gcol,
                  PAD + gx2 + 4, ry + ROW_H // 2 - 10)
            # Result
            cell(4, "CORRECT" if correct else "MISS",
                 GREEN if correct else RED_C)
            # Moves / optimal
            moves = tr["number_of_moves"] or 0
            opt   = tr["optimal_length"]  or 0
            cell(5, f"{moves} / {opt}",
                 GREEN if moves <= opt else (ORANGE if moves <= opt + 2 else RED_C))
            cell(6, f"{tr['reward_score'] or 0}", AMBER)
            # Reaction time
            rt = tr["reaction_time_ms"]
            cell(7, f"{rt:.0f}" if rt else "—",
                 WHITE if rt and rt < 3000 else ORANGE)
            # Movement time
            mt = tr["movement_time_ms"]
            mts = f"{mt/1000:.1f}s" if mt else ("—" if not tr["imagery_duration_ms"]
                  else f"{tr['imagery_duration_ms']/1000:.1f}s img")
            cell(8, mts, DIM)
            # Elapsed
            el = tr["elapsed_time_s"]
            cell(9, f"{el:.1f}s" if el else "—", DIM)

        screen.set_clip(None)

        if not trials:
            _t(screen, f_sm, "No trials recorded for this participant yet.",
               DIM, PAD + 20, CLIP_TOP2 + 20)

        # Scrollbar
        if len(trials) > VIS2:
            sb_h = CLIP_BOT - CLIP_TOP2
            th   = max(30, int(sb_h * VIS2 / len(trials)))
            ty2  = CLIP_TOP2 + int((sb_h - th) * scroll
                                   / max(1, len(trials) - VIS2))
            pygame.draw.rect(screen, (36,36,60),
                             (PAD + TW - 6, CLIP_TOP2, 6, sb_h), border_radius=3)
            pygame.draw.rect(screen, BORDER,
                             (PAD + TW - 6, ty2, 6, th), border_radius=3)

        # Bottom bar
        pygame.draw.line(screen, BORDER, (0, H - 58), (W, H - 58))
        pygame.draw.rect(screen, PANEL2, back_r, border_radius=8)
        pygame.draw.rect(screen, BORDER, back_r, width=1, border_radius=8)
        _t(screen, f_xs, "< Back", DIM, back_r.x + 14, back_r.y + 10)

        _btn(screen, fonts, f"Export {participant_id}", exp_r, ACCENT,
             sub="Full keypress CSV")

        if msg:
            ms = f_xs.render(msg, True, msg_col)
            screen.blit(ms, (W - PAD - ms.get_width(), H - 44))

        _t(screen, f_xs,
           "Green row = correct  |  Red row = missed goal  |  Scroll to browse all attempts",
           DIM, 0, H - 40, center_w=W)

        pygame.display.flip()


# ── Entry point ───────────────────────────────────────────────

def run_data_viewer(screen, clock, fonts):
    """
    Main entry: shows overview, then drills into participant trials on click.
    Returns when user ESCs all the way back.
    """
    drill_target = [None]

    def on_select(pid):
        drill_target[0] = pid

    while True:
        drill_target[0] = None
        _view_a(screen, clock, fonts, on_select)

        if drill_target[0]:
            _view_b(screen, clock, fonts, drill_target[0])
        else:
            return   # ESC from overview = go back to researcher home
