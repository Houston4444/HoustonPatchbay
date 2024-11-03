from enum import Enum, auto
from typing import TYPE_CHECKING

from PyQt5.QtWidgets import QApplication

from .patchcanvas.patshared import ViewData, ViewsDict

if TYPE_CHECKING:
    from patchbay_manager import PatchbayManager


_translate = QApplication.translate


class CancelOp(Enum):    
    VIEW_CHOICE = auto()
    'save and restore view choice only'
    
    VIEW = auto()
    'save and restore all the current view'
    
    ALL_VIEWS = auto()
    'save and restore all the views'
    # TODO : ALL_VIEWS is still required at keyboard view change 
    # because it can create a view 
    
    ALL_VIEWS_NO_POS = auto()
    'save and restore all the views, without group positions'    


ACTION_NAMES = {
    CancelOp.VIEW_CHOICE:
        _translate('undo', 'View choice action'),
    CancelOp.VIEW:
        _translate('undo', 'Action affecting the current view'),
    CancelOp.ALL_VIEWS:
        _translate('undo', 'Action affecting several views'),
    CancelOp.ALL_VIEWS_NO_POS:
        _translate('undo', 'Action affecting views datas')
}


class ActionRestorer:
    def __init__(self, op_type: CancelOp):
        self.type = op_type
        self.name = ACTION_NAMES.get(op_type, '')

        self.view_num_bef = 1
        self.view_num_aft = 1
        self.view_data_bef: ViewData = None
        self.view_data_aft: ViewData = None
        self.views_bef : ViewsDict = None
        self.views_aft: ViewsDict = None


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

        if op_type in (CancelOp.VIEW_CHOICE,
                       CancelOp.VIEW,
                       CancelOp.ALL_VIEWS):
            action.view_num_bef = self.mng.view_number
            
        if op_type is CancelOp.VIEW:
            action.view_data_bef = self.mng.views[self.mng.view_number].copy()
            
        elif op_type is CancelOp.ALL_VIEWS:
            action.views_bef = self.mng.views.copy()
            
        elif op_type is CancelOp.ALL_VIEWS_NO_POS:
            action.views_bef = self.mng.views.copy(with_positions=False)

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
        
        if op_type in (CancelOp.VIEW_CHOICE,
                       CancelOp.VIEW,
                       CancelOp.ALL_VIEWS):
            action.view_num_aft = self.mng.view_number
            
        if op_type is CancelOp.VIEW:
            action.view_data_aft = self.mng.views[self.mng.view_number].copy()
            
        elif op_type is CancelOp.ALL_VIEWS:
            action.views_aft = self.mng.views.copy()
        
        elif op_type is CancelOp.ALL_VIEWS_NO_POS:
            action.views_aft = self.mng.views.copy(with_positions=False)

        self.mng.sg.undo_redo_changed.emit()

    def undo(self):
        if not self.actions:
            return

        action = self.actions.pop(-1)
        self.canceled_acts.append(action)

        if action.type is CancelOp.VIEW_CHOICE:
            self.mng.change_view(action.view_num_bef)
            
        elif action.type is CancelOp.VIEW:
            self.mng.views[action.view_num_bef] = action.view_data_bef.copy()
            self.mng.set_views_changed()
            self.mng.change_view(action.view_num_bef)
                
        elif action.type is CancelOp.ALL_VIEWS:
            self.mng.views = action.views_bef.copy()
            self.mng.set_views_changed()
            self.mng.change_view(action.view_num_bef)

        elif action.type is CancelOp.ALL_VIEWS_NO_POS:
            self.mng.views.eat_views_dict_datas(action.views_bef)
            self.mng.set_views_changed()
            self.mng.change_view(action.view_num_bef)
            
        self.mng.sg.undo_redo_changed.emit()
        
    def redo(self):
        if not self.canceled_acts:
            return

        action = self.canceled_acts.pop(-1)
        self.actions.append(action)

        if action.type is CancelOp.VIEW_CHOICE:
            self.mng.change_view(action.view_num_aft)

        elif action.type is CancelOp.VIEW:
            self.mng.views[action.view_num_aft] = action.view_data_aft.copy()
            self.mng.set_views_changed()
            self.mng.change_view(action.view_num_aft)

        elif action.type is CancelOp.ALL_VIEWS:
            self.mng.views = action.views_aft.copy()
            self.mng.set_views_changed()
            self.mng.change_view(action.view_num_aft)

        self.mng.sg.undo_redo_changed.emit()

    def reset(self):
        self.actions.clear()
        self.canceled_acts.clear()
        self.mng.sg.undo_redo_changed.emit()

    