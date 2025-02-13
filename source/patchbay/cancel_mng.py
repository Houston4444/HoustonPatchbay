from enum import Enum, auto
from typing import TYPE_CHECKING, Callable

from patshared import ViewData, ViewsDict, PortTypesViewFlag

if TYPE_CHECKING:
    from patchbay_manager import PatchbayManager    


class CancelOp(Enum):
    PTV_CHOICE = auto()
    'Save the port types view choice only'
    
    VIEW_CHOICE = auto()
    'save the view choice only'
    
    VIEW = auto()
    'save all the current view'
    
    ALL_VIEWS = auto()
    'save all the views'
    
    ALL_VIEWS_NO_POS = auto()
    'save all the views, without group positions'    


class ActionRestorer:
    def __init__(self, op_type: CancelOp):
        self.type = op_type
        self.name = ''

        self.view_num_bef = 1
        self.view_num_aft = 1
        self.view_data_bef: ViewData = None
        self.view_data_aft: ViewData = None
        self.views_bef : ViewsDict = None
        self.views_aft: ViewsDict = None
        self.ptv_bef: PortTypesViewFlag = None
        self.ptv_aft: PortTypesViewFlag = None

        self.undo_func: Callable = None
        self.undo_args: tuple = ()
        self.redo_func: Callable = None
        self.redo_args: tuple = ()


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
        
        self.new_pos_created = False
        '''In VIEW_CHOICE action, GroupPos can be be created in a view
        , in this case, cancel_mng considers finally this action
        as ALL_VIEWS.'''
        
        self._recording = False

    def prepare(self, op_type: CancelOp):
        if self._recording:
            raise RecursionError
        
        self.new_pos_created = False
        self._recording = True
        
        action = ActionRestorer(op_type)
        action.view_num_bef = self.mng.view_number
            
        if op_type in (CancelOp.VIEW, CancelOp.PTV_CHOICE):
            action.view_data_bef = self.mng.view().copy()
            if op_type is CancelOp.PTV_CHOICE:
                action.ptv_bef = self.mng.port_types_view
            
        elif op_type in (CancelOp.VIEW_CHOICE, CancelOp.ALL_VIEWS):
            action.views_bef = self.mng.views.copy()
            
        elif op_type is CancelOp.ALL_VIEWS_NO_POS:
            action.views_bef = self.mng.views.copy(with_positions=False)

        self.actions.append(action)
        self.canceled_acts.clear()
        return action
            
    def post_prepare(self, op_type: CancelOp):
        self._recording = False
        
        if not self.actions:
            # should not happen, prepare has just added an action
            return
        
        action = self.actions[-1]
        if not action.type is op_type:
            # should not happen, for the same reason
            return
        
        if op_type is CancelOp.VIEW_CHOICE:
            if self.new_pos_created:
                action.type = CancelOp.ALL_VIEWS
            else:
                action.view_data_bef = None

        elif op_type is CancelOp.PTV_CHOICE:
            if self.new_pos_created:
                action.type = CancelOp.VIEW
                action.ptv_bef = None
            else:
                action.view_data_bef = None
                action.ptv_aft = self.mng.port_types_view

        action.view_num_aft = self.mng.view_number

        if action.type is CancelOp.VIEW:
            action.view_data_aft = self.mng.view().copy()
            
        elif action.type is CancelOp.ALL_VIEWS:
            action.views_aft = self.mng.views.copy()
        
        elif action.type is CancelOp.ALL_VIEWS_NO_POS:
            action.views_aft = self.mng.views.copy(with_positions=False)

        self.mng.sg.undo_redo_changed.emit()

    def undo(self):
        if not self.actions:
            return

        action = self.actions.pop(-1)
        self.canceled_acts.append(action)

        if action.undo_func is not None:
            action.undo_func(*action.undo_args)

        if action.type is CancelOp.PTV_CHOICE:
            self.mng.change_port_types_view(action.ptv_bef)

        elif action.type is CancelOp.VIEW_CHOICE:
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

        if action.redo_func is not None:
            action.redo_func(*action.redo_args)

        if action.type is CancelOp.VIEW_CHOICE:
            self.mng.change_view(action.view_num_aft)

        elif action.type is CancelOp.PTV_CHOICE:
            self.mng.change_port_types_view(action.ptv_aft)

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

    