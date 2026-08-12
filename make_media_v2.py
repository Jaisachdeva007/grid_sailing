"""GridSailing Media v2 — richer content, proper storytelling.

Path: start=(0,0), goal=(3,3), sequence=[2,1,2,1,2,2,3], 7 moves
Full path: (0,0)→(1,1)→(0,1)→(1,2)→(0,2)→(1,3)→(2,4)→(3,3)
"""
import sys, os, math, random, time
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
import imageio.v2 as imageio

sys.path.insert(0, "/Users/jaisachdeva/Desktop/grid_sailing")

pygame.init()
W, H   = 1280, 800
screen = pygame.display.set_mode((W, H))
fonts  = (
    pygame.font.SysFont("Arial", 64, bold=True),
    pygame.font.SysFont("Arial", 36, bold=True),
    pygame.font.SysFont("Arial", 24),
    pygame.font.SysFont("Arial", 18),
)
f_big, f_med, f_sm, f_xs = fonts
FPS    = 30
BG     = (8, 8, 16)
WHITE  = (245, 245, 255)
ACCENT = (88, 148, 255)
DIM    = (118, 118, 158)
CORRECT_C = (0, 168, 175)
AMBER  = (220, 162, 28)

OUT_G = "/Users/jaisachdeva/Desktop/GridSailing_Media/gamification"
OUT   = "/Users/jaisachdeva/Desktop/GridSailing_Media"

from core.trial import (
    TrialData, _draw_stage_planning, _draw_stage_input,
    _draw_stage_feedback, _draw_stage_iti, _draw_grid,
    _spawn_particles, _update_draw_particles, _layout,
)

# ── Demo puzzle: start=(0,0) goal=(3,3) seq=[2,1,2,1,2,2,3] ──
# Verified with find_all_valid_puzzles() — uses all 3 keys, 7 moves
DEMO_START = (0, 0)
DEMO_GOAL  = (3, 3)
DEMO_SEQ   = [2, 1, 2, 1, 2, 2, 3]
FULL_PATH  = [(0,0),(1,1),(0,1),(1,2),(0,2),(1,3),(2,4),(3,3)]
FULL_TRAIL = {pos: 0 for pos in FULL_PATH[:-1]}   # all except goal, value=0 → fully faded

GL, GT, GR, GRW, CELL = _layout(W, H)
CHEESE_PCX = GL + DEMO_GOAL[1] * CELL + CELL // 2   # col=3
CHEESE_PCY = GT + DEMO_GOAL[0] * CELL + CELL // 2   # row=3


def mk_trial(tn=5, correct=True, score=None, seq=None, oob=0):
    t = TrialData(
        session_id=1, participant_id="P-Demo",
        trial_number=tn, grid_type="repeated",
        start=DEMO_START, goal=DEMO_GOAL,
        optimal_sequence=DEMO_SEQ, group="PP-High",
    )
    t.planned_sequence = seq if seq is not None else DEMO_SEQ
    t.is_correct       = correct
    t.reward_score     = score if score is not None else (100 if correct else 0)
    t.number_of_moves  = len(t.planned_sequence)
    t.oob_count        = oob
    t.reaction_time_ms = 2140.0
    t.movement_time_ms = 3870.0
    return t


def mk_bad_trial(tn=8):
    # seq [2,1,3] → (0,0)→(1,1)→(0,1)→(1,0)  — doesn't reach (3,3)
    return mk_trial(tn=tn, correct=False, score=0, seq=[2, 1, 3])


def to_rgb(s):
    return pygame.surfarray.array3d(s).transpose(1, 0, 2)


def write_mp4(frames, path):
    w = imageio.get_writer(path, fps=FPS, quality=9, macro_block_size=None)
    for f in frames:
        w.append_data(f)
    w.close()
    kb = os.path.getsize(path) // 1024
    print(f"  -> {os.path.basename(path)}  ({len(frames)/FPS:.1f}s, {kb}KB)")


