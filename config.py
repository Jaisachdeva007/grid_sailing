# ============================================================
#  GRID-SAILING TASK — Master Configuration File
#
#  *** THIS IS THE MAIN FILE JULIET WILL NEED TO EDIT ***
#
#  Everything that controls how the experiment runs lives here.
#  You do NOT need to touch any other file for normal changes.
#
#  How to make a change:
#    1. Find the setting you want to change below
#    2. Edit the number or text on the right side of the = sign
#    3. Save the file (Ctrl+S)
#    4. Restart the experiment app for the change to take effect
#
#  IMPORTANT: Only change the VALUES (right side of =).
#             Do not delete the variable name (left side).
#             Do not remove the # comment lines — they explain things.
# ============================================================


# ── Grid ──────────────────────────────────────────────────────
# The grid is a square of cells that the participant navigates.

# How many rows AND columns the grid has. 5 = a 5×5 grid (25 cells total).
# Changing this changes the whole experiment structure — only change if
# you know what you're doing, as it affects puzzle generation.
GRID_SIZE = 5

# The maximum number of key presses an "optimal" path can have.
# Puzzles where the shortest valid route needs MORE than this many presses
# are thrown out. Currently 7 means: optimal paths are at most 7 moves long.
MAX_OPTIMAL_LENGTH = 7

# The MINIMUM number of key presses a valid puzzle path must have.
# Puzzles shorter than this are thrown out (too easy).
# Must be less than or equal to MAX_OPTIMAL_LENGTH.
MIN_SEQUENCE_LENGTH = 7


# ── Key Mappings ──────────────────────────────────────────────
# This maps each key number (1, 2, 3) to a direction on the grid.
# Format: key_number: (row_change, column_change)
#   row_change: negative = move UP a row, positive = move DOWN a row
#   col_change: negative = move LEFT a column, positive = move RIGHT a column
#
# Current mapping:
#   Key 1 (index finger)  → moves UP           (one row up, same column)
#   Key 2 (middle finger) → moves DOWN-RIGHT    (one row down, one column right)
#   Key 3 (ring finger)   → moves DOWN-LEFT     (one row down, one column left)
#
# Only change this if you physically remap which finger presses which key.
KEY_MAPPINGS = {
    1: (-1,  0),   # Key 1 → UP
    2: ( 1,  1),   # Key 2 → DOWN-RIGHT
    3: ( 1, -1),   # Key 3 → DOWN-LEFT
}


# ── Trial Timing ──────────────────────────────────────────────
# All times are in SECONDS. Adjust these to make the experiment
# easier (more time) or harder (less time).

# How long the participant can SEE the grid before the planning phase starts.
# They study the grid during this time. Range from the protocol: 6–9 seconds.
PLANNING_TIME_SEC = 6

# How long the participant has to TYPE their planned key sequence.
# If they run out of time, the trial is recorded as incorrect.
INPUT_TIME_SEC = 10

# How long the action/imagery phase lasts AFTER the participant submits
# their sequence. For MI groups this is when they imagine doing the movement.
# For PP groups this is when they physically execute it.
ACTION_TIME_SEC = 4

# How long the feedback screen (showing score, correct/incorrect) stays visible
# between trials. Longer = more time to read the result.
FEEDBACK_TIME_SEC = 2

# The gap (blank screen / "get ready") between one trial ending and the next starting.
# Protocol recommends 3–5 seconds.
INTERTRIAL_SEC = 4


# ── Scoring ───────────────────────────────────────────────────
# How points are awarded and deducted each trial.

# Points awarded for reaching the goal using EXACTLY the optimal number of moves.
# This is the maximum score possible on a single trial.
OPTIMAL_SCORE = 100

# Points DEDUCTED for each move that is more OR fewer than the optimal number.
# Example: optimal = 7 moves, participant used 9 → 2 extra → penalty = 2 × 5 = 10 pts
#          optimal = 7 moves, participant used 5 → 2 fewer  → penalty = 2 × 5 = 10 pts
EXTRA_MOVE_PENALTY = 5

# Score given if the participant does NOT reach the goal at all (incorrect trial).
# Leave at 0 — there is no partial credit.
ERROR_SCORE = 0


# ── Experiment Structure ──────────────────────────────────────
# How many sessions and trials make up the full experiment.

# Total number of sessions each participant completes across all their visits.
NUM_SESSIONS = 3

# Number of trials in every block (one block = one continuous run of trials).
TRIALS_PER_BLOCK = 20

# How many familiarisation blocks come at the START of Session 1.
# Familiarisation uses 100% random puzzles so the participant learns the controls.
FAMILIARIZATION_BLOCKS = 2


# ── Grid Ratios ───────────────────────────────────────────────
# What proportion of puzzles in each block type are the REPEATED puzzle
# (the same grid shown across all participants) vs. a new random puzzle.
# 0.72 means 72% repeated, 28% random. 0.0 means 100% random.

# Ratio for PRACTICE blocks (the main training phase).
PRACTICE_REPEATED_RATIO = 0.72   # 72% repeated, 28% random

