"""Common engine interface.

Every AI opponent implements `choose(state) -> SearchResult`. The result
carries not just the move but the search statistics the proposal's sidebar and
benchmark report are built on: nodes visited, wall time, depth reached and
evaluated score.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from ..core.move import Move


@dataclass
class SearchResult:
    move: Optional[Move]
    score: float = 0.0
    nodes: int = 0            # positions evaluated or expanded
    time_ms: float = 0.0
    depth: int = 0            # plies actually searched
    extra: dict = field(default_factory=dict)

    @property
    def nodes_per_second(self) -> float:
        return self.nodes / (self.time_ms / 1000) if self.time_ms > 0 else 0.0

    def __str__(self) -> str:
        return (f"{self.move}  score={self.score:+.0f}  nodes={self.nodes:,}  "
                f"depth={self.depth}  {self.time_ms:.1f}ms")


class Engine(ABC):
    """Base class for all KROSH opponents."""

    name = "engine"

    def __init__(self, seed: Optional[int] = None):
        self.seed = seed
        self.total_nodes = 0
        self.total_time_ms = 0.0
        self.moves_played = 0

    @abstractmethod
    def search(self, state) -> SearchResult:
        """Pick a move. Must leave `state` exactly as it was found."""

    def choose(self, state) -> SearchResult:
        """Timed wrapper around `search` that accumulates lifetime stats."""
        start = time.perf_counter()
        result = self.search(state)
        if not result.time_ms:
            result.time_ms = (time.perf_counter() - start) * 1000

        self.total_nodes += result.nodes
        self.total_time_ms += result.time_ms
        self.moves_played += 1
        return result

    def reset_stats(self) -> None:
        self.total_nodes = 0
        self.total_time_ms = 0.0
        self.moves_played = 0

    def summary(self) -> dict:
        """Aggregate stats for the benchmark report."""
        n = max(self.moves_played, 1)
        return {
            "engine": self.name,
            "moves": self.moves_played,
            "total_nodes": self.total_nodes,
            "avg_nodes": self.total_nodes / n,
            "avg_ms": self.total_time_ms / n,
            "nodes_per_sec": (self.total_nodes / (self.total_time_ms / 1000)
                              if self.total_time_ms > 0 else 0.0),
        }

    def __repr__(self) -> str:
        return f"<{self.name}>"
