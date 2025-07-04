from typing import TYPE_CHECKING

from patshared import PortType
from ..patchcanvas import patchcanvas

if TYPE_CHECKING:
    from ..patchbay_manager import PatchbayManager
    from .port import Port

class Connection:
    def __init__(self, manager: 'PatchbayManager', connection_id: int,
                 port_out: 'Port', port_in: 'Port'):
        self.manager = manager
        self.connection_id = connection_id
        self.port_out = port_out
        self.port_in = port_in
        self.in_canvas = False

    @property
    def port_type(self) -> PortType:
        return self.port_out.type

    def add_to_canvas(self):
        if self.manager.very_fast_operation:
            return

        if self.in_canvas:
            return

        if not (self.port_out.in_canvas and self.port_in.in_canvas):
            for port in (self.port_out, self.port_in):
                port.set_hidden_conn_in_canvas(self, True)
            return

        patchcanvas.connect_ports(
            self.connection_id,
            self.port_out.group_id, self.port_out.port_id,
            self.port_in.group_id, self.port_in.port_id)

        self.in_canvas = True
        
        for port in (self.port_out, self.port_in):
            port.set_hidden_conn_in_canvas(self, False)

    def remove_from_canvas(self):
        if self.manager.very_fast_operation:
            return

        for port in (self.port_out, self.port_in):
            port.set_hidden_conn_in_canvas(self, False)

        if not self.in_canvas:
            return

        patchcanvas.disconnect_ports(self.connection_id)
        self.in_canvas = False
