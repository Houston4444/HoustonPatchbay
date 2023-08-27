
from cProfile import label
from typing import TYPE_CHECKING, Union
from PyQt5.QtWidgets import (
    QMenu, QCheckBox, QFrame, QLabel, QHBoxLayout,
    QSpacerItem, QSizePolicy, QWidgetAction,
    QApplication)
from PyQt5.QtGui import QIcon, QColor, QKeyEvent, QPixmap
from PyQt5.QtCore import Qt, QSize


from .patchcanvas import canvas, CallbackAct, BoxType
from .patchcanvas.theme import StyleAttributer
from .patchcanvas.utils import get_portgroup_name_from_ports_names, get_icon, is_dark_theme
from .base_elements import Connection, Port, Portgroup, PortType, PortSubType, PortMode, Group

if TYPE_CHECKING:
    from patchbay_manager import PatchbayManager

_translate = QApplication.translate

def theme_css(theme: StyleAttributer) -> str:
    pen = theme.fill_pen()
    
    return (f"background-color: {theme.background_color().name(QColor.HexArgb)};"
            f"color: {theme.text_color().name(QColor.HexArgb)};"
            f"border: {pen.widthF()}px solid {pen.color().name(QColor.HexArgb)}")

    
class PortCheckBox(QCheckBox):
    def __init__(self, p_object:  Union[Port, Portgroup],
                 parent: 'CheckFrame', pg_pos=0, pg_len=1):
        QCheckBox.__init__(self, "", parent)
        self.setTristate(True)
        self._p_object = p_object
        self._parent = parent
        self._pg_pos = pg_pos
        self._pg_len = pg_len
        self.set_theme()

    def set_theme(self):        
        po = self._p_object
        
        full_theme = canvas.theme
        theme = full_theme.port
        line_theme = full_theme.line
        
        if isinstance(po, Portgroup):
            theme = full_theme.portgroup
            
        if po.full_type()[0] is PortType.AUDIO_JACK:
            theme = theme.audio
            line_theme = line_theme.audio
        elif po.full_type()[0] is PortType.MIDI_JACK:
            theme = theme.midi
            line_theme = line_theme.midi
        elif po.full_type()[0] is PortType.MIDI_ALSA:
            theme = theme.alsa
            line_theme = line_theme.alsa

        text_color = theme.text_color().name(QColor.HexArgb)
        border_color = theme.fill_pen().color().name(QColor.HexArgb)
        h_text_color = theme.selected.text_color().name(QColor.HexArgb)
        ind_bg = full_theme.scene_background_color.name(QColor.HexArgb)
        checked_bg = line_theme.selected.background_color().name(QColor.HexArgb)
        
        border_width = theme.fill_pen().widthF()
        
        TOP, RIGHT, BOTTOM, LEFT = 0, 1, 2, 3
        SIDES = ['top', 'right', 'bottom', 'left']
        margin_texts = [f"margin-{side}: 2px" for side in SIDES]
        border_texts = [f"border-{side}: {border_width}px solid {border_color}"
                        for side in SIDES]
        radius_text = ""
        
        if isinstance(po, Port) and po.portgroup_id:
            if self._pg_pos == 0:
                margin_texts.pop(BOTTOM)
                radius_text = "border-bottom-left-radius: 0px; border-bottom-right-radius: 0px"
            elif self._pg_pos + 1 == self._pg_len:
                margin_texts.pop(TOP)
                radius_text = "border-top-left-radius: 0px; border-top-right-radius: 0px"
                
            if self._pg_pos != 0:
                border_texts[TOP] = f"border-top: 0px solid transparent"

        self.setStyleSheet(
            f"QCheckBox{{background-color: none;color: {text_color}; spacing: 0px;"
                       f"border-radius: 3px; {radius_text};}}"
            f"QCheckBox:hover{{background-color: none;color: {h_text_color}}}"
        )
        # # this stylesheet code is commented because the checkbox was not clear 
        # # with some Qt theme (fusion, kvantum).
        # # seems impossible to have a coherent and readable style
        # # because change indicator size seems to not be applied when box is checked
        # # and it is very ugly.
        # # So we keep native checkboxes for the moment to ensure readability,
        # # and will see later if we found a better solution.

        #     f"QCheckBox::indicator{{width: 12px;height: 12px;"
        #                           f"background-color: {ind_bg};margin: 3px;"
        #                           f"border-radius: 3px; border: 1px solid "
        #                           f"{theme.fill_pen().color().name()}}}"
        #     f"QCheckBox::indicator:checked{{"
        #         f"background-color: {checked_bg}; border: 3px solid {ind_bg}}}"
        #     f"QCheckBox::indicator:indeterminate{{width: 12px;height: 12px;"
        #         f"background-color: qlineargradient("
        #             f"x1: 0, y1: 0, x2: 1, y2: 1, "
        #             f"stop: 0 {checked_bg}, stop: 0.55 {checked_bg}, "
        #             f"stop: 0.60 {ind_bg}, stop: 1 {ind_bg}); "
        #         f"border: 3px solid {ind_bg}}}")

    def nextCheckState(self):
        po = self._p_object
        port_id = po.port_id if isinstance(po, Port) else -1
        
        self._parent.connection_asked_from_box(po, not self.isChecked())


