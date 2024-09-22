from typing import TYPE_CHECKING

from PyQt5.QtWidgets import QWidget

from .base_elements import ToolDisplayed

from .ui.canvas_bar import Ui_Form as CanvasUiForm

if TYPE_CHECKING:
    from .patchbay_manager import PatchbayManager


class BarWidgetCanvas(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.ui = CanvasUiForm()
        self.ui.setupUi(self)
        
    def change_tools_displayed(self, tools_displayed: ToolDisplayed):
        self.ui.viewSelector.setVisible(
            bool(tools_displayed & ToolDisplayed.VIEWS_SELECTOR))
        self.ui.toolButtonHiddenBoxes.setVisible(
            bool(tools_displayed & ToolDisplayed.HIDDENS_BOX))
        self.ui.frameTypeFilter.setVisible(
            bool(tools_displayed & ToolDisplayed.PORT_TYPES_VIEW))
        self.ui.sliderZoom.setVisible(
            bool(tools_displayed & ToolDisplayed.ZOOM_SLIDER))
        
    def set_patchbay_manager(self, mng: 'PatchbayManager'):
        self.ui.frameTypeFilter.set_patchbay_manager(mng)
        self.ui.sliderZoom.set_patchbay_manager(mng)
        self.ui.viewSelector.set_patchbay_manager(mng)
        self.ui.toolButtonHiddenBoxes.set_patchbay_manager(mng)
        
    def set_at_end_of_line(self, end_of_line: bool):
        self.ui.widgetSpacerRight.setVisible(not end_of_line)