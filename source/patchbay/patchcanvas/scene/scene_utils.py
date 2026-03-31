from qtpy.QtCore import QPointF, QRectF

from ..box_widget import BoxWidget
from ..init_values import BoxHidding


class MovingBox:
    widget: BoxWidget
    from_pt: QPointF
    to_pt: QPointF
    final_rect: QRectF
    start_time: float
    is_joining: bool
    is_wrapping: bool
    hidding_state: BoxHidding
    needs_move: bool

    def __init__(self, widget: BoxWidget):
        self.widget = widget
        self.from_pt = QPointF(*widget.top_left())
        self.to_pt = QPointF(*widget.top_left())
        self.final_rect = widget.after_wrap_rect().translated(self.to_pt)
        self.start_time = 0.0
        self.is_joining = False
        self.is_wrapping = False
        self.hidding_state = BoxHidding.NONE
        self.needs_move = False

    def is_usefull(self) -> bool:
        if self.needs_move or self.is_wrapping:
            return True
        return self.hidding_state is not BoxHidding.NONE
