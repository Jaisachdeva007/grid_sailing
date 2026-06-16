# ============================================================
#  GRID-SAILING TASK — Data Viewer  (v4 — clean redesign)
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
BG      = (8,    8,   16)
SURFACE = (14,  14,   26)
PANEL   = (20,  20,   36)
PANEL2  = (28,  28,   46)
BORDER  = (48,  48,   76)
WHITE   = (245, 245, 255)
DIM     = (118, 118, 158)
DIM2    = (80,   80, 120)
ACCENT  = ( 88, 148, 255)
GREEN   = ( 52, 200, 100)
AMBER   = (220, 162,  28)
ORANGE  = (228, 138,  48)
RED_C   = (220,  60,  60)
PURPLE  = (160,  90, 220)

GROUP_COLORS = {
    "MI-High":   ( 88, 148, 255),  "MI-Low":    ( 60, 110, 210),
    "PP-High":   ( 52, 200, 100),  "PP-Low":    ( 38, 148,  80),
    "CTRL-High": (220, 162,  28),  "CTRL-Low":  (168, 118,  18),
}

W, H  = WINDOW_WIDTH, WINDOW_HEIGHT
PAD   = 40
ROW_H = 52


# ── Helpers ───────────────────────────────────────────────────

def _t(screen, font, text, col, x, y, cw=0):
    s = font.render(text, True, col)
    screen.blit(s, (x + cw // 2 - s.get_width() // 2, y) if cw else (x, y))
    return s

def _panel(screen, x, y, w, h, col=BORDER, r=10):
    pygame.draw.rect(screen, PANEL, (x, y, w, h), border_radius=r)
    pygame.draw.rect(screen, col,   (x, y, w, h), width=1, border_radius=r)

def _bar(screen, x, y, w, h, pct, fg):
    pygame.draw.rect(screen, (22, 22, 44), (x, y, w, h), border_radius=4)
    if pct > 0:
        pygame.draw.rect(screen, fg,
                         (x, y, max(4, int(w * min(pct, 1.0))), h), border_radius=4)

def _pill(screen, font, text, fg, bg, x, y):
    s  = font.render(text, True, fg)
    pw, ph = s.get_width() + 16, s.get_height() + 8
    pygame.draw.rect(screen, bg, (x, y, pw, ph), border_radius=ph // 2)
    screen.blit(s, (x + 8, y + 4))
    return pw

def _back_btn(screen, fonts, rect):
    _, _, f_sm, f_xs = fonts
    mouse = pygame.mouse.get_pos()
    hover = rect.collidepoint(mouse)
    col   = PANEL2 if not hover else (38, 38, 62)
    pygame.draw.rect(screen, col,   rect, border_radius=8)
    pygame.draw.rect(screen, BORDER, rect, width=1, border_radius=8)
    _t(screen, f_xs, "< Back", DIM, rect.x + 14, rect.y + 10)

def _action_btn(screen, fonts, label, sub, rect, color):
    _, _, f_sm, f_xs = fonts
    mouse = pygame.mouse.get_pos()
    hover = rect.collidepoint(mouse)
    col   = tuple(min(255, c + 24) for c in color) if hover else color
    pygame.draw.rect(screen, (4, 4, 10),
                     (rect.x + 2, rect.y + 3, rect.w, rect.h), border_radius=10)
    pygame.draw.rect(screen, col, rect, border_radius=10)
    ls = f_sm.render(label, True, (8, 8, 16))
    screen.blit(ls, (rect.x + rect.w // 2 - ls.get_width() // 2,
                     rect.y + rect.h // 2 - ls.get_height() // 2 - (9 if sub else 0)))
    if sub:
        ss = f_xs.render(sub, True, (24, 24, 40))
        screen.blit(ss, (rect.x + rect.w // 2 - ss.get_width() // 2,
                         rect.y + rect.h // 2 + 6))

def _title_bar(screen, fonts, title, hint=""):
    _, f_med, _, f_xs = fonts
    pygame.draw.rect(screen, SURFACE, (0, 0, W, 60))
    pygame.draw.line(screen, BORDER, (0, 60), (W, 60))
    _t(screen, f_med, title, WHITE, PAD, 19)
    if hint:
        hs = f_xs.render(hint, True, DIM2)
        screen.blit(hs, (W - PAD - hs.get_width(), 23))

def _stat_card(screen, fonts, x, y, w, h, label, value, sub, col):
    _, f_med, _, f_xs = fonts
    pygame.draw.rect(screen, (4, 4, 10),  (x + 3, y + 4, w, h), border_radius=14)
    _panel(screen, x, y, w, h, col, r=14)
    pygame.draw.rect(screen, col, (x + 1, y + 1, w - 2, 5), border_radius=14)
    _t(screen, f_xs,  label, DIM,  x + 16, y + 16)
    _t(screen, f_med, value, col,  x + 16, y + 36)
    _t(screen, f_xs,  sub,   DIM2, x + 16, y + h - 20)


# ──────────────────────────────────────────────────────────────
#  VIEW A — Participant list
# ──────────────────────────────────────────────────────────────

def _view_a(screen, clock, fonts, on_select):
    f_big, f_med, f_sm, f_xs = fonts

    CARD_H   = 84
    CARDS_Y  = 68
    TABLE_Y  = CARDS_Y + CARD_H + 16
    SIDE_W   = 268
    TABLE_W  = W - PAD * 2 - SIDE_W - 16
    SIDE_X   = PAD + TABLE_W + 16
    HDR_H    = 32
    CLIP_TOP = TABLE_Y + HDR_H
    CLIP_BOT = H - 64
    VIS      = (CLIP_BOT - CLIP_TOP) // ROW_H

    # Columns: (x, w, label)
    COLS = [
        (0,   92,  "Participant"),
        (92,  120, "Group"),
        (212,  48, "Age"),
        (260,  80, "Sessions"),
        (340,  72, "Trials"),
        (412,  88, "Avg Score"),
        (500, TABLE_W - 500 - 48, "Accuracy"),
    ]

    stats     = []
    sessions  = []
    sel       = 0
    scroll    = 0
    refresh_t = 0
    msg       = ""; msg_col = GREEN

    back_r    = pygame.Rect(PAD,       H - 52, 100, 36)
    exp_all_r = pygame.Rect(PAD + 110, H - 52, 180, 36)
    exp_sum_r = pygame.Rect(PAD + 300, H - 52, 200, 36)

    pygame.display.set_caption("Grid-Sailing — Data Overview")

    while True:
        clock.tick(FPS)
        now = pygame.time.get_ticks()

        if now - refresh_t > 3000:
            stats    = get_participant_stats()
            sessions = (get_session_breakdown(stats[sel]["participant_id"])
                        if stats else [])
            refresh_t = now

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE: return
                if ev.key == pygame.K_DOWN and stats:
                    sel = min(sel + 1, len(stats) - 1)
                    if sel >= scroll + VIS: scroll += 1
                    sessions = get_session_breakdown(stats[sel]["participant_id"])
                if ev.key == pygame.K_UP and stats:
                    sel = max(sel - 1, 0)
                    if sel < scroll: scroll -= 1
                    sessions = get_session_breakdown(stats[sel]["participant_id"])
            if ev.type == pygame.MOUSEBUTTONDOWN:
                mx, my = ev.pos
                for i in range(len(stats)):
                    ri = i - scroll
                    if 0 <= ri < VIS:
                        ry = CLIP_TOP + ri * ROW_H
                        if PAD <= mx <= PAD + TABLE_W and ry <= my <= ry + ROW_H - 2:
                            sel = i
                            sessions = get_session_breakdown(stats[i]["participant_id"])
                            on_select(stats[i]["participant_id"])
                            return
                if back_r.collidepoint(ev.pos):    return
                if exp_all_r.collidepoint(ev.pos):
                    path = export_all();   msg = f"Saved  {os.path.basename(path)}"; msg_col = GREEN
                if exp_sum_r.collidepoint(ev.pos):
                    path = export_summary(); msg = f"Saved  {os.path.basename(path)}"; msg_col = GREEN
            if ev.type == pygame.MOUSEWHEEL:
                scroll = max(0, min(scroll - ev.y, max(0, len(stats) - VIS)))

        # ── Draw ─────────────────────────────────────────────
        screen.fill(BG)
        _title_bar(screen, fonts, "Data Overview",
                   "Click a row to drill into every trial   |   ESC to go back")

        # Summary cards
        n_parts  = len(stats)
        n_trials = sum(int(s["total_trials"]) for s in stats)
        avg_acc  = (sum(s["accuracy_pct"] for s in stats) / n_parts) if n_parts else 0
        avg_rt   = (sum(s["avg_rt_ms"]    for s in stats) / n_parts) if n_parts else 0
        card_w   = (W - PAD * 2 - 36) // 4
        cx = PAD
        for label, val, sub, col in [
            ("Participants",    str(n_parts),              "registered",             ACCENT),
            ("Total Trials",    str(n_trials),             "across all participants", GREEN),
            ("Avg Accuracy",    f"{avg_acc:.0f}%",         "correct trials",          AMBER),
            ("Avg React. Time", f"{avg_rt/1000:.2f}s" if avg_rt else "—",
                                                           "planning to first key",   PURPLE),
        ]:
            _stat_card(screen, fonts, cx, CARDS_Y, card_w, CARD_H, label, val, sub, col)
            cx += card_w + 12

        # Table header
        pygame.draw.rect(screen, PANEL2, (PAD, TABLE_Y, TABLE_W, HDR_H), border_radius=8)
        for cx2, cw, lbl in COLS:
            _t(screen, f_xs, lbl, DIM, PAD + cx2 + 10, TABLE_Y + 9)
        pygame.draw.line(screen, BORDER,
                         (PAD, TABLE_Y + HDR_H), (PAD + TABLE_W, TABLE_Y + HDR_H))

        # Rows
        screen.set_clip(pygame.Rect(PAD, CLIP_TOP, TABLE_W + 52, CLIP_BOT - CLIP_TOP))
        for i, stat in enumerate(stats):
            ri = i - scroll
            if ri < 0 or ri >= VIS: continue
            ry  = CLIP_TOP + ri * ROW_H
            sel_row = (i == sel)
            bg  = PANEL2 if sel_row else PANEL
            pygame.draw.rect(screen, bg, (PAD, ry, TABLE_W, ROW_H - 4), border_radius=8)
            if sel_row:
                pygame.draw.rect(screen, ACCENT,
                                 (PAD, ry, TABLE_W, ROW_H - 4), width=1, border_radius=8)
                pygame.draw.rect(screen, ACCENT,
                                 (PAD, ry, 3, ROW_H - 4), border_radius=4)
            cy2 = ry + ROW_H // 2 - 9
            # ID
            _t(screen, f_sm, stat["participant_id"],
               ACCENT if sel_row else WHITE, PAD + 10, cy2)
            # Group pill
            gcol = GROUP_COLORS.get(stat["group_name"], DIM)
            _pill(screen, f_xs, stat["group_name"], (8,8,16), gcol,
                  PAD + 92 + 6, ry + ROW_H // 2 - 12)
            # Text cells
            for idx, (key, fmt) in enumerate([
                ("age","{}"), ("sessions_done","{:.0f}"),
                ("total_trials","{:.0f}"), ("avg_score","{:.0f}")
            ]):
                cx2, _, _ = COLS[idx + 2]
                v = stat[key]
                _t(screen, f_xs, fmt.format(v) if v else "—",
                   DIM, PAD + cx2 + 10, cy2)
            # Accuracy bar + %
            ax, aw, _ = COLS[6]
            bx  = PAD + ax + 10
            pct = stat["accuracy_pct"] / 100.0
            _bar(screen, bx, ry + ROW_H // 2 - 6, aw, 12, pct,
                 GREEN if pct >= 0.7 else (ORANGE if pct >= 0.4 else RED_C))
            _t(screen, f_xs, f"{stat['accuracy_pct']:.0f}%", WHITE,
               bx + aw + 8, ry + ROW_H // 2 - 8)
        screen.set_clip(None)

        if not stats:
            _t(screen, f_sm, "No participants registered yet.", DIM, PAD + 20, CLIP_TOP + 24)

        # Scrollbar
        if len(stats) > VIS:
            sb_h = CLIP_BOT - CLIP_TOP
            th   = max(32, int(sb_h * VIS / len(stats)))
            ty2  = CLIP_TOP + int((sb_h - th) * scroll / max(1, len(stats) - VIS))
            pygame.draw.rect(screen, (32,32,58),
                             (PAD + TABLE_W - 6, CLIP_TOP, 6, sb_h), border_radius=3)
            pygame.draw.rect(screen, BORDER,
                             (PAD + TABLE_W - 6, ty2, 6, th), border_radius=3)

        # Side panel
        ph = CLIP_BOT - TABLE_Y
        _panel(screen, SIDE_X, TABLE_Y, SIDE_W, ph, BORDER, r=12)
        if stats:
            pid = stats[sel]["participant_id"]
            _t(screen, f_sm, pid, ACCENT, SIDE_X + 16, TABLE_Y + 16)
            _t(screen, f_xs, "Sessions", DIM, SIDE_X + 16, TABLE_Y + 40)
            pygame.draw.line(screen, BORDER,
                             (SIDE_X + 12, TABLE_Y + 58),
                             (SIDE_X + SIDE_W - 12, TABLE_Y + 58))
            ry2 = TABLE_Y + 68
            for s in sessions:
                if ry2 + 64 > TABLE_Y + ph - 8: break
                done  = bool(s["completed"])
                bc    = GREEN if done else BORDER
                label = f"S{s['session_number']}  {s['block_type'].replace('_',' ')}"
                _panel(screen, SIDE_X + 10, ry2, SIDE_W - 20, 56, bc, r=9)
                _t(screen, f_sm, label,
                   WHITE if done else DIM, SIDE_X + 20, ry2 + 8)
                _t(screen, f_xs,
                   f"Trials: {int(s['trials'])}   Acc: {s['accuracy_pct']:.0f}%",
                   DIM, SIDE_X + 20, ry2 + 32)
                _bar(screen, SIDE_X + 20, ry2 + 50,
                     SIDE_W - 40, 4, s["accuracy_pct"] / 100.0,
                     GREEN if s["accuracy_pct"] >= 70 else ORANGE)
                ry2 += 64
            if not sessions:
                _t(screen, f_xs, "No sessions yet.", DIM, SIDE_X + 16, TABLE_Y + 78)
        else:
            _t(screen, f_xs, "Select a participant", DIM, SIDE_X + 16, TABLE_Y + 24)

        # Bottom bar
        pygame.draw.line(screen, BORDER, (0, H - 60), (W, H - 60))
        _back_btn(screen, fonts, back_r)
        _action_btn(screen, fonts, "Export All", "all participants CSV",  exp_all_r, ORANGE)
        _action_btn(screen, fonts, "Trial Summary", "one row per trial",  exp_sum_r, PURPLE)

        if msg:
            ms = f_xs.render(msg, True, msg_col)
            screen.blit(ms, (W - PAD - ms.get_width(), H - 40))

        _t(screen, f_xs,
           f"Auto-refreshes every 3s  ·  {n_parts} participant(s)  ·  {n_trials} trial(s)",
           DIM2, 0, H - 40, cw=W)

        pygame.display.flip()


# ──────────────────────────────────────────────────────────────
#  VIEW B — Per-participant trial breakdown
# ──────────────────────────────────────────────────────────────

def _view_b(screen, clock, fonts, pid):
    f_big, f_med, f_sm, f_xs = fonts

    trials   = get_participant_trials(pid)
    scroll   = 0
    msg      = ""; msg_col = GREEN

    STATS_H  = 72
    STATS_Y  = 68
    HDR_Y    = STATS_Y + STATS_H + 12
    HDR_H    = 32
    CLIP_TOP = HDR_Y + HDR_H
    CLIP_BOT = H - 64
    TW       = W - PAD * 2
    VIS      = (CLIP_BOT - CLIP_TOP) // ROW_H

    # Columns: (x, w, label)  — wider so nothing gets cut
    COLS = [
        (0,   46, "Sn"),
        (46, 138, "Block"),
        (184,  44, "#"),
        (228,  76, "Grid"),
        (304,  96, "Result"),
        (400, 104, "Moves / Opt"),
        (504,  76, "Score"),
        (580, 110, "React (ms)"),
        (690, TW - 690, "Duration"),
    ]

    back_r  = pygame.Rect(PAD,       H - 52, 100, 36)
    exp_r   = pygame.Rect(PAD + 110, H - 52, 220, 36)

    pygame.display.set_caption(f"Grid-Sailing — {pid}")

    while True:
        clock.tick(FPS)

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE: return
                if ev.key == pygame.K_DOWN:
                    scroll = min(scroll + 1, max(0, len(trials) - VIS))
                if ev.key == pygame.K_UP:
                    scroll = max(scroll - 1, 0)
            if ev.type == pygame.MOUSEBUTTONDOWN:
                if back_r.collidepoint(ev.pos): return
                if exp_r.collidepoint(ev.pos):
                    path = export_participant(pid)
                    msg = f"Saved  {os.path.basename(path)}"; msg_col = GREEN
            if ev.type == pygame.MOUSEWHEEL:
                scroll = max(0, min(scroll - ev.y, max(0, len(trials) - VIS)))

        # ── Draw ─────────────────────────────────────────────
        screen.fill(BG)
        _title_bar(screen, fonts,
                   f"{pid}  —  All Trials  ({len(trials)} total)",
                   "ESC to go back")

        # Stat strip
        if trials:
            n_corr = sum(1 for t in trials if t["is_correct"])
            rts    = [t["reaction_time_ms"] for t in trials if t["reaction_time_ms"]]
            avg_rt = sum(rts) / len(rts) if rts else 0
            avg_sc = sum(t["reward_score"] or 0 for t in trials) / len(trials)
            sw     = (TW - 36) // 4
            for i, (val, lbl, col) in enumerate([
                (f"{n_corr} / {len(trials)}", "Correct Trials", GREEN),
                (f"{n_corr/len(trials)*100:.0f}%",  "Accuracy",      AMBER),
                (f"{avg_rt:.0f} ms",   "Avg Reaction",  ACCENT),
                (f"{avg_sc:.0f}",      "Avg Score",     PURPLE),
            ]):
                sx = PAD + i * (sw + 12)
                _stat_card(screen, fonts, sx, STATS_Y, sw, STATS_H,
                           lbl, val, "", col)

        # Table header
        pygame.draw.rect(screen, PANEL2, (PAD, HDR_Y, TW, HDR_H), border_radius=8)
        for cx2, cw, lbl in COLS:
            _t(screen, f_xs, lbl, DIM, PAD + cx2 + 10, HDR_Y + 9)
        pygame.draw.line(screen, BORDER,
                         (PAD, HDR_Y + HDR_H), (PAD + TW, HDR_Y + HDR_H))

        # Rows
        screen.set_clip(pygame.Rect(PAD, CLIP_TOP, TW, CLIP_BOT - CLIP_TOP))
        for i, tr in enumerate(trials):
            ri = i - scroll
            if ri < 0 or ri >= VIS: continue
            ry = CLIP_TOP + ri * ROW_H

            correct = bool(tr["is_correct"])

            # Clean neutral row — no harsh color fill
            pygame.draw.rect(screen, PANEL,
                             (PAD, ry, TW, ROW_H - 4), border_radius=8)
            pygame.draw.rect(screen, BORDER,
                             (PAD, ry, TW, ROW_H - 4), width=1, border_radius=8)
            # Left accent stripe
            stripe_col = GREEN if correct else RED_C
            pygame.draw.rect(screen, stripe_col,
                             (PAD, ry, 3, ROW_H - 4), border_radius=3)

            cy2 = ry + ROW_H // 2 - 9

            def cell(col_i, text, color=WHITE):
                cx2, cw2, _ = COLS[col_i]
                _t(screen, f_xs, str(text), color, PAD + cx2 + 10, cy2)

            cell(0, tr["session_number"], DIM)

            bt = (tr["block_type"]
                  .replace("familiarization", "Familiar.")
                  .replace("pre_test", "Pre-Test")
                  .replace("post_test", "Post-Test")
                  .replace("practice", "Practice")
                  .replace("_", " "))
            cell(1, f"B{tr['block_number']}  {bt}", DIM)
            cell(2, tr["trial_number"], WHITE)

            # Grid pill
            gx, _, _ = COLS[3]
            is_rep = tr["grid_type"] == "repeated"
            _pill(screen, f_xs,
                  "REP" if is_rep else "RAN",
                  (8, 8, 16),
                  ACCENT if is_rep else ORANGE,
                  PAD + gx + 6, ry + ROW_H // 2 - 12)

            cell(4, "Correct" if correct else "Missed",
                 GREEN if correct else RED_C)

            moves = tr["number_of_moves"] or 0
            opt   = tr["optimal_length"]  or 0
            extra = moves - opt
            moves_col = GREEN if extra <= 0 else (ORANGE if extra <= 2 else RED_C)
            cell(5, f"{moves}  /  {opt}", moves_col)

            cell(6, str(tr["reward_score"] or 0), AMBER)

            rt = tr["reaction_time_ms"]
            cell(7, f"{rt:.0f} ms" if rt else "—",
                 WHITE if rt and rt < 5000 else DIM)

            # Duration — movement time or imagery
            mt  = tr["movement_time_ms"]
            idt = tr["imagery_duration_ms"]
            if mt:
                dur_str = f"{mt/1000:.1f} s"
            elif idt:
                dur_str = f"{idt/1000:.1f} s  (img)"
            else:
                et = tr["elapsed_time_s"]
                dur_str = f"{et:.1f} s" if et else "—"
            cell(8, dur_str, DIM)

        screen.set_clip(None)

        if not trials:
            _t(screen, f_sm, "No trials recorded for this participant yet.",
               DIM, PAD + 20, CLIP_TOP + 24)

        # Scrollbar
        if len(trials) > VIS:
            sb_h = CLIP_BOT - CLIP_TOP
            th   = max(32, int(sb_h * VIS / len(trials)))
            ty2  = CLIP_TOP + int((sb_h - th) * scroll / max(1, len(trials) - VIS))
            pygame.draw.rect(screen, (32,32,58),
                             (PAD + TW - 6, CLIP_TOP, 6, sb_h), border_radius=3)
            pygame.draw.rect(screen, BORDER,
                             (PAD + TW - 6, ty2, 6, th), border_radius=3)

        # Bottom bar  — two rows: buttons row + hint row
        pygame.draw.line(screen, BORDER, (0, H - 72), (W, H - 72))
        _back_btn(screen, fonts, back_r)
        _action_btn(screen, fonts, f"Export {pid}", "full keypress CSV", exp_r, ACCENT)

        if msg:
            ms = f_xs.render(msg, True, msg_col)
            screen.blit(ms, (W - PAD - ms.get_width(), H - 56))

        _t(screen, f_xs,
           "Green stripe = correct   ·   Red stripe = missed   ·   Scroll or arrow keys to browse",
           DIM2, 0, H - 18, cw=W)

        pygame.display.flip()


# ── Entry point ───────────────────────────────────────────────

def run_data_viewer(screen, clock, fonts):
    drill = [None]
    def on_select(pid): drill[0] = pid

    while True:
        drill[0] = None
        _view_a(screen, clock, fonts, on_select)
        if drill[0]:
            _view_b(screen, clock, fonts, drill[0])
        else:
            return
