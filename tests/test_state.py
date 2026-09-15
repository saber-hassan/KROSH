"""Rule-correctness suite for the KROSH core.

If these pass, every search engine built on top is reasoning about a legal game.
"""

import pytest

from krosh.core.constants import (
    DRAW, EMPTY, RED, RED_KING, RED_MAN, RED_WINS, WHITE, WHITE_KING,
    WHITE_MAN, WHITE_WINS, sq,
)
from krosh.core.state import GameState, perft


def empty_state(turn=RED, **pieces):
    """Build a sparse position: empty_state(RED, r5c2=RED_MAN, r4c3=WHITE_MAN)."""
    board = [EMPTY] * 64
    for key, value in pieces.items():
        r, c = int(key[1]), int(key[3])
        board[sq(r, c)] = value
    return GameState(board, turn)


# ---------------------------------------------------------------- perft ----
# Published node counts for English draughts from the standard opening.
PERFT_EXPECTED = [1, 7, 49, 302, 1469, 7361, 36768, 179740, 845931]


@pytest.mark.parametrize("depth", range(len(PERFT_EXPECTED)))
def test_perft_matches_reference(depth):
    state = GameState()
    assert perft(state, depth) == PERFT_EXPECTED[depth]


def test_perft_leaves_state_untouched():
    state = GameState()
    before, turn, h = list(state.board), state.turn, state.hash
    perft(state, 4)
    assert state.board == before
    assert state.turn == turn
    assert state.hash == h


# ----------------------------------------------------------- setup ----
def test_initial_material():
    counts = GameState().counts()
    assert counts == {"red_men": 12, "red_kings": 0,
                      "white_men": 12, "white_kings": 0}


def test_red_moves_first():
    assert GameState().turn == RED


def test_only_dark_squares_occupied():
    state = GameState()
    for r in range(8):
        for c in range(8):
            if (r + c) % 2 == 0:
                assert state.piece_at(r, c) == EMPTY


# ------------------------------------------------------ apply / undo ----
def test_undo_restores_position_exactly():
    state = GameState()
    import random
    rng = random.Random(7)
    snapshots = []
    for _ in range(40):
        moves = state.legal_moves()
        if not moves:
            break
        snapshots.append((list(state.board), state.turn,
                          state.quiet_plies, state.hash))
        state.apply(rng.choice(moves))
    while snapshots:
        state.undo()
        board, turn, quiet, h = snapshots.pop()
        assert state.board == board
        assert state.turn == turn
        assert state.quiet_plies == quiet
        assert state.hash == h


def test_hash_is_incrementally_consistent():
    state = GameState()
    import random
    rng = random.Random(11)
    for _ in range(30):
        moves = state.legal_moves()
        if not moves:
            break
        state.apply(rng.choice(moves))
        assert state.hash == state._compute_hash()


def test_hash_differs_by_side_to_move():
    a = GameState()
    b = GameState(turn=WHITE)
    assert a.hash != b.hash


# ------------------------------------------------------ movement ----
def test_red_man_moves_toward_row_zero():
    state = empty_state(RED, r5c2=RED_MAN)
    destinations = {m.to for m in state.legal_moves()}
    assert destinations == {sq(4, 1), sq(4, 3)}


def test_white_man_moves_toward_row_seven():
    state = empty_state(WHITE, r2c3=WHITE_MAN)
    destinations = {m.to for m in state.legal_moves()}
    assert destinations == {sq(3, 2), sq(3, 4)}


def test_king_moves_in_all_four_diagonals():
    state = empty_state(RED, r4c3=RED_KING)
    destinations = {m.to for m in state.legal_moves()}
    assert destinations == {sq(3, 2), sq(3, 4), sq(5, 2), sq(5, 4)}


def test_pieces_cannot_move_onto_friendly_pieces():
    state = empty_state(RED, r5c2=RED_MAN, r4c1=RED_MAN, r4c3=RED_MAN)
    assert {m.to for m in state.moves_from(5, 2)} == set()


# ------------------------------------------------------- captures ----
def test_capture_is_mandatory():
    # RED has a free quiet move at (5,6) but a capture is available at (5,2).
    state = empty_state(RED, r5c2=RED_MAN, r4c3=WHITE_MAN, r5c6=RED_MAN)
    moves = state.legal_moves()
    assert moves and all(m.is_capture for m in moves)
    assert {m.frm for m in moves} == {sq(5, 2)}


def test_single_capture_removes_the_victim():
    state = empty_state(RED, r5c2=RED_MAN, r4c3=WHITE_MAN)
    move, = state.legal_moves()
    assert move.captures == (sq(4, 3),)
    state.apply(move)
    assert state.piece_at(4, 3) == EMPTY
    assert state.piece_at(3, 4) == RED_MAN
    assert state.piece_at(5, 2) == EMPTY


