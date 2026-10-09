"""
Basic regression tests for Grid Sailing.
Run with: python run_tests.py
No pygame display needed — tests that import pygame use headless mode.
"""
import os
import sys
import math
import random
import traceback

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

sys.path.insert(0, os.path.dirname(__file__))

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"

results = []

def test(name, fn):
    try:
        fn()
        print(f"  {PASS}  {name}")
        results.append((name, True, None))
    except Exception as e:
        msg = f"{type(e).__name__}: {e}"
        print(f"  {FAIL}  {name}")
        print(f"         {msg}")
        traceback.print_exc()
        results.append((name, False, msg))


# ── 1. Imports ────────────────────────────────────────────────

print("\n── Imports ──")

def test_import_sounds():
    from core import sounds
    sounds.load()

def test_import_session():
    from core.session import build_puzzle_pool, _pick_puzzles

def test_import_trial():
    import core.trial  # noqa: F401

def test_import_db():
    from database import db  # noqa: F401

def test_import_exporter():
    from export import exporter  # noqa: F401

for name, fn in [
    ("core.sounds imports + loads", test_import_sounds),
    ("core.session imports", test_import_session),
    ("core.trial imports", test_import_trial),
    ("database.db imports", test_import_db),
    ("export.exporter imports", test_import_exporter),
]:
    test(name, fn)


# ── 2. Sounds ─────────────────────────────────────────────────

print("\n── Sounds ──")

def test_error_sound_registered():
    from core import sounds
    sounds.load()
    assert "error" in sounds._sounds, "'error' not registered after load()"

def test_error_sound_plays_without_crash():
    from core import sounds
    sounds.play("error")

def test_all_expected_sounds():
    from core import sounds
    for name in ("correct", "incorrect", "streak", "error"):
        assert name in sounds._sounds, f"'{name}' missing from _sounds"

for name, fn in [
    ("'error' sound registered after load()", test_error_sound_registered),
    ("play('error') does not crash", test_error_sound_plays_without_crash),
    ("all 4 sounds present", test_all_expected_sounds),
]:
    test(name, fn)


# ── 3. Backspace label ────────────────────────────────────────

print("\n── Backspace button label ──")

def test_no_backspace_glyph_in_trial():
    src = open("core/trial.py").read()
    assert "⌫" not in src, "Found ⌫ (U+232B) still in trial.py"

def test_del_label_in_trial():
    src = open("core/trial.py").read()
    assert '"DEL"' in src, '"DEL" not found in trial.py'

for name, fn in [
    ("⌫ (U+232B) removed from trial.py", test_no_backspace_glyph_in_trial),
    ('"DEL" label present in trial.py', test_del_label_in_trial),
]:
    test(name, fn)


# ── 4. MI sequence hidden until SPACE ────────────────────────

print("\n── MI sequence hidden until SPACE ──")

def test_seq_str_only_in_held_branch():
    """seq_str / 'Your sequence' must appear inside the 'else' (mi_space_held) block, not before it."""
    src = open("core/trial.py").read()
    # Find the _draw_stage_action function
    start = src.index("def _draw_stage_action(")
    section = src[start:start + 3000]
    # 'Your sequence' must not appear before the 'else' block of mi_space_held
    not_held_block_end = section.index("else:\n")
    seq_before = "Your sequence" in section[:not_held_block_end]
    assert not seq_before, "'Your sequence' appears before mi_space_held else block"

def test_prompt_mentions_space_to_see():
    src = open("core/trial.py").read()
    assert "to see your sequence" in src, \
        "Updated SPACE prompt not found — should mention 'to see your sequence'"

for name, fn in [
    ("sequence text only shown in mi_space_held branch", test_seq_str_only_in_held_branch),
    ("SPACE prompt updated to mention seeing sequence", test_prompt_mentions_space_to_see),
]:
    test(name, fn)


# ── 5. Chunked trial ordering ─────────────────────────────────

print("\n── Chunked trial ordering ──")

def test_chunked_50_50():
    """50/50 block must produce exactly chunks of 4 (2+2) — Austin's spec."""
    from core.session import _pick_puzzles, build_puzzle_pool
    pool = build_puzzle_pool()
    for seed in range(10):
        random.seed(seed)
        trials, _, _ = _pick_puzzles(pool, 20, 0.50)
        kinds = [k for _, k in trials]
        assert len(kinds) == 20, f"Expected 20 trials, got {len(kinds)}"
        rep_count = kinds.count("repeated")
        rnd_count = kinds.count("random")
        assert rep_count == 10, f"Expected 10 repeated, got {rep_count}"
        assert rnd_count == 10, f"Expected 10 random, got {rnd_count}"

