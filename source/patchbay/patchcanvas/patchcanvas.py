#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# PatchBay Canvas engine using QGraphicsView/Scene
# Copyright (C) 2010-2019 Filipe Coelho <falktx@falktx.com>
# Copyright (C) 2019-2024 Mathieu Picot <picotmathieu@gmail.com>
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
from pathlib import Path
import time
from typing import Callable

from qtpy.QtCore import (
    Slot, Signal, QObject, QPointF, QRectF,#type:ignore
    QSettings, QTimer)

from patshared import (
    PortMode,
    BoxLayoutMode,
    BoxType,
    GroupPos
    )

from .init_values import (
    AliasingReason,
    CanvasNeverInit,
    GridStyle,
    PortSubType,
    PortType,
    Joining,
    canvas,
    options,
    features,
    CanvasOptionsObject,
    CanvasFeaturesObject,
    MAX_PLUGIN_ID_ALLOWED,
    GroupObject,
    PortObject,
    PortgrpObject,
    ConnectionObject,
    BoxHidding,
    Zv
)

from .utils import (
    nearest_on_grid, 
    previous_left_on_grid,
    previous_top_on_grid)
from .box_widget import BoxWidget
from .port_widget import PortWidget
from .grouped_lines_widget import GroupedLinesWidget
from .hidden_conn_widget import HiddenConnWidget
from .theme_manager import ThemeData, ThemeManager
from .scene import PatchScene
from .scene_view import PatchGraphicsView
from .proto_callbacker import ProtoCallbacker


_logger = logging.getLogger(__name__)
_logging_str = ''
'''used by patchbay_api decorator to get function_name
and arguments, easily usable by logger'''


# decorator
def patchbay_api(func: Callable):
    '''decorator for API callable functions.
    It makes debug logs and also a global logging string
    usable directly in the functions'''

    def wrapper(*args, **kwargs):
        args_strs = [str(arg) for arg in args]
        args_strs += [f"{k}={v}" for k, v in kwargs.items()]

        global _logging_str
        _logging_str = f"{func.__name__}({', '.join(args_strs)})"
        _logger.debug(_logging_str)
        return func(*args, **kwargs)
    return wrapper


class CanvasObject(QObject):
    port_added = Signal(int, int)
    port_removed = Signal(int, int)
    connection_added = Signal(int)
    connection_removed = Signal(int)
    move_boxes_finished = Signal()

    def __init__(self, parent=None):
        QObject.__init__(self, parent)
        self._gps_to_join = set[int]()
        self.move_boxes_finished.connect(self._join_after_move)

        self.connect_update_timer = QTimer()
        self.connect_update_timer.setInterval(0)
        self.connect_update_timer.setSingleShot(True)
        self.connect_update_timer.timeout.connect(
            self._connect_update_timer_finished)
        
        self._aliasing_reason = AliasingReason.NONE
        self._aliasing_timer_started_at = 0.0
        self._aliasing_move_timer = QTimer()
        self._aliasing_move_timer.setInterval(0)
        self._aliasing_move_timer.setSingleShot(True)
        self._aliasing_move_timer.timeout.connect(
            self._aliasing_move_timer_finished)
        
        self._aliasing_view_timer = QTimer()
        self._aliasing_view_timer.setInterval(500)
        self._aliasing_view_timer.setSingleShot(True)
        self._aliasing_view_timer.timeout.connect(
            self._aliasing_view_timer_finished)

    @Slot()
    def _connect_update_timer_finished(self):
        GroupedLinesWidget.change_all_prepared_conns()

    @Slot()
    def _aliasing_move_timer_finished(self):
        if time.time() - self._aliasing_timer_started_at > 0.060:
            canvas.set_aliasing_reason(self._aliasing_reason, True)
        
        if self._aliasing_reason is AliasingReason.VIEW_MOVE:
            self._aliasing_view_timer.start()

    @Slot()
    def _aliasing_view_timer_finished(self):
        canvas.set_aliasing_reason(AliasingReason.VIEW_MOVE, False)

    def start_aliasing_check(self, aliasing_reason: AliasingReason):
        self._aliasing_reason = aliasing_reason
        self._aliasing_timer_started_at = time.time()
        self._aliasing_move_timer.start()

    @Slot()
    def _join_after_move(self):
        for group_id in self._gps_to_join:
            join_group(group_id)

        self._gps_to_join.clear()
        
        canvas.cb.animation_finished()

    def add_group_to_join(self, group_id: int):
        self._gps_to_join.add(group_id)
    
    def rm_group_to_join(self, group_id: int):
        self._gps_to_join.discard(group_id)
            
    def rm_all_groups_to_join(self):
        self._gps_to_join.clear()


