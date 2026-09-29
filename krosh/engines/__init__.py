from .base import Engine, SearchResult
from .evaluate import (
    DEFAULT_WEIGHTS, WIN_SCORE, Weights, evaluate, material_balance,
)
from .greedy import GreedyEngine, RandomEngine
from .minimax import MinimaxEngine
from .alphabeta import AlphaBetaEngine
from .mcts import MCTSEngine
from .hybrid import HybridEngine
from .match import MatchResult, play_game, play_series

ENGINES = {
    "greedy": GreedyEngine,
    "minimax": MinimaxEngine,
    "alphabeta": AlphaBetaEngine,
    "mcts": MCTSEngine,
    "hybrid": HybridEngine,
}

__all__ = [
    "Engine", "SearchResult", "DEFAULT_WEIGHTS", "WIN_SCORE", "Weights",
    "evaluate", "material_balance", "GreedyEngine", "RandomEngine",
    "MinimaxEngine", "AlphaBetaEngine", "MCTSEngine", "HybridEngine", "ENGINES",
    "MatchResult", "play_game", "play_series",
]