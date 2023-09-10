from dataclasses import dataclass
from enum import IntFlag, IntEnum, auto
from typing import TYPE_CHECKING, Any

from .patchcanvas import (patchcanvas, PortMode, PortType, BoxType,
                          BoxLayoutMode, PortSubType, BoxPos)


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
    SPLITTED = 0x04          # still used
    WRAPPED_INPUT = 0x10     # used for old config
    WRAPPED_OUTPUT = 0x20    # used fot old config
    HAS_BEEN_SPLITTED = 0x40 # Not used anymore


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





class GroupPos:
    port_types_view: PortTypesViewFlag = PortTypesViewFlag.NONE
    group_name: str = ""
    flags: GroupPosFlag = GroupPosFlag.NONE
    hidden_sides: PortMode = PortMode.NULL
    boxes: dict[PortMode, BoxPos]
    splitted: bool = False
    fully_set: bool = True
    
    def __init__(self):
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
        in_zone = src.get('in_zone')
        out_zone = src.get('out_zone')
        both_zone = src.get('null_zone')
        null_xy = src.get('null_xy')
        in_xy = src.get('in_xy')
        out_xy = src.get('out_xy')
        flags = src.get('flags')
        layout_modes = src.get('layout_modes')
        hidden_sides = src.get('hidden_sides')
        
        gpos = GroupPos()
        
        if isinstance(port_types_view, int):
            gpos.port_types_view = PortTypesViewFlag(port_types_view)
        if isinstance(group_name, str):
            gpos.group_name = group_name
        if isinstance(flags, int):
            gpos.flags = GroupPosFlag(flags)
        if isinstance(hidden_sides, int):
            try:
                gpos.hidden_sides = PortMode(hidden_sides)
            except:
                gpos.hidden_sides = PortMode.NULL
        
        for port_mode in PortMode.INPUT, PortMode.OUTPUT, PortMode.BOTH:
            if port_mode is PortMode.INPUT:
                if isinstance(in_zone, str):
                    gpos.boxes[port_mode].zone = in_zone
                if GroupPos._is_point(in_xy):
                    gpos.boxes[port_mode].pos = in_xy
                wrapped = bool(gpos.flags & GroupPosFlag.WRAPPED_INPUT)
            elif port_mode is PortMode.OUTPUT:
                if isinstance(out_zone, str):
                    gpos.boxes[port_mode].zone = out_zone
                if GroupPos._is_point(out_xy):
                    gpos.boxes[port_mode].pos = out_xy
                wrapped = bool(gpos.flags & GroupPosFlag.WRAPPED_OUTPUT)
            else:
                if isinstance(both_zone, str):
                    gpos.boxes[port_mode].zone = both_zone
                if GroupPos._is_point(null_xy):
                    gpos.boxes[port_mode].pos = null_xy
                wrapped = bool(gpos.flags & (GroupPosFlag.WRAPPED_INPUT
                                             | GroupPosFlag.WRAPPED_OUTPUT)
                               == (GroupPosFlag.WRAPPED_INPUT
                                   | GroupPosFlag.WRAPPED_OUTPUT))
            
            try:
                gpos.boxes[port_mode].layout_mode = BoxLayoutMode(
                    layout_modes[int(port_mode)])
            except:
                pass

            gpos.boxes[port_mode].set_wrapped(wrapped)
        
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
                    # 'null_zone': self.null_zone,
                    # 'in_zone': self.in_zone,
                    # 'out_zone': self.out_zone,
                    # 'null_xy': self.null_xy,
                    # 'in_xy': self.in_xy,
                    # 'out_xy': self.out_xy,
                    'flags': self.flags,
                    # 'layout_modes': self.layout_modes,
                    'hidden_sides': self.hidden_sides.value}
        
        out_dict = {'port_types_view': self.port_types_view.value,
                    'group_name': self.group_name}
        
        # if self.null_zone:
        #     out_dict['null_zone'] = self.null_zone
        # if self.in_zone:
        #     out_dict['in_zone'] = self.in_zone
        # if self.out_zone:
        #     out_dict['out_zone'] = self.out_zone

        # if self.null_xy != (0, 0):
        #     out_dict['null_xy'] = self.null_xy
        # if self.in_xy != (0, 0):
        #     out_dict['in_xy'] = self.in_xy
        # if self.out_xy != (0, 0):
        #     out_dict['out_xy'] = self.out_xy
        if self.flags is not GroupPosFlag.NONE:
            out_dict['flags'] = self.flags.value

        layout_modes = dict[int, int]()
        
        for port_mode, box_pos in self.boxes.items():
            if box_pos.layout_mode is not BoxLayoutMode.AUTO:
                layout_modes[port_mode.value] = box_pos.layout_mode.value
        if layout_modes:
            out_dict['layout_modes'] = layout_modes
            
        if self.hidden_sides:
            out_dict['hidden_sides'] = self.hidden_sides.value
            
        out_dict['null_xy'] = self.boxes[PortMode.BOTH].pos
        out_dict['in_xy'] = self.boxes[PortMode.INPUT].pos
        out_dict['out_xy'] = self.boxes[PortMode.OUTPUT].pos

        return out_dict
    
    def is_splitted(self) -> bool:
        return bool(self.flags & GroupPosFlag.SPLITTED)
    
    def set_splitted(self, yesno: bool):
        if yesno:
            self.flags |= GroupPosFlag.SPLITTED
        else:
            self.flags &= ~GroupPosFlag.SPLITTED
        


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



