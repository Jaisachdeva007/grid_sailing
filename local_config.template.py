# ============================================================
#  GRID-SAILING TASK — Per-Machine Configuration Template
#
#  *** HOW TO SET UP A NEW COMPUTER ***
#
#  Each computer that runs the experiment needs its OWN local_config.py.
#  This template shows you exactly what to put in it.
#
#  Steps:
#    1. Copy this file and rename the copy to:   local_config.py
#       (keep it in the same folder as main.py)
#    2. Set DEVICE_NAME to a short label for this machine (see below).
#    3. Set FIREBASE_CREDENTIALS to the full path of the Firebase key file.
#    4. Save and restart the app.
#
#  The local_config.py file is NEVER uploaded to GitHub — it is private
#  to each machine and keeps the Firebase credentials secure.
# ============================================================

# Short label for this computer. Appears in Firebase under "devices/"
# so you can tell which machine collected which data.
# Use something clear like "ASUS-Juliet" or "MacBook-Jai".
DEVICE_NAME = "ASUS-Juliet"

# Full path to the Firebase credentials file (the .json key file).
#
# On the ASUS (Windows), if you put the key file in the grid_sailing folder:
#   FIREBASE_CREDENTIALS = "gridsailing-firebase-adminsdk-fbsvc-557bd2a360.json"
#
# On Mac, if you stored it in a hidden config folder:
#   FIREBASE_CREDENTIALS = "/Users/jai/.config/grid_sailing/serviceAccountKey.json"
FIREBASE_CREDENTIALS = "/path/to/serviceAccountKey.json"

# (Optional) Override where the database file is stored on this machine.
# Only set this if you want the database somewhere other than database/experiment.db
# DB_PATH = "/path/to/experiment.db"
