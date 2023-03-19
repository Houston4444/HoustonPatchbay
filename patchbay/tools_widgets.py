
import time
from typing import TYPE_CHECKING
from PyQt5.QtCore import pyqtSignal, QTimer, pyqtSlot
from PyQt5.QtGui import QPalette, QIcon, QColor, QKeySequence
from PyQt5.QtWidgets import QWidget


from .ui.patchbay_tools import Ui_Form as PatchbayToolsUiForm
from .base_elements import (
    ToolDisplayed, TransportPosition, TransportViewMode)

if TYPE_CHECKING:
    from .patchbay_manager import PatchbayManager


def is_dark_theme(widget: QWidget) -> bool:
    return bool(
        widget.palette().brush(
            QPalette.Active, QPalette.WindowText).color().lightness()
        > 128)


class PatchbayToolsWidget(QWidget):
    buffer_size_change_order = pyqtSignal(int)

    def __init__(self):
        QWidget.__init__(self)
        self.ui = PatchbayToolsUiForm()
        self.ui.setupUi(self)

        self.ui.toolButtonPlayPause.clicked.connect(self._play_clicked)
        self.ui.toolButtonStop.clicked.connect(self._stop_clicked)
        self.ui.toolButtonRewind.clicked.connect(self._rewind_clicked)
        self.ui.toolButtonForward.clicked.connect(self._forward_clicked)
        self.ui.labelTime.transport_view_changed.connect(self._transport_view_changed)
        
        self._jack_running = True
        
        self._patchbay_mng: 'PatchbayManager' = None
        self._last_transport_pos = TransportPosition(0, False, False, 0, 0, 0, 120.00)
        
        self.ui.toolButtonPlayPause.setShortcut(QKeySequence(' '))
        
        self._fw_clicked_last_time = 0
        self._fw_click_started_at = 0
        self._bw_clicked_last_time = 0
        self._bw_click_started_at = 0
        
        dark = is_dark_theme(self)

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
        
        self._tools_displayed = ToolDisplayed.ALL
        
        # set theme
        app_bg = self.ui.labelTempo.palette().brush(
            QPalette.Active, QPalette.Background).color()
        
        scheme = 'dark' if dark else 'light'
        self._icon_play = QIcon(f':/transport/{scheme}/media-playback-start.svg')
        self._icon_pause = QIcon(f':/transport/{scheme}/media-playback-pause.svg')
        
        self.ui.toolButtonRewind.setIcon(
            QIcon(f':/transport/{scheme}/media-seek-backward.svg'))
        self.ui.toolButtonForward.setIcon(
            QIcon(f':/transport/{scheme}/media-seek-forward.svg'))
        self.ui.toolButtonPlayPause.setIcon(self._icon_play)
        self.ui.toolButtonStop.setIcon(
            QIcon(f':/transport/{scheme}/media-playback-stop.svg'))

        bg = QColor(app_bg)
        more_gray = 20 if dark else -30
        
        bg.setRed(max(min(app_bg.red() + more_gray, 255), 0))
        bg.setGreen(max(min(app_bg.green() + more_gray, 255), 0))
        bg.setBlue(max(min(app_bg.blue() + more_gray, 255), 0))
        background = bg.name()

        round_side = 'left'
        for button in (self.ui.toolButtonRewind, self.ui.toolButtonPlayPause,
                       self.ui.toolButtonForward, self.ui.toolButtonStop):
            if button is self.ui.toolButtonForward:
                round_side = "right"

            button.setStyleSheet(
                f"QToolButton{{background:{background}; border:none;"
                f"border-top-{round_side}-radius:4px;"
                f"border-bottom-{round_side}-radius:4px}}")

        count_bg = self.palette().base().color().name()

        self.ui.labelTime.setStyleSheet(
            f"QLabel{{background:{count_bg}; border: 2px solid {background}}}")
    
    def _play_clicked(self, play: bool):
        if self._patchbay_mng is not None:
            self._patchbay_mng.transport_play_pause(play)
            
    def _stop_clicked(self):
        if self._patchbay_mng is not None:
            self._patchbay_mng.transport_stop()

    def _rewind_clicked(self):
        if self._patchbay_mng is not None:
            now = time.time()
            move = 1.0 * self._samplerate
            
            if now - self._bw_clicked_last_time < 0.400:
                move = (1.0 + (now - self._bw_click_started_at) ** 1.5) * self._samplerate
            else:
                self._bw_click_started_at = now

            self._patchbay_mng.transport_relocate(
                max(0, int(self._last_transport_pos.frame - move)))
    
            self._bw_clicked_last_time = now
        
    def _forward_clicked(self):
        if self._patchbay_mng is not None:
            now = time.time()
            move = 1.0 * self._samplerate
            
            if now - self._fw_clicked_last_time < 0.400:
                move = (1.0 + (now - self._fw_click_started_at) ** 1.5) * self._samplerate
            else:
                self._fw_click_started_at = now

            self._patchbay_mng.transport_relocate(
                int(self._last_transport_pos.frame + move))
    
            self._fw_clicked_last_time = now

    def set_patchbay_manager(self, mng: 'PatchbayManager'):
        self._patchbay_mng = mng
        self.ui.frameTypeFilter.set_patchbay_manager(mng)
        self.ui.sliderZoom.set_patchbay_manager(mng)
    
    def refresh_transport(self, transport_pos: TransportPosition):
        self.ui.toolButtonPlayPause.setChecked(transport_pos.rolling)
        
        if transport_pos.rolling:
            self.ui.toolButtonPlayPause.setIcon(self._icon_pause)
        else:
            self.ui.toolButtonPlayPause.setIcon(self._icon_play)
            
        if self.ui.labelTime.transport_view_mode is not TransportViewMode.FRAMES:
            # switch the view mode in case beats info appears/disappears 
            if transport_pos.valid_bbt and not self._last_transport_pos.valid_bbt:
                self.ui.labelTime.transport_view_mode = TransportViewMode.BEAT_BAR_TICK
            elif not transport_pos.valid_bbt and self._last_transport_pos.valid_bbt:
                self.ui.labelTime.transport_view_mode = TransportViewMode.HOURS_MINUTES_SECONDS
        
        if (self.ui.labelTime.transport_view_mode
                is TransportViewMode.HOURS_MINUTES_SECONDS):
            # if the transport time is during the first second
            # but not at 0, we display something else to show
            # that transport is rolling after press play.
            # If it is not rolling, it shows that transport is not
            # exactly at start.
            if 0 < transport_pos.frame < self._samplerate / 2:
                self.ui.labelTime.setText("00:00:0_")
            elif 0 < transport_pos.frame < self._samplerate:
                self.ui.labelTime.setText("00:00:0-")
            else:
                time = transport_pos.frame // self._samplerate
                secs = time % 60
                mins = (time / 60) % 60
                hrs  = (time / 3600) % 60
                self.ui.labelTime.setText("%02i:%02i:%02i" % (hrs, mins, secs))
            
        elif (self.ui.labelTime.transport_view_mode
                is TransportViewMode.FRAMES):
            frame1 =  transport_pos.frame % 1000
            frame2 = int(transport_pos.frame / 1000) % 1000
            frame3 = int(transport_pos.frame / 1000000) % 1000
            
            self.ui.labelTime.setText("%03i'%03i'%03i" % (frame3, frame2, frame1))
            
        elif (self.ui.labelTime.transport_view_mode
                is TransportViewMode.BEAT_BAR_TICK):
            if transport_pos.valid_bbt:
                self.ui.labelTime.setText(
                    "%03i|%02i|%04i" % (transport_pos.bar,
                                        transport_pos.beat,
                                        transport_pos.tick))
            else:
                self.ui.labelTime.setText("???|??|????")
                
        if transport_pos.valid_bbt:
            if int(transport_pos.beats_per_minutes) == transport_pos.beats_per_minutes:
                self.ui.labelTempo.setText(f"{int(transport_pos.beats_per_minutes)} BPM")
            else:
                self.ui.labelTempo.setText('%.2f BPM' % transport_pos.beats_per_minutes)
        else:
            self.ui.labelTempo.setText('')
            
        self.ui.toolButtonRewind.setEnabled(transport_pos.frame != 0)

        self._last_transport_pos = transport_pos

    @pyqtSlot()
    def _transport_view_changed(self):
        self.refresh_transport(self._last_transport_pos)
    
    def change_tools_displayed(self, tools_displayed: ToolDisplayed):        
        self._tools_displayed = tools_displayed
        
        if not self._jack_running:
            self.set_jack_running(
                False, use_alsa_midi=self._patchbay_mng.alsa_midi_enabled)
            return
        
        self.ui.frameTypeFilter.setVisible(
            bool(self._tools_displayed & ToolDisplayed.PORT_TYPES_VIEW))
        self.ui.sliderZoom.setVisible(
            bool(self._tools_displayed & ToolDisplayed.ZOOM_SLIDER))

        # manage transport widgets
        has_clock = bool(tools_displayed & ToolDisplayed.TRANSPORT_CLOCK)
        has_play_stop = bool(tools_displayed & ToolDisplayed.TRANSPORT_PLAY_STOP)
        
        self.ui.toolButtonRewind.setVisible(has_clock)
        self.ui.labelTime.setVisible(has_clock)
        self.ui.toolButtonForward.setVisible(has_clock)
        self.ui.toolButtonPlayPause.setVisible(has_play_stop)
        self.ui.toolButtonStop.setVisible(has_play_stop)
        self.ui.labelTempo.setVisible(tools_displayed & ToolDisplayed.TRANSPORT_TEMPO)
        
        SR_AND_LT = ToolDisplayed.SAMPLERATE | ToolDisplayed.LATENCY
        
        self.ui.labelBuffer.setVisible(
            bool(tools_displayed & ToolDisplayed.BUFFER_SIZE))
        self.ui.comboBoxBuffer.setVisible(
            bool(tools_displayed & ToolDisplayed.BUFFER_SIZE))
        self.ui.labelSamplerate.setVisible(
            bool(tools_displayed & ToolDisplayed.SAMPLERATE))
        self.ui.labelPipeSeparator.setVisible(
            bool(self._tools_displayed & SR_AND_LT == SR_AND_LT))
        self.ui.labelLatency.setVisible(
            bool(self._tools_displayed & ToolDisplayed.LATENCY))
        self.ui.pushButtonXruns.setVisible(
            bool(tools_displayed & ToolDisplayed.XRUNS))
        self.ui.progressBarDsp.setVisible(
            bool(tools_displayed & ToolDisplayed.DSP_LOAD))
    
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
        self.buffer_size_change_order.emit(
            self.ui.comboBoxBuffer.currentData())

        # only in the case no set_buffer_size message come back
        QTimer.singleShot(10000, self._re_enable_buffer_combobox)

    def _re_enable_buffer_combobox(self):
        if self._waiting_buffer_change:
            self.set_buffer_size(self._current_buffer_size)

    def set_jack_running(self, yesno: bool, use_alsa_midi=False):
        self._jack_running = yesno
        
        self.ui.labelJackNotStarted.setVisible(not yesno)
        if yesno:
            self.change_tools_displayed(self._tools_displayed)
        else:
            self.ui.frameTypeFilter.setVisible(
                use_alsa_midi and self._tools_displayed & ToolDisplayed.PORT_TYPES_VIEW)
            self.ui.sliderZoom.setVisible(
                use_alsa_midi and self._tools_displayed & ToolDisplayed.ZOOM_SLIDER)
            self.ui.toolButtonRewind.setVisible(False)
            self.ui.labelTime.setVisible(False)
            self.ui.toolButtonForward.setVisible(False)
            self.ui.toolButtonPlayPause.setVisible(False)
            self.ui.toolButtonStop.setVisible(False)
            self.ui.labelTempo.setVisible(False)
            self.ui.labelBuffer.setVisible(False)
            self.ui.comboBoxBuffer.setVisible(False)
            self.ui.labelSamplerate.setVisible(False)
            self.ui.labelPipeSeparator.setVisible(False)
            self.ui.labelLatency.setVisible(False)
            self.ui.pushButtonXruns.setVisible(False)
            self.ui.progressBarDsp.setVisible(False)


