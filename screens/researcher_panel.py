# ============================================================
#  GRID-SAILING TASK — Researcher Access Panel
#
#  You don't need to touch this file.
#
#  This is the mid-session panel you use while the study is running.
#  Hit the "Researcher" button in the bottom bar, enter the
#  admin password, and you get a live view of every trial in the
#  current block — what's done, what's pending, what was skipped —
#  plus the ability to jump straight to any upcoming pending trial.
#
#  Jumping forward abandons the current in-progress trial (never saved).
#  DONE trials are read-only: click them to see the cursor path + stats.
#  SKIPPED trials show with a warning at the bottom — note them and
#  handle them manually after the block if needed.
# ============================================================

import pygame
import sys
import math
import time

from config import FPS, ADMIN_PASSWORD, GRID_SIZE
from core.grid import apply_key

# Palette — matches trial.py
BG      = (8,    8,   16)
PANEL   = (20,  20,   36)
BORDER  = (48,  48,   76)
WHITE   = (245, 245, 255)
DIM     = (118, 118, 158)
DIM2    = (72,   72, 112)
ACCENT  = (88,  148, 255)
CORRECT = (0,   168, 175)
WRONG   = (210,  95,  20)
AMBER   = (220, 162,  28)
SKIP_C  = (180,  90,  20)

ROW_H      = 52      # each trial row height
PAD        = 20
HDR_H      = 116     # panel header height
FTR_H      = 88      # panel footer height
PANEL_FRAC = 0.52    # panel takes this share of screen width


# ── Shared helpers ─────────────────────────────────────────────

def _t(screen, font, text, col, x, y):
    s = font.render(text, True, col)
    screen.blit(s, (x, y))
    return s.get_width()


