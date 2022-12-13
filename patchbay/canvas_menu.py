
from typing import TYPE_CHECKING
from PyQt5.QtGui import QIcon, QDesktopServices
from PyQt5.QtWidgets import QMenu, QApplication
from PyQt5.QtCore import QLocale, QUrl

from . import patchcanvas
from .base_elements import PortType, PortTypesViewFlag

if TYPE_CHECKING:
    from .patchbay_manager import PatchbayManager

_translate = QApplication.translate


class CanvasMenu(QMenu):
    def __init__(self, patchbay_manager: 'PatchbayManager'):
        QMenu.__init__(self, _translate('patchbay', 'Patchbay'))
        self.patchbay_manager = patchbay_manager

        # fix wrong menu position with Wayland,
        # see https://community.kde.org/Guidelines_and_HOWTOs/Wayland_Porting_Notes
        self.winId()
        main_win = self.patchbay_manager.main_win
        main_win.winId()
        parent_window_handle = main_win.windowHandle()
        if not parent_window_handle:
            native_parent_widget = main_win.nativeParentWidget()
            if native_parent_widget:
                parent_window_handle = native_parent_widget.windowHandle()
        self.windowHandle().setTransientParent(parent_window_handle)

        self.patchbay_manager.sg.port_types_view_changed.connect(
            self._port_types_view_changed)

        self.action_fullscreen = self.addAction(
            _translate('patchbay', "Toggle Full Screen"))
        self.action_fullscreen.setIcon(QIcon.fromTheme('view-fullscreen'))
        self.action_fullscreen.triggered.connect(
            patchbay_manager.sg.full_screen_toggle_wanted.emit)

        port_types_view = patchbay_manager.port_types_view & (
            PortType.AUDIO_JACK | PortType.MIDI_JACK)

        self.action_find_box = self.addAction(
            _translate('patchbay', "Find a box...\tCtrl+F"))
        self.action_find_box.setIcon(QIcon.fromTheme('edit-find'))
        self.action_find_box.triggered.connect(
            patchbay_manager.sg.filters_bar_toggle_wanted.emit)

        self.port_types_menu = QMenu(_translate('patchbay', 'Type filter'), self)
        self.port_types_menu.setIcon(QIcon.fromTheme('view-filter'))
        self.action_audio_midi = self.port_types_menu.addAction(
            _translate('patchbay', 'Audio | Midi | CV'))
        self.action_audio_midi.setCheckable(True)
        self.action_audio_midi.setChecked(
            bool(port_types_view is PortTypesViewFlag.ALL))
        self.action_audio_midi.triggered.connect(
            self.port_types_view_audio_midi_choice)

        self.action_audio = self.port_types_menu.addAction(
            _translate('patchbay', 'Audio only'))
        self.action_audio.setCheckable(True)
        self.action_audio.setChecked(port_types_view is PortTypesViewFlag.AUDIO)
        self.action_audio.triggered.connect(
            self.port_types_view_audio_choice)

        self.action_midi = self.port_types_menu.addAction(
            _translate('patchbay', 'MIDI only'))
        self.action_midi.setCheckable(True)
        self.action_midi.setChecked(port_types_view is PortTypesViewFlag.MIDI)
        self.action_midi.triggered.connect(
            self.port_types_view_midi_choice)
        
        self.action_cv = self.port_types_menu.addAction(
            _translate('patchbay', 'CV only'))
        self.action_cv.setCheckable(True)
        self.action_cv.setChecked(port_types_view is PortTypesViewFlag.CV)
        self.action_cv.triggered.connect(
            self.port_types_view_midi_choice)

        self.addMenu(self.port_types_menu)

        self.zoom_menu = QMenu(_translate('patchbay', 'Zoom'), self)
        self.zoom_menu.setIcon(QIcon.fromTheme('zoom'))

        self.autofit = self.zoom_menu.addAction(
            _translate('patchbay', 'auto-fit'))
        self.autofit.setIcon(QIcon.fromTheme('zoom-select-fit'))
        self.autofit.setShortcut('Home')
        self.autofit.triggered.connect(patchcanvas.canvas.scene.zoom_fit)

        self.zoom_in = self.zoom_menu.addAction(
            _translate('patchbay', 'Zoom +'))
        self.zoom_in.setIcon(QIcon.fromTheme('zoom-in'))
        self.zoom_in.setShortcut('Ctrl++')
        self.zoom_in.triggered.connect(patchcanvas.canvas.scene.zoom_in)

        self.zoom_out = self.zoom_menu.addAction(
            _translate('patchbay', 'Zoom -'))
        self.zoom_out.setIcon(QIcon.fromTheme('zoom-out'))
        self.zoom_out.setShortcut('Ctrl+-')
        self.zoom_out.triggered.connect(patchcanvas.canvas.scene.zoom_out)

        self.zoom_orig = self.zoom_menu.addAction(
            _translate('patchbay', 'Default Zoom'))
        self.zoom_orig.setIcon(QIcon.fromTheme('zoom'))
        self.zoom_orig.setShortcut('Ctrl+1')
        self.zoom_orig.triggered.connect(patchcanvas.canvas.scene.zoom_reset)

        self.addMenu(self.zoom_menu)

        self.action_refresh = self.addAction(
            _translate('patchbay', "Refresh the canvas\tCtrl+R"))
        self.action_refresh.setIcon(QIcon.fromTheme('view-refresh'))
        self.action_refresh.triggered.connect(patchbay_manager.refresh)

        self.action_arrange = self.addAction(
            _translate('patchbay', 'Auto-Arrange'))
        self.action_arrange.setIcon(QIcon.fromTheme('auto-transition'))
        self.action_arrange.triggered.connect(patchbay_manager.arrange_canvas)

        self.action_manual = self.addAction(
            _translate('patchbay', "Patchbay manual"))
        self.action_manual.setIcon(QIcon.fromTheme('system-help'))
        self.action_manual.triggered.connect(self.internal_manual)
        self.action_manual.setVisible(
            self.patchbay_manager._manual_path is not None)

        self.action_options = self.addAction(
            _translate('patchbay', "Canvas options"))
        self.action_options.setIcon(QIcon.fromTheme("configure"))
        self.action_options.triggered.connect(
            patchbay_manager.show_options_dialog)

    def _port_types_view_changed(self, port_types_view: int):
        self.action_audio_midi.setChecked(
            port_types_view == PortTypesViewFlag.AUDIO | PortTypesViewFlag.MIDI)
        self.action_audio.setChecked(
            port_types_view == PortTypesViewFlag.AUDIO)
        self.action_midi.setChecked(
            port_types_view == PortTypesViewFlag.MIDI)

    def port_types_view_audio_midi_choice(self):
        self.patchbay_manager.change_port_types_view(
            PortTypesViewFlag.ALL)

    def port_types_view_audio_choice(self):
        self.patchbay_manager.change_port_types_view(
            PortTypesViewFlag.AUDIO)

    def port_types_view_midi_choice(self):
        self.patchbay_manager.change_port_types_view(
            PortTypesViewFlag.MIDI)

    def port_types_view_cv_choice(self):
        self.patchbay_manager.change_port_types_view(
            PortTypesViewFlag.CV)

    def internal_manual(self):
        short_locale = 'en'
        manual_dir = self.patchbay_manager._manual_path
        if manual_dir is None:
            return        
        
        locale_str = QLocale.system().name()
        html_path = manual_dir / locale_str[:2] / 'manual.html'
        
        if (len(locale_str) > 2 and '_' in locale_str
                and html_path.is_file()):
            short_locale = locale_str[:2]

        url = QUrl(f"file://{manual_dir}/{short_locale}/manual.html")
        QDesktopServices.openUrl(url)
