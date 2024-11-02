
from typing import TYPE_CHECKING

from PyQt5.QtWidgets import QFrame, QApplication


from .base_elements import PortTypesViewFlag
from .cancel_mng import CancelOp, CancellableAction

from .ui.type_filter_frame import Ui_FrameTypesFilter

if TYPE_CHECKING:
    from patchbay_manager import PatchbayManager


_translate = QApplication.translate


class TypeFilterFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_FrameTypesFilter()
        self.ui.setupUi(self)
        
        self.ui.checkBoxAudioFilter.really_clicked.connect(
            self._check_box_audio_right_clicked)
        self.ui.checkBoxMidiFilter.really_clicked.connect(
            self._check_box_midi_right_clicked)
        self.ui.checkBoxCvFilter.really_clicked.connect(
            self._check_box_cv_right_clicked)
        self.ui.checkBoxAlsaFilter.really_clicked.connect(
            self._check_box_alsa_right_clicked)
        
        self._mng = None
    
    def set_patchbay_manager(self, manager: 'PatchbayManager'):
        self._mng = manager
        self._mng.sg.port_types_view_changed.connect(
            self._port_types_view_changed)
        self._port_types_view_changed(self._mng.port_types_view)
    
    def _change_port_types_view(self):
        if self._mng is None:
            return
        
        audio_checked = self.ui.checkBoxAudioFilter.isChecked()
        midi_checked = self.ui.checkBoxMidiFilter.isChecked()
        cv_checked = self.ui.checkBoxCvFilter.isChecked()
        alsa_checked = self.ui.checkBoxAlsaFilter.isChecked()
        
        port_types_view = PortTypesViewFlag.NONE

        if audio_checked:
            port_types_view |= PortTypesViewFlag.AUDIO
        if midi_checked:
            port_types_view |= PortTypesViewFlag.MIDI
        if cv_checked:
            port_types_view |= PortTypesViewFlag.CV
        if self._mng.alsa_midi_enabled and alsa_checked:
            port_types_view |= PortTypesViewFlag.ALSA

        # if all visible checkboxes are checked
        # we consider port types view as PortTypesViewFlag.ALL
        with_video = port_types_view | PortTypesViewFlag.VIDEO
        if self._mng.alsa_midi_enabled:
            if with_video is PortTypesViewFlag.ALL:
                port_types_view = PortTypesViewFlag.ALL
        else:
            if with_video | PortTypesViewFlag.ALSA is PortTypesViewFlag.ALL:
                port_types_view = PortTypesViewFlag.ALL

        if port_types_view is PortTypesViewFlag.NONE:
            # if no visible checkbox is checked, 
            # invert the port types selection.
            port_types_view = PortTypesViewFlag.ALL
            port_types_view &= ~self._mng.port_types_view
            port_types_view &= ~PortTypesViewFlag.VIDEO
            if not self._mng.alsa_midi_enabled:
                port_types_view &= ~PortTypesViewFlag.ALSA
        
        self._change_mng_port_types_view(port_types_view)
    
    def _change_mng_port_types_view(self, port_types_view: PortTypesViewFlag):
        if self._mng is None:
            return

        with CancellableAction(self._mng, CancelOp.ALL_VIEWS_NO_POS) as a:
            a.name = _translate('undo', 'Change visible port types to %s') \
                % port_types_view.name
            self._mng.change_port_types_view(port_types_view)
    
    def _exclusive_choice(self, view_flag: PortTypesViewFlag):
        if self._mng is None:
            return
        
        if self._mng.port_types_view is view_flag:
            self._change_mng_port_types_view(PortTypesViewFlag.ALL)
        else:
            self._change_mng_port_types_view(view_flag)
    
    def _check_box_audio_right_clicked(self, alternate: bool):
        if alternate:
            self._exclusive_choice(PortTypesViewFlag.AUDIO)
            return
        
        self.ui.checkBoxAudioFilter.setChecked(
            not self.ui.checkBoxAudioFilter.isChecked())
        self._change_port_types_view()
    
    def _check_box_midi_right_clicked(self, alternate: bool):
        if alternate:
            self._exclusive_choice(PortTypesViewFlag.MIDI)
            return
        
        self.ui.checkBoxMidiFilter.setChecked(
            not self.ui.checkBoxMidiFilter.isChecked())
        self._change_port_types_view()
    
    def _check_box_cv_right_clicked(self, alternate: bool):
        if alternate:
            self._exclusive_choice(PortTypesViewFlag.CV)
            return
        
        self.ui.checkBoxCvFilter.setChecked(
            not self.ui.checkBoxCvFilter.isChecked())
        self._change_port_types_view()
    
    def _check_box_alsa_right_clicked(self, alternate: bool):
        if alternate:
            self._exclusive_choice(PortTypesViewFlag.ALSA)
            return

        self.ui.checkBoxAlsaFilter.setChecked(
            not self.ui.checkBoxAlsaFilter.isChecked())
        self._change_port_types_view()
    
    def _port_types_view_changed(self, port_types_view: int):
        self.ui.checkBoxAlsaFilter.setVisible(
            self._mng.alsa_midi_enabled)

        self.ui.checkBoxAudioFilter.setChecked(
            bool(port_types_view & PortTypesViewFlag.AUDIO))
        self.ui.checkBoxMidiFilter.setChecked(
            bool(port_types_view & PortTypesViewFlag.MIDI))
        self.ui.checkBoxCvFilter.setChecked(
            bool(port_types_view & PortTypesViewFlag.CV))
        self.ui.checkBoxAlsaFilter.setChecked(
            bool(port_types_view & PortTypesViewFlag.ALSA))
        