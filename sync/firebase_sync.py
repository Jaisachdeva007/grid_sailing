# ============================================================
#  GRID-SAILING TASK — Firebase Sync Layer
#
#  Syncs to Firestore every 5 trials OR every 20 seconds,
#  whichever comes first. Runs in a background thread so it
#  never pauses or disrupts the experiment.
#
#  Firestore layout (human-readable, navigable in console):
#
#    devices/
#      ASUS-Juliet/                ← DEVICE_NAME
#        (fields: last_active, last_participant, trials_synced)
#        participants/
#          P012/                   ← participant_id
#            (fields: group, age, gender, handedness, enrolled)
#            s1_practice_b2/       ← session key
#              (fields: started, last_synced, trials_synced)
#              trials/
#                01/  02/  03/ … ← zero-padded trial number
#
#  Idempotent: calling twice for the same trial just overwrites.
# ============================================================

import threading
import socket
import sqlite3

_KEY_DIR = {1: "UP", 2: "DOWN-RIGHT", 3: "DOWN-LEFT"}

_db_client = None


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


# ── Helpers ──────────────────────────────────────────────────

def _session_key(sn, block_type, bn):
    """Human-readable Firestore document ID for a session.
    e.g. s1_practice_b2, s2_pre_test_b1
    """
    return f"s{sn}_{block_type}_b{bn}"


def _trial_key(n):
    """Zero-padded trial number so console sorts 01,02…10,11…20."""
    return f"{n:02d}"


def _fmt_seq(raw):
    """'[1, 2, 3]' → '1 → 2 → 3'. None → ''."""
    if raw is None:
        return ""
    s = str(raw).strip().lstrip("[").rstrip("]")
    parts = [p.strip() for p in s.split(",") if p.strip()]
    return " → ".join(parts)


def _clean_keypresses(kp_list):
    """Strip internal SQLite IDs; keep only researcher-relevant fields."""
    out = []
    for kp in kp_list:
        k = kp.get("key_pressed")
        before = (kp.get("cursor_row_before"), kp.get("cursor_col_before"))
        after  = (kp.get("cursor_row_after"),  kp.get("cursor_col_after"))
        out.append({
            "key":           k,
            "direction":     _KEY_DIR.get(k, ""),
            "row_before":    before[0],
            "col_before":    before[1],
            "row_after":     after[0],
            "col_after":     after[1],
            "out_of_bounds": before == after,
            "t_ms":          kp.get("timestamp_ms"),
            "since_start_ms": kp.get("time_since_trial_start_ms"),
            "iki_ms":        kp.get("time_since_last_press_ms"),
        })
    return out


# ── SQLite fetch ─────────────────────────────────────────────

def _fetch(session_id, up_to_trial):
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
            f"SELECT * FROM keypresses "
            f"WHERE trial_id IN ({ph}) ORDER BY trial_id, keypress_id",
            tids,
        ).fetchall():
            d = dict(kp)
            kp_by_tid.setdefault(d["trial_id"], []).append(d)

    conn.close()
    return sess, part, trials, kp_by_tid


# ── Firestore write ───────────────────────────────────────────

def _push(client, session_id, up_to_trial):
    from config import DEVICE_NAME
    from firebase_admin import firestore as fb

    sess, part, trials, kp_by_tid = _fetch(session_id, up_to_trial)
    if not sess or not trials:
        return

    pid = sess["participant_id"]
    sn  = sess.get("session_number")
    bt  = sess.get("block_type", "")
    bn  = sess.get("block_number")
    s_key = _session_key(sn, bt, bn)

    # ── Device document ───────────────────────────────────────
    device_ref = client.collection("devices").document(DEVICE_NAME)
    device_ref.set({
        "last_active":      fb.SERVER_TIMESTAMP,
        "last_participant": pid,
        "last_session":     s_key,
        "trials_synced":    up_to_trial,
        "hostname":         socket.gethostname(),
    }, merge=True)

    # ── Participant document ───────────────────────────────────
    p_ref = device_ref.collection("participants").document(pid)
    p_ref.set({
        "group":      part.get("group_name", ""),
        "age":        part.get("age"),
        "gender":     part.get("gender", ""),
        "handedness": part.get("handedness", ""),
        "enrolled":   (part.get("created_at") or "")[:10],
    }, merge=True)

    # ── Session document ──────────────────────────────────────
    s_ref = p_ref.collection(s_key).document("_info")
    s_ref.set({
        "session_number": sn,
        "block_type":     bt.replace("_", " ").title(),
        "block_number":   bn,
        "started":        sess.get("started_at", ""),
        "last_synced":    fb.SERVER_TIMESTAMP,
        "trials_synced":  up_to_trial,
    }, merge=True)

    trials_col = p_ref.collection(s_key)

    # ── Trial documents (batched, idempotent) ─────────────────
    batch = client.batch()
    ops   = 0

    for t in trials:
        tid    = t["trial_id"]
        n_mov  = t.get("number_of_moves") or 0
        opt    = t.get("optimal_length")  or 0
        score  = t.get("reward_score")    or 0
        kps    = _clean_keypresses(kp_by_tid.get(tid, []))

        t_ref = trials_col.document(_trial_key(t.get("trial_number", 0)))
        batch.set(t_ref, {
            "grid_type":     t.get("grid_type", ""),
            "start":         f"row {t.get('start_row')}, col {t.get('start_col')}",
            "goal":          f"row {t.get('goal_row')}, col {t.get('goal_col')}",
            "planned":       _fmt_seq(t.get("planned_sequence")),
            "optimal":       _fmt_seq(t.get("optimal_sequence")),
            "moves":         n_mov,
            "optimal_moves": opt,
            "extra_moves":   max(0, n_mov - opt),
            "score":         score,
            "correct":       bool(t.get("is_correct")),
            "reaction_ms":   t.get("reaction_time_ms"),
            "movement_ms":   t.get("movement_time_ms"),
            "imagery_ms":    t.get("imagery_duration_ms"),
            "boundary_hits": t.get("oob_count", 0),
            "keypresses":    kps,
            "recorded":      t.get("created_at", ""),
        })
        ops += 1

        if ops >= 490:
            batch.commit()
            batch = client.batch()
            ops   = 0

    if ops:
        batch.commit()

    print(f"[SYNC] ✓ {len(trials)} trials → Firebase  "
          f"({pid}  ·  {s_key}  ·  up to trial {up_to_trial})")


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
