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

# global imports
import logging
from pathlib import Path
from typing import Callable, Optional
from PyQt5.QtCore import (pyqtSlot, QObject, QPoint, QPointF, QRectF,
                          QSettings, QTimer, pyqtSignal)


# local imports
from .init_values import (
    CanvasItemType,
    PortSubType,
    PortType,
    canvas,
    options,
    features,
    CanvasOptionsObject,
    CanvasFeaturesObject,
    CallbackAct,
    MAX_PLUGIN_ID_ALLOWED,
    GroupObject,
    PortObject,
    PortgrpObject,
    ConnectionObject,
    PortMode,
    BoxLayoutMode,
    BoxType,
    BoxPos
)

from .utils import get_new_group_pos
from .box_widget import BoxWidget
from .port_widget import PortWidget
from .line_widget import LineWidget
from .hidden_conn_widget import HiddenConnWidget
from .theme_manager import ThemeManager
from .scene import PatchScene
from .scene_view import PatchGraphicsView

_logger = logging.getLogger(__name__)
# used by patchbay_api decorator to get function_name
# and arguments, easily usable by logger
_logging_str = ''

# decorator
def patchbay_api(func):
    ''' decorator for API callable functions.
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
    port_added = pyqtSignal(int, int)
    port_removed = pyqtSignal(int, int)
    connection_added = pyqtSignal(int)
    connection_removed = pyqtSignal(int)
    move_boxes_finished = pyqtSignal()

    def __init__(self, parent=None):
        QObject.__init__(self, parent)
        self.groups_to_join = list[tuple[GroupObject, PortMode]]()
        self.move_boxes_finished.connect(self.join_after_move)

    @pyqtSlot()
    def join_after_move(self):
        for group, origin_box_mode in self.groups_to_join:
            join_group(group.group_id, origin_box_mode)

        self.groups_to_join.clear()


def _get_stored_canvas_position(key, fallback_pos):
    try:
        return canvas.settings.value(
            "CanvasPositions/" + key, fallback_pos, type=QPointF)
    except:
        return fallback_pos




@patchbay_api
def init(view: PatchGraphicsView, callback: Callable,
          theme_paths: tuple[Path], fallback_theme: str):
    if canvas.initiated:
        _logger.critical("init() - already initiated")
        return

    if not callback:
        _logger.critical("init() - fatal error: callback not set")
        return

    canvas.callback = callback
    canvas.scene = PatchScene(view)
    view.setScene(canvas.scene)
    
    canvas.last_z_value = 0
    canvas.initial_pos = QPointF(0, 0)
    canvas.size_rect = QRectF()

    if canvas.qobject is None:
        canvas.qobject = CanvasObject()

    if canvas.settings is None:
        # TODO : may remove this because it is not used
        # while features.handle_positions is False. 
        canvas.settings = QSettings()

    if canvas.theme_manager is None:
        canvas.theme_manager = ThemeManager(theme_paths)
        if not canvas.theme_manager.set_theme(options.theme_name):
            if canvas.theme_manager.set_theme(fallback_theme):
                _logger.warning(
                f"theme {options.theme_name}' has not been found,"
                f"use '{fallback_theme}' instead.")
            else:
                _logger.warning(
                f"theme '{options.theme_name}' has not been found,"
                "use the very ugly fallback theme.")
                canvas.theme_manager.set_fallback_theme()

        canvas.theme.load_cache()

    canvas.scene.zoom_reset()
    canvas.initiated = True

@patchbay_api
def clear():
    if not canvas.initiated:
        return
    
    group_list_ids = [g.group_id for g in canvas.group_list]
    port_list_ids = [(p.group_id, p.port_id) for p in canvas.list_ports()]
    connection_list_ids = [c.connection_id for c in canvas.list_connections()]

    for idx in connection_list_ids:
        disconnect_ports(idx)

    for group_id, port_id in port_list_ids:
        remove_port(group_id, port_id)

    for idx in group_list_ids:
        remove_group(idx)

    canvas.last_z_value = 0

    canvas.clear_all()
    canvas.group_plugin_map = {}

    canvas.scene.clearSelection()

    for item in canvas.scene.items():
        if item.type() in (CanvasItemType.ICON, CanvasItemType.RUBBERBAND):
            continue
        canvas.scene.removeItem(item)
        del item

    canvas.initiated = False

    QTimer.singleShot(0, canvas.scene.update)

# ------------------------------------------------------------------------------------------------------------
@patchbay_api
def set_initial_pos(x: int, y: int):
    canvas.initial_pos.setX(x)
    canvas.initial_pos.setY(y)

@patchbay_api
def set_canvas_size(x: int, y: int, width: int, height: int):
    canvas.size_rect.setX(x)
    canvas.size_rect.setY(y)
    canvas.size_rect.setWidth(width)
    canvas.size_rect.setHeight(height)
    canvas.scene.update_limits()
    canvas.scene.fix_scale_factor()

@patchbay_api
def set_loading_items(yesno: bool):
    '''while canvas is loading items (groups or ports, connections...)
    then, items will be added, but not redrawn.
    This is an optimization that prevents a lot of redraws.
    Think to set loading items at False and use redraw_all_groups
    or redraw_group once the long operation is finished'''
    canvas.loading_items = yesno

@patchbay_api
def add_group(group_id: int, group_name: str, split: bool,
              box_type=BoxType.APPLICATION, icon_name='', layout_modes={},
              box_poses : dict[PortMode, BoxPos]={}):
    if canvas.get_group(group_id) is not None:
        _logger.error(f"{_logging_str} - group already exists.")
        return

    bx_poses = dict[PortMode, BoxPos]()
    for port_mode in PortMode.OUTPUT, PortMode.INPUT, PortMode.BOTH:
        box_pos = box_poses.get(port_mode)
        bx_poses[port_mode] = BoxPos() if box_pos is None else BoxPos(box_pos)

    group = GroupObject()
    group.group_id = group_id
    group.group_name = group_name
    group.splitted = split
    group.box_type = box_type
    group.icon_name = icon_name
    group.layout_modes = layout_modes
    group.plugin_id = -1
    group.plugin_ui = False
    group.plugin_inline = False
    group.handle_client_gui = False
    group.gui_visible = False
    group.box_poses = bx_poses
    group.widgets = list[BoxWidget]()

    if split:
        out_box = BoxWidget(group, PortMode.OUTPUT)
        out_box.setPos(bx_poses[PortMode.OUTPUT].to_point())
        canvas.last_z_value += 1
        out_box.setZValue(canvas.last_z_value)

        in_box = BoxWidget(group, PortMode.INPUT)
        in_box.setPos(bx_poses[PortMode.INPUT].to_point())
        canvas.last_z_value += 1
        in_box.setZValue(canvas.last_z_value)

        group.widgets = [out_box, in_box]

    else:
        box = BoxWidget(group, PortMode.BOTH)
        box.setPos(bx_poses[PortMode.BOTH].to_point())
        canvas.last_z_value += 1
        box.setZValue(canvas.last_z_value)
        group.widgets = [box, None]

    canvas.add_group(group)

    if canvas.loading_items:
        return

    QTimer.singleShot(0, canvas.scene.update)

@patchbay_api
def remove_group(group_id: int, save_positions=True):
    group = canvas.get_group(group_id)
    if group is None:
        _logger.error(f"{_logging_str} - unable to find group to remove")
        return
              
    item = group.widgets[0]

    if group.splitted:
        s_item = group.widgets[1]

        for moving_box in canvas.scene.move_boxes:
            if moving_box.widget is s_item:
                canvas.scene.move_boxes.remove(moving_box)
                break

        s_item.remove_icon_from_scene()
        
        canvas.scene.removeItem(s_item)
        del s_item
    
    for moving_box in canvas.scene.move_boxes:
        if moving_box.widget is item:
            canvas.scene.move_boxes.remove(moving_box)
            break

    item.remove_icon_from_scene()
    canvas.scene.removeItem(item)
    del item

    canvas.remove_group(group)
    canvas.group_plugin_map.pop(group.plugin_id, None)

    if canvas.loading_items:
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
    group.widgets[0].set_group_name(new_group_name)

    if group.splitted and group.widgets[1]:
        group.widgets[1].set_group_name(new_group_name)

    QTimer.singleShot(0, canvas.scene.update)

@patchbay_api
def get_splitted_on_place_pos(group_id: int,) -> dict[PortMode, BoxPos]:
    out_dict = {PortMode.INPUT: BoxPos(),
                PortMode.OUTPUT: BoxPos(),
                PortMode.BOTH: BoxPos()}
    
    group = canvas.get_group(group_id)
    if group is None:
        _logger.error(f"{_logging_str} - unable to find group")
        return out_dict
    
    if group.splitted:
        _logger.error(
            f"{_logging_str} - group is already splitted")
        return out_dict

    item = group.widgets[0]
    if item is None:
        _logger.error(
            f"{_logging_str} - group has no widget box")
        return out_dict
    
    pos = item.pos()
    rect = item.boundingRect()
    out_dict[PortMode.INPUT].pos = (
        int(pos.x() - rect.width() / 2), int(pos.y()))
    out_dict[PortMode.OUTPUT].pos = (
        int(pos.x() + rect.width() / 2), int(pos.y()))
    if item.is_wrapped():
        out_dict[PortMode.INPUT].set_wrapped(True)
        out_dict[PortMode.OUTPUT].set_wrapped(True)
    
    return out_dict

@patchbay_api
def get_box_rect(group_id: int, port_mode: PortMode) -> QRectF:
    group = canvas.get_group(group_id)
    if group is None:
        _logger.error(f"{_logging_str} - unable to find group")
        return QRectF()
    
    if bool(port_mode is PortMode.BOTH) == group.splitted:
        if port_mode is PortMode.BOTH:
            widget = BoxWidget(group, port_mode)
            rectf = widget.get_dummy_rect()
            canvas.scene.removeItem(widget)
            del widget
            return rectf
        return QRectF()
    
    if port_mode in (PortMode.BOTH, PortMode.INPUT):
        if group.widgets[0] is None:
            return QRectF()
        
        return group.widgets[0].sceneBoundingRect()
    
    elif port_mode is PortMode.OUTPUT:
        if group.widgets[1] is None:
            return QRectF()
        
        return group.widgets[1].sceneBoundingRect()
    
    else:
        return QRectF()

@patchbay_api
def move_splitted_boxes_on_place(group_id: int, orig_width: int):
    group = canvas.get_group(group_id)
    if group is None:
        _logger.error(f"{_logging_str} - unable to find group")
        return

    if not group.splitted:
        return
    
    out_item = group.widgets[0]
    if out_item is None:
        return

    in_item = group.widgets[1]
    if in_item is None:
        _logger.error(
            f"{_logging_str} - group has no widget box")
        return
    
    pos = in_item.pos()
    in_width = in_item.boundingRect().width()
    out_width = out_item.boundingRect().width()
    total_width = in_width + canvas.theme.box_spacing + out_width
    
    left = int(pos.x() + (orig_width - total_width) / 2)
    
    canvas.scene.add_box_to_animation(
        in_item, left, int(pos.y()))
    canvas.scene.add_box_to_animation(
        out_item, left + in_width + canvas.theme.box_spacing, int(pos.y()))
    

@patchbay_api
def split_group(group_id: int, on_place=False):
    item = None

    # Step 1 - Store all Item data
    group = canvas.get_group(group_id)
    if group is None:
        _logger.error(f"{_logging_str} - unable to find group to split")
        return
    
    if group.splitted:
        _logger.error(
            f"{_logging_str} - group is already splitted")
        return

    item = group.widgets[0]
    tmp_group = group.copy_no_widget()

    ex_rect = QRectF(item.sceneBoundingRect())

    if on_place and item is not None:
        pos = item.pos()
        # tmp_group.in_pos = pos.toPoint()
        # tmp_group.out_pos = pos.toPoint()
        for port_mode in PortMode.INPUT, PortMode.OUTPUT:
            box_pos = tmp_group.box_poses[port_mode]
            box_pos.set_pos_from_pt(pos)
            box_pos.set_wrapped(item.is_wrapped())

    wrap = item.is_wrapped()

    portgrps_data = [pg.copy_no_widget() for pg 
                     in canvas.list_portgroups(group_id=group_id)]
    ports_data = [p.copy_no_widget() for p in canvas.list_ports(group_id=group_id)]
    conns_data = [c.copy_no_widget()
                  for c in canvas.list_connections(group_id=group_id)]

    canvas.loading_items = True

    # Step 2 - Remove Item and Children
    for conn in conns_data:
        disconnect_ports(conn.connection_id)

    for portgrp in portgrps_data:
        if portgrp.group_id == group_id:
            remove_portgroup(group_id, portgrp.portgrp_id)

    for port in ports_data:
        if port.group_id == group_id:
            remove_port(group_id, port.port_id)

    remove_group(group_id)

    g = tmp_group

    # Step 3 - Re-create Item, now split
    add_group(group_id, g.group_name, True,
              g.box_type, g.icon_name, g.layout_modes,
              box_poses=g.box_poses)

    if g.handle_client_gui:
        set_optional_gui_state(group_id, g.gui_visible)

    if g.plugin_id >= 0:
        set_group_as_plugin(group_id, g.plugin_id, g.plugin_ui, g.plugin_inline)

    for port in ports_data:
        add_port(group_id, port.port_id, port.port_name, port.port_mode,
                 port.port_type, port.port_subtype)

    for portgrp in portgrps_data:
        add_portgroup(group_id, portgrp.portgrp_id, portgrp.port_mode,
                      portgrp.port_type, portgrp.port_subtype,
                      portgrp.port_id_list)

    for conn in conns_data:
        connect_ports(conn.connection_id, conn.group_out_id, conn.port_out_id,
                      conn.group_in_id, conn.port_in_id)

    canvas.loading_items = False
    
    full_width = canvas.theme.box_spacing
    
    for box in canvas.get_group(group_id).widgets:
        if box is not None:
            box.set_wrapped(wrap, animate=False)
            box.update_positions(even_animated=True, prevent_overlap=False)
            full_width += box.boundingRect().width()
            
    for box in canvas.get_group(group_id).widgets:
        if box is not None:
            if box.get_current_port_mode() is PortMode.OUTPUT:
                canvas.scene.add_box_to_animation(
                    box,
                    ex_rect.right() + (full_width - ex_rect.width()) / 2
                        - box.boundingRect().width(),
                    ex_rect.y())
            else:
                canvas.scene.add_box_to_animation(
                    box,
                    ex_rect.left() - (full_width - ex_rect.width()) / 2,
                    ex_rect.y())

    QTimer.singleShot(0, canvas.scene.update)

@patchbay_api
def join_group(group_id: int, origin_box_mode=PortMode.NULL):
    item_in = None
    item_out = None

    # Step 1 - Store all Item data
    group = canvas.get_group(group_id)
    if group is None:
        _logger.error(f"{_logging_str} - unable to find groups to join")
        return

    if not group.splitted:
        _logger.error(f"{_logging_str} - group is not splitted")
        return

    item_out, item_in = group.widgets
    item_in_rect = QRectF(item_in.sceneBoundingRect())
    item_out_rect = QRectF(item_out.sceneBoundingRect())

    tmp_widget = BoxWidget(group, PortMode.BOTH)
    if group.handle_client_gui:
        tmp_widget.set_optional_gui_state(group.gui_visible)
    tmp_rect = QRectF(tmp_widget.get_dummy_rect())
    canvas.scene.removeItem(tmp_widget)
    del tmp_widget

    tmp_group = group.copy_no_widget()

    wrap = item_in.is_wrapped() and item_out.is_wrapped()

    portgrps_data = [pg.copy_no_widget() for pg in
                     canvas.list_portgroups(group_id=group_id)]
    ports_data = [p.copy_no_widget()
                  for p in canvas.list_ports(group_id=group_id)]
    conns_data = [c.copy_no_widget() 
                  for c in canvas.list_connections(group_id=group_id)]

    canvas.loading_items = True

    # Step 2 - Remove Item and Children
    for conn in conns_data:
        disconnect_ports(conn.connection_id)

    for portgrp in portgrps_data:
        remove_portgroup(group_id, portgrp.portgrp_id)

    for port in ports_data:
        remove_port(group_id, port.port_id)

    remove_group(group_id)

    g = tmp_group
    
    if origin_box_mode is PortMode.OUTPUT:
        g.box_poses[PortMode.BOTH].pos = (
            int(item_out_rect.right() - tmp_rect.width()),
            int(item_out_rect.top()))
    elif origin_box_mode is PortMode.INPUT:
        g.box_poses[PortMode.BOTH].pos = (
            int(item_in_rect.x()), int(item_out_rect.y()))
    
    # Step 3 - Re-create Item, now together
    add_group(group_id, g.group_name, False,
              g.box_type, g.icon_name, g.layout_modes,
              box_poses=g.box_poses)

    if g.handle_client_gui:
        set_optional_gui_state(group_id, g.gui_visible)

    if g.plugin_id >= 0:
        set_group_as_plugin(group_id, g.plugin_id, g.plugin_ui, g.plugin_inline)

    for port in ports_data:
        add_port(group_id, port.port_id, port.port_name, port.port_mode,
                 port.port_type, port.port_subtype)

    for portgrp in portgrps_data:
        add_portgroup(group_id, portgrp.portgrp_id, portgrp.port_mode,
                      portgrp.port_type, portgrp.port_subtype,
                      portgrp.port_id_list)

    for conn in conns_data:
        connect_ports(conn.connection_id, conn.group_out_id, conn.port_out_id,
                      conn.group_in_id, conn.port_in_id)

    for box in canvas.get_group(group_id).widgets:
        if box is not None:
            box.set_wrapped(wrap, animate=False)

    canvas.loading_items = False
    redraw_group(group_id)

    canvas.callback(CallbackAct.GROUP_JOINED, group_id)
    QTimer.singleShot(0, canvas.scene.update)

@patchbay_api
def repulse_all_boxes():
    if options.prevent_overlap:
        canvas.scene.full_repulse()

@patchbay_api
def redraw_all_groups(force_no_prevent_overlap=False):    
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
            prevent_overlap=False)
    
    for connection in canvas.list_connections():
        if connection.widget is not None:
            connection.widget.update_line_pos()
    
    if canvas.scene is None:
        options.elastic = elastic
        options.prevent_overlap = prevent_overlap
        return
    
    if elastic:
        canvas.scene.set_elastic(True)
    
    if prevent_overlap:
        options.prevent_overlap = True
        if not force_no_prevent_overlap:
            repulse_all_boxes()
    
    if not elastic or prevent_overlap:
        QTimer.singleShot(0, canvas.scene.update)

@patchbay_api
def redraw_group(group_id: int, ensure_visible=False):
    group = canvas.get_group(group_id)
    if group is None:
        return

    for box in group.widgets:
        if box is not None:
            box.update_positions()

    canvas.scene.update()

    if ensure_visible:
        for box in group.widgets:
            if box is not None:
                canvas.scene.center_view_on(box)
                break

@patchbay_api
def animate_before_join(group_id: int,
                        origin_box_mode: PortMode=PortMode.NULL):
    group = canvas.get_group(group_id)
    if group is None:
        return

    canvas.qobject.groups_to_join.append((group, origin_box_mode))

    if origin_box_mode is PortMode.OUTPUT:
        x, y = int(group.widgets[0].pos().x()), int(group.widgets[0].pos().y())
    elif origin_box_mode is PortMode.INPUT:
        x, y = int(group.widgets[1].pos().x()), int(group.widgets[1].pos().y())
    else:
        x, y = group.box_poses[PortMode.BOTH].pos

    for widget in group.widgets:
        canvas.scene.add_box_to_animation(
            widget, x, y, joining=True)

@patchbay_api
def move_group_boxes(
        group_id: int, box_poses: dict[PortMode, BoxPos],
        animate=True, force=False):
    group = canvas.get_group(group_id)
    if group is None:
        return

    if group.splitted:
        for port_mode in (PortMode.OUTPUT, PortMode.INPUT):
            xy = box_poses[port_mode].pos

            box = group.widgets[0]
            if port_mode is PortMode.INPUT:
                box = group.widgets[1]

            if box is None:
                continue

            box_pos = box.pos()

            if (not force
                    and int(box_pos.x()) == xy[0]
                    and int(box_pos.y()) == xy[1]):
                continue

            canvas.scene.add_box_to_animation(
                box, xy[0], xy[1], force_anim=animate)
    else:
        box = group.widgets[0]
        if box is None:
            return

        box_pos = box.pos()
        xy = box_poses[PortMode.BOTH].pos
        if (not force
                and int(box_pos.x()) == xy[0] and int(box_pos.y()) == xy[1]):
            return
        
        canvas.scene.add_box_to_animation(box, xy[0], xy[1],
                                          force_anim=animate)

@patchbay_api
def wrap_group_box(group_id: int, port_mode: PortMode, yesno: bool,
                   animate=True, prevent_overlap=True):
    group = canvas.get_group(group_id)
    if group is None:
        return

    for box in group.widgets:
        if (box is not None
                and box.get_port_mode() is port_mode):
            box.set_wrapped(yesno, animate=animate,
                            prevent_overlap=prevent_overlap)

@patchbay_api
def set_group_layout_mode(group_id: int, port_mode: PortMode,
                          layout_mode: BoxLayoutMode,
                          prevent_overlap=True):
    group = canvas.get_group(group_id)
    if group is None:
        _logger.warning(
            "set_group_layout_mode, no group with group_id {group_id}")
        return
    
    group.layout_modes[port_mode] = layout_mode
    
    if canvas.loading_items:
        return

    for box in group.widgets:
        if box is not None:
            box.update_positions(prevent_overlap=prevent_overlap)

# ------------------------------------------------------------------------

@patchbay_api
def get_group_pos(group_id, port_mode=PortMode.OUTPUT):
    # Not used now
    group = canvas.get_group(group_id)
    if group is None:
        _logger.error(f"{_logging_str} - unable to find group")
        return QPointF(0, 0)
    
    return group.widgets[1 if (group.splitted and port_mode is PortMode.INPUT) else 0].pos()

@patchbay_api
def restore_group_positions(data_list):
    # Not used now
    mapping = {}

    for group in canvas.group_list:
        mapping[group.group_name] = group

    for data in data_list:
        name = data['name']
        group = mapping.get(name, None)

        if group is None:
            continue

        assert isinstance(group, GroupObject)

        group.widgets[0].setPos(data['pos1x'], data['pos1y'])

        if group.splitted and group.widgets[1]:
            group.widgets[1].setPos(data['pos2x'], data['pos2y'])

@patchbay_api
def set_group_pos(group_id, group_pos_x, group_pos_y):
    # Not used now
    set_group_pos_full(group_id, group_pos_x, group_pos_y, group_pos_x, group_pos_y)

@patchbay_api
def set_group_pos_full(group_id, group_pos_x_o, group_pos_y_o,
                       group_pos_x_i, group_pos_y_i):
    # Not used now    
    group = canvas.get_group(group_id)
    if group is None:
        _logger.error(f"set_group_pos_full({group_id}, {group_pos_x_o}, {group_pos_y_o}"
                      f"{group_pos_x_i}, {group_pos_y_i})"
                      " - unable to find group to reposition")
        return

    group.widgets[0].setPos(group_pos_x_o, group_pos_y_o)

    if group.splitted and group.widgets[1]:
        group.widgets[1].setPos(group_pos_x_i, group_pos_y_i)

    QTimer.singleShot(0, canvas.scene.update)

@patchbay_api
def set_group_icon(group_id: int, box_type: BoxType, icon_name: str):
    group = canvas.get_group(group_id)
    if group is None:
        _logger.critical(f"{_logging_str} - unable to find group to change icon")
        return
    
    group.box_type = box_type
    group.icon_name = icon_name

    for widget in group.widgets:
        if widget is not None:
            widget.set_icon(box_type, icon_name)

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
    group.widgets[0].set_as_plugin(plugin_id, has_ui, has_inline_display)

    if group.splitted and group.widgets[1]:
        group.widgets[1].set_as_plugin(plugin_id, has_ui, has_inline_display)

    canvas.group_plugin_map[plugin_id] = group

# ------------------------------------------------------------------------------------------------------------
@patchbay_api
def add_port(group_id: int, port_id: int, port_name: str,
             port_mode: PortMode, port_type: PortType,
             port_subtype: PortSubType):
    if canvas.get_port(group_id, port_id) is not None:
        _logger.critical(f"{_logging_str} - port already exists")

    group = canvas.get_group(group_id)
    if group is None:
        _logger.critical(f"{_logging_str} - Unable to find parent group")
        return

    n = 0
    if (group.splitted
            and group.widgets[0].get_port_mode() != port_mode
            and group.widgets[1] is not None):
        n = 1

    box_widget = group.widgets[n]

    port = PortObject()
    port.group_id = group_id
    port.port_id = port_id
    port.port_name = port_name
    port.port_mode = port_mode
    port.port_type = port_type
    port.portgrp_id = 0
    port.port_subtype = port_subtype
    port.hidden_conn_ids = set[int]()
    port.hidden_conn_widget = None
    port.widget = PortWidget(port, box_widget)
    
    port.widget.setVisible(not box_widget.is_wrapped())
    canvas.add_port(port)

    canvas.last_z_value += 1
    port.widget.setZValue(canvas.last_z_value)

    if canvas.loading_items:
        return

    box_widget.update_positions()

    QTimer.singleShot(0, canvas.scene.update)

@patchbay_api
def remove_port(group_id: int, port_id: int):
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
    del port.hidden_conn_widget

    item = port.widget
    box = None
    
    if item is not None:
        box = item.parentItem()
        canvas.scene.removeItem(item)

    del item
    canvas.remove_port(port)

    canvas.qobject.port_removed.emit(group_id, port_id)
    if canvas.loading_items:
        return

    if box is not None:
        box.update_positions()

    QTimer.singleShot(0, canvas.scene.update)

@patchbay_api
def rename_port(group_id: int, port_id: int, new_port_name: str):
    port = canvas.get_port(group_id, port_id)
    if port is None:
        _logger.critical(f"{_logging_str} - Unable to find port to rename")
        return

    if new_port_name != port.port_name:
        port.port_name = new_port_name
        port.widget.set_port_name(new_port_name)

    if canvas.loading_items:
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

    if yesno:
        port.hidden_conn_widget = HiddenConnWidget(port.widget)
        canvas.scene.addItem(port.hidden_conn_widget)
        
    else:
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
    portgrp.port_id_list = tuple(port_id_list)
    portgrp.widget = None

    i = 0
    # check that port ids are present and groupable in this group
    for port in canvas.list_ports(group_id=group_id):
        if (port.port_type == port_type
                and port.port_mode == port_mode):
            if port.port_id == port_id_list[i]:
                if port.portgrp_id:
                    _logger.error(
                        f"{_logging_str} - "
                        f"port id {port.port_id} is already in portgroup {port.portgrp_id}")
                    return

                i += 1

                if i == len(port_id_list):
                    # everything seems ok for this portgroup, stop the check
                    break

            elif i > 0:
                _logger.critical(f"{_logging_str} - port ids are not consecutive")
                return
    else:
        _logger.critical(f"{_logging_str} - not enought ports with port_id_list")
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
        if box is None:
            continue

        if box.get_port_mode() & port_mode:
        # if (not box.is_splitted()
        #         or box.get_splitted_mode() == port_mode):
            portgrp.widget = box.add_portgroup_from_group(portgrp)

            if not canvas.loading_items:
                box.update_positions()

@patchbay_api
def remove_portgroup(group_id: int, portgrp_id: int):
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
        _logger.critical(f"{_logging_str} - Unable to find portgrp to remove")
        return

    canvas.remove_portgroup(portgrp)

    if canvas.loading_items:
        return

    if box_widget is not None:
        box_widget.update_positions()

    QTimer.singleShot(0, canvas.scene.update)

@patchbay_api
def connect_ports(connection_id: int, group_out_id: int, port_out_id: int,
                  group_in_id: int, port_in_id: int):    
    out_port = canvas.get_port(group_out_id, port_out_id)
    in_port = canvas.get_port(group_in_id, port_in_id)
    
    if out_port is None or in_port is None:
        _logger.critical(f"{_logging_str} - unable to find ports to connect")
        return
    
    out_port_wg, in_port_wg = out_port.widget, in_port.widget

    connection = ConnectionObject()
    connection.connection_id = connection_id
    connection.group_in_id = group_in_id
    connection.port_in_id = port_in_id
    connection.group_out_id = group_out_id
    connection.port_out_id = port_out_id
    connection.widget = LineWidget(connection_id, out_port_wg, in_port_wg)

    canvas.scene.addItem(connection.widget)

    canvas.add_connection(connection)
    out_port_wg.parentItem().add_line_to_box(connection.widget)
    in_port_wg.parentItem().add_line_to_box(connection.widget)
    out_port_wg.add_line_to_port(connection.widget)
    in_port_wg.add_line_to_port(connection.widget)

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
    
    tmp_conn = connection.copy_no_widget()
    line = connection.widget
    canvas.remove_connection(connection)
    canvas.qobject.connection_removed.emit(connection_id)

    out_port = canvas.get_port(tmp_conn.group_out_id, tmp_conn.port_out_id)
    in_port = canvas.get_port(tmp_conn.group_in_id, tmp_conn.port_in_id)
    
    if out_port is None or in_port is None:
        canvas.scene.removeItem(line)
        del line
    
        _logger.info(f"{_logging_str} - connection cleaned after its ports")
        return
        
    item1 = out_port.widget
    item2 = in_port.widget
    if item1 is None or item2 is None:
        _logger.critical(f"{_logging_str} - port has no widget")
        return

    item1.parentItem().remove_line_from_box(connection)
    item2.parentItem().remove_line_from_box(connection)
    item1.remove_line_from_port(connection)
    item2.remove_line_from_port(connection)

    canvas.scene.removeItem(line)
    del line

    if canvas.loading_items:
        return

    QTimer.singleShot(0, canvas.scene.update)

# ----------------------------------------------------------------------------

@patchbay_api
def get_theme() -> str:
    return canvas.theme_manager.get_theme()

@patchbay_api
def list_themes() -> list[dict]:
    return canvas.theme_manager.list_themes()

@patchbay_api
def change_theme(theme_name='') -> bool:
    return canvas.theme_manager.set_theme(theme_name)

@patchbay_api
def copy_and_load_current_theme(new_theme_name: str) -> int:
    return canvas.theme_manager.copy_and_load_current_theme(new_theme_name)

# ----------------------------------------------------------------------------
@patchbay_api
def redraw_plugin_group(plugin_id: int):
    group = canvas.group_plugin_map.get(plugin_id, None)

    if group is None:
        _logger.critical(f"{_logging_str} - unable to find group")
        return

    assert isinstance(group, GroupObject)

    group.widgets[0].redraw_inline_display()

    if group.splitted and group.widgets[1]:
        group.widgets[1].redraw_inline_display()

@patchbay_api
def handle_plugin_removed(plugin_id: int):
    group = canvas.group_plugin_map.pop(plugin_id, None)

    if group is not None:
        assert isinstance(group, GroupObject)
        group.plugin_id = -1
        group.plugin_ui = False
        group.plugin_inline = False
        group.widgets[0].remove_as_plugin()

        if group.splitted and group.widgets[1]:
            group.widgets[1].remove_as_plugin()

    for group in canvas.group_list:
        if group.plugin_id < plugin_id or group.plugin_id > MAX_PLUGIN_ID_ALLOWED:
            continue

        group.plugin_id -= 1
        group.widgets[0]._plugin_id -= 1

        if group.splitted and group.widgets[1]:
            group.widgets[1]._plugin_id -= 1

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
        group.widgets[0].remove_as_plugin()

        if group.splitted and group.widgets[1]:
            group.widgets[1].remove_as_plugin()

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
def semi_hide_group(group_id: int, yesno: bool):
    group = canvas.get_group(group_id)
    if group is None:
        return

    for widget in group.widgets:
        if widget is not None:
            widget.semi_hide(yesno)

@patchbay_api
def semi_hide_connection(connection_id: int, yesno: bool):
    connection = canvas.get_connection(connection_id)
    if connection and connection.widget is not None:
        connection.widget.semi_hide(yesno)

@patchbay_api
def set_group_in_front(group_id: int):
    canvas.last_z_value += 1
    group = canvas.get_group(group_id)
    if group is None:
        return
    
    for widget in group.widgets:
        if widget is not None:
            widget.setZValue(canvas.last_z_value)

@patchbay_api
def set_connection_in_front(connection_id: int):
    canvas.last_z_value += 1
    
    connection = canvas.get_connection(connection_id)
    if connection and connection.widget is not None:
        connection.widget.setZValue(canvas.last_z_value)

@patchbay_api
def select_port(group_id: int, port_id: int):
    port = canvas.get_port(group_id, port_id)
    if port is None:
        return
    
    if port.widget is None:
        return
    
    box_widget = port.widget.parentItem()
    canvas.scene.clearSelection()

    if box_widget.is_wrapped():
        canvas.scene.center_view_on(box_widget)
        box_widget.setSelected(True)
    else:
        canvas.scene.center_view_on(port.widget)
        port.widget.setSelected(True)

@patchbay_api
def select_filtered_group_box(group_id: int, n_select=1):
    group = canvas.get_group(group_id)
    if group is None:
        return
    
    n_widget = 1

    for widget in group.widgets:
        if widget is not None and widget.isVisible():
            if n_select == n_widget:
                canvas.scene.clearSelection()
                widget.setSelected(True)
                canvas.scene.center_view_on(widget)
                break

            n_widget += 1

@patchbay_api
def get_box_true_layout(group_id: int, port_mode: PortMode) -> BoxLayoutMode:
    '''Should never return BoxLayoutMode.AUTO'''
    group = canvas.get_group(group_id)
    if group_id is None:
        return BoxLayoutMode.AUTO
    
    if port_mode & PortMode.OUTPUT:
        return group.widgets[0]._current_layout_mode
    
    return group.widgets[1]._current_layout_mode

@patchbay_api
def get_number_of_boxes(group_id: int) -> int:
    group = canvas.get_group(group_id)
    if group is None:
        return 0
    
    n = 0
    for widget in group.widgets:
        if widget is not None and widget.isVisible():
            n += 1
    
    return n

@patchbay_api    
def set_semi_hide_opacity(opacity: float):
    options.semi_hide_opacity = opacity

    for box in canvas.list_boxes():
        box.update_opacity()
                
    for conn in canvas.list_connections():
        if conn.widget is not None:
            conn.widget.update_line_gradient()

@patchbay_api
def set_optional_gui_state(group_id: int, visible: bool):
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
    if canvas.scene is None:
        return

    canvas.scene.zoom_reset()
    
@patchbay_api
def zoom_fit():
    if canvas.scene is None:
        return
    
    canvas.scene.zoom_fit()

@patchbay_api
def save_cache():
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