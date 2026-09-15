"""Visual constants for the KROSH Pygame frontend.

The crown is drawn with primitives rather than loaded from disk, so the app has
no binary asset dependency and runs straight from a clone.
"""

import pygame

# ---------------------------------------------------------------- layout ----
SQUARE_SIZE = 88
BOARD_SIZE = SQUARE_SIZE * 8          # 704
SIDEBAR_WIDTH = 296
WIDTH = BOARD_SIZE + SIDEBAR_WIDTH    # 1000
HEIGHT = BOARD_SIZE                   # 704
FPS = 60

PIECE_PADDING = 12
PIECE_OUTLINE = 3

# ----------------------------------------------------------------- colour ----
DARK_SQUARE = (82, 58, 46)
LIGHT_SQUARE = (222, 196, 160)
BOARD_EDGE = (44, 30, 24)

RED_PIECE = (196, 54, 48)
RED_PIECE_DARK = (132, 30, 26)
WHITE_PIECE = (238, 234, 226)
WHITE_PIECE_DARK = (176, 170, 160)
CROWN_GOLD = (232, 186, 74)

SELECT_RING = (94, 196, 122)
HINT_DOT = (94, 196, 122)
LAST_MOVE = (120, 150, 210)
CAPTURE_MARK = (214, 96, 84)

PANEL_BG = (28, 28, 32)
PANEL_LINE = (58, 58, 66)
TEXT = (232, 232, 238)
TEXT_DIM = (150, 150, 162)
TEXT_ACCENT = (232, 186, 74)

MENU_BG = (22, 22, 26)
BUTTON_BG = (44, 44, 52)
BUTTON_HOVER = (64, 64, 76)
BUTTON_ACTIVE = (94, 130, 96)
BUTTON_TEXT = (232, 232, 238)


def load_fonts():
    """Called after pygame.font.init()."""
    return {
        "title": pygame.font.SysFont("dejavusans", 38, bold=True),
        "heading": pygame.font.SysFont("dejavusans", 20, bold=True),
        "body": pygame.font.SysFont("dejavusans", 16),
        "small": pygame.font.SysFont("dejavusans", 13),
        "mono": pygame.font.SysFont("dejavusansmono", 14),
    }


def draw_crown(surface, cx, cy, size=18, colour=CROWN_GOLD):
    """A small five-point crown centred on (cx, cy)."""
    w, h = size, size * 0.62
    left, right = cx - w / 2, cx + w / 2
    top, bottom = cy - h / 2, cy + h / 2
    points = [
        (left, bottom), (left, top),
        (cx - w * 0.25, cy), (cx, top - h * 0.12),
        (cx + w * 0.25, cy), (right, top),
        (right, bottom),
    ]
    pygame.draw.polygon(surface, colour, points)
    pygame.draw.line(surface, colour, (left, bottom), (right, bottom), 2)
