# ============================================================
#  GRID-SAILING TASK — Entry Point
#
#  Flow:
#    1. Welcome screen  (researcher enters admin password)
#    2. Researcher Setup  (configure session, view data, export)
#    3. Participant Login  (participant enters ID + PIN)
#    4. Session  (blocks + trials run automatically)
# ============================================================

import pygame
from config import WINDOW_WIDTH, WINDOW_HEIGHT, FPS
from database.db import initialise_database
from screens.welcome import run_welcome
from screens.researcher_setup import run_researcher_setup, run_researcher_home
from screens.participant_login import run_participant_login
from core.session import run_session


def main():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT),
                                      pygame.FULLSCREEN | pygame.SCALED)
    pygame.display.set_caption("Grid-Sailing Task")
    clock = pygame.time.Clock()

    initialise_database()

    # Step 1: Welcome — researcher logs in with admin password
    role = run_welcome(screen, clock)
    if role != "researcher":
        return

    # Step 2: Researcher picks what to do (home screen)
    from screens.data_viewer import run_data_viewer
    fonts_setup = (
        pygame.font.SysFont("Helvetica Neue", 34, bold=True),
        pygame.font.SysFont("Helvetica Neue", 22, bold=True),
        pygame.font.SysFont("Helvetica Neue", 17),
        pygame.font.SysFont("Helvetica Neue", 14),
    )

    config = None
    while config is None:
        choice = run_researcher_home(screen, clock)
        if choice is None:
            return
        if choice == "data":
            run_data_viewer(screen, clock, fonts_setup)
            continue
        config = run_researcher_setup(screen, clock, mode=choice)
        if config is None:
            continue   # researcher hit ESC — go back to home

    print(f"[MAIN] Session config: {config}")

    # Step 3: Participant logs in with ID + PIN
    fonts = (
        pygame.font.SysFont("Helvetica Neue", 34, bold=True),
        pygame.font.SysFont("Helvetica Neue", 22, bold=True),
        pygame.font.SysFont("Helvetica Neue", 17),
        pygame.font.SysFont("Helvetica Neue", 14),
    )

    pid = config["participant_id"]
    sn  = config["session_number"]
    pygame.display.set_caption(f"Grid-Sailing  ·  {pid}  ·  Session {sn}")

    participant = run_participant_login(screen, clock, fonts, config)
    if not participant:
        return

    print(f"[MAIN] Participant confirmed: {participant['participant_id']}")

    # Step 4: Run the session
    run_session(screen, clock, fonts, config, participant)

    pygame.quit()


if __name__ == "__main__":
    main()
