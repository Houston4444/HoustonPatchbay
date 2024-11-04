from typing import TYPE_CHECKING

from .patchcanvas.patshared import (
    PortType,
    PortSubType,
    PortTypesViewFlag
)
from .patchcanvas import patchcanvas

if TYPE_CHECKING:
    from .patchbay_manager import PatchbayManager
    from .base_port import Port

class Connection:
    def __init__(self, manager: 'PatchbayManager', connection_id: int,
                 port_out: 'Port', port_in: 'Port'):
        self.manager = manager
        self.connection_id = connection_id
        self.port_out = port_out
        self.port_in = port_in
        self.in_canvas = False

    def port_type(self) -> PortType:
        return self.port_out.type

    def full_type(self) -> tuple[PortType, PortSubType]:
        port_out_type, port_out_subtype = self.port_out.full_type()
        port_in_type, port_in_subtype = self.port_in.full_type()
        return (port_out_type, port_out_subtype | port_in_subtype)
        
    def shown_in_port_types_view(
            self, port_types_view: PortTypesViewFlag) -> bool:
        if self.port_out.type is PortType.MIDI_JACK:
            return bool(port_types_view & PortTypesViewFlag.MIDI)
        
        if (self.port_out.type is PortType.AUDIO_JACK
                and self.port_in.type is PortType.AUDIO_JACK):
            if (self.port_out.subtype is PortSubType.CV
                    and self.port_in.subtype is PortSubType.CV): 
                return bool(port_types_view & PortTypesViewFlag.CV)
            if (self.port_out.subtype is PortSubType.REGULAR
                    and self.port_in.subtype is PortSubType.REGULAR):
                return bool(port_types_view & PortTypesViewFlag.AUDIO)
        
        return False

    def add_to_canvas(self):
        if self.manager.very_fast_operation:
            return

        if self.in_canvas:
            return

        if not (self.port_out.in_canvas and self.port_in.in_canvas):
            if not (self.port_out.in_canvas or self.port_in.in_canvas):
                return

            for port in (self.port_out, self.port_in):
                port.set_hidden_conn_in_canvas(self, True)
            return

        self.in_canvas = True

        patchcanvas.connect_ports(
            self.connection_id,
            self.port_out.group_id, self.port_out.port_id,
            self.port_in.group_id, self.port_in.port_id)
        
        for port in (self.port_out, self.port_in):
            port.set_hidden_conn_in_canvas(self, False)

    def remove_from_canvas(self):
        if self.manager.very_fast_operation:
            return

        if not self.in_canvas:
            for port in (self.port_out, self.port_in):
                port.set_hidden_conn_in_canvas(self, False)
            return

        patchcanvas.disconnect_ports(self.connection_id)
        self.in_canvas = False

    def semi_hide(self, yesno: bool):
        if not self.in_canvas:
            return
        
        patchcanvas.semi_hide_connection(
            self.connection_id, yesno)
    
    def set_in_front(self):
        if not self.in_canvas:
            return
        
        patchcanvas.set_connection_in_front(self.connection_id)