class CheckFrame(QFrame):
    def __init__(self, p_object: Union[Port, Portgroup],
                 port_name: str, port_name_end: str,
                 parent: 'ConnectMenu', pg_pos=0, pg_len=1):
        QFrame.__init__(self, parent)
        # self.setMinimumSize(QSize(100, 18))
        
        self._p_object = p_object
        self._parent = parent
        
        self._check_box = PortCheckBox(p_object, self, pg_pos, pg_len)
        self._label_left = QLabel(port_name)
        self._layout = QHBoxLayout(self)
        self._layout.setSpacing(0)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.addWidget(self._check_box)
        self._layout.addWidget(self._label_left)
        spacer = QSpacerItem(2, 2, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self._layout.addSpacerItem(spacer)
        self._label_right = None
        if port_name_end:
            self._label_right = QLabel(port_name_end)
            self._layout.addWidget(self._label_right)
        
        self._pg_pos = pg_pos
        self._pg_len = pg_len
        self._set_theme()

    def _set_theme(self):
        po = self._p_object

        full_theme = canvas.theme
        theme = full_theme.port
        line_theme = full_theme.line        

        if isinstance(po, Portgroup):
            theme = full_theme.portgroup
        
        if po.full_type()[0] is PortType.AUDIO_JACK:
            theme = theme.cv if po.full_type()[1] is PortSubType.CV else theme.audio
            line_theme = line_theme.audio
            
        elif po.full_type()[0] is PortType.MIDI_JACK:
            theme = theme.midi
            line_theme = line_theme.midi
            
        elif po.full_type()[0] is PortType.MIDI_ALSA:
            theme = theme.alsa
            line_theme = line_theme.alsa

        text_color = theme.text_color().name()
        border_color = theme.fill_pen().color().name()
        h_text_color = theme.selected.text_color().name()
        
        border_width = theme.fill_pen().widthF()
        
        TOP, RIGHT, BOTTOM, LEFT = 0, 1, 2, 3
        SIDES = ['top', 'right', 'bottom', 'left']
        margin_texts = [f"margin-{side}: 2px" for side in SIDES]
        border_texts = [f"border-{side}: {border_width}px solid {border_color}"
                        for side in SIDES]
        radius_text = ""
        
        if isinstance(po, Port) and po.portgroup_id:
            if self._pg_pos == 0:
                margin_texts.pop(BOTTOM)
                radius_text = ("border-bottom-left-radius: 0px; "
                               "border-bottom-right-radius: 0px")
            elif self._pg_pos + 1 == self._pg_len:
                margin_texts.pop(TOP)
                radius_text = ("border-top-left-radius: 0px; "
                               "border-top-right-radius: 0px")
                
            if self._pg_pos != 0:
                border_texts[TOP] = f"border-top: 0px solid transparent"

        margins_text = ';'.join(margin_texts)
        borders_text = ';'.join(border_texts)

        self.setFont(theme.font())
        self.setStyleSheet(
            f"CheckFrame{{{theme_css(theme)}; spacing: 0px;"
            f"{borders_text}; border-radius: 3px; {radius_text};"
            f"{margins_text}; padding-right: 0px}}"
            f"CheckFrame:focus{{{theme_css(theme.selected)}}};")
        
        self._label_left.setFont(theme.font())
        self._label_left.setStyleSheet(
            f"QLabel{{color: {text_color}}} QLabel:focus{{color: {h_text_color}}} ")
        
        if self._label_right is not None:
            port_theme = full_theme.port
            if po.port_type() is PortType.AUDIO_JACK:
                port_theme = port_theme.audio
            elif po.port_type() is PortType.MIDI_JACK:
                port_theme = port_theme.midi

            self._label_right.setFont(port_theme.font())
            self._label_right.setStyleSheet(
                f"QLabel{{margin-left: 3px; margin-right: 0px; padding: 0px; {theme_css(port_theme)}}} "
                f"QLabel:focus{{{theme_css(port_theme.selected)}}}")

    def set_check_state(self, check_state: int):
        self._check_box.setCheckState(check_state)

    def connection_asked_from_box(self, po: Union[Port, Portgroup], yesno: bool):
        self._parent.connection_asked_from_box(self._p_object, yesno)
    
    def mousePressEvent(self, event):
        self._check_box.nextCheckState()
        
    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key_Space, Qt.Key_Return):
            self._check_box.nextCheckState()
            return
        QFrame.keyPressEvent(self, event)
        
    def enterEvent(self, event):
        super().enterEvent(event)
        self.setFocus()


