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

from typing import TYPE_CHECKING, Optional, Iterator

from PyQt5.QtCore import Qt
from PyQt5.QtGui import (QColor, QLinearGradient,
                         QPainterPath, QPen, QBrush)
from PyQt5.QtWidgets import QGraphicsPathItem

from .init_values import (
    ConnectionThemeState,
    BoxHidding,
    canvas,
    options,
    CanvasItemType,
    PortType,
    PortMode,
    Zv)


_groups_to_check = set[tuple[int, int]]()
_all_lines_widgets = {}


if TYPE_CHECKING:
    _all_lines_widgets: dict[
        tuple[int, int],
        dict[PortType, dict[ConnectionThemeState,
                            'GroupedLinesWidget']]]


class GroupOutInsDict(dict):
    def __init__(self):
        dict.__init__(self)
    
    def add_group_ids(self, group_out_id: int, group_in_id: int):
        gp_set: Optional[set] = self.get(group_out_id)
        if gp_set is None:
            self[group_out_id] = gp_set = set()
        gp_set.add(group_in_id)
        
    def send_changes(self):
        for group_out_id, group_in_ids in self.items():
            for group_in_id in group_in_ids:
                GroupedLinesWidget.connections_changed(
                    group_out_id, group_in_id)


class _ThemeAttributes:
    base_pen: QPen
    color_main: QColor
    color_alter: Optional[QColor]
    base_width: float


