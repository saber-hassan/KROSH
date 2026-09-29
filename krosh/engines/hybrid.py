"""Phase-switching Hybrid engine for KROSH.

The insight behind this engine: no single search algorithm is optimal for
every phase of a checkers game.

  - In the OPENING (many pieces, huge branching factor, no clear tactics),
    a deep alpha-beta search is wasted -- the position is too "quiet" for
    tactical vision to matter. Play shallow and fast.

  - In the MIDGAME (captures, exchanges, king promotions dominating), a deep
    alpha-beta search with move ordering and quiescence is the strongest
    tool in the classical toolbox. Play deep.

  - In the ENDGAME (few pieces, long forced sequences, alpha-beta struggles
    because there are no captures to prune around), MCTS with a large
    simulation budget traces long lines that alpha-beta can only guess at.

HybridEngine counts pieces at each move and delegates to whichever inner
engine fits the current phase. Thresholds are class attributes so the
benchmark can tune them without changing the code.
"""

from __future__ import annotations

from typing import Optional

from .alphabeta import AlphaBetaEngine
from .base import Engine, SearchResult
from .mcts import MCTSEngine


class HybridEngine(Engine):
    """Delegates to alpha-beta or MCTS depending on total piece count."""

    name = "hybrid"

    # ------------------------------------------------------------------
    # Phase thresholds (total pieces on the board)
    # ------------------------------------------------------------------
    OPENING_CUTOFF: int = 16   # pieces > this  -> opening
    ENDGAME_CUTOFF: int = 8    # pieces < this  -> endgame

    # ------------------------------------------------------------------
    # Per-phase engine strength
    # ------------------------------------------------------------------
    OPENING_DEPTH: int = 5      # shallow alpha-beta
    MIDGAME_DEPTH: int = 8      # deep alpha-beta
    ENDGAME_ROLLOUTS: int = 5000  # heavy MCTS

    def __init__(self, seed: Optional[int] = 0, **overrides):
        super().__init__(seed)

        # Allow constructor overrides for benchmarking (any of the class attrs)
        for key, value in overrides.items():
            if hasattr(self, key.upper()):
                setattr(self, key.upper(), value)

        # Build the three inner engines once. Each keeps its own stats.
        self.opening_engine = AlphaBetaEngine(depth=self.OPENING_DEPTH, seed=seed)
        self.midgame_engine = AlphaBetaEngine(depth=self.MIDGAME_DEPTH, seed=seed)
        self.endgame_engine = MCTSEngine(
            simulations=self.ENDGAME_ROLLOUTS, seed=seed,
        )

    # ------------------------------------------------------------------
    def _phase_of(self, state) -> str:
        """Classify the current position."""
        counts = state.counts()
        total = (counts["red_men"] + counts["red_kings"]
                 + counts["white_men"] + counts["white_kings"])
        if total > self.OPENING_CUTOFF:
            return "opening"
        if total < self.ENDGAME_CUTOFF:
            return "endgame"
        return "midgame"

    # ------------------------------------------------------------------
    def _delegate(self, phase: str) -> Engine:
        return {
            "opening": self.opening_engine,
            "midgame": self.midgame_engine,
            "endgame": self.endgame_engine,
        }[phase]

    # ------------------------------------------------------------------
    def search(self, state) -> SearchResult:
        phase = self._phase_of(state)
        engine = self._delegate(phase)
        result = engine.search(state)

        # Annotate the result so the sidebar and benchmark can see which
        # inner engine actually chose the move.
        extra = dict(result.extra) if result.extra else {}
        extra["phase"] = phase
        extra["delegate"] = engine.name

        return SearchResult(
            move=result.move,
            score=result.score,
            nodes=result.nodes,
            time_ms=result.time_ms,
            depth=result.depth,
            extra=extra,
        )

    # ------------------------------------------------------------------
    def reset_stats(self) -> None:
        super().reset_stats()
        self.opening_engine.reset_stats()
        self.midgame_engine.reset_stats()
        self.endgame_engine.reset_stats()
