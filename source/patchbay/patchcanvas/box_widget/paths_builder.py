
from typing import TYPE_CHECKING

from qtpy.QtCore import QRectF
from qtpy.QtGui import QPainterPath

from patshared import PortMode

from ..patchcanvas import canvas
from ..theme import StyleAttributer

from .box_utils import BoxStyler, PaintElement, WrappingState

if TYPE_CHECKING:
    from .box_widget import BoxWidget


# theses values are needed to prevent some incorrect painter_path
# united or subtracted results
EPSY = 0.001
EPSD = EPSY * 2.0


def _build_main_path(
        box: 'BoxWidget', pos_dict: dict[str, list[list[float]]],
        selected=False) -> QPainterPath:
    input_segments = pos_dict['input_segments']
    output_segments = pos_dict['output_segments']

    painter_path = QPainterPath()
    theme = box.get_theme()
    if selected:
        theme = theme.selected

    border_radius = theme.border_radius
    port_in_offset = abs(theme.port_in_offset)
    port_out_offset = abs(theme.port_out_offset)
    bore_in = bool(theme.port_in_offset_mode == 'bore')
    bore_out = bool(theme.port_out_offset_mode == 'bore')
    line_hinting = theme.border_width / 2

    rect = QRectF(0.0, 0.0, box._width, box._height)
    rect.adjust(line_hinting, line_hinting, -line_hinting, -line_hinting)

    if border_radius == 0.0:
        painter_path.addRect(rect)
    else:
        painter_path.addRoundedRect(rect, border_radius, border_radius)

    if not bore_in:
        port_in_offset = 0.0
    if not bore_out:
        port_out_offset = 0.0

    if box._wrapping_state is WrappingState.NORMAL:
        # substract rects in the box shape in case of 
        # port_offset (even negativ).
        # logic would want to add rects if port_offset is negativ
        # But that also means that we should change the boudingRect,
        # So we won't.
        if port_in_offset != 0.0:
            for in_segment in input_segments:
                moins_path = QPainterPath()
                moins_path.addRect(QRectF(
                    0.0 - EPSY,
                    in_segment[0] - line_hinting - EPSY,
                    port_in_offset + line_hinting + EPSD,
                    in_segment[1] - in_segment[0] + line_hinting * 2 + EPSD))
                painter_path = painter_path.subtracted(moins_path)

        if port_out_offset != 0.0:
            for out_segment in output_segments:
                moins_path = QPainterPath()
                moins_path.addRect(QRectF(
                    box._width - line_hinting - port_out_offset - EPSY,
                    out_segment[0] - line_hinting - EPSY,
                    port_out_offset + line_hinting + EPSD,
                    out_segment[1] - out_segment[0] + line_hinting * 2 + EPSD))
                painter_path = painter_path.subtracted(moins_path)

        # No rounded corner if the last port is to close from the corner
        if (input_segments
                and box._height - input_segments[-1][1] <= border_radius):
            left_path = QPainterPath()
            left_path.addRect(QRectF(
                0.0 + line_hinting - EPSY,
                max(box._height - border_radius, input_segments[-1][1])
                    + line_hinting - EPSY,
                border_radius + EPSD,
                min(border_radius, box._height - input_segments[-1][1])
                    - 2 * line_hinting + EPSD))
            painter_path = painter_path.united(left_path)

        if (input_segments
                and input_segments[0][0] <= border_radius):
            top_left_path = QPainterPath()
            top_left_path.addRect(QRectF(
                0.0 + line_hinting - EPSY,
                0.0 + line_hinting - EPSY,
                border_radius + EPSD,
                min(border_radius, input_segments[0][0])
                - 2 * line_hinting + EPSD))
            painter_path = painter_path.united(top_left_path)

        if (output_segments
                and box._height - output_segments[-1][1] <= border_radius):
            right_path = QPainterPath()
            right_path.addRect(QRectF(
                box._width - border_radius - line_hinting - EPSY,
                max(box._height - border_radius, output_segments[-1][1])
                    + line_hinting - EPSY,
                border_radius + EPSD,
                min(border_radius, box._height - output_segments[-1][1])
                    - 2 * line_hinting + EPSD))
            painter_path = painter_path.united(right_path)

        if (output_segments
                and output_segments[0][0] <= border_radius):
            top_right_path = QPainterPath()
            top_right_path.addRect(QRectF(
                box._width - line_hinting + EPSY - border_radius,
                0.0 + line_hinting - EPSY,
                border_radius + EPSD,
                min(border_radius, output_segments[0][0])
                - 2 * line_hinting + EPSD))
            painter_path = painter_path.united(top_right_path)

    if box.is_monitor and border_radius:
        if box._current_port_mode is PortMode.OUTPUT:
            left_path = QPainterPath()
            left_path.addRect(QRectF(
                0.0 + line_hinting - EPSY,
                box._height - border_radius - EPSY,
                border_radius + EPSD, border_radius - line_hinting + EPSD))
            painter_path = painter_path.united(left_path)

            top_left_path = QPainterPath()
            top_left_path.addRect(QRectF(
                0.0 + line_hinting - EPSY, 0.0 + line_hinting - EPSY,
                border_radius + EPSD, border_radius - line_hinting + EPSD))
            painter_path = painter_path.united(top_left_path)

        elif box._current_port_mode is PortMode.INPUT:
            right_path = QPainterPath()
            right_path.addRect(QRectF(
                box._width - line_hinting - EPSY - border_radius,
                box._height - border_radius - EPSY,
                border_radius + EPSD, border_radius - line_hinting + EPSD))
            painter_path = painter_path.united(right_path)

            top_right_path = QPainterPath()
            top_right_path.addRect(QRectF(
                box._width - line_hinting - EPSY - border_radius,
                0.0 + line_hinting - EPSY,
                border_radius + EPSD, border_radius - line_hinting + EPSD))
            painter_path = painter_path.united(top_right_path)
    
    return painter_path

