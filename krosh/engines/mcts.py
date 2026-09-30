"""Monte Carlo Tree Search opponent for KROSH.

UCT with the four standard phases: selection, expansion, simulation and
backpropagation.

Three checkers-specific adaptations matter here, and each is a deliberate
departure from the textbook algorithm:

1. **Rollouts are cut short and scored by the evaluation function.** A random
   playout from the opening almost never reaches a decisive result inside a
   reasonable ply budget, so a plain win/loss/draw reward is 0.5 essentially
   every time and the tree learns nothing. Cutting the rollout off and asking
   the evaluator "who stands better here?" gives a graded signal every time.

2. **Playouts are biased, not uniform.** Pure random play in checkers wanders;
   weighting captures and promotions makes a rollout resemble plausible play,
   so its outcome correlates with the quality of the position it started from.

3. **Values are stored from the root player's point of view, and selection
   inverts them at opponent nodes.** Without this the tree maximises the root
   player's score at *every* level -- it assumes the opponent is helping.
"""

from __future__ import annotations

import math
import random
import time
from typing import List, Optional

from ..core.constants import DRAW, ONGOING, RED
from .base import Engine, SearchResult
from .evaluate import DEFAULT_WEIGHTS, Weights, evaluate

EVAL_SCALE = 400.0


class MCTSNode:
    __slots__ = ("state", "parent", "move", "children", "untried",
                 "visits", "value")

    def __init__(self, state, parent=None, move=None):
        self.state = state
        self.parent = parent
        self.move = move
        self.children: List["MCTSNode"] = []
        self.untried: Optional[List] = None
        self.visits = 0
        self.value = 0.0

    def is_terminal(self) -> bool:
        return self.state.is_terminal()

    def expandable(self) -> bool:
        return bool(self.untried)

    def uct_select(self, c: float, root_player: int) -> "MCTSNode":
        """Best child by UCB1.

        `value` is always stored from the root player's perspective, so at a
        node where the opponent moves we invert it -- they pick the line that
        is worst for us.
        """
        maximising = self.state.turn == root_player
        log_n = math.log(max(1, self.visits))
        best, best_score = None, -math.inf
        for child in self.children:
            exploit = child.value / child.visits
            if not maximising:
                exploit = 1.0 - exploit
            score = exploit + c * math.sqrt(2 * log_n / child.visits)
            if score > best_score:
                best, best_score = child, score
        return best


class MCTSEngine(Engine):
    """UCT search with evaluation-backed, capture-biased rollouts."""

    name = "mcts"

    def __init__(self, simulations: int = 800, exploration: float = 1.414,
                 rollout_depth: int = 40, weights: Weights = DEFAULT_WEIGHTS,
                 seed: Optional[int] = 0, **kwargs):
        super().__init__(seed)
        self.simulations = simulations
        self.exploration = exploration
        self.rollout_depth = rollout_depth
        self.weights = weights
        # An instance RNG, never the global `random` module: seeding the
        # global one silently changes every other engine's tie-breaking and
        # makes benchmark runs unreproducible.
        self.rng = random.Random(seed)

    def search(self, state) -> SearchResult:
        start = time.perf_counter()
        root_player = state.turn

        legal = state.legal_moves()
        if not legal:
            return SearchResult(move=None, score=0.0, nodes=0, depth=0)
        if len(legal) == 1:
            # Forced move -- a compulsory capture with no alternative. Don't
            # spend the budget proving what is already decided.
            return SearchResult(
                move=legal[0], score=0.0, nodes=0, depth=0,
                time_ms=(time.perf_counter() - start) * 1000,
                extra={"simulations": 0, "forced": True})

        root = MCTSNode(state.copy())
        root.untried = list(legal)
        rollouts = 0

        for _ in range(self.simulations):
            node = root

            while not node.expandable() and node.children:
                node = node.uct_select(self.exploration, root_player)

            if node.untried is None:
                node.untried = ([] if node.is_terminal()
                                else list(node.state.legal_moves()))
            if node.untried:
                move = node.untried.pop(self.rng.randrange(len(node.untried)))
                child_state = node.state.copy()
                child_state.apply(move)
                child = MCTSNode(child_state, parent=node, move=move)
                node.children.append(child)
                node = child

            reward = self._rollout(node.state, root_player)
            rollouts += 1

            while node is not None:
                node.visits += 1
                node.value += reward
                node = node.parent

        # Most-visited child, not best average: visit count is far more robust
        # than a mean a few lucky rollouts can skew on a rare node.
        best = max(root.children, key=lambda c: c.visits)
        win_rate = best.value / best.visits if best.visits else 0.0

        return SearchResult(
            move=best.move,
            score=round((win_rate - 0.5) * 2000),
            nodes=rollouts,
            time_ms=(time.perf_counter() - start) * 1000,
            depth=self._tree_depth(root),
            extra={
                "simulations": self.simulations,
                "win_rate": round(win_rate, 3),
                "root_children": len(root.children),
                "best_visits": best.visits,
                "exploration": self.exploration,
            },
        )

    def _rollout(self, state, root_player: int) -> float:
        """Play a biased random game and return a reward in [0, 1]."""
        sim = state.copy()
        rng = self.rng

        for _ in range(self.rollout_depth):
            outcome = sim.result()
            if outcome != ONGOING:
                return self._terminal_reward(outcome, root_player)
            moves = sim.legal_moves()
            if not moves:
                break
            sim.apply(self._pick_rollout_move(moves, rng))

        outcome = sim.result()
        if outcome != ONGOING:
            return self._terminal_reward(outcome, root_player)

        score = evaluate(sim, root_player, self.weights)
        return 0.5 + 0.5 * math.tanh(score / EVAL_SCALE)

    @staticmethod
    def _pick_rollout_move(moves, rng):
        """Weighted choice: prefer long capture chains, then promotions."""
        if len(moves) == 1:
            return moves[0]
        weights = []
        for move in moves:
            weight = 1.0
            if move.captures:
                weight += 3.0 * len(move.captures)
            if move.promotion:
                weight += 2.0
            weights.append(weight)
        return rng.choices(moves, weights=weights, k=1)[0]

    @staticmethod
    def _terminal_reward(outcome: str, root_player: int) -> float:
        if outcome == DRAW:
            return 0.5
        red_won = outcome == "red"
        return 1.0 if red_won == (root_player == RED) else 0.0

    @staticmethod
    def _tree_depth(root) -> int:
        depth, node = 0, root
        while node.children:
            node = max(node.children, key=lambda c: c.visits)
            depth += 1
        return depth
