#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# PatchBay Canvas engine using QGraphicsView/Scene
# Copyright (C) 2010-2019 Filipe Coelho <falktx@falktx.com>
# Copyright (C) 2019-2026 Mathieu Picot <picotmathieu@gmail.com>
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
from typing import Optional

from qtpy.QtCore import Qt, QPointF, QRectF, QTimer, QMarginsF
from qtpy.QtGui import QCursor, QPainterPath, QImage
from qtpy.QtWidgets import QGraphicsItem, QApplication

from patshared import PortMode, BoxLayoutMode, BoxType

from ..init_values import (
    AliasingReason,
    CanvasItemType,
    GroupObject,
    PortObject,
    PortgrpObject,
    InlineDisplay,
    canvas,
    options,
    Direction,
    Zv)
from .. import grid
from ..utils import (
    get_portgroup_name_from_ports_names)
from ..port_widget import PortWidget
from ..portgroup_widget import PortgroupWidget
from ..grouped_lines_widget import GroupedLinesWidget
from ..theme import UslStyleAttributer

from . import box_painters, box_positions
from .box_hidder import BoxHidder
from .box_layout import BoxLayout
from .box_shadow import BoxWidgetShadow
from .box_utils import (
    BoxStyler, PaintElement, TitleLine, UnwrapButton, WrappingState)
from .icon_widget import IconSvgWidget, IconPixmapWidget


_logger = logging.getLogger(__name__)


