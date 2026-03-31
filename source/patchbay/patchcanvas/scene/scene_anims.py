import time
from typing import TYPE_CHECKING

from qtpy.QtCore import QPointF, QRectF

from patshared import PortMode

from ..box_widget import BoxWidget
from ..grouped_lines_widget import GroupedLinesWidget
from ..init_values import canvas, AliasingReason, BoxHidding, Joining

from .scene_utils import MovingBox

if TYPE_CHECKING:
    from .scene import PatchScene


def move_boxes_animation(scene: 'PatchScene'):
    # Animation is nice but not the priority.
    # Do not ensure all steps are played
    # but just move the box where it has to go now.
    move_time = time.time()
    time_since_start = move_time - scene._move_timer_start_at
    ratio = min(1.0, time_since_start / scene._MOVE_DURATION)

    if scene._move_timer_last_time == scene._move_timer_start_at:
        # this is the first animation step
        if time_since_start > 0.33 * scene._MOVE_DURATION:
            # this seems to be a big patch,
            # animation won't be pretty anyway,
            # let's finish it now.
            ratio = 1.0
    else:
        # this is not the first animation step.
        # If the timer called this method two times too late,
        # i.e. >40ms instead of 20ms after the previous step,
        # anti-aliasing is de-activated for a smoother animation.
        if (move_time - scene._move_timer_last_time
                > 0.002 * scene._MOVE_TIMER_INTERVAL):
            canvas.set_aliasing_reason(AliasingReason.ANIMATION, True)

    scene._move_timer_last_time = move_time

    lws = set[GroupedLinesWidget]()

    usefull = False

    for box, moving_box in scene.move_boxes.items():
        if not usefull:
            usefull = moving_box.is_usefull()

        if moving_box.needs_move:
            x = (moving_box.from_pt.x()
                    + ((moving_box.to_pt.x() - moving_box.from_pt.x())
                    * (ratio ** 0.6)))

            y = (moving_box.from_pt.y()
                    + ((moving_box.to_pt.y() - moving_box.from_pt.y())
                    * (ratio ** 0.6)))

            box.set_top_left((x, y))
            box.repaint_lines(fast_move=True)

        if moving_box.is_wrapping:
            box.animate_wrapping(ratio)

        if moving_box.hidding_state in (BoxHidding.HIDDING,
                                        BoxHidding.RESTORING):
            if moving_box.hidding_state is BoxHidding.HIDDING:
                box.animate_hidding(ratio)
            else:
                box.animate_restoring(ratio)

            for lw in GroupedLinesWidget.widgets_for_box(
                    box._group_id, box._port_mode):
                if lw not in lws:
                    lw.animate_hidding(ratio)
                    lws.add(lw)

    if not usefull:
        # stop animation now if all moving boxes have no change to make
        ratio = 1.0

    scene.resize_the_scene(ratio)

    if ratio >= 1.0:
        # Animation is finished
        scene._move_box_timer.stop()
        canvas.set_aliasing_reason(AliasingReason.ANIMATION, False)
        scene.prevent_box_user_move = False
        GroupedLinesWidget.animation_finished()

        # box update positions is forbidden while widget is in self.move_boxes,
        # so we copy the list before to clear it,
        # then we can ask update_positions on widgets
        boxes = [b for b, mb in scene.move_boxes.items()
                    if not (mb.is_joining or mb.hidding_state is BoxHidding.HIDDING)]

        scene.move_boxes.clear()

        for box in boxes:
            if box.update_positions_pending:
                box.update_positions()

        canvas.qobject.move_boxes_finished.emit()

