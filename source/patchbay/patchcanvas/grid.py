'''Contains functions to get the next, previous or nearest point
on the current grid, mainly to know where to place the boxes.'''

from typing import TYPE_CHECKING

from qtpy.QtCore import QPointF

from .init_values import canvas, options

if TYPE_CHECKING:
    from .box_widget import BoxWidget


def nearest(xy: tuple[int, int]) -> tuple[int, int]:
    canvas.ensure_init()
    x, y = xy
    cell_x = options.cell_width
    cell_y = options.cell_height
    margin = canvas.theme.box_spacing // 2

    ret_x = cell_x * (x // cell_x) + margin
    if x - ret_x > cell_x / 2:
        ret_x += cell_x

    ret_y = cell_y * (y // cell_y) + margin
    if y - ret_y > cell_y / 2:
        ret_y += cell_y

    return (ret_x, ret_y)

def nearest_check_others(
        xy: tuple[int, int], orig_box: 'BoxWidget') -> tuple[int, int]:
    '''return the pos for a just moved box,
    may be not exactly the nearest point on grid,
    to prevent unwanted other boxes move.'''
    canvas.ensure_init()
    spacing = canvas.theme.box_spacing
    check_rect = orig_box.boundingRect().translated(QPointF(*xy))
    search_rect = check_rect.adjusted(- spacing, - spacing, spacing, spacing)

    boxes = [b for b in canvas.scene.list_boxes_at(search_rect)
             if b is not orig_box]
    x, y = xy
    new_x, new_y = nearest(xy)

    for box in boxes:
        rect = box.sceneBoundingRect()

        if (previous_top(y)
                == previous_top(rect.bottom())):
            return (new_x, previous_top(y) + options.cell_height)

        if (next_bottom(check_rect.bottom())
                == next_bottom(rect.top())):
            return (new_x, next_top(y) - options.cell_height)

    return nearest(xy)

def previous_left(x: int | float) -> int:
    canvas.ensure_init()
    cell_x = options.cell_width
    margin = canvas.theme.box_spacing / 2

    ret = int(cell_x * (x // cell_x) + margin)
    if ret > x:
        ret -= cell_x

    return ret

def next_left(x: int | float) -> int:
    canvas.ensure_init()
    cell_x = options.cell_width
    margin = canvas.theme.box_spacing / 2

    ret = int(cell_x * (x // cell_x) + margin)
    if ret < x:
        ret += cell_x

    return ret

def previous_top(y: int | float) -> int:
    canvas.ensure_init()
    cell_y = options.cell_height
    margin = canvas.theme.box_spacing / 2

    ret = int(cell_y * (y // cell_y) + margin)
    if ret > y:
        ret -= cell_y

    return ret

def next_top(y: int | float) -> int:
    canvas.ensure_init()
    cell_y = options.cell_height
    margin = canvas.theme.box_spacing / 2

    ret = int(cell_y * ((y - 1) // cell_y) + margin)
    if ret < y:
        ret += cell_y

    return ret

def next_bottom(y: int | float) -> int:
    canvas.ensure_init()
    cell_y = options.cell_height
    margin = canvas.theme.box_spacing / 2

    ret = int(cell_y * (1 + y // cell_y) - margin)
    if ret < y:
        ret += cell_y

    return ret

def next_width(width: int | float) -> int:
    canvas.ensure_init()
    cell_x = options.cell_width
    box_spacing = canvas.theme.box_spacing
    ret = cell_x * (1 + (width // cell_x)) - box_spacing
    while ret < width:
        ret += cell_x

    return int(ret)

def next_height(height: int | float) -> int:
    canvas.ensure_init()
    cell_y = options.cell_height
    box_spacing = canvas.theme.box_spacing
    ret = cell_y * (1 + (height // cell_y)) - box_spacing
    while ret < height:
        ret += cell_y

    return int(ret)
