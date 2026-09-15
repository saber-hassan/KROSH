from .base import Engine, SearchResult
from .evaluate import (
    DEFAULT_WEIGHTS, WIN_SCORE, Weights, evaluate, material_balance,
)
from .greedy import GreedyEngine, RandomEngine
from .match import MatchResult, play_game, play_series

ENGINES = {
    "random": RandomEngine,
    "greedy": GreedyEngine,
}

__all__ = [
    "Engine", "SearchResult", "DEFAULT_WEIGHTS", "WIN_SCORE", "Weights",
    "evaluate", "material_balance", "GreedyEngine", "RandomEngine", "ENGINES",
    "MatchResult", "play_game", "play_series",
]
