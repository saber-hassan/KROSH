"""KROSH web backend.

A thin JSON layer over `GameSession`. The browser renders and captures clicks;
every rule decision and every search runs here in Python, so the engines are
the same objects the benchmark suite uses.

    python run_web.py           then open http://127.0.0.1:5000

Games live in memory keyed by an id the client holds. That is fine for local
single-player use and keeps the server dependency-free; it also means restarting
the server clears every game in progress.
"""

from __future__ import annotations

import uuid
from typing import Dict

from flask import Flask, jsonify, render_template, request

from ..app.session import GameSession
from ..core.constants import RED, ROWS, COLS, WHITE, rc, sq
from ..engines import ENGINES

MODE_AI = "ai"
MODE_HUMAN = "human"

games: Dict[str, GameSession] = {}


# ---------------------------------------------------------------- codec ----
def serialise(session: GameSession) -> dict:
    """Everything the browser needs to draw one frame."""
    board = [[session.state.piece_at(r, c) for c in range(COLS)] for r in range(ROWS)]

    result = session.last_result
    last_search = None
    if result is not None:
        last_search = {
            "move": str(result.move),
            "score": result.score,
            "depth": result.depth,
            "nodes": result.nodes,
            "time_ms": round(result.time_ms, 2),
            "nodes_per_second": round(result.nodes_per_second),
        }

    last_move = None
    if session.history:
        move = session.history[-1].move
        last_move = {
            "squares": [list(rc(s)) for s in move.squares()],
            "captures": [list(rc(s)) for s in move.captures],
        }

    return {
        "board": board,
        "turn": "red" if session.state.turn == RED else "white",
        "status": session.status_line(),
        "message": session.message,
        "is_over": session.is_over,
        "is_human_turn": session.is_human_turn,
        "selected": list(rc(session.selected)) if session.selected is not None else None,
        "partial_path": [list(rc(s)) for s in session.partial_path],
        "highlights": [list(cell) for cell in session.highlights()],
        "counts": session.counts(),
        "labels": {
            "red": session.side_label(RED),
            "white": session.side_label(WHITE),
        },
        "last_move": last_move,
        "last_search": last_search,
        "history": [
            {
                "n": i + 1,
                "player": "red" if entry.player == RED else "white",
                "move": str(entry.move),
                "engine": entry.engine,
            }
            for i, entry in enumerate(session.history)
        ],
        "can_undo": bool(session.history),
    }


def find(game_id: str) -> GameSession | None:
    return games.get(game_id)


# ----------------------------------------------------------------- app ----
def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index():
        return render_template("index.html", engines=list(ENGINES))

    @app.get("/api/engines")
    def engine_list():
        return jsonify({"engines": list(ENGINES)})

    @app.post("/api/game")
    def new_game():
        payload = request.get_json(silent=True) or {}
        mode = payload.get("mode", MODE_AI)
        colour = RED if payload.get("human_colour", "red") == "red" else WHITE

        if mode == MODE_AI:
            name = payload.get("engine", "greedy")
            if name not in ENGINES:
                return jsonify({"error": f"unknown engine '{name}'"}), 400
            session = GameSession.human_vs_ai(ENGINES[name](seed=0), human_plays=colour)
        else:
            session = GameSession.human_vs_human()

        game_id = uuid.uuid4().hex
        games[game_id] = session
        return jsonify({"game_id": game_id, "state": serialise(session)})

    @app.get("/api/game/<game_id>")
    def get_state(game_id):
        session = find(game_id)
        if session is None:
            return jsonify({"error": "no such game"}), 404
        return jsonify(serialise(session))

    @app.post("/api/game/<game_id>/click")
    def click(game_id):
        session = find(game_id)
        if session is None:
            return jsonify({"error": "no such game"}), 404
        payload = request.get_json(silent=True) or {}
        try:
            row, col = int(payload["row"]), int(payload["col"])
        except (KeyError, TypeError, ValueError):
            return jsonify({"error": "row and col are required"}), 400
        if not (0 <= row < ROWS and 0 <= col < COLS):
            return jsonify({"error": "square is off the board"}), 400

        completed = session.click(row, col)
        state = serialise(session)
        state["move_completed"] = completed
        return jsonify(state)

    @app.post("/api/game/<game_id>/ai")
    def ai_move(game_id):
        session = find(game_id)
        if session is None:
            return jsonify({"error": "no such game"}), 404
        if session.is_human_turn or session.is_over:
            return jsonify(serialise(session))
        session.run_ai()
        return jsonify(serialise(session))

    @app.post("/api/game/<game_id>/undo")
    def undo(game_id):
        session = find(game_id)
        if session is None:
            return jsonify({"error": "no such game"}), 404
        session.undo()
        return jsonify(serialise(session))

    @app.post("/api/game/<game_id>/reset")
    def reset(game_id):
        session = find(game_id)
        if session is None:
            return jsonify({"error": "no such game"}), 404
        session.reset()
        return jsonify(serialise(session))

    return app
