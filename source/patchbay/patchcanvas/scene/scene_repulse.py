from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING

from qtpy.QtCore import QRectF, QPointF, QMarginsF, Qt

from patshared import PortMode

from ..box_widget import BoxWidget
from ..init_values import canvas, options, Direction, BoxHidding
from .. import grid

from .scene_utils import MovingBox

if TYPE_CHECKING:
    from . import PatchScene


_logger = logging.getLogger(__name__)


@dataclass
class ToMoveBox:
    directions: list[Direction]
    box: BoxWidget
    rect: QRectF
    pusher_box: BoxWidget
    pusher_rect: QRectF

    def __lt__(self, other: 'ToMoveBox'):
        if self.directions != other.directions:
            return self.directions < other.directions

        # should not happen
        if not self.directions:
            return True

        last_direc = self.directions[-1]
        match last_direc:
            case Direction.LEFT:
                return self.rect.right() > other.rect.right()
            case Direction.UP:
                return self.rect.bottom() > other.rect.bottom()
            case Direction.RIGHT:
                return self.rect.left() < other.rect.left()
            case Direction.DOWN:
                return self.rect.top() < other.rect.top()
            case _:
                # should not happen
                return True


def _get_direction(fixed_rect: QRectF, moving_rect: QRectF,
                   parent_directions: list[Direction] =[]) -> Direction:
    if (moving_rect.top() <= fixed_rect.center().y() <= moving_rect.bottom()
            or (fixed_rect.top()
                <= moving_rect.center().y()
                <= fixed_rect.bottom())):
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

def _repulse(
        direction: Direction, pusher: BoxWidget | QRectF,
        pushed: BoxWidget | QRectF, pusher_port_mode: PortMode,
        pushed_port_mode: PortMode) -> QRectF:
    '''returns a QRectF to be placed at side of fixed_rect
    where fixed_rect is an already determinated futur place
    for a box'''
    if isinstance(pusher, BoxWidget):
        pusher_rect = pusher.boundingRect().translated(pusher.pos())
    else:
        pusher_rect = pusher

    if isinstance(pushed, BoxWidget):
        rect = pushed.boundingRect().translated(pushed.pos())
    else:
        rect = pushed

    x = rect.left()
    y = rect.top()

    spacing = canvas.theme.box_spacing
    spacing_hor = canvas.theme.box_spacing_horizontal
    magnet = canvas.theme.magnet

    match direction:
        case Direction.LEFT | Direction.RIGHT:
            if direction is Direction.LEFT:
                if (pusher_port_mode & PortMode.INPUT
                        or pushed_port_mode & PortMode.OUTPUT):
                    x = grid.previous_left(
                        pusher_rect.left() - rect.width() - spacing_hor)
                else:
                    x = grid.previous_left(
                        pusher_rect.left() - rect.width() - spacing)
            else:
                if (pusher_port_mode & PortMode.OUTPUT
                        or pushed_port_mode & PortMode.INPUT):
                    x = grid.next_left(pusher_rect.right() + spacing_hor)
                else:
                    x = grid.next_left(pusher_rect.right() + spacing)

            top_diff = abs(pusher_rect.top() - rect.top())
            bottom_diff = abs(pusher_rect.bottom() - rect.bottom())

            if bottom_diff > top_diff and top_diff <= magnet:
                y = pusher_rect.top()
            elif bottom_diff <= magnet:
                y = pusher_rect.bottom() - rect.height()

        case Direction.UP | Direction.DOWN:
            if direction is Direction.UP:
                y = grid.previous_top(
                    pusher_rect.top() - rect.height() - spacing)
            else:
                y = grid.next_top(pusher_rect.bottom() + spacing)

            left_diff = abs(pusher_rect.left() - rect.left())
            right_diff = abs(pusher_rect.right() - rect.right())

            if right_diff > left_diff and left_diff <= magnet:
                x = pusher_rect.left()
            elif right_diff <= magnet:
                x = pusher_rect.right() - rect.width()

    return QRectF(float(x), float(y), rect.width(), rect.height())

def _rect_may_have_to_move_from(
        repulser_rect: QRectF, rect: QRectF, margins: QMarginsF) -> bool:
    return rect.intersects(repulser_rect.marginsAdded(margins))

