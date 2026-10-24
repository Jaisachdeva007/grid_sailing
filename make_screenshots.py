"""
Generate reference screenshots for paper figures (headless render).
Run:  python make_screenshots.py
Output: ~/Desktop/Tier Previews/planning_stage.png
        ~/Desktop/Tier Previews/random_grid.png

For live in-session screenshots, press F12 during any trial —
it saves a timestamped PNG to the Desktop automatically.
"""
import os, sys, time
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(__file__))

import pygame
pygame.init()

from core.trial import (
    TrialData, BG,
    _draw_stage_planning,
    _draw_stage_feedback,
)

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
# 7-move path: start(7,3) → 2:(8,4) → 2:(9,5)[sub_goal] → 1×5 → (4,5)[goal]
trial_plan = make_trial(start=(7, 3), goal=(4, 5),
                        seq=[2, 2, 1, 1, 1, 1, 1],
                        sub_goal=(9, 5))

screen.fill(BG)
_draw_stage_planning(
    screen, fonts, trial_plan,
    elapsed=3.2, p_time=10.0,
    total_trials=20, block_type="practice", sn=1,
    cum_score=9600, show_timer=True, eyes_open=True,
    amb_particles=None, typed_seq=None, btns=None,
    mouse_tier=3,
)
pygame.display.flip()
path = os.path.join(OUT, "planning_stage.png")
pygame.image.save(screen, path)
print(f"Saved: {path}")


# ── Screenshot 2: Feedback/replay, correct trial ──────────────
# Same 7-move puzzle, mid-replay: start(7,3) → (8,4) → (9,5)[sub_goal] → cursor at (8,5)
trial_nav = make_trial(start=(7, 3), goal=(4, 5),
                       seq=[2, 2, 1, 1, 1, 1, 1],
                       sub_goal=(9, 5))
trial_nav.reward_score = 100
trial_nav.is_correct   = True

now = time.time()
trail = {
    (7, 3): now - 1.5,
    (8, 4): now - 1.0,
    (9, 5): now - 0.5,
}
cursor = (8, 5)

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

pygame.quit()
print(f"\nBoth screenshots saved to: {OUT}/")
