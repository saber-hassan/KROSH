"""Board rendering and click mapping."""

import pygame

from ..core.constants import COLS, RED_KING, RED_MAN, ROWS, WHITE_KING, WHITE_MAN, rc, sq
from . import theme as T


def square_rect(row: int, col: int) -> pygame.Rect:
    return pygame.Rect(col * T.SQUARE_SIZE, row * T.SQUARE_SIZE,
                       T.SQUARE_SIZE, T.SQUARE_SIZE)


def square_center(row: int, col: int):
    return (col * T.SQUARE_SIZE + T.SQUARE_SIZE // 2,
            row * T.SQUARE_SIZE + T.SQUARE_SIZE // 2)


def square_from_mouse(pos):
    """(row, col) under the cursor, or None if the click missed the board."""
    x, y = pos
    if x >= T.BOARD_SIZE or y >= T.HEIGHT or x < 0 or y < 0:
        return None
    return y // T.SQUARE_SIZE, x // T.SQUARE_SIZE


class BoardView:
    def __init__(self, fonts):
        self.fonts = fonts

    def draw(self, surface, session):
        self._draw_squares(surface)
        self._draw_last_move(surface, session)
        self._draw_selection(surface, session)
        self._draw_pieces(surface, session)
        self._draw_hints(surface, session)

    # ------------------------------------------------------------------
    def _draw_squares(self, surface):
        for row in range(ROWS):
            for col in range(COLS):
                dark = (row + col) % 2 == 1
                colour = T.DARK_SQUARE if dark else T.LIGHT_SQUARE
                pygame.draw.rect(surface, colour, square_rect(row, col))

        label = self.fonts["small"]
        for i in range(ROWS):
            tint = T.LIGHT_SQUARE if i % 2 else T.DARK_SQUARE
            surface.blit(label.render(str(i), True, tint), (4, i * T.SQUARE_SIZE + 3))
            surface.blit(label.render(str(i), True, tint),
                         (i * T.SQUARE_SIZE + 4, T.HEIGHT - 17))

        pygame.draw.rect(surface, T.BOARD_EDGE,
                         pygame.Rect(0, 0, T.BOARD_SIZE, T.HEIGHT), 3)

    def _draw_last_move(self, surface, session):
        if not session.history:
            return
        move = session.history[-1].move
        for square in move.squares():
            row, col = rc(square)
            overlay = pygame.Surface((T.SQUARE_SIZE, T.SQUARE_SIZE), pygame.SRCALPHA)
            overlay.fill((*T.LAST_MOVE, 70))
            surface.blit(overlay, (col * T.SQUARE_SIZE, row * T.SQUARE_SIZE))
        for square in move.captures:
            row, col = rc(square)
            cx, cy = square_center(row, col)
            r = T.SQUARE_SIZE // 2 - 20
            pygame.draw.line(surface, T.CAPTURE_MARK,
                             (cx - r, cy - r), (cx + r, cy + r), 3)
            pygame.draw.line(surface, T.CAPTURE_MARK,
                             (cx + r, cy - r), (cx - r, cy + r), 3)

    def _draw_selection(self, surface, session):
        if session.selected is None:
            return
        row, col = rc(session.selected)
        pygame.draw.rect(surface, T.SELECT_RING, square_rect(row, col), 4)
        for square in session.partial_path:
            r2, c2 = rc(square)
            pygame.draw.rect(surface, T.SELECT_RING, square_rect(r2, c2), 2)

    def _draw_pieces(self, surface, session):
        board = session.state.board
        # A piece mid-chain is drawn at its current landing square.
        origin = session.selected
        path = session.partial_path

        for row in range(ROWS):
            for col in range(COLS):
                value = board[sq(row, col)]
                if value == 0:
                    continue
                if path and sq(row, col) == origin:
                    continue
                self._draw_piece(surface, row, col, value)

        if path and origin is not None:
            row, col = rc(path[-1])
            self._draw_piece(surface, row, col, board[origin], ghost=True)

    def _draw_piece(self, surface, row, col, value, ghost=False):
        cx, cy = square_center(row, col)
        radius = T.SQUARE_SIZE // 2 - T.PIECE_PADDING

        if value > 0:
            face, edge = T.RED_PIECE, T.RED_PIECE_DARK
        else:
            face, edge = T.WHITE_PIECE, T.WHITE_PIECE_DARK

        if ghost:
            layer = pygame.Surface((T.SQUARE_SIZE, T.SQUARE_SIZE), pygame.SRCALPHA)
            pygame.draw.circle(layer, (*face, 160),
                               (T.SQUARE_SIZE // 2, T.SQUARE_SIZE // 2), radius)
            surface.blit(layer, (col * T.SQUARE_SIZE, row * T.SQUARE_SIZE))
        else:
            pygame.draw.circle(surface, edge, (cx, cy), radius)
            pygame.draw.circle(surface, face, (cx, cy - 2), radius - T.PIECE_OUTLINE)

        if abs(value) == 2:
            T.draw_crown(surface, cx, cy - 2, size=radius)

    def _draw_hints(self, surface, session):
        for row, col in session.highlights():
            cx, cy = square_center(row, col)
            occupied = session.state.board[sq(row, col)] != 0
            if occupied:
                pygame.draw.circle(surface, T.HINT_DOT, (cx, cy),
                                   T.SQUARE_SIZE // 2 - 8, 4)
            else:
                pygame.draw.circle(surface, T.HINT_DOT, (cx, cy), 13)
