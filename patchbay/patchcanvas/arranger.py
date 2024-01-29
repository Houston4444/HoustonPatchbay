from enum import IntEnum
import logging
import math
from typing import Optional
from PyQt5.QtCore import QRectF

from .init_values import (
    BoxLayoutMode,
    BoxPos,
    PortMode,
    GroupObject,
    canvas,
    BoxType,
    Joining,
    options)
from .utils import nearest_on_grid, next_left_on_grid, next_top_on_grid
from .box_widget import BoxWidget
from .patchcanvas import animate_before_join, move_group_boxes, split_group

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
        self.box: BoxWidget = None
        self.box_rect = QRectF()
        
        # we don't take the group here
        # because it can be splitted during the BoxArranger life
        self.group_id = group.group_id
        self.box_type = group.box_type
        self.group_name = group.group_name
        self.port_mode = port_mode
        self.joining = False

        # connected group ids will be stocked here
        self.conns_in_group_ids = set[int]()
        self.conns_out_group_ids = set[int]()
        
        # self.set_neighbours() function will fill theses attributes
        # with connected group ids
        self.ins_connected_to = list[BoxArranger]()
        self.outs_connected_to = list[BoxArranger]()

        # col_left is mininum column number,
        # it must be a positiv integer and can only grow
        # if col_left_fixed is True, col_left becomes the column number
        self.col_left = 2 
        self.col_left_fixed = False
        self.col_left_counted = False

        # col_right is maximum column number, starting from the end.
        # it must be a negativ integer and can only decrease.
        # if col_right_fixed is True, col_right becomes the column number
        # in regard to the given number of columns        
        self.col_right = -2
        self.col_right_fixed = False
        self.col_right_counted = False

        self.analyzed = False
        
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
        if group.splitted:
            if self.port_mode is PortMode.OUTPUT:
                self.box = group.widgets[0]
                self.box_rect = self.box.after_wrap_rect()
            elif self.port_mode is PortMode.INPUT:
                self.box = group.widgets[1]
                self.box_rect = self.box.after_wrap_rect()
            elif self.port_mode is PortMode.BOTH:
                box = BoxWidget(group, PortMode.BOTH)
                self.box_rect = box.get_dummy_rect()
                canvas.scene.remove_box(box)
                self.joining = True
        else:
            if self.port_mode is PortMode.BOTH:
                self.box = group.widgets[0]
                self.box_rect = self.box.after_wrap_rect()
            else:
                _logger.error(f'{self} says that group should be splitted')
    
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
        fixed_ins_len = 0

        for ba in self.ins_connected_to:
            left_min = max(left_min, ba.col_left + 1)
            if ba.col_left_fixed:
                fixed_ins_len += 1

        self.col_left = left_min

        if fixed_ins_len and fixed_ins_len == len(self.ins_connected_to):
            # if all ins connected have col_left_fixed
            # we can assume this BoxArranger has now col_left_fixed
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
        fixed_outs_len = 0
        
        for ba in self.outs_connected_to:
            right_min = min(right_min, ba.col_right - 1)
            if ba.col_right_fixed:
                fixed_outs_len += 1
        
        self.col_right = right_min
        if fixed_outs_len and fixed_outs_len == len(self.outs_connected_to):
            # if all outs connected have col_right_fixed
            # we can assume this BoxArranger has now col_right_fixed
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
            return BoxAlign.CENTER
        if self.outs_connected_to:
            return BoxAlign.RIGHT
        if self.ins_connected_to:
            return BoxAlign.LEFT
        return BoxAlign.CENTER

    def reset(self):
        self.col_left = 2
        self.col_left_counted = False
        self.col_left_fixed = False
        self.col_right = -2
        self.col_right_counted = False
        self.col_right_fixed = False
        self.analyzed = False


