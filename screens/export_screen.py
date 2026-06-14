# ============================================================
#  GRID-SAILING TASK — Export Screen
#
#  Accessible from the researcher setup screen.
#  Juliet can export data without touching the terminal.
#
#  Options:
#    1. Export single participant (by ID)
#    2. Export all participants
#    3. Export trial summary (no keypress rows)
# ============================================================

import pygame
import sys
from config import WINDOW_WIDTH, WINDOW_HEIGHT, FPS
from database.db import get_all_participants
from export.exporter import export_participant, export_all, export_summary

BG       = (15,  15,  25)
WHITE    = (235, 235, 245)
DIM      = (110, 110, 145)
ACCENT   = ( 90, 150, 255)
GREEN    = ( 70, 190, 110)
ORANGE   = (230, 140,  50)
RED      = (210,  65,  65)
BORDER   = ( 55,  55,  80)
INPUT_BG = ( 35,  35,  55)
INPUT_ACT= ( 45,  45,  70)
PAD      = 48


def draw_text(screen, font, text, color, x, y):
    surf = font.render(text, True, color)
    screen.blit(surf, (x, y))


class Button:
    def __init__(self, x, y, w, h, label, color=ACCENT, sub=""):
        self.rect  = pygame.Rect(x, y, w, h)
        self.label = label
        self.color = color
        self.sub   = sub   # small subtitle under the label

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            return self.rect.collidepoint(event.pos)
        return False

    def draw(self, screen, f_med, f_xs):
        pygame.draw.rect(screen, self.color, self.rect, border_radius=10)
        lbl = f_med.render(self.label, True, BG)
        screen.blit(lbl, (self.rect.x + self.rect.w // 2 - lbl.get_width() // 2,
                           self.rect.y + 10))
        if self.sub:
            sub = f_xs.render(self.sub, True, (20, 20, 35))
            screen.blit(sub, (self.rect.x + self.rect.w // 2 - sub.get_width() // 2,
                               self.rect.y + 34))


class InputBox:
    def __init__(self, x, y, w, h, placeholder=""):
        self.rect        = pygame.Rect(x, y, w, h)
        self.text        = ""
        self.placeholder = placeholder
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
                         self.rect, border_radius=6)
        pygame.draw.rect(screen, ACCENT if self.active else BORDER,
                         self.rect, width=1, border_radius=6)
        txt = font.render(
            self.text if self.text else self.placeholder,
            True, WHITE if self.text else DIM
        )
        screen.blit(txt, (self.rect.x + 10,
                           self.rect.y + self.rect.h // 2 - txt.get_height() // 2))


def run_export_screen(screen, clock, fonts):
    """
    Show the data export screen for Juliet.
    Returns when the user presses ESC or Back.
    """
    f_big, f_med, f_sm, f_xs = fonts
    cx = WINDOW_WIDTH // 2

    pid_box = InputBox(cx - 130, 220, 200, 36, "e.g. P001")

    btn_single  = Button(cx - 230, 270, 200, 58, "Export Participant",
                         ACCENT, "One participant — full keypresses")
    btn_all     = Button(cx + 30,  270, 200, 58, "Export All",
                         ORANGE,  "All participants — full keypresses")
    btn_summary = Button(cx - 100, 355, 200, 58, "Trial Summary",
                         GREEN,   "All participants — trials only")
    btn_back    = Button(PAD, WINDOW_HEIGHT - 58, 120, 38, "Back", DIM)

    message     = ""
    msg_color   = GREEN

    # List of registered participants
    participants = [p["participant_id"] for p in get_all_participants()]

    while True:
        clock.tick(FPS)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return

            pid_box.handle_event(event)

            if btn_single.handle_event(event):
                pid = pid_box.text.strip().upper()
                if not pid:
                    message   = "Enter a participant ID first."
                    msg_color = RED
                elif pid not in participants:
                    message   = f"'{pid}' not found in database."
                    msg_color = RED
                else:
                    path      = export_participant(pid)
                    message   = f"Saved: {path}"
                    msg_color = GREEN

            if btn_all.handle_event(event):
                path      = export_all()
                message   = f"Saved: {path}"
                msg_color = GREEN

            if btn_summary.handle_event(event):
                path      = export_summary()
                message   = f"Saved: {path}"
                msg_color = GREEN

            if btn_back.handle_event(event):
                return

        # ── Draw ─────────────────────────────────────────────
        screen.fill(BG)

        draw_text(screen, f_big, "Data Export", WHITE, PAD, 28)
        draw_text(screen, f_sm,
                  "All files are saved to the  exports/  folder.",
                  DIM, PAD, 68)

        # Registered participants list
        draw_text(screen, f_sm, "Registered participants:", DIM, PAD, 108)
        p_list = "  |  ".join(participants) if participants else "None yet"
        draw_text(screen, f_xs, p_list, ACCENT, PAD, 132)

        # Single participant export
        draw_text(screen, f_sm, "Participant ID:", DIM, PAD, 228)
        pid_box.draw(screen, f_sm)

        btn_single.draw(screen, f_sm, f_xs)
        btn_all.draw(screen, f_sm, f_xs)
        btn_summary.draw(screen, f_sm, f_xs)
        btn_back.draw(screen, f_sm, f_xs)

        # Export format note
        draw_text(screen, f_xs,
                  "Full export: one row per key press, joined with trial + participant metadata.",
                  DIM, PAD, 430)
        draw_text(screen, f_xs,
                  "Trial summary: one row per trial — faster to open in R for quick analysis.",
                  DIM, PAD, 450)

        # Status message
        if message:
            msg = f_xs.render(message, True, msg_color)
            screen.blit(msg, (cx - msg.get_width() // 2, WINDOW_HEIGHT - 70))

        pygame.display.flip()
