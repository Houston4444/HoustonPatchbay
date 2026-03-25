from enum import Enum, Flag, auto
from typing import Iterator

from patshared import PortMode

from qtpy.QtCore import QRectF, QPointF
from qtpy.QtGui import QPainter


class Margin:
    top = 0
    'The top margin in a box with title on top'
    
    bottom = 0
    'The bottom margin in a box with title on top'
    
    sides = 0
    'The sides margin in a box with title on top'

    ports_side = 0
    'The margin on the ports side in a box with title on side'
    
    free_side = 0
    'The margin on the opposite side of the ports in a box with title on side'
    
    top_side = 0
    'The top (or the bottom) margin in a box with title on side'
    
    def __add__(self, other: 'Margin | int') -> 'Margin':
        new = Margin()
        if isinstance(other, Margin):
            new.top = self.top + other.top
            new.bottom = self.bottom + other.bottom
            new.sides = self.sides + other.sides
            new.ports_side = self.ports_side + other.ports_side
            new.free_side = self.free_side + other.free_side
            new.top_side = self.top_side + other.top_side
        else:
            new.top = self.top + other
            new.bottom = self.bottom + other
            new.sides = self.sides + other
            new.ports_side = self.ports_side + other
            new.free_side = self.free_side + other
            new.top_side = self.top_side + other
        return new

    @property
    def height(self) -> int:
        return self.top + self.bottom
    
    @property
    def width(self) -> int:
        return self.sides * 2
    
    @property
    def sided_width(self) -> int:
        return self.ports_side + self.free_side
    
    @property
    def sided_height(self) -> int:
        return self.top_side * 2

    def super(self, other: 'Margin') -> 'SuperMargin':
        return SuperMargin(self, other)


class SuperMargin(Margin):
    '''Combinaison of margins with the max values margins.
    Useful to calculate the needed sizes of a box, depending
    on the selected state, for example.'''
    def __init__(self, *margins: Margin):
        self.top = max([m.top for m in margins])
        self.bottom = max([m.bottom for m in margins])
        self.sides = max([m.sides for m in margins])
        self.ports_side = max([m.ports_side for m in margins])
        self.free_side = max([m.free_side for m in margins])
        self.top_side = max([m.top_side for m in margins])
        self._height = max([m.height for m in margins])
        self._sided_width = max([m.sided_width for m in margins])
        
    @property
    def height(self) -> int:
        return self._height
    
    @property
    def sided_width(self) -> int:
        return self._sided_width
    

class BoxStyler(Enum):
    BOX = auto()
    SHADOW = auto()
    HEADER = auto()
    HEADER_LINE = auto()
    WRAPPER = auto()
    PORTS_BORDER = auto()


class BorderSide(Flag):
    NONE = 0x00
    TOP = auto()
    BOTTOM = auto()
    PORTS_SIDE = auto()
    FREE_SIDE = auto()
    SIDES = auto()
    TOP_SIDE = auto()

    FULL = TOP | BOTTOM | SIDES
    FULL_ON_SIDE = PORTS_SIDE | FREE_SIDE | TOP_SIDE
    
    @staticmethod
    def from_text(text: str) -> 'BorderSide':
        str_names = set([bs.name for bs in BorderSide])
        border_side = BorderSide.NONE
        
        for word in text.split('|'):
            word = word.strip().upper()
            if word in str_names:
                border_side |= BorderSide[word]
        
        return border_side


class _Border(Flag):
    NONE = 0x00
    TOP = auto()
    RIGHT = auto()
    BOTTOM = auto()
    LEFT = auto()
    

def rotate(border: _Border) -> Iterator[_Border | None]:
    if border is _Border.NONE:
        return
    
    start_side = None
    started = False
    
    for i in range(2):
        for side in (_Border.TOP, _Border.RIGHT,
                     _Border.BOTTOM, _Border.LEFT):
            if start_side is None:
                if side not in border:
                    start_side = side
            elif start_side is side:
                yield None
                break
            else:
                if side in border:
                    started = True
                    yield side
                elif started:
                    yield None
        
        if start_side is None:
            yield None
            break



def draw_border(
        border_side: BorderSide, rect: QRectF,
        painter: QPainter, radius=0.0, on_side=False,
        port_mode=PortMode.BOTH):
    if ((on_side and border_side is BorderSide.FULL_ON_SIDE)
            or (not on_side and border_side is BorderSide.FULL)):
        if radius:
            painter.drawRoundedRect(rect, radius, radius)
        else:
            painter.drawRect(rect)
        return
    
    borders = _Border.NONE
    
    if on_side:
        if ((port_mode is PortMode.OUTPUT
                and BorderSide.FREE_SIDE in border_side)
            or (port_mode is PortMode.INPUT
                and BorderSide.PORTS_SIDE in border_side)):
            borders |= _Border.LEFT

        if ((port_mode is PortMode.OUTPUT
                and BorderSide.PORTS_SIDE in border_side)
             or (port_mode is PortMode.INPUT
                 and BorderSide.FREE_SIDE in border_side)):
            borders |= _Border.RIGHT
        
        if BorderSide.TOP_SIDE:
            borders |= (_Border.LEFT | _Border.RIGHT)
    else:
        if BorderSide.TOP in border_side:
            borders |= _Border.TOP
        if BorderSide.BOTTOM in border_side:
            borders |= borders.BOTTOM
        if BorderSide.SIDES in border_side:
            borders |= (_Border.LEFT | _Border.RIGHT)
        
    pointss = list[list[QPointF]]()
    points = list[QPointF]()
    
    for border in rotate(borders):
        if border is None:
            if points:
                pointss.append(points)
                points = list[QPointF]()
            continue
        
        if not points:
            match border:
                case _Border.TOP:
                    point = rect.topLeft()
                case _Border.RIGHT:
                    point = rect.topRight()
                case _Border.BOTTOM:
                    point = rect.bottomRight()
                case _Border.LEFT:
                    point = rect.bottomLeft()
                case _ :
                    return
            
            points.append(point)
            
        match border:
            case _Border.TOP:
                point = rect.topRight()
            case _Border.RIGHT:
                point = rect.bottomRight()
            case _Border.BOTTOM:
                point = rect.bottomLeft()
            case _Border.LEFT:
                point = rect.topLeft()
            case _ :
                return
        
        points.append(point)
        
    for points in pointss:
        painter.drawPolyline(points)
        