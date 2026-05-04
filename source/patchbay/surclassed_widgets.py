
from typing import TYPE_CHECKING

from qtpy import QT5
from qtpy.QtCore import (
    Qt, Signal, Slot, QPoint, QSize, QRectF, QPointF) # type:ignore
from qtpy.QtGui import (
    QWheelEvent, QKeyEvent, QMouseEvent, QPaintEvent,
    QPainter, QPen, QPainterPath, QPixmap, QColor, QFont)
from qtpy.QtWidgets import (
    QApplication, QProgressBar, QLineEdit, QLabel, QMenu,
    QCheckBox, QComboBox, QFrame, QWidget)

if not QT5 or TYPE_CHECKING:
    from qtpy.QtGui import QAction
else:
    from qtpy.QtWidgets import QAction

from patshared import PortTypesViewFlag, PortType, PortSubType

from .patchcanvas import patchcanvas
from .patchcanvas.utils import polyline
from .patchcanvas.theme import BorderMode
from .bases.elements import TransportViewMode

if TYPE_CHECKING:
    from .widgets.view_selector_frame import ViewSelectorWidget

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
        match self.transport_view_mode:
            case TransportViewMode.HOURS_MINUTES_SECONDS:
                text = _translate('transport', 'Hours:Minutes:Seconds')
            case TransportViewMode.BEAT_BAR_TICK:
                text = _translate('transport', 'Beat|Bar|Tick')
            case TransportViewMode.FRAMES:
                text = _translate('transport', 'Frames')
            case _:
                text = ''
        
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
        self.setMaximumWidth(50)
        self._port_type = PortType.NULL
        self._port_sub_type = PortSubType.REGULAR

    def set_full_port_type(self, port_type: PortType, sub_type: PortSubType):
        self._port_type = port_type
        self._port_sub_type = sub_type

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() in (Qt.MouseButton.LeftButton,
                              Qt.MouseButton.RightButton):
            alternate = bool(
                event.button() == Qt.MouseButton.RightButton
                or (QApplication.keyboardModifiers()
                    & Qt.KeyboardModifier.ControlModifier))
            self.really_clicked.emit(alternate)
            return

        super().mousePressEvent(event)
        
    def paintEvent(self, event):
        theme = patchcanvas.canvas.theme

        port_height = 18
        port_theme = theme.port
        line_theme = theme.line

        TOP_SPACE = 6
        lh = port_theme.fill_pen.widthF() * 0.5
        top = lh + TOP_SPACE
        bottom = port_height - lh + TOP_SPACE
        left = lh
        right = self.width() - lh
        arrow_base = lh + port_height * 0.5
        arrow_mid = lh + port_height * 0.25
        y_arrow_pic = TOP_SPACE + port_height * 0.5
        
        points = []

        match self._port_type:
            case PortType.AUDIO_JACK:
                match self._port_sub_type:
                    case PortSubType.CV:
                        port_theme = port_theme.cv
                        line_theme = line_theme.audio
                        points = [(arrow_base, top),
                                (right, top),
                                (right, bottom),
                                (arrow_base, bottom),
                                (arrow_base, top)]
                    case _:                    
                        port_theme = port_theme.audio
                        line_theme = line_theme.audio
                        points = [(arrow_base, top),
                                (right, top),
                                (right, bottom),
                                (arrow_base, bottom),
                                (left, y_arrow_pic),
                                (arrow_base, top)]

            case PortType.MIDI_JACK:
                port_theme = port_theme.midi
                line_theme = line_theme.midi
                points = [
                    (right, top),
                    (arrow_base, top),
                    (arrow_base + (arrow_mid - arrow_base) * 0.62,
                     TOP_SPACE + port_height * 0.15),
                    (arrow_mid, TOP_SPACE + port_height * 0.40),
                    (arrow_mid, TOP_SPACE + port_height * 0.60),
                    (arrow_base + (arrow_mid - arrow_base) * 0.62,
                     TOP_SPACE + port_height * 0.85),
                    (arrow_base, bottom),
                    (right, bottom),
                    (right, top)]
                
            case PortType.MIDI_ALSA:
                port_theme = port_theme.alsa
                line_theme = line_theme.alsa
                points = [(arrow_mid, top),
                          (right, top),
                          (right, bottom),
                          (arrow_mid, bottom),
                          (arrow_mid, top)]

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        if port_theme.border_mode is BorderMode.MINIMAL:
            painter.setPen(Qt.PenStyle.NoPen)
        else:
            painter.setPen(port_theme.fill_pen)
        painter.setBrush(port_theme.background_color)
        
        painter.drawPolygon(polyline(points))
        
        if port_theme.border_mode is BorderMode.MINIMAL:
            painter.setPen(port_theme.fill_pen)
            match self._port_type:
                case PortType.AUDIO_JACK:
                    match self._port_sub_type:
                        case PortSubType.CV:
                            painter.drawPolyline(polyline(points[1:3]))
                            painter.drawPolyline(polyline(points[3:5]))
                        case _:
                            painter.drawPolyline(polyline(points[1:3]))
                            painter.drawPolyline(polyline(points[3:6]))
                
                case PortType.MIDI_JACK:
                    painter.drawPolyline(polyline(points[1:7]))
                    painter.drawPolyline(polyline(points[7:9]))
                    
                case PortType.MIDI_ALSA:
                    painter.drawPolyline(polyline(points[1:3]))
                    painter.drawPolyline(polyline(points[3:5]))
        
        match (self._port_type, self._port_sub_type):
            case (PortType.AUDIO_JACK, PortSubType.CV):
                divid = (bottom - top) / 12
                painter.drawPolyline(polyline(
                    [(arrow_base, top + divid * 5),
                    (left, top + divid * 5),
                    (left, top + divid * 7),
                    (arrow_base, top + divid * 7)]))
            case (PortType.MIDI_ALSA, PortSubType.REGULAR):
                scene_col = theme.scene_background_color
                circle_bg_col = QColor(scene_col)
                circle_bg_col.setAlphaF(1.0)
                painter.setBrush(circle_bg_col)
                radius = abs(left - arrow_mid) * 0.667
                painter.drawEllipse(
                    QPointF(arrow_mid, TOP_SPACE + port_height / 2.0),
                    radius, radius)

        font = QFont(port_theme.font)
        font.setPixelSize(12)
        
        painter.setFont(font)
        text_y_pos = TOP_SPACE + ((port_height - 0.667 * font.pixelSize()) / 2
                      + font.pixelSize() * 0.667)
        painter.setPen(QPen(port_theme.text_color))
        painter.drawText(
            QPointF(3.0 + port_height * 0.5, text_y_pos), self.text())
        
        if self.isChecked():
            painter.setPen(QPen(line_theme.background_color, 3.0))
            painter.drawLine(
                QPointF(1.5 + port_height * 0.5, TOP_SPACE + port_height + 4.0),
                QPointF(self.width() - 1.5, TOP_SPACE + port_height + 4.0))

        painter.end()


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
            f':scalables/{color_scheme}/breeze/color-picker-white.svg').toImage()

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

        port_type_colors = patchcanvas.canvas.theme.port_type_colors

        pcols = [port_type_colors['audio'], port_type_colors['midi'],
                 port_type_colors['cv'], port_type_colors['alsa']]

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
                if pcols[i].lightnessF() == 0.0:
                    # avoid black to stay black with lighter() 
                    # and make an infinite loop
                    pcols[i] = QColor(1, 1, 1)

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