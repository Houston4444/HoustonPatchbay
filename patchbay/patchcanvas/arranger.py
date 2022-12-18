import logging
import time

from .init_values import PortMode, GroupObject, canvas, BoxType
from .box_widget import BoxWidget

_logger = logging.getLogger(__name__)


class BoxArranger:
    group_id: int
    hardware: bool
    port_mode: PortMode
    conns_in_group_ids: set[int]
    conns_out_group_ids: set[int]
    box: BoxWidget
    level: int

    def __init__(self, arranger: 'CanvasArranger',
                 group: GroupObject, port_mode: PortMode):
        self.arranger = arranger
        self.box: BoxWidget = None
        
        # we don't take the group here
        # because it can be splitted during the BoxArranger life
        self.group_id = group.group_id
        self.box_type = group.box_type
        self.group_name = group.group_name
        self.port_mode = port_mode

        self.conns_in_group_ids = set[int]()
        self.conns_out_group_ids = set[int]()
        self.level = 0
        self.col_left = 2 # is mininum if not fixed
        self.col_right = -2 # is maximum if not fixed
        self.col_left_fixed = False
        self.col_right_fixed = False
        self.col_left_counted = False
        self.col_right_counted = False
        self.analyzed = False
        
        self.ins_connected_to = list[BoxArranger]()
        self.outs_connected_to = list[BoxArranger]()
        
        self.y_pos = 0.0
        self.column = 0

    def __repr__(self) -> str:
        return f"BoxArranger({self.group_name}, {self.port_mode.name})"
    
    def set_box(self):
        group = canvas.get_group(self.group_id)
        if self.port_mode in (PortMode.OUTPUT, PortMode.BOTH):
            self.box = group.widgets[0]
        else:
            self.box = group.widgets[1]
            
        if self.box is None:
            _logger.error(f"{self} did not found its box !")
    
    def is_owner(self, group_id: int, port_mode: PortMode):
        return bool(self.group_id == group_id
                    and self.port_mode & port_mode)
    
    def set_next_boxes(self, box_arrangers: list['BoxArranger']):
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
        
        if 'Invada' in self.group_name:
            print('JJ', self, self.col_left, self.col_left_counted, self.col_left_fixed)
        
        for ba in self.ins_connected_to:
            if 'Invada' in self.group_name:
                print('JA', ba, ba.col_left, ba.col_left_fixed, ba.col_left_counted)
            ba.count_left(path)
            if 'Invada' in self.group_name:
                print('JB', ba, ba.col_left, ba.col_left_fixed, ba.col_left_counted)
        
        if 'Invada' in self.group_name:
            print('JK', self, self.col_left, self.col_left_counted, self.col_left_fixed)
        
        left_min = self.col_left
        fixed = 0

        for ba in self.ins_connected_to:
            left_min = max(left_min, ba.col_left + 1)
            if ba.col_left_fixed:
                fixed += 1
            if 'Invada' in self.group_name:
                print('JX', ba, ba.col_left, ba.col_left_fixed, ba.col_left_counted)
        self.col_left = left_min
        if fixed and fixed == len(self.ins_connected_to):
            self.col_left_fixed = True
        
        if 'Invada' in self.group_name:
            print('JL', self, self.col_left, self.col_left_counted, self.col_left_fixed, fixed)
        
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
            self.col_right_fixed = True

        self.col_right_counted = True
    
    def get_needed_columns(self) -> int:
        print('needs cols:', self, self.col_left - self.col_right -1)
        print('___', f"[{self.col_left}:{self.col_right}] [{self.col_left_fixed}:{self.col_right_fixed}]")
        return self.col_left - self.col_right - 1
    
    def get_level(self, n_columns: int) -> int:
        if self.col_left_fixed:
            return self.col_left
        
        if self.col_right_fixed:
            return n_columns + self.col_right + 1
        
        return self.col_left

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
        self.box_arrangers = list[BoxArranger]()
        self.ba_networks = list[list[BoxArranger]]()

        # is set only in case there are looping connections
        # around this box arranger.
        self.ba_to_split: BoxArranger = None

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
            box_arranger.set_next_boxes(self.box_arrangers)

    def conn_loop_error(self) -> bool:
        if self.ba_to_split is None:
            return False

        group = canvas.get_group(self.ba_to_split.group_id)
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

    def set_all_levels(self) -> bool:
        self.ba_to_split = None
        self.ba_networks.clear()
        
        print('____==CUSTOM')
        for box_arranger in self.box_arrangers:
            if (box_arranger.col_left == 1
                    and box_arranger.col_left_fixed
                    and not box_arranger.analyzed):
                ba_network = list[BoxArranger]()
                box_arranger.parse_all(ba_network)

                print('CHOOOPP')
                for ba in ba_network:
                    print('YAA', ba, ba.col_left, ba.col_left_fixed, ba.col_right, ba.col_right_fixed)
                    if ba.group_name == '0/Surround Level 3':
                        print('dd', ba, ba.outs_connected_to)

                if self.conn_loop_error():
                    return False

                self.ba_networks.append(ba_network)
        
        for box_arranger in self.box_arrangers:
            if (box_arranger.col_right == -1
                    and box_arranger.col_right_fixed
                    and not box_arranger.analyzed):
                ba_network = list[BoxArranger]()
                box_arranger.parse_all(ba_network)
                
                if self.conn_loop_error():
                    return False
                
                print('KOPPPZ')
                for ba in ba_network:
                    print('YBB', ba, ba.col_left, ba.col_left_fixed, ba.col_right, ba.col_right_fixed)
                
                self.ba_networks.append(ba_network)

        for box_arranger in self.box_arrangers:
            if box_arranger.analyzed:
                continue
            
            ba_network = list[BoxArranger]()
            box_arranger.parse_all(ba_network)
            
            if self.conn_loop_error():
                return False

            print('POOAAS')
            for ba in ba_network:
                print('YCC', ba, ba.col_left, ba.col_left_fixed, ba.col_right, ba.col_right_fixed)
            
            self.ba_networks.append(ba_network)
            
        n_columns = 2
        for ba in self.box_arrangers:
            n_columns = max(n_columns, ba.col_left - ba.col_right -1)
        
        print('NEEDDED COLS1', n_columns)
        
        for ba in self.box_arrangers:
            if ba.col_left - ba.col_right - 1 == n_columns:
                ba.col_left_fixed = True
                ba.col_right_fixed = True
        
        # for ba in self.box_arrangers:
        #     if not (ba.col_left_fixed or ba.col_right_fixed):
        #         for ba_in in ba.ins_connected_to:
        #             if ba_in.col_left_fixed:
        #                 ba.col_left_fixed = True
        #                 ba.col_right = ba.col_left - n_columns - 1
        #                 break
        #         else:
        #             for ba_out in ba.outs_connected_to:
        #                 if ba_out.col_right_fixed:
        #                     ba.col_left = n_columns + ba.col_right + 1
        #                     ba.col_right_fixed = True
        #                     break

        needed_columns = max(
            [ba.get_needed_columns() for ba in self.box_arrangers] + [3])
        
        print('NEEDED COLUMNS :', needed_columns)

        for ba_network in self.ba_networks:
            while True:
                for ba in ba_network:
                    ba.col_left_counted = False
                    ba.col_right_counted = False
                    ba.analyzed = False
                    
                    if not (ba.col_left_fixed or ba.col_right_fixed):
                        print('try it', ba, ba.col_left, ba.col_right)
                        ba.count_left()
                        ba.count_right()
                        print('joozzz', ba, ba.col_left, ba.col_right)
                        if ba.col_left_fixed or ba.col_right_fixed:
                            break
                else:
                    break

        for ba in self.box_arrangers:
            if ba.col_left_fixed:
                ba.level = ba.col_left
            elif ba.col_right_fixed:
                ba.level = n_columns + 1 + ba.col_right
            else:
                ba.level = ba.col_left
        
        return True
    
    def get_group_ids_to_split(self) -> set[int]:
        group_ids = set[int]()
        
        for ba in self.box_arrangers:
            if ba.port_mode is not PortMode.BOTH:
                group_ids.add(ba.group_id)
        
        return group_ids