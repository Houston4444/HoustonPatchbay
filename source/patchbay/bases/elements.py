from dataclasses import dataclass
from enum import IntFlag, IntEnum, auto, Flag
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from patchbay_manager import PatchbayManager


class JackPortFlag(IntFlag):
    'Port Flags as defined by JACK'
    IS_INPUT = 0x01
    IS_OUTPUT = 0x02
    IS_PHYSICAL = 0x04
    CAN_MONITOR = 0x08
    IS_TERMINAL = 0x10
    IS_CONTROL_VOLTAGE = 0x100


class TransportViewMode(IntEnum):
    HOURS_MINUTES_SECONDS = 0
    BEAT_BAR_TICK = 1
    FRAMES = 2


class ToolDisplayed(IntFlag):
    UNDO_REDO = auto()
    VIEWS_SELECTOR = auto()
    HIDDENS_BOX = auto()
    PORT_TYPES_VIEW = auto()
    TRANSPORT_CLOCK = auto()
    TRANSPORT_PLAY_STOP = auto()
    TRANSPORT_TEMPO = auto()
    ZOOM_SLIDER = auto()
    BUFFER_SIZE = auto()
    SAMPLERATE = auto()
    LATENCY = auto()
    XRUNS = auto()
    DSP_LOAD = auto()
    ALL = (UNDO_REDO
           | VIEWS_SELECTOR
           | HIDDENS_BOX
           | PORT_TYPES_VIEW
           | TRANSPORT_CLOCK
           | TRANSPORT_PLAY_STOP
           | TRANSPORT_TEMPO
           | ZOOM_SLIDER
           | BUFFER_SIZE
           | SAMPLERATE
           | LATENCY
           | XRUNS
           | DSP_LOAD)
    
    def to_save_string(self) -> str:
        '''return a string containing all flags names
        separated with pipe symbol.'''
        all_strs = list[str]()
        
        for flag in ToolDisplayed:
            if flag is ToolDisplayed.ALL:
                continue

            if self & flag:
                all_strs.append(flag.name)
            else:
                all_strs.append('~' + flag.name)
        
        return '|'.join(all_strs)
    
    def filtered_by_string(self, string: str) -> 'ToolDisplayed':
        '''returns another ToolDisplayed with value filtered
           by string where string contains flags names separated with pipe symbol
           as given by to_save_string method.'''
        return_td = ToolDisplayed(self.value)
        
        for disp_str in string.split('|'):
            delete = False
            if disp_str.startswith('~'):
                delete = True
                disp_str = disp_str[1:]

            if disp_str in ToolDisplayed._member_names_:
                if delete:
                    return_td &= ~ToolDisplayed[disp_str]
                else:
                    return_td |= ToolDisplayed[disp_str]

        return return_td


class CanvasOptimize(IntEnum):
    NORMAL = 0
    '''No particular optimization, objects are added to canvas and redrawn
    directly.'''

    FAST = 1
    '''Objects are added to canvas, but boxes and connections
    are not redrawn. Groups need to be redrawn once finished.'''

    VERY_FAST = 2
    '''Objects are not added to canvas (useful for sort operations)
    objects need to be added to canvas and redrawn once finished'''


class CanvasOptimizeIt:
    '''Context for 'with' statment. save the data at begin and at end
    for undo/redo actions'''
    def __init__(
            self, mng: 'PatchbayManager', canvas_optimize=CanvasOptimize.FAST,
            auto_redraw=False, prevent_overlap=True):
        self.mng = mng
        self._auto_redraw = auto_redraw
        self._prevent_overlap = prevent_overlap
        self._previous_optim = mng.canvas_optimize
        if canvas_optimize > mng.canvas_optimize:
            mng.canvas_optimize = canvas_optimize
            mng.optimize_operation(True)

    def __enter__(self):
        ...

    def __exit__(self, *args, **kwargs):
        self.mng.canvas_optimize = self._previous_optim

        if self.mng.canvas_optimize is CanvasOptimize.NORMAL:
            self.mng.optimize_operation(
                False, auto_redraw=self._auto_redraw,
                prevent_overlap=self._prevent_overlap)


