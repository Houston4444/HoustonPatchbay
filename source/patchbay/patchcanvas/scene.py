#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# PatchBay Canvas engine using QGraphicsView/Scene
# Copyright (C) 2010-2019 Filipe Coelho <falktx@falktx.com>
# Copyright (C) 2019-2024 Mathieu Picot <picotmathieu@gmail.com>
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

from qtpy.QtCore import QRectF, QMarginsF, Qt
from qtpy.QtWidgets import QGraphicsView

from patshared import PortMode
from .init_values import canvas, options, Direction
from .utils import (previous_left_on_grid, next_left_on_grid,
                    previous_top_on_grid, next_top_on_grid)

from .scene_moth import MovingBox, PatchSceneMoth
from .box_widget_moth import BoxWidgetMoth
from .scene_view import PatchGraphicsView


@dataclass
class BoxAndRect:
    rect: QRectF
    item: BoxWidgetMoth
    
        
@dataclass
class ToMoveBox:
    directions: list[Direction]
    item: BoxWidgetMoth
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
    def __init__(self, view: PatchGraphicsView):
        PatchSceneMoth.__init__(self, view)
        self._full_repulse_boxes = set[BoxWidgetMoth]()

    def deplace_boxes_from_repulsers(self, repulser_boxes: list[BoxWidgetMoth],
                                     wanted_direction=Direction.NONE,
                                     mov_repulsables: Optional[list[MovingBox]]=None):
        '''Change the place of boxes in order to have no box overlapping
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
                    fixed: BoxWidgetMoth | QRectF,
                    moving: BoxWidgetMoth | QRectF,
                    fixed_port_mode: PortMode,
                    moving_port_mode: PortMode) -> QRectF:
            '''returns a QRectF to be placed at side of fixed_rect
            where fixed_rect is an already determinated futur place
            for a box'''
            if isinstance(fixed, BoxWidgetMoth):
                fixed_rect = fixed.boundingRect().translated(fixed.pos())
            else:
                fixed_rect = fixed
            
            if isinstance(moving, BoxWidgetMoth):
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

            return rect.intersects(
                repulser_rect.adjusted(
                    - left_spacing, - box_spacing,
                    right_spacing, box_spacing))

        def rect_may_have_to_move_from(
                repulser_rect: QRectF, rect: QRectF) -> bool:
            return rect.intersects(
                repulser_rect.marginsAdded(normal_margins))

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
        
        normal_margins = QMarginsF(
            canvas.theme.box_spacing_horizontal,
            canvas.theme.box_spacing, 
            canvas.theme.box_spacing_horizontal,
            canvas.theme.box_spacing)
        
        for box in repulser_boxes:
            self._full_repulse_boxes.add(box)

            if mov_repulsables is not None:
                # in view change the moving box for this box
                # is the first of the list (optimisation).
                # there is only one repulser
                srect = mov_repulsables[0].final_rect # type:ignore wtf
            else:
                # if box is already moving, consider its end position
                moving_box = self.move_boxes.get(box)
                if moving_box is None:
                    srect = box.after_wrap_rect().translated(box.pos())
                else:
                    srect = moving_box.final_rect
                    if srect.isNull():
                        # if this box is joining or hidding,
                        # it will be removed soon
                        # so, it has not to be a repulser.
                        continue

            repulser = BoxAndRect(srect, box)
            repulsers.append(repulser)
            items_to_move = list[BoxAndRect]()

            if mov_repulsables is not None:
                for moving_box in mov_repulsables[1:]:
                    if moving_box.widget in [b.item for b in to_move_boxes]:
                        continue

                    if not rect_may_have_to_move_from(
                            repulser.rect, moving_box.final_rect):
                        continue
                        
                    if rect_has_to_move_from(
                            repulser.rect, moving_box.final_rect,
                            repulser.item.get_current_port_mode(),
                            moving_box.widget.get_current_port_mode()):
                        items_to_move.append(
                            BoxAndRect(moving_box.final_rect, moving_box.widget))
            else:
                search_rect = srect.marginsAdded(
                QMarginsF(canvas.theme.box_spacing_horizontal,
                          canvas.theme.box_spacing, 
                          canvas.theme.box_spacing_horizontal,
                          canvas.theme.box_spacing))
                
                # search intersections in non moving boxes
                for widget in self.items(
                        search_rect, Qt.ItemSelectionMode.IntersectsItemShape,
                        Qt.SortOrder.AscendingOrder):
                    if not isinstance(widget, BoxWidgetMoth):
                        continue
                    
                    if (widget in repulser_boxes
                            or widget in [b.item for b in to_move_boxes]
                            or widget in self.move_boxes):
                        continue

                    irect = widget.sceneBoundingRect()

                    if rect_has_to_move_from(
                            repulser.rect, irect,
                            repulser.item.get_current_port_mode(),
                            widget.get_current_port_mode()):
                        items_to_move.append(BoxAndRect(irect, widget))

                # search intersections in moving boxes
                for widget, moving_box in self.move_boxes.items():
                    if (widget in repulser_boxes
                            or moving_box.final_rect.isNull()
                            or widget in [b.item for b in to_move_boxes]):
                        continue

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
                for moving_box in mov_repulsables: # type:ignore
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
                    if not isinstance(widget, BoxWidgetMoth):
                        continue
                    if (widget in [r.item for r in repulsers]
                            or widget in [b.item for b in to_move_boxes]
                            or widget in self.move_boxes):
                        continue
                    
                    mirect = widget.sceneBoundingRect()
                    if rect_has_to_move_from(
                            new_rect, mirect,
                            to_move_box.item.get_current_port_mode(),
                            widget.get_current_port_mode()):
                        adding_list.append(
                            ToMoveBox(directions, widget, mirect, repulser))                        
                
                for mitem, moving_box in self.move_boxes.items():                    
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

    def full_repulse(self):
        if not options.prevent_overlap:
            return

        self._full_repulse_boxes.clear()

        for box in canvas.list_boxes():
            if box.isVisible() and not box in self.move_boxes:
                self.add_box_to_animation(box, *box.top_left())

        # in view change, all boxes are in self.move_boxes
        moving_boxes = [mb for b, mb in self.move_boxes.items()
                        if (not mb.final_rect.isNull()
                            and b.isVisible())]

        while moving_boxes:
            self.deplace_boxes_from_repulsers(
                [moving_boxes[0].widget],
                mov_repulsables=moving_boxes)
            to_rm_movboxes = [mb for mb in moving_boxes
                                if mb.widget in self._full_repulse_boxes]
            for to_rm_mb in to_rm_movboxes:
                moving_boxes.remove(to_rm_mb)
        
        self._full_repulse_boxes.clear()

    def bring_neighbors_and_deplace_boxes(
            self, box_widget: BoxWidgetMoth, ex_rect: QRectF):
        if not options.prevent_overlap:
            return
        
        neighbors = [box_widget]
        limit_top = ex_rect.top()
        less_y = ex_rect.height() - box_widget.after_wrap_rect().height()
        
        box_spacing = canvas.theme.box_spacing
        
        for neighbor in neighbors:
            if neighbor is box_widget:
                srect = ex_rect
            else:
                moving_box = self.move_boxes.get(neighbor)
                if moving_box is None:
                    srect = neighbor.after_wrap_rect().translated(
                        neighbor.pos())
                else:
                    srect = moving_box.final_rect

            for item in self.items(
                    srect.adjusted(0, 0, 0,
                                   box_spacing + 1)):
                if item not in neighbors and isinstance(item, BoxWidgetMoth):
                    nrect = item.after_wrap_rect().translated(item.pos())                    
                    if nrect.top() >= limit_top:
                        neighbors.append(item)
        
        neighbors.remove(box_widget)

        repulser_boxes = list[BoxWidgetMoth]()

        for neighbor in neighbors:
            x, y = neighbor.top_left()           
            self.add_box_to_animation(neighbor, x, int(y - less_y))
            repulser_boxes.append(neighbor)
        repulser_boxes.append(box_widget)
        
        self.deplace_boxes_from_repulsers(
            repulser_boxes, wanted_direction=Direction.UP)
