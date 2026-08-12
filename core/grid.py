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
#  The puzzle generator searches every possible path through the grid
#  and keeps only the ones that: hit the right length, use all 3 keys
#  at least once, and never step on the same cell twice.
#  It runs once when the session starts — not during trials.
# ============================================================

from config import GRID_SIZE, KEY_MAPPINGS, MIN_SEQUENCE_LENGTH, MAX_SEQUENCE_LENGTH


def is_valid_position(row, col):
    """Return True if (row, col) is inside the grid."""
    return 0 <= row < GRID_SIZE and 0 <= col < GRID_SIZE


def apply_key(row, col, key):
    """
    Apply a key press to the current cursor position.

    Args:
        row (int): Current row.
        col (int): Current column.
        key (int): Key pressed (1, 2, or 3).

    Returns:
        (int, int): New (row, col) after the move, or None if the move is out of bounds.
    """
    dr, dc = KEY_MAPPINGS[key]
    new_row, new_col = row + dr, col + dc
    if is_valid_position(new_row, new_col):
        return new_row, new_col
    return None


def find_valid_paths(start_row, start_col):
    """
    Use depth-first search to find all valid paths from a given start position.

    A valid path must:
      - Be at least MIN_SEQUENCE_LENGTH key presses long
      - Use all three keys (1, 2, 3) at least once
      - Never revisit a grid square

    Args:
        start_row (int): Starting row index.
        start_col (int): Starting column index.

    Returns:
        list of dicts: Each dict has keys 'start', 'goal', 'sequence', 'length'.
    """
    results = []

    def dfs(row, col, sequence, visited):
        # Record puzzle if it meets the length and key-variety constraints
        if (MIN_SEQUENCE_LENGTH <= len(sequence) <= MAX_SEQUENCE_LENGTH
                and set(sequence) == {1, 2, 3}):
            results.append({
                "start":    [start_row, start_col],
                "goal":     [row, col],
                "sequence": list(sequence),
                "length":   len(sequence),
            })

        # Prune — no path longer than MAX_SEQUENCE_LENGTH is valid
        if len(sequence) >= MAX_SEQUENCE_LENGTH:
            return

        # Try each key press and continue exploring
        for key in [1, 2, 3]:
            next_pos = apply_key(row, col, key)
            if next_pos and next_pos not in visited:
                visited.add(next_pos)
                sequence.append(key)
                dfs(next_pos[0], next_pos[1], sequence, visited)
                sequence.pop()
                visited.remove(next_pos)

    dfs(start_row, start_col, [], {(start_row, start_col)})
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
            puzzles = find_valid_paths(row, col)
            all_puzzles.extend(puzzles)
    return all_puzzles
