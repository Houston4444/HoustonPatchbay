import json
from enum import Enum, IntEnum, IntFlag, auto
from typing import Iterator, Optional, Union, Any
import logging

_logger = logging.getLogger(__name__)


def from_json_to_str(input_dict: dict[str, Any]) -> str:
    '''for a canvas json dict ready to be saved,
    return a str containing the json contents with a 2 chars indentation
    and xy pos grouped on the same line.'''

    PATH_OPENING = 0
    PATH_IN = 1
    PATH_CLOSING = 2

    json_str = json.dumps(input_dict, indent=2)
    final_str = ''
    
    path = list[str]()
    path_step = PATH_IN
    
    for line in json_str.splitlines():
        strip = line.strip()
        
        if line.endswith(('{', '[')):
            path_name = ''
            if strip.startswith('"') and strip[:-1].endswith('": '):
                path_name = strip[1:-4]

            n_spaces = 0
            for c in line:
                if c != ' ':
                    break
                n_spaces += 1
            
            path = path[:(n_spaces // 2)]
            path.append(path_name)
            path_step = PATH_OPENING
        
        elif line.endswith(('],', ']', '},', '}')):
            path_step = PATH_CLOSING
        
        else:
            path_step = PATH_IN
        
        if len(path) > 1 and path[1] == 'views' and path[-1] == 'pos':
            # set box pos in one line
            if path_step == PATH_OPENING:
                final_str += line
            
            elif path_step == PATH_CLOSING:
                final_str += strip
                final_str += '\n'
                
            else:
                final_str += strip
                if line.endswith(','):
                    final_str += ' '
                
        elif len(path) >= 6 and path[1] == 'portgroups':
            # organize portgroups
            if len(path) == 6:
                if path_step == PATH_OPENING:
                    final_str += line
                    
                elif path_step == PATH_CLOSING:
                    final_str += strip
                    final_str += '\n'
                
                else:
                    # only concerns "above_metadatas"
                    final_str += line[1:]
            
            elif len(path) == 7 and path[-1] == 'port_names':
                if path_step == PATH_OPENING:
                    final_str += strip
                
                elif path_step == PATH_CLOSING:
                    final_str += strip
                    if line.endswith(','):
                        final_str += '\n'
                
                else:
                    final_str += strip
                    if line.endswith(','):
                        final_str += '\n'
                        for i in range(26):
                            final_str += ' '
            
            else:
                final_str += strip
                if strip.endswith(','):
                    final_str += ' '
            
        else:
            final_str += line
            final_str += '\n'

        if path_step == PATH_CLOSING:
            path = path[:-1]

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
                    gpos.boxes[port_mode].pos = in_xy
                wrapped = bool(gpos.flags & GroupPosFlag.WRAPPED_INPUT)
            elif port_mode is PortMode.OUTPUT:
                if GroupPos.is_point(out_xy):
                    gpos.boxes[port_mode].pos = out_xy
                wrapped = bool(gpos.flags & GroupPosFlag.WRAPPED_OUTPUT)
            else:
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
    def from_arg_list(arg_tuple: tuple[Union[str, int], ...]) -> 'GroupPos':
        arg_list = list(arg_tuple)
        gpos = GroupPos()

        try:
            gpos.port_types_view = PortTypesViewFlag(arg_list.pop(0))
            gpos.group_name = arg_list.pop(0)
            gpos.flags = GroupPosFlag(arg_list.pop(0))
            
            for port_mode in PortMode.in_out_both():
                gpos.boxes[port_mode].pos = (arg_list.pop(0), arg_list.pop(0))
                gpos.boxes[port_mode].flags = BoxFlag(arg_list.pop(0))
                gpos.boxes[port_mode].layout_mode = BoxLayoutMode(
                    arg_list.pop(0))
        except:
            print('group pos from arg list failed !!!')

        return gpos
    
    @staticmethod
    def args_types() -> str:
        return 'isiiiiiiiiiiiii'
    
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


class ViewData:
    name: str
    default_port_types_view: PortTypesViewFlag
    is_white_list: bool
    
    def __init__(self, default_ptv: PortTypesViewFlag):
        self.name = ''
        self.default_port_types_view = default_ptv
        self.is_white_list = False
        self.ptvs = dict[PortTypesViewFlag, dict[str, GroupPos]]()
    

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
    def from_arg_list(arg_tuple: tuple[Union[str, int], ...]) -> 'PortgroupMem':
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


def portgroups_mem_from_json(
        portgroups: Union[list[dict], dict]) -> \
            dict[PortType, dict[str, dict[PortMode, list[PortgroupMem]]]]:
    '''Used to set PatchbayManager.portgroups_memory from
    a json list or dict. This is a json list with old config files.'''
    portgroups_memory = dict[
        PortType, dict[str, dict[PortMode, list[PortgroupMem]]]]()
    
    if isinstance(portgroups, dict):
        for ptype_str, ptype_dict in portgroups.items():
            try:
                port_type = PortType[ptype_str]
                assert isinstance(ptype_dict, dict)
            except:
                continue

            nw_ptype_dict = portgroups_memory[port_type] = \
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
                    
    elif isinstance(portgroups, list): 
        for pg_mem_dict in portgroups:
            portgroups: list[dict]
            pg_mem = PortgroupMem.from_serialized_dict(pg_mem_dict)
            
            ptype_dict = portgroups_memory.get(pg_mem.port_type)
            if ptype_dict is None:
                ptype_dict = portgroups_memory[pg_mem.port_type] = \
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
            
            port_in_other_portgroup_mem = False

            for port_name in pg_mem.port_names:
                if port_name in all_port_names:
                    port_in_other_portgroup_mem = True
                    break
            
            if port_in_other_portgroup_mem:
                continue
            
            pmode_list.append(pg_mem)
    
    return portgroups_memory

def portgroups_memory_to_json(
        portgroups_memory: \
            dict[PortType, dict[str, dict[PortMode, list[PortgroupMem]]]]) -> \
                dict[str, dict[str, dict[str, list[dict]]]]:
    portgroups_dict = dict[str, dict[str, dict[str, dict]]]()

    for port_type, ptype_dict in portgroups_memory.items():
        portgroups_dict[port_type.name] = js_ptype_dict = {}
        for gp_name, group_dict in ptype_dict.items():
            js_ptype_dict[gp_name] = {}

            for port_mode, pmode_list in group_dict.items():
                pg_list = js_ptype_dict[gp_name][port_mode.name] = []
                for pg_mem in pmode_list:
                    pg_list.append(pg_mem.as_new_dict())

    return portgroups_dict
    

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

            if isinstance(name, str):
                view_data.name = name
                
            if isinstance(is_white_list, bool):
                view_data.is_white_list = bool
                
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
            out_dict = {'index': index}

            if view_data.name:
                out_dict['name'] = view_data.name
            if view_data.default_port_types_view:
                out_dict['default_port_types'] = \
                    view_data.default_port_types_view.name
            if view_data.is_white_list:
                out_dict['is_white_list'] = True
            
            for ptv, ptv_dict in view_data.ptvs.items():
                js_ptv_dict = out_dict[ptv.name] = \
                    dict[str, dict[str, dict]]()
                for gp_name, gpos in ptv_dict.items():
                    if gpos.has_sure_existence:
                        js_ptv_dict[gp_name] = gpos.as_new_dict()
            
            out_list.append(out_dict)

        return out_list

    def add_old_json_gpos(
            self, old_gpos_dict: dict, version: Optional[tuple[int]]=None):
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

    def short_data_states(self) -> list[dict[str, Union[str, bool]]]:
        '''Used by RaySession to send short OSC str messages
        about view datas'''

        out_list = list[dict[str, Union[str, bool]]]()
        for index, view_data in self.items():
            out_dict = {'index': index}
            if view_data.name:
                out_dict['name'] = view_data.name
            if view_data.default_port_types_view is not PortTypesViewFlag.ALL:
                out_dict['default_ptv'] = \
                    view_data.default_port_types_view.name
            if view_data.is_white_list:
                out_dict['is_white_list'] = True
            out_list.append(out_dict)
        return out_list
    
    def update_from_short_data_states(
            self, data_states: list[dict[str, Union[str, bool]]]):
        if not isinstance(data_states, list):
            return

        for view_state in data_states:
            if not isinstance(view_state, dict):
                return
        
        indexes = set[int]()
        
        for view_state in data_states:
            index = view_state.get('index')
            if not isinstance(index, int):
                continue
            
            indexes.add(index)
            
            view_data = self.get(index)
            if view_data is None:
                continue
            
            name = view_state.get('name')
            if isinstance(name, str):
                view_data.name = name
                
            default_ptv_str = view_state.get('default_ptv')
            if isinstance(default_ptv_str, str):
                view_data.default_port_types_view = \
                    PortTypesViewFlag.from_config_str(default_ptv_str)
                    
            is_white_list = view_state.get('is_white_list')
            if isinstance(is_white_list, bool):
                view_data.is_white_list = is_white_list
                
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