@patchbay_api
def init(view: PatchGraphicsView, callbacker: ProtoCallbacker,
          theme_paths: tuple[Path, ...], fallback_theme: str):
    if canvas.initiated:
        _logger.critical("init() - already initiated")
        return

    if not callbacker:
        _logger.critical("init() - fatal error: callback not set")
        return

    canvas.initiated = True
    canvas._cb = callbacker
    canvas._scene = PatchScene(view)
    view.setScene(canvas._scene)
    
    canvas.initial_pos = QPointF(0, 0)
    canvas.size_rect = QRectF()

    if canvas._qobject is None:
        canvas._qobject = CanvasObject()

    if canvas.settings is None:
        # TODO : may remove this because it is not used
        # while features.handle_positions is False. 
        canvas.settings = QSettings()

    if canvas.theme_manager is None:
        canvas.theme_manager = ThemeManager(theme_paths)
        if not canvas.theme_manager.set_theme(options.theme_name):
            if canvas.theme_manager.set_theme(fallback_theme):
                _logger.warning(
                f"theme '{options.theme_name}' has not been found,"
                f"use '{fallback_theme}' instead.")
            else:
                _logger.warning(
                f"theme '{options.theme_name}' has not been found,"
                "use the very ugly fallback theme.")
                canvas.theme_manager.set_fallback_theme()

        canvas.theme.load_cache()

    canvas._scene.zoom_reset()    

@patchbay_api
def set_loading_items(yesno: bool, auto_redraw=False, prevent_overlap=True):
    '''while canvas is loading items (groups or ports, connections...)
    items will be added, but not redrawn.
    This is an optimization that prevents a lot of redraws.
    Think to set loading items at False and use redraw_all_groups
    or redraw_group once the long operation is finished'''
    canvas.ensure_init()
    canvas.loading_items = yesno
    
    if not yesno and auto_redraw:
        both_done = set[int]()
        boxes = list[BoxWidget]()
        
        for group_id in canvas.groups_to_redraw_out:
            group = canvas.get_group(group_id)
            if group is None:
                continue

            for box in group.widgets:
                port_mode = box.get_port_mode()
                if port_mode & PortMode.OUTPUT:
                    box.update_positions(scene_checks=False)
                    if box.isVisible():
                        boxes.append(box)
                    
                    if port_mode & PortMode.INPUT:
                        both_done.add(group_id)
        
        for group_id in canvas.groups_to_redraw_in:
            if group_id in both_done:
                continue
            
            group = canvas.get_group(group_id)
            if group is None:
                continue

            for box in group.widgets:
                port_mode = box.get_port_mode()
                if port_mode & PortMode.INPUT:
                    box.update_positions(scene_checks=False)
                    if box.isVisible():
                        boxes.append(box)
        
        if prevent_overlap:
            for box in boxes:
                canvas.scene.deplace_boxes_from_repulsers([box])
        
        if canvas.groups_to_redraw_out or canvas.groups_to_redraw_in:
            canvas.scene.resize_the_scene()
        canvas.scene.update()
    
    canvas.groups_to_redraw_out.clear()
    canvas.groups_to_redraw_in.clear()

@patchbay_api
def add_group(group_id: int, group_name: str, split: bool,
              box_type: BoxType, icon_name: str, gpos: GroupPos):
    if canvas.get_group(group_id) is not None:
        _logger.error(f"{_logging_str} - group already exists.")
        return

    group = GroupObject()
    group.group_id = group_id
    group.group_name = group_name
    group.splitted = split
    group.box_type = box_type
    group.icon_name = icon_name
    group.plugin_id = -1
    group.plugin_ui = False
    group.plugin_inline = False
    group.handle_client_gui = False
    group.gui_visible = False
    group.gpos = gpos
    group.widgets = list[BoxWidget]()

    if split:
        out_box = BoxWidget(group, PortMode.OUTPUT)
        out_box.set_top_left(nearest_on_grid(gpos.boxes[PortMode.OUTPUT].pos))
        group.widgets.append(out_box)

        in_box = BoxWidget(group, PortMode.INPUT)
        in_box.set_top_left(nearest_on_grid(gpos.boxes[PortMode.INPUT].pos))
        group.widgets.append(in_box)

    else:
        box = BoxWidget(group, PortMode.BOTH)
        box.set_top_left(nearest_on_grid(gpos.boxes[PortMode.BOTH].pos))
        group.widgets.append(box)

    canvas.add_group(group)

    if canvas.loading_items:
        canvas.groups_to_redraw_in.add(group_id)
        canvas.groups_to_redraw_out.add(group_id)
        return

    if canvas.scene is not None:
        QTimer.singleShot(0, canvas.scene.update)

@patchbay_api
def remove_group(group_id: int, save_positions=True):
    canvas.ensure_init()
    group = canvas.get_group(group_id)
    if group is None:
        _logger.error(f"{_logging_str} - unable to find group to remove")
        return
    
    for box in group.widgets:
        box.remove_icon_from_scene()
        canvas.scene.remove_box(box)
    
    canvas.remove_group(group)
    canvas.group_plugin_map.pop(group.plugin_id, None)

    if canvas.loading_items:
        canvas.groups_to_redraw_in.add(group_id)
        canvas.groups_to_redraw_out.add(group_id)
        return

    QTimer.singleShot(0, canvas.scene.update)
    QTimer.singleShot(0, canvas.scene.resize_the_scene)

@patchbay_api
def rename_group(group_id: int, new_group_name: str):
    group = canvas.get_group(group_id)
    if group is None:
        _logger.critical(f"{_logging_str} - unable to find group to rename")
        return

    group.group_name = new_group_name    
    for box in group.widgets:
        box._group_name = new_group_name
        if not canvas.loading_items:
            box.update_positions()

    if canvas.loading_items:
        canvas.groups_to_redraw_in.add(group_id)
        canvas.groups_to_redraw_out.add(group_id)
        return

    if canvas.scene is not None:
        QTimer.singleShot(0, canvas.scene.update)

