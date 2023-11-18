from PyQt5.QtCore import Qt
from PyQt5.QtGui import QMouseEvent, QPainter, QTransform
from PyQt5.QtWidgets import QApplication, QGraphicsView, QScrollBar

from .init_values import AliasingReason, canvas


class CustomScrollBar(QScrollBar):
    def __init__(self, orientation, parent):
        QScrollBar.__init__(self, orientation, parent)

    def mouseMoveEvent(self, event) -> None:
        super().mouseMoveEvent(event)
        canvas.qobject.start_aliasing_check(AliasingReason.SCROLL_BAR_MOVE)
        
    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        canvas.set_aliasing_reason(AliasingReason.SCROLL_BAR_MOVE, False)


# taken partially from carla (falktx)
class PatchGraphicsView(QGraphicsView):
    def __init__(self, parent):
        super().__init__(parent)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setOptimizationFlag(QGraphicsView.DontAdjustForAntialiasing, True)
        self.setOptimizationFlag(QGraphicsView.DontSavePainterState, True)
        self.setRenderHint(QPainter.Antialiasing, True)
        
        self._h_scroll_bar = CustomScrollBar(Qt.Horizontal, self)
        self.setHorizontalScrollBar(self._h_scroll_bar)
        self._v_scroll_bar = CustomScrollBar(Qt.Vertical, self)
        self.setVerticalScrollBar(self._v_scroll_bar)

        self._panning = False
        self.transforming = False

        try:
            self._middle_button = Qt.MiddleButton
        except:
            self._middle_button = Qt.MidButton

    # def setTransform(self, matrix: QTransform):
    #     self.transforming = True
    #     super().setTransform(matrix)
    #     self.transforming = False

    def mousePressEvent(self, event):
        if (event.button() == self._middle_button
                and not QApplication.keyboardModifiers() & Qt.ControlModifier):
            self._panning = True
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            event = QMouseEvent(event.type(), event.pos(), Qt.LeftButton,
                                Qt.LeftButton, event.modifiers())

        QGraphicsView.mousePressEvent(self, event)

    def mouseReleaseEvent(self, event):
        QGraphicsView.mouseReleaseEvent(self, event)

        if not self._panning:
            return

        self._panning = False
        self.setDragMode(QGraphicsView.NoDrag)