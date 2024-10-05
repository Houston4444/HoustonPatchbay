from dataclasses import dataclass
from enum import IntFlag, IntEnum, auto
from typing import Any, Union

from .patchcanvas import (
    PortMode, PortType, PortSubType,
    BoxLayoutMode, BoxPos, BoxFlag, BoxType,
    AliasingReason)
from .patchcanvas.base_enums import GroupPos, GroupPosFlag, PortTypesViewFlag


# Port Flags as defined by JACK
class JackPortFlag(IntFlag):
    IS_INPUT = 0x01
    IS_OUTPUT = 0x02
    IS_PHYSICAL = 0x04
    CAN_MONITOR = 0x08
    IS_TERMINAL = 0x10
    IS_CONTROL_VOLTAGE = 0x100
            

@dataclass
class ViewData:
    name: str
    default_port_types_view: PortTypesViewFlag
    is_white_list: bool


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
    VIEWS_SELECTOR = auto()
    HIDDENS_BOX = auto()
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
    ALL = (VIEWS_SELECTOR
           | HIDDENS_BOX
           | PORT_TYPES_VIEW
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
        '''return a string containing all flags names
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



