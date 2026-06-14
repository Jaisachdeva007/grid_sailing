# ============================================================
#  GRID-SAILING TASK — Configuration
#  All researcher-adjustable settings live here.
#  No Python knowledge needed — just change the numbers.
# ============================================================

# --- Grid ---
GRID_SIZE = 5               # Number of rows and columns (5 = 5x5 grid)

# --- Key Mappings (do not change unless remapping fingers) ---
# Each key moves the cursor by (row_delta, col_delta)
KEY_MAPPINGS = {
    1: (-1,  0),   # Key 1 (index finger)  → UP
    2: ( 1,  1),   # Key 2 (middle finger) → DOWN-RIGHT
    3: ( 1, -1),   # Key 3 (ring finger)   → DOWN-LEFT
}

# --- Trial Timing (seconds) ---
PLANNING_TIME_SEC  = 6     # How long the start-goal grid stays on screen
ACTION_TIME_SEC    = 10    # Duration of the blank action/imagery stage
FEEDBACK_TIME_SEC  = 2     # How long the feedback screen is shown

# --- Experiment Structure ---
NUM_SESSIONS           = 3
NUM_BLOCKS_PER_SESSION = 4
NUM_TRIALS_PER_BLOCK   = 20
MIN_SEQUENCE_LENGTH    = 7  # Minimum key presses required for a valid puzzle

# --- Conditions ---
CONDITIONS = ["physical_practice", "motor_imagery", "control"]

# --- File Paths ---
PUZZLES_FILE = "valid_puzzles.json"
DATA_DIR     = "data/"

# --- Demo / Visual Settings ---
WINDOW_WIDTH   = 900
WINDOW_HEIGHT  = 700
ANIMATION_DELAY_MS = 600   # Milliseconds between each cursor step in the demo
