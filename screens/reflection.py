# ============================================================
#  GRID-SAILING TASK — Reflection Screen (MI Groups Only)
#
#  Shown after each practice session for motor imagery groups.
#  Implements the Effect-Engage-Evolve (3E) report card.
#
#  Fields:
#    1. What sensations did you imagine? (free text)
#    2. Imagery perspective (first-person / third-person / both)
#    3. Imagery modalities (visual / kinesthetic / auditory / other)
#    4. Overall engagement (1–5 scale)
#    5. Goal for next session (free text)
# ============================================================

import pygame
import sys
from config import WINDOW_WIDTH, WINDOW_HEIGHT, FPS
from database.db import save_reflection

# ── Colours ──────────────────────────────────────────────────
BG        = (15,  15,  25)
PANEL     = (25,  25,  40)
WHITE     = (235, 235, 245)
DIM       = (110, 110, 145)
ACCENT    = ( 90, 150, 255)
GREEN     = ( 70, 190, 110)
BORDER    = ( 55,  55,  80)
INPUT_BG  = ( 35,  35,  55)
INPUT_ACT = ( 45,  45,  70)
SELECTED  = ( 40,  80, 160)
RED       = (210,  65,  65)

PAD = 48


def draw_text(screen, font, text, color, x, y):
    surf = font.render(text, True, color)
    screen.blit(surf, (x, y))
    return surf.get_height()


