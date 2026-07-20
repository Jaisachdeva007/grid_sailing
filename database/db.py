# ============================================================
#  GRID-SAILING TASK — Database Layer
#
#  You don't need to touch this file.
#
#  This is what keeps all the data on the laptop's hard drive.
#  It runs automatically in the background — you never interact
#  with it directly. Here's what it does:
#    - Creates the database file (database/experiment.db) on first run
#    - Saves every trial and key press the moment they happen
#    - If the computer crashes, nothing is lost — it's committed to disk
#      before the next trial even starts
#
#  Database tables (if you ever want to peek: install SQLite Viewer
#  as a Firefox extension and open experiment.db directly):
#    participants    — one row per participant (ID, age, group, etc.)
#    sessions        — one row per block run
#    trials          — one row per completed trial (score, moves, timing)
#    keypresses      — one row per individual key press (most detailed)
#    reflections     — one row per 3E reflection form (MI groups only)
#    global_settings — stores the repeated puzzle positions
# ============================================================

import sqlite3
import os
from datetime import datetime
from config import DB_PATH


def get_connection():
    """
    Open and return a connection to the SQLite database.
    Creates the database file if it does not exist.
    """
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row   # allows dict-style access to rows
    conn.execute("PRAGMA journal_mode=WAL")  # safer concurrent writes
    return conn


def initialise_database():
    """
    Create all tables if they do not already exist.
    Safe to call on every startup — will not overwrite existing data.
    """
    conn = get_connection()
    c = conn.cursor()

    # --- Participants ---
    c.execute("""
        CREATE TABLE IF NOT EXISTS participants (
            participant_id   TEXT PRIMARY KEY,
            pin_hash         TEXT NOT NULL DEFAULT '',
            group_name       TEXT NOT NULL,
            age              INTEGER,
            gender           TEXT,
            handedness       TEXT,
            created_at       TEXT DEFAULT (datetime('now'))
        )
    """)

    # --- Sessions ---
    c.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id            INTEGER PRIMARY KEY AUTOINCREMENT,
            participant_id        TEXT NOT NULL,
            session_number        INTEGER NOT NULL,
            block_type            TEXT NOT NULL,
            block_number          INTEGER NOT NULL,
            started_at            TEXT,
            completed_at          TEXT,
            last_trial_completed  INTEGER DEFAULT 0,
            FOREIGN KEY (participant_id) REFERENCES participants(participant_id)
        )
    """)

    # --- Trials ---
    c.execute("""
        CREATE TABLE IF NOT EXISTS trials (
            trial_id             INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id           INTEGER NOT NULL,
            participant_id       TEXT NOT NULL,
            trial_number         INTEGER NOT NULL,
            grid_type            TEXT NOT NULL,
            start_row            INTEGER NOT NULL,
            start_col            INTEGER NOT NULL,
            goal_row             INTEGER NOT NULL,
            goal_col             INTEGER NOT NULL,
            planned_sequence     TEXT,
            optimal_sequence     TEXT NOT NULL,
            optimal_length       INTEGER NOT NULL,
            number_of_moves      INTEGER,
            reward_score         INTEGER,
            reaction_time_ms     REAL,
            movement_time_ms     REAL,
            elapsed_time_s       REAL,
            imagery_duration_ms  REAL,
            is_correct           INTEGER,
            oob_count            INTEGER DEFAULT 0,
            created_at           TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        )
    """)

    # --- Key Presses (most granular — one row per key press) ---
    c.execute("""
        CREATE TABLE IF NOT EXISTS keypresses (
            keypress_id              INTEGER PRIMARY KEY AUTOINCREMENT,
            trial_id                 INTEGER NOT NULL,
            participant_id           TEXT NOT NULL,
            key_pressed              INTEGER NOT NULL,
            cursor_row_before        INTEGER NOT NULL,
            cursor_col_before        INTEGER NOT NULL,
            cursor_row_after         INTEGER NOT NULL,
            cursor_col_after         INTEGER NOT NULL,
            timestamp_ms             REAL NOT NULL,
            time_since_trial_start_ms REAL NOT NULL,
            time_since_last_press_ms  REAL,
            FOREIGN KEY (trial_id) REFERENCES trials(trial_id)
        )
    """)

    # --- Reflections (MI groups only, after each practice session) ---
    c.execute("""
        CREATE TABLE IF NOT EXISTS reflections (
            reflection_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            participant_id    TEXT NOT NULL,
            session_number    INTEGER NOT NULL,
            imagery_content   TEXT,
            perspective       TEXT,
            modalities        TEXT,
            engagement_score  INTEGER,
            next_session_goal TEXT,
            created_at        TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (participant_id) REFERENCES participants(participant_id)
        )
    """)

    # Global settings (e.g. experiment-wide repeated puzzle)
    c.execute("""
        CREATE TABLE IF NOT EXISTS global_settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    # Migrations for existing databases
    for migration in [
        "ALTER TABLE trials ADD COLUMN all_optimal_sequences TEXT",
        "ALTER TABLE trials ADD COLUMN oob_count INTEGER DEFAULT 0",
    ]:
        try:
            c.execute(migration)
            conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists

    conn.commit()
    conn.close()
    print(f"[DB] Database ready at {DB_PATH}")


