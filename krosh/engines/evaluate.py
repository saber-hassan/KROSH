"""Static board evaluation for KROSH.

Every engine -- Greedy, Minimax, Alpha-Beta, and the MCTS tree policy -- scores
positions through this one module. Keeping a single evaluator means an
improvement to the heuristic lifts all engines at once, and means the benchmark
compares *search strategies* rather than accidentally comparing four different
notions of "good position".

Scores are returned from the perspective of a given player: positive is good
for that player, negative is good for the opponent. Units are roughly
"hundredths of a man", so a full man is 100.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..core.constants import (
    COLS, N_SQUARES, RED, RED_KING, RED_MAN, ROWS, WHITE, WHITE_KING,
    WHITE_MAN, rc,
)

# A score that dwarfs any positional consideration but stays well clear of
# float/int overflow, so engines can safely add depth offsets to it.
WIN_SCORE = 1_000_000


@dataclass(frozen=True)
class Weights:
    """Tunable heuristic weights.

    Exposed as a dataclass so the benchmark suite can sweep them and so the
    report can state exactly which configuration produced which win rate.
    """
    man: int = 100
    king: int = 175

    advancement: int = 4      # per row a man has advanced toward promotion
    back_row: int = 12        # men still guarding their own king row
    center: int = 6           # occupancy of the four central files
    center_row: int = 3       # extra for the central ranks
    edge: int = 3             # edge pieces cannot be captured
    king_center: int = 8      # kings are worth more with room to operate

    mobility: int = 0         # per legal move; costs a move-gen, off by default
    chase: int = 3            # endgame: drive the winning side toward contact
    endgame_pieces: int = 6   # total pieces at or below which chase turns on


DEFAULT_WEIGHTS = Weights()


def _build_tables(w: Weights):
    """Precompute the full positional value of each piece type per square."""
    red_man = [0] * N_SQUARES
    white_man = [0] * N_SQUARES
    red_king = [0] * N_SQUARES
    white_king = [0] * N_SQUARES

    for s in range(N_SQUARES):
        r, c = rc(s)

        central_file = w.center if 2 <= c <= 5 else 0
        central_rank = w.center_row if 2 <= r <= 5 else 0
        on_edge = w.edge if c == 0 or c == COLS - 1 else 0

        # RED men advance toward row 0; WHITE men toward row 7.
        red_man[s] = (w.man
                      + (ROWS - 1 - r) * w.advancement
                      + central_file + on_edge
                      + (w.back_row if r == ROWS - 1 else 0))

        white_man[s] = (w.man
                        + r * w.advancement
                        + central_file + on_edge
                        + (w.back_row if r == 0 else 0))

        king_bonus = w.king_center if (2 <= r <= 5 and 2 <= c <= 5) else 0
        red_king[s] = w.king + king_bonus + on_edge
        white_king[s] = w.king + king_bonus + on_edge

    return red_man, white_man, red_king, white_king


_TABLE_CACHE = {}


def tables(w: Weights = DEFAULT_WEIGHTS):
    """Positional tables for a weight set, built once and cached."""
    if w not in _TABLE_CACHE:
        _TABLE_CACHE[w] = _build_tables(w)
    return _TABLE_CACHE[w]


def evaluate(state, player: int, w: Weights = DEFAULT_WEIGHTS) -> int:
    """Static score of `state` from `player`'s point of view.

    This does NOT detect terminal positions -- engines handle those, because
    they already generate moves at every node and can tell a loss from a draw.
    """
    red_man_t, white_man_t, red_king_t, white_king_t = tables(w)
    board = state.board

    score = 0
    red_pieces = white_pieces = 0

    for s in range(N_SQUARES):
        v = board[s]
        if v == 0:
            continue
        if v == RED_MAN:
            score += red_man_t[s]
            red_pieces += 1
        elif v == RED_KING:
            score += red_king_t[s]
            red_pieces += 1
        elif v == WHITE_MAN:
            score -= white_man_t[s]
            white_pieces += 1
        else:  # WHITE_KING
            score -= white_king_t[s]
            white_pieces += 1

    # Endgame: a side that is materially ahead must be pushed toward contact,
    # otherwise it shuffles kings around and the 80-ply rule declares a draw.
    total = red_pieces + white_pieces
    if w.chase and total and total <= w.endgame_pieces and red_pieces != white_pieces:
        score += _chase_term(board, red_pieces > white_pieces, w)

    if w.mobility:
        score += _mobility_term(state, w)

    return score if player == RED else -score


def _chase_term(board, red_is_ahead: bool, w: Weights) -> int:
    """Reward the stronger side for closing distance on the weaker side."""
    strong, weak = [], []
    for s in range(N_SQUARES):
        v = board[s]
        if v == 0:
            continue
        is_red = v > 0
        (strong if is_red == red_is_ahead else weak).append(rc(s))

    if not strong or not weak:
        return 0

    spread = 0
    for sr, sc in strong:
        spread += min(abs(sr - wr) + abs(sc - wc) for wr, wc in weak)

    penalty = w.chase * spread // len(strong)
    return -penalty if red_is_ahead else penalty


def _mobility_term(state, w: Weights) -> int:
    """Legal-move count difference. Accurate but costs two generations."""
    mover = len(state.legal_moves())
    state.turn = -state.turn
    opponent = len(state.legal_moves())
    state.turn = -state.turn
    diff = mover - opponent if state.turn == RED else opponent - mover
    return w.mobility * diff


def material_balance(state, player: int, w: Weights = DEFAULT_WEIGHTS) -> int:
    """Pure material, no positional terms -- used by tests and the report."""
    counts = state.counts()
    red = counts["red_men"] * w.man + counts["red_kings"] * w.king
    white = counts["white_men"] * w.man + counts["white_kings"] * w.king
    balance = red - white
    return balance if player == RED else -balance
