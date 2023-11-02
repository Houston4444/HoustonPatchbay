from enum import IntEnum
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING

from .init_values import PortMode, canvas, BoxLayoutMode
from .utils import next_width_on_grid, next_height_on_grid

if TYPE_CHECKING:
    from .box_widget import BoxWidget

_logger = logging.getLogger(__name__)


class TitleOn(IntEnum):
    TOP = 0
    SIDE = 1
    SIDE_UNDER_ICON = 2


@dataclass()
class PortsMinSizes:
    last_in_pos: float
    last_out_pos: float
    last_inout_pos: float
    ins_width: float
    outs_width: float
    n_in_type_and_subs: int
    n_out_type_and_subs: int
    n_inout_type_and_subs: int
    last_port_mode: PortMode


class BoxLayout:
    @classmethod
    def init_from_box(
            cls, box: 'BoxWidget',
            ports_min_sizes: PortsMinSizes):
        cls.pms = ports_min_sizes
        theme = box.get_theme()
        cls.pen_width = theme.fill_pen().widthF()
        cls.port_spacing = theme.port_spacing()
        cls.hwr = canvas.theme.hardware_rack_width if box._is_hardware else 0
        cls.port_mode = box._current_port_mode
        cls.can_handle_gui = box._can_handle_gui
        cls.is_hardware = box._is_hardware
    
    @classmethod
    def width_for_ports(cls):
        return (cls.pms.ins_width + cls.pms.outs_width + 6.0)
    
    def __init__(self, n_lines: int,
                 layout_mode: BoxLayoutMode,
                 title_on: TitleOn,
                 title_template: dict[str, int]):
        self.n_lines = n_lines
        self.layout_mode = layout_mode
        self.title_on = title_on
        self.one_column = False
        self.header_width = title_template['header_width']
        self.header_height = title_template['header_height']
        
        height_for_ports = max(self.pms.last_in_pos, self.pms.last_out_pos)

        if self.port_mode in (PortMode.INPUT, PortMode.OUTPUT):
            if self.port_mode is PortMode.INPUT:
                ports_width = self.pms.ins_width
            else:
                ports_width = self.pms.outs_width

            if layout_mode is BoxLayoutMode.LARGE:
                if title_on is TitleOn.SIDE:
                    self.needed_width = (
                        ports_width + self.header_width + self.pen_width)
                    self.needed_height = (
                        max(self.header_height,
                            height_for_ports + self.port_spacing)
                    + 2 * self.pen_width)

                elif title_on is TitleOn.SIDE_UNDER_ICON:
                    self.header_width = max(
                        38, title_template['title_width'] + 10)
                    self.header_height = title_template['title_height'] + 32

                    if self.can_handle_gui:
                        self.header_width += 4
                        self.header_height += 4
                        
                    self.needed_width = (ports_width + self.header_width
                                         + self.pen_width)

                    self.needed_height = (
                        max(height_for_ports + self.port_spacing,
                            self.header_height)
                        + 2 * self.pen_width)
                else:
                    _logger.error(
                        f'incompatible _BoxLayout {layout_mode}'
                        f' and TitleOn {title_on}')
            else:
                self.needed_width = (
                    max(self.header_width + 2 * self.pen_width,
                        self.width_for_ports()))
                self.needed_height = (
                    self.header_height + height_for_ports
                    + 2 * self.pen_width)
        else:
            if layout_mode is BoxLayoutMode.HIGH:
                self.one_column = True
                self.needed_width = (
                    max(self.header_width + 2 * self.pen_width,
                        30.0 + max(self.pms.ins_width, self.pms.outs_width)))
                self.needed_height = (
                    self.header_height + self.pms.last_inout_pos
                    + 2 * self.pen_width)
            else:
                self.needed_width = (
                    max(self.header_width + 2 * self.pen_width,
                        self.width_for_ports()))
                self.needed_height = (
                    self.header_height + height_for_ports
                    + 2 * self.pen_width)

        self.full_width = next_width_on_grid(self.hwr * 2 + self.needed_width)
        self.full_height = next_height_on_grid(self.hwr * 2 + self.needed_height)

        self.area = self.full_width * self.full_height
        self.width = self.full_width - 2 * self.hwr
        self.height = self.full_height - 2 * self.hwr

    def __lt__(self, other: 'BoxLayout') -> bool:
        if self.area != other.area:
            return self.area < other.area
        
        if self.n_lines != other.n_lines:
            return self.n_lines < other.n_lines
        
        if self.one_column is not other.one_column:
            return self.one_column < other.one_column
        
        return self.title_on < other.title_on

    def set_choosed(self):
        self.pms = PortsMinSizes(**self.pms.__dict__)
        
        if (self.port_mode in (PortMode.INPUT, PortMode.OUTPUT)
                and self.layout_mode is BoxLayoutMode.LARGE):
            needed_width = (2 * self.pen_width + self.header_width)
            full_width = next_width_on_grid(self.hwr * 2 + needed_width)
            self.wrapped_width = full_width - 2 * self.hwr

            needed_height = (2 * self.pen_width + self.header_height)
            full_height = next_height_on_grid(self.hwr * 2 + needed_height)
            self.wrapped_height = full_height - 2 * self.hwr
        else:
            self.wrapped_width = self.width

            if (self.title_on is TitleOn.TOP
                    and (self.width - self.header_width) / 2 >= 14):
                needed_height = (2 * self.pen_width + self.header_height)
            else:
                needed_height = (self.pen_width
                                 + self.header_height
                                 + max(12, self.pen_width))
            
            full_height = next_height_on_grid(self.hwr * 2 + needed_height)
            self.wrapped_height = full_height - 2 * self.hwr
        
        self.exceeding_y_ins = 0.0
        self.exceeding_y_outs = 0.0
        self.exceeding_y_inouts = 0.0
        
        if ((self.port_mode is PortMode.BOTH
                    and self.layout_mode is BoxLayoutMode.LARGE)
                or (self.port_mode in (PortMode.INPUT, PortMode.OUTPUT)
                    and self.layout_mode is BoxLayoutMode.HIGH)):
            self.exceeding_y_ins = (
                self.height 
                - (2 * self.pen_width + self.header_height
                    + self.pms.last_in_pos))
            self.exceeding_y_outs = (
                self.height 
                - (2 * self.pen_width + self.header_height
                    + self.pms.last_out_pos))

        elif self.port_mode is PortMode.OUTPUT:
            self.exceeding_y_outs = (
                self.height
                - (2 * self.pen_width + self.port_spacing
                   + self.pms.last_out_pos))
        
        elif self.port_mode is PortMode.INPUT:
            self.exceeding_y_ins = (
                self.height
                - (2 * self.pen_width + self.port_spacing
                   + self.pms.last_in_pos))
        else:
            self.exceeding_y_inouts = (
                self.height
                - (2 * self.pen_width + self.header_height
                   + self.pms.last_inout_pos))
            
    def set_ports_top_bottom(
            self, ports_top_in: float, ports_bottom_in: float,
            ports_top_out: float, ports_bottom_out: float):
        self.ports_top_in = ports_top_in
        self.ports_bottom_in = ports_bottom_in
        self.ports_top_out = ports_top_out
        self.ports_bottom_out = ports_bottom_out
            
                    