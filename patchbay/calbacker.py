import time
from typing import TYPE_CHECKING, Callable
from PyQt5.QtCore import QPoint
from PyQt5.QtGui import QCursor


from . import patchcanvas
from .patchcanvas import CallbackAct, PortMode, PortType, BoxLayoutMode
from .base_elements import PortgroupMem, BoxPos
from .base_port import Port
from .port_info_dialog import CanvasPortInfoDialog
from .port_menu import PoMenu, ConnectMenu
from .group_menu import GroupMenu

if TYPE_CHECKING:
    from .patchbay_manager import PatchbayManager


class Callbacker:
    '''manage actions coming from patchcanvas.
    Each protected method implements the action to run
    when the action happens.'''
    
    def __init__(self, manager: 'PatchbayManager'):
        self.mng = manager
        self.patchcanvas = patchcanvas

        self._funcs = dict[Callable, CallbackAct]()
        for cb_act in CallbackAct:
            func_name = '_' + cb_act.name.lower()
            if func_name in self.__dir__():
                self._funcs[cb_act] = self.__getattribute__(func_name)
    
    def receive(self, action: CallbackAct, args: tuple):
        '''receives a callback from patchcanvas and execute
        the function with action name in lowercase.'''
        self._funcs[action](*args)
        
    # ￬￬￬ functions connected to CallBackAct ￬￬￬
    
    def _group_info(self, group_id: int):
        ...
    
    def _group_rename(self, group_id: int):
        ...

    def _group_splitted(self, group_id: int):
        group = self.mng.get_group_from_id(group_id)
        if group is not None:
            group.current_position.set_splitted(True)
            group.save_current_position()
    
    def _group_joined(self, group_id: int):
        group = self.mng.get_group_from_id(group_id)
        if group is not None:
            group.current_position.set_splitted(False)
            group.save_current_position()

    def _group_move(self, group_id: int, port_mode: PortMode, x: int, y: int):
        group = self.mng.get_group_from_id(group_id)
        if group is None:
            return
        group.current_position.boxes[port_mode].pos = (x, y)
        group.save_current_position()

    def _group_box_pos_changed(
            self, group_id: int, port_mode: PortMode, box_pos: BoxPos):
        group = self.mng.get_group_from_id(group_id)
        if group is None:
            return

        group.current_position.boxes[port_mode].eat(box_pos)
        
        group.save_current_position()

    def _group_wrap(self, group_id: int, splitted_mode: PortMode, yesno: bool):
        group = self.mng.get_group_from_id(group_id)
        if group is not None:
            group.wrap_box(splitted_mode, yesno)
    
    def _group_layout_change(self, group_id: int, port_mode: PortMode,
                            layout_mode: BoxLayoutMode):
        group = self.mng.get_group_from_id(group_id)
        if group is not None:
            group.set_layout_mode(port_mode, layout_mode)
    
    def _group_selected(self, group_id: int, port_mode: PortMode):
        ...
    
    def _group_hide_box(self, group_id: int, port_mode: PortMode):
        group = self.mng.get_group_from_id(group_id)
        if group is None:
            return
        
        self.mng.set_group_hidden_sides(group_id, port_mode)

    def _group_menu_call(self, group_id: int, port_mode: PortMode):
        group = self.mng.get_group_from_id(group_id)
        if group is not None:
            menu = GroupMenu(self.mng, group, port_mode)
            menu.exec(QCursor().pos())
    
    def _portgroup_add(self, group_id: int, port_mode: PortMode,
                       port_type: PortType, port_ids: tuple[int]):
        port_list = list[Port]()
        above_metadatas = False

        for port_id in port_ids:
            port = self.mng.get_port_from_id(group_id, port_id)
            if port.mdata_portgroup:
                above_metadatas = True
            port_list.append(port)

        group = self.mng.get_group_from_id(group_id)
        if group is None:
            return

        # we add a PortgroupMem, manager will add the portgroup with it
        pg_mem = PortgroupMem()
        pg_mem.group_name = group.name
        pg_mem.port_type = port_type
        pg_mem.port_mode = port_mode
        
        pg_mem.above_metadatas = above_metadatas
        pg_mem.port_names = [p.short_name() for p in port_list]

        self.mng.add_portgroup_memory(pg_mem)
        self.mng.save_portgroup_memory(pg_mem)
    
    def _portgroup_remove(self, group_id: int, portgroup_id: int):
        group = self.mng.get_group_from_id(group_id)
        if group is None:
            return

        for portgroup in group.portgroups:
            if portgroup.portgroup_id == portgroup_id:
                for port in portgroup.ports:
                    # save a fake portgroup with one port only
                    # it will be considered as a forced mono port
                    # (no stereo detection)
                    pg_mem = PortgroupMem()
                    pg_mem.group_name = group.name
                    pg_mem.port_type = port.type
                    pg_mem.port_mode = portgroup.port_mode
                    pg_mem.above_metadatas = bool(port.mdata_portgroup)
                    pg_mem.port_names = [port.short_name()]
                    self.mng.add_portgroup_memory(pg_mem)
                    self.mng.save_portgroup_memory(pg_mem)
                break

    def _port_info(self, group_id: int, port_id: int):
        port = self.mng.get_port_from_id(group_id, port_id)
        if port is None:
            return

        dialog = CanvasPortInfoDialog(self.mng.main_win)
        dialog.set_port(port)
        dialog.show()

    def _port_rename(self, group_id: int, port_id: int):
        ...
    
    def _ports_connect(self, group_out_id: int, port_out_id: int,
                       group_in_id: int, port_in_id: int):
        ...

    def _ports_disconnect(self, connection_id: int):
        ...

    def _port_menu_call(self, group_id: int, port_id: int, connect_only: bool,
                        x: int, y: int):
        port = self.mng.get_port_from_id(group_id, port_id)
        if connect_only:
            menu = ConnectMenu(self.mng, port)
        else:
            menu = PoMenu(self.mng, port)
        menu.exec(QPoint(x, y))

    def _portgroup_menu_call(self, group_id: int, portgrp_id: int, connect_only: bool,
                             x: int, y: int):
        for group in self.mng.groups:
            if group.group_id != group_id:
                continue
            
            for portgroup in group.portgroups:
                if portgroup.portgroup_id == portgrp_id:
                    break
            else:
                continue
            break
        else:
            return

        if connect_only:
            menu = ConnectMenu(self.mng, portgroup)
        else:
            menu = PoMenu(self.mng, portgroup)
        menu.exec(QPoint(x, y))

    def _plugin_clone(self, plugin_id: int):
        ...
        
    def _plugin_edit(self, plugin_id: int):
        ...
        
    def _plugin_rename(self, plugin_id: int):
        ...
        
    def _plugin_replace(self, plugin_id: int):
        ...
        
    def _plugin_remove(self, plugin_id: int):
        ...
        
    def _plugin_show_ui(self, plugin_id: int):
        ...
        
    def _inline_display(self):
        ...

    def _bg_right_click(
            self, x: int, y: int, scene_x: float, scene_y: float,
            selected_boxes: dict[int, PortMode]):
        if self.mng.canvas_menu is not None:
            self.mng.canvas_menu.remember_scene_pos(scene_x, scene_y)
            self.mng.canvas_menu.set_selected_boxes(selected_boxes)
            self.mng.canvas_menu.exec(QPoint(x, y))
    
    def _bg_double_click(self):
        self.mng.sg.full_screen_toggle_wanted.emit()
    
    def _client_show_gui(self, group_id: int, visible: int):
        ...
                    
    def _theme_changed(self, theme_ref: str):
        if self.mng.options_dialog is not None:
            self.mng.options_dialog.set_theme(theme_ref)

        patchcanvas.redraw_all_groups(theme_change=True)

    def _animation_finished(self):
        self.mng.animation_finished()