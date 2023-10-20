#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# PatchBay Canvas engine using QGraphicsView/Scene
# Copyright (C) 2010-2019 Filipe Coelho <falktx@falktx.com>
# Copyright (C) 2019-2022 Mathieu Picot <picotmathieu@gmail.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of
# the License, or any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# For a full copy of the GNU General Public License see the doc/GPL.txt file.

from enum import Enum
import time
from typing import TYPE_CHECKING, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtGui import (QColor, QLinearGradient, QPainter,
                         QPainterPath, QPen, QBrush)
from PyQt5.QtWidgets import QGraphicsPathItem

from .init_values import (
    GroupObject,
    canvas,
    options,
    CanvasItemType,
    CallbackAct,
    PortType)

if TYPE_CHECKING:
    from .port_widget import PortWidget
    from .box_widget import BoxWidget


class _ThemeAttributes:
    base_pen: QPen
    color_main: QColor
    color_alter: Optional[QColor]
    base_width: float


class GroupedLinesWidget(QGraphicsPathItem):
    def __init__(self, group_out_id: int, group_in_id: int,
                 port_type: PortType):
        ''' Class for connection line widget '''
        QGraphicsPathItem.__init__(self)

        self._group_out_id = group_out_id
        self._group_in_id = group_in_id
        self._port_type = port_type

        self._semi_hidden = False        
        
        self._th_attribs: _ThemeAttributes = None
        self.update_theme()
        self.update_line_gradient()

        self.setBrush(QColor(0, 0, 0, 0))
        self.setGraphicsEffect(None)
        self.update_lines_pos()

    def semi_hide(self, yesno: bool):
        self._semi_hidden = yesno
        self.update_line_gradient()

    def update_lines_pos(self):
        paths = dict[tuple[float, float], QPainterPath]()

        for conn in canvas.list_connections(
                group_out_id=self._group_out_id,
                group_in_id=self._group_in_id):
            port_out = canvas.get_port(self._group_out_id, conn.port_out_id)
            # group_out = canvas.get_group(self._group_out_id)
            # if group_out.group_name == 'SamplesFX3Reverb (In)':
            #     print('Pofo', port_out.port_name, port_in.port_name)
            
            if port_out.port_type is not self._port_type:
                continue
            
            port_in = canvas.get_port(self._group_in_id, conn.port_in_id)
            
            port_out_con_pos = port_out.widget.connect_pos()
            port_in_con_pos = port_in.widget.connect_pos()
            
            item1_x = port_out_con_pos.x()
            item1_y = port_out_con_pos.y()
            item2_x = port_in_con_pos.x()
            item2_y = port_in_con_pos.y()

            if (item1_y, item2_y) in paths.keys():
                # same coords, do not draw 2 times the same path.
                # (both boxes are wrapped very probably).
                continue
            
            existing_path = False
            
            for key, value in paths.items():
                y1, y2 = key
                if item1_y - y1 == item2_y - y2:
                    paths[(item1_y, item2_y)] = value.translated(
                        0.0, item1_y - y1)
                    existing_path = True
                    break
            
            if existing_path:
                continue

            x_diff = item2_x - item1_x
            mid_x = abs(x_diff) / 2

            diffxy = abs(item1_y - item2_y) - abs(x_diff)
            if diffxy > 0:
                mid_x += diffxy

            mid_x = min(mid_x, max(200.0, x_diff / 2))

            path = QPainterPath(port_out_con_pos)
            # path = QPainterPath(item1_con_pos)
            path.cubicTo(item1_x + mid_x, item1_y,
                         item2_x - mid_x, item2_y,
                         item2_x, item2_y)
            
            paths[(item1_y, item2_y)] = path

        main_path = QPainterPath()
        for path in paths.values():
            main_path.addPath(path)

        self.setPath(main_path)
        
        self.update_line_gradient()

    def type(self) -> CanvasItemType:
        return CanvasItemType.BEZIER_LINE

    def update_theme(self):
        theme = canvas.theme.line
        if self._port_type is PortType.AUDIO_JACK:
            theme = theme.audio
        elif self._port_type is PortType.MIDI_JACK:
            theme = theme.midi
        elif self._port_type is PortType.MIDI_ALSA:
            theme = theme.alsa
        elif self._port_type is PortType.VIDEO:
            theme = theme.video

        tha = _ThemeAttributes()
        tha.base_pen = theme.fill_pen()
        tha.color_main = theme.background_color()
        tha.color_alter = theme.background2_color()
        if tha.color_alter is None:
            tha.color_alter = tha.color_main
        tha.base_width = tha.base_pen.widthF() + 0.000001
        self._th_attribs = tha

    def update_line_gradient(self):
        pos_top = self.boundingRect().top()
        pos_bot = self.boundingRect().bottom()

        tha = self._th_attribs
        
        has_gradient = bool(tha.color_main != tha.color_alter)
        
        if has_gradient:
            port_gradient = QLinearGradient(0, pos_top, 0, pos_bot)

            if self._semi_hidden:
                shd = options.semi_hide_opacity
                bgcolor = canvas.theme.scene_background_color
                
                color_main = QColor(
                    int(tha.color_main.red() * shd + bgcolor.red() * (1.0 - shd) + 0.5),
                    int(tha.color_main.green() * shd + bgcolor.green() * (1.0 - shd)+ 0.5),
                    int(tha.color_main.blue() * shd + bgcolor.blue() * (1.0 - shd) + 0.5),
                    tha.color_main.alpha())
                
                color_alter = QColor(
                    int(tha.color_alter.red() * shd + bgcolor.red() * (1.0 - shd) + 0.5),
                    int(tha.color_alter.green() * shd + bgcolor.green() * (1.0 - shd)+ 0.5),
                    int(tha.color_alter.blue() * shd + bgcolor.blue() * (1.0 - shd) + 0.5),
                    tha.color_alter.alpha())
            
            else:
                color_main, color_alter = tha.color_main, tha.color_alter

            port_gradient.setColorAt(0.0, color_main)
            port_gradient.setColorAt(0.5, color_alter)
            port_gradient.setColorAt(1.0, color_main)
            
            self.setPen(QPen(port_gradient, tha.base_width, Qt.SolidLine, Qt.FlatCap))
        else:
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
        
            self.setPen(QPen(QBrush(color_main), tha.base_width, Qt.SolidLine, Qt.FlatCap))
        
    # def paint(self, painter, option, widget):
    #     if canvas.loading_items:
    #         return

    #     painter.save()
    #     if True:
    #     # if canvas.antialiasing:
    #         painter.setRenderHint(QPainter.Antialiasing, True)

    #     # print('okelmz', painter.boundingRect())

    #     QGraphicsPathItem.paint(self, painter, option, widget)

    #     cosm_pen = QPen(self.pen())
    #     cosm_pen.setCosmetic(True)
    #     cosm_pen.setWidthF(1.00001)

    #     painter.setPen(cosm_pen)
    #     painter.setBrush(Qt.NoBrush)
    #     painter.drawPath(self.path())

    #     painter.restore()
