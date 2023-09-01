from typing import TYPE_CHECKING
from enum import Enum
from PyQt5.QtWidgets import QGraphicsPathItem
from PyQt5.QtGui import QPolygonF, QPen, QColor, QBrush, QPainter, QPainterPath
from PyQt5.QtCore import QPointF, Qt

from .init_values import PortMode, PortType, canvas, CanvasItemType, options

if TYPE_CHECKING:
    from .port_widget import PortWidget


class _ThemeState(Enum):
    NORMAL = 0
    SELECTED = 1
    DISCONNECTING = 2


class _ThemeAttributes:
    base_pen: QPen
    color_main: QColor
    color_alter: QColor
    base_width: float


class HiddenConnWidget(QGraphicsPathItem):
    def __init__(self, port_widget: 'PortWidget'):
        QGraphicsPathItem.__init__(self)
        
        self._port_widget = port_widget
        self._semi_hidden = False
        self._polygon = QPolygonF()
        
        self._th_attribs = dict[_ThemeState, _ThemeAttributes]()
        print('slslslp', self._port_widget._port_name)
        
        self.setBrush(QColor(0, 0, 0, 0))
        self.setGraphicsEffect(None)
        self.update_theme()
        self.update_line_pos()
        self.update_line_gradient()
        
    def semi_hide(self, yesno: bool):
        self._semi_hidden = yesno
        self.update_line_gradient()

    def update_line_pos(self, fast_move=False):
        x = self._port_widget.connect_pos().x()
        # y = self._port_widget.scenePos().y() + canvas.theme.port_height / 2
        y = self._port_widget.scenePos().y()
        
        polygon = QPolygonF()
        
        if self._port_widget.get_port_mode() is PortMode.OUTPUT:
            # x += 2
            polygon += QPointF(x + 3, y + 5)
            polygon += QPointF(x + 3, y + canvas.theme.port_height - 5)
            polygon += QPointF(x + 6, y + 3)
            polygon += QPointF(x + 6, y + canvas.theme.port_height - 3)
        else:
            polygon += QPointF(x - 3, y + 5)
            polygon += QPointF(x - 3, y + canvas.theme.port_height - 5)
            polygon += QPointF(x - 6, y + 3)
            polygon += QPointF(x - 6, y + canvas.theme.port_height - 3)

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
        
        for theme_state in _ThemeState:
            if self.isSelected():
                theme = theme.selected
                
            tha = _ThemeAttributes()
            tha.base_pen = theme.fill_pen()
            tha.color_main = theme.background_color()
            tha.color_alter = theme.background2_color()
            if tha.color_alter is None:
                tha.color_alter = tha.color_main
            tha.base_width = tha.base_pen.widthF() + 0.000001
            
            self._th_attribs[theme_state] = tha

    def update_line_gradient(self):
        pos_top = self.boundingRect().top()
        pos_bot = self.boundingRect().bottom()

        if self._port_widget.isSelected():
            tha = self._th_attribs[_ThemeState.SELECTED]
        else:
            tha = self._th_attribs[_ThemeState.NORMAL]
        
        has_gradient = bool(tha.color_main != tha.color_alter)
        
        if has_gradient:
            pass
            # port_gradient = QLinearGradient(0, pos_top, 0, pos_bot)

            # if self.ready_to_disc:
            #     port_gradient.setColorAt(0.0, tha.color_main)
            #     port_gradient.setColorAt(1.0, tha.color_main)
            # else:
            #     if self._semi_hidden:
            #         shd = options.semi_hide_opacity
            #         bgcolor = canvas.theme.scene_background_color
                    
            #         color_main = QColor(
            #             int(tha.color_main.red() * shd + bgcolor.red() * (1.0 - shd) + 0.5),
            #             int(tha.color_main.green() * shd + bgcolor.green() * (1.0 - shd)+ 0.5),
            #             int(tha.color_main.blue() * shd + bgcolor.blue() * (1.0 - shd) + 0.5),
            #             tha.color_main.alpha())
                    
            #         color_alter = QColor(
            #             int(tha.color_alter.red() * shd + bgcolor.red() * (1.0 - shd) + 0.5),
            #             int(tha.color_alter.green() * shd + bgcolor.green() * (1.0 - shd)+ 0.5),
            #             int(tha.color_alter.blue() * shd + bgcolor.blue() * (1.0 - shd) + 0.5),
            #             tha.color_alter.alpha())
                
            #     else:
            #         color_main, color_alter = tha.color_main, tha.color_alter

            #     port_gradient.setColorAt(0.0, color_main)
            #     port_gradient.setColorAt(0.5, color_alter)
            #     port_gradient.setColorAt(1.0, color_main)
            
            # self.setPen(QPen(port_gradient, tha.base_width, Qt.SolidLine, Qt.FlatCap))
        if True:
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
        
            self.setPen(QPen(QBrush(color_main), tha.base_width * 0.5, Qt.SolidLine, Qt.FlatCap))
        
    def paint(self, painter, option, widget):
        # print('apintnt', self._port_widget._port_name)
        if canvas.loading_items:
            return
        
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        # painter.setPen(QPen(QBrush(color_main), tha.base_width, Qt.SolidLine, Qt.FlatCap))

        QGraphicsPathItem.paint(self, painter, option, widget)

        cosm_pen = QPen(self.pen())
        cosm_pen.setCosmetic(True)
        cosm_pen.setWidthF(1.00001)

        painter.setPen(cosm_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(self.path())

        painter.restore()