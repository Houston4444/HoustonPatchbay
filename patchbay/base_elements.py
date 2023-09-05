from dataclasses import dataclass
from enum import IntFlag, IntEnum, auto
from typing import TYPE_CHECKING, Any, Union, Optional

from .patchcanvas import (patchcanvas, PortMode, PortType, BoxType,
                          BoxLayoutMode, BoxSplitMode, PortSubType)

if TYPE_CHECKING:
    from .patchbay_manager import PatchbayManager
    from .base_group import Group

# Port Flags as defined by JACK
class JackPortFlag(IntFlag):
    IS_INPUT = 0x01
    IS_OUTPUT = 0x02
    IS_PHYSICAL = 0x04
    CAN_MONITOR = 0x08
    IS_TERMINAL = 0x10
    IS_CONTROL_VOLTAGE = 0x100


class GroupPosFlag(IntFlag):
    # used in some config files,
    # it explains why some numbers are missing.
    NONE = 0x00
    SPLITTED = 0x04
    WRAPPED_INPUT = 0x10
    WRAPPED_OUTPUT = 0x20
    HAS_BEEN_SPLITTED = 0x40


class PortTypesViewFlag(IntFlag):
    NONE = 0x00
    AUDIO = 0x01
    MIDI = 0x02
    CV = 0x04
    VIDEO = 0x08
    ALSA = 0x10
    ALL = AUDIO | MIDI | CV | VIDEO | ALSA


@dataclass
class TransportPosition:
    frame: int
    rolling: bool
    valid_bbt: bool
    bar: int
    beat: int
    tick: int
    beats_per_minutes: float


class TransportViewMode(IntEnum):
    HOURS_MINUTES_SECONDS = 0
    BEAT_BAR_TICK = 1
    FRAMES = 2


class ToolDisplayed(IntFlag):
    PORT_TYPES_VIEW = auto()
    TRANSPORT_CLOCK = auto()
    TRANSPORT_PLAY_STOP = auto()
    TRANSPORT_TEMPO = auto()
    ZOOM_SLIDER = auto()
    BUFFER_SIZE = auto()
    SAMPLERATE = auto()
    LATENCY = auto()
    XRUNS = auto()
    DSP_LOAD = auto()
    ALL = (PORT_TYPES_VIEW
           | TRANSPORT_CLOCK
           | TRANSPORT_PLAY_STOP
           | TRANSPORT_TEMPO
           | ZOOM_SLIDER
           | BUFFER_SIZE
           | SAMPLERATE
           | LATENCY
           | XRUNS
           | DSP_LOAD)
    
    def to_save_string(self) -> str:
        ''' returns a string containing all flags names
            separated with pipe symbol.'''
        all_strs = list[str]()
        
        for flag in ToolDisplayed:
            if flag is ToolDisplayed.ALL:
                continue

            if self & flag:
                all_strs.append(flag.name)
            else:
                all_strs.append('~' + flag.name)
        
        return '|'.join(all_strs)
    
    def filtered_by_string(self, string: str) -> 'ToolDisplayed':
        '''returns another ToolDisplayed with value filtered
           by string where string contains flags names separated with pipe symbol
           as given by to_save_string method.'''
        return_td = ToolDisplayed(self.value)
        
        for disp_str in string.split('|'):
            delete = False
            if disp_str.startswith('~'):
                delete = True
                disp_str = disp_str[1:]

            if disp_str in ToolDisplayed._member_names_:
                if delete:
                    return_td &= ~ToolDisplayed[disp_str]
                else:
                    return_td |= ToolDisplayed[disp_str]

        return return_td


class BoxFlag(IntFlag):
    NONE = 0x00
    WRAPPED = auto()
    HIDDEN = auto()
    

class BoxPos:
    pos: tuple[int, int]
    zone: str = ''
    layout_mode: BoxLayoutMode = BoxLayoutMode.AUTO
    flags: BoxFlag = BoxFlag.NONE

    def __init__(self) -> None:
        self.pos = (0, 0)
    
    def _set_flag(self, flag: BoxFlag, yesno: bool):
        if yesno:
            self.flags |= flag
        else:
            self.flags &= ~flag
    
    def is_wrapped(self) -> bool:
        return bool(self.flags & BoxFlag.WRAPPED)
    
    def _is_hidden(self) -> bool:
        return bool(self.flags & BoxFlag.HIDDEN)

    def set_wrapped(self, yesno: bool):
        self._set_flag(BoxFlag.WRAPPED, yesno)
            
    def set_hidden(self, yesno: bool):
        self._set_flag(BoxFlag.HIDDEN, yesno)


