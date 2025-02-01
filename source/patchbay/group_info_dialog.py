from qtpy.QtWidgets import QDialog

from .base_group import Group

from .ui.canvas_group_info import Ui_CanvasGroupInfo


class GroupInfoDialog(QDialog):
    def __init__(self, parent, group: Group):
        super().__init__(parent)
        self.ui = Ui_CanvasGroupInfo()
        self.ui.setupUi(self)
        self.group = group
        self.ui.labelAlsaClientId.setVisible(False)
        self.ui.labelColonAlsaClientId.setVisible(False)
        self.ui.labelAlsaClientIdNum.setVisible(False)
        
        self._fill_contents()
        self.ui.toolButtonRefresh.triggered.connect(self._fill_contents)
        
    def _fill_contents(self):
        self.ui.lineEditClientName.setText(self.group.name)
        self.ui.lineEditUuid.setText(str(self.group.uuid))
        
        mng = self.group.manager
        
        contents = ''

        if self.group.uuid:
            uuid_dict = mng.jack_metadatas.get(self.group.uuid)
            if uuid_dict is not None:
                for key, value in uuid_dict.items():
                    contents += f'{key}\n{value}\n\n'
            
        self.ui.plainTextEditMetadata.setPlainText(contents)
        
        
        