@patchbay_api
def split_group(group_id: int, on_place=False, redraw=True):
    '''Split inputs and outputs in two box widgets.

    on_place: the new boxes will have a pos near from the existing one
    
    redraw: draw the box, quite long operation. Needed for 'on_place'
    to be effective.'''
    canvas.ensure_init()

    group = canvas.get_group(group_id)
    if group is None:
        _logger.error(f"{_logging_str} - unable to find group to split")
        return
    
    if group.splitted:
        _logger.error(
            f"{_logging_str} - group is already splitted")
        return

    if not group.widgets:
        _logger.error(
            f"{_logging_str} - group has no box widget to split")
        return

    box = group.widgets[0]
    wrap = box.is_wrapped()
    ex_rect = QRectF(box.sceneBoundingRect())        
    new_box = BoxWidget(group, PortMode.INPUT)
    new_box.setPos(box.pos())
    new_box.set_wrapped(wrap, animate=False)
    
    for portgroup in canvas.list_portgroups(group_id):
        if (portgroup.port_mode is PortMode.INPUT
                and portgroup.widget is not None):
            portgroup.widget.setParentItem(new_box)
            
    for port in canvas.list_ports(group_id):
        if (port.port_mode is PortMode.INPUT
                and port.widget is not None):
            port.widget.setParentItem(new_box)

    box.set_port_mode(PortMode.OUTPUT)
    group.widgets.append(new_box)
    canvas.add_box(new_box)
    group.splitted = True

    group.gpos.set_splitted(True)
    canvas.cb.group_splitted(group_id)
    
    if not redraw:
        return
    
    full_width = canvas.theme.box_spacing
    
    for box in group.widgets:
        box.update_positions(even_animated=True, scene_checks=False)
        full_width += box.boundingRect().width()
                
    if on_place:
        for box in group.widgets:
            if box.get_current_port_mode() is PortMode.OUTPUT:
                group.gpos.boxes[PortMode.OUTPUT].pos = (
                    previous_left_on_grid(
                        int(ex_rect.right() + (full_width - ex_rect.width()) / 2
                            - box.boundingRect().width())),
                    previous_top_on_grid(
                        int(ex_rect.y()))
                )
            else:
                group.gpos.boxes[PortMode.INPUT].pos = (
                    previous_left_on_grid(
                        int(ex_rect.left() - (full_width - ex_rect.width()) / 2)),
                    previous_top_on_grid(int(ex_rect.y()))
                )
        
        move_group_boxes(group_id, group.gpos)    
        canvas.scene.deplace_boxes_from_repulsers(
            [b for b in group.widgets if b.isVisible()])

    QTimer.singleShot(0, canvas.scene.update)

@patchbay_api
def join_group(group_id: int):
    canvas.ensure_init()
    group = canvas.get_group(group_id)
    if group is None:
        _logger.error(f"{_logging_str} - unable to find groups to join")
        return

    if not group.splitted:
        _logger.error(f"{_logging_str} - group is not splitted")
        return

    wrap = True
    for box in group.widgets:
        wrap = wrap and box.is_wrapped()

    eater, eaten = group.widgets

    for portgroup in canvas.list_portgroups(group_id=group_id):
        if (portgroup.port_mode is eaten.get_port_mode()
                and portgroup.widget is not None):
            portgroup.widget.setParentItem(eater)
    
    for port in canvas.list_ports(group_id=group_id):
        if (port.port_mode is eaten.get_port_mode()
                and port.widget is not None):
            port.widget.setParentItem(eater)

    eater.set_port_mode(PortMode.BOTH)
    eaten.remove_icon_from_scene()
    canvas.scene.remove_box(eaten)
    group.widgets.remove(eaten)
    canvas.remove_box(eaten)
    group.splitted = False
    del eaten

    eater.send_move_callback()
    eater.set_wrapped(wrap, animate=False)
    eater.update_positions(scene_checks=False)

    canvas.cb.group_joined(group_id)
    QTimer.singleShot(0, canvas.scene.update)

@patchbay_api
def repulse_all_boxes():
    canvas.ensure_init()
    if options.prevent_overlap:
        canvas.scene.full_repulse()      

@patchbay_api
def repulse_from_group(group_id: int, port_mode: PortMode):
    if not options.prevent_overlap:
        return

    group = canvas.get_group(group_id)
    if group is None:
        return
    
    canvas.ensure_init()
    
    for box in group.widgets:
        if (box.get_port_mode() & port_mode
                and (box.isVisible()
                     or (box in canvas.scene.move_boxes
                         and canvas.scene.move_boxes[box].hidding_state
                            is BoxHidding.RESTORING))):
            canvas.scene.deplace_boxes_from_repulsers([box])

