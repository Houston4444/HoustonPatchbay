import pickle
from enum import Enum, auto
from typing import TYPE_CHECKING

from PyQt5.QtWidgets import QApplication

from .patchcanvas.patshared.views_dict import ViewsDict

if TYPE_CHECKING:
    from patchbay_manager import PatchbayManager


_translate = QApplication.translate


class CancelOp(Enum):
    CONNECTION = auto()
    ARRANGE = auto()
    VIEW_CHANGE = auto()
    PTV_CHANGE = auto()
    VIEW_RENAME = auto()
    VIEW_REMOVE = auto()
    FORGET_ABSENTS = auto()
    VIEW_NUM_CHANGE = auto()
    VIEW_WHITE_LIST = auto()
    REMOVE_OTHER_VIEWS = auto()
    NEW_VIEW = auto()
    DISPLAY_ALL_BOXES = auto()


ACTION_NAMES = {
    CancelOp.CONNECTION:
        _translate('cancellable', 'Connect'),
    CancelOp.ARRANGE:
        _translate('cancellable', 'Arrange'),
    CancelOp.VIEW_CHANGE: 
        _translate('cancellable', 'Change view'),
    CancelOp.PTV_CHANGE:
        _translate('cancellable', 'Change visible port types'),
    CancelOp.VIEW_RENAME:
        _translate('cancellable', 'Rename view'),
    CancelOp.VIEW_REMOVE:
        _translate('cancellable', 'Remove view'),
    CancelOp.FORGET_ABSENTS:
        _translate('cancellable', 'Forget positions of those absents'),
    CancelOp.VIEW_NUM_CHANGE:
        _translate('cancellable', 'Change view number'),
    CancelOp.VIEW_WHITE_LIST:
        _translate('cancellable', 'Toggle hide all new boxes'),
    CancelOp.REMOVE_OTHER_VIEWS:
        _translate('cancellable', 'Remove all other views'),
    CancelOp.NEW_VIEW:
        _translate('cancellable', 'New view'),
    CancelOp.DISPLAY_ALL_BOXES:
        _translate('cancellable', 'Display all boxes')
}

class ActionRestorer:
    def __init__(self, op_type: CancelOp):
        self.type = op_type
        self.datas = []
        self.name = ACTION_NAMES.get(op_type, '')


class CancellableAction:
    '''Context for 'with' statment. save the data at begin and at end
    for undo/redo actions'''
    def __init__(self, mng: 'PatchbayManager', op_type: CancelOp, *datas):
        self.cancel_mng = mng.cancel_mng
        self.op_type = op_type

    def __enter__(self) -> ActionRestorer:
        return self.cancel_mng.prepare(self.op_type)

    def __exit__(self, *args, **kwargs):
        self.cancel_mng.post_prepare(self.op_type)


