import json
from enum import Enum, IntEnum, IntFlag, auto
from typing import Iterator, Optional, Union, Any
from dataclasses import dataclass


from PyQt5.QtCore import QPoint, QPointF


def from_json_to_str(input_dict: dict[str, Any]) -> str:
    json_str = json.dumps(input_dict, indent=2)

    final_str = ''
    comp_line = ''

    for line in json_str.splitlines():
        if line.strip() == '"pos": [':
            comp_line = line
            continue
        
        if comp_line:
            comp_line += line.strip()
            if comp_line.endswith(','):
                comp_line += ' '

            if line.strip().startswith(']'):
                final_str += comp_line
                final_str += '\n'
                comp_line = ''
        else:
            final_str += line
            final_str += '\n'
            
    return final_str


class PortMode(IntFlag):
    NULL = 0x00
    INPUT = 0x01
    OUTPUT = 0x02
    BOTH = INPUT | OUTPUT
    
    def opposite(self) -> 'PortMode':
        if self is PortMode.INPUT:
            return PortMode.OUTPUT
        if self is PortMode.OUTPUT:
            return PortMode.INPUT
        if self is PortMode.BOTH:
            return PortMode.NULL
        if self is PortMode.NULL:
            return PortMode.BOTH
        return PortMode.NULL

    @staticmethod
    def in_out_both() -> Iterator['PortMode']:
        yield PortMode.INPUT
        yield PortMode.OUTPUT
        yield PortMode.BOTH


class PortType(IntFlag):
    NULL = 0x00
    AUDIO_JACK = 0x01
    MIDI_JACK = 0x02
    MIDI_ALSA = 0x04
    VIDEO = 0x08
    PARAMETER = 0x10


class PortSubType(IntFlag):
    '''a2j ports are MIDI ports, we only specify a decoration for them.
    CV ports are audio ports, but we prevent to connect an output CV port
    to a regular audio port to avoid material destruction, CV ports also
    look different, simply because this is absolutely not the same use.'''
    REGULAR = 0x01
    CV = 0x02
    A2J = 0x04

class BoxType(Enum):
    APPLICATION = 0
    HARDWARE = 1
    MONITOR = 2
    DISTRHO = 3
    FILE = 4
    PLUGIN = 5
    LADISH_ROOM = 6
    CLIENT = 7
    INTERNAL = 8
    
    def __lt__(self, other: 'BoxType'):
        return self.value < other.value
    

class BoxLayoutMode(IntEnum):
    'Define the way ports are put in a box'

    AUTO = 0
    '''Choose the layout between HIGH or LARGE
    within the box area.'''
    
    HIGH = 1
    '''In the case there are only INPUT or only OUTPUT ports,
    the title will be on top of the box.
    In the case there are both INPUT and OUTPUT ports,
    ports will be displayed from top to bottom, whatever they
    are INPUT or OUTPUT.'''
    
    LARGE = 2
    '''In the case there are only INPUT or only OUTPUT ports,
    the title will be on a side of the box.
    In the case there are both INPUT and OUTPUT ports,
    ports will be displayed in two columns, left for INPUT, 
    right for OUTPUT.'''


class BoxFlag(IntFlag):
    NONE = 0x00
    WRAPPED = auto()
    HIDDEN = auto()


class GroupPosFlag(IntFlag):
    # used in some config files,
    # it explains why some numbers are missing.
    NONE = 0x00
    SPLITTED = 0x04          # still used
    WRAPPED_INPUT = 0x10     # used for old config
    WRAPPED_OUTPUT = 0x20    # used fot old config
    HAS_BEEN_SPLITTED = 0x40 # Not used anymore


