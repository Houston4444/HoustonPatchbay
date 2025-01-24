
from dataclasses import dataclass
from typing import Iterator


@dataclass()
class _PrettyAndOver:
    pretty: str
    'the saved pretty-name'
    above_pretty: str
    '''the pretty-name of the subject when pretty-name was saved.
    This way, pretty name can be set only when the existing pretty-name
    is the same than above_pretty.'''


class PrettyNames:
    def __init__(self):
        self.groups = dict[str, _PrettyAndOver]()
        self.ports = dict[str, _PrettyAndOver]()
    
    def eat_json(self, json_dict: dict[str, dict[str, list[str]]]):
        if not isinstance(json_dict, dict):
            return

        groups = json_dict.get('groups')
        if groups is not None and isinstance(groups, dict):
            for group_name, pretty_names in groups.items():
                if not (isinstance(pretty_names, list)
                        and len(pretty_names) == 2):
                    continue
                
                self.groups[group_name] = _PrettyAndOver(*pretty_names)
                
        ports = json_dict.get('ports')
        if ports is not None and isinstance(ports, dict):
            for port_name, pretty_names in ports.items():
                if not (isinstance(pretty_names, list)
                        and len(pretty_names) == 2):
                    continue
                
                self.ports[port_name] = _PrettyAndOver(*pretty_names)
    
    def to_json(self) -> dict[str, dict[str, tuple[str, str]]]:
        gp_dict = dict[str, tuple[str, str]]()
        pt_dict = dict[str, tuple[str, str]]()
        for group_name, ptov in self.groups.items():
            gp_dict[group_name] = (ptov.pretty, ptov.above_pretty)
        for port_name, ptov in self.ports.items():
            pt_dict[port_name] = (ptov.pretty, ptov.above_pretty)
        
        return {'groups': gp_dict, 'ports': pt_dict}
    
    def save_group(self, group_name: str, pretty_name: str, over_pretty=''):
        self.groups[group_name] = _PrettyAndOver(pretty_name, over_pretty)
    
    def save_port(self, port_name: str, pretty_name: str, over_pretty=''):
        self.ports[port_name] = _PrettyAndOver(pretty_name, over_pretty)

    def pretty_group(self, group_name: str, cur_pretty_name='') -> str:
        '''return the group (client) pretty_name if conditions are full,
        otherwire empty string'''
        ptov = self.groups.get(group_name)
        if ptov is None:
            return ''
        
        if ptov.pretty == cur_pretty_name:
            return ''
        
        if ptov.above_pretty != cur_pretty_name:
            return ''
        return ptov.pretty
    
    def pretty_port(self, port_name: str, cur_pretty_name='') -> str:
        '''return the port pretty_name if conditions are full,
        otherwire empty string'''
        ptov = self.ports.get(port_name)
        if ptov is None:
            return ''
        
        if ptov.pretty == cur_pretty_name:
            return ''
        
        if ptov.above_pretty != cur_pretty_name:
            return ''
        return ptov.pretty
        
    def copy(self) -> 'PrettyNames':
        ret = PrettyNames()
        ret.groups = self.groups.copy()
        ret.ports = self.ports.copy()
        return ret
    
    def clear(self):
        self.groups.clear()
        self.ports.clear()