from qtpy.QtGui import QShowEvent, QFontMetrics, QFont
from qtpy.QtWidgets import QApplication, QDialog

from .patchcanvas.patshared import PortType
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
            JackPortFlag.IS_CONTROL_VOLTAGE: _translate('patchbay', 'Control Voltage')}

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
    
    def showEvent(self, event: QShowEvent) -> None:
        self.resize(0, 0)
        self.ui.lineEditFullPortName.setMinimumWidth(
            QFontMetrics(QFont()).width(
            self.ui.lineEditFullPortName.text()) + 20
        )
        super().showEvent(event)