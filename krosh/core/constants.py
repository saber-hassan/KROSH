"""Geometry, piece encoding and precomputed move tables for KROSH.

The board is stored as a FLAT list of 64 ints (row-major, index = row * 8 + col).
Flat indexing keeps the search hot-loop cheap: one list lookup instead of two.
Use ``sq(row, col)`` / ``rc(square)`` to convert, and ``GameState.matrix()``
when you want the 8x8 NumPy view for evaluation, rendering or reporting.

Piece encoding (sign = owner, magnitude = rank):

    +2  RED king        RED  is the human / "bottom" side, moves toward row 0
    +1  RED man
     0  empty
    -1  WHITE man       WHITE is the "top" side, moves toward row 7
    -2  WHITE king
"""

ROWS = COLS = 8
N_SQUARES = ROWS * COLS

EMPTY = 0
RED_MAN, RED_KING = 1, 2
WHITE_MAN, WHITE_KING = -1, -2

RED, WHITE = 1, -1          # player identifiers == sign of their pieces

# Terminal / result codes
ONGOING, RED_WINS, WHITE_WINS, DRAW = "ongoing", "red", "white", "draw"

# Plies without a capture or a man move before the game is declared drawn.
DRAW_PLY_LIMIT = 80


def sq(row: int, col: int) -> int:
    """Flat index of (row, col)."""
    return row * COLS + col


def rc(square: int) -> tuple:
    """(row, col) of a flat index."""
    return divmod(square, COLS)


def is_playable(row: int, col: int) -> bool:
    """Dark squares only -- matches the original Pygame board layout."""
    return (row + col) % 2 == 1


# Direction order: 0 = NW, 1 = NE, 2 = SW, 3 = SE
DIRECTIONS = ((-1, -1), (-1, 1), (1, -1), (1, 1))

RED_DIRS = (0, 1)           # men move toward row 0
WHITE_DIRS = (2, 3)         # men move toward row 7
KING_DIRS = (0, 1, 2, 3)

# Promotion rows
RED_KING_ROW = 0
WHITE_KING_ROW = ROWS - 1


def _build_tables():
    """Precompute, for every square and direction, the quiet step and the jump.

    STEPS[square][dir]  -> destination square, or -1 if off-board
    JUMPS[square][dir]  -> (midpoint square, landing square), or None
    """
    steps = [[-1] * 4 for _ in range(N_SQUARES)]
    jumps = [[None] * 4 for _ in range(N_SQUARES)]
    for r in range(ROWS):
        for c in range(COLS):
            s = sq(r, c)
            for d, (dr, dc) in enumerate(DIRECTIONS):
                nr, nc = r + dr, c + dc
                if 0 <= nr < ROWS and 0 <= nc < COLS:
                    steps[s][d] = sq(nr, nc)
                    jr, jc = r + 2 * dr, c + 2 * dc
                    if 0 <= jr < ROWS and 0 <= jc < COLS:
                        jumps[s][d] = (sq(nr, nc), sq(jr, jc))
    return steps, jumps


STEPS, JUMPS = _build_tables()

# Directions available to each piece value, indexed for fast lookup.
PIECE_DIRS = {
    RED_MAN: RED_DIRS,
    WHITE_MAN: WHITE_DIRS,
    RED_KING: KING_DIRS,
    WHITE_KING: KING_DIRS,
}
