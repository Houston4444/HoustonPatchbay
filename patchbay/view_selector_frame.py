from typing import TYPE_CHECKING, Optional
from math import ceil
from PyQt5.QtWidgets import QWidget, QApplication, QMenu, QAbstractItemDelegate, QStyleOptionViewItem
from PyQt5.QtGui import QIcon, QKeyEvent, QPen, QColor, QFont, QFontMetrics, QFontMetricsF
from PyQt5.QtCore import pyqtSlot, Qt, QSize, QPointF, QRect, QRectF

from .ui.view_selector import Ui_Form

if TYPE_CHECKING:
    from patchbay_manager import PatchbayManager
    from surclassed_widgets import ViewsComboBox


_translate = QApplication.translate


class ItemmDeleg(QAbstractItemDelegate):
    def __init__(self, parent: 'ViewsComboBox'):
        super().__init__(parent)
        self.mng: Optional['PatchbayManager'] = None
        self._parent = parent
        self._highlighted_index = -1
        
        font = QFont()

        self._height = int(font.pointSize() * 2.5)
        self._width = 500
    
    def sizeHint(self, option: 'QStyleOptionViewItem', index: int) -> QSize:
        size = QSize(self._width, self._height)
        return size
    
    def highlighted(self, index: int):
        self._highlighted_index = index
    
    def get_needed_width(self) -> int:
        font = QApplication.font()
        # font = QFont()
        itafont = QFont()
        itafont.setItalic(True)
        needed_width = 0.0
        
        for index in range(self._parent.count()):
            view_name = self._parent.itemText(index)
            view_num = self._parent.itemData(index)
            
            if self.mng is not None:
                view_name = self.mng.views_datas[view_num].name
                        
            font = QFont()
            name_width = QFontMetricsF(font).width(view_name)
            if 1 <= view_num <= 9:
                num_width = QFontMetricsF(itafont).width(f'Alt+{view_num}')
            else:
                num_width = QFontMetricsF(font).width(str(view_num))
            
            needed_width = max(needed_width, name_width + num_width + 30.0)
            
        return ceil(needed_width)
    
    def set_width(self, width: int):
        self._width = width
    
    def set_patchbay_manager(self, mng: 'PatchbayManager'):
        self.mng = mng
    
    def paint(self, painter, option, index):        
        row = index.row()
        painter.save()
        
        if row == self._highlighted_index:
            pen = QPen(Qt.NoPen)
            bg = QApplication.palette().alternateBase()
            # bg = QColor(127, 127, 127, 70)
            
            painter.setPen(pen)
            painter.setBrush(bg)
            painter.drawRect(QRect(0, row * self._height, self._width, self._height))
        
        text_brush = QApplication.palette().highlightedText()
        font = QFont()
        painter.setFont(font)
        
        text_y = font.pointSize() + 0.5 * (self._height - font.pointSize()) + row * self._height
        text_pos = QPointF(6.0, text_y)
        num_zone_x = self._parent.width() - 30.0
        num_pos = QPointF(num_zone_x + 4.0, text_y)
        
        view_name = self._parent.itemText(row)
        view_num = self._parent.itemData(row)

        painter.setBrush(QColor(127, 127, 127, 80))
        painter.setPen(QPen(Qt.NoPen))
        # painter.drawRect(
        #     QRectF(num_zone_x, 1.0 + row * self._HEIGHT,
        #            20.0, self._HEIGHT - 2.0))

        painter.setPen(QPen(text_brush, 1.0))
        painter.drawText(text_pos, view_name)
        
        num_text = str(view_num)
        
        if 1 <= view_num <= 9:
            num_text = f'Alt+{view_num}'
            font.setItalic(True)
            painter.setFont(font)

        num_pos.setX(self._width - QFontMetricsF(font).width(num_text) - 4.0)

        painter.drawText(num_pos, num_text)
        
        # painter.drawText(num_pos, str(view_num))
        
        painter.restore()
    


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
        self._act_remove = self._menu.addAction(
            QIcon.fromTheme('edit-delete'),
            _translate('views_menu', 'Remove'))
        self._act_remove.triggered.connect(self._remove)
        
        self._menu.addSeparator()
        self._act_new_view = self._menu.addAction(
            QIcon.fromTheme('list-add'),
            _translate('views_menu', 'New View'))
        self._act_new_view.triggered.connect(self._new_view)
        
        self.ui.toolButtonRemove.setMenu(self._menu)
        
        self._selected_index = 0
        self._selected_view = 1
        self._editing_text = ''
        
        self.item_dellag = ItemmDeleg(self.ui.comboBoxView)
        self.ui.comboBoxView.setItemDelegate(self.item_dellag)
        self.ui.comboBoxView.highlighted.connect(self.item_dellag.highlighted)
    
    def _fill_combo(self):
        if self.mng is None:
            return

        self._filling_combo = True
        self.ui.comboBoxView.clear()

        index = 0
        view_names = set[str]()
        
        for view_num in self.mng.views.keys():
            view_data = self.mng.views_datas.get(view_num)
            if view_data is None or not view_data.name:
                view_name = _translate('views_widget', f'View {view_num}')
            else:
                view_name = view_data.name
            
            full_view_name = view_name
            view_names.add(full_view_name)

            self.ui.comboBoxView.addItem(full_view_name)
            self.ui.comboBoxView.setItemData(index, view_num)

            index += 1
        
        # select the current view
        index = 0
        for view_num in self.mng.views.keys():
            if view_num == self.mng.view_number:
                self.ui.comboBoxView.setCurrentIndex(index)
            index += 1
        
        needed_width = self.item_dellag.get_needed_width()
        self.item_dellag.set_width(needed_width)
        self.ui.comboBoxView.view().setMinimumWidth(
            self.item_dellag.get_needed_width())

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
        self._fill_combo()

    @pyqtSlot(int) 
    def _change_view(self, index: int):
        if self._filling_combo:
            return
        
        self.ui.comboBoxView.setEditable(False)
        
        if self.mng is not None:
            view_number = self.ui.comboBoxView.itemData(index)
            if isinstance(view_number, int):
                if view_number >= 0:
                    self.mng.change_view(view_number)
                elif view_number == -1:
                    self.mng.new_view()
            
    @pyqtSlot()
    def _rename(self):
        if self.ui.comboBoxView.isEditable():
            self.ui.comboBoxView.setEditable(False)
        else:
            self.ui.comboBoxView.set_editable()

    @pyqtSlot()
    def _remove(self):
        index: int = self.ui.comboBoxView.currentData()
        
        if self.mng is None:
            return
        
        if self.mng.views.get(index) is None:
            return
        
        ex_view_num = -1
        
        for view_num in self.mng.views.keys():
            if view_num < index:
                ex_view_num = view_num
            
            elif view_num == index:
                if ex_view_num >= 0:
                    self.mng.change_view(ex_view_num)
                    self.mng.remove_view(index)
                    break
            
            elif view_num > index:
                self.mng.change_view(view_num)
                self.mng.remove_view(index)
                break
                
    @pyqtSlot()
    def _new_view(self):
        if self.mng is not None:
            self.mng.new_view()

    def write_view_name(self, view_number: int, name: str):
        if self.mng is not None:
            self.mng.write_view_data(view_number, name=name)

    def keyPressEvent(self, event: QKeyEvent):
        if (self.ui.comboBoxView.isEditable()
                and event.key() in (Qt.Key_Return, Qt.Key_Enter)):
            self.mng.write_view_data(
                self._selected_view, name=self._editing_text)
            self.ui.comboBoxView.setEditable(False)
            self.ui.comboBoxView.setCurrentIndex(self._selected_index)
            event.ignore()
            return

        super().keyPressEvent(event)