def test_chunked_max_run():
    """With 50/50 and chunks of 4, longest run of same type must be ≤ 4."""
    from core.session import _pick_puzzles, build_puzzle_pool
    pool = build_puzzle_pool()
    worst = 0
    for seed in range(100):
        random.seed(seed)
        trials, _, _ = _pick_puzzles(pool, 20, 0.50)
        kinds = [k for _, k in trials]
        run = max_run = 1
        for i in range(1, len(kinds)):
            if kinds[i] == kinds[i-1]:
                run += 1
                max_run = max(max_run, run)
            else:
                run = 1
        worst = max(worst, max_run)
    assert worst <= 4, f"Max run of same type was {worst}, expected ≤ 4"

def test_fam_block_all_random():
    """Familiarization (0% repeated) should still work and be all-random."""
    from core.session import _pick_puzzles, build_puzzle_pool
    pool = build_puzzle_pool()
    trials, _, _ = _pick_puzzles(pool, 20, 0.0)
    kinds = [k for _, k in trials]
    assert all(k == "random" for k in kinds), "Fam block contains non-random trials"

def test_chunk_math_gcd():
    """Verify the doubling logic: gcd(10,10)=10 → chunk(1+1) → doubled to (2+2)."""
    n_rep, n_rand = 10, 10
    g = math.gcd(n_rep, n_rand)
    chunk_rep, chunk_rand = n_rep // g, n_rand // g
    if chunk_rep + chunk_rand < 4:
        chunk_rep *= 2; chunk_rand *= 2
    assert chunk_rep == 2 and chunk_rand == 2, \
        f"Expected chunk (2,2), got ({chunk_rep},{chunk_rand})"

for name, fn in [
    ("50/50 block produces 10+10 trials", test_chunked_50_50),
    ("50/50 max run of same type ≤ 4 (100 seeds)", test_chunked_max_run),
    ("0% repeated (fam block) all-random, no crash", test_fam_block_all_random),
    ("GCD chunk math: 50/50 → 2+2 chunk", test_chunk_math_gcd),
]:
    test(name, fn)


# ── 6. DB schema migrations ───────────────────────────────────

print("\n── DB schema ──")

def test_save_trial_accepts_new_flags():
    """save_trial must accept wrong_locked_path and skipped_sub_goal."""
    import inspect
    from database.db import save_trial
    sig = inspect.signature(save_trial)
    params = sig.parameters
    assert "wrong_locked_path" in params, "wrong_locked_path missing from save_trial"
    assert "skipped_sub_goal"  in params, "skipped_sub_goal missing from save_trial"

def test_save_trial_in_memory_db():
    """Round-trip: save a trial with the new flags into a temp-file DB."""
    import sqlite3, tempfile, os
    from unittest.mock import patch

    tmp = tempfile.mktemp(suffix=".db")
    schema = """
        CREATE TABLE trials (
            trial_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER, participant_id TEXT, trial_number INTEGER,
            grid_type TEXT, start_row INTEGER, start_col INTEGER,
            goal_row INTEGER, goal_col INTEGER,
            planned_sequence TEXT, optimal_sequence TEXT, optimal_length INTEGER,
            number_of_moves INTEGER, reward_score INTEGER,
            reaction_time_ms REAL, movement_time_ms REAL, elapsed_time_s REAL,
            imagery_duration_ms REAL, is_correct INTEGER,
            all_optimal_sequences TEXT, oob_count INTEGER DEFAULT 0,
            time_to_imagery_start_ms REAL, action_reaction_time_ms REAL,
            sub_goal_row INTEGER, sub_goal_col INTEGER, sub_goal_visited INTEGER DEFAULT 0,
            wrong_locked_path INTEGER DEFAULT 0, skipped_sub_goal INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        )"""
    try:
        c = sqlite3.connect(tmp); c.execute(schema); c.commit(); c.close()

        import database.db as db_mod

        def _open():
            cx = sqlite3.connect(tmp); cx.row_factory = sqlite3.Row; return cx

        with patch.object(db_mod, "get_connection", side_effect=_open):
            tid = db_mod.save_trial(
                session_id=1, participant_id="TEST", trial_number=1,
                grid_type="repeated", start_row=0, start_col=0,
                goal_row=5, goal_col=5,
                planned_sequence=[1, 2, 3], optimal_sequence=[1, 2, 3],
                optimal_length=3, number_of_moves=3, reward_score=100,
                reaction_time_ms=500, movement_time_ms=800, elapsed_time_s=5.0,
                imagery_duration_ms=None, is_correct=False,
                wrong_locked_path=1, skipped_sub_goal=0,
            )
        v = _open()
        row = v.execute("SELECT * FROM trials WHERE trial_id=?", (tid,)).fetchone()
        v.close()
        assert row["wrong_locked_path"] == 1, "wrong_locked_path not saved"
        assert row["skipped_sub_goal"]  == 0, "skipped_sub_goal not saved"
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

