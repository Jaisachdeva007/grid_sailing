"""
Generate reference screenshots for paper figures (headless render).
Run:  python make_screenshots.py
Output: ~/Desktop/Tier Previews/planning_stage.png
        ~/Desktop/Tier Previews/random_grid.png
        ~/Desktop/Tier Previews/break_screen.png
        ~/Desktop/Tier Previews/action_stage_pp.png
        ~/Desktop/Tier Previews/action_stage_mi.png
        ~/Desktop/Tier Previews/tier_progression.png

For live in-session screenshots, press F12 during any trial —
it saves a timestamped PNG to the Desktop automatically.
"""
import os, sys, time, math
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(__file__))

import pygame
pygame.init()

from core.trial import (
    TrialData, BG,
    _draw_stage_planning,
    _draw_stage_feedback,
    _draw_stage_action,
    _draw_mouse_icon,
    _draw_mouse_accessory,
    _MOUSE_TIERS,
)

# Colours matching session.py card screens
_PANEL  = (20,  20,  36)
_BORDER = (48,  48,  76)
_WHITE  = (245, 245, 255)
_DIM    = (118, 118, 158)
_ACCENT = (88,  148, 255)
_GREEN  = (52,  200, 100)

W, H = 1440, 900
_fs  = max(0.80, min(1.40, H / 900))

screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("Grid Sailing — Screenshot")

fonts = (
    pygame.font.SysFont("Helvetica Neue", int(52 * _fs), bold=True),
    pygame.font.SysFont("Helvetica Neue", int(34 * _fs), bold=True),
    pygame.font.SysFont("Helvetica Neue", int(26 * _fs)),
    pygame.font.SysFont("Helvetica Neue", int(20 * _fs)),
)

OUT = "/Users/jaisachdeva/Desktop/Tier Previews"
os.makedirs(OUT, exist_ok=True)


def make_trial(start, goal, seq, sub_goal=None):
    t = TrialData(
        session_id=1, participant_id="demo", trial_number=7,
        grid_type="random", start=start, goal=goal,
        optimal_sequence=seq, group="PP",
        all_optimal_sequences=[seq],
    )
    t.planned_sequence = list(seq)
    t.sub_goal = sub_goal
    return t


# ── Screenshot 1: Planning stage ──────────────────────────────
# Valid moves: 1=UP (r-1,c), 2=DOWN-RIGHT (r+1,c+1), 3=DOWN-LEFT (r+1,c-1)
# 7-move path using all 3 keys, NO cell revisits:
# start(6,4) →3→(7,3) →2→(8,4) →2→(9,5)[sub_goal] →1→(8,5) →1→(7,5) →1→(6,5) →1→(5,5)[goal]
trial_plan = make_trial(start=(6, 4), goal=(5, 5),
                        seq=[3, 2, 2, 1, 1, 1, 1],
                        sub_goal=(9, 5))

screen.fill(BG)
_draw_stage_planning(
    screen, fonts, trial_plan,
    elapsed=3.2, p_time=10.0,
    total_trials=20, block_type="practice", sn=1,
    cum_score=9600, show_timer=True, eyes_open=True,
    amb_particles=None, typed_seq=[2, 2, 3, 1, 1, 1, 1], btns={},
    mouse_tier=3,
)
pygame.display.flip()
path = os.path.join(OUT, "planning_stage.png")
pygame.image.save(screen, path)
print(f"Saved: {path}")


# ── Screenshot 2: Feedback/replay, correct trial ──────────────
# Same 7-move puzzle, mid-replay after 5 of 7 moves:
# cursor at (7,5) heading UP toward goal (5,5) — clearly 2 steps away
trial_nav = make_trial(start=(6, 4), goal=(5, 5),
                       seq=[3, 2, 2, 1, 1, 1, 1],
                       sub_goal=(9, 5))
trial_nav.reward_score = 100
trial_nav.is_correct   = True

now = time.time()
trail = {
    (6, 4): now - 2.4,
    (7, 3): now - 1.9,
    (8, 4): now - 1.4,
    (9, 5): now - 1.0,
    (8, 5): now - 0.5,
}
cursor = (7, 5)

screen.fill(BG)
_draw_stage_feedback(
    screen, fonts, trial_nav,
    cum_score=9600, rp_cursor=cursor, rp_trail=trail, rp_done=False,
    total_trials=20, block_type="practice", sn=1,
    streak=3, show_score=True, mouse_tier=3,
)
pygame.display.flip()
path = os.path.join(OUT, "random_grid.png")
pygame.image.save(screen, path)
print(f"Saved: {path}")

