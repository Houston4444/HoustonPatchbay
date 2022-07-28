
from enum import IntEnum
from PyQt5.QtCore import QObject, pyqtSignal

# we need a QObject for pyqtSignal
class SignalsObject(QObject):
    out_thread_order = pyqtSignal()
    to_main_thread = pyqtSignal(object, tuple, dict)
    callback_sig = pyqtSignal(IntEnum, tuple)
    
    port_types_view_changed = pyqtSignal(int)
    full_screen_toggle_wanted = pyqtSignal()
    filters_bar_toggle_wanted = pyqtSignal()

    def __init__(self):
        QObject.__init__(self)