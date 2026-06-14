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
#    6. Launch / Export buttons
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
from screens.export_screen import run_export_screen

# ── Colours ──────────────────────────────────────────────────
BG          = (15,  15,  25)
PANEL       = (24,  24,  40)
BORDER      = (60,  60,  88)
WHITE       = (235, 235, 245)
DIM         = (120, 120, 155)
ACCENT      = (100, 160, 255)
GREEN       = ( 70, 200, 115)
RED         = (220,  65,  65)
ORANGE      = (235, 145,  55)
INPUT_BG    = (32,  32,  52)
INPUT_ACT   = (44,  44,  68)
SELECTED    = ( 38,  82, 170)
HOVER_BG    = ( 50,  50,  78)

# ── Layout constants ─────────────────────────────────────────
PAD   = 44
COL1  = PAD
COL2  = WINDOW_WIDTH // 2 + 20
LABEL_W = 180     # width reserved for labels before inputs
ROW_H   = 44      # height of each input row
SEC_GAP = 18      # extra gap after section header


# ── Helpers ──────────────────────────────────────────────────

def draw_text(screen, font, text, color, x, y):
    surf = font.render(text, True, color)
    screen.blit(surf, (x, y))
    return surf.get_width(), surf.get_height()


def draw_section_header(screen, font, label, y):
    """Numbered section header with a horizontal rule."""
    surf = font.render(label.upper(), True, ACCENT)
    screen.blit(surf, (PAD, y))
    line_x = PAD + surf.get_width() + 14
    line_y = y + surf.get_height() // 2
    pygame.draw.line(screen, BORDER, (line_x, line_y), (WINDOW_WIDTH - PAD, line_y), 1)
    return surf.get_height() + SEC_GAP


# ── Widgets ───────────────────────────────────────────────────

