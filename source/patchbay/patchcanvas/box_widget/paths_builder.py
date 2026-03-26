
from typing import TYPE_CHECKING

from qtpy.QtCore import QRectF
from qtpy.QtGui import QPainterPath

from patshared import PortMode

from ..patchcanvas import canvas
from ..theme import BoxStyler

from .box_utils import PaintElement, WrappingState

if TYPE_CHECKING:
    from .box_widget import BoxWidget


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

    # theses values are needed to prevent some incorrect painter_path
    # united or subtracted results
    epsy = 0.001
    epsd = epsy * 2.0

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
                    0.0 - epsy,
                    in_segment[0] - line_hinting - epsy,
                    port_in_offset + line_hinting + epsd,
                    in_segment[1] - in_segment[0] + line_hinting * 2 + epsd))
                painter_path = painter_path.subtracted(moins_path)

        if port_out_offset != 0.0:
            for out_segment in output_segments:
                moins_path = QPainterPath()
                moins_path.addRect(QRectF(
                    box._width - line_hinting - port_out_offset - epsy,
                    out_segment[0] - line_hinting - epsy,
                    port_out_offset + line_hinting + epsd,
                    out_segment[1] - out_segment[0] + line_hinting * 2 + epsd))
                painter_path = painter_path.subtracted(moins_path)

        # No rounded corner if the last port is to close from the corner
        if (input_segments
                and box._height - input_segments[-1][1] <= border_radius):
            left_path = QPainterPath()
            left_path.addRect(QRectF(
                0.0 + line_hinting - epsy,
                max(box._height - border_radius, input_segments[-1][1])
                    + line_hinting - epsy,
                border_radius + epsd,
                min(border_radius, box._height - input_segments[-1][1])
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
                and box._height - output_segments[-1][1] <= border_radius):
            right_path = QPainterPath()
            right_path.addRect(QRectF(
                box._width - border_radius - line_hinting - epsy,
                max(box._height - border_radius, output_segments[-1][1])
                    + line_hinting - epsy,
                border_radius + epsd,
                min(border_radius, box._height - output_segments[-1][1])
                    - 2 * line_hinting + epsd))
            painter_path = painter_path.united(right_path)

        if (output_segments
                and output_segments[0][0] <= border_radius):
            top_right_path = QPainterPath()
            top_right_path.addRect(QRectF(
                box._width - line_hinting + epsy - border_radius,
                0.0 + line_hinting - epsy,
                border_radius + epsd,
                min(border_radius, output_segments[0][0])
                - 2 * line_hinting + epsd))
            painter_path = painter_path.united(top_right_path)

    if box.is_monitor and border_radius:
        if box._current_port_mode is PortMode.OUTPUT:
            left_path = QPainterPath()
            left_path.addRect(QRectF(
                0.0 + line_hinting - epsy,
                box._height - border_radius - epsy,
                border_radius + epsd, border_radius - line_hinting + epsd))
            painter_path = painter_path.united(left_path)

            top_left_path = QPainterPath()
            top_left_path.addRect(QRectF(
                0.0 + line_hinting - epsy, 0.0 + line_hinting - epsy,
                border_radius + epsd, border_radius - line_hinting + epsd))
            painter_path = painter_path.united(top_left_path)

        elif box._current_port_mode is PortMode.INPUT:
            right_path = QPainterPath()
            right_path.addRect(QRectF(
                box._width - line_hinting - epsy - border_radius,
                box._height - border_radius - epsy,
                border_radius + epsd, border_radius - line_hinting + epsd))
            painter_path = painter_path.united(right_path)

            top_right_path = QPainterPath()
            top_right_path.addRect(QRectF(
                box._width - line_hinting - epsy - border_radius,
                0.0 + line_hinting - epsy,
                border_radius + epsd, border_radius - line_hinting + epsd))
            painter_path = painter_path.united(top_right_path)
    
    return painter_path

def build_painter_path(
        box: 'BoxWidget', pos_dict: dict[str, list[list[float]]],
        selected=False):
    painter_path = _build_main_path(box, pos_dict, selected)

    theme = box.get_theme()
    usl_border = theme.border_width
    if selected:
        theme = theme.selected

    line_hinting = theme.border_width / 2

    # theses values are needed to prevent some incorrect painter_path
    # united or subtracted results
    epsy = 0.001
    epsd = epsy * 2.0

    painter_paths = box._painter_paths.get(selected)
    if painter_paths is None:
        painter_paths = box._painter_paths[selected] = \
            dict[PaintElement, QPainterPath]()
    painter_paths[PaintElement.MAIN] = painter_path

    header_theme = box.get_theme(BoxStyler.HEADER)
    if selected:
        header_theme = header_theme.selected

    if header_theme.visible:
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
                    border + header_lh + mg.free_side - epsy,
                    border + header_lh - epsy,
                    box._header_width - mg.sided_width
                        - 2 * header_lh - border + usl_border + epsd,
                    box._height - 2 * (border + header_lh) + epsd
                )
            else:
                header_rect = QRectF(
                    box._width - border - box._header_width + mg.ports_side
                        + header_lh + border - usl_border - epsy,
                    border + header_lh - epsy,
                    box._header_width - mg.sided_width - 2 * header_lh + epsd,
                    box._height - 2 * (border + header_lh) + epsd
                )

        else:
            header_rect = QRectF(
                border + header_lh - epsy,
                border + mg.top + header_lh -epsy,
                box._width - 2 * (border + header_lh) + epsd,
                box._header_height - mg.height
                    - 2 * header_lh - border + usl_border + epsd)

        gui_path = None
        if box._can_handle_gui:
            gui_theme = canvas.theme.gui_button
            if gui_theme.drilled:
                gui_path = QPainterPath()
                gmg = gui_theme.margin
                # header_theme = box.get_theme(BoxStyler.HEADER)
                hmg = header_theme.margin
                mg = hmg + gmg
                gui_lh = gui_theme.border_width / 2
                border = theme.border_width
                
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

        tmp_header_path = QPainterPath()
        tmp_header_path.addRect(header_rect)
        if gui_path is not None:
            tmp_header_path = tmp_header_path.subtracted(gui_path)
            painter_paths[PaintElement.GUI_BUTTON] = gui_path
        else:
            painter_paths[PaintElement.GUI_BUTTON] = None

        painter_paths[PaintElement.HEADER] = \
            painter_path.intersected(tmp_header_path)        
        
        if header_theme.drilled:
            painter_paths[PaintElement.ANTI_HEADER] = \
                painter_path.subtracted(tmp_header_path)
        else:
            painter_paths[PaintElement.ANTI_HEADER] = painter_path
    else:
        painter_paths[PaintElement.HEADER] = None
        painter_paths[PaintElement.ANTI_HEADER] = None