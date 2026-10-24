"""
Renders all mouse tiers and milestone overlays to PNG files.
Run with: python preview_tiers.py
No display needed — uses offscreen SDL.
"""
import os, sys, math, time
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(__file__))

import pygame
pygame.init()

W, H = 1280, 800
screen = pygame.Surface((W, H))

# Build fonts the same way the game does
f_big = pygame.font.SysFont("Helvetica Neue", 52, bold=True)
f_med = pygame.font.SysFont("Helvetica Neue", 32)
f_sm  = pygame.font.SysFont("Helvetica Neue", 22)
f_xs  = pygame.font.SysFont("Helvetica Neue", 17)
fonts = (f_big, f_med, f_sm, f_xs)

from core.trial import _draw_mouse_icon, _draw_mouse_accessory, _MOUSE_TIERS, show_milestone_overlay

BG    = (8, 8, 16)
WHITE = (245, 245, 255)
DIM   = (118, 118, 158)

OUT = os.path.join(os.path.dirname(__file__), "tier_previews")
os.makedirs(OUT, exist_ok=True)

# ── 1. All 6 tiers side-by-side ───────────────────────────────
screen.fill(BG)

cols = 6
cell_w = W // cols
icon_sz = 120

for i, (threshold, body, ear, name, headline, sub) in enumerate(_MOUSE_TIERS):
    cx = cell_w * i + cell_w // 2
    cy = H // 2 - 60

    # Tier colour background pill
    pill = pygame.Rect(cx - 70, cy - 90, 140, 30)
    pygame.draw.rect(screen, tuple(min(255, c // 2) for c in body) + (0,),
                     pill, border_radius=15)
    pygame.draw.rect(screen, body, pill, width=2, border_radius=15)
    tier_lbl = f_xs.render(f"Tier {i}", True, body)
    screen.blit(tier_lbl, (cx - tier_lbl.get_width() // 2, cy - 84))

    _draw_mouse_icon(screen, cx, cy, eyes_open=True, cell_sz=icon_sz, mouse_tier=i)
    _draw_mouse_accessory(screen, cx, cy, tier_idx=i, s=icon_sz / 75)

    name_s = f_sm.render(name, True, WHITE)
    screen.blit(name_s, (cx - name_s.get_width() // 2, cy + 80))

    pts_s = f_xs.render(f"{threshold:,} pts" if threshold else "default", True, DIM)
    screen.blit(pts_s, (cx - pts_s.get_width() // 2, cy + 108))

title = f_med.render("All Mouse Tiers", True, WHITE)
screen.blit(title, (W // 2 - title.get_width() // 2, 30))

pygame.image.save(screen, os.path.join(OUT, "00_all_tiers.png"))  # type: ignore
print("Saved: 00_all_tiers.png")

# ── 2. Each milestone overlay (tiers 1-5) ────────────────────
# show_milestone_overlay uses clock.tick and pygame.display.flip,
# so we intercept by monkey-patching display.flip and faking time.

import unittest.mock as mock

for tier_idx in range(1, len(_MOUSE_TIERS)):
    screen.fill(BG)

    # Simulate the overlay drawing for one frame at elapsed=1.0 s
    _, body_col, ear_col, tier_name, headline, sub_line = _MOUSE_TIERS[tier_idx]

    elapsed = 1.0   # well past fade-in
    alpha   = 255

    overlay = pygame.Surface((W, H), pygame.SRCALPHA)
    overlay.fill((8, 8, 20, 210))
    screen.blit(overlay, (0, 0))

    ring_r = int(min(W, H) * 0.17)
    ring_surf = pygame.Surface((ring_r * 2 + 20, ring_r * 2 + 20), pygame.SRCALPHA)
    pulse = 0.82 + 0.18 * math.sin(elapsed * 4.5)
    glow_col = tuple(min(255, int(c * pulse)) for c in body_col) + (120,)
    pygame.draw.circle(ring_surf, glow_col, (ring_r + 10, ring_r + 10), ring_r, 14)
    cx = W // 2
    screen.blit(ring_surf, (cx - ring_r - 10, H // 2 - 140 - ring_r - 10))

    _draw_mouse_icon(screen, cx, H // 2 - 140, eyes_open=True,
                     cell_sz=120, mouse_tier=tier_idx)

    badge_surf = f_xs.render(tier_name.upper(), True, body_col)
    badge_bg   = pygame.Rect(cx - badge_surf.get_width() // 2 - 10,
                             H // 2 - 50, badge_surf.get_width() + 20, 26)
    pygame.draw.rect(screen, (*body_col, 60), badge_bg, border_radius=13)
    screen.blit(badge_surf, (badge_bg.x + 10, badge_bg.y + 4))

    hl = f_big.render(headline, True, WHITE)
    screen.blit(hl, (cx - hl.get_width() // 2, H // 2 - 10))

    sl = f_med.render(sub_line, True, DIM)
    screen.blit(sl, (cx - sl.get_width() // 2, H // 2 + 50))

    hint = f_xs.render("Tap to continue", True, (70, 70, 110))
    screen.blit(hint, (cx - hint.get_width() // 2, H // 2 + 100))

    fname = f"0{tier_idx}_tier{tier_idx}_{tier_name.replace(' ', '_').lower()}.png"
    pygame.image.save(screen, os.path.join(OUT, fname))
    print(f"Saved: {fname}")

pygame.quit()
print(f"\nAll screenshots saved to: {OUT}/")
