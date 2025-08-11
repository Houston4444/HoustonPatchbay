from typing import Any, Union, Optional

from .base_enums import (
    BoxLayoutMode, BoxFlag,
    PortTypesViewFlag, GroupPosFlag, PortMode)


class BoxPos:
    pos: tuple[int, int]
    zone: str = ''
    layout_mode: BoxLayoutMode = BoxLayoutMode.AUTO
    flags: BoxFlag = BoxFlag.NONE

    def __init__(self, box_pos: Optional['BoxPos']=None) -> None:
        if box_pos:
            self.eat(box_pos)
            return

        self.pos = (0, 0)
    
    def __repr__(self) -> str:
        return f"BoxPos({self.pos})"
    
    def _set_flag(self, flag: BoxFlag, yesno: bool):
        if yesno:
            self.flags |= flag
        else:
            self.flags &= ~flag
    
    def eat(self, other: 'BoxPos'):
        # faster way I found to copy a tuple without
        # linking to it.
        # write self.pos = tuple(box_pos.pos) does not
        # copy the tuple.
        self.pos = tuple(list(other.pos))
        self.zone = other.zone
        self.layout_mode = other.layout_mode
        self.flags = other.flags
    
    def is_wrapped(self) -> bool:
        return bool(self.flags & BoxFlag.WRAPPED)
    
    def is_hidden(self) -> bool:
        return bool(self.flags & BoxFlag.HIDDEN)

    def set_wrapped(self, yesno: bool):
        self._set_flag(BoxFlag.WRAPPED, yesno)
            
    def set_hidden(self, yesno: bool):
        self._set_flag(BoxFlag.HIDDEN, yesno)

    def copy(self) -> 'BoxPos':
        return BoxPos(self)


