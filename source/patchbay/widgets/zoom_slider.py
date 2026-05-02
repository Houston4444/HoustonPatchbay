from typing import TYPE_CHECKING

from qtpy.QtCore import QSize, QPoint, QPointF, Qt, Slot # type:ignore
from qtpy.QtGui import QWheelEvent, QMouseEvent, QColor, QPainter, QPen, QFont
from qtpy.QtWidgets import QSlider, QSizePolicy, QApplication, QToolTip

from ..patchcanvas import AliasingReason
from ..patchcanvas.utils import polyline

if TYPE_CHECKING:
    from ..patchbay_manager import PatchbayManager


def map_float_to(x: int | float, min_a: int | float, max_a: int | float,
                 min_b: int | float, max_b: int | float) -> float:
    if max_a == min_a:
        return min_b
    return min_b + ((x - min_a) / (max_a - min_a)) * (max_b - min_b)


class ZoomSlider(QSlider):
    def __init__(self, parent):
        super().__init__(parent)

        self._mng = None
        self._moving = False
        self.setMinimumSize(QSize(40, 0))
        self.setMaximumSize(QSize(180, 16777215))

        self.setMinimum(0)
        self.setMaximum(1000)
        self.setValue(500)

        self.setSingleStep(10)
        self.setPageStep(10)
        self.setOrientation(Qt.Orientation.Horizontal)
        self.setInvertedAppearance(False)
        self.setInvertedControls(False)
        self.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.setTickInterval(500)
        self.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Minimum,
                                       QSizePolicy.Policy.Minimum))

        self._last_mouse_pos = QPoint()
        self.valueChanged.connect(self._value_changed)

    def _show_tool_tip(self):
        win = QApplication.activeWindow()
        if win and win.isFullScreen():
            return
        string = "  Zoom: %i%%  " % int(self.zoom_percent())
        QToolTip.showText(self.mapToGlobal(QPoint(0, 12)), string)

    @Slot(int)
    def _value_changed(self, value: int):
        if self._mng is None:
            return

        self._mng.set_zoom(self.zoom_percent())

    def set_patchbay_manager(self, patchbay_manager: 'PatchbayManager'):
        self._mng = patchbay_manager
        self._mng.sg.scene_scale_changed.connect(
            self._scale_changed)

    def zoom_percent(self) -> int:
        if self.value() <= 500:
            return int(map_float_to(self.value(), 0, 500, 20, 100))
        return int(map_float_to(self.value(), 500, 1000, 100, 300))

    def set_percent(self, percent: float):
        if self._moving:
            return

        if 99.99999 < percent < 100.00001:
            self.setValue(500)
        elif percent < 100:
            self.setValue(int(map_float_to(percent, 20, 100, 0, 500)))
        else:
            self.setValue(int(map_float_to(percent, 100, 300, 500, 1000)))
        self._show_tool_tip()

    def _scale_changed(self, ratio: float):
        self.set_percent(ratio * 100)

    def mouseDoubleClickEvent(self, event):
        if self._mng is None:
            super().mouseDoubleClickEvent(event)
            return

        self._mng.zoom_fit()

    def contextMenuEvent(self, event):
        if self._mng is None:
            super().contextMenuEvent(event)
            return

        self._mng.zoom_reset()

    def wheelEvent(self, event: QWheelEvent):
        direction = 1 if event.angleDelta().y() > 0 else -1

        if QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier:
            self.set_percent(self.zoom_percent() + direction)
        else:
            self.set_percent(self.zoom_percent() + direction * 5)
        self._show_tool_tip()

    def mousePressEvent(self, event: QMouseEvent):
        self._last_mouse_pos = event.pos()

    def mouseMoveEvent(self, event: QMouseEvent):
        mouse_pos = event.pos()
        self._moving = True
        self.setValue(
            self.value()
            + 10 * (mouse_pos.x() - self._last_mouse_pos.x()))

        self._moving = False
        self._last_mouse_pos = mouse_pos
        
        if self._mng is not None and event.buttons():
            self._mng.start_aliasing_check(AliasingReason.SCROLL_BAR_MOVE)
        
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        super().mouseReleaseEvent(event)

        if self._mng is not None:
            self._mng.set_aliasing_reason(AliasingReason.SCROLL_BAR_MOVE, False)

    def paintEvent(self, event):
        BAND_WIDTH = 20
        TOP = 8
        loupe_side = 7 * (self.zoom_percent() / 100) ** 0.25
        zm_center = map_float_to(
            self.value(), 0, 1000, loupe_side, self.width() - loupe_side)

        fill_col = QColor(self.palette().buttonText().color())
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        ramp = [(self.width() - loupe_side, TOP),
                (self.width() - loupe_side, TOP + BAND_WIDTH),
                (loupe_side, TOP + BAND_WIDTH),
                (loupe_side, TOP + BAND_WIDTH * 0.75)]
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.palette().base().color())
        painter.drawPolygon(polyline(ramp))

        done_ramp = [
            (zm_center, TOP + BAND_WIDTH
             - BAND_WIDTH * map_float_to(self.value(), 0, 1000, 0.25, 1.0)),
            (zm_center, TOP + BAND_WIDTH * 1.0),
            (loupe_side, TOP + BAND_WIDTH * 1.0),
            (loupe_side, TOP + BAND_WIDTH * 0.75)]

        done_col = self.palette().highlight().color()
        done_col.setAlphaF(0.25)
        painter.setBrush(done_col)
        painter.drawPolygon(polyline(done_ramp))

        topi = (loupe_side * 2 - BAND_WIDTH) * 0.5 + ((self.value() - 500)/500) * 6
        lh = 0.5
        
        loupe = [(zm_center - 0.75 * loupe_side + lh, TOP - topi + lh),
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
        
        painter.setPen(QPen(fill_col, 1.0))
        font = QFont(self.font())
        font.setPixelSize(10)
        painter.setFont(font)
        painter.drawText(
            QPointF(3.0, 3.0 + font.pixelSize()),
            "%.0f %%" % self.zoom_percent())
        
        painter.end()
