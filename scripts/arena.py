"""Engine arena -- round-robin benchmark across all registered engines.

    python scripts/arena.py --games 100
    python scripts/arena.py --games 40 --engines greedy random --csv out.csv

Colours alternate every game so neither engine keeps the first-move advantage.
Scores use the usual convention: a win is 1, a draw 0.5.
"""

import argparse
import csv
import itertools
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from krosh.engines import ENGINES, play_series


def build(name, seed):
    return ENGINES[name](seed=seed)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=60,
                    help="games per pairing (split evenly between colours)")
    ap.add_argument("--engines", nargs="+", default=list(ENGINES),
                    choices=list(ENGINES))
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--csv", type=str, default=None)
    args = ap.parse_args()

    if len(args.engines) < 2:
        ap.error("need at least two engines to run a round robin")

    rows = []
    print(f"Round robin: {args.games} games per pairing\n")
    header = f"{'matchup':<26}{'W':>5}{'L':>5}{'D':>5}{'score':>8}{'sec':>8}"
    print(header)
    print("-" * len(header))

    for a_name, b_name in itertools.combinations(args.engines, 2):
        a, b = build(a_name, args.seed), build(b_name, args.seed + 1)
        start = time.perf_counter()
        tally = play_series(a, b, games=args.games)
        elapsed = time.perf_counter() - start

        label = f"{a_name} vs {b_name}"
        print(f"{label:<26}{tally['a_wins']:>5}{tally['b_wins']:>5}"
              f"{tally['draws']:>5}{tally['a_score']:>8.1%}{elapsed:>8.1f}")

        rows.append({
            "engine_a": a_name, "engine_b": b_name, "games": args.games,
            "a_wins": tally["a_wins"], "b_wins": tally["b_wins"],
            "draws": tally["draws"], "a_score": round(tally["a_score"], 4),
            "avg_plies": round(sum(g.plies for g in tally["games"]) / args.games, 1),
            "seconds": round(elapsed, 2),
        })

    print("\nPer-engine search cost (last pairing played):")
    cost_header = f"{'engine':<12}{'avg nodes':>12}{'avg ms':>10}{'nodes/s':>14}"
    print(cost_header)
    print("-" * len(cost_header))
    seen = set()
    for name in args.engines:
        if name in seen:
            continue
        seen.add(name)
        engine = build(name, args.seed)
        from krosh.core import GameState
        state = GameState()
        for _ in range(30):
            moves = state.legal_moves()
            if not moves:
                break
            result = engine.choose(state)
            state.apply(result.move)
        s = engine.summary()
        print(f"{name:<12}{s['avg_nodes']:>12,.1f}{s['avg_ms']:>10.3f}"
              f"{s['nodes_per_sec']:>14,.0f}")

    if args.csv:
        with open(args.csv, "w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nwrote {args.csv}")


if __name__ == "__main__":
    main()
