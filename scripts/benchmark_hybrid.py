"""Phase 6 benchmark: Hybrid vs AlphaBeta and Hybrid vs MCTS.

Also reports a phase-mix histogram (how many of hybrid's moves were played
by each inner engine), which is the key evidence that the phase-switching
logic actually kicks in during real games.

Usage:
    python scripts/benchmark_hybrid.py
    python scripts/benchmark_hybrid.py --games 4
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from krosh.core.constants import DRAW, RED_WINS, WHITE_WINS
from krosh.engines import AlphaBetaEngine, HybridEngine, MCTSEngine, play_game


def _tally(result, our_colour, w, l, d):
    if result.outcome == DRAW:
        return w, l, d + 1
    our_win = RED_WINS if our_colour == "red" else WHITE_WINS
    if result.outcome == our_win:
        return w + 1, l, d
    return w, l + 1, d


def run_match(hybrid_factory, opponent_factory, games):
    """Play `games` from each side. Returns (w, l, d, phase_counter, total_ms)."""
    w = l = d = 0
    phase_counter = Counter()
    total_ms = 0.0

    for i in range(games):
        # Hybrid plays red
        hy = hybrid_factory(seed=i)
        opp = opponent_factory(seed=i + 1000)
        r = play_game(hy, opp)
        w, l, d = _tally(r, "red", w, l, d)
        total_ms += hy.total_time_ms
        # Track which delegates hy used
        for phase in _extract_phases(hy):
            phase_counter[phase] += 1

        # Hybrid plays white
        hy2 = hybrid_factory(seed=i + 500)
        opp2 = opponent_factory(seed=i + 1500)
        r = play_game(opp2, hy2)
        w, l, d = _tally(r, "white", w, l, d)
        total_ms += hy2.total_time_ms
        for phase in _extract_phases(hy2):
            phase_counter[phase] += 1

    return w, l, d, phase_counter, total_ms


def _extract_phases(hybrid: HybridEngine):
    """Very rough phase count: how many moves each inner engine played."""
    return {
        "opening": hybrid.opening_engine.moves_played,
        "midgame": hybrid.midgame_engine.moves_played,
        "endgame": hybrid.endgame_engine.moves_played,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=2,
                        help="Games from each side per matchup")
    args = parser.parse_args()

    start = time.perf_counter()

    print(f"Phase 6 benchmark -- {args.games} games from each side\n")

    # ---- Hybrid vs AlphaBeta(depth=8) ------------------------------
    print("Hybrid vs AlphaBeta(depth=8)")
    w, l, d, phases, ms = run_match(
        hybrid_factory=lambda seed: HybridEngine(
            seed=seed,
            opening_depth=5, midgame_depth=8, endgame_rollouts=2000,
        ),
        opponent_factory=lambda seed: AlphaBetaEngine(depth=8, seed=seed),
        games=args.games,
    )
    print(f"  W-L-D: {w}-{l}-{d}   total_time: {ms/1000:.1f}s")
    _print_phase_mix(phases)

    # ---- Hybrid vs MCTS(2000) --------------------------------------
    print("\nHybrid vs MCTS(2000 simulations)")
    w, l, d, phases, ms = run_match(
        hybrid_factory=lambda seed: HybridEngine(
            seed=seed,
            opening_depth=5, midgame_depth=8, endgame_rollouts=2000,
        ),
        opponent_factory=lambda seed: MCTSEngine(simulations=2000, seed=seed),
        games=args.games,
    )
    print(f"  W-L-D: {w}-{l}-{d}   total_time: {ms/1000:.1f}s")
    _print_phase_mix(phases)

    elapsed = time.perf_counter() - start
    print(f"\nTotal benchmark time: {elapsed:.1f}s")


def _print_phase_mix(phases: Counter):
    total = sum(phases.values())
    if total == 0:
        print("  (no moves recorded)")
        return
    print("  Phase mix:", end=" ")
    for name in ("opening", "midgame", "endgame"):
        n = phases[name]
        pct = 100 * n / total
        print(f"{name}={n} ({pct:.0f}%)", end="  ")
    print()


if __name__ == "__main__":
    main()
