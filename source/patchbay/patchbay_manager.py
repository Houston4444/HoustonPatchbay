import logging
from pathlib import Path
from typing import Callable, Iterator

from qtpy.QtGui import QCursor, QGuiApplication, QKeyEvent
from qtpy.QtWidgets import QMainWindow, QMessageBox, QWidget
from qtpy.QtCore import QTimer, QSettings, QThread, Qt

from patshared import (
    PortType, PortSubType, PortMode, JackMetadatas,
    PortTypesViewFlag, GroupPos, Naming, TransportPosition,
    ViewsDictEnsureOne, ViewData, PortgroupsDict, PortgroupMem, CustomNames)

from . import patchbay_batches, patchbay_hiddens, patchbay_views
from .bases.connection import Connection
from .bases.elements import ToolDisplayed, CanvasOptimizeIt, CanvasOptimize
from .bases.group import Group
from .bases.port import Port
from .bases.portgroup import Portgroup
from .calbacker import Callbacker
from .cancel_mng import CancelMng, CancelOp, CancellableAction
from .conns_clipboard import ConnClipboard
from .dialogs.options_dialog import CanvasOptionsDialog
from .menus.canvas_menu import CanvasMenu
from .patchbay_signals import SignalsObject
from .patchcanvas import patchcanvas
from .patchcanvas.utils import get_new_group_positions
from .patchcanvas.scene_view import PatchGraphicsView
from .patchcanvas.init_values import (
    AliasingReason, CanvasFeaturesObject, CanvasOptionsObject)
from .patchichi_export import export_to_patchichi_json
from .pretty_diff_checker import PrettyDiffChecker
from .tools_widgets import PatchbayToolsWidget
from .widgets.filter_frame import FilterFrame


_translate = QGuiApplication.translate
_logger = logging.getLogger(__name__)


