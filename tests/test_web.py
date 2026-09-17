"""Tests for the web backend.

These use Flask's test client, so no server is started and no browser is needed.
"""

import pytest

flask = pytest.importorskip("flask")

from krosh.web import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def new_game(client, **overrides):
    payload = {"mode": "ai", "engine": "greedy", "human_colour": "red"}
    payload.update(overrides)
    data = client.post("/api/game", json=payload).get_json()
    return data["game_id"], data["state"]


# ----------------------------------------------------------- serving ----
def test_index_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Krosh" in response.data


def test_engine_list_is_exposed(client):
    engines = client.get("/api/engines").get_json()["engines"]
    assert "greedy" in engines and "random" in engines


# -------------------------------------------------------- new games ----
def test_new_game_returns_an_opening_position(client):
    _, state = new_game(client)
    assert state["turn"] == "red"
    assert state["is_human_turn"] is True
    assert state["counts"] == {"red_men": 12, "red_kings": 0,
                               "white_men": 12, "white_kings": 0}
    assert len(state["board"]) == 8 and len(state["board"][0]) == 8


def test_human_vs_human_has_no_engine(client):
    _, state = new_game(client, mode="human")
    assert state["labels"]["white"] == "Player 2: Human"


def test_playing_white_means_the_engine_opens(client):
    _, state = new_game(client, human_colour="white")
    assert state["is_human_turn"] is False


def test_unknown_engine_is_rejected(client):
    response = client.post("/api/game", json={"mode": "ai", "engine": "wat"})
    assert response.status_code == 400


def test_games_are_independent(client):
    first, _ = new_game(client)
    second, _ = new_game(client)
    assert first != second
    client.post(f"/api/game/{first}/click", json={"row": 5, "col": 2})
    client.post(f"/api/game/{first}/click", json={"row": 4, "col": 3})
    state = client.get(f"/api/game/{second}").get_json()
    assert state["history"] == []


# ----------------------------------------------------------- clicks ----
def test_selecting_a_piece_returns_highlights(client):
    game_id, _ = new_game(client)
    state = client.post(f"/api/game/{game_id}/click",
                        json={"row": 5, "col": 2}).get_json()
    assert state["selected"] == [5, 2]
    assert sorted(state["highlights"]) == [[4, 1], [4, 3]]


def test_completing_a_move_updates_history(client):
    game_id, _ = new_game(client)
    client.post(f"/api/game/{game_id}/click", json={"row": 5, "col": 2})
    state = client.post(f"/api/game/{game_id}/click",
                        json={"row": 4, "col": 3}).get_json()
    assert state["move_completed"] is True
    assert len(state["history"]) == 1
    assert state["is_human_turn"] is False


def test_last_move_trail_is_reported(client):
    game_id, _ = new_game(client)
    client.post(f"/api/game/{game_id}/click", json={"row": 5, "col": 2})
    state = client.post(f"/api/game/{game_id}/click",
                        json={"row": 4, "col": 3}).get_json()
    assert state["last_move"]["squares"] == [[5, 2], [4, 3]]
    assert state["last_move"]["captures"] == []


def test_off_board_click_is_rejected(client):
    game_id, _ = new_game(client)
    response = client.post(f"/api/game/{game_id}/click", json={"row": 9, "col": 0})
    assert response.status_code == 400


def test_missing_coordinates_are_rejected(client):
    game_id, _ = new_game(client)
    assert client.post(f"/api/game/{game_id}/click", json={}).status_code == 400


def test_unknown_game_is_a_404(client):
    assert client.get("/api/game/nope").status_code == 404
    assert client.post("/api/game/nope/ai").status_code == 404


# --------------------------------------------------------------- ai ----
def test_ai_endpoint_moves_and_reports_search_stats(client):
    game_id, _ = new_game(client)
    client.post(f"/api/game/{game_id}/click", json={"row": 5, "col": 2})
    client.post(f"/api/game/{game_id}/click", json={"row": 4, "col": 3})
    state = client.post(f"/api/game/{game_id}/ai").get_json()

    assert state["is_human_turn"] is True
    search = state["last_search"]
    assert search["nodes"] > 0
    assert search["depth"] == 1
    assert search["time_ms"] >= 0
    assert state["history"][-1]["engine"] == "greedy"


def test_ai_endpoint_is_a_no_op_on_a_human_turn(client):
    game_id, _ = new_game(client)
    state = client.post(f"/api/game/{game_id}/ai").get_json()
    assert state["history"] == []


# ------------------------------------------------------ undo / reset ----
def test_undo_rolls_back_both_plies(client):
    game_id, _ = new_game(client)
    client.post(f"/api/game/{game_id}/click", json={"row": 5, "col": 2})
    client.post(f"/api/game/{game_id}/click", json={"row": 4, "col": 3})
    client.post(f"/api/game/{game_id}/ai")
    state = client.post(f"/api/game/{game_id}/undo").get_json()
    assert state["history"] == []
    assert state["is_human_turn"] is True
    assert state["can_undo"] is False


def test_reset_clears_the_game(client):
    game_id, _ = new_game(client)
    client.post(f"/api/game/{game_id}/click", json={"row": 5, "col": 2})
    client.post(f"/api/game/{game_id}/click", json={"row": 4, "col": 3})
    state = client.post(f"/api/game/{game_id}/reset").get_json()
    assert state["history"] == []
    assert state["counts"]["red_men"] == 12


# ------------------------------------------------------ full game ----
def test_a_whole_game_can_be_played_through_the_api(client):
    """Random-vs-random through the HTTP layer -- catches serialisation bugs
    that only appear with kings, captures and terminal states."""
    game_id, state = new_game(client, human_colour="white", engine="random")
    # Human plays WHITE; drive it by replaying the server's own highlights.
    for _ in range(300):
        if state["is_over"]:
            break
        if not state["is_human_turn"]:
            state = client.post(f"/api/game/{game_id}/ai").get_json()
            continue
        moved = False
        for row in range(8):
            for col in range(8):
                value = state["board"][row][col]
                if value >= 0:
                    continue
                probe = client.post(f"/api/game/{game_id}/click",
                                    json={"row": row, "col": col}).get_json()
                if probe["highlights"]:
                    target = probe["highlights"][0]
                    state = client.post(f"/api/game/{game_id}/click",
                                        json={"row": target[0],
                                              "col": target[1]}).get_json()
                    moved = True
                    break
            if moved:
                break
        if not moved:
            break
    assert state["status"]
