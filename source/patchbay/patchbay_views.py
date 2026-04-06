
import logging
from typing import TYPE_CHECKING

from patshared import GroupPos, PortMode, PortTypesViewFlag

from .bases.elements import CanvasOptimizeIt
from .bases.group import Group
from .patchcanvas import patchcanvas

if TYPE_CHECKING:
    from .patchbay_manager import PatchbayManager


_logger = logging.getLogger(__name__)


def change_port_types_view(
        mng: 'PatchbayManager', port_types_view: PortTypesViewFlag,
        force=False):
    if not force and port_types_view is mng.port_types_view:
        return

    ex_ptv = mng.port_types_view
    mng.port_types_view = port_types_view
    _logger.info(
        f"Change Port Types View: {ex_ptv.name} -> {port_types_view.name}")
    # Prevent visual update at each canvas item creation
    # because we may create/remove a lot of ports here

    change_counter = 0

    if len(mng.groups) > 30:
        for group in mng.groups:
            in_outs_ptv = group.ins_ptv | group.outs_ptv

            if in_outs_ptv & port_types_view is not in_outs_ptv & ex_ptv:
                change_counter += 1
                continue

            new_gpos = mng.get_group_position(group.name)
            if group.current_position.needs_redraw(new_gpos):
                change_counter += 1

    if change_counter > 30:
        # Big changes between the current and the next view
        # Strategy is to remove all from canvas and add all what is needed
        # without animation.
        for connection in mng.connections:
            connection.in_canvas = False

        for group in mng.groups:
            group.in_canvas = False
            for portgroup in group.portgroups:
                portgroup.in_canvas = False
            for port in group.ports:
                port.in_canvas = False

        patchcanvas.clear_all()

        with CanvasOptimizeIt(mng):
            for group in mng.groups:
                group.current_position = mng.get_group_position(group.name)
                if (group.outs_ptv | group.ins_ptv) & mng.port_types_view:
                    group.add_to_canvas()
                    group.add_all_ports_to_canvas()

            for connection in mng.connections:
                connection.add_to_canvas()

        patchcanvas.redraw_all_groups()

        mng.sg.port_types_view_changed.emit(mng.port_types_view)
        mng.view().default_port_types_view = mng.port_types_view
        mng.save_view_and_port_types_view()
        return

    rm_all_before = bool(ex_ptv & mng.port_types_view
                            is PortTypesViewFlag.NONE)

    with CanvasOptimizeIt(mng):
        if rm_all_before:
            # there is no common port type between previous and next view,
            # strategy is to remove fastly all contents from the patchcanvas.
            for connection in mng.connections:
                connection.in_canvas = False

            for group in mng.groups:
                group.in_canvas = False
                for portgroup in group.portgroups:
                    portgroup.in_canvas = False
                for port in group.ports:
                    port.in_canvas = False

            patchcanvas.clear_all()

        else:
            for connection in mng.connections:
                connection.remove_from_canvas()

        groups_and_pos = dict[Group, tuple[GroupPos, PortMode, PortMode]]()

        for group in mng.groups:
            new_gpos = mng.get_group_position(group.name)
            in_outs_ptv = group.ins_ptv | group.outs_ptv
            hidden_modes = group.current_position.hidden_port_modes()
            new_hidden_modes = new_gpos.hidden_port_modes()
            redraw_mode = PortMode.NULL

            if (hidden_modes is not new_hidden_modes
                    or mng.port_types_view & in_outs_ptv
                    is not ex_ptv & in_outs_ptv):
                # group needs to be redrawn because visible ports
                # are not the sames.

                if new_hidden_modes is not hidden_modes:
                    # During the animation, we need to see the ports we hide,
                    # so the hidden ports in the new view must be shown.
                    # But, if the ports are hidden in the two views,
                    # we won't show them.
                    for port_mode in PortMode.INPUT, PortMode.OUTPUT:
                        if (not new_hidden_modes & port_mode
                                and hidden_modes & port_mode):
                            redraw_mode |= port_mode

                if (mng.port_types_view & group.ins_ptv
                        is not ex_ptv & group.ins_ptv):
                    redraw_mode |= PortMode.INPUT

                if (mng.port_types_view & group.outs_ptv
                        is not ex_ptv & group.outs_ptv):
                    redraw_mode |= PortMode.OUTPUT

                if not rm_all_before:
                    for portgroup in group.portgroups:
                        if portgroup.port_mode & redraw_mode:
                            portgroup.remove_from_canvas()

                    for port in group.ports:
                        if port.mode & redraw_mode:
                            port.remove_from_canvas()

                if (new_gpos.is_splitted()
                        is not group.current_position.is_splitted()):
                    group.add_to_canvas(gpos=new_gpos)
                else:
                    group.add_to_canvas()

                # only ports which should be hidden in previous and next
                # view will be hidden (before to animate).
                for port in group.ports:
                    port.add_to_canvas(
                        ignore_gpos=True,
                        hidden_sides=hidden_modes & new_hidden_modes)

                for portgroup in group.portgroups:
                    portgroup.add_to_canvas()

            for port in group.ports:
                if port.in_canvas:
                    new_gpos.has_sure_existence = True
                    break
            else:
                group.remove_from_canvas()

            restore_mode = PortMode.NULL
            for pmode in (PortMode.INPUT, PortMode.OUTPUT):
                if (group.current_position.hidden_port_modes() & pmode
                        and not new_gpos.hidden_port_modes() & pmode):
                    restore_mode |= pmode
            groups_and_pos[group] = (new_gpos, redraw_mode, restore_mode)

        for conn in mng.connections:
            conn.add_to_canvas()

    if groups_and_pos:
        patchcanvas.canvas.scene.prevent_box_user_move = True

        for group, gpos_redraw in groups_and_pos.items():
            group.set_group_position(*gpos_redraw)

        patchcanvas.repulse_all_boxes()

    mng.sg.port_types_view_changed.emit(mng.port_types_view)
    mng.view().default_port_types_view = mng.port_types_view
    mng.save_view_and_port_types_view()

