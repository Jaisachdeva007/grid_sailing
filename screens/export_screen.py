# ============================================================
#  GRID-SAILING TASK — Export Screen
#
#  You don't need to touch this file.
#
#  This is the screen you get when you click "Export Data" in the
#  Data Viewer. The three buttons do slightly different things:
#    Export All           → every key press from every participant (big file)
#    Trial Summary        → one row per trial — usually what you want first
#    Export Participant   → same as Export All but for just one person
#
#  Everything goes into the exports/ folder next to main.py.
#  The folder gets created automatically if it doesn't exist yet.
#
#  File names include a timestamp (e.g. all_participants_20260708_143022.csv)
#  so you can't accidentally overwrite an older export.
# ============================================================

import pygame
import sys
import os
from config import WINDOW_WIDTH, WINDOW_HEIGHT, FPS
from database.db import get_all_participants
from export.exporter import export_participant, export_all, export_summary

BG      = (8,    8,  16)
SURFACE = (14,  14,  26)
PANEL   = (20,  20,  36)
PANEL2  = (26,  26,  44)
BORDER  = (48,  48,  76)
WHITE   = (245, 245, 255)
DIM     = (118, 118, 158)
DIM2    = (72,   72, 112)
ACCENT  = ( 88, 148, 255)
GREEN   = ( 52, 200, 100)
ORANGE  = (228, 138,  48)
PURPLE  = (160,  90, 220)
RED     = (220,  60,  60)
PAD     = 48
W, H    = WINDOW_WIDTH, WINDOW_HEIGHT
CX      = W // 2


