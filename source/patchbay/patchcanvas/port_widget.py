#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# PatchBay Canvas engine using QGraphicsView/Scene
# Copyright (C) 2010-2019 Filipe Coelho <falktx@falktx.com>
# Copyright (C) 2019-2023 Mathieu Picot <picotmathieu@gmail.com>
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


import logging
from typing import TYPE_CHECKING

from qtpy.QtCore import Qt, QPointF, QRectF
from qtpy.QtGui import (
    QBrush, QFontMetrics, QPainter, QPen, QPolygonF,
    QLinearGradient, QColor, QPainterPath)
from qtpy.QtWidgets import QGraphicsItem, QApplication


# Imports (Custom)
from patshared import PortMode, PortType, PortSubType
from .init_values import (
    CanvasItemType, PortObject, canvas, ZvBox)
from .connectable_widget import ConnectableWidget
from .grouped_lines_widget import GroupedLinesWidget

if TYPE_CHECKING:
    from .box_widget_moth import BoxWidgetMoth
    from .portgroup_widget import PortgroupWidget
    

# --------------------

class PortWidget(ConnectableWidget):
    def __init__(self, port: PortObject, parent: 'BoxWidgetMoth'):
        ConnectableWidget.__init__(self, port, parent)        
        self._logger = logging.getLogger(__name__)

        # Save Variables, useful for later
        self._port = port
        self._port_id = port.port_id
        self._port_name = port.port_name
        self._portgrp_id = port.portgrp_id
        self._pg_pos = port.pg_pos
        self._pg_len = port.pg_len
        self._port_subtype = port.port_subtype
        self._print_name = port.port_name
        self._print_name_right = ''
        self._name_truncked = False
        self._trunck_sep = '⠿'

        # Base Variables
        self._port_width = 15

        theme = canvas.theme.port
        if self._port_type == PortType.AUDIO_JACK:
            if self._port_subtype is PortSubType.CV:
                theme = theme.cv
            else:
                theme = theme.audio
        elif self._port_type == PortType.MIDI_JACK:
            theme = theme.midi
        
        self._theme = theme
        self._port_font = theme.font

        self._portgrp_widget = None
        self._loop_select_done = False

        self._connect_pos = QPointF(0.0, 0.0)
        self._update_connect_pos()
        self.setZValue(ZvBox.PORT.value)

    def get_port_id(self) -> int:
        return self._port_id

    def get_connection_distance(self) -> float:
        return self._port_width

    def get_port_width(self) -> float:
        return self._port_width

    def set_portgroup_id(self, portgrp_id: int, index: int, portgrp_len: int):
        self._portgrp_id = portgrp_id
        self._pg_pos = index
        self._pg_len = portgrp_len
        self._update_connect_pos()

    def set_portgroup_widget(self, widget: 'PortgroupWidget'):
        self._portgrp_widget = widget

    def set_port_name(self, port_name: str):
        self._port_name = port_name
        self._update_connect_pos()

    def set_port_width(self, port_width):
        self._port_width = port_width
        self._update_connect_pos()

    def set_print_name(self, print_name:str, width_limited: int):
        self._print_name = print_name
        self._name_truncked = False

        if width_limited:
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
        self._update_connect_pos()

    def get_text_width(self) -> float:
        if self._name_truncked:
            return (self._theme.get_text_width(self._print_name)
                    + self._theme.get_text_width(self._trunck_sep)
                    + self._theme.get_text_width(self._print_name_right))
        
        return self._theme.get_text_width(self._print_name)

    def set_as_stereo(self, port_id: int):
        canvas.cb.portgroup_add(
            self._group_id, self._port_mode, self._port_type,
            tuple([p.port_id for p in canvas.list_ports(group_id=self._group_id)
                   if p.port_id in (self._port_id, port_id)]))

    def type(self) -> CanvasItemType:
        return CanvasItemType.PORT

    def _update_connect_pos(self):
        phi = 0.75 if self._pg_len > 2 else 0.62
        
        height = canvas.theme.port_height
        
        x_delta = (self._port_width if self._port_mode is PortMode.OUTPUT
                   else 0.0)
        y_delta = canvas.theme.port_height / 2
        
        if self._pg_len >= 2:
            first_old_y = height * phi
            last_old_y = height * (self._pg_len - phi)
            delta = (last_old_y - first_old_y) / (self._pg_len -1)
            y_delta = (first_old_y
                       + (self._pg_pos * delta)
                       - (height * self._pg_pos))
            
        if not self.isVisible():
            # item is hidden port when its box is folded
            y_delta = height - y_delta

        self._connect_pos = QPointF(x_delta, y_delta)

    def connect_pos(self) -> QPointF:
        return self.scenePos() + self._connect_pos # type:ignore

    def setVisible(self, visible: bool):
        super().setVisible(visible)
        self._update_connect_pos()

    def itemChange(
            self, change: QGraphicsItem.GraphicsItemChange, value: bool):
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:            
            if self.changing_select_state:
                self.changing_select_state = False
                return
            
            self.changing_select_state = True

            if self._portgrp_widget is not None:
                if self._portgrp_widget.mouse_releasing:
                    self.setSelected(self._portgrp_widget.isSelected())
                elif not self._portgrp_widget.changing_select_state:
                    self._portgrp_widget.ensure_selection_with_ports()
            
            self.setZValue(ZvBox.SEL_PORT.value if self.isSelected()
                           else ZvBox.PORT.value)

            connections = [c for c in canvas.list_connections(self._port)]
            
            if connections:
                other_group_ids = set[int]()
                selected = self.isSelected()

                if self._port_mode is PortMode.OUTPUT:
                    for conn in connections:
                        conn.out_selected = selected
                        other_group_ids.add(conn.group_in_id)

                    for in_group_id in other_group_ids:
                        GroupedLinesWidget.connections_changed(
                            self._group_id, in_group_id)
                       
                elif self._port_mode is PortMode.INPUT:
                    for conn in connections:
                        conn.in_selected = selected
                        other_group_ids.add(conn.group_out_id)
                
                    for out_group_id in other_group_ids:
                        GroupedLinesWidget.connections_changed(
                            out_group_id, self._group_id)

            self.changing_select_state = False

        return QGraphicsItem.itemChange(self, change, value)

    def contextMenuEvent(self, event):
        if canvas.scene.get_zoom_scale() <= 0.4:
            # prefer move box if zoom is too low
            event.ignore()
            return
        
        if canvas.is_line_mov:
            return

        event.accept()
        canvas.scene.clearSelection()
        self.setSelected(True)

        canvas.menu_shown = True
        is_only_connect = bool(
            QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier)

        # precise the menu start point to still view the port
        # and be able to read its portgroup name.
        start_point = canvas.scene.screen_position(
            self.scenePos() + QPointF(0.0, canvas.theme.port_height)) # type:ignore
        
        if (self._portgrp_id and self._port_mode is PortMode.INPUT
                and self._pg_pos + 1 <= self._pg_len // 2):
            start_point = canvas.scene.screen_position(
                self.scenePos() + QPointF(
                    0.0, canvas.theme.port_height * (0.5 + self._pg_len / 2.0))) # type:ignore
            
        bottom_screen = QApplication.primaryScreen().geometry().bottom()
        more = 12 if self._port_mode is PortMode.OUTPUT else 0

        if start_point.y() + 250 > bottom_screen:
            start_point = canvas.scene.screen_position(
                self.scenePos()
                + QPointF(self._port_width + more, canvas.theme.port_height)) # type:ignore
        
        canvas.cb.port_menu_call(
            self._group_id, self._port_id,
            is_only_connect, start_point.x(), start_point.y())

    def boundingRect(self):
        return QRectF(0.0, 0.0, self._port_width, canvas.theme.port_height)

    def mousePressEvent(self, event):
        if (self._portgrp_widget is not None
                and self._portgrp_widget.isSelected()):
            self._portgrp_widget.setSelected(False)
        super().mousePressEvent(event)

    def paint(self, painter, option, widget):
        if canvas.loading_items:
            return
        
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        
        theme = canvas.theme.port

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
        
        poly_image = theme.background_image
        poly_color = theme.background_color
        poly_color_alter = theme.background2_color
        poly_pen = theme.fill_pen
        text_pen = QPen(theme.text_color)

        # To prevent quality worsening
        poly_pen = QPen(poly_pen)
        poly_pen.setWidthF(poly_pen.widthF() + 0.00001)

        line_hinting = poly_pen.widthF() / 2
        p_height = canvas.theme.port_height
        
        text_y_pos = ((p_height - 0.667 * self._port_font.pixelSize()) / 2
                      + self._port_font.pixelSize() * 0.667)

        middle_width = p_height * 0.5
        is_cv_port = bool(self._port_subtype is PortSubType.CV)
        y_top = line_hinting
        y_bottom = p_height - line_hinting

        if self._port_mode is PortMode.INPUT:
            text_pos = QPointF(3.0, text_y_pos)

            x_box_border = line_hinting
            x_arrowbase = self._port_width - middle_width - line_hinting
            x_arrowmid = self._port_width - middle_width / 2 - line_hinting
            x_arrowhead = self._port_width - line_hinting * 2

        elif self._port_mode is PortMode.OUTPUT:
            text_pos = QPointF(middle_width + 3.0, text_y_pos)

            x_box_border = self._port_width - line_hinting
            x_arrowbase = middle_width + line_hinting
            x_arrowmid = middle_width / 2 + line_hinting
            x_arrowhead = line_hinting * 2

        else:
            self._logger.critical(
                f"paint() - invalid port mode {str(self._port_mode)}")
            return

        polygon = QPolygonF()

        if self._portgrp_id:
            first_of_portgrp = bool(self._pg_pos == 0)
            last_of_portgrp = bool(self._pg_pos + 1 == self._pg_len)

            if first_of_portgrp:
                points = [(line_hinting, y_top),
                          (self._port_width - line_hinting, y_top)]
            else:
                points = [(line_hinting, 0.0),
                          (self._port_width - line_hinting, 0.0)]

            if last_of_portgrp:
                points += [(self._port_width - line_hinting, y_bottom),
                           (line_hinting, y_bottom)]
            else:
                points += [(self._port_width - line_hinting, p_height),
                           (line_hinting, p_height)]

        elif self._port_type is PortType.MIDI_JACK:
            points = [(x_box_border, y_top),
                      (x_arrowbase, y_top),
                      (x_arrowbase + (x_arrowmid - x_arrowbase) * 0.62,
                       p_height * 0.15),
                      (x_arrowmid, p_height * 0.40),
                      (x_arrowmid, p_height * 0.60),
                      (x_arrowbase + (x_arrowmid - x_arrowbase) * 0.62,
                       p_height * 0.85),
                      (x_arrowbase, y_bottom),
                      (x_box_border, y_bottom),
                      (x_box_border, y_top)]

        elif is_cv_port:
            points = [(x_box_border, y_top),
                      (x_arrowbase, y_top),
                      (x_arrowbase, y_bottom),
                      (x_box_border, y_bottom)]

        elif self._port_type is PortType.MIDI_ALSA:
            points = [(x_box_border, y_top),
                      (x_arrowmid, y_top),
                      (x_arrowmid, y_bottom),
                      (x_box_border, y_bottom)]

        elif self._port_type is PortType.VIDEO:
            x_cam_base = x_box_border + x_arrowhead - x_arrowbase
            
            points = [(x_box_border, y_top),
                      (x_cam_base, y_top + y_bottom * 0.3),
                      (x_cam_base, y_top),
                      (x_arrowhead, y_top),
                      (x_arrowhead, y_bottom),
                      (x_cam_base, y_bottom),
                      (x_cam_base, y_bottom * 0.7),
                      (x_box_border, y_bottom),
                      (x_box_border, y_top)]

        else:
            points = [(x_box_border, y_top),
                      (x_arrowbase, y_top),
                      (x_arrowhead, p_height * 0.5),
                      (x_arrowbase, y_bottom),
                      (x_box_border, y_bottom),
                      (x_box_border, y_top)]

        for xy in points:
            polygon += QPointF(*xy)

        if poly_image is not None:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(poly_image))
            painter.drawPolygon(polygon)

        if poly_color_alter is not None:
            port_gradient = QLinearGradient(0, 0, 0, canvas.theme.port_height)

            port_gradient.setColorAt(0, poly_color)
            port_gradient.setColorAt(0.5, poly_color_alter)
            port_gradient.setColorAt(1, poly_color)

            painter.setBrush(port_gradient)
        else:
            painter.setBrush(poly_color)
        
        painter.setPen(poly_pen)
        painter.drawPolygon(polygon)

        if not self._portgrp_id:
            if self._port_subtype is PortSubType.CV:
                poly_pen.setWidthF(p_height * 0.167)
                llh = poly_pen.widthF() * 0.5
                painter.setPen(poly_pen)

                y_line = canvas.theme.port_height / 2.0
                if self._port_mode is PortMode.OUTPUT:
                    painter.drawLine(
                        QPointF(x_arrowhead + llh, y_line),
                        QPointF(x_arrowbase - llh, y_line))
                elif self._port_mode is PortMode.INPUT:
                    painter.drawLine(
                        QPointF(x_arrowhead - llh, y_line),
                        QPointF(x_arrowbase + llh, y_line))

            elif (self._port_subtype is PortSubType.A2J
                    or self._port_type is PortType.MIDI_ALSA):
                # draw the little circle for a2j (or MidiBridge) port.                
                # we emulate a hole in the port, so we need the background
                # of the box.

                parent = self.parentItem()
                box_theme = parent.get_theme()
                if parent.isSelected():
                    box_theme = box_theme.selected

                scene_col = canvas.theme.scene_background_color
                box_bg_col = box_theme.background_color
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
                    QPointF(x_arrowmid, p_height / 2.0), radius, radius)

        painter.setPen(text_pen)
        painter.setFont(self._port_font)

        sizer = QFontMetrics(self._port_font)
        sep_width = sizer.horizontalAdvance(self._trunck_sep)

        if self._portgrp_id:
            print_name_size = self.get_text_width()

            if self._port_mode is PortMode.OUTPUT:
                text_pos = QPointF(self._port_width - 3 - print_name_size,
                                   text_y_pos)

        elif self._port_type is PortType.VIDEO:
            if self._port_mode is PortMode.OUTPUT:
                text_pos.setX(text_pos.x() - middle_width)
            else:
                text_pos.setX(text_pos.x() + middle_width)

        painter.drawText(text_pos, self._print_name)
        
        if self._name_truncked:
            sep_x = text_pos.x() + sizer.horizontalAdvance(self._print_name)
            
            painter.drawText(QPointF(sep_x + sep_width, text_pos.y()),
                             self._print_name_right)

            trunck_pen = QPen(text_pen)
            color = text_pen.color()
            color.setAlphaF(color.alphaF() * 0.25)
            trunck_pen.setColor(color)
            painter.setPen(trunck_pen)
            painter.drawText(QPointF(sep_x, text_pos.y() + 1), self._trunck_sep)

        painter.restore()
