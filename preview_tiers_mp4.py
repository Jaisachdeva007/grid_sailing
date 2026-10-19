"""
Renders each milestone overlay as an MP4 at 30fps.
Frames are piped directly to ffmpeg — no temp files needed.
"""
import os, sys, math, subprocess, tempfile
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(__file__))

import pygame
pygame.init()

from core.trial import (
    _draw_mouse_icon, _MOUSE_TIERS,
    _init_milestone_particles, _draw_milestone_particles,
    _draw_mouse_with_animation,
    _ease_out_cubic,
)

W, H     = 1280, 800
BG       = (8,   8,  16)
WHITE    = (245, 245, 255)
DIM      = (118, 118, 158)
FPS      = 30
N_FRAMES = 106   # 3.5 seconds

f_big = pygame.font.SysFont("Helvetica Neue", 64, bold=True)
f_med = pygame.font.SysFont("Helvetica Neue", 38)
f_sm  = pygame.font.SysFont("Helvetica Neue", 24)
f_xs  = pygame.font.SysFont("Helvetica Neue", 20)

OUT = "/Users/jaisachdeva/Desktop/Tier Previews"

def render_frame(surf, tier_idx, elapsed, particles):
    _, body_col, _, tier_name, _, sub_line = _MOUSE_TIERS[tier_idx]
    prev_milestone    = _MOUSE_TIERS[tier_idx - 1][0]
    current_milestone = _MOUSE_TIERS[tier_idx][0]
    cx  = W // 2
    MCY = H // 2 - 150

    surf.fill(BG)

    # Faint grid backdrop
    cell = 46
    gx = 60; gy = (H - 10 * cell) // 2
    for r in range(10):
        for c in range(10):
            pygame.draw.rect(surf, (18, 18, 36),
                             pygame.Rect(gx + c*cell+2, gy + r*cell+2, cell-4, cell-4),
                             border_radius=5)

    # Dark overlay fade-in
    fade = min(1.0, elapsed / 0.35)
    overlay = pygame.Surface((W, H), pygame.SRCALPHA)
    overlay.fill((8, 8, 20, int(215 * fade)))
    surf.blit(overlay, (0, 0))
    if fade < 0.05:
        return

    # Particles
    _draw_milestone_particles(surf, tier_idx, particles, elapsed, cx, MCY, W, H)

    # Pulsing glow ring
    ring_r = int(min(W, H) * 0.18)
    rs     = pygame.Surface((ring_r*2+20, ring_r*2+20), pygame.SRCALPHA)
    pulse  = 0.82 + 0.18 * math.sin(elapsed * 4.5)
    gc     = tuple(min(255, int(c * pulse)) for c in body_col) + (int(130 * fade),)
    pygame.draw.circle(rs, gc, (ring_r+10, ring_r+10), ring_r, 16)
    surf.blit(rs, (cx - ring_r - 10, MCY - ring_r - 10))

    # Mouse with per-tier animation
    icon_sz = int(60 + 80 * min(1.0, elapsed / 0.40))
    _draw_mouse_with_animation(surf, cx, MCY, tier_idx, elapsed, icon_sz)

    # Tier badge
    bs     = f_xs.render(tier_name.upper(), True, body_col)
    badge_y = MCY + icon_sz//2 + 16
    bb  = pygame.Rect(cx - bs.get_width()//2 - 14,
                      badge_y, bs.get_width()+28, 28)
    pygame.draw.rect(surf, (*body_col, int(55 * fade)), bb, border_radius=14)
    surf.blit(bs, (bb.x + 14, bb.y + 5))

    # Animated score counter
    COUNTER_DUR = 1.5
    t_c = min(1.0, elapsed / COUNTER_DUR)
    displayed = int(prev_milestone +
                    (current_milestone - prev_milestone) * _ease_out_cubic(t_c))
    hl_y = badge_y + 28 + 18 + int(10 * (1 - fade))
    hl   = f_big.render(f"{displayed:,} points!", True, WHITE)
    surf.blit(hl, (cx - hl.get_width()//2, hl_y))

    sl = f_med.render(sub_line, True, DIM)
    surf.blit(sl, (cx - sl.get_width()//2, hl_y + 76))

    # Tier-5 white flash
    if tier_idx == 5 and elapsed < 0.20:
        fs = pygame.Surface((W, H))
        fs.fill((255, 255, 255))
        fs.set_alpha(int(255 * (1 - elapsed / 0.20)))
        surf.blit(fs, (0, 0))

    # Tap hint
    if elapsed > 0.85:
        hint_fade = min(1.0, (elapsed - 0.85) / 0.4)
        hint = f_xs.render("Tap to continue", True,
                            tuple(int(c * hint_fade) for c in (90, 90, 140)))
        surf.blit(hint, (cx - hint.get_width()//2, hl_y + 138))


surf = pygame.Surface((W, H))

for tier_idx in range(1, len(_MOUSE_TIERS)):
    _, _, _, tier_name, _, _ = _MOUSE_TIERS[tier_idx]
    safe_name = tier_name.replace(" ", "_").lower()
    out_path  = os.path.join(OUT, f"tier{tier_idx}_{safe_name}.mp4")

    # Pre-init particles once per tier (deterministic)
    cx_init = W // 2
    cy_init = H // 2 - 150
    from core.trial import _init_milestone_particles
    tier_particles = _init_milestone_particles(tier_idx, cx_init, cy_init, W, H)

    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-s", f"{W}x{H}", "-pix_fmt", "rgb24",
        "-r", str(FPS), "-i", "pipe:0",
        "-vcodec", "libx264", "-pix_fmt", "yuv420p",
        "-crf", "18", "-preset", "fast",
        out_path,
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    for f in range(N_FRAMES):
        elapsed = f / FPS
        render_frame(surf, tier_idx, elapsed, tier_particles)
        raw = pygame.image.tostring(surf, "RGB")
        proc.stdin.write(raw)

    proc.stdin.close()
    proc.wait()
    print(f"Saved: {os.path.basename(out_path)}")

pygame.quit()
print(f"\nAll videos saved to: {OUT}/")
