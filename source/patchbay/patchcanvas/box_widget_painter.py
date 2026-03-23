import logging
from math import ceil
from struct import pack
from typing import TYPE_CHECKING

from qtpy.QtCore import Qt, QRectF, QPointF
from qtpy.QtGui import (
    QColor, QPen, QPainter, QBrush, QLinearGradient,
    QFontMetrics, QImage, QPolygonF)
# from sip import voidptr

from patshared import BoxType, PortMode

from .init_values import InlineDisplay, options, MAX_PLUGIN_ID_ALLOWED
from .patchcanvas import canvas
from .theme import BoxStyler, StyleAttributer
from .box_widget_utils import PaintElement, UnwrapButton, WrappingState

if TYPE_CHECKING:
    from .box_widget import BoxWidget


_logger = logging.getLogger(__name__)


def _paint_ports_border_lines(box: 'BoxWidget', painter: QPainter):
    theme = box.get_theme(BoxStyler.PORTS_BORDER)
    if not theme.visible:
        return

    box_theme = box.get_theme()
    border_width = box_theme.border_width
    pen = theme.fill_pen
    painter.setPen(theme.fill_pen)
    
    lh2 = pen.widthF()
    lh = lh2 * 0.5
    
    for port_mode in (PortMode.OUTPUT, PortMode.INPUT):
        if not box._current_port_mode & port_mode:
            continue

        if port_mode is PortMode.INPUT:
            x = border_width + lh
        else:
            x = box._width - border_width - lh
        
        if box._has_side_title():
            painter.drawLine(
                QPointF(x, lh2), QPointF(x, box._height - border_width -lh))

        else:
            header_theme = box.get_theme(BoxStyler.HEADER)
            top = header_theme.margin.top + box._header_height
            painter.drawLine(QPointF(x, top + lh * 2),
                             QPointF(x, box._height - border_width - lh))

def _paint_hardware_rack(box: 'BoxWidget', painter: QPainter):
    if not box.is_hardware:
        return

    if box._layout is None:
        return

    d = float(canvas.theme.hardware_rack_width)
    sd = d * 0.5

    theme = canvas.theme.hardware_rack
    if box.isSelected():
        theme = theme.selected

    background1 = theme.background_color
    background2 = theme.background2_color

    if background2 is not None:
        hw_gradient = QLinearGradient(
            -d, -d, box._width + d, box._height + d)
        hw_gradient.setColorAt(0, background1)
        hw_gradient.setColorAt(0.5, background2)
        hw_gradient.setColorAt(1, background1)

        painter.setBrush(hw_gradient)
    else:
        painter.setBrush(background1)

    pen = theme.fill_pen
    painter.setPen(pen)
    lh = pen.widthF() / 2.0

    ports_top_in = box._layout.ports_top_in
    ports_top_out = box._layout.ports_top_out
    ports_bottom_in = box._layout.ports_bottom_in
    ports_bottom_out = box._layout.ports_bottom_out

    if box._current_port_mode is not PortMode.BOTH:
        if box._current_port_mode is PortMode.INPUT:
            points = [
                (- lh, - lh),
                (- lh, ports_top_in - lh),
                (- sd, ports_top_in - lh),
                (- d + lh, ports_top_in - sd),
                (- d + lh, - sd),
                (- sd, - d + lh),
                (box._width + sd, - d + lh),
                (box._width + d - lh, -sd),
                (box._width + d - lh, box._height - lh + sd),
                (box._width + sd, box._height + d - lh),
                (- sd, box._height + d - lh),
                (-d + lh, box._height + sd),
                (-d + lh, ports_bottom_in + sd),
                (- sd, ports_bottom_in + lh),
                (- lh, ports_bottom_in + lh),
                (- lh, box._height + lh),
                (box._width + lh, box._height + lh),
                (box._width + lh, - lh)
            ]

        else:
            points = [
                (box._width + lh, - lh),
                (box._width + lh, ports_top_out - lh),
                (box._width + sd, ports_top_out - lh),
                (box._width + d - lh, ports_top_out - sd),
                (box._width + d - lh, - sd),
                (box._width + sd, -d + lh),
                (- sd, -d + lh),
                (-d + lh, - sd),
                (-d + lh, box._height + sd),
                (- sd, box._height + d - lh),
                (box._width + sd, box._height + d - lh),
                (box._width + d - lh, box._height + sd),
                (box._width + d - lh, ports_bottom_out + sd),
                (box._width + sd, ports_bottom_out + lh),
                (box._width + lh, ports_bottom_out + lh),
                (box._width + lh, box._height + lh),
                (-lh, box._height + lh),
                (-lh, -lh)
            ]

        hardware_poly = QPolygonF()
        for xy in points:
            hardware_poly += QPointF(*xy)

        if theme.border_mode == 'minimal':
            painter.drawPolyline([QPointF(*xy) for xy in points[2:6]])
            painter.drawPolyline([QPointF(*xy) for xy in points[10:14]])
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPolygon(hardware_poly)
        else:
            painter.drawPolygon(hardware_poly)
    else:
        top_points = [
            (- lh, - lh),
            (- lh, ports_top_in - lh),
            (- sd, ports_top_in - lh),
            (- d + lh, ports_top_in - sd),
            (- d + lh, - sd),
            (- sd, -d + lh),
            (box._width + sd, -d + lh),
            (box._width + d - lh, - sd),
            (box._width + d - lh, ports_top_out - sd),
            (box._width + d/2, ports_top_out - lh),
            (box._width + lh, ports_top_out - lh),
            (box._width + lh, -lh)
        ]

        bottom_points = [
            (- lh, box._height + lh),
            (- lh, ports_bottom_in + lh),
            (- sd, ports_bottom_in + lh),
            (- d + lh, ports_bottom_in + sd),
            (-d + lh, box._height + sd),
            (- sd, box._height + d - lh),
            (box._width + sd, box._height + d - lh),
            (box._width + d - lh, box._height + sd),
            (box._width + d - lh, ports_bottom_out + sd),
            (box._width + sd, ports_bottom_out + lh),
            (box._width + lh, ports_bottom_out + lh),
            (box._width + lh, box._height + lh)
        ]

        hw_poly_top = QPolygonF()
        for xy in top_points:
            hw_poly_top += QPointF(*xy)

        hw_poly_bottom = QPolygonF()
        for xy in bottom_points:
            hw_poly_bottom += QPointF(*xy)

        if theme.border_mode == 'minimal':
            painter.drawPolyline([QPointF(*xy) for xy in top_points[2:6]])
            painter.drawPolyline([QPointF(*xy) for xy in top_points[6:10]])
            painter.drawPolyline([QPointF(*xy) for xy in bottom_points[2:6]])
            painter.drawPolyline([QPointF(*xy) for xy in bottom_points[6:10]])
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPolygon(hw_poly_top)
            painter.drawPolygon(hw_poly_bottom)
        else:
            painter.drawPolygon(hw_poly_top)
            painter.drawPolygon(hw_poly_bottom)

