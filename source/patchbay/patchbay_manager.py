import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Callable, Iterator, Optional, Union
from queue import Queue

from qtpy.QtGui import QCursor, QGuiApplication, QKeyEvent
from qtpy.QtWidgets import QMainWindow, QMessageBox, QWidget
from qtpy.QtCore import QTimer, QSettings, QThread, Qt
from patchbay.pretty_diff_checker import PrettyDiffChecker

from patshared import (
    PortType, PortSubType, PortMode, JackMetadata, JackMetadatas,
    PortTypesViewFlag, GroupPos, Naming, TransportPosition,
    ViewsDictEnsureOne, ViewData, PortgroupsDict, PortgroupMem, CustomNames)

from .patchcanvas import arranger, patchcanvas
from .patchcanvas.utils import get_new_group_positions
from .patchcanvas.scene_view import PatchGraphicsView
from .patchcanvas.init_values import (
    AliasingReason, CanvasFeaturesObject, CanvasOptionsObject)

from .cancel_mng import CancelMng, CancelOp, CancellableAction
from .patchbay_signals import SignalsObject
from .tools_widgets import PatchbayToolsWidget
from .menus.canvas_menu import CanvasMenu
from .dialogs.options_dialog import CanvasOptionsDialog
from .widgets.filter_frame import FilterFrame
from .bases.elements import (
    JackPortFlag, ToolDisplayed, CanvasOptimizeIt, CanvasOptimize)
from .bases.group import Group
from .bases.connection import Connection
from .bases.port import Port
from .bases.portgroup import Portgroup
from .conns_clipboard import ConnClipboard
from .calbacker import Callbacker
from .patchichi_export import export_to_patchichi_json


_translate = QGuiApplication.translate
_logger = logging.getLogger(__name__)


def enum_to_flag(enum_int: int) -> int:
    if enum_int <= 0:
        return 0
    return 2 ** (enum_int - 1)


@dataclass
class DelayedOrder:
    func: Callable
    args: tuple
    kwargs: dict
    draw_group: bool
    sort_group: bool
    clear_conns: bool
    metadata_change: bool

    
def later_by_batch(draw_group=False, sort_group=False,
                   clear_conns=False, metadata_change=False):
    '''This decorator indicates that the decorated method will be executed
    later by batch in the main thread when `_delayed_orders_timer` will
    call it.'''

    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            mng: PatchbayManager = args[0]
            if mng.very_fast_operation:
                return func(*args, **kwargs)

            mng.delayed_orders.put(
                DelayedOrder(func, args, kwargs,
                             draw_group or sort_group,
                             sort_group,
                             clear_conns,
                             metadata_change))

            if QThread.currentThread() is QGuiApplication.instance().thread():
                mng._delayed_orders_timer.start()
            else:
                mng.sg.out_thread_order.emit()
            return
        return wrapper
    return decorator


def in_main_thread():
    '''This decorator indicates that the decorated method will be executed
    directly if called in the main thread, otherwise as soon as possible
    in the main thread.'''
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            mng: PatchbayManager = args[0]
            
            if QThread.currentThread() is QGuiApplication.instance().thread():
                return func(*args, **kwargs)
            
            mng.sg.to_main_thread.emit(func, args, kwargs)
        return wrapper
    return decorator


