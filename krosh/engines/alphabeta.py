import time
from typing import Optional, Dict, Tuple, List, Any

from krosh.core.state import GameState
from krosh.core.move import Move
from krosh.core.constants import (
    RED,
    WHITE,
    ONGOING,
    RED_WINS,
    WHITE_WINS,
    DRAW,
    RED_MAN,
    WHITE_MAN,
    RED_KING,
    WHITE_KING,
    ROWS,
)
from krosh.engines.base import Engine, SearchResult
from krosh.engines.evaluate import evaluate, Weights, WIN_SCORE


EXACT = 0
LOWERBOUND = 1
UPPERBOUND = 2


class AlphaBetaEngine(Engine):

    def __init__(
        self,
        depth: int = 10,
        weights: Optional[Weights] = None,
        seed: Optional[int] = None,
    ):
        super().__init__(seed)

        self.max_depth = depth
        self.name = f"AlphaBeta (d={depth})"
        self.weights = weights or Weights()

        self.tt: Dict[
            Any,
            Tuple[int, float, int, Optional[Move]]
        ] = {}

        self.nodes_visited = 0
        self.qnodes = 0

        # Tactical capture extension
        self.max_qdepth = 8

        # Killer moves
        self.killers: Dict[int, List[Move]] = {}

        # History heuristic
        self.history: Dict[Tuple, int] = {}

    # ==========================================================
    # STATE KEY
    # ==========================================================

    def _get_state_key(self, state: GameState):

        # hash already contains board + side to move.
        # quiet_plies is also important for draw detection.
        return (
            state.hash,
            state.quiet_plies,
        )

    # ==========================================================
    # MOVE KEY
    # ==========================================================

    @staticmethod
    def _move_key(move: Move):

        return (
            move.frm,
            move.to,
            move.captures,
            move.path,
            move.promotion,
        )

    # ==========================================================
    # SEARCH
    # ==========================================================

    def search(self, state: GameState) -> SearchResult:

        start = time.perf_counter()

        self.nodes_visited = 0
        self.qnodes = 0

        self.tt.clear()
        self.killers.clear()
        self.history.clear()

        root_player = state.turn

        best_move = None
        best_score = -float("inf")
        completed_depth = 0

        # ------------------------------------------------------
        # Iterative deepening
        # ------------------------------------------------------

        for depth in range(1, self.max_depth + 1):

            score, move = self._alpha_beta(
                state=state,
                depth=depth,
                alpha=-float("inf"),
                beta=float("inf"),
                root_player=root_player,
            )

            if move is not None:
                best_move = move
                best_score = score
                completed_depth = depth

        # ------------------------------------------------------
        # Safety fallback
        # ------------------------------------------------------

        if best_move is None:

            legal = state.legal_moves()

            if legal:
                best_move = legal[0]

        elapsed_ms = (
            time.perf_counter() - start
        ) * 1000

        return SearchResult(
            move=best_move,
            score=best_score,
            nodes=self.nodes_visited,
            time_ms=elapsed_ms,
            depth=completed_depth,
            extra={
                "qnodes": self.qnodes,
                "tt_size": len(self.tt),
            },
        )

    # ==========================================================
    # STRONG STATIC EVALUATION
    # ==========================================================

    def _evaluate(self, state: GameState, player: int) -> float:

        # Original project's evaluation
        score = evaluate(
            state,
            player,
            self.weights,
        )

        # ------------------------------------------------------
        # Get moves for both players
        # ------------------------------------------------------

        original_turn = state.turn

        current_moves = state.legal_moves()

        current_captures = [
            m for m in current_moves
            if m.is_capture
        ]

        current_capture_value = sum(
            len(m.captures)
            for m in current_captures
        )

        state.turn = -original_turn

        opponent_moves = state.legal_moves()

        opponent_captures = [
            m for m in opponent_moves
            if m.is_capture
        ]

        opponent_capture_value = sum(
            len(m.captures)
            for m in opponent_captures
        )

        state.turn = original_turn

        # ------------------------------------------------------
        # Convert to player's perspective
        # ------------------------------------------------------

        if original_turn == player:

            own_moves = len(current_moves)
            enemy_moves = len(opponent_moves)

            own_captures = current_capture_value
            enemy_captures = opponent_capture_value

        else:

            own_moves = len(opponent_moves)
            enemy_moves = len(current_moves)

            own_captures = opponent_capture_value
            enemy_captures = current_capture_value

        # ------------------------------------------------------
        # 1. Mobility
        # ------------------------------------------------------

        score += (
            own_moves - enemy_moves
        ) * 5

        # ------------------------------------------------------
        # 2. Capture pressure
        # ------------------------------------------------------

        score += (
            own_captures - enemy_captures
        ) * 35

        # ------------------------------------------------------
        # 3. Promotion pressure
        # ------------------------------------------------------

        promotion_score = 0

        for s, piece in enumerate(state.board):

            if piece == 0:
                continue

            row = s // 8

            if piece == RED_MAN:

                distance = row

                value = max(
                    0,
                    7 - distance
                )

                if player == RED:
                    promotion_score += value * 8
                else:
                    promotion_score -= value * 8

            elif piece == WHITE_MAN:

                distance = 7 - row

                value = max(
                    0,
                    7 - distance
                )

                if player == WHITE:
                    promotion_score += value * 8
                else:
                    promotion_score -= value * 8

        score += promotion_score

        # ------------------------------------------------------
        # 4. King activity
        # ------------------------------------------------------

        for s, piece in enumerate(state.board):

            if piece not in (RED_KING, WHITE_KING):
                continue

            row = s // 8
            col = s % 8

            center_distance = abs(3.5 - row) + abs(3.5 - col)

            activity = int(
                12 - center_distance * 2
            )

            if piece == RED_KING:

                if player == RED:
                    score += activity
                else:
                    score -= activity

            else:

                if player == WHITE:
                    score += activity
                else:
                    score -= activity

        return score

    # ==========================================================
    # MOVE ORDERING
    # ==========================================================

    def _order_moves(
        self,
        state: GameState,
        moves: List[Move],
        tt_move: Optional[Move],
        depth: int,
        root_player: int,
    ) -> List[Move]:

        scored = []

        killers = self.killers.get(depth, [])

        for move in moves:

            priority = 0

            # --------------------------------------------------
            # TT move
            # --------------------------------------------------

            if tt_move is not None and move == tt_move:
                priority += 10_000_000

            # --------------------------------------------------
            # Killer move
            # --------------------------------------------------

            if move in killers:
                priority += 2_000_000

            # --------------------------------------------------
            # Capture
            # --------------------------------------------------

            if move.is_capture:

                priority += 1_000_000

                # Multiple captures are much more valuable
                priority += (
                    len(move.captures) * 150_000
                )

            # --------------------------------------------------
            # Promotion
            # --------------------------------------------------

            if move.promotion:
                priority += 500_000

            # --------------------------------------------------
            # History
            # --------------------------------------------------

            priority += self.history.get(
                self._move_key(move),
                0
            )

            # --------------------------------------------------
            # Quick child evaluation
            # --------------------------------------------------

            state.apply(move)

            child_result = state.result()

            if child_result == DRAW:

                priority += 0

            elif (
                child_result == RED_WINS
                and root_player == RED
            ) or (
                child_result == WHITE_WINS
                and root_player == WHITE
            ):

                priority += WIN_SCORE

            elif child_result in (
                RED_WINS,
                WHITE_WINS,
            ):

                priority -= WIN_SCORE

            else:

                priority += int(
                    self._evaluate(
                        state,
                        root_player,
                    )
                )

            state.undo()

            scored.append(
                (priority, move)
            )

        scored.sort(
            key=lambda x: x[0],
            reverse=True
        )

        return [
            move
            for _, move in scored
        ]

    # ==========================================================
    # TERMINAL SCORE
    # ==========================================================

    def _terminal_score(
        self,
        result: str,
        player: int,
        depth: int,
    ) -> float:

        if result == DRAW:
            return 0

        player_won = (
            result == RED_WINS
            and player == RED
        ) or (
            result == WHITE_WINS
            and player == WHITE
        )

        if player_won:

            # Prefer faster wins
            return WIN_SCORE + depth

        # Prefer delaying a loss
        return -WIN_SCORE - depth

    # ==========================================================
    # ALPHA-BETA
    # ==========================================================

    def _alpha_beta(
        self,
        state: GameState,
        depth: int,
        alpha: float,
        beta: float,
        root_player: int,
    ) -> Tuple[float, Optional[Move]]:

        self.nodes_visited += 1

        alpha_original = alpha
        beta_original = beta

        # ------------------------------------------------------
        # Terminal
        # ------------------------------------------------------

        result = state.result()

        if result != ONGOING:

            return (
                self._terminal_score(
                    result,
                    root_player,
                    depth,
                ),
                None,
            )

        # ------------------------------------------------------
        # Depth reached
        # ------------------------------------------------------

        if depth <= 0:

            # Tactical extension if captures exist
            moves = state.legal_moves()

            if any(
                m.is_capture
                for m in moves
            ):

                return self._quiescence(
                    state,
                    alpha,
                    beta,
                    root_player,
                    self.max_qdepth,
                )

            return (
                self._evaluate(
                    state,
                    root_player,
                ),
                None,
            )

        # ------------------------------------------------------
        # Transposition table
        # ------------------------------------------------------

        key = self._get_state_key(state)

        entry = self.tt.get(key)

        tt_move = None

        if entry is not None:

            tt_depth, tt_score, tt_flag, tt_move = entry

            if tt_depth >= depth:

                if tt_flag == EXACT:
                    return tt_score, tt_move

                if tt_flag == LOWERBOUND:
                    alpha = max(
                        alpha,
                        tt_score
                    )

                elif tt_flag == UPPERBOUND:
                    beta = min(
                        beta,
                        tt_score
                    )

                if alpha >= beta:
                    return tt_score, tt_move

        # ------------------------------------------------------
        # Legal moves
        # ------------------------------------------------------

        moves = state.legal_moves()

        if not moves:

            return (
                self._terminal_score(
                    RED_WINS
                    if state.turn == WHITE
                    else WHITE_WINS,
                    root_player,
                    depth,
                ),
                None,
            )

        # ------------------------------------------------------
        # MAX / MIN
        # ------------------------------------------------------

        maximizing = (
            state.turn == root_player
        )

        moves = self._order_moves(
            state,
            moves,
            tt_move,
            depth,
            root_player,
        )

        best_move = None

        # ======================================================
        # MAX
        # ======================================================

        if maximizing:

            value = -float("inf")

            for move in moves:

                state.apply(move)

                child_value, _ = self._alpha_beta(
                    state,
                    depth - 1,
                    alpha,
                    beta,
                    root_player,
                )

                state.undo()

                if child_value > value:

                    value = child_value
                    best_move = move

                alpha = max(
                    alpha,
                    value
                )

                if alpha >= beta:

                    self._record_killer(
                        depth,
                        move
                    )

                    self._record_history(
                        move,
                        depth
                    )

                    break

        # ======================================================
        # MIN
        # ======================================================

        else:

            value = float("inf")

            for move in moves:

                state.apply(move)

                child_value, _ = self._alpha_beta(
                    state,
                    depth - 1,
                    alpha,
                    beta,
                    root_player,
                )

                state.undo()

                if child_value < value:

                    value = child_value
                    best_move = move

                beta = min(
                    beta,
                    value
                )

                if alpha >= beta:

                    self._record_killer(
                        depth,
                        move
                    )

                    self._record_history(
                        move,
                        depth
                    )

                    break

        # ------------------------------------------------------
        # TT flag
        # ------------------------------------------------------

        if value <= alpha_original:

            flag = UPPERBOUND

        elif value >= beta_original:

            flag = LOWERBOUND

        else:

            flag = EXACT

        self.tt[key] = (
            depth,
            value,
            flag,
            best_move,
        )

        return value, best_move

    # ==========================================================
    # QUIESCENCE SEARCH
    # ==========================================================

    def _quiescence(
        self,
        state: GameState,
        alpha: float,
        beta: float,
        root_player: int,
        qdepth: int,
    ) -> Tuple[float, Optional[Move]]:

        self.nodes_visited += 1
        self.qnodes += 1

        # ------------------------------------------------------
        # Terminal
        # ------------------------------------------------------

        result = state.result()

        if result != ONGOING:

            return (
                self._terminal_score(
                    result,
                    root_player,
                    qdepth,
                ),
                None,
            )

        # ------------------------------------------------------
        # Stop
        # ------------------------------------------------------

        if qdepth <= 0:

            return (
                self._evaluate(
                    state,
                    root_player,
                ),
                None,
            )

        moves = state.legal_moves()

        captures = [
            m
            for m in moves
            if m.is_capture
        ]

        # No tactical capture
        if not captures:

            return (
                self._evaluate(
                    state,
                    root_player,
                ),
                None,
            )

        maximizing = (
            state.turn == root_player
        )

        captures = self._order_moves(
            state,
            captures,
            None,
            qdepth,
            root_player,
        )

        best_move = None

        # ======================================================
        # MAX
        # ======================================================

        if maximizing:

            value = -float("inf")

            for move in captures:

                state.apply(move)

                child_value, _ = self._quiescence(
                    state,
                    alpha,
                    beta,
                    root_player,
                    qdepth - 1,
                )

                state.undo()

                if child_value > value:

                    value = child_value
                    best_move = move

                alpha = max(
                    alpha,
                    value
                )

                if alpha >= beta:
                    break

        # ======================================================
        # MIN
        # ======================================================

        else:

            value = float("inf")

            for move in captures:

                state.apply(move)

                child_value, _ = self._quiescence(
                    state,
                    alpha,
                    beta,
                    root_player,
                    qdepth - 1,
                )

                state.undo()

                if child_value < value:

                    value = child_value
                    best_move = move

                beta = min(
                    beta,
                    value
                )

                if alpha >= beta:
                    break

        return value, best_move

    # ==========================================================
    # KILLER MOVES
    # ==========================================================

    def _record_killer(
        self,
        depth: int,
        move: Move,
    ):

        killers = self.killers.setdefault(
            depth,
            []
        )

        if move in killers:
            return

        killers.insert(0, move)

        # Keep only 2 killer moves
        del killers[2:]

    # ==========================================================
    # HISTORY HEURISTIC
    # ==========================================================

    def _record_history(
        self,
        move: Move,
        depth: int,
    ):

        key = self._move_key(move)

        self.history[key] = (
            self.history.get(key, 0)
            + depth * depth
        )