class GroupConnectMenu(QMenu):
    def __init__(self, group: Group, po: Union[Port, Portgroup],
                 parent: 'ConnectMenu'):
        short_group_name = group.cnv_name        
        if len(short_group_name) > 15 and '/' in short_group_name:
            short_group_name = short_group_name.partition('/')[2]

        QMenu.__init__(self, short_group_name, parent)
        self.hovered.connect(self._mouse_hover_menu)
        
        theme = canvas.theme.box        
        if group.cnv_box_type is BoxType.CLIENT:
            theme = theme.client
        elif group.cnv_box_type is BoxType.HARDWARE:
            theme = theme.hardware

        bg_color = theme.background_color().name(QColor.HexArgb)
        border_color = theme.fill_pen().color().name(QColor.HexArgb)
        
        self.setStyleSheet(
            "QMenu{"
                f"background-color:{bg_color}; "
                f"border: 2px solid {border_color}; "
                f"border-radius:4px"
            "}")
        self.setMinimumWidth(70)
        self.setMinimumHeight(50)

    def _mouse_hover_menu(self, action: QWidgetAction):
        # for better use with keyboard
        action.defaultWidget().setFocus()


class AbstractConnectionsMenu(QMenu):
    def __init__(self, mng: 'PatchbayManager',
                 po: Union[Portgroup, Port], parent=None):
        QMenu.__init__(self, '', parent)
        mng.sg.patch_may_have_changed.connect(self._patch_may_have_change)

        self._mng = mng
        self._po = po
        
        self._check_frames = dict[Union[Port, Portgroup], CheckFrame]()
    
    def _display_name(self, port: Port) -> str:
        if port.full_type() == (PortType.AUDIO_JACK, PortSubType.CV):
            return f"CV | {port.cnv_name}"
        return port.cnv_name
    
    def _ports(self, po: Union[Port, Portgroup, None]=None) -> list[Port]:
        if po is not None:
            if isinstance(po, Portgroup):
                return po.ports
            return [po]
        
        if isinstance(self._po, Portgroup):
            return self._po.ports
        return [self._po]
    
    def _port_type(self) -> PortType:
        if isinstance(self._po, Portgroup):
            return self._po.port_type()
        return self._po.type
    
    def _port_mode(self) -> PortMode:
        if isinstance(self._po, Portgroup):
            return self._po.port_mode
        return self._po.mode()

    def _get_connection_status(
            self, po_conns: list[Connection],
            out_ports: list[Port], in_ports: list[Port]) -> int:
        if not po_conns:
            return 0
        
        has_irregular = False
        missing_regulars = False
        
        for i in range(len(out_ports)):
            port_out = out_ports[i]
            for j in range(len(in_ports)):
                port_in = in_ports[j]
                regular = (i % len(in_ports) == j
                           or j % len(out_ports) == i)

                for conn in po_conns:
                    if (conn.port_out is port_out
                            and conn.port_in is port_in):
                        if not regular:
                            has_irregular = True
                        break
                else:
                    if regular:
                        missing_regulars = True

        if has_irregular or missing_regulars:
            return 1
        return 2

    def connection_asked_from_box(self, po: Union[Port, Portgroup], yesno: bool):
        out_ports, in_ports = self._ports(), self._ports(po)
        if self._port_mode() is PortMode.INPUT:
            out_ports, in_ports = in_ports, out_ports
            
        conns = [c for c in self._mng.connections
                    if c.port_out in out_ports
                    and c.port_in in in_ports]

        for i in range(len(out_ports)):
            port_out = out_ports[i]
            for j in range(len(in_ports)):
                port_in = in_ports[j]

                if yesno and (i % len(in_ports) == j
                                or j % len(out_ports) == i):
                    for conn in conns:
                        if (conn.port_out is port_out
                                and conn.port_in is port_in):
                            break
                    else:
                        canvas.callback(
                            CallbackAct.PORTS_CONNECT,
                            port_out.group_id, port_out.port_id,
                            port_in.group_id, port_in.port_id)
                else:
                    for conn in conns:
                        if (conn.port_out is port_out
                                and conn.port_in is port_in):
                            canvas.callback(
                                CallbackAct.PORTS_DISCONNECT,
                                conn.connection_id)
                            break
    
    def _patch_may_have_change(self):
        if self._port_mode() is PortMode.OUTPUT:
            conns = [c for c in self._mng.connections
                     if c.port_out in self._ports()]

            for po, check_frame in self._check_frames.items():
                in_ports = self._ports(po)
                check_frame.set_check_state(
                    self._get_connection_status(
                        [c for c in conns if c.port_in in in_ports],
                         self._ports(), in_ports))
                
        else:
            conns = [c for c in self._mng.connections
                     if c.port_in in self._ports()]

            for po, check_frame in self._check_frames.items():
                out_ports = self._ports(po)
                check_frame.set_check_state(
                    self._get_connection_status(
                        [c for c in conns if c.port_out in out_ports], 
                        out_ports, self._ports()))


