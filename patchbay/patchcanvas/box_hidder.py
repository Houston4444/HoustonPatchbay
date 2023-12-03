from typing import TYPE_CHECKING, Optional
from PyQt5.QtWidgets import QGraphicsItem
from PyQt5.QtGui import QPainter, QPen, QBrush
from PyQt5.QtCore import QRectF, Qt

from .init_values import canvas, Zv

if TYPE_CHECKING:
    from .box_widget import BoxWidget


class BoxHidder(QGraphicsItem):
    def __init__(self, parent: Optional['QGraphicsItem'] = ...):
        super().__init__(parent)
        self._orig_rect = self.parentItem().boundingRect()

        self.setZValue(Zv.BOX_HIDDER.value)
        self._hide_ratio = 0.0
        
    def set_hide_ratio(self, ratio: float):
        self._hide_ratio = ratio
        print('raiooo', ratio)
        self.update()
        
    def parentItem(self) -> 'BoxWidget':
        return super().parentItem()
    
    def boundingRect(self) -> QRectF:
        return self._orig_rect
    
    def paint(self, painter: QPainter, option, widget):
        # return super().paint(painter, option, widget)
        painter.save()
        rect = QRectF(self._orig_rect)
        rect.setHeight(rect.height() * self._hide_ratio)
        # left_rect = QRectF(rect)
        # left_rect.setRight(rect.width() * 0.5 * self._hide_ratio)
        # right_rect = QRectF(rect)
        # right_rect.setLeft(rect.right() - rect.width() * 0.5 * self._hide_ratio)

        box_theme = self.parentItem().get_theme()
        # if self.parentItem().isSelected():
        #     box_theme = box_theme.selected
        radius = box_theme.border_radius()
        
        if canvas.theme.scene_background_image is not None:
            painter.setPen(QPen(Qt.NoPen))
            bg_brush = QBrush()
            bg_brush.setTextureImage(canvas.theme.scene_background_image)
            painter.setBrush(bg_brush)
            if radius:
                painter.drawRoundedRect(rect, radius, radius)
            else:
                painter.drawRect(rect)
            
        painter.setPen(box_theme.fill_pen())
        painter.setBrush(canvas.theme.scene_background_color)
        if radius:
            painter.drawRoundedRect(rect, radius, radius)
        else:
            # painter.drawRect(rect)
            painter.drawRect(rect)
        
        painter.restore()
        