# ============================================================
#  GRID-SAILING TASK — Firebase Sync Layer
#
#  Syncs local SQLite data to Firebase Firestore after every
#  N trials (default 5) so data is safe even if the hard
#  drive fails mid-session.
#
#  Sync is non-blocking — runs in a daemon thread so it never
#  pauses or disrupts the experiment.
#
#  Firestore structure:
#    devices/{device_id}/
#      _info                        ← device heartbeat
#      participants/{pid}/
#        _info                      ← demographics
#        sessions/{session_id}/
#          _info                    ← session metadata
#          trials/{trial_id}        ← trial + embedded keypresses
#
#  Idempotent: safe to call multiple times for the same
#  trials — Firestore set() with merge just overwrites.
# ============================================================

import threading
import socket
import sqlite3

_db_client = None   # cached Firestore client


def _get_client():
    """
    Lazily initialise Firebase Admin SDK.
    Returns the Firestore client, or None if not configured.
    Prints a clear message on first failure so it's easy to debug.
    """
    global _db_client
    if _db_client is not None:
        return _db_client

    try:
        from config import FIREBASE_CREDENTIALS, DEVICE_ID
        if not FIREBASE_CREDENTIALS:
            return None

        import firebase_admin
        from firebase_admin import credentials, firestore

        if not firebase_admin._apps:
            cred = credentials.Certificate(FIREBASE_CREDENTIALS)
            firebase_admin.initialize_app(cred)

        _db_client = firestore.client()
        print(f"[SYNC] Firebase connected — device: {DEVICE_ID}")
        return _db_client

    except ImportError:
        print("[SYNC] firebase-admin not installed — skipping cloud sync.")
        print("[SYNC] Run:  pip install firebase-admin")
        return None
    except Exception as e:
        print(f"[SYNC] Firebase init failed (non-fatal): {e}")
        return None


# ── SQLite fetch ─────────────────────────────────────────────

def _fetch(session_id, up_to_trial):
    """
    Pull everything we need from the local SQLite DB.
    Returns (session_row, participant_row, trials_list, keypresses_by_trial_id).
    """
    from config import DB_PATH

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    sess_row = conn.execute(
        "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
    ).fetchone()
    if not sess_row:
        conn.close()
        return None, None, [], {}
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

    kp_by_tid = {}
    if trials:
        tids = [t["trial_id"] for t in trials]
        ph   = ",".join("?" * len(tids))
        for kp in conn.execute(
            f"SELECT * FROM keypresses WHERE trial_id IN ({ph}) ORDER BY trial_id, keypress_id",
            tids
        ).fetchall():
            d = dict(kp)
            kp_by_tid.setdefault(d["trial_id"], []).append(d)

    conn.close()
    return sess, part, trials, kp_by_tid


# ── Firestore write ───────────────────────────────────────────

def _push(client, session_id, up_to_trial):
    from config import DEVICE_ID, DEVICE_NAME
    from firebase_admin import firestore

    sess, part, trials, kp_by_tid = _fetch(session_id, up_to_trial)
    if not sess or not trials:
        return

    pid = sess["participant_id"]

    # ── Device heartbeat ──────────────────────────────────────
    device_ref = client.collection("devices").document(DEVICE_ID)
    device_ref.set({
        "device_name":      DEVICE_NAME,
        "hostname":         socket.gethostname(),
        "last_sync":        firestore.SERVER_TIMESTAMP,
        "last_participant": pid,
        "trials_synced":    up_to_trial,
    }, merge=True)

    # ── Participant demographics ───────────────────────────────
    p_ref = device_ref.collection("participants").document(pid)
    p_ref.set({
        "participant_id": pid,
        "group_name":     part.get("group_name", ""),
        "age":            part.get("age"),
        "gender":         part.get("gender", ""),
        "handedness":     part.get("handedness", ""),
        "created_at":     part.get("created_at", ""),
    }, merge=True)

    # ── Session metadata ──────────────────────────────────────
    s_ref = p_ref.collection("sessions").document(str(session_id))
    s_ref.set({
        "session_id":     session_id,
        "session_number": sess.get("session_number"),
        "block_type":     sess.get("block_type", ""),
        "block_number":   sess.get("block_number"),
        "started_at":     sess.get("started_at", ""),
        "synced_at":      firestore.SERVER_TIMESTAMP,
        "trials_synced":  up_to_trial,
    }, merge=True)

    # ── Trials (batched writes, idempotent) ───────────────────
    batch = client.batch()
    ops   = 0

    for trial in trials:
        tid   = trial["trial_id"]
        t_ref = s_ref.collection("trials").document(str(tid))

        batch.set(t_ref, {
            "trial_id":            tid,
            "trial_number":        trial.get("trial_number"),
            "grid_type":           trial.get("grid_type", ""),
            "start":               [trial.get("start_row"), trial.get("start_col")],
            "goal":                [trial.get("goal_row"),  trial.get("goal_col")],
            "planned_sequence":    trial.get("planned_sequence", ""),
            "optimal_sequence":    trial.get("optimal_sequence", ""),
            "optimal_length":      trial.get("optimal_length"),
            "number_of_moves":     trial.get("number_of_moves"),
            "reward_score":        trial.get("reward_score"),
            "is_correct":          bool(trial.get("is_correct")),
            "reaction_time_ms":    trial.get("reaction_time_ms"),
            "movement_time_ms":    trial.get("movement_time_ms"),
            "elapsed_time_s":      trial.get("elapsed_time_s"),
            "imagery_duration_ms": trial.get("imagery_duration_ms"),
            "oob_count":           trial.get("oob_count", 0),
            "created_at":          trial.get("created_at", ""),
            "keypresses":          kp_by_tid.get(tid, []),
        })
        ops += 1

        if ops >= 490:   # Firestore batch limit is 500
            batch.commit()
            batch = client.batch()
            ops   = 0

    if ops:
        batch.commit()

    print(f"[SYNC] ✓ {len(trials)} trials → Firebase  "
          f"({pid} · session {session_id} · up to trial {up_to_trial})")


# ── Public API ────────────────────────────────────────────────

def sync_in_background(session_id, up_to_trial):
    """
    Spawn a daemon thread to push data to Firebase.
    Returns immediately — never blocks the experiment.
    Silently skips if Firebase is not configured.
    """
    def _worker():
        try:
            client = _get_client()
            if client is None:
                return
            _push(client, session_id, up_to_trial)
        except Exception as e:
            print(f"[SYNC] Non-fatal sync error: {e}")

    threading.Thread(target=_worker, daemon=True).start()
