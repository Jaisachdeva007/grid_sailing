# ============================================================
#  GRID-SAILING TASK — Configuration
#  Default values for all experiment parameters.
#  Researcher can override any of these from the setup screen
#  before each session — no code changes needed.
# ============================================================

# --- Grid ---
GRID_SIZE            = 5    # Rows and columns (5 = 5x5 grid)
MAX_OPTIMAL_LENGTH   = 7    # Optimal path must be at most this many presses
MIN_SEQUENCE_LENGTH  = 7    # DFS paths must be at least this many presses

# --- Key Mappings (do not change unless remapping fingers) ---
KEY_MAPPINGS = {
    1: (-1,  0),   # Key 1 (index finger)  → UP
    2: ( 1,  1),   # Key 2 (middle finger) → DOWN-RIGHT
    3: ( 1, -1),   # Key 3 (ring finger)   → DOWN-LEFT
}

# --- Trial Timing (seconds) ---
PLANNING_TIME_SEC    = 6    # How long the grid is shown (6–9 per protocol)
INPUT_TIME_SEC       = 10   # Time to enter planned sequence
ACTION_TIME_SEC      = 10   # Duration of action / imagery stage
FEEDBACK_TIME_SEC    = 2    # How long per-trial feedback is displayed
INTERTRIAL_SEC       = 4    # Gap between trials (3–5 seconds)

# --- Scoring ---
OPTIMAL_SCORE        = 100  # Points for executing the shortest valid sequence
EXTRA_MOVE_PENALTY   = 5    # Points deducted per move beyond optimal
ERROR_SCORE          = 0    # Score if cursor does not reach goal

# --- Experiment Structure ---
NUM_SESSIONS              = 3
TRIALS_PER_BLOCK          = 20
FAMILIARIZATION_BLOCKS    = 2

# --- Grid Ratios (proportion of REPEATED grids per block type) ---
PRACTICE_REPEATED_RATIO       = 0.72   # 72:28 repeated:random
TEST_REPEATED_RATIO           = 0.60   # 60:40 repeated:random
FAMILIARIZATION_REPEATED_RATIO = 0.00  # 100% random during familiarization

# --- Experimental Groups ---
GROUPS = [
    "MI-High",    # Motor imagery — high sensory feedback keypad
    "MI-Low",     # Motor imagery — low sensory feedback keypad
    "PP-High",    # Physical practice — high sensory feedback keypad
    "PP-Low",     # Physical practice — low sensory feedback keypad
    "CTRL-High",  # Control (planning only) — high sensory feedback
    "CTRL-Low",   # Control (planning only) — low sensory feedback
]

# --- Session Structure (ordered block types per session) ---
SESSION_STRUCTURE = {
    1: ["familiarization", "familiarization", "pre_test", "practice", "practice"],
    2: ["practice", "practice"],
    3: ["practice", "practice", "post_test"],
}

# --- Admin Access ---
# Change this password before deployment. Juliet uses it to access researcher setup.
ADMIN_PASSWORD = "2110"

# --- Database & Export ---
DB_PATH    = "database/experiment.db"
EXPORT_DIR = "exports/"

# --- Display ---
WINDOW_WIDTH       = 1100
WINDOW_HEIGHT      = 820
ANIMATION_DELAY_MS = 600
FPS                = 60
