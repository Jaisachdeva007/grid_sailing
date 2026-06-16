# ============================================================
#  GRID-SAILING TASK — Researcher Setup Screen  (v3 polish)
#
#  Juliet sees this screen before every session.
#  Sections:
#    1. Participant  (New or Returning tab)
#    2. Group assignment
#    3. Session selection
#    4. Timing overrides
#    5. Grid ratio override
#    Bottom bar: Launch Session | View Data | Export Data
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
from screens.data_viewer  import run_data_viewer

# ── Palette ───────────────────────────────────────────────────
BG        = (8,    8,   16)
SURFACE   = (14,  14,   26)
PANEL     = (20,  20,   36)
BORDER    = (48,  48,   76)
BORDER_LT = (68,  68,  108)
WHITE     = (245, 245, 255)
DIM       = (118, 118, 158)
ACCENT    = ( 88, 148, 255)
GREEN     = ( 52, 200, 100)
RED       = (220,  60,  60)
ORANGE    = (228, 138,  48)
PURPLE    = (160,  90, 220)
INPUT_BG  = (24,  24,   44)
INPUT_ACT = (34,  34,   58)
SELECTED  = ( 32,  72, 160)
TAB_ACT   = ( 88, 148, 255)

GROUP_COLORS = {
    "MI-High":   ( 88, 148, 255),
    "MI-Low":    ( 60, 108, 210),
    "PP-High":   ( 58, 196, 108),
    "PP-Low":    ( 38, 148,  80),
    "CTRL-High": (210, 158,  28),
    "CTRL-Low":  (168, 118,  18),
}

# ── Layout ────────────────────────────────────────────────────
PAD      = 48
HALF     = WINDOW_WIDTH // 2
COL1     = PAD
COL2     = HALF + 20
LBL_W    = 180
INP_X1   = COL1 + LBL_W
INP_X2   = COL2 + LBL_W
ROW_H    = 48
SEC_GAP  = 18
CONTENT_TOP = 110


# ── Tiny helpers ─────────────────────────────────────────────

def _t(screen, font, text, col, x, y):
    s = font.render(text, True, col)
    screen.blit(s, (x, y))
    return s

def _panel(screen, x, y, w, h, col=BORDER, radius=10):
    pygame.draw.rect(screen, PANEL,  (x, y, w, h), border_radius=radius)
    pygame.draw.rect(screen, col,    (x, y, w, h), width=1, border_radius=radius)

