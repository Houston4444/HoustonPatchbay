
from enum import Enum, IntEnum, auto
import time
from typing import TYPE_CHECKING
from PyQt5.QtCore import pyqtSignal, QTimer, pyqtSlot, QPoint
from PyQt5.QtGui import QPalette, QIcon, QColor, QKeySequence
from PyQt5.QtWidgets import (
    QWidget, QToolBar, QMainWindow, QAction, QApplication, QMenu)

from .bar_widget_jack import BarWidgetJack
from .bar_widget_transport import BarWidgetTransport
from .bar_widget_canvas import BarWidgetCanvas

from .ui.patchbay_tools import Ui_Form as PatchbayToolsUiForm
from .base_elements import (
    ToolDisplayed, TransportPosition, TransportViewMode)

if TYPE_CHECKING:
    from .patchbay_manager import PatchbayManager
    from .tool_bar import PatchbayToolBar


_translate = QApplication.translate


def is_dark_theme(widget: QWidget) -> bool:
    return bool(
        widget.palette().brush(
            QPalette.Active, QPalette.WindowText).color().lightness()
        > 128)


class JackAgnostic(Enum):
    'Enum used by Patchichi to set what is displayed'
    
    NONE = 0
    'Not JACK agnostic, used by Patchance and RaySession'
    
    DUMMY = 1
    'JACK agnostic in reality, but display all widgets'
    
    FULL = 2
    'Hide all widgets related to JACK'


class TBar(IntEnum):
    MAIN = 0
    TRANSPORT = 1
    JACK = 2
    CANVAS = 3
    

class ToolBarsLayout(Enum):
    # M for Main
    # C for Canvas
    # T for Transport
    # J for JACK
    # _ for toolbar break (new line)
    MCTJ = auto()
    MTJ_C = auto()
    MJ_TC = auto()
    MJ_T_C = auto()
    M_CTJ = auto()
    M_TJ_C = auto()
    M_J_TC = auto()
    M_J_T_C = auto()


