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
        

class JackMetadatas(dict[int, dict[str, str]]):
    def __init__(self):
        super().__init__()
    
    def add(self, uuid: int, key: str, value: str):
        'add a metadata to the bank, or remove it if value is empty string'
        
        uuid_dict = self.get(uuid)
        if uuid_dict is None:
            uuid_dict = self[uuid] = dict[str, str]()
        
        if value:
            uuid_dict[key] = value
        elif uuid_dict.get(key) is not None:
            uuid_dict.pop(key)
    
    def str_for_key(self, uuid: int, key: JackMetadata) -> str:
        uuid_dict = self.get(uuid)
        if uuid_dict is None:
            return ''
        
        return uuid_dict.get(key, '')
    
    def pretty_name(self, uuid: int) -> str:
        return self.str_for_key(uuid, JackMetadata.PRETTY_NAME)
        
    def icon_name(self, uuid: int) -> str:
        return self.str_for_key(uuid, JackMetadata.ICON_NAME)