@patchbay_api
def redraw_all_groups(force_no_prevent_overlap=False, theme_change=False):
    if canvas.loading_items:
        return

    canvas.ensure_init()
    # We are redrawing all groups.
    # For optimization reason we prevent here to resize the scene
    # at each group draw, we'll do it once all is done,
    # same for prevent_overlap.
    elastic = options.elastic
    prevent_overlap = options.prevent_overlap
    options.elastic = False
    options.prevent_overlap = False

    for box in canvas.list_boxes():
        box.update_positions(
            without_connections=True,
            scene_checks=False,
            theme_change=theme_change)

    for group_out in canvas.group_list:
        for group_in in canvas.group_list:
            GroupedLinesWidget.connections_changed(
                group_out.group_id, group_in.group_id)
        
    if elastic:
        canvas.scene.set_elastic(True)
    
    if prevent_overlap:
        options.prevent_overlap = True
        if not force_no_prevent_overlap:
            repulse_all_boxes()
    
    if not elastic or prevent_overlap:
        QTimer.singleShot(0, canvas.scene.update)

@patchbay_api
def redraw_group(group_id: int, ensure_visible=False, prevent_overlap=True):
    if canvas.loading_items:
        return
    
    group = canvas.get_group(group_id)
    if group is None:
        _logger.error(f"{_logging_str}, no group to redraw")
        return

    canvas.ensure_init()

    for box in group.widgets:
        box.update_positions(scene_checks=prevent_overlap)

    canvas.scene.update()

    if ensure_visible:
        for box in group.widgets:
            canvas.scene.center_view_on(box)
            break

@patchbay_api
def change_grid_width(grid_width: int):
    canvas.ensure_init()
    if grid_width <= 0:
        _logger.error(
            f'Can not change the grid width to a value <= 0 : {grid_width}')
        return
    
    options.cell_width = grid_width
    
    canvas.scene.update_grid_widget()
    
    for box in canvas.list_boxes():
        box.fix_pos()
        
    redraw_all_groups()

@patchbay_api
def change_grid_height(grid_height: int):
    canvas.ensure_init()
    if grid_height <= 0:
        _logger.error(
            f'Can not change the grid height to a value <= 0 : {grid_height}')
        return
    
    options.cell_height = grid_height
    
    canvas.scene.update_grid_widget()
    
    for box in canvas.list_boxes():
        box.fix_pos()
        
    redraw_all_groups()

@patchbay_api
def change_grid_widget_style(style: GridStyle):
    canvas.ensure_init()
    options.grid_style = style
    canvas.scene.update_grid_style()

@patchbay_api
def move_group_boxes(
        group_id: int, gpos: GroupPos,
        redraw=PortMode.NULL, restore=PortMode.NULL):
    '''Highly optimized function used at view change.
    Only things that need to be redrawn are redrawn.
    Any change in this function can easily create unwanted bugs ;)
    
    restore is required because the previous box_pos can be hidden
    and this one shown, but without ports
    (e.g. a pure audio group in midi view)'''
    canvas.ensure_init()
    group = canvas.get_group(group_id)
    if group is None:
        return

    group.gpos = gpos
    split = gpos.is_splitted()
    join = False
    splitted = False
    orig_rect = QRectF()

    if group.splitted != split:
        if split:
            for box in group.widgets:
                if box._port_mode is PortMode.BOTH:
                    orig_rect = QRectF(box.sceneBoundingRect())
                    break

            split_group(group_id, redraw=False)
            splitted = True
            redraw |= PortMode.BOTH
        else:
            join = True

    for port_mode, box_pos, in gpos.boxes.items():
        for box in group.widgets:
            if box.get_port_mode() is not port_mode:
                continue

            if box._layout_mode is not box_pos.layout_mode:
                box.set_layout_mode(box_pos.layout_mode)
                redraw |= port_mode

            if box.is_hidding_or_restore() and not box_pos.is_hidden():
                redraw |= port_mode

            if join:
                wanted_wrap = gpos.boxes[PortMode.BOTH].is_wrapped()
            else:
                wanted_wrap = box_pos.is_wrapped()

            if box.is_wrapped() is not wanted_wrap:
                # we need to update the box now, because the port_list
                # of the box is not re-evaluted when we update positions
                # during the wrap/unwrap animation.
                box.update_positions(
                    even_animated=True, scene_checks=False)
                box.set_wrapped(
                    wanted_wrap, prevent_overlap=False)
                redraw &= ~port_mode

            if redraw & port_mode:
                box.update_positions(
                    even_animated=True, scene_checks=False)
            
            if splitted and not orig_rect.isNull():
                # the splitted boxes start with inputs aligned to the inputs
                # of the previous joined box, and same for the outputs.
                if port_mode is PortMode.INPUT:
                    box.set_top_left((orig_rect.left(), orig_rect.top()))
                elif port_mode is PortMode.OUTPUT:
                    box.set_top_left(
                        (orig_rect.right() - box.boundingRect().width(),
                         orig_rect.top()))
            
            xy = nearest_on_grid(box_pos.pos)

            if box_pos.is_hidden():
                if box.isVisible():
                    canvas.scene.add_box_to_animation_hidding(box)
            
            elif restore & port_mode:
                if join:
                    canvas.scene.add_box_to_animation_restore(box)

                    both_pos = nearest_on_grid(gpos.boxes[PortMode.BOTH].pos)

                    if port_mode is PortMode.OUTPUT:
                        canvas.qobject.add_group_to_join(group.group_id)
                        joined_widget = BoxWidget(group, PortMode.BOTH)
                        joined_rect = joined_widget.get_dummy_rect()
                        canvas.scene.remove_box(joined_widget)
                        joined_rect.translate(QPointF(*both_pos))

                        canvas.scene.add_box_to_animation(
                            box, *both_pos,
                            joining=Joining.YES,
                            joined_rect=joined_rect)
                    else:
                        canvas.scene.add_box_to_animation(
                            box, *both_pos,
                            joining=Joining.YES)
                else:
                    box.set_top_left(xy)
                    canvas.scene.add_box_to_animation(box, *xy)
                    canvas.scene.add_box_to_animation_restore(box)

            else:
                if box.hidder_widget is not None:
                    canvas.scene.removeItem(box.hidder_widget)
                    box.hidder_widget = None

                if join:
                    both_pos = nearest_on_grid(gpos.boxes[PortMode.BOTH].pos)

                    if port_mode is PortMode.OUTPUT:
                        canvas.qobject.add_group_to_join(group.group_id)

                        joined_widget = BoxWidget(group, PortMode.BOTH)
                        joined_rect = joined_widget.get_dummy_rect()
                        canvas.scene.remove_box(joined_widget)
                        joined_rect.translate(QPointF(*both_pos))
                    
                        canvas.scene.add_box_to_animation(
                            box, *both_pos,
                            joining=Joining.YES,
                            joined_rect=joined_rect)
                    else:
                        canvas.scene.add_box_to_animation(
                            box, *both_pos,
                            joining=Joining.YES)
                else:
                    canvas.scene.add_box_to_animation(
                        box, *xy, joining=Joining.NO)