def _pill(screen, font, text, fg, bg, x, y):
    s  = font.render(text, True, fg)
    pw = s.get_width() + 14
    ph = s.get_height() + 6
    pygame.draw.rect(screen, bg, (x, y, pw, ph), border_radius=ph//2)
    screen.blit(s, (x + 7, y + 3))
    return pw

def _section(screen, font, label, y):
    s = font.render(label.upper(), True, ACCENT)
    screen.blit(s, (PAD, y))
    lx = PAD + s.get_width() + 14
    ly = y + s.get_height() // 2
    pygame.draw.line(screen, BORDER, (lx, ly), (WINDOW_WIDTH - PAD, ly))
    return s.get_height() + SEC_GAP

def _label(screen, font, text, x, y):
    s = font.render(text, True, DIM)
    screen.blit(s, (x, y + ROW_H // 2 - s.get_height() // 2))


# ── Widgets ───────────────────────────────────────────────────

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
                if len(self.text) < 40:
                    self.text += event.unicode

    def draw(self, screen, font):
        bg = INPUT_ACT if self.active else INPUT_BG
        bc = ACCENT    if self.active else BORDER
        pygame.draw.rect(screen, bg, self.rect, border_radius=7)
        pygame.draw.rect(screen, bc, self.rect, width=1, border_radius=7)
        # Left accent stripe when active
        if self.active:
            pygame.draw.rect(screen, ACCENT,
                             (self.rect.x, self.rect.y + 6, 2, self.rect.h - 12),
                             border_radius=1)
        display = ("•" * len(self.text)) if self.secret else self.text
        txt = font.render(display if display else self.placeholder,
                          True, WHITE if display else DIM)
        screen.blit(txt, (self.rect.x + 14,
                           self.rect.y + self.rect.h // 2 - txt.get_height() // 2))


class Dropdown:
    def __init__(self, x, y, w, h, options):
        self.rect     = pygame.Rect(x, y, w, h)
        self.options  = options
        self.selected = 0
        self.open     = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos):
                self.open = not self.open; return True
            if self.open:
                for i, r in enumerate(self._option_rects()):
                    if r.collidepoint(event.pos):
                        self.selected = i; self.open = False; return True
                self.open = False
        return False

    def close(self): self.open = False

    def _option_rects(self):
        return [pygame.Rect(self.rect.x, self.rect.y + self.rect.h * (i + 1),
                            self.rect.w, self.rect.h)
                for i in range(len(self.options))]

    @property
    def value(self): return self.options[self.selected]

    def draw_closed(self, screen, font):
        bc = ACCENT if self.open else BORDER
        pygame.draw.rect(screen, INPUT_BG, self.rect, border_radius=7)
        pygame.draw.rect(screen, bc,       self.rect, width=1, border_radius=7)
        lbl = font.render(str(self.value), True, WHITE)
        screen.blit(lbl, (self.rect.x + 14,
                           self.rect.y + self.rect.h // 2 - lbl.get_height() // 2))
        arr = font.render("▾", True, DIM)
        screen.blit(arr, (self.rect.right - 24,
                           self.rect.y + self.rect.h // 2 - arr.get_height() // 2))

    def draw_open(self, screen, font):
        if not self.open: return
        for i, (opt, r) in enumerate(zip(self.options, self._option_rects())):
            bg = SELECTED if i == self.selected else INPUT_BG
            pygame.draw.rect(screen, bg,     r, border_radius=6)
            pygame.draw.rect(screen, BORDER, r, width=1, border_radius=6)
            t = font.render(str(opt), True, WHITE)
            screen.blit(t, (r.x + 14, r.y + r.h // 2 - t.get_height() // 2))


class NumericInput:
    def __init__(self, x, y, value, min_val, max_val, step=1, fmt=".0f"):
        self.value   = value
        self.min_val = min_val
        self.max_val = max_val
        self.step    = step
        self.fmt     = fmt
        self.btn_w   = 30
        self.val_w   = 60
        self.h       = ROW_H
        self._place(x, y)

    def _place(self, x, y):
        self.minus_rect = pygame.Rect(x, y, self.btn_w, self.h)
        self.val_rect   = pygame.Rect(x + self.btn_w + 2, y, self.val_w, self.h)
        self.plus_rect  = pygame.Rect(x + self.btn_w + self.val_w + 4, y, self.btn_w, self.h)

    def reposition(self, x, y): self._place(x, y)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.minus_rect.collidepoint(event.pos):
                self.value = max(self.min_val, round(self.value - self.step, 2))
            if self.plus_rect.collidepoint(event.pos):
                self.value = min(self.max_val, round(self.value + self.step, 2))

    def draw(self, screen, font):
        for rect, lbl in [(self.minus_rect, "−"), (self.plus_rect, "+")]:
            pygame.draw.rect(screen, INPUT_BG, rect, border_radius=6)
            pygame.draw.rect(screen, BORDER,   rect, width=1, border_radius=6)
            s = font.render(lbl, True, WHITE)
            screen.blit(s, (rect.x + rect.w//2 - s.get_width()//2,
                             rect.y + rect.h//2 - s.get_height()//2))
        pygame.draw.rect(screen, INPUT_BG, self.val_rect, border_radius=6)
        vs = font.render(format(self.value, self.fmt), True, ACCENT)
        screen.blit(vs, (self.val_rect.x + self.val_rect.w//2 - vs.get_width()//2,
                          self.val_rect.y + self.val_rect.h//2 - vs.get_height()//2))


class Button:
    def __init__(self, x, y, w, h, label, color=ACCENT, icon=""):
        self.rect  = pygame.Rect(x, y, w, h)
        self.label = label
        self.color = color
        self.icon  = icon

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            return self.rect.collidepoint(event.pos)
        return False

    def draw(self, screen, font):
        mouse = pygame.mouse.get_pos()
        hover = self.rect.collidepoint(mouse)
        col   = tuple(min(255, c + 22) for c in self.color) if hover else self.color
        # Shadow
        shadow = pygame.Rect(self.rect.x + 2, self.rect.y + 3,
                             self.rect.w, self.rect.h)
        pygame.draw.rect(screen, (8, 8, 16), shadow, border_radius=10)
        pygame.draw.rect(screen, col, self.rect, border_radius=10)
        text = f"{self.icon}  {self.label}" if self.icon else self.label
        lbl = font.render(text, True, BG)
        screen.blit(lbl, (self.rect.x + self.rect.w//2 - lbl.get_width()//2,
                           self.rect.y + self.rect.h//2 - lbl.get_height()//2))


# ── Researcher Home (landing screen after admin login) ────────

def run_researcher_home(screen, clock):
    """
    Landing screen shown after Juliet logs in.
    Returns one of: "new", "returning", "data", or None (quit).
    """
    f_title = pygame.font.SysFont("Helvetica Neue", 42, bold=True)
    f_med   = pygame.font.SysFont("Helvetica Neue", 23, bold=True)
    f_sm    = pygame.font.SysFont("Helvetica Neue", 19)
    f_xs    = pygame.font.SysFont("Helvetica Neue", 15)

    pygame.display.set_caption("Grid-Sailing — Researcher Home")

    CX = WINDOW_WIDTH  // 2
    CY = WINDOW_HEIGHT // 2

    CARD_W, CARD_H = 300, 220
    GAP = 32
    total_w = CARD_W * 3 + GAP * 2
    start_x = CX - total_w // 2

    cards = [
        {
            "key":   "new",
            "label": "New Participant",
            "sub":   "Register a first-time participant\nand configure their session",
            "color": GREEN,
            "icon":  "N",
        },
        {
            "key":   "returning",
            "label": "Returning Participant",
            "sub":   "Look up an existing participant\nand start their next session",
            "color": ACCENT,
            "icon":  "R",
        },
        {
            "key":   "data",
            "label": "View Data",
            "sub":   "Browse participant progress,\naccuracy and session breakdown",
            "color": PURPLE,
            "icon":  "D",
        },
    ]

    rects = [
        pygame.Rect(start_x + i * (CARD_W + GAP), CY - CARD_H // 2, CARD_W, CARD_H)
        for i in range(3)
    ]

    while True:
        clock.tick(FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN:
                for i, r in enumerate(rects):
                    if r.collidepoint(event.pos):
                        return cards[i]["key"]
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return None

        screen.fill(BG)

        # Title bar
        pygame.draw.rect(screen, SURFACE, (0, 0, WINDOW_WIDTH, 60))
        pygame.draw.line(screen, BORDER, (0, 60), (WINDOW_WIDTH, 60))
        ts = f_title.render("Researcher Setup", WHITE, False)  # unused, use _t
        _t(screen, f_title, "Researcher Setup", WHITE, PAD, 16)
        _t(screen, f_xs, "Grid-Sailing Task", DIM, WINDOW_WIDTH - PAD - 120, 22)

        # Subtitle
        sub = f_sm.render("What would you like to do today?", True, DIM)
        screen.blit(sub, (CX - sub.get_width() // 2, CY - CARD_H // 2 - 52))

        mouse = pygame.mouse.get_pos()

        for i, (card, r) in enumerate(zip(cards, rects)):
            hover  = r.collidepoint(mouse)
            col    = card["color"]

            # Shadow
            pygame.draw.rect(screen, (4, 4, 10),
                             (r.x + 3, r.y + 5, r.w, r.h), border_radius=18)
            # Card body
            bg = tuple(min(255, c + 8) for c in PANEL) if hover else PANEL
            pygame.draw.rect(screen, bg, r, border_radius=18)
            pygame.draw.rect(screen, col if hover else BORDER,
                             r, width=2 if hover else 1, border_radius=18)

            # Top colour strip
            pygame.draw.rect(screen, col,
                             (r.x + 1, r.y + 1, r.w - 2, 6), border_radius=18)

            # Icon circle — clean
            ic = (r.x + r.w // 2, r.y + 52)
            dark_col = tuple(max(0, c - 50) for c in col)
            pygame.draw.circle(screen, dark_col, ic, 28)
            pygame.draw.circle(screen, col,      ic, 28, width=2)
            g = f_med.render(card["icon"], True, col)
            screen.blit(g, (ic[0] - g.get_width() // 2,
                            ic[1] - g.get_height() // 2))

            # Label
            lt = f_med.render(card["label"], True, WHITE)
            screen.blit(lt, (r.x + r.w // 2 - lt.get_width() // 2, r.y + 94))

            # Subtitle
            for j, line in enumerate(card["sub"].split("\n")):
                ls = f_xs.render(line, True, DIM)
                screen.blit(ls, (r.x + r.w // 2 - ls.get_width() // 2,
                                 r.y + 122 + j * 20))

        # Hint
        hint = f_xs.render("ESC to return to the login screen", True, BORDER)
        screen.blit(hint, (CX - hint.get_width() // 2, WINDOW_HEIGHT - 36))

        pygame.display.flip()


# ── Main setup screen ─────────────────────────────────────────

def run_researcher_setup(screen=None, clock=None, mode="new"):
    """
    Display researcher configuration screen.
    screen/clock are passed in from main (shared window).
    Falls back to creating its own window if called standalone.
    """
    if screen is None:
        pygame.init()
        screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SCALED)
        clock  = pygame.time.Clock()
    pygame.display.set_caption("Grid-Sailing — Researcher Setup")

    initialise_database()

    # Fonts
    f_title = pygame.font.SysFont("Helvetica Neue", 38, bold=True)
    f_sec   = pygame.font.SysFont("Helvetica Neue", 16, bold=True)
    f_med   = pygame.font.SysFont("Helvetica Neue", 21, bold=True)
    f_sm    = pygame.font.SysFont("Helvetica Neue", 19)
    f_xs    = pygame.font.SysFont("Helvetica Neue", 16)
    # Fallback
    if not f_title.get_height():
        f_title = pygame.font.SysFont("Arial", 38, bold=True)
        f_sec   = pygame.font.SysFont("Arial", 16, bold=True)
        f_med   = pygame.font.SysFont("Arial", 21, bold=True)
        f_sm    = pygame.font.SysFont("Arial", 19)
        f_xs    = pygame.font.SysFont("Arial", 16)

    fonts = (f_med, f_med, f_sm, f_xs)

    # ── Widgets ──────────────────────────────────────────────
    pid_box   = InputBox(INP_X1, 0, 190, ROW_H, "e.g. P001")
    pin_box   = InputBox(INP_X1, 0, 190, ROW_H, "4-digit PIN", secret=True)
    age_box   = InputBox(INP_X2, 0, 100, ROW_H, "e.g. 22")
    gender_dd = Dropdown(INP_X2, 0, 190, ROW_H,
                         ["Female", "Male", "Non-binary", "Other", "Prefer not to say"])
    hand_dd   = Dropdown(INP_X2, 0, 190, ROW_H, ["Right", "Left", "Ambidextrous"])

    ret_pid_box = InputBox(INP_X1, 0, 190, ROW_H, "Participant ID")
    ret_pin_box = InputBox(INP_X1, 0, 190, ROW_H, "PIN", secret=True)

    group_dd   = Dropdown(INP_X1, 0, 210, ROW_H, GROUPS)
    session_dd = Dropdown(INP_X1, 0, 100, ROW_H, [1, 2, 3])

    planning_input   = NumericInput(INP_X1, 0, PLANNING_TIME_SEC,  4, 12)
    action_input     = NumericInput(INP_X1, 0, ACTION_TIME_SEC,    5, 20)
    feedback_input   = NumericInput(INP_X2, 0, FEEDBACK_TIME_SEC,  1,  5)
    intertrial_input = NumericInput(INP_X2, 0, INTERTRIAL_SEC,     2, 10)

    practice_ratio_input = NumericInput(INP_X1, 0, PRACTICE_REPEATED_RATIO * 100, 50, 100, step=4)
    test_ratio_input     = NumericInput(INP_X2,  0, TEST_REPEATED_RATIO * 100,     40,  80, step=4)

    BH = 46   # bottom button height
    BY = WINDOW_HEIGHT - BH - 18
    BW = WINDOW_WIDTH - PAD * 2
    launch_btn = Button(PAD,                       BY, int(BW * 0.45), BH, "Launch Session", GREEN)
    data_btn   = Button(PAD + int(BW * 0.47),      BY, int(BW * 0.25), BH, "View Data",     PURPLE)
    export_btn = Button(PAD + int(BW * 0.74),      BY, int(BW * 0.26), BH, "Export Data",   ORANGE)

    message     = ""
    message_col = RED
    scroll_y    = 0          # vertical scroll offset for the form content

    all_dropdowns = [gender_dd, hand_dd, group_dd, session_dd]
    all_inputs    = [pid_box, pin_box, age_box, ret_pid_box, ret_pin_box]
    all_steppers  = [planning_input, action_input, feedback_input,
                     intertrial_input, practice_ratio_input, test_ratio_input]

    while True:
        clock.tick(FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return None

            for box in all_inputs:   box.handle_event(event)
            for s in all_steppers:   s.handle_event(event)

            active_dds = [group_dd, session_dd] + ([gender_dd, hand_dd] if mode == "new" else [])
            consumed = False
            for dd in active_dds:
                if dd.handle_event(event):
                    for other in active_dds:
                        if other is not dd: other.close()
                    consumed = True; break
            if not consumed and event.type == pygame.MOUSEBUTTONDOWN:
                for dd in all_dropdowns: dd.close()

            if data_btn.handle_event(event):
                run_data_viewer(screen, clock, fonts)

            if export_btn.handle_event(event):
                run_export_screen(screen, clock, fonts)

            if event.type == pygame.MOUSEWHEEL:
                scroll_y = max(0, min(scroll_y - event.y * 24, 220))

            if launch_btn.handle_event(event):
                result = _validate_and_launch(
                    mode, pid_box, pin_box, age_box, gender_dd, hand_dd,
                    ret_pid_box, ret_pin_box, group_dd, session_dd,
                    planning_input, action_input, feedback_input, intertrial_input,
                    practice_ratio_input, test_ratio_input
                )
                if isinstance(result, str):
                    message = result; message_col = RED
                elif isinstance(result, dict):
                    return result

        # ── Draw ─────────────────────────────────────────────
        screen.fill(BG)

        # ── Top title bar (fixed — never scrolls) ─────────────
        pygame.draw.rect(screen, SURFACE, (0, 0, WINDOW_WIDTH, 60))
        pygame.draw.line(screen, BORDER, (0, 60), (WINDOW_WIDTH, 60))
        _t(screen, f_title, "Researcher Setup", WHITE, PAD, 16)
        _t(screen, f_xs, "Grid-Sailing Task", DIM, WINDOW_WIDTH - PAD - 120, 22)

        # ── Breadcrumb (fixed) ────────────────────────────────
        crumb_label = "New Participant" if mode == "new" else "Returning Participant"
        _t(screen, f_xs, f"Home  /  {crumb_label}", DIM, PAD, 76)

        # ── Scroll helper ─────────────────────────────────────
        # oy(base, extra=0) converts a layout y to a screen y by
        # subtracting the current scroll offset.
        def oy(base, extra=0):
            return base + extra - scroll_y

        BY_LINE = WINDOW_HEIGHT - BH - 30

        # Clip so content that scrolls off-screen is hidden.
        screen.set_clip(pygame.Rect(0, 96, WINDOW_WIDTH, BY_LINE - 96))

        y = CONTENT_TOP

        # ── §1: Participant ───────────────────────────────────
        y += _section(screen, f_sec, "1  Participant", oy(y))

        if mode == "new":
            _label(screen, f_sm, "Participant ID", COL1, oy(y))
            pid_box.rect.y = oy(y);  pid_box.draw(screen, f_sm)
            _label(screen, f_sm, "PIN (4 digits)", COL1, oy(y, ROW_H + 8))
            pin_box.rect.y = oy(y, ROW_H + 8); pin_box.draw(screen, f_sm)

            _label(screen, f_sm, "Age",        COL2, oy(y))
            age_box.rect.y = oy(y); age_box.draw(screen, f_sm)
            _label(screen, f_sm, "Gender",     COL2, oy(y, ROW_H + 8))
            gender_dd.rect.y = oy(y, ROW_H + 8); gender_dd.draw_closed(screen, f_sm)
            _label(screen, f_sm, "Handedness", COL2, oy(y, ROW_H * 2 + 16))
            hand_dd.rect.y   = oy(y, ROW_H * 2 + 16); hand_dd.draw_closed(screen, f_sm)
            y += ROW_H * 3 + 24
        else:
            _label(screen, f_sm, "Participant ID", COL1, oy(y))
            ret_pid_box.rect.y = oy(y); ret_pid_box.draw(screen, f_sm)
            _label(screen, f_sm, "PIN",           COL1, oy(y, ROW_H + 8))
            ret_pin_box.rect.y = oy(y, ROW_H + 8); ret_pin_box.draw(screen, f_sm)

            parts = [p["participant_id"] for p in get_all_participants()]
            px = COL2; py2 = oy(y, 6)
            for pid in parts[:10]:
                pw = _pill(screen, f_xs, pid, BG, ACCENT, px, py2)
                px += pw + 8
                if px > WINDOW_WIDTH - PAD - 60:
                    px = COL2; py2 += 28
            if not parts:
                _t(screen, f_xs, "No participants yet", DIM, COL2, oy(y, 14))
            y += ROW_H * 2 + 24

        # ── §2: Group ─────────────────────────────────────────
        y += _section(screen, f_sec, "2  Group Assignment", oy(y))
        _label(screen, f_sm, "Experimental group", COL1, oy(y))
        group_dd.rect.y = oy(y); group_dd.draw_closed(screen, f_sm)

        gcol = GROUP_COLORS.get(group_dd.value, DIM)
        _pill(screen, f_xs, group_dd.value, BG, gcol,
              INP_X1 + 218, oy(y, ROW_H // 2 - 12))

        group_desc = {
            "MI-High":   "Motor imagery  ·  high sensory feedback keypad",
            "MI-Low":    "Motor imagery  ·  low sensory feedback keypad",
            "PP-High":   "Physical practice  ·  high sensory feedback keypad",
            "PP-Low":    "Physical practice  ·  low sensory feedback keypad",
            "CTRL-High": "Control (planning only)  ·  high sensory feedback",
            "CTRL-Low":  "Control (planning only)  ·  low sensory feedback",
        }
        _t(screen, f_xs, group_desc.get(group_dd.value, ""), DIM, COL2, oy(y, ROW_H // 2 - 7))
        y += ROW_H + 20

        # ── §3: Session ───────────────────────────────────────
        y += _section(screen, f_sec, "3  Session", oy(y))
        _label(screen, f_sm, "Session number", COL1, oy(y))
        session_dd.rect.y = oy(y); session_dd.draw_closed(screen, f_sm)

        blocks = SESSION_STRUCTURE.get(session_dd.value, [])
        bx = COL2
        for b in blocks:
            bw = _pill(screen, f_xs,
                       b.replace("_", " "),
                       BG,
                       ACCENT if "practice" in b else (GREEN if "test" in b else DIM),
                       bx, oy(y, ROW_H // 2 - 12))
            bx += bw + 8
        y += ROW_H + 20

        # ── §4: Timing ────────────────────────────────────────
        y += _section(screen, f_sec, "4  Timing Overrides (seconds)", oy(y))

        _label(screen, f_sm, "Planning time",  COL1, oy(y))
        planning_input.reposition(INP_X1, oy(y, 5)); planning_input.draw(screen, f_sm)
        _label(screen, f_sm, "Feedback time",  COL2, oy(y))
        feedback_input.reposition(INP_X2, oy(y, 5)); feedback_input.draw(screen, f_sm)

        y += ROW_H + 8
        _label(screen, f_sm, "Action time",    COL1, oy(y))
        action_input.reposition(INP_X1, oy(y, 5)); action_input.draw(screen, f_sm)
        _label(screen, f_sm, "Intertrial gap", COL2, oy(y))
        intertrial_input.reposition(INP_X2, oy(y, 5)); intertrial_input.draw(screen, f_sm)
        y += ROW_H + 20

        # ── §5: Ratio ─────────────────────────────────────────
        y += _section(screen, f_sec, "5  Repeated Grid Ratio (%)", oy(y))
        _label(screen, f_sm, "Practice blocks", COL1, oy(y))
        practice_ratio_input.reposition(INP_X1, oy(y, 5)); practice_ratio_input.draw(screen, f_sm)
        _label(screen, f_sm, "Test blocks",     COL2, oy(y))
        test_ratio_input.reposition(INP_X2, oy(y, 5)); test_ratio_input.draw(screen, f_sm)

        # Thin scroll indicator bar on right edge
        content_end = y + ROW_H + 30
        content_span = content_end - CONTENT_TOP
        view_span    = BY_LINE - CONTENT_TOP
        if content_span > view_span:
            sb_h  = view_span
            th    = max(28, int(sb_h * view_span / content_span))
            ty_   = 96 + int((sb_h - th) * scroll_y / max(1, content_span - view_span))
            pygame.draw.rect(screen, (30, 30, 52),
                             (WINDOW_WIDTH - 6, 96, 6, sb_h), border_radius=3)
            pygame.draw.rect(screen, BORDER_LT,
                             (WINDOW_WIDTH - 6, ty_, 6, th), border_radius=3)

        # ── Open dropdowns (still within clip) ───────────────
        if mode == "new":
            gender_dd.draw_open(screen, f_sm)
            hand_dd.draw_open(screen, f_sm)
        group_dd.draw_open(screen, f_sm)
        session_dd.draw_open(screen, f_sm)

        # ── End content clip ──────────────────────────────────
        screen.set_clip(None)

        # ── Bottom action bar (fixed) ─────────────────────────
        pygame.draw.line(screen, BORDER,
                         (0, WINDOW_HEIGHT - BH - 30),
                         (WINDOW_WIDTH, WINDOW_HEIGHT - BH - 30))

        if message:
            ms = f_sm.render(message, True, message_col)
            screen.blit(ms, (PAD, WINDOW_HEIGHT - BH - 24))

        launch_btn.draw(screen, f_med)
        data_btn.draw(screen, f_sm)
        export_btn.draw(screen, f_sm)

        pygame.display.flip()


# ── Validation ────────────────────────────────────────────────

def _validate_and_launch(mode, pid_box, pin_box, age_box, gender_dd, hand_dd,
                         ret_pid_box, ret_pin_box, group_dd, session_dd,
                         planning_input, action_input, feedback_input, intertrial_input,
                         practice_ratio_input, test_ratio_input):
    if mode == "new":
        pid     = pid_box.text.strip().upper()
        pin     = pin_box.text.strip()
        age_str = age_box.text.strip()
        if not pid:               return "Participant ID is required."
        if not pin.isdigit() or len(pin) != 4:
                                  return "PIN must be exactly 4 digits."
        if not age_str.isdigit(): return "Age must be a number."
        ok = create_participant(participant_id=pid, pin=pin,
                                group_name=group_dd.value, age=int(age_str),
                                gender=gender_dd.value, handedness=hand_dd.value)
        if not ok: return f"Participant ID '{pid}' already exists. Use Returning tab."
        participant_id = pid
    else:
        pid = ret_pid_box.text.strip().upper()
        pin = ret_pin_box.text.strip()
        p   = verify_participant(pid, pin)
        if not p: return "Participant not found or incorrect PIN."
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
