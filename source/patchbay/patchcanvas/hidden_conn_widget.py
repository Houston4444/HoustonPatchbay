from typing import TYPE_CHECKING

from qtpy.QtWidgets import QGraphicsPathItem
from qtpy.QtGui import QPolygonF, QPen, QColor, QBrush, QPainter, QPainterPath
from qtpy.QtCore import QPointF, Qt

from patshared import PortMode, PortType
from .init_values import canvas, CanvasItemType, options, Zv

if TYPE_CHECKING:
    from .port_widget import PortWidget


class _ThemeAttributes:
    base_pen: QPen
    color_main: QColor
    color_alter: QColor | None
    base_width: float


class HiddenConnWidget(QGraphicsPathItem):
    '''This widget is shown near to a port if it has hidden connection(s)'''
    def __init__(self, port_widget: 'PortWidget'):
        QGraphicsPathItem.__init__(self)
        
        self._port_widget = port_widget
        self._semi_hidden = False
        self._polygon = QPolygonF()
        
        self._theme_attrs = _ThemeAttributes()
        
        self.setBrush(QColor(0, 0, 0, 0))
        self.setGraphicsEffect(None) # type:ignore or #TODO what should be sent ?
        self.update_theme()
        self.update_line_pos()
        self.update_line_gradient()
        self.setZValue(Zv.HIDDEN_CONN.value)
        
    def semi_hide(self, yesno: bool):
        self._semi_hidden = yesno
        self.update_line_gradient()

    def update_line_pos(self, fast_move=False):
        x = self._port_widget.connect_pos().x()
        y = self._port_widget.scenePos().y()
        
        polygon = QPolygonF()
        
        dx = 3
        dy1 = 5
        dy2 = 3
        
        x_type_offset = 0
        if not self._port_widget.isVisible():
            # if port is hidden, the group box is wrapped
            # a X offset is applied, this way user can see
            # there are many type of hidden connections
            port_type = self._port_widget._port_type
            if port_type is PortType.MIDI_JACK:
                x_type_offset += 1
            elif port_type is PortType.MIDI_ALSA:
                x_type_offset += 2
            elif port_type is PortType.VIDEO:
                x_type_offset += 3
        
        if self._port_widget.get_port_mode() is PortMode.OUTPUT:
            x += x_type_offset
            polygon += QPointF(x + dx, y + dy1)
            polygon += QPointF(x + dx, y + canvas.theme.port_height - dy1)
            polygon += QPointF(x + dx + dx, y + dy2)
            polygon += QPointF(x + dx + dx, y + canvas.theme.port_height - dy2)
        else:
            x -= x_type_offset
            polygon += QPointF(x - dx, y + dy1)
            polygon += QPointF(x - dx, y + canvas.theme.port_height - dy1)
            polygon += QPointF(x - dx - dx, y + dy2)
            polygon += QPointF(x - dx - dx, y + canvas.theme.port_height - dy2)

        self._polygon = polygon
        path = QPainterPath(self._polygon[0])
        path.lineTo(self._polygon[1])
        path.moveTo((self._polygon[2]))
        path.lineTo(self._polygon[3])
        self.setPath(path)

    def type(self) -> CanvasItemType:
        return CanvasItemType.BEZIER_LINE

    def update_theme(self):
        port_type = self._port_widget.get_port_type()

        theme = canvas.theme.line
        if port_type is PortType.AUDIO_JACK:
            theme = theme.audio
        elif port_type is PortType.MIDI_JACK:
            theme = theme.midi
        elif port_type is PortType.MIDI_ALSA:
            theme = theme.alsa
        elif port_type is PortType.VIDEO:
            theme = theme.video
                
        tha = _ThemeAttributes()
        tha.base_pen = theme.fill_pen
        tha.color_main = theme.background_color()
        tha.color_alter = theme.background2_color()
        if tha.color_alter is None:
            tha.color_alter = tha.color_main
        tha.base_width = tha.base_pen.widthF() + 0.000001
        
        self._theme_attrs = tha

    def update_line_gradient(self):
        tha = self._theme_attrs
        
        if self._semi_hidden:
            
            shd = options.semi_hide_opacity
            bgcolor = canvas.theme.scene_background_color

            color_main = QColor(
                int(tha.color_main.red() * shd + bgcolor.red() * (1.0 - shd) + 0.5),
                int(tha.color_main.green() * shd + bgcolor.green() * (1.0 - shd)+ 0.5),
                int(tha.color_main.blue() * shd + bgcolor.blue() * (1.0 - shd) + 0.5),
                tha.color_main.alpha())
        else:
            color_main = tha.color_main
    
        self.setPen(QPen(
            QBrush(color_main), tha.base_width * 0.5,
            Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
        
    def paint(self, painter, option, widget):
        if canvas.loading_items:
            return
        
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        QGraphicsPathItem.paint(self, painter, option, widget)

        cosm_pen = QPen(self.pen())
        cosm_pen.setCosmetic(True)
        cosm_pen.setWidthF(1.00001)

        painter.setPen(cosm_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self.path())

        painter.restore()