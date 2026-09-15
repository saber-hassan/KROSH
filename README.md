# KROSH

Checkers with four classical AI opponents — Greedy, Minimax, Alpha-Beta and MCTS.
CSE 3811 | AI Lab | Section A | Group 5

## Layout

```
krosh/
  core/              pure rules engine — no Pygame, no I/O
    constants.py     geometry, piece encoding, precomputed step/jump tables
    move.py          Move (immutable) and Undo records
    state.py         GameState: move generation, apply/undo, Zobrist, terminals
  engines/
    base.py          Engine interface + SearchResult stat payload
    evaluate.py      the single shared heuristic, with tunable Weights
    greedy.py        GreedyEngine (one-ply) and RandomEngine (control)
    match.py         headless play_game / play_series drivers
  app/
    session.py       GameSession -- turn logic, selection, AI dispatch
  web/
    server.py        Flask JSON API over GameSession
    templates/       page shell
    static/          stylesheet and browser client
  ui/
    theme.py         palette, geometry, fonts, vector crown
    board_view.py    board + piece rendering, click mapping
    sidebar.py       status, material, live search stats, move history
    menu.py          mode / opponent / colour selection
    app.py           main loop, threaded AI search
main.py              desktop entry point
run_web.py           browser entry point
tests/               Pytest suite
scripts/             benchmarks and report generation
```

The core is deliberately isolated from Pygame. Engines search it by mutating a
single board in place through `apply` / `undo` — no `deepcopy` anywhere — which
is what makes depth-8 Minimax and large MCTS budgets feasible.

## Setup

On Arch and other PEP 668 distros, use a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Then:

```bash
python run_web.py                   # play in a browser at 127.0.0.1:5000
python main.py                      # play in a desktop window
python -m pytest tests/ -q          # 104 tests
python scripts/perft_bench.py --depth 8
python scripts/arena.py --games 100
```

## Two frontends, one backend

```
web/  (Flask + browser)  ─┐
                          ├─>  app/GameSession  ->  engines/  ->  core/GameState
ui/   (Pygame desktop)   ─┘
```

Both frontends are thin. Every rule decision and every search runs in Python
behind `GameSession`, so the browser client never decides what is legal — it
draws the state it is given and posts clicks back. The engines the browser
plays against are the same objects the benchmark suite runs.

The browser build is the one to demo: it needs no display server, runs from any
machine on the network with `--host 0.0.0.0`, and the search telemetry updates
in place after each engine move.

Games live in server memory keyed by an id the browser holds, so restarting the
server clears any game in progress. That is deliberate — it keeps the backend
dependency-free, with no database for a single-player desktop game.

### API

| method | route | purpose |
|--------|-------|---------|
| `POST` | `/api/game` | start a game, returns `game_id` |
| `GET` | `/api/game/<id>` | current state |
| `POST` | `/api/game/<id>/click` | send a board click |
| `POST` | `/api/game/<id>/ai` | let the engine move, returns search stats |
| `POST` | `/api/game/<id>/undo` | roll back to the player |
| `POST` | `/api/game/<id>/reset` | restart the position |

## Playing

Pick a mode on the menu: **Human vs AI** (choose the opponent engine and your
colour) or **Human vs Human** for two players at one keyboard.

Click a piece to select it; green dots mark every legal destination. Captures
are mandatory, so a piece with no legal move says so instead of selecting.
A multi-jump is played by clicking **each landing square in turn** — the piece
shows as a ghost mid-chain — which keeps two chains that share a first hop
unambiguous.

| key | action |
|-----|--------|
| `U` | undo (rolls back the AI reply too, so you are always on move) |
| `R` | restart |
| `ESC` | back to menu |
| `Q` | quit |

The sidebar shows the live search payload from the last AI move: chosen move,
score, depth, nodes visited, elapsed time and nodes/second.

## Architecture

```
ui/  (Pygame)  ->  app/GameSession  ->  engines/  ->  core/GameState
```

`GameSession` is the frontend-agnostic controller. The UI never touches
`GameState` directly — it sends clicks in and reads back highlights, a status
line and a `SearchResult`. That is why the entire turn layer is unit-tested
without opening a window, and why swapping in a web frontend later would touch
only `ui/`.

