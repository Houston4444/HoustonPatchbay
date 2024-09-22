
from enum import Enum, IntEnum, auto
from typing import TYPE_CHECKING
from PyQt5.QtCore import QTimer, pyqtSlot, QPoint, QObject
from PyQt5.QtGui import QPalette, QIcon
from PyQt5.QtWidgets import (
    QWidget, QMainWindow, QAction, QApplication, QMenu)

from .bar_widget_jack import BarWidgetJack
from .bar_widget_transport import BarWidgetTransport
from .bar_widget_canvas import BarWidgetCanvas

from .base_elements import ToolDisplayed, TransportPosition

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


class PatchbayToolsWidget(QObject):
    def __init__(self):
        QObject.__init__(self)
        self._jack_running = True
        
        self.mng: 'PatchbayManager' = None
        self._jack_agnostic = JackAgnostic.NONE
        
        self._tools_displayed = ToolDisplayed.ALL
        self.tbars : tuple[PatchbayToolBar, ...]= None
        self._last_layout = 'MCTJ'

        self._transport_wg: BarWidgetTransport = None
        self._jack_wg: BarWidgetJack = None
        self._canvas_wg: BarWidgetCanvas = None
        
        self._last_win_width = 0

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
        if self._canvas_wg is not None:
            self._canvas_wg.set_patchbay_manager(mng)
    
    def set_tool_bars(self, *tool_bars: 'PatchbayToolBar'):
        self.tbars = tool_bars

        self._transport_wg = BarWidgetTransport(self.tbars[TBar.TRANSPORT])
        self._jack_wg = BarWidgetJack(self.tbars[TBar.JACK])
        self._canvas_wg = BarWidgetCanvas(self.tbars[TBar.CANVAS])

        self.tbars[TBar.TRANSPORT].addWidget(self._transport_wg)        
        self.tbars[TBar.JACK].addWidget(self._jack_wg)
        self.tbars[TBar.CANVAS].addWidget(self._canvas_wg)

        for tbar in self.tbars:
            tbar.toggleViewAction().setEnabled(False)
            tbar.toggleViewAction().setVisible(False)
            tbar.menu_asked.connect(self._menu_asked)
    
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
    
    def set_jack_agnostic(self, agnostic: JackAgnostic):
        '''Use without any jack tool. Used by Patchichi.'''
        self._jack_agnostic = agnostic
        self.change_tools_displayed(self._tools_displayed)
    
    def change_tools_displayed(self, tools_displayed: ToolDisplayed):        
        self._tools_displayed = tools_displayed
        
        if (self._jack_agnostic is not JackAgnostic.FULL
                and not self._jack_running):
            self.set_jack_running(
                False, use_alsa_midi=self.mng.alsa_midi_enabled)
            return
        
        if self.tbars is None:
            return
        
        if self._canvas_wg is not None:
            self._canvas_wg.change_tools_displayed(tools_displayed)

        if self._transport_wg is not None:
            self._transport_wg.change_tools_displayed(tools_displayed)
            
        if self._jack_wg is not None:
            self._jack_wg.change_tools_displayed(tools_displayed)
        
        if self._jack_agnostic is JackAgnostic.FULL:
            if self._jack_wg is not None:
                self._jack_wg.setVisible(False)
            if self._transport_wg is not None:
                self._transport_wg.setVisible(False)
            
        elif self._jack_agnostic is JackAgnostic.DUMMY:
            if self._jack_wg is not None:
                self._jack_wg.set_jack_running(True)
                self._jack_wg.set_dsp_load(2)

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

    def update_xruns(self):
        if self._jack_wg is not None:
            self._jack_wg.update_xruns()

    def add_xrun(self):
        if self._jack_wg is not None:
            self._jack_wg.add_xrun()

    def reset_xruns(self):
        if self._jack_wg is not None:
            self._jack_wg.reset_xruns()

    def set_dsp_load(self, dsp_load: int):
        if self._jack_wg is not None:
            self._jack_wg.set_dsp_load(dsp_load)

    def change_buffersize(self, index: int):
        if self._jack_wg is not None:
            self._jack_wg.change_buffersize()

    def refresh_transport(self, transport_pos: TransportPosition):
        if self._transport_wg is not None:
            self._transport_wg.refresh_transport(transport_pos)

    def set_jack_running(self, yesno: bool, use_alsa_midi=False):
        self._jack_running = yesno
        
        if yesno:
            self.change_tools_displayed(self._tools_displayed)
        else:
            if self._jack_wg is not None:
                self._jack_wg.set_jack_running(False)
                self._transport_wg.set_jack_running(False)

    def _canvas_is_last_of_line(self, layout: str) -> bool:
        for line in layout.split('_'):
            if line.endswith('C'):
                return True
        return False

    def _get_toolbars_layout(self, width: int) -> str:
        tbar_widths = tuple([b.needed_width() for b in self.tbars])
        m, t, j, c = tbar_widths
        # Main, Transport, Jack, Canvas
        # '_' for toolbarBreak (new line)

        if self._jack_agnostic is JackAgnostic.FULL:
            if width >= m + c:
                return 'MC'
            return 'M_C'
        
        if width >= sum(tbar_widths):
            return 'MTCJ'

        if width >= m + t + j:
            if width >= t + c:
                return 'MJ_TC'
            return 'MTJ_C'
        
        if width >= m + j:
            if width >= t + c:
                return 'MJ_TC'
            return 'MJ_T_C'
        
        if width >= c + t + j:
            return 'M_CTJ'
        
        if width >= t + j:
            return 'M_TJ_C'
        
        if width >= t + c:
            return 'M_J_TC'
        
        return 'M_J_T_C'

    def main_win_resize(self, main_win: QMainWindow):
        self._last_win_width = main_win.width()
        layout = self._get_toolbars_layout(self._last_win_width)
        if (layout == self._last_layout):
            QTimer.singleShot(0, self._arrange_tool_bars_later)
            return
        
        self._last_layout = layout
        
        for toolbar in self.tbars:
            main_win.removeToolBar(toolbar)
        
        letter_bar = {'M': TBar.MAIN,
                      'T': TBar.TRANSPORT, 
                      'C': TBar.CANVAS,
                      'J': TBar.JACK}
        
        for letter in layout:
            if letter == '_':
                main_win.addToolBarBreak()
            elif letter in letter_bar:
                main_win.addToolBar(self.tbars[letter_bar[letter]])

        for i in range(len(self.tbars)):
            if (self._jack_agnostic is JackAgnostic.FULL
                    and i in (TBar.JACK, TBar.TRANSPORT)):
                continue
            self.tbars[i].setVisible(True)
            
        # add/remove spacer at right of canvas bar widget
        if self._canvas_wg is not None:
            self._canvas_wg.set_at_end_of_line(
                self._canvas_is_last_of_line(self._last_layout))
            
        QTimer.singleShot(0, self._arrange_tool_bars_later)
    
    @pyqtSlot()
    def _arrange_tool_bars_later(self):
        if self._last_layout in ('MTCJ', 'M_TCJ'):
            width = self._last_win_width
            tbar_widths = tuple([b.needed_width() for b in self.tbars])
            m, t, j, c = tbar_widths
            
            if self._last_layout == 'MTCJ':
                diff = width - m - t - c - j
            else:
                diff = width - t -c -j

            if diff > 0:
                self.tbars[TBar.TRANSPORT].set_min_width(t + int(diff * 0.25))
                self.tbars[TBar.CANVAS].set_min_width(c + int(diff * 0.75))
            else:
                for tbar in self.tbars:
                    tbar.set_min_width(None)
        else:
            for tbar in self.tbars:
                tbar.set_min_width(None)
        
        