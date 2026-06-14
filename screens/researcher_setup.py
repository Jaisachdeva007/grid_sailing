# ============================================================
#  GRID-SAILING TASK — Researcher Setup Screen
#
#  Juliet sees this screen before every session.
#  She can configure the experiment and register or select
#  a participant before handing the laptop over.
#
#  Sections:
#    1. Participant — new or returning
#    2. Group assignment
#    3. Session selection
#    4. Timing overrides
#    5. Grid ratio override
#    6. Launch button
# ============================================================

import pygame
import sys
from config import (
    WINDOW_WIDTH, WINDOW_HEIGHT, GROUPS, SESSION_STRUCTURE,
    PLANNING_TIME_SEC, ACTION_TIME_SEC, FEEDBACK_TIME_SEC, INTERTRIAL_SEC,
    PRACTICE_REPEATED_RATIO, TEST_REPEATED_RATIO, FPS
)
from database.db import (
    initialise_database, get_all_participants,
    create_participant, verify_participant
)

# ── Colours ──────────────────────────────────────────────────
BG          = (15,  15,  25)
PANEL       = (28,  28,  45)
BORDER      = (55,  55,  80)
WHITE       = (235, 235, 245)
DIM         = (110, 110, 145)
ACCENT      = ( 90, 150, 255)
GREEN       = ( 70, 190, 110)
RED         = (210,  65,  65)
ORANGE      = (230, 140,  50)
INPUT_BG    = (35,  35,  55)
INPUT_ACT   = (45,  45,  70)
SELECTED    = ( 40,  80, 160)

# ── Layout ───────────────────────────────────────────────────
PAD   = 32
COL1  = PAD
COL2  = WINDOW_WIDTH // 2 + 10


def draw_text(screen, font, text, color, x, y):
    surf = font.render(text, True, color)
    screen.blit(surf, (x, y))
    return surf.get_width(), surf.get_height()


