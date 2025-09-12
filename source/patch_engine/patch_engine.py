#!/usr/bin/python3 -u

# standard lib imports
from enum import Enum
import signal
from typing import Optional
import threading
import time
from pathlib import Path
import logging
import json

# third party imports
import jack

# imports from HoustonPatchbay
from patshared import (
    PortType, JackMetadatas, JackMetadata, CustomNames,
    TransportPosition, TransportWanted)

# local imports
from .jack_bases import (
    ClientNamesUuids, PatchEngineOuterMissing, PatchEventQueue, PatchEvent)
from .patch_engine_outer import PatchEngineOuter
from .port_data import PortData, PortDataList
from .suppress_stdout_stderr import SuppressStdoutStderr
from .alsa_lib_check import ALSA_LIB_OK
if ALSA_LIB_OK:
    from .alsa_manager import AlsaManager


_logger = logging.getLogger(__name__)

METADATA_LOCKER = 'pretty-name-export.locker'


class AutoExportPretty(Enum):
    NO = 0
    YES = 1
    ZOMBIE = 2

    @property
    def active(self) -> bool:
        return self is self.YES

    def __bool__(self) -> bool:
        return bool(self.value)


def jack_pretty_name(uuid: int) -> str:
    value_type = jack.get_property(uuid, JackMetadata.PRETTY_NAME)
    if value_type is None:
        return ''
    return value_type[0].decode()


