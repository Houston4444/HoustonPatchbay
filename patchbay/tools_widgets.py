
import os
from typing import TYPE_CHECKING

from PyQt5.QtCore import pyqtSignal, QTimer
from PyQt5.QtGui import QIcon, QPalette
from PyQt5.QtWidgets import QWidget, QMenu, QApplication, QDialog

from .patchcanvas import patchcanvas
from .base_elements import JackPortFlag, Port, PortType

from .ui.canvas_port_info import Ui_CanvasPortInfo as PortInfoUiDialog
from .ui.patchbay_tools import Ui_Form as PatchbayToolsUiForm

if TYPE_CHECKING:
    from .patchbay_manager import PatchbayManager

_translate = QApplication.translate

def is_dark_theme(widget: QWidget) -> bool:
    return bool(
        widget.palette().brush(
            QPalette.Active, QPalette.WindowText).color().lightness()
        > 128)

def get_code_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.realpath(__file__))))


class PatchbayToolsWidget(QWidget):
    buffer_size_change_order = pyqtSignal(int)

    def __init__(self):
        QWidget.__init__(self)
        self.ui = PatchbayToolsUiForm()
        self.ui.setupUi(self)

        if is_dark_theme(self):
            self.ui.sliderZoom.setStyleSheet(
                self.ui.sliderZoom.styleSheet().replace('/breeze/', '/breeze-dark/'))

        self._waiting_buffer_change = False
        self._buffer_change_from_osc = False

        self.ui.sliderZoom.valueChanged.connect(self.set_zoom)

        self.ui.pushButtonXruns.clicked.connect(
            self.reset_xruns)
        self.ui.comboBoxBuffer.currentIndexChanged.connect(
            self.change_buffersize)

        self.buffer_sizes = [16, 32, 64, 128, 256, 512,
                             1024, 2048, 4096, 8192]

        for size in self.buffer_sizes:
            self.ui.comboBoxBuffer.addItem(str(size), size)

        self.current_buffer_size = self.ui.comboBoxBuffer.currentData()
        self.xruns_counter = 0

    def zoom_changed_from_canvas(self, ratio):
        self.ui.sliderZoom.set_percent(ratio * 100)

    def set_zoom(self, value):
        percent = self.ui.sliderZoom.zoom_percent()
        patchcanvas.canvas.scene.zoom_ratio(percent)

    def set_samplerate(self, samplerate: int):
        str_sr = str(samplerate)
        str_samplerate = str_sr
        
        # separate the three last digits from begin with a space
        # 48000 -> 48 000
        if len(str_sr) > 3:
            str_samplerate = str_sr[:-3] + ' ' + str_sr[-3:]

        self.ui.labelSamplerate.setText(str_samplerate)

    def set_buffer_size(self, buffer_size: int):
        self._waiting_buffer_change = False
        self.ui.comboBoxBuffer.setEnabled(True)

        if self.ui.comboBoxBuffer.currentData() == buffer_size:
            return

        self._buffer_change_from_osc = True

        index = self.ui.comboBoxBuffer.findData(buffer_size)

        # manage exotic buffer sizes
        # findData returns -1 if buffer_size is not in combo box values
        if index < 0:
            index = 0
            for size in self.buffer_sizes:
                if size > buffer_size:
                    break
                index += 1

            self.buffer_sizes.insert(index, buffer_size)
            self.ui.comboBoxBuffer.insertItem(
                index, str(buffer_size), buffer_size)

        self.ui.comboBoxBuffer.setCurrentIndex(index)
        self.current_buffer_size = buffer_size

    def update_xruns(self):
        self.ui.pushButtonXruns.setText("%i Xruns" % self.xruns_counter)

    def add_xrun(self):
        self.xruns_counter += 1
        self.update_xruns()

    def reset_xruns(self):
        self.xruns_counter = 0
        self.update_xruns()

    def set_dsp_load(self, dsp_load: int):
        self.ui.progressBarDsp.setValue(dsp_load)

    def change_buffersize(self, index: int):
        # prevent loop of buffer size change
        if self._buffer_change_from_osc:
            # change_buffersize not called by user
            # but ensure next time it could be
            self._buffer_change_from_osc = False
            return

        self.ui.comboBoxBuffer.setEnabled(False)
        self._waiting_buffer_change = True
        self.buffer_size_change_order.emit(
            self.ui.comboBoxBuffer.currentData())

        # only in the case no set_buffer_size message come back
        QTimer.singleShot(10000, self._re_enable_buffer_combobox)

    def _re_enable_buffer_combobox(self):
        if self._waiting_buffer_change:
            self.set_buffer_size(self.current_buffer_size)

    def set_jack_running(self, yesno: bool):
        for widget in (
                self.ui.sliderZoom,
                self.ui.labelSamplerate,
                self.ui.labelSamplerateUnits,
                self.ui.labelBuffer,
                self.ui.comboBoxBuffer,
                self.ui.pushButtonXruns,
                self.ui.progressBarDsp,
                self.ui.lineSep1,
                self.ui.lineSep2,
                self.ui.lineSep3):
            widget.setVisible(yesno)

        self.ui.labelJackNotStarted.setVisible(not yesno)
        if yesno:
            patchcanvas.canvas.scene.scale_changed.connect(
                self.zoom_changed_from_canvas)
            self.ui.sliderZoom.zoom_fit_asked.connect(
                patchcanvas.canvas.scene.zoom_fit)


class CanvasPortInfoDialog(QDialog):
    def __init__(self, parent):
        QDialog.__init__(self, parent)
        self.ui = PortInfoUiDialog()
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

        self.ui.lineEditFullPortName.setText(self._port.full_name)
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

