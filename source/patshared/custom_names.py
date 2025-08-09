class _CustomAndOver:
    custom: str
    'the saved custom name'
    above_pretty: set[str]
    '''Set of JACK pretty-name(s) of the subject when custom name was saved.
    This way, custom name can be set as JACK pretty name 
    when the existing JACK pretty-name is in above_pretty.'''
    
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
    'Container for internal custom names'
    def __init__(self):
        self.groups = dict[str, _CustomAndOver]()
        self.ports = dict[str, _CustomAndOver]()
    
    def __or__(self, other: 'CustomNames') -> 'CustomNames':
        custom_names = CustomNames()
        custom_names.groups = self.groups | other.groups
        custom_names.ports = self.ports | other.ports
        return custom_names
    
    def eat_json(self, json_dict: dict[str, dict[str, list[str]]]):
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
    
    def to_json(self) -> dict[str, dict[str, tuple[str, str]]]:
        gp_dict = dict[str, tuple[str, str]]()
        pt_dict = dict[str, tuple[str, str]]()
        for group_name, ctov in self.groups.items():
            gp_dict[group_name] = ctov.to_json_item()
        for port_name, ctov in self.ports.items():
            pt_dict[port_name] = ctov.to_json_item()
        
        return {'groups': gp_dict, 'ports': pt_dict}
    
    def _save_el(self, is_group: bool, el_name: str,
                 custom_name: str, *over_prettys: str):
        d = self.groups if is_group else self.ports

        if custom_name:
            ctov = d.get(el_name)
            if ctov is None:
                d[el_name] = _CustomAndOver(custom_name, *over_prettys)
            else:
                for over_pretty in over_prettys:
                    ctov.above_pretty.add(over_pretty)
        elif el_name in d:
            d.pop(el_name)
    
    def save_group(self, group_name: str, custom_name: str,
                   *over_prettys: str):
        self._save_el(True, group_name, custom_name, *over_prettys)
    
    def save_port(self, port_name: str, custom_name: str, *over_prettys: str):
        self._save_el(False, port_name, custom_name, *over_prettys)

    def custom_group(self, group_name: str, cur_pretty_name='') -> str:
        '''return the group (client) custom name if conditions are full,
        otherwire empty string'''
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
        '''return the port pretty_name if conditions are full,
        otherwire empty string'''
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