from typing import TYPE_CHECKING
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot, QPoint, QSize
from PyQt5.QtGui import QWheelEvent, QKeyEvent, QMouseEvent
from PyQt5.QtWidgets import (QApplication, QProgressBar, QSlider, QToolTip,
                             QLineEdit, QLabel, QMenu, QAction, QCheckBox)

from .base_elements import TransportViewMode

if TYPE_CHECKING:
    from .patchbay_manager import PatchbayManager

_translate = QApplication.translate


class FilterBar(QLineEdit):
    up_down_pressed = pyqtSignal(int)
    key_event = pyqtSignal(object)

    def __init__(self, parent):
        QLineEdit.__init__(self)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key_Up, Qt.Key_Down):
            self.up_down_pressed.emit(event.key())
            self.key_event.emit(event)
        QLineEdit.keyPressEvent(self, event)


class ProgressBarDsp(QProgressBar):
    def __init__(self, parent):
        QProgressBar.__init__(self)

    def setValue(self, value: int):
        color_border = "rgba(%i%%, %i%%, 0, 55%%)" % (value, 100 - value)
        color_center = "rgba(%i%%, %i%%, 0, 45%%)" % (value, 100 - value)
        self.setStyleSheet(
            "QProgressBar:chunk{background-color: "
            + "qlineargradient(x1:0, y1:0, x2:0, y1:1, "
            + "stop:0 " + color_border + ','
            + "stop:0.5 " + color_center + ','
            + "stop:1 " + color_border + ',' + ')}')
        QProgressBar.setValue(self, value)
        

class ZoomSlider(QSlider):
    def __init__(self, parent):
        QSlider.__init__(self, parent)
        
        self.patchbay_manager = None
        self.setMinimumSize(QSize(40, 0))
        self.setMaximumSize(QSize(90, 16777215))
        self.setMouseTracking(True)

        dark_theme = self.palette().text().color().lightnessF() > 0.5
        dark = '-dark' if dark_theme else '' 

        self.setStyleSheet(
            'QSlider:focus{border: none;} '
            'QSlider::handle:horizontal{'
            f'image: url(:scalable/breeze{dark}/zoom-centered.svg);}}'
            )
        self.setMinimum(0)
        self.setMaximum(1000)
        self.setSingleStep(10)
        self.setPageStep(10)
        self.setProperty("value", 500)
        self.setTracking(True)
        self.setOrientation(Qt.Horizontal)
        self.setInvertedAppearance(False)
        self.setInvertedControls(False)
        self.setTickPosition(QSlider.TicksBelow)
        self.setTickInterval(500)
        
        self.valueChanged.connect(self._value_changed)

    @staticmethod
    def map_float_to(x: float, min_a: int, max_a: int,
                     min_b: int, max_b: int) -> float:
        if max_a == min_a:
            return min_b
        return min_b + ((x - min_a) / (max_a - min_a)) * (max_b - min_b)

    def _show_tool_tip(self):
        win = QApplication.activeWindow()
        if win and win.isFullScreen():
            return
        string = "  Zoom: %i%%  " % int(self.zoom_percent())
        QToolTip.showText(self.mapToGlobal(QPoint(0, 12)), string)

    @pyqtSlot(int)
    def _value_changed(self, value: int):
        if self.patchbay_manager is None:
            return
        
        self.patchbay_manager.set_zoom(self.zoom_percent())

    def set_patchbay_manager(self, patchbay_manager: 'PatchbayManager'):
        self.patchbay_manager = patchbay_manager
        self.patchbay_manager.sg.scene_scale_changed.connect(
            self._scale_changed)

    def zoom_percent(self) -> int:
        if self.value() <= 500:
            return self.map_float_to(self.value(), 0, 500, 20, 100)
        return self.map_float_to(self.value(), 500, 1000, 100, 300)

    def set_percent(self, percent: float):
        if 99.99999 < percent < 100.00001:
            self.setValue(500)
        elif percent < 100:
            self.setValue(int(self.map_float_to(percent, 20, 100, 0, 500)))
        else:
            self.setValue(int(self.map_float_to(percent, 100, 300, 500, 1000)))
        self._show_tool_tip()

    def _scale_changed(self, ratio: float):
        self.set_percent(ratio * 100)

    def mouseDoubleClickEvent(self, event):
        if self.patchbay_manager is None:
            super().mouseDoubleClickEvent(event)
            return

        self.patchbay_manager.zoom_fit()

    def contextMenuEvent(self, event):
        if self.patchbay_manager is None:
            super().contextMenuEvent(event)
            return

        self.patchbay_manager.zoom_reset()

    def wheelEvent(self, event: QWheelEvent):
        direction = 1 if event.angleDelta().y() > 0 else -1

        if QApplication.keyboardModifiers() & Qt.ControlModifier:
            self.set_percent(self.zoom_percent() + direction)
        else:
            self.set_percent(self.zoom_percent() + direction * 5)
        self._show_tool_tip()

    def mouseMoveEvent(self, event):
        QSlider.mouseMoveEvent(self, event)
        self._show_tool_tip()


class TimeTransportLabel(QLabel):
    transport_view_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._actions = {
            TransportViewMode.HOURS_MINUTES_SECONDS:
                QAction(_translate('transport', 'Hours:Minutes:Seconds')),
            TransportViewMode.BEAT_BAR_TICK:
                QAction(_translate('transport', 'Beat|Bar|Tick')),
            TransportViewMode.FRAMES:
                QAction(_translate('transport', 'Frames'))}
        
        self._context_menu = QMenu()

        for key, action in self._actions.items():
            action.setCheckable(True)
            action.setChecked(False)
            action.setData(key)
            self._context_menu.addAction(action)
        
        self.transport_view_mode = TransportViewMode.HOURS_MINUTES_SECONDS
        self._actions[TransportViewMode.HOURS_MINUTES_SECONDS].setChecked(True)
        
    def _update_tool_tip(self):
        text = ""
        if self.transport_view_mode is TransportViewMode.HOURS_MINUTES_SECONDS:
            text = _translate('transport', 'Hours:Minutes:Seconds')
        elif self.transport_view_mode is TransportViewMode.BEAT_BAR_TICK:
            text = _translate('transport', 'Beat|Bar|Tick')
        elif self.transport_view_mode is TransportViewMode.FRAMES:
            text = _translate('transport', 'Frames')
        
        self.setToolTip(text)
        
    def mousePressEvent(self, event: QMouseEvent):
        for key, action in self._actions.items():
            action.setChecked(self.transport_view_mode is key)
        
        act_selected = self._context_menu.exec(
            self.mapToGlobal(QPoint(0, self.height())))

        if act_selected is not None:
            data: TransportViewMode = act_selected.data()
            self.transport_view_mode = data            
            self.transport_view_changed.emit()
            self._update_tool_tip()
    
    def wheelEvent(self, event):
        self.transport_view_mode = TransportViewMode(
            (self.transport_view_mode + 1) % 3)
        self.transport_view_changed.emit()
        self._update_tool_tip()


class TypeViewCheckBox(QCheckBox):
    really_clicked = pyqtSignal(bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
    
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() in (Qt.LeftButton, Qt.RightButton):
            alternate = bool(event.button() == Qt.RightButton
                             or QApplication.keyboardModifiers() & Qt.ControlModifier)
            self.really_clicked.emit(alternate)
            return
    
        super().mousePressEvent(event)