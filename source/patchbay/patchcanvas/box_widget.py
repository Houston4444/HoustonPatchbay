
import logging
from typing import Iterator, Optional

from qtpy.QtCore import QRectF
from qtpy.QtGui import QPainterPath
from qtpy.QtWidgets import QGraphicsItem

from patshared import (
    BoxLayoutMode, PortMode, PortType, PortSubType, BoxType)
from .init_values import (
    canvas, options, InlineDisplay, GroupObject)
from .utils import get_portgroup_name_from_ports_names
from .box_widget_moth import BoxWidgetMoth, UnwrapButton, TitleLine, WrappingState
from .box_layout import PortsMinSizes, TitleOn, BoxLayout


_logger = logging.getLogger(__name__)


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


def from_float_to(from_f: float, to_f: float, ratio: float) -> float:
    if ratio >= 1.0:
        return to_f
    if ratio <= 0.0:
        return from_f
    
    return from_f + (to_f - from_f) * ratio 


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
        return f"BoxWidget({self._group_name}, {self._port_mode.name})"

    def _get_portgroup_name(self, portgrp_id: int):
        return get_portgroup_name_from_ports_names(
            [p.port_name for p in self._port_list
             if p.portgrp_id == portgrp_id])

    def _should_align_port_types(self) -> bool:
        '''check if we can align port types
           eg, align first midi input to first midi output'''
        if self._current_port_mode is not PortMode.BOTH:
            return False
        
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
        last_in_pos = last_out_pos = 0.0
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

                        if portgrp is not None and portgrp.widget is not None:
                            portgrp.widget.set_print_name(
                                portgrp_name,
                                max_pwidth - canvas.theme.port_grouped_width - 5)
                    
                    port.widget.set_print_name(
                        port.port_name.replace(
                            self._get_portgroup_name(port.portgrp_id), '', 1),
                        int(max_pwidth/2))
                    
                    if portgrp is None or portgrp.widget is None:
                        _logger.warning('_get_ports_min_sizes, '
                                        'no portgrp or no portgrp.widget')
                        continue
                    
                    if (portgrp.widget.get_text_width() + 5
                            > max_pwidth - port.widget.get_text_width()):
                        portgrp.widget.reduce_print_name(
                            max_pwidth - int(port.widget.get_text_width()) - 5)
                    
                    # the port_grouped_width is also used to define
                    # the portgroup minimum width
                    size = (max(portgrp.widget.get_text_width() + 3.0,
                                canvas.theme.port_grouped_width)
                            + max(port.widget.get_text_width() + 6.0,
                                  canvas.theme.port_grouped_width)
                            + port_offset)
                else:
                    port.widget.set_print_name(port.port_name, max_pwidth)
                    size = max(port.widget.get_text_width() + 6.0 + port_offset, 20.0)
                
                type_and_sub = (port.port_type, port.port_subtype)
                
                if port.port_mode is PortMode.INPUT:
                    max_in_width = max(max_in_width, size)
                    if type_and_sub != last_in_type_and_sub:
                        if (last_in_type_and_sub 
                                != (PortType.NULL, PortSubType.REGULAR)):
                            last_in_pos += port_type_spacing
                        last_in_type_and_sub = type_and_sub
                        n_in_type_and_subs += 1

                    last_in_pos += canvas.theme.port_height
                    if last_of_portgrp:
                        last_in_pos += port_spacing

                elif port.port_mode is PortMode.OUTPUT:
                    max_out_width = max(max_out_width, size)
                    
                    if type_and_sub != last_out_type_and_sub:
                        if (last_out_type_and_sub != 
                                (PortType.NULL, PortSubType.REGULAR)):
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
        last_inout_pos = 0.0
        last_type_and_sub = (PortType.NULL, PortSubType.REGULAR)
        n_inout_types_and_sub = 0

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
                        n_inout_types_and_sub += 1

                    if port.pg_pos:
                        continue

                    last_inout_pos += port.pg_len * canvas.theme.port_height
                    last_inout_pos += port_spacing
                    
                    last_port_mode = port.port_mode
        
        return PortsMinSizes(
            final_last_in_pos,
            final_last_out_pos,
            last_inout_pos,
            max_in_width + canvas.theme.port_height / 2.0,
            max_out_width + canvas.theme.port_height / 2.0,
            n_in_type_and_subs,
            n_out_type_and_subs,
            n_inout_types_and_sub,
            last_port_mode
        )

    @staticmethod
    def split_in_two(string: str, n_lines: int) -> list[str]:
        def polished_list(input_list: list[str]) -> list:
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
                titles = list[str]()
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

    def _choose_box_layout(
            self,
            ports_min_sizes: PortsMinSizes) -> tuple[BoxLayout, BoxLayout]:
        '''choose in how many lines the title should be splitted
        and if the box layout should be large or high.
        Return the 2 best layout choices.'''

        box_theme = self.get_theme()
        font_size = box_theme.font().pixelSize()

        if self.has_top_icon():
            icon_size = int(box_theme.icon_size())
        else:
            icon_size = 0
        
        # Check Text Name size
        
        # first look in cache if title sizes are stocked
        all_title_templates = box_theme.get_title_templates(
            self._group_name, self._can_handle_gui, icon_size)
        lines_choice_max = len(all_title_templates) - 1

        if not all_title_templates:
            # this box title is not in cache, we need to estimate all its sizes
            # depending number of splitted lines.
            title_template = {
                "title_width": 0,
                "header_width": 0,
                "title_height": 0,
                "header_height": 0}

            all_title_templates = [title_template.copy() for i in range(8)]

            last_lines_count = 0
            GUI_MARGIN = 2
            title_line_y_start = 1 + font_size
            title_height = title_line_y_start + 3
            
            if self.has_top_icon():
                header_height = 3 + icon_size + 3
            else:
                header_height = title_height

            i = 0
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

                    if self.has_top_icon() and title_line.y <= icon_size + 6 + font_size:
                        # text line is at right of the icon
                        header_width += icon_size + 4

                    max_header_width = max(max_header_width, int(header_width))
                
                title_height = int(
                    title_line_y_start
                    + int(font_size * 1.4) * (len(title_lines) - 1)
                    + font_size / 2)
                
                header_height = max(header_height, title_height)
                
                if self._can_handle_gui:
                    max_header_width += 2 * GUI_MARGIN
                    header_height += 2 * GUI_MARGIN

                new_title_template = title_template.copy()
                new_title_template['title_width'] = max_title_width
                new_title_template['header_width'] = max_header_width
                new_title_template['title_height'] = title_height
                new_title_template['header_height'] = header_height
                all_title_templates[i] = new_title_template

                if i > 2 and len(title_lines) <= last_lines_count:
                    break

                last_lines_count = len(title_lines)

            lines_choice_max = i
            if self.has_top_icon():
                icon_size = int(box_theme.icon_size())
            else:
                icon_size = 0

            box_theme.save_title_templates(
                self._group_name, self._can_handle_gui, icon_size,
                all_title_templates[:lines_choice_max])

        # Now compare multiple possible areas for the box,
        # depending on BoxLayoutMode and number of lines for the box title.

        layout_mode = self._layout_mode
        BoxLayout.init_from_box(self, ports_min_sizes)
        box_layouts = list[BoxLayout]()
        
        if self._current_port_mode in (PortMode.INPUT, PortMode.OUTPUT):
            for i in range(1, lines_choice_max + 1):
                box_layouts.append(
                    BoxLayout(i, BoxLayoutMode.LARGE,
                              TitleOn.SIDE, all_title_templates[i]))
            
            if self.has_top_icon():
                for i in range(1, lines_choice_max + 1):
                    box_layouts.append(
                        BoxLayout(i, BoxLayoutMode.LARGE,
                                  TitleOn.SIDE_UNDER_ICON,
                                  all_title_templates[i]))
                
            for i in range(1, lines_choice_max + 1):
                box_layouts.append(
                    BoxLayout(i, BoxLayoutMode.HIGH,
                              TitleOn.TOP, all_title_templates[i]))
        else:
            for i in range(1, lines_choice_max + 1):
                box_layouts.append(
                    BoxLayout(i, BoxLayoutMode.LARGE,
                              TitleOn.TOP, all_title_templates[i]))

            for i in range(1, lines_choice_max + 1):
                box_layouts.append(
                    BoxLayout(i, BoxLayoutMode.HIGH,
                              TitleOn.TOP, all_title_templates[i]))

        # sort areas and choose the first one (the littlest area)
        box_layouts.sort()
        
        high_layout, large_layout = None, None
        
        for layout in box_layouts:
            if (high_layout is None
                    and layout.layout_mode is BoxLayoutMode.HIGH):
                high_layout = layout
            elif (large_layout is None
                    and layout.layout_mode is BoxLayoutMode.LARGE):
                large_layout = layout

        if high_layout is None or large_layout is None:
            # can not happen, just for typing
            raise Exception

        high_layout.set_choosed()
        large_layout.set_choosed()
        
        if layout_mode is BoxLayoutMode.AUTO:
            if high_layout is box_layouts[0]:
                return high_layout, large_layout
            return large_layout, high_layout
        
        if layout_mode is BoxLayoutMode.HIGH:
            return high_layout, large_layout
        
        return large_layout, high_layout

    def _set_ports_y_positions(
            self, align_port_types: bool) -> dict[str, list[list[float]]]:
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
        
        if self._layout is None:
            raise Exception('._layout is needed')
        
        box_theme = self.get_theme()
        port_spacing = box_theme.port_spacing()
        port_type_spacing = box_theme.port_type_spacing()
        pen_width = box_theme.fill_pen().widthF()
        last_in_type_and_sub = (PortType.NULL, PortSubType.REGULAR)
        last_out_type_and_sub = (PortType.NULL, PortSubType.REGULAR)
        last_type_and_sub = (PortType.NULL, PortSubType.REGULAR)

        port_type_spacing_in = port_type_spacing_out = port_type_spacing        
        one_column = self._layout.one_column
        
        if self._has_side_title():
            start_pos = pen_width + port_spacing
        else:
            start_pos = pen_width + self._header_height

        if self._layout.title_on is TitleOn.TOP:
            wrapped_port_pos = (self._layout.wrapped_height
                                - canvas.theme.port_height - pen_width)
        else:
            wrapped_port_pos = pen_width + port_spacing

        last_in_pos = last_out_pos = start_pos
        
        # manage exceedent height in the box
        # due to the grid height (or to the others side ports
        # in a grouped box).
        exc_in = self._layout.exceeding_y_ins
        exc_out = self._layout.exceeding_y_outs
        exc_inout = self._layout.exceeding_y_inouts
        n_types_in = self._layout._pms.n_in_type_and_subs
        n_types_out = self._layout._pms.n_out_type_and_subs
        n_types_inout = self._layout._pms.n_inout_type_and_subs
        
        if one_column:
            new_pts = exc_inout / (1 + n_types_inout)
            if new_pts > port_type_spacing:
                port_type_spacing = port_type_spacing_in = \
                    port_type_spacing_out = new_pts
                last_in_pos += new_pts
                last_out_pos += new_pts
            else:
                last_in_pos += exc_inout / 2
                last_out_pos += exc_inout / 2

        elif align_port_types:
            exceeding = min(exc_in, exc_out)
            n_types = max(n_types_in, n_types_out)
            new_pts = exceeding / (1 + n_types)
            if new_pts > port_type_spacing:
                port_type_spacing = new_pts
                port_type_spacing_in = port_type_spacing_out = new_pts
                last_in_pos += port_type_spacing
                last_out_pos += port_type_spacing
            else:
                last_in_pos += exceeding / 2
                last_out_pos += exceeding / 2

        elif self._current_port_mode is PortMode.BOTH:
            if exc_out < exc_in:
                new_pts_out = exc_out / (1 + n_types_out)
                more_out = 0.0
                if new_pts_out > port_type_spacing:
                    port_type_spacing_out = new_pts_out
                    last_in_pos += new_pts_out
                    last_out_pos += new_pts_out
                    more_out = (new_pts_out - port_type_spacing) * (n_types_out -1)
                
                if n_types_in > 1:
                    port_type_spacing_in += (
                        (exc_in + more_out - exc_out) / (n_types_in - 1))
            else:
                new_pts_in = exc_in / (1 + n_types_in)
                more_in = 0.0
                if new_pts_in > port_type_spacing:
                    port_type_spacing_in = new_pts_in
                    last_in_pos += new_pts_in
                    last_out_pos += new_pts_in
                    more_in = (new_pts_in - port_type_spacing) * (n_types_in - 1)
                
                if n_types_out > 1:
                    port_type_spacing_out += (
                        (exc_out + more_in - exc_in) / (n_types_out - 1))
        else:
            new_pts_in = exc_in / (n_types_in + 1)
            if new_pts_in > port_type_spacing_in:
                port_type_spacing_in = new_pts_in
                last_in_pos += new_pts_in
            else:
                last_in_pos += exc_in / 2
                
            new_pts_out = exc_out / (n_types_out + 1)
            if new_pts_out > port_type_spacing_out:
                port_type_spacing_out = new_pts_out
                last_out_pos += new_pts_out
            else:
                last_out_pos += exc_out / 2
            
        input_segments = list[list[float]]()
        output_segments = list[list[float]]()
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
                            last_in_pos += port_type_spacing_in
                        last_in_type_and_sub = type_and_sub

                    if last_in_pos >= in_segment[1] + port_spacing + port_type_spacing_in:
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
                        if portgrp is not None:
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
                            last_out_pos += port_type_spacing_out
                        last_out_type_and_sub = type_and_sub

                    if last_out_pos >= out_segment[1] + port_spacing + port_type_spacing_out:
                        if out_segment[0] != out_segment[1]:
                            output_segments.append(out_segment)
                        out_segment = [last_out_pos, last_out_pos]

                    if port.portgrp_id:
                        portgrp = port.portgrp
                        if portgrp is not None:
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
        
        ports_top_in = 0.0
        ports_bottom_in = 0.0
        ports_top_out = 0.0
        ports_bottom_out = 0.0
        
        if input_segments:
            ports_top_in = input_segments[0][0]
            ports_bottom_in = input_segments[-1][1]
        
        if output_segments:
            ports_top_out = output_segments[0][0]
            ports_bottom_out = output_segments[-1][1]
        
        wp_ports_bottom = wrapped_port_pos + canvas.theme.port_height
        
        match self._wrapping_state:
            case WrappingState.WRAPPED:
                ports_top_in = ports_top_out = wrapped_port_pos
                ports_bottom_in = ports_bottom_out = wp_ports_bottom

            case WrappingState.WRAPPING:
                ports_top_in = from_float_to(
                    ports_top_in, wrapped_port_pos, self._wrapping_ratio)
                ports_top_out = from_float_to(
                    ports_top_out, wrapped_port_pos, self._wrapping_ratio)
                ports_bottom_in = from_float_to(
                    ports_bottom_in, wp_ports_bottom, self._wrapping_ratio)
                ports_bottom_out = from_float_to(
                    ports_bottom_out, wp_ports_bottom, self._wrapping_ratio)
                
            case WrappingState.UNWRAPPING:
                ports_top_in = from_float_to(
                    wrapped_port_pos, ports_top_in, self._wrapping_ratio)
                ports_top_out = from_float_to(
                    wrapped_port_pos, ports_top_out, self._wrapping_ratio)
                ports_bottom_in = from_float_to(
                    wp_ports_bottom, ports_bottom_in, self._wrapping_ratio)
                ports_bottom_out = from_float_to(
                    wp_ports_bottom, ports_bottom_out, self._wrapping_ratio)

        self._layout.set_ports_top_bottom(
            ports_top_in, ports_bottom_in,
            ports_top_out, ports_bottom_out)
        
        return {'input_segments': input_segments,
                'output_segments': output_segments}

    def _set_ports_x_positions(self, ports_min_sizes: PortsMinSizes):
        box_theme = self.get_theme()
        port_in_offset = box_theme.port_in_offset()
        port_out_offset = box_theme.port_out_offset()
        
        max_in_width = ports_min_sizes.ins_width
        max_out_width = ports_min_sizes.outs_width
        
        # Horizontal ports re-positioning
        in_x = port_in_offset
        out_x = self._width - max_out_width

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
                    portgrp.widget.setX(in_x)
                elif portgrp.port_mode is PortMode.OUTPUT:
                    portgrp.widget.set_portgrp_width(max_out_width - port_out_offset)
                    portgrp.widget.setX(out_x)

            max_port_in_pg_width = canvas.theme.port_grouped_width

            for port in portgrp.ports:
                if port.widget is not None:
                    port_print_width = int(port.widget.get_text_width())

                    # change port in portgroup width only if
                    # portgrp will have a name
                    # to ensure that portgroup widget is large enough
                    max_port_in_pg_width = max(max_port_in_pg_width,
                                               port_print_width + 6)

            out_in_portgrp_x = (self._width - port_out_offset
                                - max_port_in_pg_width)

            if portgrp.widget is not None:
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
        icon_size = box_theme.icon_size()

        # when client is client capable of gui state
        # header has margins
        gui_margin = 2 if self._can_handle_gui else 0
        
        # set title lines Y position
        title_y_start = font_size + 1 + gui_margin + pen_width

        if self._title_under_icon:
            title_y_start = 3 + gui_margin + icon_size + font_spacing + pen_width
        
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
                    
                    self.set_top_icon_pos(
                        self._width - int(icon_size) - 3 - pen_width - gui_margin,
                        int(3 + pen_width + gui_margin))
    
                elif self._current_port_mode is PortMode.OUTPUT:
                    title_line.x = (pen_width + self._header_width
                                    - title_line.size - 6)
                    
                    if self._can_handle_gui:
                        title_line.x -= 2
                    
                    self.set_top_icon_pos(
                        3 + int(pen_width) + gui_margin,
                        3 + int(pen_width) + gui_margin)
                
                title_line.y += y_correction
            return

        # Now we are sure title is on top

        # get title global sizes
        max_title_size = 0
        max_title_icon_size = 0

        for title_line in self._title_lines:
            title_size = title_line.size
            if self.has_top_icon() and title_line.y <= icon_size + 6 + font_size:
                # title line is beside icon
                title_size += icon_size + 4
                max_title_icon_size = max(max_title_icon_size, title_size)
            max_title_size = max(max_title_size, title_size)
        
        # set title lines X position
        for title_line in self._title_lines:
            if self.has_top_icon() and title_line.y <= icon_size + 6 + font_size:
                # title line is beside the icon
                title_line.x = int((self._width - max_title_icon_size) / 2 + icon_size + 4)
            else:
                title_line.x = int((self._width - title_line.size) / 2)
        
        # set icon position
        self.set_top_icon_pos(
            int((self._width - max_title_icon_size)/2),
            int(3 + pen_width + gui_margin))

        # calculate header lines positions
        side_size = (self._width - max(max_title_icon_size, max_title_size)) * 0.5
        
        if side_size > 10:
            y = self._header_height / 2 + pen_width
            
            self._header_line_left = (5.0, y, side_size - 5.0, y)
            self._header_line_right = (self._width - side_size + 5.0, y,
                                       self._width - 5.0, y)
    
    def _build_painter_path(
            self, pos_dict: dict[str, list[list[float]]],
            selected=False):
        input_segments = pos_dict['input_segments']
        output_segments = pos_dict['output_segments']
        
        painter_path = QPainterPath()
        theme = self.get_theme()
        if selected:
            theme = theme.selected
        
        border_radius = theme.border_radius()
        port_in_offset = abs(theme.port_in_offset())
        port_out_offset = abs(theme.port_out_offset())
        bore_in = bool(theme.port_in_offset_mode() == 'bore')
        bore_out = bool(theme.port_out_offset_mode() == 'bore')
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
        
        if not bore_in:
            port_in_offset = 0.0
        if not bore_out:
            port_out_offset = 0.0
        
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

        if selected:
            self._painter_path_sel = painter_path
        else:
            self._painter_path = painter_path

    def _get_wrap_triangle_pos(self) -> UnwrapButton:
        if self._has_side_title():
            if self._height - self._header_height >= 15.0:
                if self._current_port_mode is PortMode.OUTPUT:
                    return UnwrapButton.LEFT
                else:
                    return UnwrapButton.RIGHT

        if self._layout is None:
            raise Exception('_get_wrap_triangle_pos, _layout is needed')

        last_in_pos = self._layout.ports_bottom_in
        last_out_pos = self._layout.ports_bottom_out

        if self._height - self._header_height >= 64.0:
            if (self._current_port_mode is PortMode.BOTH
                    and self._current_layout_mode is BoxLayoutMode.HIGH):
                if last_in_pos > last_out_pos:
                    return UnwrapButton.RIGHT
                else:
                    return UnwrapButton.LEFT

            elif self._current_port_mode is PortMode.INPUT:
                return UnwrapButton.RIGHT
            
            elif self._current_port_mode is PortMode.OUTPUT:
                return UnwrapButton.LEFT

            y_side_space = last_in_pos - last_out_pos

            if y_side_space < -10.0:
                return UnwrapButton.LEFT
            if y_side_space > 10.0:
                return UnwrapButton.RIGHT
            return UnwrapButton.CENTER
            
        return UnwrapButton.NONE

    def update_positions(self, even_animated=False, without_connections=False,
                         scene_checks=True, theme_change=False,
                         wrap_anim=False):
        '''Redraw the box, may take some time (~ 10ms for a 30 ports box).
        It checks the present ports and portgroups, and choose the box size.
        
        even_animated : if we need to update the box even
        if the box is in animation.
        
        without_connections : optimization, if we redraw all groups, we can
        redraw connections after having redrawn all boxes (2 times faster).
            
        scene_checks : if we redraw multiple boxes, we can resize the scene
        and check box overlapping after having redrawn all boxes.
            
        theme_change : only when we change theme.
        
        wrap_anim : only while wrapping/unwrapping, does not check the
        present ports, size is based on saved sizes.'''
        
        if canvas.loading_items:
            return

        if (not (even_animated or wrap_anim)
                and self in canvas.scene.move_boxes):
            self.update_positions_pending = True
            # do not change box layout while box is moved by animation
            # update_positions will be called when animation is finished
            return

        self.prepareGeometryChange()

        if (self._wrapping_state
                in (WrappingState.NORMAL, WrappingState.WRAPPED)
                or even_animated):
            # update port/portgrp list if box is not in wrapping animation
            # or forced with even_animated
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
        
        if theme_change:
            for portgrp in self._portgrp_list:
                if portgrp.widget is not None:
                    portgrp.widget.update_theme()
                
            for port in self._port_list:
                if port.hidden_conn_widget is not None:
                    port.hidden_conn_widget.update_theme()
                    port.hidden_conn_widget.update_line_gradient()

        if options.auto_hide_groups and not self._port_list:
            self.setVisible(False)
            return
    
        self.setVisible(True)
    
        align_port_types = self._should_align_port_types()
        ports_min_sizes = self._get_ports_min_sizes(align_port_types)

        if (self._wrapping_state in (WrappingState.NORMAL, WrappingState.WRAPPED)
                or even_animated):
            box_layout, alter_layout = self._choose_box_layout(ports_min_sizes)
            self._layout = box_layout
            self._alter_layout = alter_layout
            self._current_layout_mode = box_layout.layout_mode
            self._title_under_icon = bool(
                box_layout.title_on is TitleOn.SIDE_UNDER_ICON)
            self._title_lines = self._split_title(box_layout.n_lines)
            self._header_width = box_layout.header_width
            self._header_height = box_layout.header_height

            self._unwrapped_width = box_layout.width
            self._unwrapped_height = box_layout.height
            self._wrapped_width = box_layout.wrapped_width
            self._wrapped_height = box_layout.wrapped_height
            
        if self._wrapping_state is WrappingState.NORMAL:
            self._width = self._unwrapped_width
            self._height = self._unwrapped_height
            
        elif self._wrapping_state is WrappingState.WRAPPED:
            self._width = self._wrapped_width
            self._height = self._wrapped_height

        elif self._wrapping_state is WrappingState.WRAPPING:
            self._width = (self._unwrapped_width
                           - (self._unwrapped_width - self._wrapped_width)
                             * self._wrapping_ratio)
            self._height = (self._unwrapped_height
                            - (self._unwrapped_height - self._wrapped_height)
                              * self._wrapping_ratio)

        elif self._wrapping_state is WrappingState.UNWRAPPING:
            self._width = (self._wrapped_width
                           + (self._unwrapped_width - self._wrapped_width)
                             * self._wrapping_ratio)
            self._height = (self._wrapped_height
                            + (self._unwrapped_height - self._wrapped_height)
                              * self._wrapping_ratio)            

        ports_y_segments_dict = self._set_ports_y_positions(align_port_types)

        self._set_ports_x_positions(ports_min_sizes)
        self._set_title_positions()
        
        if self._wrapping_state is WrappingState.NORMAL:
            self._wrap_triangle_pos = self._get_wrap_triangle_pos()

        if (theme_change
                or self._width != self._ex_width
                or self._height != self._ex_height
                or ports_y_segments_dict != self._ex_ports_y_segments_dict):
            self._build_painter_path(ports_y_segments_dict)
            self._build_painter_path(ports_y_segments_dict, selected=True)

        if (self._width != self._ex_width
                or self._height != self._ex_height
                or self.scenePos() != self._ex_scene_pos):
            if scene_checks:
                canvas.scene.resize_the_scene()

        self._ex_width = self._width
        self._ex_height = self._height
        self._ex_ports_y_segments_dict = ports_y_segments_dict
        self._ex_scene_pos = self.scenePos()

        if not without_connections:
            self.repaint_lines(forced=True)

        if scene_checks:
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
        '''Used only for dummy box, to know its size
        before joining or arranging.'''
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
        ports_min_sizes = self._get_ports_min_sizes(align_port_types)
        box_layout, alter_layout = self._choose_box_layout(ports_min_sizes)
        
        if self.is_hardware:
            hwr = float(canvas.theme.hardware_rack_width)
        else:
            hwr = 0.0

        if self.is_wrapped():
            return QRectF(-hwr, -hwr, box_layout.full_wrapped_width,
                          box_layout.full_wrapped_height)
        
        return QRectF(-hwr, -hwr,
                      box_layout.full_width, box_layout.full_height)
    
    def get_layout(self, layout_mode: Optional[BoxLayoutMode] = None) -> BoxLayout:
        if self._layout is None:
            raise Exception('get_layout, .layout is required !')
        
        if layout_mode is None:
            return self._layout
        
        if layout_mode is BoxLayoutMode.LARGE:
            if self._current_layout_mode is BoxLayoutMode.LARGE:
                return self._layout
            return self._alter_layout
        
        if layout_mode is BoxLayoutMode.HIGH:
            if self._current_layout_mode is BoxLayoutMode.HIGH:
                return self._layout
            return self._alter_layout
        
        return self._layout