@patchbay_api
def wrap_group_box(group_id: int, port_mode: PortMode, yesno: bool):
    group = canvas.get_group(group_id)
    if group is None:
        return

    for box in group.widgets:
        if box.get_port_mode() is port_mode:
            box.set_wrapped(yesno, animate=True,
                            prevent_overlap=True)

@patchbay_api
def set_group_layout_mode(group_id: int, port_mode: PortMode,
                          layout_mode: BoxLayoutMode,
                          prevent_overlap=True):
    group = canvas.get_group(group_id)
    if group is None:
        _logger.warning(
            "set_group_layout_mode, no group with group_id {group_id}")
        return
    
    group.gpos.boxes[port_mode].layout_mode = layout_mode
    
    if canvas.loading_items:
        return

    for box in group.widgets:
        if (box.get_port_mode() is port_mode
                and box._layout_mode is not layout_mode):
            box.set_layout_mode(layout_mode)
            box.update_positions(scene_checks=prevent_overlap)

@patchbay_api
def clear_selection():
    canvas.ensure_init()
    canvas.scene.clear_selection()

# ------------------------------------------------------------------------

@patchbay_api
def set_group_icon(group_id: int, box_type: BoxType, icon_name: str):
    canvas.ensure_init()
    group = canvas.get_group(group_id)
    if group is None:
        _logger.critical(f"{_logging_str} - unable to find group to change icon")
        return
    
    group.box_type = box_type
    group.icon_name = icon_name

    for box in group.widgets:
        box.set_icon(box_type, icon_name)

    if canvas.loading_items:
        canvas.groups_to_redraw_out.add(group_id)
        canvas.groups_to_redraw_in.add(group_id)
        return

    QTimer.singleShot(0, canvas.scene.update)

@patchbay_api
def set_group_as_plugin(group_id: int, plugin_id: int,
                        has_ui: bool, has_inline_display: bool):
    group = canvas.get_group(group_id)
    if group is None:
        _logger.critical(f"{_logging_str} - unable to find group to set as plugin")
        return

    group.plugin_id = plugin_id
    group.plugin_ui = has_ui
    group.plugin_inline = has_inline_display
    
    for box in group.widgets:
        box.set_as_plugin(plugin_id, has_ui, has_inline_display)

    canvas.group_plugin_map[plugin_id] = group

# ---------------------------------------------

@patchbay_api
def add_port(group_id: int, port_id: int, port_name: str,
             port_mode: PortMode, port_type: PortType,
             port_subtype: PortSubType):
    canvas.ensure_init()
    if canvas.get_port(group_id, port_id) is not None:
        _logger.critical(f"{_logging_str} - port already exists")

    group = canvas.get_group(group_id)
    if group is None:
        _logger.critical(f"{_logging_str} - Unable to find parent group")
        return
    
    for box in group.widgets:
        if port_mode in box.get_port_mode():
            break
    else:
        _logger.error(f"{_logging_str} - Unable to find a box for port")
        return

    port = PortObject()
    port.group_id = group_id
    port.port_id = port_id
    port.port_name = port_name
    port.port_mode = port_mode
    port.port_type = port_type
    port.portgrp_id = 0
    port.port_subtype = port_subtype
    port.hidden_conn_widget = None
    port.widget = PortWidget(port, box)
    
    port.widget.setVisible(box.ports_are_visible())
    canvas.add_port(port)

    if canvas.loading_items:
        if port_mode is PortMode.INPUT:
            canvas.groups_to_redraw_in.add(group_id)
        elif port_mode is PortMode.OUTPUT:
            canvas.groups_to_redraw_out.add(group_id)
        return

    box.update_positions()

    QTimer.singleShot(0, canvas.scene.update)

