
from types import NoneType
from typing import Optional

from qtpy import QT5
from qtpy.QtWidgets import QToolBar, QLabel
from qtpy.QtGui import QMouseEvent
from qtpy.QtCore import Qt, QPoint, Signal, QSize

from .surclassed_widgets import SpacerWidget
from .hiddens_indicator import HiddensIndicator
from .bar_widget_canvas import BarWidgetCanvas
from .bar_widget_jack import BarWidgetJack
from .bar_widget_transport import BarWidgetTransport


class PatchbayToolBar(QToolBar):
    menu_asked = Signal(QPoint)
    
    def __init__(self, parent):
        super().__init__(parent)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.PreventContextMenu)
        self._min_width: Optional[int] = None

    def set_min_width(self, width: int):
        self._min_width = width

    def mousePressEvent(self, event: QMouseEvent) -> None:
        child_widget = self.childAt(event.pos())
        super().mousePressEvent(event)

        if (event.button() != Qt.MouseButton.RightButton
                or not isinstance(
                    child_widget,
                    (QLabel, BarWidgetCanvas,
                     BarWidgetJack, BarWidgetTransport,
                     NoneType, SpacerWidget, HiddensIndicator))):
            return
        
        # execute the menu, exit if no action
        if QT5:
            point = event.screenPos().toPoint()
        else:
            point = QPoint(int(event.scenePosition().x()), 0)
        point.setY(self.mapToGlobal(QPoint(0, self.height())).y())

        self.menu_asked.emit(point)
    
    def sizeHint(self) -> QSize:
        if self._min_width is None:
            return super().sizeHint()
        size = super().sizeHint()
        size.setWidth(self._min_width)
        return size
    
    def needed_width(self) -> QSize:
        return super().sizeHint().width()