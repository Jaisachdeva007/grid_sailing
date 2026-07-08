# ============================================================
#  GRID-SAILING TASK — Firebase Cloud Sync Layer
#
#  *** Juliet does NOT need to edit this file. ***
#
#  This file automatically backs up trial data to Firebase
#  (a Google cloud database) in the background while the
#  experiment runs. Data is never lost even if the hard drive fails.
#
#  When does it sync?
#    - Automatically every 5 trials during the experiment
#    - Automatically every 20 seconds (even if 5 trials haven't happened)
#    - Immediately when a session ends or is paused
#    - Manually via the "Sync All" button in the Data Viewer
#
#  The sync always runs in a background thread — the participant
#  never sees any pause or delay because of it.
#
#  What data goes to Firebase?
#    - Same fields as the CSV export (reward_score, is_correct,
#      number_of_moves, timing fields, sequences, etc.)
#    - Each trial is stored as its own document so it's easy to
#      browse in the Firebase Console at console.firebase.google.com
#
#  Firebase structure (what you see in the console):
#    devices/
#      ASUS-Juliet/                ← this machine (from local_config.py)
#        participants/
#          P001/                   ← participant ID
#            s1_practice_b2/       ← session 1, practice block 2
#              _info               ← session start/end times
#              01/  02/  03/ …     ← one document per trial
#
#  Writing the same trial twice is safe — it just overwrites with
#  the latest values. You can re-sync at any time without duplicating data.
# ============================================================

import threading
import socket
import sqlite3
import json

_KEY_LABELS = {1: "UP", 2: "DOWN-RIGHT", 3: "DOWN-LEFT"}
_db_client  = None


def _get_client():
    """Lazily init Firebase. Returns Firestore client or None."""
    global _db_client
    if _db_client is not None:
        return _db_client
    try:
        from config import FIREBASE_CREDENTIALS, DEVICE_NAME
        if not FIREBASE_CREDENTIALS:
            return None
        import firebase_admin
        from firebase_admin import credentials, firestore
        if not firebase_admin._apps:
            cred = credentials.Certificate(FIREBASE_CREDENTIALS)
            firebase_admin.initialize_app(cred)
        _db_client = firestore.client()
        print(f"[SYNC] Firebase connected  ·  device: {DEVICE_NAME}")
        return _db_client
    except ImportError:
        print("[SYNC] firebase-admin not installed — run: pip install firebase-admin")
        return None
    except Exception as e:
        print(f"[SYNC] Firebase init failed (non-fatal): {e}")
        return None


# ── Format helpers (match exporter.py exactly) ────────────────

def _clean_sequence(val) -> str:
    """'[1, 2, 3]' → '1,2,3'. None → ''."""
    if val is None:
        return ""
    if isinstance(val, (list, tuple)):
        return ",".join(str(x) for x in val)
    s = str(val).strip().lstrip("[").rstrip("]")
    return ",".join(p.strip() for p in s.split(",") if p.strip())


def _clean_all_optimal(val) -> str:
    """JSON '[[1,2,3],[1,3,2]]' → '1,2,3|1,3,2'. None → ''."""
    if val is None:
        return ""
    try:
        seqs = json.loads(val)
        return "|".join(",".join(str(k) for k in seq) for seq in seqs)
    except Exception:
        return str(val)


def _ms_to_s(val):
    """ms → seconds (4 dp). None → None."""
    return None if val is None else round(val / 1000, 4)


def _bool_str(val) -> str:
    return "TRUE" if val else "FALSE"


# ── Key helpers ──────────────────────────────────────────────

def _session_key(sn, block_type, bn):
    """e.g. s1_practice_b2, s2_pre_test_b1"""
    return f"s{sn}_{block_type}_b{bn}"


def _trial_key(n):
    """Zero-padded so Firebase console sorts 01, 02 … 10, 11 … 20."""
    return f"{n:02d}"


# ── Keypress formatter ───────────────────────────────────────

