# ============================================================
#  GRID-SAILING TASK — Main Settings File
#
#  Hey Juliet — this is basically the only file you'll ever
#  need to open. Everything that controls how the experiment
#  runs is in here: timing, scoring, groups, password, etc.
#
#  How to change something:
#    1. Find the setting below
#    2. Change the number or text on the RIGHT side of the =
#    3. Ctrl+S to save
#    4. Close and reopen the app for the change to kick in
#
#  One rule: only change the VALUE (the right side).
#  Don't delete the variable name on the left or the # lines.
# ============================================================


# ── Grid ──────────────────────────────────────────────────────

# The grid is a square — this sets how many rows AND columns it has.
# 5 means a 5×5 grid (25 cells). We built the whole study around this
# so don't change it unless you're redesigning the experiment.
GRID_SIZE = 5

# The longest "optimal" route we'll accept for a puzzle.
# Any puzzle that needs more than 7 moves to solve is thrown out.
MAX_OPTIMAL_LENGTH = 7

# The shortest route we'll accept. Must be ≤ MAX_OPTIMAL_LENGTH.
# Set to 3 because every valid puzzle already requires all 3 keys at least once,
# so the minimum possible valid path is 3 moves.
MIN_SEQUENCE_LENGTH = 5
MAX_SEQUENCE_LENGTH = 7


# ── Key Mappings ──────────────────────────────────────────────
# This links each key number to a direction on the grid.
# Only change this if you physically rewire which finger uses which key.
#   Key 1 = index finger  → moves UP
#   Key 2 = middle finger → moves DOWN-RIGHT
#   Key 3 = ring finger   → moves DOWN-LEFT
KEY_MAPPINGS = {
    1: (-1,  0),   # Key 1 → UP
    2: ( 1,  1),   # Key 2 → DOWN-RIGHT
    3: ( 1, -1),   # Key 3 → DOWN-LEFT
}


# ── Trial Timing ──────────────────────────────────────────────
# Everything here is in SECONDS. These are the defaults — you can
# also override them per-session from the Researcher Setup screen
# without permanently changing this file.

# How long participants get to stare at the grid and plan their route
# before anything happens. Protocol says 6–9 seconds.
PLANNING_TIME_SEC = 6

# How long they have to actually TYPE their key sequence after planning.
# If the timer runs out, that trial gets marked as incorrect.
INPUT_TIME_SEC = 10

# How long the action / imagery phase lasts after they submit their sequence.
# MI groups: they imagine doing the movement during this time.
# PP groups: they physically press the keys.
# CTRL groups: they just wait.
ACTION_TIME_SEC = 4

# How long the feedback card (score, correct/incorrect) stays on screen
# between trials. Longer gives them more time to read it.
FEEDBACK_TIME_SEC = 2

# The blank "Get Ready" gap between one trial finishing and the next starting.
# Protocol says 3–5 seconds.
INTERTRIAL_SEC = 4


# ── Scoring ───────────────────────────────────────────────────

# Maximum points for a perfect trial — reached the goal in exactly the
# optimal number of moves.
OPTIMAL_SCORE = 100

# Points taken off for every move that's MORE or FEWER than optimal.
# e.g. optimal = 7, participant used 9 → 2 off → penalty = 2 × 10 = 20 pts
#      optimal = 7, participant used 5 → 2 short → penalty = 2 × 10 = 20 pts
# Both directions are penalised equally.
EXTRA_MOVE_PENALTY = 10

# Score when the participant doesn't reach the goal at all. Leave at 0.
ERROR_SCORE = 0


# ── Experiment Structure ──────────────────────────────────────

# Total number of sessions per participant across all their visits.
NUM_SESSIONS = 3

# Number of trials in every single block (one block = one continuous run).
TRIALS_PER_BLOCK = 20

# How many familiarisation blocks are in Session 1.
# These use random puzzles only — purely for learning the controls.
FAMILIARIZATION_BLOCKS = 2


