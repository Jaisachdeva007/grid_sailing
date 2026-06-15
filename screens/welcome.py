# ============================================================
#  GRID-SAILING TASK — Welcome Screen
#
#  First screen participants and researchers see.
#  Two paths:
#    · Researcher  → password prompt → setup screen
#    · Participant → shows "Please wait for the researcher"
#
#  This keeps the experiment config completely hidden from
#  participants — they only ever see their login screen.
# ============================================================

import pygame
import sys
import hashlib
import math
import time
from config import WINDOW_WIDTH, WINDOW_HEIGHT, FPS, ADMIN_PASSWORD

# ── Palette ───────────────────────────────────────────────────
BG      = (10,  10,  20)
SURFACE = (18,  18,  32)
PANEL   = (24,  24,  42)
BORDER  = (50,  50,  78)
WHITE   = (228, 228, 242)
DIM     = (100, 100, 138)
ACCENT  = ( 88, 148, 255)
GREEN   = ( 58, 196, 108)
RED     = (212,  58,  58)
INPUT_BG  = (28,  28,  48)
INPUT_ACT = (36,  36,  60)

W = WINDOW_WIDTH
H = WINDOW_HEIGHT
CX = W // 2
CY = H // 2


def _hash(pw): return hashlib.sha256(pw.encode()).hexdigest()
ADMIN_HASH = _hash(ADMIN_PASSWORD)