class GroupPos:
    port_types_view: PortTypesViewFlag = PortTypesViewFlag.NONE
    group_name: str = ""
    null_zone: str = ""
    in_zone: str = ""
    out_zone: str = ""
    null_xy: tuple[int, int]
    in_xy: tuple[int, int]
    out_xy: tuple[int, int]
    flags: GroupPosFlag = GroupPosFlag.NONE
    layout_modes: dict[PortMode, BoxLayoutMode]
    hidden_sides: PortMode = PortMode.NULL
    boxes: dict[PortMode, BoxPos]
    splitted: bool = False
    fully_set: bool = True
    
    def __init__(self):
        self.null_xy = (0, 0)
        self.in_xy = (0, 0)
        self.out_xy = (0, 0)
        self.layout_modes = dict[PortMode, BoxLayoutMode]()
        for port_mode in (PortMode.INPUT, PortMode.OUTPUT, PortMode.BOTH):
            self.layout_modes[port_mode] = BoxLayoutMode.AUTO
        
        self.boxes = dict[PortMode, BoxPos]()
        
        for port_mode in (PortMode.INPUT, PortMode.OUTPUT, PortMode.BOTH):
            self.boxes[port_mode] = BoxPos()
    
    @staticmethod
    def _is_point(value: Any) -> bool:
        if not isinstance(value, (list, tuple)):
            return False
        
        if len(value) != 2:
            return False
        
        for v in value:
            if not isinstance(v, int):
                return False
        return True

    @staticmethod
    def from_serialized_dict(src: dict[str, Any]) -> 'GroupPos':
        port_types_view = src.get('port_types_view')
        group_name = src.get('group_name')
        null_zone = src.get('null_zone')
        out_zone = src.get('out_zone')
        in_zone = src.get('in_zone')
        null_xy = src.get('null_xy')
        in_xy = src.get('in_xy')
        out_xy = src.get('out_xy')
        flags = src.get('flags')
        layout_modes = src.get('layout_modes')
        hidden_sides = src.get('hidden_sides')
        
        gpos = GroupPos()
        
        if isinstance(port_types_view, int):
            gpos.port_types_view = PortTypesViewFlag(
                port_types_view & PortTypesViewFlag.ALL)
        if isinstance(group_name, str):
            gpos.group_name = group_name
        if isinstance(null_zone, str):
            gpos.null_zone = null_zone
        if isinstance(in_zone, str):
            gpos.in_zone = in_zone
        if isinstance(out_zone, str):
            gpos.out_zone = out_zone
        if GroupPos._is_point(null_xy):
            gpos.null_xy = tuple(null_xy)
        if GroupPos._is_point(in_xy):
            gpos.in_xy = tuple(in_xy)
        if GroupPos._is_point(out_xy):
            gpos.out_xy = tuple(out_xy)
        if isinstance(flags, int):
            gpos.flags = GroupPosFlag(flags)

        if isinstance(layout_modes, dict):
            for key, value in layout_modes.items():
                try:
                    gpos.layout_modes[PortMode(key)] = BoxLayoutMode(value)
                except:
                    pass
        
        if isinstance(hidden_sides, int):
            try:
                gpos.hidden_sides = PortMode(hidden_sides)
            except:
                gpos.hidden_sides = PortMode.NULL
        
        for port_mode in PortMode.INPUT, PortMode.OUTPUT, PortMode.BOTH:
            if port_mode is PortMode.INPUT:
                gpos.boxes[port_mode].zone = in_zone
                gpos.boxes[port_mode].pos = in_xy
                wrapped = bool(gpos.flags & GroupPosFlag.WRAPPED_INPUT)
            elif port_mode is PortMode.OUTPUT:
                gpos.boxes[port_mode].zone = out_zone
                gpos.boxes[port_mode].pos = out_xy
                wrapped = bool(gpos.flags & GroupPosFlag.WRAPPED_OUTPUT)
            else:
                gpos.boxes[port_mode].zone = null_zone
                gpos.boxes[port_mode].pos = null_xy
                wrapped = bool(gpos.flags & (GroupPosFlag.WRAPPED_INPUT
                                             | GroupPosFlag.WRAPPED_OUTPUT)
                               == (GroupPosFlag.WRAPPED_INPUT
                                   | GroupPosFlag.WRAPPED_OUTPUT))
            
            gpos.boxes[port_mode].layout_mode = gpos.layout_modes[port_mode]
            hidden = bool(gpos.hidden_sides & port_mode == port_mode)
            box_flags = BoxFlag.NONE
            if wrapped:
                box_flags |= BoxFlag.WRAPPED
            if hidden:
                box_flags |= BoxFlag.HIDDEN
            gpos.boxes[port_mode].flags = box_flags
        
        return gpos

    def copy(self) -> 'GroupPos':
        group_pos = GroupPos()
        group_pos.__dict__ = self.__dict__.copy()
        return group_pos

    def eat(self, other: 'GroupPos'):
        self.__dict__ = other.__dict__.copy()

    def as_serializable_dict(self, minimal=False):
        if not minimal:
            return {'port_types_view': self.port_types_view.value,
                    'group_name': self.group_name,
                    'null_zone': self.null_zone,
                    'in_zone': self.in_zone,
                    'out_zone': self.out_zone,
                    'null_xy': self.null_xy,
                    'in_xy': self.in_xy,
                    'out_xy': self.out_xy,
                    'flags': self.flags,
                    'layout_modes': self.layout_modes,
                    'hidden_sides': self.hidden_sides.value}
        
        out_dict = {'port_types_view': self.port_types_view.value,
                    'group_name': self.group_name}
        
        if self.null_zone:
            out_dict['null_zone'] = self.null_zone
        if self.in_zone:
            out_dict['in_zone'] = self.in_zone
        if self.out_zone:
            out_dict['out_zone'] = self.out_zone

        if self.null_xy != (0, 0):
            out_dict['null_xy'] = self.null_xy
        if self.in_xy != (0, 0):
            out_dict['in_xy'] = self.in_xy
        if self.out_xy != (0, 0):
            out_dict['out_xy'] = self.out_xy
        if self.flags is not GroupPosFlag.NONE:
            out_dict['flags'] = self.flags.value

        layout_modes = dict[int, int]()
        for port_mode, box_layout_mode in self.layout_modes.items():
            if box_layout_mode is not BoxLayoutMode.AUTO:
                layout_modes[port_mode.value] = box_layout_mode.value
        if layout_modes:
            out_dict['layout_modes'] = layout_modes
            
        if self.hidden_sides:
            out_dict['hidden_sides'] = self.hidden_sides.value

        return out_dict

    def set_layout_mode(self, port_mode: PortMode, layout_mode: BoxLayoutMode):
        self.layout_modes[port_mode] = layout_mode

    def get_layout_mode(self, port_mode: PortMode) -> BoxLayoutMode:
        if port_mode in self.layout_modes.keys():
            return self.layout_modes[port_mode]
        return BoxLayoutMode.AUTO


