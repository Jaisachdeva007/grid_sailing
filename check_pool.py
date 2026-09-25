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

# Count distinct PRIMARY sequences (what participants are guided to press)
distinct_primaries = {tuple(p["sequence"]) for p in pool}

print(f"\n{'='*60}")
print(f"  Total unique puzzles in pool   : {len(pool)}")
print(f"  Distinct primary sequences     : {len(distinct_primaries)}")
print(f"{'='*60}\n")

# Simulate a full experiment for one participant.
# used_pairs is a set of primary sequence tuples — matches production format exactly.
repeated_puzzle = None
used_pairs: set = set()
all_blocks = (
    [("familiarization", FAM_RATIO)]      * N_FAM_BLOCKS    +
    [("practice",        REPEATED_RATIO)] * N_PRACTICE_BLOCKS +
    [("post_test",       0.60)]           * N_TEST_BLOCKS
)

print(f"{'BLOCK':<20} {'RANDOM':>7} {'PRIM AVAIL':>11} {'FALLBACK?':>10}")
print("-" * 60)

all_primaries_used = set()
fallback_fired     = False

for label, ratio in all_blocks:
    # How many pool puzzles have a primary not yet tracked
    avail_count = sum(1 for p in pool if tuple(p["sequence"]) not in used_pairs)

    trials, repeated_puzzle, new_pairs = _pick_puzzles(
        pool, TRIALS_PER_BLOCK, ratio,
        repeated_puzzle=repeated_puzzle,
        used_pairs=used_pairs,
    )

    random_picks = [p for p, kind in trials if kind == "random"]
    n_random     = len(random_picks)

    # new_pairs is now a set of primary sequence tuples
    block_primaries = new_pairs
    overlap = block_primaries & all_primaries_used
    all_primaries_used |= block_primaries
    used_pairs         |= new_pairs

    fallback = "YES !" if (avail_count - 1 < n_random) else "-"
    if fallback == "YES !":
        fallback_fired = True
    print(f"{label:<20} {n_random:>7}   {avail_count:>9}   {fallback:>10}")
    if overlap:
        print(f"  *** PRIMARY REPEAT: {len(overlap)} sequence(s) seen in a prior block ***")

print("-" * 60)
print(f"\nRandom trials run                    : {sum(len([p for p, k in trials if k=='random']) for trials, _, _ in [])}")
print(f"Distinct primary sequences used      : {len(all_primaries_used)}")
print(f"Primaries remaining in pool          : {len(distinct_primaries) - len(all_primaries_used)}")
print(f"Pool consumed                        : {len(all_primaries_used)} / {len(distinct_primaries)} "
      f"({100*len(all_primaries_used)/len(distinct_primaries):.1f}%)")
print()
if not fallback_fired:
    print("RESULT: No primary-sequence repeats. Pool headroom is healthy.")
else:
    print("RESULT: No repeats, but fallback triggered (consider adding sessions to simulation).")
print()
