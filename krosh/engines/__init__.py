from .base import Engine, SearchResult
from .evaluate import (
    DEFAULT_WEIGHTS, WIN_SCORE, Weights, evaluate, material_balance,
)
from .greedy import GreedyEngine, RandomEngine
from .minimax import MinimaxEngine
from .match import MatchResult, play_game, play_series
from .alphabeta import AlphaBetaEngine

ENGINES = {
    "random": RandomEngine,
    "greedy": GreedyEngine,
<<<<<<< Updated upstream
    "minimax": MinimaxEngine,
=======
    "alphabeta": AlphaBetaEngine,
>>>>>>> Stashed changes
}

__all__ = [
    "Engine", "SearchResult", "DEFAULT_WEIGHTS", "WIN_SCORE", "Weights",
<<<<<<< Updated upstream
    "evaluate", "material_balance", "GreedyEngine", "RandomEngine", "MinimaxEngine", "ENGINES",
    "MatchResult", "play_game", "play_series",
=======
    "evaluate", "material_balance", "GreedyEngine", "RandomEngine", "ENGINES",
    "MatchResult", "play_game", "play_series","AlphaBetaEngine",
>>>>>>> Stashed changes
]