class PatchEngine:
    ports = PortDataList()
    connections = list[tuple[str, str]]()
    metadatas = JackMetadatas()
    'JACK metadatas, r/w in main thread only'

    client_name_uuids = ClientNamesUuids()
    patch_event_queue = PatchEventQueue()
    '''JACK events, clients and ports registrations,
    connections, metadata changes'''
    jack_running = False
    alsa_mng: Optional['AlsaManager'] = None
    terminate = False
    client = None
    samplerate = 48000
    buffer_size = 1024
    
    pretty_names_lockers = set[int]()
    '''
    Contains uuids of clients containing the METADATA_LOCKER.
    Normally, the way the program is done, only one client
    could have this metadata written, but we can't ensure
    that any other programs write this.

    This locker means that another instance has 'auto export pretty names'
    activated. In this case, 'auto export pretty names' feature will be
    deactivate for this instance to avoid conflicts.
    '''

    auto_export_pretty_names = AutoExportPretty.YES
    '''True if the patchbay option 'Auto-Export pretty names to JACK'
    is activated (True by default).'''
    
    one_shot_act = ''
    '''can be an OSC path in case if this object is instantiated
    only to make one action about pretty names
    (import, export, clear)'''
    
    mdata_locker_value = '1'
    '''The value of the locker metadata, has no real effect.
    Ideally the daemon port for a Session Manager.'''

    dsp_wanted = True
    transport_wanted = TransportWanted.FULL
    
    def __init__(
            self, client_name: str, pretty_tmp_path: Optional[Path]=None,
            auto_export_pretty_names=False):
        self.wanted_client_name = client_name
        self.custom_names_ready = False

        self.last_sent_dsp_load = 0
        self.max_dsp_since_last_sent = 0.00

        self._waiting_jack_client_open = True

        self.last_transport_pos = TransportPosition(
            0, False, False, 0, 0, 0, 0.0)

        if auto_export_pretty_names:
            self.auto_export_pretty_names = AutoExportPretty.YES
        else:
            self.auto_export_pretty_names = AutoExportPretty.NO

        self.custom_names = CustomNames()
        '''Contains all internal custom names,
        including some groups and ports not existing now'''

        self.uuid_pretty_names = dict[int, str]()
        '''Contains pairs of 'uuid: pretty_name' of all pretty_names
        exported to JACK metadatas by this program.'''
        
        self.uuid_waiting_pretty_names = dict[int, str]()
        '''Contains pairs of 'uuid: pretty_name' of pretty_names just
        set and waiting for the property change callback.'''

        self.pretty_tmp_path = pretty_tmp_path
        
        self._locker_written = False
        self._client_uuid = 0
        self._client_name = ''
        
        self.peo: Optional[PatchEngineOuter] = None
        
    def start(self, patchbay_engine: PatchEngineOuter):
        self.peo = patchbay_engine
        self.peo.write_existence_file()
        self.start_jack_client()
        
        if ALSA_LIB_OK:
            self.alsa_mng = AlsaManager(self)
            self.alsa_mng.add_all_ports()
            
    @property
    def can_leave(self) -> bool:
        if self.peo is None:
            raise PatchEngineOuterMissing
        
        if self.terminate:
            return True
        if self.auto_export_pretty_names:
            return False
        if self.one_shot_act:
            return False
        return self.peo.can_leave
    
    @classmethod
    def signal_handler(cls, sig: int, frame):
        if sig in (signal.SIGINT, signal.SIGTERM):
            cls.terminate = True
    
    def internal_stop(self):
        self.terminate = True
    
    def _write_locker_mdata(self):
        '''set locker identifier.
        Multiple daemons can co-exist,
        But if we want things going right,
        we have to ensure that each daemon runs on a different JACK server'''
        if self.client is None:
            return
        if self.pretty_names_lockers:
            return
        if not self.auto_export_pretty_names.active:
            return

        try:
            self.client.set_property(
                self.client.uuid, METADATA_LOCKER,
                self.mdata_locker_value)
        except:
            _logger.warning(
                f'Failed to set locker metadata for {self._client_name}, '
                'could cause troubles if you start multiple daemons.')
        else:
            self._locker_written = True
    
    def _remove_locker_mdata(self):
        if self.client is None:
            return
        
        if self._locker_written:
            try:
                self.client.remove_property(
                    self.client.uuid, METADATA_LOCKER)
            except:
                _logger.warning(
                    f'Failed to remove locker metadata for {self._client_name}')
        self._locker_written = False
        
    def process_patch_events(self):
        if self.client is None:
            return
        if self.peo is None:
            raise PatchEngineOuterMissing
        
        for event, event_arg in self.patch_event_queue:
            match event:
                case PatchEvent.CLIENT_ADDED:
                    name: str = event_arg #type:ignore
                    try:
                        client_uuid = int(
                            self.client.get_uuid_for_client_name(name))
                    except:
                        ...
                    else:
                        self.client_name_uuids[name] = client_uuid
                        self.peo.associate_client_name_and_uuid(
                            name, client_uuid)
                    self.peo.jack_client_added(name)

                case PatchEvent.CLIENT_REMOVED:
                    name: str = event_arg #type:ignore
                    if name not in self.client_name_uuids:
                        continue

                    uuid = self.client_name_uuids.pop(name)
                    if uuid not in self.metadatas:
                        continue
                    
                    uuid_dict = self.metadatas.pop(uuid)
                    if uuid_dict.get(METADATA_LOCKER) is not None:
                        self.pretty_names_lockers.discard(uuid)
                        self.peo.send_pretty_names_locked(
                            bool(self.pretty_names_lockers))
                    self.peo.jack_client_removed(name)

                case PatchEvent.PORT_ADDED:
                    port: PortData = event_arg #type:ignore
                    self.ports.append(port)
                    self.peo.port_added(
                        port.name, port.type, port.flags, port.uuid)

                case PatchEvent.PORT_REMOVED:
                    port = self.ports.from_name(event_arg) #type:ignore
                    self.ports.remove(port)
                    self.peo.port_removed(port.name)

                case PatchEvent.PORT_RENAMED:
                    old_new: tuple[str, str, int] = event_arg #type:ignore
                    old, new, uuid = old_new
                    self.ports.rename(old, new)
                    self.peo.port_renamed(old, new, uuid)
                
                case PatchEvent.CONNECTION_ADDED:
                    conn: tuple[str, str] = event_arg #type:ignore
                    self.connections.append(conn)
                    self.peo.connection_added(conn)
                
                case PatchEvent.CONNECTION_REMOVED:
                    conn: tuple[str, str] = event_arg #type:ignore
                    if conn in self.connections:
                        self.connections.remove(conn)
                    self.peo.connection_removed(conn)
                
                case PatchEvent.CLIENT_ADDED:
                    client_name: str = event_arg #type:ignore
                    self.peo.jack_client_added(client_name)
                
                case PatchEvent.CLIENT_REMOVED:
                    client_name: str = event_arg # type:ignore
                    self.peo.jack_client_removed(client_name)
                
                case PatchEvent.XRUN:
                    self.peo.send_one_xrun()
                
                case PatchEvent.BLOCKSIZE_CHANGED:
                    buffer_size: int = event_arg #type:ignore
                    self.buffer_size = buffer_size
                    self.peo.send_buffersize(self.buffer_size)
                
                case PatchEvent.SAMPLERATE_CHANGED:
                    samplerate: int = event_arg #type:ignore
                    self.samplerate = samplerate
                    self.peo.send_samplerate(self.samplerate)
                
                case PatchEvent.METADATA_CHANGED:
                    uuid_key_value: tuple[int, str, str] = event_arg #type:ignore
                    uuid, key, value = uuid_key_value
                    
                    if key == '':
                        if uuid == 0:
                            self.uuid_pretty_names.clear()
                            self._save_uuid_pretty_names()
                            self._write_locker_mdata()

                        elif uuid == self._client_uuid :
                            self._write_locker_mdata()
                        
                        else:
                            uuid_dict = self.metadatas.get(uuid)
                            if uuid_dict is not None:
                                if METADATA_LOCKER in uuid_dict.keys():
                                    self.pretty_names_lockers.discard(uuid)
                                    self.peo.send_pretty_names_locked(
                                        bool(self.pretty_names_lockers))
                            
                    self.metadatas.add(uuid, key, value)
                    self.peo.metadata_updated(uuid, key, value)

                    if key == METADATA_LOCKER:
                        if uuid == self._client_uuid:
                            if not value:
                                # if the metadata locker has been removed
                                # from an external client,
                                # re-set it immediatly.
                                self._write_locker_mdata()
                        else:
                            try:
                                client_name = \
                                    self.client.get_client_name_by_uuid(
                                        str(uuid))
                            except:
                                ...
                            else:
                                if value and self.auto_export_pretty_names:
                                    self.auto_export_pretty_names = \
                                        AutoExportPretty.ZOMBIE
                                
                                if value:
                                    self.pretty_names_lockers.add(uuid)
                                else:
                                    self.pretty_names_lockers.discard(uuid)
                                self.peo.send_pretty_names_locked(
                                    bool(self.pretty_names_lockers))

                case PatchEvent.SHUTDOWN:
                    self.ports.clear()
                    self.connections.clear()
                    self.metadatas.clear()
                    self.peo.server_stopped()
                    self.jack_running = False

    def check_pretty_names_export(self):
        client_names = set[str]()
        port_names = set[str]()
        
        for event, event_arg in self.patch_event_queue.oldies():
            if not isinstance(event_arg, str):
                continue
            
            match event:
                case PatchEvent.CLIENT_ADDED:
                    client_names.add(event_arg)
                case PatchEvent.CLIENT_REMOVED:
                    client_names.discard(event_arg)
                case PatchEvent.PORT_ADDED:
                    port_names.add(event_arg)
                case PatchEvent.PORT_REMOVED:
                    port_names.discard(event_arg)
        
        if not self.jack_running:
            return
        
        if self.client is None:
            return
        
        if self.pretty_names_lockers:
            return
        
        if not self.auto_export_pretty_names.active:
            return
        
        has_changes = False
        
        for client_name in client_names:
            client_uuid = self.client_name_uuids.get(client_name)
            if client_uuid is None:
                continue
            
            if self.set_jack_pretty_name_conditionally(
                    True, client_name, client_uuid):
                has_changes = True
                
        for port_name in port_names:
            try:
                port = self.client.get_port_by_name(port_name)
            except:
                continue
            
            if self.set_jack_pretty_name_conditionally(
                    False, port_name, port.uuid):
                has_changes = True
        
        if has_changes:
            self._save_uuid_pretty_names()
    
    def _check_jack_client_responding(self):
        '''Launched in parrallel thread,
        checks that JACK client creation finish.'''
        if self.peo is None:
            raise PatchEngineOuterMissing

        for i in range(100): # JACK has 5s to answer
            time.sleep(0.050)

            if not self._waiting_jack_client_open:
                break
        else:
            # server never answer
            _logger.error(
                'Server never answer when trying to open JACK client !')
            self.peo.send_server_lose()
            self.peo.remove_existence_file()
            
            # JACK is not responding at all
            # probably it is started but totally bugged
            # finally kill this program from system
            self.terminate = True
    
    def refresh(self):
        if self.peo is None:
            raise PatchEngineOuterMissing
        
        _logger.debug(f'refresh jack running {self.jack_running}')
        if self.jack_running:
            self._collect_graph()
            self.peo.server_restarted()
            
        if self.alsa_mng is not None:
            self.alsa_mng.add_all_ports()
    
    def remember_dsp_load(self):
        if self.client is None:
            return
        
        self.max_dsp_since_last_sent = max(
            self.max_dsp_since_last_sent,
            self.client.cpu_load())
        
    def send_dsp_load(self):
        if self.peo is None:
            raise PatchEngineOuterMissing
        
        current_dsp = int(self.max_dsp_since_last_sent + 0.5)
        if current_dsp != self.last_sent_dsp_load:
            self.peo.send_dsp_load(current_dsp)
            self.last_sent_dsp_load = current_dsp
        self.max_dsp_since_last_sent = 0.00

    def send_transport_pos(self):
        if self.transport_wanted is TransportWanted.NO:
            return
        
        if self.peo is None:
            raise PatchEngineOuterMissing
        
        if self.client is None:
            return
        
        state, pos_dict = self.client.transport_query()
        
        if (self.transport_wanted is TransportWanted.STATE_ONLY
                and bool(state) == self.last_transport_pos.rolling):
            return

        transport_position = TransportPosition(
            pos_dict['frame'],
            state == jack.ROLLING,
            'bar' in pos_dict,
            pos_dict.get('bar', 0),
            pos_dict.get('beat', 0),
            pos_dict.get('tick', 0),
            pos_dict.get('beats_per_minute', 0.0))
        
        if transport_position == self.last_transport_pos:
            return
        
        self.last_transport_pos = transport_position
        self.peo.send_transport_position(transport_position)
    
    def connect_ports(self, port_out_name: str, port_in_name: str,
                      disconnect=False):
        if (self.alsa_mng is not None
                and port_out_name.startswith(':ALSA_OUT:')):
            self.alsa_mng.connect_ports(
                port_out_name, port_in_name, disconnect=disconnect)
            return

        if self.client is None:
            return

        if disconnect:
            try:
                self.client.disconnect(port_out_name, port_in_name)
            except jack.JackErrorCode:
                # ports already disconnected
                ...
            except BaseException as e:
                _logger.warning(
                    f"Failed to disconnect '{port_out_name}' "
                    f"from '{port_in_name}'\n{str(e)}")
        else:
            try:
                self.client.connect(port_out_name, port_in_name)
            except jack.JackErrorCode:
                # ports already connected
                ...
            except BaseException as e:
                _logger.warning(
                    f"Failed to connect '{port_out_name}' "
                    f"to '{port_in_name}'\n{str(e)}")
    
    def set_buffer_size(self, blocksize: int):
        if self.client is None:
            return
        
        self.client.blocksize = blocksize
             
    def exit(self):
        self._save_uuid_pretty_names()
        
        if self.client is not None:
            _logger.debug('deactivate JACK client')
            self.client.deactivate()
            _logger.debug('close JACK client')
            self.client.close()
            _logger.debug('JACK client closed')

        if self.alsa_mng is not None:
            self.alsa_mng.stop_events_loop()
            del self.alsa_mng

        if self.peo is not None:
            self.peo.remove_existence_file()
        _logger.debug('Exit, bye bye.')
    
    def start_jack_client(self):
        if self.peo is None:
            raise PatchEngineOuterMissing
        
        self._waiting_jack_client_open = True
        
        # Sometimes JACK never registers the client
        # and never answers. This thread will allow to exit
        # if JACK didn't answer 5 seconds after register ask
        jack_waiter_thread = threading.Thread(
            target=self._check_jack_client_responding)
        jack_waiter_thread.start()

        fail_info = False
        self.client = None

        _logger.debug('Start JACK client')

        with SuppressStdoutStderr():
            try:
                self.client = jack.Client(
                    self.wanted_client_name,
                    no_start_server=True)

            except jack.JackOpenError:
                fail_info = True
                del self.client
                self.client = None
        
        if fail_info:
            _logger.info('Failed to connect client to JACK server')
        else:
            _logger.info('JACK client started successfully')
        
        if self.client is not None:
            try:
                self._client_name = self.client.name
            except:
                _logger.warning('Failed to get client name, very strange.')
            
            try:
                self._client_uuid = int(self.client.uuid)
            except:
                _logger.warning('JACK metadatas seems to not work correctly')
        
        self._waiting_jack_client_open = False

        jack_waiter_thread.join()
        if self.terminate:
            return

        self.jack_running = bool(self.client is not None)

        if self.client is not None:
            self._set_registrations()
            self._collect_graph()
            self._write_locker_mdata()

            self.samplerate = self.client.samplerate
            self.buffer_size = self.client.blocksize
            self.peo.server_restarted()
        
        if (self.pretty_tmp_path is not None
                and self.pretty_tmp_path.exists()):
            # read the contents of pretty names set by this program
            # in a previous run (with same daemon osc port).
            try:
                with open(self.pretty_tmp_path, 'r') as f:
                    pretty_dict = json.load(f)
                    if isinstance(pretty_dict, dict):
                        self.uuid_pretty_names.clear()
                        for key, value in pretty_dict.items():
                            self.uuid_pretty_names[int(key)] = value
            except ValueError:
                _logger.warning(
                    f'{self.pretty_tmp_path} badly written, ignored.')
            except:
                _logger.warning(
                    f'Failed to read {self.pretty_tmp_path}, ignored.')
        
        self.peo.is_now_ready()
    
    def _set_registrations(self):
        if self.client is None:
            return

        @self.client.set_client_registration_callback
        def client_registration(name: str, register: bool):
            _logger.debug(f'client registration {register} "{name}"')
            if register:
                self.patch_event_queue.add(
                    PatchEvent.CLIENT_ADDED, name)
            else:
                self.patch_event_queue.add(
                    PatchEvent.CLIENT_REMOVED, name)
            
        @self.client.set_port_registration_callback
        def port_registration(port: jack.Port, register: bool):
            port_type = PortType.NULL
            if port.is_audio:
                port_type = PortType.AUDIO_JACK
            elif port.is_midi:
                port_type = PortType.MIDI_JACK

            flags = jack._lib.jack_port_flags(port._ptr) #type:ignore
            port_name = port.name
            port_uuid = port.uuid

            _logger.debug(
                f'port registration {register} "{port_name}" {port_uuid}')

            if register:                
                self.patch_event_queue.add(
                    PatchEvent.PORT_ADDED,
                    PortData(port_name, port_type, flags, port_uuid))
            else:
                self.patch_event_queue.add(
                    PatchEvent.PORT_REMOVED, port_name)

        @self.client.set_port_connect_callback
        def port_connect(port_a: jack.Port, port_b: jack.Port, connect: bool):
            conn = (port_a.name, port_b.name)
            _logger.debug(f'ports connected {connect} {conn}')

            if connect:
                self.patch_event_queue.add(
                    PatchEvent.CONNECTION_ADDED, conn)
            else:
                self.patch_event_queue.add(
                    PatchEvent.CONNECTION_REMOVED, conn)
            
        @self.client.set_port_rename_callback
        def port_rename(port: jack.Port, old: str, new: str):
            _logger.debug(f'port renamed "{old}" to "{new}"')
            self.patch_event_queue.add(
                PatchEvent.PORT_RENAMED, old, new, port.uuid)

        @self.client.set_xrun_callback
        def xrun(delayed_usecs: float):
            self.patch_event_queue.add(PatchEvent.XRUN)
            
        @self.client.set_blocksize_callback
        def blocksize(size: int):
            self.patch_event_queue.add(PatchEvent.BLOCKSIZE_CHANGED, size)
            
        @self.client.set_samplerate_callback
        def samplerate(samplerate: int):
            self.patch_event_queue.add(
                PatchEvent.SAMPLERATE_CHANGED, samplerate)
            
        try:
            @self.client.set_property_change_callback
            def property_change(subject: int, key: str, change: int):
                if change == jack.PROPERTY_DELETED:
                    self.patch_event_queue.add(
                        PatchEvent.METADATA_CHANGED, subject, key, '')
                    
                    if key in (JackMetadata.PRETTY_NAME, ''):
                        if subject in self.uuid_waiting_pretty_names:
                            self.uuid_waiting_pretty_names.pop(subject)
                    return                            

                value_type = jack.get_property(subject, key)
                if value_type is None:
                    return
                value = value_type[0].decode()

                if key == JackMetadata.PRETTY_NAME:
                    if subject in self.uuid_waiting_pretty_names:
                        if value != self.uuid_waiting_pretty_names[subject]:
                            _logger.warning(
                                f'Incoming pretty-name property does not '
                                f'have the expected value\n'
                                f'expected: {self.uuid_pretty_names[subject]}\n'
                                f'value   : {value}')

                        self.uuid_waiting_pretty_names.pop(subject)

                self.patch_event_queue.add(
                    PatchEvent.METADATA_CHANGED, subject, key, value)

        except jack.JackError as e:
            _logger.warning(
                "jack-metadatas are not available,"
                "probably due to the way JACK has been compiled."
                + str(e))
            
        @self.client.set_shutdown_callback
        def on_shutdown(status: jack.Status, reason: str):
            _logger.debug('Jack shutdown')
            self.patch_event_queue.add(PatchEvent.SHUTDOWN)
            
        self.client.activate()
        
        if self.client.name != self.wanted_client_name:
            _logger.warning(
                f'This instance seems to not be the only one ' 
                f'{self.wanted_client_name} instance in this JACK graph. '
                f'It can easily create conflicts, especially for pretty-names'
            )
    
    def _collect_graph(self):
        if self.peo is None:
            raise PatchEngineOuterMissing
        
        self.ports.clear()
        self.connections.clear()
        self.metadatas.clear()

        client_names = set[str]()
        known_uuids = set[int]()

        if self.client is None:
            return

        #get all currents Jack ports and connections
        for port in self.client.get_ports():
            flags = jack._lib.jack_port_flags(port._ptr) #type:ignore
            port_name = port.name
            port_uuid = port.uuid
            port_type = PortType.NULL
            if port.is_audio:
                port_type = PortType.AUDIO_JACK
            elif port.is_midi:
                port_type = PortType.MIDI_JACK

            known_uuids.add(port_uuid)

            self.ports.append(
                PortData(port_name, port_type, flags, port_uuid))

            client_names.add(port_name.partition(':')[0])
                
            if port.is_input:
                continue

            # this port is output, list its connections
            for conn_port in self.client.get_all_connections(port):
                self.connections.append((port_name, conn_port.name))
        
        for client_name in client_names:
            try:
                client_uuid = int(
                    self.client.get_uuid_for_client_name(client_name))
            except jack.JackError:
                continue
            except ValueError:
                _logger.warning(
                    f"uuid for client name {client_name} is not digit")
                continue

            self.client_name_uuids[client_name] = client_uuid
            known_uuids.add(client_uuid)
        
        for uuid, uuid_dict in jack.get_all_properties().items():
            if uuid not in known_uuids:
                # uuid seems to not belong to a port, 
                # or to a client containing ports.
                # It very probably belongs to a client without ports.
                try:
                    client_name = \
                        self.client.get_client_name_by_uuid(str(uuid))
                except:
                    ...
                else:
                    self.client_name_uuids[client_name] = uuid
            
            for key, valuetype in uuid_dict.items():
                value = valuetype[0].decode()
                self.metadatas.add(uuid, key, value)
                
                if (key == METADATA_LOCKER 
                        and uuid != self._client_uuid and value.isdigit()):
                    if self.auto_export_pretty_names.active:
                        self.auto_export_pretty_names = \
                            AutoExportPretty.ZOMBIE
                    self.pretty_names_lockers.add(uuid)
                    self.peo.send_pretty_names_locked(True)

    def _save_uuid_pretty_names(self):
        '''save the contents of self.uuid_pretty_names in /tmp
        
        In order to recognize which JACK pretty names have been set
        by this program (in this process or not), pretty names are
        saved somewhere in the /tmp directory.'''
        if self.pretty_tmp_path is None:
            return
        
        try:
            self.pretty_tmp_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.pretty_tmp_path, 'w') as f:
                json.dump(self.uuid_pretty_names, f)
        except:
            _logger.warning(f'Failed to save {self.pretty_tmp_path}')

    def _set_jack_pretty_name(self, uuid: int, pretty_name: str):
        'write pretty-name metadata, or remove it if value is empty'
        if self.client is None:
            _logger.warning(
                'Attempting to set pretty-name metadata while JACK '
                'is not running or JACK client is not ready.')
            return
        
        if pretty_name:
            try:
                self.client.set_property(
                    uuid, JackMetadata.PRETTY_NAME, pretty_name)
                _logger.info(f'Pretty-name set to "{pretty_name}" on {uuid}')
            except:
                _logger.warning(
                    f'Failed to set pretty-name "{pretty_name}" for {uuid}')
                return
            
            if self.auto_export_pretty_names.active:
                self.uuid_pretty_names[uuid] = pretty_name
            self.uuid_waiting_pretty_names[uuid] = pretty_name

        else:
            try:
                self.client.remove_property(uuid, JackMetadata.PRETTY_NAME)
                _logger.info(f'Pretty-name removed from {uuid}')
            except:
                _logger.warning(
                    f'Failed to remove pretty-name for {uuid}')
                return
            
            if self.auto_export_pretty_names.active:
                if uuid in self.uuid_pretty_names:
                    self.uuid_pretty_names.pop(uuid)
            if uuid in self.uuid_waiting_pretty_names:
                self.uuid_waiting_pretty_names.pop(uuid)

    def _jack_pretty_name_if_not_mine(self, uuid: int) -> str:
        mdata_pretty_name = jack_pretty_name(uuid)
        if not mdata_pretty_name:
            return ''
        
        if mdata_pretty_name == self.uuid_pretty_names.get(uuid):
            return ''
        
        return mdata_pretty_name

    def apply_pretty_names_export(self):
        '''Set all pretty names once all custom names are received,
        or clear them if self.auto_export_pretty_names is False 
        and some pretty names have been written by a previous process.'''
        self.custom_names_ready = True

        if not self.jack_running or self.pretty_names_lockers:
            return

        self.set_pretty_names_auto_export(
            self.auto_export_pretty_names.active, force=True)

    def write_group_pretty_name(self, client_name: str, pretty_name: str):
        if not self.jack_running:
            return
        
        client_uuid = self.client_name_uuids.get(client_name)
        if client_uuid is None:
            return

        mdata_pretty_name = self._jack_pretty_name_if_not_mine(client_uuid)
        self.custom_names.save_group(
            client_name, pretty_name, mdata_pretty_name)
        
        self._set_jack_pretty_name(client_uuid, pretty_name)
        self._save_uuid_pretty_names()

    def write_port_pretty_name(self, port_name: str, pretty_name: str):        
        if self.client is None:
            return

        try:
            port = self.client.get_port_by_name(port_name)
        except BaseException as e:
            _logger.warning(
                f'Unable to find port {port_name} '
                f'to set the pretty-name {pretty_name}')
            return

        if port is None:
            return

        port_uuid = port.uuid
        mdata_pretty_name = self._jack_pretty_name_if_not_mine(port_uuid)
        self.custom_names.save_port(port_name, pretty_name, mdata_pretty_name)
        self._set_jack_pretty_name(port.uuid, pretty_name)
        self._save_uuid_pretty_names()

    def set_jack_pretty_name_conditionally(
            self, for_client: bool, name: str, uuid: int) -> bool:
        '''set jack pretty name if checks are ok.
        checks are :
        - a custom name exists for this item
        - this custom name is not the current pretty name
        - the current pretty name is empty or known to be overwritable
        
        return False if one of theses checks fails.'''

        mdata_pretty_name = jack_pretty_name(uuid)
        if for_client:
            ptov = self.custom_names.groups.get(name)
        else:
            ptov = self.custom_names.ports.get(name)

        if (ptov is None
                or not ptov.custom
                or ptov.custom == mdata_pretty_name):
            return False
        
        if (mdata_pretty_name
                and ptov.above_pretty
                and mdata_pretty_name not in ptov.above_pretty
                and mdata_pretty_name != self.uuid_pretty_names.get(uuid)):
            item_type = 'client' if for_client else 'port'
            _logger.warning(
                f"pretty-name not set\n"
                f"  {item_type}: {name}\n"
                f"  uuid: {uuid}\n"
                f"  wanted   : '{ptov.custom}'\n"
                f"  above    : '{ptov.above_pretty}'\n"
                f"  existing : '{mdata_pretty_name}'\n")
            return False
        
        self._set_jack_pretty_name(uuid, ptov.custom)
        return True

    def set_pretty_names_auto_export(self, active: bool, force=False):
        if self.pretty_names_lockers:
            if active:
                self.auto_export_pretty_names = AutoExportPretty.ZOMBIE
            else:
                self.auto_export_pretty_names = AutoExportPretty.NO
            return

        if (self.auto_export_pretty_names is not AutoExportPretty.ZOMBIE
                and not force
                and active is self.auto_export_pretty_names.active):
            return
        
        if self.client is None:
            return
        
        if active:
            self.auto_export_pretty_names = AutoExportPretty.YES
            self._write_locker_mdata()
            
            for client_name, client_uuid in self.client_name_uuids.items():
                self.set_jack_pretty_name_conditionally(
                    True, client_name, client_uuid)
            
            for port_name in self.custom_names.ports:
                try:
                    port = self.client.get_port_by_name(port_name)
                except jack.JackError:
                    continue
                
                self.set_jack_pretty_name_conditionally(
                    False, port_name, port.uuid)

        else:
            self.auto_export_pretty_names = AutoExportPretty.NO
            self._remove_locker_mdata()

            # clear pretty-name metadata created by this from JACK

            for client_name, client_uuid in self.client_name_uuids.items():
                if client_uuid not in self.uuid_pretty_names:
                    continue

                mdata_pretty_name = jack_pretty_name(client_uuid)
                pretty_name = self.custom_names.custom_group(client_name)
                if pretty_name == mdata_pretty_name:
                    self._set_jack_pretty_name(client_uuid, '')
                    
            for port in self.client.get_ports():
                port_uuid = port.uuid
                if port_uuid not in self.uuid_pretty_names:
                    continue
                
                port_name = port.name
                mdata_pretty_name = jack_pretty_name(port_uuid)
                pretty_name = self.custom_names.custom_port(port_name)
                if pretty_name == mdata_pretty_name:
                    self._set_jack_pretty_name(port_uuid, '')

            self.uuid_pretty_names.clear()
        
        self._save_uuid_pretty_names()

    def import_all_pretty_names_from_jack(
            self) -> tuple[dict[str, str], dict[str, str]]:
        clients_dict = dict[str, str]()
        ports_dict = dict[str, str]()

        for client_name, uuid in self.client_name_uuids.items():
            jack_pretty = jack_pretty_name(uuid)
            if not jack_pretty:
                continue

            pretty_name = self.custom_names.custom_group(client_name)
            if pretty_name != jack_pretty:
                self.custom_names.save_group(client_name, jack_pretty)
                clients_dict[client_name] = jack_pretty

        for jport in self.ports:
            jack_pretty = jack_pretty_name(jport.uuid)
            if not jack_pretty:
                continue
            
            pretty_name = self.custom_names.custom_port(jport.name)
            if pretty_name != jack_pretty:
                self.custom_names.save_port(jport.name, jack_pretty)
                ports_dict[jport.name] = jack_pretty
        
        return clients_dict, ports_dict

    def export_all_custom_names_to_jack_now(self):
        for client_name, uuid in self.client_name_uuids.items():
            pretty_name = self.custom_names.custom_group(client_name)
            if pretty_name:
                self._set_jack_pretty_name(uuid, pretty_name)
        
        for jport in self.ports:
            pretty_name = self.custom_names.custom_port(jport.name)
            if pretty_name:
                self._set_jack_pretty_name(jport.uuid, pretty_name)

    def clear_all_pretty_names_from_jack(self):
        for uuid, uuid_dict in self.metadatas.items():
            if JackMetadata.PRETTY_NAME in uuid_dict:
                self._set_jack_pretty_name(uuid, '')
        
        if self.auto_export_pretty_names.active:
            self.set_pretty_names_auto_export(True, force=True)

    def transport_play(self, play: bool):
        if self.client is None:
            return
        
        if play:
            self.client.transport_start()
        else:
            self.client.transport_stop()
            
    def transport_stop(self):
        if self.client is None:
            return
        
        self.client.transport_stop()
        self.client.transport_locate(0)
        
    def transport_relocate(self, frame: int):
        if self.client is None:
            return
        self.client.transport_locate(frame)
