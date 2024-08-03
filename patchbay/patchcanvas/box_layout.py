from enum import IntEnum
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING

from .init_values import PortMode, canvas, BoxLayoutMode, options
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
        # never call for external one of theses attributes !
        # Indeed, for optimization reasons, all BoxLayout instances are modified
        # when we init one from box.
        cls._pms = ports_min_sizes
        theme = box.get_theme()
        cls._pen_width = theme.fill_pen().widthF()
        cls._port_spacing = theme.port_spacing()
        cls._hwr = canvas.theme.hardware_rack_width if box.is_hardware else 0
        cls._port_mode = box._current_port_mode
        cls._can_handle_gui = box._can_handle_gui
        cls._is_hardware = box.is_hardware
    
    @classmethod
    def width_for_ports(cls):
        return (cls._pms.ins_width + cls._pms.outs_width + 6.0)
    
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
        
        height_for_ports = max(self._pms.last_in_pos, self._pms.last_out_pos)

        if self._port_mode in (PortMode.INPUT, PortMode.OUTPUT):
            if self._port_mode is PortMode.INPUT:
                ports_width = self._pms.ins_width
            else:
                ports_width = self._pms.outs_width

            if layout_mode is BoxLayoutMode.LARGE:
                if title_on is TitleOn.SIDE:
                    self.needed_width = (
                        ports_width + self.header_width + self._pen_width)
                    self.needed_height = (
                        max(self.header_height,
                            height_for_ports + self._port_spacing)
                        + 2 * self._pen_width)

                elif title_on is TitleOn.SIDE_UNDER_ICON:
                    self.header_width = max(
                        38, title_template['title_width'] + 10)
                    self.header_height = title_template['title_height'] + 32

                    if self._can_handle_gui:
                        self.header_width += 4
                        self.header_height += 4
                        
                    self.needed_width = (ports_width + self.header_width
                                         + self._pen_width)

                    self.needed_height = (
                        max(height_for_ports + self._port_spacing,
                            self.header_height)
                        + 2 * self._pen_width)
                else:
                    _logger.error(
                        f'incompatible _BoxLayout {layout_mode}'
                        f' and TitleOn {title_on}')
            else:
                self.needed_width = (
                    max(self.header_width + 2 * self._pen_width,
                        self.width_for_ports()))
                self.needed_height = (
                    self.header_height + height_for_ports
                    + 2 * self._pen_width)
        else:
            if layout_mode is BoxLayoutMode.HIGH:
                self.one_column = True
                self.needed_width = (
                    max(self.header_width + 2 * self._pen_width,
                        30.0 + max(self._pms.ins_width, self._pms.outs_width)))
                self.needed_height = (
                    self.header_height + self._pms.last_inout_pos
                    + 2 * self._pen_width)
            else:
                self.needed_width = (
                    max(self.header_width + 2 * self._pen_width,
                        self.width_for_ports()))
                self.needed_height = (
                    self.header_height + height_for_ports
                    + 2 * self._pen_width)

        self.full_width = next_width_on_grid(self._hwr * 2 + self.needed_width)
        self.full_height = next_height_on_grid(self._hwr * 2 + self.needed_height)

        # n_cells is used to sort layouts, to use the littlest area
        self._n_cells = (
            ((self.full_width + canvas.theme.box_spacing) / options.cell_width)
            * ((self.full_height + canvas.theme.box_spacing) / options.cell_height))

        # with the option box_grouped_auto_layout_ratio,
        # we simulate that the area can be higher in one_column mode
        # (PortMode.BOTH and BoxLayoutMode.HIGH)
        if self.one_column:
            self._n_cells *= options.box_grouped_auto_layout_ratio

        self.width = self.full_width - 2 * self._hwr
        self.height = self.full_height - 2 * self._hwr

    def __lt__(self, other: 'BoxLayout') -> bool:
        if self._n_cells != other._n_cells:
            return self._n_cells < other._n_cells
        
        if self.n_lines != other.n_lines:
            return self.n_lines < other.n_lines
        
        if self.one_column is not other.one_column:
            return self.one_column < other.one_column
        
        return self.title_on < other.title_on

    def set_choosed(self):
        self._pms = PortsMinSizes(**self._pms.__dict__)
        
        if (self._port_mode in (PortMode.INPUT, PortMode.OUTPUT)
                and self.layout_mode is BoxLayoutMode.LARGE):
            needed_width = 2 * self._pen_width + self.header_width
            self.full_wrapped_width = \
                next_width_on_grid(self._hwr * 2 + needed_width)
            self.wrapped_width = self.full_wrapped_width - 2 * self._hwr

            needed_height = (2 * self._pen_width + self.header_height)
            self.full_wrapped_height = \
                next_height_on_grid(self._hwr * 2 + needed_height)
            self.wrapped_height = self.full_wrapped_height - 2 * self._hwr
        else:
            self.wrapped_width = self.width
            self.full_wrapped_width = self.full_width

            if (self.title_on is TitleOn.TOP
                    and (self.width - self.header_width) / 2 >= 14):
                needed_height = (2 * self._pen_width + self.header_height)
            else:
                needed_height = (self._pen_width
                                 + self.header_height
                                 + max(12, self._pen_width))
            
            self.full_wrapped_height = \
                next_height_on_grid(self._hwr * 2 + needed_height)
            self.wrapped_height = self.full_wrapped_height - 2 * self._hwr
        
        self.exceeding_y_ins = 0.0
        self.exceeding_y_outs = 0.0
        self.exceeding_y_inouts = 0.0
        
        if ((self._port_mode is PortMode.BOTH
                    and self.layout_mode is BoxLayoutMode.LARGE)
                or (self._port_mode in (PortMode.INPUT, PortMode.OUTPUT)
                    and self.layout_mode is BoxLayoutMode.HIGH)):
            self.exceeding_y_ins = (
                self.height 
                - (2 * self._pen_width + self.header_height
                    + self._pms.last_in_pos))
            self.exceeding_y_outs = (
                self.height 
                - (2 * self._pen_width + self.header_height
                    + self._pms.last_out_pos))

        elif self._port_mode is PortMode.OUTPUT:
            self.exceeding_y_outs = (
                self.height
                - (2 * self._pen_width + self._port_spacing
                   + self._pms.last_out_pos))
        
        elif self._port_mode is PortMode.INPUT:
            self.exceeding_y_ins = (
                self.height
                - (2 * self._pen_width + self._port_spacing
                   + self._pms.last_in_pos))
        else:
            self.exceeding_y_inouts = (
                self.height
                - (2 * self._pen_width + self.header_height
                   + self._pms.last_inout_pos))
            
    def set_ports_top_bottom(
            self, ports_top_in: float, ports_bottom_in: float,
            ports_top_out: float, ports_bottom_out: float):
        self.ports_top_in = ports_top_in
        self.ports_bottom_in = ports_bottom_in
        self.ports_top_out = ports_top_out
        self.ports_bottom_out = ports_bottom_out
            
                    