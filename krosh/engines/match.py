"""Headless game driver.

Runs engine-vs-engine matches with no Pygame involved, which is what makes the
benchmark suite fast and CI-friendly. Phase 8's report is generated from the
`MatchResult` records this produces.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from ..core.constants import DRAW, ONGOING, RED, RED_WINS, WHITE, WHITE_WINS
from ..core.state import GameState
from .base import Engine


@dataclass
class MatchResult:
    outcome: str                      # RED_WINS / WHITE_WINS / DRAW
    plies: int
    red_engine: str
    white_engine: str
    red_stats: dict = field(default_factory=dict)
    white_stats: dict = field(default_factory=dict)
    move_log: List[str] = field(default_factory=list)

    @property
    def winner_name(self) -> Optional[str]:
        if self.outcome == RED_WINS:
            return self.red_engine
        if self.outcome == WHITE_WINS:
            return self.white_engine
        return None


def play_game(red: Engine, white: Engine, max_plies: int = 400,
              state: Optional[GameState] = None,
              log_moves: bool = False) -> MatchResult:
    """Play one game to completion. Returns the result and per-engine stats."""
    state = state or GameState()
    red.reset_stats()
    white.reset_stats()

    log: List[str] = []
    plies = 0

    while plies < max_plies:
        outcome = state.result()
        if outcome != ONGOING:
            break

        engine = red if state.turn == RED else white
        result = engine.choose(state)
        if result.move is None:
            break

        state.apply(result.move)
        if log_moves:
            log.append(str(result.move))
        plies += 1
    else:
        outcome = DRAW

    if state.result() == ONGOING:
        outcome = DRAW
    else:
        outcome = state.result()

    return MatchResult(
        outcome=outcome,
        plies=plies,
        red_engine=red.name,
        white_engine=white.name,
        red_stats=red.summary(),
        white_stats=white.summary(),
        move_log=log,
    )


def play_series(engine_a: Engine, engine_b: Engine, games: int = 20,
                max_plies: int = 400) -> dict:
    """Play `games` games, alternating colours so neither side gets the first-
    move advantage for the whole series."""
    tally = {"a_wins": 0, "b_wins": 0, "draws": 0, "games": [],
             "a_name": engine_a.name, "b_name": engine_b.name}

    for i in range(games):
        a_is_red = (i % 2 == 0)
        red, white = (engine_a, engine_b) if a_is_red else (engine_b, engine_a)
        result = play_game(red, white, max_plies=max_plies)

        if result.outcome == DRAW:
            tally["draws"] += 1
        elif (result.outcome == RED_WINS) == a_is_red:
            tally["a_wins"] += 1
        else:
            tally["b_wins"] += 1
        tally["games"].append(result)

    decisive = tally["a_wins"] + tally["b_wins"]
    tally["a_win_rate"] = tally["a_wins"] / games
    tally["a_score"] = (tally["a_wins"] + 0.5 * tally["draws"]) / games
    tally["decisive"] = decisive
    return tally
