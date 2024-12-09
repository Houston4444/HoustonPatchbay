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
from math import ceil
from struct import pack
from typing import Optional, Union

try:
    from sip import voidptr
except:
    # not really used for now because there is no InlineDisplay
    pass

import sys
from enum import Enum

from qtpy.QtCore import Qt, QPointF, QRectF, QTimer, QMarginsF
from qtpy.QtGui import (QCursor, QFontMetrics, QImage, QFont,
                         QLinearGradient, QPainter, QPen, QPolygonF,
                         QColor, QPainterPath, QBrush)
from qtpy.QtWidgets import QGraphicsItem, QApplication

from .patshared import PortMode, BoxLayoutMode, BoxType
from .init_values import (
    AliasingReason,
    CanvasItemType,
    GroupObject,
    PortObject,
    PortgrpObject,
    InlineDisplay,
    canvas,
    options,
    CallbackAct,
    MAX_PLUGIN_ID_ALLOWED,
    Direction,
    Zv)

from .utils import (
    canvas_callback,
    nearest_on_grid, nearest_on_grid_check_others)
from .box_widget_shadow import BoxWidgetShadow
from .icon_widget import IconSvgWidget, IconPixmapWidget
from .port_widget import PortWidget
from .portgroup_widget import PortgroupWidget
from .grouped_lines_widget import GroupedLinesWidget
from .theme import BoxStyleAttributer
from .box_layout import BoxLayout
from .box_hidder import BoxHidder

_logger = logging.getLogger(__name__)


class UnwrapButton(Enum):
    NONE = 0
    LEFT = 1
    CENTER = 2
    RIGHT = 3


class WrappingState(Enum):
    NORMAL = 0
    WRAPPING = 1
    WRAPPED = 2
    UNWRAPPING = 3


class TitleLine:
    text = ''
    size = 0.0
    x = 0
    y = 0
    is_little = False

    def __init__(self, text: str, theme: BoxStyleAttributer, little=False):
        self.theme = theme
        self.text = text
        self.is_little = little
        self.x = 0
        self.y = 0

        self.font = None
        self.size = theme.get_text_width(text)

    def get_font(self) -> QFont:
        return self.theme.font()


