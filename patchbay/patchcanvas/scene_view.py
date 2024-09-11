from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QMouseEvent, QWheelEvent, QPainter
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
        
    def wheelEvent(self, ev: QWheelEvent) -> None:
        if ev.modifiers() == Qt.ShiftModifier:
            # lie to Qt saying to QGraphicsView and QGraphicsScene
            # that keyboard modifier key is ALT
            x, y = ev.angleDelta().x(), ev.angleDelta().y()
            new_delta = QPoint(y, x)
            new_event = QWheelEvent(
                ev.posF(), ev.globalPosF(), ev.pixelDelta(), new_delta,
                ev.buttons(), Qt.AltModifier, ev.phase(), ev.inverted(),
                ev.source())
            QGraphicsView.wheelEvent(self, new_event)
            return

        QGraphicsView.wheelEvent(self, ev)