def add_box_to_animation(
        scene: 'PatchScene', box_widget: BoxWidget, to_x: int, to_y: int,
        joining=Joining.NO_CHANGE, joined_rect=QRectF()):
    '''add a box to the move animation, to_x and to_y refer
    to the top left of the box at the end of animation.
    if joining is set to Joining.YES, joined_rect must be set'''

    moving_box = scene.move_boxes.get(box_widget)
    if moving_box is None:
        # box is not already moving, create a MovingBox instance
        moving_box = MovingBox(box_widget)
        if joining is Joining.YES:
            moving_box.is_joining = True
        scene.move_boxes[box_widget] = moving_box
    else:
        # box is already moving, check joining state and change it
        # if needed.
        if moving_box.is_joining and joining is Joining.NO:
            moving_box.is_joining = False
            canvas.qobject.rm_group_to_join(box_widget._group_id)

    moving_box.from_pt = QPointF(*box_widget.top_left())
    moving_box.to_pt = QPointF(to_x, to_y)
    moving_box.needs_move = bool(moving_box.from_pt != moving_box.to_pt)

    if joining is Joining.YES or not box_widget.isVisible():
        moving_box.final_rect = joined_rect

    elif joining is Joining.NO_CHANGE and moving_box.is_joining:
        final_rect = QRectF(
            0.0, 0.0,
            moving_box.final_rect.width(),
            moving_box.final_rect.height())
        final_rect.translate(moving_box.to_pt)
        moving_box.final_rect = final_rect

    elif not moving_box.is_joining:
        aft_wrap_rect = box_widget.after_wrap_rect()
        final_rect = QRectF(
            0.0, 0.0, aft_wrap_rect.width(), aft_wrap_rect.height())
        final_rect.translate(moving_box.to_pt)
        moving_box.final_rect = final_rect

    else:
        # can not happens
        # would means moving_box.is_joining and joining is JOINING.NO,
        # It is prevented
        moving_box.final_rect = joined_rect

    if joining is not Joining.NO_CHANGE:
        moving_box.is_joining = True if joining is Joining.YES else False

    # save the group position
    group = canvas.get_group(box_widget._group_id)
    if group is not None:
        if moving_box.is_joining:
            if not joined_rect.isNull():
                group.gpos.boxes[PortMode.BOTH].pos = (to_x, to_y)
        else:
            group.gpos.boxes[box_widget._port_mode].pos = (to_x, to_y)
        canvas.cb.group_pos_modified(group.group_id)

    moving_box.start_time = time.time() - scene._move_timer_start_at

    if not scene._move_box_timer.isActive():
        moving_box.start_time = 0.0

    scene._start_move_timer()

    if canvas.aliasing_reason:
        # if antialiasing is already prevented
        # we need to keep it prevented at animation start
        canvas.set_aliasing_reason(AliasingReason.ANIMATION, True)

def remove_box_from_animation(scene: 'PatchScene', box_widget: BoxWidget):
    if scene.prevent_box_user_move:
        # should not happens.
        # For now we can remove a box from animation
        # only by moving box manually,
        # and this is prevented by this attr in box_widget_moth.
        return

    if box_widget in scene.move_boxes:
        scene.move_boxes.pop(box_widget)

def add_box_to_animation_wrapping(
        scene: 'PatchScene', box_widget: BoxWidget, wrap: bool):
    moving_box = scene.move_boxes.get(box_widget)
    if moving_box is None:
        moving_box = MovingBox(box_widget)
        scene.move_boxes[box_widget] = moving_box

    moving_box.start_time = time.time() - scene._move_timer_start_at

    aft_wrap_rect = box_widget.after_wrap_rect()
    final_rect = QRectF(0.0, 0.0, aft_wrap_rect.width(), aft_wrap_rect.height())
    moving_box.final_rect = \
        final_rect.translated(moving_box.to_pt)
    moving_box.is_wrapping = True

    scene._start_move_timer()

def add_box_to_animation_hidding(scene: 'PatchScene', box_widget: BoxWidget):
    moving_box = scene.move_boxes.get(box_widget)
    if moving_box is None:
        moving_box = MovingBox(box_widget)
        scene.move_boxes[box_widget] = moving_box

    moving_box.start_time = time.time() - scene._move_timer_start_at
    moving_box.final_rect = QRectF()
    moving_box.hidding_state = BoxHidding.HIDDING

    for port_mode in PortMode.OUTPUT, PortMode.INPUT:
        if port_mode not in box_widget.get_port_mode():
            continue

        for lw in GroupedLinesWidget.widgets_for_box(
                box_widget._group_id, port_mode):
            lw.set_mode_hidding(port_mode, BoxHidding.HIDDING)

    scene._start_move_timer()

def add_box_to_animation_restore(scene: 'PatchScene', box_widget: BoxWidget):
    moving_box = scene.move_boxes.get(box_widget)
    if moving_box is None:
        moving_box = MovingBox(box_widget)
        scene.move_boxes[box_widget] = moving_box

    moving_box.start_time = time.time() - scene._move_timer_start_at
    moving_box.from_pt = moving_box.to_pt

    aft_wrap_rect = box_widget.after_wrap_rect()
    final_rect = QRectF(
        0.0, 0.0, aft_wrap_rect.width(), aft_wrap_rect.height())
    moving_box.final_rect = \
        final_rect.translated(moving_box.to_pt)

    if moving_box.hidding_state is BoxHidding.NONE:
        box_widget.animate_restoring(0.0)
    moving_box.hidding_state = BoxHidding.RESTORING

    for port_mode in PortMode.OUTPUT, PortMode.INPUT:
        if port_mode not in box_widget._port_mode:
            continue

        for lw in GroupedLinesWidget.widgets_for_box(
                box_widget._group_id, port_mode):
            lw.set_mode_hidding(port_mode, BoxHidding.RESTORING)

    scene._start_move_timer()