@patchbay_api
def remove_port(group_id: int, port_id: int):
    canvas.ensure_init()
    port = canvas.get_port(group_id, port_id)
    if port is None:
        _logger.critical(f"{_logging_str} - Unable to find port to remove")
        return

    if port.portgrp_id:
        _logger.critical(f"{_logging_str} - Port is in portgroup " 
                            f"{port.portgrp_id}, remove it before !")
        return

    if port.hidden_conn_widget is not None:
        canvas.scene.removeItem(port.hidden_conn_widget)
        port.hidden_conn_widget = None

    item = port.widget
    box = None
    
    if item is not None:
        box = item.parentItem()
        canvas.scene.removeItem(item)

    del item
    canvas.remove_port(port)

    canvas.qobject.port_removed.emit(group_id, port_id)
    if canvas.loading_items:
        if port.port_mode is PortMode.OUTPUT:
            canvas.groups_to_redraw_out.add(group_id)
        else:
            canvas.groups_to_redraw_in.add(group_id)
        return

    if box is not None:
        box.update_positions()

    QTimer.singleShot(0, canvas.scene.update)

@patchbay_api
def rename_port(group_id: int, port_id: int, new_port_name: str):
    canvas.ensure_init()
    port = canvas.get_port(group_id, port_id)
    if port is None:
        _logger.critical(f"{_logging_str} - Unable to find port to rename")
        return

    if new_port_name != port.port_name:
        port.port_name = new_port_name
        port.widget.set_port_name(new_port_name)

    if canvas.loading_items:
        if port.port_mode is PortMode.OUTPUT:
            canvas.groups_to_redraw_out.add(group_id)
        else:
            canvas.groups_to_redraw_in.add(group_id)
        return

    port.widget.parentItem().update_positions()

    QTimer.singleShot(0, canvas.scene.update)

@patchbay_api
def port_has_hidden_connection(group_id: int, port_id: int, yesno: bool):
    port = canvas.get_port(group_id, port_id)
    if port is None:
        _logger.critical(
            f"{_logging_str} - Unable to find port to set hidden connection")
        return

    if bool(port.hidden_conn_widget is None) == bool(not yesno):
        return

    canvas.ensure_init()

    if yesno:
        port.hidden_conn_widget = HiddenConnWidget(port.widget)
        canvas.scene.addItem(port.hidden_conn_widget)

    else:
        if port.hidden_conn_widget is not None:
            canvas.scene.removeItem(port.hidden_conn_widget)
        del port.hidden_conn_widget
        port.hidden_conn_widget = None

    if canvas.loading_items:
        return

    QTimer.singleShot(0, canvas.scene.update)

@patchbay_api
def add_portgroup(group_id: int, portgrp_id: int, port_mode: PortMode,
                  port_type: PortType, port_subtype: PortSubType,
                  port_id_list: list[int]):
    if canvas.get_portgroup(group_id, portgrp_id) is not None:
        _logger.critical(f"{_logging_str} - portgroup already exists")
        return
    
    portgrp = PortgrpObject()
    portgrp.group_id = group_id
    portgrp.portgrp_id = portgrp_id
    portgrp.port_mode = port_mode
    portgrp.port_type = port_type
    portgrp.port_subtype = port_subtype
    portgrp.port_id_list = list(port_id_list)
    portgrp.widget = None

    i = 0
    # check that port ids are present and groupable in this group
    for port in canvas.list_ports(group_id=group_id):
        if (port.port_type is port_type
                and port.port_mode is port_mode):
            if port.port_id == port_id_list[i]:
                if port.portgrp_id:
                    _logger.error(
                        f"{_logging_str} - "
                        f"port id {port.port_id} is already "
                        f"in portgroup {port.portgrp_id}")
                    return

                i += 1

                if i == len(port_id_list):
                    # everything seems ok for this portgroup, stop the check
                    break

            elif i > 0:
                _logger.error(f"{_logging_str} - port ids are not consecutive")
                return
    else:
        _logger.error(f"{_logging_str} - not enought ports with port_id_list")
        return

    # modify ports impacted by portgroup
    for port in canvas.list_ports(group_id=group_id):
        if (port.port_id in port_id_list):
            port.set_portgroup_id(
                portgrp_id, port_id_list.index(port.port_id), len(port_id_list))

    canvas.add_portgroup(portgrp)
    
    # add portgroup widget and refresh the view
    group = canvas.get_group(group_id)
    if group is None:
        return
    
    for box in group.widgets:
        if box.get_port_mode() & port_mode:
            portgrp.widget = box.add_portgroup_from_group(portgrp)

            if not canvas.loading_items:
                box.update_positions()

@patchbay_api
def remove_portgroup(group_id: int, portgrp_id: int):
    canvas.ensure_init()
    box_widget = None

    for portgrp in canvas.list_portgroups(group_id=group_id):
        if portgrp.portgrp_id == portgrp_id:
            # set portgrp_id to the concerned ports
            for port in canvas.list_ports(group_id=group_id):
                if port.portgrp_id == portgrp_id:
                    port.set_portgroup_id(0, 0, 1)

            if portgrp.widget is not None:
                item = portgrp.widget
                box_widget = item.parentItem()
                canvas.scene.removeItem(item)
                del item
                portgrp.widget = None
            break
    else:
        _logger.error(f"{_logging_str} - Unable to find portgrp to remove")
        return

    canvas.remove_portgroup(portgrp)

    if canvas.loading_items:
        return

    if box_widget is not None:
        box_widget.update_positions()

    QTimer.singleShot(0, canvas.scene.update)