def _t(screen, font, text, col, x, y, center=False):
    s = font.render(text, True, col)
    if center:
        screen.blit(s, (x - s.get_width() // 2, y))
    else:
        screen.blit(s, (x, y))
    return s


def _panel(screen, x, y, w, h, col=BORDER, r=12):
    pygame.draw.rect(screen, PANEL,  (x, y, w, h), border_radius=r)
    pygame.draw.rect(screen, col,    (x, y, w, h), width=1, border_radius=r)


def _draw_bg_grid(screen, t):
    """Subtle animated dot grid in background."""
    spacing = 48
    pulse = 0.18 + 0.06 * math.sin(t * 0.8)
    for gx in range(0, W + spacing, spacing):
        for gy in range(0, H + spacing, spacing):
            alpha = int(255 * pulse)
            pygame.draw.circle(screen, (30, 30, 55), (gx, gy), 1)


def run_welcome(screen, clock):
    """
    Show the welcome / role-select screen.

    Returns:
        "researcher"  — password verified, proceed to setup
        "quit"        — window closed
    """
    f_big  = pygame.font.SysFont("Helvetica Neue", 38, bold=True)
    f_med  = pygame.font.SysFont("Helvetica Neue", 20, bold=True)
    f_sm   = pygame.font.SysFont("Helvetica Neue", 16)
    f_xs   = pygame.font.SysFont("Helvetica Neue", 13)
    # Arial fallback
    if f_big.get_height() < 10:
        f_big = pygame.font.SysFont("Arial", 38, bold=True)
        f_med = pygame.font.SysFont("Arial", 20, bold=True)
        f_sm  = pygame.font.SysFont("Arial", 16)
        f_xs  = pygame.font.SysFont("Arial", 13)

    # State
    pw_text  = ""
    pw_active = False
    error    = ""
    error_t  = 0
    start_t  = time.time()

    pw_rect  = pygame.Rect(CX - 180, CY + 40, 360, 46)
    btn_rect = pygame.Rect(CX - 100, CY + 102, 200, 44)

    while True:
        clock.tick(FPS)
        now = time.time()
        t   = now - start_t

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()

            if event.type == pygame.MOUSEBUTTONDOWN:
                pw_active = pw_rect.collidepoint(event.pos)
                if btn_rect.collidepoint(event.pos):
                    if _hash(pw_text) == ADMIN_HASH:
                        return "researcher"
                    else:
                        error = "Incorrect password."
                        error_t = now
                        pw_text = ""

            if event.type == pygame.KEYDOWN and pw_active:
                if event.key == pygame.K_BACKSPACE:
                    pw_text = pw_text[:-1]
                elif event.key == pygame.K_RETURN:
                    if _hash(pw_text) == ADMIN_HASH:
                        return "researcher"
                    else:
                        error = "Incorrect password."
                        error_t = now
                        pw_text = ""
                elif event.key == pygame.K_ESCAPE:
                    pw_text = ""; pw_active = False
                elif len(pw_text) < 32:
                    pw_text += event.unicode

        # Clear error after 2.5s
        if error and now - error_t > 2.5:
            error = ""

        # ── Draw ─────────────────────────────────────────────
        screen.fill(BG)
        _draw_bg_grid(screen, t)

        # Glow circle behind title
        pulse = 0.5 + 0.5 * math.sin(t * 1.2)
        for rad, alpha in [(140, 18), (100, 28), (68, 40)]:
            glow = pygame.Surface((rad*2, rad*2), pygame.SRCALPHA)
            pygame.draw.circle(glow, (*ACCENT, int(alpha * pulse)),
                               (rad, rad), rad)
            screen.blit(glow, (CX - rad, CY - 210 - rad))

        # Title
        title = f_big.render("Grid-Sailing Task", True, WHITE)
        screen.blit(title, (CX - title.get_width() // 2, CY - 230))

        subtitle = f_sm.render("Motor Imagery Sequential Learning Experiment", True, DIM)
        screen.blit(subtitle, (CX - subtitle.get_width() // 2, CY - 185))

        # Divider
        pygame.draw.line(screen, BORDER,
                         (CX - 220, CY - 158), (CX + 220, CY - 158))

        # Researcher login panel
        panel_h = 220
        _panel(screen, CX - 220, CY - 145, 440, panel_h, BORDER)

        lock_lbl = f_xs.render("RESEARCHER ACCESS", True, DIM)
        screen.blit(lock_lbl, (CX - lock_lbl.get_width() // 2, CY - 128))

        pw_label = f_sm.render("Admin password", True, DIM)
        screen.blit(pw_label, (CX - 180, CY + 16))

        # Password input
        pw_bc = ACCENT if pw_active else BORDER
        pw_bg = INPUT_ACT if pw_active else INPUT_BG
        pygame.draw.rect(screen, pw_bg,  pw_rect, border_radius=8)
        pygame.draw.rect(screen, pw_bc,  pw_rect, width=1, border_radius=8)
        if pw_active:
            pygame.draw.rect(screen, ACCENT,
                             (pw_rect.x, pw_rect.y + 8, 2, pw_rect.h - 16))
        display = "•" * len(pw_text) if pw_text else ""
        if display:
            ds = f_sm.render(display, True, WHITE)
            screen.blit(ds, (pw_rect.x + 14,
                              pw_rect.y + pw_rect.h // 2 - ds.get_height() // 2))
        elif not pw_active:
            ph = f_sm.render("Enter password", True, DIM)
            screen.blit(ph, (pw_rect.x + 14,
                              pw_rect.y + pw_rect.h // 2 - ph.get_height() // 2))

        # Login button
        mouse = pygame.mouse.get_pos()
        bcol  = tuple(min(255, c + 20) for c in ACCENT) \
                if btn_rect.collidepoint(mouse) else ACCENT
        pygame.draw.rect(screen, (8, 8, 16),
                         (btn_rect.x+2, btn_rect.y+3, btn_rect.w, btn_rect.h),
                         border_radius=10)
        pygame.draw.rect(screen, bcol, btn_rect, border_radius=10)
        bl = f_sm.render("Log In", True, BG := (10, 10, 20))
        screen.blit(bl, (btn_rect.x + btn_rect.w // 2 - bl.get_width() // 2,
                          btn_rect.y + btn_rect.h // 2 - bl.get_height() // 2))

        # Error
        if error:
            alpha = min(1.0, (2.5 - (now - error_t)) / 0.5)
            er = f_xs.render(error, True, RED)
            screen.blit(er, (CX - er.get_width() // 2, CY + 155))

        # Bottom hint — for participants
        hint = f_xs.render(
            "Participant? Please wait — your researcher will start the session for you.",
            True, DIM
        )
        screen.blit(hint, (CX - hint.get_width() // 2, H - 40))

        pygame.display.flip()
