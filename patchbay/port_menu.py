
from ast import Call
from typing import TYPE_CHECKING, Union
from PyQt5.QtWidgets import (
    QMenu, QCheckBox, QFrame, QLabel, QHBoxLayout,
    QSpacerItem, QSizePolicy, QWidgetAction)
from PyQt5.QtGui import QIcon, QColor, QKeyEvent
from PyQt5.QtCore import Qt

from .patchcanvas import canvas, CallbackAct
from .patchcanvas.theme import StyleAttributer
from .base_elements import Port, Portgroup, PortType, PortSubType, PortMode

if TYPE_CHECKING:
    from patchbay_manager import PatchbayManager


def theme_css(theme: StyleAttributer) -> str:
    pen = theme.fill_pen()
    
    return (f"background-color: {theme.background_color().name(QColor.HexArgb)};"
            f"color: {theme.text_color().name(QColor.HexArgb)};"
            f"border: {pen.widthF()}px solid {pen.color().name(QColor.HexArgb)}")

    
class PortCheckBox(QCheckBox):
    def __init__(self, p_object:  Union[Port, Portgroup],
                 parent: 'SubMenu', pg_pos=0, pg_len=1):
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
                 parent: 'SubMenu', pg_pos=0, pg_len=1):
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
                radius_text = "border-bottom-left-radius: 0px; border-bottom-right-radius: 0px"
            elif self._pg_pos + 1 == self._pg_len:
                margin_texts.pop(TOP)
                radius_text = "border-top-left-radius: 0px; border-top-right-radius: 0px"
                
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
            if po.port_type is PortType.AUDIO_JACK:
                port_theme = port_theme.audio
            elif po.port_type is PortType.MIDI_JACK:
                port_theme = port_theme.midi

            self._label_right.setFont(port_theme.font())
            self._label_right.setStyleSheet(
                f"QLabel{{margin-left: 3px; margin-right: 0px; padding: 0px; {theme_css(port_theme)}}} "
                f"QLabel:focus{{{theme_css(port_theme.selected)}}}")

    def set_check_state(self, check_state: int):
        self._check_box.setCheckState(check_state)

    def connection_asked_from_box(self, po: Union[Port, Portgroup], yesno: bool):
        po = self._p_object
        self._parent.connection_asked_from_box(po, yesno)
    
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


class PortMenu(QMenu):
    def __init__(self, mng: 'PatchbayManager', group_id: int, port_id: int):
        self._mng = mng
        mng.sg.connection_added.connect(self._connection_added)
        mng.sg.connection_removed.connect(self._connection_removed)
        QMenu.__init__(self)
        
        conn_menu = QMenu('Connect', self)        
        self._port = self._mng.get_port_from_id(group_id, port_id)
        if self._port is None:
            return
        
        for group in mng.groups:
            gp_menu = None
            
            for port in group.ports:
                if (port.type is self._port.type
                        and port.mode() is self._port.mode().opposite()):
                    if gp_menu is None:
                        gp_menu = QMenu(group.name, self)
                        gp_menu.setIcon(QIcon.fromTheme(group.client_icon))
                    # gp_menu.addAction(port.short_name())
                    pg_pos, pg_len = group.port_pg_pos(port.port_id)
                    print('dkdk', pg_pos, pg_len, port.display_name)
                    check_frame = CheckFrame(port, port.display_name, '', self,
                                             pg_pos, pg_len)
                    action = QWidgetAction(self)
                    action.setDefaultWidget(check_frame)
                    gp_menu.addAction(action)
                    
                    if self._port.mode() is PortMode.OUTPUT:
                        for conn in mng.connections:
                            if (conn.port_out is self._port and conn.port_in is port):
                                check_frame.set_check_state(2)
                    elif self._port.mode() is PortMode.INPUT:
                        for conn in mng.connections:
                            if (conn.port_out is port and conn.port_in is self._port):
                                check_frame.set_check_state(2)

            if gp_menu is not None:
                conn_menu.addMenu(gp_menu)

        self.addMenu(conn_menu)
    
    def _connection_added(self, connection_id: int):
        for conn in self._mng.connections:
            if (conn.connection_id == connection_id
                    and ((self._port.mode() is PortMode.OUTPUT
                          and conn.port_out is self._port)
                         or (self._port.mode() is PortMode.INPUT
                             and conn.port_in is self._port))):
                pass
    
    def _connection_removed(self, connection_id: int):
        pass
    
    def connection_asked_from_box(self, po: Union[Port, Portgroup], yesno: bool):
        if self._port.mode() is PortMode.OUTPUT:
            group_out_id = self._port.group_id
            port_out_id = self._port.port_id
            group_in_id = po.group_id
            port_in_id = po.port_id
        else:
            group_out_id = po.group_id
            port_out_id = po.port_id
            group_in_id = self._port.group_id
            port_in_id = self._port.port_id

        if yesno:
            canvas.callback(CallbackAct.PORTS_CONNECT,
                            group_out_id, port_out_id, group_in_id, port_in_id)
        else:
            for conn in self._mng.connections:
                if (conn.port_out.group_id == group_out_id
                        and conn.port_out.port_id == port_out_id
                        and conn.port_in.group_id == group_in_id
                        and conn.port_in.port_id == port_in_id):
                    canvas.callback(CallbackAct.PORTS_DISCONNECT, conn.connection_id)
                    break