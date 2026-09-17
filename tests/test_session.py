"""Tests for the GameSession controller -- all headless, no window opened."""

import pytest

from krosh.app import HUMAN, GameSession
from krosh.core.constants import EMPTY, RED, RED_KING, RED_MAN, WHITE, WHITE_MAN, sq
from krosh.core.state import GameState
from krosh.engines import GreedyEngine, RandomEngine


def mk(turn=RED, **pieces):
    board = [EMPTY] * 64
    for key, value in pieces.items():
        board[sq(int(key[1]), int(key[3]))] = value
    return GameState(board, turn)


def session_with(state, controllers=None):
    s = GameSession(controllers=controllers or {RED: HUMAN, WHITE: HUMAN})
    s.state = state
    return s


# ------------------------------------------------------------- modes ----
def test_human_vs_human_has_no_engines():
    s = GameSession.human_vs_human()
    assert s.controllers[RED] is HUMAN and s.controllers[WHITE] is HUMAN
    assert s.is_human_turn


def test_human_vs_ai_puts_engine_on_the_other_side():
    engine = GreedyEngine()
    s = GameSession.human_vs_ai(engine, human_plays=RED)
    assert s.controllers[RED] is HUMAN
    assert s.controllers[WHITE] is engine


def test_human_can_play_white():
    engine = GreedyEngine()
    s = GameSession.human_vs_ai(engine, human_plays=WHITE)
    assert s.controllers[RED] is engine
    assert not s.is_human_turn          # RED moves first, so the AI opens


def test_side_labels():
    s = GameSession.human_vs_ai(GreedyEngine())
    assert s.side_label(RED) == "Player 1: Human"
    assert s.side_label(WHITE) == "Player 2: greedy"


# --------------------------------------------------------- selection ----
def test_selecting_a_piece_shows_its_destinations():
    s = GameSession.human_vs_human()
    s.click(5, 2)
    assert set(s.highlights()) == {(4, 1), (4, 3)}


def test_clicking_an_opponent_piece_selects_nothing():
    s = GameSession.human_vs_human()
    s.click(2, 1)                       # a WHITE piece on RED's turn
    assert s.selected is None
    assert s.highlights() == []


def test_clicking_empty_space_clears_selection():
    s = GameSession.human_vs_human()
    s.click(5, 2)
    s.click(3, 3)
    assert s.selected is None


def test_completing_a_move_advances_the_turn():
    s = GameSession.human_vs_human()
    s.click(5, 2)
    assert s.click(4, 3) is True
    assert s.state.turn == WHITE
    assert len(s.history) == 1


def test_selection_clears_after_a_move():
    s = GameSession.human_vs_human()
    s.click(5, 2)
    s.click(4, 3)
    assert s.selected is None and s.highlights() == []


def test_reselecting_another_piece_is_allowed():
    s = GameSession.human_vs_human()
    s.click(5, 2)
    s.click(5, 4)
    assert s.selected == sq(5, 4)


# -------------------------------------------------- forced captures ----
def test_piece_without_a_legal_move_reports_why():
    state = mk(RED, r5c2=RED_MAN, r4c3=WHITE_MAN, r5c6=RED_MAN)
    s = session_with(state)
    s.click(5, 6)                        # legal-looking, but a capture exists
    assert s.selected is None
    assert "capture" in s.message.lower()


def test_forced_capture_piece_is_selectable():
    state = mk(RED, r5c2=RED_MAN, r4c3=WHITE_MAN, r5c6=RED_MAN)
    s = session_with(state)
    s.click(5, 2)
    assert s.highlights() == [(3, 4)]


# ------------------------------------------------ multi-jump chains ----
def test_multi_jump_is_played_one_click_at_a_time():
    state = mk(RED, r5c2=RED_MAN, r4c3=WHITE_MAN, r2c5=WHITE_MAN)
    s = session_with(state)
    s.click(5, 2)
    assert s.highlights() == [(3, 4)]

    assert s.click(3, 4) is False        # chain not finished yet
    assert s.state.turn == RED
    assert s.highlights() == [(1, 6)]

    assert s.click(1, 6) is True         # now it completes
    assert s.state.turn == WHITE
    assert s.counts()["white_men"] == 0


