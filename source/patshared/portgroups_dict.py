import logging
from typing import Union, Iterator, Any

from .base_enums import PortType, PortMode


_logger = logging.getLogger(__name__)


class PortgroupMem:
    group_name: str = ""
    port_type: PortType = PortType.NULL
    port_mode: PortMode = PortMode.NULL
    port_names: list[str]
    above_metadatas: bool = False
    
    def __init__(self):
        self.port_names = list[str]()

    @staticmethod
    def from_serialized_dict(src: dict[str, Any]) -> 'PortgroupMem':
        pg_mem = PortgroupMem()

        try:
            pg_mem.group_name = str(src['group_name'])
            pg_mem.port_type = PortType(src['port_type'])
            pg_mem.port_mode = PortMode(src['port_mode'])
            pg_mem.port_names = [str(a) for a in src['port_names']]
            pg_mem.above_metadatas = bool(src['above_metadatas'])
        except:
            pass

        return pg_mem

    def has_a_common_port_with(self, other: 'PortgroupMem') -> bool:
        if (self.port_type is not other.port_type
                or self.port_mode is not other.port_mode
                or self.group_name != other.group_name):
            return False
        
        for port_name in self.port_names:
            if port_name in other.port_names:
                return True
        
        return False
    
    def as_serializable_dict(self) -> dict[str, Any]:
        return {
            'group_name': self.group_name,
            'port_type': self.port_type,
            'port_mode': self.port_mode,
            'port_names': self.port_names,
            'above_metadatas': self.above_metadatas
        }

    def as_new_dict(self) -> dict[str, Any]:
        new_dict = {'port_names': self.port_names}
        if self.above_metadatas:
            new_dict['above_metadatas'] = self.above_metadatas
        return new_dict
    
    @staticmethod
    def from_new_dict(new_dict: dict[str, Any]) -> 'PortgroupMem':
        pg_mem = PortgroupMem()
        
        port_names = new_dict.get('port_names')
        if not isinstance(port_names, list):
            return pg_mem
        
        for port_name in port_names:
            if not isinstance(port_name, str):
                return pg_mem
        
        for port_name in port_names:
            pg_mem.port_names.append(port_name)
        
        above_metadatas = new_dict.get('above_metadatas', False)
        if isinstance(above_metadatas, bool):
            pg_mem.above_metadatas = above_metadatas
        
        return pg_mem

    def to_arg_list(self) -> list[Union[str, int]]:
        arg_list = list[Union[str, int]]()
        
        return [self.group_name,
                self.port_type.value,
                self.port_mode.value,
                int(self.above_metadatas),
                ] + self.port_names
    
    @staticmethod
    def from_arg_list(arg_tuple: tuple[str | int, ...]) -> 'PortgroupMem':
        arg_list = list(arg_tuple)
        pg_mem = PortgroupMem()
        
        try:
            pg_mem.group_name = arg_list.pop(0)
            pg_mem.port_type = PortType(arg_list.pop(0))
            pg_mem.port_mode = PortMode(arg_list.pop(0))
            pg_mem.above_metadatas = bool(arg_list.pop(0))
            for arg in arg_list:
                assert isinstance(arg, str)
                pg_mem.port_names.append(arg)
        
        except:
            _logger.warning('Failed to convert OSC list to portgroup mem')
        
        return pg_mem


