from enum import Enum, Flag, IntEnum, IntFlag, auto
from typing import Iterator


class PortMode(IntFlag):
    """Direction flags used for ports and box layouts.

    For individual ports, use `INPUT`, `OUTPUT` or `NULL` (a single port
    cannot be `BOTH`). The `BOTH` value is intended for boxes/groups that
    contain both input and output ports and is useful when describing
    layout or group visibility. Helper methods such as `opposite` and
    `in_out_both` are provided for common operations. Note that
    `in_out_both()` yields modes useful for iterating over input/output
    and box-level `BOTH` contexts.
    """
    NULL = 0x00
    INPUT = 0x01
    OUTPUT = 0x02
    BOTH = INPUT | OUTPUT

    def opposite(self) -> 'PortMode':
        """Return the opposite mode (INPUT <-> OUTPUT, BOTH <-> NULL)."""
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
        """Yield modes, useful for iterating input, output and both."""
        yield PortMode.INPUT
        yield PortMode.OUTPUT
        yield PortMode.BOTH


class PortType(IntFlag):
    """Enumeration of port technologies.

    Indicates the underlying technology of a port (Audio JACK, JACK MIDI,
    ALSA MIDI, Video, or Parameter (not used)). Provides a convenience `is_jack`
    property to detect JACK-based types.
    """
    NULL = 0x00
    AUDIO_JACK = 0x01
    MIDI_JACK = 0x02
    MIDI_ALSA = 0x04
    VIDEO = 0x08
    PARAMETER = 0x10

    @classmethod
    def _missing_(cls, value) -> 'PortType':
        """Return default `PortType.NULL` for unknown values."""
        return PortType.NULL

    @property
    def is_jack(self) -> bool:
        """Return True for JACK-based port types."""
        return self in (self.AUDIO_JACK, self.MIDI_JACK)


class PortSubType(IntFlag):
    """Annotates port sub-types such as CV (control voltage) or a2j MIDI.

    CV ports are treated as audio ports but have connection restrictions.
    A2J indicates ports originating from the ALSA-to-JACK bridge.
    """
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
    TRACK = 9

    def __lt__(self, other: 'BoxType'):
        """Compare BoxType by their integer value."""
        return self.value < other.value


class BoxLayoutMode(IntEnum):
    """Define how ports are arranged inside a box."""

    AUTO = 0
    '''Choose the layout between HIGH or LARGE
    within the box area.'''

    HIGH = 1
    """When only INPUT or only OUTPUT ports exist the title is on top.
    If both types are present, ports are displayed top-to-bottom."""

    LARGE = 2
    """When only INPUT or only OUTPUT ports exist the title is on a side.
    If both types are present, ports are displayed in two columns
    (left = INPUT, right = OUTPUT)."""


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
        """Return configuration string for this flag set.

        Examples: 'ALL' or 'AUDIO|MIDI'."""
        if self is PortTypesViewFlag.ALL:
            return 'ALL'

        str_list = list[str]()
        for ptv in PortTypesViewFlag:
            if ptv in (PortTypesViewFlag.NONE, PortTypesViewFlag.ALL):
                continue

            if self & ptv and isinstance(ptv.name, str):
                str_list.append(ptv.name)
        return '|'.join(str_list)

    @staticmethod
    def from_config_str(input_str: str) -> 'PortTypesViewFlag':
        """Parse a config string into a `PortTypesViewFlag` value."""
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


class Naming(Flag):
    """Define how clients and ports should be named"""
    TRUE_NAME = 0x0
    "True JACK or ALSA item name."

    GRACEFUL = 0x1
    """Shorter, more readable name (no underscores) with
    custom arrangements."""

    CUSTOM = 0x2
    "Custom name saved when user renames a port or group."

    METADATA_PRETTY = 0x4
    """Pretty name from JACK metadata
    (http://jackaudio.org/metadata/pretty-name)"""

    ALL = METADATA_PRETTY | CUSTOM | GRACEFUL

    @classmethod
    def from_config_str(cls, string: str) -> 'Naming':
        """Convert a string like 'GRACEFUL|CUSTOM' into a `Naming` value."""
        naming = cls.TRUE_NAME
        for s in string.split('|'):
            try:
                naming |= Naming[s]
            except:
                continue
        return naming


class PrettyDiff(Flag):
    NO_DIFF = 0x0
    """No difference between internal pretty names and JACK's pretty names."""

    NON_EXPORTED = 0x1
    "Some custom names are not exported to JACK."

    NON_IMPORTED = 0x2
    "Some JACK pretty names are not present in custom names."

    NON_BOTH = 0x3
    """Some custom names are not exported to JACK, and some JACK pretty
    names are not present in custom names."""