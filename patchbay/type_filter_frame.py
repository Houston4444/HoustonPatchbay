
from typing import TYPE_CHECKING
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
        
        self.ui.checkBoxAudioFilter.stateChanged.connect(
            self._check_box_audio_checked)
        self.ui.checkBoxMidiFilter.stateChanged.connect(
            self._check_box_midi_checked)
        self.ui.checkBoxCvFilter.stateChanged.connect(
            self._check_box_cv_checked)
        
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
        
        port_types_view = PortTypesViewFlag.NONE

        if audio_checked and midi_checked and cv_checked:
            port_types_view = PortTypesViewFlag.ALL
        else:
            if audio_checked:
                port_types_view |= PortTypesViewFlag.AUDIO
            if midi_checked:
                port_types_view |= PortTypesViewFlag.MIDI
            if cv_checked:
                port_types_view |= PortTypesViewFlag.CV

        # if not self.ui.checkBoxAudioFilter.isChecked():
        #     port_types_view &= ~PortTypesViewFlag.AUDIO
        # if not self.ui.checkBoxMidiFilter.isChecked():
        #     port_types_view &= ~PortTypesViewFlag.MIDI
        # if not self.ui.checkBoxCvFilter.isChecked():
        #     port_types_view &= ~PortTypesViewFlag.CV
        
        self._patchbay_mng.change_port_types_view(port_types_view)

    def _check_box_audio_checked(self, state: int):
        self._change_port_types_view()

    def _check_box_midi_checked(self, state: int):
        self._change_port_types_view()
    
    def _check_box_cv_checked(self, state: int):
        self._change_port_types_view()
        
    def _port_types_view_changed(self, port_types_view: int):
        self.ui.checkBoxAudioFilter.setChecked(
            bool(port_types_view & PortTypesViewFlag.AUDIO))
        self.ui.checkBoxMidiFilter.setChecked(
            bool(port_types_view & PortTypesViewFlag.MIDI))
        self.ui.checkBoxCvFilter.setChecked(
            bool(port_types_view & PortTypesViewFlag.CV))
        