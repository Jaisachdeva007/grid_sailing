# ============================================================
#  GRID-SAILING TASK — Entry Point
#
#  This is the file you run to start the experiment:
#      python main.py
#
#  You do NOT need to edit this file. All experiment settings
#  are in config.py. This file just wires everything together
#  and defines the flow from screen to screen.
#
#  Screen flow:
#    1. Welcome screen  →  Juliet types the admin password
#    2. Researcher Home →  choose New / Returning / View Data
#    3. Researcher Setup → fill in participant details, timing, etc.
#    4. Participant Login → participant types their ID
#    5. Session runs (trials, feedback, imagery stage)
#    6. After session → automatically back to step 2
# ============================================================

import pygame


def main():
    # Initialise the pygame library (required before any display or input work).
    pygame.init()

    # Open the window in TRUE fullscreen mode, using the screen's native resolution.
    # On the ASUS this will be 1920×1080; on a MacBook it auto-detects the size.
    screen    = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    native_w  = screen.get_width()
    native_h  = screen.get_height()

    # Overwrite the config width/height with the actual screen size so all
    # screens in the app lay out correctly for this machine.
    import config
    config.WINDOW_WIDTH  = native_w
    config.WINDOW_HEIGHT = native_h

    pygame.display.set_caption("Grid-Sailing Task")
    clock = pygame.time.Clock()   # controls how fast the screen refreshes (see FPS in config.py)

    # Import all the major modules.  These are loaded here (not at the top of the
    # file) so that config's width/height override is already in place when they run.
    from database.db           import initialise_database
    from screens.welcome       import run_welcome
    from screens.researcher_setup import run_researcher_setup, run_researcher_home
    from screens.participant_login import run_participant_login
    from core.session          import run_session
    from screens.data_viewer   import run_data_viewer

    # Create the database file and tables if they don't exist yet.
    # Safe to call every time — it never deletes existing data.
    initialise_database()

    # Build the shared font set that most screens use.
    # Font sizes scale up/down automatically based on screen height so the
    # interface looks good on both the ASUS (1080p) and any other display.
    _fs = max(0.80, min(1.40, native_h / 900))   # scale factor: 1.0 = 900px reference height
    fonts = (
        pygame.font.SysFont("Helvetica Neue", int(40 * _fs), bold=True),  # f_big  — large headings
        pygame.font.SysFont("Helvetica Neue", int(26 * _fs), bold=True),  # f_med  — medium labels
        pygame.font.SysFont("Helvetica Neue", int(20 * _fs)),              # f_sm   — body text
        pygame.font.SysFont("Helvetica Neue", int(16 * _fs)),              # f_xs   — small captions
    )

    # ── Step 1: Welcome / admin password screen ───────────────
    # Shown once at startup. Juliet types the admin password to enter.
    # If she closes the window without logging in, the app exits cleanly.
    role = run_welcome(screen, clock)
    if role != "researcher":
        pygame.quit(); return

    # ── Main loop ─────────────────────────────────────────────
    # After login, the app stays in this loop indefinitely.
    # Each time a session finishes (or the researcher goes back to the home
    # screen), execution returns to the top of this while loop.
    while True:
        pygame.display.set_caption("Grid-Sailing Task")

        # ── Step 2: Researcher Home ───────────────────────────
        # Three cards: New Participant, Returning Participant, View Data.
        # Returns the card the researcher clicked, or None if they pressed ESC.
        choice = run_researcher_home(screen, clock)
        if choice is None:
            break   # researcher chose to quit — exit the loop and close

        if choice == "data":
            # Researcher clicked "View Data" — open the data viewer, then loop back.
            run_data_viewer(screen, clock, fonts)
            continue

        # ── Step 3: Researcher Setup ──────────────────────────
        # Form where Juliet sets participant ID, group, session number, timing, etc.
        # Returns a dictionary of settings, or None if the researcher cancelled.
        config_data = run_researcher_setup(screen, clock, mode=choice)
        if config_data is None:
            continue   # cancelled — go back to the home screen

        # Update the window title to show which participant and session is running.
        pid = config_data["participant_id"]
        sn  = config_data["session_number"]
        pygame.display.set_caption(f"Grid-Sailing  ·  {pid}  ·  Session {sn}")

        # ── Step 4: Participant Login ─────────────────────────
        # The participant types their own ID to confirm they are the right person.
        # Returns the participant's database record, or None if cancelled.
        participant = run_participant_login(screen, clock, fonts, config_data)
        if not participant:
            continue   # login cancelled — go back to home

        # ── Step 5: Run the session ───────────────────────────
        # This runs all the blocks and trials for this session.
        # Control returns here when the session ends normally OR the researcher
        # uses "Save & Exit" to pause mid-session.
        run_session(screen, clock, fonts, config_data, participant)

        # Automatically loop back to the home screen for the next participant.

    # Clean shutdown of the pygame library when the researcher quits.
    pygame.quit()


# Only run main() when this file is executed directly (python main.py).
# If another module imports this file, main() does NOT run automatically.
if __name__ == "__main__":
    main()
