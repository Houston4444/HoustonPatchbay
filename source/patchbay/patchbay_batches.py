from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Callable

from qtpy.QtCore import QThread
from qtpy.QtGui import QGuiApplication

from patshared import PortType, PortSubType, JackMetadata

from .bases.connection import Connection
from .bases.elements import JackPortFlag
from .bases.group import Group
from .bases.port import Port

if TYPE_CHECKING:
    from .patchbay_manager import PatchbayManager


_logger = logging.getLogger(__name__)


@dataclass
class DelayedOrder:
    func: Callable
    args: tuple
    kwargs: dict
    draw_group: bool
    sort_group: bool
    clear_conns: bool
    metadata_change: bool


def later_by_batch(draw_group=False, sort_group=False,
                   clear_conns=False, metadata_change=False):
    '''This decorator indicates that the decorated method will be executed
    later by batch in the main thread when `_delayed_orders_timer` will
    call it.'''

    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            mng: PatchbayManager = args[0]
            if mng.very_fast_operation:
                return func(*args, **kwargs)

            mng.delayed_orders.put(
                DelayedOrder(func, args, kwargs,
                             draw_group or sort_group,
                             sort_group,
                             clear_conns,
                             metadata_change))

            if QThread.currentThread() is QGuiApplication.instance().thread():
                mng._delayed_orders_timer.start()
            else:
                mng.sg.out_thread_order.emit()
            return
        return wrapper
    return decorator

# @later_by_batch()
def set_group_uuid_from_name(
        mng: 'PatchbayManager', client_name: str, uuid: int):
    mng.client_uuids[client_name] = uuid

    group = mng.get_group_from_name(client_name)
    if group is not None:
        group.uuid = uuid

# @later_by_batch(draw_group=True)
def add_port(mng: 'PatchbayManager', name: str, port_type: PortType,
                flags: int, uuid: int) -> int:
    '''adds port and returns the group_id'''
    exst_port = mng.get_port_from_name(name)
    if exst_port is not None:
        _logger.warning(
            f'add port "{name}", '
            f'it already exists, remove it first !')

        if name in mng._ports_by_name:
            mng._ports_by_name.pop(name)
        if uuid in mng._ports_by_uuid:
            mng._ports_by_uuid.pop(uuid)

        if exst_port.type.is_jack and exst_port.uuid:
            mng.jack_metadatas.remove_uuid(exst_port.uuid)

        group = mng.get_group_from_id(exst_port.group_id)
        if group is not None:
            # remove portgroup first if port is in a portgroup
            if exst_port.portgroup_id:
                for portgroup in group.portgroups:
                    if portgroup.portgroup_id == exst_port.portgroup_id:
                        group.portgroups.remove(portgroup)
                        portgroup.remove_from_canvas()
                        break

            exst_port.remove_from_canvas()
            group.remove_port(exst_port)

    port = Port(mng, mng._next_port_id, name, port_type, flags, uuid)
    mng._next_port_id += 1

    full_port_name = name
    group_name, colon, port_name = full_port_name.partition(':')

    is_a2j_group = False
    group_is_new = False

    if (port_type is PortType.MIDI_ALSA
            and full_port_name.startswith((':ALSA_OUT:', ':ALSA_IN:'))):
        _, _alsa_key, alsa_gp_id, alsa_p_id, group_name, *rest = \
            full_port_name.split(':')
        port_name = ':'.join(rest)

        if port.flags & JackPortFlag.IS_PHYSICAL:
            is_a2j_group = True

    elif (full_port_name.startswith(('a2j:', 'Midi-Bridge:'))
            and (not mng.group_a2j_hw
                    or not port.flags & JackPortFlag.IS_PHYSICAL)):
        group_name, colon, port_name = port_name.partition(':')
        if full_port_name.startswith('a2j:'):
            if ' [' in group_name:
                group_name = group_name.rpartition(' [')[0]
            else:
                if ' (capture)' in group_name:
                    group_name = group_name.partition(' (capture)')[0]
                else:
                    group_name = group_name.partition(' (playback)')[0]

            # fix a2j wrongly substitute '.' with space
            group_name = mng.get_corrected_a2j_group_name(group_name)

        if port.flags & JackPortFlag.IS_PHYSICAL:
            is_a2j_group = True

    group = mng.get_group_from_name(group_name)
    if group is None:
        # port is in an non existing group, create the group
        gpos = mng.get_group_position(group_name)
        group = Group(mng, mng._next_group_id, group_name, gpos)

        group.a2j_group = is_a2j_group
        mng.set_group_as_nsm_client(group)

        mng._next_group_id += 1
        mng._add_group(group)

        group_is_new = True

    group.add_port(port)
    group.graceful_port(port)

    group.add_to_canvas()
    port.add_to_canvas()
    group.check_for_portgroup_on_last_port()
    group.check_for_display_name_on_last_port()

    if group_is_new:
        mng.sg.group_added.emit(group.group_id)

    return group.group_id

