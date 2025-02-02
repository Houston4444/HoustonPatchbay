from dataclasses import dataclass
from enum import IntFlag, IntEnum, auto, Flag


class JackPortFlag(IntFlag):
    'Port Flags as defined by JACK'
    IS_INPUT = 0x01
    IS_OUTPUT = 0x02
    IS_PHYSICAL = 0x04
    CAN_MONITOR = 0x08
    IS_TERMINAL = 0x10
    IS_CONTROL_VOLTAGE = 0x100


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
    UNDO_REDO = auto()
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
    ALL = (UNDO_REDO
           | VIEWS_SELECTOR
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
        

class Naming(Flag):
    '''Define the way clients and ports should be named.'''
    TRUE_NAME = 0x0
    'True JACK or ALSA item name'
    
    GRACEFUL = 0x1
    '''Shorter than TRUE_NAME, more readable name without underscores
    and with custom arrangements depending on the client name.'''
    
    INTERNAL_PRETTY = 0x2
    'The pretty name saved internally when user renames a port or a group'
    
    METADATA_PRETTY = 0x4
    '''The pretty name contained in JACK metadatas
    (http://jackaudio.org/metadata/pretty-name)'''
    
    ALL = METADATA_PRETTY|INTERNAL_PRETTY|GRACEFUL

    @classmethod
    def from_config_str(cls, string: str) -> 'Naming':
        naming = cls.TRUE_NAME
        for s in string.split('|'):
            try:
                naming |= Naming[s]
            except:
                continue
        return naming