def enum_to_flag(enum_int: int) -> int:
    if enum_int <= 0:
        return 0
    return 2 ** (enum_int - 1)

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

    jack_metadatas = JackMetadatas()

    def __init__(self, settings: QSettings):
        self.callbacker = Callbacker(self)
        self.cancel_mng = CancelMng(self)
        self._settings = settings

        self.main_win: QMainWindow | None = None
        self._tools_widget: PatchbayToolsWidget | None = None
        self.options_dialog: CanvasOptionsDialog | None = None
        self.filter_frame: FilterFrame | None = None

        self._manual_path: Path | None = None

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
                 manual_path: Path | None = None,
                 callbacker: Callbacker | None = None,
                 options: CanvasOptionsObject | None = None,
                 features: CanvasFeaturesObject | None = None,
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
        patchcanvas.canvas.scene.scale_changed.connect(
            self._scene_scale_changed)

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

        match port_type:
            case PortType.MIDI_JACK:
                return PortTypesViewFlag.MIDI in self.port_types_view
            case PortType.AUDIO_JACK:
                match sub_type:
                    case PortSubType.REGULAR:
                        return PortTypesViewFlag.AUDIO in self.port_types_view
                    case PortSubType.CV:
                        return PortTypesViewFlag.CV in self.port_types_view
                    case (PortSubType.REGULAR | PortSubType.CV):
                        return (
                            (PortTypesViewFlag.AUDIO | PortTypesViewFlag.CV)
                            in self.port_types_view)
            case PortType.MIDI_ALSA:
                return (self.alsa_midi_enabled
                        and PortTypesViewFlag.ALSA in self.port_types_view)
            case PortType.VIDEO:
                return PortTypesViewFlag.VIDEO in self.port_types_view

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
        patchbay_hiddens.set_group_hidden_sides(self, group_id, port_mode)

    def restore_group_hidden_sides(
            self, group_id: int, scene_pos: tuple[int, int] | None =None):
        patchbay_hiddens.restore_group_hidden_sides(
            self, group_id, scene_pos=scene_pos)

    def restore_all_group_hidden_sides(self):
        patchbay_hiddens.restore_all_group_hidden_sides(self)

    def hide_all_groups(self):
        patchbay_hiddens.hide_all_groups(self)

    def list_hidden_groups(self) -> Iterator[Group]:
        for group in self.groups:
            if (group.current_position.hidden_port_modes()
                    is not PortMode.NULL):
                yield group

    def get_group_from_name(self, group_name: str) -> Group | None:
        return self._groups_by_name.get(group_name)

    def get_group_from_id(self, group_id: int) -> Group | None:
        return self._groups_by_id.get(group_id)

    def get_port_from_name(self, port_name: str) -> Port | None:
        return self._ports_by_name.get(port_name)

    def get_port_from_uuid(self, uuid:int) -> Port | None:
        return self._ports_by_uuid.get(uuid)

    def get_port_from_id(self, group_id: int, port_id: int) -> Port | None:
        group = self.get_group_from_id(group_id)
        if group is not None:
            for port in group.ports:
                if port.port_id == port_id:
                    return port

    def save_group_position(self, gpos: GroupPos):
        'reimplement this to save a group position elsewhere'
        pass

    def save_portgroup_memory(self, portgrp_mem: PortgroupMem):
        'reimplement this to save a portgroup memory elsewhere'
        pass

    def get_corrected_a2j_group_name(self, group_name: str) -> str:
        '''a2j replace points with spaces in the group name.
        we do nothing here, but in some conditions we can
        assume we know it.'''
        return group_name

    def set_group_as_nsm_client(self, group: Group):
        'do nothing, reimplement this'
        pass

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
        pass

    def change_port_types_view(
            self, port_types_view: PortTypesViewFlag, force=False):
        patchbay_views.change_port_types_view(
            self, port_types_view, force=force)

    def set_views_changed(self):
        '''emit the `view_changed` signal. Can be Inherited to do other tasks'''
        self.sg.views_changed.emit()

    def new_view(self, view_number: int | None =None,
                 exclusive_with: dict[int, PortMode] | None =None):
        '''create a new view and switch directly to this view.

        If `view_number` is not set, it will choose the first available
        number.

        if `exclusive_with` is set, all non matching boxes will be hidden,
        and new view will be a white list view.'''
        patchbay_views.new_view(
            self, view_number=view_number, exclusive_with=exclusive_with)

    def rename_current_view(self, new_name: str):
        patchbay_views.rename_current_view(self, new_name)

    def change_view(self, view_number: int):
        patchbay_views.change_view(self, view_number)

    def remove_view(self, view_number: int):
        patchbay_views.remove_view(self, view_number)

    def clear_absents_in_view(self, only_current_ptv=False):
        patchbay_views.clear_absents_in_view(
            self, only_current_ptv=only_current_ptv)

    def remove_all_other_views(self):
        patchbay_views.remove_all_other_views(self)

    def change_view_number(self, new_num: int):
        patchbay_views.change_view_number(self, new_num)

    def write_view_data(
            self, view_number: int, name: str | None =None,
            port_types: PortTypesViewFlag | None =None,
            white_list_view=False):
        patchbay_views.write_view_data(
            self, view_number, name=name, port_types=port_types,
            white_list_view=white_list_view)

    def arrange_follow_signal(self):
        with CancellableAction(self, CancelOp.VIEW) as a:
            a.name = _translate(
                'arrange', 'Arrange: follow the signal chain')
            patchcanvas.arrange_follow_signal()

            # boxes will be at a completely different place after arrange
            # it takes no sense to keep positions of absent boxes
            self.clear_absents_in_view(only_current_ptv=True)

    def arrange_face_to_face(self):
        with CancellableAction(self, CancelOp.VIEW) as a:
            a.name = _translate(
                'arrange', 'Arrange: Two columns facing each other')
            patchcanvas.arrange_face_to_face()

            # boxes will be at a completely different place after arrange
            # it takes no sense to keep positions of absent boxes
            self.clear_absents_in_view(only_current_ptv=True)

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
        pass

    def import_pretty_names_from_jack(self):
        pass

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
        patchcanvas.canvas.scene.set_zoom_ratio(zoom)

    def zoom_reset(self):
        patchcanvas.zoom_reset()

    def zoom_fit(self):
        patchcanvas.zoom_fit()

    def refresh(self):
        self.clear_all()

    def set_group_uuid_from_name(self, client_name: str, uuid: int):
        patchbay_batches.set_group_uuid_from_name(self, client_name, uuid)

    def add_port(self, name: str, port_type: PortType, flags: int, uuid: int):
        'add port to the global patch, it will be applied later by batches'
        patchbay_batches.add_port(self, name, port_type, flags, uuid)

    def remove_port(self, name: str):
        'remove port from the global patch, will be applied later by batches'
        patchbay_batches.remove_port(self, name)

    def rename_port(self, name: str, new_name: str, uuid=0):
        'rename port in the global patch, will be applied later by batches'
        patchbay_batches.rename_port(self, name, new_name, uuid=uuid)

    def metadata_update(
            self, uuid: int, key: str, value: str):
        '''remember metadata, will be applied later by batches'''
        return patchbay_batches.metadata_update(self, uuid, key, value)

    def add_connection(self, port_out_name: str, port_in_name: str):
        '''add connection to the global patch,
        will be applied later by batches'''
        patchbay_batches.add_connection(self, port_out_name, port_in_name)

    def remove_connection(self, port_out_name: str, port_in_name: str):
        '''remove connection from the global patch,
        will be applied later by batches'''
        patchbay_batches.remove_connection(self, port_out_name, port_in_name)

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
                _translate('patchbay', "JACK server seems to be "
                           "totally busy... ;("))

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
        '''Inherit this'''

    def transport_play_pause(self, play: bool):
        '''Inherit this'''

    def transport_stop(self):
        '''Inherit this'''

    def transport_relocate(self, frame: int):
        '''Inherit this'''

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

    def _delayed_orders_timeout(self):
        '''This method is called by the QTimer self._delayed_orders_timer
        when no graph event happens during 50ms.
        It executes in the main thread all methods called since last time,
        then, it updates the canvas with new contents.'''
        patchbay_batches.delayed_orders_timeout(self)

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
