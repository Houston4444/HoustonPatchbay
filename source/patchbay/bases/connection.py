from typing import TYPE_CHECKING, Iterator

from patshared import PortType

from ..patchcanvas import patchcanvas

if TYPE_CHECKING:
    from ..patchbay_manager import PatchbayManager
    from .port import Port
    from .group import Group


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
        

class Connections(list[Connection]):
    def __init__(self):
        super().__init__()
        self._group_out: 'dict[Group, list[Connection]]' = {}
        self._group_in: 'dict[Group, list[Connection]]' = {}
    
    def append(self, conn: Connection):
        super().append(conn)
        
        group_ins = self._group_in.get(conn.port_in.group)
        if group_ins is None:
            group_ins = self._group_in[conn.port_in.group] = \
                list[Connection]()
                
        group_outs = self._group_out.get(conn.port_out.group)
        if group_outs is None:
            group_outs = self._group_out[conn.port_out.group] = \
                list[Connection]()

        group_ins.append(conn)
        group_outs.append(conn)
        
    def remove(self, conn: Connection):
        super().remove(conn)
        self._group_in[conn.port_in.group].remove(conn)
        self._group_out[conn.port_out.group].remove(conn)

    def from_group(self, group: 'Group') -> Iterator[Connection]:
        group_out = self._group_out.get(group)
        if group_out is None:
            return
        
        for conn in group_out:
            yield conn
            
    def to_group(self, group: 'Group') -> Iterator[Connection]:
        group_in = self._group_in.get(group)
        if group_in is None:
            return
        
        for conn in group_in:
            yield conn
            
    def with_group(self, group: 'Group') -> Iterator[Connection]:
        already = set[Connection]()
        group_out = self._group_out.get(group)
        if group_out is not None:
            for conn in group_out:
                already.add(conn)
                yield conn
        group_in = self._group_in.get(group)
        if group_in is not None:
            for conn in group_in:
                if conn not in already:
                    yield conn