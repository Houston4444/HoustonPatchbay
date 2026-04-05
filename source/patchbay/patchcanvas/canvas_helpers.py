
import logging

from qtpy.QtCore import QPointF, QRectF, QTimer

from patshared import GroupPos, PortMode

from .init_values import canvas, options, Joining
from . import grid
from .box_widget import BoxWidget
from .api_log import LogStr

_logger = logging.getLogger(__name__)


def split_group(group_id: int, on_place=False, redraw=True):
    '''Split inputs and outputs in two box widgets.

    on_place: the new boxes will have a pos near from the existing one

    redraw: draw the box, quite long operation. Needed for 'on_place'
    to be effective.'''
    canvas.ensure_init()

    group = canvas.get_group(group_id)
    if group is None:
        _logger.error(f"{LogStr.func_args} - unable to find group to split")
        return

    if group.splitted:
        _logger.error(
            f"{LogStr.func_args} - group is already splitted")
        return

    if not group.widgets:
        _logger.error(
            f"{LogStr.func_args} - group has no box widget to split")
        return

    box = group.widgets[0]
    wrap = box.is_wrapped
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
            if box.current_port_mode is PortMode.OUTPUT:
                group.gpos.boxes[PortMode.OUTPUT].pos = (
                    grid.previous_left(
                        int(ex_rect.right() + (full_width - ex_rect.width()) / 2
                            - box.boundingRect().width())),
                    grid.previous_top(
                        int(ex_rect.y()))
                )
            else:
                group.gpos.boxes[PortMode.INPUT].pos = (
                    grid.previous_left(
                        int(ex_rect.left() - (full_width - ex_rect.width()) / 2)),
                    grid.previous_top(int(ex_rect.y()))
                )

        move_group_boxes(group_id, group.gpos)
        canvas.scene.deplace_boxes_from_repulsers(
            [b for b in group.widgets if b.isVisible()])

    QTimer.singleShot(0, canvas.scene.update)

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
            if box.port_mode is not port_mode:
                continue

            if box._layout_mode is not box_pos.layout_mode:
                box.set_layout_mode(box_pos.layout_mode)
                redraw |= port_mode

            if box.is_hidding_or_restore and not box_pos.is_hidden():
                redraw |= port_mode

            if join:
                wanted_wrap = gpos.boxes[PortMode.BOTH].is_wrapped()
            else:
                wanted_wrap = box_pos.is_wrapped()

            if box.is_wrapped is not wanted_wrap:
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

            xy = grid.nearest(box_pos.pos)

            if box_pos.is_hidden():
                if box.isVisible():
                    canvas.scene.add_box_to_animation_hidding(box)

            elif restore & port_mode:
                if join:
                    canvas.scene.add_box_to_animation_restore(box)

                    both_pos = grid.nearest(gpos.boxes[PortMode.BOTH].pos)

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
                    both_pos = grid.nearest(gpos.boxes[PortMode.BOTH].pos)

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

def repulse_all_boxes():
    canvas.ensure_init()
    if options.prevent_overlap:
        canvas.scene.full_repulse()