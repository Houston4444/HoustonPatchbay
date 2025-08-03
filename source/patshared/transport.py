from dataclasses import dataclass
from enum import IntEnum

@dataclass
class TransportPosition:
    frame: int
    rolling: bool
    valid_bbt: bool
    bar: int
    beat: int
    tick: int
    beats_per_minutes: float
    

class TransportWanted(IntEnum):
    NO = 0
    'do not send any transport info'
    
    STATE_ONLY = 1
    'send transport info only when play/pause changed'

    FULL = 2
    'send all transport infos'