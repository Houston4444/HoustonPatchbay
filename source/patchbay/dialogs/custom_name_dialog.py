from typing import Union

from qtpy.QtCore import Slot # type:ignore
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QDialog, QDialogButtonBox, QApplication

from patshared import Naming
from ..patchcanvas.utils import portgroup_name_splitted
from ..bases.group import Group
from ..bases.port import Port
from ..bases.portgroup import Portgroup

from ..ui.rename_group import Ui_RenameGroupDialog


_translate = QApplication.translate


class CustomNameDialog(QDialog):
    def __init__(self, element: Union[Group, Port, Portgroup]):
        super().__init__(element.manager.main_win)

        self.ui = Ui_RenameGroupDialog()
        self.ui.setupUi(self)
        
        self.element = element
        
        if isinstance(element, Portgroup):
            pg_name, suffixes = portgroup_name_splitted(
                *[p.cnv_name for p in element.ports])
            label_intro = _translate(
                'custom_name', 'Set a custom name for the portgroup :')
            name = pg_name + '|'.join(suffixes)
            suggest = pg_name.strip()
        else:
            if isinstance(element, Group):
                label_intro = _translate(
                    'custom_name', 'Set a custom name for the group :')
            else:
                label_intro = _translate(
                    'custom_name', 'Set a custom name for the port :')
            
            name = element.cnv_name
            if element.custom_name:
                suggest = element.custom_name
            elif element.mdata_pretty_name:
                suggest = element.mdata_pretty_name
            else:
                suggest = element.graceful_name
        
        self.ui.labelIntro.setText(label_intro)
        self.ui.labelGroupName.setText(f'<strong>{name}</strong>')
        
        ok_button = self.ui.buttonBox.button(
            QDialogButtonBox.StandardButton.Ok) # type:ignore
        self._ok_text = ok_button.text()
        self._ok_icon = ok_button.icon()
        
        self.ui.lineEditCustomName.setText(suggest)
        self.ui.lineEditCustomName.selectAll()
        self.ui.lineEditCustomName.textEdited.connect(self._text_edited)
        
        save_in_jack: bool = self.element.manager._settings.value(
            'Canvas/save_pretty_name_in_jack', True, type=bool)
        
        has_jack_uuid = False

        if isinstance(self.element, Portgroup):
            if self.element.type.is_jack:
                for port in self.element.ports:
                    if port.uuid:
                        has_jack_uuid = True
                        break

        elif isinstance(self.element, Port):
            if self.element.type.is_jack:
                has_jack_uuid = bool(self.element.uuid)
        
        else:
            has_jack_uuid = bool(self.element.uuid)
        
        if (has_jack_uuid
                and (Naming.CUSTOM
                     in self.element.manager.jack_export_naming)):
            save_in_jack = True
        
        if (not has_jack_uuid
                or (Naming.CUSTOM
                    in self.element.manager.jack_export_naming)):
            self.ui.checkBoxExportJack.setVisible(False)
        
        self.ui.checkBoxExportJack.setChecked(save_in_jack)

    @Slot(str)    
    def _text_edited(self, text: str):
        ok_button = self.ui.buttonBox.button(
            QDialogButtonBox.StandardButton.Ok) # type:ignore
        
        if not text:
            ok_button.setText(_translate('rename', 'Clear'))
            ok_button.setIcon(QIcon.fromTheme('edit-clear')) # type:ignore
        else:
            ok_button.setText(self._ok_text)
            ok_button.setIcon(self._ok_icon)
            
    def pretty_name(self) -> str:
        return self.ui.lineEditCustomName.text()
    
    def save_in_metadata(self) -> bool:
        return self.ui.checkBoxExportJack.isChecked()
    
    def exec(self) -> int:
        ret = super().exec()
        self.element.manager._settings.setValue(
            'Canvas/save_pretty_name_in_jack',
            self.save_in_metadata())
        
        return ret