def _format_keypresses(tid, kp_by_tid: dict) -> list:
    """Format keypresses with exact CSV column names (KEYPRESS_COLUMNS)."""
    out = []
    for kp in kp_by_tid.get(tid, []):
        k      = kp.get("key_pressed")
        before = (kp.get("cursor_row_before"), kp.get("cursor_col_before"))
        after  = (kp.get("cursor_row_after"),  kp.get("cursor_col_after"))
        out.append({
            "keypress_id":               kp.get("keypress_id"),
            "key_pressed":               k,
            "key_direction":             _KEY_LABELS.get(k, ""),
            "cursor_row_before":         before[0],
            "cursor_col_before":         before[1],
            "cursor_row_after":          after[0],
            "cursor_col_after":          after[1],
            "was_out_of_bounds":         _bool_str(before == after),
            "timestamp_ms":              kp.get("timestamp_ms"),
            "time_since_trial_start_ms": kp.get("time_since_trial_start_ms"),
            "time_since_last_press_ms":  kp.get("time_since_last_press_ms"),
        })
    return out


# ── Trial document builder ───────────────────────────────────

def _build_trial_doc(t: dict, sess: dict, part: dict,
                     cum_score: int, kp_by_tid: dict) -> tuple:
    """
    Build a Firestore trial document with exact CSV column names.
    Returns (doc_dict, updated_cumulative_score).
    """
    is_corr = bool(t.get("is_correct"))
    n_moves = t.get("number_of_moves")
    opt_len = t.get("optimal_length") or 0
    score   = t.get("reward_score") or 0

    if n_moves is not None:
        extra   = n_moves - opt_len
        is_opt  = _bool_str(is_corr and extra == 0)
        penalty = abs(extra) * 5 if is_corr else 0
    else:
        extra   = None
        is_opt  = ""
        penalty = None

    cum_score += score
    tid = t.get("trial_id")

    doc = {
        # Participant demographics
        "participant_id":        t.get("participant_id", ""),
        "age":                   part.get("age"),
        "gender":                part.get("gender", ""),
        "handedness":            part.get("handedness", ""),
        "group_name":            part.get("group_name", ""),
        # Session context
        "session_id":            sess.get("session_id"),
        "session_number":        sess.get("session_number"),
        "block_type":            sess.get("block_type", ""),
        "block_number":          sess.get("block_number"),
        "session_started_at":    sess.get("started_at", ""),
        "session_completed_at":  sess.get("completed_at"),
        # Trial identity
        "trial_id":              tid,
        "trial_number":          t.get("trial_number"),
        "grid_type":             t.get("grid_type", ""),
        "start_row":             t.get("start_row"),
        "start_col":             t.get("start_col"),
        "goal_row":              t.get("goal_row"),
        "goal_col":              t.get("goal_col"),
        # Sequences (comma-separated; alternative paths pipe-separated)
        "planned_sequence":      _clean_sequence(t.get("planned_sequence")),
        "optimal_sequence":      _clean_sequence(t.get("optimal_sequence")),
        "all_optimal_sequences": _clean_all_optimal(t.get("all_optimal_sequences")),
        "optimal_length":        opt_len,
        # Performance
        "number_of_moves":       n_moves,
        "extra_moves":           extra,
        "is_optimal":            is_opt,
        "oob_count":             t.get("oob_count") or 0,
        "reward_score":          t.get("reward_score"),
        "penalty_pts":           penalty,
        "cumulative_score":      cum_score,
        # Timing (both ms and s to match CSV)
        "reaction_time_ms":      t.get("reaction_time_ms"),
        "reaction_time_s":       _ms_to_s(t.get("reaction_time_ms")),
        "movement_time_ms":      t.get("movement_time_ms"),
        "movement_time_s":       _ms_to_s(t.get("movement_time_ms")),
        "elapsed_time_s":        t.get("elapsed_time_s"),
        "imagery_duration_ms":   t.get("imagery_duration_ms"),
        "imagery_duration_s":    _ms_to_s(t.get("imagery_duration_ms")),
        # Outcome
        "is_correct":            _bool_str(is_corr),
        "trial_created_at":      t.get("created_at", ""),
        # Keypresses embedded array (CSV KEYPRESS_COLUMNS per entry)
        "keypresses":            _format_keypresses(tid, kp_by_tid),
    }
    return doc, cum_score


