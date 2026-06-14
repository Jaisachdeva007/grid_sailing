# ============================================================
#  GRID-SAILING TASK — Entry Point
#
#  Run this file to start the experiment.
#  Flow:
#    1. Researcher setup screen  (Juliet configures the session)
#    2. Participant login screen  (participant confirms identity)
#    3. Experiment session        (trials run automatically)
# ============================================================

from database.db import initialise_database
from screens.researcher_setup import run_researcher_setup
from screens.participant_login import run_participant_login


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

    # Step 3: Run the session (to be built in Phase 3)
    print("[MAIN] Session runner coming in Phase 3.")


if __name__ == "__main__":
    main()
