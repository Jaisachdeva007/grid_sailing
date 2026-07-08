# ============================================================
#  GRID-SAILING TASK — Key Mapping Tutorial
#
#  *** Juliet does NOT need to edit this file. ***
#
#  This tutorial screen is shown ONCE, automatically, before the
#  very first familiarisation block of Session 1.
#  It is not shown again in Sessions 2 or 3 (participant already knows).
#
#  What it teaches:
#    - Which physical key (1, 2, or 3) maps to which direction
#    - Key 1 (index finger)  → UP
#    - Key 2 (middle finger) → DOWN-RIGHT
#    - Key 3 (ring finger)   → DOWN-LEFT
#
#  How it works:
#    - Three animated pages cycle through keys 1 → 2 → 3, each showing
#      the cursor moving on a small 3×3 demo grid
#    - The participant presses SPACE to advance through each page
#    - At the end, they must press each key (1, 2, 3) once to confirm
#      they understand before the real trials begin
#
#  The key directions are defined in KEY_MAPPINGS in config.py.
# ============================================================

import pygame
import sys
import math
import time
from config import WINDOW_WIDTH, WINDOW_HEIGHT, FPS

BG      = (12,  12,  22)
PANEL   = (22,  22,  38)
BORDER  = (52,  52,  80)
WHITE   = (230, 230, 242)
DIM     = (100, 100, 138)
ACCENT  = ( 88, 148, 255)
GREEN   = ( 58, 196, 108)
AMBER   = (210, 158,  28)
RED_C   = (175,  45,  45)
CELL_D  = (28,  28,  48)
GRID_B  = (44,  44,  70)

CX = WINDOW_WIDTH  // 2
CY = WINDOW_HEIGHT // 2


def _panel(screen, x, y, w, h, bc=BORDER):
    pygame.draw.rect(screen, PANEL,  (x, y, w, h), border_radius=12)
    pygame.draw.rect(screen, bc,     (x, y, w, h), width=1, border_radius=12)


