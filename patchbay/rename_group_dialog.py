
from qtpy.QtCore import Slot
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QDialog, QDialogButtonBox, QApplication


from .ui.rename_group import Ui_RenameGroupDialog


_translate = QApplication.translate


class RenameGroupDialog(QDialog):
    def __init__(self, parent, group_name: str, pretty_name: str):
        super().__init__(parent)
        self.ui = Ui_RenameGroupDialog()
        self.ui.setupUi(self)
        self.ui.labelGroupName.setText(f'<strong>{group_name}</strong>')
        
        ok_button = self.ui.buttonBox.button(
            QDialogButtonBox.StandardButton.Ok)
        self._ok_text = ok_button.text()
        self._ok_icon = ok_button.icon()
        
        self.ui.lineEditPrettyName.setText(pretty_name)
        self.ui.lineEditPrettyName.selectAll()
        self.ui.lineEditPrettyName.textEdited.connect(self._text_edited)

    @Slot(str)    
    def _text_edited(self, text: str):
        ok_button = self.ui.buttonBox.button(
            QDialogButtonBox.StandardButton.Ok)
        
        if not text:
            ok_button.setText(_translate('rename', 'Clear'))
            ok_button.setIcon(QIcon.fromTheme('edit-clear'))
        else:
            ok_button.setText(self._ok_text)
            ok_button.setIcon(self._ok_icon)
            
    def pretty_name(self) -> str:
        return self.ui.lineEditPrettyName.text()