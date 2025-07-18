from typing import TYPE_CHECKING
import time

from patshared import PortMode, PortType, PortSubType, Naming, JackMetadata
from ..patchcanvas import patchcanvas
from .elements import JackPortFlag
from .connection import Connection

if TYPE_CHECKING:
    from ..patchbay_manager import PatchbayManager
    from .group import Group


class Port:
    graceful_name = ''
    group_id = -1
    portgroup_id = 0
    prevent_stereo = False
    last_digit_to_add = ''
    in_canvas = False
    order = None
    uuid = 0
    'contains the real JACK uuid'

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

    @property
    def mode(self) -> PortMode:
        if self.flags & JackPortFlag.IS_OUTPUT:
            return PortMode.OUTPUT
        if self.flags & JackPortFlag.IS_INPUT:
            return PortMode.INPUT
        return PortMode.NULL

    @property
    def full_type(self) -> tuple[PortType, PortSubType]:
        return (self.type, self.subtype)
    
    @property
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

    @property
    def cnv_name(self):
        'The name of this port in the canvas, depending on Naming options'
        if self.manager.naming & Naming.METADATA_PRETTY:
            mdata_pretty_name = self.mdata_pretty_name
            if mdata_pretty_name:
                return mdata_pretty_name
        
        if self.manager.naming & Naming.INTERNAL_PRETTY:
            pretty_name = self.pretty_name
            if pretty_name:
                return pretty_name
        
        if self.manager.naming & Naming.GRACEFUL:
            return self.graceful_name

        return self.short_name

    @property
    def mdata_pretty_name(self) -> str:
        if not self.uuid:
            return ''
        return self.manager.jack_metadatas.pretty_name(self.uuid)

    @property
    def mdata_portgroup(self) -> str:
        if not self.uuid:
            return ''
        return self.manager.jack_metadatas.str_for_key(
            self.uuid, JackMetadata.PORT_GROUP)

    @property
    def mdata_signal_type(self) -> str:
        if not self.uuid:
            return ''
        return self.manager.jack_metadatas.str_for_key(
            self.uuid, JackMetadata.SIGNAL_TYPE)

    @property
    def pretty_name(self) -> str:
        'The internal pretty-name of this port, if it exists'
        return self.manager.pretty_names.pretty_port(self.full_name_id_free)

    @property
    def alsa_client_id(self) -> int:
        if self.type is not PortType.MIDI_ALSA:
            return -1
        splitted_name = self.full_name.split(':')
        if len(splitted_name) < 6:
            return -1
        alsa_client_id_str = splitted_name[2]
        if not alsa_client_id_str.isdigit():
            return -1
        return int(alsa_client_id_str)

    @property
    def full_name_id_free(self) -> str:
        'full_name without alsa client or port id, useful for pretty_names'
        if self.type is PortType.MIDI_ALSA:
            names = self.full_name.split(':')
            return ':'.join(names[0:2] + names[4:])
        return self.full_name

    def add_the_last_digit(self):
        self.graceful_name += ' ' + self.last_digit_to_add
        self.last_digit_to_add = ''
        self.rename_in_canvas()

    def add_to_canvas(self, ignore_gpos=False, hidden_sides=PortMode.NULL):
        if self.manager.very_fast_operation:
            return
        
        if self.in_canvas:
            return

        if not self.manager.port_type_shown(self.full_type):
            return

        if ignore_gpos:
            if hidden_sides & self.mode:
                return
        else:
            if self.group.current_position.hidden_port_modes() & self.mode:
                return

        patchcanvas.add_port(
            self.group_id, self.port_id, self.cnv_name,
            self.mode, self.type, self.subtype)

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
        if not self.in_canvas:
            return
        
        patchcanvas.rename_port(
            self.group_id, self.port_id, self.cnv_name)

    def select_in_canvas(self):
        if not self.in_canvas:
            return
        
        patchcanvas.select_port(self.group_id, self.port_id)

    def set_hidden_conn_in_canvas(self, conn: Connection, yesno: bool):
        had_hidden_conns = bool(self.conns_hidden_in_canvas)

        if yesno:
            self.conns_hidden_in_canvas.add(conn)
        else:
            self.conns_hidden_in_canvas.discard(conn)
        
        if not self.in_canvas:
            return

        if had_hidden_conns == bool(self.conns_hidden_in_canvas):
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
