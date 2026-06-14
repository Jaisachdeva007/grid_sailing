# ============================================================
#  GRID-SAILING TASK — Entry Point
#
#  Run this file to start the experiment.
#  Flow:
#    1. Researcher setup screen  (Juliet configures the session)
#    2. Participant login screen  (participant confirms identity)
#    3. Experiment session        (blocks + trials run automatically)
# ============================================================

import pygame
from config import WINDOW_WIDTH, WINDOW_HEIGHT, FPS
from database.db import initialise_database
from screens.researcher_setup import run_researcher_setup
from screens.participant_login import run_participant_login
from core.session import run_session


def main():
    # Ensure the database and all tables exist on startup
    initialise_database()

    # Step 1: Researcher configures the session
    config = run_researcher_setup()
    if not config:
        return

    print(f"[MAIN] Session config: {config}")

    # Step 2: Participant logs in with ID + PIN
    participant = run_participant_login(config)
    if not participant:
        return

    print(f"[MAIN] Participant confirmed: {participant['participant_id']}")

    # Step 3: Run the full session
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Grid-Sailing Task")
    clock  = pygame.time.Clock()

    fonts = (
        pygame.font.SysFont("Arial", 30, bold=True),
        pygame.font.SysFont("Arial", 20, bold=True),
        pygame.font.SysFont("Arial", 15),
        pygame.font.SysFont("Arial", 12),
    )

    run_session(screen, clock, fonts, config, participant)

    pygame.quit()


if __name__ == "__main__":
    main()
