# ============================================================
#  GRID-SAILING TASK — Participant Login Screen
#
#  Shown after researcher setup. Participant enters their ID
#  and PIN. This is the ONLY screen participants see — they
#  never interact with any researcher config.
# ============================================================

import pygame
import sys
import math
import time
from config import WINDOW_WIDTH, WINDOW_HEIGHT, FPS
from database.db import verify_participant

BG        = (10,  10,  20)
PANEL     = (22,  22,  38)
BORDER    = (52,  52,  80)
WHITE     = (228, 228, 242)
DIM       = (100, 100, 138)
ACCENT    = ( 88, 148, 255)
GREEN     = ( 58, 196, 108)
RED       = (212,  58,  58)
INPUT_BG  = (28,  28,  48)
INPUT_ACT = (36,  36,  60)

W  = WINDOW_WIDTH
H  = WINDOW_HEIGHT
CX = W // 2
CY = H // 2


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
        pygame.draw.rect(screen, bg, self.rect, border_radius=8)
        pygame.draw.rect(screen, bc, self.rect, width=1, border_radius=8)
        if self.active:
            pygame.draw.rect(screen, ACCENT,
                             (self.rect.x, self.rect.y + 8, 2, self.rect.h - 16))
        display = ("•" * len(self.text)) if self.secret else self.text
        txt = font.render(display if display else self.placeholder,
                          True, WHITE if display else DIM)
        screen.blit(txt, (self.rect.x + 14,
                           self.rect.y + self.rect.h // 2 - txt.get_height() // 2))


def run_participant_login(screen, clock, fonts, config: dict):
    """
    Show the participant-facing login screen.

    Args:
        screen, clock: shared pygame objects from main
        fonts:         font tuple (f_big, f_med, f_sm, f_xs)
        config (dict): session config set by researcher

    Returns:
        dict: verified participant record, or None if quit
    """
    f_big, f_med, f_sm, f_xs = fonts
    pygame.display.set_caption("Grid-Sailing Task")

    start_t = time.time()

    pid_box = InputBox(CX - 150, CY - 40,  300, 48, "e.g.  P001")
    pin_box = InputBox(CX - 150, CY + 28,  300, 48, "4-digit PIN", secret=True)
    btn_r   = pygame.Rect(CX - 130, CY + 98, 260, 48)

    message     = ""
    message_col = RED
    error_t     = 0

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
                    message = "Please enter your ID and PIN."
                    error_t = now
                else:
                    participant = verify_participant(pid, pin)
                    if not participant:
                        message = "Incorrect ID or PIN. Please try again."
                        error_t = now
                        pin_box.text = ""
                    elif participant["participant_id"] != config["participant_id"]:
                        message = "This ID doesn't match today's session. Ask your researcher."
                        error_t = now
                    else:
                        return participant

        if message and now - error_t > 3:
            message = ""

        # ── Draw ─────────────────────────────────────────────
        screen.fill(BG)

        # Subtle animated background
        for gx in range(0, W + 48, 48):
            for gy in range(0, H + 48, 48):
                pygame.draw.circle(screen, (24, 24, 44), (gx, gy), 1)

        # Glow
        pulse = 0.5 + 0.5 * math.sin(t * 1.1)
        for rad, alpha in [(110, 16), (75, 26), (48, 38)]:
            g = pygame.Surface((rad*2, rad*2), pygame.SRCALPHA)
            pygame.draw.circle(g, (*ACCENT, int(alpha * pulse)), (rad, rad), rad)
            screen.blit(g, (CX - rad, CY - 250 - rad))

        # Title
        ts = f_big.render("Grid-Sailing Task", True, WHITE)
        screen.blit(ts, (CX - ts.get_width() // 2, CY - 270))

        # Session badge
        badge_txt = f"Session {config['session_number']}"
        bs = f_xs.render(badge_txt, True, ACCENT)
        bw = bs.get_width() + 20
        pygame.draw.rect(screen, (28, 44, 88), (CX - bw//2, CY - 228, bw, 26), border_radius=13)
        pygame.draw.rect(screen, ACCENT,       (CX - bw//2, CY - 228, bw, 26), width=1, border_radius=13)
        screen.blit(bs, (CX - bs.get_width()//2, CY - 224))

        # Login card
        card_w, card_h = 380, 240
        card_x = CX - card_w // 2
        card_y = CY - 72
        pygame.draw.rect(screen, PANEL,  (card_x, card_y, card_w, card_h), border_radius=16)
        pygame.draw.rect(screen, BORDER, (card_x, card_y, card_w, card_h), width=1, border_radius=16)

        # Card labels + inputs
        _lbl(screen, f_xs, "Participant ID", CX - 150, card_y + 14)
        pid_box.rect.y = card_y + 34;  pid_box.draw(screen, f_sm)

        _lbl(screen, f_xs, "PIN",          CX - 150, card_y + 96)
        pin_box.rect.y = card_y + 114; pin_box.draw(screen, f_sm)

        # Confirm button
        mouse = pygame.mouse.get_pos()
        bcol  = tuple(min(255, c + 22) for c in GREEN) if btn_r.collidepoint(mouse) else GREEN
        btn_r.y = card_y + 182
        pygame.draw.rect(screen, (8, 8, 16), (btn_r.x+2, btn_r.y+3, btn_r.w, btn_r.h), border_radius=10)
        pygame.draw.rect(screen, bcol, btn_r, border_radius=10)
        bl = f_sm.render("Confirm & Begin", True, BG := (10, 10, 20))
        screen.blit(bl, (btn_r.x + btn_r.w//2 - bl.get_width()//2,
                          btn_r.y + btn_r.h//2 - bl.get_height()//2))

        # Error message
        if message:
            er = f_xs.render(message, True, RED)
            screen.blit(er, (CX - er.get_width()//2, card_y + card_h + 16))

        # Footer
        ft = f_xs.render("Press Enter or click Confirm & Begin", True, DIM)
        screen.blit(ft, (CX - ft.get_width()//2, H - 36))

        pygame.display.flip()


def _lbl(screen, font, text, x, y):
    s = font.render(text, True, DIM)
    screen.blit(s, (x, y))
