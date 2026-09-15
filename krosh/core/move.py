"""Move and Undo records.

A Move is immutable and fully describes a turn, including a whole multi-jump
chain. An Undo carries everything needed to restore the previous position
exactly -- this is what lets the search engines avoid copying the board.
"""

from dataclasses import dataclass, field
from typing import Tuple

from .constants import rc


@dataclass(frozen=True)
class Move:
    frm: int                          # origin square (flat index)
    to: int                           # final landing square
    captures: Tuple[int, ...] = ()    # squares of captured pieces, in order
    path: Tuple[int, ...] = ()        # intermediate landing squares of a chain
    promotion: bool = False           # did this move crown the piece?

    @property
    def is_capture(self) -> bool:
        return bool(self.captures)

    def squares(self) -> Tuple[int, ...]:
        """Full trajectory: origin, every landing, final square."""
        return (self.frm,) + self.path

    def __str__(self) -> str:
        sep = "x" if self.is_capture else "-"
        pts = [f"{r}{c}" for r, c in (rc(s) for s in self.squares())]
        return sep.join(pts) + ("=K" if self.promotion else "")


@dataclass
class Undo:
    """Everything needed to reverse one `apply`."""
    move: Move
    moved_value: int                  # piece value BEFORE promotion
    captured_values: Tuple[int, ...] = field(default_factory=tuple)
    prev_quiet_plies: int = 0
    prev_hash: int = 0
