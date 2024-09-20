
from types import NoneType

from PyQt5.QtWidgets import QToolBar, QLabel
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtCore import Qt, QPoint, pyqtSignal

from .bar_widget_canvas import BarWidgetCanvas
from .bar_widget_jack import BarWidgetJack
from .bar_widget_transport import BarWidgetTransport


class PatchbayToolBar(QToolBar):
    menu_asked = pyqtSignal(QPoint)
    
    def __init__(self, parent):
        super().__init__(parent)
        self.setContextMenuPolicy(Qt.PreventContextMenu)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        child_widget = self.childAt(event.pos())
        super().mousePressEvent(event)

        if (event.button() != Qt.RightButton
                or not isinstance(
                    child_widget,
                    (QLabel, BarWidgetCanvas,
                     BarWidgetJack, BarWidgetTransport,
                     NoneType))):
            return
        
        # execute the menu, exit if no action
        point = event.screenPos().toPoint()
        point.setY(self.mapToGlobal(QPoint(0, self.height())).y())
        
        self.menu_asked.emit(point)