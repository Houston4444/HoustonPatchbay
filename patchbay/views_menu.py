from typing import TYPE_CHECKING
from PyQt5.QtWidgets import QMenu, QApplication, QInputDialog, QLineEdit
from PyQt5.QtGui import QIcon, QKeySequence
from PyQt5.QtCore import pyqtSlot

from .base_elements import PortTypesViewFlag

if TYPE_CHECKING:
    from patchbay_manager import PatchbayManager
    

_translate = QApplication.translate


class ViewsMenu(QMenu):
    def __init__(self, parent: QMenu, mng: 'PatchbayManager'):
        QMenu.__init__(self, parent)
        self.mng = mng
        self.setTitle(
            _translate('views_menu', 'Views'))
        self.setIcon(QIcon.fromTheme('view-group'))
        self._build()
        
    def _build(self):
        self.clear()
        
        view_keys = self.mng.views.keys()
        n_views = len(self.mng.views)
        
        if n_views > 1:
            remove_menu = QMenu(
                _translate('views_menu', 'Remove the view'), self)
            remove_menu.setIcon(QIcon.fromTheme('document-close'))
            
            for view in view_keys:
                view_data = self.mng.views_datas.get(view)
                if view_data is None or not view_data.name:
                    view_name = _translate('views_menu', 'View n°%i') % view
                else:
                    view_name = view_data.name

                view_text = view_name
                if 0 <= view <= 9:
                    view_text += f'\tAlt+{view}'

                view_act = self.addAction(view_text)
                view_act.setData(view)
                view_act.triggered.connect(self._change_view)                    
                    
                rm_act = remove_menu.addAction(view_name)
                rm_act.setData(view)
                rm_act.triggered.connect(self._remove_view)
                
                if view == self.mng.view_number:
                    view_act.setEnabled(False)
                    rm_act.setEnabled(False)

            self.addSeparator()
            
            self.addMenu(remove_menu)
            self.addSeparator()
        
        new_view_act = self.addAction(
            _translate('views_menu', 'New view'))
        new_view_act.setIcon(QIcon.fromTheme('document-new'))
        new_view_act.triggered.connect(self._new_view)
        
        if n_views > 1:
            mv_view_act = self.addAction(
                _translate('views_menu', 'Rename the current view'))
            mv_view_act.setIcon(QIcon.fromTheme('edit-rename'))
            mv_view_act.triggered.connect(self._rename_view)
        
        clear_view_act = self.addAction(
            _translate('views_menu', 'Forget the positions of those absent'))
        clear_view_act.setIcon(QIcon.fromTheme('edit-clear-all'))
        clear_view_act.triggered.connect(self._clear_view)

    @pyqtSlot()
    def _new_view(self):
        self.mng.new_view()
    
    @pyqtSlot()
    def _rename_view(self):
        new_name, ok = QInputDialog.getText(
            self.mng.main_win,
            _translate('views_menu', 'Rename view'),
            _translate('views_menu', 'New view name :'))
        
        if ok:
            self.mng.rename_current_view(new_name)
    
    
    @pyqtSlot()
    def _clear_view(self):
        print('clear viewww')

    @pyqtSlot()
    def _change_view(self):
        view_number: int = self.sender().data()
        self.mng.change_view(view_number)

    @pyqtSlot()
    def _remove_view(self):
        view_number: int = self.sender().data()
        if view_number in self.mng.views.keys():
            self.mng.views.pop(view_number)
        if view_number in self.mng.views_datas.keys():
            self.mng.views_datas.pop(view_number)
    
    def showEvent(self, event) -> None:
        self._build()
        super().showEvent(event)