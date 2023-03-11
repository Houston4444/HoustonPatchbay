
from PyQt5.QtWidgets import QApplication, QDialog

from .base_elements import Port, PortType, JackPortFlag
from .ui.canvas_port_info import Ui_CanvasPortInfo

_translate = QApplication.translate

class CanvasPortInfoDialog(QDialog):
    def __init__(self, parent):
        QDialog.__init__(self, parent)
        self.ui = Ui_CanvasPortInfo()
        self.ui.setupUi(self)

        self._port = None
        self.ui.toolButtonRefresh.clicked.connect(
            self.update_contents)

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
        else:
            port_type_str = _translate('patchbay', 'NULL')

        flags_list = list[str]()

        dict_flag_str = {
            JackPortFlag.IS_INPUT: _translate('patchbay', 'Input'),
            JackPortFlag.IS_OUTPUT: _translate('patchbay', 'Output'),
            JackPortFlag.IS_PHYSICAL: _translate('patchbay', 'Physical'),
            JackPortFlag.CAN_MONITOR: _translate('patchbay', 'Monitor'),
            JackPortFlag.IS_TERMINAL: _translate('patchbay', 'Terminal'),
            JackPortFlag.IS_CONTROL_VOLTAGE: _translate('patchbay', 'Control Voltage')}

        for key in dict_flag_str.keys():
            if self._port.flags & key:
                flags_list.append(dict_flag_str[key])

        port_flags_str = ' | '.join(flags_list)

        port_full_name = self._port.full_name
        if self._port.type is PortType.MIDI_ALSA:
            port_full_name = port_full_name[1:].partition(':')[2]
            self.ui.labelJackUuid.setVisible(False)
            self.ui.labelColonJackUuid.setVisible(False)
            self.ui.lineEditUuid.setVisible(False)
            
        self.ui.lineEditFullPortName.setText(port_full_name)
        self.ui.lineEditUuid.setText(str(self._port.uuid))
        self.ui.labelPortType.setText(port_type_str)
        self.ui.labelPortFlags.setText(port_flags_str)
        self.ui.labelPrettyName.setText(self._port.pretty_name)
        self.ui.labelPortOrder.setText(str(self._port.order))
        self.ui.labelPortGroup.setText(self._port.mdata_portgroup)

        self.ui.groupBoxMetadatas.setVisible(bool(
            self._port.pretty_name
            or self._port.order is not None
            or self._port.mdata_portgroup))