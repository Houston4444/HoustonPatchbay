from typing import TYPE_CHECKING
from PyQt5.QtWidgets import QMenu, QApplication
from PyQt5.QtCore import pyqtSlot
from PyQt5.QtGui import QIcon, QPixmap

from .base_elements import PortMode, GroupPosFlag, BoxLayoutMode
from .base_group import Group
from .patchcanvas import canvas, CallbackAct, patchcanvas, utils
if TYPE_CHECKING:
    from .patchbay_manager import PatchbayManager

_translate = QApplication.translate


class DisconnectMenu(QMenu):
    def __init__(self, mng: 'PatchbayManager',
                 group: Group, port_mode: PortMode):
        super().__init__()
        self._mng = mng
        self._group = group
        self._port_mode = port_mode
        
        self.setTitle(_translate('patchbay', 'Disconnect'))
        
        self._fill_menu()
    
    def _fill_menu(self):
        out_groups = set[Group]()
        in_groups = set[Group]()
        
        if self._port_mode & PortMode.OUTPUT:
            for conn in self._mng.connections:
                if conn.port_out.group_id == self._group.group_id:
                    in_groups.add(
                        self._mng.get_group_from_id(conn.port_in.group_id))
                    
        if self._port_mode & PortMode.INPUT:
            for conn in self._mng.connections:
                if conn.port_in.group_id == self._group.group_id:
                    out_groups.add(
                        self._mng.get_group_from_id(conn.port_out.group_id))

        if not out_groups and not in_groups:
            no_conn_act = self.addAction(_translate('patchbay', 'No connections'))
            no_conn_act.setEnabled(False)
            return

        use_dark_icon = utils.is_dark_theme(self)

        for group in self._mng.groups:
            if (group in out_groups and group in in_groups
                    and group is not self._group):
                in_str, out_str = 'ins', 'outs'
                if group._is_hardware:
                    in_str, out_str = 'playbacks', 'captures'

                group_act_in = self.addAction(f"{group.cnv_name} ({in_str})")
                group_act_in.setData((PortMode.INPUT, group))
                group_act_in.setIcon(
                    utils.get_icon(
                        group.cnv_box_type, group.cnv_icon_name,
                        PortMode.INPUT, dark=use_dark_icon))
                group_act_in.triggered.connect(self._apply_disconnections)

                group_act_out = self.addAction(f"{group.cnv_name} ({out_str})")
                group_act_out.setData((PortMode.OUTPUT, group))
                group_act_in.setIcon(
                    utils.get_icon(
                        group.cnv_box_type, group.cnv_icon_name,
                        PortMode.OUTPUT, dark=use_dark_icon))
                group_act_out.triggered.connect(self._apply_disconnections)
            
            elif group in out_groups:
                group_act = self.addAction(group.cnv_name)
                group_act.setData((PortMode.OUTPUT, group))
                group_act.setIcon(
                    utils.get_icon(
                        group.cnv_box_type, group.cnv_icon_name,
                        PortMode.OUTPUT, dark=use_dark_icon))
                group_act.triggered.connect(self._apply_disconnections)
            
            elif group in in_groups:
                group_act = self.addAction(group.cnv_name)
                group_act.setData((PortMode.INPUT, group))
                group_act.setIcon(
                    utils.get_icon(
                        group.cnv_box_type, group.cnv_icon_name,
                        PortMode.INPUT, dark=use_dark_icon))
                group_act.triggered.connect(self._apply_disconnections)
                
    @pyqtSlot()
    def _apply_disconnections(self):
        data : tuple[PortMode, Group] = self.sender().data()
        port_mode, group = data
        
        if port_mode is PortMode.INPUT:
            for conn in self._mng.connections:
                if (conn.port_out.group_id == self._group.group_id
                        and conn.port_in.group_id == group.group_id):
                    canvas.callback(CallbackAct.PORTS_DISCONNECT,
                                    conn.connection_id)
                    
        elif port_mode is PortMode.OUTPUT:
            for conn in self._mng.connections:
                if (conn.port_in.group_id == self._group.group_id
                        and conn.port_out.group_id == group.group_id):
                    canvas.callback(CallbackAct.PORTS_DISCONNECT,
                                    conn.connection_id)

