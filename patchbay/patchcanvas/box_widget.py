
from dataclasses import dataclass
from enum import IntEnum
from math import ceil
from typing import Iterator
from PyQt5.QtCore import QRectF
from PyQt5.QtGui import QPainterPath
from PyQt5.QtWidgets import QGraphicsItem


from .init_values import (
    canvas,
    options,
    InlineDisplay,
    BoxLayoutMode,
    PortMode,
    PortType,
    PortSubType,
    BoxType,
    GroupObject)

from .utils import (get_portgroup_name_from_ports_names,
                    next_width_on_grid,
                    next_height_on_grid)
from .box_widget_moth import BoxWidgetMoth, UnwrapButton, TitleLine, WrappingState


def list_port_types_and_subs() -> Iterator[tuple[PortType, PortSubType]]:
    ''' simple fast generator port PortType and PortSubType preventing
        incoherent couples '''
    for port_type in PortType:
        if port_type is PortType.NULL:
            continue
        
        for port_subtype in PortSubType:
            if ((port_subtype is PortSubType.A2J
                    and not port_type is PortType.MIDI_JACK)
                or (port_subtype is PortSubType.CV
                    and not port_type is PortType.AUDIO_JACK)):
                # No such port should exist, it is just for win some time
                continue
            
            yield (port_type, port_subtype)


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
    last_port_mode: PortMode


@dataclass()
class BestLayoutProps:
    true_layout_mode: BoxLayoutMode
    max_title_size: float
    box_width: float
    box_height: float
    header_width: float
    header_height: float
    ports_y_start: float
    one_column: bool


