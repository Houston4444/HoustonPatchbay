
from types import NoneType
from typing import Union

from PyQt5.QtWidgets import (
    QToolBar, QLabel, QMenu,
    QApplication, QAction, QWidget, QBoxLayout)
from PyQt5.QtGui import QMouseEvent, QIcon, QResizeEvent
from PyQt5.QtCore import Qt, QPoint, pyqtSignal

from .bar_widget_canvas import BarWidgetCanvas
from .bar_widget_jack import BarWidgetJack
from .bar_widget_transport import BarWidgetTransport
from .base_elements import ToolDisplayed
from .patchbay_manager import PatchbayManager
from .tools_widgets import JackAgnostic, PatchbayToolsWidget
from .surclassed_widgets import ToolsWidgetFrame

_translate = QApplication.translate

_displayed_widgets = (
    ToolDisplayed.ZOOM_SLIDER
    | ToolDisplayed.TRANSPORT_PLAY_STOP
    | ToolDisplayed.BUFFER_SIZE
    | ToolDisplayed.SAMPLERATE
    | ToolDisplayed.XRUNS
    | ToolDisplayed.DSP_LOAD)


class PatchbayToolBar(QToolBar):
    menu_asked = pyqtSignal(QPoint)
    
    def __init__(self, parent):
        super().__init__(parent)
        self.setContextMenuPolicy(Qt.PreventContextMenu)

        self._displayed_widgets = (
            ToolDisplayed.ZOOM_SLIDER
            | ToolDisplayed.TRANSPORT_PLAY_STOP
            | ToolDisplayed.BUFFER_SIZE
            | ToolDisplayed.SAMPLERATE
            | ToolDisplayed.XRUNS
            | ToolDisplayed.DSP_LOAD)
        
        self.mng : PatchbayManager = None
        self._tools_widget: PatchbayToolsWidget = None
    
    def set_patchbay_manager(self, patchbay_manager: PatchbayManager):
        self.mng = patchbay_manager
        self._tools_widget = patchbay_manager._tools_widget
        # self._tools_widget.ui.mainLayout.setDirection(
        #     QBoxLayout.TopToBottom)
        patchbay_manager.change_tools_displayed(_displayed_widgets)
    
    def _change_visibility(self):
        if self.mng is not None:
            self.mng.change_tools_displayed(_displayed_widgets)

    def set_default_displayed_widgets(self, displayed_widgets: ToolDisplayed):
        global _displayed_widgets
        _displayed_widgets = displayed_widgets
        self._change_visibility()
        
    def get_displayed_widgets(self) -> ToolDisplayed:
        return _displayed_widgets

    def _make_context_actions(self) -> dict[ToolDisplayed, QAction]:
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
        
        global _displayed_widgets
        if self.mng is not None:
            _displayed_widgets = self.mng._tools_displayed
        
        for key, act in context_actions.items():
            act.setCheckable(True)
            act.setChecked(bool(_displayed_widgets & key))
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

    def mousePressEvent(self, event: QMouseEvent) -> None:
        child_widget = self.childAt(event.pos())
        super().mousePressEvent(event)

        if self.mng is None:
            return

        if (event.button() != Qt.RightButton
                or not isinstance(
                    child_widget,
                    (QLabel, BarWidgetCanvas,
                     BarWidgetJack, BarWidgetTransport,
                     NoneType))):
            return

        context_actions = self._make_context_actions()
        menu = self._make_context_menu(context_actions)
        
        # execute the menu, exit if no action
        point = event.screenPos().toPoint()
        point.setY(self.mapToGlobal(QPoint(0, self.height())).y())
        
        self.menu_asked.emit(point)
        
        # selected_act = menu.exec(point)
        # if selected_act is None:
        #     return

        # global _displayed_widgets

        # for key, act in context_actions.items():
        #     if act is selected_act:
        #         if act.isChecked():
        #             _displayed_widgets |= key
        #         else:
        #             _displayed_widgets &= ~key

        # self._change_visibility()