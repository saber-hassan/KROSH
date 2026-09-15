"""Tests for the Phase 2 evaluation function and Greedy agent."""

import pytest

from krosh.core.constants import (
    EMPTY, RED, RED_KING, RED_MAN, WHITE, WHITE_KING, WHITE_MAN, sq,
)
from krosh.core.state import GameState
from krosh.engines import (
    WIN_SCORE, GreedyEngine, RandomEngine, Weights, evaluate,
    material_balance, play_game, play_series,
)


def mk(turn=RED, **pieces):
    board = [EMPTY] * 64
    for key, value in pieces.items():
        board[sq(int(key[1]), int(key[3]))] = value
    return GameState(board, turn)


# ------------------------------------------------------- evaluation ----
def test_opening_position_is_balanced():
    state = GameState()
    assert evaluate(state, RED) == 0
    assert evaluate(state, WHITE) == 0


def test_evaluation_is_antisymmetric():
    state = GameState()
    import random
    rng = random.Random(3)
    for _ in range(25):
        moves = state.legal_moves()
        if not moves:
            break
        state.apply(rng.choice(moves))
        assert evaluate(state, RED) == -evaluate(state, WHITE)


def test_extra_man_is_worth_about_one_hundred():
    state = mk(RED, r5c0=RED_MAN, r5c2=RED_MAN, r4c1=WHITE_MAN)
    assert 80 <= evaluate(state, RED) <= 130


def test_king_outvalues_man():
    king = mk(RED, r4c3=RED_KING)
    man = mk(RED, r4c3=RED_MAN)
    assert evaluate(king, RED) > evaluate(man, RED)


def test_advanced_man_scores_higher():
    near = mk(RED, r1c2=RED_MAN)
    far = mk(RED, r6c1=RED_MAN)
    assert evaluate(near, RED) > evaluate(far, RED)


def test_white_advancement_runs_the_other_way():
    near = mk(WHITE, r6c1=WHITE_MAN)
    far = mk(WHITE, r1c2=WHITE_MAN)
    assert evaluate(near, WHITE) > evaluate(far, WHITE)


def test_back_row_guard_is_rewarded():
    guarded = mk(RED, r7c0=RED_MAN)
    forward = mk(RED, r6c1=RED_MAN)
    w = Weights(advancement=0)          # isolate the back-row term
    assert evaluate(guarded, RED, w) > evaluate(forward, RED, w)


def test_material_balance_ignores_position():
    a = mk(RED, r1c2=RED_MAN)
    b = mk(RED, r6c1=RED_MAN)
    assert material_balance(a, RED) == material_balance(b, RED)


def test_mobility_is_off_by_default():
    state = mk(RED, r4c3=RED_KING, r0c1=WHITE_MAN)
    plain = evaluate(state, RED, Weights(mobility=0))
    mobile = evaluate(state, RED, Weights(mobility=5))
    assert plain != mobile          # the term does something when enabled
    assert evaluate(state, RED) == plain


def test_chase_rewards_closing_distance_when_ahead():
    w = Weights()
    close = mk(RED, r4c3=RED_KING, r4c5=RED_KING, r3c4=WHITE_KING)
    far = mk(RED, r7c0=RED_KING, r7c2=RED_KING, r0c7=WHITE_KING)
    assert evaluate(close, RED, w) > evaluate(far, RED, w)


def test_chase_is_inactive_with_many_pieces():
    state = GameState()
    assert evaluate(state, RED, Weights(chase=0)) == evaluate(state, RED)


def test_evaluation_does_not_mutate_state():
    state = GameState()
    before = list(state.board), state.turn, state.hash
    evaluate(state, RED, Weights(mobility=5))
    assert (list(state.board), state.turn, state.hash) == before


# ----------------------------------------------------------- greedy ----
def test_greedy_returns_a_legal_move():
    state = GameState()
    result = GreedyEngine().choose(state)
    assert result.move in state.legal_moves()


def test_greedy_leaves_state_untouched():
    state = GameState()
    before = list(state.board), state.turn, state.quiet_plies, state.hash
    GreedyEngine().choose(state)
    assert (list(state.board), state.turn, state.quiet_plies, state.hash) == before


def test_greedy_prefers_the_larger_capture():
    state = mk(RED, r5c0=RED_MAN, r4c1=WHITE_MAN, r2c3=WHITE_MAN,
               r5c4=RED_MAN, r4c5=WHITE_MAN)
    result = GreedyEngine().choose(state)
    assert len(result.move.captures) == 2


def test_greedy_takes_an_immediate_win():
    # Capturing WHITE's last piece ends the game.
    state = mk(RED, r5c0=RED_MAN, r4c1=WHITE_MAN)
    result = GreedyEngine().choose(state)
    assert result.score == WIN_SCORE


def test_greedy_reports_stats():
    state = GameState()
    result = GreedyEngine().choose(state)
    assert result.nodes == len(state.legal_moves())
    assert result.depth == 1
    assert result.time_ms > 0


def test_greedy_is_deterministic_for_a_fixed_seed():
    a = GreedyEngine(seed=42).choose(GameState()).move
    b = GreedyEngine(seed=42).choose(GameState()).move
    assert a == b


def test_engine_returns_none_when_stalemated():
    state = mk(RED, r7c0=RED_MAN, r6c1=WHITE_MAN, r5c2=WHITE_MAN)
    assert GreedyEngine().choose(state).move is None
    assert RandomEngine().choose(state).move is None


def test_greedy_is_fast():
    engine = GreedyEngine()
    state = GameState()
    for _ in range(20):
        moves = state.legal_moves()
        if not moves:
            break
        engine.choose(state)
        state.apply(moves[0])
    assert engine.summary()["avg_ms"] < 5.0


# ------------------------------------------------------------ match ----
def test_play_game_reaches_a_terminal_result():
    result = play_game(GreedyEngine(seed=1), RandomEngine(seed=2))
    assert result.outcome in {"red", "white", "draw"}
    assert result.plies > 0


def test_match_records_per_engine_stats():
    result = play_game(GreedyEngine(seed=1), RandomEngine(seed=2))
    assert result.red_stats["engine"] == "greedy"
    assert result.white_stats["engine"] == "random"
    assert result.red_stats["moves"] > 0


@pytest.mark.slow
def test_greedy_outperforms_random():
    """The floor check: if this fails, the evaluation sign is wrong."""
    tally = play_series(GreedyEngine(seed=1), RandomEngine(seed=2), games=120)
    assert tally["a_score"] > 0.58
