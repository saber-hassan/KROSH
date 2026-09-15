"""Perft benchmark: proves rule correctness and measures raw generation speed.

    python scripts/perft_bench.py --depth 8

The node counts are the published reference values for English draughts, so a
mismatch means a rules bug -- not a performance problem.
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from krosh.core import GameState, perft

REFERENCE = [1, 7, 49, 302, 1469, 7361, 36768, 179740, 845931, 3963680]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--depth", type=int, default=8)
    args = ap.parse_args()

    state = GameState()
    print(f"{'depth':>5} {'nodes':>12} {'seconds':>9} {'nodes/s':>12}  check")
    for depth in range(1, args.depth + 1):
        start = time.perf_counter()
        nodes = perft(state, depth)
        elapsed = time.perf_counter() - start
        rate = nodes / elapsed if elapsed else float("inf")
        if depth < len(REFERENCE):
            check = "OK" if nodes == REFERENCE[depth] else f"MISMATCH (want {REFERENCE[depth]})"
        else:
            check = "-"
        print(f"{depth:>5} {nodes:>12,} {elapsed:>9.3f} {rate:>12,.0f}  {check}")


if __name__ == "__main__":
    main()