class GroupMenu(QMenu):
    def __init__(self, mng: 'PatchbayManager',
                 group: Group, port_mode: PortMode):
        super().__init__()
        self._mng = mng
        self._group = group
        self._port_mode = port_mode
        
        dark = '-dark' if utils.is_dark_theme(self) else ''
        
        self._disconnect_menu = DisconnectMenu(mng, group, port_mode)
        self._disconnect_menu.setIcon(
            QIcon(QPixmap(':scalable/breeze%s/lines-disconnector' % dark)))
        
        self.addMenu(self._disconnect_menu)
        
        disco_all_act = self.addAction(_translate('patchbay', 'Disconnect All'))
        disco_all_act.setIcon(
            QIcon(QPixmap(':scalable/breeze%s/lines-disconnector' % dark)))

        self.addSeparator()

        current_port_mode = PortMode.NULL
        for port in group.ports:
            if port.in_canvas:
                current_port_mode |= port.mode()
                if current_port_mode is PortMode.BOTH:
                    break

        if current_port_mode is PortMode.BOTH:
            if self._group.current_position.is_splitted():
                join_act = self.addAction(
                    _translate('patchbay', 'Join'))
                join_act.setIcon(QIcon.fromTheme('join'))
                join_act.triggered.connect(self._join)
            else:
                split_act = self.addAction(
                    _translate('patchbay', 'Split'))
                split_act.setIcon(QIcon.fromTheme('split'))
                split_act.triggered.connect(self._split)

        box_pos = self._group.current_position.boxes[self._port_mode]
        self._is_wrapped = box_pos.is_wrapped()
        
        wrap_title = _translate('patchbay', 'Wrap')
        wrap_icon = QIcon.fromTheme('pan-up-symbolic')

        if self._is_wrapped:
            wrap_title = _translate('patchbay', 'Unwrap')
            wrap_icon = QIcon.fromTheme('pan-down-symbolic')

        wrap_act = self.addAction(wrap_title)
        wrap_act.setIcon(wrap_icon)

        # layout mode entries        
        auto_layout_act = self.addAction(
            _translate('patchbay', 'Automatic layout'))
        auto_layout_act.setIcon(QIcon.fromTheme('auto-scale-x'))
        auto_layout_act.setVisible(
            self._group.current_position.boxes[port_mode].layout_mode
            is not BoxLayoutMode.AUTO)
        
        change_layout_act = self.addAction(
            _translate('patchbay', 'Change layout'))
        change_layout_act.setIcon(QIcon.fromTheme('view-split-left-right'))
        
        # entry 'hide the box'
        hide_box_act = self.addAction(
            _translate('patchbay', 'Hide'))
        hide_box_act.setIcon(QIcon.fromTheme('hide_table_row'))
        
        disco_all_act.triggered.connect(self._disconnect_all)
        wrap_act.triggered.connect(self._wrap)
        auto_layout_act.triggered.connect(self._auto_layout)
        change_layout_act.triggered.connect(self._change_layout)
        hide_box_act.triggered.connect(self._hide_box)
    
    def _disconnect_all(self):
        if self._port_mode & PortMode.OUTPUT:
            for conn in self._mng.connections:
                if (conn.port_out.group_id == self._group.group_id
                        and conn.in_canvas):
                    canvas.callback(
                        CallbackAct.PORTS_DISCONNECT, conn.connection_id)
                    
        if self._port_mode & PortMode.INPUT:
            for conn in self._mng.connections:
                if (conn.port_in.group_id == self._group.group_id
                        and conn.in_canvas):
                    canvas.callback(
                        CallbackAct.PORTS_DISCONNECT, conn.connection_id)
    
    @pyqtSlot()
    def _join(self):
        patchcanvas.animate_before_join(self._group.group_id, self._port_mode)
        self._group.current_position.set_splitted(False)
    
    @pyqtSlot()  
    def _split(self):
        canvas.callback(
            CallbackAct.GROUP_SPLIT, self._group.group_id)

    @pyqtSlot()
    def _wrap(self):
        canvas.callback(CallbackAct.GROUP_WRAP,
                        self._group.group_id, self._port_mode,
                        not self._is_wrapped)
        
    @pyqtSlot()
    def _auto_layout(self):
        canvas.callback(CallbackAct.GROUP_LAYOUT_CHANGE,
                        self._group.group_id, self._port_mode,
                        BoxLayoutMode.AUTO)
        
    @pyqtSlot()
    def _change_layout(self):
        current_layout = patchcanvas.get_box_true_layout(
            self._group.group_id, self._port_mode)
        
        if current_layout is BoxLayoutMode.HIGH:
            next_layout = BoxLayoutMode.LARGE
        elif current_layout is BoxLayoutMode.LARGE:
            next_layout = BoxLayoutMode.HIGH
        else:
            next_layout = BoxLayoutMode.AUTO
        
        canvas.callback(CallbackAct.GROUP_LAYOUT_CHANGE,
                        self._group.group_id, self._port_mode,
                        next_layout)
    
    @pyqtSlot()
    def _hide_box(self):
        patchcanvas.animate_before_hide_box(
            self._group.group_id, self._port_mode)
