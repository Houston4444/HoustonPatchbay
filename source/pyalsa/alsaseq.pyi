
from typing import TypeAlias, Any

PortTuple: TypeAlias = tuple[int, int]
AlsaConstant: TypeAlias = int

SEQ_LIB_VERSION_STR: str

SEQ_PORT_CAP_READ: AlsaConstant = 0x01
SEQ_PORT_CAP_WRITE: AlsaConstant = 0x02
SEQ_PORT_CAP_SUBS_READ: AlsaConstant = 0x20
SEQ_PORT_CAP_SUBS_WRITE: AlsaConstant = 0x40
SEQ_PORT_CAP_NO_EXPORT: AlsaConstant = 0x80
SEQ_PORT_TYPE_APPLICATION: AlsaConstant = 0x100000
SEQ_CLIENT_SYSTEM: AlsaConstant = 0
SEQ_USER_CLIENT: AlsaConstant = 1
SEQ_PORT_SYSTEM_ANNOUNCE: AlsaConstant = 1
SEQ_EVENT_CLIENT_START: AlsaConstant = 60
SEQ_EVENT_CLIENT_EXIT: AlsaConstant = 61
SEQ_EVENT_PORT_START: AlsaConstant = 63
SEQ_EVENT_PORT_EXIT: AlsaConstant = 64
SEQ_EVENT_PORT_SUBSCRIBED: AlsaConstant = 66
SEQ_EVENT_PORT_UNSUBSCRIBED: AlsaConstant = 67


class SequencerError:...


class AlsaEvent:
    type: AlsaConstant
    
    def get_data(self) -> dict[str, Any]:...


class Sequencer:
    client_id: int
    
    def __init__(self, clientname=''):
        ...
    def create_simple_port(
            self, name='', type=SEQ_USER_CLIENT, caps=0) -> int:
        ...
    def connect_ports(
            self, from_: PortTuple, to_: PortTuple, *oargs):
        ...
    def disconnect_ports(self, from_: PortTuple, to_: PortTuple):
        ...
    def connection_list(self) -> list[
            tuple[str, int, list[tuple[
                str, int, list[list[tuple[int, int]]]]]]]:
        ...
    def receive_events(self, timeout=128, maxevents=1) -> list[AlsaEvent]:
        ...
    def get_client_info(self, client_id: int) -> dict[str, str]:
        ...
    def get_port_info(self, port_id: int, client_id: int) -> dict[str, Any]:
        ...
    def exit(self):
        ...