def apply_fade(frames, n, start_alpha, direction="in"):
    n = min(n, len(frames))
    for i in range(n):
        alpha = int(start_alpha * (1 - i/n)) if direction == "in" else int(start_alpha * (i/n))
        idx = i if direction == "in" else len(frames) - n + i
        if idx < 0:
            continue
        sf = pygame.surfarray.make_surface(frames[idx].transpose(1, 0, 2))
        ov = pygame.Surface((W, H))
        ov.set_alpha(alpha)
        ov.fill((0, 0, 0))
        sf.blit(ov, (0, 0))
        frames[idx] = to_rgb(sf)
    return frames


def crossfade_join(sections, n=12):
    """Join frame-list sections with n-frame crossfades — no hard cuts."""
    if not sections:
        return []
    result = list(sections[0])
    for sec in sections[1:]:
        if not sec:
            continue
        nc = min(n, len(result), len(sec))
        blend = []
        for i in range(nc):
            t  = (i + 1) / (nc + 1)
            fa = result[-nc + i]
            fb = sec[i]
            sa = pygame.surfarray.make_surface(fa.transpose(1, 0, 2))
            sb = pygame.surfarray.make_surface(fb.transpose(1, 0, 2))
            canvas = pygame.Surface((W, H))
            canvas.blit(sa, (0, 0))
            sb.set_alpha(int(255 * t))
            canvas.blit(sb, (0, 0))
            blend.append(to_rgb(canvas))
        result = result[:-nc] + blend + list(sec[nc:])
    return result