class PortTypesViewFlag(IntFlag):
    NONE = 0x00
    AUDIO = 0x01
    MIDI = 0x02
    CV = 0x04
    VIDEO = 0x08
    ALSA = 0x10
    ALL = AUDIO | MIDI | CV | VIDEO | ALSA

    def to_config_str(self):
        if self is PortTypesViewFlag.ALL:
            return 'ALL'

        str_list = list[str]()        
        for ptv in PortTypesViewFlag:
            if ptv in (PortTypesViewFlag.NONE, PortTypesViewFlag.ALL):
                continue

            if self & ptv:
                str_list.append(ptv.name)
        return '|'.join(str_list)
    
    @staticmethod
    def from_config_str(input_str: str) -> 'PortTypesViewFlag':
        if not isinstance(input_str, str):
            return PortTypesViewFlag.NONE

        if input_str.upper() == 'ALL':
            return PortTypesViewFlag.ALL

        ret = PortTypesViewFlag.NONE

        names = [nm.upper() for nm in input_str.split('|')]
        for ptv in PortTypesViewFlag:
            if ptv in (PortTypesViewFlag.NONE, PortTypesViewFlag.ALL):
                continue
                
            if ptv.name in names:
                ret |= ptv

        return ret


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

    def to_point(self) -> QPoint:
        return QPoint(*self.pos)
    
    def to_pointf(self) -> QPointF:
        return QPointF(*self.pos)

    def set_pos_from_pt(self, point: Union[QPoint, QPointF]):
        self.pos = (int(point.x()), int(point.y()))

    def copy(self) -> 'BoxPos':
        return BoxPos(self)


