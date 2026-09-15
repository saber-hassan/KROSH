"""Sidebar panel: status, material, live search statistics and move history.

The search-stat block is the piece the proposal calls out -- nodes visited,
time and score reported by whichever engine just moved.
"""

import pygame

from ..core.constants import RED, WHITE
from . import theme as T


class Sidebar:
    def __init__(self, fonts):
        self.fonts = fonts
        self.x = T.BOARD_SIZE

    def draw(self, surface, session):
        pygame.draw.rect(surface, T.PANEL_BG,
                         pygame.Rect(self.x, 0, T.SIDEBAR_WIDTH, T.HEIGHT))
        y = 18
        y = self._title(surface, y, session)
        y = self._rule(surface, y)
        y = self._material(surface, y, session)
        y = self._rule(surface, y)
        y = self._search_stats(surface, y, session)
        y = self._rule(surface, y)
        y = self._history(surface, y, session)
        self._controls(surface, session)

    # ------------------------------------------------------------------
    def _text(self, surface, text, y, font="body", colour=T.TEXT, indent=18):
        surface.blit(self.fonts[font].render(text, True, colour),
                     (self.x + indent, y))
        return y + self.fonts[font].get_height() + 4

    def _rule(self, surface, y):
        y += 6
        pygame.draw.line(surface, T.PANEL_LINE, (self.x + 16, y),
                         (self.x + T.SIDEBAR_WIDTH - 16, y))
        return y + 12

    def _title(self, surface, y, session):
        y = self._text(surface, "KROSH", y, "heading", T.TEXT_ACCENT)
        y = self._text(surface, session.side_label(RED), y, "small", T.TEXT_DIM)
        y = self._text(surface, session.side_label(WHITE), y, "small", T.TEXT_DIM)
        y += 6
        colour = T.TEXT_ACCENT if session.is_over else T.TEXT
        y = self._text(surface, session.status_line(), y, "body", colour)
        if session.message:
            y = self._text(surface, session.message, y, "small", T.CAPTURE_MARK)
        return y

    def _material(self, surface, y, session):
        c = session.counts()
        y = self._text(surface, "MATERIAL", y, "small", T.TEXT_DIM)
        y = self._text(surface,
                       f"RED    {c['red_men']} men  {c['red_kings']} kings",
                       y, "mono")
        y = self._text(surface,
                       f"WHITE  {c['white_men']} men  {c['white_kings']} kings",
                       y, "mono")
        return y

    def _search_stats(self, surface, y, session):
        y = self._text(surface, "LAST SEARCH", y, "small", T.TEXT_DIM)
        result = session.last_result
        if result is None:
            return self._text(surface, "-- no AI move yet --", y, "small", T.TEXT_DIM)

        rows = [
            ("move", str(result.move)),
            ("score", f"{result.score:+.0f}"),
            ("depth", str(result.depth)),
            ("nodes", f"{result.nodes:,}"),
            ("time", f"{result.time_ms:.1f} ms"),
            ("nodes/s", f"{result.nodes_per_second:,.0f}"),
        ]
        for label, value in rows:
            surface.blit(self.fonts["mono"].render(f"{label:<8}", True, T.TEXT_DIM),
                         (self.x + 18, y))
            surface.blit(self.fonts["mono"].render(value, True, T.TEXT),
                         (self.x + 96, y))
            y += self.fonts["mono"].get_height() + 3
        return y + 4

    def _history(self, surface, y, session):
        y = self._text(surface, "MOVES", y, "small", T.TEXT_DIM)
        available = T.HEIGHT - y - 96
        line_h = self.fonts["mono"].get_height() + 2
        capacity = max(int(available // line_h), 1)

        entries = session.history[-capacity:]
        start = len(session.history) - len(entries)
        for i, entry in enumerate(entries):
            tag = "R" if entry.player == RED else "W"
            colour = T.RED_PIECE if entry.player == RED else T.WHITE_PIECE
            label = f"{start + i + 1:>3}. {tag} {entry.move}"
            surface.blit(self.fonts["mono"].render(label, True, colour),
                         (self.x + 18, y))
            y += line_h
        return y

    def _controls(self, surface, session):
        y = T.HEIGHT - 76
        pygame.draw.line(surface, T.PANEL_LINE, (self.x + 16, y),
                         (self.x + T.SIDEBAR_WIDTH - 16, y))
        y += 10
        for line in ("U  undo      R  restart",
                     "ESC  menu    Q  quit"):
            surface.blit(self.fonts["small"].render(line, True, T.TEXT_DIM),
                         (self.x + 18, y))
            y += self.fonts["small"].get_height() + 4