def caption(text, sub=None, col=WHITE):
    bar = pygame.Surface((W, 52), pygame.SRCALPHA)
    bar.fill((0, 0, 0, 210))
    screen.blit(bar, (0, H - 52))
    ts = f_sm.render(text, True, col)
    screen.blit(ts, (W // 2 - ts.get_width() // 2, H - 52 + 6))
    if sub:
        ss = f_xs.render(sub, True, DIM)
        screen.blit(ss, (W // 2 - ss.get_width() // 2, H - 52 + 6 + ts.get_height() + 2))


def title_card(line1, line2=None, col=ACCENT, n=FPS):
    out = []
    for _ in range(n):
        screen.fill(BG)
        t1 = f_med.render(line1, True, col)
        screen.blit(t1, (W // 2 - t1.get_width() // 2,
                         H // 2 - t1.get_height() // 2 - (16 if line2 else 0)))
        if line2:
            t2 = f_xs.render(line2, True, DIM)
            screen.blit(t2, (W // 2 - t2.get_width() // 2, H // 2 + 18))
        out.append(to_rgb(screen.copy()))
    return out


def mk_amb(n=22):
    return [{"x": float(GL + random.randint(10, CELL * 5 - 10)),
             "y": float(GT + random.randint(10, CELL * 5 - 10)),
             "vx": random.uniform(-0.6, 0.6),
             "vy": random.uniform(-0.6, 0.6)} for _ in range(n)]


# ═══════════════════════════════════════════════════════════════
# VID 1 — CHEESE BURST
# cursor walks last 5 steps -> lands on cheese -> burst -> CORRECT
# ═══════════════════════════════════════════════════════════════
print("\nRendering: cheese_burst...")
frames = []
trial  = mk_trial()

WALK_START = 3   # animate from FULL_PATH[3] onward
walk_path  = FULL_PATH[WALK_START:]              # (1,2)→(0,2)→(1,3)→(2,4)→(3,3)
base_trail = {pos: 0 for pos in FULL_PATH[:WALK_START]}

for step_i, cursor in enumerate(walk_path[:-1]):   # all but the goal
    for fi in range(16):
        screen.fill(BG)
        t_now = dict(base_trail)
        for k in range(step_i):
            t_now[walk_path[k]] = 0
        _draw_grid(screen, fonts, trial, t_now, cursor, eyes_open=True)
        caption("Cursor executing the planned sequence...",
                "Each key press advances one step toward the cheese")
        frames.append(to_rgb(screen.copy()))

# Landing hold on cheese (0.4 s)
for _ in range(12):
    screen.fill(BG)
    _draw_grid(screen, fonts, trial, FULL_TRAIL, DEMO_GOAL, eyes_open=True)
    frames.append(to_rgb(screen.copy()))

# Burst only — no feedback card yet (1 s)
particles = _spawn_particles(CHEESE_PCX, CHEESE_PCY, is_perfect=True)
for i in range(FPS):
    screen.fill(BG)
    _draw_grid(screen, fonts, trial, FULL_TRAIL, DEMO_GOAL, eyes_open=True)
    _update_draw_particles(screen, particles, 1 / FPS)
    caption("CORRECT  — cheese reached!", col=CORRECT_C)
    frames.append(to_rgb(screen.copy()))

# CORRECT feedback card (3 s)
for i in range(FPS * 3):
    screen.fill(BG)
    _draw_stage_feedback(screen, fonts, trial, cum_score=700,
                         rp_cursor=DEMO_GOAL, rp_trail=FULL_TRAIL,
                         rp_done=True, total_trials=20,
                         block_type="practice", sn=1, streak=1, show_score=True)
    if particles:
        _update_draw_particles(screen, particles, 1 / FPS)
    if i < 40:
        caption("Score breakdown — optimal path earns maximum points",
                "Reaction time, movement time and streak recorded")
    frames.append(to_rgb(screen.copy()))

write_mp4(apply_fade(apply_fade(frames, 15, 255, "in"), 15, 255, "out"),
          f"{OUT_G}/cheese_burst.mp4")


# ═══════════════════════════════════════════════════════════════
# VID 2 — MOUSE BLINK + MAGNETIC PARTICLES
# full planning screen, timer 6->0, blinks twice, particles drift
# ═══════════════════════════════════════════════════════════════
print("Rendering: mouse_blink_and_particles...")
frames = []
amb = mk_amb(22)
BLINK_EVERY  = FPS * 4
BLINK_CLOSED = 4
TOTAL        = FPS * 9

for i in range(TOTAL):
    in_cycle  = i % BLINK_EVERY
    eyes_open = not (BLINK_EVERY - BLINK_CLOSED <= in_cycle < BLINK_EVERY)
    screen.fill(BG)
    elapsed = 6 * (i / TOTAL)
    _draw_stage_planning(screen, fonts, mk_trial(),
                         elapsed=elapsed, p_time=6, total_trials=20,
                         block_type="practice", sn=1, cum_score=600,
                         show_timer=True, eyes_open=eyes_open, amb_particles=amb)
    if i < 45:
        caption("PLANNING PHASE",
                "Mouse blinks while thinking  .  particles drift magnetically toward the cheese")
    elif BLINK_EVERY - BLINK_CLOSED - 2 < i % BLINK_EVERY < BLINK_EVERY + 2:
        caption("Eyes closed  (120 ms blink)  — subtle character life")
    frames.append(to_rgb(screen.copy()))

write_mp4(apply_fade(apply_fade(frames, 15, 255, "in"), 15, 255, "out"),
          f"{OUT_G}/mouse_blink_and_particles.mp4")


# ═══════════════════════════════════════════════════════════════
# VID 3 — MAGNETIC PARTICLES (dramatic pull)
# particles seeded far from goal, converge clearly over 8 s
# ═══════════════════════════════════════════════════════════════
print("Rendering: magnetic_particles...")
frames = []
amb2 = []
for _ in range(30):
    amb2.append({
        "x": float(GL + random.randint(0, CELL * 2)),
        "y": float(GT + random.randint(CELL, CELL * 4)),
        "vx": random.uniform(-0.2, 0.2),
        "vy": random.uniform(-0.2, 0.2),
    })

for i in range(FPS * 8):
    screen.fill(BG)
    _draw_stage_planning(screen, fonts, mk_trial(),
                         elapsed=i / FPS * 0.6, p_time=6, total_trials=20,
                         block_type="practice", sn=1, cum_score=600,
                         show_timer=True, eyes_open=True, amb_particles=amb2)
    if i < 40:
        caption("Particles scattered at start of planning phase",
                "Each particle is magnetically pulled toward the cheese")
    elif FPS * 3 < i < FPS * 3 + 50:
        caption("Pull accelerates as particles get closer",
                "strength proportional to 1/distance")
    frames.append(to_rgb(screen.copy()))

write_mp4(apply_fade(apply_fade(frames, 15, 255, "in"), 15, 255, "out"),
          f"{OUT_G}/magnetic_particles.mp4")


# ═══════════════════════════════════════════════════════════════
# VID 4 — STREAK BUILDING (x1 -> x2 -> x3 -> x4 flame)
# ═══════════════════════════════════════════════════════════════
print("Rendering: streak_flame...")
frames = []


def streak_segment(streak_in, trial_n, cum, n_frames, label):
    fs = []
    for i in range(n_frames):
        screen.fill(BG)
        _draw_stage_feedback(screen, fonts, mk_trial(tn=trial_n),
                             cum_score=cum, rp_cursor=DEMO_GOAL,
                             rp_trail=FULL_TRAIL, rp_done=True,
                             total_trials=20, block_type="practice",
                             sn=1, streak=streak_in, show_score=True)
        if i < 40 or i > n_frames - 40:
            caption(label)
        fs.append(to_rgb(screen.copy()))
    return fs


def mini_iti(trial_n, cum, n=20):
    fs = []
    t0 = time.time()
    for i in range(n):
        screen.fill(BG)
        _draw_stage_iti(screen, fonts, mk_trial(tn=trial_n),
                        iti_start=t0 - (i / FPS), iti_dur=4,
                        total_trials=20, block_type="practice",
                        sn=1, cum_score=cum)
        fs.append(to_rgb(screen.copy()))
    return fs


frames += title_card("Streak System",
                     "Consecutive correct trials build the flame badge", n=FPS)
frames += streak_segment(0, 5, 400, FPS * 2, "Trial 5 correct  — first in a new streak")
frames += mini_iti(6, 500)
frames += streak_segment(1, 6, 500, FPS * 2, "x2  Streak!  — flame badge appears")
frames += mini_iti(7, 600)
frames += streak_segment(2, 7, 600, FPS * 2, "x3  Streak!  — flame grows taller")
frames += mini_iti(8, 700)
frames += streak_segment(3, 8, 700, FPS * 3, "x4  Streak!  — maximum flame intensity")

write_mp4(apply_fade(apply_fade(frames, 15, 255, "in"), 20, 255, "out"),
          f"{OUT_G}/streak_flame.mp4")


# ═══════════════════════════════════════════════════════════════
# DEMO VIDEO — full experiment walkthrough, smooth crossfades
# Each stage is built into its own list; crossfade_join blends them
# ═══════════════════════════════════════════════════════════════
print("\nRendering: demo_video...")


def build_planning(n_frames=FPS * 6):
    fs = []
    amb = mk_amb(22)
    BD  = FPS * 4
    for i in range(n_frames):
        screen.fill(BG)
        in_c    = i % BD
        eyes    = not (BD - 4 <= in_c < BD)
        elapsed = 6 * (i / n_frames)
        _draw_stage_planning(screen, fonts, mk_trial(tn=7),
                             elapsed=elapsed, p_time=6, total_trials=20,
                             block_type="practice", sn=1, cum_score=600,
                             show_timer=True, eyes_open=eyes, amb_particles=amb)
        if i < 50:
            caption("PLANNING  (6 s)",
                    "Participant studies the grid and plans the shortest route to the cheese")
        elif i > n_frames - 35:
            caption("Timer ending  — grid disappears when time runs out")
        fs.append(to_rgb(screen.copy()))
    return fs


def build_input(n_frames=FPS * 3):
    fs = []
    for i in range(n_frames):
        screen.fill(BG)
        revealed = min(len(DEMO_SEQ), i // (FPS // 3))
        _draw_stage_input(screen, fonts, mk_trial(tn=7),
                          typed_seq=DEMO_SEQ[:revealed], blink_on=(i % 30 < 15),
                          total_trials=20, block_type="practice",
                          sn=1, btns={}, cum_score=600, is_mi=False)
        if i < 40:
            caption("INPUT  — grid is hidden",
                    "Participant enters the planned sequence from memory: 1 / 2 / 3")
        fs.append(to_rgb(screen.copy()))
    return fs


def build_action_to_correct():
    """Action replay + landing + burst + correct card — one continuous section."""
    fs = []
    # Cursor walks full path (3 s)
    for i in range(FPS * 3 + 10):
        screen.fill(BG)
        step   = min(len(FULL_PATH) - 1, i // 12)
        cursor = FULL_PATH[step]
        trail  = {FULL_PATH[j]: 0 for j in range(step)}
        _draw_grid(screen, fonts, mk_trial(tn=7), trail, cursor, eyes_open=True)
        if i < 40:
            caption("ACTION  — cursor executes the sequence",
                    "PP group: participant presses keys on the physical keypad")
        fs.append(to_rgb(screen.copy()))
    # Landing hold (0.4 s)
    for _ in range(12):
        screen.fill(BG)
        _draw_grid(screen, fonts, mk_trial(tn=7), FULL_TRAIL, DEMO_GOAL, eyes_open=True)
        fs.append(to_rgb(screen.copy()))
    # Burst (1 s)
    parts = _spawn_particles(CHEESE_PCX, CHEESE_PCY, is_perfect=True)
    for _ in range(FPS):
        screen.fill(BG)
        _draw_grid(screen, fonts, mk_trial(tn=7), FULL_TRAIL, DEMO_GOAL, eyes_open=True)
        _update_draw_particles(screen, parts, 1 / FPS)
        fs.append(to_rgb(screen.copy()))
    # Correct feedback x2 streak (3 s)
    for i in range(FPS * 3):
        screen.fill(BG)
        _draw_stage_feedback(screen, fonts, mk_trial(tn=7), cum_score=700,
                             rp_cursor=DEMO_GOAL, rp_trail=FULL_TRAIL,
                             rp_done=True, total_trials=20,
                             block_type="practice", sn=1, streak=2, show_score=True)
        if parts:
            _update_draw_particles(screen, parts, 1 / FPS)
        if i < 50:
            caption("CORRECT  — score breakdown + x2 streak flame",
                    "Reaction time, movement time and cumulative score recorded")
        fs.append(to_rgb(screen.copy()))
    return fs


def build_iti(n_frames=FPS + 15):
    fs = []
    t0 = time.time()
    for i in range(n_frames):
        screen.fill(BG)
        _draw_stage_iti(screen, fonts, mk_trial(tn=8),
                        iti_start=t0 - (i / FPS), iti_dur=4,
                        total_trials=20, block_type="practice", sn=1, cum_score=800)
        fs.append(to_rgb(screen.copy()))
    return fs


def build_missed():
    fs = []
    bad        = mk_bad_trial(tn=8)
    BAD_CURSOR = (1, 0)
    BAD_TRAIL  = {(0, 0): 0, (1, 1): 0, (0, 1): 0}
    for i in range(FPS * 2 + 15):
        screen.fill(BG)
        _draw_stage_feedback(screen, fonts, bad, cum_score=800,
                             rp_cursor=BAD_CURSOR, rp_trail=BAD_TRAIL,
                             rp_done=True, total_trials=20,
                             block_type="practice", sn=1, streak=0, show_score=True)
        if i < 50:
            caption("MISSED  — goal not reached",
                    "0 points awarded, streak resets to zero")
        fs.append(to_rgb(screen.copy()))
    return fs


def build_streak_x4(n_frames=FPS * 3):
    fs = []
    for i in range(n_frames):
        screen.fill(BG)
        _draw_stage_feedback(screen, fonts, mk_trial(tn=9), cum_score=900,
                             rp_cursor=DEMO_GOAL, rp_trail=FULL_TRAIL,
                             rp_done=True, total_trials=20,
                             block_type="practice", sn=1, streak=3, show_score=True)
        if i < 50:
            caption("x4 Streak!  — flame grows with each consecutive correct trial")
        fs.append(to_rgb(screen.copy()))
    return fs


# Build all sections then crossfade-join — zero hard cuts
sections = [
    title_card("Grid Sailing",
               "Motor sequence learning experiment — participant walkthrough",
               n=FPS * 2),
    build_planning(),
    build_input(),
    build_action_to_correct(),
    build_iti(),
    build_missed(),
    build_streak_x4(),
    title_card("Grid Sailing",
               "All trial data saved automatically to SQLite + Firebase",
               n=FPS * 2),
]

frames = crossfade_join(sections, n=12)
write_mp4(apply_fade(apply_fade(frames, 20, 255, "in"), 20, 255, "out"),
          f"{OUT}/demo_video.mp4")

print("\nAll done.")