class PatchbayManager:
    naming = Naming.ALL
    port_types_view = PortTypesViewFlag.ALL

    canvas_optimize = CanvasOptimize.NORMAL

    groups = list[Group]()
    connections = list[Connection]()
    _groups_by_name = dict[str, Group]()
    _groups_by_id = dict[int, Group]()
    _ports_by_name = dict[str, Port]()
    _ports_by_uuid = dict[int, Port]()

    view_number = 1
    views = ViewsDictEnsureOne()
    
    portgroups_memory = PortgroupsDict()
    custom_names = CustomNames()
    
    delayed_orders = Queue[DelayedOrder]()
    
    jack_metadatas = JackMetadatas()

    def __init__(self, settings: QSettings):
        self.callbacker = Callbacker(self)
        self.cancel_mng = CancelMng(self)
        self._settings = settings

        self.main_win: Optional[QMainWindow] = None
        self._tools_widget: Optional[PatchbayToolsWidget] = None
        self.options_dialog: Optional[CanvasOptionsDialog] = None
        self.filter_frame: Optional[FilterFrame] = None
        
        self._manual_path: Optional[Path] = None

        self.connections_clipboard = ConnClipboard(self)

        self.server_is_started = True

        self.sg = SignalsObject()

        self._next_group_id = 0
        self._next_port_id = 0
        self._next_connection_id = 0
        self._next_portgroup_id = 1
        
        self.client_uuids = dict[str, int]()
        '''Stock JACK client names and their uuid,
        uuid can be provided before the group creation.'''

        self.jack_export_naming = Naming.CUSTOM
        self.naming = Naming.from_config_str(settings.value(
            'Canvas/naming', 'ALL', type=str))
        self.pretty_diff_checker = PrettyDiffChecker(self)

        self.group_a2j_hw: bool = settings.value(
            'Canvas/group_a2j_ports', True, type=bool)
        self.alsa_midi_enabled: bool = settings.value(
            'Canvas/alsa_midi_enabled', False, type=bool)

        # all patchbay events are delayed
        # to reduce the patchbay comsumption.
        # Redraws in canvas are made once 50ms have passed without any event.
        # This prevent one group redraw per port added/removed
        # when a lot of ports are added/removed/renamed simultaneously.
        self._delayed_orders_timer = QTimer()
        self._delayed_orders_timer.setInterval(50)
        self._delayed_orders_timer.setSingleShot(True)
        self._delayed_orders_timer.timeout.connect(
            self._delayed_orders_timeout)

        self.sg.out_thread_order.connect(self._delayed_orders_timer.start)
        self.sg.to_main_thread.connect(self._execute_in_main_thread)
        
        self.sg.theme_changed.connect(self.change_theme)
        
        self.sg.a2j_grouped_changed.connect(self.set_a2j_grouped)
        self.sg.alsa_midi_enabled_changed.connect(self.set_alsa_midi_enabled)
        self.sg.group_shadows_changed.connect(self.set_group_shadows)
        self.sg.auto_select_items_changed.connect(self.set_auto_select_items)
        self.sg.elastic_changed.connect(self.set_elastic_canvas)
        self.sg.borders_nav_changed.connect(self.set_borders_navigation)
        self.sg.prevent_overlap_changed.connect(self.set_prevent_overlap)
        self.sg.max_port_width_changed.connect(patchcanvas.set_max_port_width)
        self.sg.default_zoom_changed.connect(patchcanvas.set_default_zoom)
        
        self._tools_displayed = ToolDisplayed.ALL

    def app_init(self,
                 view: PatchGraphicsView,
                 theme_paths: tuple[Path, ...],
                 manual_path: Optional[Path] = None,
                 callbacker: Optional[Callbacker] = None,
                 options: Optional[CanvasOptionsObject] = None,
                 features: Optional[CanvasFeaturesObject] = None,
                 default_theme_name='Black Gold'):
        if callbacker is None:
            self.callbacker = Callbacker(self)
        else:
            if not isinstance(callbacker, Callbacker):
                exception = TypeError(
                    "callbacker must be a Callbacker instance !")
                raise exception
            
            self.callbacker = callbacker
        
        self._manual_path = manual_path
        
        if options is None:
            options = patchcanvas.CanvasOptionsObject()
            if isinstance(self._settings, QSettings):
                options.set_from_settings(self._settings)
        
        if features is None:
            features = CanvasFeaturesObject()

        patchcanvas.set_options(options)
        patchcanvas.set_features(features)
        patchcanvas.init(
            view, self.callbacker, theme_paths, default_theme_name)
        patchcanvas.canvas.scene.scale_changed.connect(self._scene_scale_changed)
        
        # just to have the zoom slider updated with the default zoom
        patchcanvas.canvas.scene.zoom_reset()
    
    @property
    def very_fast_operation(self) -> bool:
        '''when True, items are not added/removed from patchcanvas.
        Useful to win time at startup or refresh'''
        return self.canvas_optimize is CanvasOptimize.VERY_FAST
    
    def _scene_scale_changed(self, value: float):
        self.sg.scene_scale_changed.emit(value)

    def _execute_in_main_thread(
            self, func: Callable, args: tuple, kwargs: dict):
        func(*args, **kwargs)

    # --- widgets related methods --- #

    def set_main_win(self, main_win: QWidget):
        self.main_win = main_win # type:ignore

    def set_tools_widget(self, tools_widget: PatchbayToolsWidget):
        self._tools_widget = tools_widget
        self._tools_widget.set_patchbay_manager(self)

    def set_canvas_menu(self, canvas_menu: CanvasMenu):
        self.canvas_menu = canvas_menu

    def set_filter_frame(self, filter_frame: FilterFrame):
        self.filter_frame = filter_frame
        self.filter_frame.set_settings(self._settings)

    def set_options_dialog(self, options_dialog: CanvasOptionsDialog):
        self.options_dialog = options_dialog

    def show_options_dialog(self):
        if self.options_dialog is None:
            return
        
        self.options_dialog.move(QCursor.pos())
        self.options_dialog.show()

    def view(self) -> ViewData:
        return self.views[self.view_number]

    # --- manager methods --- #

    @staticmethod
    def save_patchcanvas_cache():
        patchcanvas.save_cache()
    
    def save_settings(self):
        if self._settings is None:
            return

        self._settings.setValue('Canvas/naming', self.naming.name)
        self._settings.setValue('Canvas/group_a2j_ports',
                                self.group_a2j_hw)
        self._settings.setValue('Canvas/alsa_midi_enabled',
                                self.alsa_midi_enabled)
        patchcanvas.options.save_to_settings(self._settings)

    def optimize_operation(
            self, yesno: bool, auto_redraw=False, prevent_overlap=True):
        if patchcanvas.canvas is not None:
            patchcanvas.set_loading_items(
                yesno,
                auto_redraw=auto_redraw,
                prevent_overlap=prevent_overlap)

    def _add_group(self, group: Group):
        self.groups.append(group)
        self._groups_by_id[group.group_id] = group
        self._groups_by_name[group.name] = group

    def _remove_group(self, group: Group):
        if group in self.groups:
            self.groups.remove(group)
            self._groups_by_id.pop(group.group_id)
            self._groups_by_name.pop(group.name)

    def new_portgroup(self, group_id: int, port_mode: PortMode,
                      ports: tuple[Port, ...] | list[Port]) -> Portgroup:
        portgroup = Portgroup(self, group_id, self._next_portgroup_id,
                              port_mode, tuple(ports))
        self._next_portgroup_id += 1
        return portgroup

    def port_type_shown(
            self, full_port_type: tuple[PortType, PortSubType]) -> bool:
        port_type, sub_type = full_port_type

        if port_type is PortType.MIDI_JACK:
            return bool(self.port_types_view & PortTypesViewFlag.MIDI)

        if port_type is PortType.AUDIO_JACK:
            if sub_type is PortSubType.REGULAR:
                return bool(self.port_types_view & PortTypesViewFlag.AUDIO)
            elif sub_type is PortSubType.CV:
                return bool(self.port_types_view & PortTypesViewFlag.CV)
            elif sub_type is (PortSubType.REGULAR | PortSubType.CV):
                return bool(
                    self.port_types_view & (PortTypesViewFlag.AUDIO
                                            | PortTypesViewFlag.CV)
                    == PortTypesViewFlag.AUDIO | PortTypesViewFlag.CV)

        if port_type is PortType.MIDI_ALSA:
            return bool(self.alsa_midi_enabled
                        and self.port_types_view & PortTypesViewFlag.ALSA)

        if port_type is PortType.VIDEO:
            return bool(self.port_types_view & PortTypesViewFlag.VIDEO)

        return False

    def animation_finished(self):
        '''Executed after any patchcanvas animation, it cleans
        in patchcanvas all boxes that should be hidden now.'''
        with CanvasOptimizeIt(self, auto_redraw=True, prevent_overlap=False):
            for group in self.groups:
                if group.current_position.hidden_port_modes() is PortMode.NULL:
                    continue

                hidden_port_mode = group.current_position.hidden_port_modes()
                
                if hidden_port_mode & PortMode.OUTPUT:
                    for conn in self.connections:
                        if conn.port_out.group_id is group.group_id:
                            conn.remove_from_canvas()
                
                if hidden_port_mode & PortMode.INPUT:
                    for conn in self.connections:
                        if conn.port_in.group_id is group.group_id:
                            conn.remove_from_canvas()
                
                for portgroup in group.portgroups:
                    if hidden_port_mode & portgroup.port_mode:
                        portgroup.remove_from_canvas()
                        
                for port in group.ports:
                    if hidden_port_mode & port.mode:
                        port.remove_from_canvas()
                
                if group.outs_ptv is PortTypesViewFlag.NONE:
                    hidden_port_mode |= PortMode.OUTPUT
                if group.ins_ptv is PortTypesViewFlag.NONE:
                    hidden_port_mode |= PortMode.INPUT

                if hidden_port_mode is PortMode.BOTH:
                    group.remove_from_canvas()
                    
            for conn in self.connections:
                conn.add_to_canvas()

        # patchcanvas.canvas.scene.resize_the_scene()
        self.sg.hidden_boxes_changed.emit()
        self.sg.animation_finished.emit()

    def set_group_hidden_sides(self, group_id: int, port_mode: PortMode):
        group = self.get_group_from_id(group_id)
        if group is None:
            return
        
        group.current_position.set_hidden_port_mode(
            group.current_position.hidden_port_modes() | port_mode)
        group.save_current_position()

        with CanvasOptimizeIt(self, auto_redraw=True):
            if port_mode & PortMode.OUTPUT:
                for conn in self.connections:
                    if conn.port_out.group_id == group_id:
                        conn.remove_from_canvas()
                        
                for portgroup in group.portgroups:
                    if portgroup.port_mode is PortMode.OUTPUT:
                        portgroup.remove_from_canvas()
                        
                for port in group.ports:
                    if port.mode is PortMode.OUTPUT:
                        port.remove_from_canvas()
                        
                for conn in self.connections:
                    if conn.port_out.group_id is group_id:
                        conn.add_to_canvas()
                        
            if port_mode & PortMode.INPUT:
                for conn in self.connections:
                    if conn.port_in.group_id == group_id:
                        conn.remove_from_canvas()
                        
                for portgroup in group.portgroups:
                    if portgroup.port_mode is PortMode.INPUT:
                        portgroup.remove_from_canvas()
                        
                for port in group.ports:
                    if port.mode is PortMode.INPUT:
                        port.remove_from_canvas()
                        
                for conn in self.connections:
                    if conn.port_in.group_id is group_id:
                        conn.add_to_canvas()

        self.sg.hidden_boxes_changed.emit()

    def restore_group_hidden_sides(
            self, group_id: int, scene_pos: Optional[tuple[int, int]]=None):
        group = self.get_group_from_id(group_id)
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

        with CanvasOptimizeIt(self):
            group.add_to_canvas()
            group.add_all_ports_to_canvas()
                    
            for conn in self.connections:
                if conn.port_out.group is group or conn.port_in.group is group:
                    conn.add_to_canvas()

        patchcanvas.move_group_boxes(
            group.group_id, gpos,
            redraw=hidden_port_mode, restore=hidden_port_mode)
        patchcanvas.repulse_from_group(group.group_id, hidden_port_mode)

        self.sg.hidden_boxes_changed.emit()

    def restore_all_group_hidden_sides(self):
        groups_to_restore = set[Group]()

        with CanvasOptimizeIt(self):
            for group in self.groups:
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
            for gpos in self.views.iter_group_poses(view_num=self.view_number):            
                gpos.set_hidden_port_mode(PortMode.NULL)
            
            for conn in self.connections:
                conn.add_to_canvas()
        
        for group in groups_to_restore:
            patchcanvas.move_group_boxes(
                group.group_id, group.current_position,
                redraw=PortMode.BOTH, restore=PortMode.BOTH)
            patchcanvas.repulse_from_group(group.group_id, PortMode.BOTH)

        self.sg.hidden_boxes_changed.emit()

    def hide_all_groups(self):
        groups_to_hide = set[Group]()
        
        with CanvasOptimizeIt(self):
            for group in self.groups:
                if (group.current_position.hidden_port_modes()
                        is not PortMode.BOTH):
                    groups_to_hide.add(group)
                    group.current_position.set_hidden_port_mode(PortMode.BOTH)
            
            for conn in self.connections:
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
        
        self.sg.hidden_boxes_changed.emit()

    def list_hidden_groups(self) -> Iterator[Group]:
        for group in self.groups:
            if (group.current_position.hidden_port_modes()
                    is not PortMode.NULL):
                yield group

    def get_group_from_name(self, group_name: str) -> Union[Group, None]:
        return self._groups_by_name.get(group_name)

    def get_group_from_id(self, group_id: int) -> Union[Group, None]:
        return self._groups_by_id.get(group_id)

    def get_port_from_name(self, port_name: str) -> Optional[Port]:
        return self._ports_by_name.get(port_name)

    def get_port_from_uuid(self, uuid:int) -> Optional[Port]:
        return self._ports_by_uuid.get(uuid)

    def get_port_from_id(self, group_id: int, port_id: int) -> Optional[Port]:
        group = self.get_group_from_id(group_id)
        if group is not None:
            for port in group.ports:
                if port.port_id == port_id:
                    return port

    def save_group_position(self, gpos: GroupPos):
        # reimplement this to save a group position elsewhere
        ...

    def save_portgroup_memory(self, portgrp_mem: PortgroupMem):
        # reimplement this to save a portgroup memory elsewhere
        ...

    def get_corrected_a2j_group_name(self, group_name: str) -> str:
        # a2j replace points with spaces in the group name
        # we do nothing here, but in some conditions we can 
        # assume we know it.
        return group_name

    def set_group_as_nsm_client(self, group: Group):
        ...

    def get_group_position(self, group_name: str) -> GroupPos:
        ptv_view = self.view().ptvs.get(self.port_types_view)
        if ptv_view is None:
            ptv_view = dict[str, GroupPos]()
            self.view().ptvs[self.port_types_view] = ptv_view
            
        gpos = ptv_view.get(group_name)
        if gpos is not None:
            return gpos

        self.cancel_mng.new_pos_created = True

        is_white_list_view = self.view().is_white_list

        # prevent move to a new position in case of port_types_view change
        # if there is no remembered position for this group in new view
        if not is_white_list_view:
            group = self.get_group_from_name(group_name)
            if group is not None:
                # copy the group_position
                gpos = group.current_position.copy()
                gpos.port_types_view = self.port_types_view
                gpos.has_sure_existence = False
                gpos.set_hidden_port_mode(PortMode.NULL)
                ptv_view[group_name] = gpos
                self.save_group_position(gpos)
                return gpos

        # group position doesn't already exists, create one
        gpos = GroupPos()
        gpos.fully_set = False
        gpos.port_types_view = self.port_types_view
        gpos.group_name = group_name

        if is_white_list_view:
            gpos.set_hidden_port_mode(PortMode.BOTH)

        for port_mode, xy in get_new_group_positions().items():
            gpos.boxes[port_mode].pos = xy

        ptv_view[group_name] = gpos
        self.save_group_position(gpos)
        return gpos

    def add_portgroup_memory(self, portgroup_mem: PortgroupMem):
        self.portgroups_memory.save_portgroup(portgroup_mem)
        
        group = self.get_group_from_name(portgroup_mem.group_name)
        if group is not None:
            group.portgroup_memory_added(portgroup_mem)

    def remove_and_add_all(self):
        with CanvasOptimizeIt(self, auto_redraw=True):
            for connection in self.connections:
                connection.remove_from_canvas()
            
            for group in self.groups:
                for portgroup in group.portgroups:
                    portgroup.remove_from_canvas()
                
                for port in group.ports:
                    port.remove_from_canvas()

                group.remove_from_canvas()
                group.add_to_canvas()
                group.add_all_ports_to_canvas()
            
            for connection in self.connections:
                connection.add_to_canvas()

    def clear_all(self):
        patchcanvas.clear_all()
        self.connections.clear()
        self.jack_metadatas.clear()
        self.groups.clear()
        self._groups_by_id.clear()
        self._groups_by_name.clear()
        self._ports_by_name.clear()
        self._ports_by_uuid.clear()

        self._next_group_id = 0
        self._next_port_id = 0
        self._next_portgroup_id = 1
        self._next_connection_id = 0
        
        self.sg.all_groups_removed.emit()

    def save_view_and_port_types_view(self):
        ...

    def change_port_types_view(
            self, port_types_view: PortTypesViewFlag, force=False):
        if not force and port_types_view is self.port_types_view:
            return

        ex_ptv = self.port_types_view
        self.port_types_view = port_types_view
        _logger.info(
            f"Change Port Types View: {ex_ptv.name} -> {port_types_view.name}")
        # Prevent visual update at each canvas item creation
        # because we may create/remove a lot of ports here

        change_counter = 0

        if len(self.groups) > 30:
            for group in self.groups:
                in_outs_ptv = group.ins_ptv | group.outs_ptv
                
                if in_outs_ptv & port_types_view is not in_outs_ptv & ex_ptv:
                    change_counter += 1
                    continue

                new_gpos = self.get_group_position(group.name)
                if group.current_position.needs_redraw(new_gpos):
                    change_counter += 1
        
        if change_counter > 30:
            # Big changes between the current and the next view
            # Strategy is to remove all from canvas and add all what is needed
            # without animation.
            for connection in self.connections:
                connection.in_canvas = False
                        
            for group in self.groups:
                group.in_canvas = False
                for portgroup in group.portgroups:
                    portgroup.in_canvas = False
                for port in group.ports:
                    port.in_canvas = False
            
            patchcanvas.clear_all()

            with CanvasOptimizeIt(self):
                for group in self.groups:
                    group.current_position = self.get_group_position(group.name)
                    if (group.outs_ptv | group.ins_ptv) & self.port_types_view:
                        group.add_to_canvas()
                        group.add_all_ports_to_canvas()
                
                for connection in self.connections:
                    connection.add_to_canvas()
            
            patchcanvas.redraw_all_groups()
            
            self.sg.port_types_view_changed.emit(self.port_types_view)
            self.view().default_port_types_view = self.port_types_view
            self.save_view_and_port_types_view()
            return
        
        rm_all_before = bool(ex_ptv & self.port_types_view
                             is PortTypesViewFlag.NONE)

        with CanvasOptimizeIt(self):
            if rm_all_before:
                # there is no common port type between previous and next view,
                # strategy is to remove fastly all contents from the patchcanvas.            
                for connection in self.connections:
                    connection.in_canvas = False
                            
                for group in self.groups:
                    group.in_canvas = False
                    for portgroup in group.portgroups:
                        portgroup.in_canvas = False
                    for port in group.ports:
                        port.in_canvas = False
                        
                patchcanvas.clear_all()

            else:
                for connection in self.connections:
                    connection.remove_from_canvas()

            groups_and_pos = dict[Group, tuple[GroupPos, PortMode, PortMode]]()

            for group in self.groups:
                new_gpos = self.get_group_position(group.name)
                in_outs_ptv = group.ins_ptv | group.outs_ptv
                hidden_modes = group.current_position.hidden_port_modes()
                new_hidden_modes = new_gpos.hidden_port_modes()
                redraw_mode = PortMode.NULL

                if (hidden_modes is not new_hidden_modes
                        or self.port_types_view & in_outs_ptv
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

                    if (self.port_types_view & group.ins_ptv
                            is not ex_ptv & group.ins_ptv):
                        redraw_mode |= PortMode.INPUT

                    if (self.port_types_view & group.outs_ptv
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

            for conn in self.connections:
                conn.add_to_canvas()

        if groups_and_pos:
            patchcanvas.canvas.scene.prevent_box_user_move = True

            for group, gpos_redraw in groups_and_pos.items():
                group.set_group_position(*gpos_redraw)

            patchcanvas.repulse_all_boxes()

        self.sg.port_types_view_changed.emit(self.port_types_view)
        self.view().default_port_types_view = self.port_types_view
        self.save_view_and_port_types_view()

    def set_views_changed(self):
        '''emit the `view_changed` signal. Can be Inherited to do other tasks'''
        self.sg.views_changed.emit()

    def new_view(self, view_number: Optional[int]=None,
                 exclusive_with: Optional[dict[int, PortMode]]=None):
        '''create a new view and switch directly to this view.
        
        If `view_number` is not set, it will choose the first available
        number.
        
        if `exclusive_with` is set, all non matching boxes will be hidden,
        and new view will be a white list view.'''
        
        new_num = self.views.add_view(
            view_number, default_ptv=self.port_types_view)
        if new_num is None:
            _logger.warning(f'failed to create new view n°{view_number}')
            return
        
        if exclusive_with is None:
            for gpos in self.views.iter_group_poses(view_num=self.view_number):
                self.views.add_group_pos(new_num, gpos.copy())
            
            if self.view().is_white_list:
                self.views[new_num].is_white_list = True

        else:
            self.views[new_num].is_white_list = True

            v = self.view().ptvs[self.port_types_view]
            self.views[new_num].ptvs[self.port_types_view] = new_v = {}

            for group_id, port_mode in exclusive_with.items():
                group = self.get_group_from_id(group_id)
                if group is not None:
                    new_v[group.name] = gpos = v[group.name].copy()
                    for pmode, box_pos in gpos.boxes.items():
                        if not port_mode & pmode:
                            box_pos.set_hidden(True)

        self.view().default_port_types_view = self.port_types_view
        self.view_number = new_num
        self.set_views_changed()
        self.change_port_types_view(self.port_types_view, force=True)
    
    def rename_current_view(self, new_name: str):
        self.view().name = new_name
        self.set_views_changed()
    
    def change_view(self, view_number: int):
        if not view_number in self.views.keys():
            self.new_view(view_number=view_number)
            return
        
        self.view_number = view_number
        new_view = self.views.get(self.view_number)
        if new_view is None:
            ptv = self.port_types_view
        else:
            ptv = new_view.default_port_types_view

        self.change_port_types_view(ptv, force=True)
        self.sg.view_changed.emit(view_number)
    
    def remove_view(self, view_number: int):
        if len(self.views) <= 1:
            _logger.error(
                f"Will not remove view {view_number}, "
                "to ensure there is at least one view.")
            return

        rm_current_view = bool(view_number is self.view_number)
        self.views.remove_view(view_number)

        if rm_current_view:
            switch_to_view = -1
            for view_num in self.views.keys():
                if view_num < view_number:
                    switch_to_view = view_num
                elif switch_to_view == -1:
                    switch_to_view = view_num
                    break
            
            self.change_view(switch_to_view)
    
        self.set_views_changed()

    def clear_absents_in_view(self, only_current_ptv=False):
        if only_current_ptv:
            self.views.clear_absents(
                self.view_number, self.port_types_view,
                set([g.name for g in self.groups
                     if g.is_in_port_types_view(self.port_types_view)]))
            return

        for ptv in self.view().ptvs.keys():
            self.views.clear_absents(
                self.view_number, ptv,
                set([g.name for g in self.groups
                     if g.is_in_port_types_view(ptv)]))
    
    def remove_all_other_views(self):
        view_nums = [n for n in self.views.keys() if n != self.view_number]
        for n in view_nums:
            self.views.remove_view(n)
        self.set_views_changed()
    
    def change_view_number(self, new_num: int):
        if new_num == self.view_number:
            return
        
        self.views.change_view_number(self.view_number, new_num)
        self.view_number = new_num
        self.sg.views_changed.emit()

    def write_view_data(
            self, view_number: int, name: Optional[str]=None,
            port_types: Optional[PortTypesViewFlag]=None,
            white_list_view=False):
        view_data = self.views.get(view_number)
        if view_data is None:
            if port_types is None:
                port_types = PortTypesViewFlag.ALL

            self.views.add_view(view_number, port_types)
            view_data = self.views[view_number]
        
        if name is not None:
            view_data.name = name
            
        if port_types is not None:
            view_data.default_port_types_view = port_types
        
        view_data.is_white_list = white_list_view
        
        self.set_views_changed()

    def arrange_follow_signal(self):
        with CancellableAction(self, CancelOp.VIEW) as a:
            a.name = _translate(
                'arrange', 'Arrange: follow the signal chain')
            arranger.arrange_follow_signal()
            
            # boxes will be at a completely different place after arrange
            # it takes no sense to keep positions of absent boxes
            self.clear_absents_in_view(only_current_ptv=True)
        
    def arrange_face_to_face(self):
        with CancellableAction(self, CancelOp.VIEW) as a:
            a.name = _translate(
                'arrange', 'Arrange: Two columns facing each other')
            arranger.arrange_face_to_face()
            
            # boxes will be at a completely different place after arrange
            # it takes no sense to keep positions of absent boxes
            self.clear_absents_in_view(only_current_ptv=True)

    # --- options triggers ---

    def set_a2j_grouped(self, yesno: int):
        if self.group_a2j_hw != bool(yesno):
            self.group_a2j_hw = bool(yesno)
            self.refresh()

    def set_alsa_midi_enabled(self, yesno: int):
        if self.alsa_midi_enabled != bool(yesno):
            self.alsa_midi_enabled = bool(yesno)
            self.change_port_types_view(PortTypesViewFlag.ALL, force=True)
            self.cancel_mng.reset()

    def set_group_shadows(self, yesno: int):
        patchcanvas.options.show_shadows = bool(yesno)
        self.remove_and_add_all()

    def set_auto_select_items(self, yesno: int):
        patchcanvas.set_auto_select_items(bool(yesno))

    def change_naming(self, naming: Naming):
        if naming is self.naming:
            return
        
        groups_dict = dict[Group, str]()
        ports_dict = dict[Port, str]()
        
        for group in self.groups:
            groups_dict[group] = group.cnv_name
            for port in group.ports:
                ports_dict[port] = port.cnv_name
        
        self.naming = naming

        with CanvasOptimizeIt(self, auto_redraw=True):
            for group in self.groups:
                if not group.in_canvas:
                    continue
                
                if group.cnv_name != groups_dict[group]:
                    group.rename_in_canvas()

                for port in group.ports:
                    if not port.in_canvas:
                        continue
                    if port.cnv_name != ports_dict[port]:
                        port.rename_in_canvas()

    def change_jack_export_naming(self, naming: Naming):
        self.jack_export_naming = naming

    def export_custom_names_to_jack(self):
        ...
        
    def import_pretty_names_from_jack(self):
        ...

    def change_theme(self, theme_name: str):
        if not theme_name:
            return
        
        for connection in self.connections:
            connection.in_canvas = False
        
        for group in self.groups:
            for portgroup in group.portgroups:
                portgroup.in_canvas = False
            for port in group.ports:
                port.in_canvas = False
            group.in_canvas = False

        patchcanvas.clear_all()
        patchcanvas.change_theme(theme_name)

        with CanvasOptimizeIt(self):
            for group in self.groups:
                group.add_to_canvas()
                for port in group.ports:
                    port.add_to_canvas()
                for portgroup in group.portgroups:
                    portgroup.add_to_canvas()
            
            for connection in self.connections:
                connection.add_to_canvas()

        patchcanvas.redraw_all_groups()

    def set_elastic_canvas(self, yesno: int):
        patchcanvas.set_elastic(bool(yesno))

    def set_borders_navigation(self, yesno: int):
        patchcanvas.set_borders_navigation(bool(yesno))

    def set_prevent_overlap(self, yesno: int):
        patchcanvas.set_prevent_overlap(bool(yesno))

    def set_zoom(self, zoom: float):
        patchcanvas.canvas.scene.zoom_ratio(zoom)

    def zoom_reset(self):
        patchcanvas.zoom_reset()
    
    def zoom_fit(self):
        patchcanvas.zoom_fit()  

    def refresh(self):
        self.clear_all()

    @later_by_batch()
    def set_group_uuid_from_name(self, client_name: str, uuid: int):
        self.client_uuids[client_name] = uuid
        
        group = self.get_group_from_name(client_name)
        if group is not None:
            group.uuid = uuid

    @later_by_batch(draw_group=True)
    def add_port(self, name: str, port_type: PortType,
                 flags: int, uuid: int) -> int:
        '''adds port and returns the group_id'''
        exst_port = self.get_port_from_name(name)
        if exst_port is not None:
            _logger.warning(
                f'add port "{name}", '
                f'it already exists, remove it first !')

            if name in self._ports_by_name:
                self._ports_by_name.pop(name)
            if uuid in self._ports_by_uuid:
                self._ports_by_uuid.pop(uuid)

            if exst_port.type.is_jack and exst_port.uuid:
                self.jack_metadatas.remove_uuid(exst_port.uuid)

            group = self.get_group_from_id(exst_port.group_id)
            if group is not None:
                # remove portgroup first if port is in a portgroup
                if exst_port.portgroup_id:
                    for portgroup in group.portgroups:
                        if portgroup.portgroup_id == exst_port.portgroup_id:
                            group.portgroups.remove(portgroup)
                            portgroup.remove_from_canvas()
                            break

                exst_port.remove_from_canvas()
                group.remove_port(exst_port)

        port = Port(self, self._next_port_id, name, port_type, flags, uuid)
        self._next_port_id += 1
        
        full_port_name = name
        group_name, colon, port_name = full_port_name.partition(':')

        is_a2j_group = False
        group_is_new = False

        if (port_type is PortType.MIDI_ALSA
                and full_port_name.startswith((':ALSA_OUT:', ':ALSA_IN:'))):
            _, _alsa_key, alsa_gp_id, alsa_p_id, group_name, *rest = \
                full_port_name.split(':')
            port_name = ':'.join(rest)

            if port.flags & JackPortFlag.IS_PHYSICAL:
                is_a2j_group = True

        elif (full_port_name.startswith(('a2j:', 'Midi-Bridge:'))
                and (not self.group_a2j_hw
                     or not port.flags & JackPortFlag.IS_PHYSICAL)):
            group_name, colon, port_name = port_name.partition(':')
            if full_port_name.startswith('a2j:'):
                if ' [' in group_name:
                    group_name = group_name.rpartition(' [')[0]
                else:
                    if ' (capture)' in group_name:
                        group_name = group_name.partition(' (capture)')[0]
                    else:
                        group_name = group_name.partition(' (playback)')[0]

                # fix a2j wrongly substitute '.' with space
                group_name = self.get_corrected_a2j_group_name(group_name)

            if port.flags & JackPortFlag.IS_PHYSICAL:
                is_a2j_group = True
        
        group = self.get_group_from_name(group_name)
        if group is None:
            # port is in an non existing group, create the group
            gpos = self.get_group_position(group_name)
            group = Group(self, self._next_group_id, group_name, gpos)
            
            group.a2j_group = is_a2j_group
            self.set_group_as_nsm_client(group)

            self._next_group_id += 1
            self._add_group(group)
            
            group_is_new = True

        group.add_port(port)
        group.graceful_port(port)

        group.add_to_canvas()
        port.add_to_canvas()
        group.check_for_portgroup_on_last_port()
        group.check_for_display_name_on_last_port()

        if group_is_new:
            self.sg.group_added.emit(group.group_id)
        
        return group.group_id

    @later_by_batch(draw_group=True, clear_conns=True)
    def remove_port(self, name: str) -> Union[int, None]:
        '''remove a port from name and return its group_id'''
        port = self.get_port_from_name(name)
        if port is None:
            return None

        if name in self._ports_by_name:
            self._ports_by_name.pop(name)
        if port.uuid in self._ports_by_uuid:
            self._ports_by_uuid.pop(port.uuid)
        if port.type.is_jack and port.uuid:
            self.jack_metadatas.remove_uuid(port.uuid)

        group = self.get_group_from_id(port.group_id)
        if group is None:
            return None

        # remove portgroup first if port is in a portgroup
        if port.portgroup_id:
            for portgroup in group.portgroups:
                if portgroup.portgroup_id == port.portgroup_id:
                    group.portgroups.remove(portgroup)
                    portgroup.remove_from_canvas()
                    break

        port.remove_from_canvas()
        group.remove_port(port)

        if not group.ports:
            group.remove_from_canvas()
            self._remove_group(group)
            self.sg.group_removed.emit(group.group_id)
            return None
        
        return group.group_id

    @later_by_batch(draw_group=True)
    def rename_port(self, name: str, new_name: str, uuid=0) -> Union[int, None]:
        if uuid:
            port = self.get_port_from_uuid(uuid)
        else:
            port = self.get_port_from_name(name)

        if port is None:
            if uuid:
                _logger.warning(
                    f"rename_port to {new_name}, no port with uuid {uuid}")
            else:
                _logger.warning(
                    f"rename_port to '{new_name}', no port named '{name}'")
            return

        # change port key in self._ports_by_name dict
        self._ports_by_name.pop(name)
        self._ports_by_name[new_name] = port

        group_name = name.partition(':')[0]
        new_group_name = new_name.partition(':')[0]

        # In case a port rename implies another group for the port
        if group_name != new_group_name:
            group = self.get_group_from_name(group_name)
            if group is not None:
                group.remove_port(port)
                if not group.ports:
                    self._remove_group(group)

            port.remove_from_canvas()
            port.full_name = new_name

            group = self.get_group_from_name(new_group_name)
            if group is None:
                # copy the group_position to not move the group
                # because group has been renamed
                orig_gpos = self.get_group_position(group_name)
                gpos = orig_gpos.copy()
                gpos.group_name = new_group_name

                group = Group(self, self._next_group_id, new_group_name, gpos)
                self._next_group_id += 1
                group.add_port(port)
                group.add_to_canvas()
            else:
                group.add_port(port)

            port.add_to_canvas()
            return group.group_id

        port.full_name = new_name
        port.group.graceful_port(port)
        port.rename_in_canvas()
        return port.group.group_id

    @later_by_batch(metadata_change=True)
    def metadata_update(
            self, uuid: int, key: str, value: str) -> Optional[int]:
        '''remember metadata and return the group_id'''
        
        # first store metadata
        self.jack_metadatas.add(uuid, key, value)
        
        if not uuid:
            # all JACK metadatas removed
            self.pretty_diff_checker.full_update()
            self.remove_and_add_all()
            return
        
        match key:
            case '':
                # all metadatas removed for an item (client or port)
                port = self.get_port_from_uuid(uuid)
                if port is not None:
                    port.rename_in_canvas()
                    return port.group_id
                
                for group in self.groups:
                    if group.uuid == uuid:
                        return group.group_id
            
            case JackMetadata.ORDER:
                port = self.get_port_from_uuid(uuid)
                if port is None:
                    return

                try:
                    port_order = int(value)
                except:
                    _logger.warning(
                        f"JACK_METADATA_ORDER for UUID {uuid} "
                        f"value '{value}' is not an int")
                    return
                else:
                    port.order = port_order
                    return port.group_id

            case JackMetadata.PRETTY_NAME:
                self.pretty_diff_checker.uuid_change(uuid)
                port = self.get_port_from_uuid(uuid)
                if port is not None:
                    port.rename_in_canvas()
                    return port.group_id

                for group in self.groups:
                    if group.uuid == uuid:
                        group.rename_in_canvas()
                        return group.group_id

            case JackMetadata.PORT_GROUP:
                port = self.get_port_from_uuid(uuid)
                if port is None:
                    return

                return port.group_id

            case JackMetadata.ICON_NAME:
                for group in self.groups:
                    if group.uuid == uuid:
                        group.set_client_icon(value, from_metadata=True)
                        return group.group_id

            case JackMetadata.SIGNAL_TYPE:
                port = self.get_port_from_uuid(uuid)
                if port is None:
                    return

                if port.type is PortType.AUDIO_JACK:
                    if value == 'CV':
                        port.subtype = PortSubType.CV
                    elif value == 'AUDIO':
                        port.subtype = PortSubType.REGULAR

                return port.group_id

    @later_by_batch()
    def add_connection(self, port_out_name: str, port_in_name: str):
        port_out = self.get_port_from_name(port_out_name)
        port_in = self.get_port_from_name(port_in_name)  

        if port_out is None or port_in is None:
            return

        for connection in self.connections:
            if (connection.port_out is port_out
                    and connection.port_in is port_in):
                return

        connection = Connection(self, self._next_connection_id, port_out, port_in)
        self._next_connection_id += 1
        self.connections.append(connection)

        connection.add_to_canvas()

    @later_by_batch()
    def remove_connection(self, port_out_name: str, port_in_name: str):
        port_out = self.get_port_from_name(port_out_name)
        port_in = self.get_port_from_name(port_in_name)
        if port_out is None or port_in is None:
            return

        for connection in self.connections:
            if (connection.port_out == port_out
                    and connection.port_in == port_in):
                self.connections.remove(connection)
                self.sg.connection_removed.emit(connection.connection_id)
                connection.remove_from_canvas()
                break

    def disannounce(self):
        self.clear_all()

    @in_main_thread()
    def server_started(self):
        self.server_is_started = True
        if self._tools_widget is not None:
            self._tools_widget.set_jack_running(True)
        
        self.clear_all()
        # if this function is executed, all graph will appear just after

    @in_main_thread()
    def server_stopped(self):
        self.server_is_started = False
        if self._tools_widget is not None:
            self._tools_widget.set_jack_running(
                False, use_alsa_midi=self.alsa_midi_enabled)

        self.clear_all()
        if self.alsa_midi_enabled:
            self.refresh()

    @in_main_thread()
    def server_lose(self):
        self.server_is_started = False
        
        if self._tools_widget is not None:
            self._tools_widget.set_jack_running(False)

        self.clear_all()
        if self.alsa_midi_enabled:
            self.refresh()

        if self.main_win is not None:
            ret = QMessageBox.critical(
                self.main_win,
                _translate('patchbay', "JACK server lose"),
                _translate('patchbay', "JACK server seems to be totally busy... ;("))

    @in_main_thread()
    def set_dsp_load(self, dsp_load: int):
        if self._tools_widget is not None:
            self._tools_widget.set_dsp_load(dsp_load)

    @in_main_thread()
    def add_xrun(self):
        if self._tools_widget is not None:
            self._tools_widget.add_xrun()

    @in_main_thread()
    def refresh_transport(self, transport_position: TransportPosition):
        if self._tools_widget is not None:
            self._tools_widget.refresh_transport(transport_position)

    def change_buffersize(self, buffer_size: int):
        ...

    def transport_play_pause(self, play: bool):
        ...

    def transport_stop(self):
        ...

    def transport_relocate(self, frame: int):
        ...

    def change_tools_displayed(self, tools_displayed: ToolDisplayed):
        if self._tools_widget is not None:
            self._tools_widget.change_tools_displayed(tools_displayed)

        self._tools_displayed = tools_displayed

    def redraw_all_groups(self):
        patchcanvas.redraw_all_groups()

    def filter_groups(self, text: str, n_select=0) -> int:
        '''Semi hides groups not matching with text
        and returns number of matching boxes.'''
        opac_grp_ids = set()

        for group in self.groups:
            if (text.lower() not in group.name.lower()
                    and text.lower() not in group.graceful_name.lower()):
                opac_grp_ids.add(group.group_id)
        
        patchcanvas.semi_hide_groups(opac_grp_ids)
        
        n_boxes = 0
        
        for group in self.groups:
            if group.group_id not in opac_grp_ids:
                n_grp_boxes = group.get_number_of_boxes()

                if n_select > n_boxes and n_select <= n_boxes + n_grp_boxes:
                    group.select_filtered_box(n_select - n_boxes)
                n_boxes += n_grp_boxes

        return n_boxes

    def set_semi_hide_opacity(self, opacity: float):
        patchcanvas.set_semi_hide_opacity(opacity)
        
    def set_aliasing_reason(self, aliasing_reason: AliasingReason, yesno: bool):
        patchcanvas.set_aliasing_reason(aliasing_reason, yesno)
        
    def start_aliasing_check(self, aliasing_reason: AliasingReason):
        patchcanvas.start_aliasing_check(aliasing_reason)

    @in_main_thread()
    def buffer_size_changed(self, buffer_size: int):
        if self._tools_widget is not None:
            self._tools_widget.set_buffer_size(buffer_size)

    @in_main_thread()
    def sample_rate_changed(self, samplerate: int):
        if self._tools_widget is not None:
            self._tools_widget.set_samplerate(samplerate)

    # @Slot()
    def _delayed_orders_timeout(self):
        '''This method is called by the QTimer self._delayed_orders_timer
        when no graph event happens during 50ms.
        It executes in the main thread all methods called since last time,
        then, it updates the canvas with new contents.'''
        _logger.debug('patchbay delayed order')

        group_ids_to_sort = set()
        some_groups_removed = False
        clear_conns = False
        
        with CanvasOptimizeIt(self, auto_redraw=True):
            while self.delayed_orders.qsize():
                oq = self.delayed_orders.get()
                
                _logger.debug(f'  execute {oq.func.__name__}, {oq.args[1:]}')
                
                # execute the function, and get concerned group_id
                group_id = oq.func(*oq.args, **oq.kwargs)

                if oq.metadata_change and group_id is not None:
                    key = oq.args[2]
                    if key in (JackMetadata.ORDER, ''):
                        group_ids_to_sort.add(group_id)

                if oq.draw_group:
                    if group_id is None:
                        some_groups_removed = True
                if oq.clear_conns:
                    clear_conns = True
    
            for group in self.groups:
                if group.group_id in group_ids_to_sort:
                    group.sort_ports_in_canvas()

            if clear_conns:
                # sometimes connections are still in canvas without ports
                # probably because the message for their destruction
                # has not been received.
                # here we can assume to clear all of them
                conns_to_clean = list[Connection]()

                for conn in self.connections:
                    for port in (conn.port_out, conn.port_in):
                        fport = self.get_port_from_name(port.full_name)
                        if fport is None:
                            conn.remove_from_canvas()
                            conns_to_clean.append(conn)
                            break
                        
                        if not fport.in_canvas:
                            conn.remove_from_canvas()
                        
                for conn in conns_to_clean:
                    self.connections.remove(conn)

        if some_groups_removed:
            patchcanvas.canvas.scene.resize_the_scene()
        
        self.sg.patch_may_have_changed.emit()
    
    def apply_delayed_changes_now(self):
        self._delayed_orders_timer.stop()
        self._delayed_orders_timeout()
    
    def export_to_patchichi_json(self, path: Path, editor_text='') -> bool:
        return export_to_patchichi_json(self, path, editor_text)
    
    def key_press_event(self, event: QKeyEvent):
        if not event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.modifiers() & Qt.KeyboardModifier.AltModifier:
                if Qt.Key.Key_0 <= event.key() <= Qt.Key.Key_9:
                    new_num = event.key() - Qt.Key.Key_0
                    if self.views.get(new_num) is None:
                            cancel_op = CancelOp.ALL_VIEWS
                    else:
                        cancel_op = CancelOp.VIEW_CHOICE

                    with CancellableAction(self, cancel_op) as a:
                        a.name = _translate('patchbay', 'Change view %i -> %i') \
                            % (self.view_number, new_num)
                        self.change_view(new_num)
            return

        if event.modifiers() & Qt.KeyboardModifier.AltModifier:
            if event.key() == Qt.Key.Key_A:
                self.arrange_follow_signal()            
            elif event.key() == Qt.Key.Key_Q:
                self.arrange_face_to_face()
                
        else:
            if event.key() == Qt.Key.Key_Z:
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    self.cancel_mng.redo()
                else:
                    self.cancel_mng.undo()
        