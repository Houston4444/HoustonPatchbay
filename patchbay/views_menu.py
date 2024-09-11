from typing import TYPE_CHECKING

from PyQt5.QtCore import pyqtSlot
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QMenu, QApplication, QInputDialog

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
    
    def _are_there_absents(self) -> bool:
        group_names = set[str]()
        for group in self.mng.groups:
            group_names.add(group.name)
        
        if self.mng.views.get(self.mng.view_number) is None:
            return False

        for ptv, gp_name_pos in self.mng.views[self.mng.view_number].items():
            for gp_name in gp_name_pos.keys():
                if not gp_name in group_names:
                    return True
        return False
    
    def _build(self):
        self.clear()
        
        view_keys = [n for n in self.mng.views.keys()]
        
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

            if view == self.mng.view_number:
                view_act.setEnabled(False)

        self.addSeparator()
        
        act_mv_view = self.addAction(
            _translate('views_menu', 'Rename'))
        act_mv_view.setIcon(QIcon.fromTheme('edit-rename'))
        act_mv_view.triggered.connect(self._rename_view)

        act_rm_view = self.addAction(
            _translate('views_menu', 'Remove'))
        act_rm_view.setIcon(QIcon.fromTheme('edit-delete'))
        act_rm_view.triggered.connect(self._remove_view)

        act_clear_absents = self.addAction(
            _translate('views_menu', 'Forget the positions of those absent'))
        act_clear_absents.setIcon(QIcon.fromTheme('edit-clear-all'))
        act_clear_absents.triggered.connect(self._clear_absents)
        
        change_num_menu = QMenu(
            _translate('views_menu', 'Change view number to...'), self)
        
        if self.mng is not None and view_keys:
            n_nums_in_change_menu = max(max(view_keys) + 2, 10)
        else:
            n_nums_in_change_menu = 10
        
        for i in range(1, n_nums_in_change_menu):
            act_new_view_num = change_num_menu.addAction(str(i))
            if self.mng is not None:
                if self.mng.views.get(i) is not None:
                    if self.mng.views_datas.get(i) is not None:
                        view_name = self.mng.views_datas[i].name
                        act_new_view_num.setText(f'{i}\t{view_name}')

                    if i == self.mng.view_number:
                        act_new_view_num.setEnabled(False)
                    else:
                        act_new_view_num.setIcon(QIcon.fromTheme('reverse'))

            act_new_view_num.setData(i)
            act_new_view_num.triggered.connect(self._change_view_number)

        self.addMenu(change_num_menu)

        self.addSeparator()

        act_remove_others = self.addAction(
            QIcon.fromTheme('edit-delete'),
            _translate('views_menu', 'Remove all other views'))
        act_remove_others.triggered.connect(self._remove_all_other_views)

        act_new_view = self.addAction(
            _translate('views_menu', 'New view'))
        act_new_view.setIcon(QIcon.fromTheme('document-new'))
        act_new_view.triggered.connect(self._new_view)
        
        if len(view_keys) <= 1:
            act_rm_view.setEnabled(False)
            act_remove_others.setEnabled(False)
        
        if not self._are_there_absents():
            act_clear_absents.setEnabled(False)

    @pyqtSlot()
    def _change_view(self):
        view_number: int = self.sender().data()
        self.mng.change_view(view_number)

    @pyqtSlot()
    def _rename_view(self):
        view_data = self.mng.views_datas.get(self.mng.view_number)
        if view_data is None:
            view_name = ''
        else:
            view_name = view_data.name
        
        new_name, ok = QInputDialog.getText(
            self.mng.main_win,
            _translate('views_menu', 'Rename view'),
            _translate('views_menu', 'New view name :'),
            text=view_name)
        
        if ok:
            self.mng.rename_current_view(new_name)

    @pyqtSlot()
    def _clear_absents(self):
        self.mng.clear_absents_in_view()
        self._build()

    @pyqtSlot()
    def _change_view_number(self):
        new_num: int = self.sender().data()
        self.mng.change_view_number(new_num)

    @pyqtSlot()
    def _remove_all_other_views(self):
        self.mng.remove_all_other_views()

    @pyqtSlot()
    def _new_view(self):
        self.mng.new_view()

    @pyqtSlot()
    def _remove_view(self):
        self.mng.remove_view(self.mng.view_number)
    
    def showEvent(self, event) -> None:
        self._build()
        super().showEvent(event)