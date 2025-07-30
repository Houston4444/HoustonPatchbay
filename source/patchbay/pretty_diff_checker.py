
from typing import TYPE_CHECKING
from patshared import PrettyDiff

if TYPE_CHECKING:
    from patchbay_manager import PatchbayManager
# from port_data import PortDataList


class PrettyDiffChecker:
    def __init__(self, manager: 'PatchbayManager'):
        self.mng = manager
        self.metadatas = self.mng.jack_metadatas
        self.pretty_names = self.mng.pretty_names
        self.client_name_uuids = self.mng.client_uuids
        
        self.clients_diff = dict[int, PrettyDiff]()
        self.ports_diff = dict[int, PrettyDiff]()
        self.pretty_diff = PrettyDiff.NO_DIFF
        self.full_update()
    
    def uuid_change(self, uuid: int):
        change_diff_old = PrettyDiff.NO_DIFF
        change_diff_new = PrettyDiff.NO_DIFF
        glob_diff_old = self.pretty_diff
        glob_diff_new = PrettyDiff.NO_DIFF

        if uuid in self.clients_diff:
            change_diff_old = self.clients_diff[uuid]

            for client_name, client_uuid in self.client_name_uuids.items():
                if client_uuid != uuid:
                    continue

                self.clients_diff[uuid] = self._get_diff(
                    self.pretty_names.pretty_group(client_name),
                    self.metadatas.pretty_name(uuid))
                change_diff_new = self.clients_diff[uuid]
                break
        
        elif uuid in self.ports_diff:
            change_diff_old = self.ports_diff[uuid]
            port = self.mng.get_port_from_uuid(uuid)

            if port is not None:
                self.ports_diff[uuid] = self._get_diff(
                    self.pretty_names.pretty_port(port.full_name),
                    self.metadatas.pretty_name(uuid))
                change_diff_new = self.ports_diff[uuid]
        
        else:
            port = self.mng.get_port_from_uuid(uuid)
            if port is None:
                for client_name, client_uuid \
                        in self.client_name_uuids.items():
                    if client_uuid != uuid:
                        continue
                    
                    self.clients_diff[uuid] = self._get_diff(
                        self.pretty_names.pretty_group(client_name),
                        self.metadatas.pretty_name(uuid))
                    change_diff_new = self.clients_diff[uuid]
                    break
            else:
                self.ports_diff[uuid] = self._get_diff(
                    self.pretty_names.pretty_port(port.full_name),
                    self.metadatas.pretty_name(uuid))
                change_diff_new = self.ports_diff[uuid]
        
        # In many cases, no need to reevaluate all pretty names change states
        # to know the diff state
        match glob_diff_old:
            case PrettyDiff.NO_DIFF:
                glob_diff_new = change_diff_new
            case PrettyDiff.NON_BOTH:
                if change_diff_old is PrettyDiff.NO_DIFF:
                    glob_diff_new = PrettyDiff.NON_BOTH
                else:
                    glob_diff_new = self.get_glob_diff()
            case _:
                if glob_diff_old in change_diff_old:
                    glob_diff_new = self.get_glob_diff()
                else:
                    glob_diff_new = glob_diff_old | change_diff_new
        
        if glob_diff_new is not glob_diff_old:
            if self.mng.options_dialog is not None:
                self.mng.options_dialog.change_pretty_diff(glob_diff_new)

        self.pretty_diff = glob_diff_new
    
    def client_pretty_name_changed(self, client_name: str):
        client_uuid = self.client_name_uuids.get(client_name)
        if client_uuid is None:
            return

        self.uuid_change(client_uuid)
        
    def port_pretty_name_changed(self, port_name: str):
        port = self.mng.get_port_from_name(port_name)
        if port is None or not port.type.is_jack:
            return
        
        self.uuid_change(port.uuid)
    
    def _get_diff(self, pretty_name: str, jack_pretty_name: str):
        if pretty_name == jack_pretty_name:
            return PrettyDiff.NO_DIFF
        
        if pretty_name and jack_pretty_name:
            return PrettyDiff.NON_BOTH
        
        if pretty_name:
            return PrettyDiff.NON_EXPORTED
        return PrettyDiff.NON_IMPORTED
    
    def full_update(self):
        self.clients_diff.clear()
        self.ports_diff.clear()

        for client_name, client_uuid in self.client_name_uuids.items():
            self.clients_diff[client_uuid] = self._get_diff(
                self.pretty_names.pretty_group(client_name),
                self.metadatas.pretty_name(client_uuid))
        
        for group in self.mng.groups:
            for port in group.ports:
                if not port.type.is_jack:
                    continue
                
                self.ports_diff[port.uuid] = self._get_diff(
                    self.pretty_names.pretty_port(port.full_name),
                    self.metadatas.pretty_name(port.uuid))
        
        self.pretty_diff = self.get_glob_diff()
        if self.mng.options_dialog:
            self.mng.options_dialog.change_pretty_diff(self.pretty_diff)
        self.print_diffs()

    def print_diffs(self):
        print('knilou', self.pretty_diff)
        for uuid, diff in self.clients_diff.items():
            if diff is not PrettyDiff.NO_DIFF:
                print('cdiff', uuid, diff)
        
        for uuid, diff in self.ports_diff.items():
            if diff is not PrettyDiff.NO_DIFF:
                print('pdiff', uuid, diff)

    def get_glob_diff(self) -> PrettyDiff:
        glob_diff = PrettyDiff.NO_DIFF
        for pretty_diff in self.clients_diff.values():
            glob_diff |= pretty_diff
            if glob_diff is PrettyDiff.NON_BOTH:
                return glob_diff
            
        for pretty_diff in self.ports_diff.values():
            glob_diff |= pretty_diff
            if glob_diff is PrettyDiff.NON_BOTH:
                return glob_diff
        return glob_diff

    def metadatas_cleared(self):
        if self.pretty_diff in (PrettyDiff.NO_DIFF, PrettyDiff.NON_EXPORTED):
            return

        self.full_update()    