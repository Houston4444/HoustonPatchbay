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
    max_in_width: float
    max_out_width: float
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
        cls.box = box
        theme = box.get_theme()
        cls.pen_width = theme.fill_pen().widthF()
        cls.port_spacing = theme.port_spacing()
        cls.height_for_ports = max(ports_min_sizes.last_in_pos,
                                   ports_min_sizes.last_out_pos)
        cls.height_for_ports_one = ports_min_sizes.last_inout_pos
        cls.ports_in_width = ports_min_sizes.max_in_width
        cls.ports_out_width = ports_min_sizes.max_out_width
        cls.hwr = canvas.theme.hardware_rack_width if box._is_hardware else 0
        cls.port_mode = box._current_port_mode
        cls.can_handle_gui = box._can_handle_gui
        cls.is_hardware = box._is_hardware
    
    @classmethod
    def width_for_ports(cls):
        return 30.0 + cls.ports_in_width + cls.ports_out_width
    
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

        if self.port_mode in (PortMode.INPUT, PortMode.OUTPUT):
            if self.port_mode is PortMode.INPUT:
                ports_width = self.ports_in_width
            else:
                ports_width = self.ports_out_width

            if layout_mode is BoxLayoutMode.LARGE:
                if title_on is TitleOn.SIDE:
                    self.needed_width = (
                        ports_width + 15
                        + self.header_width + self.pen_width)
                    self.needed_height = (
                        max(self.header_height,
                            self.height_for_ports + self.port_spacing)
                    + 2 * self.pen_width)

                elif title_on is TitleOn.SIDE_UNDER_ICON:
                    self.header_width = max(
                        38, title_template['title_width'] + 10)
                    self.header_height = title_template['title_height'] + 32

                    if self.can_handle_gui:
                        self.header_width += 4
                        self.header_height += 4
                        
                    self.needed_width = (ports_width + self.header_width
                                         + 15 + self.pen_width)

                    self.needed_height = (
                        max(self.height_for_ports + self.port_spacing,
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
                    self.header_height + self.height_for_ports
                    + 2 * self.pen_width)
        else:
            if layout_mode is BoxLayoutMode.HIGH:
                self.one_column = True
                self.needed_width = (
                    max(self.header_width + 2 * self.pen_width,
                        30.0 + max(self.ports_in_width, self.ports_out_width)))
                self.needed_height = (
                    self.header_height + self.height_for_ports_one
                    + 2 * self.pen_width)
            else:
                self.needed_width = (
                    max(self.header_width + 2 * self.pen_width,
                        self.width_for_ports()))
                self.needed_height = (
                    self.header_height + self.height_for_ports
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

    def set_wrapped_sizes(self):
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
            needed_height = (self.header_height + canvas.theme.port_height * 0.86
                             + 2 * self.pen_width)
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