# ── Global repeated puzzle ───────────────────────────────────

def get_global_repeated_puzzle():
    """Return the experiment-wide repeated puzzle as a dict, or None if not yet set."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT key, value FROM global_settings WHERE key IN ('rep_start','rep_goal','rep_seq')"
    ).fetchall()
    conn.close()
    d = {r["key"]: r["value"] for r in rows}
    if len(d) < 3:
        return None
    start = [int(x) for x in d["rep_start"].split(",")]
    goal  = [int(x) for x in d["rep_goal"].split(",")]
    seq   = [int(x) for x in d["rep_seq"].split(",")]
    return {"start": start, "goal": goal, "sequence": seq, "length": len(seq)}


def set_global_repeated_puzzle(puzzle):
    """Save the experiment-wide repeated puzzle. Called once on the first session."""
    conn = get_connection()
    pairs = [
        ("rep_start", ",".join(str(x) for x in puzzle["start"])),
        ("rep_goal",  ",".join(str(x) for x in puzzle["goal"])),
        ("rep_seq",   ",".join(str(x) for x in puzzle["sequence"])),
    ]
    for key, val in pairs:
        conn.execute(
            "INSERT OR REPLACE INTO global_settings (key, value) VALUES (?, ?)",
            (key, val)
        )
    conn.commit()
    conn.close()


def clear_global_repeated_puzzle():
    """Reset the experiment-wide repeated puzzle (use when starting a new cohort)."""
    conn = get_connection()
    conn.execute(
        "DELETE FROM global_settings WHERE key IN ('rep_start','rep_goal','rep_seq')"
    )
    conn.commit()
    conn.close()


# ── Participant functions ────────────────────────────────────

def create_participant(participant_id, group_name, age, gender, handedness):
    """
    Register a new participant. Returns True on success, False if ID already exists.
    """
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO participants (participant_id, pin_hash, group_name, age, gender, handedness)
            VALUES (?, '', ?, ?, ?, ?)
        """, (participant_id, group_name, age, gender, handedness))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def verify_participant(participant_id):
    """
    Look up a participant by ID. Returns the participant row or None.
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM participants WHERE participant_id = ?",
        (participant_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_participants():
    """Return a list of all participant IDs for the researcher dropdown."""
    conn = get_connection()
    rows = conn.execute("SELECT participant_id, group_name FROM participants ORDER BY participant_id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_participant_stats():
    """
    Return per-participant aggregated stats for the data viewer dashboard.
    Joins participants → sessions → trials to compute accuracy, score, counts.
    """
    conn = get_connection()
    rows = conn.execute("""
        SELECT
            p.participant_id,
            p.group_name,
            p.age,
            p.gender,
            p.created_at,
            COUNT(DISTINCT s.session_id)                             AS sessions_done,
            COUNT(t.trial_id)                                        AS total_trials,
            COALESCE(AVG(CASE WHEN t.is_correct=1 THEN 100.0 ELSE 0 END), 0) AS accuracy_pct,
            COALESCE(AVG(t.reward_score), 0)                        AS avg_score,
            COALESCE(SUM(t.reward_score), 0)                        AS total_score,
            COALESCE(AVG(t.reaction_time_ms), 0)                    AS avg_rt_ms
        FROM participants p
        LEFT JOIN sessions s  ON p.participant_id = s.participant_id
                              AND s.completed_at IS NOT NULL
        LEFT JOIN trials   t  ON s.session_id = t.session_id
        GROUP BY p.participant_id
        ORDER BY p.participant_id
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_participant_trials(participant_id):
    """Return every trial for a participant with full detail."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT
            s.session_number,
            s.block_type,
            s.block_number,
            t.trial_number,
            t.grid_type,
            t.start_row,
            t.start_col,
            t.goal_row,
            t.goal_col,
            t.planned_sequence,
            t.optimal_sequence,
            t.optimal_length,
            t.number_of_moves,
            t.reward_score,
            t.is_correct,
            t.reaction_time_ms,
            t.movement_time_ms,
            t.elapsed_time_s,
            t.imagery_duration_ms,
            t.created_at
        FROM sessions s
        JOIN trials t ON s.session_id = t.session_id
        WHERE s.participant_id = ?
        ORDER BY s.session_number, s.block_number, t.trial_number
    """, (participant_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_session_breakdown(participant_id):
    """Return per-session stats for one participant (used in detail view)."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT
            s.session_number,
            s.block_type,
            s.block_number,
            s.completed_at IS NOT NULL                               AS completed,
            COUNT(t.trial_id)                                        AS trials,
            COALESCE(AVG(CASE WHEN t.is_correct=1 THEN 100.0 ELSE 0 END), 0) AS accuracy_pct,
            COALESCE(AVG(t.reward_score), 0)                        AS avg_score
        FROM sessions s
        LEFT JOIN trials t ON s.session_id = t.session_id
        WHERE s.participant_id = ?
        GROUP BY s.session_id
        ORDER BY s.session_number, s.block_number
    """, (participant_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Session functions ────────────────────────────────────────

def create_session(participant_id, session_number, block_type, block_number):
    """
    Create a new session record and return its session_id.

    Args:
        participant_id (str): Who this session belongs to.
        session_number (int): 1, 2, or 3.
        block_type (str): familiarization / pre_test / practice / post_test.
        block_number (int): Index of this block within the session.

    Returns:
        int: The new session_id.
    """
    conn = get_connection()
    cursor = conn.execute("""
        INSERT INTO sessions (participant_id, session_number, block_type, block_number, started_at)
        VALUES (?, ?, ?, ?, ?)
    """, (participant_id, session_number, block_type, block_number, datetime.now().isoformat()))
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return session_id


def update_session_progress(session_id, last_trial_completed):
    """
    Update which trial was last completed — used for auto-resume after crash.

    Args:
        session_id (int): The session to update.
        last_trial_completed (int): Trial number of the last saved trial.
    """
    conn = get_connection()
    conn.execute(
        "UPDATE sessions SET last_trial_completed = ? WHERE session_id = ?",
        (last_trial_completed, session_id)
    )
    conn.commit()
    conn.close()


def complete_session(session_id):
    """Mark a session as fully completed."""
    conn = get_connection()
    conn.execute(
        "UPDATE sessions SET completed_at = ? WHERE session_id = ?",
        (datetime.now().isoformat(), session_id)
    )
    conn.commit()
    conn.close()


def get_completed_blocks(participant_id, session_number):
    """Return set of block_numbers already fully completed for this session."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT DISTINCT block_number FROM sessions
        WHERE participant_id = ? AND session_number = ?
          AND completed_at IS NOT NULL
    """, (participant_id, session_number)).fetchall()
    conn.close()
    return {r["block_number"] for r in rows}


def get_resume_point(participant_id, session_number, block_type, block_number):
    """
    Find an incomplete session for this participant and return its state.

    Returns:
        dict with session_id and last_trial_completed, or None if no resume point.
    """
    conn = get_connection()
    row = conn.execute("""
        SELECT session_id, last_trial_completed FROM sessions
        WHERE participant_id = ? AND session_number = ?
          AND block_type = ? AND block_number = ?
          AND completed_at IS NULL
        ORDER BY session_id DESC LIMIT 1
    """, (participant_id, session_number, block_type, block_number)).fetchone()
    conn.close()
    return dict(row) if row else None


# ── Trial functions ──────────────────────────────────────────

def save_trial(session_id, participant_id, trial_number, grid_type,
               start_row, start_col, goal_row, goal_col,
               planned_sequence, optimal_sequence, optimal_length,
               number_of_moves, reward_score,
               reaction_time_ms, movement_time_ms, elapsed_time_s,
               imagery_duration_ms, is_correct,
               all_optimal_sequences=None, oob_count=0):
    """
    Save a completed trial to the database and return its trial_id.
    Called at the end of every trial regardless of outcome.
    """
    conn = get_connection()
    cursor = conn.execute("""
        INSERT INTO trials (
            session_id, participant_id, trial_number, grid_type,
            start_row, start_col, goal_row, goal_col,
            planned_sequence, optimal_sequence, optimal_length,
            number_of_moves, reward_score,
            reaction_time_ms, movement_time_ms, elapsed_time_s,
            imagery_duration_ms, is_correct, all_optimal_sequences, oob_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        session_id, participant_id, trial_number, grid_type,
        start_row, start_col, goal_row, goal_col,
        str(planned_sequence), str(optimal_sequence), optimal_length,
        number_of_moves, reward_score,
        reaction_time_ms, movement_time_ms, elapsed_time_s,
        imagery_duration_ms, int(is_correct), all_optimal_sequences, oob_count
    ))
    trial_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return trial_id


# ── Key press functions ──────────────────────────────────────

def save_keypress(trial_id, participant_id, key_pressed,
                  cursor_row_before, cursor_col_before,
                  cursor_row_after, cursor_col_after,
                  timestamp_ms, time_since_trial_start_ms, time_since_last_press_ms):
    """
    Save a single key press event immediately to the database.
    Called after EVERY key press — guarantees no data loss on crash.

    Args:
        trial_id (int): Trial this key press belongs to.
        participant_id (str): Participant who pressed the key.
        key_pressed (int): 1, 2, or 3.
        cursor_row_before / cursor_col_before: Position before the press.
        cursor_row_after / cursor_col_after: Position after the press.
        timestamp_ms (float): Absolute time in milliseconds.
        time_since_trial_start_ms (float): Time since the trial began.
        time_since_last_press_ms (float or None): Inter-key interval.
    """
    conn = get_connection()
    conn.execute("""
        INSERT INTO keypresses (
            trial_id, participant_id, key_pressed,
            cursor_row_before, cursor_col_before,
            cursor_row_after, cursor_col_after,
            timestamp_ms, time_since_trial_start_ms, time_since_last_press_ms
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        trial_id, participant_id, key_pressed,
        cursor_row_before, cursor_col_before,
        cursor_row_after, cursor_col_after,
        timestamp_ms, time_since_trial_start_ms, time_since_last_press_ms
    ))
    conn.commit()   # commit immediately — crash-safe
    conn.close()


# ── Reflection functions ─────────────────────────────────────

def save_reflection(participant_id, session_number, imagery_content,
                    perspective, modalities, engagement_score, next_session_goal):
    """
    Save a 3E report card reflection for an MI group participant.

    Args:
        participant_id (str): Who completed the reflection.
        session_number (int): Which session this follows.
        imagery_content (str): Free-text description of imagery.
        perspective (str): First-person / Third-person / Both.
        modalities (str): Comma-separated list (visual, kinesthetic, auditory).
        engagement_score (int): Self-rated engagement 1–5.
        next_session_goal (str): Free-text imagery goal for next session.
    """
    conn = get_connection()
    conn.execute("""
        INSERT INTO reflections (
            participant_id, session_number, imagery_content,
            perspective, modalities, engagement_score, next_session_goal
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (participant_id, session_number, imagery_content,
          perspective, modalities, engagement_score, next_session_goal))
    conn.commit()
    conn.close()
