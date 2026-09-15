"""GameState -- the single source of truth for KROSH's rules.

This module knows nothing about Pygame. It is pure data plus rules, so it can
be unit-tested in milliseconds and searched millions of nodes deep without
dragging a renderer along.

Rules implemented (standard English / American draughts):
  * Men move one square diagonally forward; kings move one square any diagonal.
  * Jumps are over an adjacent enemy piece to the empty square beyond.
  * Capturing is MANDATORY. If any capture exists, only captures are legal.
  * Multi-jump chains must be played to completion.
  * A man that reaches the king row is crowned and its turn ends immediately
    (crowning terminates a jump chain).
  * Captured pieces are removed only at the end of the move, so they still
    block landing squares and cannot be jumped twice.
  * A player with no legal moves loses.
  * 80 plies (40 moves each) without a capture or a man move is a draw.
"""

from __future__ import annotations

import random
from typing import List, Optional

import numpy as np

from .constants import (
    COLS, DRAW, DRAW_PLY_LIMIT, EMPTY, JUMPS, N_SQUARES, ONGOING, PIECE_DIRS,
    RED, RED_KING, RED_KING_ROW, RED_MAN, RED_WINS, ROWS, STEPS, WHITE,
    WHITE_KING, WHITE_KING_ROW, WHITE_MAN, WHITE_WINS, is_playable, rc, sq,
)
from .move import Move, Undo

# --------------------------------------------------------------------------
# Zobrist hashing -- fixed seed so runs are reproducible for benchmarking.
# --------------------------------------------------------------------------
_PIECE_INDEX = {RED_MAN: 0, RED_KING: 1, WHITE_MAN: 2, WHITE_KING: 3}
_rng = random.Random(0xC4EC4E45)
ZOBRIST_PIECE = [[_rng.getrandbits(64) for _ in range(4)] for _ in range(N_SQUARES)]
ZOBRIST_SIDE = _rng.getrandbits(64)


def _sign(value: int) -> int:
    return (value > 0) - (value < 0)


