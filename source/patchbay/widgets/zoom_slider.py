import math
from re import M
from typing import TYPE_CHECKING

from qtpy.QtCore import QSize, QPoint, QPointF, Qt, Slot, QTimer # type:ignore
from qtpy.QtGui import QWheelEvent, QMouseEvent, QColor, QPainter, QPen, QFont
from qtpy.QtWidgets import QSizePolicy, QApplication, QWidget

from ..patchcanvas import AliasingReason
from ..patchcanvas.utils import polyline

if TYPE_CHECKING:
    from ..patchbay_manager import PatchbayManager


_translate = QApplication.translate


def map_float_to(x: int | float, min_a: int | float, max_a: int | float,
                 min_b: int | float, max_b: int | float) -> float:
    if max_a == min_a:
        return min_b
    return min_b + ((x - min_a) / (max_a - min_a)) * (max_b - min_b)


class ZoomSlider(QWidget):
    def __init__(self, parent):
        super().__init__(parent)

        self._mng = None

        self._zoom = 100.0
        self._MIN = 25.0
        self._MAX = 400.0
        self._CENTER = 100.0

        self.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Preferred,
                                       QSizePolicy.Policy.Minimum))

        self.setToolTip(
            _translate(
                'zoom_slider',
                "<p style='font-weight: bold;'>Zoom</p>"
                '<p>Right click to reset to default zoom.<br>'
                'Double click to fit view to contents.</p>'))

        self._text_timer = QTimer()
        self._text_timer.setSingleShot(True)
        self._text_timer.setInterval(1000)
        self._text_timer.timeout.connect(self._hide_text)

        self._last_mouse_pos = QPoint()
        self._show_text = False

    def sizeHint(self) -> QSize:
        return QSize(80, 20)
    
    def minimumSizeHint(self) -> QSize:
        return QSize(50, 20)

    def _zoom_to_value(self, zoom: float) -> float:        
        return map_float_to(
            math.log2(zoom / self._CENTER),
            math.log2(self._MIN / self._CENTER),
            math.log2(self._MAX / self._CENTER),
            0.0, 1.0)

    def _hide_text(self):
        self._show_text = False
        self.update()

    def set_patchbay_manager(self, patchbay_manager: 'PatchbayManager'):
        self._mng = patchbay_manager
        self._mng.sg.scene_scale_changed.connect(
            self._scale_changed)

    def _scale_changed(self, ratio: float):
        self._zoom = ratio * 100.0
        self._show_text = True
        self._text_timer.start()
        self.update()

    def enterEvent(self, event):
        self._show_text = True
        self.update()

    def leaveEvent(self, event):
        self._show_text = False
        self.update()

    def mouseDoubleClickEvent(self, event):
        if self._mng is None:
            super().mouseDoubleClickEvent(event)
            return

        self._mng.zoom_fit()
        self.update()

    def contextMenuEvent(self, event):
        if self._mng is None:
            super().contextMenuEvent(event)
            return

        self._mng.zoom_reset()
        self.update()

    def wheelEvent(self, event: QWheelEvent):
        step = 1 if event.angleDelta().y() > 0 else -1
        if not (QApplication.keyboardModifiers()
                & Qt.KeyboardModifier.ControlModifier):
            step *= 4

        if step > 0:
            if self._zoom < self._MAX:
                self._zoom *= 2 ** (0.015625 * step)
                self._zoom = min(self._zoom, self._MAX)
        else:
            if self._zoom > self._MIN:
                self._zoom *= 2 ** (0.015625 * step)
                self._zoom = max(self._zoom, self._MIN)
        
        if self._mng is not None:
            self._mng.set_zoom(self._zoom)

        self.update()

    def mousePressEvent(self, event: QMouseEvent):
        self._last_mouse_pos = event.pos()

    def mouseMoveEvent(self, event: QMouseEvent):
        mouse_pos = event.pos()
        
        step = 2 * (mouse_pos.x() - self._last_mouse_pos.x())
        if step > 0:
            if self._zoom < self._MAX:
                self._zoom *= 2 ** (0.03125 * step)
                self._zoom = min(self._zoom, self._MAX)
        else:
            if self._zoom > self._MIN:
                self._zoom *= 2 ** (0.03125 * step)
                self._zoom = max(self._zoom, self._MIN)

        self._last_mouse_pos = mouse_pos
        
        if self._mng is not None:
            if event.buttons():
                self._mng.start_aliasing_check(AliasingReason.SCROLL_BAR_MOVE)
            self._mng.set_zoom(self._zoom)
        
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        super().mouseReleaseEvent(event)

        if self._mng is not None:
            self._mng.set_aliasing_reason(
                AliasingReason.SCROLL_BAR_MOVE, False)

    def paintEvent(self, event):
        BAND_WIDTH = 20
        TOP = 8
        zoom = min(max(self._zoom, self._MIN), self._MAX)
        loupe_side = 7 * (zoom / 100) ** 0.25
        left = loupe_side
        right = self.width() - loupe_side

        ratio = self._zoom_to_value(zoom)
        if ratio > 0.5:
            right -= (ratio - 0.5) * loupe_side * 2
        
        zm_center = map_float_to(ratio, 0.0, 1.0, left, right)

        fill_col = QColor(self.palette().buttonText().color())
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        ramp = [(right, TOP),
                (right, TOP + BAND_WIDTH),
                (left, TOP + BAND_WIDTH),
                (left, TOP + BAND_WIDTH * 0.75)]
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.palette().base().color())
        painter.drawPolygon(polyline(ramp))

        done_ramp = [
            (zm_center, TOP + BAND_WIDTH
             - BAND_WIDTH * map_float_to(ratio, 0.0, 1.0, 0.25, 1.0)),
            (zm_center, TOP + BAND_WIDTH * 1.0),
            (left, TOP + BAND_WIDTH * 1.0),
            (left, TOP + BAND_WIDTH * 0.75)]

        done_col = self.palette().highlight().color()
        done_col.setAlphaF(0.25)
        painter.setBrush(done_col)
        painter.drawPolygon(polyline(done_ramp))

        topi = ((loupe_side * 2 - BAND_WIDTH) * 0.5
                + 12 * (ratio - 0.5))
        lh = 0.5
        
        loupe = [
            (zm_center - 0.75 * loupe_side + lh, TOP - topi + lh),
            (zm_center + loupe_side * 0.75 - lh, TOP - topi + lh),
            (zm_center + loupe_side - lh, TOP - topi + 0.25 * loupe_side),
            (zm_center + loupe_side - lh, TOP - topi + 1.75 * loupe_side),
            (zm_center + loupe_side * 2.0, TOP - topi + 2.75 * loupe_side),
            (zm_center + loupe_side * 1.75, TOP - topi + 3.0 * loupe_side),
            (zm_center + loupe_side * 0.75, TOP + 2 * loupe_side - topi - lh),
            (zm_center - loupe_side * 0.75 + lh, TOP + 2 * loupe_side - topi - lh),
            (zm_center - loupe_side + lh, TOP - topi + 1.75 * loupe_side),
            (zm_center - loupe_side + lh, TOP - topi + 0.25 * loupe_side),
            (zm_center - 0.75 * loupe_side + lh, TOP - topi + lh)]
        
        painter.setPen(Qt.PenStyle.NoPen)
        loope_col = QColor(self.palette().brightText())
        loope_col.setAlphaF(0.35)
        painter.setBrush(loope_col)
        painter.drawPolygon(polyline(loupe))
        
        if self._show_text:
            painter.setPen(QPen(fill_col, 1.0))
            font = QFont(self.font())
            font.setPixelSize(10)
            painter.setFont(font)
            painter.drawText(QPointF(3.0, 3.0 + font.pixelSize()),
                             f"{round(self._zoom)} %")
        
        painter.end()
