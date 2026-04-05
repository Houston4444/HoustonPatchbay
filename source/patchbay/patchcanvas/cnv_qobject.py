import logging
import time

from qtpy.QtCore import Signal, Slot, QTimer, QObject # type:ignore

from patshared import PortMode

from .init_values import AliasingReason, canvas
from .grouped_lines_widget import GroupedLinesWidget


_logger = logging.getLogger(__name__)


def _join_group(group_id: int):
    '''join group boxes once animation is finished'''
    group = canvas.get_group(group_id)
    if group is None:
        _logger.error(
            f"join_group({group_id}) - unable to find groups to join")
        return

    if not group.splitted:
        _logger.error(f"join_group({group_id}) - group is not splitted")
        return

    wrap = True
    for box in group.widgets:
        wrap = wrap and box.is_wrapped

    eater, eaten = group.widgets

    for portgroup in canvas.list_portgroups(group_id=group_id):
        if (portgroup.port_mode is eaten.port_mode
                and portgroup.widget is not None):
            portgroup.widget.setParentItem(eater)

    for port in canvas.list_ports(group_id=group_id):
        if (port.port_mode is eaten.port_mode
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


class CanvasObject(QObject):
    move_boxes_finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
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
            _join_group(group_id)

        self._gps_to_join.clear()
        canvas.cb.animation_finished()

    def add_group_to_join(self, group_id: int):
        self._gps_to_join.add(group_id)

    def rm_group_to_join(self, group_id: int):
        self._gps_to_join.discard(group_id)

    def rm_all_groups_to_join(self):
        self._gps_to_join.clear()
