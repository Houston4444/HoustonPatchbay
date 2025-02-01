from qtpy.QtWidgets import QDialog

from .base_group import Group

from .ui.canvas_group_info import Ui_CanvasGroupInfo


class GroupInfoDialog(QDialog):
    def __init__(self, parent, group: Group):
        super().__init__(parent)
        self.ui = Ui_CanvasGroupInfo()
        self.ui.setupUi(self)
        
        self.ui.labelAlsaClientId.setVisible(False)
        self.ui.labelColonAlsaClientId.setVisible(False)
        self.ui.labelAlsaClientIdNum.setVisible(False)
        
        self.ui.lineEditClientName.setText(group.name)
        self.ui.lineEditUuid.setText(str(group.uuid))
        
        mng = group.manager
        
        contents = ''

        if group.uuid:
            uuid_dict = mng.jack_metadatas.get(group.uuid)
            if uuid_dict is not None:
                for key, value in uuid_dict.items():
                    contents += f'{key}\n{value}\n\n'
            
        self.ui.plainTextEditMetadata.setPlainText(contents)
        
        
        