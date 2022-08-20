
from typing import TYPE_CHECKING
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QFrame
from PyQt5.QtCore import pyqtSlot

from .base_elements import TransportPosition, TransportViewMode
from .ui.transport_controls import Ui_FrameTransportControls

if TYPE_CHECKING:
    from .patchbay_manager import PatchbayManager


class TransportControlsFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_FrameTransportControls()
        self.ui.setupUi(self)
        
        self.ui.toolButtonPlayPause.clicked.connect(self._play_clicked)
        self.ui.toolButtonStop.clicked.connect(self._stop_clicked)
        self.ui.labelTime.transport_view_changed.connect(self._transport_view_changed)
        
        self._patchbay_mng: 'PatchbayManager' = None
        self._samplerate = 48000
        self._last_transport_pos = TransportPosition(0, False, False, 0, 0, 0, 120.00)
    
    def _play_clicked(self, play: bool):
        if self._patchbay_mng is not None:
            self._patchbay_mng.transport_play_pause(play)
            
    def _stop_clicked(self):
        if self._patchbay_mng is not None:
            self._patchbay_mng.transport_stop()
            
    def set_patchbay_manager(self, mng: 'PatchbayManager'):
        self._patchbay_mng = mng
    
    def set_samplerate(self, samplerate: int):
        self._samplerate = samplerate
    
    def refresh_transport(self, transport_pos: TransportPosition):
        self._last_transport_pos = transport_pos
        
        self.ui.toolButtonPlayPause.setChecked(transport_pos.rolling)
        if transport_pos.rolling:
            self.ui.toolButtonPlayPause.setIcon(
                QIcon.fromTheme('media-playback-pause'))
        else:
            self.ui.toolButtonPlayPause.setIcon(
                QIcon.fromTheme('media-playback-start'))
        
        if (self.ui.labelTime.transport_view_mode
                is TransportViewMode.HOURS_MINUTES_SECONDS):
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
                self.ui.labelTime.setText("000|00|0000")
                
        if transport_pos.valid_bbt:
            if int(transport_pos.beats_per_minutes) == transport_pos.beats_per_minutes:
                self.ui.labelTempo.setText(f"{int(transport_pos.beats_per_minutes)} BPM")
            else:
                self.ui.labelTempo.setText('%.2f BPM' % transport_pos.beats_per_minutes)
        else:
            self.ui.labelTempo.setText('')
            
        self.ui.toolButtonRewind.setEnabled(transport_pos.frame != 0)
            
    
    @pyqtSlot()
    def _transport_view_changed(self):
        self.refresh_transport(self._last_transport_pos)