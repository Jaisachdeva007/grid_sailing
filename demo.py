# ============================================================
#  GRID-SAILING TASK — Interactive Demo
#
#  Walks through the full trial flow:
#    Screen 1 → Title / Welcome
#    Screen 2 → Key Mapping Tutorial
#    Screen 3 → Planning Stage  (grid on screen, countdown)
#    Screen 4 → Sequence Input  (type your planned sequence)
#    Screen 5 → Action Stage    (blank screen, cursor animates)
#    Screen 6 → Result / Score
#
#  Run:  python demo.py
#  Requires: pip install pygame
# ============================================================

import pygame
import sys
import time
from config import GRID_SIZE, WINDOW_WIDTH, WINDOW_HEIGHT, ANIMATION_DELAY_MS, PLANNING_TIME_SEC
from core.grid import find_valid_paths, apply_key

# ── Colours ──────────────────────────────────────────────────
BG          = (15,  15,  25)
PANEL       = (25,  25,  40)
CELL_DARK   = (35,  35,  55)
CELL_TRAIL  = (55,  90, 160)
GRID_LINE   = (50,  50,  75)
START_COL   = (200,  55,  55)
GOAL_COL    = (210, 160,  30)
CURSOR_COL  = (255, 255, 255)
WHITE       = (235, 235, 245)
DIM         = (110, 110, 140)
ACCENT      = ( 90, 150, 255)
GREEN       = ( 80, 200, 120)
ORANGE      = (230, 140,  50)

# ── Layout ───────────────────────────────────────────────────
CELL        = 86
LEFT        = 55
TOP         = 150
RIGHT_X     = LEFT + CELL * GRID_SIZE + 45   # x start of right info panel


# ── Helpers ──────────────────────────────────────────────────

def center_x(surface, text_surf):
    return surface.get_width() // 2 - text_surf.get_width() // 2

def draw_text(screen, font, text, color, x, y):
    surf = font.render(text, True, color)
    screen.blit(surf, (x, y))
    return surf.get_height()

def draw_centered(screen, font, text, color, y):
    surf = font.render(text, True, color)
    screen.blit(surf, (center_x(screen, surf), y))
    return surf.get_height()

def draw_cell(screen, row, col, color, border_r=10):
    x = LEFT + col * CELL + 3
    y = TOP  + row * CELL + 3
    rect = pygame.Rect(x, y, CELL - 6, CELL - 6)
    pygame.draw.rect(screen, color, rect, border_radius=border_r)
    pygame.draw.rect(screen, GRID_LINE, rect, width=1, border_radius=border_r)

