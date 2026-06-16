# ============================================================
#  GRID-SAILING TASK — Participant Login Screen
# ============================================================

import pygame
import sys
import math
import time
from config import WINDOW_WIDTH, WINDOW_HEIGHT, FPS
from database.db import verify_participant

BG        = (8,    8,   16)
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


class InputBox:
    def __init__(self, x, y, w, h, placeholder="", secret=False):
        self.rect        = pygame.Rect(x, y, w, h)
        self.text        = ""
        self.placeholder = placeholder
        self.secret      = secret
        self.active      = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key not in (pygame.K_RETURN, pygame.K_TAB, pygame.K_ESCAPE):
                if len(self.text) < 24:
                    self.text += event.unicode

    def draw(self, screen, font):
        bg = INPUT_ACT if self.active else INPUT_BG
        bc = ACCENT    if self.active else BORDER
        pygame.draw.rect(screen, bg, self.rect, border_radius=10)
        pygame.draw.rect(screen, bc, self.rect,
                         width=2 if self.active else 1, border_radius=10)
        if self.active:
            pygame.draw.rect(screen, ACCENT,
                             (self.rect.x, self.rect.y + 8, 2, self.rect.h - 16))
        display = ("•" * len(self.text)) if self.secret else self.text
        txt = font.render(display if display else self.placeholder,
                          True, WHITE if display else (60, 60, 90))
        screen.blit(txt, (self.rect.x + 16,
                           self.rect.y + self.rect.h // 2 - txt.get_height() // 2))


def run_participant_login(screen, clock, fonts, config: dict):
    f_big, f_med, f_sm, f_xs = fonts
    pygame.display.set_caption("Grid-Sailing Task")

    # Local larger fonts for this screen
    f_title = pygame.font.SysFont("Helvetica Neue", 50, bold=True)
    f_body  = pygame.font.SysFont("Helvetica Neue", 20)
    f_lbl   = pygame.font.SysFont("Helvetica Neue", 16)

    start_t = time.time()

    # Card geometry
    CW, CH = 440, 280
    CX2 = CX - CW // 2
    CY2 = CY - CH // 2 + 20

    pid_box = InputBox(CX2 + 20, CY2 + 72,  CW - 40, 50, "e.g.  P001")
    pin_box = InputBox(CX2 + 20, CY2 + 156, CW - 40, 50, "4-digit PIN", secret=True)
    btn_r   = pygame.Rect(CX2 + 20, CY2 + 224, CW - 40, 46)

    message = ""
    error_t = 0

    while True:
        clock.tick(FPS)
        now = time.time()
        t   = now - start_t

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()

            pid_box.handle_event(event)
            pin_box.handle_event(event)

            confirm = (
                (event.type == pygame.MOUSEBUTTONDOWN and btn_r.collidepoint(event.pos))
                or (event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN)
            )
            if confirm:
                pid = pid_box.text.strip().upper()
                pin = pin_box.text.strip()
                if not pid or not pin:
                    message = "Please enter your Participant ID and PIN."
                    error_t = now
                else:
                    participant = verify_participant(pid, pin)
                    if not participant:
                        message = "Incorrect ID or PIN — please try again."
                        error_t = now
                        pin_box.text = ""
                    elif participant["participant_id"] != config["participant_id"]:
                        message = "This ID doesn't match today's session. Ask your researcher."
                        error_t = now
                    else:
                        return participant

        if message and now - error_t > 3.5:
            message = ""

        # ── Draw ─────────────────────────────────────────────
        screen.fill(BG)

        # Dot grid
        for gx in range(0, W + 48, 48):
            for gy in range(0, H + 48, 48):
                pygame.draw.circle(screen, (20, 20, 40), (gx, gy), 1)

        # Glow
        pulse = 0.5 + 0.5 * math.sin(t * 1.0)
        for rad, alpha in [(140, 12), (96, 20), (62, 30)]:
            g = pygame.Surface((rad * 2, rad * 2), pygame.SRCALPHA)
            pygame.draw.circle(g, (*ACCENT, int(alpha * pulse)), (rad, rad), rad)
            screen.blit(g, (CX - rad, CY - 310 - rad))

        # Title
        ts = f_title.render("Grid-Sailing Task", True, WHITE)
        screen.blit(ts, (CX - ts.get_width() // 2, CY - 310))

        # Session badge
        badge_txt = f"Session {config['session_number']}"
        bs = f_lbl.render(badge_txt, True, ACCENT)
        bw = bs.get_width() + 24
        bx = CX - bw // 2
        pygame.draw.rect(screen, (20, 36, 80), (bx, CY - 262, bw, 26), border_radius=13)
        pygame.draw.rect(screen, ACCENT,       (bx, CY - 262, bw, 26), width=1, border_radius=13)
        screen.blit(bs, (CX - bs.get_width() // 2, CY - 258))

        # ── Login card ───────────────────────────────────────
        # Shadow
        pygame.draw.rect(screen, (4, 4, 10),
                         (CX2 + 4, CY2 + 6, CW, CH), border_radius=18)
        # Card
        pygame.draw.rect(screen, PANEL,  (CX2, CY2, CW, CH), border_radius=18)
        pygame.draw.rect(screen, BORDER, (CX2, CY2, CW, CH), width=1, border_radius=18)

        # Field labels
        lbl_pid = f_lbl.render("PARTICIPANT ID", True, DIM)
        screen.blit(lbl_pid, (CX2 + 20, CY2 + 20))

        pid_box.rect.topleft = (CX2 + 20, CY2 + 40)
        pid_box.draw(screen, f_body)

        lbl_pin = f_lbl.render("PIN", True, DIM)
        screen.blit(lbl_pin, (CX2 + 20, CY2 + 106))

        pin_box.rect.topleft = (CX2 + 20, CY2 + 124)
        pin_box.draw(screen, f_body)

        # Confirm button
        mouse = pygame.mouse.get_pos()
        hover = btn_r.collidepoint(mouse)
        bcol  = tuple(min(255, c + 24) for c in GREEN) if hover else GREEN
        pygame.draw.rect(screen, (4, 4, 10),
                         (btn_r.x + 2, btn_r.y + 3, btn_r.w, btn_r.h), border_radius=10)
        pygame.draw.rect(screen, bcol, btn_r, border_radius=10)
        bl = f_med.render("Confirm & Begin", True, (8, 8, 16))
        screen.blit(bl, (btn_r.x + btn_r.w // 2 - bl.get_width() // 2,
                          btn_r.y + btn_r.h // 2 - bl.get_height() // 2))

        # Error message
        if message:
            er = f_lbl.render(message, True, RED)
            screen.blit(er, (CX - er.get_width() // 2, CY2 + CH + 16))

        # Footer
        ft = f_lbl.render("Press Enter or click Confirm & Begin", True, (52, 52, 80))
        screen.blit(ft, (CX - ft.get_width() // 2, H - 34))

        pygame.display.flip()
