from enum import Enum, auto

from qtpy.QtGui import QFont

from ..theme import StyleAttributer


class UnwrapButton(Enum):
    NONE = 0
    LEFT = 1
    CENTER = 2
    RIGHT = 3


class WrappingState(Enum):
    NORMAL = 0
    WRAPPING = 1
    WRAPPED = 2
    UNWRAPPING = 3


class TitleLine:
    text = ''
    size = 0.0
    x = 0.0
    y = 0.0
    is_little = False

    def __init__(self, text: str, theme: StyleAttributer, little=False):
        self.theme = theme
        self.text = text
        self.is_little = little
        self.x = 0.0
        self.y = 0.0

        self.font = None
        self.size = theme.get_text_width(text)

    def get_font(self) -> QFont:
        return self.theme.font


class PaintElement(Enum):
    MAIN = auto()
    HEADER = auto()
    ANTI_HEADER = auto()
    GUI_BUTTON = auto()


class BoxStyler(Enum):
    BOX = auto()
    SHADOW = auto()
    HEADER = auto()
    HEADER_LINE = auto()
    WRAPPER = auto()
    PORTS_BORDER = auto()