class GroupPos:
    '''Object assigned to a group in a specific view.
    It contains its splited state, box positions,
    wrapped and hidden states.'''
    ARG_TYPES = 'isiiiiiiiiiiiii'

    port_types_view: PortTypesViewFlag = PortTypesViewFlag.NONE
    group_name: str = ""
    flags: GroupPosFlag = GroupPosFlag.NONE
    'contains now only splitted state.'
    
    hidden_sides: PortMode = PortMode.NULL
    'will be removed when HoustonPatchbay will be updated in Patchance.'
    
    boxes: dict[PortMode, BoxPos]
    fully_set: bool = True
    'If false, it will ask the program to choose the splitted state.'
    
    has_sure_existence: bool = True
    '''If false, this GroupPos may reffers to a group without ports
    in its port_types_view.'''
    
    def __init__(self):
        self.boxes = dict[PortMode, BoxPos]()

        for port_mode in PortMode.in_out_both():
            self.boxes[port_mode] = BoxPos()
    
    @staticmethod
    def is_point(value: Any) -> bool:
        if not isinstance(value, (list, tuple)):
            return False
        
        if len(value) != 2:
            return False
        
        for v in value:
            if not isinstance(v, int):
                return False
        return True

    @staticmethod
    def from_serialized_dict(
            src: dict[str, Any], version=(0, 14, 0)) -> 'GroupPos':
        'returns a GroupPos from an old json file dict.'
        port_types_view = src.get('port_types_view')
        group_name = src.get('group_name')
        null_xy = src.get('null_xy')
        in_xy = src.get('in_xy')
        out_xy = src.get('out_xy')
        flags = src.get('flags')
        layout_modes = src.get('layout_modes')
        hidden_sides = src.get('hidden_sides')
        
        gpos = GroupPos()
        
        if isinstance(port_types_view, int):
            gpos.port_types_view = PortTypesViewFlag(port_types_view)
            if version < (0, 13, 0):
                if port_types_view == 3:
                    gpos.port_types_view = PortTypesViewFlag.ALL
            elif version < (0, 14, 0):
                if port_types_view == 15:
                    gpos.port_types_view = PortTypesViewFlag.ALL
                    
        if isinstance(group_name, str):
            gpos.group_name = group_name
        if isinstance(flags, int):
            gpos.flags = GroupPosFlag(flags)
        if isinstance(hidden_sides, int):
            try:
                gpos.hidden_sides = PortMode(hidden_sides)
            except:
                gpos.hidden_sides = PortMode.NULL
        
        for port_mode in PortMode.in_out_both():
            if port_mode is PortMode.INPUT:
                if GroupPos.is_point(in_xy):
                    gpos.boxes[port_mode].pos = tuple(in_xy)
                wrapped = bool(gpos.flags & GroupPosFlag.WRAPPED_INPUT)
            elif port_mode is PortMode.OUTPUT:
                if GroupPos.is_point(out_xy):
                    gpos.boxes[port_mode].pos = tuple(out_xy)
                wrapped = bool(gpos.flags & GroupPosFlag.WRAPPED_OUTPUT)
            else:
                if GroupPos.is_point(null_xy):
                    gpos.boxes[port_mode].pos = tuple(null_xy)
                wrapped = bool(gpos.flags & (GroupPosFlag.WRAPPED_INPUT
                                             | GroupPosFlag.WRAPPED_OUTPUT)
                               == (GroupPosFlag.WRAPPED_INPUT
                                   | GroupPosFlag.WRAPPED_OUTPUT))

            try:
                assert layout_modes is not None
                gpos.boxes[port_mode].layout_mode = BoxLayoutMode(
                    layout_modes[str(int(port_mode))])
            except:
                gpos.boxes[port_mode].layout_mode = BoxLayoutMode.AUTO

            gpos.boxes[port_mode].set_wrapped(wrapped)
        
        return gpos

    def copy(self) -> 'GroupPos':
        group_pos = GroupPos()
        group_pos.__dict__ = self.__dict__.copy()

        group_pos.boxes = dict[PortMode, BoxPos]()
        for port_mode, box_pos in self.boxes.items():
            group_pos.boxes[port_mode] = box_pos.copy()

        return group_pos

    @staticmethod
    def from_new_dict(ptv: PortTypesViewFlag, group_name: str,
                      in_dict: dict) -> 'GroupPos':
        'return a new GroupPos from a new json file dict.'

        gpos = GroupPos()
        gpos.port_types_view = ptv
        gpos.group_name = group_name

        if (in_dict.get('OUTPUT') is not None
                or in_dict.get('INPUT') is not None):
            gpos.flags |= GroupPosFlag.SPLITTED

        for port_mode_str, box_dict in in_dict.items():
            if not (isinstance(port_mode_str, str)
                    and isinstance(box_dict, dict)):
                continue

            port_mode = PortMode.NULL
            for pmode_str in port_mode_str.split('|'):
                for p_mode in PortMode.INPUT, PortMode.OUTPUT:
                    if p_mode.name == pmode_str.upper():
                        port_mode |= p_mode
            
            gpos.boxes[port_mode] = BoxPos()
            
            for key, value in box_dict.items():
                if key == 'pos':
                    if not (isinstance(value, list)
                            and len(value) == 2
                            and isinstance(value[0], int)
                            and isinstance(value[1], int)):
                        continue
                    
                    gpos.boxes[port_mode].pos = tuple(value)
                
                elif key == 'flags':
                    if not isinstance(value, str):
                        continue
                    
                    flags_str_list = [v.upper() for v in value.split('|')]
                    
                    box_flags = BoxFlag.NONE
                    for box_flag in BoxFlag:
                        if box_flag.name in flags_str_list:
                            box_flags |= box_flag
                    
                    gpos.boxes[port_mode].flags = box_flags
                    
                elif key == 'layout_mode':
                    if not isinstance(value, str):
                        continue
                    
                    layout_mode = BoxLayoutMode.AUTO
                    if value.upper() == 'LARGE':
                        layout_mode = BoxLayoutMode.LARGE
                    elif value.upper() == 'HIGH':
                        layout_mode = BoxLayoutMode.HIGH
                    
                    gpos.boxes[port_mode].layout_mode = layout_mode

        if not gpos.is_splitted():
            for port_mode in PortMode.INPUT, PortMode.OUTPUT:
                gpos.boxes[port_mode].flags = gpos.boxes[PortMode.BOTH].flags

        return gpos

    def as_new_dict(self) -> dict:
        d = {}        
        splitted = bool(self.flags & GroupPosFlag.SPLITTED)

        for port_mode, box in self.boxes.items():
            if port_mode is PortMode.BOTH and splitted:
                continue
            if not splitted and port_mode is not PortMode.BOTH:
                continue

            box_dict = {'pos': box.pos}
            if box.layout_mode is not BoxLayoutMode.AUTO:
                box_dict['layout_mode'] = box.layout_mode.name #type:ignore
            
            box_flag_list = list[str]()
            for box_flag in BoxFlag:
                if box.flags & box_flag:
                    box_flag_list.append(box_flag.name) #type:ignore
            
            if box_flag_list:
                box_dict['flags'] = '|'.join(box_flag_list) #type:ignore
            
            port_mode_names = list[str]()
            for p_mode in PortMode.INPUT, PortMode.OUTPUT:
                if port_mode & p_mode:
                    port_mode_names.append(p_mode.name) #type:ignore
            
            if not port_mode_names:
                # should not happen
                # TODO log
                continue
            
            d['|'.join(port_mode_names)] = box_dict

        return d

    def to_arg_list(self) -> list[Union[str, int]]:
        arg_list = list[Union[str, int]]()

        arg_list.append(self.port_types_view.value)
        arg_list.append(self.group_name)
        arg_list.append(self.flags.value)
        
        for port_mode in PortMode.in_out_both():
            arg_list.append(self.boxes[port_mode].pos[0])
            arg_list.append(self.boxes[port_mode].pos[1])
            arg_list.append(self.boxes[port_mode].flags.value)
            arg_list.append(self.boxes[port_mode].layout_mode.value)
        
        return arg_list
    
    @staticmethod
    def from_arg_list(arg_tuple: tuple[str | int, ...]) -> 'GroupPos':
        gpos = GroupPos()
        
        if len(arg_tuple) != 15:
            return gpos
        
        ptv_int, gp_name, gp_flags, *box_args = arg_tuple # type:ignore
        if not isinstance(ptv_int, int):
            return gpos
        if not isinstance(gp_name, str):
            return gpos
        if not isinstance( gp_flags, int):
            return gpos
        
        for box_arg in box_args:
            if not isinstance(box_arg, int):
                return gpos
            
        box_args: list[int]        
        gpos.port_types_view = PortTypesViewFlag(ptv_int)
        gpos.group_name = gp_name
        gpos.flags = GroupPosFlag(gp_flags)

        for port_mode in PortMode.in_out_both():
            gpos.boxes[port_mode].pos = (box_args.pop(0), box_args.pop(0))
            gpos.boxes[port_mode].flags = BoxFlag(box_args.pop(0))
            gpos.boxes[port_mode].layout_mode = BoxLayoutMode(box_args.pop(0))
        
        return gpos
    
    def is_splitted(self) -> bool:
        return bool(self.flags & GroupPosFlag.SPLITTED)
    
    def set_splitted(self, yesno: bool):
        if yesno:
            self.flags |= GroupPosFlag.SPLITTED
        else:
            self.flags &= ~GroupPosFlag.SPLITTED

    def hidden_port_modes(self) -> PortMode:
        if self.is_splitted():
            hd_port_mode = PortMode.NULL
            for port_mode in PortMode.INPUT, PortMode.OUTPUT:
                if self.boxes[port_mode].is_hidden():
                    hd_port_mode |= port_mode
            return hd_port_mode
        
        if self.boxes[PortMode.BOTH].is_hidden():
            return PortMode.BOTH
        return PortMode.NULL

    def set_hidden_port_mode(self, hidden_port_mode: PortMode):
        for port_mode in PortMode.in_out_both():
            self.boxes[port_mode].set_hidden(
                bool(hidden_port_mode & port_mode))
    
    def needs_redraw(self, gpos: 'GroupPos') -> bool:
        if self.is_splitted() is not gpos.is_splitted():
            return True
        
        if self.hidden_port_modes() is not gpos.hidden_port_modes():
            return True
        
        if self.is_splitted():
            for port_mode in PortMode.OUTPUT, PortMode.INPUT:
                if (self.boxes[port_mode].layout_mode
                        is not gpos.boxes[port_mode].layout_mode):
                    return True
        
        else:
            if (self.boxes[PortMode.BOTH].layout_mode
                    is not self.boxes[PortMode.BOTH].layout_mode):
                return True
        
        return False
    
    def apply_only_diffs(self, orig_gpos: 'Optional[GroupPos]', new_gpos: 'GroupPos'):
        '''Apply to this config gpos only what is different between
        session gpos orig_gpos (at load) and new_gpos (now)'''
        
        if (orig_gpos is None
                or new_gpos.is_splitted() is not orig_gpos.is_splitted()):
            if orig_gpos is not None:
                self.set_splitted(new_gpos.is_splitted())

            for port_mode in PortMode.in_out_both():
                self.boxes[port_mode] = new_gpos.boxes[port_mode].copy()
            return
        
        for port_mode in PortMode.in_out_both():
            box = self.boxes[port_mode]
            orig_box = orig_gpos.boxes[port_mode]
            new_box = new_gpos.boxes[port_mode]
            
            if new_box.is_hidden() is not orig_box.is_hidden():
                box.set_hidden(new_box.is_hidden())
            if new_box.is_wrapped() is not orig_box.is_wrapped():
                box.set_wrapped(new_box.is_wrapped())
            if new_box.layout_mode is not orig_box.layout_mode:
                box.layout_mode = new_box.layout_mode
            if new_box.pos != orig_box.pos:
                box.pos = new_box.pos