def test_partial_chain_tracks_the_path():
    state = mk(RED, r5c2=RED_MAN, r4c3=WHITE_MAN, r2c5=WHITE_MAN)
    s = session_with(state)
    s.click(5, 2)
    s.click(3, 4)
    assert s.partial_path == [sq(3, 4)]
    assert s.selected == sq(5, 2)


def test_branching_chains_stay_distinguishable():
    # Two separate first hops from the same piece.
    state = mk(RED, r4c3=RED_KING, r3c2=WHITE_MAN, r3c4=WHITE_MAN)
    s = session_with(state)
    s.click(4, 3)
    assert set(s.highlights()) == {(2, 1), (2, 5)}
    s.click(2, 1)
    assert s.state.piece_at(2, 1) != EMPTY
    assert s.state.piece_at(3, 2) == EMPTY
    assert s.state.piece_at(3, 4) == WHITE_MAN


# --------------------------------------------------------------- AI ----
def test_run_ai_does_nothing_on_a_human_turn():
    s = GameSession.human_vs_ai(GreedyEngine())
    assert s.run_ai() is None
    assert s.history == []


def test_ai_moves_and_records_a_search_result():
    s = GameSession.human_vs_ai(GreedyEngine(seed=1))
    s.click(5, 2)
    s.click(4, 3)
    result = s.run_ai()
    assert result is not None
    assert result.nodes > 0
    assert s.last_result is result
    assert s.history[-1].engine == "greedy"
    assert s.is_human_turn


def test_human_clicks_are_ignored_during_the_ai_turn():
    s = GameSession.human_vs_ai(GreedyEngine())
    s.click(5, 2)
    s.click(4, 3)                        # now it is WHITE's (the AI's) turn
    before = list(s.state.board)
    s.click(2, 1)
    assert list(s.state.board) == before


# ------------------------------------------------------------ undo ----
def test_undo_in_human_vs_human_reverts_one_move():
    s = GameSession.human_vs_human()
    s.click(5, 2)
    s.click(4, 3)
    assert s.undo() is True
    assert s.state.turn == RED
    assert s.history == []


def test_undo_in_human_vs_ai_reverts_both_plies():
    s = GameSession.human_vs_ai(GreedyEngine(seed=1))
    s.click(5, 2)
    s.click(4, 3)
    s.run_ai()
    assert len(s.history) == 2
    s.undo()
    assert s.history == []
    assert s.is_human_turn
    assert s.state.board == GameState().board


def test_undo_on_an_empty_history_is_a_no_op():
    s = GameSession.human_vs_human()
    assert s.undo() is False


def test_reset_restores_the_opening_position():
    engine = GreedyEngine(seed=1)
    s = GameSession.human_vs_ai(engine)
    s.click(5, 2)
    s.click(4, 3)
    s.run_ai()
    s.reset()
    assert s.history == []
    assert s.state.board == GameState().board
    assert engine.moves_played == 0


# ---------------------------------------------------------- status ----
def test_status_reports_the_winner():
    state = mk(WHITE, r4c3=RED_MAN)      # WHITE has nothing left
    s = session_with(state)
    assert s.is_over
    assert "Player 1 wins" in s.status_line()


def test_clicks_are_ignored_once_the_game_is_over():
    state = mk(WHITE, r4c3=RED_MAN)
    s = session_with(state)
    assert s.click(4, 3) is False


def test_draw_is_reported():
    state = mk(RED, r4c1=RED_KING, r3c6=WHITE_MAN, r0c1=WHITE_MAN)
    state.quiet_plies = 80
    s = session_with(state)
    assert "Draw" in s.status_line()
