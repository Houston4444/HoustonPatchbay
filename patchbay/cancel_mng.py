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
            
    def undo(self):
        if not self.actions:
            return

        action = self.actions.pop(-1)
        self.canceled_acts.append(action)

        if isinstance(action, ArrangeRestorer):
            self.mng.views[action.view_num] = action.view_data_before
            if self.mng.view_number == action.view_num:
                self.mng.change_view(self.mng.view_number)
        
    def redo(self):
        if not self.canceled_acts:
            return
        
        action = self.canceled_acts.pop(-1)
        if isinstance(action, ArrangeRestorer):
            if action.view_data_after is None:
                return

            self.mng.views[action.view_num] = action.view_data_before
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
    