"""GameSession -- the layer between the rules core and any frontend.

The Pygame UI (or a future web UI) never touches `GameState` directly. It
sends clicks in, and reads back a highlight set, a status line and the latest
`SearchResult`. That keeps all turn logic testable without opening a window.

Selection handles multi-jump chains by *path stepping*: a chain is one legal
`Move` internally, but the player clicks each landing square in turn, so two
different chains that share a first hop stay unambiguous.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..core.constants import DRAW, ONGOING, RED, RED_WINS, WHITE, WHITE_WINS, rc, sq
from ..core.move import Move
from ..core.state import GameState
from ..engines.base import Engine, SearchResult

HUMAN = None  # a controller of None means "a person plays this side"


@dataclass
class HistoryEntry:
    move: Move
    player: int
    engine: Optional[str] = None
    result: Optional[SearchResult] = None


@dataclass
class GameSession:
    """Owns one game. Frontend-agnostic."""

    controllers: Dict[int, Optional[Engine]] = field(
        default_factory=lambda: {RED: HUMAN, WHITE: HUMAN})
    state: GameState = field(default_factory=GameState)

    selected: Optional[int] = None
    partial_path: List[int] = field(default_factory=list)
    candidates: List[Move] = field(default_factory=list)
    history: List[HistoryEntry] = field(default_factory=list)
    last_result: Optional[SearchResult] = None
    message: str = ""

    # ------------------------------------------------------------------
    # Turn ownership
    # ------------------------------------------------------------------
    @property
    def current_engine(self) -> Optional[Engine]:
        return self.controllers[self.state.turn]

    @property
    def is_human_turn(self) -> bool:
        return self.current_engine is HUMAN

    @property
    def is_over(self) -> bool:
        return self.state.result() != ONGOING

    def status_line(self) -> str:
        outcome = self.state.result()
        if outcome == DRAW:
            return "Draw - 40 moves without a capture"
        if outcome == RED_WINS:
            return "RED wins"
        if outcome == WHITE_WINS:
            return "WHITE wins"
        side = "RED" if self.state.turn == RED else "WHITE"
        who = "your move" if self.is_human_turn else "thinking..."
        return f"{side} - {who}"

    def side_label(self, player: int) -> str:
        engine = self.controllers[player]
        name = "RED" if player == RED else "WHITE"
        return f"{name}: {'Human' if engine is HUMAN else engine.name}"

    # ------------------------------------------------------------------
    # Human input
    # ------------------------------------------------------------------
    def click(self, row: int, col: int) -> bool:
        """Handle a click. Returns True if a move was completed."""
        if self.is_over or not self.is_human_turn:
            return False

        square = sq(row, col)

        # Extending an in-progress selection or jump chain.
        if self.selected is not None and square in self.next_squares():
            return self._extend(square)

        # Selecting (or re-selecting) a piece.
        piece = self.state.board[square]
        if piece != 0 and (piece > 0) == (self.state.turn > 0):
            return self._select(square)

        self.clear_selection()
        return False

    def _select(self, square: int) -> bool:
        legal = self.state.legal_moves()
        candidates = [m for m in legal if m.frm == square]
        if not candidates:
            self.clear_selection()
            if legal and any(m.is_capture for m in legal):
                self.message = "A capture is available - it must be taken"
            else:
                self.message = "That piece has no legal move"
            return False

        self.selected = square
        self.partial_path = []
        self.candidates = candidates
        self.message = ""
        return False

    def _extend(self, square: int) -> bool:
        self.partial_path.append(square)
        depth = len(self.partial_path)
        prefix = tuple(self.partial_path)
        self.candidates = [m for m in self.candidates if m.path[:depth] == prefix]

        finished = [m for m in self.candidates if len(m.path) == depth]
        if finished:
            self.apply_move(finished[0])
            return True
        return False

    def next_squares(self) -> List[int]:
        """Squares the player may click next -- drives the board highlights."""
        depth = len(self.partial_path)
        out = []
        for move in self.candidates:
            if len(move.path) > depth:
                nxt = move.path[depth]
                if nxt not in out:
                    out.append(nxt)
        return out

    def highlights(self) -> List[tuple]:
        """(row, col) of every clickable destination."""
        return [rc(s) for s in self.next_squares()]

    def clear_selection(self) -> None:
        self.selected = None
        self.partial_path = []
        self.candidates = []

    # ------------------------------------------------------------------
    # Moves
    # ------------------------------------------------------------------
    def apply_move(self, move: Move, result: Optional[SearchResult] = None) -> None:
        player = self.state.turn
        engine = self.controllers[player]
        self.state.apply(move)
        self.history.append(HistoryEntry(
            move=move, player=player,
            engine=None if engine is HUMAN else engine.name,
            result=result,
        ))
        self.clear_selection()
        self.message = ""

    def run_ai(self) -> Optional[SearchResult]:
        """Compute and play the AI move. Safe to call on a worker thread."""
        engine = self.current_engine
        if engine is HUMAN or self.is_over:
            return None
        result = engine.choose(self.state)
        if result.move is None:
            return None
        self.last_result = result
        self.apply_move(result.move, result)
        return result

    # ------------------------------------------------------------------
    # History controls
    # ------------------------------------------------------------------
    def undo(self) -> bool:
        """Undo back to the previous human decision point."""
        if not self.history:
            return False
        self.state.undo()
        self.history.pop()
        # If that leaves an engine on move, roll back one more so the board
        # comes back to the player rather than handing them a new position.
        if self.history and not self.is_human_turn:
            self.state.undo()
            self.history.pop()
        self.clear_selection()
        self.last_result = None
        self.message = "Move undone"
        return True

    def reset(self) -> None:
        self.state = GameState()
        self.history.clear()
        self.clear_selection()
        self.last_result = None
        self.message = ""
        for engine in self.controllers.values():
            if engine is not HUMAN:
                engine.reset_stats()

    # ------------------------------------------------------------------
    def counts(self) -> dict:
        return self.state.counts()

    @classmethod
    def human_vs_human(cls) -> "GameSession":
        return cls(controllers={RED: HUMAN, WHITE: HUMAN})

    @classmethod
    def human_vs_ai(cls, engine: Engine, human_plays: int = RED) -> "GameSession":
        controllers = {RED: HUMAN, WHITE: HUMAN}
        controllers[-human_plays] = engine
        return cls(controllers=controllers)