class GroupedLinesWidget(QGraphicsPathItem):
    def __init__(self, group_out_id: int, group_in_id: int,
                 port_type: PortType,
                 theme_state: ConnectionThemeState):
        ''' Class for connection line widget '''
        QGraphicsPathItem.__init__(self)

        self._group_out_id = group_out_id
        self._group_in_id = group_in_id
        self._port_type = port_type

        self._group_out_x = 0.0
        self._group_in_x = 0.0
        self._group_out_mid_y = 0.0
        self._group_in_mid_y = 0.0

        self._semi_hidden = False        
        
        self._th_attribs: _ThemeAttributes = None
        self._theme_state = theme_state
        self.update_theme()
        
        if theme_state is ConnectionThemeState.SELECTED:
            self.setZValue(Zv.SEL_LINE.value)
        else:
            self.setZValue(Zv.LINE.value)

        self._box_hidding_out = BoxHidding.NONE
        self._box_hidding_in = BoxHidding.NONE

        for hbox in canvas.scene.hidding_boxes:
            if hbox.get_group_id() is group_out_id:
                self._box_hidding_out = BoxHidding.HIDDING
            if hbox.get_group_id() is group_in_id:
                self._box_hidding_in = BoxHidding.HIDDING
        
        for rbox in canvas.scene.restore_boxes:
            if rbox.get_group_id() is group_out_id:
                self._box_hidding_out = BoxHidding.RESTORING
            if rbox.get_group_id() is group_in_id:
                self._box_hidding_in = BoxHidding.RESTORING

        self.update_lines_pos(fast_move=True)
        if (self._box_hidding_out is not BoxHidding.NONE
                or self._box_hidding_in is not BoxHidding.NONE):
            self.animate_hidding(0.0)
        else:
            self.update_line_gradient()

    @staticmethod
    def clear_all_widgets():
        'does not remove widgets from scene, it has to be down elsewhere.'
        _all_lines_widgets.clear()

    @staticmethod
    def prepare_conn_changes(group_out_id: int, group_in_id: int):
        _groups_to_check.add((group_out_id, group_in_id))
        
    @staticmethod
    def change_all_prepared_conns():
        for gp_outin in _groups_to_check:
            GroupedLinesWidget.connections_changed(*gp_outin)
        _groups_to_check.clear()

    @staticmethod
    def connections_changed(group_out_id: int, group_in_id: int):
        gp_dict = _all_lines_widgets.get((group_out_id, group_in_id))
        if gp_dict is None:
            gp_dict = {}
            _all_lines_widgets[(group_out_id, group_in_id)] = gp_dict
        
        to_update = dict[PortType, set[ConnectionThemeState]]()
        new_widgets = set[GroupedLinesWidget]()
        
        for conn in canvas.list_connections(
                group_out_id=group_out_id, group_in_id=group_in_id):
            theme_state = conn.theme_state()

            to_update_type = to_update.get(conn.port_type)
            if to_update_type is None:
                to_update_type = set()
                to_update[conn.port_type] = to_update_type
            to_update_type.add(theme_state)

            pt_dict = gp_dict.get(conn.port_type)
            if pt_dict is None:
                pt_dict = {}
                gp_dict[conn.port_type] = pt_dict

            widget = pt_dict.get(theme_state)
            if widget is None:
                pt_dict[theme_state] = GroupedLinesWidget(
                    group_out_id, group_in_id, conn.port_type,
                    theme_state)
                canvas.scene.addItem(pt_dict[theme_state])
                new_widgets.add(pt_dict[theme_state])

        for port_type in gp_dict.keys():
            pt_dict = gp_dict.get(port_type)
            if pt_dict is None:
                continue

            if port_type not in to_update.keys():
                if pt_dict is not None:
                    for widget in pt_dict.values():
                        canvas.scene.removeItem(widget)
                    pt_dict.clear()
                continue
            
            attrs_to_del = set[ConnectionThemeState]()
            
            for theme_state, widget in pt_dict.items():
                if theme_state not in to_update[port_type]:
                    canvas.scene.removeItem(widget)
                    attrs_to_del.add(theme_state)
                elif widget not in new_widgets:
                    widget.update_theme()
                    widget.update_lines_pos()
                    
            for attr_to_del in attrs_to_del:
                pt_dict.__delitem__(attr_to_del)

    @staticmethod
    def widgets_for_box(
            group_id: int, port_mode: PortMode) -> Iterator['GroupedLinesWidget']:
        if port_mode is PortMode.OUTPUT:
            gp_keys = [g for g in _all_lines_widgets if g[0] == group_id]
        elif port_mode is PortMode.INPUT:
            gp_keys = [g for g in _all_lines_widgets if g[1] == group_id]
        elif port_mode is PortMode.BOTH:
            gp_keys = [g for g in _all_lines_widgets if group_id in g]
        else:
            gp_keys = []
        
        for gp_key in gp_keys:
            for pt_dict in _all_lines_widgets[gp_key].values():
                for widget in pt_dict.values():
                    yield widget

    @staticmethod
    def groups_semi_hidden(group_ids: set[int]):
        for gp_dict, pt_dict in _all_lines_widgets.items():
            gp_out_id, gp_in_id = gp_dict
            semi_hidden = (gp_out_id in group_ids and gp_in_id in group_ids)
            
            for tstate_dict in pt_dict.values():
                for widget in tstate_dict.values():
                    widget.semi_hide(semi_hidden)
                    widget.setZValue(
                        Zv.OPAC_LINE.value if semi_hidden else Zv.LINE.value)

    @staticmethod
    def update_opacity():
        for pt_dict in _all_lines_widgets.values():
            for tstate_dict in pt_dict.values():
                for widget in tstate_dict.values():
                    if widget._semi_hidden:
                        widget.update_line_gradient()

    @staticmethod
    def animation_finished():
        for pt_dict in _all_lines_widgets.values():
            for tstate_dict in pt_dict.values():
                for widget in tstate_dict.values():
                    widget.set_mode_hidding(PortMode.BOTH, BoxHidding.NONE)

    def semi_hide(self, yesno: bool):
        self._semi_hidden = yesno
        self.update_line_gradient()

    def update_lines_pos(self, fast_move=False):
        paths = dict[tuple[float, float], QPainterPath]()

        groups_x_done = False
        group_out_min_y = float('inf')
        group_out_max_y = float('-inf')
        group_in_min_y = float('inf')
        group_in_max_y = float('-inf')

        for conn in canvas.list_connections(
                group_out_id=self._group_out_id,
                group_in_id=self._group_in_id):
            if conn.port_type is not self._port_type:
                continue
            
            if conn.theme_state() is not self._theme_state:
                continue
            
            port_out = canvas.get_port(self._group_out_id, conn.port_out_id)
            port_in = canvas.get_port(self._group_in_id, conn.port_in_id)
            
            port_out_con_pos = port_out.widget.connect_pos()
            port_in_con_pos = port_in.widget.connect_pos()
            
            item1_x = port_out_con_pos.x()
            item1_y = port_out_con_pos.y()
            item2_x = port_in_con_pos.x()
            item2_y = port_in_con_pos.y()
            
            if not groups_x_done:
                self._group_out_x = item1_x
                self._group_in_x = item2_x

            if (item1_y, item2_y) in paths.keys():
                # same coords, do not draw 2 times the same path.
                # (both boxes are very probably wrapped).
                continue

            group_out_min_y = min(group_out_min_y, item1_y)
            group_out_max_y = max(group_out_max_y, item1_y)
            group_in_min_y = min(group_in_min_y, item2_y)
            group_in_max_y = max(group_in_max_y, item2_y)
            
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
            path.cubicTo(item1_x + mid_x, item1_y,
                         item2_x - mid_x, item2_y,
                         item2_x, item2_y)
            
            paths[(item1_y, item2_y)] = path

        main_path = QPainterPath()
        for path in paths.values():
            main_path.addPath(path)

        self.setPath(main_path)

        self._group_out_mid_y = (group_out_max_y + group_out_min_y) * 0.5
        self._group_in_mid_y = (group_in_max_y + group_in_min_y) * 0.5
        
        if not fast_move:
            # line gradient is not updated at mouse move event or when box 
            # is moved by animation. It makes win few time and so avoid some
            # graphic jerks.
            self.update_line_gradient()

    def type(self) -> CanvasItemType:
        return CanvasItemType.BEZIER_LINE

    def update_theme(self):
        theme = canvas.theme.line
        if self._theme_state is ConnectionThemeState.DISCONNECTING:
            theme = theme.disconnecting
        elif self._port_type is PortType.AUDIO_JACK:
            theme = theme.audio
        elif self._port_type is PortType.MIDI_JACK:
            theme = theme.midi
        elif self._port_type is PortType.MIDI_ALSA:
            theme = theme.alsa
        elif self._port_type is PortType.VIDEO:
            theme = theme.video

        if self._theme_state is ConnectionThemeState.SELECTED:
            theme = theme.selected

        tha = _ThemeAttributes()
        tha.base_pen = theme.fill_pen()
        tha.color_main = theme.background_color()
        tha.color_alter = theme.background2_color()
        if tha.color_alter is None:
            tha.color_alter = tha.color_main
        tha.base_width = tha.base_pen.widthF()
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
        
            self.setPen(QPen(QBrush(color_main),
                             tha.base_width, Qt.SolidLine, Qt.FlatCap))
            
    def animate_hidding(self, ratio: float):
        '''animate hidding or restoring of connections.
        'ratio' goes from 0.0 (animation start) to 1.0 (animation end).'''
        
        if (self._box_hidding_out is BoxHidding.NONE
                and self._box_hidding_in is BoxHidding.NONE):
            self.update_line_gradient()
            return

        epsy = 0.001
        
        if ratio >= 1.0:
            # Animation finished
            
            if (self._box_hidding_out is BoxHidding.HIDDING
                    or self._box_hidding_in is BoxHidding.HIDDING):
                # if one of the 2 boxes is hidding,
                # the lines widget must be invisible at end of animation.
                # Lines widget will be removed very soon.
                return
            
            # the lines have now to be drawn normally
            self.update_line_gradient()
            return

        ratio = max(min(ratio, 1.0 - epsy * 2), epsy * 2)
        gradient = QLinearGradient(self._group_out_x, self._group_out_mid_y,
                                   self._group_in_x, self._group_in_mid_y)
        transparent = QColor(0, 0, 0, 0)
        color_main = self._th_attribs.color_main
        
        # OUT       | IN        | TRANSPARENT STARTS ON | REVERSE
        # ----------|-----------|-----------------------|--------            
        # NONE      | NONE      | not here              |
        # NONE      | HIDDING   | right                 | X
        # NONE      | RESTORING | right                 |
        # HIDDING   | NONE      | left                  | 
        # HIDDING   | HIDDING   | middle                |
        # HIDDING   | RESTORING | left (special)        |
        # RESTORING | NONE      | left                  | X
        # RESTORING | HIDDING   | right (special)       | X
        # RESTORING | RESTORING | middle                | X
        
        if ((self._box_hidding_out is BoxHidding.NONE
                    and self._box_hidding_in is BoxHidding.HIDDING)
                or self._box_hidding_out is BoxHidding.RESTORING):
            ratio = 1.0 - ratio

        if self._box_hidding_out is self._box_hidding_in:
            # transparent starts in the middle
            gradient.setColorAt(0.0, color_main)
            gradient.setColorAt(0.5 - ratio * 0.5 - epsy, color_main)
            gradient.setColorAt(0.5 - ratio * 0.5 + epsy, transparent)
            gradient.setColorAt(0.5 + ratio * 0.5 - epsy, transparent)
            gradient.setColorAt(0.5 + ratio * 0.5 + epsy, color_main)
            gradient.setColorAt(1.0, color_main)
        
        elif (self._box_hidding_out is not BoxHidding.NONE
                and self._box_hidding_in is not BoxHidding.NONE):
            # transparent starts on the left
            # line is full at 0.5
            if 0.5 - epsy < ratio < 0.5 + epsy:
                gradient.setColorAt(0.0, color_main)
                gradient.setColorAt(1.0, color_main)

            elif ratio < 0.5:
                gradient.setColorAt(0.0, color_main)
                gradient.setColorAt(ratio * 2.0 - epsy, color_main)
                gradient.setColorAt(ratio * 2.0 + epsy, transparent)
                gradient.setColorAt(1.0, transparent)
            else:
                gradient.setColorAt(0.0, transparent)
                gradient.setColorAt(((ratio - 0.5) * 2) - epsy, transparent)
                gradient.setColorAt(((ratio - 0.5) * 2) + epsy, color_main)
                gradient.setColorAt(1.0, color_main)
        
        elif self._box_hidding_out is BoxHidding.NONE:
            # transparent starts on the right
            gradient.setColorAt(0.0, color_main)
            gradient.setColorAt(ratio - epsy, color_main)
            gradient.setColorAt(ratio + epsy, transparent)
            gradient.setColorAt(1.0, transparent)
            
        else:
            # transparent starts on the left
            gradient.setColorAt(0.0, transparent)
            gradient.setColorAt(ratio - epsy, transparent)
            gradient.setColorAt(ratio + epsy, color_main)
            gradient.setColorAt(1.0, color_main)

        self.setPen(QPen(gradient, self._th_attribs.base_width,
                         Qt.SolidLine, Qt.FlatCap))
    
    def set_mode_hidding(self, port_mode: PortMode, box_hidding: BoxHidding):
        if port_mode & PortMode.OUTPUT:
            self._box_hidding_out = box_hidding
        if port_mode & PortMode.INPUT:
            self._box_hidding_in = box_hidding