def _build_header_path(
        box: 'BoxWidget', header_theme: StyleAttributer,
        usl_border: float, line_hinting: float) -> QPainterPath:
    mg = header_theme.margin
    header_lh = header_theme.border_width * 0.5
    if header_lh == 0:
        # fix artefacts in case there is no border for the header
        border = 0
    else:
        border = line_hinting * 2.0
    
    if box._has_side_title():
        if box._current_port_mode is PortMode.OUTPUT:
            header_rect = QRectF(
                border + header_lh + mg.free_side - EPSY,
                border + header_lh - EPSY,
                box._header_width - mg.sided_width
                    - 2 * header_lh - border + usl_border + EPSD,
                box._height - 2 * (border + header_lh) + EPSD
            )
        else:
            header_rect = QRectF(
                box._width - border - box._header_width + mg.ports_side
                    + header_lh + border - usl_border - EPSY,
                border + header_lh - EPSY,
                box._header_width - mg.sided_width - 2 * header_lh + EPSD,
                box._height - 2 * (border + header_lh) + EPSD
            )

    else:
        header_rect = QRectF(
            border + header_lh - EPSY,
            border + mg.top + header_lh -EPSY,
            box._width - 2 * (border + header_lh) + EPSD,
            box._header_height - mg.height
                - 2 * header_lh - border + usl_border + EPSD)
    
    header_path = QPainterPath()
    header_path.addRect(header_rect)
    return header_path

def _build_gui_button_path(
        box: 'BoxWidget', header_theme: StyleAttributer,
        usl_border: float) -> QPainterPath:
    gui_theme = canvas.theme.gui_button
    gui_path = QPainterPath()
    gmg = gui_theme.margin
    hmg = header_theme.margin
    mg = hmg + gmg
    gui_lh = gui_theme.border_width / 2
    
    if box._has_side_title():
        if box._current_port_mode is PortMode.OUTPUT:
            gui_rect = QRectF(
                usl_border + mg.free_side + gui_lh,
                usl_border + mg.top_side + gui_lh,
                box._header_width - mg.sided_width - 2 * gui_lh,
                box._header_height - mg.sided_height - 2 * gui_lh)
        else:
            gui_rect = QRectF(
                box._width - box._header_width - usl_border + mg.ports_side + gui_lh,
                mg.top_side + usl_border + gui_lh,
                box._header_width - mg.sided_width - gui_lh * 2,
                box._header_height - mg.sided_height - gui_lh * 2)
    else:
        space_left = (box._width - box._header_width - 2 * usl_border) / 2
        gui_rect = QRectF(
            usl_border + mg.sides + space_left + gui_lh,
            usl_border + mg.top + gui_lh,
            box._header_width - mg.width - gui_lh * 2,
            box._header_height - mg.height - gui_lh * 2)
        
    radius = gui_theme.border_radius
    if radius:
        gui_path.addRoundedRect(gui_rect, radius, radius)
    else:
        gui_path.addRect(gui_rect)
        
    return gui_path

def build_painter_path(
        box: 'BoxWidget', pos_dict: dict[str, list[list[float]]],
        selected=False):
    painter_paths = box._painter_paths.get(selected)
    if painter_paths is None:
        painter_paths = box._painter_paths[selected] = \
            dict[PaintElement, QPainterPath]()
    painter_paths.clear()

    main_path = _build_main_path(box, pos_dict, selected)
    painter_paths[PaintElement.MAIN] = main_path

    theme = box.get_theme()
    usl_border = theme.border_width
    if selected:
        theme = theme.selected

    header_theme = box.get_theme(BoxStyler.HEADER)
    if selected:
        header_theme = header_theme.selected

    drill_gui_button = False

    if box._can_handle_gui:
        painter_paths[PaintElement.GUI_BUTTON] = \
            _build_gui_button_path(box, header_theme, usl_border)
        drill_gui_button = canvas.theme.gui_button.drilled

    if header_theme.visible:
        tmp_header_path = _build_header_path(
            box, header_theme, usl_border, theme.border_width / 2)

        if drill_gui_button:
            tmp_header_path = tmp_header_path.subtracted(
                painter_paths[PaintElement.GUI_BUTTON])

        painter_paths[PaintElement.HEADER] = \
            main_path.intersected(tmp_header_path)   
        
        if header_theme.drilled:
            painter_paths[PaintElement.ANTI_HEADER] = \
                main_path.subtracted(tmp_header_path)
