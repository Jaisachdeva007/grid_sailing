# ============================================================
#  GRID-SAILING TASK — CSV Exporter
#
#  Exports SQLite data to clean CSV files Juliet can open
#  directly in R or Excel.
#
#  Two export modes:
#    1. Single participant  →  exports/{participant_id}_data.csv
#    2. All participants    →  exports/all_participants_data.csv
#
#  Each row in the export = one key press event, joined with
#  its trial and participant metadata for full context.
# ============================================================

import csv
import os
import sqlite3
from datetime import datetime
from config import DB_PATH, EXPORT_DIR


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_export_dir():
    os.makedirs(EXPORT_DIR, exist_ok=True)


# ── Column definitions ───────────────────────────────────────
# These match the REB Appendix G data fields exactly,
# with additional detail columns for keypresses.

TRIAL_COLUMNS = [
    "participant_id",
    "age",
    "gender",
    "handedness",
    "group_name",
    "session_number",
    "block_type",
    "block_number",
    "trial_number",
    "grid_type",
    "start_row",
    "start_col",
    "goal_row",
    "goal_col",
    "planned_sequence",
    "optimal_sequence",
    "optimal_length",
    "number_of_moves",
    "reward_score",
    "reaction_time_ms",
    "movement_time_ms",
    "elapsed_time_s",
    "imagery_duration_ms",
    "is_correct",
    "trial_created_at",
]

KEYPRESS_COLUMNS = [
    "keypress_id",
    "key_pressed",
    "cursor_row_before",
    "cursor_col_before",
    "cursor_row_after",
    "cursor_col_after",
    "timestamp_ms",
    "time_since_trial_start_ms",
    "time_since_last_press_ms",
]

ALL_COLUMNS = TRIAL_COLUMNS + KEYPRESS_COLUMNS


def _fetch_rows(participant_id=None):
    """
    Fetch all export rows from the database.
    Joins participants + sessions + trials + keypresses.

    If participant_id is provided, filters to that participant only.
    Returns a list of dicts, one per key press event.
    Trials with no key press events (e.g. MI/CTRL) are included
    as a single row with keypress columns set to None.
    """
    conn = _get_conn()

    pid_filter = "AND p.participant_id = ?" if participant_id else ""
    params     = (participant_id,) if participant_id else ()

    # LEFT JOIN keypresses so trials without key presses still appear
    query = f"""
        SELECT
            p.participant_id,
            p.age,
            p.gender,
            p.handedness,
            p.group_name,
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
            t.reaction_time_ms,
            t.movement_time_ms,
            t.elapsed_time_s,
            t.imagery_duration_ms,
            t.is_correct,
            t.created_at            AS trial_created_at,
            k.keypress_id,
            k.key_pressed,
            k.cursor_row_before,
            k.cursor_col_before,
            k.cursor_row_after,
            k.cursor_col_after,
            k.timestamp_ms,
            k.time_since_trial_start_ms,
            k.time_since_last_press_ms
        FROM participants p
        JOIN sessions s  ON p.participant_id = s.participant_id
        JOIN trials   t  ON s.session_id     = t.session_id
        LEFT JOIN keypresses k ON t.trial_id = k.trial_id
        WHERE 1=1 {pid_filter}
        ORDER BY
            p.participant_id,
            s.session_number,
            s.block_number,
            t.trial_number,
            k.keypress_id
    """

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _write_csv(rows, filepath):
    """Write a list of row dicts to a CSV file."""
    if not rows:
        print(f"[EXPORT] No data to export.")
        return

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ALL_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"[EXPORT] Saved {len(rows)} rows → {filepath}")


def export_participant(participant_id: str) -> str:
    """
    Export all data for one participant to a CSV file.

    Args:
        participant_id (str): e.g. "P001"

    Returns:
        str: Path to the exported file.
    """
    _ensure_export_dir()
    rows     = _fetch_rows(participant_id)
    filename = f"{participant_id}_data.csv"
    filepath = os.path.join(EXPORT_DIR, filename)
    _write_csv(rows, filepath)
    return filepath


def export_all() -> str:
    """
    Export all participants' data to a single CSV file.

    Returns:
        str: Path to the exported file.
    """
    _ensure_export_dir()
    rows     = _fetch_rows()
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"all_participants_{ts}.csv"
    filepath = os.path.join(EXPORT_DIR, filename)
    _write_csv(rows, filepath)
    return filepath


def export_summary() -> str:
    """
    Export a per-trial summary (no keypress rows) — one row per trial.
    Useful for quick analysis in R without the keypress-level detail.

    Returns:
        str: Path to the exported file.
    """
    _ensure_export_dir()
    conn = _get_conn()

    rows = conn.execute("""
        SELECT
            p.participant_id,
            p.age,
            p.gender,
            p.handedness,
            p.group_name,
            s.session_number,
            s.block_type,
            s.block_number,
            t.trial_number,
            t.grid_type,
            t.start_row, t.start_col,
            t.goal_row,  t.goal_col,
            t.planned_sequence,
            t.optimal_sequence,
            t.optimal_length,
            t.number_of_moves,
            t.reward_score,
            t.reaction_time_ms,
            t.movement_time_ms,
            t.elapsed_time_s,
            t.imagery_duration_ms,
            t.is_correct,
            t.created_at AS trial_created_at
        FROM participants p
        JOIN sessions s ON p.participant_id = s.participant_id
        JOIN trials   t ON s.session_id     = t.session_id
        ORDER BY p.participant_id, s.session_number, s.block_number, t.trial_number
    """).fetchall()
    conn.close()

    trial_rows = [dict(r) for r in rows]
    ts         = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename   = f"trial_summary_{ts}.csv"
    filepath   = os.path.join(EXPORT_DIR, filename)

    if trial_rows:
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=TRIAL_COLUMNS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(trial_rows)
        print(f"[EXPORT] Trial summary → {filepath}  ({len(trial_rows)} trials)")
    else:
        print("[EXPORT] No trial data found.")

    return filepath