def draw_grid_base(screen, start, goal, trail=None, show_cursor=None, font_sm=None):
    """Draw the 5x5 grid with optional trail and cursor."""
    trail = trail or set()
    for r in range(GRID_SIZE):
        for c in range(GRID_SIZE):
            if (r, c) == goal:
                color = GOAL_COL
            elif (r, c) == start:
                color = START_COL
            elif (r, c) in trail:
                color = CELL_TRAIL
            else:
                color = CELL_DARK
            draw_cell(screen, r, c, color)

            # Labels for start and goal
            if font_sm:
                if (r, c) == start:
                    lbl = font_sm.render("MOUSE", True, WHITE)
                    screen.blit(lbl, (LEFT + c*CELL + CELL//2 - lbl.get_width()//2,
                                      TOP  + r*CELL + CELL//2 - lbl.get_height()//2))
                elif (r, c) == goal:
                    lbl = font_sm.render("CHEESE", True, (40, 30, 5))
                    screen.blit(lbl, (LEFT + c*CELL + CELL//2 - lbl.get_width()//2,
                                      TOP  + r*CELL + CELL//2 - lbl.get_height()//2))

    # Cursor dot
    if show_cursor:
        cx = LEFT + show_cursor[1]*CELL + CELL//2
        cy = TOP  + show_cursor[0]*CELL + CELL//2
        pygame.draw.circle(screen, CURSOR_COL, (cx, cy), 16)
        pygame.draw.circle(screen, ACCENT,     (cx, cy), 16, 3)

def draw_key_legend(screen, font_sm):
    """Draw the finger-key mapping legend on the right panel."""
    mappings = [
        ("Key  1", "Index  finger", "^    Up"),
        ("Key  2", "Middle finger", "v>   Down-Right"),
        ("Key  3", "Ring   finger", "v<   Down-Left"),
    ]
    y = TOP
    draw_text(screen, font_sm, "KEY  MAPPINGS", ACCENT, RIGHT_X, y); y += 30
    pygame.draw.line(screen, GRID_LINE, (RIGHT_X, y), (RIGHT_X + 220, y)); y += 15

    for key_lbl, finger, move in mappings:
        draw_text(screen, font_sm, key_lbl, WHITE,   RIGHT_X,       y)
        draw_text(screen, font_sm, finger,  DIM,     RIGHT_X + 70,  y)
        draw_text(screen, font_sm, move,    ACCENT,  RIGHT_X,       y + 18)
        y += 50


# ═══════════════════════════════════════════════════════════════
#  SCREENS
# ═══════════════════════════════════════════════════════════════

def screen_title(screen, fonts):
    """Screen 1 — Welcome / title card."""
    screen.fill(BG)
    f_big, f_med, f_sm, f_xs = fonts

    draw_centered(screen, f_big, "Grid-Sailing Task", WHITE, 180)
    draw_centered(screen, f_sm,  "A Motor Sequence Learning Experiment", DIM, 240)

    # Three condition pills
    conditions = [("Physical Practice", GREEN), ("Motor Imagery", ACCENT), ("Control", ORANGE)]
    total_w = sum(180 for _ in conditions) + 30
    sx = WINDOW_WIDTH // 2 - total_w // 2
    for label, col in conditions:
        pill = pygame.Rect(sx, 310, 175, 38)
        pygame.draw.rect(screen, (*col, 60), pill, border_radius=20)
        pygame.draw.rect(screen, col, pill, width=2, border_radius=20)
        lbl = f_xs.render(label, True, col)
        screen.blit(lbl, (sx + 88 - lbl.get_width()//2, 322))
        sx += 185

    draw_centered(screen, f_xs, "Participants learn novel key-finger mappings to navigate a cursor", DIM, 390)
    draw_centered(screen, f_xs, "from a start position to a goal position on a 5×5 grid.", DIM, 412)

    draw_centered(screen, f_sm, "Press  SPACE  to continue", ACCENT, 500)


def screen_keymapping(screen, fonts):
    """Screen 2 — Key mapping tutorial."""
    screen.fill(BG)
    f_big, f_med, f_sm, f_xs = fonts

    draw_text(screen, f_med, "Key Mappings", WHITE, LEFT, 40)
    draw_text(screen, f_xs,  "Each key is assigned to a finger and moves the cursor in a specific direction.", DIM, LEFT, 80)

    rows = [
        ("1",  "Index finger",  "^",  "Moves cursor  ONE square  UP",         START_COL),
        ("2",  "Middle finger", "v>", "Moves cursor  DOWN and to the RIGHT",   ACCENT),
        ("3",  "Ring finger",   "v<", "Moves cursor  DOWN and to the LEFT",    GREEN),
    ]
    y = 140
    for key, finger, arrow, desc, col in rows:
        # Key badge
        badge = pygame.Rect(LEFT, y, 52, 52)
        pygame.draw.rect(screen, col, badge, border_radius=10)
        k = f_med.render(key, True, BG)
        screen.blit(k, (LEFT + 26 - k.get_width()//2, y + 26 - k.get_height()//2))

        # Arrow
        arr = f_med.render(arrow, True, col)
        screen.blit(arr, (LEFT + 75, y + 8))

        # Labels
        draw_text(screen, f_sm, finger, WHITE, LEFT + 115, y + 2)
        draw_text(screen, f_xs, desc,   DIM,   LEFT + 115, y + 26)
        y += 80

    # Mini diagram showing a single move
    draw_text(screen, f_xs, "Example: pressing  2  from the red square moves the cursor diagonally down-right.", DIM, LEFT, 390)

    # Draw a tiny 3x3 preview grid
    gx, gy, gs = LEFT + 10, 430, 60
    for r in range(3):
        for c in range(3):
            col = START_COL if (r,c)==(0,1) else ACCENT if (r,c)==(1,2) else CELL_DARK
            pygame.draw.rect(screen, col, (gx+c*gs+2, gy+r*gs+2, gs-4, gs-4), border_radius=6)
            pygame.draw.rect(screen, GRID_LINE, (gx+c*gs+2, gy+r*gs+2, gs-4, gs-4), width=1, border_radius=6)
    arrow_lbl = f_xs.render("Key 2  →", True, ACCENT)
    screen.blit(arrow_lbl, (gx + 3*gs + 15, gy + gs//2))

    draw_centered(screen, f_sm, "Press  SPACE  to start the trial", ACCENT, 610)


def screen_planning(screen, fonts, start, goal, elapsed_sec, font_sm, hint_seq=None):
    """Screen 3 — Planning stage: grid shown, countdown ticking."""
    screen.fill(BG)
    f_big, f_med, f_sm2, f_xs = fonts

    # Stage label
    draw_text(screen, f_med, "PLANNING  STAGE", ACCENT, LEFT, 30)
    draw_text(screen, f_xs,  "Study the grid. Plan your key sequence to move the mouse to the cheese.", DIM, LEFT, 68)

    draw_grid_base(screen, start, goal, font_sm=font_sm)
    draw_key_legend(screen, font_sm)

    # Countdown timer — turns orange when < 2 sec left
    remaining = max(0, PLANNING_TIME_SEC - elapsed_sec)
    timer_col  = ORANGE if remaining < 2 else WHITE
    timer_surf = f_big.render(f"{remaining:.1f}s", True, timer_col)
    screen.blit(timer_surf, (RIGHT_X, TOP + 180))
    draw_text(screen, font_sm, "Time remaining", DIM, RIGHT_X, TOP + 225)

    # Demo hint — shown in bottom corner so you can always demo a win
    if hint_seq:
        hint = "  →  ".join(str(k) for k in hint_seq)
        draw_text(screen, f_xs, f"[demo hint: {hint}]", (55, 55, 75), LEFT, WINDOW_HEIGHT - 45)

    draw_centered(screen, f_xs, "Press  SPACE  when you have your sequence ready", DIM, WINDOW_HEIGHT - 22)


def screen_input(screen, fonts, start, goal, typed, font_sm):
    """Screen 4 — Participant types their planned sequence."""
    screen.fill(BG)
    f_big, f_med, f_sm2, f_xs = fonts

    draw_text(screen, f_med, "INPUT  YOUR  SEQUENCE", WHITE, LEFT, 30)
    draw_text(screen, f_xs,  "Type your key sequence using  1, 2, 3  — press  ENTER  to confirm.", DIM, LEFT, 68)

    # Show grid (read-only reminder)
    draw_grid_base(screen, start, goal, font_sm=font_sm)

    # Input box on the right
    draw_text(screen, font_sm, "Your sequence:", ACCENT, RIGHT_X, TOP)
    display_seq = "  →  ".join(typed) if typed else "_"
    seq_surf = f_sm2.render(display_seq, True, WHITE)
    screen.blit(seq_surf, (RIGHT_X, TOP + 35))

    # Blinking cursor bar
    if int(time.time() * 2) % 2 == 0:
        bar_x = RIGHT_X + seq_surf.get_width() + 4
        pygame.draw.rect(screen, WHITE, (bar_x, TOP + 35, 3, seq_surf.get_height()))

    draw_text(screen, font_sm, f"Keys pressed: {len(typed)}", DIM, RIGHT_X, TOP + 80)
    draw_text(screen, f_xs, "Press ENTER to confirm  |  BACKSPACE to undo", DIM, RIGHT_X, TOP + 115)


def screen_action(screen, fonts, start, goal, path, step, typed_seq, font_sm):
    """Screen 5 — Action stage: blank then cursor animates through the path."""
    screen.fill(BG)
    f_big, f_med, f_sm2, f_xs = fonts

    draw_text(screen, f_med, "ACTION  STAGE", GREEN, LEFT, 30)
    draw_text(screen, f_xs,  "Executing your sequence...", DIM, LEFT, 68)

    cursor = path[min(step, len(path)-1)]
    trail  = set(path[:step])
    draw_grid_base(screen, start, goal, trail=trail, show_cursor=cursor, font_sm=font_sm)

    # Right panel — sequence replay
    draw_text(screen, font_sm, "SEQUENCE", ACCENT, RIGHT_X, TOP)
    key_labels = {1: "^   Up", 2: "v>  Down-Right", 3: "v<  Down-Left"}
    for i, key in enumerate(typed_seq):
        if i < step:
            col = DIM
        elif i == step:
            col = GREEN
        else:
            col = (60, 60, 80)
        prefix = "▶ " if i == step else f"{i+1}. "
        draw_text(screen, font_sm, prefix + f"Key {key}  {key_labels[key]}", col, RIGHT_X, TOP + 32 + i*26)

    prog = f_xs.render(f"Step  {min(step+1, len(typed_seq))}  /  {len(typed_seq)}", True, DIM)
    screen.blit(prog, (RIGHT_X, TOP + 32 + len(typed_seq)*26 + 12))


def screen_result(screen, fonts, correct, typed_seq, correct_seq, score):
    """Screen 6 — Result: did you reach the cheese?"""
    screen.fill(BG)
    f_big, f_med, f_sm, f_xs = fonts

    if correct:
        draw_centered(screen, f_big, "Reached the Cheese!", GOAL_COL, 180)
        draw_centered(screen, f_sm,  "Correct sequence — well done!", GREEN, 255)
    else:
        draw_centered(screen, f_big, "Missed the Goal", ORANGE, 180)
        draw_centered(screen, f_sm,  "Try a different sequence next time.", ORANGE, 255)

    draw_centered(screen, f_xs, f"Your sequence:     {'  →  '.join(str(k) for k in typed_seq)}", DIM, 320)
    draw_centered(screen, f_xs, f"Optimal sequence:  {'  →  '.join(str(k) for k in correct_seq)}", DIM, 345)

    # Score badge
    badge = pygame.Rect(WINDOW_WIDTH//2 - 100, 395, 200, 70)
    pygame.draw.rect(screen, PANEL, badge, border_radius=14)
    pygame.draw.rect(screen, GOAL_COL if correct else ORANGE, badge, width=2, border_radius=14)
    score_lbl = f_med.render(f"Score:  {score}", True, GOAL_COL if correct else ORANGE)
    screen.blit(score_lbl, (WINDOW_WIDTH//2 - score_lbl.get_width()//2, 415))

    draw_centered(screen, f_sm, "Press  SPACE  to play again   |   ESC  to quit", ACCENT, 530)


# ═══════════════════════════════════════════════════════════════
#  MAIN LOOP
# ═══════════════════════════════════════════════════════════════

def run_demo():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Grid-Sailing Task — Demo")
    clock = pygame.time.Clock()

    fonts = (
        pygame.font.SysFont("Arial", 32, bold=True),   # f_big
        pygame.font.SysFont("Arial", 22, bold=True),   # f_med
        pygame.font.SysFont("Arial", 17),              # f_sm
        pygame.font.SysFont("Arial", 13),              # f_xs
    )
    font_sm = fonts[2]

    def load_puzzle():
        start = (0, 2)
        puzzles = find_valid_paths(*start)
        # Optimal = shortest valid path (uses all 3 keys, min 7 presses, no revisits)
        puzzles.sort(key=lambda p: p["length"])
        p = puzzles[0]
        path = [start]
        pos  = start
        for k in p["sequence"]:
            pos = apply_key(pos[0], pos[1], k)
            path.append(pos)
        return start, tuple(p["goal"]), p["sequence"], path

    # State machine states
    TITLE, KEYMAPPING, PLANNING, INPUT, ACTION, RESULT = range(6)
    state = TITLE

    start, goal, correct_seq, full_path = load_puzzle()
    typed_seq    = []
    score        = 0
    plan_start   = None
    action_step  = 0
    action_timer = 0
    correct      = False

    while True:
        now = pygame.time.get_ticks()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()

            if event.type == pygame.KEYDOWN:

                if event.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()

                # ── TITLE ───────────────────────────────────
                if state == TITLE and event.key == pygame.K_SPACE:
                    state = KEYMAPPING

                # ── KEY MAPPING ──────────────────────────────
                elif state == KEYMAPPING and event.key == pygame.K_SPACE:
                    state = PLANNING
                    plan_start = time.time()

                # ── PLANNING ─────────────────────────────────
                elif state == PLANNING and event.key == pygame.K_SPACE:
                    state = INPUT
                    typed_seq = []

                # ── INPUT ────────────────────────────────────
                elif state == INPUT:
                    if event.key in (pygame.K_1, pygame.K_KP1): typed_seq.append(1)
                    elif event.key in (pygame.K_2, pygame.K_KP2): typed_seq.append(2)
                    elif event.key in (pygame.K_3, pygame.K_KP3): typed_seq.append(3)
                    elif event.key == pygame.K_BACKSPACE and typed_seq: typed_seq.pop()
                    elif event.key == pygame.K_RETURN and typed_seq:
                        state        = ACTION
                        action_step  = 0
                        action_timer = now

                # ── RESULT ───────────────────────────────────
                elif state == RESULT and event.key == pygame.K_SPACE:
                    start, goal, correct_seq, full_path = load_puzzle()
                    typed_seq   = []
                    state       = PLANNING
                    plan_start  = time.time()

        # ── Auto-advance planning stage ──────────────────────
        if state == PLANNING and plan_start:
            if time.time() - plan_start >= PLANNING_TIME_SEC:
                state = INPUT
                typed_seq = []

        # ── Auto-advance action animation ────────────────────
        if state == ACTION:
            if now - action_timer >= ANIMATION_DELAY_MS:
                action_step  += 1
                action_timer  = now
                if action_step >= len(typed_seq):
                    # Evaluate result
                    pos = start
                    for k in typed_seq:
                        nxt = apply_key(pos[0], pos[1], k)
                        if nxt: pos = nxt
                    correct = (pos == goal)
                    if correct:
                        # Base 10 points + up to 10 bonus for matching or beating the optimal length
                        efficiency_bonus = max(0, 10 - max(0, len(typed_seq) - len(correct_seq)))
                        score += 10 + efficiency_bonus
                    state = RESULT

        # ── Draw current screen ──────────────────────────────
        screen.fill(BG)

        if state == TITLE:
            screen_title(screen, fonts)

        elif state == KEYMAPPING:
            screen_keymapping(screen, fonts)

        elif state == PLANNING:
            elapsed = time.time() - plan_start if plan_start else 0
            screen_planning(screen, fonts, start, goal, elapsed, font_sm, hint_seq=correct_seq)

        elif state == INPUT:
            screen_input(screen, fonts, start, goal, [str(k) for k in typed_seq], font_sm)

        elif state == ACTION:
            # Build partial path from typed_seq
            pos  = start
            path = [start]
            for k in typed_seq[:action_step]:
                nxt = apply_key(pos[0], pos[1], k)
                if nxt:
                    pos = nxt
                    path.append(pos)
            screen_action(screen, fonts, start, goal, path, action_step, typed_seq, font_sm)

        elif state == RESULT:
            # Replay finished path for result screen background
            pos  = start
            path = [start]
            for k in typed_seq:
                nxt = apply_key(pos[0], pos[1], k)
                if nxt:
                    pos = nxt
                    path.append(pos)
            screen_result(screen, fonts, correct, typed_seq, correct_seq, score)

        pygame.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    run_demo()
