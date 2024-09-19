from PyQt5.QtWidgets import QWidget

from .base_elements import ToolDisplayed

from .ui.canvas_bar import Ui_Form as CanvasUiForm


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