def _rect_has_to_move_from(
        repulser_rect: QRectF, rect: QRectF,
        repulser_port_mode: PortMode, rect_port_mode: PortMode) -> bool:
    left_spacing = right_spacing = canvas.theme.box_spacing

    if (repulser_port_mode & PortMode.INPUT
            or rect_port_mode & PortMode.OUTPUT):
        left_spacing = canvas.theme.box_spacing_horizontal

    if (repulser_port_mode & PortMode.OUTPUT
            or rect_port_mode & PortMode.INPUT):
        right_spacing = canvas.theme.box_spacing_horizontal

    return rect.intersects(
        repulser_rect.adjusted(
            - left_spacing, - canvas.theme.box_spacing,
            right_spacing, canvas.theme.box_spacing))

def _get_to_move_boxes_from_repulse_boxes(
        scene: 'PatchScene', pusher_boxes: list[BoxWidget],
        wanted_direction: Direction) -> \
            tuple[list[ToMoveBox], dict[BoxWidget, QRectF]]:
    box_spacing = canvas.theme.box_spacing
    box_spacing_hor = canvas.theme.box_spacing_horizontal
    normal_margins = QMarginsF(
        box_spacing_hor,box_spacing,
        box_spacing_hor, box_spacing)

    to_move_boxes = list[ToMoveBox]()
    pushers = dict[BoxWidget, QRectF]()
    wanted_directions = [wanted_direction]
    
    for pusher_box in pusher_boxes:
        # if box is already moving, consider its end position
        moving_box = scene.move_boxes.get(pusher_box)
        if moving_box is None:
            pusher_rect = pusher_box.after_wrap_rect().translated(
                pusher_box.pos())
        else:
            pusher_rect = moving_box.final_rect
            if pusher_rect.isNull():
                # if this box is joining or hidding,
                # it will be removed soon
                # so, it has not to be a repulser.
                continue

        pushers[pusher_box] = pusher_rect
        pusheds = dict[BoxWidget, QRectF]()

        search_rect = pusher_rect.marginsAdded(normal_margins)

        # search intersections in non moving boxes
        for candidate_box in scene.items(
                search_rect, Qt.ItemSelectionMode.IntersectsItemShape,
                Qt.SortOrder.AscendingOrder):
            if not isinstance(candidate_box, BoxWidget):
                continue

            if (candidate_box in pusher_boxes
                    or candidate_box in [b.box for b in to_move_boxes]
                    or candidate_box in scene.move_boxes):
                continue

            pushed_rect = candidate_box.sceneBoundingRect()

            if _rect_has_to_move_from(
                    pusher_rect, pushed_rect,
                    pusher_box._current_port_mode,
                    candidate_box._current_port_mode):
                pusheds[candidate_box] = pushed_rect

        # search intersections in moving boxes
        for candidate_box, moving_box in scene.move_boxes.items():
            if (candidate_box in pusher_boxes
                    or moving_box.final_rect.isNull()
                    or candidate_box in [b.box for b in to_move_boxes]):
                continue

            pushed_rect = moving_box.final_rect

            if _rect_has_to_move_from(
                    pusher_rect, pushed_rect,
                    pusher_box._current_port_mode,
                    candidate_box._current_port_mode):
                pusheds[candidate_box] = pushed_rect
                
        for pushed_box, pushed_rect in pusheds.items():
            # evaluate in which direction should go the box
            direction = _get_direction(
                pusher_rect, pushed_rect, wanted_directions)
            to_move_boxes.append(
                ToMoveBox([direction], pushed_box, pushed_rect,
                          pusher_box, pusher_rect))

    to_move_boxes.sort()
    return to_move_boxes, pushers

