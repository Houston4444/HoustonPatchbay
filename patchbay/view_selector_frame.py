from typing import TYPE_CHECKING, Optional
from PyQt5.QtWidgets import QWidget, QApplication, QMenu
from PyQt5.QtGui import QIcon, QKeyEvent
from PyQt5.QtCore import pyqtSlot, Qt

from .ui.view_selector import Ui_Form

if TYPE_CHECKING:
    from patchbay_manager import PatchbayManager


_translate = QApplication.translate


class ViewSelectorWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_Form()
        self.ui.setupUi(self)
        self.mng: Optional[PatchbayManager] = None
        
        self.ui.comboBoxView.currentIndexChanged.connect(self._change_view)
        self._filling_combo = False
        
        self._menu = QMenu()
        self._act_rename = self._menu.addAction(
            QIcon.fromTheme('edit-rename'),
            _translate('views_menu', 'Rename'))
        self._act_rename.triggered.connect(self._rename)
        self.ui.toolButtonRemove.setMenu(self._menu)
        
        self._selected_index = 0
        self._selected_view = 1
        self._editing_text = ''
    
    def _fill_combo(self):
        if self.mng is None:
            return

        self._filling_combo = True
        self.ui.comboBoxView.clear()

        index = 0
        for view_num in self.mng.views.keys():
            view_data = self.mng.views_datas.get(view_num)
            if view_data is None or not view_data.name:
                view_name = _translate('views_widget', 'View n°%i') % view_num
            else:
                view_name = view_data.name
            
            full_view_name = f'{view_num} : {view_name}'

            self.ui.comboBoxView.addItem(full_view_name)
            self.ui.comboBoxView.setItemData(index, view_num)

            index += 1
        
        self._filling_combo = False
    
    def set_patchbay_manager(self, mng: 'PatchbayManager'):
        self.mng = mng
        self.mng.sg.view_changed.connect(self._view_changed)
        self.mng.sg.views_changed.connect(self._views_changed)
        self._fill_combo()

    @pyqtSlot(int)
    def _view_changed(self, view_number: int):
        for i in range(self.ui.comboBoxView.count()):
            if self.ui.comboBoxView.itemData(i) == view_number:
                self.ui.comboBoxView.setCurrentIndex(i)
                break

    @pyqtSlot()
    def _views_changed(self):
        print('hop views changed')
        self._fill_combo()

    @pyqtSlot(int) 
    def _change_view(self, index: int):
        if self._filling_combo:
            return
        
        self.ui.comboBoxView.setEditable(False)
        
        if self.mng is not None:
            view_number = self.ui.comboBoxView.itemData(index)
            self.mng.change_view(view_number)
            
    @pyqtSlot()
    def _rename(self):
        self.ui.comboBoxView.set_editable()

    def write_view_name(self, view_number: int, name: str):
        if self.mng is not None:
            self.mng.write_view_data(view_number, name=name)

    def keyPressEvent(self, event: QKeyEvent):
        if (self.ui.comboBoxView.isEditable()
                and event.key() in (Qt.Key_Return, Qt.Key_Enter)):
            print('youlla', self._editing_text)
            self.mng.write_view_data(
                self._selected_view, name=self._editing_text)
            self.ui.comboBoxView.setEditable(False)
            self.ui.comboBoxView.setCurrentIndex(self._selected_index)
            print('slappy', self._selected_index, self._selected_view)
            event.ignore()
            return

        super().keyPressEvent(event)