@patchbay_api
def clear_all():
    GroupedLinesWidget.clear_all_widgets()
    canvas.clear_all()

@patchbay_api
def connect_ports(connection_id: int, group_out_id: int, port_out_id: int,
                  group_in_id: int, port_in_id: int):
    canvas.ensure_init()
    out_port = canvas.get_port(group_out_id, port_out_id)
    in_port = canvas.get_port(group_in_id, port_in_id)
    
    if out_port is None or in_port is None:
        _logger.critical(f"{_logging_str} - unable to find ports to connect")
        return

    connection = ConnectionObject()
    connection.connection_id = connection_id
    connection.group_in_id = group_in_id
    connection.port_in_id = port_in_id
    connection.group_out_id = group_out_id
    connection.port_out_id = port_out_id
    connection.port_type = out_port.port_type
    connection.ready_to_disc = False
    connection.in_selected = False
    connection.out_selected = False
    canvas.add_connection(connection)

    GroupedLinesWidget.prepare_conn_changes(group_out_id, group_in_id)
    canvas.qobject.connect_update_timer.start()
    canvas.qobject.connection_added.emit(connection_id)
    
    if canvas.loading_items:
        return

    QTimer.singleShot(0, canvas.scene.update)

@patchbay_api
def disconnect_ports(connection_id: int):
    connection = canvas.get_connection(connection_id)
    if connection is None:
        _logger.critical(
            f"{_logging_str} - unable to find connection ports")
        return
    
    tmp_conn = connection.copy()
    canvas.remove_connection(connection)
    
    GroupedLinesWidget.prepare_conn_changes(
        tmp_conn.group_out_id, tmp_conn.group_in_id)
    
    canvas.qobject.connect_update_timer.start()
    canvas.qobject.connection_removed.emit(connection_id)

    out_port = canvas.get_port(tmp_conn.group_out_id, tmp_conn.port_out_id)
    in_port = canvas.get_port(tmp_conn.group_in_id, tmp_conn.port_in_id)
    
    if out_port is None or in_port is None:
        _logger.info(f"{_logging_str} - connection cleaned after its ports")
        return

    if out_port.widget is None or in_port.widget is None:
        _logger.error(f"{_logging_str} - port has no widget")
        return        

    if canvas.loading_items:
        return

    QTimer.singleShot(0, canvas.scene.update)

@patchbay_api
def animate_before_hide_box(group_id: int, port_mode: PortMode):
    canvas.ensure_init()
    group = canvas.get_group(group_id)
    if group is None:
        _logger.info(f"{_logging_str} - failed to find group")
        return

    for box in group.widgets:
        if port_mode & box._port_mode:
            canvas.scene.add_box_to_animation_hidding(box)
    
# ----------------------------------------------------------------------------

@patchbay_api
def start_aliasing_check(aliasing_reason: AliasingReason):
    canvas.ensure_init()
    canvas.qobject.start_aliasing_check(aliasing_reason)

@patchbay_api
def set_aliasing_reason(aliasing_reason: AliasingReason, yesno: bool):
    canvas.set_aliasing_reason(aliasing_reason, yesno)

@patchbay_api
def get_theme() -> str:
    if canvas.theme_manager is None:
        raise CanvasNeverInit
    return canvas.theme_manager.get_theme()

@patchbay_api
def list_themes() -> list[ThemeData]:
    if canvas.theme_manager is None:
        raise CanvasNeverInit
    return canvas.theme_manager.list_themes()

@patchbay_api
def change_theme(theme_name='') -> bool:
    if canvas.theme_manager is None:
        raise CanvasNeverInit
    ret = canvas.theme_manager.set_theme(theme_name)
    if ret:
        options.theme_name = theme_name
    return ret

@patchbay_api
def copy_and_load_current_theme(new_theme_name: str) -> int:
    if canvas.theme_manager is None:
        raise CanvasNeverInit
    return canvas.theme_manager.copy_and_load_current_theme(new_theme_name)

# ----------------------------------------------------------------------------
@patchbay_api
def redraw_plugin_group(plugin_id: int):
    group = canvas.group_plugin_map.get(plugin_id, None)

    if group is None:
        _logger.critical(f"{_logging_str} - unable to find group")
        return

    assert isinstance(group, GroupObject)

    for box in group.widgets:
        box.redraw_inline_display()

@patchbay_api
def handle_plugin_removed(plugin_id: int):
    group = canvas.group_plugin_map.pop(plugin_id, None)

    if group is not None:
        assert isinstance(group, GroupObject)
        group.plugin_id = -1
        group.plugin_ui = False
        group.plugin_inline = False
        
        for box in group.widgets:
            box.remove_as_plugin()

    for group in canvas.group_list:
        if (group.plugin_id < plugin_id
                or group.plugin_id > MAX_PLUGIN_ID_ALLOWED):
            continue

        group.plugin_id -= 1
        
        for box in group.widgets:
            box._plugin_id -= 1

        canvas.group_plugin_map[plugin_id] = group