class BoxWidget(BoxWidgetMoth):
    def __init__(self, group: GroupObject, port_mode: PortMode):
        BoxWidgetMoth.__init__(self, group, port_mode)
        self.update_positions_pending = False
        self._ex_width = self._width
        self._ex_height = self._height
        
        self._y_normal_rab = 0.0
        self._y_wrapped_rab = 0.0

        self._ex_scene_pos = self.scenePos()
        self._ex_ports_y_segments_dict = dict[str, list[list[int]]]()

    def __repr__(self) -> str:
        return f"BoxWidget({self._group_name}, {self._current_port_mode.name})"

    def _get_portgroup_name(self, portgrp_id: int):
        return get_portgroup_name_from_ports_names(
            [p.port_name for p in self._port_list
             if p.portgrp_id == portgrp_id])

    def _should_align_port_types(self) -> bool:
        '''check if we can align port types
           eg, align first midi input to first midi output'''
        port_types_aligner = list[tuple[int, int]]()
        
        for port_type, port_subtype in list_port_types_and_subs():
            n_ins = 0
            n_outs = 0

            for port in self._port_list:
                if (port.port_type == port_type
                        and port.port_subtype == port_subtype):
                    if port.port_mode is PortMode.INPUT:
                        n_ins += 1
                    elif port.port_mode is PortMode.OUTPUT:
                        n_outs += 1

            port_types_aligner.append((n_ins, n_outs))

        winner = PortMode.NULL

        for n_ins, n_outs in port_types_aligner:
            if ((winner is PortMode.INPUT and n_outs > n_ins)
                    or (winner is PortMode.OUTPUT and n_ins > n_outs)):
                return False

            if n_ins > n_outs:
                winner = PortMode.INPUT
            elif n_outs > n_ins:
                winner = PortMode.OUTPUT
        
        return True
    
    def _get_ports_min_sizes(
            self, align_port_types: bool) -> PortsMinSizes:
        max_in_width = max_out_width = 0.0
        
        box_theme = self.get_theme()
        port_spacing = box_theme.port_spacing()
        port_in_offset = box_theme.port_in_offset()
        port_out_offset = box_theme.port_out_offset()
        port_type_spacing = box_theme.port_type_spacing()
        last_in_pos = last_out_pos = port_spacing
        final_last_in_pos = final_last_out_pos = last_in_pos
        last_in_type_and_sub = (PortType.NULL, PortSubType.REGULAR)
        last_out_type_and_sub = (PortType.NULL, PortSubType.REGULAR)
        n_in_type_and_subs = 0
        n_out_type_and_subs = 0
        last_port_mode = PortMode.NULL
        
        for port_type, port_subtype in list_port_types_and_subs():                
            for port in self._port_list:
                if (port.port_type is not port_type
                        or port.port_subtype is not port_subtype):
                    continue

                last_of_portgrp = bool(port.pg_pos + 1 == port.pg_len)
                size = 0
                max_pwidth = options.max_port_width
    
                if port.port_mode is PortMode.INPUT:
                    port_offset = port_in_offset
                else:
                    port_offset = port_out_offset

                if port.portgrp_id:
                    portgrp = canvas.get_portgroup(self._group_id, port.portgrp_id)
                    if port.pg_pos == 0:
                        portgrp_name = self._get_portgroup_name(port.portgrp_id)

                        portgrp.widget.set_print_name(
                            portgrp_name,
                            max_pwidth - canvas.theme.port_grouped_width - 5)
                    
                    port.widget.set_print_name(
                        port.port_name.replace(
                            self._get_portgroup_name(port.portgrp_id), '', 1),
                        int(max_pwidth/2))
                    
                    if (portgrp.widget.get_text_width() + 5
                            > max_pwidth - port.widget.get_text_width()):
                        portgrp.widget.reduce_print_name(
                            max_pwidth - port.widget.get_text_width() - 5)
                    
                    # the port_grouped_width is also used to define
                    # the portgroup minimum width
                    size = (max(portgrp.widget.get_text_width(),
                                canvas.theme.port_grouped_width)
                            + max(port.widget.get_text_width() + 6,
                                    canvas.theme.port_grouped_width)
                            + port_offset)
                else:
                    port.widget.set_print_name(port.port_name, max_pwidth)
                    size = max(port.widget.get_text_width() + port_offset, 20)
                
                type_and_sub = (port.port_type, port.port_subtype)
                
                if port.port_mode is PortMode.INPUT:
                    max_in_width = max(max_in_width, size)
                    if type_and_sub != last_in_type_and_sub:
                        if last_in_type_and_sub != (PortType.NULL, PortSubType.REGULAR):
                            last_in_pos += port_type_spacing
                        last_in_type_and_sub = type_and_sub
                        n_in_type_and_subs += 1

                    last_in_pos += canvas.theme.port_height
                    if last_of_portgrp:
                        last_in_pos += port_spacing

                elif port.port_mode is PortMode.OUTPUT:
                    max_out_width = max(max_out_width, size)
                    
                    if type_and_sub != last_out_type_and_sub:
                        if last_out_type_and_sub != (PortType.NULL, PortSubType.REGULAR):
                            last_out_pos += port_type_spacing
                        last_out_type_and_sub = type_and_sub
                        n_out_type_and_subs += 1
                    
                    last_out_pos += canvas.theme.port_height
                    if last_of_portgrp:
                        last_out_pos += port_spacing
                
                final_last_in_pos = last_in_pos
                final_last_out_pos = last_out_pos
            
            if align_port_types:
                # align port types horizontally
                if last_in_pos > last_out_pos:
                    last_out_type_and_sub = last_in_type_and_sub
                else:
                    last_in_type_and_sub = last_out_type_and_sub
                last_in_pos = last_out_pos = max(last_in_pos, last_out_pos)
        
        # calculates height in case of one column only
        last_inout_pos = port_spacing
        last_type_and_sub = (PortType.NULL, PortSubType.REGULAR)

        if self._current_port_mode is PortMode.BOTH:
            for port_type, port_subtype in list_port_types_and_subs():
                for port in self._port_list:
                    if (port.port_type is not port_type
                            or port.port_subtype is not port_subtype):
                        continue

                    if (port.port_type, port.port_subtype) != last_type_and_sub:
                        if last_type_and_sub != (PortType.NULL, PortSubType.REGULAR):
                            last_inout_pos += port_type_spacing
                        last_type_and_sub = (port.port_type, port.port_subtype)

                    if port.pg_pos:
                        continue

                    last_inout_pos += port.pg_len * canvas.theme.port_height
                    last_inout_pos += port_spacing
                    
                    last_port_mode = port.port_mode
        
        return PortsMinSizes(
            final_last_in_pos,
            final_last_out_pos,
            last_inout_pos,
            max_in_width,
            max_out_width,
            n_in_type_and_subs,
            n_out_type_and_subs,
            last_port_mode
        )

    @staticmethod
    def split_in_two(string: str, n_lines: int) -> list[str]:
        def polished_list(input_list: list) -> list:
            output_list = list[str]()

            for string in input_list:
                if not string:
                    continue
                if len(string) == 1:
                    if output_list:
                        output_list[-1] += string
                    else:
                        output_list.append(string)
                else:
                    if output_list and len(output_list[-1]) <= 1:
                        output_list[-1] += string
                    else:
                        output_list.append(string)
            
            return [s.strip() for s in output_list]
                
        if n_lines <= 1:
            return [string]
            
        sep_indexes = list[int]()
        last_was_digit = False
        last_was_upper = False

        for i in range(len(string)):
            c = string[i]
            if c in (' ', '-', '_', '.'):
                sep_indexes.append(i)
            else:
                if c.upper() == c:
                    if c.isdigit():
                        if not last_was_digit:
                            sep_indexes.append(i)
                    else:
                        if last_was_digit or not last_was_upper:
                            sep_indexes.append(i)

                    last_was_upper = True
                else:
                    if last_was_digit:
                        sep_indexes.append(i)
                    last_was_upper = False

                last_was_digit = c.isdigit()
            
        if not sep_indexes:
            return [string]
        
        if len(sep_indexes) + 1 <= n_lines:
            return_list = list[str]()
            last_index = 0

            for sep_index in sep_indexes:
                return_list.append(string[last_index:sep_index])
                last_index = sep_index

            return_list.append(string[last_index:])

            return polished_list(return_list)
        
        best_indexes = [0]
        string_rest = string

        for i in range(n_lines, 1, -1):
            
            target = best_indexes[-1] + int(len(string_rest)/i)
            best_index = None
            best_dif = len(string)

            for s in sep_indexes:
                if s <= best_indexes[-1]:
                    continue

                dif = abs(target - s)
                if dif < best_dif:
                    best_index = s
                    best_dif = dif
                else:
                    break

            if best_index is None:
                continue

            string_rest = string[best_index:]
            best_indexes.append(best_index)

        best_indexes = best_indexes[1:]
        last_index = 0
        return_list = list[str]()

        for i in best_indexes:
            return_list.append(string[last_index:i])
            last_index = i

        return_list.append(string[last_index:])
        return polished_list(return_list)
    
    def _split_title(self, n_lines: int) -> tuple[TitleLine]:
        title, slash, subtitle = self._group_name.partition('/')

        if (not subtitle
                and self._box_type == BoxType.CLIENT
                and ' (' in self._group_name
                and self._group_name.endswith(')')):
            title, parenthese, subtitle = self._group_name.partition(' (')
            subtitle = subtitle[:-1]
        
        theme = self.get_theme()

        if self._box_type == BoxType.CLIENT and subtitle:
            # if there is a subtitle, title is not bold when subtitle is.
            # so title is 'little'
            client_line = TitleLine(title, theme, little=True)
            subclient_line = TitleLine(subtitle, theme)
            title_lines = []
            
            if n_lines <= 2:
                title_lines.append(client_line)
                title_lines.append(subclient_line)
            
            else:
                if client_line.size > subclient_line.size:
                    client_strs = self.split_in_two(title, 2)
                    for client_str in client_strs:
                        title_lines.append(TitleLine(client_str, theme, little=True))
                    
                    for subclient_str in self.split_in_two(subtitle, n_lines - 2):
                        title_lines.append(TitleLine(subclient_str, theme))
                else:
                    two_lines_title = False
                    
                    if n_lines >= 4:
                        # Check if we need to split the client title
                        # it could be "Carla-Multi-Client.Carla".
                        subtitles = self.split_in_two(subtitle, n_lines - 2)

                        for subtt in subtitles:
                            subtt_line = TitleLine(subtt, theme)
                            if subtt_line.size > client_line.size:
                                break
                        else:
                            client_strs = self.split_in_two(title, 2)
                            for client_str in client_strs:
                                title_lines.append(
                                    TitleLine(client_str, theme, little=True))
                            two_lines_title = True
                    
                    if not two_lines_title:
                        title_lines.append(client_line)
                    
                    subt_len = n_lines - 1
                    if two_lines_title:
                        subt_len -= 1
                        titles = self.split_in_two(subtitle, subt_len)
                        for title in titles:
                            title_lines.append(TitleLine(title, theme))
                    else:
                        titles = self.split_in_two('uuuu' + subtitle, subt_len)
                        
                        # supress the uuuu
                        for i in range(len(titles)):
                            title = titles[i]
                            if i == 0:
                                title = title[4:]
                                if not title:
                                    continue
                            title_lines.append(TitleLine(title, theme))
        else:
            if n_lines >= 2:
                titles = []
                if (self._group_name.startswith(
                     ('Carla.', 'Carla-Multi-Client.', 'Carla-Single-Client.'))
                        and '/' in self._group_name):
                    first_line, slash, last_line = self._group_name.partition('/')
                    titles = [first_line + '/'] + self.split_in_two(last_line, n_lines - 1)
                else:
                    titles = self.split_in_two(self._group_name, n_lines)

                title_lines = [TitleLine(tt, theme) for tt in titles]
            else:
                title_lines = [TitleLine(self._group_name, theme)]

        return tuple(title_lines)

    def _get_area(self, width: float, height: float) -> int:
        hwr = canvas.theme.hardware_rack_width if self._is_hardware else 0
        pen_width = self.get_theme().fill_pen().widthF()
        
        return (next_width_on_grid(hwr * 2 + width)
                * next_height_on_grid(
                    hwr * 2 + height + 2 * pen_width))

    def _choose_box_layout(
        self, height_for_ports: int, height_for_ports_one: int,
        ports_in_width: int, ports_out_width: int) -> BestLayoutProps:
        '''choose in how many lines the title should be splitted
        and if the box layout should be large or high.
        returns a dict with all required variables and values'''
        
        # width_for_ports_one is the width needed for ports
        # if inputs and outputs layouted in one column.
        ## INPUT_PORT_1
        ## INPUT_PORT_2
        ##    OUTPUT_PORT_1
        ## ...
        width_for_ports = 30 + ports_in_width + ports_out_width
        width_for_ports_one = 30 + max(ports_in_width, ports_out_width)

        ports_width = ports_in_width
        if self._current_port_mode is PortMode.OUTPUT:
            ports_width = ports_out_width

        box_theme = self.get_theme()
        font_size = box_theme.font().pixelSize()
        pen_width = box_theme.fill_pen().widthF()

        # Check Text Name size
        
        # first look in cache if title sizes are stocked
        all_title_templates = box_theme.get_title_templates(
            self._group_name, self._can_handle_gui, self.has_top_icon())
        all_title_templates = list[dict[str, int]]()
        lines_choice_max = len(all_title_templates) - 1

        if not all_title_templates:
            # this box title is not in cache, we need to estimate all its sizes
            # depending number of splitted lines.
            title_template = {
                "title_width": 0, "header_width": 0, "header_height": 0}
            all_title_templates = [title_template.copy() for i in range(8)]

            last_lines_count = 0
            GUI_MARGIN = 2
            title_line_y_start = 1 + font_size
            
            header_height = 2 + font_size + 2
            if self.has_top_icon():
                header_height = 3 + 24 + 3

            for i in range(1, 8):
                max_title_width = 0
                max_header_width = 50
                if self._plugin_inline is not InlineDisplay.DISABLED:
                    max_header_width = 200
                
                title_lines = self._split_title(i)

                for j in range(len(title_lines)):
                    title_line = title_lines[j]
                    title_line.y = title_line_y_start + j * int(font_size * 1.4)
                    max_title_width = int(max(max_title_width, title_line.size))
                    header_width = title_line.size + 10

                    if self.has_top_icon() and title_line.y <= 28 + font_size:
                        # text line is at right of the icon
                        header_width += 28

                    max_header_width = max(max_header_width, header_width)
                
                header_height = max(
                    header_height,
                    title_line_y_start
                        + int(font_size * 1.4) * (len(title_lines) - 1)
                        + 5)
                
                if self._can_handle_gui:
                    max_header_width += 2 * GUI_MARGIN
                    header_height += 2 * GUI_MARGIN

                new_title_template = title_template.copy()
                new_title_template['title_width'] = max_title_width
                new_title_template['header_width'] = max_header_width
                new_title_template['header_height'] = header_height
                all_title_templates[i] = new_title_template

                if i > 2 and len(title_lines) <= last_lines_count:
                    break

                last_lines_count = len(title_lines)

            lines_choice_max = i
            box_theme.save_title_templates(
                self._group_name, self._can_handle_gui, self.has_top_icon(),
                all_title_templates[:lines_choice_max])

        # Now compare multiple possible areas for the box,
        # depending on BoxLayoutMode and number of lines for the box title.

        sizes_tuples = list[tuple[int, int, bool, TitleOn]]()
        layout_mode = self._layout_mode
        
        if self._current_port_mode in (PortMode.INPUT, PortMode.OUTPUT):
            # splitted box
            
            if layout_mode in (BoxLayoutMode.AUTO, BoxLayoutMode.LARGE):
                ports_y_start_min = (box_theme.port_spacing()
                                     + box_theme.port_type_spacing())
                ports_y_start_min = 0.0
                
                # calculate area with title on side
                for i in range(1, lines_choice_max + 1):
                    sizes_tuples.append(
                        (self._get_area(
                            ports_width + 12 + all_title_templates[i]['header_width'],
                            max(all_title_templates[i]['header_height'],
                                height_for_ports + ports_y_start_min)),
                         i, False, TitleOn.SIDE))

                if self.has_top_icon():
                    # calculate area with title on side (title under the icon)
                    for i in range(1, lines_choice_max + 1):
                        header_width = max(
                            38, all_title_templates[i]['title_width'] + 12)
                        if self._can_handle_gui:
                            header_width += 4
                        
                        box_width = ports_width + header_width + 12
                        header_height = all_title_templates[i]['header_height']
                        header_height += 20 if i == 1 else 30
                        box_height = max(
                            height_for_ports + ports_y_start_min, header_height)
                        
                        sizes_tuples.append(
                            (self._get_area(box_width, box_height),
                             i, False, TitleOn.SIDE_UNDER_ICON))
                        
            if layout_mode in (BoxLayoutMode.AUTO, BoxLayoutMode.HIGH):
                # calculate area with title on top
                for i in range(1, lines_choice_max + 1):
                    sizes_tuples.append(
                        (self._get_area(
                            max(all_title_templates[i]['header_width'],
                                width_for_ports),
                            all_title_templates[i]['header_height']
                            + height_for_ports),
                         i, False, TitleOn.TOP))
                    
        else:
            # --- grouped box ---
            
            # calculate area with input and outputs ports descending
            if (layout_mode in (BoxLayoutMode.AUTO, BoxLayoutMode.HIGH)
                    and options.box_grouped_auto_layout_ratio < 2.0):
                for i in range(1, lines_choice_max + 1):
                    sizes_tuples.append(
                        (self._get_area(
                            max(all_title_templates[i]['header_width'],
                                width_for_ports_one),
                            all_title_templates[i]['header_height']
                            + height_for_ports_one),
                         i, True, TitleOn.TOP))

            # calculate area with input ports at left of output ports
            if (layout_mode in (BoxLayoutMode.AUTO, BoxLayoutMode.LARGE)
                    and options.box_grouped_auto_layout_ratio > 0.0):
                for i in range(1, lines_choice_max + 1):
                    sizes_tuples.append(
                        (self._get_area(
                            max(all_title_templates[i]['header_width'],
                                width_for_ports),
                            all_title_templates[i]['header_height']
                            + height_for_ports),
                         i, False, TitleOn.TOP))

        # sort areas and choose the first one (the littlest area)
        sizes_tuples.sort()
        area_size, lines_choice, one_column, title_on_side = sizes_tuples[0]

        self._title_lines = self._split_title(lines_choice)
        
        header_height = all_title_templates[lines_choice]['header_height']
        header_width = all_title_templates[lines_choice]['header_width']
        max_title_width = all_title_templates[lines_choice]['title_width']
        
        if self._current_port_mode is PortMode.BOTH:
            if one_column:
                true_layout_mode = BoxLayoutMode.HIGH
            else:
                true_layout_mode = BoxLayoutMode.LARGE
        else:
            if title_on_side:
                true_layout_mode = BoxLayoutMode.LARGE
            else:
                true_layout_mode = BoxLayoutMode.HIGH
        
        box_width = 0
        box_height = 0
        ports_y_start = header_height + pen_width

        self._title_under_icon = bool(title_on_side is TitleOn.SIDE_UNDER_ICON)

        if title_on_side:
            ports_y_start = box_theme.port_spacing() + pen_width
            
            if self._title_under_icon:
                header_width = max(38, max_title_width + 10 + 2 * pen_width)
                if self._can_handle_gui:
                    header_width += 4

                box_width = ports_width + header_width + 12 + 2 * pen_width
                header_height += 20 if len(self._title_lines) == 1 else 30
                box_height = max(height_for_ports + ports_y_start, header_height) + 2 * pen_width
            else:
                box_width = ports_width + header_width + 12 + 2 * pen_width
                box_height = max(height_for_ports + ports_y_start, header_height) + 2 * pen_width

        elif one_column:
            box_width = max(width_for_ports_one, header_width + 2 * pen_width)
            box_height = header_height + height_for_ports_one + pen_width * 2
        else:
            box_width = max(width_for_ports, header_width + 2 * pen_width)
            box_height = header_height + height_for_ports + pen_width * 2
        
        return BestLayoutProps(
            true_layout_mode,
            max_title_width,
            box_width,
            box_height,
            header_width,
            header_height,
            ports_y_start,
            one_column
        )

    def _set_ports_y_positions(
            self, align_port_types: bool, start_pos: int,
            one_column: bool) -> dict[str, list[list[int]]]:
        ''' ports Y positioning, return height segments info
            used if port-in-offset or port-out-offset are not zero in box theme'''

        def set_widget_pos(widget: QGraphicsItem, pos: float):
            if self._wrapping_state is WrappingState.WRAPPING:
                widget.setY(pos - ((pos - wrapped_port_pos)
                                   * self._wrapping_ratio))
            elif self._wrapping_state is WrappingState.UNWRAPPING:
                widget.setY(wrapped_port_pos + ((pos - wrapped_port_pos)
                                                * self._wrapping_ratio))
            elif self._wrapping_state is WrappingState.WRAPPED:
                widget.setY(wrapped_port_pos)
            else:
                widget.setY(pos)
        
        box_theme = self.get_theme()
        port_spacing = box_theme.port_spacing()
        port_type_spacing = box_theme.port_type_spacing()
        pen_width = box_theme.fill_pen().widthF()
        last_in_type_and_sub = (PortType.NULL, PortSubType.REGULAR)
        last_out_type_and_sub = (PortType.NULL, PortSubType.REGULAR)
        last_type_and_sub = (PortType.NULL, PortSubType.REGULAR)
        
        if self._has_side_title():
            start_pos = box_theme.fill_pen().widthF() + port_spacing
        else:
            start_pos = self._header_height + pen_width
        
        # last_in_pos = last_out_pos = start_pos + self._y_normal_rab / 2
        # wrapped_port_pos = start_pos +  self._y_wrapped_rab / 2
        last_in_pos = last_out_pos = start_pos
        wrapped_port_pos = start_pos        
        
        input_segments = list[list[int]]()
        output_segments = list[list[int]]()
        in_segment = [last_in_pos, last_in_pos]
        out_segment = [last_out_pos, last_out_pos]
        
        for port_type, port_subtype in list_port_types_and_subs():                
            for port in self._port_list:
                if (port.port_type is not port_type
                        or port.port_subtype is not port_subtype):
                    continue
                
                if one_column:
                    last_in_pos = last_out_pos = max(last_in_pos, last_out_pos)
                
                if port.portgrp_id and port.pg_pos > 0:
                    continue
                
                type_and_sub = (port.port_type, port.port_subtype)
                if one_column:
                    if type_and_sub != last_type_and_sub:
                        if last_type_and_sub != (PortType.NULL, PortSubType.REGULAR):
                            last_in_pos += port_type_spacing
                            last_out_pos += port_type_spacing
                        last_type_and_sub = type_and_sub
                
                if port.port_mode is PortMode.INPUT:
                    if not one_column and type_and_sub != last_in_type_and_sub:
                        if last_in_type_and_sub != (PortType.NULL, PortSubType.REGULAR):
                            last_in_pos += port_type_spacing
                        last_in_type_and_sub = type_and_sub
                    
                    if last_in_pos >= in_segment[1] + port_spacing + port_type_spacing:
                        if in_segment[0] != in_segment[1]:
                            input_segments.append(in_segment)
                        in_segment = [last_in_pos, last_in_pos]
                    
                    if port.portgrp_id:
                        # we place the portgroup widget and all its ports now
                        # because in one column mode, we can't be sure
                        # that port consecutivity isn't break by a port with
                        # another mode:
                        # 
                        # input L
                        #     output L
                        # input R
                        #     output R
                        portgrp = port.portgrp
                        if portgrp.widget is not None:
                            set_widget_pos(portgrp.widget, last_in_pos)
                        
                        for gp_port in portgrp.ports:
                            set_widget_pos(gp_port.widget, last_in_pos)
                            last_in_pos += canvas.theme.port_height
                    else:
                        set_widget_pos(port.widget, last_in_pos)
                        last_in_pos += canvas.theme.port_height
                    in_segment[1] = last_in_pos
                    last_in_pos += port_spacing

                elif port.port_mode is PortMode.OUTPUT:
                    if not one_column and type_and_sub != last_out_type_and_sub:
                        if last_out_type_and_sub != (PortType.NULL, PortSubType.REGULAR):
                            last_out_pos += port_type_spacing
                        last_out_type_and_sub = type_and_sub

                    if last_out_pos >= out_segment[1] + port_spacing + port_type_spacing:
                        if out_segment[0] != out_segment[1]:
                            output_segments.append(out_segment)
                        out_segment = [last_out_pos, last_out_pos]

                    if port.portgrp_id:
                        portgrp = port.portgrp
                        if portgrp.widget is not None:
                            set_widget_pos(portgrp.widget, last_out_pos)

                        for gp_port in portgrp.ports:
                            set_widget_pos(gp_port.widget, last_out_pos)
                            last_out_pos += canvas.theme.port_height
                    else:
                        set_widget_pos(port.widget, last_out_pos)
                        last_out_pos += canvas.theme.port_height
                    
                    out_segment[1] = last_out_pos
                    last_out_pos += port_spacing
            
            if align_port_types:
                # align port types horizontally
                if last_in_pos > last_out_pos:
                    last_out_type_and_sub = last_in_type_and_sub
                else:
                    last_in_type_and_sub = last_out_type_and_sub
                last_in_pos = last_out_pos = max(last_in_pos, last_out_pos)
        
        if in_segment[0] != in_segment[1]:
            input_segments.append(in_segment)
        if out_segment[0] != out_segment[1]:
            output_segments.append(out_segment)
        
        return {'input_segments': input_segments,
                'output_segments': output_segments}

    def _set_ports_x_positions(self, max_in_width: int, max_out_width: int):
        box_theme = self.get_theme()
        port_in_offset = box_theme.port_in_offset()
        port_out_offset = box_theme.port_out_offset()
        
        # Horizontal ports re-positioning
        in_x = port_in_offset
        out_x = self._width - max_out_width - 12

        # Horizontal ports not in portgroup re-positioning
        for port in self._port_list:
            if port.portgrp_id:
                continue

            if port.port_mode is PortMode.INPUT:
                port.widget.setX(in_x)
                port.widget.set_port_width(max_in_width - port_in_offset)
            elif port.port_mode is PortMode.OUTPUT:
                port.widget.setX(out_x)
                port.widget.set_port_width(max_out_width - port_out_offset)

        # Horizontal portgroups and ports in portgroup re-positioning
        for portgrp in self._portgrp_list:
            if portgrp.widget is not None:
                if portgrp.port_mode is PortMode.INPUT:
                    portgrp.widget.set_portgrp_width(max_in_width - port_in_offset)
                    portgrp.widget.setX(port_in_offset +1)
                elif portgrp.port_mode is PortMode.OUTPUT:
                    portgrp.widget.set_portgrp_width(max_out_width - port_out_offset)
                    portgrp.widget.setX(out_x)

            max_port_in_pg_width = canvas.theme.port_grouped_width

            for port in portgrp.ports:
                if port.widget is not None:
                    port_print_width = port.widget.get_text_width()

                    # change port in portgroup width only if
                    # portgrp will have a name
                    # to ensure that portgroup widget is large enough
                    max_port_in_pg_width = max(max_port_in_pg_width,
                                               port_print_width + 4)

            out_in_portgrp_x = (self._width - port_out_offset - 12
                                - max_port_in_pg_width)

            portgrp.widget.set_ports_width(max_port_in_pg_width)

            for port in portgrp.ports:
                if port.widget is not None:
                    port.widget.set_port_width(max_port_in_pg_width)
                    if port.port_mode is PortMode.INPUT:
                        port.widget.setX(in_x)
                    elif port.port_mode is PortMode.OUTPUT:
                        port.widget.setX(out_in_portgrp_x)
    
    def _set_title_positions(self):
        ''' set title lines, header lines and icon positions '''
        self._header_line_left = None
        self._header_line_right = None

        box_theme = self.get_theme()
        font_size = box_theme.font().pixelSize()
        font_spacing = int(font_size * 1.4)
        pen_width = box_theme.fill_pen().widthF()

        # when client is client capable of gui state
        # header has margins
        gui_margin = 2 if self._can_handle_gui else 0
        
        # set title lines Y position
        title_y_start = font_size + 1 + gui_margin + pen_width

        if self._title_under_icon:
            title_y_start = 3 + gui_margin + 24 + font_spacing + pen_width
        
        for i in range(len(self._title_lines)):
            title_line = self._title_lines[i]
            title_line.y = title_y_start + i * font_spacing
        
        if not self._title_under_icon and len(self._title_lines) == 1:
            self._title_lines[0].y = int(
                pen_width + font_size * 0.5 + (self._header_height - font_size * 0.5) / 2)
        
        if self._has_side_title():
            y_correction = 0

            # In case the title is near to be vertically centered in the box
            # It's prettier to center it correctly
            if (self._title_lines
                    and not self._title_under_icon
                    and not self._can_handle_gui
                    and self._title_lines[-1].y + int(font_size * 1.4) > self._height):
                y_correction = (self._height - self._title_lines[-1].y - 2) / 2 - 2
            
            # set title lines pos
            for title_line in self._title_lines:
                if self._current_port_mode is PortMode.INPUT:
                    title_line.x = self._width - self._header_width + 5 - pen_width
                    if self._can_handle_gui:
                        title_line.x += 2
                    
                    if self.has_top_icon():
                        self.top_icon.set_pos(self._width - 24 - 3 - pen_width - gui_margin,
                                              3 + pen_width + gui_margin)
    
                elif self._current_port_mode is PortMode.OUTPUT:
                    title_line.x = (pen_width + self._header_width
                                    - title_line.size - 6)
                    
                    if self._can_handle_gui:
                        title_line.x -= 2
                    
                    if self.has_top_icon():
                        self.top_icon.set_pos(3 + pen_width + gui_margin,
                                              3 + pen_width + gui_margin)
                
                title_line.y += y_correction
            return

        # Now we are sure title is on top

        # get title global sizes
        max_title_size = 0
        max_title_icon_size = 0

        for title_line in self._title_lines:
            title_size = title_line.size
            if self.has_top_icon() and title_line.y <= 28 + font_size:
                # title line is beside icon
                title_size += 28
                max_title_icon_size = max(max_title_icon_size, title_size)
            max_title_size = max(max_title_size, title_size)
        
        # set title lines X position
        for title_line in self._title_lines:
            if self.has_top_icon() and title_line.y <= 28 + font_size:
                # title line is beside the icon
                title_line.x = int((self._width - max_title_icon_size) / 2 + 28)
            else:
                title_line.x = int((self._width - title_line.size) / 2)
        
        # set icon position
        if self.has_top_icon():
            self.top_icon.set_pos(int((self._width - max_title_icon_size)/2),
                                  int(3 + pen_width + gui_margin))

        # calculate header lines positions
        side_size = (self._width - max(max_title_icon_size, max_title_size)) * 0.5
        
        if side_size > 10:
            y = self._header_height / 2 + pen_width
            
            self._header_line_left = (5.0, y, side_size - 5.0, y)
            self._header_line_right = (self._width - side_size + 5.0, y,
                                       self._width - 5.0, y)
    
    def build_painter_path(self, pos_dict):
        input_segments = pos_dict['input_segments']
        output_segments = pos_dict['output_segments']
        
        painter_path = QPainterPath()
        theme = self.get_theme()
        border_radius = theme.border_radius()
        port_in_offset = abs(theme.port_in_offset())
        port_out_offset = abs(theme.port_out_offset())
        pen = theme.fill_pen()
        line_hinting = pen.widthF() / 2.0
        
        # theses values are needed to prevent some incorrect painter_path
        # united or subtracted results
        epsy = 0.001
        epsd = epsy * 2.0
        
        rect = QRectF(0.0, 0.0, self._width, self._height)
        rect.adjust(line_hinting, line_hinting, -line_hinting, -line_hinting)
        
        if border_radius == 0.0:
            painter_path.addRect(rect)
        else:
            painter_path.addRoundedRect(rect, border_radius, border_radius)
        
        if self._wrapping_state is WrappingState.NORMAL:
            # substract rects in the box shape in case of port_offset (even negativ)
            # logic would want to add rects if port_offset is negativ
            # But that also means that we should change the boudingRect,
            # So we won't.
            if port_in_offset != 0.0:
                for in_segment in input_segments:
                    moins_path = QPainterPath()
                    moins_path.addRect(QRectF(
                        0.0 - epsy,
                        in_segment[0] - line_hinting - epsy,
                        port_in_offset + line_hinting + epsd,
                        in_segment[1] - in_segment[0] + line_hinting * 2 + epsd))
                    painter_path = painter_path.subtracted(moins_path)
            
            if port_out_offset != 0.0:
                for out_segment in output_segments:
                    moins_path = QPainterPath()
                    moins_path.addRect(QRectF(
                        self._width - line_hinting - port_out_offset - epsy,
                        out_segment[0] - line_hinting - epsy,
                        port_out_offset + line_hinting + epsd,
                        out_segment[1] - out_segment[0] + line_hinting * 2 + epsd))
                    painter_path = painter_path.subtracted(moins_path)

            # No rounded corner if the last port is to close from the corner
            if (input_segments
                    and self._height - input_segments[-1][1] <= border_radius):
                left_path = QPainterPath()
                left_path.addRect(QRectF(
                    0.0 + line_hinting - epsy,
                    max(self._height - border_radius, input_segments[-1][1])
                        + line_hinting - epsy,
                    border_radius + epsd,
                    min(border_radius, self._height - input_segments[-1][1])
                        - 2 * line_hinting + epsd))
                painter_path = painter_path.united(left_path)

            if (input_segments
                    and input_segments[0][0] <= border_radius):
                top_left_path = QPainterPath()
                top_left_path.addRect(QRectF(
                    0.0 + line_hinting - epsy,
                    0.0 + line_hinting - epsy,
                    border_radius + epsd,
                    min(border_radius, input_segments[0][0])
                    - 2 * line_hinting + epsd))
                painter_path = painter_path.united(top_left_path)

            if (output_segments
                    and self._height - output_segments[-1][1] <= border_radius):
                right_path = QPainterPath()
                right_path.addRect(QRectF(
                    self._width - border_radius - line_hinting - epsy,
                    max(self._height - border_radius, output_segments[-1][1])
                        + line_hinting - epsy,
                    border_radius + epsd,
                    min(border_radius, self._height - output_segments[-1][1])
                        - 2 * line_hinting + epsd))
                painter_path = painter_path.united(right_path)
                
            if (output_segments
                    and output_segments[0][0] <= border_radius):
                top_right_path = QPainterPath()
                top_right_path.addRect(QRectF(
                    self._width - line_hinting + epsy - border_radius,
                    0.0 + line_hinting - epsy,
                    border_radius + epsd,
                    min(border_radius, output_segments[0][0])
                    - 2 * line_hinting + epsd))
                painter_path = painter_path.united(top_right_path)
            
        if self.is_monitor() and border_radius:
            if self._current_port_mode is PortMode.OUTPUT:
                left_path = QPainterPath()
                left_path.addRect(QRectF(
                    0.0 + line_hinting - epsy,
                    self._height - border_radius - epsy,
                    border_radius + epsd, border_radius - line_hinting + epsd))
                painter_path = painter_path.united(left_path)

                top_left_path = QPainterPath()
                top_left_path.addRect(QRectF(
                    0.0 + line_hinting - epsy, 0.0 + line_hinting - epsy,
                    border_radius + epsd, border_radius - line_hinting + epsd))
                painter_path = painter_path.united(top_left_path)

            elif self._current_port_mode is PortMode.INPUT:
                right_path = QPainterPath()
                right_path.addRect(QRectF(
                    self._width - line_hinting - epsy - border_radius,
                    self._height - border_radius - epsy,
                    border_radius + epsd, border_radius - line_hinting + epsd))
                painter_path = painter_path.united(right_path)

                top_right_path = QPainterPath()
                top_right_path.addRect(QRectF(
                    self._width - line_hinting - epsy - border_radius,
                    0.0 + line_hinting - epsy,
                    border_radius + epsd, border_radius - line_hinting + epsd))
                painter_path = painter_path.united(top_right_path)

        self._painter_path = painter_path

    def _get_unwrap_triangle_pos(
            self, last_in_pos: float, last_out_pos: float,
            one_column: bool, last_port_mode: PortMode) -> UnwrapButton:
        if self._has_side_title():
            if self._height - self._header_height >= 15.0:
                if self._current_port_mode is PortMode.OUTPUT:
                    return UnwrapButton.LEFT
                else:
                    return UnwrapButton.RIGHT
        
        if self._height - self._header_height >= 64.0:
            if one_column:
                if last_port_mode is PortMode.INPUT:
                    return UnwrapButton.RIGHT
                else:
                    return UnwrapButton.LEFT

            y_side_space = last_in_pos - last_out_pos

            if y_side_space < -10.0:
                return UnwrapButton.LEFT
            if y_side_space > 10.0:
                return UnwrapButton.RIGHT
            return UnwrapButton.CENTER
            
        return UnwrapButton.NONE

    def _set_widths_and_heights(
            self, normal_width: int, normal_height: int,
            wrapped_width: int, wrapped_height: int):
        if self._wrapping_state is WrappingState.WRAPPING:
            self._height = (normal_height
                            - (normal_height - wrapped_height)
                              * self._wrapping_ratio)
            self._width = (normal_width
                           - (normal_width - wrapped_width)
                             * self._wrapping_ratio)

        elif self._wrapping_state is WrappingState.UNWRAPPING:
            self._height = (wrapped_height
                            + (normal_height - wrapped_height)
                              * self._wrapping_ratio)
            self._width = (wrapped_width
                           + (normal_width - wrapped_width)
                             * self._wrapping_ratio)

        elif self._wrapping_state is WrappingState.WRAPPED:
            self._height = wrapped_height
            self._width = wrapped_width
        else:
            self._height = normal_height
            self._width = normal_width
            
        self._wrapped_width = wrapped_width
        self._unwrapped_width = normal_width
        self._wrapped_height = wrapped_height
        self._unwrapped_height = normal_height

    def update_positions(self, even_animated=False, without_connections=False,
                         prevent_overlap=True):
        if canvas.loading_items:
            return

        if (not even_animated
                and self in [b.widget for b in canvas.scene.move_boxes]):
            self.update_positions_pending = True
            # do not change box layout while box is moved by animation
            # update_positions will be called when animation is finished
            return

        self.prepareGeometryChange()
        
        self._current_port_mode = PortMode.NULL
        self._port_list.clear()
        self._portgrp_list.clear()

        for port in canvas.list_ports(group_id=self._group_id):
            if port.port_mode & self._port_mode:
                self._port_list.append(port)
                self._current_port_mode |= port.port_mode

        for portgrp in canvas.list_portgroups(group_id=self._group_id):
            if self._current_port_mode & portgrp.port_mode:
                self._portgrp_list.append(portgrp)

        if options.auto_hide_groups and not self._port_list:
            self.setVisible(False)
            return
        
        self.setVisible(True)
    
        align_port_types = self._should_align_port_types()

        ports_min_sizes = self._get_ports_min_sizes(align_port_types)
        last_in_pos = ports_min_sizes.last_in_pos
        last_out_pos = ports_min_sizes.last_out_pos
        last_inout_pos = ports_min_sizes.last_inout_pos
        max_in_width = ports_min_sizes.max_in_width
        max_out_width = ports_min_sizes.max_out_width
        last_port_mode = ports_min_sizes.last_port_mode

        box_theme = self.get_theme()
        pen_width = box_theme.fill_pen().widthF()
        height_for_ports = max(last_in_pos, last_out_pos)
        height_for_ports_one = last_inout_pos
       
        self._width_in = max_in_width
        self._width_out = max_out_width

        if self._wrapping_state in (WrappingState.NORMAL, WrappingState.WRAPPED):
            best_props = self._choose_box_layout(
                height_for_ports, height_for_ports_one,
                max_in_width, max_out_width)
            self._current_layout_mode = best_props.true_layout_mode
            self._header_width = best_props.header_width
            self._header_height = best_props.header_height
            print(self, self._header_height)
            self._ports_y_start = best_props.ports_y_start

            one_column = best_props.one_column
            box_width = best_props.box_width
            box_height = best_props.box_height

            normal_height = box_height
            normal_width = box_width

            # wrapped sizes
            if self._has_side_title():
                wrapped_height = self._header_height + pen_width * 2
                if self._current_port_mode is PortMode.INPUT:
                    wrapped_width = box_width - self._width_in
                elif self._current_port_mode is PortMode.OUTPUT:
                    wrapped_width = box_width - self._width_out
            else:
                wrapped_height = self._ports_y_start + canvas.theme.port_height
                wrapped_width = box_width
            
            # adapt box sizes to the grid
            if self._is_hardware:
                hwr = canvas.theme.hardware_rack_width
                normal_width = \
                    next_width_on_grid(normal_width + hwr * 2) - 2 * hwr
                normal_height = \
                    next_height_on_grid(normal_height + hwr * 2) - 2 * hwr
                wrapped_width = \
                    next_width_on_grid(wrapped_width + hwr * 2) - 2 * hwr
                wrapped_height = \
                    next_height_on_grid(wrapped_height + hwr * 2) - 2 * hwr
            else:
                normal_width = next_width_on_grid(normal_width)
                normal_height = next_height_on_grid(normal_height)
                wrapped_width = next_width_on_grid(wrapped_width)
                wrapped_height = next_height_on_grid(wrapped_height)
            
            # evaluate height available because of the grid adaptation
            # for nicer ports y positioning.
            if self._has_side_title():
                self._y_normal_rab = (normal_height - height_for_ports
                                      - pen_width)
                self._y_wrapped_rab = (wrapped_height - height_for_ports
                                       - pen_width)
            else:
                self._y_normal_rab = normal_height - height_for_ports - self._header_height - pen_width
                self._y_wrapped_rab = wrapped_height - canvas.theme.port_height - self._header_height

        else:
            normal_height = self._unwrapped_height
            normal_width = self._unwrapped_width
            wrapped_height = self._wrapped_height
            wrapped_width = self._wrapped_width
            
            one_column = bool(
                self._current_port_mode is PortMode.BOTH
                and self._current_layout_mode is BoxLayoutMode.HIGH)

        self._set_widths_and_heights(
            normal_width, normal_height,
            wrapped_width, wrapped_height)

        if self._wrapping_state is WrappingState.NORMAL:
            self._unwrap_triangle_pos = self._get_unwrap_triangle_pos(
                last_in_pos, last_out_pos, one_column, last_port_mode)

        ports_y_segments_dict = self._set_ports_y_positions(
            align_port_types, self._ports_y_start, one_column)

        self._set_ports_x_positions(max_in_width, max_out_width)
        self._set_title_positions()

        if (self._width != self._ex_width
                or self._height != self._ex_height
                or ports_y_segments_dict != self._ex_ports_y_segments_dict):
            self.build_painter_path(ports_y_segments_dict)

        if (self._width != self._ex_width
                or self._height != self._ex_height
                or self.scenePos() != self._ex_scene_pos):
            canvas.scene.resize_the_scene()

        self._ex_width = self._width
        self._ex_height = self._height
        self._ex_ports_y_segments_dict = ports_y_segments_dict
        self._ex_scene_pos = self.scenePos()

        if not without_connections:
            self.repaint_lines(forced=True)

        if prevent_overlap:
            if (self._wrapping_state in (WrappingState.NORMAL,
                                         WrappingState.WRAPPED)
                    and self.isVisible()):
                canvas.scene.deplace_boxes_from_repulsers([self])

        self.update_positions_pending = False
        self.update()
        
        # I do not understand why without this,
        # when a renamed port does not change the box geometry,
        # port and portgroups widgets aren't updated,
        # they will be if we click on it for exemple.        
        for portgrp in self._portgrp_list:
            if portgrp.widget is not None:
                portgrp.widget.update()
                
        for port in self._port_list:
            if port.widget is not None:
                port.widget.update()
                if port.hidden_conn_widget is not None:
                    port.hidden_conn_widget.update_line_pos()
                    port.hidden_conn_widget.update()
                    
    def get_dummy_rect(self) -> QRectF:
        '''Used only for dummy box, to know its size before joining'''
        self._current_port_mode = PortMode.NULL
        self._port_list.clear()
        self._portgrp_list.clear()

        for port in canvas.list_ports(group_id=self._group_id):
            if port.port_mode & self._port_mode:
                self._port_list.append(port)
                self._current_port_mode |= port.port_mode

        for portgrp in canvas.list_portgroups(group_id=self._group_id):
            if self._current_port_mode & portgrp.port_mode:
                self._portgrp_list.append(portgrp)

        align_port_types = self._should_align_port_types()
        
        ports_geo = self._get_ports_min_sizes(align_port_types)
        last_in_pos = ports_geo.last_in_pos
        last_out_pos = ports_geo.last_out_pos
        last_inout_pos = ports_geo.last_inout_pos
        max_in_width = ports_geo.max_in_width
        max_out_width = ports_geo.max_out_width
        
        box_theme = self.get_theme()
        down_height = box_theme.fill_pen().widthF()
        height_for_ports = max(last_in_pos, last_out_pos) + down_height
        height_for_ports_one = last_inout_pos + down_height
       
        self._width_in = max_in_width
        self._width_out = max_out_width

        best_props = self._choose_box_layout(
            height_for_ports, height_for_ports_one,
            max_in_width, max_out_width)
        
        return QRectF(0.0, 0.0, best_props.box_width, best_props.box_height)