def _paint_inline_display(box: 'BoxWidget', painter: QPainter):
    if box._plugin_inline is InlineDisplay.DISABLED:
        return
    if not options.inline_displays:
        return

    inwidth  = box._width - box._width_in - box._width_out - 16
    inheight = (box._height - box._header_height
                - box.get_theme().port_spacing - 3)
    scaling  = (canvas.scene.get_scale_factor()
                * canvas.scene.get_device_pixel_ratio_f())

    if (box._plugin_id >= 0
            and box._plugin_id <= MAX_PLUGIN_ID_ALLOWED
            and (box._plugin_inline is InlineDisplay.ENABLED
                    or box._inline_scaling != scaling)):
        data = canvas.cb.inline_display(
            box._plugin_id,
            int(inwidth*scaling), int(inheight*scaling))

        if data is None:
            return

        # invalidate old image first
        del box._inline_image

        box._inline_data = pack(
            "%iB" % (data['height'] * data['stride']), *data['data'])
        box._inline_image = QImage(
            voidptr(box._inline_data), data['width'], data['height'], # type:ignore
            data['stride'], QImage.Format.Format_ARGB32)
        box._inline_scaling = scaling
        box._plugin_inline = InlineDisplay.CACHED

    if box._inline_image is None:
        _logger.warning(
            'inline display image is None for '
            f'{box._plugin_id}, {box._group_name}')
        return

    swidth = box._inline_image.width() / scaling
    sheight = box._inline_image.height() / scaling

    srcx = int(box._width_in
                + (box._width - box._width_in - box._width_out) / 2
                - swidth / 2)
    srcy = int(box._header_height + 1 + (inheight - sheight) / 2)

    painter.drawImage(
        QRectF(srcx, srcy, swidth, sheight), box._inline_image)

