
from enum import IntEnum, IntFlag
from typing import TYPE_CHECKING, Union

from qtpy.QtCore import Qt, QSize, Slot, QEvent, QPoint
from qtpy.QtGui import (
    QIcon, QColor, QKeyEvent, QPixmap, QMouseEvent,
    QCursor, QFocusEvent, QPaintEvent, QPainter,
    QPen, QBrush)

from ..dialogs.pretty_name_dialog import PrettyNameDialog
if TYPE_CHECKING:
    # FIX : QAction not found by pylance
    from qtpy.QtGui import QAction
from qtpy.QtWidgets import (
    QMenu, QCheckBox, QFrame, QLabel, QHBoxLayout,
    QSpacerItem, QSizePolicy, QWidgetAction,
    QApplication, QAction)

from ..patchcanvas import canvas, CallbackAct, BoxType, options
from ..patchcanvas.theme import StyleAttributer
from ..patchcanvas.utils import (
    get_portgroup_name_from_ports_names, get_icon, is_dark_theme, portgroup_name_splitted)
from patshared import (
    PortType, PortSubType, PortMode)
from ..bases.group import Group
from ..bases.port import Port
from ..bases.portgroup import Portgroup
from ..bases.connection import Connection

if TYPE_CHECKING:
    from patchbay_manager import PatchbayManager


_translate = QApplication.translate


def theme_css(theme: StyleAttributer) -> str:
    pen = theme.fill_pen()
    
    return (
        "background-color: "
        f"{theme.background_color().name(QColor.NameFormat.HexArgb)};"
        "color: "
        f"{theme.text_color().name(QColor.NameFormat.HexArgb)};"
        "border: "
        f"{pen.widthF()}px solid {pen.color().name(QColor.NameFormat.HexArgb)}"
    )


class ConnState(IntEnum):
    NONE = 0
    IRREGULAR = 1
    REGULAR = 2
    
    def to_qt_check_state(self):
        if self is ConnState.NONE:
            return Qt.CheckState.Unchecked
        if self is ConnState.IRREGULAR:
            return Qt.CheckState.PartiallyChecked
        return Qt.CheckState.Checked


class ExistingConns(IntFlag):
    NONE = 0x0
    VISIBLE = 0x1
    HIDDEN = 0x2

    
class PortCheckBox(QCheckBox):
    def __init__(self, p_object:  Union[Port, Portgroup],
                 parent: 'CheckFrame', pg_pos=0, pg_len=1):
        QCheckBox.__init__(self, "", parent)
        self.setTristate(True)
        
        port_height = int(
            canvas.theme.port_height * options.default_zoom / 100.0 + 2)
        self.setMinimumHeight(port_height)
        self.setMinimumWidth(port_height)
        
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        
        self._po = p_object
        self._parent = parent
        self._pg_pos = pg_pos
        self._pg_len = pg_len
        self.set_theme()

    def set_theme(self):        
        po = self._po
        
        full_theme = canvas.theme
        theme = full_theme.port
        line_theme = full_theme.line
        
        if isinstance(po, Portgroup):
            theme = full_theme.portgroup
            
        if po.full_type[0] is PortType.AUDIO_JACK:
            theme = theme.audio
            line_theme = line_theme.audio
        elif po.full_type[0] is PortType.MIDI_JACK:
            theme = theme.midi
            line_theme = line_theme.midi
        elif po.full_type[0] is PortType.MIDI_ALSA:
            theme = theme.alsa
            line_theme = line_theme.alsa

        self._theme = theme
        self._line_theme = line_theme
        text_color = theme.text_color().name(QColor.NameFormat.HexArgb)
        border_color = theme.fill_pen().color().name(QColor.NameFormat.HexArgb)
        h_text_color = theme.selected.text_color().name(QColor.NameFormat.HexArgb)
        ind_bg = full_theme.scene_background_color.name(QColor.NameFormat.HexArgb)
        checked_bg = line_theme.selected.background_color().name(QColor.NameFormat.HexArgb)
        
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
        self._parent.connection_asked_from_box(
            self._po, not self.isChecked())

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter()
        painter.begin(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self._theme.fill_pen())
        pen.setWidth(1)
        painter.setPen(pen)
        bg = QColor(canvas.theme.scene_background_color)
        bg.setAlphaF(1.0)
        painter.setBrush(QBrush(bg))
        
        rect = event.rect().adjusted(2, 2, -2, -2)        
        painter.drawRoundedRect(rect, 2.0, 2.0)
        
        line_color = self._line_theme.background_color()
        painter.setBrush(QBrush(line_color))
        painter.setPen(QPen(Qt.PenStyle.NoPen))
        circle_rect = rect.adjusted(3, 3, -3, -3)
        
        if self.checkState() == 2:
            circle_rect = rect.adjusted(3, 3, -3, -3)
            painter.drawEllipse(circle_rect)
        elif self.checkState() == 1:
            moon_rect = rect.adjusted(2, 2, -2, -2)
            painter.drawPie(moon_rect, 70*16, 220*16)

        painter.end()


