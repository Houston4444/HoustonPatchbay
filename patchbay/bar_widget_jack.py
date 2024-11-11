from typing import TYPE_CHECKING

from qtpy.QtCore import QTimer
from qtpy.QtWidgets import QWidget

from .base_elements import ToolDisplayed

from .ui.jack_bar import Ui_Form as JackUiForm

if TYPE_CHECKING:
    from patchbay_manager import PatchbayManager


class BarWidgetJack(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.ui = JackUiForm()
        self.ui.setupUi(self)
        
        self.mng: 'PatchbayManager' = None
        
        self._waiting_buffer_change = False
        self._buffer_change_from_osc = False

        self.ui.pushButtonXruns.clicked.connect(
            self.reset_xruns)
        self.ui.comboBoxBuffer.currentIndexChanged.connect(
            self.change_buffersize)

        self._buffer_sizes = [16, 32, 64, 128, 256, 512,
                              1024, 2048, 4096, 8192]

        for size in self._buffer_sizes:
            self.ui.comboBoxBuffer.addItem(str(size), size)

        self._samplerate = 48000
        self._current_buffer_size = self.ui.comboBoxBuffer.currentData()
        self._xruns_counter = 0
        
        self._jack_running = True
        self.ui.labelJackNotStarted.setVisible(False)
        
    def _set_latency(self, buffer_size=None, samplerate=None):
        if buffer_size is None:
            buffer_size = self._current_buffer_size
        if samplerate is None:
            samplerate = self._samplerate

        latency = 1000 * buffer_size / samplerate
        self.ui.labelLatency.setText("%.2f ms" % latency)

    def set_samplerate(self, samplerate: int):
        self._samplerate = samplerate
        str_sr = str(samplerate)
        str_samplerate = str_sr
        
        # separate the three last digits from begin with a space
        # 48000 -> 48 000
        if len(str_sr) > 3:
            str_samplerate = str_sr[:-3] + ' ' + str_sr[-3:]
        str_samplerate += ' Hz'

        self.ui.labelSamplerate.setText(str_samplerate)
        self._set_latency(samplerate=samplerate)

    def set_buffer_size(self, buffer_size: int):
        self._waiting_buffer_change = False
        self.ui.comboBoxBuffer.setEnabled(True)

        if self.ui.comboBoxBuffer.currentData() == buffer_size:
            self._set_latency(buffer_size=buffer_size)
            return

        self._buffer_change_from_osc = True

        index = self.ui.comboBoxBuffer.findData(buffer_size)

        # manage exotic buffer sizes
        # findData returns -1 if buffer_size is not in combo box values
        if index < 0:
            index = 0
            for size in self._buffer_sizes:
                if size > buffer_size:
                    break
                index += 1

            self._buffer_sizes.insert(index, buffer_size)
            self.ui.comboBoxBuffer.insertItem(
                index, str(buffer_size), buffer_size)

        self.ui.comboBoxBuffer.setCurrentIndex(index)
        self._current_buffer_size = buffer_size
        self._set_latency(buffer_size=buffer_size)

    def update_xruns(self):
        self.ui.pushButtonXruns.setText("%i Xruns " % self._xruns_counter)

    def add_xrun(self):
        self._xruns_counter += 1
        self.update_xruns()

    def reset_xruns(self):
        self._xruns_counter = 0
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
        
        if self.mng is not None:
            self.mng.change_buffersize(self.ui.comboBoxBuffer.currentData())
        # self.buffer_size_change_order.emit(
        #     self.ui.comboBoxBuffer.currentData())

        # only in the case no set_buffer_size message come back
        QTimer.singleShot(10000, self._re_enable_buffer_combobox)

    def _re_enable_buffer_combobox(self):
        if self._waiting_buffer_change:
            self.set_buffer_size(self._current_buffer_size)

    def set_patchbay_manager(self, mng: 'PatchbayManager'):
        self.mng = mng

    def set_jack_running(self, yesno: bool, use_alsa_midi=False):
        self._jack_running = yesno
        
        self.ui.labelJackNotStarted.setVisible(not yesno)
        if not yesno:
            self.ui.labelBuffer.setVisible(False)
            self.ui.comboBoxBuffer.setVisible(False)
            self.ui.labelSamplerate.setVisible(False)
            self.ui.labelPipeSeparator.setVisible(False)
            self.ui.labelLatency.setVisible(False)
            self.ui.pushButtonXruns.setVisible(False)
            self.ui.progressBarDsp.setVisible(False)
            
    def change_tools_displayed(self, tools_displayed: ToolDisplayed):
        if not self._jack_running:
            self.set_jack_running(False)
            return

        SR_AND_LT = ToolDisplayed.SAMPLERATE | ToolDisplayed.LATENCY
    
        self.ui.labelBuffer.setVisible(
            bool(tools_displayed & ToolDisplayed.BUFFER_SIZE))
        self.ui.comboBoxBuffer.setVisible(
            bool(tools_displayed & ToolDisplayed.BUFFER_SIZE))
        self.ui.labelSamplerate.setVisible(
            bool(tools_displayed & ToolDisplayed.SAMPLERATE))
        self.ui.labelPipeSeparator.setVisible(
            bool(tools_displayed & SR_AND_LT == SR_AND_LT))
        self.ui.labelLatency.setVisible(
            bool(tools_displayed & ToolDisplayed.LATENCY))
        self.ui.pushButtonXruns.setVisible(
            bool(tools_displayed & ToolDisplayed.XRUNS))
        self.ui.progressBarDsp.setVisible(
            bool(tools_displayed & ToolDisplayed.DSP_LOAD))