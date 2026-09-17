"""
Quick diagnostic: shows pool size and simulates block selection to verify no repeats.
Run from the grid_sailing folder:
    python check_pool.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import random
from core.session import build_puzzle_pool, _pick_puzzles

TRIALS_PER_BLOCK    = 20
REPEATED_RATIO      = 0.50   # what Juliet has set (50/50)
FAM_RATIO           = 0.00
N_FAM_BLOCKS        = 2
N_PRACTICE_BLOCKS   = 6
N_TEST_BLOCKS       = 1

pool = build_puzzle_pool()
print(f"\n{'='*55}")
print(f"  Total unique puzzles in pool: {len(pool)}")

# Deduplicate by representative sequence to show how many DISTINCT move patterns exist
unique_seqs = {tuple(p["sequence"]) for p in pool}
print(f"  Distinct optimal sequences:   {len(unique_seqs)}")
print(f"{'='*55}\n")

# Simulate a full experiment for one participant
repeated_puzzle = None
used_pairs: set = set()
all_blocks = (
    [("familiarization", FAM_RATIO)]    * N_FAM_BLOCKS    +
    [("practice",        REPEATED_RATIO)] * N_PRACTICE_BLOCKS +
    [("post_test",       0.60)]          * N_TEST_BLOCKS
)

print(f"{'BLOCK':<20} {'RANDOM':>7} {'POOL AVAIL':>11} {'FALLBACK?':>10}")
print("-" * 55)

all_random = []
fallback_fired = False

for label, ratio in all_blocks:
    avail = [
        p for p in pool
        if (tuple(p["start"]), tuple(p["goal"])) not in used_pairs
    ]

    trials, repeated_puzzle, new_pairs = _pick_puzzles(
        pool, TRIALS_PER_BLOCK, ratio,
        repeated_puzzle=repeated_puzzle,
        used_pairs=used_pairs,
    )

    random_picks = [p for p, kind in trials if kind == "random"]
    n_random = len(random_picks)
    used_pairs |= new_pairs

    # Check for overlap with previously seen random puzzles
    new_keys = [(tuple(p["start"]), tuple(p["goal"])) for p in random_picks]
    overlap = [k for k in new_keys if k in {(tuple(p["start"]), tuple(p["goal"])) for p in all_random}]
    all_random.extend(random_picks)

    fallback = "YES !" if (len(avail) - 1 < n_random) else "-"
    if fallback == "YES !":
        fallback_fired = True
    print(f"{label:<20} {n_random:>7}   {len(avail):>9}   {fallback:>10}")
    if overlap:
        print(f"  *** REPEAT DETECTED: {len(overlap)} puzzle(s) seen before ***")

print("-" * 55)
total_random = len(all_random)
unique_random = len({(tuple(p["start"]), tuple(p["goal"])) for p in all_random})
repeats = total_random - unique_random

print(f"\nTotal random trials across experiment : {total_random}")
print(f"Unique start/goal pairs used          : {unique_random}")
print(f"Repeated random pairs (should be 0)   : {repeats}")
print(f"Pool size used / available            : {unique_random} / {len(pool)}")
print()
if repeats == 0 and not fallback_fired:
    print("RESULT: No random grid repeats detected. Fix is working correctly.")
elif repeats == 0 and fallback_fired:
    print("RESULT: No repeats, but fallback was triggered (pool may be tight).")
else:
    print(f"RESULT: PROBLEM - {repeats} repeat(s) found. Fix may not be working.")
print()