def _get_to_move_boxes_in_full_repulse(
        scene: 'PatchScene', mov_repulsables: list[MovingBox]) -> \
            tuple[list[ToMoveBox], dict[BoxWidget, QRectF]]:
    box_spacing = canvas.theme.box_spacing
    box_spacing_hor = canvas.theme.box_spacing_horizontal
    normal_margins = QMarginsF(
        box_spacing_hor, box_spacing,
        box_spacing_hor, box_spacing)

    # in full repulse, the moving box for this box
    # is the first of the list (optimisation).
    pusher_box = mov_repulsables[0].widget
    pusher_rect = mov_repulsables[0].final_rect
    scene._full_repulse_boxes.add(pusher_box)

    pusheds = dict[BoxWidget, QRectF]()
    to_move_boxes = list[ToMoveBox]()

    for moving_box in mov_repulsables[1:]:
        if moving_box.widget in [b.box for b in to_move_boxes]:
            continue

        if not moving_box.final_rect.intersects(
                pusher_rect.marginsAdded(normal_margins)):
            continue

        if _rect_has_to_move_from(
                pusher_rect, moving_box.final_rect,
                pusher_box._current_port_mode,
                moving_box.widget._current_port_mode):
            pusheds[moving_box.widget] = moving_box.final_rect

    for pushed_box, pushed_rect in pusheds.items():
        # evaluate in which direction should go the box
        direction = _get_direction(pusher_rect, pushed_rect)
        to_move_boxes.append(
            ToMoveBox([direction], pushed_box, pushed_rect,
                      pusher_box, pusher_rect))

    to_move_boxes.sort()
    return to_move_boxes, {pusher_box: pusher_rect}

def deplace_boxes_from_repulsers(
        scene: 'PatchScene', repulser_boxes: list[BoxWidget],
        wanted_direction=Direction.NONE,
        mov_repulsables: list[MovingBox] | None =None):
    '''Change the place of boxes in order to have no box overlapping
    other boxes.'''
    if not options.prevent_overlap:
        return

    box_spacing = canvas.theme.box_spacing
    box_spacing_hor = canvas.theme.box_spacing_horizontal

    if mov_repulsables is not None:
        to_move_boxes, pushers = _get_to_move_boxes_in_full_repulse(
            scene, mov_repulsables)
    else:
        _logger.debug(f'move boxes from {repulser_boxes}')
        to_move_boxes, pushers = _get_to_move_boxes_from_repulse_boxes(
            scene, repulser_boxes, wanted_direction)

    normal_margins = QMarginsF(
        box_spacing_hor, box_spacing,
        box_spacing_hor, box_spacing)

    # !!! to_move_boxes list is dynamic
    # elements can be added to the list while iteration !!!
    for to_move_box in to_move_boxes:
        box, rect, pusher_box, pusher_rect = \
            to_move_box.box, to_move_box.rect, \
            to_move_box.pusher_box, to_move_box.pusher_rect

        directions = to_move_box.directions.copy()
        new_direction = _get_direction(pusher_rect, rect, directions)
        directions.append(new_direction)

        # calculate the new position of the box repulsed by its repulser
        pushed_rect = _repulse(
            new_direction, pusher_rect, rect,
            pusher_box._current_port_mode, box._current_port_mode)

        active_pusher_boxes = set[BoxWidget]()

        # while there is a pusher at new box position
        # move the future box position
        while True:
            # list just here to prevent infinite loop
            # we save the repulsers that already have moved the rect
            for pusher_box, pusher_rect in pushers.items():
                if not pushed_rect.intersects(
                        pusher_rect.marginsAdded(normal_margins)):
                    continue
                
                if _rect_has_to_move_from(
                        pusher_rect, pushed_rect,
                        pusher_box._current_port_mode,
                        box._current_port_mode):

                    if pusher_box in active_pusher_boxes:
                        continue
                    active_pusher_boxes.add(pusher_box)

                    # new_direction = _get_direction(
                    #     pusher_rect, pushed_rect, directions)
                    pushed_rect = _repulse(
                        directions[-1], pusher_rect, pushed_rect,
                        # new_direction, pusher_rect, pushed_rect,
                        pusher_box._current_port_mode,
                        box._current_port_mode)
                    directions.append(new_direction)
                    break
            else:
                break

        # Now we know where the box will be definitely positioned
        # So, this is now a pusher for other boxes
        pushers[box] = pushed_rect
        scene._full_repulse_boxes.add(box)

        # check which existing boxes exists at the new place of the box
        # and add them to this to_move_boxes iteration
        adding_list = list[ToMoveBox]()

        if mov_repulsables is not None:
            for moving_box in mov_repulsables:
                mv_box = moving_box.widget

                if (mv_box in pushers
                        or mv_box in [b.box for b in to_move_boxes]):
                    continue

                if not pushed_rect.intersects(
                        moving_box.final_rect.marginsAdded(normal_margins)):
                    continue

                if _rect_has_to_move_from(
                        pushed_rect, moving_box.final_rect,
                        to_move_box.box._current_port_mode,
                        mv_box._current_port_mode):
                    adding_list.append(
                        ToMoveBox(directions, moving_box.widget,
                                  moving_box.final_rect, box, pushed_rect))
        else:
            search_rect = pushed_rect.marginsAdded(normal_margins)
            for candidate_box in scene.items(search_rect):
                if not isinstance(candidate_box, BoxWidget):
                    continue
                if (candidate_box in pushers
                        or candidate_box in [b.box for b in to_move_boxes]
                        or candidate_box in scene.move_boxes):
                    continue

                candidate_rect = candidate_box.sceneBoundingRect()
                if _rect_has_to_move_from(
                        pushed_rect, candidate_rect,
                        to_move_box.box._current_port_mode,
                        candidate_box._current_port_mode):
                    adding_list.append(
                        ToMoveBox(directions, candidate_box, candidate_rect,
                                  box, pushed_rect))

            for mv_box, moving_box in scene.move_boxes.items():
                if (mv_box in pushers
                        or moving_box.final_rect.isNull()
                        or mv_box in [b.box for b in to_move_boxes]):
                    continue

                if _rect_has_to_move_from(
                        pushed_rect, moving_box.final_rect,
                        to_move_box.box._current_port_mode,
                        mv_box._current_port_mode):
                    adding_list.append(
                        ToMoveBox(directions, moving_box.widget,
                                  moving_box.final_rect, box, pushed_rect))

        adding_list.sort()

        for to_move_box in adding_list:
            to_move_boxes.append(to_move_box)

        # now we decide where the box is moved
        scene.add_box_to_animation(
            box, int(pushed_rect.left()), int(pushed_rect.top()))

