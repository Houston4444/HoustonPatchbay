
from typing import TYPE_CHECKING

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame

from .base_elements import PortTypesViewFlag

from .ui.type_filter_frame import Ui_FrameTypesFilter

if TYPE_CHECKING:
    from patchbay_manager import PatchbayManager


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
        
        self._patchbay_mng = None
    
    def set_patchbay_manager(self, manager: 'PatchbayManager'):
        self._patchbay_mng = manager
        self._patchbay_mng.sg.port_types_view_changed.connect(
            self._port_types_view_changed)
        self._port_types_view_changed(self._patchbay_mng.port_types_view)
    
    def _change_port_types_view(self):
        if self._patchbay_mng is None:
            return
        
        audio_checked = self.ui.checkBoxAudioFilter.isChecked()
        midi_checked = self.ui.checkBoxMidiFilter.isChecked()
        cv_checked = self.ui.checkBoxCvFilter.isChecked()
        alsa_checked = self.ui.checkBoxAlsaFilter.isChecked()
        
        port_types_view = PortTypesViewFlag.NONE

        if audio_checked and midi_checked and cv_checked and alsa_checked:
            port_types_view = PortTypesViewFlag.ALL
        else:
            if audio_checked:
                port_types_view |= PortTypesViewFlag.AUDIO
            if midi_checked:
                port_types_view |= PortTypesViewFlag.MIDI
            if cv_checked:
                port_types_view |= PortTypesViewFlag.CV
            if alsa_checked:
                port_types_view |= PortTypesViewFlag.ALSA
                
        if port_types_view is PortTypesViewFlag.NONE:
            if self._patchbay_mng.port_types_view is PortTypesViewFlag.AUDIO:
                port_types_view = (
                    PortTypesViewFlag.MIDI | PortTypesViewFlag.CV | PortTypesViewFlag.ALSA)
            elif self._patchbay_mng.port_types_view is PortTypesViewFlag.MIDI:
                port_types_view = (
                    PortTypesViewFlag.AUDIO | PortTypesViewFlag.CV | PortTypesViewFlag.ALSA)
            elif self._patchbay_mng.port_types_view is PortTypesViewFlag.CV:
                port_types_view = (
                    PortTypesViewFlag.AUDIO | PortTypesViewFlag.MIDI | PortTypesViewFlag.ALSA) 
            elif self._patchbay_mng.port_types_view is PortTypesViewFlag.ALSA:
                port_types_view = (
                    PortTypesViewFlag.AUDIO | PortTypesViewFlag.MIDI | PortTypesViewFlag.CV)
        
        self._patchbay_mng.change_port_types_view(port_types_view)
    
    def _exclusive_choice(self, view_flag: PortTypesViewFlag):
        if self._patchbay_mng is None:
            return
        
        if self._patchbay_mng.port_types_view is view_flag:
            self._patchbay_mng.change_port_types_view(PortTypesViewFlag.ALL)
        else:
            self._patchbay_mng.change_port_types_view(view_flag)
    
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
        self.ui.checkBoxAudioFilter.setChecked(
            bool(port_types_view & PortTypesViewFlag.AUDIO))
        self.ui.checkBoxMidiFilter.setChecked(
            bool(port_types_view & PortTypesViewFlag.MIDI))
        self.ui.checkBoxCvFilter.setChecked(
            bool(port_types_view & PortTypesViewFlag.CV))
        self.ui.checkBoxAlsaFilter.setChecked(
            bool(port_types_view & PortTypesViewFlag.ALSA))
        