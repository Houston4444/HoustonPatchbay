from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING, Optional

from .patchcanvas.patshared import ViewData

if TYPE_CHECKING:
    from patchbay_manager import PatchbayManager


class CancelOpType(Enum):
    CONNECTION = auto()
    ARRANGE = auto()


@dataclass()
class ArrangeRestorer:
    view_num: int
    view_data_before: ViewData
    
    def __post_init__(self):
        self.view_data_after: Optional[ViewData] = None


class CancellableAction:
    '''Context for 'with' statment. save the data at begin and at end
    for undo/redo actions'''
    def __init__(self, mng: 'PatchbayManager', op_type: CancelOpType, *datas):
        self.cancel_mng = mng.cancel_mng
        self.op_type = op_type
        self.datas = datas

    def __enter__(self):
        self.cancel_mng.prepare(self.op_type, *self.datas)

    def __exit__(self, *args, **kwargs):
        self.cancel_mng.post_prepare(self.op_type, *self.datas)


class CancelMng:
    def __init__(self, mng: 'PatchbayManager'):
        self.mng = mng
        self.actions = list[ArrangeRestorer]()
        self.canceled_acts = list[ArrangeRestorer]()

    def prepare(self, cancel_op_type: CancelOpType, view_num: int):
        view_data = self.mng.views.get(view_num)
        if view_num is None:
            return
        
        if cancel_op_type is CancelOpType.ARRANGE:
            self.actions.append(ArrangeRestorer(view_num, view_data.copy()))
            self.canceled_acts.clear()
            print('prepare', self.mng.views[view_num].ptvs[self.mng.port_types_view].get('Hydrogen').as_new_dict())
            
    def post_prepare(self, cancel_op_type: CancelOpType, view_num: int):
        if not self.actions:
            return
        
        action = self.actions[-1]
        if cancel_op_type is CancelOpType.ARRANGE:
            if not isinstance(action, ArrangeRestorer):
                return
            if action.view_num != view_num:
                return
            
            action.view_data_after = \
                self.mng.views[self.mng.view_number].copy()
            print('post prep', self.mng.views[view_num].ptvs[self.mng.port_types_view].get('Hydrogen').as_new_dict())
            print('copyy', action.view_data_after.ptvs[self.mng.port_types_view].get('Hydrogen').as_new_dict())
            
    def undo(self):
        print('undo', len(self.actions))
        
        if not self.actions:
            return

        action = self.actions.pop(-1)
        self.canceled_acts.append(action)

        if isinstance(action, ArrangeRestorer):
            self.mng.views[action.view_num] = action.view_data_before
            if self.mng.view_number == action.view_num:
                self.mng.change_view(self.mng.view_number)
        
    def redo(self):
        print('redo', len(self.canceled_acts))
        if not self.canceled_acts:
            return
        
        action = self.canceled_acts.pop(-1)
        self.actions.append(action)

        if isinstance(action, ArrangeRestorer):
            if action.view_data_after is None:
                return

            self.mng.views[action.view_num] = action.view_data_after
            print('reoos', self.mng.views[self.mng.view_number].ptvs[self.mng.port_types_view].get('Hydrogen').as_new_dict())
            if self.mng.view_number == action.view_num:
                self.mng.change_view(self.mng.view_number)

'''
arrangement
    sauver vue + num
    action
        annuler = rétablir vue dans num + change_ptv
        
nouvelle vue
    sauver 

'''
    