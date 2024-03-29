
from pathlib import Path
from typing import TYPE_CHECKING
from PyQt5.QtWidgets import (QDialog, QApplication, QInputDialog,
                             QMessageBox, QWidget, QFileDialog)
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtCore import Qt, QProcess, QSettings

from .patchcanvas import patchcanvas, xdg
from .patchcanvas.theme_manager import ThemeData
from .tools_widgets import is_dark_theme
from .ui.canvas_options import Ui_CanvasOptions

if TYPE_CHECKING:
    from .patchbay_manager import PatchbayManager


_translate = QApplication.translate


class CanvasOptionsDialog(QDialog):    
    def __init__(self, parent: QWidget, manager: 'PatchbayManager',
                 settings: QSettings =None):
        QDialog.__init__(self, parent)
        self.ui = Ui_CanvasOptions()
        self.ui.setupUi(self)
        
        self.manager = manager
        sg = manager.sg
        self._settings = settings
        self._theme_changed = sg.theme_changed
        
        box_layout_dict = {
            1.0: _translate('box_layout', 'Choose the smallest area'),
            1.1: _translate('box_layout', 'Prefer large boxes'),
            1.4: _translate('box_layout', 'Almost only large boxes'),
            2.0: _translate('box_layout', 'Force large boxes')
        }
        
        for ratio, text in box_layout_dict.items():
            self.ui.comboBoxBoxesAutoLayout.addItem(text, ratio)

        if settings is not None:
            self.ui.checkBoxGracefulNames.setChecked(
                settings.value('Canvas/use_graceful_names', True, type=bool))
            self.ui.checkBoxA2J.setChecked(
                settings.value('Canvas/group_a2j_ports', True, type=bool))
            self.ui.checkBoxAlsa.setChecked(
                settings.value('Canvas/alsa_midi_enabled', False, type=bool))
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
            self.ui.spinBoxDefaultZoom.setValue(
                settings.value('Canvas/default_zoom', 100, type=int))
            
            layout_ratio = settings.value(
                'Canvas/grouped_box_auto_layout_ratio', 1.0, type=float)
            
            if layout_ratio <= 1.0:
                box_index = 0
            elif layout_ratio <= 1.3:
                box_index = 1
            elif layout_ratio < 2.0:
                box_index = 2
            else:
                box_index = 3
                
            self.ui.comboBoxBoxesAutoLayout.setCurrentIndex(box_index)

        self.ui.comboBoxTheme.activated.connect(self._theme_box_activated)
        self.ui.pushButtonEditTheme.clicked.connect(self._edit_theme)
        self.ui.pushButtonDuplicateTheme.clicked.connect(self._duplicate_theme)
        self.ui.pushButtonPatchichiExport.clicked.connect(self._export_to_patchichi)
        
        self._current_theme_ref = ''
        self._theme_list = list[ThemeData]()
        
        # connect checkboxs and spinbox signals to patchbays signals
        self.ui.checkBoxGracefulNames.stateChanged.connect(
            manager.sg.graceful_names_changed)
        self.ui.checkBoxA2J.stateChanged.connect(
            manager.sg.a2j_grouped_changed)
        self.ui.checkBoxAlsa.stateChanged.connect(
            manager.sg.alsa_midi_enabled_changed)
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
        self.ui.spinBoxDefaultZoom.valueChanged.connect(
            self._change_default_zoom)
        self.ui.comboBoxBoxesAutoLayout.currentIndexChanged.connect(
            self._grouped_box_auto_layout_changed)

    def _change_default_zoom(self, value: int):
        patchcanvas.set_default_zoom(value)
        patchcanvas.zoom_reset()

    def _theme_box_activated(self):
        current_theme_ref_id = self.ui.comboBoxTheme.currentData(Qt.UserRole)
        if current_theme_ref_id == self._current_theme_ref:
            return
        
        for theme_data in self._theme_list:
            if theme_data.ref_id == current_theme_ref_id:
                self.ui.pushButtonEditTheme.setEnabled(theme_data.editable)
                break

        self._theme_changed.emit(current_theme_ref_id)
        
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
        
        for theme_data in self._theme_list:
            if (theme_data.ref_id == current_theme_ref_id
                    and theme_data.editable):
                # start the text editor process
                QProcess.startDetached('xdg-open', [theme_data.file_path])
                break

    def _export_to_patchichi(self):
        scenes_dir = xdg.xdg_data_home() / 'Patchichi' / 'scenes'

        if not scenes_dir.exists():
            try:
                scenes_dir.mkdir()
            except:
                pass
        
        if not scenes_dir.is_dir():
            scenes_dir = Path.home()
        
        ret, ok = QFileDialog.getSaveFileName(
            self,
            _translate('file_dialog', 'Where do you want to save this patchbay scene ?'),
            str(scenes_dir),
            _translate('file_dialog', 'Patchichi files (*.patchichi.json)'))

        if not ok:
            return
        
        self.manager.export_to_patchichi_json(Path(ret))

    def set_theme_list(self, theme_list: list[ThemeData]):
        self.ui.comboBoxTheme.clear()
        del self._theme_list
        self._theme_list = theme_list

        dark = '-dark' if is_dark_theme(self) else ''
        user_icon = QIcon(QPixmap(f':scalable/breeze{dark}/im-user'))

        for theme_data in theme_list:
            if theme_data.editable:
                self.ui.comboBoxTheme.addItem(
                    user_icon, theme_data.name, theme_data.ref_id)
            else:
                self.ui.comboBoxTheme.addItem(theme_data.name, theme_data.ref_id)

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
                    
                    # update the edit button enable state
                    for theme_data in self._theme_list:
                        if theme_data.ref_id == ref_id:
                            self.ui.pushButtonEditTheme.setEnabled(
                                theme_data.editable)
                            break
                    break

    def enable_alsa_midi(self, yesno: bool):
        self.ui.checkBoxAlsa.setEnabled(yesno)
        if yesno:
            self.ui.checkBoxAlsa.setToolTip('')
        else:
            self.ui.checkBoxAlsa.setToolTip(
                _translate('alsa_midi', 
                           "ALSA python lib version is not present or too old.\n"
                           "Ensure to have python3-pyalsa >= 1.2.4"))

    def _grouped_box_auto_layout_changed(self, index: int):
        patchcanvas.set_grouped_box_layout_ratio(
            self.ui.comboBoxBoxesAutoLayout.currentData())

    def showEvent(self, event):
        self.set_theme_list(patchcanvas.list_themes())
        self.set_theme(patchcanvas.get_theme())
        QDialog.showEvent(self, event)

    def closeEvent(self, event):
        if self._settings is not None:
            self._settings.setValue('Canvas/use_graceful_names',
                                    self.ui.checkBoxGracefulNames.isChecked())
            self._settings.setValue('Canvas/group_a2j_ports',
                                    self.ui.checkBoxA2J.isChecked())
            self._settings.setValue('Canvas/alsa_midi_enabled',
                                    self.ui.checkBoxAlsa.isChecked())
            self._settings.setValue('Canvas/box_shadows',
                                    self.ui.checkBoxShadows.isChecked())
            self._settings.setValue('Canvas/auto_select_items',
                                    self.ui.checkBoxAutoSelectItems.isChecked())
            self._settings.setValue('Canvas/elastic',
                                    self.ui.checkBoxElastic.isChecked())
            self._settings.setValue('Canvas/borders_navigation',
                                    self.ui.checkBoxBordersNavigation.isChecked())
            self._settings.setValue('Canvas/prevent_overlap',
                                    self.ui.checkBoxPreventOverlap.isChecked())
            self._settings.setValue('Canvas/max_port_width',
                                    self.ui.spinBoxMaxPortWidth.value())
            self._settings.setValue('Canvas/default_zoom',
                                    self.ui.spinBoxDefaultZoom.value())
            self._settings.setValue('Canvas/theme',
                                    self.ui.comboBoxTheme.currentData())
            self._settings.setValue('Canvas/grouped_box_auto_layout_ratio',
                                    self.ui.comboBoxBoxesAutoLayout.currentData())
        QDialog.closeEvent(self, event)