# ── SQLite fetch: single session ─────────────────────────────

def _fetch(session_id, up_to_trial):
    from config import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    sess_row = conn.execute(
        "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
    ).fetchone()
    if not sess_row:
        conn.close()
        return None, None, [], {}, 0
    sess = dict(sess_row)

    part = dict(conn.execute(
        "SELECT * FROM participants WHERE participant_id = ?",
        (sess["participant_id"],)
    ).fetchone() or {})

    trials = [dict(r) for r in conn.execute("""
        SELECT * FROM trials
        WHERE session_id = ? AND trial_number <= ?
        ORDER BY trial_number
    """, (session_id, up_to_trial)).fetchall()]

    # Cumulative score from all trials recorded before the first trial in this batch
    prior_cum = 0
    if trials:
        first_tid = trials[0]["trial_id"]
        row = conn.execute(
            "SELECT COALESCE(SUM(reward_score), 0) FROM trials "
            "WHERE participant_id = ? AND trial_id < ?",
            (sess["participant_id"], first_tid)
        ).fetchone()
        prior_cum = row[0] or 0

    kp_by_tid = {}
    if trials:
        tids = [t["trial_id"] for t in trials]
        ph   = ",".join("?" * len(tids))
        for kp in conn.execute(
            f"SELECT * FROM keypresses "
            f"WHERE trial_id IN ({ph}) ORDER BY trial_id, keypress_id",
            tids,
        ).fetchall():
            d = dict(kp)
            kp_by_tid.setdefault(d["trial_id"], []).append(d)

    conn.close()
    return sess, part, trials, kp_by_tid, prior_cum


# ── SQLite fetch: everything (for backfill) ──────────────────

def _fetch_all():
    """Return all data needed for a full backfill sync."""
    from config import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    participants = {
        dict(r)["participant_id"]: dict(r)
        for r in conn.execute("SELECT * FROM participants").fetchall()
    }

    sessions = [dict(r) for r in conn.execute(
        "SELECT * FROM sessions "
        "ORDER BY participant_id, session_number, block_number, session_id"
    ).fetchall()]

    trial_by_sid = {}
    for t in conn.execute(
        "SELECT * FROM trials ORDER BY participant_id, trial_id"
    ).fetchall():
        d = dict(t)
        trial_by_sid.setdefault(d["session_id"], []).append(d)

    kp_by_tid = {}
    for kp in conn.execute(
        "SELECT * FROM keypresses ORDER BY trial_id, keypress_id"
    ).fetchall():
        d = dict(kp)
        kp_by_tid.setdefault(d["trial_id"], []).append(d)

    conn.close()
    return participants, sessions, trial_by_sid, kp_by_tid


# ── Firestore write: one session's trials ────────────────────

def _push_session(client, p_ref, sess, part, trials, kp_by_tid, prior_cum):
    """
    Write _info + all trial documents for one session.
    Returns the cumulative score after all trials in this session.
    """
    from firebase_admin import firestore as fb

    sn    = sess.get("session_number")
    bt    = sess.get("block_type", "")
    bn    = sess.get("block_number")
    s_key = _session_key(sn, bt, bn)

    p_ref.collection(s_key).document("_info").set({
        "session_number":  sn,
        "block_type":      bt.replace("_", " ").title(),
        "block_number":    bn,
        "started":         sess.get("started_at", ""),
        "completed":       sess.get("completed_at"),
        "last_synced":     fb.SERVER_TIMESTAMP,
        "trials_synced":   len(trials),
    }, merge=True)

    trials_col = p_ref.collection(s_key)
    batch      = client.batch()
    ops        = 0
    cum        = prior_cum

    for t in trials:
        doc, cum = _build_trial_doc(t, sess, part, cum, kp_by_tid)
        t_ref = trials_col.document(_trial_key(t.get("trial_number", 0)))
        batch.set(t_ref, doc)
        ops += 1
        if ops >= 490:
            batch.commit()
            batch = client.batch()
            ops   = 0

    if ops:
        batch.commit()

    return cum


