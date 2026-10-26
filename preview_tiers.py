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

W, H = 1560, 820
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

# ── 1. All 6 tiers — 3×2 card grid ───────────────────────────
W2, H2 = 1080, 760
canvas = pygame.Surface((W2, H2))
canvas.fill((10, 10, 22))

CARD_W, CARD_H = 300, 330
COLS, ROWS     = 3, 2
GAP_X = (W2 - COLS * CARD_W) // (COLS + 1)
GAP_Y = (H2 - 60 - ROWS * CARD_H) // (ROWS + 1)

title_s = f_med.render("Grid Sailing — Mouse Tiers", True, WHITE)
canvas.blit(title_s, (W2 // 2 - title_s.get_width() // 2, 18))

icon_sz = 100

for i, (threshold, body, ear, name, headline, sub) in enumerate(_MOUSE_TIERS):
    col = i % COLS
    row = i // COLS
    cx_card = GAP_X + col * (CARD_W + GAP_X) + CARD_W // 2
    cy_card = 60 + GAP_Y + row * (CARD_H + GAP_Y)

    # Card background
    card_rect = pygame.Rect(cx_card - CARD_W // 2, cy_card, CARD_W, CARD_H)
    pygame.draw.rect(canvas, (18, 20, 40), card_rect, border_radius=18)
    pygame.draw.rect(canvas, body, card_rect, width=2, border_radius=18)

    # Circle background behind mouse
    circ_r = 72
    circ_cx, circ_cy = cx_card, cy_card + 90
    dark_body = tuple(max(0, c - 100) for c in body)
    pygame.draw.circle(canvas, dark_body, (circ_cx, circ_cy), circ_r)
    pygame.draw.circle(canvas, body, (circ_cx, circ_cy), circ_r, 2)

    _draw_mouse_icon(canvas, circ_cx, circ_cy, eyes_open=True, cell_sz=icon_sz, mouse_tier=i)
    _draw_mouse_accessory(canvas, circ_cx, circ_cy, tier_idx=i, s=icon_sz / 75)

    # Name
    name_s = f_med.render(name, True, WHITE)
    canvas.blit(name_s, (cx_card - name_s.get_width() // 2, cy_card + 170))

    # Subtitle (shrink font if too wide for card)
    if sub:
        sub_font = f_xs if f_xs.size(sub)[0] < CARD_W - 20 else pygame.font.SysFont("Helvetica Neue", 13)
        sub_s = sub_font.render(sub, True, body)
        canvas.blit(sub_s, (cx_card - sub_s.get_width() // 2, cy_card + 210))

    # Points
    pts_text = f"{threshold:,} pts" if threshold else ""
    if pts_text:
        pts_s = f_sm.render(pts_text, True, body)
        canvas.blit(pts_s, (cx_card - pts_s.get_width() // 2, cy_card + 238 if sub else cy_card + 210))

pygame.image.save(canvas, os.path.join(OUT, "00_all_tiers.png"))
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
