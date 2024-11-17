
from typing import TYPE_CHECKING

from qtpy.QtCore import Qt, Signal, Slot, QPoint, QSize, QRectF, QPointF
from qtpy.QtGui import (
    QWheelEvent, QKeyEvent, QMouseEvent, QPaintEvent,
    QPainter, QPen, QColor, QPainterPath, QPixmap)
from qtpy.QtWidgets import (
    QApplication, QProgressBar, QSlider, QToolTip,
    QLineEdit, QLabel, QMenu, QAction, QCheckBox,
    QComboBox, QFrame, QWidget)


from .patchcanvas.patshared import PortTypesViewFlag
from .patchcanvas import patchcanvas, AliasingReason
from .base_elements import TransportViewMode

if TYPE_CHECKING:
    from .patchbay_manager import PatchbayManager
    from .view_selector_frame import ViewSelectorWidget

_translate = QApplication.translate


class FilterBar(QLineEdit):
    up_down_pressed = Signal(int)
    key_event = Signal(object)

    def __init__(self, parent):
        QLineEdit.__init__(self)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
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
        self.setOrientation(Qt.Orientation.Horizontal)
        self.setInvertedAppearance(False)
        self.setInvertedControls(False)
        self.setTickPosition(QSlider.TickPosition.TicksBelow)
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

        if QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier:
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
    transport_view_changed = Signal()
    
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
    really_clicked = Signal(bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
    
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
            alternate = bool(
                event.button() == Qt.MouseButton.RightButton
                or QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier)
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
        
        dark = self.palette().text().color().lightnessF() > 0.5
        color_scheme = 'breeze-dark' if dark else 'breeze'
        
        self._white_image = QPixmap(
            f':scalable/{color_scheme}/color-picker-white.svg').toImage()
        
        self.editTextChanged.connect(self._edit_text_changed)
        self.view().setMinimumWidth(800)
    
    def set_editable(self):
        self._selected_index = self.currentIndex()
        self._selected_view = self.currentData()
        self.setEditable(True)
        self.lineEdit().selectAll()
        self.lineEdit().setFocus()
    
    @Slot(str)
    def _edit_text_changed(self, text: str):
        self._editing_text = text
    
    def sizeHint(self) -> QSize:
        size = super().sizeHint()
        size.setWidth(size.width() + 40)
        return size
    
    def keyPressEvent(self, event: QKeyEvent):
        if self.isEditable():
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._parent.write_view_name(
                    self._selected_view, self._editing_text)
                self.setEditable(False)
                self.setCurrentIndex(self._selected_index)
                event.ignore()
                return
        else:
            if event.key() == Qt.Key.Key_F2:
                if self.isEditable():
                    self.setEditable(False)
                else:
                    self.set_editable()
                return

            if event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
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
    
    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        super().mouseDoubleClickEvent(event)
        if self.isEditable():
            self.setEditable(False)
        else:
            self.set_editable()
    
    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        
        # Draw rect
        bg_col = self.palette().alternateBase().color()
        painter.setPen(QPen(self.palette().midlight().color(), 1.0))
        painter.setBrush(bg_col)
        painter.drawRoundedRect(
            QRectF(0.0, 1.0, self.width(),
                   self.height() - 2.0),
            2.0, 2.0)
        
        # Draw text      
        painter.setPen(QPen(QApplication.palette().text().color(), 1.0))
        
        font = QApplication.font()
        
        text_pos = QPoint(6, (self.height() + font.pointSize()) // 2 )
        painter.setFont(font)
        painter.drawText(text_pos, self.currentText())

        # Draw arrow
        arrow_side = self.height() / 7
        path = QPainterPath()
        path.moveTo(
            QPointF(self.width() - arrow_side * 4, arrow_side * 3))
        path.lineTo(
            QPointF(self.width() - arrow_side * 3, arrow_side * 4))
        path.lineTo(
            QPointF(self.width() - arrow_side * 2, arrow_side * 3))
        painter.drawPath(path)
        
        # Draw PortTypesView thumbnail
        thmp = patchcanvas.canvas.theme.port

        if patchcanvas.canvas.theme.thumbnail_port_colors.lower() == 'text':
            pcols = [thmp.audio.text_color(),
                     thmp.midi.text_color(),
                     thmp.cv.text_color(), 
                     thmp.alsa.text_color()]
        else:
            pcols = [thmp.audio.background_color(),
                     thmp.midi.background_color(),
                     thmp.cv.background_color(), 
                     thmp.alsa.background_color()]
        
        # adapt colors lightness to be clearly visible on this background
        bg_ligthness = bg_col.lightnessF()
        if bg_ligthness > 0.5:
            for i in range(len(pcols)):
                while bg_ligthness - pcols[i].lightnessF() < 0.25:
                    pcols[i] = pcols[i].darker()
                    
                    if pcols[i].lightnessF() == 0.0:
                        break
        else:
            for i in range(len(pcols)):                
                while pcols[i].lightnessF() - bg_ligthness < 0.25:
                    pcols[i] = pcols[i].lighter()
                    
                    if pcols[i].lightnessF() == 1.0:
                        break

        mng = self._parent.mng
        if mng is None:
            return
        
        hgt = int(self.height())
        SPAC = 4
        Y_OFFSET = 10
        XBASE = int(self.width() - 40)
        
        ptvs = [PortTypesViewFlag.AUDIO, PortTypesViewFlag.MIDI,
                PortTypesViewFlag.CV]
        if mng.alsa_midi_enabled:
            ptvs.append(PortTypesViewFlag.ALSA)

        for i in range(len(ptvs)):
            painter.setPen(QPen(pcols[i], 2.0))
            if mng.port_types_view & ptvs[i]:
                painter.drawLine(XBASE + i * SPAC, Y_OFFSET,
                                 XBASE + i * SPAC, hgt - Y_OFFSET)
            else:
                painter.drawLine(XBASE + i * SPAC, hgt // 2 - 1,
                                 XBASE + i * SPAC, hgt // 2 + 1)
        
        view_data = mng.views.get(mng.view_number)
        if view_data is not None and view_data.is_white_list:
            white_list_image_rect = QRectF(
                XBASE - 20.0, self.height() * 0.5 - 8.0, 16.0, 16.0)
            painter.drawImage(white_list_image_rect, self._white_image)


class ToolsWidgetFrame(QFrame):
    ...
        

class SpacerWidget(QWidget):
    ...