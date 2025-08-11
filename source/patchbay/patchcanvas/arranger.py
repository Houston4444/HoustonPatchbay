import logging
from enum import IntEnum
from typing import Optional

from qtpy.QtCore import QRectF

from patshared import BoxLayoutMode, PortMode, BoxType, GroupPos
from .init_values import GroupObject, CanvasThemeMissing, canvas, CallbackAct
from .utils import nearest_on_grid, next_left_on_grid, next_top_on_grid
from .box_widget import BoxWidget
from .patchcanvas import (
    move_group_boxes, repulse_all_boxes, split_group)

_logger = logging.getLogger(__name__)


class GoTo(IntEnum):
    NONE = 0
    LEFT = 1
    RIGHT = 2


class BoxAlign(IntEnum):
    LEFT = 0
    CENTER = 1
    RIGHT = 2


class BoxArranger:
    def __init__(self, arranger: 'CanvasArranger',
                 group: GroupObject, port_mode: PortMode):
        self.arranger = arranger
        self.box_rect = QRectF()
        
        # we don't take the group here
        # because it can be splitted during the BoxArranger life
        # edit TODO: it is not true anymore
        # we could take the group now.
        self.group_id = group.group_id
        self.box_type = group.box_type
        self.group_name = group.group_name
        self.port_mode = port_mode

        self.conns_in_group_ids = set[int]()
        self.conns_out_group_ids = set[int]()
        self.col_left = 2 # is mininum if not fixed
        self.col_right = -2 # is maximum if not fixed
        self.col_left_fixed = False
        self.col_right_fixed = False
        self.col_left_counted = False
        self.col_right_counted = False
        self.analyzed = False
        
        self.ins_connected_to = list[BoxArranger]()
        self.outs_connected_to = list[BoxArranger]()
        
        # needed at positioning phase
        self.y_pos = 0.0
        self.column = 0

    def __repr__(self) -> str:
        return f"BoxArranger({self.group_name}, {self.port_mode.name})"
    
    def __lt__(self, other: 'BoxArranger') -> bool:
        if self.box_type is not other.box_type:
            if self.box_type is BoxType.APPLICATION:
                return False
            if other.box_type is BoxType.APPLICATION:
                return True
            
            return self.box_type < other.box_type
        
        if self.arranger.sort_context is PortMode.INPUT:
            return len(self.ins_connected_to) > len(other.ins_connected_to)
        elif self.arranger.sort_context is PortMode.OUTPUT:
            return len(self.outs_connected_to) > len(other.outs_connected_to)
                
        return self.group_id < other.group_id
    
    def set_box(self):
        group = canvas.get_group(self.group_id)
        if group is None:
            raise Exception
        
        for box in group.widgets:
            if box._port_mode is self.port_mode:
                self.box_rect = box.boundingRect()
                return
        
        tmp_box = BoxWidget(group, self.port_mode)
        self.box_rect = tmp_box.get_dummy_rect()
        
        if canvas.scene is not None:
            canvas.scene.remove_box(tmp_box)
        del tmp_box
    
    def is_owner(self, group_id: int, port_mode: PortMode):
        return bool(self.group_id == group_id
                    and self.port_mode & port_mode)
    
    def set_neighbours(self, box_arrangers: list['BoxArranger']):
        for group_id in self.conns_in_group_ids:
            for box_arranger in box_arrangers:
                if box_arranger.is_owner(group_id, PortMode.INPUT):
                    self.outs_connected_to.append(box_arranger)
                    break

        for group_id in self.conns_out_group_ids:
            for box_arranger in box_arrangers:
                if box_arranger.is_owner(group_id, PortMode.OUTPUT):
                    self.ins_connected_to.append(box_arranger)
                    break
    
    def parse_all(self, path: list['BoxArranger']=[]):
        if self.arranger.ba_to_split is not None:
            return
        
        if self in path:
            return
        
        path.append(self)
        
        self.count_left()
        if self.arranger.ba_to_split:
            return

        self.count_right()
        if self.arranger.ba_to_split:
            return
        
        for ba_in in self.ins_connected_to:
            ba_in.parse_all(path)
        
        for ba_out in self.outs_connected_to:
            ba_out.parse_all(path)
            
        self.analyzed = True
    
    def count_left(self, path: list['BoxArranger']=[]):
        if self.arranger.ba_to_split is not None:
            return
        
        if self.col_left_fixed or self.col_left_counted:
            return
        
        if self in path:
            self.arranger.ba_to_split = self
            return
        
        path = path.copy()
        path.append(self)
        
        for ba in self.ins_connected_to:
            ba.count_left(path)
        
        left_min = self.col_left
        fixed = 0

        for ba in self.ins_connected_to:
            left_min = max(left_min, ba.col_left + 1)
            if ba.col_left_fixed:
                fixed += 1

        self.col_left = left_min
        if fixed and fixed == len(self.ins_connected_to):
            if not self.col_right_fixed:
                self.col_left_fixed = True
        
        self.col_left_counted = True
    
    def count_right(self, path: list['BoxArranger']=[]):
        if self.arranger.ba_to_split is not None:
            return
        
        if self.col_right_fixed or self.col_right_counted:
            return
        
        if self in path:
            self.arranger.ba_to_split = self
            return
        
        path = path.copy()
        path.append(self)
        
        for ba in self.outs_connected_to:
            ba.count_right(path)

        right_min = self.col_right
        fixed = 0
        
        for ba in self.outs_connected_to:
            right_min = min(right_min, ba.col_right - 1)
            if ba.col_right_fixed:
                fixed += 1
        
        self.col_right = right_min
        if fixed and fixed == len(self.outs_connected_to):
            if not self.col_left_fixed:
                self.col_right_fixed = True

        self.col_right_counted = True
    
    def get_needed_columns(self) -> int:
        return self.col_left - self.col_right - 1
    
    def get_column_with_nb(self, n_columns: int) -> int:
        if self.col_left_fixed:
            return self.col_left
        
        if self.col_right_fixed:
            return n_columns + self.col_right + 1
        
        return self.col_left

    def get_box_align(self) -> BoxAlign:
        if self.port_mode is PortMode.OUTPUT:
            return BoxAlign.RIGHT
        if self.port_mode is PortMode.INPUT:
            return BoxAlign.LEFT
        if self.outs_connected_to and self.ins_connected_to:
            return BoxAlign.LEFT
        if self.outs_connected_to:
            return BoxAlign.RIGHT
        if self.ins_connected_to:
            return BoxAlign.LEFT
        return BoxAlign.LEFT

    def reset(self):
        self.col_left = 2
        self.col_left_counted = False
        self.col_left_fixed = False
        self.col_right = -2
        self.col_right_counted = False
        self.col_right_fixed = False
        self.analyzed = False


