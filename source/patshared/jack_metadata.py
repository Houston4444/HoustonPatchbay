class JackMetadata:
    'Jack property common keys + custom'

    _PREFIX = "http://jackaudio.org/metadata/"
    CONNECTED = _PREFIX + "connected"
    EVENT_TYPES = _PREFIX + "event-types"
    HARDWARE = _PREFIX + "hardware"
    ICON_LARGE = _PREFIX + "icon-large"
    ICON_NAME = _PREFIX + "icon-name"
    ICON_SMALL = _PREFIX + "icon-small"
    ORDER = _PREFIX + "order"
    PORT_GROUP = _PREFIX + "port-group"
    PRETTY_NAME = _PREFIX + "pretty-name"
    SIGNAL_TYPE = _PREFIX + "signal-type"

    # Specific to HoustonPatchbay
    MIDI_BRIDGE_GROUP_PRETTY_NAME = \
        "HoustonPatchbay/midi-bridge-pretty-name"