class CanvasArranger:
    def __init__(self):
        # Each box will have a BoxArranger stocked in self.box_arrangers
        self.box_arrangers = list[BoxArranger]()
        
        # A BoxArranger network (ba_network) is a list[BoxArranger]
        # where there is a way to go from any of one to any other
        # parsing the connections.
        # all BoxArranger networks will be stocked in self.ba_networks
        self.ba_networks = list[list[BoxArranger]]()

        # used only to sort BoxArranger lists
        self.sort_context = PortMode.BOTH

        # self.ba_to_split is set only in case there are looping
        # connections around this box arranger.
        # Then we will have to restart the analyze
        # saying this box is splitted.
        self.ba_to_split: BoxArranger = None

        # in a first time, we know that we want the boxes with direct
        # connections from output to its input (looping) splitted,
        # and splitted hardware boxes.
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

        # fill in each BoxArranger the opposite BoxArrangers
        # of its connections.
        for conn in canvas.list_connections():
            for box_arranger in self.box_arrangers:
                if box_arranger.is_owner(conn.group_out_id, PortMode.OUTPUT):
                    box_arranger.conns_in_group_ids.add(conn.group_in_id)
                if box_arranger.is_owner(conn.group_in_id, PortMode.INPUT):
                    box_arranger.conns_out_group_ids.add(conn.group_out_id)
    
        for box_arranger in self.box_arrangers:
            box_arranger.set_neighbours(self.box_arrangers)
        
        # sort all BoxArranger lists in all BoxArrangers
        self.sort_context = PortMode.INPUT
        for box_arranger in self.box_arrangers:
            box_arranger.outs_connected_to.sort()
            
        self.sort_context = PortMode.OUTPUT
        for box_arranger in self.box_arrangers:
            box_arranger.ins_connected_to.sort()

    def _needs_to_split_a_box(self) -> bool:
        '''return True and operate the changes
           if we need to split a box because of looping connections.'''
        if self.ba_to_split is None:
            return False

        group = canvas.get_group(self.ba_to_split.group_id)

        # split the BoxArranger in two, creating one INPUT BoxArranger
        # and setting this one to OUTPUT
        new_ba = BoxArranger(self, group, PortMode.INPUT)
        new_ba.ins_connected_to = self.ba_to_split.ins_connected_to
        
        for ba in self.ba_to_split.ins_connected_to:
            ba.outs_connected_to.remove(self.ba_to_split)
            ba.outs_connected_to.append(new_ba)

        self.ba_to_split.ins_connected_to = []
        self.ba_to_split.port_mode = PortMode.OUTPUT
        
        self.box_arrangers.append(new_ba)

        # consider there is no more BoxArranger to split,
        # analyze will be done again.
        self.ba_to_split = None

        # reset the columns count for all BoxArrangers
        for ba in self.box_arrangers:
            ba.reset()

        return True

    def _define_all_box_columns(self, hardware_on_sides=False) -> bool:
        '''define the column possibilities for every BoxArranger
           return False in case of looping connections.'''
        self.ba_to_split = None
        self.ba_networks.clear()
        
        if hardware_on_sides:
            # define networks starting from a hardware OUTPUT BoxArranger
            for box_arranger in self.box_arrangers:
                if (box_arranger.col_left == 1
                        and box_arranger.col_left_fixed
                        and not box_arranger.analyzed):
                    ba_network = list[BoxArranger]()
                    box_arranger.parse_all(ba_network)

                    if self._needs_to_split_a_box():
                        return False

                    self.ba_networks.append(ba_network)

            # define undefined networks starting from 
            # a hardware INPUT BoxArranger
            for box_arranger in self.box_arrangers:
                if (box_arranger.col_right == -1
                        and box_arranger.col_right_fixed
                        and not box_arranger.analyzed):
                    ba_network = list[BoxArranger]()
                    box_arranger.parse_all(ba_network)

                    if self._needs_to_split_a_box():
                        return False

                    self.ba_networks.append(ba_network)

        # define all other networks, 
        # or all networks if hardware_on_sides is False.
        for box_arranger in self.box_arrangers:
            if box_arranger.analyzed:
                continue
            
            ba_network = list[BoxArranger]()
            box_arranger.parse_all(ba_network)
            
            if self._needs_to_split_a_box():
                return False
            
            self.ba_networks.append(ba_network)
        
        # count the needed number of columns
        n_columns = max(
            [ba.get_needed_columns() for ba in self.box_arrangers] + [3])
        
        # fix the column for BoxArranger when it needs as much columns
        # as the number of columns
        for ba in self.box_arrangers:
            if ba.get_needed_columns() == n_columns:
                ba.col_left_fixed = True
                ba.col_right_fixed = True

        # parse all BoxArrangers in all networks until all BoxArrangers
        # have col_left_fixed or col_right_fixed
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
        '''Proceed to the arrangment of all present boxes
           in the patchcanvas.
           If 'hardware_on_sides' is True,
           only hardware boxes will be located in the leftmost 
           and the rightmost columns'''
        # define all BoxArrangers columns
        graph_is_ok = False
        while not graph_is_ok:
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
            graph_is_ok = self._define_all_box_columns(
                hardware_on_sides=hardware_on_sides)
            # if 'graph_is_ok' is False, it means that we need to split
            # a box and restart analyze, 
            # because there are looping connections.
        
        # list groups to split, all others will be joined
        group_ids_to_split = set[int]()
        for ba in self.box_arrangers:
            if ba.port_mode is not PortMode.BOTH:
                group_ids_to_split.add(ba.group_id)

        group_ids_join_done = set[int]()

        # join or split groups we want to join or split
        while True:
            for group in canvas.group_list:
                if group.splitted:
                    if (group.box_type is not BoxType.HARDWARE
                            and group.group_id not in group_ids_to_split
                            and group.group_id not in group_ids_join_done):
                        animate_before_join(group.group_id)
                        group_ids_join_done.add(group.group_id)
                        break
                else:
                    if (group.box_type is BoxType.HARDWARE
                            or group.group_id in group_ids_to_split):
                        split_group(group.group_id)
                        break
            else:
                break
        
        # learn the dimensions of the box for each BoxArranger
        for box_arranger in self.box_arrangers:
            box_arranger.set_box()

        # calculate the number of needed columns
        number_of_columns = max(
            [ba.get_needed_columns() for ba in self.box_arrangers] + [3])

        columns_bottoms = dict[int, float]()
        for column in range(1, number_of_columns + 1):
            columns_bottoms[column] = 0.0

        last_top, last_bottom = 0.0, 0.0
        direction = GoTo.NONE
        used_columns_in_line = set[int]()

        # parse all networks to locate the boxes
        for ba_network in self.ba_networks:
            if len(ba_network) <= 1:
                # a network with only one box cointains a box without connections
                # we will treat it later.
                continue

            previous_column: Optional[int] = None
            direction = GoTo.NONE

            for ba in ba_network:
                # this BoxArranger has connections.
                # The network is ordered in a certain way,
                # so a BoxArranger is connected to the previous and/or
                # to the next of the network.
                # So, we check the horizontal direction of the network, and decide
                # to go to the next line if the horizontal direction changes
                
                # get the column num for this BoxArranger
                column = ba.get_column_with_nb(number_of_columns)

                # set the horizontal direction of the network parsing
                if previous_column is not None and direction is GoTo.NONE:
                    if column > previous_column:
                        direction = GoTo.RIGHT
                    elif column < previous_column:
                        direction = GoTo.LEFT

                # set the Y pos
                if hardware_on_sides and column in (1, number_of_columns):
                    y_pos = columns_bottoms[column]
                    last_top = last_bottom

                elif (previous_column is not None
                        and (direction is GoTo.RIGHT and column > previous_column)
                             or (direction is GoTo.LEFT and column < previous_column)):
                    # no direction change, align top to the previous
                    y_pos = last_top
                
                else:
                    # direction change, or first BoxArranger of the network
                    y_pos = last_bottom
                    for col, bottom in columns_bottoms.items():
                        if col in used_columns_in_line:
                            y_pos = min(y_pos, bottom)
                    
                    used_columns_in_line.clear()
                    last_bottom = 0.0
                    direction = GoTo.NONE

                # save column and y_pos in the BoxArranger
                y_pos = max(y_pos, columns_bottoms[column])

                ba.column = column
                ba.y_pos = y_pos

                # save needed vars for the next BoxArranger
                used_columns_in_line.add(column)

                if not hardware_on_sides or column not in (1, number_of_columns):
                    last_top = y_pos

                bottom = (y_pos
                          + ba.box_rect.height()
                          + canvas.theme.box_spacing)
                
                columns_bottoms[column] = bottom

                if not hardware_on_sides or column not in (1, number_of_columns):
                    last_bottom = max(bottom, last_bottom)

                previous_column = column

        # locate boxes without connections where there is some place ;)
        for ba_network in self.ba_networks:
            if len(ba_network) != 1:
                continue

            ba = ba_network[0]

            if ba.get_column_with_nb(number_of_columns) in (1, number_of_columns):
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

            columns_bottoms[ba.column] += (
                ba.box_rect.height() + canvas.theme.box_spacing)

        column_widths = dict[int, float]()
        columns_lefts = dict[int, float]()
        last_left = 0
        max_hardware = 0
        max_middle = 0
        column_spacing = (
            max(80, options.cell_width * math.ceil(80 / options.cell_width))
            + canvas.theme.box_spacing)

        # set all columns widths
        for ba in self.box_arrangers:
            column_width = column_widths.get(ba.column)
            if column_width is None:
                column_width = 0.0
            column_widths[ba.column] = max(
                ba.box_rect.width(), column_width)

        # set all columns left pos
        for column in range(1, number_of_columns + 1):
            columns_lefts[column] = last_left
            last_left += column_widths[column] + column_spacing

        # set max_hardware and max_middle
        # they will be used to align horizontally 
        # the middle to the hardware 
        for column, bottom in columns_bottoms.items():
            if column in (1, number_of_columns):
                max_hardware = max(max_hardware, bottom)
            else:
                max_middle = max(max_middle, bottom)

        # set x pos for each BoxArranger, and y compensation (see above)
        # then, move the box.
        for ba in self.box_arrangers:
            # set y_offset to align horizontally hardware contents
            # to middle contents
            if not hardware_on_sides:
                y_offset = 0
            elif ba.column in (1, number_of_columns):
                y_offset = (columns_bottoms[ba.column] - max_hardware) / 2
            else:
                y_offset = (max_hardware - max_middle) / 2

            # set x_pos in regard to column left pos and box alignment
            # in the column
            if ba.get_box_align() is BoxAlign.CENTER:
                x_pos = (columns_lefts[ba.column]
                         + (column_widths[ba.column]
                            - ba.box_rect.width()) / 2)
            elif ba.get_box_align() is BoxAlign.RIGHT:
                x_pos = (columns_lefts[ba.column]
                         + column_widths[ba.column]
                         - ba.box_rect.width())
            else:
                x_pos = columns_lefts[ba.column] 

            # choose a position on the grid
            xy = (int(x_pos), int(ba.y_pos - ba.box_rect.top() + y_offset))
            grid_xy = nearest_on_grid(xy)

            # finally, move the box
            if ba.joining:
                group = canvas.get_group(ba.group_id)
                if group is not None:
                    group.box_poses[PortMode.BOTH].pos = grid_xy
                    canvas.qobject.add_group_to_join(group.group_id)
                    canvas.scene.add_box_to_animation(
                        group.widgets[0], *grid_xy, joining=Joining.YES,
                        joined_rect=ba.box_rect)
                    canvas.scene.add_box_to_animation(
                        group.widgets[1], *grid_xy, joining=Joining.YES)
            else:    
                canvas.scene.add_box_to_animation(ba.box, *grid_xy)


