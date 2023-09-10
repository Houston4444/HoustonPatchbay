from typing import TYPE_CHECKING, Union


from .base_elements import (
    BoxType,
    GroupPos,
    BoxLayoutMode,
    PortMode,
    PortType,
    PortSubType,
    JackPortFlag,
    PortgroupMem)
from .base_port import Port
from .base_portgroup import Portgroup
from .base_connection import Connection

from .patchcanvas import patchcanvas

if TYPE_CHECKING:
    from .patchbay_manager import PatchbayManager
    

class Group:
    def __init__(self, manager: 'PatchbayManager', group_id: int,
                 name: str, group_position: GroupPos):
        self.manager = manager
        self.group_id = group_id
        self.name = name
        self.display_name = name
        self.ports = list[Port]()
        self.portgroups = list[Portgroup]()
        self._is_hardware = False
        self.client_icon = ''
        self.a2j_group = False
        self.in_canvas = False
        self.current_position = group_position
        self.uuid = 0
        
        self.has_gui = False
        self.gui_visible = False

        self.mdata_icon = ''

        self.cnv_name = ''
        self.cnv_box_type = BoxType.APPLICATION
        self.cnv_icon_name = ''

    def __repr__(self) -> str:
        return f"Group({self.name})"

    def port_pg_pos(self, port_id: int) -> tuple[int, int]:
        '''returns the port portgroup position index and portgroup len'''
        portgroup_id = 0

        for port in self.ports:
            if port.port_id == port_id:
                portgroup_id = port.portgroup_id
                break

        if not portgroup_id:
            return (0, 1)
        
        for portgroup in self.portgroups:
            if portgroup.portgroup_id == portgroup_id:
                i = 0
                for port in portgroup.ports:
                    if port.port_id == port_id:
                        return (i, len(portgroup.ports))
                    i += 1

        return (0, 1)

    def update_ports_in_canvas(self):
        for port in self.ports:
            port.rename_in_canvas()

    def add_to_canvas(self):
        if self.in_canvas:
            return

        box_type, icon_name = self._get_box_type_and_icon()

        gpos = self.current_position
        do_split = gpos.is_splitted()

        self.display_name = self.display_name.replace('.0/', '/').replace('_', ' ')
        
        display_name = self.name
        if self.manager.use_graceful_names:
            display_name = self.display_name
        
        layout_modes_ = dict[PortMode, BoxLayoutMode]()
        for port_mode in (PortMode.INPUT, PortMode.OUTPUT, PortMode.BOTH):
            layout_modes_[port_mode] = gpos.boxes[port_mode].layout_mode
        
        self.cnv_name = display_name
        self.cnv_box_type = box_type
        self.cnv_icon_name = icon_name
        
        patchcanvas.add_group(
            self.group_id, display_name, do_split,
            box_type, icon_name, layout_modes=layout_modes_,
            null_xy=gpos.boxes[PortMode.BOTH].pos,
            in_xy=gpos.boxes[PortMode.INPUT].pos,
            out_xy=gpos.boxes[PortMode.OUTPUT].pos)

        self.in_canvas = True

        if do_split:
            for port_mode in PortMode.INPUT, PortMode.OUTPUT:
                patchcanvas.wrap_group_box(
                    self.group_id, port_mode,
                    gpos.boxes[port_mode].is_wrapped(),
                    animate=False)
        else:
            patchcanvas.wrap_group_box(
                self.group_id, PortMode.BOTH,
                gpos.boxes[PortMode.BOTH].is_wrapped(),
                animate=False)
            
        if self.has_gui:
            patchcanvas.set_optional_gui_state(self.group_id, self.gui_visible)

    def remove_from_canvas(self):
        if not self.in_canvas:
            return

        patchcanvas.remove_group(self.group_id)
        self.in_canvas = False

    def redraw_in_canvas(self):
        if not self.in_canvas:
            return
        
        patchcanvas.redraw_group(self.group_id)

    def update_name_in_canvas(self):
        if not self.in_canvas:
            return
        
        display_name = self.name
        if self.manager.use_graceful_names:
            display_name = self.display_name
        self.cnv_name = display_name
        
        patchcanvas.rename_group(self.group_id, display_name)

    def split_in_canvas(self):
        box_rect = patchcanvas.get_box_rect(self.group_id, PortMode.BOTH)

        self.manager.optimize_operation(True)
        for conn in self.manager.connections:
            if conn.port_out.group is self or conn.port_in.group is self:
                conn.remove_from_canvas()

        self.remove_all_ports_from_canvas()
        gpos = self.current_position

        self.remove_from_canvas()
        
        self.current_position.set_splitted(True)
        wrapped = gpos.boxes[PortMode.BOTH].is_wrapped()
        for port_mode in PortMode.INPUT, PortMode.OUTPUT:
            gpos.boxes[port_mode].pos = gpos.boxes[PortMode.BOTH].pos
            gpos.boxes[port_mode].set_wrapped(
                gpos.boxes[PortMode.BOTH].is_wrapped())
        
        self.add_to_canvas()
        self.add_all_ports_to_canvas()

        for conn in self.manager.connections:
            if conn.port_out.group is self or conn.port_in.group is self:
                conn.add_to_canvas()

        self.manager.optimize_operation(False)
        patchcanvas.redraw_group(self.group_id)
        patchcanvas.move_splitted_boxes_on_place(
            self.group_id, box_rect.width())

    def join_in_canvas(self):
        self.manager.optimize_operation(True)
        for conn in self.manager.connections:
            if conn.port_out.group is self or conn.port_in.group is self:
                conn.remove_from_canvas()

        self.remove_all_ports_from_canvas()
        gpos = self.current_position

    def _get_box_type_and_icon(self) -> tuple[BoxType, str]:
        box_type = BoxType.APPLICATION
        icon_name = self.name.partition('.')[0].lower()

        if self._is_hardware:
            box_type = BoxType.HARDWARE
            icon_name = ''
            if self.a2j_group or self.display_name in ("Midi-Bridge", "a2j"):
                icon_name = "a2j"

        if self.client_icon:
            box_type = BoxType.CLIENT
            icon_name = self.client_icon

        if (self.name.startswith("PulseAudio ")
                and not self.client_icon):
            if "sink" in self.name.lower():
                box_type = BoxType.MONITOR
                icon_name = 'monitor_playback'
            elif "source" in self.name.lower():
                box_type = BoxType.MONITOR
                icon_name = 'monitor_capture'

        elif (self.name.endswith(" Monitor")
                and not self.client_icon):
            # this group is (probably) a pipewire Monitor group
            box_type = BoxType.MONITOR
            icon_name = 'monitor_playback'
        
        if self.mdata_icon:
            icon_name = self.mdata_icon

        return (box_type, icon_name)

    def semi_hide(self, yesno: bool):
        if not self.in_canvas:
            return 
        
        patchcanvas.semi_hide_group(self.group_id, yesno)

    def set_in_front(self):
        if not self.in_canvas:
            return
        
        patchcanvas.set_group_in_front(self.group_id)

    def get_number_of_boxes(self) -> int:
        if not self.in_canvas:
            return 0

        return patchcanvas.get_number_of_boxes(self.group_id)

    def select_filtered_box(self, n_select=0):
        if not self.in_canvas:
            return
        
        patchcanvas.select_filtered_group_box(self.group_id, n_select)

    def set_optional_gui_state(self, visible: bool):
        self.has_gui = True
        self.gui_visible = visible
        
        if not self.in_canvas:
            return
        
        patchcanvas.set_optional_gui_state(self.group_id, visible)

    def remove_all_ports(self):
        if self.in_canvas:
            for portgroup in self.portgroups:
                portgroup.remove_from_canvas()

            for port in self.ports:
                port.remove_from_canvas()

        self.portgroups.clear()
        self.ports.clear()

    def add_port(self, port: Port):
        port.group_id = self.group_id
        port.group = self
        port_full_name = port.full_name

        if (port_full_name.startswith('a2j:')
                and not port.flags & JackPortFlag.IS_PHYSICAL):
            port_full_name = port_full_name.partition(':')[2]
            
        elif port.type is PortType.MIDI_ALSA:
            port_full_name = ':'.join(port_full_name.split(':')[4:])

        port.display_name = port_full_name.partition(':')[2]

        if not self.ports:
            # we are adding the first port of the group
            if port.flags & JackPortFlag.IS_PHYSICAL:
                self._is_hardware = True

            if not self.current_position.fully_set:
                if self._is_hardware:
                    self.current_position.set_splitted(True)
                self.current_position.fully_set = True
                self.save_current_position()

        self.ports.append(port)
        self.manager._ports_by_name[port.full_name] = port

    def remove_port(self, port: Port):
        if port in self.ports:
            port.remove_from_canvas()
            self.ports.remove(port)
        
        if self.manager._ports_by_name.get(port.full_name):
            self.manager._ports_by_name.pop(port.full_name)

    def remove_portgroup(self, portgroup: Portgroup):
        if portgroup in self.portgroups:
            portgroup.remove_from_canvas()
            for port in portgroup.ports:
                port.portgroup_id = 0
            self.portgroups.remove(portgroup)

    def portgroup_memory_added(self, portgroup_mem: PortgroupMem):
        if portgroup_mem.group_name != self.name:
            return

        remove_set = set[Portgroup]()

        # first remove any existing portgroup with one of the porgroup_mem ports
        for portgroup in self.portgroups:
            if (portgroup.port_mode is not portgroup_mem.port_mode
                    or portgroup.port_type() is not portgroup_mem.port_type):
                continue

            for port in portgroup.ports:
                if port.short_name() in portgroup_mem.port_names:
                    remove_set.add(portgroup)

        for portgroup in remove_set:
            self.remove_portgroup(portgroup)

        # add a portgroup if all needed ports are present and consecutive
        port_list = list[Port]()

        for port in self.ports:
            if (port.mode() is not portgroup_mem.port_mode
                    or port.type is not portgroup_mem.port_type):
                continue

            if port.short_name() == portgroup_mem.port_names[len(port_list)]:
                port_list.append(port)

                if len(port_list) == len(portgroup_mem.port_names):
                    # all ports are presents, create the portgroup
                    portgroup = self.manager.new_portgroup(
                        self.group_id, port.mode(), port_list)
                    self.portgroups.append(portgroup)
                    portgroup.add_to_canvas()
                    break

            elif port_list:
                # here it is a port breaking the consecutivity of the portgroup
                break

    def save_current_position(self):
        self.manager.save_group_position(self.current_position)

    def set_group_position(self, group_position: GroupPos, view_change=False):
        if not self.in_canvas:
            return

        ex_gpos_splitted = self.current_position.is_splitted()
        self.current_position = group_position
        gpos = self.current_position

        for port_mode, box_pos in group_position.boxes.items():
            patchcanvas.set_group_layout_mode(
                self.group_id, port_mode, box_pos.layout_mode,
                prevent_overlap=False)

        for port_mode, box_pos in group_position.boxes.items():
            patchcanvas.set_group_layout_mode(
                self.group_id, port_mode, box_pos.layout_mode,
                prevent_overlap=False)

        patchcanvas.move_group_boxes(
            self.group_id,
            gpos.boxes,
            force=view_change)

        prevent_overlap = not view_change

        # restore split and wrapped modes
        if gpos.is_splitted():
            if not ex_gpos_splitted:
                # patchcanvas.split_group(self.group_id)
                self.split_in_canvas()

            for port_mode in PortMode.INPUT, PortMode.OUTPUT: 
                patchcanvas.wrap_group_box(
                    self.group_id, port_mode,
                    gpos.boxes[port_mode].is_wrapped(),
                    prevent_overlap=prevent_overlap)

        else:
            patchcanvas.wrap_group_box(
                self.group_id, PortMode.NULL,
                gpos.boxes[PortMode.BOTH].is_wrapped(),
                prevent_overlap=prevent_overlap)

            if ex_gpos_splitted:
                patchcanvas.animate_before_join(self.group_id)

    def set_layout_mode(self, port_mode: PortMode, layout_mode: BoxLayoutMode):
        self.current_position.boxes[port_mode].layout_mode = layout_mode
        self.save_current_position()

        if not self.in_canvas:
            return
        
        patchcanvas.set_group_layout_mode(self.group_id, port_mode, layout_mode)

    def wrap_box(self, port_mode: PortMode, yesno: bool):
        true_port_mode = port_mode
        if port_mode is PortMode.NULL:
            true_port_mode = PortMode.BOTH
        
        box_pos = self.current_position.boxes[true_port_mode]
        box_pos.set_wrapped(yesno)
        self.save_current_position()

        if not self.in_canvas:
            return

        patchcanvas.wrap_group_box(self.group_id, port_mode, yesno)

    def set_client_icon(self, icon_name: str, from_metadata=False):
        if from_metadata:
            self.mdata_icon = icon_name
        else:
            self.client_icon = icon_name
        
        box_type, ex_icon_name = self._get_box_type_and_icon()
        
        if self.in_canvas:
            patchcanvas.set_group_icon(
                self.group_id, box_type, icon_name)

    def get_pretty_client(self) -> str:
        for client_name in ('firewire_pcm', 'a2j',
                            'Hydrogen', 'ardour', 'Ardour', 'Mixbus', 'mixbus',
                            'Qtractor', 'SooperLooper', 'sooperlooper', 'Luppp',
                            'seq64', 'calfjackhost', 'rakarrack-plus',
                            'seq192', 'Non-Mixer', 'jack_mixer'):
            if self.name == client_name:
                return client_name

            if self.name.startswith(client_name + '.'):
                return client_name
            
            name = self.name.partition('/')[0]
            if name == client_name:
                return client_name
            
            if name.startswith(client_name + '_'):
                if name.replace(client_name + '_', '', 1).isdigit():
                    return client_name
            
            if ' (' in name and name.endswith(')'):
                name = name.partition(' (')[0]
                if name == client_name:
                    return client_name
                
                if name.startswith(client_name + '_'):
                    if name.replace(client_name + '_', '', 1).isdigit():
                        return client_name

        return ''

    def graceful_port(self, port: Port):
        def split_end_digits(name: str) -> tuple[str, str]:
            num = ''
            while name and name[-1].isdigit():
                num = name[-1] + num
                name = name[:-1]

            if num.startswith('0') and num not in ('0', '09'):
                num = num[1:]

            return (name, num)

        def cut_end(name: str, *ends: str) -> str:
            for end in ends:
                if name.endswith(end):
                    return name.rsplit(end)[0]
            return name

        client_name = self.get_pretty_client()

        if (not client_name
                and ((port.type is PortType.MIDI_JACK
                        and port.full_name.startswith(
                            ('a2j:', 'Midi-Bridge:')))
                     or port.type is PortType.MIDI_ALSA)
                and port.flags & JackPortFlag.IS_PHYSICAL):
            client_name = 'a2j'

        display_name = port.short_name()
        s_display_name = display_name

        if client_name == 'firewire_pcm':
            if '(' in display_name and ')' in display_name:
                after_para = display_name.partition('(')[2]
                display_name = after_para.rpartition(')')[0]
                display_name, num = split_end_digits(display_name)

                if num:
                    if display_name.endswith(':'):
                        display_name = display_name[:-1]
                    display_name += ' ' + num
            else:
                display_name = display_name.partition('_')[2]
                display_name = cut_end(display_name, '_in', '_out')
                display_name = display_name.replace(':', ' ')
                display_name, num = split_end_digits(display_name)
                display_name = display_name + num

        elif client_name == 'Hydrogen':
            if display_name.startswith('Track_'):
                display_name = display_name.replace('Track_', '', 1)

                num, udsc, name = display_name.partition('_')
                if num.isdigit():
                    display_name = num + ' ' + name

            if display_name.endswith('_Main_L'):
                display_name = display_name.replace('_Main_L', ' L', 1)
            elif display_name.endswith('_Main_R'):
                display_name = display_name.replace('_Main_R', ' R', 1)

        elif client_name == 'a2j':
            display_name, num = split_end_digits(display_name)
            if num:
                if display_name.endswith(' MIDI '):
                    display_name = cut_end(display_name, ' MIDI ')

                    if num == '1':
                        port.last_digit_to_add = '1'
                    else:
                        display_name += ' ' + num

                elif display_name.endswith(' Port-'):
                    display_name = cut_end(display_name, ' Port-')

                    if num == '0':
                        port.last_digit_to_add = '0'
                    else:
                        display_name += ' ' + num

        elif client_name in ('ardour', 'Ardour', 'Mixbus', 'mixbus'):
            if '/TriggerBox/' in display_name:
                display_name = '▸ ' + display_name.replace('/TriggerBox/', '/', 1)
            
            for pt in ('audio', 'midi'):
                if display_name == f"physical_{pt}_input_monitor_enable":
                    display_name = "physical monitor"
                    break
            else:
                display_name, num = split_end_digits(display_name)
                if num:
                    display_name = cut_end(display_name,
                                        '/audio_out ', '/audio_in ',
                                        '/midi_out ', '/midi_in ')
                    if num == '1':
                        port.last_digit_to_add = '1'
                    else:
                        display_name += ' ' + num

        elif client_name == 'Qtractor':
            display_name, num = split_end_digits(display_name)
            if num:
                display_name = cut_end(display_name,
                                       '/in_', '/out_')
                if num == '1':
                    port.last_digit_to_add = '1'
                else:
                    display_name += ' ' + num
        
        elif client_name == 'Non-Mixer':
            display_name, num = split_end_digits(display_name)
            if num:
                display_name = cut_end(display_name, '/in-', '/out-')
                
                if num == '1':
                    port.last_digit_to_add = '1'
                else:
                    display_name += ' ' + num
        
        elif client_name == 'jack_mixer':
            prefix, out, side = display_name.rpartition(' Out')
            if out and side in (' L', ' R', ''):
                display_name = prefix + side
                        
        elif client_name in ('SooperLooper', 'sooperlooper'):
            display_name, num = split_end_digits(display_name)
            if num:
                display_name = cut_end(display_name,
                                       '_in_', '_out_')
                if num == '1':
                    port.last_digit_to_add = '1'
                else:
                    display_name += ' ' + num

        elif client_name == 'Luppp':
            if display_name.endswith('\n'):
                display_name = display_name[:-1]

            display_name = display_name.replace('_', ' ')

        elif client_name == 'seq64':
            display_name = display_name.replace('seq64 midi ', '', 1)

        elif client_name == 'seq192':
            display_name = display_name.replace('seq192 ', '', 1)

        elif client_name == 'calfjackhost':
            display_name, num = split_end_digits(display_name)
            if num:
                display_name = cut_end(display_name,
                                       ' Out #', ' In #')

                display_name += " " + num

        elif client_name == 'rakarrack-plus':
            if display_name.startswith(('rakarrack-plus ', 'rakarrack-plus.')):
                display_name = display_name[15:]
            display_name = display_name.replace('_', ' ')

        elif not client_name:
            display_name = display_name.replace('_', ' ')
            if display_name.lower().endswith(('-left', ' left')):
                display_name = display_name[:-5] + ' L'
            elif display_name.lower().endswith(('-right', ' right')):
                display_name = display_name[:-6] + ' R'
            elif display_name.lower() == 'left in':
                display_name = 'In L'
            elif display_name.lower() == 'right in':
                display_name = 'In R'
            elif display_name.lower() == 'left out':
                display_name = 'Out L'
            elif display_name.lower() == 'right out':
                display_name = 'Out R'

            if display_name.startswith('Audio'):
                display_name = display_name.replace('Audio ', '')

        # reduce graceful name for pipewire Midi-Bridge with
        # option jack.filter_name = true
        if (port.full_name.startswith('Midi-Bridge')
                and display_name.startswith(('capture_', 'playback_'))):
            display_name = display_name.partition('_')[2]

        port.display_name = display_name if display_name else s_display_name

    def add_portgroup(self, portgroup: Portgroup):
        self.portgroups.append(portgroup)

    def change_port_types_view(self):
        # first add group to canvas if not already
        self.add_to_canvas()

        for portgroup in self.portgroups:
            if not self.manager.port_type_shown(portgroup.full_type()):
                portgroup.remove_from_canvas()

        for port in self.ports:
            if not self.manager.port_type_shown(port.full_type()):
                port.remove_from_canvas()

        for port in self.ports:
            port.add_to_canvas()

        for portgroup in self.portgroups:
            portgroup.add_to_canvas()

        # remove group from canvas if no visible ports
        for port in self.ports:
            if port.in_canvas:
                break
        else:
            self.remove_from_canvas()

    def stereo_detection(self, port: Port) -> Union[Port, None]:
        if port.type != PortType.AUDIO_JACK or port.subtype != PortSubType.REGULAR:
            return

        # find the last port with same type and mode in the group
        for other_port in reversed(self.ports):
            if other_port == port:
                continue

            if (other_port.type == port.type
                    and other_port.subtype == port.subtype
                    and other_port.mode() == port.mode()
                    and not other_port.portgroup_id
                    and not other_port.prevent_stereo):
                for portgroup_mem in self.manager.portgroups_memory:
                    if (portgroup_mem.group_name == self.name
                        and portgroup_mem.port_mode == other_port.mode()
                        and portgroup_mem.port_type == other_port.type
                        and other_port.short_name() in portgroup_mem.port_names):
                        # other_port (left) is in a remembered portgroup
                        # prevent stereo detection
                        return
                break
        else:
            return

        may_match_set = set[str]()

        port_name = port.full_name.replace(self.name + ':', '', 1)
        other_port_name = other_port.full_name.replace(self.name + ':', '', 1)

        if port.flags & JackPortFlag.IS_PHYSICAL:
            # force stereo detection for system ports
            # it forces it for firewire long and strange names
            may_match_set.add(other_port_name)

        elif port_name[-1].isdigit():
            # Port ends with digit
            base_port = port_name[:-1]
            in_num = port_name[-1]

            while base_port[-1].isdigit():
                in_num = base_port[-1] + in_num
                base_port = base_port[:-1]

            # if Port ends with Ldigits or Rdigits
            if base_port.endswith('R'):
                may_match_set.add(base_port[:-1] + 'L' + in_num)
            else:
                may_match_set.add(base_port + str(int(in_num) -1))

                if int(in_num) in (1, 2):
                    if base_port.endswith((' ', ('_'))):
                        may_match_set.add(base_port[:-1])
                    else:
                        may_match_set.add(base_port)
        else:
            # Port ends with non digit
            if port_name.endswith('R'):
                may_match_set.add(port_name[:-1] + 'L')
                if len(port_name) >= 2:
                    if port_name[-2] == ' ':
                        may_match_set.add(port_name[:-2])
                    else:
                        may_match_set.add(port_name[:-1])

            elif port_name.endswith('right'):
                may_match_set.add(port_name[:-5] + 'left')

            elif port_name.endswith('Right'):
                may_match_set.add(port_name[:-5] + 'Left')

            elif port_name.endswith('(Right)'):
                may_match_set.add(port_name[:-7] + '(Left)')

            elif port_name.endswith('.r'):
                may_match_set.add(port_name[:-2] + '.l')

            elif port_name.endswith('_r'):
                may_match_set.add(port_name[:-2] + '_l')

            elif port_name.endswith('_r\n'):
                may_match_set.add(port_name[:-3] + '_l\n')

            for x in ('out', 'Out', 'output', 'Output', 'in', 'In',
                      'input', 'Input', 'audio input', 'audio output'):
                if port_name.endswith('R ' + x):
                    may_match_set.add('L ' + x)

                elif port_name.endswith('right ' + x):
                    may_match_set.add('left ' + x)

                elif port_name.endswith('Right ' + x):
                    may_match_set.add('Left ' + x)

        if other_port_name in may_match_set:
            return other_port

    def check_for_portgroup_on_last_port(self):
        if not self.ports:
            return

        last_port = self.ports[-1]
        last_port_name = last_port.short_name()

        # check in the saved portgroups if we need to make a portgroup
        # or prevent stereo detection
        for portgroup_mem in self.manager.portgroups_memory:
            if (portgroup_mem.group_name == self.name
                    and portgroup_mem.port_type == last_port.type
                    and portgroup_mem.port_mode == last_port.mode()
                    and last_port_name == portgroup_mem.port_names[-1]):
                if (len(portgroup_mem.port_names) == 1
                    or portgroup_mem.port_names.index(last_port_name) + 1
                        != len(portgroup_mem.port_names)):
                    return

                port_list = list[Port]()

                for port in self.ports:
                    if (port.type == last_port.type
                            and port.mode() == last_port.mode()):
                        if (len(portgroup_mem.port_names) > len(port_list)
                                and port.short_name()
                                == portgroup_mem.port_names[len(port_list)]):
                            port_list.append(port)

                            if len(port_list) == len(portgroup_mem.port_names):
                                portgroup = self.manager.new_portgroup(
                                    self.group_id, port.mode(), port_list)
                                self.portgroups.append(portgroup)
                                for port in port_list:
                                    if not port.in_canvas:
                                        break
                                else:
                                    portgroup.add_to_canvas()

                        elif port_list:
                            return

        # detect left audio port if it is a right one
        other_port = self.stereo_detection(last_port)
        if other_port is not None:
            portgroup = self.manager.new_portgroup(
                self.group_id, last_port.mode(), (other_port, last_port))
            self.add_portgroup(portgroup)

            if self.in_canvas:
                portgroup.add_to_canvas()

    def check_for_display_name_on_last_port(self):
        if not self.ports:
            return

        last_port = self.ports[-1]
        last_digit = last_port.full_name[-1]

        if last_digit not in ('1', '2'):
            return

        for port in reversed(self.ports[:-1]):
            if (port.type == last_port.type
                    and port.mode() == last_port.mode()
                    and port is not last_port):
                if (port.full_name[:-1] == last_port.full_name[:-1]
                        and ((port.last_digit_to_add == '0'
                              and last_digit == '1'))
                             or (port.last_digit_to_add == '1'
                                 and last_digit == '2')):
                        port.add_the_last_digit()
                break

    def sort_ports_in_canvas(self):
        already_optimized = self.manager.optimized_operation
        self.manager.optimize_operation(True)

        conn_list = list[Connection]()

        if not self.manager.very_fast_operation:
            for conn in self.manager.connections:
                for port in self.ports:
                    if (port in (conn.port_out, conn.port_in)
                            and conn not in conn_list):
                        conn_list.append(conn)
            
            for connection in conn_list:
                connection.remove_from_canvas()
            
            for portgroup in self.portgroups:
                portgroup.remove_from_canvas()

            for port in self.ports:
                port.remove_from_canvas()
        
        self.ports.sort()

        # search and remove existing portgroups with non consecutive ports
        portgroups_to_remove = list[Portgroup]()

        for portgroup in self.portgroups:
            search_index = 0
            previous_port = None
            seems_ok = False

            for port in self.ports:
                if not seems_ok and port is portgroup.ports[search_index]:
                    if (port.mdata_portgroup != portgroup.mdata_portgroup
                            and not portgroup.above_metadatas):
                        portgroups_to_remove.append(portgroup)
                        break

                    if (not portgroup.above_metadatas and not search_index
                            and previous_port is not None
                            and previous_port.mdata_portgroup
                            and previous_port.mdata_portgroup == port.mdata_portgroup):
                        # previous port had the same portgroup metadata
                        # that this port. we need to remove this portgroup.
                        portgroups_to_remove.append(portgroup)
                        break

                    search_index += 1
                    if search_index == len(portgroup.ports):
                        # all ports of portgroup are consecutive
                        # but still exists the risk that metadatas says
                        # that the portgroup has now more ports
                        seems_ok = True
                        if (portgroup.above_metadatas
                                or not portgroup.mdata_portgroup):
                            break

                elif search_index:
                    if (seems_ok
                            and (port.mdata_portgroup != previous_port.mdata_portgroup
                                 or port.type != portgroup.port_type()
                                 or port.mode() != portgroup.port_mode)):
                        # port after the portgroup has not to make
                        # the portgroup higher. We keep this portgroup
                        break

                    # this port breaks portgroup ports consecutivity.
                    # note that ports have been just sorted by type and mode
                    # so no risk that this port is falsely breaking portgroup
                    portgroups_to_remove.append(portgroup)
                    break

                previous_port = port
            else:
                if not seems_ok:
                    portgroups_to_remove.append(portgroup)

        for portgroup in portgroups_to_remove:
            self.remove_portgroup(portgroup)

        # add missing portgroups aboving metadatas from portgroup memory
        for portgroup_mem in self.manager.portgroups_memory:
            if not portgroup_mem.above_metadatas:
                continue

            if portgroup_mem.group_name != self.name:
                continue

            founded_ports = list[Port]()

            for port in self.ports:
                if (not port.portgroup_id
                        and port.type == portgroup_mem.port_type
                        and port.mode() == portgroup_mem.port_mode
                        and port.short_name()
                            == portgroup_mem.port_names[len(founded_ports)]):
                    founded_ports.append(port)
                    if len(founded_ports) == len(portgroup_mem.port_names):
                        new_portgroup = self.manager.new_portgroup(
                            self.group_id, port.mode(), founded_ports)
                        self.portgroups.append(new_portgroup)
                        break

                elif founded_ports:
                    break

        # detect and add portgroups given from metadatas
        portgroups_mdata = list[dict]() # list of dicts

        for port in self.ports:
            if port.mdata_portgroup:
                pg_mdata = None
                if portgroups_mdata:
                    pg_mdata = portgroups_mdata[-1]

                if not port.portgroup_id:
                    if (pg_mdata is not None
                            and pg_mdata['pg_name'] == port.mdata_portgroup
                            and pg_mdata['port_type'] == port.type
                            and pg_mdata['port_mode'] == port.mode()):
                        pg_mdata['ports'].append(port)
                    else:
                        portgroups_mdata.append(
                            {'pg_name': port.mdata_portgroup,
                             'port_type': port.type,
                             'port_mode': port.mode(),
                             'ports':[port]})
        
        for pg_mdata in portgroups_mdata:
            if len(pg_mdata['ports']) < 2:
                continue

            new_portgroup = self.manager.new_portgroup(
                self.group_id, pg_mdata['port_mode'], pg_mdata['ports'])
            new_portgroup.mdata_portgroup = pg_mdata['pg_name']
            self.portgroups.append(new_portgroup)
        
        # add missing portgroups from portgroup memory
        for portgroup_mem in self.manager.portgroups_memory:
            if portgroup_mem.above_metadatas:
                continue

            if portgroup_mem.group_name != self.name:
                continue

            founded_ports = list[Port]()

            for port in self.ports:
                if (not port.portgroup_id
                        and port.type == portgroup_mem.port_type
                        and port.mode() == portgroup_mem.port_mode
                        and port.short_name()
                            == portgroup_mem.port_names[len(founded_ports)]):
                    founded_ports.append(port)
                    if len(founded_ports) == len(portgroup_mem.port_names):
                        new_portgroup = self.manager.new_portgroup(
                            self.group_id, port.mode(), founded_ports)
                        self.portgroups.append(new_portgroup)
                        break

                elif founded_ports:
                    break
        
        if not self.manager.very_fast_operation:
            # ok for re-adding all items to canvas
            for port in self.ports:
                port.add_to_canvas()

            for portgroup in self.portgroups:
                portgroup.add_to_canvas()
        
            for connection in conn_list:
                connection.add_to_canvas()
        
        if not already_optimized:
            self.manager.optimize_operation(False)
            self.redraw_in_canvas()

    def add_all_ports_to_canvas(self):
        for port in self.ports:
            port.add_to_canvas()

        for portgroup in self.portgroups:
            portgroup.add_to_canvas()
            
    def remove_all_ports_from_canvas(self):
        for portgroup in self.portgroups:
            portgroup.remove_from_canvas()
        
        for port in self.ports:
            port.remove_from_canvas()