# ============================================================
#  GRID-SAILING TASK — Grid Logic
#
#  You don't need to touch this file.
#
#  This file does all the grid maths behind the scenes:
#    - Checks whether a position is actually inside the grid
#    - Works out where the cursor goes when a key is pressed
#    - Generates all valid puzzles at session startup
#
#  The puzzle generator uses BFS so the stored sequence is always
#  the TRUE shortest path from start to goal — no shortcut exists.
#  A puzzle is only valid if the minimum reachable distance to the
#  cheese is between MIN_SEQUENCE_LENGTH and MAX_SEQUENCE_LENGTH.
#  It runs once when the session starts — not during trials.
# ============================================================

from collections import deque
from config import GRID_SIZE, KEY_MAPPINGS, MIN_SEQUENCE_LENGTH, MAX_SEQUENCE_LENGTH


def is_valid_position(row, col):
    """Return True if (row, col) is inside the grid."""
    return 0 <= row < GRID_SIZE and 0 <= col < GRID_SIZE


def apply_key(row, col, key):
    dr, dc = KEY_MAPPINGS[key]
    new_row, new_col = row + dr, col + dc
    if is_valid_position(new_row, new_col):
        return new_row, new_col
    return None


def find_valid_paths(start_row, start_col):
    """
    BFS from start_row, start_col.

    Because BFS explores cells in order of increasing distance, the first
    time any cell is reached that distance IS the minimum — no shorter route
    exists.  We only emit a puzzle when that minimum distance falls in
    [MIN_SEQUENCE_LENGTH, MAX_SEQUENCE_LENGTH].

    Returns a list of dicts with keys: start, goal, sequence, length.
    """
    # dist  : cell → minimum steps from start
    # parent: cell → (previous_cell, key_that_was_pressed)
    dist   = {(start_row, start_col): 0}
    parent = {(start_row, start_col): (None, None)}
    queue  = deque([(start_row, start_col)])

    while queue:
        row, col = queue.popleft()
        d = dist[(row, col)]
        if d >= MAX_SEQUENCE_LENGTH:
            continue
        for key in [1, 2, 3]:
            nxt = apply_key(row, col, key)
            if nxt and nxt not in dist:
                dist[nxt]   = d + 1
                parent[nxt] = ((row, col), key)
                queue.append(nxt)

    results = []
    for (gr, gc), d in dist.items():
        if (gr, gc) == (start_row, start_col):
            continue
        if not (MIN_SEQUENCE_LENGTH <= d <= MAX_SEQUENCE_LENGTH):
            continue

        # Reconstruct the unique BFS-shortest path
        seq  = []
        cell = (gr, gc)
        while parent[cell][0] is not None:
            seq.append(parent[cell][1])
            cell = parent[cell][0]
        seq.reverse()

        results.append({
            "start":    [start_row, start_col],
            "goal":     [gr, gc],
            "sequence": seq,
            "length":   d,
        })

    return results


def find_all_valid_puzzles():
    """
    Enumerate all valid puzzles across every possible start position on the grid.

    Returns:
        list of dicts: All valid (start, goal, sequence) combinations.
    """
    all_puzzles = []
    for row in range(GRID_SIZE):
        for col in range(GRID_SIZE):
            all_puzzles.extend(find_valid_paths(row, col))
    return all_puzzles
