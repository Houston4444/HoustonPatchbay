import math
import time
from typing import TYPE_CHECKING
from PyQt5.QtWidgets import QGraphicsPathItem
from PyQt5.QtGui import QPolygonF, QPen, QColor, QBrush, QPainter, QPainterPath
from PyQt5.QtCore import QPointF, Qt, QRectF, QRect

from .init_values import PortMode, PortType, canvas, CanvasItemType, options

if TYPE_CHECKING:
    from .scene import PatchScene

_USE_CYTHON = False

def x_multiply(path: QPainterPath, n_times: int, width: int) -> QPainterPath:
    paths = [path]
        
    while n_times >= 2 ** len(paths):
        new_path = paths[-1].translated(0.0, 0.0)
        new_path.addPath(
            paths[-1].translated(
                width * 2 ** (len(paths) -1), 0.0))
        
        paths.append(new_path)
        
    x_done = 2 ** (len(paths) - 1)
    x_path = paths[-1]
    
    for i in range(len(paths) - 2, -1, -1):
        if 2 ** i <= n_times - x_done:
            x_path.addPath(
                paths[i].translated(x_done * width, 0.0))
            x_done += 2 ** i
    return x_path

def y_multiply(path: QPainterPath, n_times: int, height: int) -> QPainterPath:
    paths = [path]
        
    while n_times >= 2 ** len(paths):
        new_path = paths[-1].translated(0.0, 0.0)
        new_path.addPath(
            paths[-1].translated(
                0.0, height * 2 ** (len(paths) -1)))
        
        paths.append(new_path)
        
    y_done = 2 ** (len(paths) - 1)
    y_path = paths[-1]
    
    for i in range(len(paths) - 2, -1, -1):
        if 2 ** i <= n_times - y_done:
            y_path.addPath(
                paths[i].translated(0.0, y_done * height))
            y_done += 2 ** i
    return y_path

