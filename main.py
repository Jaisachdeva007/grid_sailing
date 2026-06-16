# ============================================================
#  GRID-SAILING TASK — Entry Point
# ============================================================

import pygame


def main():
    pygame.init()

    # (0,0) + FULLSCREEN: SDL fills the display at its native resolution.
    # No SCALED needed — (0,0) already gives exact screen dimensions.
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    native_w = screen.get_width()
    native_h = screen.get_height()

    # Patch config BEFORE importing screen modules.
    # Every screen does  W, H = WINDOW_WIDTH, WINDOW_HEIGHT  at import
    # time; patching first makes them all use the actual screen size.
    import config
    config.WINDOW_WIDTH  = native_w
    config.WINDOW_HEIGHT = native_h

    pygame.display.set_caption("Grid-Sailing Task")
    clock = pygame.time.Clock()

    # Lazy imports — must happen AFTER config is patched
    from database.db import initialise_database
    from screens.welcome import run_welcome
    from screens.researcher_setup import run_researcher_setup, run_researcher_home
    from screens.participant_login import run_participant_login
    from core.session import run_session
    from screens.data_viewer import run_data_viewer

    initialise_database()

    # Step 1: Welcome (admin login)
    role = run_welcome(screen, clock)
    if role != "researcher":
        pygame.quit(); return

    # Step 2: Researcher home
    fonts_setup = (
        pygame.font.SysFont("Helvetica Neue", 40, bold=True),   # f_big
        pygame.font.SysFont("Helvetica Neue", 26, bold=True),   # f_med
        pygame.font.SysFont("Helvetica Neue", 20),              # f_sm
        pygame.font.SysFont("Helvetica Neue", 16),              # f_xs
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
            continue

    print(f"[MAIN] Session config: {config_data}")

    # Step 3: Participant login
    fonts = (
        pygame.font.SysFont("Helvetica Neue", 40, bold=True),
        pygame.font.SysFont("Helvetica Neue", 26, bold=True),
        pygame.font.SysFont("Helvetica Neue", 20),
        pygame.font.SysFont("Helvetica Neue", 16),
    )

    pid = config_data["participant_id"]
    sn  = config_data["session_number"]
    pygame.display.set_caption(f"Grid-Sailing  ·  {pid}  ·  Session {sn}")

    participant = run_participant_login(screen, clock, fonts, config_data)
    if not participant:
        pygame.quit(); return

    print(f"[MAIN] Participant confirmed: {participant['participant_id']}")

    # Step 4: Run the session
    run_session(screen, clock, fonts, config_data, participant)

    pygame.quit()


if __name__ == "__main__":
    main()