def draw_section_header(screen, font, text, y):
    """Draw a labelled section divider line."""
    surf = font.render(text.upper(), True, ACCENT)
    screen.blit(surf, (PAD, y))
    pygame.draw.line(screen, BORDER,
                     (PAD + surf.get_width() + 10, y + surf.get_height() // 2),
                     (WINDOW_WIDTH - PAD, y + surf.get_height() // 2))
    return surf.get_height() + 10


class InputBox:
    """A single-line text input box."""

    def __init__(self, x, y, w, h, placeholder="", secret=False):
        self.rect      = pygame.Rect(x, y, w, h)
        self.text      = ""
        self.placeholder = placeholder
        self.secret    = secret      # if True, display as ****
        self.active    = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key not in (pygame.K_RETURN, pygame.K_TAB, pygame.K_ESCAPE):
                if len(self.text) < 40:
                    self.text += event.unicode

    def draw(self, screen, font):
        color  = INPUT_ACT if self.active else INPUT_BG
        pygame.draw.rect(screen, color, self.rect, border_radius=6)
        pygame.draw.rect(screen, ACCENT if self.active else BORDER,
                         self.rect, width=1, border_radius=6)
        display = ("*" * len(self.text)) if self.secret else self.text
        if display:
            txt = font.render(display, True, WHITE)
        else:
            txt = font.render(self.placeholder, True, DIM)
        screen.blit(txt, (self.rect.x + 10, self.rect.y + self.rect.h // 2 - txt.get_height() // 2))


class Dropdown:
    """A simple single-select dropdown."""

    def __init__(self, x, y, w, h, options):
        self.rect     = pygame.Rect(x, y, w, h)
        self.options  = options
        self.selected = 0
        self.open     = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos):
                self.open = not self.open
            elif self.open:
                for i, opt_rect in enumerate(self._option_rects()):
                    if opt_rect.collidepoint(event.pos):
                        self.selected = i
                        self.open = False
                        return
                self.open = False

    def _option_rects(self):
        rects = []
        for i in range(len(self.options)):
            rects.append(pygame.Rect(
                self.rect.x, self.rect.y + self.rect.h * (i + 1),
                self.rect.w, self.rect.h
            ))
        return rects

    @property
    def value(self):
        return self.options[self.selected]

    def draw(self, screen, font):
        pygame.draw.rect(screen, INPUT_BG, self.rect, border_radius=6)
        pygame.draw.rect(screen, BORDER, self.rect, width=1, border_radius=6)
        lbl = font.render(str(self.value), True, WHITE)
        screen.blit(lbl, (self.rect.x + 10, self.rect.y + self.rect.h // 2 - lbl.get_height() // 2))
        # Arrow indicator
        arrow = font.render("v", True, DIM)
        screen.blit(arrow, (self.rect.right - 24, self.rect.y + self.rect.h // 2 - arrow.get_height() // 2))

        if self.open:
            for i, (opt, opt_rect) in enumerate(zip(self.options, self._option_rects())):
                bg = SELECTED if i == self.selected else INPUT_BG
                pygame.draw.rect(screen, bg, opt_rect, border_radius=4)
                pygame.draw.rect(screen, BORDER, opt_rect, width=1, border_radius=4)
                t = font.render(str(opt), True, WHITE)
                screen.blit(t, (opt_rect.x + 10, opt_rect.y + opt_rect.h // 2 - t.get_height() // 2))


class NumericInput:
    """A small +/- numeric stepper for timing/ratio overrides."""

    def __init__(self, x, y, value, min_val, max_val, step=0.5, fmt=".1f"):
        self.x, self.y   = x, y
        self.value        = value
        self.min_val      = min_val
        self.max_val      = max_val
        self.step         = step
        self.fmt          = fmt
        self.btn_w        = 28
        self.val_w        = 70
        self.h            = 30
        self.minus_rect   = pygame.Rect(x, y, self.btn_w, self.h)
        self.plus_rect    = pygame.Rect(x + self.btn_w + self.val_w + 4, y, self.btn_w, self.h)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.minus_rect.collidepoint(event.pos):
                self.value = max(self.min_val, round(self.value - self.step, 2))
            if self.plus_rect.collidepoint(event.pos):
                self.value = min(self.max_val, round(self.value + self.step, 2))

    def draw(self, screen, font):
        for rect, label in [(self.minus_rect, "-"), (self.plus_rect, "+")]:
            pygame.draw.rect(screen, INPUT_BG, rect, border_radius=5)
            pygame.draw.rect(screen, BORDER, rect, width=1, border_radius=5)
            lbl = font.render(label, True, WHITE)
            screen.blit(lbl, (rect.x + rect.w // 2 - lbl.get_width() // 2,
                               rect.y + rect.h // 2 - lbl.get_height() // 2))
        val_rect = pygame.Rect(self.x + self.btn_w + 2, self.y, self.val_w, self.h)
        pygame.draw.rect(screen, INPUT_BG, val_rect, border_radius=5)
        val_str = format(self.value, self.fmt)
        val_lbl = font.render(val_str, True, ACCENT)
        screen.blit(val_lbl, (val_rect.x + val_rect.w // 2 - val_lbl.get_width() // 2,
                               val_rect.y + val_rect.h // 2 - val_lbl.get_height() // 2))


class Button:
    """A clickable button."""

    def __init__(self, x, y, w, h, label, color=ACCENT):
        self.rect  = pygame.Rect(x, y, w, h)
        self.label = label
        self.color = color

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            return self.rect.collidepoint(event.pos)
        return False

    def draw(self, screen, font):
        pygame.draw.rect(screen, self.color, self.rect, border_radius=8)
        lbl = font.render(self.label, True, BG)
        screen.blit(lbl, (self.rect.x + self.rect.w // 2 - lbl.get_width() // 2,
                           self.rect.y + self.rect.h // 2 - lbl.get_height() // 2))


# ── Main setup screen ────────────────────────────────────────

def run_researcher_setup():
    """
    Display the researcher configuration screen.

    Returns:
        dict: All configuration values needed to start a session, or None if quit.
        Keys: participant_id, group, session_number, planning_time,
              action_time, feedback_time, intertrial_time,
              practice_ratio, test_ratio, is_new_participant
    """
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Grid-Sailing — Researcher Setup")
    clock  = pygame.time.Clock()

    initialise_database()

    f_big = pygame.font.SysFont("Arial", 22, bold=True)
    f_med = pygame.font.SysFont("Arial", 16, bold=True)
    f_sm  = pygame.font.SysFont("Arial", 14)
    f_xs  = pygame.font.SysFont("Arial", 12)

    # ── Mode toggle: New vs Returning ────────────────────────
    mode = "new"   # "new" or "returning"

    # ── Section 1: New participant inputs ────────────────────
    pid_box   = InputBox(COL1 + 160, 90,  180, 32, "e.g. P001")
    pin_box   = InputBox(COL1 + 160, 130, 180, 32, "4-digit PIN", secret=True)
    age_box   = InputBox(COL2 + 120, 90,  100, 32, "e.g. 22")
    gender_dd = Dropdown(COL2 + 120, 130, 160, 32,
                         ["Female", "Male", "Non-binary", "Other", "Prefer not to say"])
    hand_dd   = Dropdown(COL2 + 120, 170, 160, 32, ["Right", "Left", "Ambidextrous"])

    # ── Section 1: Returning participant inputs ───────────────
    ret_pid_box = InputBox(COL1 + 160, 90,  180, 32, "Participant ID")
    ret_pin_box = InputBox(COL1 + 160, 130, 180, 32, "PIN", secret=True)

    # ── Section 2: Group assignment ──────────────────────────
    group_dd = Dropdown(COL1 + 160, 250, 200, 32, GROUPS)

    # ── Section 3: Session selection ─────────────────────────
    session_dd = Dropdown(COL1 + 160, 330, 100, 32, [1, 2, 3])

    # ── Section 4: Timing overrides ──────────────────────────
    planning_input   = NumericInput(COL1 + 160, 410, PLANNING_TIME_SEC,   4, 12, step=1, fmt=".0f")
    action_input     = NumericInput(COL1 + 160, 448, ACTION_TIME_SEC,     5, 20, step=1, fmt=".0f")
    feedback_input   = NumericInput(COL2 + 120, 410, FEEDBACK_TIME_SEC,   1,  5, step=1, fmt=".0f")
    intertrial_input = NumericInput(COL2 + 120, 448, INTERTRIAL_SEC,      2, 10, step=1, fmt=".0f")

    # ── Section 5: Grid ratio overrides ──────────────────────
    practice_ratio_input = NumericInput(COL1 + 200, 528, PRACTICE_REPEATED_RATIO * 100, 50, 100, step=4, fmt=".0f")
    test_ratio_input     = NumericInput(COL2 + 120,  528, TEST_REPEATED_RATIO * 100,     40, 80,  step=4, fmt=".0f")

    # ── Buttons ──────────────────────────────────────────────
    new_btn       = Button(PAD,       55, 120, 28, "New Participant", ACCENT)
    return_btn    = Button(PAD + 135, 55, 140, 28, "Returning",       DIM)
    launch_btn    = Button(WINDOW_WIDTH // 2 - 120, WINDOW_HEIGHT - 60, 240, 40, "Launch Session", GREEN)

    # ── State ────────────────────────────────────────────────
    message     = ""
    message_col = RED

    all_inputs = [pid_box, pin_box, age_box, ret_pid_box, ret_pin_box]
    all_widgets = [gender_dd, hand_dd, group_dd, session_dd,
                   planning_input, action_input, feedback_input, intertrial_input,
                   practice_ratio_input, test_ratio_input]

    while True:
        clock.tick(FPS)
        events = pygame.event.get()

        for event in events:
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            # Mode toggle buttons
            if new_btn.handle_event(event):
                mode = "new"
                message = ""
            if return_btn.handle_event(event):
                mode = "returning"
                message = ""

            # Input events
            for box in all_inputs:
                box.handle_event(event)
            for w in all_widgets:
                w.handle_event(event)

            # Launch button
            if launch_btn.handle_event(event):
                result = _validate_and_launch(
                    mode, pid_box, pin_box, age_box, gender_dd, hand_dd,
                    ret_pid_box, ret_pin_box,
                    group_dd, session_dd,
                    planning_input, action_input, feedback_input, intertrial_input,
                    practice_ratio_input, test_ratio_input
                )
                if isinstance(result, str):
                    message     = result
                    message_col = RED
                elif isinstance(result, dict):
                    pygame.quit()
                    return result

        # ── Draw ─────────────────────────────────────────────
        screen.fill(BG)

        # Title
        draw_text(screen, f_big, "Grid-Sailing Task — Researcher Setup", WHITE, PAD, 18)

        # Mode toggle
        new_col    = ACCENT if mode == "new"       else DIM
        return_col = ACCENT if mode == "returning" else DIM
        new_btn.color    = new_col
        return_btn.color = return_col
        new_btn.draw(screen, f_sm)
        return_btn.draw(screen, f_sm)

        y = 80

        # ── Section 1: Participant ────────────────────────────
        y += draw_section_header(screen, f_med, "1  Participant", y)

        if mode == "new":
            draw_text(screen, f_sm, "Participant ID", DIM, COL1,       y + 7)
            pid_box.rect.y = y; pid_box.draw(screen, f_sm)
            draw_text(screen, f_sm, "PIN (4 digits)", DIM, COL1,       y + 47)
            pin_box.rect.y = y + 40; pin_box.draw(screen, f_sm)

            draw_text(screen, f_sm, "Age",           DIM, COL2,        y + 7)
            age_box.rect.y = y; age_box.draw(screen, f_sm)
            draw_text(screen, f_sm, "Gender",        DIM, COL2,        y + 47)
            gender_dd.rect.y = y + 40; gender_dd.draw(screen, f_sm)
            draw_text(screen, f_sm, "Handedness",    DIM, COL2,        y + 87)
            hand_dd.rect.y = y + 80; hand_dd.draw(screen, f_sm)
            y += 130
        else:
            draw_text(screen, f_sm, "Participant ID", DIM, COL1,       y + 7)
            ret_pid_box.rect.y = y; ret_pid_box.draw(screen, f_sm)
            draw_text(screen, f_sm, "PIN",           DIM, COL1,        y + 47)
            ret_pin_box.rect.y = y + 40; ret_pin_box.draw(screen, f_sm)
            draw_text(screen, f_xs, "Existing participants: " +
                      ", ".join(p["participant_id"] for p in get_all_participants()) or "none",
                      DIM, COL2, y + 10)
            y += 90

        # ── Section 2: Group ──────────────────────────────────
        y += draw_section_header(screen, f_med, "2  Group Assignment", y)
        draw_text(screen, f_sm, "Experimental group", DIM, COL1, y + 7)
        group_dd.rect.y = y; group_dd.draw(screen, f_sm)

        group_desc = {
            "MI-High":  "Motor imagery — high sensory feedback keypad",
            "MI-Low":   "Motor imagery — low sensory feedback keypad",
            "PP-High":  "Physical practice — high sensory feedback keypad",
            "PP-Low":   "Physical practice — low sensory feedback keypad",
            "CTRL-High":"Control (planning only) — high sensory feedback",
            "CTRL-Low": "Control (planning only) — low sensory feedback",
        }
        draw_text(screen, f_xs, group_desc.get(group_dd.value, ""), DIM, COL2, y + 10)
        y += 55

        # ── Section 3: Session ────────────────────────────────
        y += draw_section_header(screen, f_med, "3  Session", y)
        draw_text(screen, f_sm, "Session number", DIM, COL1, y + 7)
        session_dd.rect.y = y; session_dd.draw(screen, f_sm)

        blocks = SESSION_STRUCTURE.get(session_dd.value, [])
        draw_text(screen, f_xs, "Blocks: " + "  →  ".join(b.replace("_", " ") for b in blocks),
                  DIM, COL2, y + 10)
        y += 50

        # ── Section 4: Timing ─────────────────────────────────
        y += draw_section_header(screen, f_med, "4  Timing Overrides (seconds)", y)
        draw_text(screen, f_sm, "Planning time", DIM, COL1, y + 7)
        planning_input.y = y; planning_input.minus_rect.y = y; planning_input.plus_rect.y = y
        planning_input.draw(screen, f_sm)

        draw_text(screen, f_sm, "Action time",   DIM, COL1, y + 47)
        action_input.y = y + 40; action_input.minus_rect.y = y + 40; action_input.plus_rect.y = y + 40
        action_input.draw(screen, f_sm)

        draw_text(screen, f_sm, "Feedback time", DIM, COL2, y + 7)
        feedback_input.y = y; feedback_input.minus_rect.y = y; feedback_input.plus_rect.y = y
        feedback_input.draw(screen, f_sm)

        draw_text(screen, f_sm, "Intertrial gap", DIM, COL2, y + 47)
        intertrial_input.y = y + 40; intertrial_input.minus_rect.y = y + 40; intertrial_input.plus_rect.y = y + 40
        intertrial_input.draw(screen, f_sm)
        y += 80

        # ── Section 5: Grid ratio ─────────────────────────────
        y += draw_section_header(screen, f_med, "5  Repeated Grid Ratio (%)", y)
        draw_text(screen, f_sm, "Practice blocks", DIM, COL1, y + 7)
        practice_ratio_input.y = y; practice_ratio_input.minus_rect.y = y; practice_ratio_input.plus_rect.y = y
        practice_ratio_input.draw(screen, f_sm)

        draw_text(screen, f_sm, "Test blocks",    DIM, COL2, y + 7)
        test_ratio_input.y = y; test_ratio_input.minus_rect.y = y; test_ratio_input.plus_rect.y = y
        test_ratio_input.draw(screen, f_sm)
        y += 45

        # ── Message & Launch ─────────────────────────────────
        if message:
            msg_surf = f_sm.render(message, True, message_col)
            screen.blit(msg_surf, (WINDOW_WIDTH // 2 - msg_surf.get_width() // 2, WINDOW_HEIGHT - 90))

        launch_btn.draw(screen, f_med)

        pygame.display.flip()


def _validate_and_launch(mode, pid_box, pin_box, age_box, gender_dd, hand_dd,
                         ret_pid_box, ret_pin_box,
                         group_dd, session_dd,
                         planning_input, action_input, feedback_input, intertrial_input,
                         practice_ratio_input, test_ratio_input):
    """
    Validate all inputs and return a config dict, or an error string.
    """
    if mode == "new":
        pid = pid_box.text.strip().upper()
        pin = pin_box.text.strip()
        age_str = age_box.text.strip()

        if not pid:
            return "Participant ID is required."
        if not pin.isdigit() or len(pin) != 4:
            return "PIN must be exactly 4 digits."
        if not age_str.isdigit():
            return "Age must be a number."

        ok = create_participant(
            participant_id=pid,
            pin=pin,
            group_name=group_dd.value,
            age=int(age_str),
            gender=gender_dd.value,
            handedness=hand_dd.value,
        )
        if not ok:
            return f"Participant ID '{pid}' already exists. Use Returning mode."
        participant_id = pid

    else:
        pid = ret_pid_box.text.strip().upper()
        pin = ret_pin_box.text.strip()
        p   = verify_participant(pid, pin)
        if not p:
            return "Participant not found or incorrect PIN."
        participant_id = pid

    return {
        "participant_id":  participant_id,
        "group":           group_dd.value,
        "session_number":  session_dd.value,
        "planning_time":   planning_input.value,
        "action_time":     action_input.value,
        "feedback_time":   feedback_input.value,
        "intertrial_time": intertrial_input.value,
        "practice_ratio":  practice_ratio_input.value / 100,
        "test_ratio":      test_ratio_input.value / 100,
    }


if __name__ == "__main__":
    result = run_researcher_setup()
    print("Config:", result)
