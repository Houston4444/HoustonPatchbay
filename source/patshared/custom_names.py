class _CustomAndOver:
    """Custom name and optional pretty-names recorded at save time."""
    custom: str
    "The saved custom name."
    above_pretty: set[str]
    """Set of JACK pretty-names present when the custom name was saved.
    If the current pretty-name is in this set, the custom name applies."""

    def __init__(self, custom: str, *aboves: str):
        self.custom = custom
        self.above_pretty = set([a for a in aboves if a])

    def to_list(self) -> list[str]:
        return [self.custom, *self.above_pretty]

    def to_json_item(self) -> str | list[str]:
        if self.above_pretty:
            return self.to_list()
        return self.custom


class CustomNames:
    """Container for custom names of groups and ports.

    Maps group and port identifiers to `_CustomAndOver` holding the saved
    custom name and (optionally) the pretty-names that were present when
    the custom name was recorded.
    """
    def __init__(self):
        self.groups = dict[str, _CustomAndOver]()
        self.ports = dict[str, _CustomAndOver]()

    def __or__(self, other: 'CustomNames') -> 'CustomNames':
        custom_names = CustomNames()
        custom_names.groups = self.groups | other.groups
        custom_names.ports = self.ports | other.ports
        return custom_names

    def eat_json(self, json_dict: dict[str, dict[str, list[str]]]):
        """Populate this object from a JSON-like dict structure.

        Expected keys are `groups` and `ports`, each mapping names to either
        a string or a list (custom name plus optional pretty-names).
        """
        if not isinstance(json_dict, dict):
            return

        groups = json_dict.get('groups')
        if groups is not None and isinstance(groups, dict):
            for group_name, custom in groups.items():
                if isinstance(custom, str):
                    self.groups[group_name] = _CustomAndOver(custom)
                elif isinstance(custom, list):
                    self.groups[group_name] = _CustomAndOver(*custom)

        ports = json_dict.get('ports')
        if ports is not None and isinstance(ports, dict):
            for port_name, custom in ports.items():
                if isinstance(custom, str):
                    self.ports[port_name] = _CustomAndOver(custom)
                elif isinstance(custom, list):
                    self.ports[port_name] = _CustomAndOver(*custom)

    def to_json(self) -> dict[str, dict[str, str | list[str]]]:
        """Return a JSON-serializable representation with `groups` and
        `ports` mappings suitable for writing to disk.
        """
        gp_dict = dict[str, str | list[str]]()
        pt_dict = dict[str, str | list[str]]()
        for group_name, ctov in self.groups.items():
            gp_dict[group_name] = ctov.to_json_item()
        for port_name, ctov in self.ports.items():
            pt_dict[port_name] = ctov.to_json_item()

        return {'groups': gp_dict, 'ports': pt_dict}

    def _save_el(self, is_group: bool, el_name: str,
                 custom_name: str, *over_prettys: str):
        """Internal helper: save or remove a custom name for a group/port.

        If `custom_name` is empty the name is removed, otherwise the stored
        `_CustomAndOver` is created or updated with the provided
        `over_prettys`.
        """
        d = self.groups if is_group else self.ports

        if custom_name:
            ctov = d.get(el_name)
            if ctov is None or ctov.custom != custom_name:
                d[el_name] = _CustomAndOver(custom_name, *over_prettys)
            else:
                for over_pretty in over_prettys:
                    ctov.above_pretty.add(over_pretty)
        elif el_name in d:
            d.pop(el_name)

    def save_group(self, group_name: str, custom_name: str,
                   *over_prettys: str):
        """Convenience wrapper to save a custom name for `group_name`.
        """
        self._save_el(True, group_name, custom_name, *over_prettys)

    def save_port(self, port_name: str, custom_name: str, *over_prettys: str):
        """Convenience wrapper to save a custom name for `port_name`."""
        self._save_el(False, port_name, custom_name, *over_prettys)

    def custom_group(self, group_name: str, cur_pretty_name='') -> str:
        """Return the stored custom group name if it applies to
        the current pretty-name, otherwise return empty string."""
        ctov = self.groups.get(group_name)
        if ctov is None:
            return ''

        if ctov.custom == cur_pretty_name:
            return ''

        if not cur_pretty_name:
            return ctov.custom

        if cur_pretty_name not in ctov.above_pretty:
            return ''
        return ctov.custom

    def custom_port(self, port_name: str, cur_pretty_name='') -> str:
        """Return the stored custom port name if it applies to
        the current pretty-name, otherwise return empty string.
        """
        ctov = self.ports.get(port_name)
        if ctov is None:
            return ''

        if ctov.custom == cur_pretty_name:
            return ''

        if not cur_pretty_name:
            return ctov.custom

        if cur_pretty_name not in ctov.above_pretty:
            return ''
        return ctov.custom

    def copy(self) -> 'CustomNames':
        ret = CustomNames()
        ret.groups = self.groups.copy()
        ret.ports = self.ports.copy()
        return ret

    def clear(self):
        self.groups.clear()
        self.ports.clear()