def draw_centered(screen, font, text, color, y):
    surf = font.render(text, True, color)
    screen.blit(surf, (WINDOW_WIDTH // 2 - surf.get_width() // 2, y))
    return surf.get_height()


class MultiLineInput:
    """
    A multi-line text input box for free-text reflection responses.
    Supports word-wrap and scrolling within a fixed height.
    """

    def __init__(self, x, y, w, h, placeholder=""):
        self.rect        = pygame.Rect(x, y, w, h)
        self.text        = ""
        self.placeholder = placeholder
        self.active      = False
        self.line_height = 20

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key not in (pygame.K_TAB, pygame.K_ESCAPE):
                if len(self.text) < 500:
                    self.text += event.unicode

    def draw(self, screen, font):
        pygame.draw.rect(screen, INPUT_ACT if self.active else INPUT_BG,
                         self.rect, border_radius=6)
        pygame.draw.rect(screen, ACCENT if self.active else BORDER,
                         self.rect, width=1, border_radius=6)

        # Word-wrap text inside the box
        display = self.text if self.text else self.placeholder
        color   = WHITE if self.text else DIM
        words   = display.split(" ")
        lines   = []
        line    = ""
        max_w   = self.rect.w - 20

        for word in words:
            test = (line + " " + word).strip()
            if font.size(test)[0] <= max_w:
                line = test
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)

        # Draw only as many lines as fit in the box
        y = self.rect.y + 8
        for ln in lines:
            if y + self.line_height > self.rect.bottom - 4:
                break
            surf = font.render(ln, True, color)
            screen.blit(surf, (self.rect.x + 10, y))
            y += self.line_height


class ToggleGroup:
    """A horizontal set of toggle buttons where one or more can be selected."""

    def __init__(self, x, y, options, multi=False):
        self.x        = x
        self.y        = y
        self.options  = options
        self.multi    = multi        # if True, multiple can be selected
        self.selected = set()
        self.btn_w    = 155
        self.btn_h    = 34
        self.gap      = 8
        self._build_rects()

    def _build_rects(self):
        self.rects = []
        for i in range(len(self.options)):
            self.rects.append(pygame.Rect(
                self.x + i * (self.btn_w + self.gap),
                self.y, self.btn_w, self.btn_h
            ))

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            for i, rect in enumerate(self.rects):
                if rect.collidepoint(event.pos):
                    if self.multi:
                        if i in self.selected:
                            self.selected.discard(i)
                        else:
                            self.selected.add(i)
                    else:
                        self.selected = {i}

    def draw(self, screen, font):
        for i, (opt, rect) in enumerate(zip(self.options, self.rects)):
            active = i in self.selected
            bg     = SELECTED if active else INPUT_BG
            border = ACCENT   if active else BORDER
            pygame.draw.rect(screen, bg,     rect, border_radius=7)
            pygame.draw.rect(screen, border, rect, width=1, border_radius=7)
            col  = WHITE if active else DIM
            lbl  = font.render(opt, True, col)
            screen.blit(lbl, (rect.x + rect.w // 2 - lbl.get_width() // 2,
                               rect.y + rect.h // 2 - lbl.get_height() // 2))

    @property
    def value(self):
        """Return selected option(s) as a comma-separated string."""
        vals = [self.options[i] for i in sorted(self.selected)]
        return ", ".join(vals) if vals else ""


class StarRating:
    """A 1–5 clickable star/number rating widget."""

    def __init__(self, x, y, n=5):
        self.x      = x
        self.y      = y
        self.n      = n
        self.rating = 0
        self.size   = 42
        self.gap    = 8
        self.rects  = [
            pygame.Rect(x + i * (self.size + self.gap), y, self.size, self.size)
            for i in range(n)
        ]

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            for i, rect in enumerate(self.rects):
                if rect.collidepoint(event.pos):
                    self.rating = i + 1

    def draw(self, screen, font):
        for i, rect in enumerate(self.rects):
            active = i < self.rating
            bg     = SELECTED if active else INPUT_BG
            border = ACCENT   if active else BORDER
            pygame.draw.rect(screen, bg,     rect, border_radius=8)
            pygame.draw.rect(screen, border, rect, width=1, border_radius=8)
            lbl = font.render(str(i + 1), True, WHITE if active else DIM)
            screen.blit(lbl, (rect.x + rect.w // 2 - lbl.get_width() // 2,
                               rect.y + rect.h // 2 - lbl.get_height() // 2))

        # Labels below
        low  = font.render("Low", True, DIM)
        high = font.render("High", True, DIM)
        screen.blit(low,  (self.x, self.y + self.size + 4))
        screen.blit(high, (self.rects[-1].right - high.get_width(),
                            self.y + self.size + 4))


# ── Main reflection screen ────────────────────────────────────

def run_reflection(screen, clock, fonts, participant_id: str,
                   session_number: int, is_last_session: bool):
    """
    Display the 3E reflection report card for MI group participants.

    Args:
        screen:           Pygame display surface.
        clock:            Pygame clock.
        fonts:            Tuple (f_big, f_med, f_sm, f_xs).
        participant_id:   Who is completing the reflection.
        session_number:   Current session (1, 2, or 3).
        is_last_session:  If True, suppress the "next session goal" field.
    """
    f_big, f_med, f_sm, f_xs = fonts

    cx = WINDOW_WIDTH // 2

    # ── Widgets ──────────────────────────────────────────────
    content_box = MultiLineInput(
        PAD, 130, WINDOW_WIDTH - PAD * 2, 80,
        "Describe what you imagined during practice — "
        "sensations, sounds, feelings of movement..."
    )

    perspective_toggle = ToggleGroup(
        PAD, 270,
        ["First-person", "Third-person", "Both"],
        multi=False
    )

    modality_toggle = ToggleGroup(
        PAD, 340,
        ["Visual", "Kinesthetic", "Auditory", "Other"],
        multi=True
    )

    engagement_rating = StarRating(PAD, 415)

    goal_box = MultiLineInput(
        PAD, 530, WINDOW_WIDTH - PAD * 2, 65,
        "Set one imagery goal for your next session..."
    ) if not is_last_session else None

    submit_rect = pygame.Rect(cx - 120, WINDOW_HEIGHT - 58, 240, 40)
    message     = ""

    while True:
        clock.tick(FPS)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()

            content_box.handle_event(event)
            perspective_toggle.handle_event(event)
            modality_toggle.handle_event(event)
            engagement_rating.handle_event(event)
            if goal_box:
                goal_box.handle_event(event)

            if event.type == pygame.MOUSEBUTTONDOWN:
                if submit_rect.collidepoint(event.pos):
                    # Validate required fields
                    if not content_box.text.strip():
                        message = "Please describe your imagery experience before submitting."
                    elif not perspective_toggle.value:
                        message = "Please select an imagery perspective."
                    elif not modality_toggle.value:
                        message = "Please select at least one modality."
                    elif engagement_rating.rating == 0:
                        message = "Please rate your engagement level."
                    else:
                        # Save to database
                        save_reflection(
                            participant_id   = participant_id,
                            session_number   = session_number,
                            imagery_content  = content_box.text.strip(),
                            perspective      = perspective_toggle.value,
                            modalities       = modality_toggle.value,
                            engagement_score = engagement_rating.rating,
                            next_session_goal= goal_box.text.strip() if goal_box else "",
                        )
                        return  # done

        # ── Draw ─────────────────────────────────────────────
        screen.fill(BG)

        # Header
        draw_centered(screen, f_med, "Effect-Engage-Evolve  |  Reflection Report Card",
                      ACCENT, 18)
        draw_centered(screen, f_xs,
                      f"Session {session_number}  —  {participant_id}",
                      DIM, 48)

        pygame.draw.line(screen, BORDER, (PAD, 70), (WINDOW_WIDTH - PAD, 70))

        # ── Q1: Imagery content ───────────────────────────────
        draw_text(screen, f_sm,
                  "1.  What sensations did you imagine during practice?",
                  WHITE, PAD, 80)
        content_box.draw(screen, f_xs)

        # ── Q2: Perspective ───────────────────────────────────
        draw_text(screen, f_sm, "2.  Imagery perspective", WHITE, PAD, 228)
        perspective_toggle.draw(screen, f_xs)

        # ── Q3: Modalities ────────────────────────────────────
        draw_text(screen, f_sm, "3.  Modalities  (select all that apply)",
                  WHITE, PAD, 300)
        modality_toggle.draw(screen, f_xs)

        # ── Q4: Engagement ────────────────────────────────────
        draw_text(screen, f_sm, "4.  Overall engagement during imagery",
                  WHITE, PAD, 376)
        engagement_rating.draw(screen, f_xs)

        # ── Q5: Next session goal ─────────────────────────────
        if goal_box:
            draw_text(screen, f_sm,
                      "5.  Set one imagery goal for your next session",
                      WHITE, PAD, 492)
            goal_box.draw(screen, f_xs)

        # ── Validation message ────────────────────────────────
        if message:
            msg = f_xs.render(message, True, RED)
            screen.blit(msg, (cx - msg.get_width() // 2, WINDOW_HEIGHT - 70))

        # ── Submit button ─────────────────────────────────────
        pygame.draw.rect(screen, GREEN, submit_rect, border_radius=10)
        btn = f_sm.render("Submit Reflection", True, BG)
        screen.blit(btn, (submit_rect.x + submit_rect.w // 2 - btn.get_width() // 2,
                           submit_rect.y + submit_rect.h // 2 - btn.get_height() // 2))

        pygame.display.flip()