class GroupPos:
    '''Object assigned to a group in a specific view.
    It contains its splited state, box positions,
    wrapped and hidden states.'''
    
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
        in_zone = src.get('in_zone')
        out_zone = src.get('out_zone')
        both_zone = src.get('null_zone')
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
                if isinstance(in_zone, str):
                    gpos.boxes[port_mode].zone = in_zone
                if GroupPos.is_point(in_xy):
                    gpos.boxes[port_mode].pos = in_xy
                wrapped = bool(gpos.flags & GroupPosFlag.WRAPPED_INPUT)
            elif port_mode is PortMode.OUTPUT:
                if isinstance(out_zone, str):
                    gpos.boxes[port_mode].zone = out_zone
                if GroupPos.is_point(out_xy):
                    gpos.boxes[port_mode].pos = out_xy
                wrapped = bool(gpos.flags & GroupPosFlag.WRAPPED_OUTPUT)
            else:
                if isinstance(both_zone, str):
                    gpos.boxes[port_mode].zone = both_zone
                if GroupPos.is_point(null_xy):
                    gpos.boxes[port_mode].pos = null_xy
                wrapped = bool(gpos.flags & (GroupPosFlag.WRAPPED_INPUT
                                             | GroupPosFlag.WRAPPED_OUTPUT)
                               == (GroupPosFlag.WRAPPED_INPUT
                                   | GroupPosFlag.WRAPPED_OUTPUT))

            try:
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

        flags_str = in_dict.get('flags')
        if isinstance(flags_str, str):
            if flags_str.upper() == 'SPLITTED':
                gpos.flags |= GroupPosFlag.SPLITTED

        boxes_dict = in_dict.get('boxes')
        if isinstance(boxes_dict, dict):
            for port_mode_str, box_dict in boxes_dict.items():
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
        if splitted:
            d['flags'] = GroupPosFlag.SPLITTED.name
        
        boxes_dict = dict[PortMode, dict]()

        for port_mode, box in self.boxes.items():
            if port_mode is PortMode.BOTH and splitted:
                continue
            if not splitted and port_mode is not PortMode.BOTH:
                continue

            box_dict = {'pos': box.pos}
            if box.layout_mode is not BoxLayoutMode.AUTO:
                box_dict['layout_mode'] = box.layout_mode.name
            
            box_flag_list = list[str]()
            for box_flag in BoxFlag:
                if box.flags & box_flag:
                    box_flag_list.append(box_flag.name)
            
            if box_flag_list:
                box_dict['flags'] = '|'.join(box_flag_list)
            
            port_mode_names = list[str]()
            for p_mode in PortMode.INPUT, PortMode.OUTPUT:
                if port_mode & p_mode:
                    port_mode_names.append(p_mode.name)
            
            if not port_mode_names:
                # should not happen
                # TODO log
                continue
            
            boxes_dict['|'.join(port_mode_names)] = box_dict
        
        d['boxes'] = boxes_dict

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
    def from_arg_list(arg_tuple: tuple[Union[str, int], ...]) -> 'GroupPos':
        arg_list = list(arg_tuple)
        gpos = GroupPos()

        if True:
        # try:
            gpos.port_types_view = PortTypesViewFlag(arg_list.pop(0))
            gpos.group_name = arg_list.pop(0)
            gpos.flags = GroupPosFlag(arg_list.pop(0))
            
            for port_mode in PortMode.in_out_both():
                gpos.boxes[port_mode].pos = (arg_list.pop(0), arg_list.pop(0))
                gpos.boxes[port_mode].flags = BoxFlag(arg_list.pop(0))
                gpos.boxes[port_mode].layout_mode = BoxLayoutMode(
                    arg_list.pop(0))
        # except:
        #     print('group pos from arg list failed !!!')

        return gpos
    
    @staticmethod
    def args_types() -> str:
        return 'isiiiiiiiiiiiii'

    def as_serializable_dict(self, minimal=False):
        '''DEPRECATED, will be removed soon'''
        
        if not minimal:
            return {'port_types_view': self.port_types_view.value,
                    'group_name': self.group_name,
                    # 'null_zone': self.null_zone,
                    # 'in_zone': self.in_zone,
                    # 'out_zone': self.out_zone,
                    # 'null_xy': self.null_xy,
                    # 'in_xy': self.in_xy,
                    # 'out_xy': self.out_xy,
                    'flags': self.flags,
                    # 'layout_modes': self.layout_modes,
                    'hidden_sides': self.hidden_sides.value}
        
        out_dict = {'port_types_view': self.port_types_view.value,
                    'group_name': self.group_name}
        
        # if self.null_zone:
        #     out_dict['null_zone'] = self.null_zone
        # if self.in_zone:
        #     out_dict['in_zone'] = self.in_zone
        # if self.out_zone:
        #     out_dict['out_zone'] = self.out_zone

        # if self.null_xy != (0, 0):
        #     out_dict['null_xy'] = self.null_xy
        # if self.in_xy != (0, 0):
        #     out_dict['in_xy'] = self.in_xy
        # if self.out_xy != (0, 0):
        #     out_dict['out_xy'] = self.out_xy

        layout_modes = dict[int, int]()
        flags = self.flags
        flags &= ~GroupPosFlag.WRAPPED_INPUT
        flags &= ~GroupPosFlag.WRAPPED_OUTPUT
        
        for port_mode, box_pos in self.boxes.items():
            if box_pos.layout_mode is not BoxLayoutMode.AUTO:
                layout_modes[port_mode.value] = box_pos.layout_mode.value

            if box_pos.is_wrapped():
                if port_mode & PortMode.OUTPUT:
                    flags |= GroupPosFlag.WRAPPED_OUTPUT
                if port_mode & PortMode.INPUT:
                    flags |= GroupPosFlag.WRAPPED_INPUT
                
        if layout_modes:
            out_dict['layout_modes'] = layout_modes
        
        if self.flags is not GroupPosFlag.NONE:
            out_dict['flags'] = flags.value

        if self.hidden_sides:
            out_dict['hidden_sides'] = self.hidden_sides.value
            
        out_dict['null_xy'] = self.boxes[PortMode.BOTH].pos
        out_dict['in_xy'] = self.boxes[PortMode.INPUT].pos
        out_dict['out_xy'] = self.boxes[PortMode.OUTPUT].pos

        return out_dict
    
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
    
@dataclass
class ViewData:
    name: str
    default_port_types_view: PortTypesViewFlag
    is_white_list: bool
    