class ConnectMenu(AbstractConnectionsMenu):
    def __init__(self, mng: 'PatchbayManager',
                 po: Union[Portgroup, Port], parent=None):
        AbstractConnectionsMenu.__init__(self, mng, po, parent)
        self.setTitle(_translate('patchbay', 'Connect'))
        dark = '-dark' if is_dark_theme(self) else ''
        self.setIcon(
            QIcon(QPixmap(':scalable/breeze%s/lines-connector' % dark)))
        

        has_dangerous = self._fill_all_ports()
        if has_dangerous:
            self._fill_all_ports(dangerous=True)
        self._patch_may_have_change()
    
    def _is_connection_dangerous(self, port: Port) -> bool:
        t_type, t_subtype = self._po.full_type()
        p_type, p_subtype = port.full_type()
        
        if t_type is not PortType.AUDIO_JACK:
            return False
        
        if t_subtype is p_subtype:
            return False
        
        if t_subtype is PortSubType.CV:
            return self._port_mode() is PortMode.OUTPUT
        
        if p_subtype is PortSubType.CV:
            return port.mode() is PortMode.OUTPUT
        
        return False
    
    def _fill_all_ports(self, dangerous=False) -> bool:
        main_menu = self
        if dangerous:
            if self._po.full_type()[1] is PortSubType.CV:
                dangerous_name = _translate(
                    'patchbay', 'Audio | DANGEROUS !!!')
            else:
                dangerous_name = _translate(
                    'patchbay', 'CV | DANGEROUS !!!')
            main_menu = QMenu(dangerous_name, self)
            main_menu.setIcon(QIcon.fromTheme('emblem-warning'))
        
        has_dangerous_ports = False

        for group in self._mng.groups:
            gp_menu = None
            last_portgrp_id = 0
            
            for port in group.ports:
                if (port.type is self._port_type()
                        and port.mode() is self._port_mode().opposite()):
                    if self._is_connection_dangerous(port) != dangerous:
                        has_dangerous_ports = True
                        continue
                    
                    if gp_menu is None:
                        gp_menu = GroupConnectMenu(group, self._po, main_menu)
                        gp_menu.setIcon(
                            get_icon(
                                group.cnv_box_type, group.cnv_icon_name,
                                self._port_mode().opposite(),
                                dark=is_dark_theme(self)))

                    if isinstance(self._po, Portgroup) and port.portgroup_id:
                        if port.portgroup_id == last_portgrp_id:
                            continue

                        for portgroup in group.portgroups:
                            if portgroup.portgroup_id == port.portgroup_id:
                                portgrp_name = get_portgroup_name_from_ports_names(
                                    [p.cnv_name for p in portgroup.ports])
                                end_name = '/'.join(
                                    [p.cnv_name.replace(portgrp_name, '', 1)
                                     for p in portgroup.ports])
                                
                                check_frame = CheckFrame(
                                    portgroup, portgrp_name, end_name, self)
                                self._check_frames[portgroup] = check_frame
                                break
                        else:
                            continue
                        
                        last_portgrp_id = port.portgroup_id
                    
                    elif isinstance(self._po, Port) and port.portgroup_id:
                        pg_pos, pg_len = group.port_pg_pos(port.port_id)
                        check_frame = CheckFrame(port, self._display_name(port),
                                                 '', self, pg_pos, pg_len)
                        self._check_frames[port] = check_frame                  
                    else:
                        check_frame = CheckFrame(port, self._display_name(port),
                                                 '', self)
                        self._check_frames[port] = check_frame
                                
                    action = QWidgetAction(self)
                    action.setDefaultWidget(check_frame)
                    gp_menu.addAction(action)

            if gp_menu is not None:
                main_menu.addMenu(gp_menu)

        if dangerous:
            self.addSeparator()
            self.addMenu(main_menu)

        return has_dangerous_ports

    def _get_connection_status(
            self, po_conns: list[Connection],
            out_ports: list[Port], in_ports: list[Port]) -> int:
        if not po_conns:
            return 0
        
        has_irregular = False
        missing_regulars = False
        
        for i in range(len(out_ports)):
            port_out = out_ports[i]
            for j in range(len(in_ports)):
                port_in = in_ports[j]
                regular = (i % len(in_ports) == j
                           or j % len(out_ports) == i)

                for conn in po_conns:
                    if (conn.port_out is port_out
                            and conn.port_in is port_in):
                        if not regular:
                            has_irregular = True
                        break
                else:
                    if regular:
                        missing_regulars = True

        if has_irregular or missing_regulars:
            return 1
        return 2


