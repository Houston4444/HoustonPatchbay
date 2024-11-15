import time
from typing import TYPE_CHECKING

from qtpy.QtWidgets import QWidget
from qtpy.QtGui import QPalette, QIcon, QColor, QKeySequence
from qtpy.QtCore import Slot

from .base_elements import (
    ToolDisplayed, TransportPosition, TransportViewMode)

from .ui.transport_bar import Ui_Form as TransportUiForm

if TYPE_CHECKING:
    from patchbay_manager import PatchbayManager


def is_dark_theme(widget: QWidget) -> bool:
    return bool(
        widget.palette().brush(
            QPalette.ColorGroup.Active,
            QPalette.ColorRole.WindowText).color().lightness()
        > 128)


class BarWidgetTransport(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.ui = TransportUiForm()
        self.ui.setupUi(self)
        
        self.ui.toolButtonPlayPause.clicked.connect(self._play_clicked)
        self.ui.toolButtonStop.clicked.connect(self._stop_clicked)
        self.ui.toolButtonRewind.clicked.connect(self._rewind_clicked)
        self.ui.toolButtonForward.clicked.connect(self._forward_clicked)
        self.ui.labelTime.transport_view_changed.connect(
            self._transport_view_changed)
        
        self._samplerate = 48000
        
        self.mng: 'PatchbayManager' = None
        self._last_transport_pos = TransportPosition(
            0, False, False, 0, 0, 0, 120.00)
        
        self.ui.toolButtonPlayPause.setShortcut(QKeySequence(' '))
        
        self._fw_clicked_last_time = 0
        self._fw_click_started_at = 0
        self._bw_clicked_last_time = 0
        self._bw_click_started_at = 0
        
        dark = is_dark_theme(self)
        
        # set theme
        app_bg = self.ui.labelTempo.palette().brush(
            QPalette.Active, QPalette.Button).color()
        
        scheme = 'dark' if dark else 'light'
        self._icon_play = QIcon(
            f':/transport/{scheme}/media-playback-start.svg')
        self._icon_pause = QIcon(
            f':/transport/{scheme}/media-playback-pause.svg')
        
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
    
    @Slot(bool)
    def _play_clicked(self, play: bool):
        if self.mng is not None:
            self.mng.transport_play_pause(play)
    
    @Slot()
    def _stop_clicked(self):
        if self.mng is not None:
            self.mng.transport_stop()

    @Slot()
    def _rewind_clicked(self):
        if self.mng is not None:
            now = time.time()
            move = 1.0 * self._samplerate
            
            if now - self._bw_clicked_last_time < 0.400:
                move = ((1.0 + (now - self._bw_click_started_at) ** 1.5)
                        * self._samplerate)
            else:
                self._bw_click_started_at = now

            self.mng.transport_relocate(
                max(0, int(self._last_transport_pos.frame - move)))
    
            self._bw_clicked_last_time = now
    
    @Slot()
    def _forward_clicked(self):
        if self.mng is not None:
            now = time.time()
            move = 1.0 * self._samplerate
            
            if now - self._fw_clicked_last_time < 0.400:
                move = ((1.0 + (now - self._fw_click_started_at) ** 1.5)
                        * self._samplerate)
            else:
                self._fw_click_started_at = now

            self.mng.transport_relocate(
                int(self._last_transport_pos.frame + move))
    
            self._fw_clicked_last_time = now

    @Slot()
    def _transport_view_changed(self):
        self.refresh_transport(self._last_transport_pos)

    def refresh_transport(self, transport_pos: TransportPosition):
        self.ui.toolButtonPlayPause.setChecked(transport_pos.rolling)
        
        if transport_pos.rolling:
            self.ui.toolButtonPlayPause.setIcon(self._icon_pause)
        else:
            self.ui.toolButtonPlayPause.setIcon(self._icon_play)
            
        if (self.ui.labelTime.transport_view_mode
                is not TransportViewMode.FRAMES):
            # switch the view mode in case beats info appears/disappears 
            if (transport_pos.valid_bbt
                    and not self._last_transport_pos.valid_bbt):
                self.ui.labelTime.transport_view_mode = \
                    TransportViewMode.BEAT_BAR_TICK
            elif (not transport_pos.valid_bbt
                    and self._last_transport_pos.valid_bbt):
                self.ui.labelTime.transport_view_mode = \
                    TransportViewMode.HOURS_MINUTES_SECONDS
        
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
                self.ui.labelTime.setText(
                    "%02i:%02i:%02i" % (hrs, mins, secs))
            
        elif (self.ui.labelTime.transport_view_mode
                is TransportViewMode.FRAMES):
            frame1 = transport_pos.frame % 1000
            frame2 = int(transport_pos.frame / 1000) % 1000
            frame3 = int(transport_pos.frame / 1000000) % 1000
            
            self.ui.labelTime.setText(
                "%03i'%03i'%03i" % (frame3, frame2, frame1))
            
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
            if (int(transport_pos.beats_per_minutes)
                    == transport_pos.beats_per_minutes):
                self.ui.labelTempo.setText(
                    f"{int(transport_pos.beats_per_minutes)} BPM")
            else:
                self.ui.labelTempo.setText(
                    '%.2f BPM' % transport_pos.beats_per_minutes)
        else:
            self.ui.labelTempo.setText('')
            
        self.ui.toolButtonRewind.setEnabled(transport_pos.frame != 0)

        self._last_transport_pos = transport_pos

    def set_patchbay_manager(self, mng: 'PatchbayManager'):
        self.mng = mng
    
    def set_samplerate(self, samplerate: int):
        self._samplerate = samplerate
    
    def set_jack_running(self, running: bool):
        if not running:
            self.ui.toolButtonRewind.setVisible(False)
            self.ui.labelTime.setVisible(False)
            self.ui.toolButtonForward.setVisible(False)
            self.ui.toolButtonPlayPause.setVisible(False)
            self.ui.toolButtonStop.setVisible(False)
            self.ui.labelTempo.setVisible(False)
    
    def change_tools_displayed(self, tools_displayed: ToolDisplayed):
        has_clock = bool(tools_displayed & ToolDisplayed.TRANSPORT_CLOCK)
        has_play_stop = bool(
            tools_displayed & ToolDisplayed.TRANSPORT_PLAY_STOP)
        
        self.ui.toolButtonRewind.setVisible(has_clock)
        self.ui.labelTime.setVisible(has_clock)
        self.ui.toolButtonForward.setVisible(has_clock)
        self.ui.toolButtonPlayPause.setVisible(has_play_stop)
        self.ui.toolButtonStop.setVisible(has_play_stop)
        self.ui.labelTempo.setVisible(
            bool(tools_displayed & ToolDisplayed.TRANSPORT_TEMPO))
        
        