def _paint_gui_button(box: 'BoxWidget', painter: QPainter, border: int):
    gui_theme = canvas.theme.gui_button
    if box._gui_visible:
        gui_theme = gui_theme.gui_visible
    else:
        gui_theme = gui_theme.gui_hidden            
    
    gmg = gui_theme.margin
    header_theme = box.get_theme(BoxStyler.HEADER)
    if box.isSelected():
        header_theme = header_theme.selected
    hmg = header_theme.margin
    mg = hmg + gmg
    
    if box._has_side_title():
        if box._current_port_mode is PortMode.INPUT:
            gui_rect = QRectF(
                box._width - box._header_width - border + mg.ports_side,
                mg.top_side + border,
                box._header_width - mg.sided_width,
                box._header_height - mg.sided_height)
        elif box._current_port_mode is PortMode.OUTPUT:
            gui_rect = QRectF(
                border + mg.free_side,
                border + mg.top_side,
                box._header_width - mg.sided_width,
                box._header_height - mg.sided_height)
    else:
        gui_rect = QRectF(
            border + mg.sides,
            border + mg.top,
            box._width - 2 * border - mg.width,
            box._header_height - mg.height)

    radius = gui_theme.border_radius

    painter.setBrush(gui_theme.background_color)
    painter.setPen(gui_theme.fill_pen)
    
    match gui_theme.border_mode:            
        case 'minimal':
            painter.drawPolyline(
                [gui_rect.bottomLeft(),
                gui_rect.topLeft(),
                gui_rect.topRight(),
                gui_rect.bottomRight()]
            )
            painter.setPen(Qt.PenStyle.NoPen)
        case 'sides':
            painter.drawPolyline(
                [gui_rect.bottomLeft(), gui_rect.topLeft()])
            painter.drawPolyline(
                [gui_rect.topRight(), gui_rect.bottomRight()]
            )
            painter.setPen(Qt.PenStyle.NoPen)

    if radius == 0.0:
        painter.drawRect(gui_rect)
    else:
        painter.drawRoundedRect(gui_rect, radius, radius)

def _paint_monitor_deco(box: 'BoxWidget', painter: QPainter, pen_width: int):
    if box._current_port_mode is PortMode.OUTPUT:
        bor_gradient = QLinearGradient(0, 0, box._height, box._height)
    else:
        bor_gradient = QLinearGradient(
            box._width, 0, box._height, box._width - box._height)

    mon_theme = canvas.theme.monitor_decoration
    if box.isSelected():
        mon_theme = mon_theme.selected

    color_main = mon_theme.background_color
    color_alter = mon_theme.background2_color

    if color_alter is not None:
        tot = int(box._height / 20)
        for i in range(tot):
            if i % 2 == 0:
                bor_gradient.setColorAt(i/tot, color_main)
            else:
                bor_gradient.setColorAt(i/tot, color_alter)

        painter.setBrush(bor_gradient)
    else:
        painter.setBrush(color_main)

    BAND_MON_WIDTH = 9
    TRIANGLE_MON_SIZE_TOP = 7
    triangle_mon_size_bottom = 0
    if (box._wrapping_state in (WrappingState.WRAPPING,
                                    WrappingState.UNWRAPPING)
            or (box._wrapping_state is WrappingState.NORMAL
                and box._wrap_triangle_pos is not UnwrapButton.NONE)):
        triangle_mon_size_bottom = 13

    bmw = BAND_MON_WIDTH
    tms_top = TRIANGLE_MON_SIZE_TOP
    tms_bot = triangle_mon_size_bottom

    xside = pen_width
    xband = pen_width + bmw
    xtop = pen_width + bmw + tms_top
    xbot = pen_width + bmw + tms_bot

    if box._current_port_mode is PortMode.INPUT:
        xside = box._width - xside
        xband = box._width - xband
        xtop = box._width - xtop
        xbot = box._width - xbot

    mon_points = [(xside, pen_width),
                    (xtop, pen_width),
                    (xband, pen_width + tms_top),
                    (xband, box._height - tms_bot - pen_width),
                    (xbot, box._height - pen_width),
                    (xside, box._height - pen_width)]
    
    mon_poly = QPolygonF()
    for xy in mon_points:
        mon_poly += QPointF(*xy)
    
    if mon_theme.border_mode == 'minimal':
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(mon_poly)
        painter.setPen(mon_theme.fill_pen)
        painter.drawPolyline([QPointF(*xy) for xy in mon_points[1:5]])
    else:
        painter.setPen(mon_theme.fill_pen)
        painter.drawPolygon(mon_poly)

def _paint_header_lines(box: 'BoxWidget', painter: QPainter):
    ...
    
