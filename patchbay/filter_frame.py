
from typing import TYPE_CHECKING
from PyQt5.QtWidgets import QFrame
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtCore import Qt, QSettings, pyqtSlot

from .ui.filter_frame import Ui_Frame

if TYPE_CHECKING:
    from .patchbay_manager import PatchbayManager


class FilterFrame(QFrame):
    def __init__(self, parent):
        QFrame.__init__(self, parent)
        self.ui = Ui_Frame()
        self.ui.setupUi(self)

        self._settings = None
        self.mng = None
        
        self.ui.lineEditGroupFilter.textEdited.connect(self._text_changed)
        self.ui.lineEditGroupFilter.up_down_pressed.connect(self._up_down_pressed)
        self.ui.toolButtonUp.clicked.connect(self._up_pressed)
        self.ui.toolButtonDown.clicked.connect(self._down_pressed)
        self.ui.spinBoxOpacity.valueChanged.connect(
            self._set_semi_hide_opacity)
        self.ui.toolButtonCloseFilterBar.clicked.connect(
            self.hide)
        
        self._n_selected = 0
        self._n_boxes = 0
        
    def set_settings(self, settings: QSettings):
        self._settings = settings
        self.ui.spinBoxOpacity.setValue(
            int(settings.value('Canvas/semi_hide_opacity', 0.24, type=float) * 100))
    
    def _filter_groups(self):
        if self.mng is None:
            return
        
        filter_text = self.ui.lineEditGroupFilter.text()
        
        self.ui.labelBoxes.setText('')
        
        self._n_boxes = self.mng.filter_groups(
            filter_text, self._n_selected)

        if self._n_boxes:
            self.ui.lineEditGroupFilter.setStyleSheet('')
            
            if filter_text:
                self.ui.labelBoxes.setText(
                    '%i / %i' % (self._n_selected, self._n_boxes))
        else:
            self.ui.lineEditGroupFilter.setStyleSheet(
                'QLineEdit{background-color:#800000}')
            
        self.ui.toolButtonUp.setEnabled(self._n_boxes >= 2)
        self.ui.toolButtonDown.setEnabled(self._n_boxes >= 2)

    def _text_changed(self, text: str):
        if text:
            self._n_selected = 1
        else:
            self._n_selected = 0
        self._filter_groups()

    def _up_pressed(self):
        self._n_selected += 1
        if self._n_selected > self._n_boxes:
            self._n_selected = 1
        self._filter_groups()
    
    def _down_pressed(self):
        self._n_selected -= 1
        if self._n_selected < 1:
            self._n_selected = self._n_boxes

        self._filter_groups()

    @pyqtSlot(int)
    def _up_down_pressed(self, key: int):
        if not self.ui.toolButtonUp.isEnabled():
            # could be toolButtonDown
            # they both are enabled/disabled together
            return

        if key == Qt.Key_Up:
            self._up_pressed()
        elif key == Qt.Key_Down:
            self._down_pressed()
    
    def _set_semi_hide_opacity(self, value:int):
        if self.mng is None:
            return

        self.mng.set_semi_hide_opacity(float(value / 100))
    
    def showEvent(self, event):
        self.ui.lineEditGroupFilter.setFocus()
        self.ui.toolButtonDown.setEnabled(False)
        self.ui.toolButtonUp.setEnabled(False)
        self.ui.labelBoxes.setText('')
        QFrame.showEvent(self, event)
        
    def hideEvent(self, event):
        self.ui.lineEditGroupFilter.setText('')
        self._n_selected = 0
        self._filter_groups()

        if self._settings is not None:
            self._settings.setValue(
                'Canvas/semi_hide_opacity',
                float(self.ui.spinBoxOpacity.value() / 100))
        QFrame.hideEvent(self, event)
    
    def keyPressEvent(self, event: QKeyEvent):
        super().keyPressEvent(event)
        if event.key() == Qt.Key_Escape:
            self.hide()
    
    @pyqtSlot(int)
    def _port_types_view_changed(self, port_types_view: int):
        if not self.isVisible():
            return
        self._filter_groups()
    
    def set_patchbay_manager(self, mng: 'PatchbayManager'):
        self.mng = mng
        self.mng.sg.port_types_view_changed.connect(
            self._port_types_view_changed)
        self.ui.frameTypeFilter.set_patchbay_manager(mng)
        self.ui.toolButtonHiddensIndicator.set_patchbay_manager(mng)
    
    def set_filter_text(self, text: str):
        ''' used to find client boxes from client widget '''
        self.ui.lineEditGroupFilter.setText(text)

        if text:
            self._n_selected = 1
        else:
            self._n_selected = 0

        self._filter_groups()
