# ============================================================
#  GRID-SAILING TASK — Participant Login Screen
#
#  Shown after the researcher setup screen.
#  Participant enters their ID and PIN to confirm identity
#  before the session begins.
# ============================================================

import pygame
import sys
from config import WINDOW_WIDTH, WINDOW_HEIGHT, FPS
from database.db import verify_participant

# ── Colours ──────────────────────────────────────────────────
BG       = (15,  15,  25)
WHITE    = (235, 235, 245)
DIM      = (110, 110, 145)
ACCENT   = ( 90, 150, 255)
GREEN    = ( 70, 190, 110)
RED      = (210,  65,  65)
INPUT_BG = (35,  35,  55)
INPUT_ACT= (45,  45,  70)
BORDER   = (55,  55,  80)


def draw_centered(screen, font, text, color, y):
    surf = screen.get_surface() if hasattr(screen, 'get_surface') else screen
    s = font.render(text, True, color)
    screen.blit(s, (WINDOW_WIDTH // 2 - s.get_width() // 2, y))
    return s.get_height()


class InputBox:
    """Reusable single-line input box."""

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
                if len(self.text) < 20:
                    self.text += event.unicode

    def draw(self, screen, font):
        pygame.draw.rect(screen, INPUT_ACT if self.active else INPUT_BG,
                         self.rect, border_radius=8)
        pygame.draw.rect(screen, ACCENT if self.active else BORDER,
                         self.rect, width=2, border_radius=8)
        display = ("*" * len(self.text)) if self.secret else self.text
        txt = font.render(display if display else self.placeholder,
                          True, WHITE if display else DIM)
        screen.blit(txt, (self.rect.x + 14,
                           self.rect.y + self.rect.h // 2 - txt.get_height() // 2))


def run_participant_login(config: dict) -> dict | None:
    """
    Show the participant login screen.

    Args:
        config (dict): The session config returned by researcher_setup.

    Returns:
        dict: The verified participant record, or None if quit.
    """
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Grid-Sailing Task")
    clock  = pygame.time.Clock()

    f_big = pygame.font.SysFont("Arial", 30, bold=True)
    f_med = pygame.font.SysFont("Arial", 18, bold=True)
    f_sm  = pygame.font.SysFont("Arial", 15)
    f_xs  = pygame.font.SysFont("Arial", 13)

    cx = WINDOW_WIDTH // 2

    pid_box = InputBox(cx - 130, 310, 260, 44, "Your participant ID")
    pin_box = InputBox(cx - 130, 380, 260, 44, "Your 4-digit PIN", secret=True)

    confirm_rect = pygame.Rect(cx - 110, 450, 220, 44)
    message      = ""
    message_col  = RED

    while True:
        clock.tick(FPS)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            pid_box.handle_event(event)
            pin_box.handle_event(event)

            clicked_confirm = (
                event.type == pygame.MOUSEBUTTONDOWN
                and confirm_rect.collidepoint(event.pos)
            )
            pressed_enter = (
                event.type == pygame.KEYDOWN
                and event.key == pygame.K_RETURN
            )

            if clicked_confirm or pressed_enter:
                pid = pid_box.text.strip().upper()
                pin = pin_box.text.strip()
                if not pid or not pin:
                    message = "Please enter your ID and PIN."
                else:
                    participant = verify_participant(pid, pin)
                    if participant:
                        # Make sure participant matches researcher config
                        if participant["participant_id"] != config["participant_id"]:
                            message = "ID does not match this session. Ask the researcher."
                        else:
                            pygame.quit()
                            return participant
                    else:
                        message     = "Incorrect ID or PIN. Please try again."
                        message_col = RED
                        pin_box.text = ""

        # ── Draw ─────────────────────────────────────────────
        screen.fill(BG)

        # Header
        s = f_big.render("Grid-Sailing Task", True, WHITE)
        screen.blit(s, (cx - s.get_width() // 2, 120))

        s2 = f_sm.render("Please enter your participant ID and PIN to begin.", True, DIM)
        screen.blit(s2, (cx - s2.get_width() // 2, 175))

        # Session info pill
        session_text = f"Session {config['session_number']}  |  Group: {config['group']}"
        pill_surf = f_xs.render(session_text, True, ACCENT)
        pill_rect = pygame.Rect(cx - pill_surf.get_width() // 2 - 14, 210,
                                pill_surf.get_width() + 28, 28)
        pygame.draw.rect(screen, (30, 50, 90), pill_rect, border_radius=14)
        pygame.draw.rect(screen, ACCENT, pill_rect, width=1, border_radius=14)
        screen.blit(pill_surf, (cx - pill_surf.get_width() // 2, 217))

        # Labels and inputs
        lbl1 = f_sm.render("Participant ID", True, DIM)
        screen.blit(lbl1, (cx - 130, 290))
        pid_box.draw(screen, f_med)

        lbl2 = f_sm.render("PIN", True, DIM)
        screen.blit(lbl2, (cx - 130, 362))
        pin_box.draw(screen, f_med)

        # Confirm button
        pygame.draw.rect(screen, GREEN, confirm_rect, border_radius=10)
        btn_lbl = f_med.render("Confirm & Begin", True, BG := (15, 15, 25))
        screen.blit(btn_lbl, (confirm_rect.x + confirm_rect.w // 2 - btn_lbl.get_width() // 2,
                               confirm_rect.y + confirm_rect.h // 2 - btn_lbl.get_height() // 2))

        # Error / status message
        if message:
            msg = f_sm.render(message, True, message_col)
            screen.blit(msg, (cx - msg.get_width() // 2, 510))

        # Footer hint
        hint = f_xs.render("Press Enter or click Confirm", True, (60, 60, 90))
        screen.blit(hint, (cx - hint.get_width() // 2, WINDOW_HEIGHT - 35))

        pygame.display.flip()


if __name__ == "__main__":
    # Quick test with a mock config
    mock_config = {"participant_id": "P001", "group": "MI-High", "session_number": 1}
    result = run_participant_login(mock_config)
    print("Logged in as:", result)