# ── Grid Ratios ───────────────────────────────────────────────
# What fraction of puzzles in each block are the REPEATED puzzle
# (the same grid used across all participants) versus a random one.
# 0.72 = 72% repeated, 28% random.

# For practice blocks (the main training phase).
PRACTICE_REPEATED_RATIO = 0.72

# For pre-test and post-test blocks.
TEST_REPEATED_RATIO = 0.60

# For familiarisation — always fully random. Don't change this.
FAMILIARIZATION_REPEATED_RATIO = 0.00


# ── Experimental Groups ───────────────────────────────────────
# The list that appears in the Group dropdown on the setup screen.
# MI  = Motor Imagery
# PP  = Physical Practice
# CTRL = Control (planning only, no movement)
# High/Low = level of sensory feedback on the keypad
#
# To add a group: add a new line inside the square brackets like "New-Group"
# To remove one: delete that line
# To rename: change the text (but this changes labels in existing data too)
GROUPS = [
    "MI-High",
    "MI-Low",
    "PP-High",
    "PP-Low",
    "CTRL-High",
    "CTRL-Low",
]


# ── Session Structure ─────────────────────────────────────────
# This is what runs in each session, in order.
# Each session number maps to a list of block types.
#
# Available block types:
#   "familiarization" — 100% random, just learning the controls
#   "pre_test"        — measurement before training starts
#   "practice"        — main training (uses PRACTICE_REPEATED_RATIO above)
#   "post_test"       — measurement after training
#
# Each block runs TRIALS_PER_BLOCK trials (currently 20).
# Don't change this unless we're redesigning the study structure.
SESSION_STRUCTURE = {
    1: ["familiarization", "familiarization", "pre_test", "practice", "practice"],
    2: ["practice", "practice"],
    3: ["practice", "practice", "post_test"],
}


# ── Admin Password ────────────────────────────────────────────
# The password you type on the first screen to get into the researcher setup.
# Change it to anything you want — just remember what you set it to!
# It's case-sensitive (capital and lowercase letters matter).
ADMIN_PASSWORD = "2110"


# ── Database & Export Paths ───────────────────────────────────
# Where the data lives on this computer. These are paths relative to
# the grid_sailing folder. Don't change these unless you move stuff around.

# The database file — all trial data gets saved here automatically.
DB_PATH = "database/experiment.db"

# Where CSV files go when you click Export. Created automatically if missing.
EXPORT_DIR = "exports/"


# ── Display ───────────────────────────────────────────────────
# The app runs fullscreen and auto-detects your screen size at startup,
# so these two get overwritten automatically. You don't need to touch them.
WINDOW_WIDTH       = 1100
WINDOW_HEIGHT      = 820
ANIMATION_DELAY_MS = 600   # how fast the cursor replay animation plays (ms)
FPS                = 60    # screen refresh rate


# ── Firebase Cloud Backup ─────────────────────────────────────
# Settings for syncing data to the cloud in the background.
# The credentials file (the JSON key) lives in local_config.py on each machine
# — see local_config.template.py for how to set that up on a new computer.

import socket as _socket

# The name for this computer in the Firebase dashboard.
# Set to something like "ASUS-Juliet" in local_config.py.
DEVICE_ID   = _socket.gethostname()
DEVICE_NAME = DEVICE_ID

# Path to the Firebase key file. Set this in local_config.py.
# If it's left as None, cloud sync is simply skipped (no crash).
FIREBASE_CREDENTIALS = None

# Push to Firebase after this many completed trials.
SYNC_EVERY_N_TRIALS = 5

# Also push if this many seconds have passed since the last sync
# — whichever of the two comes first triggers it.
SYNC_TIME_SEC = 20

# Load per-machine settings (local_config.py is private to each computer
# and never gets uploaded to GitHub).
try:
    from local_config import *  # noqa: F401,F403
except ImportError:
    pass