@patchbay_api
def handle_all_plugins_removed():
    canvas.group_plugin_map = {}

    for group in canvas.group_list:
        if group.plugin_id < 0:
            continue
        if group.plugin_id > MAX_PLUGIN_ID_ALLOWED:
            continue

        group.plugin_id = -1
        group.plugin_ui = False
        group.plugin_inline = False
        
        for box in group.widgets:
            box.remove_as_plugin()

@patchbay_api
def set_auto_select_items(yesno: bool):
    options.auto_select_items = yesno
    
    for box in canvas.list_boxes():
        box.setAcceptHoverEvents(yesno)
    
    for portgrp in canvas.list_portgroups():
        if portgrp.widget is not None:
            portgrp.widget.setAcceptHoverEvents(yesno)
            
    for port in canvas.list_ports():
        if port.widget is not None:
            port.widget.setAcceptHoverEvents(yesno)

@patchbay_api
def set_elastic(yesno: bool):
    canvas.ensure_init()
    canvas.scene.set_elastic(yesno)

@patchbay_api
def set_prevent_overlap(yesno: bool):
    options.prevent_overlap = yesno
    if yesno:
        redraw_all_groups()

@patchbay_api
def set_borders_navigation(yesno: bool):
    options.borders_navigation = yesno

@patchbay_api
def set_max_port_width(width: int):
    options.max_port_width = width
    redraw_all_groups()

@patchbay_api
def set_default_zoom(default_zoom: int):
    options.default_zoom = default_zoom

@patchbay_api
def semi_hide_groups(group_ids: set[int]):
    for group in canvas.group_list:
        semi_hidden = group.group_id in group_ids
        for box in group.widgets:
            box.semi_hide(semi_hidden)
            box.setZValue(
                Zv.OPAC_BOX.value if semi_hidden else Zv.BOX.value)
    
    GroupedLinesWidget.groups_semi_hidden(group_ids)

@patchbay_api
def invert_boxes_selection():
    canvas.ensure_init()
    canvas.scene.invert_boxes_selection()

@patchbay_api
def select_port(group_id: int, port_id: int):
    canvas.ensure_init()
    port = canvas.get_port(group_id, port_id)
    if port is None:
        return
    
    if port.widget is None:
        return
    
    box = port.widget.parentItem()
    canvas.scene.clearSelection()

    if box.is_wrapped():
        canvas.scene.center_view_on(box)
        box.setSelected(True)
    else:
        canvas.scene.center_view_on(port.widget)
        port.widget.setSelected(True)

@patchbay_api
def select_filtered_group_box(group_id: int, n_select=1):
    canvas.ensure_init()
    group = canvas.get_group(group_id)
    if group is None:
        return
    
    n_widget = 1

    for box in group.widgets:
        if box.isVisible():
            if n_select == n_widget:
                canvas.scene.clearSelection()
                box.setSelected(True)
                canvas.scene.center_view_on(box)
                break

            n_widget += 1

@patchbay_api
def get_box_true_layout(group_id: int, port_mode: PortMode) -> BoxLayoutMode:
    '''Should never return BoxLayoutMode.AUTO'''
    group = canvas.get_group(group_id)
    if group is None:
        return BoxLayoutMode.AUTO
    
    for box in group.widgets:
        if box.get_port_mode() is port_mode:
            return box.get_current_layout_mode()
    
    return BoxLayoutMode.AUTO

@patchbay_api
def get_number_of_boxes(group_id: int) -> int:
    group = canvas.get_group(group_id)
    if group is None:
        return 0
    
    return len([b for b in group.widgets if b.isVisible()])

@patchbay_api    
def set_semi_hide_opacity(opacity: float):
    options.semi_hide_opacity = opacity

    for box in canvas.list_boxes():
        box.update_opacity()
                
    GroupedLinesWidget.update_opacity()

@patchbay_api
def set_optional_gui_state(group_id: int, visible: bool):
    canvas.ensure_init()
    group = canvas.get_group(group_id)
    if group is None:
        return

    group.handle_client_gui = True
    group.gui_visible = visible

    for widget in group.widgets:
        if widget is not None:
            widget.set_optional_gui_state(visible)
    
    if not canvas.loading_items:
        canvas.scene.update()

@patchbay_api
def zoom_reset():
    canvas.ensure_init()
    canvas.scene.zoom_reset()
    
@patchbay_api
def zoom_fit():
    canvas.ensure_init()
    canvas.scene.zoom_fit()

@patchbay_api
def save_cache():
    canvas.ensure_init()
    canvas.theme.save_cache()

@patchbay_api
def set_grouped_box_layout_ratio(value: float):
    options.box_grouped_auto_layout_ratio = max(min(2.0, value), 0.0)
    redraw_all_groups()

@patchbay_api
def set_options(new_options: CanvasOptionsObject):
    if not canvas.initiated:
        options.__dict__ = new_options.__dict__.copy()

@patchbay_api
def set_features(new_features: CanvasFeaturesObject):
    if not canvas.initiated:
        features.__dict__ = new_features.__dict__.copy()
