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
from typing import TYPE_CHECKING, Union

from PyQt5.QtCore import QPointF, QFile, QRectF
from PyQt5.QtGui import QIcon, QPalette
from PyQt5.QtWidgets import QWidget

from .patshared import PortMode, BoxType
from .init_values import canvas, options, CallbackAct

if TYPE_CHECKING:
    from .box_widget import BoxWidget

_logger = logging.getLogger(__name__)
_logging_str = ''

_PG_NAME_ENDS = (' ', '_', '.', '-', '#', ':', 'out', 'in', 'Out',
                 'In', 'Output', 'Input', 'output', 'input',
                 ' AUX', '_AUX')

# decorator
def easy_log(func):
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

def get_new_group_positions() -> dict[PortMode, tuple[int, int]]:
    def get_middle_empty_positions(scene_rect: QRectF) -> tuple[int, int]:
        if scene_rect.isNull():
            return ((0, 200))

        needed_x = 120
        needed_y = 120
        margin_x = 50
        margin_y = 10

        x = scene_rect.center().x() - needed_y / 2
        y = scene_rect.top() + 20

        y_list = list[tuple[float, float, float]]()

        min_top = scene_rect.bottom()
        max_bottom = scene_rect.top()

        for widget in canvas.list_boxes():
            box_rect = widget.sceneBoundingRect()
            min_top = min(min_top, box_rect.top())
            max_bottom = max(max_bottom, box_rect.bottom())

            if box_rect.left() - needed_x <= x <= box_rect.right() + margin_x:
                y_list.append(
                    (box_rect.top(), box_rect.bottom(), box_rect.left()))

        if not y_list:
            return (int(x), int(y))

        y_list.sort()
        available_segments = [[min_top, max_bottom, x]]

        for box_top, box_bottom, box_left in y_list:
            for segment in available_segments:
                seg_top, seg_bottom, seg_left = segment

                if box_bottom <= seg_top or box_top >= seg_bottom:
                    continue

                if box_top <= seg_top and box_bottom >= seg_bottom:
                    available_segments.remove(segment)
                    break

                if box_top > seg_top:
                    segment[1] = box_top
                    if box_bottom < seg_bottom:
                        available_segments.insert(
                            available_segments.index(segment) + 1,
                            [box_bottom, seg_bottom, box_left])
                        break

                segment[0] = box_bottom

        if not available_segments:
            return (int(x), int(max_bottom + margin_y))

        available_segments.sort()

        for seg_top, seg_bottom, seg_left in available_segments:
            if seg_bottom - seg_top >= 200:
                y = seg_top + margin_y
                x = seg_left
                break
        else:
            y = max_bottom + margin_y

        return (int(x), int(y))

    rect = canvas.scene.get_new_scene_rect()
    if rect.isNull():
        return {PortMode.BOTH: (200, 0),
                PortMode.INPUT: (400, 0),
                PortMode.OUTPUT: (0, 0)}

    y = rect.bottom()

    return {PortMode.BOTH: get_middle_empty_positions(rect),
            PortMode.INPUT: (400, int(y)),
            PortMode.OUTPUT: (0, int(y))}

def get_portgroup_name_from_ports_names(ports_names: list[str]):
    if len(ports_names) < 2:
        return ''

    # set portgrp name
    portgrp_name = ''

    for c in ports_names[0]:
        for eachname in ports_names:
            if not eachname.startswith(portgrp_name + c):
                break
        else:
            portgrp_name += c
    
    # reduce portgrp name until it ends with one of the patterns
    # in portgrp_name_ends
    while portgrp_name:
        if (portgrp_name.endswith((_PG_NAME_ENDS))
                or portgrp_name in ports_names):
            break
        
        portgrp_name = portgrp_name[:-1]
    
    return portgrp_name

def get_icon(icon_type: BoxType, icon_name: str,
             port_mode: PortMode, dark=True) -> QIcon:
    if icon_type in (BoxType.CLIENT, BoxType.APPLICATION):
        icon = QIcon.fromTheme(icon_name)

        if icon.isNull():
            for ext in ('svg', 'svgz', 'png'):
                filename = ":app_icons/%s.%s" % (icon_name, ext)

                if QFile.exists(filename):
                    del icon
                    icon = QIcon()
                    icon.addFile(filename)
                    break
        return icon

    icon = QIcon()

    if icon_type is BoxType.HARDWARE:
        icon_file = ":/canvas/"
        icon_file += "dark/" if dark else "light/"
           
        if icon_name == "a2j":
            icon_file += "DIN-5.svg"        
        else:
            if port_mode is PortMode.INPUT:
                icon_file += "audio-headphones.svg"
            elif port_mode is PortMode.OUTPUT:
                icon_file += "microphone.svg"
            else:
                icon_file += "pb_hardware.svg"

        icon.addFile(icon_file)

    elif icon_type is BoxType.MONITOR:
        prefix = ":/canvas/"
        prefix += "dark/" if dark else "light/"
        
        if port_mode is PortMode.INPUT:
            icon.addFile(prefix + "monitor_capture.svg")
        else:
            icon.addFile(prefix + "monitor_playback.svg")

    elif icon_type is BoxType.INTERNAL:
        icon.addFile(":/scalable/%s" % icon_name)

    return icon

