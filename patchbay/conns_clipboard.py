
from typing import TYPE_CHECKING

from .base_elements import PortType, PortMode, Port
from .patchcanvas import canvas
from .patchcanvas.init_values import CallbackAct
if TYPE_CHECKING:
    from patchbay_manager import PatchbayManager

class ConnClipboard:
    all_ports = list[tuple[Port, list[Port]]]()
    cut = False
    
    def __init__(self, mng: 'PatchbayManager'):
        self._mng = mng
    
    def _write(self, ports: list[Port]):
        self.all_ports.clear()
        
        for port in ports:
            if port.mode() is PortMode.OUTPUT:
                self.all_ports.append(
                    (port, 
                     [c.port_in for c in self._mng.connections
                      if c.port_out is port and c.in_canvas]))

            elif port.mode() is PortMode.INPUT:
                self.all_ports.append(
                    (port, 
                     [c.port_out for c in self._mng.connections
                      if c.port_in is port and c.in_canvas]))

    def is_compatible(self, ports: list[Port]) -> bool:
        if not (ports and self.all_ports):
            return False
        
        port = ports[0]
        orig_port = self.all_ports[0][0]
        
        if ports == [ap[0] for ap in self.all_ports]:
            # ports are incompatibles with themselves
            return False

        return orig_port.type is port.type and orig_port.mode() is port.mode()    

    def cb_cut(self, ports: list[Port]):
        self._write(ports)
        self.cut = True
        
    def cb_copy(self, ports: list[Port]):
        self._write(ports)
        self.cut = False
    
    def cb_paste(self, ports: list[Port]):
        if not self.is_compatible(ports):
            return
        
        if self.cut:
            for orig_port, conn_ports in self.all_ports:
                if orig_port.mode() is PortMode.OUTPUT:
                    for conn in self._mng.connections:
                        if (conn.port_out is orig_port
                                and conn.port_in in conn_ports):
                            canvas.callback(CallbackAct.PORTS_DISCONNECT,
                                            conn.connection_id)
                elif orig_port.mode() is PortMode.OUTPUT:
                    for conn in self._mng.connections:
                        if (conn.port_in is orig_port
                                and conn.port_out in conn_ports):
                            canvas.callback(CallbackAct.PORTS_DISCONNECT,
                                            conn.connection_id)
            self.cut = False
        
        for i in range(len(ports)):
            port = ports[i]
            if not port.in_canvas:
                continue
            
            for j in range(len(self.all_ports)):
                if i % len(self.all_ports) != j % len(ports):
                    continue
                
                orig_port, conn_ports = self.all_ports[j]
                
                if port.mode() is PortMode.OUTPUT:
                    for conn_port in conn_ports:
                        if not conn_port.in_canvas:
                            continue

                        if conn_port not in [c.port_in for c in self._mng.connections
                                             if c.port_out is port]:
                            canvas.callback(
                                CallbackAct.PORTS_CONNECT,
                                port.group_id, port.port_id,
                                conn_port.group_id, conn_port.port_id)

                elif port.mode() is PortMode.INPUT:
                    for conn_port in conn_ports:
                        if not conn_port.in_canvas:
                            continue
                        
                        if conn_port not in [c.port_out for c in self._mng.connections
                                             if c.port_in is port]:
                            canvas.callback(
                                CallbackAct.PORTS_CONNECT,
                                conn_port.group_id, conn_port.port_id,
                                port.group_id, port.port_id)
                
                