The AI search runs on a worker thread. A deep Alpha-Beta search will take
seconds, and blocking the main loop would make the window look crashed, so the
app keeps rendering at 60 FPS while the engine thinks.

## Board representation

64-element flat list, index `row * 8 + col`. Piece values encode owner in the
sign and rank in the magnitude:

| value | meaning |
|-------|---------|
| `+2`  | RED king |
| `+1`  | RED man — moves toward row 0, moves first |
| `0`   | empty |
| `-1`  | WHITE man — moves toward row 7 |
| `-2`  | WHITE king |

A flat list is used internally because scalar access in the search hot loop is
roughly twice as fast as either nested lists or NumPy element access. Call
`GameState.matrix()` for the 8×8 `int8` NumPy view used by evaluation,
rendering and the benchmark report.

## Rules implemented

Standard English/American draughts:

- men step one square diagonally forward, kings one square any diagonal
- **capturing is mandatory** — if any capture exists, only captures are legal
- multi-jump chains are generated as a single `Move` and must be completed
- a man crowned mid-chain **ends its turn immediately**
- captured pieces are removed only at end of move, so they still block landing
  squares and cannot be jumped twice
- a player with no legal move loses
- 80 plies without a capture or a man move is a draw

## Correctness

`perft(depth)` counts leaf nodes from the opening position and is checked
against the published reference values for English draughts:

| depth | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|-------|---|---|---|---|---|---|---|---|
| nodes | 7 | 49 | 302 | 1469 | 7361 | 36768 | 179740 | 845931 |

Matching every one of these is far stronger evidence of rule correctness than
any hand-written scenario test, because a single misgenerated move anywhere in
the tree changes the totals. The suite also asserts that `undo` restores the
board, side to move, quiet-ply counter and Zobrist hash bit-for-bit.

Current generation throughput is ~270k nodes/s single-threaded.

## Status

- [x] **Phase 1** — rules core, apply/undo, forced captures, perft, tests
- [x] **Phase 2** — evaluation function, Greedy + Random agents, match driver
- [x] **Frontends** — Pygame desktop app and Flask/browser app over one controller
- [ ] Phase 3 — Minimax with search-stat instrumentation
- [ ] Phase 4 — Alpha-Beta, move ordering, transposition table, iterative deepening
- [ ] Phase 5 — MCTS (UCT, light playouts, seeded)
- [ ] Phase 6 — Hybrid phase-switching engine
- [ ] Phase 7 — Pygame UI, menus, live search sidebar, AI-vs-AI
- [ ] Phase 8 — benchmark suite and comparison report

## Evaluation

All engines score positions through `engines/evaluate.py`, so the benchmark
compares search strategies rather than four different notions of a good
position. Terms: material (man 100, king 175), advancement toward promotion,
back-row guard, centre control, edge safety, and an endgame "chase" term that
stops a winning side from shuffling into the 80-ply draw. Weights live in a
frozen `Weights` dataclass so the report can state exactly which configuration
produced which result.

`evaluate()` deliberately does not detect terminal positions — engines already
generate moves at every node and can distinguish a loss from a draw.

## Engine ladder so far

| engine | search | avg nodes/move | avg ms/move |
|--------|--------|---------------:|------------:|
| random | none | 4.7 | 0.012 |
| greedy | 1 ply | 6.4 | 0.142 |

Greedy scores **64%** against Random over 400 games. That gap is real but
modest, and it is the honest result rather than a bug: with captures being
mandatory, material is decided by the *reply*, which a one-ply engine cannot
see. Greedy grabs a piece and gets jumped back. This is precisely the weakness
Minimax exists to fix, and it makes the Phase 3 comparison meaningful.

Benchmark it yourself:

```bash
python scripts/arena.py --games 100 --csv results.csv
```

## Migrating from the original prototype

The original `board.py` / `piece.py` / `game.py` remain useful as the rendering
reference, but the rules in them are superseded. Notable fixes carried into the
core:

- kinging was applied to *any* piece reaching row 0 or row 7, so a RED king
  walking back to row 7 was re-crowned and inflated the king counter
- `skipped=[]` was a mutable default argument shared across all calls
- captures were optional, and there was no draw or stalemate detection
