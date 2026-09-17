"""Small benchmark: Minimax at various depths vs Greedy.

Prints a table of wins/losses/draws plus avg nodes and time per move.
Uses play_game directly so we control both sides and reset stats between games.

Usage:
    python scripts/benchmark_minimax.py
    python scripts/benchmark_minimax.py --depths 2,3,4 --games 4
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Make the project root importable when running the script directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from krosh.core.constants import DRAW, RED_WINS, WHITE_WINS
from krosh.engines import GreedyEngine, MinimaxEngine, play_game


def bench(depth: int, games: int) -> dict:
    """Play `games` from each side against Greedy at the given depth."""
    total_nodes = 0
    total_ms = 0.0
    total_moves = 0
    w = l = d = 0

    for i in range(games):
        # Minimax plays red
        mm = MinimaxEngine(depth=depth, seed=i)
        gr = GreedyEngine(seed=i + 1000)
        result = play_game(mm, gr)
        w, l, d = _tally(result, "red", w, l, d)
        total_nodes += mm.total_nodes
        total_ms += mm.total_time_ms
        total_moves += mm.moves_played

        # Minimax plays white
        mm2 = MinimaxEngine(depth=depth, seed=i + 500)
        gr2 = GreedyEngine(seed=i + 1500)
        result = play_game(gr2, mm2)
        w, l, d = _tally(result, "white", w, l, d)
        total_nodes += mm2.total_nodes
        total_ms += mm2.total_time_ms
        total_moves += mm2.moves_played

    return {
        "depth": depth,
        "w": w, "l": l, "d": d,
        "avg_nodes": total_nodes / max(total_moves, 1),
        "avg_ms": total_ms / max(total_moves, 1),
    }


def _tally(result, our_colour: str, w: int, l: int, d: int):
    if result.outcome == DRAW:
        return w, l, d + 1
    our_win = RED_WINS if our_colour == "red" else WHITE_WINS
    if result.outcome == our_win:
        return w + 1, l, d
    return w, l + 1, d


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--depths", default="2,3,4",
                        help="Comma-separated depths to test")
    parser.add_argument("--games", type=int, default=3,
                        help="Games from each side per depth")
    args = parser.parse_args()

    depths = [int(x) for x in args.depths.split(",")]

    print(f"Minimax vs Greedy -- {args.games} games each side per depth")
    print(f"{'depth':>6} {'W':>4} {'L':>4} {'D':>4} {'avg_nodes':>12} {'avg_ms':>10}")
    print("-" * 44)

    start = time.perf_counter()
    for depth in depths:
        r = bench(depth, args.games)
        print(f"{r['depth']:>6} {r['w']:>4} {r['l']:>4} {r['d']:>4} "
              f"{r['avg_nodes']:>12,.0f} {r['avg_ms']:>10.1f}")

    elapsed = time.perf_counter() - start
    print(f"\nTotal time: {elapsed:.1f}s")


if __name__ == "__main__":
    main()
