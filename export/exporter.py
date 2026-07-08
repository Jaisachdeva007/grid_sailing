# ============================================================
#  GRID-SAILING TASK — CSV Exporter
#
#  Exports SQLite data to clean CSV files for analysis in R or Excel.
#
#  Export modes:
#    export_participant(pid)  → {pid}_data.csv          (per-keypress)
#    export_all()             → all_participants_{ts}.csv (per-keypress)
#    export_summary()         → trial_summary_{ts}.csv   (per-trial)
#    export_reflections()     → reflections_{ts}.csv     (MI reflections)
# ============================================================

import csv
import json
import os
import sqlite3
from datetime import datetime
from config import DB_PATH, EXPORT_DIR

_KEY_LABELS = {1: "UP", 2: "DOWN-RIGHT", 3: "DOWN-LEFT"}


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_export_dir():
    os.makedirs(EXPORT_DIR, exist_ok=True)


# ── Formatting helpers ───────────────────────────────────────

def _clean_sequence(val) -> str:
    """'[1, 2, 3]' or list → '1,2,3'. None → ''."""
    if val is None:
        return ""
    if isinstance(val, (list, tuple)):
        return ",".join(str(x) for x in val)
    s = str(val).strip().lstrip("[").rstrip("]")
    return ",".join(p.strip() for p in s.split(",") if p.strip())


def _clean_all_optimal(val) -> str:
    """JSON '[[1,2,3],[1,3,2]]' → '1,2,3|1,3,2' (pipe = alternative path). None → ''."""
    if val is None:
        return ""
    try:
        seqs = json.loads(val)
        return "|".join(",".join(str(k) for k in seq) for seq in seqs)
    except Exception:
        return str(val)


def _ms_to_s(val):
    """Milliseconds → seconds (4 dp). None → ''."""
    return "" if val is None else round(val / 1000, 4)


# ── Column definitions ───────────────────────────────────────

TRIAL_COLUMNS = [
    # Participant demographics
    "participant_id",
    "age",
    "gender",
    "handedness",
    "group_name",
    # Session context
    "session_id",
    "session_number",
    "block_type",
    "block_number",
    "session_started_at",
    "session_completed_at",
    # Trial identity
    "trial_id",
    "trial_number",
    "grid_type",
    "start_row",
    "start_col",
    "goal_row",
    "goal_col",
    # Sequences (human-readable: '1,2,3'; alternative paths separated by '|')
    "planned_sequence",
    "optimal_sequence",
    "all_optimal_sequences",
    "optimal_length",
    # Performance
    "number_of_moves",
    "extra_moves",        # number_of_moves - optimal_length
    "is_optimal",         # TRUE if correct and no extra moves
    "oob_count",          # moves that hit boundary (cursor stayed)
    "reward_score",
    "penalty_pts",        # extra_moves * 5 when correct, else 0
    "cumulative_score",   # running total for this participant
    # Timing
    "reaction_time_ms",
    "reaction_time_s",
    "movement_time_ms",
    "movement_time_s",
    "elapsed_time_s",
    "imagery_duration_ms",
    "imagery_duration_s",
    # Outcome
    "is_correct",
    "trial_created_at",
]

KEYPRESS_COLUMNS = [
    "keypress_id",
    "key_pressed",            # 1 / 2 / 3
    "key_direction",          # UP / DOWN-RIGHT / DOWN-LEFT
    "cursor_row_before",
    "cursor_col_before",
    "cursor_row_after",
    "cursor_col_after",
    "was_out_of_bounds",      # TRUE if cursor didn't move (boundary hit)
    "timestamp_ms",
    "time_since_trial_start_ms",
    "time_since_last_press_ms",
]

ALL_COLUMNS = TRIAL_COLUMNS + KEYPRESS_COLUMNS

REFLECTION_COLUMNS = [
    "participant_id",
    "session_number",
    "imagery_content",
    "perspective",
    "modalities",
    "engagement_score",
    "next_session_goal",
    "created_at",
]

# ── Row post-processing ──────────────────────────────────────

_NULLABLE_FIELDS = (
    "reaction_time_ms", "movement_time_ms", "elapsed_time_s",
    "imagery_duration_ms", "number_of_moves", "reward_score",
    "oob_count", "keypress_id", "key_pressed", "timestamp_ms",
    "time_since_trial_start_ms", "time_since_last_press_ms",
    "session_completed_at",
)


