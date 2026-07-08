# ============================================================
#  GRID-SAILING TASK — Entry Point
# ============================================================

import pygame


def main():
    pygame.init()

    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    native_w = screen.get_width()
    native_h = screen.get_height()

    import config
    config.WINDOW_WIDTH  = native_w
    config.WINDOW_HEIGHT = native_h

    pygame.display.set_caption("Grid-Sailing Task")
    clock = pygame.time.Clock()

    from database.db import initialise_database
    from screens.welcome import run_welcome
    from screens.researcher_setup import run_researcher_setup, run_researcher_home
    from screens.participant_login import run_participant_login
    from core.session import run_session
    from screens.data_viewer import run_data_viewer

    initialise_database()

    _fs = max(0.80, min(1.40, native_h / 900))
    fonts = (
        pygame.font.SysFont("Helvetica Neue", int(40 * _fs), bold=True),
        pygame.font.SysFont("Helvetica Neue", int(26 * _fs), bold=True),
        pygame.font.SysFont("Helvetica Neue", int(20 * _fs)),
        pygame.font.SysFont("Helvetica Neue", int(16 * _fs)),
    )

    # Step 1: Welcome / admin login — only once
    role = run_welcome(screen, clock)
    if role != "researcher":
        pygame.quit(); return

    # Main loop — every session completion or Save & Exit returns here
    while True:
        pygame.display.set_caption("Grid-Sailing Task")

        # Step 2: Researcher home
        choice = run_researcher_home(screen, clock)
        if choice is None:
            break   # researcher clicked quit

        if choice == "data":
            run_data_viewer(screen, clock, fonts)
            continue

        # Step 3: Researcher setup (configure session)
        config_data = run_researcher_setup(screen, clock, mode=choice)
        if config_data is None:
            continue   # researcher cancelled — back to home

        # Step 4: Participant login
        pid = config_data["participant_id"]
        sn  = config_data["session_number"]
        pygame.display.set_caption(f"Grid-Sailing  ·  {pid}  ·  Session {sn}")

        participant = run_participant_login(screen, clock, fonts, config_data)
        if not participant:
            continue   # login cancelled — back to home

        # Step 5: Run session (Save & Exit or normal completion both return here)
        run_session(screen, clock, fonts, config_data, participant)

        # Loop back to home automatically

    pygame.quit()


if __name__ == "__main__":
    main()