@easy_log
def canvas_callback(action: CallbackAct, *args):
    canvas.callback(action, *args)

def is_dark_theme(widget: QWidget) -> bool:
    return bool(
        widget.palette().brush(QPalette.Active,
                               QPalette.WindowText).color().lightness()
        > 128)

def boxes_in_dict(boxes: 'list[BoxWidget]') -> dict[int, PortMode]:
        '''concatenate a list of boxes to have a dict
        where key is group_id.'''
        serial_dict = dict[int, PortMode]()
        for box in boxes:
            pmode = serial_dict.get(box._group_id)
            if pmode is None:
                serial_dict[box._group_id] = box._port_mode
            else:
                serial_dict[box._group_id] |= box._port_mode
        return serial_dict

def nearest_on_grid(xy: tuple[int, int]) -> tuple[int, int]:
    x, y = xy
    cell_x = options.cell_width
    cell_y = options.cell_height
    margin = canvas.theme.box_spacing // 2

    ret_x = cell_x * (x // cell_x) + margin
    if x - ret_x > cell_x / 2:
        ret_x += cell_x
    
    ret_y = cell_y * (y // cell_y) + margin
    if y - ret_y > cell_y / 2:
        ret_y += cell_y
    
    return (ret_x, ret_y)

def nearest_on_grid_check_others(
        xy: tuple[int, int], orig_box: 'BoxWidget') -> tuple[int, int]:
    '''return the pos for a just moved box,
    may be not exactly the nearest point on grid,
    to prevent unwanted other boxes move.'''

    spacing = canvas.theme.box_spacing
    check_rect = orig_box.boundingRect().translated(QPointF(*xy))    
    search_rect = check_rect.adjusted(- spacing, - spacing, spacing, spacing)

    boxes = [b for b in canvas.scene.list_boxes_at(search_rect)
             if b is not orig_box]
    x, y = xy
    new_x, new_y = nearest_on_grid(xy)
    
    for box in boxes:
        rect = box.sceneBoundingRect()

        if (previous_top_on_grid(y)
                == previous_top_on_grid(rect.bottom())):
            return (new_x, previous_top_on_grid(y) + options.cell_height)
        
        if (next_bottom_on_grid(check_rect.bottom())
                == next_bottom_on_grid(rect.top())):
            return (new_x, next_top_on_grid(y) - options.cell_height)
     
    return nearest_on_grid(xy)

def previous_left_on_grid(x: int) -> int:
    cell_x = options.cell_width
    margin = canvas.theme.box_spacing / 2
    
    ret = int(cell_x * (x // cell_x) + margin)
    if ret > x:
        ret -= cell_x
    
    return ret

def next_left_on_grid(x: int) -> int:
    cell_x = options.cell_width
    margin = canvas.theme.box_spacing / 2
    
    ret = int(cell_x * (x // cell_x) + margin)
    if ret < x:
        ret += cell_x
    
    return ret

def previous_top_on_grid(y: int) -> int:
    cell_y = options.cell_height
    margin = canvas.theme.box_spacing / 2
    
    ret = int(cell_y * (y // cell_y) + margin)
    if ret > y:
        ret -= cell_y
    
    return ret

def next_top_on_grid(y: int) -> int:
    cell_y = options.cell_height
    margin = canvas.theme.box_spacing / 2
    
    ret = int(cell_y * ((y - 1) // cell_y) + margin)
    if ret < y:
        ret += cell_y

    return ret

def next_bottom_on_grid(y: int) -> int:
    cell_y = options.cell_height
    margin = canvas.theme.box_spacing / 2

    ret = int(cell_y * (1 + y // cell_y) - margin)
    if ret < y:
        ret += cell_y

    return ret

def next_width_on_grid(width: Union[float, int]) -> int:
    cell_x = options.cell_width
    box_spacing = canvas.theme.box_spacing
    ret = cell_x * (1 + (width // cell_x)) - box_spacing
    while ret < width:
        ret += cell_x
    
    return int(ret)

def next_height_on_grid(height: Union[float, int]) -> int:
    cell_y = options.cell_height
    box_spacing = canvas.theme.box_spacing
    ret = cell_y * (1 + (height // cell_y)) - box_spacing
    while ret < height:
        ret += cell_y
    
    return int(ret)
    