def _t(screen, font, text, col, x, y, center=False):
    s = font.render(text, True, col)
    if center:
        screen.blit(s, (x - s.get_width() // 2, y))
    else:
        screen.blit(s, (x, y))
    return s


def _mini_grid(screen, font, cell=72, left=None, top=None,
               cursor=(0, 0), trail=None, goal=None):
    """Render a small 3×3 demo grid."""
    if trail is None: trail = set()
    left = left or CX - cell * 3 // 2
    top  = top  or CY - cell * 3 // 2 - 40

    for r in range(3):
        for c in range(3):
            px = left + c * cell + 3
            py = top  + r * cell + 3
            sz = cell - 6
            rect = pygame.Rect(px, py, sz, sz)
            if (r, c) == goal:
                bg = AMBER
            elif (r, c) in trail:
                bg = (42, 78, 148)
            elif (r, c) == (0, 0):   # fixed start
                bg = RED_C
            else:
                bg = CELL_D
            pygame.draw.rect(screen, bg,     rect, border_radius=8)
            pygame.draw.rect(screen, GRID_B, rect, width=1, border_radius=8)

    # Cursor
    if cursor:
        cx = left + cursor[1] * cell + cell // 2
        cy = top  + cursor[0] * cell + cell // 2
        pygame.draw.circle(screen, WHITE,  (cx, cy), 16)
        pygame.draw.circle(screen, ACCENT, (cx, cy), 16, 3)
        pygame.draw.circle(screen, BG,     (cx, cy),  5)

    return left, top, cell * 3


# ── Page 1–3: one key per page ────────────────────────────────

PAGES = [
    {
        "key":    "1",
        "finger": "Index finger",
        "move":   "UP  ↑",
        "color":  ACCENT,
        "delta":  (-1, 0),
        "desc":   "Press Key 1 to move the cursor one step UP.",
    },
    {
        "key":    "2",
        "finger": "Middle finger",
        "move":   "DOWN-RIGHT  ↘",
        "color":  GREEN,
        "delta":  (1, 1),
        "desc":   "Press Key 2 to move the cursor DOWN and RIGHT.",
    },
    {
        "key":    "3",
        "finger": "Ring finger",
        "move":   "DOWN-LEFT  ↙",
        "color":  AMBER,
        "delta":  (1, -1),
        "desc":   "Press Key 3 to move the cursor DOWN and LEFT.",
    },
]


def _draw_page(screen, fonts, page_idx, anim_t):
    """Draw one of the three key introduction pages."""
    f_big, f_med, f_sm, f_xs = fonts
    p = PAGES[page_idx]

    screen.fill(BG)

    # Step indicator dots
    for i in range(3):
        col  = p["color"] if i == page_idx else BORDER
        pygame.draw.circle(screen, col, (CX - 20 + i * 20, 28), 5)

    # Title
    _t(screen, f_big, f"Key  {p['key']}  —  {p['finger']}", p["color"], CX, 52, center=True)
    _t(screen, f_sm,  p["move"], WHITE, CX, 94, center=True)

    # Animated mini grid — cursor bounces between start and moved position
    pulse  = (math.sin(anim_t * 3) + 1) / 2   # 0→1→0
    dr, dc = p["delta"]
    # interpolate cursor position for smooth anim feel (just alternate)
    phase  = int(anim_t * 1.2) % 2
    cur    = (1 + dr * phase, 1 + dc * phase)   # starts at (1,1) centre of 3x3
    cur    = (max(0, min(2, cur[0])), max(0, min(2, cur[1])))
    _mini_grid(screen, f_xs, cell=80, cursor=cur)

    # Arrow label
    _t(screen, f_xs, p["desc"], DIM, CX, CY + 160, center=True)

    # Info card
    card_y = CY + 195
    _panel(screen, CX - 240, card_y, 480, 60, p["color"])
    _t(screen, f_sm,
       f"Your  {p['finger']}  presses  Key {p['key']}  →  cursor moves  {p['move']}",
       WHITE, CX, card_y + 18, center=True)

    # Navigation hint
    hint = "SPACE — next" if page_idx < 2 else "SPACE — confirm keys"
    _t(screen, f_xs, hint, DIM, CX, WINDOW_HEIGHT - 60, center=True)
    _t(screen, f_xs, f"Step  {page_idx + 1}  of  3", DIM,
       CX, WINDOW_HEIGHT - 38, center=True)


# ── Page 4: press-to-confirm ──────────────────────────────────

def _draw_confirm(screen, fonts, confirmed):
    """Participant must physically press 1, 2, 3 to continue."""
    f_big, f_med, f_sm, f_xs = fonts

    screen.fill(BG)
    _t(screen, f_big, "Confirm you're ready", WHITE, CX, 52, center=True)
    _t(screen, f_sm, "Press each key once to confirm you understand the mappings.",
       DIM, CX, 92, center=True)

    keys = [
        ("1", "Index",  "Up",         ACCENT),
        ("2", "Middle", "Down-Right",  GREEN),
        ("3", "Ring",   "Down-Left",   AMBER),
    ]
    bw, bh = 280, 72
    bx = CX - bw // 2
    by = 160
    for i, (k, finger, move, col) in enumerate(keys):
        done = i in confirmed
        bc   = col if done else BORDER
        _panel(screen, bx, by, bw, bh, bc)

        # Tick or waiting dot
        mark     = "✓" if done else "·"
        mark_col = col if done else DIM
        _t(screen, f_med, mark,   mark_col, bx + 18, by + 22)
        _t(screen, f_med, f"Key {k}", col if done else DIM, bx + 52, by + 16)
        _t(screen, f_xs,  f"{finger}  —  {move}", DIM,   bx + 52, by + 44)
        by += 84

    if len(confirmed) == 3:
        _t(screen, f_med, "All set!  Press SPACE to begin.", GREEN, CX, by + 16, center=True)
    else:
        remaining = 3 - len(confirmed)
        _t(screen, f_xs, f"{remaining} key(s) left to press…", DIM,
           CX, by + 20, center=True)


# ── Entry point ───────────────────────────────────────────────

def run_tutorial(screen, clock, fonts):
    """
    Display the key-mapping tutorial.
    Returns when participant has confirmed all three keys.
    """
    page      = 0       # 0-2 = intro pages, 3 = confirm
    confirmed = set()
    start_t   = time.time()

    while True:
        clock.tick(FPS)
        anim_t = time.time() - start_t

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()

            if event.type == pygame.KEYDOWN:
                if page < 3:
                    if event.key == pygame.K_SPACE:
                        page += 1
                        start_t = time.time()
                else:
                    # Confirm page — collect key presses
                    if event.key in (pygame.K_1, pygame.K_KP1):
                        confirmed.add(0)
                    elif event.key in (pygame.K_2, pygame.K_KP2):
                        confirmed.add(1)
                    elif event.key in (pygame.K_3, pygame.K_KP3):
                        confirmed.add(2)
                    elif event.key == pygame.K_SPACE and len(confirmed) == 3:
                        return   # all confirmed → begin

        if page < 3:
            _draw_page(screen, fonts, page, anim_t)
        else:
            _draw_confirm(screen, fonts, confirmed)

        pygame.display.flip()