class PortgroupsDict(
        dict[PortType, dict[str, dict[PortMode, list[PortgroupMem]]]]):    
    def _eat_json_new(
            self, json_dict: dict[str, dict[str, dict[str, list[dict]]]]):
        for ptype_str, ptype_dict in json_dict.items():
            try:
                port_type = PortType[ptype_str]
                assert isinstance(ptype_dict, dict)
            except:
                continue

            nw_ptype_dict = self[port_type] = \
                dict[str, dict[PortMode, list[PortgroupMem]]]()
            
            for gp_name, gp_dict in ptype_dict.items():
                if not isinstance(gp_dict, dict):
                    continue
                    
                nw_gp_dict = nw_ptype_dict[gp_name] = \
                    dict[PortMode, list[PortgroupMem]]()
                
                for pmode_str, pmode_list in gp_dict.items():
                    try:
                        port_mode = PortMode[pmode_str]
                        assert isinstance(pmode_list, list)
                    except:
                        continue
                    
                    nw_pmode_list = nw_gp_dict[port_mode] = \
                        list[PortgroupMem]()
                    
                    all_port_names = set[str]()
                    
                    for pg_mem_dict in pmode_list:
                        if not isinstance(pg_mem_dict, dict):
                            continue
                        
                        port_names = pg_mem_dict.get('port_names')
                        if not isinstance(port_names, list):
                            continue
                        
                        port_already_in_pg_mem = False
                        for port_name in port_names:
                            if port_name in all_port_names:
                                port_already_in_pg_mem = True
                                break
                                
                            if isinstance(port_name, str):
                                all_port_names.add(port_name)
                        
                        if port_already_in_pg_mem:
                            continue
                        
                        pg_mem = PortgroupMem.from_new_dict(pg_mem_dict)
                        pg_mem.group_name = gp_name
                        pg_mem.port_type = port_type
                        pg_mem.port_mode = port_mode
                        
                        nw_pmode_list.append(pg_mem)
    
    def _eat_json_old(self, json_list: list[dict]):
        for pg_mem_dict in json_list:
            pg_mem = PortgroupMem.from_serialized_dict(pg_mem_dict)
            
            ptype_dict = self.get(pg_mem.port_type)
            if ptype_dict is None:
                ptype_dict = self[pg_mem.port_type] = \
                    dict[str, dict[PortMode, list[PortgroupMem]]]()
            
            gp_name_dict = ptype_dict.get(pg_mem.group_name)
            if gp_name_dict is None:
                gp_name_dict = ptype_dict[pg_mem.group_name] = \
                    dict[PortMode, list[PortgroupMem]]()
            
            pmode_list = gp_name_dict.get(pg_mem.port_mode)
            if pmode_list is None:
                pmode_list = gp_name_dict[pg_mem.port_mode] = \
                    list[PortgroupMem]()

            all_port_names = set[str]()
            for portgroup_mem in pmode_list:
                for port_name in portgroup_mem.port_names:
                    all_port_names.add(port_name)
            
            for port_name in pg_mem.port_names:
                if port_name in all_port_names:
                    break
            else:
                pmode_list.append(pg_mem)

    def eat_json(self, json_obj: Union[list, dict]):
        if isinstance(json_obj, dict):
            self._eat_json_new(json_obj)
        elif isinstance(json_obj, list):
            self._eat_json_old(json_obj)
    
    def to_json(self) -> dict[str, dict[str, dict[str, list[dict]]]]:
        out_dict = dict[str, dict[str, dict[str, list[dict]]]]()
        for port_type, ptype_dict in self.items():
            out_dict[port_type.name] = js_ptype_dict = {}
            for gp_name, group_dict in ptype_dict.items():
                js_ptype_dict[gp_name] = {}

                for port_mode, pmode_list in group_dict.items():
                    pg_list = js_ptype_dict[gp_name][port_mode.name] = []
                    for pg_mem in pmode_list:
                        pg_list.append(pg_mem.as_new_dict())
        
        return out_dict
    
    def iter_all_portgroups(self) -> Iterator[PortgroupMem]:
        for ptype_dict in self.values():
            for gpname_dict in ptype_dict.values():
                for pmode_list in gpname_dict.values():
                    for pg_mem in pmode_list:
                        yield pg_mem
                        
    def iter_portgroups(
            self, group_name: str, port_type: PortType,
            port_mode: PortMode) -> Iterator[PortgroupMem]:
        ptype_dict = self.get(port_type)
        if ptype_dict is None:
            return

        group_dict = ptype_dict.get(group_name)
        if group_dict is None:
            return

        pmode_list = group_dict.get(port_mode)
        if pmode_list is None:
            return
        
        for pg_mem in pmode_list:
            yield pg_mem
                        
    def save_portgroup(self, pg_mem: PortgroupMem):
        ptype_dict = self.get(pg_mem.port_type)
        if ptype_dict is None:
            ptype_dict = self[pg_mem.port_type] = \
                dict[str, dict[PortMode, list[PortgroupMem]]]()
        
        gpname_dict = ptype_dict.get(pg_mem.group_name)
        if gpname_dict is None:
            gpname_dict = ptype_dict[pg_mem.group_name] = \
                dict[PortMode, list[PortgroupMem]]()
        
        pmode_list = gpname_dict.get(pg_mem.port_mode)
        if pmode_list is None:
            pmode_list = gpname_dict[pg_mem.port_mode] = \
                list[PortgroupMem]()
        
        rm_pg_mems = list[PortgroupMem]()
        
        for sv_pg_mem in pmode_list:
            for port_name in sv_pg_mem.port_names:
                if port_name in pg_mem.port_names:
                    rm_pg_mems.append(sv_pg_mem)
                    break
        
        for rm_pg_mem in rm_pg_mems:
            pmode_list.remove(rm_pg_mem)
        
        pmode_list.append(pg_mem)