class BoxWidget(QGraphicsItem):
    def __init__(self, group: GroupObject, port_mode: PortMode):
        canvas.ensure_init()
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
        self._inline_data: bytes | None = None
        self._inline_image: QImage | None = None
        self._inline_scaling = 1.0

        self._icon_name = group.icon_name

        self._title_lines = tuple[TitleLine, ...]()
        self._header_line_left: \
            tuple[float, float, float, float] | None = None
        self._header_line_right: \
            tuple[float, float, float, float] | None = None

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
        match group.box_type:
            case BoxType.HARDWARE | BoxType.MONITOR:
                self.top_icon = IconSvgWidget(
                    group.box_type, group.icon_name, self._port_mode, self)
            case _:
                self.top_icon = IconPixmapWidget(
                group.box_type, group.icon_name, self)
                if self.top_icon.is_null():
                    top_icon = self.top_icon
                    self.top_icon = None
                    del top_icon

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
        self._painter_paths = dict[bool, dict[PaintElement, QPainterPath]]()
        self._layout: BoxLayout | None = None
        self._alter_layout: BoxLayout | None = None

        self.update_positions_pending = False

        self._ex_width = self._width
        self._ex_height = self._height

        self._ex_scene_pos = self.scenePos()
        self._ex_ports_y_segments_dict = dict[str, list[list[float]]]()

        # Shadow
        shadow_theme = self.get_theme(BoxStyler.SHADOW)
        self.shadow = None
        # FIXME FX on top of graphic items make them lose high-dpi
        # See https://bugreports.qt.io/browse/QTBUG-65035
        if (options.show_shadows
                and canvas.scene.get_device_pixel_ratio_f() == 1.0):
            self.shadow = BoxWidgetShadow(self.toGraphicsObject())
            self.shadow.set_fake_parent(self)
            self.shadow.set_theme(shadow_theme)
            self.setGraphicsEffect(self.shadow)

            match port_mode:
                case PortMode.INPUT:
                    self.shadow.setOffset(4, 2)
                case PortMode.OUTPUT:
                    self.shadow.setOffset(-4, 2)
                case PortMode.BOTH:
                    self.shadow.setOffset(0, 2)

        # Final touches
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable
                      | QGraphicsItem.GraphicsItemFlag.ItemIsMovable
                      | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)

        canvas.scene.addItem(self)
        self.setZValue(Zv.NEW_BOX.value)

    def __repr__(self) -> str:
        return f"BoxWidget({self._group_name}, {self._port_mode.name})"

    @property
    def is_hardware(self) -> bool:
        return self._box_type is BoxType.HARDWARE

    @property
    def is_monitor(self):
        return self._box_type is BoxType.MONITOR

    def _get_portgroup_name(self, portgrp_id: int):
        return get_portgroup_name_from_ports_names(
            [p.port_name for p in self._port_list
             if p.portgrp_id == portgrp_id])

    def get_port_mode(self):
        return self._port_mode

    def set_port_mode(self, port_mode: PortMode):
        'Use it only at split/join !!!'
        group = canvas.get_group(self._group_id)
        if group is None:
            _logger.error(
                'set_port_mode impossible, it fails to find its group')
            return

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

    def set_icon(self):
        self.remove_icon_from_scene()

        group = canvas.get_group(self._group_id)
        if group is None:
            return

        box_type = group.box_type
        icon_name = group.icon_name

        if box_type in (BoxType.HARDWARE, BoxType.MONITOR):
            self.top_icon = IconSvgWidget(
                box_type, icon_name, self._port_mode, self)
        else:
            self.top_icon = IconPixmapWidget(box_type, icon_name, self)

    def has_top_icon(self) -> bool:
        if self.top_icon is None:
            return False

        return not self.top_icon.is_null()

    def set_top_icon_pos(self, x: int | float, y: int | float):
        if self.top_icon is None:
            return
        if self.top_icon.is_null():
            return
        self.top_icon.set_pos(x, y)

    def set_optional_gui_state(self, visible: bool):
        self._can_handle_gui = True
        self._gui_visible = visible
        self.update()

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
                    pos + QPointF(self._width, self._height))): #type:ignore
                    # something is wrong in PyQt6 typing doc
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

    def update_ports(self):
        for portgrp in self._portgrp_list:
            if portgrp.widget is not None:
                portgrp.widget.update()

        for port in self._port_list:
            if port.widget is not None:
                port.widget.update()
                if port.hidden_conn_widget is not None:
                    port.hidden_conn_widget.update_line_pos()
                    port.hidden_conn_widget.update()

    def update_positions(self, even_animated=False, without_connections=False,
                         scene_checks=True, theme_change=False,
                         wrap_anim=False):
        box_positions.update_positions(
            self,
            even_animated=even_animated,
            without_connections=without_connections,
            scene_checks=scene_checks,
            theme_change=theme_change,
            wrap_anim=wrap_anim)

    def get_dummy_rect(self) -> QRectF:
        return box_positions.get_dummy_rect(self)

    def get_layout(self,
                   layout_mode: BoxLayoutMode | None =None) -> BoxLayout:
        return box_positions.get_layout(self, layout_mode)

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
            and self._current_layout_mode is BoxLayoutMode.LARGE)

    def wrap_unwrap_at_point(self, scene_pos: QPointF) -> bool:
        '''order a wrap or unwrap on the box if scene_pos is on the
        triangle wrapper'''
        if self._layout is None:
            _logger.error(f"Can not wrap or unwrap {self} now, "
                          "_layout is not set yet")
            return False

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
                canvas.cb.group_wrap(
                    self._group_id, self._port_mode, False)
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
                canvas.cb.group_wrap(
                    self._group_id, self._port_mode, True)
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

                    canvas.cb.group_selected(
                        self._group_id, self._port_mode)
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

        canvas.cb.group_menu_call(self._group_id, self._port_mode)

        canvas.menu_click_pos = QCursor.pos()

    def keyPressEvent(self, event):
        if self._plugin_id >= 0 and event.key() == Qt.Key.Key_Delete:
            event.accept()
            canvas.cb.plugin_remove(self._plugin_id)
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
            canvas.cb.client_show_gui(
                self._group_id, not self._gui_visible)

        if self._plugin_id >= 0:
            event.accept()
            if self._plugin_ui:
                canvas.cb.plugin_show_ui(self._plugin_id)
            else:
                canvas.cb.plugin_edit(self._plugin_id)
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
                xy = grid.nearest_check_others(self.top_left(), self)
                arg_list.append(
                    (self._group_id, self._port_mode, *xy))
            else:
                # many selected boxes, do not auto-adapt the position
                # to other existing boxes (no check_others)
                for box in selected_boxes:
                    xy = grid.nearest(box.top_left())
                    arg_list.append((box._group_id, box._port_mode, *xy))

            canvas.cb.boxes_moved(*arg_list)

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
            new_xy = grid.nearest_check_others(xy, self)
        else:
            new_xy = grid.nearest(xy)

        if xy == new_xy:
            self.set_top_left(xy)
            self.repaint_lines()
        else:
            canvas.scene.add_box_to_animation(self, *new_xy)

    def top_left(self) -> tuple[int, int]:
        return (round(self.sceneBoundingRect().left()),
                round(self.sceneBoundingRect().top()))

    def set_top_left(self, xy: tuple[int, int] | tuple[float, float]):
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

        canvas.cb.group_box_pos_changed(
            self._group_id, self._port_mode, box_pos)
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

    def after_wrap_rect(self) -> QRectF:
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

    def get_theme(self, styler=BoxStyler.BOX) -> UslStyleAttributer:
        match styler:
            case BoxStyler.BOX:
                theme = canvas.theme.box
            case BoxStyler.SHADOW:
                theme = canvas.theme.box_shadow
            case BoxStyler.HEADER:
                theme = canvas.theme.box_header
            case BoxStyler.HEADER_LINE:
                theme = canvas.theme.box_header_line
            case BoxStyler.WRAPPER:
                theme = canvas.theme.box_wrapper
            case BoxStyler.PORTS_BORDER:
                theme = canvas.theme.box_ports_border
            case _:
                raise Exception(f'Invalid styler {styler}')

        match self._box_type:
            case BoxType.HARDWARE:
                return theme.hardware
            case BoxType.MONITOR:
                return theme.monitor
            case BoxType.CLIENT:
                if self._can_handle_gui:
                    return theme.client.with_gui
                return theme.client

        return theme

    def paint(self, painter, option, widget):
        box_painters.paint(self, painter, option, widget)
