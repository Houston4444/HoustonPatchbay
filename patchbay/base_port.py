from typing import TYPE_CHECKING

from .patchcanvas.patshared import PortMode, PortType, PortSubType
from .patchcanvas import patchcanvas
from .base_elements import JackPortFlag
from .base_connection import Connection

if TYPE_CHECKING:
    from .patchbay_manager import PatchbayManager
    from .base_group import Group


class Port:
    display_name = ''
    group_id = -1
    portgroup_id = 0
    prevent_stereo = False
    last_digit_to_add = ''
    in_canvas = False
    order = None
    uuid = 0
    'contains the real JACK uuid'
    
    cnv_name = ''

    # given by JACK metadatas
    pretty_name = ''
    mdata_portgroup = ''
    mdata_signal_type = ''

    def __init__(self, manager: 'PatchbayManager', port_id: int, name: str,
                 port_type: PortType, flags: int, uuid: int):
        self.manager = manager
        self.port_id = port_id
        self.full_name = name
        self.type = port_type
        self.flags = flags
        self.uuid = uuid
        self.subtype = PortSubType.REGULAR
        self.group: 'Group' = None

        if (self.type is PortType.AUDIO_JACK
                and self.flags & JackPortFlag.IS_CONTROL_VOLTAGE):
            self.subtype = PortSubType.CV
        elif (self.type is PortType.MIDI_JACK
                and self.full_name.startswith(('a2j:', 'Midi-Bridge:'))):
            self.subtype = PortSubType.A2J
            
        self.conns_hidden_in_canvas = set[Connection]()

    def __repr__(self) -> str:
            return f"Port({self.full_name})"

    def mode(self) -> PortMode:
        if self.flags & JackPortFlag.IS_OUTPUT:
            return PortMode.OUTPUT
        elif self.flags & JackPortFlag.IS_INPUT:
            return PortMode.INPUT
        else:
            return PortMode.NULL

    def full_type(self) -> tuple[PortType, PortSubType]:
        return (self.type, self.subtype)
    
    def short_name(self) -> str:
        if (self.type is PortType.MIDI_ALSA
                and self.full_name.startswith((':ALSA_IN:', ':ALSA_OUT:'))):
            return ':'.join(self.full_name.split(':')[5:])
        
        if self.full_name.startswith('a2j:'):
            long_name = self.full_name.partition(':')[2]
            if ': ' in long_name:
                # normal case for a2j
                return long_name.partition(': ')[2]

        if self.full_name.startswith('Midi-Bridge:'):
            # suppress 'Midi-Bridge:' at port name begginning
            long_name = self.full_name.partition(':')[2]
            if ') ' in long_name:
                # normal case, name is after ') '
                return long_name.partition(') ')[2]

            if ': ' in long_name:
                # pipewire jack.filter_name = True
                # Midi-bridge names starts with 'MidiBridge:ClientName:'
                return long_name.partition(': ')[2]

        return self.full_name.partition(':')[2]

    def add_the_last_digit(self):
        self.display_name += ' ' + self.last_digit_to_add
        self.last_digit_to_add = ''
        self.rename_in_canvas()

    def add_to_canvas(self, ignore_gpos=False, hidden_sides=PortMode.NULL):
        if self.manager.very_fast_operation:
            return
        
        if self.in_canvas:
            return

        cnv_name = self.display_name
        
        if self.pretty_name:
            cnv_name = self.pretty_name
        
        if not self.manager.use_graceful_names:
            cnv_name = self.short_name()

        self.cnv_name = cnv_name

        if not self.manager.port_type_shown(self.full_type()):
            return

        if ignore_gpos:
            if hidden_sides & self.mode():
                return
        else:
            if self.group.current_position.hidden_port_modes() & self.mode():
                return

        patchcanvas.add_port(
            self.group_id, self.port_id, cnv_name,
            self.mode(), self.type, self.subtype)

        self.in_canvas = True
        
        if self.conns_hidden_in_canvas:
            visible_conns = set[Connection]()
            for conn in self.conns_hidden_in_canvas:
                for other_port in (conn.port_out, conn.port_in):
                    if other_port is self:
                        continue
                    
                    if other_port.in_canvas:
                        visible_conns.add(conn)
                        other_port.set_hidden_conn_in_canvas(conn, False)
            
            for conn in visible_conns:
                self.set_hidden_conn_in_canvas(conn, False)
                
        if self.conns_hidden_in_canvas:
            patchcanvas.port_has_hidden_connection(
                self.group_id, self.port_id,
                bool(self.conns_hidden_in_canvas))

    def remove_from_canvas(self):
        if self.manager.very_fast_operation:
            return
        
        if not self.in_canvas:
            return

        patchcanvas.remove_port(self.group_id, self.port_id)
        self.in_canvas = False

        if self.conns_hidden_in_canvas:
            for conn in self.conns_hidden_in_canvas:
                for other_port in (conn.port_out, conn.port_in):
                    if other_port is self:
                        continue

    def rename_in_canvas(self):
        display_name = self.display_name
        if self.pretty_name:
            display_name = self.pretty_name

        if not self.manager.use_graceful_names:
            display_name = self.short_name()

        self.cnv_name = display_name

        if not self.in_canvas:
            return
        
        patchcanvas.rename_port(
            self.group_id, self.port_id, display_name)

    def select_in_canvas(self):
        if not self.in_canvas:
            return
        
        patchcanvas.select_port(self.group_id, self.port_id)

    def set_hidden_conn_in_canvas(self, conn: Connection, yesno: bool):
        has_hidden_conns = bool(self.conns_hidden_in_canvas)

        if yesno:
            self.conns_hidden_in_canvas.add(conn)
        elif conn in self.conns_hidden_in_canvas:
            self.conns_hidden_in_canvas.remove(conn)
        
        if not self.in_canvas:
            return

        if has_hidden_conns == bool(self.conns_hidden_in_canvas):
            return

        patchcanvas.port_has_hidden_connection(
            self.group_id, self.port_id,
            bool(self.conns_hidden_in_canvas))

    def __lt__(self, other: 'Port') -> bool:
        if self.type != other.type:
            return (self.type < other.type)

        if self.subtype is not other.subtype:
            return self.subtype < other.subtype

        if self.order is None and other.order is None:
            return self.port_id < other.port_id
        if self.order is None:
            return False
        if other.order is None:
            return True

        return bool(self.order < other.order)
