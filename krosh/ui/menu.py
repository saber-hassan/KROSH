"""Start menu: pick the mode, the opponent engine and which colour you play.

Engine choices are read from `krosh.engines.ENGINES`, so registering Minimax,
Alpha-Beta or MCTS later makes them appear here with no menu changes.
"""

import pygame

from ..core.constants import RED, WHITE
from ..engines import ENGINES
from . import theme as T

MODE_HUMAN = "Human vs Human"
MODE_AI = "Human vs AI"


class Button:
    def __init__(self, rect, label, value):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.value = value

    def draw(self, surface, font, active=False, hover=False):
        if active:
            colour = T.BUTTON_ACTIVE
        elif hover:
            colour = T.BUTTON_HOVER
        else:
            colour = T.BUTTON_BG
        pygame.draw.rect(surface, colour, self.rect, border_radius=6)
        text = font.render(self.label, True, T.BUTTON_TEXT)
        surface.blit(text, text.get_rect(center=self.rect.center))


class Menu:
    """Returns a config dict once the player presses Start."""

    def __init__(self, fonts):
        self.fonts = fonts
        self.mode = MODE_AI
        self.engine_name = "greedy"
        self.human_colour = RED

        cx = T.WIDTH // 2
        self.mode_buttons = [
            Button((cx - 250, 176, 240, 48), MODE_AI, MODE_AI),
            Button((cx + 10, 176, 240, 48), MODE_HUMAN, MODE_HUMAN),
        ]

        names = list(ENGINES)
        width = min(160, 500 // max(len(names), 1))
        total = width * len(names) + 10 * (len(names) - 1)
        start = cx - total // 2
        self.engine_buttons = [
            Button((start + i * (width + 10), 286, width, 44), name, name)
            for i, name in enumerate(names)
        ]

        self.colour_buttons = [
            Button((cx - 250, 396, 240, 44), "Play RED (first)", RED),
            Button((cx + 10, 396, 240, 44), "Play WHITE (second)", WHITE),
        ]
        self.start_button = Button((cx - 130, 486, 260, 56), "Start game", "start")

    # ------------------------------------------------------------------
    def handle_click(self, pos):
        for button in self.mode_buttons:
            if button.rect.collidepoint(pos):
                self.mode = button.value
        if self.mode == MODE_AI:
            for button in self.engine_buttons:
                if button.rect.collidepoint(pos):
                    self.engine_name = button.value
            for button in self.colour_buttons:
                if button.rect.collidepoint(pos):
                    self.human_colour = button.value
        if self.start_button.rect.collidepoint(pos):
            return self.config()
        return None

    def config(self) -> dict:
        return {
            "mode": self.mode,
            "engine": self.engine_name if self.mode == MODE_AI else None,
            "human_colour": self.human_colour,
        }

    # ------------------------------------------------------------------
    def draw(self, surface):
        surface.fill(T.MENU_BG)
        mouse = pygame.mouse.get_pos()
        cx = T.WIDTH // 2

        title = self.fonts["title"].render("KROSH", True, T.TEXT_ACCENT)
        surface.blit(title, title.get_rect(center=(cx, 74)))
        sub = self.fonts["small"].render(
            "Checkers with classical AI opponents", True, T.TEXT_DIM)
        surface.blit(sub, sub.get_rect(center=(cx, 110)))

        self._label(surface, "MODE", 152, cx)
        for button in self.mode_buttons:
            button.draw(surface, self.fonts["body"],
                        active=(self.mode == button.value),
                        hover=button.rect.collidepoint(mouse))

        ai = self.mode == MODE_AI
        self._label(surface, "OPPONENT", 262, cx, dim=not ai)
        for button in self.engine_buttons:
            button.draw(surface, self.fonts["body"],
                        active=ai and self.engine_name == button.value,
                        hover=ai and button.rect.collidepoint(mouse))

        self._label(surface, "YOUR COLOUR", 372, cx, dim=not ai)
        for button in self.colour_buttons:
            button.draw(surface, self.fonts["body"],
                        active=ai and self.human_colour == button.value,
                        hover=ai and button.rect.collidepoint(mouse))

        self.start_button.draw(surface, self.fonts["heading"],
                               hover=self.start_button.rect.collidepoint(mouse))

        hint = self.fonts["small"].render(
            "Captures are mandatory. Click each landing square of a multi-jump.",
            True, T.TEXT_DIM)
        surface.blit(hint, hint.get_rect(center=(cx, T.HEIGHT - 42)))

    def _label(self, surface, text, y, cx, dim=False):
        colour = T.TEXT_DIM if dim else T.TEXT
        rendered = self.fonts["small"].render(text, True, colour)
        surface.blit(rendered, rendered.get_rect(center=(cx, y)))
