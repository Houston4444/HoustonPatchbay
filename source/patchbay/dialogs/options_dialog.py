
from pathlib import Path
from typing import TYPE_CHECKING

from qtpy.QtCore import Qt, QProcess, QSettings, Slot
from qtpy.QtGui import QIcon, QPixmap
if TYPE_CHECKING:
    # FIX : QAction not found by pylance
    from qtpy.QtGui import QAction
from qtpy.QtWidgets import (QDialog, QApplication, QInputDialog,
                             QMessageBox, QWidget, QFileDialog, QAction)


from patshared import Naming, PrettyDiff
from ..patchcanvas import patchcanvas, xdg
from ..patchcanvas.theme_manager import ThemeData
from ..patchcanvas.init_values import GridStyle
from ..tools_widgets import is_dark_theme
from ..ui.canvas_options import Ui_CanvasOptions

if TYPE_CHECKING:
    from ..patchbay_manager import PatchbayManager


_translate = QApplication.translate


class CanvasOptionsDialog(QDialog):    
    def __init__(self, parent: QWidget, manager: 'PatchbayManager',
                 settings: QSettings =None):
        QDialog.__init__(self, parent)
        self.ui = Ui_CanvasOptions()
        self.ui.setupUi(self)
        
        self.mng = manager
        
        box_layout_dict = {
            1.0: _translate('box_layout', 'Choose the smallest area'),
            1.1: _translate('box_layout', 'Prefer large boxes'),
            1.4: _translate('box_layout', 'Almost only large boxes'),
            2.0: _translate('box_layout', 'Force large boxes')
        }
        
        grid_style_dict = {
            GridStyle.NONE: _translate('grid_style', 'None'),
            GridStyle.TECHNICAL_GRID: _translate('grid_style', 'Technical Grid'),
            GridStyle.GRID: _translate('grid_style', 'Grid'),
            GridStyle.CHESSBOARD: _translate('grid_style', 'Chessboard')
        }
        
        for ratio, text in box_layout_dict.items():
            self.ui.comboBoxBoxesAutoLayout.addItem(text, ratio)

        for grid_style in GridStyle:
            self.ui.comboBoxGridStyle.addItem(
                grid_style_dict[grid_style], grid_style)

        self.set_values()

        self.ui.comboBoxTheme.activated.connect(self._theme_box_activated)
        self.ui.pushButtonEditTheme.clicked.connect(self._edit_theme)
        self.ui.pushButtonDuplicateTheme.clicked.connect(self._duplicate_theme)
        self.ui.pushButtonPatchichiExport.clicked.connect(self._export_to_patchichi)
        
        self._current_theme_ref = ''
        self._theme_list = list[ThemeData]()
        
        # connect checkboxs and spinbox signals to patchbays signals
        self.ui.checkBoxA2J.stateChanged.connect(
            manager.sg.a2j_grouped_changed)
        self.ui.checkBoxAlsa.stateChanged.connect(
            manager.sg.alsa_midi_enabled_changed)
        
        self.ui.checkBoxJackPrettyNames.stateChanged.connect(
            self._naming_changed)
        self.ui.checkBoxInternalPrettyNames.stateChanged.connect(
            self._naming_changed)
        self.ui.checkBoxGracefulNames.stateChanged.connect(
            self._naming_changed)
        self.ui.checkBoxExportPrettyNames.clicked.connect(
            self._jack_export_naming_changed)
        self.ui.pushButtonExportPrettyJack.clicked.connect(
            self._export_pretty_names_to_jack)
        self.ui.pushButtonImportPrettyJack.clicked.connect(
            self._import_pretty_names_from_jack)
        
        self.ui.checkBoxShadows.stateChanged.connect(
            manager.sg.group_shadows_changed)
        self.ui.comboBoxGridStyle.currentIndexChanged.connect(
            self._grid_style_changed)
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
        self.ui.spinBoxGridWidth.valueChanged.connect(
            self._grid_width_changed)
        self.ui.spinBoxGridHeight.valueChanged.connect(
            self._grid_height_changed)

    def set_values(self):
        self.ui.checkBoxA2J.setChecked(
            self.mng.group_a2j_hw)
        self.ui.checkBoxAlsa.setChecked(
            self.mng.alsa_midi_enabled)
        
        self.ui.checkBoxJackPrettyNames.setChecked(
            Naming.METADATA_PRETTY in self.mng.naming)
        self.ui.checkBoxInternalPrettyNames.setChecked(
            Naming.INTERNAL_PRETTY in self.mng.naming)
        self.ui.checkBoxGracefulNames.setChecked(
            Naming.GRACEFUL in self.mng.naming)
        
        b = self.ui.checkBoxExportPrettyNames
        if b.isEnabled():
            b.setChecked(
                Naming.INTERNAL_PRETTY in self.mng.jack_export_naming)
        
        options = patchcanvas.options
        
        self.ui.checkBoxShadows.setChecked(
            options.show_shadows)
        self.ui.comboBoxGridStyle.setCurrentIndex(
            options.grid_style.value)
        self.ui.checkBoxAutoSelectItems.setChecked(
            options.auto_select_items)
        self.ui.checkBoxElastic.setChecked(
            options.elastic)
        self.ui.checkBoxBordersNavigation.setChecked(
            options.borders_navigation)
        self.ui.checkBoxPreventOverlap.setChecked(
            options.prevent_overlap)
        self.ui.spinBoxMaxPortWidth.setValue(
            options.max_port_width)
        self.ui.spinBoxDefaultZoom.setValue(
            options.default_zoom)
        self.ui.spinBoxGridWidth.setValue(
            options.cell_width)
        self.ui.spinBoxGridHeight.setValue(
            options.cell_height)
        
        layout_ratio = options.box_grouped_auto_layout_ratio
        
        if layout_ratio <= 1.0:
            box_index = 0
        elif layout_ratio <= 1.3:
            box_index = 1
        elif layout_ratio < 2.0:
            box_index = 2
        else:
            box_index = 3
            
        self.ui.comboBoxBoxesAutoLayout.setCurrentIndex(box_index)

    @Slot(int)
    def _naming_changed(self, state: int):
        naming = Naming.TRUE_NAME
        if self.ui.checkBoxJackPrettyNames.isChecked():
            naming |= Naming.METADATA_PRETTY
        if self.ui.checkBoxInternalPrettyNames.isChecked():
            naming |= Naming.INTERNAL_PRETTY
        if self.ui.checkBoxGracefulNames.isChecked():
            naming |= Naming.GRACEFUL
        
        self.mng.change_naming(naming)

    @Slot(bool)
    def _jack_export_naming_changed(self, checked: bool):
        jack_exp_naming = Naming.TRUE_NAME
        if self.ui.checkBoxExportPrettyNames.isChecked():
            jack_exp_naming |= Naming.INTERNAL_PRETTY 
        
        self.mng.change_jack_export_naming(jack_exp_naming)

    @Slot()
    def _export_pretty_names_to_jack(self):
        self.mng.export_pretty_names_to_jack()
        
    @Slot()
    def _import_pretty_names_from_jack(self):
        self.mng.import_pretty_names_from_jack()

    def auto_export_pretty_names_changed(self, state: bool):
        # option has been changed from the daemon itself 
        # (probably with ray_control)
        b = self.ui.checkBoxExportPrettyNames
        if b.isEnabled():
            b.setChecked(state)
        else:
            b.setChecked(False)

    def change_pretty_diff(self, pretty_diff: PrettyDiff):
        self.ui.pushButtonExportPrettyJack.setEnabled(
            PrettyDiff.NON_EXPORTED in pretty_diff)
        self.ui.pushButtonImportPrettyJack.setEnabled(
            PrettyDiff.NON_IMPORTED in pretty_diff)

    def set_pretty_names_locked(self, locked: bool):
        b = self.ui.checkBoxExportPrettyNames
        if locked:
            b.setChecked(False)
        b.setEnabled(not locked)

    def _change_default_zoom(self, value: int):
        patchcanvas.set_default_zoom(value)
        patchcanvas.zoom_reset()

    def _theme_box_activated(self):
        current_theme_ref_id: str = self.ui.comboBoxTheme.currentData(
            Qt.ItemDataRole.UserRole)
        if current_theme_ref_id == self._current_theme_ref:
            return
        
        for theme_data in self._theme_list:
            if theme_data.ref_id == current_theme_ref_id:
                self.ui.pushButtonEditTheme.setEnabled(theme_data.editable)
                break

        self.mng.sg.theme_changed.emit(current_theme_ref_id)
        
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
        current_theme_ref_id = self.ui.comboBoxTheme.currentData(
            Qt.ItemDataRole.UserRole)
        
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
            _translate(
                'file_dialog',
                'Where do you want to save this patchbay scene ?'),
            str(scenes_dir),
            _translate('file_dialog', 'Patchichi files (*.patchichi.json)'))

        if not ok:
            return
        
        self.mng.export_to_patchichi_json(Path(ret))

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
                self.ui.comboBoxTheme.addItem(
                    theme_data.name, theme_data.ref_id)

    def set_theme(self, theme_ref: str):
        for i in range(self.ui.comboBoxTheme.count()):
            ref_id = self.ui.comboBoxTheme.itemData(
                i, Qt.ItemDataRole.UserRole)
            if ref_id == theme_ref:
                self.ui.comboBoxTheme.setCurrentIndex(i)
                break
        else:
            # the new theme has not been found
            # update the list and select it if it exists
            self.set_theme_list(patchcanvas.list_themes())
            for i in range(self.ui.comboBoxTheme.count()):
                ref_id = self.ui.comboBoxTheme.itemData(
                    i, Qt.ItemDataRole.UserRole)
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
                _translate(
                    'alsa_midi', 
                    "ALSA python lib version is not present or too old.\n"
                    "Ensure to have python3-pyalsa >= 1.2.4"))

    def _grouped_box_auto_layout_changed(self, index: int):
        patchcanvas.set_grouped_box_layout_ratio(
            self.ui.comboBoxBoxesAutoLayout.currentData())

    def _grid_width_changed(self, value: int):
        patchcanvas.change_grid_width(value)
        
    def _grid_height_changed(self, value: int):
        patchcanvas.change_grid_height(value)

    def _grid_style_changed(self, value: int):
        grid_style: GridStyle = self.ui.comboBoxGridStyle.currentData()
        patchcanvas.change_grid_widget_style(grid_style)

    def showEvent(self, event):
        self.set_theme_list(patchcanvas.list_themes())
        self.set_theme(patchcanvas.get_theme())
        self.set_values()
        QDialog.showEvent(self, event)

    def closeEvent(self, event):
        QDialog.closeEvent(self, event)
