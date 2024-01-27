#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# PatchBay Canvas engine using QGraphicsView/Scene
# Copyright (C) 2010-2019 Filipe Coelho <falktx@falktx.com>
# Copyright (C) 2019-2022 Mathieu Picot <picotmathieu@gmail.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of
# the License, or any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# For a full copy of the GNU General Public License see the doc/GPL.txt file.

from dataclasses import dataclass
from typing import Optional, Union
from PyQt5.QtCore import QRectF, QMarginsF, Qt, QPointF
from PyQt5.QtWidgets import QGraphicsView

from .init_values import (
    canvas,
    options,
    PortMode,
    Direction)
from .utils import (previous_left_on_grid, next_left_on_grid,
                    previous_top_on_grid, next_top_on_grid)

from .scene_moth import MovingBox, PatchSceneMoth
from .box_widget import BoxWidget


@dataclass
class BoxAndRect:
    rect: QRectF
    item: BoxWidget
    
        
@dataclass
class ToMoveBox:
    directions: list[Direction]
    item: BoxWidget
    rect: QRectF
    repulser: BoxAndRect
        
    def __lt__(self, other: 'ToMoveBox'):
        if self.directions != other.directions:
            return self.directions < other.directions
        
        # should not happen
        if not self.directions:
            return True
        
        last_direc = self.directions[-1]
        if last_direc is Direction.LEFT:
            return self.rect.right() > other.rect.right()
        if last_direc is Direction.UP:
            return self.rect.bottom() > other.rect.bottom()
        if last_direc is Direction.RIGHT:
            return self.rect.left() < other.rect.left()
        if last_direc is Direction.DOWN:
            return self.rect.top() < other.rect.top()
        
        # should not happen
        return True
    