class CancelMng:
    def __init__(self, mng: 'PatchbayManager'):
        self.mng = mng
        self.actions = list[ActionRestorer]()
        self.canceled_acts = list[ActionRestorer]()

    def prepare(self, op_type: CancelOp):
        view_data = self.mng.views.get(self.mng.view_number)
        if view_data is None:
            return
        
        action = ActionRestorer(op_type)

        if op_type in (CancelOp.ARRANGE,
                       CancelOp.FORGET_ABSENTS,
                       CancelOp.VIEW_REMOVE,
                       CancelOp.VIEW_WHITE_LIST,
                       CancelOp.DISPLAY_ALL_BOXES):
            action.datas = [self.mng.view_number, view_data.copy()]

        elif op_type in (CancelOp.VIEW_CHANGE,
                         CancelOp.VIEW_NUM_CHANGE,
                         CancelOp.NEW_VIEW):
            action.datas = [set(self.mng.views), self.mng.view_number]

        elif op_type is CancelOp.PTV_CHANGE:
            action.datas = [self.mng.port_types_view]

        elif op_type is CancelOp.VIEW_RENAME:
            action.datas = [view_data.name]
            
        elif op_type is CancelOp.REMOVE_OTHER_VIEWS:
            views_save = ViewsDict(ensure_one_view=False)
            for view_num, view_data in self.mng.views.items():
                views_save[view_num] = view_data.copy()
            action.datas = [self.mng.view_number, views_save]
        
        self.actions.append(action)
        self.canceled_acts.clear()
        return action
            
    def post_prepare(self, op_type: CancelOp):
        if not self.actions:
            # should not happen, prepare has just added an action
            return
        
        action = self.actions[-1]
        if not action.type is op_type:
            # should not happen, for the same reason
            return
        
        if op_type in (CancelOp.ARRANGE,
                       CancelOp.FORGET_ABSENTS,
                       CancelOp.VIEW_REMOVE,
                       CancelOp.VIEW_WHITE_LIST,
                       CancelOp.DISPLAY_ALL_BOXES):
            action.datas.append(self.mng.views[self.mng.view_number].copy())
        elif op_type in (CancelOp.VIEW_CHANGE,
                         CancelOp.VIEW_NUM_CHANGE,
                         CancelOp.NEW_VIEW):
            action.datas.append(self.mng.view_number)
        elif op_type is CancelOp.PTV_CHANGE:
            action.datas.append(self.mng.port_types_view)
        elif op_type is CancelOp.VIEW_RENAME:
            action.datas.append(self.mng.views[self.mng.view_number].name)

        self.mng.sg.undo_redo_changed.emit()

    def undo(self):
        if not self.actions:
            return

        action = self.actions.pop(-1)
        self.canceled_acts.append(action)

        if action.type is CancelOp.ARRANGE:
            view_num, view_data_before, view_data_after = action.datas
            self.mng.views[view_num] = view_data_before
            if self.mng.view_number == view_num:
                self.mng.change_view(self.mng.view_number)
        
        elif action.type is CancelOp.VIEW_CHANGE:
            nums_before, view_num_before, view_num_after = action.datas
            self.mng.change_view(view_num_before)
            if (view_num_after not in nums_before
                    and view_num_after in self.mng.views):
                self.mng.views.pop(view_num_after)
                self.mng.set_views_changed()

        elif action.type is CancelOp.PTV_CHANGE:
            self.mng.change_port_types_view(action.datas[0])
        
        elif action.type is CancelOp.VIEW_RENAME:
            name_bef, name_aft = action.datas
            self.mng.rename_current_view(name_bef)
        
        elif action.type is CancelOp.VIEW_REMOVE:
            view_num, view_data_before, view_data_after = action.datas
            self.mng.views.add_view(view_num=view_num)
            self.mng.views[view_num] = view_data_before
            self.mng.set_views_changed()
            self.mng.change_view(view_num)
        
        elif action.type is CancelOp.FORGET_ABSENTS:
            view_num, view_data_before, view_data_after = action.datas
            self.mng.views[view_num] = view_data_before
        
        elif action.type is CancelOp.VIEW_NUM_CHANGE:
            nums_before, view_num_before, view_num_after = action.datas
            self.mng.change_view_number(view_num_before)
        
        elif action.type in (CancelOp.VIEW_WHITE_LIST,
                             CancelOp.DISPLAY_ALL_BOXES):
            view_num, view_data_before, view_data_after = action.datas
            self.mng.views[view_num] = view_data_before
            self.mng.set_views_changed()
            if self.mng.view_number == view_num:
                self.mng.change_view(self.mng.view_number)
        
        elif action.type is CancelOp.REMOVE_OTHER_VIEWS:
            view_num: int = action.datas[0]
            views_save: ViewsDict = action.datas[1]
            for sv_num, sv_view_data in views_save.items():
                if sv_num not in self.mng.views:
                    self.mng.views.add_view(sv_num)
                    self.mng.views[sv_num] = sv_view_data.copy()
            self.mng.set_views_changed()
        
        elif action.type is CancelOp.NEW_VIEW:
            nums_before, view_num_before, view_num_after = action.datas
            self.mng.change_view(view_num_before)
            self.mng.remove_view(view_num_after)
            
        self.mng.sg.undo_redo_changed.emit()
        
    def redo(self):
        if not self.canceled_acts:
            return
        
        action = self.canceled_acts.pop(-1)
        self.actions.append(action)

        if action.type is CancelOp.ARRANGE:
            view_num, view_data_before, view_data_after = action.datas

            self.mng.views[view_num] = view_data_after
            if self.mng.view_number == view_num:
                self.mng.change_view(self.mng.view_number)
        
        elif action.type is CancelOp.VIEW_CHANGE:
            nums_before, view_num_before, view_num_after = action.datas
            self.mng.change_view(view_num_after)

        elif action.type is CancelOp.PTV_CHANGE:
            self.mng.change_port_types_view(action.datas[1])
            
        elif action.type is CancelOp.VIEW_RENAME:
            name_bef, name_aft = action.datas
            self.mng.rename_current_view(name_aft)
        
        elif action.type is CancelOp.VIEW_REMOVE:
            view_num, view_data_before, view_data_after = action.datas
            self.mng.remove_view(view_num)
        
        elif action.type is CancelOp.FORGET_ABSENTS:
            view_num, view_data_before, view_data_after = action.datas
            self.mng.views[view_num] = view_data_after

        elif action.type is CancelOp.VIEW_NUM_CHANGE:
            nums_before, view_num_before, view_num_after = action.datas
            self.mng.change_view_number(view_num_after)
        
        elif action.type in (CancelOp.VIEW_WHITE_LIST,
                             CancelOp.DISPLAY_ALL_BOXES):
            view_num, view_data_before, view_data_after = action.datas

            self.mng.views[view_num] = view_data_after
            self.mng.set_views_changed()
            if self.mng.view_number == view_num:
                self.mng.change_view(self.mng.view_number)
        
        elif action.type is CancelOp.REMOVE_OTHER_VIEWS:
            self.mng.remove_all_other_views()

        elif action.type is CancelOp.NEW_VIEW:
            nums_before, view_num_before, view_num_after = action.datas
            self.mng.new_view()

        self.mng.sg.undo_redo_changed.emit()

    def reset(self):
        self.actions.clear()
        self.canceled_acts.clear()
        self.mng.sg.undo_redo_changed.emit()

    