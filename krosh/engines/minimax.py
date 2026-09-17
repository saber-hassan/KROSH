"""Depth-limited Minimax opponent for KROSH.

Plain recursive negamax over apply/undo, no pruning. That is on purpose:
Phase 4 will add alpha-beta on top of the same function, and we need this
uninstrumented baseline to *measure* how much the pruning saves.

The engine returns a full SearchResult so the sidebar and the benchmark
report both draw from the same numbers. Terminal scores use a mate-distance
trick (WIN_SCORE - ply) so the search prefers a shallower mate to a deeper
one, and prefers a deeper loss to an immediate one -- basic sanity that keeps
the engine from resigning early.
"""

from __future__ import annotations

import random
from typing import List, Optional

from ..core.constants import DRAW, ONGOING
from ..core.move import Move
from .base import Engine, SearchResult
from .evaluate import DEFAULT_WEIGHTS, WIN_SCORE, Weights, evaluate


class MinimaxEngine(Engine):
    """Negamax search to a fixed ply depth. No pruning, no TT, no ordering."""

    name = "minimax"

    def __init__(self, depth: int = 4, weights: Weights = DEFAULT_WEIGHTS,
                 seed: Optional[int] = 0):
        super().__init__(seed)
        if depth < 1:
            raise ValueError("minimax depth must be >= 1")
        self.depth = depth
        self.weights = weights
        self.rng = random.Random(seed)

    # ------------------------------------------------------------------
    def search(self, state) -> SearchResult:
        player = state.turn
        moves = state.legal_moves()
        if not moves:
            # No legal reply -- the side to move has lost.
            return SearchResult(move=None, score=-WIN_SCORE, nodes=0, depth=0)

        nodes = [0]           # boxed so the recursion can mutate it
        best_score = None
        best_moves: List[Move] = []

        for move in moves:
            state.apply(move)
            nodes[0] += 1
            # Negamax: opponent picks max of their score, we negate.
            score = -self._negamax(state, self.depth - 1, ply=1, nodes=nodes)
            state.undo()

            if best_score is None or score > best_score:
                best_score = score
                best_moves = [move]
            elif score == best_score:
                best_moves.append(move)

        chosen = self.rng.choice(best_moves)
        return SearchResult(
            move=chosen, score=best_score, nodes=nodes[0], depth=self.depth,
            extra={
                "ties": len(best_moves),
                "branching": len(moves),
                "pruning": "none",
            },
        )

    # ------------------------------------------------------------------
    def _negamax(self, state, depth: int, ply: int, nodes: list) -> int:
        """Return score from the perspective of the side to move."""
        outcome = state.result()
        if outcome != ONGOING:
            if outcome == DRAW:
                return 0
            # result() is a string; side-to-move has just been dealt this
            # outcome. If it names our colour we won, else we lost.
            side_to_move = state.turn
            won = (outcome == "red" and side_to_move == 1) or \
                  (outcome == "white" and side_to_move == -1)
            # Prefer shallow wins, distant losses.
            return (WIN_SCORE - ply) if won else -(WIN_SCORE - ply)

        if depth == 0:
            return evaluate(state, state.turn, self.weights)

        moves = state.legal_moves()
        if not moves:
            # Stalemate = loss for the side to move.
            return -(WIN_SCORE - ply)

        best = None
        for move in moves:
            state.apply(move)
            nodes[0] += 1
            score = -self._negamax(state, depth - 1, ply + 1, nodes)
            state.undo()
            if best is None or score > best:
                best = score
        return best
