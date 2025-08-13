import logging
import operator
from pathlib import Path

from typing import TYPE_CHECKING, Any
from .bases.port import Port
from .bases.elements import JackPortFlag
from patshared import PortType, PortMode, from_json_to_str

if TYPE_CHECKING:
    from .patchbay_manager import PatchbayManager

_logger = logging.getLogger(__name__)


def _export_port_list_to_patchichi(mng: 'PatchbayManager') -> str:
    def slcol(input_str: str) -> str:
        return input_str.replace(':', '\\:')
    
    contents = ''

    gps_and_ports = list[tuple[str, list[Port]]]()
    for group in mng.groups:
        for port in group.ports:
            if port.type is PortType.MIDI_ALSA:
                group_name = port.full_name.split(':')[4]
            else:
                group_name = port.full_name.partition(':')[0]

            for gp_name, gp_port_list in gps_and_ports:
                if gp_name == group_name:
                    gp_port_list.append(port)
                    break
            else:
                gps_and_ports.append((group_name, [port]))

    for group_name, port_list in gps_and_ports:
        port_list.sort(key=operator.attrgetter('port_id'))
            
    for group_name, port_list in gps_and_ports:
        gp_written = False              
        last_type_and_mode = (PortType.NULL, PortMode.NULL)
        physical = False
        terminal = False
        monitor = False
        pg_name = ''
        signal_type = ''

        for port in port_list:
            if not gp_written:
                contents += f'\n::{group_name}\n'
                gp_written = True

                group = mng.get_group_from_name(group_name)
                if group is not None:
                    group_attrs = list[str]()
                    if group.client_icon:
                        group_attrs.append(
                            f'CLIENT_ICON={slcol(group.client_icon)}')
                        
                    if group.mdata_icon:
                        group_attrs.append(
                            f'ICON_NAME={slcol(group.mdata_icon)}')

                    if group.has_gui:
                        if group.gui_visible:
                            group_attrs.append('GUI_VISIBLE')
                        else:
                            group_attrs.append('GUI_HIDDEN')
                    if group_attrs:
                        contents += ':'
                        contents += '\n:'.join(group_attrs)
                        contents += '\n'

            if port.flags & JackPortFlag.IS_PHYSICAL:
                if not physical:
                    contents += ':PHYSICAL\n'
                    physical = True
            elif physical:
                contents += ':~PHYSICAL\n'
                physical = False

            if last_type_and_mode != (port.type, port.mode):
                if port.type is PortType.AUDIO_JACK:
                    if port.flags & JackPortFlag.IS_CONTROL_VOLTAGE:
                        contents += ':CV'
                    else:
                        contents += ':AUDIO'
                elif port.type is PortType.MIDI_JACK:
                    contents += ':MIDI'
                elif port.type is PortType.MIDI_ALSA:
                    contents += ':ALSA'

                contents += f':{port.mode.name}\n'
                last_type_and_mode = (port.type, port.mode)
            
            if port.mdata_signal_type != signal_type:
                if port.mdata_signal_type:
                    contents += \
                        f':SIGNAL_TYPE={slcol(port.mdata_signal_type)}\n'
                else:
                    contents += ':~SIGNAL_TYPE\n'
            
            if port.mdata_portgroup != pg_name:
                if port.mdata_portgroup:
                    contents += \
                        f':PORTGROUP={slcol(port.mdata_portgroup)}\n'
                else:
                    contents += ':~PORTGROUP\n'
                pg_name = port.mdata_portgroup

            if port.type is PortType.MIDI_ALSA:
                port_short_name = ':'.join(port.full_name.split(':')[5:])
            else:
                port_short_name = port.full_name.partition(':')[2]

            contents += f'{port_short_name}\n'
            
            if port.mdata_pretty_name or port.order:
                port_attrs = list[str]()
                if port.mdata_pretty_name:
                    port_attrs.append(f'PRETTY_NAME={slcol(port.mdata_pretty_name)}')
                if port.order:
                    port_attrs.append(f'ORDER={port.order}')
                contents += ':'
                contents += '\n:'.join(port_attrs)
                contents += '\n'

    return contents

def export_to_patchichi_json(
        mng: 'PatchbayManager', path: Path, editor_text='') -> bool:
    if not editor_text:
        editor_text = _export_port_list_to_patchichi(mng)

    file_dict = dict[str, Any]()
    file_dict['VERSION'] = (0, 3)       
    file_dict['editor_text'] = editor_text
    file_dict['connections'] = [
        (c.port_out.full_name, c.port_in.full_name)
        for c in mng.connections]

    file_dict['views'] = mng.views.to_json_list()

    # save specific portgroups json dict
    # because we save only portgroups with present ports
    portgroups_dict = dict[str, dict[str, dict[str, dict]]]()

    for port_type, ptype_dict in mng.portgroups_memory.items():
        if port_type.name is None:
            continue

        portgroups_dict[port_type.name] = js_ptype_dict = {}
        for gp_name, group_dict in ptype_dict.items():
            js_ptype_dict[gp_name] = {}
            group = mng.get_group_from_name(gp_name)
            if group is None:
                continue

            for port_mode, pmode_list in group_dict.items():
                pg_list = js_ptype_dict[gp_name][port_mode.name] = []
                for pg_mem in pmode_list:
                    one_port_found = False

                    for port_str in pg_mem.port_names:
                        for port in group.ports:
                            if (port.type is port_type
                                    and port.mode is port_mode
                                    and port.short_name == port_str):
                                pg_list.append(pg_mem.as_new_dict())
                                one_port_found = True
                                break
                        
                        if one_port_found:
                            break

    file_dict['portgroups'] = portgroups_dict

    try:
        with open(path, 'w') as f:
            f.write(from_json_to_str(file_dict))
        return True
    except Exception as e:
        _logger.error(f'Failed to save patchichi file: {str(e)}')
        return False