# ── Screenshot 3: Take a Short Break screen ──────────────────
def _draw_break_card(screen, fonts, title, title_col, body_lines, hint):
    """Single-frame render of a card screen (no event loop)."""
    f_big, f_med, f_sm, f_xs = fonts
    W, H   = screen.get_width(), screen.get_height()
    CX, CY = W // 2, H // 2
    CW = min(W - 80, max(740, W * 2 // 5))
    max_body_w = CW - 56

    def _wrap(text):
        if not text:
            return [""]
        words, out, cur = text.split(), [], ""
        for w in words:
            test = (cur + " " + w).strip()
            if f_sm.size(test)[0] <= max_body_w:
                cur = test
            else:
                if cur: out.append(cur)
                cur = w
        if cur: out.append(cur)
        return out or [""]

    wrapped = []
    for text, col in body_lines:
        for sub in _wrap(text): wrapped.append((sub, col))

    f_big_h  = f_big.get_height()
    f_sm_h   = f_sm.get_height()
    f_xs_h   = f_xs.get_height()
    line_h   = f_sm_h + 8
    ts_probe = f_big.render(title, True, _WHITE)
    f_title  = f_med if ts_probe.get_width() > CW - 32 else f_big
    f_title_h = f_title.get_height()
    CH = max(240, 16 + f_title_h + 14 + 12 + len(wrapped) * line_h + f_sm_h + 24)

    screen.fill(BG)
    for gx in range(0, W + 48, 48):
        for gy in range(0, H + 48, 48):
            pygame.draw.circle(screen, (18, 18, 36), (gx, gy), 1)

    cx2, cy2 = CX - CW // 2, CY - CH // 2
    pygame.draw.rect(screen, (4, 4, 10),   (cx2+4, cy2+6, CW, CH), border_radius=20)
    pygame.draw.rect(screen, _PANEL,       (cx2, cy2, CW, CH),     border_radius=20)
    pygame.draw.rect(screen, _BORDER,      (cx2, cy2, CW, CH),     width=1, border_radius=20)
    pygame.draw.rect(screen, title_col,    (cx2+1, cy2+1, CW-2, 6), border_radius=20)

    y = cy2 + 16
    ts = f_title.render(title, True, _WHITE)
    screen.blit(ts, (CX - ts.get_width() // 2, y))
    y += f_title_h + 14
    pygame.draw.line(screen, _BORDER, (cx2+32, y), (cx2+CW-32, y))
    y += 12
    for text, col in wrapped:
        if text:
            ls = f_sm.render(text, True, col)
            screen.blit(ls, (CX - ls.get_width() // 2, y))
        y += line_h
    hs = f_sm.render(hint, True, _ACCENT)
    screen.blit(hs, (CX - hs.get_width() // 2, cy2 + CH - f_sm_h - 16))

_draw_break_card(
    screen, fonts,
    title="Take a Short Break  (block 2 of 5)",
    title_col=_GREEN,
    body_lines=[
        ("Familiarization part 2 complete.", _DIM),
        ("", _DIM),
        ("Well done! Take a moment to rest before continuing.", _DIM),
    ],
    hint="Press  SPACE  when you are ready to continue",
)
pygame.display.flip()
path = os.path.join(OUT, "break_screen.png")
pygame.image.save(screen, path)
print(f"Saved: {path}")

# ── Screenshot 4: Action stage — PP (physical press) ─────────────────────────
trial_act = make_trial(start=(6, 4), goal=(5, 5),
                       seq=[2, 2, 3, 1, 1, 1, 1],
                       sub_goal=(9, 5))
trial_act.planned_sequence = [2, 2, 3, 1, 1, 1, 1]

screen.fill(BG)
_draw_stage_action(
    screen, fonts, trial_act,
    is_mi=False, is_pp=True,
    total_trials=20, block_type="practice", sn=1,
    cum_score=9600, show_score=True,
)
pygame.display.flip()
path = os.path.join(OUT, "action_stage_pp.png")
pygame.image.save(screen, path)
print(f"Saved: {path}")


# ── Screenshot 5: Action stage — MI (imagery, mid-imagine) ───────────────────
trial_mi = make_trial(start=(6, 4), goal=(5, 5),
                      seq=[2, 2, 3, 1, 1, 1, 1],
                      sub_goal=(9, 5))
trial_mi.planned_sequence = [2, 2, 3, 1, 1, 1, 1]

screen.fill(BG)
_draw_stage_action(
    screen, fonts, trial_mi,
    is_mi=True, is_pp=False,
    total_trials=20, block_type="practice", sn=1,
    cum_score=9600, show_score=True,
    mi_space_held=True,
    mi_space_start=time.time() - 1.2,
)
pygame.display.flip()
path = os.path.join(OUT, "action_stage_mi.png")
pygame.image.save(screen, path)
print(f"Saved: {path}")


# ── Screenshot 6: Tier progression figure ────────────────────────────────────
# Shows all 6 mouse tiers in a row with score thresholds.
def _draw_tier_progression(surface, fonts):
    f_big, f_med, f_sm, f_xs = fonts
    W, H = surface.get_width(), surface.get_height()
    surface.fill((15, 15, 25))

    # title
    title = f_med.render("Mouse Progression", True, (245, 245, 255))
    surface.blit(title, (W // 2 - title.get_width() // 2, 24))

    n      = len(_MOUSE_TIERS)
    col_w  = W // n
    icon_y = H // 2 - 10
    icon_sz = 72

    for i, (threshold, body_col, _, tier_name, _, _sub) in enumerate(_MOUSE_TIERS):
        cx = col_w * i + col_w // 2

        # connector arrow (→) between tiers
        if i > 0:
            ax = col_w * i - 14
            arrow = f_med.render("→", True, (80, 80, 110))
            surface.blit(arrow, (ax - arrow.get_width() // 2, icon_y - arrow.get_height() // 2))

        # mouse icon
        _draw_mouse_icon(surface, cx, icon_y, eyes_open=True,
                         cell_sz=icon_sz, mouse_tier=i)
        if i > 0:
            _draw_mouse_accessory(surface, cx, icon_y, i, icon_sz / 80.0)

        # tier name
        nm = f_xs.render(tier_name, True, body_col if i > 0 else (160, 160, 180))
        surface.blit(nm, (cx - nm.get_width() // 2, icon_y + icon_sz // 2 + 10))

        # score label
        if threshold == 0:
            score_lbl = "Start"
        else:
            score_lbl = f"{threshold:,} pts"
        sl = f_xs.render(score_lbl, True, (100, 100, 140))
        surface.blit(sl, (cx - sl.get_width() // 2, icon_y + icon_sz // 2 + 32))

_draw_tier_progression(screen, fonts)
pygame.display.flip()
path = os.path.join(OUT, "tier_progression.png")
pygame.image.save(screen, path)
print(f"Saved: {path}")


pygame.quit()
print(f"\nAll screenshots saved to: {OUT}/")
