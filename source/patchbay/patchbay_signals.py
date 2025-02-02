
from enum import IntEnum
from qtpy.QtCore import QObject, Signal

# we need a QObject for Signal
class SignalsObject(QObject):
    out_thread_order = Signal()
    to_main_thread = Signal(object, tuple, dict)
    callback_sig = Signal(IntEnum, tuple)
    
    view_changed = Signal(int)
    'emitted when the current view has changed [int]'
    
    views_changed = Signal()
    '''emitted when something related to views changed
    (view added, renamed, removed...)'''
    
    port_types_view_changed = Signal(int)
    'emitted when port types view filter changed the view [int]'
    
    hidden_boxes_changed = Signal()
    'emitted when list of hidden boxes has changed'
    
    animation_finished = Signal()
    'emitted when a canvas animation is finished'
    
    group_added = Signal(int)
    '''emitted when a group is added by a port.
    Used only by hiddens indicator. [group_id]'''
    
    group_removed = Signal(int)
    '''emitted when a group is removed
    with the deletion of its last port. [group_id]'''
    
    all_groups_removed = Signal()
    'emitted when all groups are removed.'

    undo_redo_changed = Signal()
    'emitted when an action changed undo/redo state'

    full_screen_toggle_wanted = Signal()
    filters_bar_toggle_wanted = Signal()

    theme_changed = Signal(str)

    # theses signals send int because they are related to checkboxes
    # but the int value is 0 or 1
    a2j_grouped_changed = Signal(int)
    alsa_midi_enabled_changed = Signal(int)
    group_shadows_changed = Signal(int)
    auto_select_items_changed = Signal(int)
    elastic_changed = Signal(int)
    borders_nav_changed = Signal(int)
    prevent_overlap_changed = Signal(int)
    
    max_port_width_changed = Signal(int)
    default_zoom_changed = Signal(int)
    scene_scale_changed = Signal(float)
    
    connection_added = Signal(int)
    connection_removed = Signal(int)
    patch_may_have_changed = Signal()

    def __init__(self):
        QObject.__init__(self)