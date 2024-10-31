from enum import Enum, auto
from typing import TYPE_CHECKING

from PyQt5.QtWidgets import QApplication

if TYPE_CHECKING:
    from patchbay_manager import PatchbayManager


_translate = QApplication.translate


class CancelOpType(Enum):
    CONNECTION = auto()
    ARRANGE = auto()
    VIEW_CHANGE = auto()
    PTV_CHANGE = auto()


class ActionRestorer:
    type: CancelOpType
    datas: list


actions_names = {
    CancelOpType.CONNECTION: _translate('cancellable', 'Connect'),
    CancelOpType.ARRANGE: _translate('cancellable', 'Arrange'),
    CancelOpType.VIEW_CHANGE: _translate('cancellable', 'Change view'),
    CancelOpType.PTV_CHANGE: _translate('cancellable', 'Change visible port types')
}


class CancellableAction:
    '''Context for 'with' statment. save the data at begin and at end
    for undo/redo actions'''
    def __init__(self, mng: 'PatchbayManager', op_type: CancelOpType, *datas):
        self.cancel_mng = mng.cancel_mng
        self.op_type = op_type

    def __enter__(self):
        self.cancel_mng.prepare(self.op_type)

    def __exit__(self, *args, **kwargs):
        self.cancel_mng.post_prepare(self.op_type)


class CancelMng:
    def __init__(self, mng: 'PatchbayManager'):
        self.mng = mng
        self.actions = list[ActionRestorer]()
        self.canceled_acts = list[ActionRestorer]()

    def prepare(self, cancel_op_type: CancelOpType):
        view_data = self.mng.views.get(self.mng.view_number)
        if view_data is None:
            return
        
        action = ActionRestorer()
        action.type = cancel_op_type

        if cancel_op_type is CancelOpType.ARRANGE:
            action.datas = [self.mng.view_number, view_data.copy()]
        elif cancel_op_type is CancelOpType.VIEW_CHANGE:
            action.datas = [self.mng.view_number]
        elif cancel_op_type is CancelOpType.PTV_CHANGE:
            action.datas = [self.mng.port_types_view]
            
        self.actions.append(action)
        self.canceled_acts.clear()
            
    def post_prepare(self, cancel_op_type: CancelOpType):
        if not self.actions:
            # should not happen, prepare has just added an action
            return
        
        action = self.actions[-1]
        if not action.type is cancel_op_type:
            # should not happen, for the same reason
            return
        
        if cancel_op_type is CancelOpType.ARRANGE:
            action.datas.append(self.mng.views[self.mng.view_number].copy())
        elif cancel_op_type is CancelOpType.VIEW_CHANGE:
            action.datas.append(self.mng.view_number)
        elif cancel_op_type is CancelOpType.PTV_CHANGE:
            action.datas.append(self.mng.port_types_view)
        
        self.mng.sg.undo_redo_changed.emit()

    def undo(self):
        if not self.actions:
            return

        action = self.actions.pop(-1)
        self.canceled_acts.append(action)

        if action.type is CancelOpType.ARRANGE:
            view_num, view_data_before, view_data_after = action.datas
            self.mng.views[view_num] = view_data_before
            if self.mng.view_number == view_num:
                self.mng.change_view(self.mng.view_number)
        
        elif action.type is CancelOpType.VIEW_CHANGE:
            view_num_before, view_num_after = action.datas
            self.mng.change_view(view_num_before)

        elif action.type is CancelOpType.PTV_CHANGE:
            self.mng.change_port_types_view(action.datas[0])
                
        self.mng.sg.undo_redo_changed.emit()
        
    def redo(self):
        if not self.canceled_acts:
            return
        
        action = self.canceled_acts.pop(-1)
        self.actions.append(action)

        if action.type is CancelOpType.ARRANGE:
            view_num, view_data_before, view_data_after = action.datas

            self.mng.views[view_num] = view_data_after
            if self.mng.view_number == view_num:
                self.mng.change_view(self.mng.view_number)
        
        elif action.type is CancelOpType.VIEW_CHANGE:
            view_num_before, view_num_after = action.datas
            self.mng.change_view(view_num_after)

        elif action.type is CancelOpType.PTV_CHANGE:
            self.mng.change_port_types_view(action.datas[1])
        
        self.mng.sg.undo_redo_changed.emit()

    def reset(self):
        self.actions.clear()
        self.canceled_acts.clear()
        self.mng.sg.undo_redo_changed.emit()

    