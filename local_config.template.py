# ============================================================
#  GRID-SAILING TASK — Setting Up a New Computer
#
#  Hey Juliet — if you're reading this, you're setting up the ASUS
#  (or any new machine) for the first time. This file tells the app
#  which computer it's running on and where the Firebase key is.
#
#  Steps to set up:
#    1. Copy THIS file and rename the copy to:  local_config.py
#       (keep it in the same grid_sailing folder as main.py)
#    2. Change DEVICE_NAME below to something like "ASUS-Juliet"
#    3. Set FIREBASE_CREDENTIALS to the path of the JSON key file
#       (Jai will give you this file separately — don't share it)
#    4. Save and run python main.py — you're good to go.
#
#  local_config.py is never uploaded to GitHub. It stays private
#  on each machine, which is how the Firebase key stays secure.
# ============================================================

# What this computer is called in the Firebase dashboard.
# Use something recognisable like "ASUS-Juliet" so you know
# which machine collected which participant's data.
DEVICE_NAME = "ASUS-Juliet"

# Full path to the Firebase key file (the .json file Jai gave you).
#
# On the ASUS, if you put the key in the grid_sailing folder:
#   FIREBASE_CREDENTIALS = "gridsailing-firebase-adminsdk-fbsvc-557bd2a360.json"
#
# On Mac (Jai's setup), stored in a config folder:
#   FIREBASE_CREDENTIALS = "/Users/jai/.config/grid_sailing/serviceAccountKey.json"
FIREBASE_CREDENTIALS = "/path/to/serviceAccountKey.json"

# (Optional) Only uncomment this if you want the database file stored
# somewhere other than the default database/experiment.db location.
# DB_PATH = "/path/to/experiment.db"