def new_view(mng: 'PatchbayManager', view_number: int | None =None,
             exclusive_with: dict[int, PortMode] | None =None):
    '''create a new view and switch directly to this view.

    If `view_number` is not set, it will choose the first available
    number.

    if `exclusive_with` is set, all non matching boxes will be hidden,
    and new view will be a white list view.'''

    new_num = mng.views.add_view(
        view_number, default_ptv=mng.port_types_view)
    if new_num is None:
        _logger.warning(f'failed to create new view n°{view_number}')
        return

    if exclusive_with is None:
        for gpos in mng.views.iter_group_poses(view_num=mng.view_number):
            mng.views.add_group_pos(new_num, gpos.copy())

        if mng.view().is_white_list:
            mng.views[new_num].is_white_list = True

    else:
        mng.views[new_num].is_white_list = True

        v = mng.view().ptvs[mng.port_types_view]
        mng.views[new_num].ptvs[mng.port_types_view] = new_v = {}

        for group_id, port_mode in exclusive_with.items():
            group = mng.get_group_from_id(group_id)
            if group is not None:
                new_v[group.name] = gpos = v[group.name].copy()
                for pmode, box_pos in gpos.boxes.items():
                    if not port_mode & pmode:
                        box_pos.set_hidden(True)

    mng.view().default_port_types_view = mng.port_types_view
    mng.view_number = new_num
    mng.set_views_changed()
    change_port_types_view(mng, mng.port_types_view, force=True)

def rename_current_view(mng: 'PatchbayManager', new_name: str):
    mng.view().name = new_name
    mng.set_views_changed()

def change_view(mng: 'PatchbayManager', view_number: int):
    if not view_number in mng.views.keys():
        mng.new_view(view_number=view_number)
        return

    mng.view_number = view_number
    new_view = mng.views.get(mng.view_number)
    if new_view is None:
        ptv = mng.port_types_view
    else:
        ptv = new_view.default_port_types_view

    change_port_types_view(mng, ptv, force=True)
    mng.sg.view_changed.emit(view_number)

def remove_view(mng: 'PatchbayManager', view_number: int):
    if len(mng.views) <= 1:
        _logger.error(
            f"Will not remove view {view_number}, "
            "to ensure there is at least one view.")
        return

    rm_current_view = bool(view_number is mng.view_number)
    mng.views.remove_view(view_number)

    if rm_current_view:
        switch_to_view = -1
        for view_num in mng.views.keys():
            if view_num < view_number:
                switch_to_view = view_num
            elif switch_to_view == -1:
                switch_to_view = view_num
                break

        mng.change_view(switch_to_view)

    mng.set_views_changed()

def clear_absents_in_view(mng: 'PatchbayManager', only_current_ptv=False):
    if only_current_ptv:
        mng.views.clear_absents(
            mng.view_number, mng.port_types_view,
            set([g.name for g in mng.groups
                    if g.is_in_port_types_view(mng.port_types_view)]))
        return

    for ptv in mng.view().ptvs.keys():
        mng.views.clear_absents(
            mng.view_number, ptv,
            set([g.name for g in mng.groups
                    if g.is_in_port_types_view(ptv)]))

def remove_all_other_views(mng: 'PatchbayManager'):
    view_nums = [n for n in mng.views.keys() if n != mng.view_number]
    for n in view_nums:
        mng.views.remove_view(n)
    mng.set_views_changed()

def change_view_number(mng: 'PatchbayManager', new_num: int):
    if new_num == mng.view_number:
        return

    mng.views.change_view_number(mng.view_number, new_num)
    mng.view_number = new_num
    mng.sg.views_changed.emit()

def write_view_data(
        mng: 'PatchbayManager', view_number: int, name: str | None =None,
        port_types: PortTypesViewFlag | None =None,
        white_list_view=False):
    view_data = mng.views.get(view_number)
    if view_data is None:
        if port_types is None:
            port_types = PortTypesViewFlag.ALL

        mng.views.add_view(view_number, port_types)
        view_data = mng.views[view_number]

    if name is not None:
        view_data.name = name

    if port_types is not None:
        view_data.default_port_types_view = port_types

    view_data.is_white_list = white_list_view

    mng.set_views_changed()
