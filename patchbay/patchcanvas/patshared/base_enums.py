from enum import Enum, IntEnum, IntFlag, auto
from typing import Iterator


class PortMode(IntFlag):
    NULL = 0x00
    INPUT = 0x01
    OUTPUT = 0x02
    BOTH = INPUT | OUTPUT
    
    def opposite(self) -> 'PortMode':
        if self is PortMode.INPUT:
            return PortMode.OUTPUT
        if self is PortMode.OUTPUT:
            return PortMode.INPUT
        if self is PortMode.BOTH:
            return PortMode.NULL
        if self is PortMode.NULL:
            return PortMode.BOTH
        return PortMode.NULL

    @staticmethod
    def in_out_both() -> Iterator['PortMode']:
        yield PortMode.INPUT
        yield PortMode.OUTPUT
        yield PortMode.BOTH


class PortType(IntFlag):
    NULL = 0x00
    AUDIO_JACK = 0x01
    MIDI_JACK = 0x02
    MIDI_ALSA = 0x04
    VIDEO = 0x08
    PARAMETER = 0x10


class PortSubType(IntFlag):
    '''a2j ports are MIDI ports, we only specify a decoration for them.
    CV ports are audio ports, but we prevent to connect an output CV port
    to a regular audio port to avoid material destruction, CV ports also
    look different, simply because this is absolutely not the same use.'''
    REGULAR = 0x01
    CV = 0x02
    A2J = 0x04


class BoxType(Enum):
    APPLICATION = 0
    HARDWARE = 1
    MONITOR = 2
    DISTRHO = 3
    FILE = 4
    PLUGIN = 5
    LADISH_ROOM = 6
    CLIENT = 7
    INTERNAL = 8
    
    def __lt__(self, other: 'BoxType'):
        return self.value < other.value
    

class BoxLayoutMode(IntEnum):
    'Define the way ports are put in a box'

    AUTO = 0
    '''Choose the layout between HIGH or LARGE
    within the box area.'''
    
    HIGH = 1
    '''In the case there are only INPUT or only OUTPUT ports,
    the title will be on top of the box.
    In the case there are both INPUT and OUTPUT ports,
    ports will be displayed from top to bottom, whatever they
    are INPUT or OUTPUT.'''
    
    LARGE = 2
    '''In the case there are only INPUT or only OUTPUT ports,
    the title will be on a side of the box.
    In the case there are both INPUT and OUTPUT ports,
    ports will be displayed in two columns, left for INPUT, 
    right for OUTPUT.'''


class BoxFlag(IntFlag):
    NONE = 0x00
    WRAPPED = auto()
    HIDDEN = auto()


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

    def to_config_str(self):
        if self is PortTypesViewFlag.ALL:
            return 'ALL'

        str_list = list[str]()        
        for ptv in PortTypesViewFlag:
            if ptv in (PortTypesViewFlag.NONE, PortTypesViewFlag.ALL):
                continue

            if self & ptv:
                str_list.append(ptv.name)
        return '|'.join(str_list)
    
    @staticmethod
    def from_config_str(input_str: str) -> 'PortTypesViewFlag':
        if not isinstance(input_str, str):
            return PortTypesViewFlag.NONE

        if input_str.upper() == 'ALL':
            return PortTypesViewFlag.ALL

        ret = PortTypesViewFlag.NONE

        names = [nm.upper() for nm in input_str.split('|')]
        for ptv in PortTypesViewFlag:
            if ptv in (PortTypesViewFlag.NONE, PortTypesViewFlag.ALL):
                continue
                
            if ptv.name in names:
                ret |= ptv

        return ret