def test_double_jump_is_generated_as_one_move():
    state = empty_state(RED, r5c2=RED_MAN, r4c3=WHITE_MAN, r2c5=WHITE_MAN)
    move, = state.legal_moves()
    assert len(move.captures) == 2
    assert move.to == sq(1, 6)
    state.apply(move)
    assert state.counts()["white_men"] == 0


def test_blocked_landing_square_prevents_capture():
    state = empty_state(RED, r5c2=RED_MAN, r4c3=WHITE_MAN, r3c4=WHITE_MAN)
    assert all(not m.is_capture for m in state.legal_moves())


def test_man_cannot_jump_backward():
    state = empty_state(RED, r3c2=RED_MAN, r4c3=WHITE_MAN)
    assert all(not m.is_capture for m in state.legal_moves())


def test_king_can_jump_backward():
    state = empty_state(RED, r3c2=RED_KING, r4c3=WHITE_MAN)
    moves = [m for m in state.legal_moves() if m.is_capture]
    assert len(moves) == 1
    assert moves[0].to == sq(5, 4)


def test_captured_piece_cannot_be_jumped_twice():
    # A king in a position where re-jumping the same victim would be the only
    # way to produce a longer chain. Chain length must stay at 1.
    state = empty_state(RED, r4c1=RED_KING, r3c2=WHITE_MAN)
    moves = [m for m in state.legal_moves() if m.is_capture]
    assert all(len(m.captures) == 1 for m in moves)


def test_undo_restores_captured_kings_with_correct_rank():
    state = empty_state(RED, r5c2=RED_MAN, r4c3=WHITE_KING)
    move, = state.legal_moves()
    state.apply(move)
    state.undo()
    assert state.piece_at(4, 3) == WHITE_KING


# ------------------------------------------------------- promotion ----
def test_red_man_is_crowned_on_row_zero():
    state = empty_state(RED, r1c2=RED_MAN)
    move = next(m for m in state.legal_moves() if m.to == sq(0, 1))
    assert move.promotion
    state.apply(move)
    assert state.piece_at(0, 1) == RED_KING


def test_white_man_is_crowned_on_row_seven():
    state = empty_state(WHITE, r6c1=WHITE_MAN)
    move = next(m for m in state.legal_moves() if m.to == sq(7, 0))
    assert move.promotion
    state.apply(move)
    assert state.piece_at(7, 0) == WHITE_KING


def test_crowning_ends_a_jump_chain():
    # RED jumps (2,1)->(0,3) and is crowned. As a king it could then jump the
    # piece on (1,4) to reach (2,5), but crowning must end the turn.
    state = empty_state(RED, r2c1=RED_MAN, r1c2=WHITE_MAN, r1c4=WHITE_MAN)
    move, = state.legal_moves()
    assert move.promotion
    assert len(move.captures) == 1
    assert move.to == sq(0, 3)


def test_undo_demotes_a_promoted_piece():
    state = empty_state(RED, r1c2=RED_MAN)
    move = next(m for m in state.legal_moves() if m.promotion)
    state.apply(move)
    state.undo()
    assert state.piece_at(1, 2) == RED_MAN
    assert state.counts()["red_kings"] == 0


def test_king_does_not_re_promote():
    state = empty_state(RED, r1c2=RED_KING)
    assert all(not m.promotion for m in state.legal_moves())


# -------------------------------------------------------- terminal ----
def test_player_with_no_pieces_loses():
    state = empty_state(RED, r4c3=WHITE_MAN)
    assert state.result() == WHITE_WINS


def test_stalemated_player_loses():
    # RED has a piece but every diagonal is blocked or off-board.
    state = empty_state(RED, r7c0=RED_MAN, r6c1=WHITE_MAN, r5c2=WHITE_MAN)
    assert state.legal_moves() == []
    assert state.result() == WHITE_WINS


def test_ongoing_at_start():
    assert GameState().result() == "ongoing"
    assert GameState().winner() is None


def test_quiet_ply_limit_draws():
    state = empty_state(RED, r4c1=RED_KING, r3c6=WHITE_KING)
    state.quiet_plies = 80
    assert state.result() == DRAW
    assert state.winner() is None


def test_capture_resets_quiet_counter():
    state = empty_state(RED, r5c2=RED_MAN, r4c3=WHITE_MAN)
    state.quiet_plies = 30
    state.apply(state.legal_moves()[0])
    assert state.quiet_plies == 0


def test_king_move_increments_quiet_counter():
    state = empty_state(RED, r4c1=RED_KING, r0c7=WHITE_KING)
    state.apply(state.legal_moves()[0])
    assert state.quiet_plies == 1


# ------------------------------------------------------ interop ----
def test_matrix_roundtrip():
    state = GameState()
    rebuilt = GameState.from_matrix(state.matrix(), state.turn)
    assert rebuilt.board == state.board
    assert rebuilt.hash == state.hash


def test_matrix_shape_and_dtype():
    m = GameState().matrix()
    assert m.shape == (8, 8)
    assert str(m.dtype) == "int8"
