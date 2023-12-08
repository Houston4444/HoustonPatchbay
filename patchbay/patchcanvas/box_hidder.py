from typing import TYPE_CHECKING, Optional
from PyQt5.QtWidgets import QGraphicsItem
from PyQt5.QtGui import QPainter, QPen, QBrush, QPolygonF
from PyQt5.QtCore import QRectF, Qt, QPointF

from .init_values import canvas, ZvBox, PortMode

if TYPE_CHECKING:
    from .box_widget import BoxWidget


class BoxHidder(QGraphicsItem):
    def __init__(self, parent: Optional['QGraphicsItem'] = ...):
        super().__init__(parent)
        self.setZValue(ZvBox.HIDDER.value)
        self._hide_ratio = 0.0
        
    def set_hide_ratio(self, ratio: float):
        self._hide_ratio = ratio ** 1.5
        self.update()
        
    def parentItem(self) -> 'BoxWidget':
        return super().parentItem()
    
    def boundingRect(self) -> QRectF:
        return self.parentItem().boundingRect()
    
    def paint(self, painter: QPainter, option, widget):
        # return super().paint(painter, option, widget)
        painter.save()
        orig_rect = self.parentItem().boundingRect()
        # rect = QRectF(orig_rect)
        # rect.setHeight(rect.height() * self._hide_ratio)
        # rect.translate(0.0, self.parentItem().boundingRect().height() * (1 - self._hide_ratio))

        box_theme = self.parentItem().get_theme()
        # radius = box_theme.border_radius()
        
        pen = box_theme.fill_pen()
        lh = pen.widthF() / 2.0
        square_side = orig_rect.width() + orig_rect.height()
        right = orig_rect.right() - lh
        bottom = orig_rect.bottom() - lh
        left = orig_rect.left() + lh
        top = orig_rect.top() + lh
        ratio = self._hide_ratio
        th_top = bottom - square_side * ratio
        th_left = right - square_side * ratio
        th_right = left + square_side * ratio
        
        if self.parentItem().get_port_mode() & PortMode.OUTPUT:
            points = [(right, bottom),
                      (right, max(th_top, top))]
            
            if th_top < top:
                points += [(max(left, right - (top - th_top)), top)]
                
            if th_left < left:
                points += [(left, max(top, bottom - (left - th_left)))]
            
            points += [(max(left, th_left), bottom),
                       (right, bottom)]
        else:
            points = [(left, bottom),
                      (left, max(th_top, top))]
            
            if th_top < top:
                points += [(min(right, left + (top - th_top)), top)]
                
            if th_right > right:
                points += [(right, max(top, bottom - (th_right - right)))]
            
            points += [(min(right, th_right), bottom),
                       (left, bottom)]
        
        polygon = QPolygonF()
        for xy in points:
            polygon += QPointF(*xy)

        if canvas.theme.scene_background_image is not None:
            painter.setPen(QPen(Qt.NoPen))
            bg_brush = QBrush()
            bg_brush.setTextureImage(canvas.theme.scene_background_image)
            painter.setBrush(bg_brush)
            # if radius:
            #     painter.drawRoundedRect(rect, radius, radius)
            # else:
            #     painter.drawRect(rect)
            painter.drawPolygon(polygon)
            
        painter.setPen(box_theme.fill_pen())
        painter.setBrush(canvas.theme.scene_background_color)
        # if radius:
        #     painter.drawRoundedRect(rect, radius, radius)
        # else:
        #     # painter.drawRect(rect)
        #     painter.drawRect(rect)
        painter.drawPolygon(polygon)
        
        painter.restore()
        