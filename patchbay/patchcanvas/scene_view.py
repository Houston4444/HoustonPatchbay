from PyQt5.QtCore import Qt
from PyQt5.QtGui import QMouseEvent, QPainter
from PyQt5.QtWidgets import QApplication, QGraphicsView

# taken from carla (falktx)
class PatchGraphicsView(QGraphicsView):
    def __init__(self, parent):
        super().__init__(parent)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setRenderHint(QPainter.Antialiasing, True)

        self._panning = False

        try:
            self._middle_button = Qt.MiddleButton
        except:
            self._middle_button = Qt.MidButton

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