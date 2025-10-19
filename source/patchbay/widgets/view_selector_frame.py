from typing import TYPE_CHECKING, Optional
from math import ceil

from qtpy.QtWidgets import (
    QWidget, QApplication, QMenu, QAbstractItemDelegate,
    QStyleOptionViewItem)
from qtpy.QtGui import (
    QIcon, QKeyEvent, QPen, QFont, QFontMetricsF,
    QResizeEvent, QColor, QPixmap)
from qtpy.QtCore import Slot, Qt, QSize, QPointF, QRect, QRectF, QModelIndex # type:ignore

from patshared import PortTypesViewFlag
from ..patchcanvas import canvas
from ..cancel_mng import CancelOp, CancellableAction

from ..ui.view_selector import Ui_Form

if TYPE_CHECKING:
    from patchbay_manager import PatchbayManager
    from surclassed_widgets import ViewsComboBox


_translate = QApplication.translate


class ItemmDeleg(QAbstractItemDelegate):
    '''Manage the menu appearance of the views selector combobox'''

    def __init__(self, parent: 'ViewsComboBox'):
        super().__init__(parent)
        self.mng: Optional['PatchbayManager'] = None
        self._parent = parent
        self._highlighted_index = -1
        
        font = QFont()

        self._height = int(font.pointSize() * 2.5)
        self._width = 500
        self._port_colors = [QColor() for i in range(4)]
        
        dark = QApplication.palette().text().color().lightnessF() > 0.5
        color_scheme = 'breeze-dark' if dark else 'breeze'
        
        self._white_image = QPixmap(
            f':scalable/{color_scheme}/color-picker-white.svg').toImage()
    
    def sizeHint(self, option: 'QStyleOptionViewItem',
                 index: QModelIndex) -> QSize:
        return QSize(self._width, self._height)
    
    def highlighted(self, index: int):
        self._highlighted_index = index
    
    def get_needed_width(self) -> int:
        font = QApplication.font()
        itafont = QFont()
        itafont.setItalic(True)
        needed_width = 0.0
        
        for index in range(self._parent.count()):
            view_name = self._parent.itemText(index)
            view_num = self._parent.itemData(index)
            
            if self.mng is not None:
                view_name = self.mng.views[view_num].name
                        
            font = QFont()
            name_width = QFontMetricsF(font).horizontalAdvance(view_name)
            if 1 <= view_num <= 9:
                num_width = QFontMetricsF(itafont).horizontalAdvance(f'Alt+{view_num}')
            else:
                num_width = QFontMetricsF(font).horizontalAdvance(str(view_num))
            
            needed_width = max(needed_width, name_width + num_width + 102.0)
            
        return ceil(needed_width)
    
    def set_width(self, width: int):
        self._width = width
    
    def update_port_colors(self):
        if self.mng is None:
            return
        
        thmp = canvas.theme.port

        if canvas.theme.thumbnail_port_colors.lower() == 'text':
            self._port_colors = [
                thmp.audio.text_color,
                thmp.midi.text_color,
                thmp.cv.text_color,
                thmp.alsa.text_color]
        else:
            self._port_colors = [
                thmp.audio.background_color,
                thmp.midi.background_color,
                thmp.cv.background_color,
                thmp.alsa.background_color]
        
        bg_col = QApplication.palette().base().color()
        bg_ligthness = bg_col.lightnessF()
        pcols = self._port_colors

        if bg_ligthness > 0.5:
            for i in range(len(pcols)):
                while bg_ligthness - pcols[i].lightnessF() < 0.25:
                    pcols[i] = pcols[i].darker()
                    
                    if pcols[i].lightnessF() == 0.0:
                        break
        else:
            for i in range(len(pcols)):                
                while pcols[i].lightnessF() - bg_ligthness < 0.25:
                    pcols[i] = pcols[i].lighter()
                    
                    if pcols[i].lightnessF() == 1.0:
                        break

    def set_patchbay_manager(self, mng: 'PatchbayManager'):
        self.mng = mng
        self.update_port_colors()
    
    def paint(self, painter, option, index):        
        row = index.row()
        painter.save()

        text_brush = QApplication.palette().text()
        
        if row == self._highlighted_index:            
            painter.setPen(QPen(Qt.PenStyle.NoPen))
            painter.setBrush(QApplication.palette().highlight())
            painter.drawRect(QRect(
                0, row * self._height, self._width, self._height))
            painter.setBrush(QApplication.palette().base())
            
            # draw rect under port types view thumbnail with the
            # base color.
            painter.drawRect(QRect(
                self._width - 23, row * self._height + 1,
                22, self._height - 2))

            text_brush = QApplication.palette().highlightedText()

        font = QFont()
        painter.setFont(font)
        
        text_y = (font.pointSize()
                  + 0.5 * (self._height - font.pointSize())
                  + row * self._height)
        text_pos = QPointF(6.0, text_y)
        num_pos = QPointF(0.0, text_y)
        
        view_name = self._parent.itemText(row)
        view_num: int = self._parent.itemData(row)

        painter.setPen(QPen(text_brush, 1.0))
        painter.drawText(text_pos, view_name)
        
        num_text = str(view_num)
        
        if 1 <= view_num <= 9:
            num_text = f'Alt+{view_num}'
            font.setItalic(True)
            painter.setFont(font)

        num_pos.setX(self._width - QFontMetricsF(font).horizontalAdvance(num_text) - 42.0)
        painter.drawText(num_pos, num_text)
        
        if self.mng is not None:
            view_data = self.mng.views.get(view_num)
            ptvs = [PortTypesViewFlag.AUDIO,
                    PortTypesViewFlag.MIDI,
                    PortTypesViewFlag.CV]
            if self.mng.alsa_midi_enabled:
                ptvs.append(PortTypesViewFlag.ALSA)
            
            if view_data is not None:
                xst = self._width - 18
                SPAC = 4
                ptv = view_data.default_port_types_view
                if view_num == self.mng.view_number:
                    ptv = self.mng.port_types_view
                
                for i, ptv_ in enumerate(ptvs):
                    pcol = self._port_colors[i]
                    painter.setPen(QPen(pcol, 2.0))
                    if ptv & ptv_:
                        painter.drawLine(
                            xst + SPAC * i, row * self._height + 6,
                            xst + SPAC * i, (row + 1) * self._height - 6)
                    else:
                        painter.drawLine(
                            xst + SPAC * i,
                            row * self._height + self._height // 2 - 1,
                            xst + SPAC * i,
                            (row + 1) * self._height - self._height // 2 + 1)
                
                if view_data.is_white_list:
                    white_rect = QRectF(
                        xst - 20.0, row * self._height + self._height * 0.5 - 8.0,
                        16.0, 16.0)
                    painter.drawImage(white_rect, self._white_image)
        
        painter.restore()
    

class ViewSelectorWidget(QWidget):
    '''Widget containing tool button for menu
    and combobox for view list'''
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_Form()
        self.ui.setupUi(self)
        self.mng: Optional[PatchbayManager] = None

        self.ui.comboBoxView.currentIndexChanged.connect(self._change_view)
        self._filling_combo = False
        
        self._menu = QMenu()
        self._menu.aboutToShow.connect(self._before_show_menu)

        self.ui.toolButtonRemove.setMenu(self._menu) # type:ignore
        
        self._selected_index = 0
        self._selected_view = 1
        self._editing_text = ''
        
        self.item_dellag = ItemmDeleg(self.ui.comboBoxView)
        self.ui.comboBoxView.setItemDelegate(self.item_dellag)
        self.ui.comboBoxView.highlighted.connect(self.item_dellag.highlighted)
    
    @Slot()
    def _before_show_menu(self):
        self._build_menu()
    
    def _are_there_absents(self) -> bool:
        if self.mng is None:
            return False
        
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
    
    def _build_menu(self):
        if self.mng is None:
            return
        
        self._menu.clear()
        act_rename = self._menu.addAction(
            QIcon.fromTheme('edit-rename'),
            _translate('views_menu', 'Rename'))
        act_rename.triggered.connect(self._rename)
        act_remove = self._menu.addAction(
            QIcon.fromTheme('edit-delete'),
            _translate('views_menu', 'Remove'))
        act_remove.triggered.connect(self._remove)
        
        act_clear_absents = self._menu.addAction(
            QIcon.fromTheme('edit-clear-all'),
            _translate('views_menu', 'Forget the positions of those absents'))
        act_clear_absents.triggered.connect(self._clear_absents)
        
        change_num_menu = QMenu(
            _translate('views_menu', 'Change view number to...'), self._menu)
        change_num_menu.setIcon(QIcon.fromTheme('enumerate'))
        view_nums = [n for n in self.mng.views.keys()]
        
        if self.mng is not None and view_nums:
            n_nums_in_change_menu = max(max(view_nums) + 2, 10)
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

        self._menu.addMenu(change_num_menu)
        
        menu_arrange = QMenu(_translate('views_menu', 'Arrange'), self)
        menu_arrange.setIcon(QIcon.fromTheme('code-block'))
        
        act_arrange_signal = menu_arrange.addAction("%s\tCtrl+Alt+A" %
            _translate('views_menu', 'Follow the signal chain'))
        act_arrange_signal.triggered.connect(self._arrange_follow_signal)
        
        act_arrange_facing = menu_arrange.addAction("%s\tCtrl+Alt+Q" %
            _translate('views_menu', 'Two columns facing each other'))
        act_arrange_facing.triggered.connect(self._arrange_face_to_face)

        self._menu.addMenu(menu_arrange)
        
        self._menu.addSeparator()
        act_remove_others = self._menu.addAction(
            QIcon.fromTheme('edit-delete'),
            _translate('views_menu', 'Remove all other views'))
        act_remove_others.triggered.connect(self._remove_all_other_views)
        
        act_new_view = self._menu.addAction(
            QIcon.fromTheme('list-add'),
            _translate('views_menu', 'New View'))
        act_new_view.triggered.connect(self._new_view)
        
        if len(view_nums) <= 1:
            act_remove.setEnabled(False)
            act_remove_others.setEnabled(False)
        
        if not self._are_there_absents():
            act_clear_absents.setEnabled(False)
    
    def _fill_combo(self):
        if self.mng is None:
            return

        self._filling_combo = True
        self.ui.comboBoxView.clear()

        index = 0
        view_names = set[str]()
        
        for view_num, view_data in self.mng.views.items():
            if not view_data.name:
                view_name = _translate('views', 'View %i') % view_num
            else:
                view_name = view_data.name
            
            view_names.add(view_name)

            self.ui.comboBoxView.addItem(view_name)
            self.ui.comboBoxView.setItemData(index, view_num)

            index += 1
        
        # select the current view
        index = 0
        for view_num in self.mng.views.keys():
            if view_num == self.mng.view_number:
                self.ui.comboBoxView.setCurrentIndex(index)
            index += 1
        
        needed_width = max(
            self.item_dellag.get_needed_width(),
            self.ui.comboBoxView.width() - 6)
        self.item_dellag.set_width(needed_width)
        self.ui.comboBoxView.view().setMinimumWidth(
            self.item_dellag.get_needed_width())

        self._filling_combo = False
    
    def set_patchbay_manager(self, mng: 'PatchbayManager'):
        self.mng = mng
        self.item_dellag.set_patchbay_manager(mng)
        self.mng.sg.port_types_view_changed.connect(
            self._port_types_view_changed)
        self.mng.sg.view_changed.connect(self._view_changed)
        self.mng.sg.views_changed.connect(self._views_changed)
        self.mng.sg.theme_changed.connect(self._theme_changed)
        
        self._fill_combo()
        self._build_menu()

    @Slot(int)
    def _view_changed(self, view_number: int):
        self._filling_combo = True

        for i in range(self.ui.comboBoxView.count()):
            if self.ui.comboBoxView.itemData(i) == view_number:
                self.ui.comboBoxView.setCurrentIndex(i)
                break
        self._build_menu()
        
        self._filling_combo = False

    @Slot()
    def _views_changed(self):
        self._fill_combo()
        self._build_menu()
        
    @Slot(int)
    def _port_types_view_changed(self, ptv_int: int):
        self.ui.comboBoxView.update()

    @Slot(str)
    def _theme_changed(self, theme_name: str):
        self.item_dellag.update_port_colors()
        self.ui.comboBoxView.update()

    @Slot(int) 
    def _change_view(self, index: int):
        if self._filling_combo:
            return
        
        self.ui.comboBoxView.setEditable(False)
        
        if self.mng is not None:
            view_number = self.ui.comboBoxView.itemData(index)
            if isinstance(view_number, int):
                if view_number >= 0:
                    with CancellableAction(
                            self.mng, CancelOp.VIEW_CHOICE) as a:
                        a.name = _translate('views', 'Change view %i -> %i') \
                            % (self.mng.view_number, view_number)
                        self.mng.change_view(view_number)
                elif view_number == -1:
                    self.mng.new_view()
            
    @Slot()
    def _rename(self):
        if self.ui.comboBoxView.isEditable():
            self.ui.comboBoxView.setEditable(False)
        else:
            self.ui.comboBoxView.set_editable()

    @Slot()
    def _remove(self):
        index: int = self.ui.comboBoxView.currentData()
        
        if self.mng is None:
            return
        
        if self.mng.views.get(index) is None:
            return
        
        with CancellableAction(self.mng, CancelOp.ALL_VIEWS) as a:
            a.name = _translate('undo', 'Remove view n°%i') % index
            self.mng.remove_view(index)
    
    @Slot()
    def _clear_absents(self):
        sender_text: str = self.sender().text() # type:ignore
        if self.mng is not None:
            with CancellableAction(self.mng, CancelOp.VIEW) as a:
                a.name = sender_text
                self.mng.clear_absents_in_view()

    @Slot()
    def _change_view_number(self):
        new_num: int = self.sender().data() # type:ignore
        if self.mng is not None:
            with CancellableAction(self.mng, CancelOp.ALL_VIEWS) as a:
                a.name = _translate('undo', 'Change view number %i to %i') % (
                    self.mng.view_number, new_num)
                self.mng.change_view_number(new_num)

    @Slot()
    def _arrange_face_to_face(self):
        if self.mng is not None:
            self.mng.arrange_face_to_face()

    @Slot()
    def _arrange_follow_signal(self):
        if self.mng is not None:
            self.mng.arrange_follow_signal()

    @Slot()
    def _remove_all_other_views(self):
        sender_text: str = self.sender().text() # type:ignore
        if self.mng is not None:
            with CancellableAction(self.mng, CancelOp.ALL_VIEWS) as a:
                a.name = sender_text
                self.mng.remove_all_other_views()

    @Slot()
    def _new_view(self):
        sender_text: str = self.sender().text() # type:ignore
        if self.mng is not None:
            with CancellableAction(self.mng, CancelOp.ALL_VIEWS) as a:
                a.name = sender_text
                self.mng.new_view()

    def write_view_name(self, view_number: int, name: str):
        if self.mng is not None:
            with CancellableAction(self.mng, CancelOp.ALL_VIEWS_NO_POS) as a:
                a.name = _translate('undo', 'View %i renamed to "%s"') % (
                    view_number, name)
                self.mng.write_view_data(view_number, name=name)

    def keyPressEvent(self, event: QKeyEvent):
        if (self.ui.comboBoxView.isEditable()
                and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)):
            if self.mng is not None:
                self.mng.write_view_data(
                    self._selected_view, name=self._editing_text)
            self.ui.comboBoxView.setEditable(False)
            self.ui.comboBoxView.setCurrentIndex(self._selected_index)
            event.ignore()
            return

        super().keyPressEvent(event)
        
    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        
        self.item_dellag.set_width(
            max(self.item_dellag.get_needed_width(),
                self.ui.comboBoxView.width() - 6))