class CheckFrame(QFrame):
    def __init__(self, p_object: Union[Port, Portgroup],
                 port_name: str, port_name_end: str,
                 parent: 'ConnectMenu', pg_pos=0, pg_len=1):
        QFrame.__init__(self, parent)
        port_height = int(canvas.theme.port_height * options.default_zoom / 100.0) + 2
        self.setMinimumHeight(port_height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        self._p_object = p_object
        self._parent = parent
        
        self._check_box = PortCheckBox(p_object, self, pg_pos, pg_len)
        self._label_left = QLabel(port_name)
        self._layout = QHBoxLayout(self)
        self._layout.setSpacing(0)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.addWidget(self._check_box)
        spacer1 = QSpacerItem(2, 2, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._layout.addSpacerItem(spacer1)
        self._layout.addWidget(self._label_left)
        spacer = QSpacerItem(2, 2, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
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

        if isinstance(po, Portgroup):
            theme = full_theme.portgroup
        
        if po.full_type[0] is PortType.AUDIO_JACK:
            theme = theme.cv if po.full_type[1] is PortSubType.CV else theme.audio
            
        elif po.full_type[0] is PortType.MIDI_JACK:
            theme = theme.midi
            
        elif po.full_type[0] is PortType.MIDI_ALSA:
            theme = theme.alsa

        self._theme = theme

        text_color = theme.text_color().name()
        border_color = theme.fill_pen().color().name()        
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
            f"QLabel{{color: {text_color}}}")
        
        if self._label_right is not None:
            port_theme = full_theme.port
            port_type = po.type
            if port_type is PortType.AUDIO_JACK:
                port_theme = port_theme.audio
            elif port_type is PortType.MIDI_JACK:
                port_theme = port_theme.midi

            self._label_right.setFont(port_theme.font())
            self._label_right.setStyleSheet(
                f"QLabel{{margin-left: 3px; margin-right: 0px; padding: 0px; {theme_css(port_theme)}}} "
                f"QLabel:focus{{{theme_css(port_theme.selected)}}}")

    def set_check_state(self, check_state: ConnState):
        self._check_box.setCheckState(
            check_state.to_qt_check_state())

    def connection_asked_from_box(self, po: Union[Port, Portgroup], yesno: bool):
        self._parent.connection_asked_from_box(self._p_object, yesno)
    
    def mousePressEvent(self, event):
        self._check_box.nextCheckState()
        
    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return):
            self._check_box.nextCheckState()
            return
        QFrame.keyPressEvent(self, event)
        
    def enterEvent(self, event):
        super().enterEvent(event)
        self.setFocus()
        
    def focusInEvent(self, event: QFocusEvent):
        super().focusInEvent(event)
        text_color = self._theme.selected.text_color().name()
        self._label_left.setStyleSheet(f"QLabel{{color: {text_color}}}")
        
    def focusOutEvent(self, event: QFocusEvent):
        super().focusOutEvent(event)
        text_color = self._theme.text_color().name()
        self._label_left.setStyleSheet(f"QLabel{{color: {text_color}}}")


class DangerousMenu(QMenu):
    def __init__(self, parent, po: Union[Port, Portgroup]):
        QMenu.__init__(self, parent)
        if po.full_type[1] is PortSubType.CV:
            dangerous_name = _translate(
                'patchbay', 'Audio | DANGEROUS !!!')
        else:
            dangerous_name = _translate(
                'patchbay', 'CV | DANGEROUS !!!')
        
        self.setTitle(dangerous_name)
        self.setIcon(QIcon.fromTheme('emblem-warning'))


class GroupConnectMenu(QMenu):
    def __init__(self, group: Group, po: Union[Port, Portgroup],
                 parent: 'ConnectMenu'):
        self._group = group
        short_group_name = group.cnv_name        
        if len(short_group_name) > 15 and '/' in short_group_name:
            short_group_name = short_group_name.partition('/')[2]

        QMenu.__init__(self, short_group_name, parent)
        self.hovered.connect(self._mouse_hover_menu)
        self.aboutToShow.connect(self._about_to_show)
        
        self._connect_menu = parent
        if isinstance(parent, DangerousMenu):
            self._connect_menu = parent.parent()
        
        theme = canvas.theme.box        
        if group.cnv_box_type is BoxType.CLIENT:
            theme = theme.client
        elif group.cnv_box_type is BoxType.HARDWARE:
            theme = theme.hardware

        bg_color = theme.background_color().name(QColor.NameFormat.HexArgb)
        border_color = theme.fill_pen().color().name(QColor.NameFormat.HexArgb)
        
        self.setStyleSheet(
            "QMenu{"
                f"background-color:{bg_color}; "
                f"border: 2px solid {border_color}; "
                f"border-radius:4px"
            "}")
        self.setMinimumWidth(70)
        self.setMinimumHeight(50)
        
        self._check_frame_templates = list[tuple]()
        self._elements_added = False

    def _mouse_hover_menu(self, action: QWidgetAction):
        # for better use with keyboard
        action.defaultWidget().setFocus()
    
    def _about_to_show(self):
        self.setMinimumWidth(self._connect_menu.group_min_width)

        if not self._elements_added:
            for cft in self._check_frame_templates:
                check_frame = CheckFrame(*cft)
                self._connect_menu._check_frames[cft[0]] = check_frame

                action = QWidgetAction(self)
                action.setDefaultWidget(check_frame)
                self.addAction(action)
            self._elements_added = True
            self._connect_menu._patch_may_have_change()

        self._connect_menu.set_group_min_width(self.sizeHint().width())
    
    def prepare_check_frame(self, *args):
        self._check_frame_templates.append(args)


class AbstractConnectionsMenu(QMenu):
    def __init__(self, mng: 'PatchbayManager',
                 po: Union[Portgroup, Port], parent=None):
        QMenu.__init__(self, '', parent)
        mng.sg.patch_may_have_changed.connect(self._patch_may_have_change)

        self._mng = mng
        self._po = po
        
        self._check_frames = dict[Union[Port, Portgroup], CheckFrame]()
        self.group_min_width = 50
    
    def exec(self, start_pos: QPoint) -> QAction:
        action = super().exec(start_pos)
        if action is None:
            canvas.menu_click_pos = QCursor().pos()
        return action
    
    def _display_name(self, port: Port) -> str:
        if port.full_type == (PortType.AUDIO_JACK, PortSubType.CV):
            return f"CV | {port.cnv_name}"
        return port.cnv_name
    
    def _ports(self, po: Union[Port, Portgroup, None]=None) -> list[Port]:
        if po is not None:
            if isinstance(po, Portgroup):
                return list(po.ports)
            return [po]
        
        if isinstance(self._po, Portgroup):
            return list(self._po.ports)
        return [self._po]
    
    def _port_mode(self) -> PortMode:
        if isinstance(self._po, Portgroup):
            return self._po.port_mode
        return self._po.mode

    def _get_connection_status(
            self, po_conns: list[Connection],
            out_ports: list[Port], in_ports: list[Port]) -> ConnState:
        if not po_conns:
            return ConnState.NONE

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
            return ConnState.IRREGULAR
        return ConnState.REGULAR

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

    def set_group_min_width(self, value: int):
        self.group_min_width = max(self.group_min_width, value)


class ConnectMenu(AbstractConnectionsMenu):
    def __init__(self, mng: 'PatchbayManager',
                 po: Union[Portgroup, Port], parent=None):
        AbstractConnectionsMenu.__init__(self, mng, po, parent)
        self.setTitle(_translate('patchbay', 'Connect'))
        dark = '-dark' if is_dark_theme(self) else ''
        self.setIcon(
            QIcon(QPixmap(':scalable/breeze%s/lines-connector' % dark)))
        
        self._gp_menus = list[GroupConnectMenu]()

        has_dangerous = self._fill_all_ports()
        if has_dangerous:
            self._fill_all_ports(dangerous=True)

        self._patch_may_have_change()
    
    def _is_connection_dangerous(self, port: Port) -> bool:
        t_type, t_subtype = self._po.full_type
        p_type, p_subtype = port.full_type
        
        if t_type is not PortType.AUDIO_JACK:
            return False
        
        if t_subtype is p_subtype:
            return False
        
        if t_subtype is PortSubType.CV:
            return self._port_mode() is PortMode.OUTPUT
        
        if p_subtype is PortSubType.CV:
            return port.mode is PortMode.OUTPUT
        
        return False
    
    def _fill_all_ports(self, dangerous=False) -> bool:
        main_menu = self
        if dangerous:
            main_menu = DangerousMenu(self, self._po)
        
        has_dangerous_ports = False

        for group in self._mng.groups:
            gp_menu: GroupConnectMenu = None
            last_portgrp_id = 0
            
            for port in group.ports:
                if (port.type is self._po.type
                        and port.mode is self._port_mode().opposite()):
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
                        self._gp_menus.append(gp_menu)

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
                                
                                gp_menu.prepare_check_frame(
                                    portgroup, portgrp_name, end_name, self)
                                break
                        else:
                            continue
                        
                        last_portgrp_id = port.portgroup_id
                    
                    elif isinstance(self._po, Port) and port.portgroup_id:
                        pg_pos, pg_len = group.port_pg_pos(port.port_id)
                        gp_menu.prepare_check_frame(
                            port, self._display_name(port),
                            '', self, pg_pos, pg_len)
               
                    else:
                        gp_menu.prepare_check_frame(
                            port, self._display_name(port), '', self)

            if gp_menu is not None:
                main_menu.addMenu(gp_menu)

        if dangerous:
            self.addSeparator()
            self.addMenu(main_menu)

        return has_dangerous_ports

    def leaveEvent(self, event: QMouseEvent):
        # prevent to close the menu accidentaly when the mouse 
        # leaves the menu area
        event.ignore()

class DisconnectMenu(AbstractConnectionsMenu):
    def __init__(self, mng: 'PatchbayManager', po: Union[Port, Portgroup],
                 parent: QMenu):
        AbstractConnectionsMenu.__init__(self, mng, po, parent)
        self.hovered.connect(self._mouse_hover_menu)

        self._one_frame_checked = False

        self.setTitle(_translate('patchbay', 'Disconnect'))
        dark = '-dark' if is_dark_theme(self) else ''
        self.setIcon(
            QIcon(QPixmap(':scalable/breeze%s/lines-disconnector' % dark)))
        
        self.setSeparatorsCollapsible(False)

        self.disco_all_act = QAction(_translate('patchbay', 'Disconnect All'))
        self._fill_all_ports()
        self._patch_may_have_change()
        
    def _fill_all_ports(self):
        if self._port_mode() is PortMode.OUTPUT:
            conn_ports = [c.port_in for c in self._mng.connections
                          if c.port_out in self._ports()]
        else:
            conn_ports = [c.port_out for c in self._mng.connections
                          if c.port_in in self._ports()]
        
        skip_separator = True
        
        for group in self._mng.groups:
            group_section_exists = False
            last_portgrp_id = 0
            
            for port in group.ports:
                if port not in conn_ports:
                    continue

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
                    spacer = QSpacerItem(2, 2, QSizePolicy.Policy.Expanding,
                                         QSizePolicy.Policy.Minimum)
                    widget.layout.addSpacerItem(spacer)
                    
                    action = QWidgetAction(self)
                    action.setDefaultWidget(widget)
                    action.setSeparator(True)
                    
                    # add separator if it is not the fisrt group
                    if not skip_separator:
                        self.addSeparator()
                    skip_separator = False
                    
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
                    check_frame = CheckFrame(
                        port, self._display_name(port),'', self)
                    self._check_frames[port] = check_frame

                po_action = QWidgetAction(self)
                po_action.setDefaultWidget(check_frame)
                self.addAction(po_action)
        
        if len(self._check_frames) >= 2:
            self.addSeparator()
            self.addAction(self.disco_all_act)

    def _mouse_hover_menu(self, action: QWidgetAction):
        # for better use with keyboard
        if not isinstance(action, QWidgetAction):
            return

        action.defaultWidget().setFocus()
    
    def connection_asked_from_box(self, po: Union[Port, Portgroup], yesno: bool):
        super().connection_asked_from_box(po, yesno)
        self._one_frame_checked = True
        
        if len(self._check_frames) < 2:
            parent: QMenu = self.parent()
            parent.close()
    
    def has_connections(self) -> bool:
        return bool(self._check_frames)

    def enterEvent(self, event: QEvent):
        super().enterEvent(event)
        self._one_frame_checked = False

    # close the disconnect menu if at least one port has been unchecked
    def leaveEvent(self, event: QEvent):
        super().leaveEvent(event)
        if self._one_frame_checked:
            parent: QMenu = self.parent()
            parent.close()


class PoMenu(AbstractConnectionsMenu):
    def __init__(self, mng: 'PatchbayManager', po: Union[Port, Portgroup]):
        AbstractConnectionsMenu.__init__(self, mng, po)
        self.conn_menu = ConnectMenu(mng, po)
        self.disconn_menu = DisconnectMenu(mng, po, self)   
        
        dark = '-dark' if is_dark_theme(self) else ''
        disconn_icon = QIcon(
            QPixmap(':scalable/breeze%s/lines-disconnector' % dark))
        self.disconn_menu.setIcon(disconn_icon)
        
        self.addMenu(self.conn_menu)
        if self.disconn_menu.has_connections():
            self.addMenu(self.disconn_menu)
        
        disco_all_act = self.addAction(
            _translate('patchbay', 'Disconnect All'))
        disco_all_act.setIcon(disconn_icon)
        
        existing_conns = self._get_existing_conns_flag()
        disco_all_act.setEnabled(
            bool(existing_conns & ExistingConns.VISIBLE))
        if existing_conns & ExistingConns.HIDDEN:
            disco_all_act.setText(
                _translate('patchbay', 'Disconnect All (visible)'))
        
        disco_all_act.triggered.connect(self._disconnect_all_visible)
        self.disconn_menu.disco_all_act.triggered.connect(self._disconnect_all)

        # Add clipboard menu
        self.clipboard_menu = QMenu(_translate('patchbay', 'Clipboard'), self)
        self.clipboard_menu.setIcon(QIcon.fromTheme('edit-paste'))
        
        cb_cut_act = self.clipboard_menu.addAction(
            _translate('patchbay', 'Cut connections'))
        cb_copy_act = self.clipboard_menu.addAction(
            _translate('patchbay', 'Copy connections'))
        cb_paste_act = QAction(
            _translate('patchbay', 'Paste connections'),
            self.clipboard_menu)

        cb_cut_act.setIcon(QIcon.fromTheme('edit-cut'))
        cb_copy_act.setIcon(QIcon.fromTheme('edit-copy'))
        cb_paste_act.setIcon(QIcon.fromTheme('edit-paste'))
        
        cb_cut_act.triggered.connect(self._cb_cut)
        cb_copy_act.triggered.connect(self._cb_copy)
        cb_paste_act.triggered.connect(self._cb_paste)
        
        if not existing_conns & ExistingConns.VISIBLE:
            cb_cut_act.setEnabled(False)
            cb_copy_act.setEnabled(False)

        if self._mng.connections_clipboard.is_compatible(self._ports()):
            self.clipboard_menu.addAction(cb_paste_act)
        
        self.addMenu(self.clipboard_menu)
        
        self.addSeparator()
        
        # Add mono <-> stereo tools
        if self._po.full_type == (PortType.AUDIO_JACK, PortSubType.REGULAR):
            if isinstance(self._po, Portgroup):
                self.split_to_monos_act = QAction(
                    _translate('patchbay', 'Split to Monos'))
                self.split_to_monos_act.triggered.connect(
                    self._split_to_monos)
                self.addAction(self.split_to_monos_act)
            
            elif isinstance(self._po, Port) and not self._po.portgroup_id:
                set_as_stereo_menu = QMenu(
                    _translate('patchbay', 'Set as stereo with...'),
                    self)
                
                for group in self._mng.groups:
                    if group.group_id != self._po.group_id:
                        continue
                    
                    previous_port: Port = None
                    next_port: Port = None
                    port_found = False
                    
                    for port in group.ports:
                        if port.full_type != self._po.full_type:
                            continue
                        
                        if port.mode is not self._po.mode:
                            continue
                        
                        if not port_found:
                            if port is self._po:
                                port_found = True
                            elif port.portgroup_id:
                                previous_port = None
                            else:
                                previous_port = port
                        else:
                            if not port.portgroup_id:
                                next_port = port
                            break
                
                self.mono_ports_acts = list[QAction]()
                
                for mono_port in (previous_port, next_port):
                    if mono_port is None:
                        continue
                    
                    act = QAction(mono_port.cnv_name, set_as_stereo_menu)
                    act.setData(mono_port)
                    act.triggered.connect(self._set_as_stereo_with)
                    self.mono_ports_acts.append(act)
                    set_as_stereo_menu.addAction(act)
                    
                if previous_port or next_port:
                    self.addMenu(set_as_stereo_menu)
        
        # add Rename
        # if isinstance(self._po, Port):
        port_rename_act = self.addAction(_translate('patchbay', 'Rename'))
        port_rename_act.setIcon(QIcon.fromTheme('edit-rename'))
        port_rename_act.triggered.connect(self._rename)
        
        # add info dialog command
        if isinstance(self._po, Port):
            port_info_act = self.addAction(
                _translate('patchbay', "Get &Info"))
            port_info_act.setIcon(QIcon.fromTheme('dialog-information'))            
            port_info_act.triggered.connect(self._display_port_infos)
    
    def _get_existing_conns_flag(self) -> ExistingConns:
        existing_conns = ExistingConns.NONE

        if self._port_mode() is PortMode.OUTPUT:
            for conn in self._mng.connections:
                if conn.port_out in self._ports():
                    if conn.in_canvas:
                        existing_conns |= ExistingConns.VISIBLE
                    else:
                        existing_conns |= ExistingConns.HIDDEN
                        
            return existing_conns
        
        if self._port_mode() is PortMode.INPUT:
            for conn in self._mng.connections:
                if conn.port_in in self._ports():
                    if conn.in_canvas:
                        existing_conns |= ExistingConns.VISIBLE
                    else:
                        existing_conns |= ExistingConns.HIDDEN
                        
            return existing_conns

    def _disconnect_all(self, visible_only=False):
        if visible_only:
            if self._port_mode() is PortMode.OUTPUT:
                conn_ids = [c.connection_id for c in self._mng.connections
                            if c.in_canvas and c.port_out in self._ports()]
            else:
                conn_ids = [c.connection_id for c in self._mng.connections
                            if c.in_canvas and c.port_in in self._ports()]
        else:   
            if self._port_mode() is PortMode.OUTPUT:
                conn_ids = [c.connection_id for c in self._mng.connections
                            if c.port_out in self._ports()]
            else:
                conn_ids = [c.connection_id for c in self._mng.connections
                            if c.port_in in self._ports()]

        for conn_id in conn_ids:
            canvas.callback(CallbackAct.PORTS_DISCONNECT, conn_id)

    @Slot()
    def _disconnect_all_visible(self):
        self._disconnect_all(visible_only=True)

    @Slot()
    def _cb_cut(self):
        self._mng.connections_clipboard.cb_cut(self._ports())
    
    @Slot()
    def _cb_copy(self):
        self._mng.connections_clipboard.cb_copy(self._ports())

    @Slot()
    def _cb_paste(self):
        self._mng.connections_clipboard.cb_paste(self._ports())

    @Slot()
    def _split_to_monos(self):
        if not isinstance(self._po, Portgroup):
            return
        
        canvas.callback(CallbackAct.PORTGROUP_REMOVE,
                        self._po.group_id, self._po.portgroup_id)
        
    @Slot()
    def _set_as_stereo_with(self):
        port: Port = self.sender().data()
        
        canvas.callback(CallbackAct.PORTGROUP_ADD, port.group_id,
                        port.mode, port.type,
                        (self._po.port_id, port.port_id))
    
    @Slot()
    def _rename(self):
        dialog = PrettyNameDialog(self._po)
        if not dialog.exec():
            return
        
        pretty_name = dialog.pretty_name()
        save_in_jack = dialog.save_in_metadata()
        
        if isinstance(self._po, Port):
            self._mng.pretty_names.save_port(
                self._po.full_name_id_free, pretty_name,
                self._po.mdata_pretty_name)
            if self._po.type.is_jack:
                self._mng.pretty_diff_checker.port_pretty_name_changed(
                    self._po.full_name)
            self._po.rename_in_canvas()
            
            canvas.callback(
                CallbackAct.PORT_RENAME, self._po.group_id, self._po.port_id,
                pretty_name, save_in_jack)

        elif isinstance(self._po, Portgroup):
            pg_name, suffixes = portgroup_name_splitted(
                *[p.cnv_name for p in self._po.ports])
            
            for i in range(len(self._po.ports)):
                port = self._po.ports[i]
                suffix = suffixes[i]
                if pretty_name:
                    port_pretty_name = f'{pretty_name} {suffix}'
                else:
                    # clear portgroup, send empty metadata value
                    port_pretty_name = ''

                self._mng.pretty_names.save_port(
                    port.full_name_id_free,
                    port_pretty_name, port.mdata_pretty_name)
                if port.type.is_jack:
                    self._mng.pretty_diff_checker.port_pretty_name_changed(
                        port.full_name)
                port.rename_in_canvas()

                canvas.callback(
                    CallbackAct.PORT_RENAME, port.group_id, port.port_id,
                    port_pretty_name, save_in_jack)

    @Slot()
    def _display_port_infos(self):
        if not isinstance(self._po, Port):
            return
        
        canvas.callback(
            CallbackAct.PORT_INFO, self._po.group_id, self._po.port_id)
        