class DisconnectMenu(AbstractConnectionsMenu):
    def __init__(self, mng: 'PatchbayManager', po: Union[Port, Portgroup],
                 parent: QMenu):
        AbstractConnectionsMenu.__init__(self, mng, po, parent)
        self.setTitle(_translate('patchbay', 'Disconnect'))
        dark = '-dark' if is_dark_theme(self) else ''
        self.setIcon(
            QIcon(QPixmap(':scalable/breeze%s/lines-disconnector' % dark)))
        
        self.setSeparatorsCollapsible(False)
        
        if self._port_mode() is PortMode.OUTPUT:
            conn_ports = [c.port_in for c in self._mng.connections
                          if c.port_out in self._ports()]
        else:
            conn_ports = [c.port_out for c in self._mng.connections
                          if c.port_in in self._ports()]
        
        for group in self._mng.groups:
            group_section_exists = False
            last_portgrp_id = 0
            
            for port in group.ports:
                if port in conn_ports:
                    # if isinstance(self._po, Portgroup) and port.portgroup_id:
                    #     for portgroup in group.portgroups:
                    #         if portgroup.portgroup_id == port.portgroup_id:
                    #             status = self._get_connection_status(
                    #                 conn_ports, self._ports(), self._ports(portgroup))
                    #             if status == 2:
                    #                 pass
                    #             break
                    
                    if not group_section_exists:
                        group_icon = get_icon(
                            group.cnv_box_type, group.cnv_icon_name,
                            self._port_mode().opposite(),
                            dark=is_dark_theme(self))
                        
                        widget = QFrame()
                        widget.layout = QHBoxLayout(widget)
                        widget.layout.setSpacing(4)
                        widget.layout.setContentsMargins(4, 4, 4, 4)
                        label_icon = QLabel()
                        label_icon.setPixmap(group_icon.pixmap(QSize(16, 16)))
                        widget.layout.addWidget(label_icon)
                        label_name = QLabel(group.cnv_name)
                        label_name.setStyleSheet("color=red")
                        widget.layout.addWidget(QLabel(group.cnv_name))
                        spacer = QSpacerItem(2, 2, QSizePolicy.Expanding, QSizePolicy.Minimum)
                        widget.layout.addSpacerItem(spacer)
                        
                        action = QWidgetAction(self)
                        action.setDefaultWidget(widget)
                        action.setSeparator(True)
                        self.addAction(action)
                        group_section_exists = True
                    
                    if isinstance(self._po, Portgroup) and port.portgroup_id:
                        if port.portgroup_id == last_portgrp_id:
                            continue

                        for portgroup in group.portgroups:
                            if portgroup.portgroup_id == port.portgroup_id:
                                portgrp_name = get_portgroup_name_from_ports_names(
                                    [p.cnv_name for p in portgroup.ports])
                                end_name = '/'.join(
                                    [p.cnv_name.replace(portgrp_name, '', 1)
                                     for p in portgroup.ports])
                                
                                check_frame = CheckFrame(
                                    portgroup, portgrp_name, end_name, self)
                                self._check_frames[portgroup] = check_frame
                                break
                        else:
                            continue
                        
                        last_portgrp_id = port.portgroup_id
                    
                    else:
                        check_frame = CheckFrame(port, self._display_name(port),'', self)

                    check_frame.set_check_state(2)
                    port_action = QWidgetAction(self)
                    port_action.setDefaultWidget(check_frame)
                    self._check_frames[port] = check_frame
                    # self.addAction('     ' + self._display_name(port))
                    self.addAction(port_action)

class PortMenu(QMenu):
    def __init__(self, mng: 'PatchbayManager', group_id: int, port_id: int):
        self._mng = mng
        QMenu.__init__(self)
        port = mng.get_port_from_id(group_id, port_id)
        conn_menu = ConnectMenu(mng, port, self)
        disconn_menu = DisconnectMenu(mng, port, self)    
        # conn_menu = PortConnectionsMenu(mng, group_id, port_id, self) 
        self._port = self._mng.get_port_from_id(group_id, port_id)
        if self._port is None:
            return

        self.addMenu(conn_menu)
        self.addMenu(disconn_menu)
        

class PortgroupMenu(QMenu):
    def __init__(self, mng: 'PatchbayManager', group_id: int, portgrp_id: int):
        self._mng = mng
        QMenu.__init__(self)
        
        for group in mng.groups:
            if group.group_id == group_id:
                for portgroup in group.portgroups:
                    if portgroup.portgroup_id == portgrp_id:
                        portgrp = portgroup
                        break
                else:
                    continue
                break
        else:
            return
        
        conn_menu = ConnectMenu(mng, portgrp)
        disconn_menu = DisconnectMenu(mng, portgroup, self)   
        
        self.addMenu(conn_menu)
        self.addMenu(disconn_menu)