class GridWidget(QGraphicsPathItem):
    def __init__(self, scene: 'PatchScene', style=''):
        QGraphicsPathItem.__init__(self)
        self._scene = scene
        self._style = style
        self._rects = list[QRectF]()
        self.orig_path = QPainterPath()
        self.setPath(QPainterPath(QPointF()))
        self.left_path: QPainterPath = None
        self.right_path: QPainterPath = None
        self.left_path_width = 0.0
        self.right_path_width = 0.0
        self.update_path()

    def grid_path(self):
        path = QPainterPath(QPointF(0.0, 0.0))
        cell_x = options.cell_x
        cell_y = options.cell_y
        
        rect = self._scene.sceneRect()

        x = rect.left()
        x -= x % cell_x
        if x < rect.left():
            x += cell_x

        y = rect.top()
        y -= y % cell_y
        if y < rect.top():
            y += cell_y

        while x <= rect.right():
            path.moveTo(QPointF(x, rect.top()))
            path.lineTo(QPointF(x, rect.bottom()))
            x += cell_x        

        while y <= rect.bottom():
            path.moveTo(QPointF(rect.left(), y))
            path.lineTo(QPointF(rect.right(), y))
            y += cell_y

        self.setPath(path)
        self.setPen(QPen(
            QBrush(QColor(128, 128, 128, 32)), 0.5, Qt.SolidLine, Qt.FlatCap))
        self.setBrush(QBrush(Qt.NoBrush))

    def update_path(self, rect=None):
        if self._style == 'chess':
            self.chess_board()
        else:
            self.grid_path()
    
    def chess_board(self):
        start_time = time.time()

        path = QPainterPath(QPointF(0.0, 0.0))
        true_cell_x = float(options.cell_x)
        true_cell_y = float(options.cell_y)
        cell_x = true_cell_x * 5
        cell_y = true_cell_y * 10
        
        print('cellls', cell_x, cell_y)
        
        rect = self._scene.sceneRect()
        
        x = rect.left()
        x -= x % (cell_x * 2)
        x += cell_x / 2.0
        y = rect.top()
        y -= y % (cell_y * 2)
        x_start = x
        y_start = y
        
        x += 2 * cell_x
        y += 2 * cell_y
        
        # make the normal pattern
        orig_path = QPainterPath()
        orig_path.moveTo(x, y)
        orig_path.lineTo(x, y + cell_y)
        orig_path.moveTo(x + cell_x, y + cell_y)
        orig_path.lineTo(x + cell_x, y + 2.0 * cell_y)
        self.orig_path = orig_path

        total_x = math.floor((rect.right() - (x - cell_x / 2)) / (2 * cell_x)) 
        total_y = math.floor((rect.bottom() - y)/ (2 * cell_y))
        
        y_path = y_multiply(orig_path, total_y, 2 * cell_y)
        
        # construct top 
        if rect.top() < y:
            top_path = QPainterPath()
            if y - rect.top() > cell_y:
                top_path.moveTo(x, rect.top())
                top_path.lineTo(x, y - cell_y)
                top_path.moveTo(x + cell_x, y - cell_y)
                top_path.lineTo(x + cell_x, y)
            else:
                top_path.moveTo(x + cell_x, rect.top())
                top_path.lineTo(x + cell_x, y)

            y_path.addPath(top_path)
        
        # construct bottom
        if rect.bottom() > y + total_y * 2 * cell_y:
            bot_path = QPainterPath()
            y_down = y + total_y * 2 * cell_y

            if rect.bottom() - y_down > cell_y:
                bot_path.moveTo(x, y_down)
                bot_path.lineTo(x, y_down + cell_y)
                bot_path.moveTo(x + cell_x, y_down + cell_y)
                bot_path.lineTo(x + cell_x, rect.bottom())
            else:
                bot_path.moveTo(x, y_down)
                bot_path.lineTo(x, rect.bottom())

            y_path.addPath(bot_path)

        x_path = x_multiply(y_path, total_x, cell_x * 2)

        sec_left_path = None

        # construct left
        if rect.left() < x - cell_x / 2:
            if x - cell_x / 2 - rect.left() > cell_x:
                left_path = QPainterPath()
                left_width = x - cell_x / 2 - cell_x - rect.left()
                left_path.moveTo(rect.left() + left_width / 2, y)
                left_path.lineTo(rect.left() + left_width / 2, y + cell_y)
                
                sec_left_path = QPainterPath()
                sec_left_path.moveTo(x - cell_x, y + cell_y)
                sec_left_path.lineTo(x - cell_x, y + 2 * cell_y)
                
                sec_lef_path = y_multiply(sec_left_path, total_y, cell_y * 2)
                    
                x_path.addPath(sec_lef_path)
                
            else:
                left_path = QPainterPath()
                left_width = x - cell_x / 2 - rect.left()
                left_path.moveTo(rect.left() + left_width / 2, y + cell_y)
                left_path.lineTo(rect.left() + left_width / 2, y + 2 * cell_y)
            
            self.left_path_width = left_width
            self.left_path = y_multiply(left_path, total_y, cell_y * 2)
        else:
            self.left_path = None
        
        right_x = x - cell_x / 2 + total_x * 2 * cell_x
        print('qplef', right_x, rect.right())

        # construct right
        if rect.right() > right_x:
            if rect.right() >= right_x + cell_x:
                sec_right_path = QPainterPath()
                sec_right_path.moveTo(right_x + cell_x / 2, y)
                sec_right_path.lineTo(right_x + cell_x / 2, y + cell_y)
                sec_rig_path = y_multiply(sec_right_path, total_y, cell_y * 2)
                x_path.addPath(sec_rig_path)
                
                right_path = QPainterPath()
                right_width = rect.right() - (right_x + cell_x)
                right_path.moveTo(right_x + cell_x + right_width / 2, y + cell_y)
                right_path.lineTo(right_x + cell_x + right_width / 2, y + 2 * cell_y)
            else:
                right_path = QPainterPath()
                right_width = rect.right() - right_x
                right_path.moveTo(right_x + right_width / 2, y)
                right_path.lineTo(right_x + right_width / 2, y + cell_y)
            
            self.right_path_width = right_width
            self.right_path = y_multiply(right_path, total_y, cell_y * 2)
        else:
            self.right_path = None
            
        

        # self.left_path = left_path
        

        path.setFillRule(Qt.WindingFill)
        
        self.setPath(x_path)
        self.setPen(QPen(
            QBrush(QColor(28, 28, 28)), cell_x, Qt.SolidLine, Qt.FlatCap))
        finish_time = time.time()
        print('ça prend : ', (finish_time - start_time) * 1000, 'ms')
        
    def paint(self, painter: QPainter, option, widget):
        # return super().paint(painter, option, widget)
        if canvas.loading_items:
            return
        
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        
        QGraphicsPathItem.paint(self, painter, option, widget)

        cosm_pen = QPen(self.pen())
        # cosm_pen.setCosmetic(True)
        # cosm_pen.setWidthF(1.00001)

        painter.setPen(cosm_pen)
        # self.setPen(QPen(Qt.NoPen))
        # self.setBrush(QBrush(QColor(256, 128, 128)))
        
        # for rect in self._rects:
        #     painter.drawRect(rect)
        # painter.fillPath(self.path(), QColor(256, 0, 0))
        # painter.setViewport(self._scene.sceneRect().toRect())
        painter.drawPath(self.path())
        
        if self.left_path is not None:
            pen = QPen(self.pen())
            pen.setWidthF(self.left_path_width)
            painter.setPen(pen)
            painter.drawPath(self.left_path)
        
        if self.right_path is not None:
            pen = QPen(self.pen())
            pen.setWidthF(self.right_path_width)
            painter.setPen(pen)
            painter.drawPath(self.right_path)
        
        # painter.setPen(QPen(QBrush(QColor(128, 64, 0)), 41.0, Qt.SolidLine, Qt.FlatCap))
        # painter.drawPath(self.orig_path)
        # for rect in self._rects:
        #     painter.fillRect(rect, QColor(256, 0, 0))
        # self.path().setFillRule()

        painter.restore()