class PatchbayToolsWidget(QWidget):
    buffer_size_change_order = pyqtSignal(int)

    def __init__(self):
        QWidget.__init__(self)
        self.ui = PatchbayToolsUiForm()
        self.ui.setupUi(self)

        # self.ui.toolButtonPlayPause.clicked.connect(self._play_clicked)
        # self.ui.toolButtonStop.clicked.connect(self._stop_clicked)
        # self.ui.toolButtonRewind.clicked.connect(self._rewind_clicked)
        # self.ui.toolButtonForward.clicked.connect(self._forward_clicked)
        # self.ui.labelTime.transport_view_changed.connect(
        #     self._transport_view_changed)
        
        self._jack_running = True
        
        self.mng: 'PatchbayManager' = None
        self._last_transport_pos = TransportPosition(
            0, False, False, 0, 0, 0, 120.00)
        
        self.ui.toolButtonPlayPause.setShortcut(QKeySequence(' '))
        
        self._jack_agnostic = JackAgnostic.NONE
        
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
        self.tbars : tuple[PatchbayToolBar, ...]= None
        self.tbar_widths = (0, 0, 0, 0)
        # # set theme
        # app_bg = self.ui.labelTempo.palette().brush(
        #     QPalette.Active, QPalette.Background).color()
        
        # scheme = 'dark' if dark else 'light'
        # self._icon_play = QIcon(
        #     f':/transport/{scheme}/media-playback-start.svg')
        # self._icon_pause = QIcon(
        #     f':/transport/{scheme}/media-playback-pause.svg')
        
        # self.ui.toolButtonRewind.setIcon(
        #     QIcon(f':/transport/{scheme}/media-seek-backward.svg'))
        # self.ui.toolButtonForward.setIcon(
        #     QIcon(f':/transport/{scheme}/media-seek-forward.svg'))
        # self.ui.toolButtonPlayPause.setIcon(self._icon_play)
        # self.ui.toolButtonStop.setIcon(
        #     QIcon(f':/transport/{scheme}/media-playback-stop.svg'))

        # bg = QColor(app_bg)
        # more_gray = 20 if dark else -30
        
        # bg.setRed(max(min(app_bg.red() + more_gray, 255), 0))
        # bg.setGreen(max(min(app_bg.green() + more_gray, 255), 0))
        # bg.setBlue(max(min(app_bg.blue() + more_gray, 255), 0))
        # background = bg.name()

        # round_side = 'left'
        # for button in (self.ui.toolButtonRewind, self.ui.toolButtonPlayPause,
        #                self.ui.toolButtonForward, self.ui.toolButtonStop):
        #     if button is self.ui.toolButtonForward:
        #         round_side = "right"

        #     button.setStyleSheet(
        #         f"QToolButton{{background:{background}; border:none;"
        #         f"border-top-{round_side}-radius:4px;"
        #         f"border-bottom-{round_side}-radius:4px}}")

        # count_bg = self.palette().base().color().name()

        # self.ui.labelTime.setStyleSheet(
        #     f"QLabel{{background:{count_bg}; border: 2px solid {background}}}")
    
    # def _play_clicked(self, play: bool):
    #     if self.mng is not None:
    #         self.mng.transport_play_pause(play)
            
    # def _stop_clicked(self):
    #     if self.mng is not None:
    #         self.mng.transport_stop()

    # def _rewind_clicked(self):
    #     if self.mng is not None:
    #         now = time.time()
    #         move = 1.0 * self._samplerate
            
    #         if now - self._bw_clicked_last_time < 0.400:
    #             move = (1.0 + (now - self._bw_click_started_at) ** 1.5) * self._samplerate
    #         else:
    #             self._bw_click_started_at = now

    #         self.mng.transport_relocate(
    #             max(0, int(self._last_transport_pos.frame - move)))
    
    #         self._bw_clicked_last_time = now
        
    # def _forward_clicked(self):
    #     if self.mng is not None:
    #         now = time.time()
    #         move = 1.0 * self._samplerate
            
    #         if now - self._fw_clicked_last_time < 0.400:
    #             move = (1.0 + (now - self._fw_click_started_at) ** 1.5) * self._samplerate
    #         else:
    #             self._fw_click_started_at = now

    #         self.mng.transport_relocate(
    #             int(self._last_transport_pos.frame + move))
    
    #         self._fw_clicked_last_time = now
    
        self._transport_wg: BarWidgetTransport = None
        self._jack_wg: BarWidgetJack = None
        self._canvas_wg: BarWidgetCanvas = None
        self._last_layout = ToolBarsLayout.MCTJ

    @staticmethod
    def _make_context_actions() -> dict[ToolDisplayed, QAction]:
        return {
            ToolDisplayed.VIEWS_SELECTOR:
                QAction(QIcon.fromTheme('view-multiple-objects'),
                        _translate('tool_bar', 'Views selector')),
            ToolDisplayed.HIDDENS_BOX:
                QAction(QIcon.fromTheme('hint'),
                        _translate('tool_bar', 'Hidden boxes')),
            ToolDisplayed.PORT_TYPES_VIEW:
                QAction(QIcon.fromTheme('view-filter'),
                        _translate('tool_bar', 'Type filter')),
            ToolDisplayed.ZOOM_SLIDER:
                QAction(QIcon.fromTheme('zoom-select'),
                        _translate('tool_bar', 'Zoom slider')),
            ToolDisplayed.TRANSPORT_CLOCK:
                QAction(QIcon.fromTheme('clock'),
                        _translate('tool_bar', 'Transport clock')),
            ToolDisplayed.TRANSPORT_PLAY_STOP:
                QAction(QIcon.fromTheme('media-playback-pause'),
                        _translate('tool_bar', 'Transport Play/Stop')),
            ToolDisplayed.TRANSPORT_TEMPO:
                QAction(QIcon.fromTheme('folder-music-symbolic'),
                        _translate('tool_bar', 'Transport Tempo')),
            ToolDisplayed.BUFFER_SIZE:
                QAction(QIcon.fromTheme('settings-configure'),
                        _translate('tool_bar', 'Buffer size')),
            ToolDisplayed.SAMPLERATE:
                QAction(QIcon.fromTheme('filename-sample-rate'),
                        _translate('tool_bar', 'Sample rate')),
            ToolDisplayed.LATENCY:
                QAction(QIcon.fromTheme('chronometer-lap'),
                        _translate('tool_bar', 'Latency')),
            ToolDisplayed.XRUNS:
                QAction(QIcon.fromTheme('data-error'),
                        _translate('tool_bar', 'Xruns')),
            ToolDisplayed.DSP_LOAD:
                QAction(QIcon.fromTheme('histogram-symbolic'),
                        _translate('tool_bar', 'DSP Load'))
        }

    def _make_context_menu(
            self, context_actions: dict[ToolDisplayed, QAction]) -> QMenu:
        menu = QMenu()
        menu.addSection(_translate('tool_bar', 'Displayed tools'))
        
        for key, act in context_actions.items():
            act.setCheckable(True)
            act.setChecked(bool(self._tools_displayed & key))
            if self.mng is not None:
                if not self.mng.server_is_started:
                    if key in (ToolDisplayed.PORT_TYPES_VIEW,
                               ToolDisplayed.ZOOM_SLIDER):
                        act.setEnabled(self.mng.alsa_midi_enabled)
                    else:
                        act.setEnabled(False)
            menu.addAction(act)
            
            if key is ToolDisplayed.ZOOM_SLIDER:
                menu.addSeparator()
            
        return menu

    def set_patchbay_manager(self, mng: 'PatchbayManager'):
        self.mng = mng
        self.ui.frameTypeFilter.set_patchbay_manager(mng)
        self.ui.sliderZoom.set_patchbay_manager(mng)
        self.ui.viewSelector.set_patchbay_manager(mng)
        self.ui.toolButtonHiddenBoxes.set_patchbay_manager(mng)
        
        for toolbar in self.tbars[1:]:
            toolbar.set_patchbay_manager(mng)
    
    def set_tool_bars(self, *tool_bars: 'PatchbayToolBar'):
        self.tbars = tool_bars

        self._transport_wg = BarWidgetTransport(self.tbars[TBar.TRANSPORT])
        self._jack_wg = BarWidgetJack(self.tbars[TBar.JACK])
        self._canvas_wg = BarWidgetCanvas(self.tbars[TBar.CANVAS])

        self.tbars[TBar.TRANSPORT].addWidget(self._transport_wg)        
        self.tbars[TBar.JACK].addWidget(self._jack_wg)
        self.tbars[TBar.CANVAS].addWidget(self._canvas_wg)

        for tbar in self.tbars:
            tbar.menu_asked.connect(self._menu_asked)
        
        self.tbar_widths = tuple([tb.sizeHint().width() for tb in tool_bars])
    
    @pyqtSlot(QPoint)
    def _menu_asked(self, point: QPoint):
        context_actions = self._make_context_actions()
        menu = self._make_context_menu(context_actions)
        
        selected_act = menu.exec(point)
        if selected_act is None:
            return

        for key, act in context_actions.items():
            if act is selected_act:
                if act.isChecked():
                    self._tools_displayed |= key
                else:
                    self._tools_displayed &= ~key
                    
        self.change_tools_displayed(self._tools_displayed)

        # self._change_visibility()
    
    def get_layout_widths(self) -> tuple[int, int]:
        return (self.ui.horizontalLayoutCanvas.sizeHint().width(),
                self.ui.horizontalLayoutJack.sizeHint().width())
    
    def set_jack_agnostic(self, agnostic: JackAgnostic):
        '''Use without any jack tool. Used by Patchichi.'''
        self._jack_agnostic = agnostic
        self.change_tools_displayed(self._tools_displayed)
    
    def update_hiddens_indicator(self):
        if self.mng is None:
            return
        
        cg = 0
        for group in self.mng.list_hidden_groups():
            cg += 1
            
        self.ui.toolButtonHiddenBoxes.setText(str(cg))
    
    # def refresh_transport(self, transport_pos: TransportPosition):
    #     self.ui.toolButtonPlayPause.setChecked(transport_pos.rolling)
        
    #     if transport_pos.rolling:
    #         self.ui.toolButtonPlayPause.setIcon(self._icon_pause)
    #     else:
    #         self.ui.toolButtonPlayPause.setIcon(self._icon_play)
            
    #     if self.ui.labelTime.transport_view_mode is not TransportViewMode.FRAMES:
    #         # switch the view mode in case beats info appears/disappears 
    #         if transport_pos.valid_bbt and not self._last_transport_pos.valid_bbt:
    #             self.ui.labelTime.transport_view_mode = TransportViewMode.BEAT_BAR_TICK
    #         elif not transport_pos.valid_bbt and self._last_transport_pos.valid_bbt:
    #             self.ui.labelTime.transport_view_mode = TransportViewMode.HOURS_MINUTES_SECONDS
        
    #     if (self.ui.labelTime.transport_view_mode
    #             is TransportViewMode.HOURS_MINUTES_SECONDS):
    #         # if the transport time is during the first second
    #         # but not at 0, we display something else to show
    #         # that transport is rolling after press play.
    #         # If it is not rolling, it shows that transport is not
    #         # exactly at start.
    #         if 0 < transport_pos.frame < self._samplerate / 2:
    #             self.ui.labelTime.setText("00:00:0_")
    #         elif 0 < transport_pos.frame < self._samplerate:
    #             self.ui.labelTime.setText("00:00:0-")
    #         else:
    #             time = transport_pos.frame // self._samplerate
    #             secs = time % 60
    #             mins = (time / 60) % 60
    #             hrs  = (time / 3600) % 60
    #             self.ui.labelTime.setText("%02i:%02i:%02i" % (hrs, mins, secs))
            
    #     elif (self.ui.labelTime.transport_view_mode
    #             is TransportViewMode.FRAMES):
    #         frame1 =  transport_pos.frame % 1000
    #         frame2 = int(transport_pos.frame / 1000) % 1000
    #         frame3 = int(transport_pos.frame / 1000000) % 1000
            
    #         self.ui.labelTime.setText("%03i'%03i'%03i" % (frame3, frame2, frame1))
            
    #     elif (self.ui.labelTime.transport_view_mode
    #             is TransportViewMode.BEAT_BAR_TICK):
    #         if transport_pos.valid_bbt:
    #             self.ui.labelTime.setText(
    #                 "%03i|%02i|%04i" % (transport_pos.bar,
    #                                     transport_pos.beat,
    #                                     transport_pos.tick))
    #         else:
    #             self.ui.labelTime.setText("???|??|????")
                
    #     if transport_pos.valid_bbt:
    #         if int(transport_pos.beats_per_minutes) == transport_pos.beats_per_minutes:
    #             self.ui.labelTempo.setText(f"{int(transport_pos.beats_per_minutes)} BPM")
    #         else:
    #             self.ui.labelTempo.setText('%.2f BPM' % transport_pos.beats_per_minutes)
    #     else:
    #         self.ui.labelTempo.setText('')
            
    #     self.ui.toolButtonRewind.setEnabled(transport_pos.frame != 0)

    #     self._last_transport_pos = transport_pos

    # @pyqtSlot()
    # def _transport_view_changed(self):
    #     self.refresh_transport(self._last_transport_pos)
    
    def change_tools_displayed(self, tools_displayed: ToolDisplayed):        
        self._tools_displayed = tools_displayed
        
        if not self._jack_running:
            self.set_jack_running(
                False, use_alsa_midi=self.mng.alsa_midi_enabled)
            return
        
        if self.tbars is None:
            return
        
        if self._canvas_wg is not None:
            self._canvas_wg.change_tools_displayed(tools_displayed)
        
        # self.ui.viewSelector.setVisible(
        #     bool(self._tools_displayed & ToolDisplayed.VIEWS_SELECTOR))
        # self.ui.toolButtonHiddenBoxes.setVisible(
        #         bool(self._tools_displayed & ToolDisplayed.HIDDENS_BOX))
        # self.ui.frameTypeFilter.setVisible(
        #     bool(self._tools_displayed & ToolDisplayed.PORT_TYPES_VIEW))
        # self.ui.sliderZoom.setVisible(
        #     bool(self._tools_displayed & ToolDisplayed.ZOOM_SLIDER))

        # manage transport widgets
        if self._transport_wg is not None:
            self._transport_wg.change_tools_displayed(tools_displayed)
            
        if self._jack_wg is not None:
            self._jack_wg.change_tools_displayed(tools_displayed)
        # self.tbars[TBar.TRANSPORT].change_tools_displayed(tools_displayed)
        
        # has_clock = bool(tools_displayed & ToolDisplayed.TRANSPORT_CLOCK)
        # has_play_stop = bool(tools_displayed & ToolDisplayed.TRANSPORT_PLAY_STOP)
        
        # self.ui.toolButtonRewind.setVisible(has_clock)
        # self.ui.labelTime.setVisible(has_clock)
        # self.ui.toolButtonForward.setVisible(has_clock)
        # self.ui.toolButtonPlayPause.setVisible(has_play_stop)
        # self.ui.toolButtonStop.setVisible(has_play_stop)
        # self.ui.labelTempo.setVisible(tools_displayed & ToolDisplayed.TRANSPORT_TEMPO)
        
        # SR_AND_LT = ToolDisplayed.SAMPLERATE | ToolDisplayed.LATENCY
        
        # self.ui.labelBuffer.setVisible(
        #     bool(tools_displayed & ToolDisplayed.BUFFER_SIZE))
        # self.ui.comboBoxBuffer.setVisible(
        #     bool(tools_displayed & ToolDisplayed.BUFFER_SIZE))
        # self.ui.labelSamplerate.setVisible(
        #     bool(tools_displayed & ToolDisplayed.SAMPLERATE))
        # self.ui.labelPipeSeparator.setVisible(
        #     bool(self._tools_displayed & SR_AND_LT == SR_AND_LT))
        # self.ui.labelLatency.setVisible(
        #     bool(self._tools_displayed & ToolDisplayed.LATENCY))
        # self.ui.pushButtonXruns.setVisible(
        #     bool(tools_displayed & ToolDisplayed.XRUNS))
        # self.ui.progressBarDsp.setVisible(
        #     bool(tools_displayed & ToolDisplayed.DSP_LOAD))
        
        if self._jack_agnostic is JackAgnostic.FULL:
            # self.ui.frameJack.setVisible(False)
            # self.tbars[TBar.JACK].setVisible(False)
            if self._jack_wg is not None:
                self._jack_wg.setVisible(False)
            if self._transport_wg is not None:
                self._transport_wg.setVisible(False)
            
        elif self._jack_agnostic is JackAgnostic.DUMMY:
            if self._jack_wg is not None:
                self._jack_wg.set_jack_running(True)
                self._jack_wg.set_dsp_load(2)
            # self.ui.labelJackNotStarted.setVisible(False)
            # self.ui.progressBarDsp.setValue(1)
    
    # def _set_latency(self, buffer_size=None, samplerate=None):
    #     if buffer_size is None:
    #         buffer_size = self._current_buffer_size
    #     if samplerate is None:
    #         samplerate = self._samplerate

    #     latency = 1000 * buffer_size / samplerate
    #     self.ui.labelLatency.setText("%.2f ms" % latency)
        self.tbar_widths = tuple([t.sizeHint().width() for t in self.tbars])
        for tbar in self.tbars:
            tbar.updateGeometry()
        print('chg displlay', self.tbar_widths)
        
        QTimer.singleShot(0, self._resize_later)        

    @pyqtSlot()
    def _resize_later(self):
        if self.mng is not None and self.mng.main_win is not None:
            self.main_win_resize(self.mng.main_win)

    def set_samplerate(self, samplerate: int):
        if self._jack_wg is not None:
            self._jack_wg.set_samplerate(samplerate)
        
        if self._transport_wg is not None:
            self._transport_wg.set_samplerate(samplerate)

    def set_buffer_size(self, buffer_size: int):
        if self._jack_wg is not None:
            self._jack_wg.set_buffer_size(buffer_size)
        
        # self._waiting_buffer_change = False
        # self.ui.comboBoxBuffer.setEnabled(True)

        # if self.ui.comboBoxBuffer.currentData() == buffer_size:
        #     self._set_latency(buffer_size=buffer_size)
        #     return

        # self._buffer_change_from_osc = True

        # index = self.ui.comboBoxBuffer.findData(buffer_size)

        # # manage exotic buffer sizes
        # # findData returns -1 if buffer_size is not in combo box values
        # if index < 0:
        #     index = 0
        #     for size in self._buffer_sizes:
        #         if size > buffer_size:
        #             break
        #         index += 1

        #     self._buffer_sizes.insert(index, buffer_size)
        #     self.ui.comboBoxBuffer.insertItem(
        #         index, str(buffer_size), buffer_size)

        # self.ui.comboBoxBuffer.setCurrentIndex(index)
        # self._current_buffer_size = buffer_size
        # self._set_latency(buffer_size=buffer_size)

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
        
        # self.ui.labelJackNotStarted.setVisible(not yesno)
        if yesno:
            self.change_tools_displayed(self._tools_displayed)
        else:
            if self._jack_wg is not None:
                self._jack_wg.set_jack_running(False)
                self._transport_wg.set_jack_running(False)
            # self.ui.frameTypeFilter.setVisible(
            #     use_alsa_midi and self._tools_displayed & ToolDisplayed.PORT_TYPES_VIEW)
            # self.ui.sliderZoom.setVisible(
            #     use_alsa_midi and self._tools_displayed & ToolDisplayed.ZOOM_SLIDER)
            # self.ui.toolButtonRewind.setVisible(False)
            # self.ui.labelTime.setVisible(False)
            # self.ui.toolButtonForward.setVisible(False)
            # self.ui.toolButtonPlayPause.setVisible(False)
            # self.ui.toolButtonStop.setVisible(False)
            # self.ui.labelTempo.setVisible(False)
            # self.ui.labelBuffer.setVisible(False)
            # self.ui.comboBoxBuffer.setVisible(False)
            # self.ui.labelSamplerate.setVisible(False)
            # self.ui.labelPipeSeparator.setVisible(False)
            # self.ui.labelLatency.setVisible(False)
            # self.ui.pushButtonXruns.setVisible(False)
            # self.ui.progressBarDsp.setVisible(False)

    def _get_toolbars_layout(self, width: int) -> ToolBarsLayout:
        self.tbar_widths = tuple([b.sizeHint().width() for b in self.tbars])
        print('get layout', self.tbar_widths)
        
        if width >= sum(self.tbar_widths):
            return ToolBarsLayout.MCTJ
        
        m, t, j, c = self.tbar_widths
        
        if width >= m + t + j:
            return ToolBarsLayout.MTJ_C
        
        if width >= m + j:
            if width >= t + c:
                return ToolBarsLayout.MJ_TC
            return ToolBarsLayout.MJ_T_C
        
        if width >= c + t + j:
            return ToolBarsLayout.M_CTJ
        
        if width >= t + j:
            return ToolBarsLayout.M_TJ_C
        
        if width >= t + c:
            return ToolBarsLayout.M_J_TC
        
        return ToolBarsLayout.M_J_T_C

    def main_win_resize(self, main_win: QMainWindow):
        layout = self._get_toolbars_layout(main_win.width())
        print('mainwiin resize', layout)
        if (layout is self._last_layout):
            return
        
        self._last_layout = layout
        
        for toolbar in self.tbars:
            main_win.removeToolBar(toolbar)
        
        letter_bar = {'M': TBar.MAIN,
                      'T': TBar.TRANSPORT, 
                      'C': TBar.CANVAS,
                      'J': TBar.JACK}
        
        for letter in layout.name:
            if letter == '_':
                main_win.addToolBarBreak()
            elif letter in letter_bar:
                main_win.addToolBar(self.tbars[letter_bar[letter]])
        
        for toolbar in self.tbars:
            toolbar.setVisible(True)
        
