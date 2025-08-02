from dataclasses import dataclass


@dataclass
class TransportPosition:
    frame: int
    rolling: bool
    valid_bbt: bool
    bar: int
    beat: int
    tick: int
    beats_per_minutes: float