def full_repulse(scene: 'PatchScene'):
    if not options.prevent_overlap:
        return

    scene._full_repulse_boxes.clear()

    # add all boxes to animation (this optimize the repulse algorythm)
    for box in canvas.list_boxes():
        if box.isVisible() and box not in scene.move_boxes:
            scene.add_box_to_animation(box, *box.top_left())

    # Now, all boxes are in self.move_boxes
    moving_boxes = [mb for b, mb in scene.move_boxes.items()
                    if (not mb.final_rect.isNull()
                        and b.isVisible())]

    while moving_boxes:
        deplace_boxes_from_repulsers(
            scene, [moving_boxes[0].widget], mov_repulsables=moving_boxes)
        to_rm_movboxes = [mb for mb in moving_boxes
                          if mb.widget in scene._full_repulse_boxes]
        for to_rm_mb in to_rm_movboxes:
            moving_boxes.remove(to_rm_mb)

    scene._full_repulse_boxes.clear()

def bring_neighbors_and_deplace_boxes(
        scene: 'PatchScene', box_widget: BoxWidget, ex_rect: QRectF):
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
            moving_box = scene.move_boxes.get(neighbor)
            if moving_box is None:
                srect = neighbor.after_wrap_rect().translated(
                    neighbor.pos())
            else:
                srect = moving_box.final_rect

        for item in scene.items(
                srect.adjusted(0, 0, 0,
                                box_spacing + 1)):
            if item not in neighbors and isinstance(item, BoxWidget):
                nrect = item.after_wrap_rect().translated(item.pos())
                if nrect.top() >= limit_top:
                    neighbors.append(item)

    neighbors.remove(box_widget)

    repulser_boxes = list[BoxWidget]()

    for neighbor in neighbors:
        x, y = neighbor.top_left()
        scene.add_box_to_animation(neighbor, x, int(y - less_y))
        repulser_boxes.append(neighbor)
    repulser_boxes.append(box_widget)

    scene.deplace_boxes_from_repulsers(
        repulser_boxes, wanted_direction=Direction.UP)