class InputBox:
    """Single-line text input."""

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
                if len(self.text) < 40:
                    self.text += event.unicode

    def draw(self, screen, font):
        bg = INPUT_ACT if self.active else INPUT_BG
        pygame.draw.rect(screen, bg, self.rect, border_radius=7)
        pygame.draw.rect(screen, ACCENT if self.active else BORDER,
                         self.rect, width=1, border_radius=7)
        display = ("•" * len(self.text)) if self.secret else self.text
        txt = font.render(display if display else self.placeholder,
                          True, WHITE if display else DIM)
        screen.blit(txt, (self.rect.x + 12,
                           self.rect.y + self.rect.h // 2 - txt.get_height() // 2))


class Dropdown:
    """Single-select dropdown. Draw last so it overlays everything."""

    def __init__(self, x, y, w, h, options):
        self.rect     = pygame.Rect(x, y, w, h)
        self.options  = options
        self.selected = 0
        self.open     = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos):
                self.open = not self.open
                return True          # consumed
            if self.open:
                for i, r in enumerate(self._option_rects()):
                    if r.collidepoint(event.pos):
                        self.selected = i
                        self.open = False
                        return True
                self.open = False
        return False

    def close(self):
        self.open = False

    def _option_rects(self):
        return [
            pygame.Rect(self.rect.x, self.rect.y + self.rect.h * (i + 1),
                        self.rect.w, self.rect.h)
            for i in range(len(self.options))
        ]

    @property
    def value(self):
        return self.options[self.selected]

    def draw_closed(self, screen, font):
        """Draw just the collapsed box (always visible)."""
        pygame.draw.rect(screen, INPUT_BG, self.rect, border_radius=7)
        pygame.draw.rect(screen, ACCENT if self.open else BORDER,
                         self.rect, width=1, border_radius=7)
        lbl = font.render(str(self.value), True, WHITE)
        screen.blit(lbl, (self.rect.x + 12,
                           self.rect.y + self.rect.h // 2 - lbl.get_height() // 2))
        arrow = font.render("▾", True, DIM)
        screen.blit(arrow, (self.rect.right - 26,
                             self.rect.y + self.rect.h // 2 - arrow.get_height() // 2))

    def draw_open(self, screen, font):
        """Draw the dropdown list on top of everything else."""
        if not self.open:
            return
        for i, (opt, r) in enumerate(zip(self.options, self._option_rects())):
            bg = SELECTED if i == self.selected else INPUT_BG
            pygame.draw.rect(screen, bg, r, border_radius=6)
            pygame.draw.rect(screen, BORDER, r, width=1, border_radius=6)
            t = font.render(str(opt), True, WHITE)
            screen.blit(t, (r.x + 12, r.y + r.h // 2 - t.get_height() // 2))


class NumericInput:
    """Compact  −  value  +  stepper."""

    def __init__(self, x, y, value, min_val, max_val, step=1, fmt=".0f"):
        self.value   = value
        self.min_val = min_val
        self.max_val = max_val
        self.step    = step
        self.fmt     = fmt
        self.btn_w   = 32
        self.val_w   = 68
        self.h       = 36
        self._place(x, y)

    def _place(self, x, y):
        self.x = x
        self.y = y
        self.minus_rect = pygame.Rect(x, y, self.btn_w, self.h)
        self.val_rect   = pygame.Rect(x + self.btn_w + 3, y, self.val_w, self.h)
        self.plus_rect  = pygame.Rect(x + self.btn_w + self.val_w + 6, y, self.btn_w, self.h)

    def reposition(self, x, y):
        self._place(x, y)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.minus_rect.collidepoint(event.pos):
                self.value = max(self.min_val, round(self.value - self.step, 2))
            if self.plus_rect.collidepoint(event.pos):
                self.value = min(self.max_val, round(self.value + self.step, 2))

    def draw(self, screen, font):
        for rect, lbl in [(self.minus_rect, "−"), (self.plus_rect, "+")]:
            pygame.draw.rect(screen, INPUT_BG, rect, border_radius=6)
            pygame.draw.rect(screen, BORDER, rect, width=1, border_radius=6)
            s = font.render(lbl, True, WHITE)
            screen.blit(s, (rect.x + rect.w // 2 - s.get_width() // 2,
                             rect.y + rect.h // 2 - s.get_height() // 2))
        pygame.draw.rect(screen, INPUT_BG, self.val_rect, border_radius=6)
        vs = font.render(format(self.value, self.fmt), True, ACCENT)
        screen.blit(vs, (self.val_rect.x + self.val_rect.w // 2 - vs.get_width() // 2,
                          self.val_rect.y + self.val_rect.h // 2 - vs.get_height() // 2))


class Button:
    def __init__(self, x, y, w, h, label, color=ACCENT):
        self.rect  = pygame.Rect(x, y, w, h)
        self.label = label
        self.color = color

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            return self.rect.collidepoint(event.pos)
        return False

    def draw(self, screen, font):
        # Subtle hover glow
        mouse = pygame.mouse.get_pos()
        col = tuple(min(255, c + 18) for c in self.color) if self.rect.collidepoint(mouse) else self.color
        pygame.draw.rect(screen, col, self.rect, border_radius=10)
        lbl = font.render(self.label, True, BG)
        screen.blit(lbl, (self.rect.x + self.rect.w // 2 - lbl.get_width() // 2,
                           self.rect.y + self.rect.h // 2 - lbl.get_height() // 2))


# ── Main setup screen ─────────────────────────────────────────

def run_researcher_setup():
    """
    Display the researcher configuration screen.

    Returns:
        dict: All configuration values needed to start a session, or None if quit.
    """
    pygame.init()

    # Enable HiDPI / Retina rendering on macOS
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SCALED)
    pygame.display.set_caption("Grid-Sailing — Researcher Setup")
    clock = pygame.time.Clock()

    initialise_database()

    # Fonts — larger for crisp HiDPI rendering
    f_title = pygame.font.SysFont("Arial", 26, bold=True)
    f_sec   = pygame.font.SysFont("Arial", 15, bold=True)
    f_med   = pygame.font.SysFont("Arial", 18, bold=True)
    f_sm    = pygame.font.SysFont("Arial", 16)
    f_xs    = pygame.font.SysFont("Arial", 13)

    fonts = (f_med, f_med, f_sm, f_xs)   # passed to export screen

    mode = "new"

    # ── Input widgets — positions set relative to y in draw loop ──

    # Section 1 – New participant
    INP_X = COL1 + LABEL_W
    pid_box   = InputBox(INP_X,       0, 200, ROW_H, "e.g. P001")
    pin_box   = InputBox(INP_X,       0, 200, ROW_H, "4-digit PIN", secret=True)
    age_box   = InputBox(COL2 + LABEL_W, 0, 120, ROW_H, "e.g. 22")
    gender_dd = Dropdown(COL2 + LABEL_W, 0, 200, ROW_H,
                         ["Female", "Male", "Non-binary", "Other", "Prefer not to say"])
    hand_dd   = Dropdown(COL2 + LABEL_W, 0, 200, ROW_H,
                         ["Right", "Left", "Ambidextrous"])

    # Section 1 – Returning
    ret_pid_box = InputBox(INP_X, 0, 200, ROW_H, "Participant ID")
    ret_pin_box = InputBox(INP_X, 0, 200, ROW_H, "PIN", secret=True)

    # Section 2
    group_dd = Dropdown(INP_X, 0, 220, ROW_H, GROUPS)

    # Section 3
    session_dd = Dropdown(INP_X, 0, 110, ROW_H, [1, 2, 3])

    # Section 4
    NX = COL1 + LABEL_W
    planning_input   = NumericInput(NX, 0, PLANNING_TIME_SEC,  4, 12, step=1)
    action_input     = NumericInput(NX, 0, ACTION_TIME_SEC,    5, 20, step=1)
    feedback_input   = NumericInput(COL2 + LABEL_W, 0, FEEDBACK_TIME_SEC,  1,  5, step=1)
    intertrial_input = NumericInput(COL2 + LABEL_W, 0, INTERTRIAL_SEC,     2, 10, step=1)

    # Section 5
    practice_ratio_input = NumericInput(NX,              0, PRACTICE_REPEATED_RATIO * 100, 50, 100, step=4)
    test_ratio_input     = NumericInput(COL2 + LABEL_W,  0, TEST_REPEATED_RATIO * 100,     40,  80, step=4)

    # Buttons
    new_btn    = Button(PAD,       54, 160, 34, "New Participant", ACCENT)
    return_btn = Button(PAD + 174, 54, 140, 34, "Returning",      DIM)
    launch_btn = Button(WINDOW_WIDTH // 2 - 140, WINDOW_HEIGHT - 66, 280, 46, "Launch Session", GREEN)
    export_btn = Button(WINDOW_WIDTH - PAD - 140, WINDOW_HEIGHT - 66, 140, 46, "Export Data", ORANGE)

    message     = ""
    message_col = RED

    # All dropdowns in one list for event routing and draw ordering
    all_dropdowns = [gender_dd, hand_dd, group_dd, session_dd]
    all_inputs    = [pid_box, pin_box, age_box, ret_pid_box, ret_pin_box]
    all_steppers  = [planning_input, action_input, feedback_input,
                     intertrial_input, practice_ratio_input, test_ratio_input]

    while True:
        clock.tick(FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()

            # Mode toggle
            if new_btn.handle_event(event):
                mode = "new"; message = ""
                for dd in all_dropdowns:
                    dd.close()
            if return_btn.handle_event(event):
                mode = "returning"; message = ""
                for dd in all_dropdowns:
                    dd.close()

            # Text inputs
            for box in all_inputs:
                box.handle_event(event)

            # Steppers
            for s in all_steppers:
                s.handle_event(event)

            # Dropdowns — only pass events to visible ones; close others
            active_dds = [group_dd, session_dd]
            if mode == "new":
                active_dds += [gender_dd, hand_dd]
            consumed = False
            for dd in active_dds:
                if dd.handle_event(event):
                    # Close other dropdowns when one opens
                    for other in active_dds:
                        if other is not dd:
                            other.close()
                    consumed = True
                    break
            # Click anywhere else closes all dropdowns
            if not consumed and event.type == pygame.MOUSEBUTTONDOWN:
                for dd in all_dropdowns:
                    dd.close()

            # Export button
            if export_btn.handle_event(event):
                run_export_screen(screen, clock, fonts)

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
                    message = result; message_col = RED
                elif isinstance(result, dict):
                    pygame.quit()
                    return result

        # ── Draw ─────────────────────────────────────────────
        screen.fill(BG)

        # Title bar
        draw_text(screen, f_title, "Grid-Sailing Task — Researcher Setup", WHITE, PAD, 16)

        # Mode buttons
        new_btn.color    = ACCENT if mode == "new"       else DIM
        return_btn.color = ACCENT if mode == "returning" else DIM
        new_btn.draw(screen, f_sm)
        return_btn.draw(screen, f_sm)

        y = 108

        # ── §1: Participant ───────────────────────────────────
        y += draw_section_header(screen, f_sec, "1  Participant", y)

        if mode == "new":
            # Left column
            draw_text(screen, f_sm, "Participant ID", DIM, COL1, y + 10)
            pid_box.rect.y = y;      pid_box.draw(screen, f_sm)
            draw_text(screen, f_sm, "PIN (4 digits)", DIM, COL1, y + ROW_H + 14)
            pin_box.rect.y = y + ROW_H + 8; pin_box.draw(screen, f_sm)

            # Right column
            draw_text(screen, f_sm, "Age",        DIM, COL2, y + 10)
            age_box.rect.y = y;      age_box.draw(screen, f_sm)
            draw_text(screen, f_sm, "Gender",     DIM, COL2, y + ROW_H + 14)
            gender_dd.rect.y = y + ROW_H + 8;   gender_dd.draw_closed(screen, f_sm)
            draw_text(screen, f_sm, "Handedness", DIM, COL2, y + ROW_H * 2 + 22)
            hand_dd.rect.y   = y + ROW_H * 2 + 16; hand_dd.draw_closed(screen, f_sm)
            y += ROW_H * 2 + 16 + ROW_H + 20
        else:
            draw_text(screen, f_sm, "Participant ID", DIM, COL1, y + 10)
            ret_pid_box.rect.y = y;          ret_pid_box.draw(screen, f_sm)
            draw_text(screen, f_sm, "PIN",   DIM, COL1, y + ROW_H + 14)
            ret_pin_box.rect.y = y + ROW_H + 8; ret_pin_box.draw(screen, f_sm)

            # List existing participants on right
            parts = [p["participant_id"] for p in get_all_participants()]
            p_str = "Registered: " + (", ".join(parts) if parts else "none yet")
            draw_text(screen, f_xs, p_str, DIM, COL2, y + 14)
            y += ROW_H + 8 + ROW_H + 20

        # ── §2: Group ─────────────────────────────────────────
        y += draw_section_header(screen, f_sec, "2  Group Assignment", y)
        draw_text(screen, f_sm, "Experimental group", DIM, COL1, y + 10)
        group_dd.rect.y = y;  group_dd.draw_closed(screen, f_sm)

        group_desc = {
            "MI-High":   "Motor imagery — high sensory feedback keypad",
            "MI-Low":    "Motor imagery — low sensory feedback keypad",
            "PP-High":   "Physical practice — high sensory feedback keypad",
            "PP-Low":    "Physical practice — low sensory feedback keypad",
            "CTRL-High": "Control (planning only) — high sensory feedback",
            "CTRL-Low":  "Control (planning only) — low sensory feedback",
        }
        draw_text(screen, f_xs, group_desc.get(group_dd.value, ""), DIM, COL2, y + 12)
        y += ROW_H + 20

        # ── §3: Session ───────────────────────────────────────
        y += draw_section_header(screen, f_sec, "3  Session", y)
        draw_text(screen, f_sm, "Session number", DIM, COL1, y + 10)
        session_dd.rect.y = y; session_dd.draw_closed(screen, f_sm)

        blocks = SESSION_STRUCTURE.get(session_dd.value, [])
        block_str = "  →  ".join(b.replace("_", " ") for b in blocks)
        draw_text(screen, f_xs, "Blocks: " + block_str, DIM, COL2, y + 12)
        y += ROW_H + 20

        # ── §4: Timing ────────────────────────────────────────
        y += draw_section_header(screen, f_sec, "4  Timing Overrides (seconds)", y)

        draw_text(screen, f_sm, "Planning time",  DIM, COL1, y + 10)
        planning_input.reposition(COL1 + LABEL_W, y)
        planning_input.draw(screen, f_sm)

        draw_text(screen, f_sm, "Feedback time",  DIM, COL2, y + 10)
        feedback_input.reposition(COL2 + LABEL_W, y)
        feedback_input.draw(screen, f_sm)

        y += ROW_H + 10

        draw_text(screen, f_sm, "Action time",    DIM, COL1, y + 10)
        action_input.reposition(COL1 + LABEL_W, y)
        action_input.draw(screen, f_sm)

        draw_text(screen, f_sm, "Intertrial gap", DIM, COL2, y + 10)
        intertrial_input.reposition(COL2 + LABEL_W, y)
        intertrial_input.draw(screen, f_sm)

        y += ROW_H + 20

        # ── §5: Grid Ratio ────────────────────────────────────
        y += draw_section_header(screen, f_sec, "5  Repeated Grid Ratio (%)", y)

        draw_text(screen, f_sm, "Practice blocks", DIM, COL1, y + 10)
        practice_ratio_input.reposition(COL1 + LABEL_W, y)
        practice_ratio_input.draw(screen, f_sm)

        draw_text(screen, f_sm, "Test blocks",     DIM, COL2, y + 10)
        test_ratio_input.reposition(COL2 + LABEL_W, y)
        test_ratio_input.draw(screen, f_sm)

        # ── Status message ────────────────────────────────────
        if message:
            msg_surf = f_sm.render(message, True, message_col)
            screen.blit(msg_surf, (WINDOW_WIDTH // 2 - msg_surf.get_width() // 2,
                                   WINDOW_HEIGHT - 84))

        # ── Bottom buttons ────────────────────────────────────
        launch_btn.draw(screen, f_med)
        export_btn.draw(screen, f_sm)

        # ── Dropdowns drawn LAST so they appear on top ────────
        if mode == "new":
            gender_dd.draw_open(screen, f_sm)
            hand_dd.draw_open(screen, f_sm)
        group_dd.draw_open(screen, f_sm)
        session_dd.draw_open(screen, f_sm)

        pygame.display.flip()


# ── Validation ────────────────────────────────────────────────

def _validate_and_launch(mode, pid_box, pin_box, age_box, gender_dd, hand_dd,
                         ret_pid_box, ret_pin_box,
                         group_dd, session_dd,
                         planning_input, action_input, feedback_input, intertrial_input,
                         practice_ratio_input, test_ratio_input):
    """
    Validate all inputs and return a config dict, or an error string.
    """
    if mode == "new":
        pid     = pid_box.text.strip().upper()
        pin     = pin_box.text.strip()
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
