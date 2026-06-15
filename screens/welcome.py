# ============================================================
#  GRID-SAILING TASK — Welcome / Admin Login Screen
# ============================================================

import pygame
import sys
import hashlib
import math
import time
from config import WINDOW_WIDTH, WINDOW_HEIGHT, FPS, ADMIN_PASSWORD

# ── Palette ───────────────────────────────────────────────────
BG        = (8,    8,   16)
SURFACE   = (14,  14,   26)
PANEL     = (20,  20,   36)
BORDER    = (48,  48,   76)
WHITE     = (245, 245, 255)
DIM       = (118, 118, 158)
ACCENT    = (88,  148, 255)
GREEN     = (52,  200, 100)
RED       = (220,  60,  60)
INPUT_BG  = (26,  26,   46)
INPUT_ACT = (34,  34,   58)

W, H   = WINDOW_WIDTH, WINDOW_HEIGHT
CX, CY = W // 2, H // 2

def _hash(pw): return hashlib.sha256(pw.encode()).hexdigest()
ADMIN_HASH = _hash(ADMIN_PASSWORD)


def run_welcome(screen, clock):
    f_title = pygame.font.SysFont("Helvetica Neue", 44, bold=True)
    f_sub   = pygame.font.SysFont("Helvetica Neue", 17)
    f_med   = pygame.font.SysFont("Helvetica Neue", 20, bold=True)
    f_sm    = pygame.font.SysFont("Helvetica Neue", 16)
    f_xs    = pygame.font.SysFont("Helvetica Neue", 13)

    pygame.display.set_caption("Grid-Sailing Task")

    pw_text   = ""
    pw_active = False
    error     = ""
    error_t   = 0
    start_t   = time.time()

    # Card geometry
    CW, CH = 420, 230
    CX2 = CX - CW // 2
    CY2 = CY - 40

    pw_rect  = pygame.Rect(CX2 + 20, CY2 + 88, CW - 40, 46)
    btn_rect = pygame.Rect(CX2 + 20, CY2 + 152, CW - 40, 46)

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
                    error = "Incorrect password."; error_t = now; pw_text = ""

            if event.type == pygame.KEYDOWN and pw_active:
                if event.key == pygame.K_BACKSPACE:
                    pw_text = pw_text[:-1]
                elif event.key == pygame.K_RETURN:
                    if _hash(pw_text) == ADMIN_HASH:
                        return "researcher"
                    error = "Incorrect password."; error_t = now; pw_text = ""
                elif event.key == pygame.K_ESCAPE:
                    pw_text = ""; pw_active = False
                elif len(pw_text) < 32:
                    pw_text += event.unicode

        if error and now - error_t > 2.5:
            error = ""

        # ── Draw ─────────────────────────────────────────────
        screen.fill(BG)

        # Dot grid
        for gx in range(0, W + 48, 48):
            for gy in range(0, H + 48, 48):
                pygame.draw.circle(screen, (22, 22, 42), (gx, gy), 1)

        # Glow behind title
        pulse = 0.5 + 0.5 * math.sin(t * 1.1)
        for rad, alpha in [(160, 14), (110, 22), (72, 34)]:
            g = pygame.Surface((rad * 2, rad * 2), pygame.SRCALPHA)
            pygame.draw.circle(g, (*ACCENT, int(alpha * pulse)), (rad, rad), rad)
            screen.blit(g, (CX - rad, CY - 260 - rad))

        # Title
        ts = f_title.render("Grid-Sailing Task", True, WHITE)
        screen.blit(ts, (CX - ts.get_width() // 2, CY - 268))

        sub = f_sub.render("Motor Imagery Sequential Learning Experiment", True, DIM)
        screen.blit(sub, (CX - sub.get_width() // 2, CY - 214))

        # Divider
        pygame.draw.line(screen, BORDER, (CX - 240, CY - 188), (CX + 240, CY - 188))

        # ── Login card ───────────────────────────────────────
        # Shadow
        pygame.draw.rect(screen, (6, 6, 12),
                         (CX2 + 3, CY2 + 5, CW, CH), border_radius=18)
        # Card body
        pygame.draw.rect(screen, PANEL, (CX2, CY2, CW, CH), border_radius=18)
        pygame.draw.rect(screen, BORDER, (CX2, CY2, CW, CH), width=1, border_radius=18)

        # "RESEARCHER ACCESS" chip
        chip_txt = f_xs.render("RESEARCHER ACCESS", True, DIM)
        chip_w = chip_txt.get_width() + 24
        chip_x = CX - chip_w // 2
        pygame.draw.rect(screen, (28, 28, 50),
                         (chip_x, CY2 + 16, chip_w, 24), border_radius=12)
        pygame.draw.rect(screen, BORDER,
                         (chip_x, CY2 + 16, chip_w, 24), width=1, border_radius=12)
        screen.blit(chip_txt, (chip_x + 12, CY2 + 19))

        # Divider inside card
        pygame.draw.line(screen, BORDER,
                         (CX2 + 20, CY2 + 52), (CX2 + CW - 20, CY2 + 52))

        # Label
        lbl = f_sm.render("Admin password", True, DIM)
        screen.blit(lbl, (CX2 + 20, CY2 + 62))

        # Password input
        pw_bc = ACCENT if pw_active else BORDER
        pw_bg = INPUT_ACT if pw_active else INPUT_BG
        pygame.draw.rect(screen, pw_bg,  pw_rect, border_radius=10)
        pygame.draw.rect(screen, pw_bc,  pw_rect, width=1 if not pw_active else 2,
                         border_radius=10)
        if pw_active:
            pygame.draw.rect(screen, ACCENT,
                             (pw_rect.x, pw_rect.y + 8, 2, pw_rect.h - 16))
        display = "•" * len(pw_text)
        if display:
            ds = f_sm.render(display, True, WHITE)
            screen.blit(ds, (pw_rect.x + 14,
                              pw_rect.y + pw_rect.h // 2 - ds.get_height() // 2))
        elif not pw_active:
            ph = f_sm.render("Enter password", True, (60, 60, 90))
            screen.blit(ph, (pw_rect.x + 14,
                              pw_rect.y + pw_rect.h // 2 - ph.get_height() // 2))

        # Log In button
        mouse = pygame.mouse.get_pos()
        hover = btn_rect.collidepoint(mouse)
        bcol  = tuple(min(255, c + 24) for c in ACCENT) if hover else ACCENT
        pygame.draw.rect(screen, (6, 6, 14),
                         (btn_rect.x + 2, btn_rect.y + 3, btn_rect.w, btn_rect.h),
                         border_radius=10)
        pygame.draw.rect(screen, bcol, btn_rect, border_radius=10)
        bl = f_med.render("Log In", True, BG)
        screen.blit(bl, (btn_rect.x + btn_rect.w // 2 - bl.get_width() // 2,
                          btn_rect.y + btn_rect.h // 2 - bl.get_height() // 2))

        # Error
        if error:
            er = f_xs.render(error, True, RED)
            screen.blit(er, (CX - er.get_width() // 2, CY2 + CH + 14))

        # Bottom participant hint
        hint = f_xs.render(
            "Participant? Please wait — your researcher will start the session for you.",
            True, (52, 52, 80))
        screen.blit(hint, (CX - hint.get_width() // 2, H - 34))

        pygame.display.flip()