class PatchScene(PatchSceneMoth):
    '''This class part of the scene is for repulsive boxes option
       because the algorythm is not simple and takes a lot of lines.
       See scene_moth.py for others scene methods.'''
    def __init__(self, view: QGraphicsView):
        PatchSceneMoth.__init__(self, view)
        self._full_repulse_boxes = set[BoxWidget]()

    def deplace_boxes_from_repulsers(self, repulser_boxes: list[BoxWidget],
                                     wanted_direction=Direction.NONE,
                                     mov_repulsables: Optional[list[MovingBox]]=None):
        ''' This function change the place of boxes in order to have no box overlapping
            other boxes.'''
        def get_direction(fixed_rect: QRectF, moving_rect: QRectF,
                          parent_directions=list[Direction]()) -> Direction:
            if (moving_rect.top() <= fixed_rect.center().y() <= moving_rect.bottom()
                    or fixed_rect.top() <= moving_rect.center().y() <= fixed_rect.bottom()):
                if (fixed_rect.right() < moving_rect.center().x()
                        and fixed_rect.center().x() < moving_rect.left()):
                    if Direction.LEFT in parent_directions:
                        return Direction.LEFT
                    return Direction.RIGHT
                
                if (fixed_rect.left() > moving_rect.center().x()
                        and fixed_rect.center().x() > moving_rect.right()):
                    if Direction.RIGHT in parent_directions:
                        return Direction.RIGHT
                    return Direction.LEFT
            
            if fixed_rect.center().y() <= moving_rect.center().y():
                if Direction.UP in parent_directions:
                    return Direction.UP
                return Direction.DOWN
            
            if Direction.DOWN in parent_directions:
                return Direction.DOWN
            return Direction.UP
        
        def repulse(direction: Direction,
                    fixed: Union[BoxWidget, QRectF],
                    moving: Union[BoxWidget, QRectF],
                    fixed_port_mode: PortMode,
                    moving_port_mode: PortMode) -> QRectF:
            '''returns a QRectF to be placed at side of fixed_rect
               where fixed_rect is an already determinated futur place
               for a box'''
                
            if isinstance(fixed, BoxWidget):
                fixed_rect = fixed.boundingRect().translated(fixed.pos())
            else:
                fixed_rect = fixed
            
            if isinstance(moving, BoxWidget):
                rect = moving.boundingRect().translated(moving.pos())
            else:
                rect = moving
            
            x = rect.left()
            y = rect.top()
            
            spacing = canvas.theme.box_spacing
            spacing_hor = canvas.theme.box_spacing_horizontal
            
            if direction in (Direction.LEFT, Direction.RIGHT):
                if direction is Direction.LEFT:
                    if (fixed_port_mode & PortMode.INPUT
                            or moving_port_mode & PortMode.OUTPUT):
                        x = previous_left_on_grid(
                            fixed_rect.left() - rect.width() - spacing_hor)
                    else: 
                        x = previous_left_on_grid(
                            fixed_rect.left() - rect.width() - spacing)
                else:
                    if (fixed_port_mode & PortMode.OUTPUT
                            or moving_port_mode & PortMode.INPUT):
                        x = next_left_on_grid(fixed_rect.right() + spacing_hor)
                    else:
                        x = next_left_on_grid(fixed_rect.right() + spacing)

                top_diff = abs(fixed_rect.top() - rect.top())
                bottom_diff = abs(fixed_rect.bottom() - rect.bottom())

                if bottom_diff > top_diff and top_diff <= magnet:
                    y = fixed_rect.top()
                elif bottom_diff <= magnet:
                    y = fixed_rect.bottom() - rect.height()

            elif direction in (Direction.UP, Direction.DOWN):
                if direction is Direction.UP:
                    y = previous_top_on_grid(
                        fixed_rect.top() - rect.height() - spacing)
                else:
                    y = next_top_on_grid(fixed_rect.bottom() + spacing)

                left_diff = abs(fixed_rect.left() - rect.left())
                right_diff = abs(fixed_rect.right() - rect.right())
                
                if right_diff > left_diff and left_diff <= magnet:
                    x = fixed_rect.left()
                elif right_diff <= magnet:
                    x = fixed_rect.right() - rect.width()

            return QRectF(float(x), float(y), rect.width(), rect.height())

        def rect_has_to_move_from(
                repulser_rect: QRectF, rect: QRectF,
                repulser_port_mode: PortMode, rect_port_mode: PortMode) -> bool:
            left_spacing = right_spacing = box_spacing
            
            if (repulser_port_mode & PortMode.INPUT
                    or rect_port_mode & PortMode.OUTPUT):
                left_spacing = box_spacing_hor
            
            if (repulser_port_mode & PortMode.OUTPUT
                    or rect_port_mode & PortMode.INPUT):
                right_spacing = box_spacing_hor
            
            large_repulser_rect = repulser_rect.adjusted(
                - left_spacing, - box_spacing,
                right_spacing, box_spacing)

            return rect.intersects(large_repulser_rect)

        # ---      ---       ---
        # --- function start ---
        if not options.prevent_overlap:
            return
        
        box_spacing = canvas.theme.box_spacing
        box_spacing_hor = canvas.theme.box_spacing_horizontal
        magnet = canvas.theme.magnet

        to_move_boxes = list[ToMoveBox]()
        repulsers = list[BoxAndRect]()
        wanted_directions = [wanted_direction]
        
        for box in repulser_boxes:
            self._full_repulse_boxes.add(box)

            if mov_repulsables is not None:
                # in view change the moving box for this box
                # is the first of the list (optimisation).
                # there is only one repulser
                srect = mov_repulsables[0].final_rect
            else:
                # if box is already moving, consider its end position
                for moving_box in self.move_boxes:
                    if moving_box.widget is box:
                        if moving_box.final_rect.isNull():
                            # if this box is joining or hidding,
                            # it will be removed soon
                            # so, it has not to be a repulser.
                            return
                        srect = moving_box.final_rect
                        break
                else:
                    srect = box.after_wrap_rect().translated(box.pos())

            repulser = BoxAndRect(srect, box)
            repulsers.append(repulser)
            items_to_move = list[BoxAndRect]()

            search_rect = srect.marginsAdded(
                QMarginsF(canvas.theme.box_spacing_horizontal,
                          canvas.theme.box_spacing, 
                          canvas.theme.box_spacing_horizontal,
                          canvas.theme.box_spacing))

            if mov_repulsables is not None:
                for moving_box in mov_repulsables:
                    if (moving_box.widget in repulser_boxes
                            or moving_box.widget in [b.item for b in to_move_boxes]):
                        continue
                    
                    widget = moving_box.widget
                    irect = moving_box.final_rect
                    
                    if rect_has_to_move_from(
                            repulser.rect, irect,
                            repulser.item.get_current_port_mode(),
                            widget.get_current_port_mode()):
                        items_to_move.append(BoxAndRect(irect, widget))
            else:
                # search intersections in non moving boxes
                for widget in self.items(search_rect, Qt.IntersectsItemShape,
                                        Qt.AscendingOrder):
                    if not isinstance(widget, BoxWidget):
                        continue
                    
                    if (widget in repulser_boxes
                            or widget in [b.item for b in to_move_boxes]
                            or widget in [b.widget for b in self.move_boxes]):
                        continue

                    irect = widget.sceneBoundingRect()

                    if rect_has_to_move_from(
                            repulser.rect, irect,
                            repulser.item.get_current_port_mode(),
                            widget.get_current_port_mode()):
                        items_to_move.append(BoxAndRect(irect, widget))

                # search intersections in moving boxes
                for moving_box in self.move_boxes:
                    if (moving_box.widget in repulser_boxes
                            or moving_box.final_rect.isNull()
                            or moving_box.widget in [b.item for b in to_move_boxes]):
                        continue

                    widget = moving_box.widget
                    irect = moving_box.final_rect
                    
                    if rect_has_to_move_from(
                            repulser.rect, irect,
                            repulser.item.get_current_port_mode(),
                            widget.get_current_port_mode()):
                        items_to_move.append(BoxAndRect(irect, widget))
            
            for item_to_move in items_to_move:
                item = item_to_move.item
                irect = item_to_move.rect

                # evaluate in which direction should go the box
                direction = get_direction(srect, irect, wanted_directions)
                to_move_boxes.append(ToMoveBox([direction], item, irect, repulser))

        to_move_boxes.sort()

        # !!! to_move_boxes list is dynamic
        # elements can be added to the list while iteration !!!
        for to_move_box in to_move_boxes:
            item, irect, repulser = \
                to_move_box.item, to_move_box.rect, to_move_box.repulser
            # item, repulser = to_move_box.item, to_move_box.repulser
            
            # irect = item.boundingRect().translated(item.pos())

            directions = to_move_box.directions.copy()
            new_direction = get_direction(repulser.rect, irect, directions)
            directions.append(new_direction)

            # calculate the new position of the box repulsed by its repulser
            new_rect = repulse(new_direction, repulser.rect, irect,
                               repulser.item.get_current_port_mode(),
                               item.get_current_port_mode())
            
            active_repulsers = list[BoxAndRect]()
            
            # while there is a repulser rect at new box position
            # move the future box position
            while True:
                # list just here to prevent infinite loop
                # we save the repulsers that already have moved the rect
                for repulser in repulsers:
                    if rect_has_to_move_from(
                            repulser.rect, new_rect,
                            repulser.item.get_current_port_mode(),
                            item.get_current_port_mode()):

                        if repulser in active_repulsers:
                            continue
                        active_repulsers.append(repulser)
                        
                        new_direction = get_direction(
                            repulser.rect, new_rect, directions)
                        new_rect = repulse(
                            new_direction, repulser.rect, new_rect,
                            repulser.item._current_port_mode,
                            item._current_port_mode)
                        directions.append(new_direction)
                        break
                else:
                    break

            # Now we know where the box will be definitely positioned
            # So, this is now a repulser for other boxes
            repulser = BoxAndRect(new_rect, item)
            repulsers.append(repulser)
            self._full_repulse_boxes.add(item)
            
            # check which existing boxes exists at the new place of the box
            # and add them to this to_move_boxes iteration
            adding_list = list[ToMoveBox]()

            if mov_repulsables is not None:
                for moving_box in mov_repulsables:
                    mitem = moving_box.widget
                    
                    if (mitem in [r.item for r in repulsers]
                            or mitem in [b.item for b in to_move_boxes]):
                        continue
                    
                    if rect_has_to_move_from(
                            new_rect, moving_box.final_rect,
                            to_move_box.item.get_current_port_mode(),
                            mitem.get_current_port_mode()):
                        adding_list.append(
                            ToMoveBox(directions, moving_box.widget,
                                      moving_box.final_rect, repulser))
            else:
                search_rect = new_rect.marginsAdded(
                    QMarginsF(canvas.theme.box_spacing_horizontal,
                            canvas.theme.box_spacing, 
                            canvas.theme.box_spacing_horizontal,
                            canvas.theme.box_spacing))
                
                for widget in self.items(search_rect):
                    if not isinstance(widget, BoxWidget):
                        continue
                    if (widget in [r.item for r in repulsers]
                            or widget in [b.item for b in to_move_boxes]
                            or widget in [b.widget for b in self.move_boxes]):
                        continue
                    
                    mirect = widget.sceneBoundingRect()
                    if rect_has_to_move_from(
                            new_rect, mirect,
                            to_move_box.item.get_current_port_mode(),
                            widget.get_current_port_mode()):
                        adding_list.append(
                            ToMoveBox(directions, widget, mirect, repulser))                        
                
                for moving_box in self.move_boxes:
                    mitem = moving_box.widget
                    
                    if (mitem in [r.item for r in repulsers]
                            or moving_box.final_rect.isNull()
                            or mitem in [b.item for b in to_move_boxes]):
                        continue
                    
                    if rect_has_to_move_from(
                            new_rect, moving_box.final_rect,
                            to_move_box.item.get_current_port_mode(),
                            mitem.get_current_port_mode()):

                        adding_list.append(
                            ToMoveBox(directions, moving_box.widget,
                                      moving_box.final_rect, repulser))

            adding_list.sort()

            for to_move_box in adding_list:
                to_move_boxes.append(to_move_box)

            # now we decide where the box is moved
            self.add_box_to_animation(
                item, int(new_rect.left()), int(new_rect.top()))

    def full_repulse(self, view_change=False):
        if not options.prevent_overlap:
            return
        
        self._full_repulse_boxes.clear()
        if view_change:
            moving_boxes = [b for b in self.move_boxes
                            if (not b.final_rect.isNull()
                                and b.widget.isVisible()
                                and not b in self.hidding_boxes)]

            while moving_boxes:
                self.deplace_boxes_from_repulsers(
                    [moving_boxes[0].widget],
                    mov_repulsables=moving_boxes)
                to_rm_movboxes = [mb for mb in moving_boxes
                                  if mb.widget in self._full_repulse_boxes]
                for to_rm_mb in to_rm_movboxes:
                    moving_boxes.remove(to_rm_mb)
        else:
            for box in canvas.list_boxes():
                if box not in self._full_repulse_boxes:
                    self.deplace_boxes_from_repulsers([box])
        self._full_repulse_boxes.clear()

    def bring_neighbors_at_wrap(
            self, box_widget: BoxWidget, new_scene_rect: QRectF):
        if not options.prevent_overlap:
            return
        
        neighbors = [box_widget]
        limit_top = box_widget.top_left()[1]
        box_spacing = canvas.theme.box_spacing
        
        for neighbor in neighbors:
            srect = QRectF(
                0.0, 0.0,
                neighbor.boundingRect().width(),
                neighbor.boundingRect().height())
            for moving_box in self.move_boxes:
                if moving_box.widget is neighbor:
                    srect.translate(moving_box.to_pt)
                    break
            else:
                srect.translate(QPointF(*neighbor.top_left()))

            for item in self.items(
                    srect.adjusted(0, 0, 0,
                                   box_spacing + 1)):
                if item not in neighbors and isinstance(item, BoxWidget):
                    nrect = item.boundingRect().translated(item.pos())
                    if nrect.top() >= limit_top:
                        neighbors.append(item)
        
        neighbors.remove(box_widget)
        
        less_y = box_widget.boundingRect().height() - new_scene_rect.height()

        repulser_boxes = list[BoxWidget]()

        for neighbor in neighbors:
            x, y = neighbor.top_left()           
            self.add_box_to_animation(neighbor, x, int(y - less_y))
            repulser_boxes.append(neighbor)
        repulser_boxes.append(box_widget)
        
        self.deplace_boxes_from_repulsers(
            repulser_boxes, wanted_direction=Direction.UP)
        
    def bring_neighbors_after_layout_change(
            self, box_widget: BoxWidget, ex_rect: QRectF):
        if not options.prevent_overlap:
            return
        
        neighbors = [box_widget]
        limit_top = box_widget.pos().y()
        box_spacing = canvas.theme.box_spacing

        for neighbor in neighbors:
            if neighbor is box_widget:
                srect = ex_rect
            else:
                for moving_box in self.move_boxes:
                    if (moving_box.widget is neighbor
                            and not moving_box.final_rect.isNull()):
                        srect = moving_box.final_rect
                        srect.translate(moving_box.to_pt)
                        break
                else:
                    srect = neighbor.after_wrap_rect()
                    srect.translate(neighbor.pos())

            for item in self.items(
                    srect.adjusted(0, 0, 0,
                                   box_spacing + 1)):
                if item not in neighbors and isinstance(item, BoxWidget):
                    nrect = item.after_wrap_rect().translated(item.pos())
                    if nrect.top() >= limit_top:
                        neighbors.append(item)
        
        neighbors.remove(box_widget)
        
        less_y = ex_rect.height() - box_widget.after_wrap_rect().height() 

        repulser_boxes = list[BoxWidget]()

        for neighbor in neighbors:
            x, y = neighbor.top_left()           
            self.add_box_to_animation(neighbor, x, int(y - less_y))
            repulser_boxes.append(neighbor)
        repulser_boxes.append(box_widget)
        
        if less_y >= 0.0:
            self.deplace_boxes_from_repulsers(
                repulser_boxes, wanted_direction=Direction.UP)
        else:
            self.deplace_boxes_from_repulsers(
                repulser_boxes, wanted_direction=Direction.DOWN)