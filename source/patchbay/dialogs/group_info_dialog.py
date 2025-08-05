from qtpy.QtWidgets import QDialog, QTableWidgetItem
from qtpy.QtGui import QIcon
from qtpy.QtCore import Qt

from patshared.base_enums import BoxType, PortType

from ..bases.group import Group
from ..patchcanvas.icon_widget import get_app_icon

from ..ui.canvas_group_info import Ui_CanvasGroupInfo


class GroupInfoDialog(QDialog):
    def __init__(self, parent, group: Group):
        super().__init__(parent)
        self.ui = Ui_CanvasGroupInfo()
        self.ui.setupUi(self)
        self.group = group
        
        self._fill_contents()
        self.ui.toolButtonRefresh.clicked.connect(self._fill_contents)
        self.ui.tableWidgetMetadatas.horizontalHeader().\
            setStretchLastSection(True)
        self.ui.tableWidgetMetadatas.cellChanged.connect(self._cell_changed)
        self._populating = False
    
    def show(self):
        super().show()
        self.adjustSize()
    
    def _fill_contents(self):
        if self.group.cnv_box_type in (BoxType.HARDWARE, BoxType.MONITOR):
            icon = QIcon()
            if self.group.cnv_box_type is BoxType.HARDWARE:
                if self.group.cnv_icon_name == 'a2j':
                    icon.addFile(':scalable/DIN-5.svg')
                else:
                    icon.addFile(':scalable/pb_hardware.svg')
            else:
                icon.addFile(':scalable/audio-volume-medium.svg')
            self.ui.toolButtonGroupIcon.setIcon(icon)
        else:
            app_icon = get_app_icon(self.group.cnv_icon_name)
            self.ui.toolButtonGroupIcon.setVisible(not app_icon.isNull())
            self.ui.toolButtonGroupIcon.setIcon(app_icon)
        self.ui.labelCnvName.setText(f'<b>{self.group.cnv_name}</b>')

        self.ui.lineEditClientName.setText(self.group.name)
        self.ui.lineEditUuid.setText(str(self.group.uuid))
        
        self.ui.lineEditPrettyName.setText(self.group.custom_name)
        self.ui.lineEditGracefulName.setText(self.group.graceful_name)
        display_graceful = self.group.graceful_name != self.group.name
        for widget in (self.ui.labelGracefulName,
                       self.ui.labelColonGracefulName,
                       self.ui.lineEditGracefulName):
            widget.setVisible(display_graceful)
        
        mng = self.group.manager
        
        # fill ALSA client id
        alsa_client_ids = set[str]()
        
        for port in self.group.ports:
            if port.type is PortType.MIDI_ALSA:
                alsa_client_ids.add(str(port.alsa_client_id))
        
        self.ui.labelAlsaClientIdNum.setText(' '.join(alsa_client_ids))
        has_alsa = bool(alsa_client_ids)
        self.ui.labelAlsaClientId.setVisible(has_alsa)
        self.ui.labelColonAlsaClientId.setVisible(has_alsa)
        self.ui.labelAlsaClientIdNum.setVisible(has_alsa)
        
        # fill JACK metadatas
        self._populating = True

        if self.group.uuid:
            uuid_dict = mng.jack_metadatas.get(self.group.uuid)
            if uuid_dict is not None:
                self.ui.tableWidgetMetadatas.setRowCount(len(uuid_dict))
                row = 0
                
                for key, value in uuid_dict.items():                    
                    key_item = QTableWidgetItem(key)
                    value_item = QTableWidgetItem(value)
                    key_item.setData(Qt.ItemDataRole.UserRole, key)
                    value_item.setData(Qt.ItemDataRole.UserRole, value)
                    self.ui.tableWidgetMetadatas.setItem(row, 0, key_item)
                    self.ui.tableWidgetMetadatas.setItem(row, 1, value_item)
                    row += 1
                
            self.ui.tableWidgetMetadatas.resizeColumnToContents(0)
        
        self._populating = False
        
        show_jack = bool(self.group.uuid)
        self.ui.labelJackUuid.setVisible(show_jack)
        self.ui.labelColonJackUuid.setVisible(show_jack)
        self.ui.lineEditUuid.setVisible(show_jack)
        self.ui.line.setVisible(show_jack)
        self.ui.labelJackMetadatas.setVisible(show_jack)
        self.ui.tableWidgetMetadatas.setVisible(show_jack)
        self.ui.verticalWidget.setVisible(not show_jack)
    
    def _cell_changed(self, row: int, column: int):
        if self._populating:
            return

        item = self.ui.tableWidgetMetadatas.item(row, column)
        item.setText(item.data(Qt.ItemDataRole.UserRole))

        
        
        