def _t(screen, font, text, col, x, y, cw=0):
    s = font.render(text, True, col)
    screen.blit(s, (x + cw // 2 - s.get_width() // 2, y) if cw else (x, y))

def _panel(screen, x, y, w, h, col=BORDER, r=10):
    pygame.draw.rect(screen, PANEL, (x, y, w, h), border_radius=r)
    pygame.draw.rect(screen, col,   (x, y, w, h), width=1, border_radius=r)

def _btn(screen, font_sm, font_xs, label, sub, rect, color):
    mouse = pygame.mouse.get_pos()
    hover = rect.collidepoint(mouse)
    col   = tuple(min(255, c + 24) for c in color) if hover else color
    pygame.draw.rect(screen, (4, 4, 10),
                     (rect.x + 2, rect.y + 3, rect.w, rect.h), border_radius=10)
    pygame.draw.rect(screen, col, rect, border_radius=10)
    ls = font_sm.render(label, True, (8, 8, 16))
    screen.blit(ls, (rect.x + rect.w // 2 - ls.get_width() // 2,
                     rect.y + rect.h // 2 - ls.get_height() // 2 - (10 if sub else 0)))
    if sub:
        ss = font_xs.render(sub, True, (24, 24, 40))
        screen.blit(ss, (rect.x + rect.w // 2 - ss.get_width() // 2,
                         rect.y + rect.h // 2 + 7))


def run_export_screen(screen, clock, fonts):
    f_big, f_med, f_sm, f_xs = fonts

    pid_input = ""
    pid_active = False

    INPUT_W = 260
    INPUT_H = 48
    INPUT_X = CX - INPUT_W // 2
    INPUT_Y = 280

    pid_rect   = pygame.Rect(INPUT_X, INPUT_Y, INPUT_W, INPUT_H)
    single_btn = pygame.Rect(CX - 130, INPUT_Y + 64,  260, 52)
    all_btn    = pygame.Rect(PAD,      INPUT_Y + 148,  int((W - PAD*2 - 24)/2), 52)
    sum_btn    = pygame.Rect(PAD + int((W - PAD*2 - 24)/2) + 24,
                             INPUT_Y + 148, int((W - PAD*2 - 24)/2), 52)
    back_rect  = pygame.Rect(PAD, H - 52, 100, 36)

    message   = ""
    msg_col   = GREEN
    refresh_t = 0
    participants = []

    pygame.display.set_caption("Grid-Sailing — Export Data")

    while True:
        clock.tick(FPS)
        now = pygame.time.get_ticks()
        if now - refresh_t > 2000:
            participants  = [p["participant_id"] for p in get_all_participants()]
            refresh_t = now

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return
                if pid_active:
                    if event.key == pygame.K_BACKSPACE:
                        pid_input = pid_input[:-1]
                    elif event.key not in (pygame.K_RETURN, pygame.K_TAB):
                        if len(pid_input) < 20:
                            pid_input += event.unicode
            if event.type == pygame.MOUSEBUTTONDOWN:
                pid_active = pid_rect.collidepoint(event.pos)
                if back_rect.collidepoint(event.pos):
                    return
                if single_btn.collidepoint(event.pos):
                    pid = pid_input.strip().upper()
                    if not pid:
                        message = "Enter a participant ID first."; msg_col = RED
                    elif pid not in participants:
                        message = f"'{pid}' not found in database."; msg_col = RED
                    else:
                        path = export_participant(pid)
                        message = f"Saved  {os.path.basename(path)}"; msg_col = GREEN
                if all_btn.collidepoint(event.pos):
                    path = export_all()
                    message = f"Saved  {os.path.basename(path)}"; msg_col = GREEN
                if sum_btn.collidepoint(event.pos):
                    path = export_summary()
                    message = f"Saved  {os.path.basename(path)}"; msg_col = GREEN

        # ── Draw ─────────────────────────────────────────────
        screen.fill(BG)

        # Title bar
        pygame.draw.rect(screen, SURFACE, (0, 0, W, 60))
        pygame.draw.line(screen, BORDER, (0, 60), (W, 60))
        _t(screen, f_med, "Export Data", WHITE, PAD, 19)
        _t(screen, f_xs, "ESC to go back", DIM, W - PAD - 120, 23)

        # Destination note
        _t(screen, f_xs, "All files are saved to the  exports/  folder next to main.py",
           DIM, 0, 80, cw=W)

        # Registered participants chips
        _t(screen, f_xs, "REGISTERED PARTICIPANTS", DIM, PAD, 116)
        px = PAD; py = 138
        for p in participants:
            ps = f_xs.render(p, True, ACCENT)
            pw = ps.get_width() + 20
            pygame.draw.rect(screen, (20, 32, 68), (px, py, pw, 26), border_radius=13)
            pygame.draw.rect(screen, ACCENT,       (px, py, pw, 26), width=1, border_radius=13)
            screen.blit(ps, (px + 10, py + 5))
            px += pw + 10
            if px > W - PAD - 100:
                px = PAD; py += 34
        if not participants:
            _t(screen, f_xs, "None yet", DIM, PAD, 138)

        # Divider
        pygame.draw.line(screen, BORDER, (PAD, 196), (W - PAD, 196))

        # Single participant section
        _t(screen, f_sm, "Export one participant", WHITE, PAD, 222)
        _t(screen, f_xs, "Full keypress-level data — one row per keypress",
           DIM, PAD, 248)

        # PID input
        bg = (34, 34, 58) if pid_active else (24, 24, 44)
        bc = ACCENT if pid_active else BORDER
        pygame.draw.rect(screen, bg, pid_rect, border_radius=10)
        pygame.draw.rect(screen, bc, pid_rect, width=2 if pid_active else 1, border_radius=10)
        if pid_active:
            pygame.draw.rect(screen, ACCENT,
                             (pid_rect.x, pid_rect.y + 8, 2, pid_rect.h - 16))
        display = pid_input.upper() if pid_input else "Participant ID  (e.g. P001)"
        ds = f_sm.render(display, True, WHITE if pid_input else (52, 52, 80))
        screen.blit(ds, (pid_rect.x + 14,
                          pid_rect.y + pid_rect.h // 2 - ds.get_height() // 2))

        _btn(screen, f_sm, f_xs, "Export Participant", "keypresses + trials CSV",
             single_btn, ACCENT)

        # Divider
        pygame.draw.line(screen, BORDER,
                         (PAD, INPUT_Y + 136), (W - PAD, INPUT_Y + 136))

        # All participants section
        _t(screen, f_sm, "Export everyone", WHITE, PAD, INPUT_Y + 140)

        _btn(screen, f_sm, f_xs, "Export All Participants",
             "every keypress, all participants", all_btn, ORANGE)
        _btn(screen, f_sm, f_xs, "Trial Summary",
             "one row per trial, no keypresses", sum_btn, PURPLE)

        # Status message
        if message:
            ms = f_sm.render(message, True, msg_col)
            screen.blit(ms, (CX - ms.get_width() // 2, H - 84))

        # Back
        pygame.draw.line(screen, BORDER, (0, H - 60), (W, H - 60))
        pygame.draw.rect(screen, PANEL2, back_rect, border_radius=8)
        pygame.draw.rect(screen, BORDER, back_rect, width=1, border_radius=8)
        _t(screen, f_xs, "< Back", DIM, back_rect.x + 14, back_rect.y + 10)

        pygame.display.flip()