def _paint_title_lines(box: 'BoxWidget', painter: QPainter,
                       normal_color: QColor):    
    opac_color = QColor(normal_color)
    opac_color.setAlpha(int(normal_color.alpha() / 2))

    text_pen = QPen(normal_color)
    opac_text_pen = QPen(opac_color)

    # draw title lines
    for title_line in box._title_lines:
        painter.setFont(title_line.get_font())

        if title_line.is_little:
            painter.setPen(opac_text_pen)
        else:
            painter.setPen(text_pen)

        if (box.is_monitor()
                and title_line == box._title_lines[-1]
                and box._group_name.endswith(' Monitor')):
            # Title line endswith " Monitor"
            # Draw "Monitor" in yellow
            # but keep the rest in white
            pre_text = title_line.text.rpartition(' Monitor')[0]
            painter.drawText(
                ceil(title_line.x), ceil(title_line.y), pre_text)

            x_pos = title_line.x
            if pre_text:
                t_font = title_line.get_font()
                x_pos += QFontMetrics(t_font).horizontalAdvance(pre_text)
                x_pos += QFontMetrics(t_font).horizontalAdvance(' ')

            painter.setPen(QPen(canvas.theme.monitor_color, 0))
            painter.drawText(ceil(x_pos), ceil(title_line.y), 'Monitor')
        else:
            painter.drawText(ceil(title_line.x), ceil(title_line.y),
                                title_line.text)

def _paint_wrappers(
        box: 'BoxWidget', painter: QPainter, wtheme: StyleAttributer,
        pen_width: int, tr_pen_width: float):
    painter.setPen(wtheme.fill_pen)
    painter.setBrush(wtheme.background_color)

    match box._wrap_triangle_pos:
        case _ if box._wrapping_state in(
                WrappingState.WRAPPED, WrappingState.UNWRAPPING):
            for port_mode in PortMode.INPUT, PortMode.OUTPUT:
                if not box._current_port_mode & port_mode:
                    continue
                
                painter.setPen(wtheme.fill_pen)
                
                if box._has_side_title():
                    side = 8.5
                    ypos = box._height - pen_width - 2.0

                    triangle = QPolygonF()
                    if port_mode is PortMode.INPUT:
                        xpos = pen_width + 2.0
                        triangle += QPointF(xpos, ypos - side)
                        triangle += QPointF(xpos + side, ypos)
                        triangle += QPointF(xpos, ypos)
                    else:
                        xpos = box._width - pen_width - 2.0
                        triangle += QPointF(xpos, ypos - side)
                        triangle += QPointF(xpos - side, ypos)
                        triangle += QPointF(xpos, ypos)
                else:
                    side = 6
                    xpos = pen_width + 2.0
                    ypos = box._height - pen_width - side - 2.0

                    if port_mode is PortMode.OUTPUT:
                        xpos = \
                            box._width - pen_width - 2.0 - 2 * side

                    triangle = QPolygonF()
                    triangle += QPointF(xpos, ypos)
                    triangle += QPointF(xpos + 2 * side, ypos)
                    triangle += QPointF(xpos + side, ypos + side)

                if wtheme.border_mode == 'minimal':
                    painter.drawPolyline(
                        [triangle[0], triangle[2], triangle[1]])
                    painter.setPen(Qt.PenStyle.NoPen)
                painter.drawPolygon(triangle)

        case UnwrapButton.LEFT:
            side = 6
            xpos = 2.0 + pen_width
            ypos = box._height - pen_width - 2.0
            triangle = QPolygonF()
            triangle += QPointF(xpos, ypos)
            triangle += QPointF(xpos + 2 * side, ypos)
            triangle += QPointF(xpos + side, ypos -side)

            if wtheme.border_mode == 'minimal':
                painter.drawPolyline(
                    [triangle[0], triangle[2], triangle[1]])
                painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPolygon(triangle)

        case UnwrapButton.RIGHT:
            side = 6
            xpos = box._width - pen_width - 2 * side - 2.0

            ypos = box._height - pen_width - 2.0
            triangle = QPolygonF()
            triangle += QPointF(xpos, ypos)
            triangle += QPointF(xpos + 2 * side, ypos)
            triangle += QPointF(xpos + side, ypos - side)
            
            if wtheme.border_mode == 'minimal':
                painter.drawPolyline(
                    [triangle[0], triangle[2], triangle[1]])
                painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPolygon(triangle)

        case UnwrapButton.CENTER:
            side = 7
            xpos = (box._width
                    + box._layout._pms.ins_width
                    - box._layout._pms.outs_width) / 2 - side

            ypos = box._height - tr_pen_width / 2.0
            triangle = QPolygonF()
            triangle += QPointF(xpos, ypos)
            triangle += QPointF(xpos + 2 * side, ypos)
            triangle += QPointF(xpos + side, ypos -side)
            
            if wtheme.border_mode == 'minimal':
                painter.drawPolyline(
                    [triangle[0], triangle[2], triangle[1]])
                painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPolygon(triangle)