# @later_by_batch(draw_group=True, clear_conns=True)
def remove_port(mng: 'PatchbayManager', name: str) -> int | None:
    '''remove a port from name and return its group_id'''
    port = mng.get_port_from_name(name)
    if port is None:
        return None

    if name in mng._ports_by_name:
        mng._ports_by_name.pop(name)
    if port.uuid in mng._ports_by_uuid:
        mng._ports_by_uuid.pop(port.uuid)
    if port.type.is_jack and port.uuid:
        mng.jack_metadatas.remove_uuid(port.uuid)

    group = mng.get_group_from_id(port.group_id)
    if group is None:
        return None

    # remove portgroup first if port is in a portgroup
    if port.portgroup_id:
        for portgroup in group.portgroups:
            if portgroup.portgroup_id == port.portgroup_id:
                group.portgroups.remove(portgroup)
                portgroup.remove_from_canvas()
                break

    port.remove_from_canvas()
    group.remove_port(port)

    if not group.ports:
        group.remove_from_canvas()
        mng._remove_group(group)
        mng.sg.group_removed.emit(group.group_id)
        return None

    return group.group_id

# @later_by_batch(draw_group=True)
def rename_port(
        mng: 'PatchbayManager', name: str, new_name: str,
        uuid=0) -> int | None:
    if uuid:
        port = mng.get_port_from_uuid(uuid)
    else:
        port = mng.get_port_from_name(name)

    if port is None:
        if uuid:
            _logger.warning(
                f"rename_port to {new_name}, no port with uuid {uuid}")
        else:
            _logger.warning(
                f"rename_port to '{new_name}', no port named '{name}'")
        return

    # change port key in self._ports_by_name dict
    if name in mng._ports_by_name:
        mng._ports_by_name.pop(name)
    mng._ports_by_name[new_name] = port

    group_name = name.partition(':')[0]
    new_group_name = new_name.partition(':')[0]

    # In case a port rename implies another group for the port
    if group_name != new_group_name:
        group = mng.get_group_from_name(group_name)
        if group is not None:
            group.remove_port(port)
            if not group.ports:
                mng._remove_group(group)

        port.remove_from_canvas()
        port.full_name = new_name

        group = mng.get_group_from_name(new_group_name)
        if group is None:
            # copy the group_position to not move the group
            # because group has been renamed
            orig_gpos = mng.get_group_position(group_name)
            gpos = orig_gpos.copy()
            gpos.group_name = new_group_name

            group = Group(mng, mng._next_group_id, new_group_name, gpos)
            mng._next_group_id += 1
            group.add_port(port)
            group.add_to_canvas()
        else:
            group.add_port(port)

        port.add_to_canvas()
        return group.group_id

    port.full_name = new_name
    port.group.graceful_port(port)
    port.rename_in_canvas()
    return port.group.group_id

# @later_by_batch(metadata_change=True)
def metadata_update(
        mng: 'PatchbayManager', uuid: int,
        key: str, value: str) -> int | None:
    '''remember metadata and return the group_id'''

    # first store metadata
    mng.jack_metadatas.add(uuid, key, value)

    if not uuid:
        # all JACK metadatas removed
        mng.pretty_diff_checker.full_update()
        mng.remove_and_add_all()
        return

    match key:
        case '':
            # all metadatas removed for an item (client or port)
            port = mng.get_port_from_uuid(uuid)
            if port is not None:
                port.rename_in_canvas()
                return port.group_id

            for group in mng.groups:
                if group.uuid == uuid:
                    return group.group_id

        case JackMetadata.ORDER:
            port = mng.get_port_from_uuid(uuid)
            if port is None:
                return

            try:
                port_order = int(value)
            except:
                _logger.warning(
                    f"JACK_METADATA_ORDER for UUID {uuid} "
                    f"value '{value}' is not an int")
                return
            else:
                port.order = port_order
                return port.group_id

        case JackMetadata.PRETTY_NAME:
            mng.pretty_diff_checker.uuid_change(uuid)
            port = mng.get_port_from_uuid(uuid)
            if port is not None:
                port.rename_in_canvas()
                return port.group_id

            for group in mng.groups:
                if group.uuid == uuid:
                    group.rename_in_canvas()
                    return group.group_id

        case JackMetadata.PORT_GROUP:
            port = mng.get_port_from_uuid(uuid)
            if port is None:
                return

            return port.group_id

        case JackMetadata.ICON_NAME:
            for group in mng.groups:
                if group.uuid == uuid:
                    group.set_client_icon(value, from_metadata=True)
                    return group.group_id

        case JackMetadata.SIGNAL_TYPE:
            port = mng.get_port_from_uuid(uuid)
            if port is None:
                return

            if port.type is PortType.AUDIO_JACK:
                if value == 'CV':
                    port.subtype = PortSubType.CV
                elif value == 'AUDIO':
                    port.subtype = PortSubType.REGULAR

            return port.group_id

# @later_by_batch()
def add_connection(
        mng: 'PatchbayManager', port_out_name: str, port_in_name: str):
    port_out = mng.get_port_from_name(port_out_name)
    port_in = mng.get_port_from_name(port_in_name)

    if port_out is None or port_in is None:
        return

    for connection in mng.connections:
        if (connection.port_out is port_out
                and connection.port_in is port_in):
            return

    connection = Connection(mng, mng._next_connection_id, port_out, port_in)
    mng._next_connection_id += 1
    mng.connections.append(connection)

    connection.add_to_canvas()

# @later_by_batch()
def remove_connection(
        mng: 'PatchbayManager', port_out_name: str, port_in_name: str):
    port_out = mng.get_port_from_name(port_out_name)
    port_in = mng.get_port_from_name(port_in_name)
    if port_out is None or port_in is None:
        return

    for connection in mng.connections:
        if (connection.port_out is port_out
                and connection.port_in is port_in):
            mng.connections.remove(connection)
            mng.sg.connection_removed.emit(connection.connection_id)
            connection.remove_from_canvas()
            break
