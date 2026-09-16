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
    BFS from start_row, start_col that finds ALL optimal paths to every goal.

    Standard BFS records only the first predecessor for each cell, missing
    equally-short alternatives.  This version tracks every predecessor at
    minimum distance, then backtracks to enumerate all optimal sequences.

    Returns a list of dicts with keys: start, goal, sequence, sequences, length.
      sequence  — one representative optimal path (first found)
      sequences — every optimal path of that same minimum length
    """
    start = (start_row, start_col)
    dist  = {start: 0}
    # preds: cell → list of (prev_cell, key) for every shortest predecessor
    preds = {start: []}
    queue = deque([start])

    while queue:
        row, col = queue.popleft()
        d = dist[(row, col)]
        if d >= MAX_SEQUENCE_LENGTH:
            continue
        for key in [1, 2, 3]:
            nxt = apply_key(row, col, key)
            if nxt is None:
                continue
            if nxt not in dist:
                dist[nxt]  = d + 1
                preds[nxt] = [((row, col), key)]
                queue.append(nxt)
            elif dist[nxt] == d + 1:
                # Another path of the same minimum length — keep it
                preds[nxt].append(((row, col), key))

    results = []
    for (gr, gc), d in dist.items():
        if (gr, gc) == start:
            continue
        if not (MIN_SEQUENCE_LENGTH <= d <= MAX_SEQUENCE_LENGTH):
            continue

        # Backtrack from goal to start, collecting every optimal sequence
        all_seqs: list = []

        def _backtrack(cell, path):
            if cell == start:
                all_seqs.append(list(reversed(path)))
                return
            for prev_cell, key in preds[cell]:
                path.append(key)
                _backtrack(prev_cell, path)
                path.pop()

        _backtrack((gr, gc), [])

        if all_seqs:
            results.append({
                "start":     [start_row, start_col],
                "goal":      [gr, gc],
                "sequence":  all_seqs[0],
                "sequences": all_seqs,
                "length":    d,
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