# ── Firestore write: incremental per-session sync ─────────────

def _push(client, session_id, up_to_trial):
    from config import DEVICE_NAME
    from firebase_admin import firestore as fb

    sess, part, trials, kp_by_tid, prior_cum = _fetch(session_id, up_to_trial)
    if not sess or not trials:
        return

    pid   = sess["participant_id"]
    sn    = sess.get("session_number")
    bt    = sess.get("block_type", "")
    bn    = sess.get("block_number")
    s_key = _session_key(sn, bt, bn)

    device_ref = client.collection("devices").document(DEVICE_NAME)
    device_ref.set({
        "last_active":      fb.SERVER_TIMESTAMP,
        "last_participant": pid,
        "last_session":     s_key,
        "trials_synced":    up_to_trial,
        "hostname":         socket.gethostname(),
    }, merge=True)

    p_ref = device_ref.collection("participants").document(pid)
    p_ref.set({
        "participant_id": pid,
        "group_name":     part.get("group_name", ""),
        "age":            part.get("age"),
        "gender":         part.get("gender", ""),
        "handedness":     part.get("handedness", ""),
        "enrolled":       (part.get("created_at") or "")[:10],
    }, merge=True)

    _push_session(client, p_ref, sess, part, trials, kp_by_tid, prior_cum)

    print(f"[SYNC] + {len(trials)} trials -> Firebase  "
          f"({pid}  .  {s_key}  .  up to trial {up_to_trial})")


# ── Firestore write: full backfill ────────────────────────────

def _push_all(client):
    from config import DEVICE_NAME
    from firebase_admin import firestore as fb

    participants, sessions, trial_by_sid, kp_by_tid = _fetch_all()

    if not sessions:
        print("[SYNC] No data to backfill.")
        return

    device_ref = client.collection("devices").document(DEVICE_NAME)
    device_ref.set({
        "last_active": fb.SERVER_TIMESTAMP,
        "hostname":    socket.gethostname(),
    }, merge=True)

    cum_by_pid   = {}
    total_trials = 0

    for sess in sessions:
        pid    = sess["participant_id"]
        part   = participants.get(pid, {})
        trials = trial_by_sid.get(sess["session_id"], [])
        if not trials:
            continue

        p_ref = device_ref.collection("participants").document(pid)
        p_ref.set({
            "participant_id": pid,
            "group_name":     part.get("group_name", ""),
            "age":            part.get("age"),
            "gender":         part.get("gender", ""),
            "handedness":     part.get("handedness", ""),
            "enrolled":       (part.get("created_at") or "")[:10],
        }, merge=True)

        prior_cum = cum_by_pid.get(pid, 0)
        new_cum   = _push_session(client, p_ref, sess, part,
                                  trials, kp_by_tid, prior_cum)
        cum_by_pid[pid] = new_cum
        total_trials   += len(trials)

    n_pids = len([p for p in cum_by_pid])
    device_ref.set({"trials_synced": total_trials}, merge=True)
    print(f"[SYNC] Backfill complete -- "
          f"{n_pids} participant(s), {total_trials} trial(s) pushed to Firebase")


# ── Public API ────────────────────────────────────────────────

def sync_in_background(session_id, up_to_trial):
    """Non-blocking sync — spawns a daemon thread and returns immediately."""
    def _worker():
        try:
            client = _get_client()
            if client:
                _push(client, session_id, up_to_trial)
        except Exception as e:
            print(f"[SYNC] Non-fatal sync error: {e}")
    threading.Thread(target=_worker, daemon=True).start()


def sync_all_in_background():
    """Backfill ALL historical SQLite data to Firebase. Non-blocking."""
    def _worker():
        try:
            client = _get_client()
            if client:
                _push_all(client)
        except Exception as e:
            print(f"[SYNC] Non-fatal backfill error: {e}")
    threading.Thread(target=_worker, daemon=True).start()
