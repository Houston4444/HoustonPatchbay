
from dataclasses import dataclass


@dataclass()
class _CustomAndOver:
    custom: str
    'the saved custom name'
    above_pretty: str
    '''the JACK pretty-name of the subject when custom name was saved.
    This way, custom name can be set as JACK pretty name 
    when the existing JACK pretty-name is the same than above_pretty.'''


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
            for group_name, pretty_names in groups.items():
                if not (isinstance(pretty_names, list)
                        and len(pretty_names) == 2):
                    continue
                
                self.groups[group_name] = _CustomAndOver(*pretty_names)
                
        ports = json_dict.get('ports')
        if ports is not None and isinstance(ports, dict):
            for port_name, pretty_names in ports.items():
                if not (isinstance(pretty_names, list)
                        and len(pretty_names) == 2):
                    continue
                
                self.ports[port_name] = _CustomAndOver(*pretty_names)
    
    def to_json(self) -> dict[str, dict[str, tuple[str, str]]]:
        gp_dict = dict[str, tuple[str, str]]()
        pt_dict = dict[str, tuple[str, str]]()
        for group_name, ptov in self.groups.items():
            gp_dict[group_name] = (ptov.custom, ptov.above_pretty)
        for port_name, ptov in self.ports.items():
            pt_dict[port_name] = (ptov.custom, ptov.above_pretty)
        
        return {'groups': gp_dict, 'ports': pt_dict}
    
    def save_group(self, group_name: str, custom_name: str, over_pretty=''):
        if custom_name:
            self.groups[group_name] = _CustomAndOver(custom_name, over_pretty)
        elif group_name in self.groups:
            self.groups.pop(group_name)
    
    def save_port(self, port_name: str, custom_name: str, over_pretty=''):
        if custom_name:
            self.ports[port_name] = _CustomAndOver(custom_name, over_pretty)
        elif port_name in self.ports:
            self.ports.pop(port_name)

    def custom_group(self, group_name: str, cur_pretty_name='') -> str:
        '''return the group (client) custom name if conditions are full,
        otherwire empty string'''
        ptov = self.groups.get(group_name)
        if ptov is None:
            return ''
        
        if ptov.custom == cur_pretty_name:
            return ''
        
        if not cur_pretty_name:
            return ptov.custom
        
        if ptov.above_pretty != cur_pretty_name:
            return ''
        return ptov.custom
    
    def custom_port(self, port_name: str, cur_pretty_name='') -> str:
        '''return the port pretty_name if conditions are full,
        otherwire empty string'''
        ptov = self.ports.get(port_name)
        if ptov is None:
            return ''
        
        if ptov.custom == cur_pretty_name:
            return ''
        
        if not cur_pretty_name:
            return ptov.custom
        
        if ptov.above_pretty != cur_pretty_name:
            return ''
        return ptov.custom
        
    def copy(self) -> 'CustomNames':
        ret = CustomNames()
        ret.groups = self.groups.copy()
        ret.ports = self.ports.copy()
        return ret
    
    def clear(self):
        self.groups.clear()
        self.ports.clear()