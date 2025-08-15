from typing import Optional, Any, Union, Iterator

from .base_enums import PortTypesViewFlag
from .group_pos import GroupPos


class ViewData:
    name: str
    default_port_types_view: PortTypesViewFlag
    is_white_list: bool
    
    def __init__(self, default_ptv: PortTypesViewFlag):
        self.name = ''
        self.default_port_types_view = default_ptv
        self.is_white_list = False
        self.ptvs = dict[PortTypesViewFlag, dict[str, GroupPos]]()
    
    def __eq__(self, view_data: 'ViewData') -> bool:        
        return (self.name == view_data.name
                and (self.default_port_types_view
                     is view_data.default_port_types_view)
                and self.is_white_list is view_data.is_white_list)
    
    def copy(self, with_positions=True) -> 'ViewData':
        view_data = ViewData(self.default_port_types_view)
        view_data.name = self.name
        view_data.is_white_list = self.is_white_list

        if with_positions:
            for ptv, ptv_dict in self.ptvs.items():
                view_data.ptvs[ptv] = dict[str, GroupPos]()
                for gp_name, gpos in ptv_dict.items():
                    view_data.ptvs[ptv][gp_name] = gpos.copy()

        return view_data
    

class ViewsDict(dict[int, ViewData]):
    def __init__(self, ensure_one_view=True):
        super().__init__()
        self._ensure_one_view = ensure_one_view
        if self._ensure_one_view:
            self[1] = ViewData(PortTypesViewFlag.ALL)

    def _sort_views_by_index(self):
        sorted_indexes = sorted([k for k in self.keys()])
        tmp_copy = dict[int, ViewData]()
        for i in sorted_indexes:
            tmp_copy[i] = self[i]
        
        super().clear()
        for i, vd in tmp_copy.items():
            self[i] = vd        
    
    def copy(self, with_positions=True) -> 'ViewsDict':
        views_dict = ViewsDict(ensure_one_view=self._ensure_one_view)
        for index, view_data in self.items():
            views_dict[index] = view_data.copy(with_positions=with_positions)
        return views_dict

    def eat_views_dict_datas(self, views_dict: 'ViewsDict'):
        '''For all view, take all property of the incoming views_dict
        except group positions.'''

        for view_num, view_data in self.items():
            vdata = views_dict.get(view_num)
            if vdata is None:
                continue
            
            view_data.default_port_types_view = vdata.default_port_types_view
            view_data.name = vdata.name
            view_data.is_white_list = vdata.is_white_list

    def clear(self):
        super().clear()
        if self._ensure_one_view:
            self[1] = ViewData(PortTypesViewFlag.ALL)
    
    def first_view_num(self) -> Optional[int]:
        '''if this instance has "ensure_one_view", 
        we are sure this returns a valid int.'''
        for key in self.keys():
            return key
    
    def eat_json_list(self, json_list: list, clear=False):
        if not isinstance(json_list, list):
            return
        
        if clear:
            super().clear()

        for view_dict in json_list:
            if not isinstance(view_dict, dict):
                continue
            
            index = view_dict.get('index')
            if not isinstance(index, int):
                continue
            
            name = view_dict.get('name')
            default_ptv_str = view_dict.get('default_port_types')
            is_white_list = view_dict.get('is_white_list')
            
            if not isinstance(default_ptv_str, str):
                continue
            
            default_ptv = PortTypesViewFlag.from_config_str(default_ptv_str)
            if default_ptv is PortTypesViewFlag.NONE:
                continue
            
            view_data = self.get(index)
            if view_data is None:
                view_data = self[index] = ViewData(default_ptv)
            else:
                view_data.default_port_types_view = default_ptv

            if isinstance(name, str):
                view_data.name = name
                
            if isinstance(is_white_list, bool):
                view_data.is_white_list = is_white_list
                
            for ptv_str, gp_dict in view_dict.items():
                if not (isinstance(ptv_str, str)
                        and isinstance(gp_dict, dict)):
                    continue
            
                ptv = PortTypesViewFlag.from_config_str(ptv_str)
                if ptv is PortTypesViewFlag.NONE:
                    continue
                
                nw_ptv_dict = view_data.ptvs.get(ptv)
                if nw_ptv_dict is None:
                    nw_ptv_dict = view_data.ptvs[ptv] = dict[str, GroupPos]()
                
                for gp_name, gpos_dict in gp_dict.items():
                    nw_ptv_dict[gp_name] = GroupPos.from_new_dict(
                        ptv, gp_name, gpos_dict)

        self._sort_views_by_index()
        
        if self._ensure_one_view and not self.keys():
            self[1] = ViewData(PortTypesViewFlag.ALL)
                    
    def to_json_list(self) -> list[dict[str, Any]]:
        self._sort_views_by_index()
        
        out_list = list[dict[str, Any]]()
        
        for index, view_data in self.items():
            out_dict: dict[str, Any] = {'index': index}

            if view_data.name:
                out_dict['name'] = view_data.name
            if view_data.default_port_types_view:
                out_dict['default_port_types'] = \
                    view_data.default_port_types_view.name
            if view_data.is_white_list:
                out_dict['is_white_list'] = True
            
            for ptv, ptv_dict in view_data.ptvs.items():
                if ptv.name is None:
                    continue

                js_ptv_dict = out_dict[ptv.name] = \
                    dict[str, dict[str, dict]]()
                for gp_name, gpos in ptv_dict.items():
                    if gpos.has_sure_existence:
                        js_ptv_dict[gp_name] = gpos.as_new_dict()
            
            out_list.append(out_dict)

        return out_list

    def add_old_json_gpos(
            self, old_gpos_dict: dict,
            version: Optional[tuple[int, int, int]]=None):
        if version is None:
            gpos = GroupPos.from_serialized_dict(old_gpos_dict)
        else:
            gpos = GroupPos.from_serialized_dict(old_gpos_dict, version)
        
        view_one = self.get(1)
        if view_one is None:
            view_one = self[1] = ViewData(PortTypesViewFlag.ALL)
        
        ptv_dict = view_one.ptvs.get(gpos.port_types_view)
        if ptv_dict is None:
            ptv_dict = view_one.ptvs[gpos.port_types_view] = \
                dict[str, GroupPos]()
        
        ptv_dict[gpos.group_name] = gpos

    def short_data_states(self) -> dict[int, dict[str, Union[str, bool]]]:
        '''Used by RaySession to send short OSC str messages
        about view datas'''

        out_dict = dict[int, dict[str, Union[str, bool]]]()
        
        for index, view_data in self.items():
            view_dict = {}
            if view_data.name:
                view_dict['name'] = view_data.name
            if view_data.default_port_types_view is not PortTypesViewFlag.ALL:
                view_dict['default_ptv'] = \
                    view_data.default_port_types_view.name
            if view_data.is_white_list:
                view_dict['is_white_list'] = True
            out_dict[index] = view_dict
        return out_dict
    
    def update_from_short_data_states(
            self, data_states: dict[str, dict[str, Union[str, bool]]]):
        
        if not isinstance(data_states, dict):
            return
        
        for index_str, view_state in data_states.items():
            if not (isinstance(index_str, str) and index_str.isdigit()
                    and isinstance(view_state, dict)):
                return
        
        indexes = set[int]()
        
        for index_str, view_state in data_states.items():
            index = int(index_str)
            indexes.add(index)
            
            view_data = self.get(index)
            if view_data is None:
                continue
            
            name = view_state.get('name')
            if isinstance(name, str):
                view_data.name = name
            else:
                view_data.name = ''
                
            default_ptv_str = view_state.get('default_ptv')
            if isinstance(default_ptv_str, str):
                view_data.default_port_types_view = \
                    PortTypesViewFlag.from_config_str(default_ptv_str)
            else:
                view_data.default_port_types_view = PortTypesViewFlag.ALL
            
            is_white_list = view_state.get('is_white_list')
            if isinstance(is_white_list, bool):
                view_data.is_white_list = is_white_list
            else:
                view_data.is_white_list = False

        rm_indexes = set[int]()
        for index in self.keys():
            if index not in indexes:
                rm_indexes.add(index)
                
        for rm_index in rm_indexes:
            self.pop(rm_index)
            
        if self._ensure_one_view and not self.keys():
            self[1] = ViewData(PortTypesViewFlag.ALL)
    
    def add_group_pos(self, view_num: int, gpos: GroupPos):
        view_data = self.get(view_num)
        if view_data is None:
            view_data = self[view_num] = ViewData(PortTypesViewFlag.ALL)
            
        ptv_dict = view_data.ptvs.get(gpos.port_types_view)
        if ptv_dict is None:
            ptv_dict = view_data.ptvs[gpos.port_types_view] = \
                dict[str, GroupPos]()
        
        ptv_dict[gpos.group_name] = gpos

    def clear_absents(
            self, view_num: int, ptv: PortTypesViewFlag, presents: set[str]):
        view_data = self.get(view_num)
        if view_data is None:
            return
        
        ptv_dict = view_data.ptvs.get(ptv)
        if ptv_dict is None:
            return
        
        rm_list = list[str]()
        for group_name in ptv_dict.keys():
            if group_name not in presents:
                rm_list.append(group_name)
        
        for rm_group_name in rm_list:
            ptv_dict.pop(rm_group_name)

    def get_group_pos(
            self, view_num: int, ptv: PortTypesViewFlag,
            group_name: str) -> Optional[GroupPos]:
        view_data = self.get(view_num)
        if view_data is None:
            return
        
        ptv_dict = view_data.ptvs.get(ptv)
        if ptv_dict is None:
            return
        
        return ptv_dict.get(group_name)

    def iter_group_poses(
            self, view_num: Optional[int] =None) -> Iterator[GroupPos]:
        if view_num is None:
            for view_data in self.values():
                for ptv_dict in view_data.ptvs.values():
                    for gpos in ptv_dict.values():
                        yield gpos
                        
            return
        
        view_data = self.get(view_num)
        if view_data is None:
            return

        for ptv_dict in view_data.ptvs.values():
            for gpos in ptv_dict.values():
                yield gpos
    
    def add_view(
            self, view_num: Optional[int]=None,
            default_ptv=PortTypesViewFlag.ALL) -> Optional[int]:
        if view_num is None:
            new_num = 1
            while True:
                for num in self.keys():
                    if new_num == num:
                        new_num += 1
                        break
                else:
                    break
        else:
            new_num = view_num

        if new_num in self.keys():
            return None

        self[new_num] = ViewData(default_ptv)
        self._sort_views_by_index()
        return new_num

    def remove_view(self, index: int):
        if len(self.keys()) <= 1:
            return

        if index in self.keys():
            self.pop(index)
            
        if self._ensure_one_view and not self.keys():
            self[1] = ViewData(PortTypesViewFlag.ALL)    

    def change_view_number(self, from_num: int, to_num: int):
        if not from_num in self.keys():
            return

        if to_num in self.keys():
            self[from_num], self[to_num] = self[to_num], self[from_num]
        else:
            self[to_num] = self.pop(from_num)
            
        self._sort_views_by_index()


class ViewsDictEnsureOne(ViewsDict):
    def __init__(self):
        super().__init__()
        self._ensure_one_view = True
        self[1] = ViewData(PortTypesViewFlag.ALL)
    
    def _ensure_one(self):
        if not self.keys():
            self[1] = ViewData(PortTypesViewFlag.ALL)
    
    def copy(self, with_positions=True) -> 'ViewsDictEnsureOne':
        views_dict = ViewsDictEnsureOne()
        for index, view_data in self.items():
            views_dict[index] = view_data.copy(with_positions=with_positions)
        return views_dict
    
    def clear(self):
        super().clear()
        self._ensure_one()
    
    def eat_json_list(self, json_list: list, clear=False):
        super().eat_json_list(json_list, clear)
        self._ensure_one()
    
    def update_from_short_data_states(
            self, data_states: dict[str, dict[str, Union[str, bool]]]):
        super().update_from_short_data_states(data_states)
        self._ensure_one()
            
    def remove_view(self, index: int):
        super().remove_view(index)
        self._ensure_one()
    
    def first_view_num(self) -> int:
        for key in self.keys():
            return key
        
        # should be strictly impossible
        return -1