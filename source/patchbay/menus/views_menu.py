from typing import TYPE_CHECKING

from qtpy.QtCore import Slot
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QMenu, QApplication, QInputDialog

from ..cancel_mng import CancelOp, CancellableAction

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

        for gpos in self.mng.views.iter_group_poses(
                view_num=self.mng.view_number):
            if gpos.group_name not in group_names:
                return True
        return False
    
    def _build(self):
        self.clear()
        view_keys = list[int]()
        
        if self.mng is not None:
            view_keys = [k for k in self.mng.views.keys()]

            for index, view_data in self.mng.views.items():
                view_text = view_data.name
                if not view_text:
                    view_text = _translate('views_menu', 'View n°%i') % index
                
                if 0 <= index <= 9:
                    view_text += f'\tAlt+{index}'

                view_act = self.addAction(view_text)
                view_act.setData(index)
                view_act.triggered.connect(self._change_view)

                if index == self.mng.view_number:
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
        
        if view_keys:
            n_nums_in_change_menu = max(max(view_keys) + 2, 10)
        else:
            n_nums_in_change_menu = 10
        
        for i in range(1, n_nums_in_change_menu):
            act_new_view_num = change_num_menu.addAction(str(i))
            if self.mng is not None:
                view_data = self.mng.views.get(i)
                if view_data is not None:
                    if view_data.name:
                        act_new_view_num.setText(f'{i}\t{view_data.name}')

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

    @Slot()
    def _change_view(self):
        view_number: int = self.sender().data()
        with CancellableAction(self.mng, CancelOp.VIEW_CHOICE) as a:
            a.name = _translate('undo', 'Change view %i -> %i') % (
                self.mng.view_number, view_number)
            self.mng.change_view(view_number)

    @Slot()
    def _rename_view(self):
        view_data = self.mng.views.get(self.mng.view_number)
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
            with CancellableAction(self.mng, CancelOp.ALL_VIEWS_NO_POS) as a:
                a.name = _translate('undo', 'View %i renamed to "%s"') % (
                    self.mng.view_number, new_name)
                self.mng.rename_current_view(new_name)

    @Slot()
    def _clear_absents(self):
        with CancellableAction(self.mng, CancelOp.VIEW) as a:
            a.name = self.sender().text()
            self.mng.clear_absents_in_view()
        self._build()

    @Slot()
    def _change_view_number(self):
        new_num: int = self.sender().data()
        with CancellableAction(self.mng, CancelOp.ALL_VIEWS) as a:
            a.name = _translate('undo', 'Change view number %i to %i') % (
                self.mng.view_number, new_num)
            self.mng.change_view_number(new_num)

    @Slot()
    def _remove_all_other_views(self):
        with CancellableAction(self.mng, CancelOp.ALL_VIEWS) as a:
            a.name = self.sender().text()
            self.mng.remove_all_other_views()

    @Slot()
    def _new_view(self):
        with CancellableAction(self.mng, CancelOp.ALL_VIEWS) as a:
            a.name = self.sender().text()
            self.mng.new_view()

    @Slot()
    def _remove_view(self):
        with CancellableAction(self.mng, CancelOp.ALL_VIEWS) as a:
            a.name = self.sender().text()
            self.mng.remove_view(self.mng.view_number)
    
    def showEvent(self, event) -> None:
        self._build()
        super().showEvent(event)