class GameState:
    __slots__ = ("board", "turn", "quiet_plies", "hash", "_undo_stack")

    def __init__(self, board: Optional[List[int]] = None, turn: int = RED,
                 quiet_plies: int = 0):
        self.board = board if board is not None else self._initial_board()
        self.turn = turn
        self.quiet_plies = quiet_plies
        self._undo_stack: List[Undo] = []
        self.hash = self._compute_hash()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    @staticmethod
    def _initial_board() -> List[int]:
        board = [EMPTY] * N_SQUARES
        for r in range(ROWS):
            for c in range(COLS):
                if not is_playable(r, c):
                    continue
                if r < 3:
                    board[sq(r, c)] = WHITE_MAN
                elif r > 4:
                    board[sq(r, c)] = RED_MAN
        return board

    @classmethod
    def from_matrix(cls, matrix, turn: int = RED) -> "GameState":
        """Build a state from an 8x8 array/list-of-lists of piece values."""
        flat = [int(matrix[r][c]) for r in range(ROWS) for c in range(COLS)]
        return cls(flat, turn)

    def copy(self) -> "GameState":
        """Independent deep-ish copy. Cheap, but prefer apply/undo in search."""
        return GameState(list(self.board), self.turn, self.quiet_plies)

    # ------------------------------------------------------------------
    # Views / queries
    # ------------------------------------------------------------------
    def matrix(self) -> np.ndarray:
        """8x8 NumPy view for evaluation, rendering and reporting."""
        return np.array(self.board, dtype=np.int8).reshape(ROWS, COLS)

    def piece_at(self, row: int, col: int) -> int:
        return self.board[sq(row, col)]

    def counts(self) -> dict:
        """Material census: men and kings for each side."""
        out = {"red_men": 0, "red_kings": 0, "white_men": 0, "white_kings": 0}
        for v in self.board:
            if v == RED_MAN:
                out["red_men"] += 1
            elif v == RED_KING:
                out["red_kings"] += 1
            elif v == WHITE_MAN:
                out["white_men"] += 1
            elif v == WHITE_KING:
                out["white_kings"] += 1
        return out

    def _compute_hash(self) -> int:
        h = 0
        for s, v in enumerate(self.board):
            if v:
                h ^= ZOBRIST_PIECE[s][_PIECE_INDEX[v]]
        if self.turn == WHITE:
            h ^= ZOBRIST_SIDE
        return h

    # ------------------------------------------------------------------
    # Move generation
    # ------------------------------------------------------------------
    def legal_moves(self) -> List[Move]:
        """All legal moves for the side to move. Captures are forced."""
        captures = self._generate_captures(self.turn)
        if captures:
            return captures
        return self._generate_quiet(self.turn)

    def moves_from(self, row: int, col: int) -> List[Move]:
        """Legal moves originating at (row, col) -- used by the UI."""
        origin = sq(row, col)
        return [m for m in self.legal_moves() if m.frm == origin]

    def _generate_quiet(self, player: int) -> List[Move]:
        moves: List[Move] = []
        board = self.board
        for s, value in enumerate(board):
            if value == EMPTY or _sign(value) != player:
                continue
            for d in PIECE_DIRS[value]:
                dest = STEPS[s][d]
                if dest == -1 or board[dest] != EMPTY:
                    continue
                promo = self._promotes(value, dest)
                moves.append(Move(s, dest, (), (dest,), promo))
        return moves

    def _generate_captures(self, player: int) -> List[Move]:
        moves: List[Move] = []
        board = self.board
        for s, value in enumerate(board):
            if value == EMPTY or _sign(value) != player:
                continue
            board[s] = EMPTY          # vacate origin for the whole chain
            self._extend_chain(s, s, value, [], [], moves)
            board[s] = value
        return moves

    def _extend_chain(self, origin: int, current: int, value: int,
                      captured: list, path: list, out: list) -> bool:
        """Depth-first expansion of a jump chain. Returns True if extended."""
        board = self.board
        extended = False
        for d in PIECE_DIRS[value]:
            jump = JUMPS[current][d]
            if jump is None:
                continue
            mid, land = jump
            victim = board[mid]
            # Must be an enemy piece, not already captured this chain, and the
            # landing square must be genuinely empty.
            if victim == EMPTY or _sign(victim) == _sign(value):
                continue
            if mid in captured or board[land] != EMPTY:
                continue

            extended = True
            promo = self._promotes(value, land)
            new_value = value * 2 if promo else value

            board[land] = new_value
            captured.append(mid)
            path.append(land)

            if promo:
                # Crowning ends the turn even if more jumps look available.
                out.append(Move(origin, land, tuple(captured), tuple(path), True))
            else:
                if not self._extend_chain(origin, land, new_value, captured, path, out):
                    out.append(Move(origin, land, tuple(captured), tuple(path), False))

            board[land] = EMPTY
            captured.pop()
            path.pop()
        return extended

    @staticmethod
    def _promotes(value: int, dest: int) -> bool:
        row = dest // COLS
        if value == RED_MAN:
            return row == RED_KING_ROW
        if value == WHITE_MAN:
            return row == WHITE_KING_ROW
        return False

    # ------------------------------------------------------------------
    # Apply / undo -- no board copying
    # ------------------------------------------------------------------
    def apply(self, move: Move) -> Undo:
        board = self.board
        value = board[move.frm]
        record = Undo(
            move=move,
            moved_value=value,
            captured_values=tuple(board[s] for s in move.captures),
            prev_quiet_plies=self.quiet_plies,
            prev_hash=self.hash,
        )

        h = self.hash
        h ^= ZOBRIST_PIECE[move.frm][_PIECE_INDEX[value]]
        board[move.frm] = EMPTY

        for s in move.captures:
            h ^= ZOBRIST_PIECE[s][_PIECE_INDEX[board[s]]]
            board[s] = EMPTY

        new_value = value * 2 if move.promotion else value
        board[move.to] = new_value
        h ^= ZOBRIST_PIECE[move.to][_PIECE_INDEX[new_value]]
        h ^= ZOBRIST_SIDE

        self.hash = h
        self.turn = -self.turn

        if move.captures or abs(value) == 1:
            self.quiet_plies = 0
        else:
            self.quiet_plies += 1

        self._undo_stack.append(record)
        return record

    def undo(self) -> None:
        record = self._undo_stack.pop()
        move = record.move
        board = self.board

        board[move.to] = EMPTY
        board[move.frm] = record.moved_value
        for s, v in zip(move.captures, record.captured_values):
            board[s] = v

        self.turn = -self.turn
        self.quiet_plies = record.prev_quiet_plies
        self.hash = record.prev_hash

    # ------------------------------------------------------------------
    # Terminal detection
    # ------------------------------------------------------------------
    def is_terminal(self) -> bool:
        return self.result() != ONGOING

    def result(self) -> str:
        """ONGOING / RED_WINS / WHITE_WINS / DRAW."""
        if self.quiet_plies >= DRAW_PLY_LIMIT:
            return DRAW
        if not self.legal_moves():
            # Side to move is stalemated or wiped out -- it loses.
            return WHITE_WINS if self.turn == RED else RED_WINS
        return ONGOING

    def winner(self) -> Optional[int]:
        """RED / WHITE / None (None covers both ongoing and drawn games)."""
        res = self.result()
        if res == RED_WINS:
            return RED
        if res == WHITE_WINS:
            return WHITE
        return None

    # ------------------------------------------------------------------
    def __str__(self) -> str:
        glyph = {RED_MAN: "r", RED_KING: "R", WHITE_MAN: "w",
                 WHITE_KING: "W", EMPTY: "."}
        lines = ["  " + " ".join(str(c) for c in range(COLS))]
        for r in range(ROWS):
            row = " ".join(glyph[self.board[sq(r, c)]] for c in range(COLS))
            lines.append(f"{r} {row}")
        lines.append(f"turn: {'RED' if self.turn == RED else 'WHITE'}  "
                     f"quiet_plies: {self.quiet_plies}")
        return "\n".join(lines)


def perft(state: GameState, depth: int) -> int:
    """Count leaf nodes at `depth`. The gold-standard rules correctness test."""
    if depth == 0:
        return 1
    moves = state.legal_moves()
    if depth == 1:
        return len(moves)
    total = 0
    for m in moves:
        state.apply(m)
        total += perft(state, depth - 1)
        state.undo()
    return total
