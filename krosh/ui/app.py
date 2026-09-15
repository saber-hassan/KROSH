"""KROSH application loop.

The AI search runs on a worker thread. A depth-8 Alpha-Beta search will take
seconds, and doing that on the main thread would freeze the window and make the
app look crashed -- so the loop keeps rendering at 60 FPS while the engine
thinks, and picks up the move when the thread finishes.
"""

from __future__ import annotations

import threading

import pygame

from ..app.session import GameSession
from ..core.constants import RED
from ..engines import ENGINES
from . import theme as T
from .board_view import BoardView, square_from_mouse
from .menu import MODE_AI, Menu
from .sidebar import Sidebar

SCREEN_MENU, SCREEN_GAME = "menu", "game"


class KroshApp:
    def __init__(self):
        # Only the subsystems we need -- pygame.init() also opens audio, which
        # prints driver errors on machines with no sound card.
        pygame.display.init()
        pygame.font.init()
        pygame.display.set_caption("KROSH - Checkers AI")
        self.surface = pygame.display.set_mode((T.WIDTH, T.HEIGHT))
        self.clock = pygame.time.Clock()
        self.fonts = T.load_fonts()

        self.menu = Menu(self.fonts)
        self.board_view = BoardView(self.fonts)
        self.sidebar = Sidebar(self.fonts)

        self.screen = SCREEN_MENU
        self.session: GameSession | None = None
        self.ai_thread: threading.Thread | None = None
        self.running = True

    # ------------------------------------------------------------------
    def start_game(self, config: dict) -> None:
        if config["mode"] == MODE_AI:
            engine = ENGINES[config["engine"]](seed=0)
            self.session = GameSession.human_vs_ai(
                engine, human_plays=config["human_colour"])
        else:
            self.session = GameSession.human_vs_human()
        self.screen = SCREEN_GAME

    @property
    def ai_busy(self) -> bool:
        return self.ai_thread is not None and self.ai_thread.is_alive()

    def maybe_start_ai(self) -> None:
        session = self.session
        if session is None or session.is_over or session.is_human_turn:
            return
        if self.ai_busy:
            return
        self.ai_thread = threading.Thread(target=session.run_ai, daemon=True)
        self.ai_thread.start()

    # ------------------------------------------------------------------
    def handle_event(self, event) -> None:
        if event.type == pygame.QUIT:
            self.running = False
            return

        if self.screen == SCREEN_MENU:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                config = self.menu.handle_click(event.pos)
                if config:
                    self.start_game(config)
            elif event.type == pygame.KEYDOWN and event.key in (pygame.K_q,
                                                               pygame.K_ESCAPE):
                self.running = False
            return

        # In-game
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_q:
                self.running = False
            elif event.key == pygame.K_ESCAPE:
                if not self.ai_busy:
                    self.screen = SCREEN_MENU
            elif event.key == pygame.K_r:
                if not self.ai_busy:
                    self.session.reset()
            elif event.key == pygame.K_u:
                if not self.ai_busy:
                    self.session.undo()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.ai_busy:
                return
            cell = square_from_mouse(event.pos)
            if cell:
                self.session.click(*cell)

    # ------------------------------------------------------------------
    def draw(self) -> None:
        if self.screen == SCREEN_MENU:
            self.menu.draw(self.surface)
        else:
            self.board_view.draw(self.surface, self.session)
            self.sidebar.draw(self.surface, self.session)
        pygame.display.flip()

    def step(self) -> None:
        """One frame. Split out so tests can drive the app headlessly."""
        for event in pygame.event.get():
            self.handle_event(event)
        if self.screen == SCREEN_GAME:
            self.maybe_start_ai()
        self.draw()

    def run(self) -> None:
        while self.running:
            self.clock.tick(T.FPS)
            self.step()
        pygame.quit()


def main() -> None:
    KroshApp().run()
