from qtpy.QtGui import QShowEvent, QFontMetrics, QFont
from qtpy.QtWidgets import QApplication, QDialog, QTableWidgetItem
from qtpy.QtCore import Qt

from patshared import PortType
from .base_elements import JackPortFlag
from .base_port import Port
from .ui.canvas_port_info import Ui_CanvasPortInfo

_translate = QApplication.translate

class CanvasPortInfoDialog(QDialog):
    def __init__(self, parent):
        QDialog.__init__(self, parent)
        self.ui = Ui_CanvasPortInfo()
        self.ui.setupUi(self)

        self._port = None
        
        self._show_alsa_props(False)

        self._populating = False
        self.ui.tableWidgetMetadatas.horizontalHeader().\
            setStretchLastSection(True)
        self.ui.toolButtonRefresh.clicked.connect(
            self.update_contents)

    def _show_alsa_props(self, yesno: bool):
        for widget in (self.ui.labelAlsaClientId, 
                       self.ui.labelColonAlsaClientId,
                       self.ui.labelAlsaClientIdNum,
                       self.ui.labelAlsaPortId,
                       self.ui.labelColonAlsaPortId,
                       self.ui.labelAlsaPortIdNum):
            widget.setVisible(yesno)

    def set_port(self, port: Port):
        self._port = port
        self.update_contents()

    def update_contents(self):
        if self._port is None:
            return

        if self._port.type is PortType.AUDIO_JACK:
            port_type_str = _translate('patchbay', "Audio")
        elif self._port.type is PortType.MIDI_JACK:
            port_type_str = _translate('patchbay', "MIDI")
        elif self._port.type is PortType.MIDI_ALSA:
            port_type_str = _translate('patchbay', "ALSA")
            self._show_alsa_props(True)
        else:
            port_type_str = _translate('patchbay', 'NULL')

        flags_list = list[str]()

        dict_flag_str = {
            JackPortFlag.IS_INPUT: _translate('patchbay', 'Input'),
            JackPortFlag.IS_OUTPUT: _translate('patchbay', 'Output'),
            JackPortFlag.IS_PHYSICAL: _translate('patchbay', 'Physical'),
            JackPortFlag.CAN_MONITOR: _translate('patchbay', 'Monitor'),
            JackPortFlag.IS_TERMINAL: _translate('patchbay', 'Terminal'),
            JackPortFlag.IS_CONTROL_VOLTAGE:
                _translate('patchbay', 'Control Voltage')}

        for key in dict_flag_str.keys():
            if self._port.flags & key:
                flags_list.append(dict_flag_str[key])

        port_flags_str = ' | '.join(flags_list)

        port_full_name = self._port.full_name
        if self._port.type is PortType.MIDI_ALSA:
            splitted_names = port_full_name.split(':')
            
            port_full_name = ':'.join(splitted_names[4:])
            self.ui.labelAlsaClientIdNum.setText(splitted_names[2])
            self.ui.labelAlsaPortIdNum.setText(splitted_names[3])
            self.ui.labelJackUuid.setVisible(False)
            self.ui.labelColonJackUuid.setVisible(False)
            self.ui.lineEditUuid.setVisible(False)
            
        self.ui.lineEditFullPortName.setText(port_full_name)
        self.ui.labelGracefulNameValue.setText(self._port.graceful_name)
        self.ui.labelInternalPrettyNameValue.setText(
            self._port.manager.pretty_names.pretty_port(self._port.full_name))
        self.ui.lineEditUuid.setText(str(self._port.uuid))
        self.ui.labelPortType.setText(port_type_str)
        self.ui.labelPortFlags.setText(port_flags_str)

        if self._port.uuid:
            uuid_dict = self._port.manager.jack_metadatas.get(self._port.uuid)
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
        
    def show(self):
        super().show()
        self.adjustSize()
        
    def _cell_changed(self, row: int, column: int):
        if self._populating:
            return

        item = self.ui.tableWidgetMetadatas.item(row, column)
        item.setText(item.data(Qt.ItemDataRole.UserRole))
