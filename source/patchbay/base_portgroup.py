from typing import TYPE_CHECKING

from patshared import PortMode, PortType, PortSubType
from .base_port import Port
from .patchcanvas import patchcanvas

if TYPE_CHECKING:
    from .patchbay_manager import PatchbayManager

class Portgroup:
    '''Portgroup is a group of ports, in most cases a stereo pair'''
    def __init__(self, manager: 'PatchbayManager', group_id: int,
                 portgroup_id: int, port_mode: PortMode, ports: tuple[Port]):
        self.manager = manager
        self.group_id = group_id
        self.portgroup_id = portgroup_id
        self.port_mode = port_mode
        self.ports = tuple(ports)

        self.mdata_portgroup = ''
        self.above_metadatas = False

        self.in_canvas = False

        if len(self.ports) >= 2:
            for port in self.ports:
                port.portgroup_id = portgroup_id

    def port_type(self):
        if not self.ports:
            return PortType.NULL

        return self.ports[0].type

    @property
    def full_type(self) -> tuple[PortType, PortSubType]:
        if not self.ports:
            return (PortType.NULL, PortSubType.REGULAR)
        
        return self.ports[0].full_type

    def update_ports_in_canvas(self):
        for port in self.ports:
            port.rename_in_canvas()

    def sort_ports(self):
        port_list = list(self.ports)
        port_list.sort()
        self.ports = tuple(port_list)

    def add_to_canvas(self):
        if self.manager.very_fast_operation:
            return

        if self.in_canvas:
            return
    
        if not self.manager.port_type_shown(self.full_type):
            return

        if len(self.ports) < 2:
            return

        for port in self.ports:
            if not port.in_canvas:
                return

        self.in_canvas = True

        patchcanvas.add_portgroup(
            self.group_id, self.portgroup_id,
            self.port_mode, self.ports[0].type, self.ports[0].subtype,
            [port.port_id for port in self.ports])

    def remove_from_canvas(self):
        if self.manager.very_fast_operation:
            return
        
        if not self.in_canvas:
            return

        patchcanvas.remove_portgroup(self.group_id, self.portgroup_id)
        self.in_canvas = False
