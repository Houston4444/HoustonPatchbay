from typing import TYPE_CHECKING

from qtpy.QtCore import Slot
from qtpy.QtWidgets import QWidget, QApplication

from .base_elements import ToolDisplayed
from .ui.canvas_bar import Ui_Form as CanvasUiForm

if TYPE_CHECKING:
    from .patchbay_manager import PatchbayManager


_translate = QApplication.translate


class BarWidgetCanvas(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.ui = CanvasUiForm()
        self.ui.setupUi(self)
        self.mng: 'PatchbayManager' = None
        
        self.ui.toolButtonUndo.clicked.connect(self.undo)
        self.ui.toolButtonRedo.clicked.connect(self.redo)
        
    def change_tools_displayed(self, tools_displayed: ToolDisplayed):
        self.ui.viewSelector.setVisible(
            bool(tools_displayed & ToolDisplayed.VIEWS_SELECTOR))
        self.ui.toolButtonHiddenBoxes.setVisible(
            bool(tools_displayed & ToolDisplayed.HIDDENS_BOX))
        self.ui.frameTypeFilter.setVisible(
            bool(tools_displayed & ToolDisplayed.PORT_TYPES_VIEW))
        self.ui.sliderZoom.setVisible(
            bool(tools_displayed & ToolDisplayed.ZOOM_SLIDER))
        self.ui.toolButtonUndo.setVisible(
            bool(tools_displayed & ToolDisplayed.UNDO_REDO))
        self.ui.toolButtonRedo.setVisible(
            bool(tools_displayed & ToolDisplayed.UNDO_REDO))
        
    def set_patchbay_manager(self, mng: 'PatchbayManager'):
        self.ui.frameTypeFilter.set_patchbay_manager(mng)
        self.ui.sliderZoom.set_patchbay_manager(mng)
        self.ui.viewSelector.set_patchbay_manager(mng)
        self.ui.toolButtonHiddenBoxes.set_patchbay_manager(mng)
        self.mng = mng
        
        self.mng.sg.undo_redo_changed.connect(self.undo_redo_changed)
        
    def set_at_end_of_line(self, end_of_line: bool):
        self.ui.widgetSpacerRight.setVisible(not end_of_line)
    
    @Slot()
    def undo_redo_changed(self):
        if self.mng is None:
            return

        cc = self.mng.cancel_mng
        
        if cc.actions:
            self.ui.toolButtonUndo.setEnabled(True)
            self.ui.toolButtonUndo.setToolTip(
                '<p>%s<br>' %  _translate('undo', 'Undo')
                + f'<i>{cc.actions[-1].name}</i></p>')
        else:
            self.ui.toolButtonUndo.setEnabled(False)
            self.ui.toolButtonUndo.setToolTip('')
            
        if cc.canceled_acts:
            self.ui.toolButtonRedo.setEnabled(True)
            self.ui.toolButtonRedo.setToolTip(
                '<p>%s<br>' % _translate('undo', 'Redo')                
                + f'<i>{cc.canceled_acts[-1].name}</i></p>')
        else:
            self.ui.toolButtonRedo.setEnabled(False)
            self.ui.toolButtonRedo.setToolTip('')
        
    @Slot()
    def undo(self):
        if self.mng is None:
            return
        
        self.mng.cancel_mng.undo()
        
    @Slot()
    def redo(self):
        if self.mng is None:
            return
        
        self.mng.cancel_mng.redo()