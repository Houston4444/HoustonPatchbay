class JackMetadata:
    """Constants for JACK metadata keys."""

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


class JackMetadatas(dict[int, dict[str, str]]):
    """Mapping of client or port UUID to metadata dict."""
    def __init__(self):
        super().__init__()

    def add(self, uuid: int, key: str, value: str):
        """Add or remove a metadata entry for `uuid`.

        If `value` is an empty string the key is removed. Passing an empty
        `uuid` will clear the whole mapping.
        """
        if not uuid:
            self.clear()
            return

        uuid_dict = self.get(uuid)
        if uuid_dict is None:
            uuid_dict = self[uuid] = dict[str, str]()

        if not key:
            uuid_dict.clear()
            return

        if value:
            uuid_dict[key] = value
        elif uuid_dict.get(key) is not None:
            uuid_dict.pop(key)

    def str_for_key(self, uuid: int, key: str) -> str:
        """Return the metadata value for `key` or empty string if absent."""
        uuid_dict = self.get(uuid)
        if uuid_dict is None:
            return ''

        return uuid_dict.get(key, '')

    def pretty_name(self, uuid: int) -> str:
        """Convenience: return PRETTY_NAME for `uuid` or empty string."""
        return self.str_for_key(uuid, JackMetadata.PRETTY_NAME)

    def icon_name(self, uuid: int) -> str:
        """Convenience: return ICON_NAME for `uuid` or empty string."""
        return self.str_for_key(uuid, JackMetadata.ICON_NAME)

    def remove_uuid(self, uuid: int):
        """Remove all metadata for `uuid` if present."""
        if uuid in self:
            self.pop(uuid)