def _tc(screen, font, text, col, cx, y):
    s = font.render(text, True, col)
    screen.blit(s, (int(cx - s.get_width() // 2), y))


def _build_path(start, seq):
    """Reconstruct list of (row, col) from a start position + key sequence."""
    pos  = tuple(start)
    path = [pos]
    for k in seq:
        nxt  = apply_key(pos[0], pos[1], k)
        pos  = nxt if nxt else pos
        path.append(pos)
    return path


def _draw_mini_grid(screen, start, goal, path, x, y, cell=50):
    """
    Draw a static 5×5 mini grid with the cursor path highlighted.
    (x, y) is the top-left corner of the grid.
    """
    n        = GRID_SIZE
    path_set = {tuple(p) for p in path}
    start_t  = tuple(start)
    goal_t   = tuple(goal)

    CELL_DARK  = (22, 22, 44)
    CELL_TRAIL = (40, 80, 160)
    CELL_START = (20, 80, 180)
    CELL_GOAL  = (180, 130, 18)
    GRID_BDR   = (42,  42,  70)

    for r in range(n):
        for c in range(n):
            px = x + c * cell + 2
            py = y + r * cell + 2
            sz = cell - 4
            rect = pygame.Rect(px, py, sz, sz)
            br   = max(3, sz // 10)

            if   (r, c) == goal_t:                             bg = CELL_GOAL
            elif (r, c) in path_set and (r, c) != start_t:    bg = CELL_TRAIL
            elif (r, c) == start_t:                            bg = CELL_START
            else:                                               bg = CELL_DARK

            pygame.draw.rect(screen, bg,       rect, border_radius=br)
            pygame.draw.rect(screen, GRID_BDR, rect, width=1, border_radius=br)

    return n * cell   # total width


# ── Password prompt ────────────────────────────────────────────

def _password_prompt(screen, clock, fonts, bg_snap):
    """
    Center overlay on top of bg_snap asking for the admin password.
    Returns True if correct, False if cancelled (ESC).
    """
    f_big, f_med, f_sm, f_xs = fonts
    W, H = screen.get_width(), screen.get_height()
    cx   = W // 2

    pw       = ""
    wrong    = False
    shake_t0 = 0.0
    cw, ch   = 480, 326
    cy2      = H // 2 - ch // 2
    cx2      = cx - cw // 2

    # Fixed click target (unshifted; shake is visual only)
    btn_r = pygame.Rect(cx - 100, cy2 + 242, 200, 52)
    fx    = cx2 + PAD
    fy    = cy2 + 112
    fw    = cw - PAD * 2
    fh    = 52

    while True:
        clock.tick(FPS)
        now = time.time()

        events = pygame.event.get()
        for ev in events:
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    return False
                elif ev.key == pygame.K_BACKSPACE:
                    pw = pw[:-1]; wrong = False
                elif ev.key == pygame.K_RETURN:
                    if pw == ADMIN_PASSWORD:
                        return True
                    pw = ""; wrong = True; shake_t0 = now
                elif ev.unicode:
                    if len(pw) < 64:
                        pw += ev.unicode
            if ev.type == pygame.MOUSEBUTTONDOWN:
                if btn_r.collidepoint(ev.pos):
                    if pw == ADMIN_PASSWORD:
                        return True
                    pw = ""; wrong = True; shake_t0 = now

        sx = 0
        if shake_t0 and (now - shake_t0) < 0.5:
            t  = (now - shake_t0) / 0.5
            sx = int(10 * math.sin(t * 22) * (1 - t))

        screen.blit(bg_snap, (0, 0))
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 175))
        screen.blit(dim, (0, 0))

        x2 = cx2 + sx
        pygame.draw.rect(screen, (4,  4, 10), (x2+4, cy2+6, cw, ch), border_radius=18)
        pygame.draw.rect(screen, PANEL,        (x2,   cy2,   cw, ch), border_radius=18)
        pygame.draw.rect(screen, BORDER,       (x2,   cy2,   cw, ch), width=1, border_radius=18)
        pygame.draw.rect(screen, ACCENT,       (x2+1, cy2+1, cw-2, 5), border_radius=18)

        ts = f_med.render("Researcher Access", True, WHITE)
        screen.blit(ts, (cx - ts.get_width()//2 + sx, cy2 + 28))
        sub = f_xs.render("Enter the admin password to continue", True, DIM)
        screen.blit(sub, (cx - sub.get_width()//2 + sx, cy2 + 72))

        fc = WRONG if wrong else ACCENT
        pygame.draw.rect(screen, (28, 28, 52), (fx + sx, fy, fw, fh), border_radius=10)
        pygame.draw.rect(screen, fc,            (fx + sx, fy, fw, fh), width=2, border_radius=10)
        disp = ("●" * len(pw)) if pw else "Password"
        dc   = WHITE if pw else DIM2
        ds   = f_sm.render(disp, True, dc)
        screen.blit(ds, (fx + sx + 16, fy + fh//2 - ds.get_height()//2))

        if wrong and shake_t0 and (now - shake_t0) < 2.0:
            ws = f_xs.render("Incorrect — try again", True, WRONG)
            screen.blit(ws, (cx - ws.get_width()//2 + sx, fy + fh + 10))

        # Enter button
        bx = cx - 100 + sx
        hv = pygame.Rect(bx, cy2+242, 200, 52).collidepoint(pygame.mouse.get_pos())
        bc = tuple(min(255, c+28) for c in ACCENT) if hv else ACCENT
        pygame.draw.rect(screen, (4, 4, 12), (bx+2, cy2+245, 200, 52), border_radius=10)
        pygame.draw.rect(screen, bc,         (bx,   cy2+242, 200, 52), border_radius=10)
        bl = f_sm.render("Enter", True, (8, 8, 16))
        screen.blit(bl, (bx + 100 - bl.get_width()//2, cy2+242+26 - bl.get_height()//2))

        es = f_xs.render("ESC to cancel", True, DIM2)
        screen.blit(es, (cx - es.get_width()//2 + sx, cy2 + 306))

        pygame.display.flip()


# ── Jump confirmation ──────────────────────────────────────────

def _jump_confirm(screen, clock, fonts, current_num, target_num, bg_snap):
    """
    Compact overlay confirming a forward jump.
    Returns True if confirmed, False if cancelled.
    """
    f_big, f_med, f_sm, f_xs = fonts
    W, H = screen.get_width(), screen.get_height()
    cx   = W // 2

    cw, ch = 500, 248
    cy2    = H // 2 - ch // 2
    cx2    = cx - cw // 2

    n_skip = max(0, target_num - current_num - 1)

    confirm_r = pygame.Rect(cx2 + PAD,              cy2 + ch - 70, (cw - PAD*3) // 2, 50)
    cancel_r  = pygame.Rect(confirm_r.right + PAD,  cy2 + ch - 70, (cw - PAD*3) // 2, 50)

    while True:
        clock.tick(FPS)
        events = pygame.event.get()
        for ev in events:
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:     return False
                if ev.key == pygame.K_RETURN:     return True
            if ev.type == pygame.MOUSEBUTTONDOWN:
                if confirm_r.collidepoint(ev.pos): return True
                if cancel_r.collidepoint(ev.pos):  return False

        screen.blit(bg_snap, (0, 0))
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 170))
        screen.blit(dim, (0, 0))

        pygame.draw.rect(screen, (4,4,10), (cx2+4, cy2+6, cw, ch), border_radius=16)
        pygame.draw.rect(screen, PANEL,     (cx2,   cy2,   cw, ch), border_radius=16)
        pygame.draw.rect(screen, BORDER,    (cx2,   cy2,   cw, ch), width=1, border_radius=16)
        pygame.draw.rect(screen, AMBER,     (cx2+1, cy2+1, cw-2, 5), border_radius=16)

        _tc(screen, f_med, f"Jump to Trial {target_num}?", WHITE, cx, cy2 + 24)

        if n_skip > 0:
            first_skip  = current_num + 1
            last_skip   = target_num - 1
            skip_range  = (f"Trial {first_skip}" if n_skip == 1
                           else f"Trials {first_skip}–{last_skip}")
            msg = f"Current trial abandoned.  {skip_range} will be skipped."
        else:
            msg = "Current trial will be abandoned — no trials skipped."

        ms = f_xs.render(msg, True, AMBER)
        screen.blit(ms, (cx - ms.get_width()//2, cy2 + 78))

        ws = f_xs.render("This cannot be undone.", True, DIM)
        screen.blit(ws, (cx - ws.get_width()//2, cy2 + 104))

        # Buttons
        mouse = pygame.mouse.get_pos()
        for rect, label, col in [(confirm_r, "Confirm Jump", AMBER),
                                  (cancel_r,  "Cancel",       BORDER)]:
            hv = rect.collidepoint(mouse)
            bg = tuple(min(255, c+28) for c in col) if hv else tuple(c//3 for c in col)
            tc = (8, 8, 16) if hv else WHITE
            pygame.draw.rect(screen, (4,4,12), (rect.x+2, rect.y+3, rect.w, rect.h), border_radius=10)
            pygame.draw.rect(screen, bg, rect, border_radius=10)
            pygame.draw.rect(screen, col, rect, width=1, border_radius=10)
            ls = f_sm.render(label, True, tc)
            screen.blit(ls, (rect.centerx - ls.get_width()//2, rect.centery - ls.get_height()//2))

        pygame.display.flip()


# ── Stats modal ────────────────────────────────────────────────

def _stats_modal(screen, clock, fonts, trial_info, bg_snap):
    """
    Full overlay showing cursor path + stats for a completed trial.
    Closes on any key or click.
    """
    f_big, f_med, f_sm, f_xs = fonts
    W, H = screen.get_width(), screen.get_height()
    cx   = W // 2

    r = trial_info.get("result") or {}

    # Graceful fallback if trial has no in-session data
    if not r:
        cw, ch = 480, 200
        cy2 = H//2 - ch//2; cx2 = cx - cw//2
        while True:
            clock.tick(FPS)
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT: pygame.quit(); sys.exit()
                if ev.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN): return
            screen.blit(bg_snap, (0, 0))
            dim = pygame.Surface((W, H), pygame.SRCALPHA); dim.fill((0,0,0,175))
            screen.blit(dim, (0, 0))
            pygame.draw.rect(screen, PANEL, (cx2, cy2, cw, ch), border_radius=16)
            pygame.draw.rect(screen, BORDER, (cx2, cy2, cw, ch), width=1, border_radius=16)
            ms = f_sm.render("Completed before this panel session — no data.", True, DIM)
            screen.blit(ms, (cx - ms.get_width()//2, cy2 + 60))
            hs = f_xs.render("Click anywhere to close", True, DIM2)
            screen.blit(hs, (cx - hs.get_width()//2, cy2 + ch - 36))
            pygame.display.flip()
        return

    start = r.get("start", (0, 0))
    goal  = r.get("goal",  (4, 4))
    seq   = r.get("planned_sequence", [])
    opt   = r.get("optimal_sequence", [])
    path  = _build_path(start, seq)

    CELL    = 48
    GRID_PX = GRID_SIZE * CELL   # 240

    cw = min(W - 80, max(720, GRID_PX + 400))
    ch = min(H - 80, 500)
    cy2 = H//2 - ch//2
    cx2 = cx - cw//2

    res_col = CORRECT if r.get("is_correct") else WRONG

    while True:
        clock.tick(FPS)
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if ev.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                return

        screen.blit(bg_snap, (0, 0))
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 180))
        screen.blit(dim, (0, 0))

        pygame.draw.rect(screen, (4,4,10), (cx2+4, cy2+6, cw, ch), border_radius=16)
        pygame.draw.rect(screen, PANEL,     (cx2,   cy2,   cw, ch), border_radius=16)
        pygame.draw.rect(screen, BORDER,    (cx2,   cy2,   cw, ch), width=1, border_radius=16)
        pygame.draw.rect(screen, res_col,   (cx2+1, cy2+1, cw-2, 5), border_radius=16)

        # Header
        tn = trial_info["trial_number"]
        gt = trial_info["grid_type"].title()
        ts = f_med.render(f"Trial {tn}  ·  {gt}", True, WHITE)
        screen.blit(ts, (cx2 + PAD, cy2 + 20))

        res_lbl = "CORRECT" if r.get("is_correct") else "MISSED"
        rs  = f_med.render(res_lbl, True, res_col)
        screen.blit(rs, (cx2 + cw - PAD - rs.get_width(), cy2 + 20))

        pygame.draw.line(screen, BORDER, (cx2+PAD, cy2+62), (cx2+cw-PAD, cy2+62))

        # Mini grid (left column)
        grid_x = cx2 + PAD
        grid_y = cy2 + 76
        _draw_mini_grid(screen, start, goal, path, grid_x, grid_y, cell=CELL)

        # Start / Goal labels below grid
        sl = f_xs.render(f"Start {start}  →  Goal {goal}", True, DIM)
        screen.blit(sl, (grid_x, grid_y + GRID_PX + 8))

        # Stats (right column)
        sx = grid_x + GRID_PX + PAD * 2
        sy = cy2 + 80
        lh = f_sm.get_height() + 6

        def stat_line(label, val, lc=DIM, vc=WHITE):
            nonlocal sy
            _t(screen, f_xs, label, lc, sx, sy)
            sy += f_xs.get_height() + 3
            _t(screen, f_sm, val,   vc, sx, sy)
            sy += lh + 4

        score   = r.get("reward_score", 0)
        n_moves = r.get("number_of_moves", len(seq))
        n_opt   = len(opt) if opt else "?"
        diff    = (n_moves - n_opt) if isinstance(n_opt, int) else None

        if diff is not None:
            moves_col = CORRECT if diff == 0 else (AMBER if abs(diff) <= 2 else WRONG)
            moves_str = f"{n_moves} vs {n_opt} optimal  ({'+' if diff >= 0 else ''}{diff})"
        else:
            moves_col = WHITE
            moves_str = f"{n_moves} moves"

        stat_line("Score",         f"{score} pts", vc=res_col)
        pygame.draw.line(screen, BORDER, (sx, sy), (cx2 + cw - PAD, sy));  sy += 10
        stat_line("Moves / Optimal", moves_str, vc=moves_col)

        rt = r.get("reaction_time_ms")
        mt = r.get("movement_time_ms")
        if rt is not None:
            stat_line("Reaction time",  f"{rt/1000:.2f}s")
        if mt is not None:
            stat_line("Movement time",  f"{mt/1000:.2f}s")

        pygame.draw.line(screen, BORDER, (sx, sy), (cx2 + cw - PAD, sy));  sy += 10

        seq_str = "  ".join(str(k) for k in seq) if seq else "—"
        opt_str = "  ".join(str(k) for k in opt) if opt else "—"
        stat_line("Your sequence", seq_str, vc=ACCENT)
        stat_line("Optimal",       opt_str, vc=DIM)

        hs = f_xs.render("Click anywhere or press any key to close", True, DIM2)
        screen.blit(hs, (cx - hs.get_width()//2, cy2 + ch - 22))

        pygame.display.flip()


# ── Session item list builder ──────────────────────────────────

HEADER_H = 38   # block-header row height in the scroll list

def _build_items(session_state):
    """
    Build a flat list of renderable items (block headers + trial rows)
    covering the FULL session: past blocks from DB, current block from
    live session_state, future blocks as placeholders.
    """
    import ast
    from config import SESSION_STRUCTURE
    from database.db import get_participant_trials

    sn        = session_state["session_number"]
    pid       = session_state["participant_id"]
    cur_block = session_state["block_number"]
    structure = SESSION_STRUCTURE.get(sn, [])

    # Past block data from DB, grouped by block_number
    all_rows = get_participant_trials(pid)
    this_sn  = [r for r in all_rows if r["session_number"] == sn]
    by_block = {}
    for r in this_sn:
        by_block.setdefault(r["block_number"], []).append(r)

    items = []
    for block_idx, btype in enumerate(structure):
        bnum    = block_idx + 1
        is_cur  = bnum == cur_block
        is_past = bnum < cur_block

        items.append({
            "kind":       "header",
            "block_num":  bnum,
            "block_type": btype,
            "is_cur":     is_cur,
            "is_past":    is_past,
            "h":          HEADER_H,
        })

        if is_cur:
            # For trials already done in a prior run (resume), result is None
            # in memory. Back-fill from DB so the panel shows real data.
            db_cur = {r["trial_number"]: r for r in by_block.get(bnum, [])}
            for t in session_state["trials"]:
                item = {"kind": "trial", "h": ROW_H, "from_db": False, **t}
                if t["status"] == "done" and t.get("result") is None:
                    r = db_cur.get(t["trial_number"])
                    if r:
                        try:    seq = ast.literal_eval(r["planned_sequence"] or "[]")
                        except: seq = []
                        try:    opt = ast.literal_eval(r["optimal_sequence"] or "[]")
                        except: opt = []
                        item["result"] = {
                            "reward_score":     r["reward_score"] or 0,
                            "is_correct":       bool(r["is_correct"]),
                            "reaction_time_ms": r["reaction_time_ms"],
                            "movement_time_ms": r["movement_time_ms"],
                            "start":            (r["start_row"], r["start_col"]),
                            "goal":             (r["goal_row"],  r["goal_col"]),
                            "planned_sequence": seq,
                            "optimal_sequence": opt,
                        }
                items.append(item)

        elif is_past:
            past = sorted(by_block.get(bnum, []), key=lambda x: x["trial_number"])
            for r in past:
                try:    seq = ast.literal_eval(r["planned_sequence"] or "[]")
                except: seq = []
                try:    opt = ast.literal_eval(r["optimal_sequence"] or "[]")
                except: opt = []
                items.append({
                    "kind":         "trial",
                    "h":            ROW_H,
                    "from_db":      True,
                    "trial_number": r["trial_number"],
                    "grid_type":    r["grid_type"],
                    "status":       "done",
                    "result": {
                        "reward_score":       r["reward_score"] or 0,
                        "is_correct":         bool(r["is_correct"]),
                        "reaction_time_ms":   r["reaction_time_ms"],
                        "movement_time_ms":   r["movement_time_ms"],
                        "start":              (r["start_row"], r["start_col"]),
                        "goal":               (r["goal_row"],  r["goal_col"]),
                        "planned_sequence":   seq,
                        "optimal_sequence":   opt,
                    },
                })
            if not past:
                items.append({"kind": "note", "h": 28, "msg": "No data saved yet"})

        else:  # future block — show DB data if it exists from a previous run
            prior = sorted(by_block.get(bnum, []), key=lambda x: x["trial_number"])
            if prior:
                for r in prior:
                    try:    seq = ast.literal_eval(r["planned_sequence"] or "[]")
                    except: seq = []
                    try:    opt = ast.literal_eval(r["optimal_sequence"] or "[]")
                    except: opt = []
                    items.append({
                        "kind":         "trial",
                        "h":            ROW_H,
                        "from_db":      True,
                        "trial_number": r["trial_number"],
                        "grid_type":    r["grid_type"],
                        "status":       "done",
                        "result": {
                            "reward_score":     r["reward_score"] or 0,
                            "is_correct":       bool(r["is_correct"]),
                            "reaction_time_ms": r["reaction_time_ms"],
                            "movement_time_ms": r["movement_time_ms"],
                            "start":            (r["start_row"], r["start_col"]),
                            "goal":             (r["goal_row"],  r["goal_col"]),
                            "planned_sequence": seq,
                            "optimal_sequence": opt,
                        },
                    })
            else:
                items.append({"kind": "note", "h": 28, "msg": "Not started"})

    return items


# ── Side panel ─────────────────────────────────────────────────

def _side_panel(screen, clock, fonts, session_state, bg_snap):
    """
    Right-side panel showing the full trial list for the current block.

    Returns:
        ("resume", None)  — researcher closed the panel; continue the trial
        ("jump", N)       — jump to trial N (1-indexed); current trial abandoned
        ("exit", None)    — end the session
    """
    f_big, f_med, f_sm, f_xs = fonts
    W, H = screen.get_width(), screen.get_height()

    PANEL_HDR_H = max(116, 14 + f_med.get_height() + 8 + f_xs.get_height() + 12 + f_xs.get_height() + 10)

    sn    = session_state["session_number"]
    pid   = session_state["participant_id"]
    group = session_state["group"]

    panel_w  = max(520, int(W * PANEL_FRAC))
    panel_x  = W - panel_w
    panel_cx = panel_x + panel_w // 2

    LIST_Y   = PANEL_HDR_H
    LIST_BOT = H - FTR_H
    LIST_H   = LIST_BOT - LIST_Y

    # Build full session item list (all blocks)
    items        = _build_items(session_state)
    total_list_h = sum(item["h"] for item in items) + PAD * 2
    max_scroll   = max(0, total_list_h - LIST_H)

    # Live current-block info for jump logic
    live_trials  = session_state["trials"]
    cur_num      = next((t["trial_number"] for t in live_trials if t["status"] == "current"), 0)
    # Count skipped across ALL blocks in the session
    n_skipped    = sum(1 for it in items if it["kind"] == "trial" and it.get("status") == "skipped")
    skipped_nums = [it["trial_number"] for it in items
                    if it["kind"] == "trial" and it.get("status") == "skipped"]

    # Auto-scroll so the current trial is visible
    scroll_y = 0
    _offset  = PAD
    for item in items:
        if item["kind"] == "trial" and item.get("status") == "current":
            if _offset + item["h"] > LIST_H:
                scroll_y = min(max_scroll, _offset + item["h"] - LIST_H)
            break
        _offset += item["h"]

    # Footer buttons
    btn_y    = H - FTR_H + 36
    btn_w    = (panel_w - PAD * 3) // 2
    resume_r = pygame.Rect(panel_x + PAD,       btn_y, btn_w, 46)
    exit_r   = pygame.Rect(resume_r.right + PAD, btn_y, btn_w, 46)

    while True:
        clock.tick(FPS)
        events = pygame.event.get()
        for ev in events:
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit()

            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    return ("resume", None)
                elif ev.key in (pygame.K_DOWN, pygame.K_PAGEDOWN):
                    scroll_y = min(max_scroll, scroll_y + ROW_H)
                elif ev.key in (pygame.K_UP, pygame.K_PAGEUP):
                    scroll_y = max(0, scroll_y - ROW_H)

            if ev.type == pygame.MOUSEWHEEL:
                dy = getattr(ev, 'precise_y', None)
                if dy is None or (dy == 0 and ev.y != 0):
                    dy = float(ev.y)
                scroll_y = max(0, min(max_scroll, scroll_y - int(dy * ROW_H // 2)))

            if ev.type == pygame.MOUSEBUTTONDOWN:
                if ev.button == 4:
                    scroll_y = max(0, scroll_y - ROW_H); continue
                if ev.button == 5:
                    scroll_y = min(max_scroll, scroll_y + ROW_H); continue

                mx, my = ev.pos

                if resume_r.collidepoint(mx, my):
                    return ("resume", None)
                if exit_r.collidepoint(mx, my):
                    return ("exit", None)

                # Click on a trial row
                if panel_x <= mx <= W and LIST_Y <= my <= LIST_BOT:
                    hit_y = LIST_Y + PAD - scroll_y
                    for item in items:
                        item_bot = hit_y + item["h"]
                        if hit_y <= my < item_bot:
                            if item["kind"] == "trial":
                                row_r = pygame.Rect(panel_x + PAD, hit_y,
                                                    panel_w - PAD * 2, item["h"] - 6)
                                if row_r.collidepoint(mx, my):
                                    status = item.get("status", "")
                                    if status == "done":
                                        _stats_modal(screen, clock, fonts, item, screen.copy())
                                    elif status in ("pending", "skipped") and not item.get("from_db"):
                                        confirmed = _jump_confirm(
                                            screen, clock, fonts,
                                            cur_num, item["trial_number"], screen.copy()
                                        )
                                        if confirmed:
                                            return ("jump", item["trial_number"])
                            break
                        hit_y = item_bot

        # ── Draw ──────────────────────────────────────────────
        screen.blit(bg_snap, (0, 0))
        left_dim = pygame.Surface((panel_x, H), pygame.SRCALPHA)
        left_dim.fill((0, 0, 0, 155))
        screen.blit(left_dim, (0, 0))

        pygame.draw.rect(screen, BG, (panel_x, 0, panel_w, H))
        pygame.draw.line(screen, (72, 72, 116), (panel_x, 0), (panel_x, H), 2)

        # ── Panel header ──────────────────────────────────────
        pygame.draw.rect(screen, (14, 14, 28), (panel_x, 0, panel_w, PANEL_HDR_H))
        pygame.draw.line(screen, BORDER, (panel_x, PANEL_HDR_H), (W, PANEL_HDR_H))

        ts = f_med.render("RESEARCHER VIEW  —  Full Session", True, ACCENT)
        screen.blit(ts, (panel_x + PAD, 14))

        info_str = f"{pid}  ·  Session {sn}  ·  {group}"
        info_s   = f_xs.render(info_str, True, DIM)
        screen.blit(info_s, (panel_x + PAD, 14 + ts.get_height() + 8))

        n_total = sum(1 for it in items if it["kind"] == "trial")
        n_done  = sum(1 for it in items if it["kind"] == "trial" and it.get("status") == "done")
        summ_s  = f_xs.render(f"Trials done: {n_done} / {n_total}", True, DIM2)
        screen.blit(summ_s, (panel_x + PAD, PANEL_HDR_H - summ_s.get_height() - 10))

        # ── Scrollable item list ───────────────────────────────
        screen.set_clip(pygame.Rect(panel_x, LIST_Y, panel_w, LIST_H))
        mouse    = pygame.mouse.get_pos()
        item_y   = LIST_Y + PAD - scroll_y

        for item in items:
            ih = item["h"]

            if item_y + ih < LIST_Y or item_y > LIST_BOT:
                item_y += ih
                continue

            kind = item["kind"]

            if kind == "header":
                bnum   = item["block_num"]
                btype  = item["block_type"].replace("_", " ").title()
                is_cur = item["is_cur"]
                is_past= item["is_past"]
                hdr_col= ACCENT if is_cur else (CORRECT if is_past else DIM2)
                lbl    = f"Block {bnum}  ·  {btype}"
                if is_cur:   lbl += "  ◀ CURRENT"
                elif is_past: lbl += "  ✓"
                pygame.draw.rect(screen, (14, 14, 28),
                                 (panel_x, item_y, panel_w, ih))
                pygame.draw.line(screen, hdr_col,
                                 (panel_x + PAD, item_y + ih - 1),
                                 (W - PAD, item_y + ih - 1))
                hs = f_xs.render(lbl, True, hdr_col)
                screen.blit(hs, (panel_x + PAD, item_y + (ih - hs.get_height()) // 2))

            elif kind == "note":
                ns = f_xs.render(item["msg"], True, DIM2)
                screen.blit(ns, (panel_x + PAD + 16,
                                 item_y + (ih - ns.get_height()) // 2))

            else:  # trial row
                status  = item.get("status", "pending")
                trial_n = item["trial_number"]
                gtype   = item.get("grid_type", "random")
                res     = item.get("result") or {}

                if   status == "current":  row_bg=(30,44,90);  row_bc=ACCENT
                elif status == "done":     row_bg=(16,28,44);  row_bc=(36,60,100)
                elif status == "skipped":  row_bg=(36,18, 8);  row_bc=SKIP_C
                else:                      row_bg=(18,18,34);  row_bc=BORDER

                row_r = pygame.Rect(panel_x + PAD, item_y, panel_w - PAD*2, ih - 6)
                is_hover = row_r.collidepoint(mouse) and status in ("done", "pending", "skipped")
                if is_hover:
                    row_bg = tuple(min(255, c + 14) for c in row_bg)

                pygame.draw.rect(screen, row_bg, row_r, border_radius=8)
                pygame.draw.rect(screen, row_bc, row_r, width=1, border_radius=8)

                ry_mid = item_y + (ih - 6) // 2
                rx     = panel_x + PAD + 10

                # Status icon
                if   status == "done":    icon = "✓" if res.get("is_correct") else "✗"
                elif status == "current": icon = "▶"
                elif status == "skipped": icon = "✗"
                else:                     icon = "○"
                ic = (CORRECT if (status=="done" and res.get("is_correct"))
                      else WRONG if status in ("done","skipped") and not res.get("is_correct", True)
                      else SKIP_C if status=="skipped"
                      else ACCENT if status=="current"
                      else DIM)
                is_s = f_sm.render(icon, True, ic)
                screen.blit(is_s, (rx, ry_mid - is_s.get_height()//2))
                rx += is_s.get_width() + 10

                tn_s = f_sm.render(f"Trial {trial_n:2d}", True, WHITE)
                screen.blit(tn_s, (rx, ry_mid - tn_s.get_height()//2))
                rx += tn_s.get_width() + 12

                gt_fg, gt_bg_c, gt_lbl = ((ACCENT,(20,36,80),"REP")
                                           if gtype=="repeated"
                                           else (AMBER,(44,36,8),"RAN"))
                gt_s  = f_xs.render(gt_lbl, True, gt_fg)
                gt_pw = gt_s.get_width() + 12
                gt_ph = gt_s.get_height() + 6
                gt_py = ry_mid - gt_ph // 2
                pygame.draw.rect(screen, gt_bg_c, (rx, gt_py, gt_pw, gt_ph), border_radius=gt_ph//2)
                screen.blit(gt_s, (rx + 6, gt_py + 3))
                rx += gt_pw + 14

                if status == "done" and res:
                    sc_s = f_sm.render(f"{res.get('reward_score',0)} pts", True,
                                       CORRECT if res.get("is_correct") else WRONG)
                    screen.blit(sc_s, (rx, ry_mid - sc_s.get_height()//2))
                    rt = res.get("reaction_time_ms")
                    if rt is not None:
                        rt_s = f_xs.render(f"  {rt/1000:.1f}s RT", True, DIM)
                        screen.blit(rt_s, (rx + sc_s.get_width(),
                                           ry_mid - rt_s.get_height()//2))
                elif status == "current":
                    screen.blit(f_sm.render("IN PROGRESS", True, ACCENT),
                                (rx, ry_mid - f_sm.get_height()//2))
                elif status == "skipped":
                    screen.blit(f_xs.render("SKIPPED", True, SKIP_C),
                                (rx, ry_mid - f_xs.get_height()//2))
                elif not is_hover:
                    screen.blit(f_xs.render("Pending", True, DIM2),
                                (rx, ry_mid - f_xs.get_height()//2))

                if is_hover:
                    if status == "done":
                        hint, hc = "View →", ACCENT
                    elif status == "skipped" and not item.get("from_db"):
                        hint, hc = "Jump here →", AMBER
                    else:
                        can_jump = (trial_n > cur_num and not item.get("from_db"))
                        hint, hc = ("Jump here →", ACCENT) if can_jump else ("—", DIM2)
                    hs2 = f_xs.render(hint, True, hc)
                    screen.blit(hs2, (panel_x + panel_w - PAD - hs2.get_width() - 6,
                                      ry_mid - hs2.get_height()//2))

            item_y += ih

        screen.set_clip(None)

        # Scrollbar
        SB_W = 6
        sb_x  = W - SB_W - 2
        if total_list_h > LIST_H:
            track_h = LIST_H - 8
            track_y = LIST_Y + 4
            thumb_h = max(28, int(track_h * LIST_H / total_list_h))
            thumb_y = track_y + int((track_h - thumb_h) * scroll_y / max(1, max_scroll))
            pygame.draw.rect(screen, (32, 32, 56), (sb_x, track_y, SB_W, track_h), border_radius=3)
            pygame.draw.rect(screen, ACCENT,        (sb_x, thumb_y, SB_W, thumb_h), border_radius=3)

        pygame.draw.line(screen, BORDER, (panel_x, LIST_Y),   (W, LIST_Y))
        pygame.draw.line(screen, BORDER, (panel_x, LIST_BOT),  (W, LIST_BOT))

        # ── Footer ────────────────────────────────────────────
        pygame.draw.rect(screen, (14, 14, 28), (panel_x, LIST_BOT, panel_w, FTR_H))

        if n_skipped > 0:
            sk_str = ", ".join(str(x) for x in skipped_nums)
            warn   = f_xs.render(
                f"⚠  {n_skipped} trial{'s' if n_skipped>1 else ''} skipped "
                f"(Trial{'s' if n_skipped>1 else ''} {sk_str})", True, AMBER)
            screen.blit(warn, (panel_x + PAD, LIST_BOT + 8))

        mouse = pygame.mouse.get_pos()
        for rect, label, col in [(resume_r, "Resume Trial", CORRECT),
                                  (exit_r,   "End Session",  WRONG)]:
            hv = rect.collidepoint(mouse)
            bg = tuple(min(255, c+28) for c in col) if hv else tuple(c//3 for c in col)
            tc = (8, 8, 16) if hv else WHITE
            pygame.draw.rect(screen, (4,4,12), (rect.x+2, rect.y+3, rect.w, rect.h), border_radius=10)
            pygame.draw.rect(screen, bg, rect, border_radius=10)
            pygame.draw.rect(screen, col, rect, width=1, border_radius=10)
            ls = f_sm.render(label, True, tc)
            screen.blit(ls, (rect.centerx - ls.get_width()//2,
                              rect.centery - ls.get_height()//2))

        es = f_xs.render("ESC to resume", True, DIM2)
        screen.blit(es, (panel_cx - es.get_width()//2, H - 16))

        pygame.display.flip()


# ── Entry point ────────────────────────────────────────────────

def run_researcher_access(screen, clock, fonts, session_state):
    """
    Full researcher access flow: password prompt → side panel.

    Args:
        session_state (dict): Built by run_block; tracks all trial statuses.

    Returns:
        ("resume", None)  — continue the current trial
        ("jump", N)       — jump to trial N; current trial will be abandoned
        ("exit", None)    — end the session
    """
    bg_snap = screen.copy()

    if not _password_prompt(screen, clock, fonts, bg_snap):
        return ("resume", None)

    return _side_panel(screen, clock, fonts, session_state, bg_snap)