class PortgroupMem:
    group_name: str = ""
    port_type: PortType = PortType.NULL
    port_mode: PortMode = PortMode.NULL
    port_names: list[str]
    above_metadatas: bool = False
    
    def __init__(self):
        self.port_names = list[str]()

    @staticmethod
    def from_serialized_dict(src: dict[str, Any]) -> 'PortgroupMem':
        pg_mem = PortgroupMem()

        try:
            pg_mem.group_name = str(src['group_name'])
            pg_mem.port_type = PortType(src['port_type'])
            pg_mem.port_mode = PortMode(src['port_mode'])
            pg_mem.port_names = [str(a) for a in src['port_names']]
            pg_mem.above_metadatas = bool(src['above_metadatas'])
        except:
            pass

        return pg_mem

    def has_a_common_port_with(self, other: 'PortgroupMem') -> bool:
        if (self.port_type is not other.port_type
                or self.port_mode is not other.port_mode
                or self.group_name != other.group_name):
            return False
        
        for port_name in self.port_names:
            if port_name in other.port_names:
                return True
        
        return False
    
    def as_serializable_dict(self) -> dict[str, Any]:
        return {
            'group_name': self.group_name,
            'port_type': self.port_type,
            'port_mode': self.port_mode,
            'port_names': self.port_names,
            'above_metadatas': self.above_metadatas
        }