def _add_derived(row: dict, cumulative_score: int) -> dict:
    """Enrich a raw DB row dict with derived and formatted columns."""
    is_corr = bool(row.get("is_correct"))
    n_moves = row.get("number_of_moves")
    opt_len = row.get("optimal_length") or 0

    # Extra moves, optimality, penalty
    if n_moves is not None:
        extra = n_moves - opt_len
        row["extra_moves"] = extra
        row["is_optimal"]  = "TRUE" if (is_corr and extra == 0) else "FALSE"
        row["penalty_pts"] = abs(extra) * 5 if is_corr else 0
    else:
        row["extra_moves"] = ""
        row["is_optimal"]  = ""
        row["penalty_pts"] = ""

    row["cumulative_score"] = cumulative_score

    # Clean sequence strings
    row["planned_sequence"]      = _clean_sequence(row.get("planned_sequence"))
    row["optimal_sequence"]      = _clean_sequence(row.get("optimal_sequence"))
    row["all_optimal_sequences"] = _clean_all_optimal(row.get("all_optimal_sequences"))

    # Timing in seconds
    row["reaction_time_s"]    = _ms_to_s(row.get("reaction_time_ms"))
    row["movement_time_s"]    = _ms_to_s(row.get("movement_time_ms"))
    row["imagery_duration_s"] = _ms_to_s(row.get("imagery_duration_ms"))

    # Boolean as text
    row["is_correct"] = "TRUE" if is_corr else "FALSE"

    # Keypress-level derived columns
    kp = row.get("key_pressed")
    if kp is not None:
        row["key_direction"] = _KEY_LABELS.get(kp, "")
        before = (row.get("cursor_row_before"), row.get("cursor_col_before"))
        after  = (row.get("cursor_row_after"),  row.get("cursor_col_after"))
        row["was_out_of_bounds"] = "TRUE" if before == after else "FALSE"
    else:
        row["key_direction"]     = ""
        row["was_out_of_bounds"] = ""

    # Convert remaining NULLs to empty string
    for f in _NULLABLE_FIELDS:
        if row.get(f) is None:
            row[f] = ""

    return row


# ── Fetch functions ──────────────────────────────────────────

def _fetch_rows(participant_id=None) -> list:
    """
    Fetch per-keypress rows (one row per key press; trials with no
    keypresses appear once with keypress columns blank).
    Adds all derived columns and cumulative score per participant.
    """
    conn       = _get_conn()
    pid_filter = "AND p.participant_id = ?" if participant_id else ""
    params     = (participant_id,) if participant_id else ()

    query = f"""
        SELECT
            p.participant_id, p.age, p.gender, p.handedness, p.group_name,
            s.session_id, s.session_number, s.block_type, s.block_number,
            s.started_at   AS session_started_at,
            s.completed_at AS session_completed_at,
            t.trial_id, t.trial_number, t.grid_type,
            t.start_row, t.start_col, t.goal_row, t.goal_col,
            t.planned_sequence, t.optimal_sequence, t.all_optimal_sequences,
            t.optimal_length,
            t.number_of_moves,
            t.reward_score,
            t.reaction_time_ms, t.movement_time_ms, t.elapsed_time_s,
            t.imagery_duration_ms,
            t.is_correct,
            COALESCE(t.oob_count, 0) AS oob_count,
            t.created_at             AS trial_created_at,
            k.keypress_id,
            k.key_pressed,
            k.cursor_row_before, k.cursor_col_before,
            k.cursor_row_after,  k.cursor_col_after,
            k.timestamp_ms,
            k.time_since_trial_start_ms,
            k.time_since_last_press_ms
        FROM participants p
        JOIN sessions     s  ON p.participant_id = s.participant_id
        JOIN trials       t  ON s.session_id     = t.session_id
        LEFT JOIN keypresses k ON t.trial_id = k.trial_id
        WHERE 1=1 {pid_filter}
        ORDER BY
            p.participant_id,
            s.session_number,
            s.block_number,
            t.trial_number,
            k.keypress_id
    """
    raw = conn.execute(query, params).fetchall()
    conn.close()

    cum_by_pid      = {}
    last_tid_by_pid = {}
    rows            = []

    for r in raw:
        d   = dict(r)
        pid = d["participant_id"]
        tid = d["trial_id"]

        # Add reward_score to running total only once per trial
        if last_tid_by_pid.get(pid) != tid:
            cum_by_pid[pid] = cum_by_pid.get(pid, 0) + (d.get("reward_score") or 0)
            last_tid_by_pid[pid] = tid

        rows.append(_add_derived(d, cum_by_pid[pid]))

    return rows


