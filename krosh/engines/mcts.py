import math
import random
import time

from .base import Engine, SearchResult


class MCTSNode:
    def __init__(self, state, parent=None, move=None):
        self.state = state
        self.parent = parent
        self.move = move

        self.children = []
        self.visits = 0
        self.wins = 0.0

    def is_fully_expanded(self, legal_moves):
        return len(self.children) == len(legal_moves)

    def best_child(self, c_param=1.414):
        if not self.children:
            return None

        choices_weights = []

        for child in self.children:

            # Unvisited node gets priority
            if child.visits == 0:
                choices_weights.append(float("inf"))
                continue

            exploitation = child.wins / child.visits

            exploration = c_param * math.sqrt(
                (2 * math.log(max(1, self.visits)))
                / child.visits
            )

            choices_weights.append(
                exploitation + exploration
            )

        return self.children[
            choices_weights.index(max(choices_weights))
        ]


class MCTSEngine(Engine):

    name = "Monte Carlo"

    def __init__(self, simulations=200, seed=None, **kwargs):
        super().__init__(seed)

        self.simulations = simulations

        if seed is not None:
            random.seed(seed)

    def search(self, state):
        start_time = time.perf_counter()

        nodes_searched = 0

        # Root node
        root = MCTSNode(
            state=state.copy()
        )

        # ======================================================
        # MCTS ITERATIONS
        # ======================================================

        for _ in range(self.simulations):

            node = root

            # ==================================================
            # 1. SELECTION
            # ==================================================

            while not node.state.is_terminal():

                legal_moves = node.state.legal_moves()

                if (
                    not legal_moves
                    or not node.is_fully_expanded(legal_moves)
                    or not node.children
                ):
                    break

                node = node.best_child()

                if node is None:
                    break

            # ==================================================
            # 2. EXPANSION
            # ==================================================

            legal_moves = node.state.legal_moves()

            if (
                not node.state.is_terminal()
                and legal_moves
            ):

                tried_moves = [
                    child.move
                    for child in node.children
                ]

                untried_moves = [
                    move
                    for move in legal_moves
                    if move not in tried_moves
                ]

                if untried_moves:

                    # Select an unexplored move
                    move = random.choice(
                        untried_moves
                    )

                    # Create next state
                    next_state = node.state.copy()

                    next_state.apply(move)

                    # Create child node
                    child_node = MCTSNode(
                        state=next_state,
                        parent=node,
                        move=move
                    )

                    node.children.append(
                        child_node
                    )

                    node = child_node

            # ==================================================
            # 3. SIMULATION / ROLLOUT
            # ==================================================

            sim_state = node.state.copy()

            nodes_searched += 1

            rollout_depth = 0
            max_rollout_depth = 20

            while (
                not sim_state.is_terminal()
                and rollout_depth < max_rollout_depth
            ):

                moves = sim_state.legal_moves()

                if not moves:
                    break

                # Random move during simulation
                move = random.choice(moves)

                sim_state.apply(move)

                rollout_depth += 1

            # ==================================================
            # 4. BACKPROPAGATION
            # ==================================================

            winner = sim_state.winner()

            # Reward from root player's perspective
            if winner == state.turn:
                reward = 1.0

            elif winner is None:
                reward = 0.5

            else:
                reward = 0.0

            # Update current node and all parents
            while node is not None:

                node.visits += 1
                node.wins += reward

                node = node.parent

        # ======================================================
        # CHOOSE BEST MOVE
        # ======================================================

        if root.children:

            # c_param = 0
            # means choose based on exploitation
            best_child = root.best_child(
                c_param=0.0
            )

            if best_child is not None:
                best_move = best_child.move
            else:
                best_move = None

        else:
            best_move = None

        # ======================================================
        # FALLBACK
        # ======================================================

        if best_move is None:

            legal = state.legal_moves()

            if legal:
                best_move = legal[0]

        # ======================================================
        # SEARCH STATISTICS
        # ======================================================

        elapsed_ms = (
            time.perf_counter() - start_time
        ) * 1000

        # ======================================================
        # RETURN RESULT
        # ======================================================

        return SearchResult(
            move=best_move,
            score=0,
            nodes=nodes_searched,
            time_ms=elapsed_ms,
            depth=self.simulations,
            extra={
                "simulations": self.simulations,
            },
        )