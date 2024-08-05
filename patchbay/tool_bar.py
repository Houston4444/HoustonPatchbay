
from typing import Union

from PyQt5.QtWidgets import (
    QToolBar, QLabel, QMenu,
    QApplication, QAction, QWidget, QBoxLayout)
from PyQt5.QtGui import QMouseEvent, QIcon, QResizeEvent
from PyQt5.QtCore import Qt, QPoint, QTimer

from .base_elements import ToolDisplayed
from .patchbay_manager import PatchbayManager
from .tools_widgets import PatchbayToolsWidget

_translate = QApplication.translate


class PatchbayToolBar(QToolBar):
    _jack_width: int
    'width of the jack tools widgets (0 if not measured yet)'
    
    _canvas_width: int
    'width of the canvas tools widgets (0 if not measured yet)'
    
    _non_patchbay_width: int
    'width of the menu entries on top left (0 if not measured yet)'
    
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
        
        self._patchbay_mng : PatchbayManager = None
        self._tools_widget: PatchbayToolsWidget = None
        
        self._non_patchbay_width = 0
        self._canvas_width = 0
        self._jack_width = 0
    
    def set_patchbay_manager(self, patchbay_manager: PatchbayManager):
        self._patchbay_mng = patchbay_manager
        self._tools_widget = patchbay_manager._tools_widget
        self._tools_widget.ui.mainLayout.setDirection(
            QBoxLayout.TopToBottom)
        patchbay_manager.change_tools_displayed(self._displayed_widgets)
    
    def _change_visibility(self):
        if self._patchbay_mng is not None:
            # before to change the widgets visibility, 
            # we set the display in two lines,
            # else, the single line can be too long and all the patchbay tools
            # are hidden.
            self._tools_widget.ui.mainLayout.setDirection(
                QBoxLayout.TopToBottom)
            self._patchbay_mng.change_tools_displayed(self._displayed_widgets)

        self._jack_width = 0
        self._canvas_width = 0
        
        self._check_layout()

    def set_default_displayed_widgets(self, displayed_widgets: ToolDisplayed):
        self._displayed_widgets = displayed_widgets
        self._change_visibility()
        
    def get_displayed_widgets(self) -> ToolDisplayed:
        return self._displayed_widgets

    def _make_context_actions(self) -> dict[ToolDisplayed, QAction]:
        return {
            ToolDisplayed.VIEWS_SELECTOR:
                QAction(QIcon.fromTheme('view-multiple-objects'),
                        _translate('tool_bar', 'Views selector')),
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

    def _make_context_menu(self, context_actions: dict[ToolDisplayed, QAction]) -> QMenu:
        menu = QMenu()
        menu.addSection(_translate('tool_bar', 'Displayed tools'))
        
        for key, act in context_actions.items():
            act.setCheckable(True)
            act.setChecked(bool(self._displayed_widgets & key))
            if self._patchbay_mng is not None:
                if not self._patchbay_mng.server_is_started:
                    if key in (ToolDisplayed.PORT_TYPES_VIEW, ToolDisplayed.ZOOM_SLIDER):
                        act.setEnabled(self._patchbay_mng.alsa_midi_enabled)
                    else:
                        act.setEnabled(False)
            menu.addAction(act)
            
            if key is ToolDisplayed.ZOOM_SLIDER:
                menu.addSeparator()
            
        return menu

    def mousePressEvent(self, event: QMouseEvent) -> None:
        child_widget = self.childAt(event.pos())
        super().mousePressEvent(event)

        if (event.button() != Qt.RightButton
                or not isinstance(child_widget, (QLabel, PatchbayToolsWidget))):
            return

        context_actions = self._make_context_actions()
        menu = self._make_context_menu(context_actions)
        
        # execute the menu, exit if no action
        point = event.screenPos().toPoint()
        point.setY(self.mapToGlobal(QPoint(0, self.height())).y())
        selected_act = menu.exec(point)
        if selected_act is None:
            return

        for key, act in context_actions.items():
            if act is selected_act:
                if act.isChecked():
                    self._displayed_widgets |= key
                else:
                    self._displayed_widgets &= ~key

        self._change_visibility()
        
    def _check_layout(self):
        if self._tools_widget is None:
            return
        
        if self._tools_widget._jack_agnostic:
            self._tools_widget.ui.mainLayout.setDirection(
                QBoxLayout.RightToLeft)
            return
        
        if self._canvas_width == 0 or self._jack_width == 0:
            self._canvas_width, self._jack_width = \
                self._tools_widget.get_layout_widths()
        
        if self._non_patchbay_width == 0:
            if (self._tools_widget.ui.mainLayout.direction()
                    in (QBoxLayout.LeftToRight, QBoxLayout.RightToLeft)):
                self._non_patchbay_width = (
                    self.sizeHint().width()
                    - self._canvas_width - self._jack_width)
            else:
                self._non_patchbay_width = (
                    self.sizeHint().width()
                    - max(self._canvas_width, self._jack_width))

        large_width = (self._non_patchbay_width
                       + self._canvas_width + self._jack_width)

        if self.width() >= large_width:
            self._tools_widget.ui.mainLayout.setDirection(
                QBoxLayout.RightToLeft)
        else:
            self._tools_widget.ui.mainLayout.setDirection(
                QBoxLayout.TopToBottom)
    
    def widgetForAction(
            self, action: QAction) -> Union[QWidget, 'PatchbayToolsWidget']:
        return super().widgetForAction(action)
    
    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self._check_layout()
        
        