class BoxWidgetMoth(QGraphicsItem):
    def __init__(self, group: GroupObject, port_mode: PortMode):
        QGraphicsItem.__init__(self)
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)

        # Save Variables, useful for later
        self._group_id = group.group_id
        self._group_name = group.group_name
        self._box_type = group.box_type

        # plugin Id, < 0 if invalid
        self._plugin_id = -1
        self._plugin_ui = False
        self._plugin_inline = InlineDisplay.DISABLED

        # Base Variables
        self._width = 50
        self._width_in = 0
        self._width_out = 0
        self._header_width = self._width
        self._header_height = 0
        self._wrapped_width = 0
        self._unwrapped_width = 0
        self._wrapped_height = 0
        self._unwrapped_height = 0
        self._height = self._header_height + 1
        self._ports_y_start = self._header_height

        self._last_pos = QPointF()
        self._port_mode = port_mode
        'port modes  it can contain (OUTPUT, INPUT or BOTH)'

        self._current_port_mode = PortMode.NULL
        'depends on present ports'

        self._cursor_moving = False
        self._mouse_down = False
        self._inline_data = None
        self._inline_image = None
        self._inline_scaling = 1.0

        self.is_hardware = bool(group.box_type is BoxType.HARDWARE)
        self._icon_name = group.icon_name

        self._title_lines = list[TitleLine]()
        self._header_line_left = None
        self._header_line_right = None
        
        if group.gpos.boxes[port_mode].is_wrapped():
            self._wrapping_state = WrappingState.WRAPPED
        else:
            self._wrapping_state = WrappingState.NORMAL

        self.hidder_widget: Optional[BoxHidder] = None

        self._wrapping_ratio = 1.0
        self._wrap_triangle_pos = UnwrapButton.NONE

        self._port_list = list[PortObject]()
        self._portgrp_list = list[PortgrpObject]()

        # Icon
        if group.box_type in (BoxType.HARDWARE, BoxType.MONITOR):
            self.top_icon = IconSvgWidget(
                group.box_type, group.icon_name, self._port_mode, self)
        else:
            self.top_icon = IconPixmapWidget(
                group.box_type, group.icon_name, self)
            if self.top_icon.is_null():
                top_icon = self.top_icon
                self.top_icon = None
                del top_icon

        # Shadow
        shadow_theme = canvas.theme.box_shadow
        if self.is_hardware:
            shadow_theme = shadow_theme.hardware
        elif self._box_type is BoxType.CLIENT:
            shadow_theme = shadow_theme.client
        elif self.is_monitor():
            shadow_theme = shadow_theme.monitor
        
        self.shadow = None
        # FIXME FX on top of graphic items make them lose high-dpi
        # See https://bugreports.qt.io/browse/QTBUG-65035
        if (options.show_shadows
                and canvas.scene.get_device_pixel_ratio_f() == 1.0):
            self.shadow = BoxWidgetShadow(self.toGraphicsObject())
            self.shadow.set_fake_parent(self)
            self.shadow.set_theme(shadow_theme)
            self.setGraphicsEffect(self.shadow)
            
            if port_mode is PortMode.INPUT:
                self.shadow.setOffset(4, 2)
            elif port_mode is PortMode.OUTPUT:
                self.shadow.setOffset(-4, 2)
            elif port_mode is PortMode.BOTH:
                self.shadow.setOffset(0, 2)

        # Final touches
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable
                      | QGraphicsItem.GraphicsItemFlag.ItemIsMovable
                      | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)

        # Wait for at least 1 port
        if options.auto_hide_groups:
            self.setVisible(False)

        if options.auto_select_items:
            self.setAcceptHoverEvents(True)

        self._is_semi_hidden = False
        '''is True when the group name does not match
        with the filter bar text. The box opacity becomes lighter.'''
        
        self._can_handle_gui = group.handle_client_gui
        'used for optional-gui switch (NSM)'
        self._gui_visible = group.gui_visible
        'NSM GUI visibility state'

        self._layout_mode = group.gpos.boxes[port_mode].layout_mode
        self._current_layout_mode = BoxLayoutMode.LARGE
        self._title_under_icon = False
        self._painter_path = QPainterPath()
        self._painter_path_sel = QPainterPath()
        self._layout: BoxLayout = None

        canvas.scene.addItem(self)
        self.setZValue(Zv.NEW_BOX.value)

    def get_group_id(self):
        return self._group_id

    def get_group_name(self):
        return self._group_name

    def is_monitor(self):
        return (self._box_type is BoxType.MONITOR
                and self._icon_name in ('monitor_playback', 'monitor_capture'))

    def get_port_mode(self):
        return self._port_mode

    def set_port_mode(self, port_mode: PortMode):
        'Use it only at split/join !!!'
        group = canvas.get_group(self._group_id)
        if group is None:
            _logger.error(
                'set_port_mode impossible, it fails to find its group')
        
        self._port_mode = port_mode
        self._layout_mode = group.gpos.boxes[port_mode].layout_mode

    def get_current_port_mode(self):
        return self._current_port_mode
    
    def set_layout_mode(self, layout_mode: BoxLayoutMode):
        self._layout_mode = layout_mode
    
    def get_current_layout_mode(self) -> BoxLayoutMode:
        if self._layout is None:
            return BoxLayoutMode.AUTO
        return self._layout.layout_mode
    
    def redraw_inline_display(self):
        if self._plugin_inline is InlineDisplay.CACHED:
            self._plugin_inline = InlineDisplay.ENABLED
            self.update()

    def remove_as_plugin(self):
        self._plugin_id = -1
        self._plugin_ui = False

    def set_as_plugin(self, plugin_id, has_ui, has_inline_display):
        if has_inline_display and not options.inline_displays:
            has_inline_display = False

        if not has_inline_display:
            del self._inline_image
            self._inline_data = None
            self._inline_image = None
            self._inline_scaling = 1.0

        self._plugin_id = plugin_id
        self._plugin_ui = has_ui
        self._plugin_inline = (
            InlineDisplay.ENABLED if has_inline_display
            else InlineDisplay.DISABLED)
        self.update()

    def set_icon(self, box_type: BoxType, icon_name: str):
        if isinstance(self.top_icon, IconSvgWidget):
            self.remove_icon_from_scene()

        if (box_type is BoxType.HARDWARE
                and (not icon_name or icon_name == 'a2j')):
            self.top_icon = IconSvgWidget(
                box_type, icon_name, self._port_mode, self)
            return

        if self.top_icon is not None:
            self.top_icon.set_icon(
                box_type, icon_name, self._current_port_mode)
        else:
            self.top_icon = IconPixmapWidget(box_type, icon_name, self)

        self.update_positions()

    def has_top_icon(self) -> bool:
        if self.top_icon is None:
            return False

        return not self.top_icon.is_null()

    def set_optional_gui_state(self, visible: bool):
        self._can_handle_gui = True
        self._gui_visible = visible
        self.update()

    def set_group_name(self, group_name: str):
        self._group_name = group_name
        self.update_positions()

    def set_shadow_opacity(self, opacity):
        if self.shadow:
            self.shadow.set_opacity(opacity)

    def add_port_from_group(self, port: PortObject):
        self.setVisible(True)

        new_widget = PortWidget(port, self)
        if self._wrapping_state is not WrappingState.NORMAL:
            new_widget.setVisible(False)

        return new_widget

    def add_portgroup_from_group(self, portgroup: PortgrpObject):
        new_widget = PortgroupWidget(portgroup, self)

        if self._wrapping_state is not WrappingState.NORMAL:
            new_widget.setVisible(False)

        return new_widget

    def check_item_pos(self):
        if canvas.size_rect.isNull():
            return
        
        pos = self.scenePos()
        if not (canvas.size_rect.contains(pos) and
                canvas.size_rect.contains(
                    pos + QPointF(self._width, self._height))):
            if pos.x() < canvas.size_rect.x():
                self.setPos(canvas.size_rect.x(), pos.y())
            elif pos.x() + self._width > canvas.size_rect.width():
                self.setPos(canvas.size_rect.width() - self._width, pos.y())

            pos = self.scenePos()
            if pos.y() < canvas.size_rect.y():
                self.setPos(pos.x(), canvas.size_rect.y())
            elif pos.y() + self._height > canvas.size_rect.height():
                self.setPos(pos.x(), canvas.size_rect.height() - self._height)

    def remove_icon_from_scene(self):
        if self.top_icon is None:
            return

        item = self.top_icon
        self.top_icon = None
        canvas.scene.removeItem(item)
        del item
        
    def animate_wrapping(self, ratio: float):
        # we expose wrapping ratio only for prettier animation
        # i.e. self._wrapping_ratio = ratio would also works fine        
        if self._wrapping_state is WrappingState.WRAPPING:
            self._wrapping_ratio = ratio ** 0.25
        elif self._wrapping_state is WrappingState.UNWRAPPING:
            self._wrapping_ratio = ratio ** 4
        else:
            return

        if ratio == 1.00:
            # counter is terminated
            if self._wrapping_state is WrappingState.UNWRAPPING:
                self.hide_ports_for_wrap(False)
                self._wrapping_state = WrappingState.NORMAL
            else:
                self._wrapping_state = WrappingState.WRAPPED

        self.update_positions(wrap_anim=True, scene_checks=False)

    def animate_hidding(self, ratio: float):
        'ratio goes from 0.0 (box shown) to 1.0 (box hidden)'
        if ratio >= 1.0:
            if self.hidder_widget is not None:
                canvas.scene.removeItem(self.hidder_widget)
                self.hidder_widget = None

            self.setVisible(False)
            self.setZValue(
                Zv.SEL_BOX.value if self.isSelected() else Zv.BOX.value)
        else:
            if self.hidder_widget is None:
                self.hidder_widget = BoxHidder(self)
            self.hidder_widget.set_hide_ratio(ratio)
        
            self.setZValue(Zv.HIDDING_BOX.value)
        
    def animate_restoring(self, ratio: float):
        'ratio goes from 0.0 (box hidden) to 1.0 (box shown)'
        if ratio >= 1.0:
            if self.hidder_widget is not None:
                canvas.scene.removeItem(self.hidder_widget)
                self.hidder_widget = None

            self.setZValue(
                Zv.SEL_BOX.value if self.isSelected() else Zv.BOX.value)
            
        else:
            if self.hidder_widget is None:
                self.hidder_widget = BoxHidder(self)
            self.hidder_widget.set_hide_ratio(1.0 - ratio)
            self.setZValue(Zv.HIDDING_BOX.value)

    def is_hidding_or_restore(self) -> bool:
        return self.hidder_widget is not None

    def hide_ports_for_wrap(self, hide: bool):
        for portgrp in canvas.list_portgroups(group_id=self._group_id):
            if not portgrp.port_mode & self._port_mode:
                continue

            if portgrp.widget is not None:
                portgrp.widget.setVisible(not hide)

        for port in canvas.list_ports(group_id=self._group_id):
            if not port.port_mode & self._port_mode:
                continue

            if port.widget is not None:
                port.widget.setVisible(not hide)

    def ports_are_visible(self) -> bool:
        return self._wrapping_state is WrappingState.NORMAL

    def is_wrapped(self) -> bool:
        return bool(
            self._wrapping_state in (
                WrappingState.WRAPPED, WrappingState.WRAPPING))

    def set_wrapped(self, yesno: bool, animate=True, prevent_overlap=True):
        if yesno == bool(self._wrapping_state
                         in (WrappingState.WRAPPED, WrappingState.WRAPPING)):
            return

        if yesno:
            self.hide_ports_for_wrap(True)

        if not animate:
            if yesno:
                self._wrapping_state = WrappingState.WRAPPED
            else:
                self._wrapping_state = WrappingState.NORMAL
                self.hide_ports_for_wrap(False)
            return

        if yesno:
            self._wrapping_state = WrappingState.WRAPPING
        else:
            self._wrapping_state = WrappingState.UNWRAPPING

        canvas.scene.add_box_to_animation_wrapping(self, yesno)
        
        if not prevent_overlap:
            return
        
        if self._has_side_title() and self._current_port_mode is PortMode.OUTPUT:
            # keep ports at same right pos in this case.
            x, y = self.top_left()

            if yesno:
                new_x = int(x + self._width - self._wrapped_width)
            else:
                new_x = int(x + self._width - self._unwrapped_width)
            canvas.scene.add_box_to_animation(self, new_x, y)

        if yesno:
            hws = canvas.theme.hardware_rack_width
            new_bounding_rect = QRectF(0, 0, self._width, self._wrapped_height)
            if self.is_hardware:
                new_bounding_rect = QRectF(- hws, - hws, self._width + 2 * hws,
                                           self._wrapped_height + 2 * hws)
            canvas.scene.bring_neighbors_and_deplace_boxes(
                self, self.sceneBoundingRect())

        else:
            canvas.scene.deplace_boxes_from_repulsers(
                [self], wanted_direction=Direction.DOWN)

    def update_positions(self, even_animated=False, without_connections=False,
                         scene_checks=True, theme_change=False,
                         wrap_anim=False):
        # see box_widget.py
        ...

    def repaint_lines(self, forced=False, fast_move=False):
        if forced or self.pos() != self._last_pos:
            for port in self._port_list:
                if port.hidden_conn_widget is not None:
                    port.hidden_conn_widget.update_line_pos()

            for gp_lines in GroupedLinesWidget.widgets_for_box(
                    self._group_id, self._current_port_mode):
                gp_lines.update_lines_pos(fast_move=fast_move)

        self._last_pos = self.pos()

    def semi_hide(self, yesno: bool):
        self._is_semi_hidden = yesno
        if yesno:
            self.setOpacity(options.semi_hide_opacity)
        else:
            self.setOpacity(1.0)

        for port in self._port_list:
            if port.hidden_conn_widget is not None:
                port.hidden_conn_widget.semi_hide(yesno)

    def update_opacity(self):
        if not self._is_semi_hidden:
            return

        self.setOpacity(options.semi_hide_opacity)
        for port in self._port_list:
            if port.hidden_conn_widget is not None:
                port.hidden_conn_widget.update_line_gradient()
                port.hidden_conn_widget.update()

    def _has_side_title(self):
        return bool(
            self._current_port_mode is not PortMode.BOTH
            and self._current_layout_mode == BoxLayoutMode.LARGE)

    def wrap_unwrap_at_point(self, scene_pos: QPointF) -> bool:
        '''order a wrap or unwrap on the box if scene_pos is on the
            triangle wrapper'''
        if self._wrapping_state is WrappingState.WRAPPED:
            # unwrap the box if scene_pos is in one of the triangles zones
            triangle_rect_out = QRectF(0.0, self._height - 24.0, 24.0, 24.0)
            triangle_rect_in = QRectF(
                self._width - 24.0, self._height - 24.0, 24.0, 24.0)

            mode = PortMode.INPUT
            wrap = False

            for trirect in triangle_rect_out, triangle_rect_in:
                trirect.translate(self.scenePos())
                if (self._current_port_mode & mode
                        and trirect.contains(scene_pos)):
                    wrap = True
                    break

                mode = PortMode.OUTPUT

            if wrap:
                canvas_callback(
                    CallbackAct.GROUP_WRAP, self._group_id,
                    self._port_mode, False)
                return True
            
        elif self._wrap_triangle_pos is not UnwrapButton.NONE:
            # wrap the box if scene_pos is on the triangle zone
            trirect = QRectF(0, self._height - 16, 16, 16)
            
            if self._wrap_triangle_pos is UnwrapButton.CENTER:
                center_width = (self._width + self._layout._pms.ins_width
                                - self._layout._pms.outs_width) / 2.0
                
                trirect = QRectF(center_width - 8.0, self._height - 16.0,
                                 16.0, 16.0)
            elif self._wrap_triangle_pos is UnwrapButton.RIGHT:
                trirect = QRectF(self._width - 16.0, self._height -16.0,
                                 16.0, 16.0)
                
            trirect.translate(self.scenePos())
            if trirect.contains(scene_pos):
                canvas_callback(
                    CallbackAct.GROUP_WRAP, self._group_id,
                    self._port_mode, True)
                return True
        
        return False

    def type(self) -> CanvasItemType:
        return CanvasItemType.BOX

    # --- protected Qt Functions redefined here ---
    
    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            is_selected = bool(value)
            if is_selected:
                self.setZValue(Zv.SEL_BOX.value)
            else:
                self.setZValue(Zv.BOX.value)

            if not canvas.scene.selecting_boxes:
                if is_selected:
                    for lines in GroupedLinesWidget.widgets_for_box(
                            self._group_id, self._port_mode):
                        lines.setZValue(Zv.SEL_BOX_LINE.value)

                    canvas_callback(
                        CallbackAct.GROUP_SELECTED, self._group_id,
                        self._port_mode)
                else:
                    for lines in GroupedLinesWidget.widgets_for_box(
                            self._group_id, self._port_mode):
                        lines.setZValue(Zv.LINE.value)

        return super().itemChange(change, value)

    def contextMenuEvent(self, event):
        if canvas.is_line_mov:
            return

        event.accept()
        canvas.menu_shown = True

        canvas.callback(CallbackAct.GROUP_MENU_CALL,
                        self._group_id,
                        self._port_mode)

        canvas.menu_click_pos = QCursor.pos()

    def keyPressEvent(self, event):
        if self._plugin_id >= 0 and event.key() == Qt.Key.Key_Delete:
            event.accept()
            canvas.callback(CallbackAct.PLUGIN_REMOVE, self._plugin_id)
            return
        QGraphicsItem.keyPressEvent(self, event)

    def hoverEnterEvent(self, event):
        if options.auto_select_items:
            if len(canvas.scene.selectedItems()) > 0:
                canvas.scene.clearSelection()
            self.setSelected(True)
        QGraphicsItem.hoverEnterEvent(self, event)

    def mouseDoubleClickEvent(self, event):
        if self._can_handle_gui:
            canvas.callback(
                CallbackAct.CLIENT_SHOW_GUI, self._group_id,
                not self._gui_visible)

        if self._plugin_id >= 0:
            event.accept()
            canvas.callback(
                CallbackAct.PLUGIN_SHOW_UI
                if self._plugin_ui else CallbackAct.PLUGIN_EDIT,
                self._plugin_id)
            return

        QGraphicsItem.mouseDoubleClickEvent(self, event)

    def mousePressEvent(self, event):
        self._cursor_moving = False
        if canvas.menu_shown and canvas.menu_click_pos == QCursor.pos():
            # prevent box move if user just quit a context menu with click outside
            # because it moves the box at the very strange position
            # if the cursor didn't move between the click for menu quit 
            # and the next one (this one).
            # strange Qt Bug.
            self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        
        elif event.button() == Qt.MouseButton.RightButton:
            event.accept()
            canvas.scene.clearSelection()
            self.setSelected(True)
            self._mouse_down = False
            return

        elif event.button() == Qt.MouseButton.LeftButton:
            if self.sceneBoundingRect().contains(event.scenePos()):
                if self.wrap_unwrap_at_point(event.scenePos()):
                    event.ignore()
                    return

                self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
                self._mouse_down = True
        else:
            self._mouse_down = False

        QGraphicsItem.mousePressEvent(self, event)

    def mouseMoveEvent(self, event):
        if canvas.scene.resizing_scene:
            # QGraphicsScene.setSceneRect calls this method indirectly
            # and resize_the_scene can be called from this method
            # So, here we avoid a RecursionError
            return

        if canvas.scene.prevent_box_user_move:
            return

        if self._mouse_down:
            if not self._cursor_moving:
                # if box is moved by animation, animation could relocate
                # the box just after, prevent this.
                canvas.scene.remove_box_from_animation(self)

                canvas.scene.set_cursor(QCursor(Qt.CursorShape.SizeAllCursor))
                self._cursor_moving = True
                canvas.scene.fix_temporary_scroll_bars()
            QGraphicsItem.mouseMoveEvent(self, event)

            for item in canvas.scene.get_selected_boxes():
                item.repaint_lines(fast_move=True)

            canvas.scene.resize_the_scene()
            canvas.qobject.start_aliasing_check(AliasingReason.USER_MOVE)
            return

        QGraphicsItem.mouseMoveEvent(self, event)

    def mouseReleaseEvent(self, event):
        if self._cursor_moving:
            canvas.scene.unset_cursor()
            self.repaint_lines(forced=True)
            canvas.scene.reset_scroll_bars()
            
            selected_boxes = canvas.scene.get_selected_boxes()
            
            # callback the state of positions 
            arg_list = list[tuple[int, PortMode, int, int]]()
            if len(selected_boxes) == 1:
                xy = nearest_on_grid_check_others(self.top_left(), self)
                arg_list.append(
                    (self._group_id, self._port_mode, *xy))
            else: 
                # many selected boxes, do not auto-adapt the position
                # to other existing boxes (no check_others)
                for box in selected_boxes:
                    xy = nearest_on_grid(box.top_left())
                    arg_list.append((box._group_id, box._port_mode, *xy))
                
            canvas.callback(CallbackAct.BOXES_MOVED, *arg_list)

            canvas.set_aliasing_reason(AliasingReason.USER_MOVE, False)

            QTimer.singleShot(0, canvas.scene.update)

        self._mouse_down = False

        if (QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier
                and not self._cursor_moving):
            return
        
        self._cursor_moving = False
        
        QGraphicsItem.mouseReleaseEvent(self, event)
    
    def fix_pos(self, check_others=False):
        xy = self.top_left()

        if check_others:
            new_xy = nearest_on_grid_check_others(xy, self)
        else:
            new_xy = nearest_on_grid(xy)
        
        if xy == new_xy:
            self.set_top_left(xy)
            self.repaint_lines()
        else:
            canvas.scene.add_box_to_animation(self, *new_xy)

    def top_left(self) -> tuple[int, int]:
        return (round(self.sceneBoundingRect().left()),
                round(self.sceneBoundingRect().top()))

    def set_top_left(self, xy: Union[tuple[int, int], tuple[float, float]]):        
        if self.is_hardware:
            point = QPointF(*xy)
            point += QPointF(
                canvas.theme.hardware_rack_width,
                canvas.theme.hardware_rack_width)
            self.setPos(point)
        else:
            self.setPos(QPointF(*xy))

    def send_move_callback(self):
        group = canvas.get_group(self._group_id)
        if group is None:
            _logger.warning(
                "send_move_callback - "
                f"Box has no group_id {self._group_id} in canvas")
            return

        box_pos = group.gpos.boxes[self._port_mode]
        box_pos.pos = self.top_left()
        box_pos.set_wrapped(self.is_wrapped())
        box_pos.layout_mode = self._layout_mode

        canvas_callback(
            CallbackAct.GROUP_BOX_POS_CHANGED, self._group_id,
            self._port_mode, box_pos)
        group.gpos.boxes[self._port_mode].pos = self.top_left()

    def set_in_cache(self, yesno: bool):
        cache_mode = self.cacheMode()
        if yesno and cache_mode == QGraphicsItem.CacheMode.DeviceCoordinateCache:
            return
        
        if not yesno and cache_mode == QGraphicsItem.CacheMode.NoCache:
            return

        # toggle cache_mode value
        if cache_mode == QGraphicsItem.CacheMode.DeviceCoordinateCache:
            cache_mode = QGraphicsItem.CacheMode.NoCache
        else:
            cache_mode = QGraphicsItem.CacheMode.DeviceCoordinateCache
        
        self.setCacheMode(cache_mode)
        for port in self._port_list:
            if port.widget is not None:
                port.widget.setCacheMode(cache_mode)
        
        for portgroup in self._portgrp_list:
            if (self._current_port_mode & portgroup.port_mode
                    and portgroup.widget is not None):
                portgroup.widget.setCacheMode(cache_mode)

    def after_wrap_rect(self):
        if self._wrapping_state in (WrappingState.NORMAL,
                                    WrappingState.UNWRAPPING):
            width = self._unwrapped_width
            height = self._unwrapped_height
        else:
            width = self._wrapped_width
            height = self._wrapped_height
        
        if self.is_hardware:
            hws = float(canvas.theme.hardware_rack_width)
            
            return QRectF(- hws, - hws,
                          width + 2.0 * hws,
                          height + 2.0 * hws)
        return QRectF(0.0, 0.0, float(width), float(height))

    def rect_needed_in_scene(self, futur=False) -> QRectF:
        '''return the rect that can change the scene size'''
        if (self._current_port_mode is PortMode.NULL
                or not self.isVisible()):
            return QRectF()
        
        if futur:
            move_box = canvas.scene.move_boxes.get(self)
            if move_box is not None:
                if move_box.final_rect.isNull():
                    return move_box.final_rect

                if self._current_port_mode is PortMode.OUTPUT:
                    return move_box.final_rect.marginsAdded(
                        QMarginsF(20.0, 20.0, 50.0, 20.0))
                if self._current_port_mode is PortMode.INPUT:
                    return move_box.final_rect.marginsAdded(
                        QMarginsF(50.0, 20.0, 20.0, 20.0))
                return move_box.final_rect.marginsAdded(
                    QMarginsF(50.0, 20.0, 50.0, 20.0))
        
        # the scene size needs a little margin at top and bottom
        # of the box.
        # It needs a bigger margin on sides with ports,
        # for the possible connections.
        
        if self._current_port_mode is PortMode.OUTPUT:
            return self.sceneBoundingRect().marginsAdded(
                QMarginsF(20.0, 20.0, 50.0, 20.0))
        if self._current_port_mode is PortMode.INPUT:
            return self.sceneBoundingRect().marginsAdded(
                QMarginsF(50.0, 20.0, 20.0, 20.0))
        return self.sceneBoundingRect().marginsAdded(
            QMarginsF(50.0, 20.0, 50.0, 20.0))

    def boundingRect(self):
        if self.is_hardware:
            hws = canvas.theme.hardware_rack_width
            
            return QRectF(- hws, - hws,
                          self._width + 2 * hws,
                          self._height + 2 * hws)
        return QRectF(0, 0, self._width, self._height)

    def paint(self, painter, option, widget):
        if canvas.loading_items:
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # define theme for box, wrappers and header lines
        theme = canvas.theme.box
        wtheme = canvas.theme.box_wrapper
        hltheme = canvas.theme.box_header_line
        
        if self.is_hardware:
            theme = theme.hardware
            wtheme = wtheme.hardware
            hltheme = hltheme.hardware
        elif self._box_type is BoxType.CLIENT:
            theme = theme.client
            wtheme = wtheme.client
            hltheme = hltheme.client
        elif (self._box_type is BoxType.INTERNAL
                and self._icon_name == 'monitor_playback'):
            theme = theme.monitor
            wtheme = wtheme.monitor
            hltheme = hltheme.monitor

        if self.isSelected():
            theme = theme.selected
            wtheme = wtheme.selected
            hltheme = hltheme.selected

        bg_image = theme.background_image()

        # draw the background image if exists
        if bg_image:
            painter.setBrush(QBrush(bg_image))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPath(self._painter_path)

        # draw the main rectangle
        pen = theme.fill_pen()        
        painter.setPen(pen)
        pen_width = pen.widthF()

        color_main = theme.background_color()
        color_alter = theme.background2_color()

        if color_alter is not None:
            max_size = max(self._height, self._width)
            box_gradient = QLinearGradient(0, 0, max_size, max_size)
            gradient_size = 20

            box_gradient.setColorAt(0, color_main)
            tot = int(max_size / gradient_size)
            for i in range(tot):
                if i % 2 == 0:
                    box_gradient.setColorAt((i/tot) ** 0.7, color_main)
                else:
                    box_gradient.setColorAt((i/tot) ** 0.7, color_alter)

            painter.setBrush(box_gradient)
        else:
            painter.setBrush(color_main)
        
        if self.isSelected():
            painter.drawPath(self._painter_path_sel)
        else:
            painter.drawPath(self._painter_path)
        
        # draw hardware box decoration (flyrack like)
        self._paint_hardware_rack(painter)

        # Draw plugin inline display if supported
        self._paint_inline_display(painter)

        # Draw toggle GUI client button
        if self._can_handle_gui:
            header_rect = QRectF(
                3.0 + pen_width, 3.0 + pen_width,
                self._width - 6.0 - 2 * pen_width, self._header_height - 6.0)
            if self._has_side_title():
                if self._current_port_mode is PortMode.INPUT:
                    header_rect = QRectF(
                        self._width - self._header_width - pen_width + 3.0,
                        3.0 + pen_width,
                        self._header_width - 6.0,
                        self._header_height -6.0)
                elif self._current_port_mode is PortMode.OUTPUT:
                    header_rect = QRectF(
                        3.0 + pen_width, 3.0 + pen_width,
                        self._header_width - 6.0, self._header_height - 6.0)
            
            gui_theme = canvas.theme.gui_button
            if self._gui_visible:
                gui_theme = gui_theme.gui_visible
            else:
                gui_theme = gui_theme.gui_hidden
            
            painter.setBrush(gui_theme.background_color())
            painter.setPen(gui_theme.fill_pen())
            
            radius = gui_theme.border_radius()
            if radius == 0.0:
                painter.drawRect(header_rect)
            else:
                painter.drawRoundedRect(header_rect, radius, radius)

        # draw Pipewire Monitor (or PulseAudio bridges) decorations
        elif self.is_monitor() and not self._current_port_mode is PortMode.BOTH:
            if self._current_port_mode is PortMode.OUTPUT:
                bor_gradient = QLinearGradient(0, 0, self._height, self._height)
            else:
                bor_gradient = QLinearGradient(
                    self._width, 0, self._height, self._width - self._height)
            
            mon_theme = canvas.theme.monitor_decoration
            if self.isSelected():
                mon_theme = mon_theme.selected
            
            color_main = mon_theme.background_color()
            color_alter = mon_theme.background2_color()

            if color_alter is not None:
                tot = int(self._height / 20)
                for i in range(tot):
                    if i % 2 == 0:
                        bor_gradient.setColorAt(i/tot, color_main)
                    else:
                        bor_gradient.setColorAt(i/tot, color_alter)

                painter.setBrush(bor_gradient)
            else:
                painter.setBrush(color_main)

            painter.setPen(mon_theme.fill_pen())

            BAND_MON_WIDTH = 9
            TRIANGLE_MON_SIZE_TOP = 7
            triangle_mon_size_bottom = 0
            if (self._wrapping_state in (WrappingState.WRAPPING,
                                         WrappingState.UNWRAPPING)
                    or (self._wrapping_state is WrappingState.NORMAL
                        and self._wrap_triangle_pos is not UnwrapButton.NONE)):
                triangle_mon_size_bottom = 13

            bmw = BAND_MON_WIDTH
            tms_top = TRIANGLE_MON_SIZE_TOP
            tms_bot = triangle_mon_size_bottom

            xside = pen_width
            xband = pen_width + bmw
            xtop = pen_width + bmw + tms_top
            xbot = pen_width + bmw + tms_bot

            if self._current_port_mode is PortMode.INPUT:
                xside = self._width - xside
                xband = self._width - xband
                xtop = self._width - xtop
                xbot = self._width - xbot                

            mon_poly = QPolygonF()
            mon_poly += QPointF(xside, pen_width)
            mon_poly += QPointF(xtop, pen_width)
            mon_poly += QPointF(xband, pen_width + tms_top)
            mon_poly += QPointF(xband, self._height - tms_bot - pen_width)
            mon_poly += QPointF(xbot, self._height - pen_width)
            mon_poly += QPointF(xside, self._height - pen_width)
            
            painter.drawPolygon(mon_poly)

        # may draw horizontal lines around title (header lines)
        if (self._header_line_left is not None
                and self._header_line_right is not None):
            painter.setPen(hltheme.fill_pen())
            painter.drawLine(QPointF(*self._header_line_left[0:2]),
                             QPointF(*self._header_line_left[2:]))
            painter.drawLine(QPointF(*self._header_line_right[0:2]),
                             QPointF(*self._header_line_right[2:]))

        normal_color = theme.text_color()
        opac_color = QColor(normal_color)
        opac_color.setAlpha(int(normal_color.alpha() / 2))
        
        text_pen = QPen(normal_color)
        opac_text_pen = QPen(opac_color)

        # draw title lines
        for title_line in self._title_lines:
            painter.setFont(title_line.get_font())
            
            if title_line.is_little:
                painter.setPen(opac_text_pen)
            else:
                painter.setPen(text_pen)

            if (self.is_monitor()
                    and title_line == self._title_lines[-1]
                    and self._group_name.endswith(' Monitor')):
                # Title line endswith " Monitor"
                # Draw "Monitor" in yellow
                # but keep the rest in white
                pre_text = title_line.text.rpartition(' Monitor')[0]
                painter.drawText(
                    ceil(title_line.x), ceil(title_line.y), pre_text)

                x_pos = title_line.x
                if pre_text:
                    t_font = title_line.get_font()
                    x_pos += QFontMetrics(t_font).horizontalAdvance(pre_text)
                    x_pos += QFontMetrics(t_font).horizontalAdvance(' ')

                painter.setPen(QPen(canvas.theme.monitor_color, 0))
                painter.drawText(ceil(x_pos), ceil(title_line.y), 'Monitor')
            else:
                painter.drawText(ceil(title_line.x), ceil(title_line.y),
                                 title_line.text)

        # draw (un)wrapper triangles
        painter.setPen(wtheme.fill_pen())
        painter.setBrush(wtheme.background_color())
        tr_pen_width = pen.widthF()

        if self._wrapping_state in (WrappingState.WRAPPED,
                                    WrappingState.UNWRAPPING):
            for port_mode in PortMode.INPUT, PortMode.OUTPUT:
                if self._current_port_mode & port_mode:
                    if self._has_side_title():
                        side = 9
                        # offset = 4
                        # ypos = self._height - offset
                        ypos = self._height - pen_width - 2.0

                        triangle = QPolygonF()
                        if port_mode is PortMode.INPUT:
                            xpos = pen_width + 2.0
                            triangle += QPointF(xpos, ypos)
                            triangle += QPointF(xpos, ypos - side)
                            triangle += QPointF(xpos + side, ypos)
                        else:
                            xpos = self._width - pen_width - 2.0
                            triangle += QPointF(xpos, ypos)
                            triangle += QPointF(xpos, ypos - side)
                            triangle += QPointF(xpos - side, ypos)
                    else:
                        side = 6
                        xpos = pen_width + 2.0
                        ypos = self._height - pen_width - side - 2.0

                        if port_mode is PortMode.OUTPUT:
                            xpos = self._width - pen_width - 2.0 - 2 * side

                        triangle = QPolygonF()
                        triangle += QPointF(xpos, ypos)
                        triangle += QPointF(xpos + 2 * side, ypos)
                        triangle += QPointF(xpos + side, ypos + side)
                    
                    painter.drawPolygon(triangle)

        elif self._wrap_triangle_pos is UnwrapButton.LEFT:
            side = 6
            xpos = 2.0 + pen_width
            ypos = self._height - pen_width - 2.0
            triangle = QPolygonF()
            triangle += QPointF(xpos, ypos)
            triangle += QPointF(xpos + 2 * side, ypos)
            triangle += QPointF(xpos + side, ypos -side)

            painter.drawPolygon(triangle)
        
        elif self._wrap_triangle_pos is UnwrapButton.RIGHT:
            side = 6
            xpos = self._width - pen_width - 2 * side - 2.0
            
            ypos = self._height - pen_width - 2.0
            triangle = QPolygonF()
            triangle += QPointF(xpos, ypos)
            triangle += QPointF(xpos + 2 * side, ypos)
            triangle += QPointF(xpos + side, ypos - side)
            painter.drawPolygon(triangle)
        
        elif self._wrap_triangle_pos is UnwrapButton.CENTER:
            side = 7
            xpos = (self._width 
                    + self._layout._pms.ins_width
                    - self._layout._pms.outs_width) / 2 - side
            
            ypos = self._height - tr_pen_width / 2.0
            triangle = QPolygonF()
            triangle += QPointF(xpos, ypos)
            triangle += QPointF(xpos + 2 * side, ypos)
            triangle += QPointF(xpos + side, ypos -side)
            painter.drawPolygon(triangle)

        painter.restore()

    def _paint_hardware_rack(self, painter: QPainter):
        if not self.is_hardware:
            return
        
        d = float(canvas.theme.hardware_rack_width)
        sd = d * 0.5
        
        theme = canvas.theme.hardware_rack
        if self.isSelected():
            theme = theme.selected
        
        background1 = theme.background_color()
        background2 = theme.background2_color()
        
        if background2 is not None:
            hw_gradient = QLinearGradient(
                -d, -d, self._width + d, self._height + d)
            hw_gradient.setColorAt(0, background1)
            hw_gradient.setColorAt(0.5, background2)
            hw_gradient.setColorAt(1, background1)

            painter.setBrush(hw_gradient)
        else:
            painter.setBrush(background1)
        
        pen = theme.fill_pen()
        painter.setPen(pen)
        lh = pen.widthF() / 2.0
        
        ports_top_in = self._layout.ports_top_in
        ports_top_out = self._layout.ports_top_out
        ports_bottom_in = self._layout.ports_bottom_in
        ports_bottom_out = self._layout.ports_bottom_out
        
        if self._current_port_mode is not PortMode.BOTH:
            if self._current_port_mode is PortMode.INPUT:
                points = [
                    (- lh, - lh),
                    (- lh, ports_top_in - lh),
                    (- sd, ports_top_in - lh),
                    (- d + lh, ports_top_in - sd),
                    (- d + lh, - sd),
                    (- sd, - d + lh),
                    (self._width + sd, - d + lh),
                    (self._width + d - lh, -sd),
                    (self._width + d - lh, self._height - lh + sd),
                    (self._width + sd, self._height + d - lh),
                    (- sd, self._height + d - lh),
                    (-d + lh, self._height + sd),
                    (-d + lh, ports_bottom_in + sd),
                    (- sd, ports_bottom_in + lh),
                    (- lh, ports_bottom_in + lh),
                    (- lh, self._height + lh),
                    (self._width + lh, self._height + lh),
                    (self._width + lh, - lh)
                ]
                
            else:
                points = [
                    (self._width + lh, - lh),
                    (self._width + lh, ports_top_out - lh),
                    (self._width + sd, ports_top_out - lh),
                    (self._width + d - lh, ports_top_out - sd),
                    (self._width + d - lh, - sd),
                    (self._width + sd, -d + lh),
                    (- sd, -d + lh),
                    (-d + lh, - sd),
                    (-d + lh, self._height + sd),
                    (- sd, self._height + d - lh),
                    (self._width + sd, self._height + d - lh),
                    (self._width + d - lh, self._height + sd),
                    (self._width + d - lh, ports_bottom_out + sd),
                    (self._width + sd, ports_bottom_out + lh),
                    (self._width + lh, ports_bottom_out + lh),
                    (self._width + lh, self._height + lh),
                    (-lh, self._height + lh),
                    (-lh, -lh)
                ]
            
            hardware_poly = QPolygonF()   
            for xy in points:
                hardware_poly += QPointF(*xy)

            painter.drawPolygon(hardware_poly)
        else:
            top_points = [
                (- lh, - lh),
                (- lh, ports_top_in - lh),
                (- sd, ports_top_in - lh),
                (- d + lh, ports_top_in - sd),
                (- d + lh, - sd),
                (- sd, -d + lh),
                (self._width + sd, -d + lh),
                (self._width + d - lh, - sd),
                (self._width + d - lh, ports_top_out - sd),
                (self._width + d/2, ports_top_out - lh),
                (self._width + lh, ports_top_out - lh),
                (self._width + lh, -lh)
            ]

            bottom_points = [
                (- lh, self._height + lh),
                (- lh, ports_bottom_in + lh),
                (- sd, ports_bottom_in + lh),
                (- d + lh, ports_bottom_in + sd),
                (-d + lh, self._height + sd),
                (- sd, self._height + d - lh),
                (self._width + sd, self._height + d - lh),
                (self._width + d - lh, self._height + sd),
                (self._width + d - lh, ports_bottom_out + sd),
                (self._width + sd, ports_bottom_out + lh),
                (self._width + lh, ports_bottom_out + lh),
                (self._width + lh, self._height + lh)
            ]
            
            hw_poly_top = QPolygonF()
            for xy in top_points:
                hw_poly_top += QPointF(*xy)
            painter.drawPolygon(hw_poly_top)
            
            hw_poly_bottom = QPolygonF()
            for xy in bottom_points:
                hw_poly_bottom += QPointF(*xy)
            painter.drawPolygon(hw_poly_bottom)

    # def _paint_hidding_polygon(self, painter: QPainter):
    #     theme = canvas.theme.background_color()

    def _paint_inline_display(self, painter: QPainter):
        if self._plugin_inline is InlineDisplay.DISABLED:
            return
        if not options.inline_displays:
            return

        inwidth  = self._width - self._width_in - self._width_out - 16
        inheight = (self._height - self._header_height
                    - self.get_theme().port_spacing() - 3)
        scaling  = (canvas.scene.get_scale_factor()
                    * canvas.scene.get_device_pixel_ratio_f())

        if (self._plugin_id >= 0
                and self._plugin_id <= MAX_PLUGIN_ID_ALLOWED
                and (self._plugin_inline is InlineDisplay.ENABLED
                     or self._inline_scaling != scaling)):
            data = canvas.callback(
                CallbackAct.INLINE_DISPLAY, self._plugin_id,
                int(inwidth*scaling), int(inheight*scaling))

            if data is None:
                return

            # invalidate old image first
            del self._inline_image

            self._inline_data = pack(
                "%iB" % (data['height'] * data['stride']), *data['data'])
            self._inline_image = QImage(
                voidptr(self._inline_data), data['width'], data['height'],
                data['stride'], QImage.Format.Format_ARGB32)
            self._inline_scaling = scaling
            self._plugin_inline = InlineDisplay.CACHED

        if self._inline_image is None:
            _logger.warning(
                'inline display image is None for '
                f'{self._plugin_id}, {self._group_name}')
            return

        swidth = self._inline_image.width() / scaling
        sheight = self._inline_image.height() / scaling

        srcx = int(self._width_in
                   + (self._width - self._width_in - self._width_out) / 2
                   - swidth / 2)
        srcy = int(self._header_height + 1 + (inheight - sheight) / 2)

        painter.drawImage(
            QRectF(srcx, srcy, swidth, sheight), self._inline_image)
    
    def get_theme(self, for_wrapper=False) -> BoxStyleAttributer:
        theme = canvas.theme.box
        if for_wrapper:
            theme = canvas.theme.box_wrapper
        
        if self.is_hardware:
            theme = theme.hardware
        elif self._box_type == BoxType.CLIENT:
            theme = theme.client
        elif self.is_monitor():
            theme = theme.monitor
        
        return theme