def _get_gradient(
        color_main: QColor, color_alter: QColor | None,
        width: int, height: int) -> QLinearGradient | QColor:
    if color_alter is None:
        return color_main
    
    max_size = max(width, height)
    box_gradient = QLinearGradient(0, 0, max_size, max_size)
    gradient_size = 20

    box_gradient.setColorAt(0, color_main)
    tot = int(max_size / gradient_size)
    for i in range(tot):
        if i % 2 == 0:
            box_gradient.setColorAt((i/tot) ** 0.7, color_main)
        else:
            box_gradient.setColorAt((i/tot) ** 0.7, color_alter)

    return box_gradient

def paint(box: 'BoxWidget', painter: QPainter, option, widget):
    if canvas.loading_items:
        return

    if box._layout is None:
        return

    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    # define theme for box, wrappers and header lines
    theme = canvas.theme.box
    wtheme = canvas.theme.box_wrapper
    htheme = canvas.theme.box_header
    hltheme = canvas.theme.box_header_line

    if box.is_hardware:
        theme = theme.hardware
        wtheme = wtheme.hardware
        hltheme = hltheme.hardware
    elif box._box_type is BoxType.CLIENT:
        theme = theme.client
        wtheme = wtheme.client
        hltheme = hltheme.client
    elif box.is_monitor():
        theme = theme.monitor
        wtheme = wtheme.monitor
        hltheme = hltheme.monitor

    border_unselected = theme.fill_pen.widthF()
    selected = box.isSelected()
    
    if selected:
        theme = theme.selected
        wtheme = wtheme.selected
        hltheme = hltheme.selected

    bg_image = theme.background_image
    painter_paths = box._painter_paths.get(selected)
    if painter_paths is None:
        _logger.error(f'Ask to paint {box} but no QPainterPath is created')
        return

    main_ppath = painter_paths.get(PaintElement.MAIN)
    header_ppath = painter_paths.get(PaintElement.HEADER)
    anti_header_ppath = painter_paths.get(PaintElement.ANTI_HEADER)

    # draw the background image if exists
    if not bg_image.isNull():
        painter.setBrush(QBrush(bg_image))
        painter.setPen(Qt.PenStyle.NoPen)
        if anti_header_ppath is not None:
            painter.drawPath(anti_header_ppath)
        elif main_ppath is not None:
            painter.drawPath(main_ppath)

    # draw the main rectangle
    pen = theme.fill_pen
    painter.setPen(pen)
    pen_width = pen.widthF()

    painter.setBrush(
        _get_gradient(
            theme.background_color, theme.background2_color,
            box._width, box._height))
    
    painter.setPen(Qt.PenStyle.NoPen)
    
    if anti_header_ppath is not None:
        painter.drawPath(anti_header_ppath)
    elif main_ppath is not None:
        # should not happen
        painter.drawPath(main_ppath)

    _paint_ports_border_lines(box, painter)

    if header_ppath is not None:
        hbg_image = htheme.background_image
        if not hbg_image.isNull():
            painter.setBrush(QBrush(hbg_image))
            painter.drawPath(header_ppath)

        painter.setPen(htheme.fill_pen)
        painter.setBrush(_get_gradient(
            htheme.background_color, htheme.background2_color,
            box._width, box._height))
        painter.drawPath(header_ppath)

    painter.setPen(pen)        
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(main_ppath)

    # draw hardware box decoration (flyrack like)
    _paint_hardware_rack(box, painter)

    # Draw plugin inline display if supported
    _paint_inline_display(box, painter)

    # Draw toggle GUI client button
    if box._can_handle_gui:
        _paint_gui_button(box, painter, border_unselected)

    # draw Pipewire Monitor (or PulseAudio bridges) decorations
    elif box.is_monitor() and box._current_port_mode is not PortMode.BOTH:
        _paint_monitor_deco(box, painter, pen_width)

    # may draw horizontal lines around title (header lines)
    if (box._header_line_left is not None
            and box._header_line_right is not None):
        painter.setPen(hltheme.fill_pen)
        painter.drawLine(QPointF(*box._header_line_left[0:2]),
                            QPointF(*box._header_line_left[2:]))
        painter.drawLine(QPointF(*box._header_line_right[0:2]),
                            QPointF(*box._header_line_right[2:]))

    _paint_title_lines(box, painter, theme.text_color)

    # draw (un)wrapper triangles
    _paint_wrappers(box, painter, wtheme, pen_width, pen.widthF())

    painter.restore()