def arrange_follow_signal():
    arranger = CanvasArranger()
    arranger.arrange_boxes()

def arrange_face_to_face():
    '''arrange all boxes, all boxes will be splitted and probably wrapped.
       This looks like the old known QJackCtl Patchbay style'''
    # first, split all groups
    while True:
        for group in canvas.group_list:
            if not group.splitted:
                split_group(group.group_id)
                break
        else:
            break
    
    X_SPACING = 300
    max_out_width = 0
    
    gp_box_poses = dict[int, dict[PortMode, BoxPos]]()
    
    # analyze, and stock all box properties (layout and wrapped state)
    # in gp_box_poses.
    for group in canvas.group_list:
        for box in group.widgets:
            if box is None or not box.isVisible():
                continue

            # create the BoxPos object for the box
            # and place it in gp_box_poses  
            box_poses = gp_box_poses.get(group.group_id)
            if box_poses is None:
                box_poses = dict[PortMode, BoxPos]()
                for port_mode in PortMode.in_out_both():
                    box_poses[port_mode] = BoxPos()
                gp_box_poses[group.group_id] = box_poses

            box_pos = box_poses[box.get_port_mode()]

            # choose box layout mode with the littlest wrapped height
            layout_mode = BoxLayoutMode.LARGE

            high_layout = box.get_layout(BoxLayoutMode.HIGH)
            large_layout = box.get_layout(BoxLayoutMode.LARGE)
            
            if (high_layout.full_wrapped_height
                    < large_layout.full_wrapped_height):
                layout_mode = BoxLayoutMode.HIGH

            # wrap the box if wrapped height is littler than normal height
            layout = box.get_layout(layout_mode=layout_mode)
            wrapped = bool(layout.full_height > layout.full_wrapped_height)
            
            # set box_pos properties
            box_pos.set_wrapped(wrapped)
            box_pos.layout_mode = layout_mode
            
            # get the max width for all output boxes
            if box.get_port_mode() is PortMode.OUTPUT:
                if wrapped:
                    max_out_width = max(
                        max_out_width, layout.full_wrapped_width)
                else:
                    max_out_width = max(
                        max_out_width, layout.full_width)
    
    # prepare global positions 
    out_most_left = next_left_on_grid(0)
    out_right = out_most_left + max_out_width
    in_left = next_left_on_grid(out_right + X_SPACING)
    last_out_y = next_top_on_grid(0)
    last_in_y = last_out_y
    
    # sort groups by id, to keep groups in id (apparition) order
    group_ids = list[int]()
    for group in canvas.group_list:
        group_ids.append(group.group_id)
    group_ids.sort()
    
    # set box positions in all BoxPos objects in gp_box_poses
    for group_id in group_ids:
        group = canvas.get_group(group_id)
        if group is None:
            continue

        box_poses = gp_box_poses.get(group_id)
        if box_poses is None:
            continue

        for box in group.widgets:
            if box is None or not box.isVisible():
                continue

            box_pos = box_poses.get(box.get_port_mode())
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
    
    # estimate the needed compensation to try to align horizontally
    # the outputs and the inputs
    last_out_y -= canvas.theme.box_spacing
    last_in_y -= canvas.theme.box_spacing
    more_y = (options.cell_height
              * (((last_out_y - last_in_y) // 2)
                 // options.cell_height))

    # modify all positions of the inputs to try to align horizontally
    for group_id, box_poses in gp_box_poses.items():
        box_pos = box_poses.get(PortMode.INPUT)
        if box_pos is not None:
            box_pos.pos = box_pos.pos[0], box_pos.pos[1] + more_y
    
    # Now, move all the boxes (and set them properties)
    for group_id, box_poses in gp_box_poses.items():
        move_group_boxes(group_id, box_poses, True)
