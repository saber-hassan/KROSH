"""Headless frontend tests.

These run against SDL's dummy video driver, so they render real frames without
opening a window and work fine in CI. They are smoke tests: they check the app
wires up and does not crash, not that it looks right.
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest

pygame = pytest.importorskip("pygame")

from krosh.core.constants import RED, WHITE
from krosh.ui.app import SCREEN_GAME, SCREEN_MENU, KroshApp
from krosh.ui.board_view import square_from_mouse
from krosh.ui.menu import MODE_AI, MODE_HUMAN
from krosh.ui import theme as T


@pytest.fixture
def app():
    instance = KroshApp()
    yield instance
    pygame.display.quit()


# ---------------------------------------------------------- geometry ----
@pytest.mark.parametrize("pos,expected", [
    ((0, 0), (0, 0)),
    ((T.SQUARE_SIZE + 5, 5), (0, 1)),
    ((5, T.SQUARE_SIZE * 7 + 5), (7, 0)),
])
def test_mouse_maps_to_the_right_square(pos, expected):
    assert square_from_mouse(pos) == expected


def test_clicks_on_the_sidebar_miss_the_board():
    assert square_from_mouse((T.BOARD_SIZE + 20, 40)) is None


def test_board_and_sidebar_fill_the_window():
    assert T.BOARD_SIZE + T.SIDEBAR_WIDTH == T.WIDTH
    assert T.SQUARE_SIZE * 8 == T.BOARD_SIZE


# --------------------------------------------------------------- app ----
def test_app_opens_on_the_menu(app):
    assert app.screen == SCREEN_MENU
    app.step()


def test_menu_renders(app):
    app.step()
    assert app.surface.get_size() == (T.WIDTH, T.HEIGHT)


def test_starting_a_human_vs_ai_game(app):
    app.start_game({"mode": MODE_AI, "engine": "greedy", "human_colour": RED})
    assert app.screen == SCREEN_GAME
    assert app.session.controllers[WHITE].name == "greedy"
    app.step()


def test_starting_a_human_vs_human_game(app):
    app.start_game({"mode": MODE_HUMAN, "engine": None, "human_colour": RED})
    assert app.session.controllers[RED] is None
    assert app.session.controllers[WHITE] is None
    app.step()


def test_game_screen_renders_after_a_move(app):
    app.start_game({"mode": MODE_HUMAN, "engine": None, "human_colour": RED})
    app.session.click(5, 2)
    app.step()
    app.session.click(4, 3)
    app.step()
    assert len(app.session.history) == 1


def test_ai_thread_runs_and_completes(app):
    app.start_game({"mode": MODE_AI, "engine": "greedy", "human_colour": RED})
    app.session.click(5, 2)
    app.session.click(4, 3)
    for _ in range(200):
        app.step()
        if app.session.is_human_turn and len(app.session.history) == 2:
            break
    assert len(app.session.history) == 2
    assert app.session.last_result is not None


def test_menu_start_button_launches_a_game(app):
    config = app.menu.handle_click(app.menu.start_button.rect.center)
    assert config is not None
    app.start_game(config)
    assert app.screen == SCREEN_GAME


def test_menu_mode_toggle(app):
    app.menu.handle_click(app.menu.mode_buttons[1].rect.center)
    assert app.menu.mode == MODE_HUMAN
    app.menu.handle_click(app.menu.mode_buttons[0].rect.center)
    assert app.menu.mode == MODE_AI


def test_every_registered_engine_is_offered_in_the_menu(app):
    from krosh.engines import ENGINES
    assert {b.value for b in app.menu.engine_buttons} == set(ENGINES)


def test_engine_choice_is_ignored_in_human_vs_human(app):
    app.menu.handle_click(app.menu.mode_buttons[1].rect.center)
    before = app.menu.engine_name
    app.menu.handle_click(app.menu.engine_buttons[0].rect.center)
    assert app.menu.engine_name == before