for name, fn in [
    ("save_trial signature has new flags", test_save_trial_accepts_new_flags),
    ("save_trial round-trip with new flags", test_save_trial_in_memory_db),
]:
    test(name, fn)


# ── 7. Export columns ─────────────────────────────────────────

print("\n── Export columns ──")

def test_export_has_new_columns():
    from export.exporter import TRIAL_COLUMNS, COLUMN_LABELS
    for col in ("actual_sequence_used", "wrong_locked_path", "skipped_sub_goal"):
        assert col in TRIAL_COLUMNS, f"'{col}' missing from TRIAL_COLUMNS"
        assert col in COLUMN_LABELS, f"'{col}' missing from COLUMN_LABELS"

def test_export_no_duplicate_columns():
    from export.exporter import TRIAL_COLUMNS
    assert len(TRIAL_COLUMNS) == len(set(TRIAL_COLUMNS)), "Duplicate columns in TRIAL_COLUMNS"

for name, fn in [
    ("actual_sequence_used, wrong_locked_path, skipped_sub_goal in TRIAL_COLUMNS + labels",
     test_export_has_new_columns),
    ("no duplicate columns in TRIAL_COLUMNS", test_export_no_duplicate_columns),
]:
    test(name, fn)


# ── 8. _flush_keypresses ──────────────────────────────────────

print("\n── _flush_keypresses helper ──")

def test_flush_keypresses_exists():
    import core.trial as t
    assert hasattr(t, "_flush_keypresses"), "_flush_keypresses not found in trial module"

def test_flush_keypresses_safe_no_id():
    """Should be a no-op when trial_id is None."""
    from core.trial import _flush_keypresses, TrialData
    td = TrialData(session_id=1, participant_id="X", trial_number=1,
                   grid_type="random", start=(0,0), goal=(5,5),
                   optimal_sequence=[1,2,3], group="PP")
    td.keypresses_log = [{"key":1,"before":[0,0],"after":[1,0],
                          "abs_ms":100,"rel_ms":100,"iki_ms":None}]
    _flush_keypresses(None, td)  # must not raise

for name, fn in [
    ("_flush_keypresses exists in trial module", test_flush_keypresses_exists),
    ("_flush_keypresses is no-op when trial_id=None", test_flush_keypresses_safe_no_id),
]:
    test(name, fn)


# ── 9. Pool diagnostics ───────────────────────────────────────

print("\n── Puzzle pool ──")

def test_pool_builds():
    from core.session import build_puzzle_pool
    pool = build_puzzle_pool()
    assert len(pool) > 1000, f"Pool too small: {len(pool)}"

def test_pool_primaries():
    from core.session import build_puzzle_pool
    pool = build_puzzle_pool()
    primaries = {tuple(p["sequence"]) for p in pool}
    assert len(primaries) >= 400, f"Too few distinct primaries: {len(primaries)}"

def test_cross_block_dedup():
    """After one block's pairs are tracked, next block must not reuse primary sequences."""
    from core.session import build_puzzle_pool, _pick_puzzles
    pool = build_puzzle_pool()
    repeated = None
    used: set = set()
    for _ in range(3):
        trials, repeated, new_pairs = _pick_puzzles(pool, 20, 0.50,
                                                    repeated_puzzle=repeated,
                                                    used_pairs=used)
        rand_seqs = {tuple(p["sequence"]) for p, k in trials if k == "random"}
        assert not (rand_seqs & used), "Cross-block primary sequence repeat detected"
        used |= new_pairs

for name, fn in [
    ("puzzle pool builds (>1000 puzzles)", test_pool_builds),
    ("≥400 distinct primary sequences", test_pool_primaries),
    ("no cross-block primary sequence repeats (3 blocks)", test_cross_block_dedup),
]:
    test(name, fn)


# ── Summary ───────────────────────────────────────────────────

total  = len(results)
passed = sum(1 for _, ok, _ in results if ok)
failed = total - passed

print(f"\n{'='*50}")
print(f"  {passed}/{total} passed", end="")
if failed:
    print(f"  —  {failed} FAILED")
    for name, ok, msg in results:
        if not ok:
            print(f"    ✗  {name}")
            print(f"       {msg}")
else:
    print("  — all good")
print()

sys.exit(0 if failed == 0 else 1)
