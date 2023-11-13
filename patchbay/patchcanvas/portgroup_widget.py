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


# Imports (Global)
import logging
from typing import TYPE_CHECKING

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import (QFontMetrics, QPainter, QBrush,
                         QPolygonF, QLinearGradient, QPen,
                         QColor)
from PyQt5.QtWidgets import QApplication, QGraphicsItem

# Imports (Custom)
from .connectable_widget import ConnectableWidget
from .init_values import (
    CanvasItemType,
    PortSubType,
    PortgrpObject,
    canvas,
    CallbackAct,
    PortMode,
    PortType)

if TYPE_CHECKING:
    from .box_widget import BoxWidget

# -------------------------

_translate = QApplication.translate

# -------------------------

class PortgroupWidget(ConnectableWidget):
    def __init__(self, portgrp: PortgrpObject, parent: 'BoxWidget'):
        ConnectableWidget.__init__(self, portgrp, parent)
        self._logger = logging.getLogger(__name__)

        # Save Variables, useful for later
        self._portgrp = portgrp
        self._portgrp_id = portgrp.portgrp_id

        # Base Variables
        self._portgrp_width  = 15
        self._portgrp_height = canvas.theme.port_height
        
        theme = canvas.theme.portgroup
        if self._port_type is PortType.AUDIO_JACK:
            if self._port_subtype is PortSubType.CV:
                theme = theme.cv
            else:
                theme = theme.audio
        elif self._port_type is PortType.MIDI_JACK:
            theme = theme.midi
        elif self._port_type is PortType.MIDI_ALSA:
            theme = theme.alsa
        elif self._port_type is PortType.VIDEO:
            theme = theme.video
        
        self._theme = theme
        self._portgrp_font = theme.font()

        self._ports_width = canvas.theme.port_grouped_width
        self._print_name = ''
        self._normal_print_name = '' # same as m_print_name but not reduced
        self._print_name_right = ''
        self._name_truncked = False
        self._trunck_sep = '⠿'
        
        self._ports_widgets = [
            p.widget for p in canvas.list_ports(group_id=portgrp.group_id)
            if p.portgrp_id == portgrp.portgrp_id]

        for port_widget in self._ports_widgets:
            port_widget.set_portgroup_widget(self)

    def get_connection_distance(self) -> float:
        return self._portgrp_width

    def type(self) -> CanvasItemType:
        return CanvasItemType.PORTGROUP

    def set_portgrp_width(self, portgrp_width: float):
        self._portgrp_width = portgrp_width

    def set_ports_width(self, ports_width: int):
        self._ports_width = ports_width

    def set_print_name(self, print_name:str, width_limited: int):
        self._print_name = print_name
        self._normal_print_name = print_name
        self._name_truncked = False

        if width_limited:
            #sizer = QFontMetrics(self._port_font)
            long_size = self._theme.get_text_width(self._print_name)
            
            if long_size > width_limited:
                name_len = len(self._print_name)
                middle = int(name_len / 2)
                left_text = self._print_name[:middle]
                middle_text = self._trunck_sep
                right_text = self._print_name[middle + 1:]
                left_size = self._theme.get_text_width(left_text)
                middle_size = self._theme.get_text_width(middle_text)
                right_size = self._theme.get_text_width(right_text)
                
                while left_size + middle_size + right_size > width_limited:
                    if left_size > right_size:
                        left_text = left_text[:-1]
                        left_size = self._theme.get_text_width(left_text)
                    else:
                        right_text = right_text[1:]
                        right_size = self._theme.get_text_width(right_text)
                        
                    if not (left_text or right_text):
                        break

                self._print_name = left_text
                self._print_name_right = right_text
                self._name_truncked = True

    def reduce_print_name(self, width_limited: int):
        self.set_print_name(self._normal_print_name, width_limited)

    def get_text_width(self):
        if self._name_truncked:
            return (self._theme.get_text_width(self._print_name)
                    + self._theme.get_text_width(self._trunck_sep)
                    + self._theme.get_text_width(self._print_name_right))
        
        return self._theme.get_text_width(self._print_name)

    def ensure_selection_with_ports(self):
        for port_widget in self._ports_widgets:
            if not port_widget.isSelected():
                self.setSelected(False)
                return
        self.setSelected(True)

    def itemChange(self, change: int, value: bool):
        if change == QGraphicsItem.ItemSelectedHasChanged:
            self.changing_select_state = True
            
            modify_port_selection = True
            for port_widget in self._ports_widgets:
                if port_widget.changing_select_state:
                    modify_port_selection = False
            
            if modify_port_selection:
                for port_widget in self._ports_widgets:
                    if not port_widget.changing_select_state:
                        port_widget.setSelected(bool(value))

            self.changing_select_state = False

        return QGraphicsItem.itemChange(self, change, value)

    def contextMenuEvent(self, event):        
        if canvas.scene.get_zoom_scale() <= 0.4:
            # prefer move box if zoom is too low
            event.ignore()
            return
        
        if canvas.is_line_mov:
            return

        canvas.scene.clearSelection()
        self.setSelected(True)
        canvas.menu_shown = True

        is_only_connect = bool(
            QApplication.keyboardModifiers() & Qt.ControlModifier)
        
        self.parentItem().setFlag(QGraphicsItem.ItemIsMovable, False)
        
        start_point = canvas.scene.screen_position(
            self.scenePos() + QPointF(0.0, self.boundingRect().bottom()))
        bottom_screen = QApplication.desktop().screenGeometry().bottom()
        more = 12 if self._port_mode is PortMode.OUTPUT else 0

        if start_point.y() + 250 > bottom_screen:
            start_point = canvas.scene.screen_position(
                self.scenePos() + QPointF(self._portgrp_width + more, self._portgrp_height))
        
        canvas.callback(
            CallbackAct.PORTGROUP_MENU_CALL, self._group_id, self._portgrp_id,
            is_only_connect, start_point.x(), start_point.y())

    def boundingRect(self) -> QRectF:
        middle_width = canvas.theme.port_height / 2.0

        if self._port_mode is PortMode.INPUT:
            return QRectF(
                canvas.theme.port_grouped_width, 0.0,
                self._portgrp_width + middle_width - canvas.theme.port_grouped_width,
                canvas.theme.port_height * len(self._port_ids))
        else:
            return QRectF(
                0.0, 0.0,
                self._portgrp_width + middle_width - canvas.theme.port_grouped_width,
                canvas.theme.port_height * len(self._port_ids))

    def paint(self, painter: QPainter, option, widget):
        if canvas.loading_items:
            return

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)

        theme = canvas.theme.portgroup
        
        if self._port_type is PortType.AUDIO_JACK:
            if self._port_subtype is PortSubType.CV:
                theme = theme.cv
            else:
                theme = theme.audio
        elif self._port_type is PortType.MIDI_JACK:
            theme = theme.midi
        elif self._port_type is PortType.MIDI_ALSA:
            theme = theme.alsa
        elif self._port_type is PortType.VIDEO:
            theme = theme.video

        if self.isSelected():
            theme = theme.selected

        poly_image = theme.background_image()
        poly_pen = theme.fill_pen()
        color_main = theme.background_color()
        color_alter = theme.background2_color()
        text_pen = QPen(theme.text_color())

        line_hinting = poly_pen.widthF() / 2.0
        p_height = canvas.theme.port_height
        middle_width = p_height * 0.5

        text_main_height = self._portgrp_font.pixelSize() * 0.667
        text_y_pos = ((p_height * len(self._port_ids)
                       - text_main_height) / 2
                      + text_main_height)

        if self._port_mode is PortMode.INPUT:
            text_pos = QPointF(self._ports_width + 3, text_y_pos)
            
            x_ports_border = self._ports_width - line_hinting
            x_arrowbase = self._portgrp_width - middle_width - line_hinting
            x_arrowmid = self._portgrp_width - middle_width / 2 - line_hinting
            x_arrowhead = self._portgrp_width - 2 * line_hinting

        elif self._port_mode is PortMode.OUTPUT:
            text_pos = QPointF(3.0 + middle_width, text_y_pos)
            
            x_ports_border = (self._portgrp_width - self._ports_width
                              + line_hinting)
            x_arrowbase = middle_width + line_hinting
            x_arrowmid = middle_width / 2.0 + line_hinting
            x_arrowhead = line_hinting * 2

        else:
            self._logger.critical(f"CanvasPortGroup.paint() - "
                                  "invalid port mode {str(self._port_mode)}")
            return

        y_top = line_hinting
        y_bottom = p_height * len(self._port_ids) - line_hinting

        if self._port_type is PortType.MIDI_JACK:            
            points = [(x_ports_border, y_top),
                      (x_arrowbase, y_top),
                      (x_arrowbase + (x_arrowmid - x_arrowbase) * 0.62,
                       p_height * 0.15),
                      (x_arrowmid, p_height * 0.40),
                      (x_arrowmid, p_height * (len(self._port_ids) - 0.40)),
                      (x_arrowbase + (x_arrowmid - x_arrowbase) * 0.62,
                       p_height * (len(self._port_ids) - 0.15)),
                      (x_arrowbase, y_bottom),
                      (x_ports_border, y_bottom),
                      (x_ports_border, y_top)]

        elif self._port_subtype is PortSubType.CV:
            points = [(x_ports_border, y_top),
                      (x_arrowbase, y_top),
                      (x_arrowbase, y_bottom),
                      (x_ports_border, y_bottom),
                      (x_ports_border, y_top)]

        elif self._port_type is PortType.MIDI_ALSA:
            points = [(x_ports_border, y_top),
                      (x_arrowmid, y_top),
                      (x_arrowmid, y_bottom),
                      (x_ports_border, y_bottom),
                      (x_ports_border, y_top)]

        elif self._port_type is PortType.VIDEO:
            points = [(x_ports_border, y_top),
                      (x_arrowhead, y_top),
                      (x_arrowhead, y_bottom),
                      (x_ports_border, y_bottom),
                      (x_ports_border, y_top)]
        else:
            points = [(x_ports_border, y_top),
                      (x_arrowbase, y_top),
                      (x_arrowhead, p_height * 0.5),
                      (x_arrowhead, p_height * (len(self._port_ids) - 0.5)),
                      (x_arrowbase, y_bottom),
                      (x_ports_border, y_bottom),
                      (x_ports_border, y_top)]
        
        polygon = QPolygonF()
        for xy in points:
            polygon += QPointF(*xy)

        if poly_image is not None:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(poly_image))
            painter.drawPolygon(polygon)

        if color_alter is not None:
            portgrp_gradient = QLinearGradient(0, 0, 0, self._portgrp_height * 2)
            portgrp_gradient.setColorAt(0, color_main)
            portgrp_gradient.setColorAt(0.5, color_alter)
            portgrp_gradient.setColorAt(1, color_main)

            painter.setBrush(portgrp_gradient)
        else:
            painter.setBrush(color_main)
            
        painter.setPen(poly_pen)
        painter.drawPolygon(polygon)

        if self._port_subtype is PortSubType.CV:
            cv_line_pen = QPen(poly_pen)
            cv_line_pen.setWidthF(p_height * 0.167)
            llh = cv_line_pen.widthF() * 0.5
            painter.setPen(cv_line_pen)

            y_line_pos = len(self._port_ids) * p_height * 0.5
            if self._port_mode is PortMode.OUTPUT:
                painter.drawLine(
                    QPointF(x_arrowhead + llh, y_line_pos),
                    QPointF(x_arrowbase - llh, y_line_pos))
            else:
                painter.drawLine(
                    QPointF(x_arrowhead - llh, y_line_pos),
                    QPointF(x_arrowbase + llh, y_line_pos))

        if (self._port_type is PortType.MIDI_ALSA
                or self._port_subtype is PortSubType.A2J):
            parent = self.parentItem()
            box_theme = parent.get_theme()
            if parent.isSelected():
                box_theme = box_theme.selected

            scene_col = canvas.theme.scene_background_color
            box_bg_col = box_theme.background_color()
            ra = box_bg_col.alphaF()
            rb = 1.0 - ra
            
            circle_bg_col = QColor()
            circle_bg_col.setRgbF(
                scene_col.redF() * rb + box_bg_col.redF() * ra,
                scene_col.greenF() * rb + box_bg_col.greenF() * ra,
                scene_col.blueF() * rb + box_bg_col.blueF() * ra)
            
            painter.setBrush(circle_bg_col)
            painter.setPen(poly_pen)
            
            radius = abs(x_arrowhead - x_arrowmid) * 0.667            
            painter.drawEllipse(
                QPointF(x_arrowmid, p_height * len(self._port_ids) * 0.5),
                radius, radius)

        painter.setPen(text_pen)
        painter.setFont(self._portgrp_font)
        painter.drawText(text_pos, self._print_name)
        if self._name_truncked:
            sizer = QFontMetrics(self._portgrp_font)
            sep_x = text_pos.x() + sizer.width(self._print_name)
            sep_width = sizer.width(self._trunck_sep)

            painter.drawText(QPointF(sep_x + sep_width, text_pos.y()),
                             self._print_name_right)

            trunck_pen = QPen(text_pen)
            color = text_pen.color()
            color.setAlphaF(color.alphaF() * 0.25)
            trunck_pen.setColor(color)
            painter.setPen(trunck_pen)
            
            painter.drawText(QPointF(sep_x, text_pos.y() + 1), self._trunck_sep)

        painter.restore()

