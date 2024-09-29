from enum import Enum, IntEnum
from typing import TYPE_CHECKING
from PyQt5.QtCore import QTimer, pyqtSlot, QPoint, QObject, Qt
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


class TextWithIcons(Enum):
    NO = 0
    AUTO = 1
    YES = 2

    @classmethod    
    def by_name(cls, name: str) -> 'TextWithIcons':
        if name == 'NO':
            return cls.NO
        if name == 'YES':
            return cls.YES
        return cls.AUTO


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
        self._last_layout = ''
        self._text_with_icons = TextWithIcons.AUTO

        self._transport_wg: BarWidgetTransport = None
        self._jack_wg: BarWidgetJack = None
        self._canvas_wg: BarWidgetCanvas = None
        
        self._last_win_width = 0
        self._main_bar_little_width = 0
        self._main_bar_large_width = 0
        self._first_resize_done = False

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
            
            if self._jack_agnostic is JackAgnostic.FULL:
                if key in (ToolDisplayed.TRANSPORT_CLOCK,
                           ToolDisplayed.TRANSPORT_PLAY_STOP,
                           ToolDisplayed.TRANSPORT_TEMPO,
                           ToolDisplayed.BUFFER_SIZE,
                           ToolDisplayed.SAMPLERATE,
                           ToolDisplayed.LATENCY,
                           ToolDisplayed.XRUNS,
                           ToolDisplayed.DSP_LOAD):
                    continue
            
            menu.addAction(act)
            
            if key is ToolDisplayed.ZOOM_SLIDER:
                menu.addSeparator()
        
        return menu

    def set_patchbay_manager(self, mng: 'PatchbayManager'):
        self.mng = mng
        if self._canvas_wg is not None:
            self._canvas_wg.set_patchbay_manager(mng)
        if self._transport_wg is not None:
            self._transport_wg.set_patchbay_manager(mng)
        if self._jack_wg is not None:
            self._jack_wg.set_patchbay_manager(mng)
    
    def set_tool_bars(self, *tool_bars: 'PatchbayToolBar'):
        self.tbars = tool_bars

        if self._transport_wg is None:
            self._transport_wg = BarWidgetTransport(
                self.tbars[TBar.TRANSPORT])
        if self._jack_wg is None:
            self._jack_wg = BarWidgetJack(self.tbars[TBar.JACK])
        if self._canvas_wg is None:
            self._canvas_wg = BarWidgetCanvas(self.tbars[TBar.CANVAS])

        if self._text_with_icons is not TextWithIcons.NO:
            # evaluate main bar widths (with and without text beside icons)
            main_bar = self.tbars[TBar.MAIN]
            tool_button_style = main_bar.toolButtonStyle()
            main_bar.setToolButtonStyle(Qt.ToolButtonIconOnly)
            self._main_bar_little_width = main_bar.sizeHint().width()
            main_bar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            self._main_bar_large_width = main_bar.sizeHint().width()
            main_bar.setToolButtonStyle(tool_button_style)

        self.tbars[TBar.TRANSPORT].addWidget(self._transport_wg)        
        self.tbars[TBar.JACK].addWidget(self._jack_wg)
        self.tbars[TBar.CANVAS].addWidget(self._canvas_wg)

        for tbar in self.tbars:
            tbar.toggleViewAction().setEnabled(False)
            tbar.toggleViewAction().setVisible(False)
            tbar.menu_asked.connect(self._menu_asked)
    
    def change_text_with_icons(self, text_with_icons: TextWithIcons):
        if text_with_icons is self._text_with_icons:
            return
        
        self._text_with_icons = text_with_icons
        if self.tbars is None:
            return

        main_bar = self.tbars[TBar.MAIN]
        
        main_bar.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self._main_bar_little_width = main_bar.sizeHint().width()
        
        main_bar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._main_bar_large_width = main_bar.sizeHint().width()
        
        self._resize_later()
    
    @pyqtSlot(QPoint)
    def _menu_asked(self, point: QPoint):
        context_actions = self._make_context_actions()
        menu = self._make_context_menu(context_actions)
        
        act_text_with_icons = QAction(
            QIcon.fromTheme('format-text-direction-symbolic'),
            _translate('tool_bar', 'Display text beside icons'))
        act_text_with_icons.setCheckable(True)
        act_text_with_icons.setChecked(
            self._text_with_icons is TextWithIcons.YES)

        menu.addSeparator()
        menu.addAction(act_text_with_icons)
        
        selected_act = menu.exec(point)
        if selected_act is None:
            return

        if selected_act is act_text_with_icons:
            if act_text_with_icons.isChecked():
                self._text_with_icons = TextWithIcons.YES
            else:
                self._text_with_icons = TextWithIcons.NO

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

    def _get_toolbars_layout(
            self, width: int, text_icons=TextWithIcons.AUTO) -> str:
        if self.tbars is None:
            return ''
        
        tbar_widths = [b.needed_width() for b in self.tbars]
        if text_icons is TextWithIcons.NO:
            tbar_widths[TBar.MAIN] = self._main_bar_little_width
        elif text_icons is TextWithIcons.YES:
            tbar_widths[TBar.MAIN] = self._main_bar_large_width
        
        m, t, j, c = tbar_widths
        # Main, Transport, Jack, Canvas
        # '_' for toolbarBreak (new line)

        if self._jack_agnostic is JackAgnostic.FULL:
            if width >= m + c:
                return 'MC'
            return 'M_C'
        
        if width >= sum(tbar_widths):
            return 'MCTJ'

        if width >= m + t + j:
            return 'MTJ_C'
        
        if width >= m + j:
            if width >= t + c:
                return 'MJ_CT'
            return 'MJ_T_C'
        
        if width >= c + t + j:
            return 'M_TJC'
        
        if width >= t + j:
            return 'M_TJ_C'
        
        if width >= t + c:
            return 'M_J_CT'
        
        return 'M_J_T_C'

    def main_win_resize(self, main_win: QMainWindow):
        if self.tbars is None:
            return
        
        self._last_win_width = main_win.width()
        
        if self._text_with_icons is TextWithIcons.AUTO:
            layout_little = self._get_toolbars_layout(
                self._last_win_width, TextWithIcons.NO)
            layout_large = self._get_toolbars_layout(
                self._last_win_width, TextWithIcons.YES)
            little_lines = len(layout_little.split('_'))
            large_lines = len(layout_large.split('_'))
            if little_lines < large_lines:
                layout = layout_little
                self.tbars[TBar.MAIN].setToolButtonStyle(
                    Qt.ToolButtonIconOnly)
            else:
                layout = layout_large
                if self._main_bar_large_width < self._last_win_width:
                    self.tbars[TBar.MAIN].setToolButtonStyle(
                        Qt.ToolButtonTextBesideIcon)
                else:
                    self.tbars[TBar.MAIN].setToolButtonStyle(
                        Qt.ToolButtonIconOnly)

        elif self._text_with_icons is TextWithIcons.YES:
            if (self._main_bar_large_width
                    > self._last_win_width):
                self.tbars[TBar.MAIN].setToolButtonStyle(
                    Qt.ToolButtonIconOnly)
            else:
                self.tbars[TBar.MAIN].setToolButtonStyle(
                    Qt.ToolButtonTextBesideIcon)
            layout = self._get_toolbars_layout(self._last_win_width)
        
        else:
            self.tbars[TBar.MAIN].setToolButtonStyle(
                Qt.ToolButtonIconOnly)
            layout = self._get_toolbars_layout(self._last_win_width)
            

        if (layout == self._last_layout):
            self._arrange_tool_bars()
            return
        
        self._last_layout = layout
        
        # add/remove spacer at right of canvas bar widget
        if self._canvas_wg is not None:
            self._canvas_wg.set_at_end_of_line(
                self._canvas_is_last_of_line(self._last_layout))
        
        self._arrange_tool_bars()
        
        visibles = [t.isVisible() for t in self.tbars]
        if (self._first_resize_done
                and visibles == [False, False, False, False]):
            return

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
        
        self._first_resize_done = True

    def _arrange_tool_bars(self):
        tbar_widths = [b.needed_width() for b in self.tbars]
        m, t, j, c = tbar_widths

        if self._last_layout in ('MCTJ', 'M_CTJ', 'MJ_CT'):            
            diff = self._last_win_width - t - c
            if self._last_layout in ('MCTJ', 'M_CTJ'):
                diff -= j
            if self._last_layout == 'MCTJ':
                diff -= m

            if diff > 0:
                self.tbars[TBar.CANVAS].set_min_width(c + int(diff * 1.0))
            else:
                for tbar in self.tbars:
                    tbar.set_min_width(None)
                    
        elif self._last_layout in ('MTJ_C', 'M_TJ_C'):
            diff = self._last_win_width - t - j
            if self._last_layout == 'MTJ_C':
                diff -= m
            
            if diff > 0:
                self.tbars[TBar.TRANSPORT].set_min_width(t + diff)
            else:
                for tbar in self.tbars:
                    tbar.set_min_width(None)

        else:
            for tbar in self.tbars:
                tbar.set_min_width(None)
        
        