import time
from typing import Optional, Dict, Tuple, List, Any

from krosh.core.state import GameState
from krosh.core.move import Move
from krosh.core.constants import (
    RED, WHITE, ONGOING, RED_WINS, WHITE_WINS, DRAW,
    RED_MAN, WHITE_MAN, RED_KING, WHITE_KING, ROWS,
)
from krosh.engines.base import Engine, SearchResult
from krosh.engines.evaluate import evaluate, Weights, WIN_SCORE

EXACT = 0
LOWERBOUND = 1
UPPERBOUND = 2


class AlphaBetaEngine(Engine):

    def __init__(self, depth: int = 8, weights: Optional[Weights] = None,
                 seed: Optional[int] = None, time_budget_ms: Optional[float] = 2000,
                 order_mode: str = "cheap"):
        super().__init__(seed)
        self.max_depth = depth
        # "cheap"  -- static ordering only (TT move, killers, captures, history)
        # "eval"   -- also evaluates every child while ordering. Far more
        #             accurate per node but ~6x slower overall; kept so the
        #             report can measure the trade-off.
        self.order_mode = order_mode
        self.time_budget_ms = time_budget_ms
        self.name = f"AlphaBeta (d={depth})"
        self.weights = weights or Weights()
        self.tt: Dict[Any, Tuple[int, float, int, Optional[Move]]] = {}
        self._deadline = None
        self._aborted = False
        self.nodes_visited = 0
        self.qnodes = 0
        self.max_qdepth = 8
        self.killers: Dict[int, List[Move]] = {}
        self.history: Dict[Tuple, int] = {}

    def _get_state_key(self, state: GameState):
        return (state.hash, state.quiet_plies)

    @staticmethod
    def _move_key(move: Move):
        return (move.frm, move.to, move.captures, move.path, move.promotion)

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

        self._deadline = (start + self.time_budget_ms / 1000
                          if self.time_budget_ms else None)
        self._aborted = False

        for depth in range(1, self.max_depth + 1):
            score, move = self._alpha_beta(
                state=state, depth=depth, alpha=-float("inf"),
                beta=float("inf"), root_player=root_player)
            # A search cut short by the clock is unreliable -- keep the last
            # fully completed depth instead.
            if self._aborted:
                break
            if move is not None:
                best_move = move
                best_score = score
                completed_depth = depth
            if self._deadline and time.perf_counter() >= self._deadline:
                break

        if best_move is None:
            legal = state.legal_moves()
            if legal:
                best_move = legal[0]

        elapsed_ms = (time.perf_counter() - start) * 1000
        return SearchResult(
            move=best_move, score=best_score, nodes=self.nodes_visited,
            time_ms=elapsed_ms, depth=completed_depth,
            extra={"qnodes": self.qnodes, "tt_size": len(self.tt),
                   "ordering": self.order_mode,
                   "aborted": self._aborted})

    def _evaluate(self, state: GameState, player: int) -> float:
        score = evaluate(state, player, self.weights)
        original_turn = state.turn
        current_moves = state.legal_moves()
        current_captures = [m for m in current_moves if m.is_capture]
        current_capture_value = sum(len(m.captures) for m in current_captures)
        state.turn = -original_turn
        opponent_moves = state.legal_moves()
        opponent_captures = [m for m in opponent_moves if m.is_capture]
        opponent_capture_value = sum(len(m.captures) for m in opponent_captures)
        state.turn = original_turn

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

        score += (own_moves - enemy_moves) * 5
        score += (own_captures - enemy_captures) * 35

        promotion_score = 0
        for s, piece in enumerate(state.board):
            if piece == 0:
                continue
            row = s // 8
            if piece == RED_MAN:
                distance = row
                value = max(0, 7 - distance)
                promotion_score += value * 8 if player == RED else -value * 8
            elif piece == WHITE_MAN:
                distance = 7 - row
                value = max(0, 7 - distance)
                promotion_score += value * 8 if player == WHITE else -value * 8
        score += promotion_score

        for s, piece in enumerate(state.board):
            if piece not in (RED_KING, WHITE_KING):
                continue
            row = s // 8
            col = s % 8
            center_distance = abs(3.5 - row) + abs(3.5 - col)
            activity = int(12 - center_distance * 2)
            if piece == RED_KING:
                score += activity if player == RED else -activity
            else:
                score += activity if player == WHITE else -activity
        return score

    def _order_moves(self, state, moves, tt_move, depth, root_player):
        if self.order_mode == "cheap":
            return self._order_moves_cheap(moves, tt_move, depth)
        return self._order_moves_eval(state, moves, tt_move, depth, root_player)

    def _order_moves_cheap(self, moves, tt_move, depth):
        """Static ordering -- no child evaluation, no move generation.

        Captures are compulsory in checkers, so when any capture exists it is
        the *only* legal move type; the capture bonuses then only separate
        chains by length, which is exactly what we want.
        """
        killers = self.killers.get(depth, ())
        history = self.history

        def priority(move):
            score = 0
            if tt_move is not None and move == tt_move:
                score += 10_000_000
            if move in killers:
                score += 2_000_000
            if move.captures:
                score += 1_000_000 + len(move.captures) * 150_000
            if move.promotion:
                score += 500_000
            score += history.get(self._move_key(move), 0)
            return score

        return sorted(moves, key=priority, reverse=True)

    def _order_moves_eval(self, state, moves, tt_move, depth, root_player):
        scored = []
        killers = self.killers.get(depth, [])
        for move in moves:
            priority = 0
            if tt_move is not None and move == tt_move:
                priority += 10_000_000
            if move in killers:
                priority += 2_000_000
            if move.is_capture:
                priority += 1_000_000
                priority += len(move.captures) * 150_000
            if move.promotion:
                priority += 500_000
            priority += self.history.get(self._move_key(move), 0)

            state.apply(move)
            child_result = state.result()
            if child_result == DRAW:
                priority += 0
            elif (child_result == RED_WINS and root_player == RED) or \
                 (child_result == WHITE_WINS and root_player == WHITE):
                priority += WIN_SCORE
            elif child_result in (RED_WINS, WHITE_WINS):
                priority -= WIN_SCORE
            else:
                priority += int(self._evaluate(state, root_player))
            state.undo()
            scored.append((priority, move))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [move for _, move in scored]

    def _terminal_score(self, result, player, depth):
        if result == DRAW:
            return 0
        player_won = (result == RED_WINS and player == RED) or \
                     (result == WHITE_WINS and player == WHITE)
        return WIN_SCORE + depth if player_won else -WIN_SCORE - depth

    def _alpha_beta(self, state, depth, alpha, beta, root_player):
        self.nodes_visited += 1
        if self._deadline is not None and (self.nodes_visited & 1023) == 0:
            if time.perf_counter() >= self._deadline:
                self._aborted = True
                return self._evaluate(state, root_player), None
        alpha_original = alpha
        beta_original = beta

        result = state.result()
        if result != ONGOING:
            return self._terminal_score(result, root_player, depth), None

        if depth <= 0:
            moves = state.legal_moves()
            if any(m.is_capture for m in moves):
                return self._quiescence(state, alpha, beta, root_player,
                                        self.max_qdepth)
            return self._evaluate(state, root_player), None

        key = self._get_state_key(state)
        entry = self.tt.get(key)
        tt_move = None
        if entry is not None:
            tt_depth, tt_score, tt_flag, tt_move = entry
            if tt_depth >= depth:
                if tt_flag == EXACT:
                    return tt_score, tt_move
                if tt_flag == LOWERBOUND:
                    alpha = max(alpha, tt_score)
                elif tt_flag == UPPERBOUND:
                    beta = min(beta, tt_score)
                if alpha >= beta:
                    return tt_score, tt_move

        moves = state.legal_moves()
        if not moves:
            return self._terminal_score(
                RED_WINS if state.turn == WHITE else WHITE_WINS,
                root_player, depth), None

        maximizing = (state.turn == root_player)
        moves = self._order_moves(state, moves, tt_move, depth, root_player)
        best_move = None

        if maximizing:
            value = -float("inf")
            for move in moves:
                state.apply(move)
                child_value, _ = self._alpha_beta(state, depth - 1, alpha, beta,
                                                  root_player)
                state.undo()
                if child_value > value:
                    value = child_value
                    best_move = move
                alpha = max(alpha, value)
                if alpha >= beta:
                    self._record_killer(depth, move)
                    self._record_history(move, depth)
                    break
        else:
            value = float("inf")
            for move in moves:
                state.apply(move)
                child_value, _ = self._alpha_beta(state, depth - 1, alpha, beta,
                                                  root_player)
                state.undo()
                if child_value < value:
                    value = child_value
                    best_move = move
                beta = min(beta, value)
                if alpha >= beta:
                    self._record_killer(depth, move)
                    self._record_history(move, depth)
                    break

        if value <= alpha_original:
            flag = UPPERBOUND
        elif value >= beta_original:
            flag = LOWERBOUND
        else:
            flag = EXACT
        self.tt[key] = (depth, value, flag, best_move)
        return value, best_move

    def _quiescence(self, state, alpha, beta, root_player, qdepth):
        self.nodes_visited += 1
        self.qnodes += 1
        result = state.result()
        if result != ONGOING:
            return self._terminal_score(result, root_player, qdepth), None
        if qdepth <= 0:
            return self._evaluate(state, root_player), None

        moves = state.legal_moves()
        captures = [m for m in moves if m.is_capture]
        if not captures:
            return self._evaluate(state, root_player), None

        maximizing = (state.turn == root_player)
        captures = self._order_moves(state, captures, None, qdepth, root_player)
        best_move = None

        if maximizing:
            value = -float("inf")
            for move in captures:
                state.apply(move)
                child_value, _ = self._quiescence(state, alpha, beta,
                                                  root_player, qdepth - 1)
                state.undo()
                if child_value > value:
                    value = child_value
                    best_move = move
                alpha = max(alpha, value)
                if alpha >= beta:
                    break
        else:
            value = float("inf")
            for move in captures:
                state.apply(move)
                child_value, _ = self._quiescence(state, alpha, beta,
                                                  root_player, qdepth - 1)
                state.undo()
                if child_value < value:
                    value = child_value
                    best_move = move
                beta = min(beta, value)
                if alpha >= beta:
                    break
        return value, best_move

    def _record_killer(self, depth, move):
        killers = self.killers.setdefault(depth, [])
        if move in killers:
            return
        killers.insert(0, move)
        del killers[2:]

    def _record_history(self, move, depth):
        key = self._move_key(move)
        self.history[key] = self.history.get(key, 0) + depth * depth
