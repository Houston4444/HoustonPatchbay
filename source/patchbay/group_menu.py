from typing import TYPE_CHECKING

from qtpy.QtWidgets import QMenu, QApplication
from qtpy.QtCore import Slot
from qtpy.QtGui import QIcon, QPixmap

from .cancel_mng import CancelOp, CancellableAction
from patshared import PortMode, BoxLayoutMode
from .base_group import Group
from .patchcanvas import canvas, CallbackAct, patchcanvas, utils
from .rename_group_dialog import RenameGroupDialog

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
                if (conn.port_out.group_id is self._group.group_id
                        and conn.in_canvas):
                    in_groups.add(
                        self._mng.get_group_from_id(conn.port_in.group_id))
                    
        if self._port_mode & PortMode.INPUT:
            for conn in self._mng.connections:
                if (conn.port_in.group_id is self._group.group_id
                        and conn.in_canvas):
                    out_groups.add(
                        self._mng.get_group_from_id(conn.port_out.group_id))

        if not out_groups and not in_groups:
            no_conn_act = self.addAction(
                _translate('patchbay', 'No connections'))
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
                
    @Slot()
    def _apply_disconnections(self):
        data : tuple[PortMode, Group] = self.sender().data()
        port_mode, group = data
        
        if port_mode is PortMode.INPUT:
            for conn in self._mng.connections:
                if (conn.port_out.group_id is self._group.group_id
                        and conn.port_in.group_id is group.group_id
                        and conn.in_canvas):
                    canvas.callback(CallbackAct.PORTS_DISCONNECT,
                                    conn.connection_id)
                    
        elif port_mode is PortMode.OUTPUT:
            for conn in self._mng.connections:
                if (conn.port_in.group_id is self._group.group_id
                        and conn.port_out.group_id is group.group_id
                        and conn.in_canvas):
                    canvas.callback(CallbackAct.PORTS_DISCONNECT,
                                    conn.connection_id)

