from typing import TYPE_CHECKING
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot, QPoint, QSize, QTimer
from PyQt5.QtGui import (
    QWheelEvent, QKeyEvent, QMouseEvent, QIcon, QPixmap)
from PyQt5.QtWidgets import (
    QApplication, QProgressBar, QSlider, QToolTip,
    QLineEdit, QLabel, QMenu, QAction, QCheckBox,
    QComboBox, QToolButton)


from .base_elements import TransportViewMode, AliasingReason
from .patchcanvas import utils

if TYPE_CHECKING:
    from .patchbay_manager import PatchbayManager
    from .view_selector_frame import ViewSelectorWidget

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
        
        self._mng = None
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
        if self._mng is None:
            return
        
        self._mng.set_zoom(self.zoom_percent())

    def set_patchbay_manager(self, patchbay_manager: 'PatchbayManager'):
        self._mng = patchbay_manager
        self._mng.sg.scene_scale_changed.connect(
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

        if QApplication.keyboardModifiers() & Qt.ControlModifier:
            self.set_percent(self.zoom_percent() + direction)
        else:
            self.set_percent(self.zoom_percent() + direction * 5)
        self._show_tool_tip()

    def mouseMoveEvent(self, event: QMouseEvent):
        QSlider.mouseMoveEvent(self, event)
        self._show_tool_tip()
        
        if self._mng is not None and event.buttons():
            self._mng.start_aliasing_check(AliasingReason.SCROLL_BAR_MOVE)
            
    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        
        if self._mng is not None:
            self._mng.set_aliasing_reason(AliasingReason.SCROLL_BAR_MOVE, False)


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


class ViewsComboBox(QComboBox):
    def __init__(self, parent: 'ViewSelectorWidget'):
        super().__init__(parent)
        self._parent = parent
        self._editing_text = ''
        self._selected_index = 0
        self._selected_view = 1
        self.editTextChanged.connect(self._edit_text_changed)
        self.view().setMinimumWidth(800)
    
    def set_editable(self):
        self._selected_index = self.currentIndex()
        self._selected_view = self.currentData()
        self.setEditable(True)
        self.lineEdit().selectAll()
        self.lineEdit().setFocus()
    
    @pyqtSlot(str)
    def _edit_text_changed(self, text: str):
        self._editing_text = text
        
    def keyPressEvent(self, event: QKeyEvent):
        if self.isEditable():
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                self._parent.write_view_name(
                    self._selected_view, self._editing_text)
                self.setEditable(False)
                self.setCurrentIndex(self._selected_index)
                event.ignore()
                return
        else:
            if event.key() == Qt.Key_F2:
                if self.isEditable():
                    self.setEditable(False)
                else:
                    self.set_editable()
                return

            if event.key() in (Qt.Key_Up, Qt.Key_Down):
                previous_index = self.currentIndex()
                super().keyPressEvent(event)
                
                # set arrow keys Up/Down circular 
                if self.currentIndex() == previous_index:
                    if previous_index == 0:
                        self.setCurrentIndex(self.count() - 1)
                    else:
                        self.setCurrentIndex(0)
                return

        super().keyPressEvent(event)
        
    def wheelEvent(self, event: QWheelEvent) -> None:
        previous_index = self.currentIndex()
        super().wheelEvent(event)

        # set the wheelEvent circular
        if self.currentIndex() == previous_index:
            if previous_index == 0:
                self.setCurrentIndex(self.count() - 1)
            else:
                self.setCurrentIndex(0)        


class HiddensIndicator(QToolButton):
    def __init__(self, parent):
        super().__init__(parent)
        
        self.mng: 'PatchbayManager' = None
        
        self._count = 0
        self._is_blinking = False
        self._blink_timer = QTimer()
        self._blink_timer.setInterval(400)
        self._blink_timer.timeout.connect(self._blink_timer_timeout)
        
        self._BLINK_TIMES = 6
        self._blink_times_done = 0
        
        dark = '-dark' if self._is_dark() else ''

        self._icon_normal = QIcon(QPixmap(f':scalable/breeze{dark}/hint.svg'))
        self._icon_orange = QIcon(QPixmap(f':scalable/breeze{dark}/hint_orange.svg'))
        
        self.setIcon(self._icon_normal)
        self._menu = QMenu()

    def _is_dark(self) -> bool:
        return self.palette().text().color().lightnessF() > 0.5

    def set_patchbay_manager(self, mng: 'PatchbayManager'):
        self.mng = mng
        self.mng.sg.view_changed.connect(self._view_changed)
        self.mng.sg.port_types_view_changed.connect(
            self._port_types_view_changed)
        
    def set_count(self, count: int):
        self._count = count
        self.setText(str(count))
        
        if count == 0 and self._blink_timer.isActive():
            self._blink_timer.stop()
            self.setIconSize(QSize(16, 16))
        
    def add_one(self):
        self._count += 1
        self.setText(str(self._count))
        if not self._blink_timer.isActive():
            self._blink_timer.start()
    
    def _start_blink(self):
        if self._blink_timer.isActive():
            return
        
        self.setIcon(self._icon_orange)
        self._blink_times_done = 1
        self._blink_timer.start()
    
    def _check_count(self):
        cg = 0
        for group in self.mng.list_hidden_groups():
            cg += 1
        
        self.set_count(cg)
        if cg:
            self._start_blink()
    
    @pyqtSlot()
    def _blink_timer_timeout(self):
        self._blink_times_done += 1
        if self._blink_times_done % 2:
            self.setIcon(self._icon_orange)
        else:
            self.setIcon(self._icon_normal)
        
        if self._blink_times_done == self._BLINK_TIMES:
            self._blink_times_done = 0
            self._blink_timer.stop()
    
    @pyqtSlot(int)
    def _view_changed(self, view_num: int):
        self._check_count()
        
    @pyqtSlot(int)
    def _port_types_view_changed(self, port_types_flag: int):
        self._check_count()
    
    def mousePressEvent(self, event: QMouseEvent) -> None:
        super().mousePressEvent(event)
        
        self._menu.clear()
        
        dark = self._is_dark()
        cg = 0
        has_hiddens = False
        
        for group in self.mng.list_hidden_groups():
            hidden_port_mode = group.current_position.hidden_port_modes()
            if hidden_port_mode:
                cg += 1

                group_act = self._menu.addAction(group.cnv_name)
                group_act.setIcon(utils.get_icon(
                    group.cnv_box_type, group.cnv_icon_name,
                    hidden_port_mode,
                    dark=dark))
                group_act.setData(group.group_id)
                has_hiddens = True
        
        self.set_count(cg)

        sel_act = self._menu.exec(
            self.mapToGlobal(QPoint(0, self.height())))
        
        if sel_act is None:
            return
        
        self.mng.restore_group_hidden_sides(sel_act.data())
        
        