"""Greedy and Random opponents -- the bottom two rungs of the KROSH ladder.

Greedy is a one-ply search: it plays whichever legal move looks best *after it
is made*, with no model of the reply. That makes it fast (well under a
millisecond) and a useful baseline: any deeper engine that cannot beat Greedy
convincingly has a bug, and Greedy that cannot beat Random has a sign error in
the evaluation.
"""

from __future__ import annotations

import random
from typing import Optional

from ..core.constants import DRAW, ONGOING
from .base import Engine, SearchResult
from .evaluate import DEFAULT_WEIGHTS, WIN_SCORE, Weights, evaluate


class RandomEngine(Engine):
    """Uniformly random legal move. The control group for the benchmark."""

    name = "random"

    def __init__(self, seed: Optional[int] = 0):
        super().__init__(seed)
        self.rng = random.Random(seed)

    def search(self, state) -> SearchResult:
        moves = state.legal_moves()
        if not moves:
            return SearchResult(move=None, nodes=0, depth=0)
        return SearchResult(move=self.rng.choice(moves), nodes=len(moves), depth=1)


class GreedyEngine(Engine):
    """One-ply best-first search over the static evaluation."""

    name = "greedy"

    def __init__(self, weights: Weights = DEFAULT_WEIGHTS, seed: Optional[int] = 0):
        super().__init__(seed)
        self.weights = weights
        self.rng = random.Random(seed)

    def search(self, state) -> SearchResult:
        player = state.turn
        moves = state.legal_moves()
        if not moves:
            return SearchResult(move=None, score=-WIN_SCORE, nodes=0, depth=0)

        best_score = None
        best_moves = []
        nodes = 0

        for move in moves:
            state.apply(move)
            nodes += 1

            outcome = state.result()
            if outcome == ONGOING:
                score = evaluate(state, player, self.weights)
            elif outcome == DRAW:
                score = 0
            else:
                # result() names the winner; we just moved, so a decisive
                # outcome here means the opponent is stalemated or wiped out.
                won = (outcome == "red" and player == 1) or \
                      (outcome == "white" and player == -1)
                score = WIN_SCORE if won else -WIN_SCORE

            state.undo()

            if best_score is None or score > best_score:
                best_score = score
                best_moves = [move]
            elif score == best_score:
                best_moves.append(move)

        # Random tie-break, seeded, so matches stay reproducible.
        chosen = self.rng.choice(best_moves)
        return SearchResult(move=chosen, score=best_score, nodes=nodes, depth=1,
                            extra={"ties": len(best_moves), "branching": len(moves)})
