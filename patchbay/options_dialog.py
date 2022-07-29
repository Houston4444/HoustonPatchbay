
from typing import TYPE_CHECKING
from PyQt5.QtWidgets import QDialog, QApplication, QInputDialog, QMessageBox, QWidget
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtCore import Qt, pyqtSignal, QProcess, QSettings


from .patchcanvas import patchcanvas
from .tools_widgets import is_dark_theme
from .ui.canvas_options import Ui_CanvasOptions

if TYPE_CHECKING:
    from .patchbay_manager import PatchbayManager


_translate = QApplication.translate


class CanvasOptionsDialog(QDialog):
    theme_changed = pyqtSignal(str)
    
    def __init__(self, parent: QWidget, manager: 'PatchbayManager',
                 settings: QSettings =None):
        QDialog.__init__(self, parent)
        self.ui = Ui_CanvasOptions()
        self.ui.setupUi(self)
        
        sg = manager.sg
        self._settings = settings

        if settings is not None:
            self.ui.checkBoxGracefulNames.setChecked(
                settings.value('Canvas/use_graceful_names', True, type=bool))
            self.ui.checkBoxA2J.setChecked(
                settings.value('Canvas/group_a2j_ports', True, type=bool))
            self.ui.checkBoxShadows.setChecked(
                settings.value('Canvas/box_shadows', False, type=bool))
            self.ui.checkBoxAutoSelectItems.setChecked(
                settings.value('Canvas/auto_select_items', False, type=bool))
            self.ui.checkBoxElastic.setChecked(
                settings.value('Canvas/elastic', True, type=bool))
            self.ui.checkBoxBordersNavigation.setChecked(
                settings.value('Canvas/borders_navigation', True, type=bool))
            self.ui.checkBoxPreventOverlap.setChecked(
                settings.value('Canvas/prevent_overlap', True, type=bool))
            self.ui.spinBoxMaxPortWidth.setValue(
                settings.value('Canvas/max_port_width', 170, type=int))

        self.ui.comboBoxTheme.activated.connect(self._theme_box_activated)
        self.ui.pushButtonEditTheme.clicked.connect(self._edit_theme)
        self.ui.pushButtonDuplicateTheme.clicked.connect(self._duplicate_theme)
        
        self._current_theme_ref = ''
        self._theme_list = list[dict]()
        
        # connect checkboxs and spinbox signals to patchbays signals
        self.ui.checkBoxGracefulNames.stateChanged.connect(
            manager.sg.graceful_names_changed)
        self.ui.checkBoxA2J.stateChanged.connect(
            manager.sg.a2j_grouped_changed)
        self.ui.checkBoxShadows.stateChanged.connect(
            manager.sg.group_shadows_changed)
        self.ui.checkBoxAutoSelectItems.stateChanged.connect(
            manager.sg.auto_select_items_changed)
        self.ui.checkBoxElastic.stateChanged.connect(
            manager.sg.elastic_changed)
        self.ui.checkBoxBordersNavigation.stateChanged.connect(
            manager.sg.borders_nav_changed)
        self.ui.checkBoxPreventOverlap.stateChanged.connect(
            manager.sg.prevent_overlap_changed)
        self.ui.spinBoxMaxPortWidth.valueChanged.connect(
            manager.sg.max_port_width_changed)

    def _theme_box_activated(self):
        current_theme_ref_id = self.ui.comboBoxTheme.currentData(Qt.UserRole)
        if current_theme_ref_id == self._current_theme_ref:
            return
        
        for theme_dict in self._theme_list:
            if theme_dict['ref_id'] == current_theme_ref_id:
                self.ui.pushButtonEditTheme.setEnabled(bool(theme_dict['editable']))
                break

        self.theme_changed.emit(current_theme_ref_id)
        
    def _duplicate_theme(self):        
        new_theme_name, ok = QInputDialog.getText(
            self, _translate('patchbay_theme', 'New Theme Name'),
            _translate('patchbay_theme', 'Choose a name for the new theme :'))
        
        if not new_theme_name or not ok:
            return
        
        new_theme_name = new_theme_name.replace('/', '⁄')

        err = patchcanvas.copy_and_load_current_theme(new_theme_name)
        
        if err:
            message = _translate(
                'patchbay_theme', 'The copy of the theme directory failed')
            
            QMessageBox.warning(
                self, _translate('patchbay_theme', 'Copy failed !'), message)

    def _edit_theme(self):
        current_theme_ref_id = self.ui.comboBoxTheme.currentData(Qt.UserRole)
        
        for theme_dict in self._theme_list:
            if theme_dict['ref_id'] == current_theme_ref_id:
                if not theme_dict['editable']:
                    patchcanvas.copy_theme_to_editable_path_and_load(
                        theme_dict['file_path'])

                # start the text editor process
                QProcess.startDetached('xdg-open', [theme_dict['file_path']])
                break

    def set_theme_list(self, theme_list: list[dict]):
        self.ui.comboBoxTheme.clear()
        del self._theme_list
        self._theme_list = theme_list

        dark = '-dark' if is_dark_theme(self) else ''
        user_icon = QIcon(QPixmap(f':scalable/breeze{dark}/im-user'))

        for theme_dict in theme_list:
            if theme_dict['editable']:
                self.ui.comboBoxTheme.addItem(
                    user_icon, theme_dict['name'], theme_dict['ref_id'])
            else:
                self.ui.comboBoxTheme.addItem(theme_dict['name'], theme_dict['ref_id'])

    def set_theme(self, theme_ref: str):
        for i in range(self.ui.comboBoxTheme.count()):
            ref_id = self.ui.comboBoxTheme.itemData(i, Qt.UserRole)
            if ref_id == theme_ref:
                self.ui.comboBoxTheme.setCurrentIndex(i)
                break
        else:
            # the new theme has not been found
            # update the list and select it if it exists
            self.set_theme_list(patchcanvas.list_themes())
            for i in range(self.ui.comboBoxTheme.count()):
                ref_id = self.ui.comboBoxTheme.itemData(i, Qt.UserRole)
                if ref_id == theme_ref:
                    self.ui.comboBoxTheme.setCurrentIndex(i)
                    break

    def get_gracious_names(self) -> bool:
        return self.ui.checkBoxGracefulNames.isChecked()

    def get_a2j_grouped(self) -> bool:
        return self.ui.checkBoxA2J.isChecked()

    def get_group_shadows(self) -> bool:
        return self.ui.checkBoxShadows.isChecked()

    def get_auto_select_items(self) -> bool:
        return self.ui.checkBoxAutoSelectItems.isChecked()

    def get_elastic(self) -> bool:
        return self.ui.checkBoxElastic.isChecked()

    def get_borders_nav(self) -> bool:
        return self.ui.checkBoxBordersNavigation.isChecked()

    def get_prevent_overlap(self) -> bool:
        return self.ui.checkBoxPreventOverlap.isChecked()

    def get_max_port_width(self) -> int:
        return self.ui.spinBoxMaxPortWidth.value()

    def showEvent(self, event):
        self.set_theme_list(patchcanvas.list_themes())
        self.set_theme(patchcanvas.get_theme())
        QDialog.showEvent(self, event)

    def closeEvent(self, event):
        if self._settings is not None:
            self._settings.setValue('Canvas/use_graceful_names',
                                    self.get_gracious_names())
            self._settings.setValue('Canvas/group_a2j_ports',
                                    self.get_a2j_grouped())
            self._settings.setValue('Canvas/box_shadows',
                                    self.get_group_shadows())
            self._settings.setValue('Canvas/auto_select_items',
                                    self.get_auto_select_items())
            self._settings.setValue('Canvas/elastic',
                                    self.get_elastic())
            self._settings.setValue('Canvas/borders_navigation',
                                    self.get_borders_nav())
            self._settings.setValue('Canvas/prevent_overlap',
                                    self.get_prevent_overlap())
            self._settings.setValue('Canvas/max_port_width',
                                    self.get_max_port_width())
            self._settings.setValue('Canvas/theme',
                                    self.ui.comboBoxTheme.currentData())
        QDialog.closeEvent(self, event)