class Connection:
    def __init__(self, manager: 'PatchbayManager', connection_id: int,
                 port_out: 'Port', port_in: 'Port'):
        self.manager = manager
        self.connection_id = connection_id
        self.port_out = port_out
        self.port_in = port_in
        self.in_canvas = False

    def port_type(self) -> PortType:
        return self.port_out.type

    def full_type(self) -> tuple[PortType, PortSubType]:
        port_out_type, port_out_subtype = self.port_out.full_type()
        port_in_type, port_in_subtype = self.port_in.full_type()
        return (port_out_type, port_out_subtype | port_in_subtype)
        
    def shown_in_port_types_view(self, port_types_view: PortTypesViewFlag) -> bool:
        if self.port_out.type is PortType.MIDI_JACK:
            return bool(port_types_view & PortTypesViewFlag.MIDI)
        
        if (self.port_out.type is PortType.AUDIO_JACK
                and self.port_in.type is PortType.AUDIO_JACK):
            if (self.port_out.subtype is PortSubType.CV
                    and self.port_in.subtype is PortSubType.CV): 
                return bool(port_types_view & PortTypesViewFlag.CV)
            if (self.port_out.subtype is PortSubType.REGULAR
                    and self.port_in.subtype is PortSubType.REGULAR):
                return bool(port_types_view & PortTypesViewFlag.AUDIO)
        
        return False

    def add_to_canvas(self):
        if self.manager.very_fast_operation:
            return

        if self.in_canvas:
            return

        if not (self.port_out.in_canvas and self.port_in.in_canvas):
            if not (self.port_out.in_canvas or self.port_in.in_canvas):
                return

            for port in (self.port_out, self.port_in):
                port.set_hidden_conn_in_canvas(self, True)
            return

        self.in_canvas = True

        patchcanvas.connect_ports(
            self.connection_id,
            self.port_out.group_id, self.port_out.port_id,
            self.port_in.group_id, self.port_in.port_id)
        
        for port in (self.port_out, self.port_in):
            port.set_hidden_conn_in_canvas(self, False)

    def remove_from_canvas(self):
        if self.manager.very_fast_operation:
            return

        if not self.in_canvas:
            for port in (self.port_out, self.port_in):
                port.set_hidden_conn_in_canvas(self, False)
            return

        patchcanvas.disconnect_ports(self.connection_id)
        self.in_canvas = False

    def semi_hide(self, yesno: bool):
        if not self.in_canvas:
            return
        
        patchcanvas.semi_hide_connection(
            self.connection_id, yesno)
    
    def set_in_front(self):
        if not self.in_canvas:
            return
        
        patchcanvas.set_connection_in_front(self.connection_id)


class Port:
    display_name = ''
    group_id = -1
    portgroup_id = 0
    prevent_stereo = False
    last_digit_to_add = ''
    in_canvas = False
    order = None
    uuid = 0 # will contains the real JACK uuid
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

    def add_to_canvas(self, gpos: Optional[GroupPos]=None):
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

        if gpos is None:
            gpos = self.group.current_position

        if gpos.hidden_sides & self.mode():
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

    def __lt__(self, other: 'Port'):
        if self.type != other.type:
            return (self.type < other.type)

        if self.subtype is not other.subtype:
            return self.subtype < other.subtype

        # if self.mode() != other.mode():
        #     return (self.mode() < other.mode())

        if self.order is None and other.order is None:
            return self.port_id < other.port_id
        if self.order is None:
            return False
        if other.order is None:
            return True

        return bool(self.order < other.order)


class Portgroup:
    # Portgroup is a stereo pair of ports
    # but could be a group of more ports
    def __init__(self, manager: 'PatchbayManager', group_id: int,
                 portgroup_id: int, port_mode: PortMode, ports: tuple[Port]):
        self.manager = manager
        self.group_id = group_id
        self.portgroup_id = portgroup_id
        self.port_mode = port_mode
        self.ports = tuple(ports)

        self.mdata_portgroup = ''
        self.above_metadatas = False

        self.in_canvas = False

        if len(self.ports) >= 2:
            for port in self.ports:
                port.portgroup_id = portgroup_id

    def port_type(self):
        if not self.ports:
            return PortType.NULL

        return self.ports[0].type

    def full_type(self) -> tuple[PortType, PortSubType]:
        if not self.ports:
            return (PortType.NULL, PortSubType.REGULAR)
        
        return self.ports[0].full_type()

    def update_ports_in_canvas(self):
        for port in self.ports:
            port.rename_in_canvas()

    def sort_ports(self):
        port_list = list(self.ports)
        port_list.sort()
        self.ports = tuple(port_list)

    def add_to_canvas(self):
        if self.manager.very_fast_operation:
            return

        if self.in_canvas:
            return
    
        if not self.manager.port_type_shown(self.full_type()):
            return

        if len(self.ports) < 2:
            return

        for port in self.ports:
            if not port.in_canvas:
                return

        self.in_canvas = True

        patchcanvas.add_portgroup(
            self.group_id, self.portgroup_id,
            self.port_mode, self.ports[0].type, self.ports[0].subtype,
            [port.port_id for port in self.ports])

    def remove_from_canvas(self):
        if self.manager.very_fast_operation:
            return
        
        if not self.in_canvas:
            return

        patchcanvas.remove_portgroup(self.group_id, self.portgroup_id)
        self.in_canvas = False



