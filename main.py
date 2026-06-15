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
from screens.researcher_setup import run_researcher_setup
from screens.participant_login import run_participant_login
from core.session import run_session


def main():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SCALED)
    pygame.display.set_caption("Grid-Sailing Task")
    clock = pygame.time.Clock()

    initialise_database()

    # Step 1: Welcome — researcher logs in with admin password
    role = run_welcome(screen, clock)
    if role != "researcher":
        return

    # Step 2: Researcher configures the session
    config = run_researcher_setup(screen, clock)
    if not config:
        return

    print(f"[MAIN] Session config: {config}")

    # Step 3: Participant logs in with ID + PIN
    fonts = (
        pygame.font.SysFont("Helvetica Neue", 28, bold=True),
        pygame.font.SysFont("Helvetica Neue", 20, bold=True),
        pygame.font.SysFont("Helvetica Neue", 15),
        pygame.font.SysFont("Helvetica Neue", 12),
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