class CanvasArranger:
    'Arranger main class for "follow signal chain" action'

    def __init__(self):
        self.box_arrangers = list[BoxArranger]()
        self.ba_networks = list[list[BoxArranger]]()
        self.sort_context = PortMode.BOTH

        # is set only in case there are looping connections
        # around this box arranger.
        self.ba_to_split: Optional[BoxArranger] = None

        to_split_group_ids = set[int]()

        for conn in canvas.list_connections():
            if conn.group_out_id == conn.group_in_id:
                to_split_group_ids.add(conn.group_out_id)

        for group in canvas.group_list:
            if (group.box_type is BoxType.HARDWARE
                    or group.group_id in to_split_group_ids):
                self.box_arrangers.append(
                    BoxArranger(self, group, PortMode.OUTPUT))
                self.box_arrangers.append(
                    BoxArranger(self, group, PortMode.INPUT))
            else:
                self.box_arrangers.append(
                    BoxArranger(self, group, PortMode.BOTH))

        for conn in canvas.list_connections():
            for box_arranger in self.box_arrangers:
                if box_arranger.is_owner(conn.group_out_id, PortMode.OUTPUT):
                    box_arranger.conns_in_group_ids.add(conn.group_in_id)
                if box_arranger.is_owner(conn.group_in_id, PortMode.INPUT):
                    box_arranger.conns_out_group_ids.add(conn.group_out_id)
    
        for box_arranger in self.box_arrangers:
            box_arranger.set_neighbours(self.box_arrangers)
        
        self.sort_context = PortMode.INPUT
        for box_arranger in self.box_arrangers:
            box_arranger.outs_connected_to.sort()
            
        self.sort_context = PortMode.OUTPUT
        for box_arranger in self.box_arrangers:
            box_arranger.ins_connected_to.sort()

    def needs_to_split_a_box(self) -> bool:
        if self.ba_to_split is None:
            return False

        group = canvas.get_group(self.ba_to_split.group_id)
        if group is None:
            return False
        
        new_ba = BoxArranger(self, group, PortMode.INPUT)
        new_ba.ins_connected_to = self.ba_to_split.ins_connected_to
        
        for ba in self.ba_to_split.ins_connected_to:
            ba.outs_connected_to.remove(self.ba_to_split)
            ba.outs_connected_to.append(new_ba)

        self.ba_to_split.ins_connected_to = []
        self.ba_to_split.port_mode = PortMode.OUTPUT
        
        self.box_arrangers.append(new_ba)
        self.ba_to_split = None

        for ba in self.box_arrangers:
            ba.reset()

        return True

    def count_column_boxes(self, hardware_on_sides=False) -> bool:
        self.ba_to_split = None
        self.ba_networks.clear()
        
        if hardware_on_sides:
            for box_arranger in self.box_arrangers:
                if (box_arranger.col_left == 1
                        and box_arranger.col_left_fixed
                        and not box_arranger.analyzed):
                    ba_network = list[BoxArranger]()
                    box_arranger.parse_all(ba_network)

                    if self.needs_to_split_a_box():
                        return False

                    self.ba_networks.append(ba_network)

            for box_arranger in self.box_arrangers:
                if (box_arranger.col_right == -1
                        and box_arranger.col_right_fixed
                        and not box_arranger.analyzed):
                    ba_network = list[BoxArranger]()
                    box_arranger.parse_all(ba_network)

                    if self.needs_to_split_a_box():
                        return False

                    self.ba_networks.append(ba_network)

        for box_arranger in self.box_arrangers:
            if box_arranger.analyzed:
                continue
            
            ba_network = list[BoxArranger]()
            box_arranger.parse_all(ba_network)
            
            if self.needs_to_split_a_box():
                return False
            
            self.ba_networks.append(ba_network)
                    
        n_columns = max(
            [ba.get_needed_columns() for ba in self.box_arrangers] + [3])
        
        for ba in self.box_arrangers:
            if ba.get_needed_columns() == n_columns:
                ba.col_left_fixed = True
                ba.col_right_fixed = True

        for ba_network in self.ba_networks:
            while True:
                for ba in ba_network:
                    ba.col_left_counted = False
                    ba.col_right_counted = False
                    ba.analyzed = False
                    
                    if not (ba.col_left_fixed or ba.col_right_fixed):
                        ba.count_left()
                        ba.count_right()
                        if ba.col_left_fixed or ba.col_right_fixed:
                            break
                else:
                    break
        
        return True
        
    def arrange_boxes(self, hardware_on_sides=True):
        if canvas.theme is None:
            raise CanvasThemeMissing
        
        correct_leveling = False
        while not correct_leveling:
            for box_arranger in self.box_arrangers:
                box_arranger.reset()
                
                if (hardware_on_sides
                        and box_arranger.box_type is BoxType.HARDWARE):
                    if box_arranger.port_mode & PortMode.OUTPUT:
                        box_arranger.col_left = 1
                        box_arranger.col_left_fixed = True
                    else:
                        box_arranger.col_right = -1
                        box_arranger.col_right_fixed = True
                        
            correct_leveling = self.count_column_boxes(
                hardware_on_sides=hardware_on_sides)
        
        group_ids_to_split = set[int]()
        for ba in self.box_arrangers:
            if ba.port_mode is not PortMode.BOTH:
                group_ids_to_split.add(ba.group_id)

        # join or split groups we want to join or split
        for group in canvas.group_list:
            group.gpos.set_splitted(group.group_id in group_ids_to_split)
        
        for box_arranger in self.box_arrangers:
            box_arranger.set_box()

        number_of_columns = max(
            [ba.get_needed_columns() for ba in self.box_arrangers] + [3])

        column_widths = dict[int, float]()
        columns_pos = dict[int, float]()
        columns_bottoms = dict[int, float]()
        last_col_pos = next_left_on_grid(0)

        for column in range(1, number_of_columns + 1):
            columns_bottoms[column] = 0.0

        last_top, last_bottom = 0.0, 0.0
        direction = GoTo.NONE
        previous_column: Optional[int] = None
        used_columns_in_line = set[int]()

        for ba_network in self.ba_networks:
            if len(ba_network) <= 1:
                continue

            previous_column = None
            direction = GoTo.NONE

            for ba in ba_network:
                column = ba.get_column_with_nb(number_of_columns)
                
                if previous_column is not None and direction is GoTo.NONE:
                    if column > previous_column:
                        direction = GoTo.RIGHT
                    elif column < previous_column:
                        direction = GoTo.LEFT
            
                if hardware_on_sides and column in (1, number_of_columns):
                    y_pos = columns_bottoms[column]
                    last_top = last_bottom

                elif (previous_column is not None
                        and ((direction is GoTo.RIGHT
                              and column > previous_column)
                             or (direction is GoTo.LEFT
                                 and column < previous_column))):
                    y_pos = last_top
                
                else:
                    y_pos = last_bottom
                    for col, bottom in columns_bottoms.items():
                        if col in used_columns_in_line:
                            y_pos = min(y_pos, bottom)
                    
                    used_columns_in_line.clear()
                    last_bottom = 0.0
                    direction = GoTo.NONE

                y_pos = max(y_pos, columns_bottoms[column])

                ba.column = column
                ba.y_pos = y_pos

                used_columns_in_line.add(column)

                if (not hardware_on_sides
                        or column not in (1, number_of_columns)):
                    last_top = y_pos

                bottom = (y_pos
                          + ba.box_rect.height()
                          + canvas.theme.box_spacing)
                
                columns_bottoms[column] = bottom

                if (not hardware_on_sides
                        or column not in (1, number_of_columns)):
                    last_bottom = max(bottom, last_bottom)

                previous_column = column

        for ba_network in self.ba_networks:
            if len(ba_network) != 1:
                continue

            ba = ba_network[0]
            
            if (ba.get_column_with_nb(number_of_columns)
                    in (1, number_of_columns)):
                ba.column = ba.get_column_with_nb(number_of_columns)
                ba.y_pos = columns_bottoms[ba.column]
                columns_bottoms[ba.column] += (ba.box_rect.height()
                                               + canvas.theme.box_spacing)
                continue
            
            # This is an isolated box (without connections)
            # we place it in the column with the lowest bottom value,
            # (the nearest from top)
            choosed_column = 2            
            bottom_min = min([columns_bottoms[c] for c in columns_bottoms
                              if c not in (1, number_of_columns)])
            
            for column, bottom in columns_bottoms.items():
                if column in (1, number_of_columns):
                    continue

                if bottom == bottom_min:
                    choosed_column = column
                    break
            
            ba.column = choosed_column
            ba.y_pos = bottom_min

            columns_bottoms[ba.column] += (ba.box_rect.height()
                                           + canvas.theme.box_spacing)

        max_hardware = 0
        max_middle = 0

        for column in range(1, number_of_columns + 1):
            column_widths[column] = 0.0

        for ba in self.box_arrangers:
            column_width = column_widths.get(ba.column)
            if column_width is None:
                column_width = 0.0
            column_widths[ba.column] = max(
                ba.box_rect.width(), column_width)

        for column in range(1, number_of_columns + 1):
            columns_pos[column] = last_col_pos
            last_col_pos = next_left_on_grid(
                last_col_pos + int(column_widths[column]) + 80)

        for column, bottom in columns_bottoms.items():
            if column in (1, number_of_columns):
                max_hardware = max(max_hardware, bottom)
            else:
                max_middle = max(max_middle, bottom)

        for ba in self.box_arrangers:
            if not hardware_on_sides:
                y_offset = 0
            elif ba.column in (1, number_of_columns):
                y_offset = (columns_bottoms[ba.column] - max_hardware) / 2
            else:
                y_offset = (max_hardware - max_middle) / 2

            if ba.get_box_align() is BoxAlign.CENTER:
                x_pos = (columns_pos[ba.column]
                         + (column_widths[ba.column]
                            - ba.box_rect.width()) / 2)
            elif ba.get_box_align() is BoxAlign.RIGHT:
                x_pos = (columns_pos[ba.column]
                         + column_widths[ba.column]
                         - ba.box_rect.width())
            else:
                x_pos = columns_pos[ba.column] 

            xy = (int(x_pos), int(ba.y_pos - ba.box_rect.top() + y_offset))
            grid_xy = nearest_on_grid(xy)

            group = canvas.get_group(ba.group_id)
            if group is not None:
                group.gpos.boxes[ba.port_mode].pos = grid_xy
                move_group_boxes(group.group_id, group.gpos)


