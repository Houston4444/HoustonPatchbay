
from typing import TYPE_CHECKING

from qtpy.QtGui import QIcon, QDesktopServices, QPixmap
from qtpy.QtWidgets import QMenu, QApplication
from qtpy.QtCore import QLocale, QUrl, Slot # type:ignore

from .. import patchcanvas
from ..patchcanvas import utils
from patshared import PortTypesViewFlag, PortMode
from .views_menu import ViewsMenu
from .selected_boxes_menu import SelectedBoxesMenu
from ..cancel_mng import CancelOp, CancellableAction

if TYPE_CHECKING:
    from ..patchbay_manager import PatchbayManager


_translate = QApplication.translate


class CanvasMenu(QMenu):
    def __init__(self, patchbay_manager: 'PatchbayManager'):
        QMenu.__init__(self, _translate('patchbay', 'Patchbay'))
        self.mng = patchbay_manager

        # fix wrong menu position with Wayland,
        # see https://community.kde.org/Guidelines_and_HOWTOs/Wayland_Porting_Notes
        self.winId()
        main_win = self.mng.main_win
        if main_win is None:
            return
        
        main_win.winId()
        parent_window_handle = main_win.windowHandle()
        if not parent_window_handle:
            native_parent_widget = main_win.nativeParentWidget()
            if native_parent_widget:
                parent_window_handle = native_parent_widget.windowHandle()
        self.windowHandle().setTransientParent(parent_window_handle)

        self.mng.sg.port_types_view_changed.connect(
            self._port_types_view_changed)
        self.mng.sg.alsa_midi_enabled_changed.connect(
            self._alsa_midi_enabled)

        self._selected_boxes = dict[int, PortMode]()
        self._scene_pos = (0, 0)
        self._build()
        
    def _build(self):
        self.clear()
        
        if self._selected_boxes:
            self.selected_boxes_menu = SelectedBoxesMenu(self)
            self.selected_boxes_menu.set_patchbay_manager(self.mng)
            self.selected_boxes_menu.set_selected_boxes(self._selected_boxes)
            self.addMenu(self.selected_boxes_menu)
            self.addSeparator()

        self.action_fullscreen = self.addAction(
            _translate('patchbay', "Toggle Full Screen"))
        self.action_fullscreen.setIcon(QIcon.fromTheme('view-fullscreen'))
        self.action_fullscreen.triggered.connect(
            self.mng.sg.full_screen_toggle_wanted.emit)

        port_types_view = self.mng.port_types_view

        self.action_find_box = self.addAction(
            _translate('patchbay', "Find a box...\tCtrl+F"))
        self.action_find_box.setIcon(QIcon.fromTheme('edit-find'))
        self.action_find_box.triggered.connect(
            self.mng.sg.filters_bar_toggle_wanted.emit)

        self.show_hiddens_menu = QMenu(
            _translate('patchbay', 'Show hidden boxes'), self)
        self.show_hiddens_menu.setIcon(QIcon.fromTheme('show_table_row'))
        self.show_hiddens_menu.aboutToShow.connect(self._list_hidden_groups)
        self.addMenu(self.show_hiddens_menu)

        menu_arrange = QMenu(_translate('views_menu', 'Arrange'), self)
        menu_arrange.setIcon(QIcon.fromTheme('code-block'))

        act_arrange_signal = menu_arrange.addAction(
            "%s\tCtrl+Alt+A" %
                _translate('views_menu', 'Follow the signal chain'))
        act_arrange_signal.triggered.connect(self._arrange_follow_signal)
        
        act_arrange_facing = menu_arrange.addAction(
            "%s\tCtrl+Alt+Q" %
                _translate('views_menu', 'Two columns facing each other'))
        act_arrange_facing.triggered.connect(self._arrange_facing)

        self.addMenu(menu_arrange)

        self.views_menu = ViewsMenu(self, self.mng)
        self.addMenu(self.views_menu)

        self.port_types_menu = QMenu(_translate('patchbay', 'Type filter'), self)
        self.port_types_menu.setIcon(QIcon.fromTheme('view-filter'))
        self.action_all_types = self.port_types_menu.addAction(
            _translate('patchbay', 'AUDIO | MIDI | CV'))
        self.action_all_types.setCheckable(True)
        self.action_all_types.setChecked(
            bool(port_types_view is PortTypesViewFlag.ALL))
        self.action_all_types.triggered.connect(
            self.port_types_view_all_types_choice)

        self.action_audio = self.port_types_menu.addAction(
            _translate('patchbay', 'AUDIO only'))
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
            self.port_types_view_cv_choice)

        self.action_alsa = self.port_types_menu.addAction(
            _translate('patchbay', 'ALSA only'))
        self.action_alsa.setCheckable(True)
        self.action_alsa.setChecked(port_types_view is PortTypesViewFlag.ALSA)
        self.action_alsa.triggered.connect(
            self.port_types_view_alsa_choice)

        self.addMenu(self.port_types_menu)

        self._alsa_midi_enabled(self.mng.alsa_midi_enabled)

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
        self.action_refresh.triggered.connect(self.mng.refresh)

        self.action_manual = self.addAction(
            _translate('patchbay', "Patchbay manual"))
        self.action_manual.setIcon(QIcon.fromTheme('system-help'))
        self.action_manual.triggered.connect(self.internal_manual)
        self.action_manual.setVisible(
            self.mng._manual_path is not None)

        self.action_options = self.addAction(
            _translate('patchbay', "Canvas options"))
        self.action_options.setIcon(QIcon.fromTheme("configure"))
        self.action_options.triggered.connect(
            self.mng.show_options_dialog)

    def remember_scene_pos(self, x: float, y: float):
        self._scene_pos = (int(x), int(y))

    def set_selected_boxes(self, selected_boxes: dict[int, PortMode]):
        self._selected_boxes = selected_boxes
    
    @Slot()
    def _new_exclusive_view(self):
        self.mng.new_view(exclusive_with=self._selected_boxes)
        patchcanvas.clear_selection()
    
    @Slot()
    def _hide_selected_boxes(self):
        for group_id, port_mode in self._selected_boxes.items():
            group = self.mng.get_group_from_id(group_id)
            if group is None:
                continue

            group.hide(port_mode)

    @Slot()
    def _invert_boxes_selection(self):
        patchcanvas.invert_boxes_selection()

    @Slot()
    def _arrange_facing(self):
        self.mng.arrange_face_to_face()

    @Slot()
    def _arrange_follow_signal(self):
        self.mng.arrange_follow_signal()

    def _port_types_view_changed(self, port_types_view: int):
        self.action_all_types.setChecked(
            port_types_view == PortTypesViewFlag.ALL)
        self.action_audio.setChecked(
            port_types_view == PortTypesViewFlag.AUDIO)
        self.action_midi.setChecked(
            port_types_view == PortTypesViewFlag.MIDI)
        self.action_cv.setChecked(
            port_types_view == PortTypesViewFlag.CV)
        self.action_alsa.setChecked(
            port_types_view == PortTypesViewFlag.ALSA)

    def _change_ptv(self, ptv: PortTypesViewFlag):
        with CancellableAction(self.mng, CancelOp.PTV_CHOICE) as a:
            a.name = _translate(
                'undo', 'Change visible port types from %s to %s') \
                    % (self.mng.port_types_view.name, ptv.name)
            self.mng.change_port_types_view(ptv)

    @Slot()
    def port_types_view_all_types_choice(self):
        self._change_ptv(PortTypesViewFlag.ALL)

    @Slot()
    def port_types_view_audio_choice(self):
        self._change_ptv(PortTypesViewFlag.AUDIO)

    @Slot()
    def port_types_view_midi_choice(self):
        self._change_ptv(PortTypesViewFlag.MIDI)

    Slot()
    def port_types_view_cv_choice(self):
        self._change_ptv(PortTypesViewFlag.CV)

    Slot()
    def port_types_view_alsa_choice(self):
        self._change_ptv(PortTypesViewFlag.ALSA)

    def _alsa_midi_enabled(self, yesno: bool):
        self.action_alsa.setVisible(yesno)
        if yesno:
            self.action_all_types.setText(
                _translate('patchbay', 'AUDIO | MIDI | CV | ALSA'))
        else:
            self.action_all_types.setText(
                _translate('patchbay', 'AUDIO | MIDI | CV'))

    @Slot()
    def _list_hidden_groups(self):
        self.show_hiddens_menu.clear()
        
        dark = utils.is_dark_theme(self)
        has_hiddens = False
        
        for group in self.mng.groups:
            hidden_port_mode = group.current_position.hidden_port_modes()
            if hidden_port_mode:
                if not ((group.outs_ptv & self.mng.port_types_view
                            and PortMode.OUTPUT in hidden_port_mode)
                         or (group.ins_ptv & self.mng.port_types_view
                            and PortMode.INPUT in hidden_port_mode)):
                    continue
                
                group_act = self.show_hiddens_menu.addAction(
                    group.cnv_name)
                group_act.setIcon(utils.get_icon(
                        group.cnv_box_type, group.cnv_icon_name,
                        hidden_port_mode,
                        dark=dark))
                group_act.setData(group.group_id)
                group_act.triggered.connect(self._show_hidden_group)
                has_hiddens = True
        
        self.show_hiddens_menu.addSeparator()
        
        color_scheme = 'breeze-dark' if dark else 'breeze'
        act_white_list = self.show_hiddens_menu.addAction(
            QIcon(QPixmap(
                f':scalable/{color_scheme}/color-picker-white.svg')),
                _translate('hiddens_indicator', 'Hide all new boxes'))
        act_white_list.setCheckable(True)
        act_white_list.setChecked(
            self.mng.view().is_white_list)
        act_white_list.triggered.connect(self._set_view_white_list)
        
        if not has_hiddens:
            for gpos in self.mng.views.iter_group_poses(
                    view_num=self.mng.view_number):
                if gpos.hidden_port_modes() is not PortMode.NULL:
                    has_hiddens = True
                    break

        if has_hiddens:
            self.show_hiddens_menu.addSeparator()
            display_all_act = self.show_hiddens_menu.addAction(
                _translate('patchbay', 'Display all boxes'))
            display_all_act.setIcon(QIcon.fromTheme('show_table_row'))
            display_all_act.triggered.connect(
                self._show_all_hidden_groups)
        else:
            no_hiddens_act = self.show_hiddens_menu.addAction(
                _translate('patchbay', 'All boxes are visible.'))
            no_hiddens_act.setEnabled(False)

    @Slot()
    def _show_hidden_group(self):
        group_id: int = self.sender().data() # type:ignore
        sender_text: str = self.sender().text() # type:ignore
        with CancellableAction(self.mng, CancelOp.VIEW) as a:
            a.name = _translate('undo', 'Restore "%s"') % sender_text
            self.mng.restore_group_hidden_sides(group_id, self._scene_pos)
    
    @Slot()
    def _show_all_hidden_groups(self):
        sender_text: str = self.sender().text() # type:ignore
        with CancellableAction(self.mng, CancelOp.VIEW) as a:
            a.name = sender_text
            self.mng.restore_all_group_hidden_sides()
    
    @Slot(bool)
    def _set_view_white_list(self, state: bool):
        sender_text: str = self.sender().text() # type:ignore
        with CancellableAction(self.mng, op_type=CancelOp.VIEW) as a:
            a.name = sender_text
            self.mng.view().is_white_list = state
            self.mng.set_views_changed()

    def internal_manual(self):
        short_locale = 'en'
        manual_dir = self.mng._manual_path
        if manual_dir is None:
            return        
        
        locale_str = QLocale.system().name()
        html_path = manual_dir / locale_str[:2] / 'manual.html'
        
        if (len(locale_str) > 2 and '_' in locale_str
                and html_path.is_file()):
            short_locale = locale_str[:2]

        url = QUrl(f"file://{manual_dir}/{short_locale}/manual.html")
        QDesktopServices.openUrl(url)

    def showEvent(self, event):
        self._build()
        super().showEvent(event)