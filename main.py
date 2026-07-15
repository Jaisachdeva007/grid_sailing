# ============================================================
#  GRID-SAILING TASK — Entry Point
#
#  To start the experiment, run:
#      python main.py
#
#  You don't need to edit this file — all settings are in config.py.
#  This file just starts everything up and controls what screen
#  comes after what.
#
#  Screen flow:
#    1. Welcome screen   → you type the admin password
#    2. Researcher Home  → choose New / Returning / View Data
#    3. Researcher Setup → fill in participant details + session info
#    4. Participant Login → participant types their own ID to confirm
#    5. Session runs     → trials, scoring, imagery stage, etc.
#    6. After session    → automatically back to step 2
# ============================================================

import pygame


def main():
    # Start up pygame — the library that runs the window and reads keypresses.
    pygame.init()

    # Open in fullscreen using whatever the screen's actual resolution is.
    # On the ASUS this'll be 1920×1080; on a MacBook it picks it up automatically.
    screen    = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    native_w  = screen.get_width()
    native_h  = screen.get_height()

    # Tell the rest of the app how big the screen actually is, so everything
    # lays out correctly regardless of which computer this runs on.
    import config
    config.WINDOW_WIDTH  = native_w
    config.WINDOW_HEIGHT = native_h

    pygame.display.set_caption("Grid-Sailing Task")
    clock = pygame.time.Clock()   # keeps the screen refreshing at 60 fps

    # Load the screen modules here (not at the top) so the width/height above
    # is already set before any screen does its layout calculations.
    from database.db           import initialise_database
    from screens.welcome       import run_welcome
    from screens.researcher_setup import run_researcher_setup, run_researcher_home
    from screens.participant_login import run_participant_login
    from core.session          import run_session
    from screens.data_viewer   import run_data_viewer

    # Create the database and tables on first run. Totally safe to call every
    # time — it checks if they exist first and never deletes anything.
    initialise_database()

    # Build the four font sizes used throughout the app.
    # The scale factor adjusts them based on screen height so they look right
    # on the ASUS (1080p) and any other display we use.
    _fs = max(0.80, min(1.40, native_h / 900))   # 1.0 = baseline at 900px height
    fonts = (
        pygame.font.SysFont("Helvetica Neue", int(52 * _fs), bold=True),  # f_big  — large headings
        pygame.font.SysFont("Helvetica Neue", int(34 * _fs), bold=True),  # f_med  — medium labels
        pygame.font.SysFont("Helvetica Neue", int(26 * _fs)),              # f_sm   — body text
        pygame.font.SysFont("Helvetica Neue", int(20 * _fs)),              # f_xs   — small captions
    )

    # ── Step 1: Welcome screen ────────────────────────────────
    # You type the admin password here. If you close without logging in,
    # the app exits cleanly.
    role = run_welcome(screen, clock)
    if role != "researcher":
        pygame.quit(); return

    # ── Main loop ─────────────────────────────────────────────
    # Once you're logged in, the app stays in this loop until you quit.
    # Every time a session finishes, it comes back here and shows the home screen.
    while True:
        pygame.display.set_caption("Grid-Sailing Task")

        # ── Step 2: Researcher Home ───────────────────────────
        # You pick: New Participant, Returning Participant, or View Data.
        choice = run_researcher_home(screen, clock)
        if choice is None:
            break   # you pressed ESC or closed — exit

        if choice == "data":
            # You clicked "View Data" — open the dashboard, then come back here.
            run_data_viewer(screen, clock, fonts)
            continue

        # ── Step 3: Researcher Setup ──────────────────────────
        # You fill in participant ID, group, session number, timing overrides, etc.
        # Returns None if you hit Cancel (goes back to home screen).
        config_data = run_researcher_setup(screen, clock, mode=choice)
        if config_data is None:
            continue

        # Update the window title bar to show who's running and which session.
        pid = config_data["participant_id"]
        sn  = config_data["session_number"]
        pygame.display.set_caption(f"Grid-Sailing  ·  {pid}  ·  Session {sn}")

        # ── Step 4: Participant Login ─────────────────────────
        # The participant types their own ID to confirm they're the right person.
        participant = run_participant_login(screen, clock, fonts, config_data)
        if not participant:
            continue   # they cancelled — back to home

        # ── Step 5: Run the session ───────────────────────────
        # All blocks and trials run here. Returns when the session ends
        # normally or when you hit "Save & Exit" to pause mid-session.
        run_session(screen, clock, fonts, config_data, participant)

        # Session done — loop back to the home screen automatically.

    # Shut down cleanly when you quit.
    pygame.quit()


# This makes sure main() only runs when you do `python main.py` directly.
# If some other file imports this one, main() won't fire by accident.
if __name__ == "__main__":
    main()