def arrange_follow_signal():
    arranger = CanvasArranger()
    arranger.arrange_boxes()

def arrange_face_to_face():
    if canvas.theme is None:
        raise CanvasThemeMissing
    
    # split all groups
    while True:
        for group in canvas.group_list:
            if not group.splitted:
                split_group(group.group_id)
                break
        else:
            break
    
    max_out_width = 0
    X_SPACING = 300
    
    gp_gposes = dict[int, GroupPos]()
    
    for group in canvas.group_list:
        for box in group.widgets:
            if not box.isVisible():
                continue
            
            gpos = gp_gposes.get(group.group_id)
            if gpos is None:
                gpos = group.gpos
                gpos.set_splitted(True)
                gp_gposes[group.group_id] = gpos
                
            box_pos = gpos.boxes[box.get_port_mode()]
            layout_mode = BoxLayoutMode.LARGE
            wrapped = False
            
            high_layout = box.get_layout(BoxLayoutMode.HIGH)
            
            # decide if box should be wrapped with its height
            if high_layout.needed_height - high_layout.header_height >= 64:
                layout_mode = BoxLayoutMode.HIGH
                wrapped = True
                
            box_pos.set_wrapped(wrapped)
            box_pos.layout_mode = layout_mode
            
            if box.get_port_mode() is PortMode.OUTPUT:
                layout = box.get_layout(layout_mode=layout_mode)
                if wrapped:
                    max_out_width = max(
                        max_out_width, layout.wrapped_width)
                else:
                    max_out_width = max(
                        max_out_width, layout.full_width)
    
    out_most_left = next_left_on_grid(0)
    out_right = out_most_left + max_out_width
    in_left = next_left_on_grid(out_right + X_SPACING)
    last_out_y = next_top_on_grid(0)
    last_in_y = last_out_y
    
    group_ids = list[int]()
    for group in canvas.group_list:
        group_ids.append(group.group_id)
    group_ids.sort()
    
    for group_id in group_ids:
        group = canvas.get_group(group_id)
        if group is None:
            continue

        for box in group.widgets:
            if not box.isVisible():
                continue

            box_pos = group.gpos.boxes.get(box.get_port_mode())
            if box_pos is None:
                continue

            layout = box.get_layout(box_pos.layout_mode)
            if box_pos.is_wrapped():
                width = layout.full_wrapped_width
                height = layout.full_wrapped_height
            else:
                width = layout.full_width
                height = layout.full_height
            
            if box.get_port_mode() is PortMode.OUTPUT:
                to_x = int(out_right - width)
                to_y = next_top_on_grid(last_out_y)
                last_out_y += height + canvas.theme.box_spacing
            
            else:
                to_x = in_left
                to_y = next_top_on_grid(last_in_y)
                last_in_y += height + canvas.theme.box_spacing
            
            box_pos.pos = (to_x, to_y)
            
    for group_id, gpos in gp_gposes.items():
        move_group_boxes(group_id, gpos)

    repulse_all_boxes()