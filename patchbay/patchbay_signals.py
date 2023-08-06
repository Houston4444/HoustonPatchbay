
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

    theme_changed = pyqtSignal(str)

    # theses signals send int because they are related to checkboxes
    # but the int value is 0 or 1
    graceful_names_changed = pyqtSignal(int)
    a2j_grouped_changed = pyqtSignal(int)
    alsa_midi_enabled_changed = pyqtSignal(int)
    group_shadows_changed = pyqtSignal(int)
    auto_select_items_changed = pyqtSignal(int)
    elastic_changed = pyqtSignal(int)
    borders_nav_changed = pyqtSignal(int)
    prevent_overlap_changed = pyqtSignal(int)
    
    max_port_width_changed = pyqtSignal(int)
    default_zoom_changed = pyqtSignal(int)
    scene_scale_changed = pyqtSignal(float)
    
    connection_added = pyqtSignal(int)
    connection_removed = pyqtSignal(int)

    def __init__(self):
        QObject.__init__(self)