class GroupMenu(QMenu):
    def __init__(self, mng: 'PatchbayManager',
                 group: Group, port_mode: PortMode):
        super().__init__()
        self._mng = mng
        self._group = group
        self._port_mode = port_mode
        self._build()

    def _build(self):
        dark = '-dark' if utils.is_dark_theme(self) else ''
        
        self._disconnect_menu = DisconnectMenu(
            self._mng, self._group, self._port_mode)
        self._disconnect_menu.setIcon(
            QIcon(QPixmap(':scalable/breeze%s/lines-disconnector' % dark)))
        
        self.addMenu(self._disconnect_menu)
        
        disco_all_act = self.addAction(_translate('patchbay', 'Disconnect All'))
        disco_all_act.setIcon(
            QIcon(QPixmap(':scalable/breeze%s/lines-disconnector' % dark)))

        self.addSeparator()

        current_port_mode = PortMode.NULL
        for port in self._group.ports:
            if port.in_canvas:
                current_port_mode |= port.mode
                if current_port_mode is PortMode.BOTH:
                    break

        if self._group.current_position.is_splitted():
            join_act = self.addAction(
                _translate('patchbay', 'Join'))
            join_act.setIcon(QIcon.fromTheme('join'))
            join_act.triggered.connect(self._join)
            if current_port_mode is not PortMode.BOTH:
                join_act.setEnabled(False)
        else:
            split_act = self.addAction(
                _translate('patchbay', 'Split'))
            split_act.setIcon(QIcon.fromTheme('split'))
            split_act.triggered.connect(self._split)
            if current_port_mode is not PortMode.BOTH:
                split_act.setEnabled(False)

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
            self._group.current_position.boxes[self._port_mode].layout_mode
            is not BoxLayoutMode.AUTO)
        
        change_layout_act = self.addAction(
            _translate('patchbay', 'Change layout'))
        change_layout_act.setIcon(QIcon.fromTheme('view-split-left-right'))
        
        # entry 'hide the box'
        hide_box_act = self.addAction(
            _translate('patchbay', 'Hide'))
        hide_box_act.setIcon(QIcon.fromTheme('hide_table_row'))
        
        rename_act = self.addAction(
            _translate('patchbay', 'Rename'))
        rename_act.setIcon(QIcon.fromTheme('edit-rename'))
        
        disco_all_act.triggered.connect(self._disconnect_all)
        wrap_act.triggered.connect(self._wrap)
        auto_layout_act.triggered.connect(self._auto_layout)
        change_layout_act.triggered.connect(self._change_layout)
        hide_box_act.triggered.connect(self._hide_box)
        rename_act.triggered.connect(self._rename)
    
    def _disconnect_all(self):
        if self._port_mode & PortMode.OUTPUT:
            for conn in self._mng.connections:
                if (conn.port_out.group_id is self._group.group_id
                        and conn.in_canvas):
                    canvas.callback(
                        CallbackAct.PORTS_DISCONNECT, conn.connection_id)
                    
        if self._port_mode & PortMode.INPUT:
            for conn in self._mng.connections:
                if (conn.port_in.group_id is self._group.group_id
                        and conn.in_canvas):
                    canvas.callback(
                        CallbackAct.PORTS_DISCONNECT, conn.connection_id)
    
    @Slot()
    def _join(self):
        with CancellableAction(self._mng, CancelOp.VIEW) as a:
            a.name = _translate('undo', 'Join "%s"') % self._group.cnv_name

            gpos = self._group.current_position
            gpos.set_splitted(False)
            gpos.boxes[PortMode.BOTH].pos = gpos.boxes[self._port_mode].pos
            gpos.boxes[PortMode.BOTH].set_wrapped(
                gpos.boxes[PortMode.OUTPUT].is_wrapped()
                and gpos.boxes[PortMode.INPUT].is_wrapped())

            patchcanvas.move_group_boxes(self._group.group_id, gpos)
            patchcanvas.repulse_from_group(self._group.group_id, PortMode.BOTH)
    
    @Slot()  
    def _split(self):
        with CancellableAction(self._mng, CancelOp.VIEW) as a:
            a.name = _translate('undo', 'Split "%s"') % self._group.cnv_name
            patchcanvas.split_group(self._group.group_id, on_place=True)

    @Slot()
    def _wrap(self):
        canvas.callback(CallbackAct.GROUP_WRAP,
                        self._group.group_id, self._port_mode,
                        not self._is_wrapped)
        
    @Slot()
    def _auto_layout(self):
        with CancellableAction(self._mng, CancelOp.VIEW) as a:
            a.name = _translate('undo', 'Set auto layout for "%s"') \
                % self._group.cnv_name
            self._group.set_layout_mode(self._port_mode, BoxLayoutMode.AUTO)
        
    @Slot()
    def _change_layout(self):
        current_layout = patchcanvas.get_box_true_layout(
            self._group.group_id, self._port_mode)
        
        if current_layout is BoxLayoutMode.HIGH:
            next_layout = BoxLayoutMode.LARGE
        elif current_layout is BoxLayoutMode.LARGE:
            next_layout = BoxLayoutMode.HIGH
        else:
            next_layout = BoxLayoutMode.AUTO
        
        with CancellableAction(self._mng, CancelOp.VIEW) as a:
            a.name = _translate('undo', 'Set "%s" layout to %s') \
                % (self._group.cnv_name, next_layout.name)
            self._group.set_layout_mode(self._port_mode, next_layout)
    
    @Slot()
    def _hide_box(self):
        with CancellableAction(self._mng, CancelOp.VIEW) as a:
            a.name = _translate('undo', 'Hide "%s"') \
                % self._group.cnv_name
            self._group.hide(self._port_mode)
            
    @Slot()
    def _rename(self):
        pretty_name = self._mng.pretty_names.pretty_group(self._group.name)
        if pretty_name:
            suggest = pretty_name
        elif self._group.mdata_pretty_name:
            suggest = self._group.mdata_pretty_name
        else:
            suggest = self._group.display_name
        
        dialog = RenameGroupDialog(
            self._mng.main_win, self._group.name, suggest)
        if not dialog.exec():
            return
        
        pretty_name = dialog.pretty_name()
        self._mng.pretty_names.save_group(
            self._group.name, pretty_name, self._group.mdata_pretty_name)
        self._group.rename_in_canvas()
        
        canvas.callback(
            CallbackAct.GROUP_RENAME, self._group.group_id, pretty_name)