# Ratio for TEST blocks (pre-test and post-test measurement sessions).
TEST_REPEATED_RATIO = 0.60       # 60% repeated, 40% random

# Ratio for FAMILIARISATION blocks.
# This is ALWAYS 0.0 (fully random) — do not change.
# Familiarisation is about learning the controls, not the specific grid.
FAMILIARIZATION_REPEATED_RATIO = 0.00


# ── Experimental Groups ───────────────────────────────────────
# The list of groups participants can be assigned to.
# Each group name appears as an option in the researcher setup screen.
# MI  = Motor Imagery  (participants imagine doing the movement)
# PP  = Physical Practice  (participants physically press the keys)
# CTRL = Control  (participants only plan, no movement or imagery)
# High/Low refers to the level of sensory feedback on the keypad device.
#
# To add a group: add a new line like "My-Group", inside the square brackets.
# To remove a group: delete that line.
# To rename a group: change the text (but this will affect existing data labels).
GROUPS = [
    "MI-High",    # Motor imagery — high sensory feedback keypad
    "MI-Low",     # Motor imagery — low sensory feedback keypad
    "PP-High",    # Physical practice — high sensory feedback keypad
    "PP-Low",     # Physical practice — low sensory feedback keypad
    "CTRL-High",  # Control (planning only) — high sensory feedback
    "CTRL-Low",   # Control (planning only) — low sensory feedback
]


# ── Session Structure ─────────────────────────────────────────
# Defines exactly which block types run in each session, in order.
# Each session number (1, 2, 3) maps to a list of block type names.
#
# Block types available:
#   "familiarization" — random puzzles only, teaches the controls
#   "pre_test"        — test measurement taken BEFORE practice
#   "practice"        — main training blocks (uses PRACTICE_REPEATED_RATIO)
#   "post_test"       — test measurement taken AFTER practice
#
# Example: session 1 runs 2 familiarisation blocks, then 1 pre-test, then 2 practice.
# Each block has TRIALS_PER_BLOCK trials (currently 20).
#
# Do NOT change this unless you are redesigning the experiment structure.
SESSION_STRUCTURE = {
    1: ["familiarization", "familiarization", "pre_test", "practice", "practice"],
    2: ["practice", "practice"],
    3: ["practice", "practice", "post_test"],
}


# ── Admin Access ──────────────────────────────────────────────
# The password Juliet types on the login screen to access the researcher setup.
# Change this to any password you want — just remember what you set it to!
# The password is case-sensitive (uppercase and lowercase matter).
ADMIN_PASSWORD = "2110"


# ── Database & Export ─────────────────────────────────────────
# Where the experiment data is stored on this computer.
# These are file paths relative to the folder where main.py lives.

# The SQLite database file. All trial data is saved here automatically.
# DO NOT change this unless you move the database/  folder.
DB_PATH = "database/experiment.db"

# The folder where CSV export files are saved when you click "Export" in the app.
# The folder is created automatically if it doesn't exist.
EXPORT_DIR = "exports/"


# ── Display ───────────────────────────────────────────────────
# Screen and visual settings. The app runs fullscreen, so WINDOW_WIDTH
# and WINDOW_HEIGHT are overwritten automatically at startup with the
# actual screen resolution. You generally do NOT need to change these.

WINDOW_WIDTH       = 1100   # default fallback — overwritten at runtime
WINDOW_HEIGHT      = 820    # default fallback — overwritten at runtime
ANIMATION_DELAY_MS = 600    # milliseconds between steps in the cursor replay animation
FPS                = 60     # frames per second (screen refresh rate)


# ── Cloud Sync (Firebase) ─────────────────────────────────────
# Settings for automatically backing up data to the Firebase cloud database.
# The actual credentials (the key file) live in local_config.py on each machine.
# See local_config.template.py for instructions on how to set that up.

import socket as _socket

# The unique name for THIS computer in the Firebase database.
# Overridden in local_config.py — e.g. "ASUS-Juliet" or "MacBook-Jai"
DEVICE_ID   = _socket.gethostname()   # uses computer's network name as default
DEVICE_NAME = DEVICE_ID

# Full path to the Firebase credentials JSON file on this machine.
# Set this in local_config.py — see local_config.template.py for an example.
# If left as None, syncing is disabled (no crash, just no cloud backup).
FIREBASE_CREDENTIALS = None

# How many trials to complete before automatically syncing to the cloud.
# 5 means: after every 5 trials, the data is pushed to Firebase in the background.
SYNC_EVERY_N_TRIALS = 5

# Also sync if this many SECONDS have passed since the last sync,
# even if 5 trials haven't been completed yet. Whichever comes first.
SYNC_TIME_SEC = 20

# Load per-machine overrides from local_config.py.
# That file is gitignored and never shared — it holds machine-specific settings
# like the Firebase key path and device name. Safe to ignore if the file doesn't exist.
try:
    from local_config import *  # noqa: F401,F403
except ImportError:
    pass
