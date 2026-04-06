
from typing import Iterator, TYPE_CHECKING

from patshared import PortMode

from .bases.elements import CanvasOptimizeIt
from .bases.group import Group
from .patchcanvas import patchcanvas

if TYPE_CHECKING:
    from .patchbay_manager import PatchbayManager


def set_group_hidden_sides(
        mng: 'PatchbayManager', group_id: int, port_mode: PortMode):
    group = mng.get_group_from_id(group_id)
    if group is None:
        return

    group.current_position.set_hidden_port_mode(
        group.current_position.hidden_port_modes() | port_mode)
    group.save_current_position()

    with CanvasOptimizeIt(mng, auto_redraw=True):
        if port_mode & PortMode.OUTPUT:
            for conn in mng.connections:
                if conn.port_out.group_id == group_id:
                    conn.remove_from_canvas()

            for portgroup in group.portgroups:
                if portgroup.port_mode is PortMode.OUTPUT:
                    portgroup.remove_from_canvas()

            for port in group.ports:
                if port.mode is PortMode.OUTPUT:
                    port.remove_from_canvas()

            for conn in mng.connections:
                if conn.port_out.group_id is group_id:
                    conn.add_to_canvas()

        if port_mode & PortMode.INPUT:
            for conn in mng.connections:
                if conn.port_in.group_id == group_id:
                    conn.remove_from_canvas()

            for portgroup in group.portgroups:
                if portgroup.port_mode is PortMode.INPUT:
                    portgroup.remove_from_canvas()

            for port in group.ports:
                if port.mode is PortMode.INPUT:
                    port.remove_from_canvas()

            for conn in mng.connections:
                if conn.port_in.group_id is group_id:
                    conn.add_to_canvas()

    mng.sg.hidden_boxes_changed.emit()

def restore_group_hidden_sides(
        mng: 'PatchbayManager', group_id: int,
        scene_pos: tuple[int, int] | None =None):
    group = mng.get_group_from_id(group_id)
    if group is None:
        return

    gpos = group.current_position
    hidden_port_mode = gpos.hidden_port_modes()
    if hidden_port_mode is PortMode.NULL:
        return

    if scene_pos is not None:
        for port_mode in PortMode.in_out_both():
            if hidden_port_mode & port_mode:
                gpos.boxes[port_mode].pos = scene_pos

    gpos.set_hidden_port_mode(PortMode.NULL)
    group.save_current_position()

    with CanvasOptimizeIt(mng):
        group.add_to_canvas()
        group.add_all_ports_to_canvas()

        for conn in mng.connections:
            if conn.port_out.group is group or conn.port_in.group is group:
                conn.add_to_canvas()

    patchcanvas.move_group_boxes(
        group.group_id, gpos,
        redraw=hidden_port_mode, restore=hidden_port_mode)
    patchcanvas.repulse_from_group(group.group_id, hidden_port_mode)

    mng.sg.hidden_boxes_changed.emit()

def restore_all_group_hidden_sides(mng: 'PatchbayManager'):
    groups_to_restore = set[Group]()

    with CanvasOptimizeIt(mng):
        for group in mng.groups:
            if group.current_position.hidden_port_modes():
                group.current_position.set_hidden_port_mode(PortMode.NULL)
                if not group.current_position.fully_set:
                    if group._is_hardware:
                        group.current_position.set_splitted(True)

                group.add_to_canvas()
                group.add_all_ports_to_canvas()
                groups_to_restore.add(group)

        # forget all hidden boxes even if these boxes are not
        # currently present in the patchbay.
        for gpos in mng.views.iter_group_poses(view_num=mng.view_number):
            gpos.set_hidden_port_mode(PortMode.NULL)

        for conn in mng.connections:
            conn.add_to_canvas()

    for group in groups_to_restore:
        patchcanvas.move_group_boxes(
            group.group_id, group.current_position,
            redraw=PortMode.BOTH, restore=PortMode.BOTH)
        patchcanvas.repulse_from_group(group.group_id, PortMode.BOTH)

    mng.sg.hidden_boxes_changed.emit()

def hide_all_groups(mng: 'PatchbayManager'):
    groups_to_hide = set[Group]()

    with CanvasOptimizeIt(mng):
        for group in mng.groups:
            if (group.current_position.hidden_port_modes()
                    is not PortMode.BOTH):
                groups_to_hide.add(group)
                group.current_position.set_hidden_port_mode(PortMode.BOTH)

        for conn in mng.connections:
            conn.remove_from_canvas()

        for group in groups_to_hide:
            for portgroup in group.portgroups:
                portgroup.remove_from_canvas()

            for port in group.ports:
                port.remove_from_canvas()

    for group in groups_to_hide:
        patchcanvas.move_group_boxes(
            group.group_id, group.current_position,
            redraw=PortMode.BOTH)

    mng.sg.hidden_boxes_changed.emit()

def list_hidden_groups(mng: 'PatchbayManager') -> Iterator[Group]:
    for group in mng.groups:
        if (group.current_position.hidden_port_modes()
                is not PortMode.NULL):
            yield group