def _fetch_summary_rows(participant_id=None) -> list:
    """
    Fetch per-trial rows (one row per trial, no keypress detail).
    Adds all derived columns and cumulative score per participant.
    """
    conn       = _get_conn()
    pid_filter = "AND p.participant_id = ?" if participant_id else ""
    params     = (participant_id,) if participant_id else ()

    query = f"""
        SELECT
            p.participant_id, p.age, p.gender, p.handedness, p.group_name,
            s.session_id, s.session_number, s.block_type, s.block_number,
            s.started_at   AS session_started_at,
            s.completed_at AS session_completed_at,
            t.trial_id, t.trial_number, t.grid_type,
            t.start_row, t.start_col, t.goal_row, t.goal_col,
            t.planned_sequence, t.optimal_sequence, t.all_optimal_sequences,
            t.optimal_length,
            t.number_of_moves,
            t.reward_score,
            t.reaction_time_ms, t.movement_time_ms, t.elapsed_time_s,
            t.imagery_duration_ms,
            t.is_correct,
            COALESCE(t.oob_count, 0) AS oob_count,
            t.created_at             AS trial_created_at
        FROM participants p
        JOIN sessions s ON p.participant_id = s.participant_id
        JOIN trials   t ON s.session_id     = t.session_id
        WHERE 1=1 {pid_filter}
        ORDER BY p.participant_id, s.session_number, s.block_number, t.trial_number
    """
    raw = conn.execute(query, params).fetchall()
    conn.close()

    cum_by_pid = {}
    rows       = []

    for r in raw:
        d   = dict(r)
        pid = d["participant_id"]
        cum_by_pid[pid] = cum_by_pid.get(pid, 0) + (d.get("reward_score") or 0)
        rows.append(_add_derived(d, cum_by_pid[pid]))

    return rows


# ── CSV writer ───────────────────────────────────────────────

def _write_csv(rows: list, filepath: str, fieldnames: list) -> bool:
    if not rows:
        print("[EXPORT] No data to export.")
        return False
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"[EXPORT] {len(rows)} rows → {filepath}")
    return True


# ── Public export functions ──────────────────────────────────

def export_participant(participant_id: str) -> str:
    """Export per-keypress data for one participant."""
    _ensure_export_dir()
    rows     = _fetch_rows(participant_id)
    filepath = os.path.join(EXPORT_DIR, f"{participant_id}_data.csv")
    _write_csv(rows, filepath, ALL_COLUMNS)
    return filepath


def export_all() -> str:
    """Export per-keypress data for all participants."""
    _ensure_export_dir()
    rows     = _fetch_rows()
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(EXPORT_DIR, f"all_participants_{ts}.csv")
    _write_csv(rows, filepath, ALL_COLUMNS)
    return filepath


def export_summary() -> str:
    """Export one row per trial for all participants (no keypress detail)."""
    _ensure_export_dir()
    rows     = _fetch_summary_rows()
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(EXPORT_DIR, f"trial_summary_{ts}.csv")
    _write_csv(rows, filepath, TRIAL_COLUMNS)
    return filepath


def export_reflections() -> str:
    """Export MI group 3E reflections to a separate CSV."""
    _ensure_export_dir()
    conn = _get_conn()
    raw  = conn.execute("""
        SELECT participant_id, session_number, imagery_content,
               perspective, modalities, engagement_score,
               next_session_goal, created_at
        FROM reflections
        ORDER BY participant_id, session_number
    """).fetchall()
    conn.close()
    rows     = [dict(r) for r in raw]
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(EXPORT_DIR, f"reflections_{ts}.csv")
    _write_csv(rows, filepath, REFLECTION_COLUMNS)
    return filepath
