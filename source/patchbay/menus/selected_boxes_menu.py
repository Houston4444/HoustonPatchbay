from typing import TYPE_CHECKING
from qtpy.QtCore import Slot
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QMenu, QApplication


from .. import patchcanvas
from patshared import PortMode
from ..cancel_mng import CancelOp, CancellableAction

if TYPE_CHECKING:
    from ..patchbay_manager import PatchbayManager

_translate = QApplication.translate


class SelectedBoxesMenu(QMenu):
    def __init__(self, parent):
        super().__init__(parent)
        self.mng : 'PatchbayManager' = None
        self._selected_boxes = dict[int, PortMode]()

        self.setTitle(_translate('sel_boxes_menu', 'Selected boxes'))
        self.setIcon(QIcon.fromTheme('tool_rect_selection'))
        self._build()

    def set_patchbay_manager(self, mng: 'PatchbayManager'):
        self.mng = mng
    
    def set_selected_boxes(self, selected_boxes: dict[int, PortMode]):
        self._selected_boxes = selected_boxes
    
    def _build(self):
        self.action_new_white_view = self.addAction(
            _translate('sel_boxes_menu', "Put in a new exclusive view"))
        self.action_new_white_view.setIcon(QIcon.fromTheme('list-add'))
        self.action_new_white_view.triggered.connect(
            self._new_exclusive_view)

        self.action_hide_selected = self.addAction(
            _translate('sel_boxes_menu', "Hide boxes"))
        self.action_hide_selected.setIcon(QIcon.fromTheme('hint'))
        self.action_hide_selected.triggered.connect(
            self._hide_selected_boxes)

        self.action_invert_selection = self.addAction(
            _translate('sel_boxes_menu', 'Invert selection'))
        self.action_invert_selection.setIcon(
            QIcon.fromTheme('edit-select-invert'))
        self.action_invert_selection.triggered.connect(
            self._invert_boxes_selection)
    
    @Slot()    
    def _new_exclusive_view(self):
        with CancellableAction(self.mng, CancelOp.ALL_VIEWS) as a:
            a.name = self.sender().text()
            patchcanvas.clear_selection()
            self.mng.new_view(exclusive_with=self._selected_boxes)
        
    @Slot()
    def _hide_selected_boxes(self):
        with CancellableAction(self.mng, CancelOp.VIEW) as a:
            a.name = self.sender().text()

            for group_id, port_mode in self._selected_boxes.items():
                group = self.mng.get_group_from_id(group_id)
                if group is None:
                    continue

                group.hide(port_mode)

    @Slot()
    def _invert_boxes_selection(self):
        patchcanvas.invert_boxes_selection()