
import time
from typing import TYPE_CHECKING, Optional
from qtpy.QtCore import Qt, QPointF
from qtpy.QtGui import QCursor
from qtpy.QtWidgets import QGraphicsItem

from patshared import PortMode, PortType, PortSubType

from .init_values import (
    AliasingReason,
    ConnectableObject,
    ConnectionObject,
    canvas,
    options)
from .line_move_widget import LineMoveWidget
from .grouped_lines_widget import GroupedLinesWidget, GroupOutInsDict

if TYPE_CHECKING:
    from .box_widget import BoxWidget


class ConnectableWidget(QGraphicsItem):
    """This class is the mother class for port and portgroups
    widgets because the way to manage the connection process
    is the same for both."""

    if TYPE_CHECKING:
        _hover_item: Optional['ConnectableWidget']

    def __init__(self, connectable: ConnectableObject, parent: 'BoxWidget'):
        canvas.ensure_init()
        QGraphicsItem.__init__(self, parent)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)

        if options.auto_select_items:
            self.setAcceptHoverEvents(True)

        self._po = connectable

        # needed for line mov
        self._line_mov_list = list[LineMoveWidget]()
        self._dotcon_list = list[ConnectionObject]()
        self._last_rclick_item = None
        self._r_click_time = 0
        self._hover_item = None
        self._mouse_down = False
        self._cursor_moving = False
        self._has_connections = False

        self._last_mouse_point = QPointF(0.0, 0.0)

        # needed for selecting portgroup and ports together
        self.mouse_releasing = False
        self.changing_select_state = False

    @property
    def group_id(self) -> int:
        return self._po.group_id
    
    @property
    def port_ids(self) -> tuple[int, ...]:
        return self._po.get_port_ids()
    
    @property
    def port_mode(self) -> PortMode:
        return self._po.port_mode
    
    @property
    def port_type(self) -> PortType:
        return self._po.port_type
    
    @property
    def port_subtype(self) -> PortSubType:
        return self._po.port_subtype

    def get_connection_distance(self) -> float:
        # overclassed
        return 0.0

    def trigger_disconnect(self):
        " used to disconnect ports/portgroups from Ctrl+Middle Click "
        conn_ids_to_remove = list[int]()

        for connection in canvas.list_connections(self._po):
            conn_ids_to_remove.append(connection.connection_id)

        for conn_id in conn_ids_to_remove:
            canvas.cb.ports_disconnect(conn_id)

    def is_connectable_to(self, other: 'ConnectableWidget',
                          accept_same_port_mode=False)->bool:
        if self.port_type is not other.port_type:
            return False

        if not accept_same_port_mode:
            if self.port_mode is other.port_mode:
                return False

        if self.port_type is PortType.AUDIO_JACK:
            if other.port_mode is self.port_mode:
                return self.port_subtype is other.port_subtype
            # absolutely forbidden to connect an output CV port
            # to an input audio port.
            # It could destroy material.
            if self.port_mode is PortMode.OUTPUT:
                if self.port_subtype is PortSubType.CV:
                    return other.port_subtype is PortSubType.CV
                return True

            if self.port_mode is PortMode.INPUT:
                if self.port_subtype is PortSubType.CV:
                    return True
                return not (other.port_subtype is PortSubType.CV)

        return True

    def reset_line_mov_positions(self):
        self_ports_len = len(self.port_ids)

        for i, line_mov in enumerate(self._line_mov_list):
            if i < self_ports_len:
                line_mov.set_destination_portgrp_pos(i, self_ports_len)
            else:
                item = line_mov
                canvas.scene.removeItem(item)
                del item

        while len(self._line_mov_list) < self_ports_len:
            line_mov = LineMoveWidget(
                self.port_mode, self.port_type, len(self._line_mov_list),
                self_ports_len, self)

            self._line_mov_list.append(line_mov)

        self._line_mov_list = self._line_mov_list[:self_ports_len]

    def reset_dot_lines(self):
        gp_outs_ins = dict[int, set[int]]()

        for connection in self._dotcon_list:
            if connection.ready_to_disc:
                connection.ready_to_disc = False

                ins_set = gp_outs_ins.get(connection.group_out_id)
                if ins_set is None:
                    ins_set = set()
                    gp_outs_ins[connection.group_out_id] = ins_set
                ins_set.add(connection.group_in_id)

        for group_out_id, group_in_ids in gp_outs_ins.items():
            for group_in_id in group_in_ids:
                GroupedLinesWidget.connections_changed(
                    group_out_id, group_in_id)

        for line_mov in self._line_mov_list:
            line_mov.ready_to_disc = False
        self._dotcon_list.clear()

    def _connect_to_hover(self):
        if self._hover_item is None:
            return

        hover_port_ids = self._hover_item.port_ids
        if not hover_port_ids:
            return

        hover_group_id = self._hover_item.group_id
        con_list = list[ConnectionObject]()
        ports_connected_list = list[list[int]]()

        maxportgrp = max(len(self.port_ids), len(hover_port_ids))

        if self._hover_item.port_mode is self.port_mode:
            # Copy connections from this widget to the other one (hover)

            for i, port_id in enumerate(self.port_ids):
                for connection in [
                        c for c in canvas.list_connections(self._po)
                        if c.concerns(self.group_id, set([port_id]))]:
                    canvas.cb.ports_disconnect(
                        connection.connection_id)

                    for j, hover_port_id in enumerate(hover_port_ids):
                        if len(hover_port_ids) >= len(self.port_ids):
                            if j % len(self.port_ids) != i:
                                continue
                        else:
                            if i % len(hover_port_ids) != j:
                                continue

                        if self.port_mode is PortMode.OUTPUT:
                            canvas.cb.ports_connect(
                                hover_group_id, hover_port_id,
                                connection.group_in_id, connection.port_in_id)
                        else:
                            canvas.cb.ports_connect(
                                connection.group_out_id, connection.port_out_id,
                                hover_group_id, hover_port_id)
            return

        for i, port_id in enumerate(self.port_ids):
            for j, hover_port_id in enumerate(hover_port_ids):
                for connection in canvas.list_connections(self._po):
                    if connection.matches(self.group_id, [port_id],
                                          hover_group_id, [hover_port_id]):
                        if i % len(hover_port_ids) == j % len(self.port_ids):
                            con_list.append(connection)
                            ports_connected_list.append(
                                [port_id, hover_port_id])
                        else:
                            canvas.cb.ports_disconnect(
                                connection.connection_id)

        if len(con_list) == maxportgrp:
            for connection in con_list:
                canvas.cb.ports_disconnect(
                    connection.connection_id)
        else:
            for i, port_id in enumerate(self.port_ids):
                for j, hover_port_id in enumerate(hover_port_ids):
                    if i % len(hover_port_ids) == j % len(self.port_ids):
                        if not [port_id, hover_port_id] in ports_connected_list:
                            if self.port_mode is PortMode.OUTPUT:
                                canvas.cb.ports_connect(
                                    self.group_id, port_id,
                                    hover_group_id, hover_port_id)
                            else:
                                canvas.cb.ports_connect(
                                    hover_group_id, hover_port_id,
                                    self.group_id, port_id)

    def parentItem(self) -> 'BoxWidget':
        # only here to say IDE parent is a BoxWidget
        return super().parentItem() # type:ignore

    def hoverEnterEvent(self, event):
        if options.auto_select_items:
            self.setSelected(True)
        QGraphicsItem.hoverEnterEvent(self, event)

    def hoverLeaveEvent(self, event):
        if options.auto_select_items:
            self.setSelected(False)
        QGraphicsItem.hoverLeaveEvent(self, event)

    def mousePressEvent(self, event):
        if canvas.scene.get_zoom_scale() <= 0.4:
            # prefer move box if zoom is too low
            event.ignore()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            self._hover_item = None
            self._mouse_down = True
            self._cursor_moving = False

            for connection in canvas.list_connections(self._po):
                self._has_connections = True
                break
            else:
                self._has_connections = False

        elif event.button() == Qt.MouseButton.RightButton:
            if canvas.is_line_mov:
                if self._hover_item:
                    self._r_click_time = time.time()
                    self._connect_to_hover()
                    self._last_rclick_item = self._hover_item

                    for line_mov in self._line_mov_list:
                        line_mov.ready_to_disc = not line_mov.ready_to_disc
                        line_mov.update_line_pos(event.scenePos())

                    gp_out_ins = GroupOutInsDict()
                    for connection in self._dotcon_list:
                        if connection in canvas.list_connections(self._po):
                            connection.ready_to_disc = True
                            gp_out_ins.add_group_ids(
                                connection.group_out_id, connection.group_in_id)

                    gp_out_ins.send_changes()

                else:
                    box_under = canvas.scene.get_box_at(event.scenePos())
                    if box_under is not None and box_under is not self.parentItem():
                        box_under.wrap_unwrap_at_point(event.scenePos())

        QGraphicsItem.mousePressEvent(self, event)

    def mouseMoveEvent(self, event):
        if (not event.buttons() & Qt.MouseButton.LeftButton
                and canvas.scene.flying_connectable is not self):
            QGraphicsItem.mouseMoveEvent(self, event)
            return

        if not self._cursor_moving:
            canvas.scene.set_cursor(QCursor(Qt.CursorShape.CrossCursor))
            self._cursor_moving = True

        if not self._line_mov_list:
            self._last_rclick_item = None

            for i in range(len(self.port_ids)):
                line_mov = LineMoveWidget(
                    self.port_mode, self.port_type, i,
                    len(self.port_ids), self)

                self._line_mov_list.append(line_mov)

            canvas.is_line_mov = True

        item = canvas.scene.get_connectable_item_at(event.scenePos(), self)

        if self._hover_item is not None and item is not self._hover_item:
            self._hover_item.setSelected(False)

        # if item has same port mode
        # verify we can use it for cut and paste connections
        if (item is not None
                and item.port_type is self.port_type
                and item.port_mode is self.port_mode):
            item_valid = False

            if (self._has_connections
                    and len(item.port_ids) == len(self.port_ids)):
                for connection in canvas.list_connections(
                        group_id=item.group_id):
                    if connection.concerns(
                            item.group_id, set(item.port_ids)):
                        break
                else:
                    item_valid = True

            if not item_valid:
                item = None

        if (item is not None
                and not self.is_connectable_to(
                    item, accept_same_port_mode=True)):
            # prevent connection from an out CV port to a non CV port input
            # because it is very dangerous for monitoring
            pass

        elif (item is not None
              and item is not self._hover_item
              and item.port_type is self.port_type):
            item.setSelected(True)

            if item is self._hover_item:
                # prevent unneeded operations
                pass

            else:
                self._hover_item = item
                hover_len = len(item.port_ids)
                self.reset_dot_lines()
                self.reset_line_mov_positions()

                if item.port_mode is self.port_mode:
                    gp_out_ins = GroupOutInsDict()

                    for connection in canvas.list_connections(self._po):
                        connection.ready_to_disc = True
                        self._dotcon_list.append(connection)
                        gp_out_ins.add_group_ids(
                            connection.group_out_id, connection.group_in_id)

                    gp_out_ins.send_changes()

                    for line_mov in self._line_mov_list:
                        line_mov.ready_to_disc = True
                else:
                    if hover_len <= len(self._line_mov_list):
                        for i, line_mov in enumerate(self._line_mov_list):
                            line_mov.set_destination_portgrp_pos(
                                i % hover_len, hover_len)
                    else:
                        start_n_linemov = len(self._line_mov_list)

                        for i in range(hover_len):
                            if i < start_n_linemov:
                                line_mov = self._line_mov_list[i]
                                line_mov.set_destination_portgrp_pos(
                                    i, hover_len)
                            else:
                                port_posinportgrp = i % len(self.port_ids)
                                line_mov  = LineMoveWidget(
                                    self.port_mode,
                                    self.port_type,
                                    port_posinportgrp,
                                    hover_len,
                                    self)

                                line_mov.set_destination_portgrp_pos(
                                    i, hover_len)
                                self._line_mov_list.append(line_mov)

                    self._dotcon_list.clear()
                    symetric_con_list = []
                    gp_out_ins = GroupOutInsDict()

                    for portself_id in self.port_ids:
                        for porthover_id in self._hover_item.port_ids:
                            for connection in canvas.list_connections(
                                    group_id=self.group_id):
                                if connection.matches(
                                        self.group_id, [portself_id],
                                        self._hover_item.group_id,
                                        [porthover_id]):
                                    if (self.port_ids.index(portself_id)
                                        % hover_len
                                            == (self._hover_item.port_ids.index(porthover_id)
                                                % len(self.port_ids))):
                                        self._dotcon_list.append(connection)
                                        symetric_con_list.append(connection)
                                    else:
                                        self._dotcon_list.append(connection)
                                        connection.ready_to_disc = True
                                        gp_out_ins.add_group_ids(
                                            connection.group_out_id,
                                            connection.group_in_id)

                    gp_out_ins.send_changes()

                    biggest_list = (self.port_ids if len(self.port_ids) >= hover_len
                                    else self._hover_item.port_ids)

                    if len(symetric_con_list) == len(biggest_list):
                        gp_out_ins = GroupOutInsDict()

                        for connection in self._dotcon_list:
                            connection.ready_to_disc = True
                            gp_out_ins.add_group_ids(
                                connection.group_out_id, connection.group_in_id)

                        gp_out_ins.send_changes()

                        for line_mov in self._line_mov_list:
                            line_mov.ready_to_disc = True
        else:
            if item is not self._hover_item:
                self._hover_item = None
                self._last_rclick_item = None
                self.reset_dot_lines()
                self.reset_line_mov_positions()

        for line_mov in self._line_mov_list:
            line_mov.update_line_pos(event.scenePos())

        QGraphicsItem.mouseMoveEvent(self, event)

        canvas.qobject.start_aliasing_check(AliasingReason.USER_MOVE)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._mouse_down or canvas.scene.flying_connectable is self:
                for line_mov in self._line_mov_list:
                    item = line_mov
                    canvas.scene.removeItem(item)
                    del item
                self._line_mov_list.clear()

                if self._hover_item:
                    if (self._last_rclick_item is not self._hover_item
                            and time.time() > self._r_click_time + 0.3):
                        self._connect_to_hover()
                    canvas.scene.clearSelection()

                elif self._last_rclick_item:
                    canvas.scene.clearSelection()

            if self._cursor_moving:
                canvas.scene.set_cursor(QCursor(Qt.CursorShape.ArrowCursor))

            self._hover_item = None
            self._mouse_down = False
            self._cursor_moving = False
            canvas.is_line_mov = False

        canvas.set_aliasing_reason(AliasingReason.USER_MOVE, False)

        self.mouse_releasing = True
        QGraphicsItem.mouseReleaseEvent(self, event)
        self.mouse_releasing = False