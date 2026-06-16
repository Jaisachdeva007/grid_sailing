# ============================================================
#  GRID-SAILING TASK — Entry Point
#
#  Imports are intentionally lazy (inside main()) so that
#  config.WINDOW_WIDTH / WINDOW_HEIGHT can be patched to the
#  native display size BEFORE any screen module is imported.
#  Each screen module reads those constants at import time as
#  module-level variables — patching first keeps everything
#  consistent and renders at native resolution (no blur).
# ============================================================

import pygame


def main():
    pygame.init()

    # ── Native resolution ─────────────────────────────────────
    # Detect the display's logical resolution.  Rendering at this
    # size (no pygame.SCALED) means 1 pixel == 1 physical pixel on
    # the GPU — sharp text, no bilinear-filter blur.
    info = pygame.display.Info()
    native_w, native_h = info.current_w, info.current_h

    # Patch config BEFORE importing any screen modules.
    # Screen modules do  W, H = WINDOW_WIDTH, WINDOW_HEIGHT  at the
    # top of their file; patching here ensures they get native size.
    import config
    config.WINDOW_WIDTH  = native_w
    config.WINDOW_HEIGHT = native_h

    # FULLSCREEN | SCALED: SDL stretches the surface to fill the physical display.
    # When surface size == logical screen size the scale ratio is 1:1 → no blur.
    # On Retina (physical = 2× logical) SDL does a clean 2× integer upscale → sharp.
    screen = pygame.display.set_mode((native_w, native_h),
                                      pygame.FULLSCREEN | pygame.SCALED)
    pygame.display.set_caption("Grid-Sailing Task")
    clock = pygame.time.Clock()

    # ── Lazy imports (after config patch) ─────────────────────
    from database.db import initialise_database
    from screens.welcome import run_welcome
    from screens.researcher_setup import run_researcher_setup, run_researcher_home
    from screens.participant_login import run_participant_login
    from core.session import run_session
    from screens.data_viewer import run_data_viewer

    initialise_database()

    # ── Step 1: Welcome (admin login) ─────────────────────────
    role = run_welcome(screen, clock)
    if role != "researcher":
        pygame.quit(); return

    # ── Step 2: Researcher home ────────────────────────────────
    fonts_setup = (
        pygame.font.SysFont("Helvetica Neue", 34, bold=True),
        pygame.font.SysFont("Helvetica Neue", 22, bold=True),
        pygame.font.SysFont("Helvetica Neue", 17),
        pygame.font.SysFont("Helvetica Neue", 14),
    )

    config_data = None
    while config_data is None:
        choice = run_researcher_home(screen, clock)
        if choice is None:
            pygame.quit(); return
        if choice == "data":
            run_data_viewer(screen, clock, fonts_setup)
            continue
        config_data = run_researcher_setup(screen, clock, mode=choice)
        if config_data is None:
            continue   # ESC → back to home

    print(f"[MAIN] Session config: {config_data}")

    # ── Step 3: Participant login ──────────────────────────────
    fonts = (
        pygame.font.SysFont("Helvetica Neue", 34, bold=True),
        pygame.font.SysFont("Helvetica Neue", 22, bold=True),
        pygame.font.SysFont("Helvetica Neue", 17),
        pygame.font.SysFont("Helvetica Neue", 14),
    )

    pid = config_data["participant_id"]
    sn  = config_data["session_number"]
    pygame.display.set_caption(f"Grid-Sailing  ·  {pid}  ·  Session {sn}")

    participant = run_participant_login(screen, clock, fonts, config_data)
    if not participant:
        pygame.quit(); return

    print(f"[MAIN] Participant confirmed: {participant['participant_id']}")

    # ── Step 4: Run the session ────────────────────────────────
    run_session(screen, clock, fonts, config_data, participant)

    pygame.quit()


if __name__ == "__main__":
    main()
