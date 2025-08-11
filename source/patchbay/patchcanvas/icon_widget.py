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

import logging
import os

from qtpy.QtCore import QRectF, QFile, Qt
from qtpy.QtGui import QPainter, QIcon, QPixmap
from qtpy.QtWidgets import QGraphicsPixmapItem
from qtpy.QtSvg import QSvgRenderer
try:
    from qtpy.QtSvgWidgets import QGraphicsSvgItem
except:
    from qtpy.QtSvg import QGraphicsSvgItem

from patshared import BoxType, PortMode
from .init_values import CanvasSceneMissing, CanvasThemeMissing, canvas, CanvasItemType


_logger = logging.getLogger(__name__)
_app_icons_cache = {}
_icons_pixmaps_cache = dict[QIcon, dict[int, QPixmap]]()


def get_app_icon(icon_name: str) -> QIcon:
    if icon_name in _app_icons_cache.keys():
        return _app_icons_cache[icon_name]
    
    icon = QIcon.fromTheme(icon_name)

    if icon.isNull():
        for ext in ('svg', 'svgz', 'png'):
            filename = ":app_icons/%s.%s" % (icon_name, ext)

            if QFile.exists(filename):
                del icon
                icon = QIcon()
                icon.addFile(filename)
                break

    if icon.isNull():
        for path in ('/usr/local', '/usr', '%s/.local' % os.getenv('HOME')):
            for ext in ('png', 'svg', 'svgz', 'xpm'):
                filename = "%s/share/pixmaps/%s.%s" % (path, icon_name, ext)
                if QFile.exists(filename):
                    del icon
                    icon = QIcon()
                    icon.addFile(filename)
                    break

    _app_icons_cache[icon_name] = icon

    return icon


class IconPixmapWidget(QGraphicsPixmapItem):
    def __init__(self, box_type: BoxType, icon_name: str, parent):
        if canvas.theme is None:
            raise CanvasThemeMissing
        
        QGraphicsPixmapItem.__init__(self, parent)

        box_theme = canvas.theme.box
        if box_type is BoxType.CLIENT:
            box_theme = box_theme.client

        self._icon_size = box_theme.icon_size()
        self.icon = None
        self._pixmaps_cache = dict[int, QPixmap]()

        self.set_icon(box_type, icon_name)

    def set_icon(self, box_type: BoxType, name: str, port_mode=PortMode.NULL):
        if canvas.scene is None:
            raise CanvasSceneMissing
        
        self.icon = get_app_icon(name)

        if not self.icon.isNull():
            scale = canvas.scene.get_zoom_scale()
            pix_size = int(0.5 + self._icon_size * scale)
            
            self_icon_pix_cache = _icons_pixmaps_cache.get(self.icon)
            if self_icon_pix_cache is None:
                self_icon_pix_cache = dict[int, QPixmap]()
                _icons_pixmaps_cache[self.icon] = self_icon_pix_cache
                
            pixmap = self_icon_pix_cache.get(pix_size)
            if pixmap is None:
                pixmap = self.icon.pixmap(pix_size, pix_size)
                self_icon_pix_cache[pix_size] = pixmap

            self.setPixmap(pixmap)

            self.setScale(1.0 / scale)
            self.setPos(4.0, 4.0)
        else:
            _icons_pixmaps_cache[self.icon] = {}

    def update_zoom(self, scale: float):
        if self.icon is None or scale <= 0.0:
            return

        pix_size = int(0.5 + self._icon_size *scale)
        pixmap = _icons_pixmaps_cache[self.icon].get(pix_size)
        
        if pixmap is None:
            pixmap = self.icon.pixmap(pix_size, pix_size)
            _icons_pixmaps_cache[self.icon][pix_size] = pixmap

        self.setPixmap(pixmap)
        self.setScale(1.0 / scale)

    def is_null(self) -> bool:
        if self.icon is None:
            return True

        return self.icon.isNull()

    def set_pos(self, x: int, y: int):
        self.setPos(float(x), float(y))
        
    def type(self) -> CanvasItemType:
        return CanvasItemType.ICON


class IconSvgWidget(QGraphicsSvgItem): # type:ignore
    def __init__(self, box_type: BoxType, name: str, port_mode: PortMode, parent):
        super().__init__(parent)
        self._renderer = None
        self._size = QRectF(4, 4, 24, 24)
        self._icon_size = 24
        self.set_icon(box_type, name, port_mode)

    def set_icon(self, box_type: BoxType, name: str, port_mode: PortMode):
        if canvas.theme is None:
            raise CanvasThemeMissing
        
        name = name.lower()
        icon_path = ""
        theme = canvas.theme.icon
        box_theme = canvas.theme.box

        match box_type:
            case BoxType.APPLICATION:
                self._size = QRectF(3, 2, 19, 18)

                if "audacious" in name:
                    icon_path = ":/scalable/pb_audacious.svg"
                    self._size = QRectF(5, 4, 16, 16)
                elif "clementine" in name:
                    icon_path = ":/scalable/pb_clementine.svg"
                    self._size = QRectF(5, 4, 16, 16)
                elif "distrho" in name:
                    icon_path = ":/scalable/pb_distrho.svg"
                    self._size = QRectF(5, 4, 16, 16)
                elif "jamin" in name:
                    icon_path = ":/scalable/pb_jamin.svg"
                    self._size = QRectF(5, 3, 16, 16)
                elif "mplayer" in name:
                    icon_path = ":/scalable/pb_mplayer.svg"
                    self._size = QRectF(5, 4, 16, 16)
                elif "vlc" in name:
                    icon_path = ":/scalable/pb_vlc.svg"
                    self._size = QRectF(5, 3, 16, 16)
                else:
                    icon_path = ":/scalable/pb_generic.svg"
                    self._size = QRectF(4, 4, 24, 24)

            case BoxType.HARDWARE:
                box_theme = box_theme.hardware
                icon_size = int(box_theme.icon_size())
                self._size = QRectF(4, 4, icon_size, icon_size)
                self._icon_size = icon_size

                if name == "a2j":
                    icon_path = theme.hardware_midi
                else:
                    if port_mode is PortMode.INPUT:
                        icon_path = theme.hardware_playback
                    elif port_mode is PortMode.OUTPUT:
                        icon_path = theme.hardware_capture
                    else:
                        icon_path = theme.hardware_grouped

            case BoxType.DISTRHO:
                icon_path = ":/scalable/pb_distrho.svg"
                self._size = QRectF(5, 4, 16, 16)

            case BoxType.FILE:
                icon_path = ":/scalable/pb_file.svg"
                self._size = QRectF(5, 4, 16, 16)

            case BoxType.PLUGIN:
                icon_path = ":/scalable/pb_plugin.svg"
                self._size = QRectF(5, 4, 16, 16)

            case BoxType.LADISH_ROOM:
                icon_path = ":/scalable/pb_hardware.svg"
                self._size = QRectF(5, 2, 16, 16)

            case BoxType.MONITOR:
                box_theme = box_theme.monitor
                icon_size = int(box_theme.icon_size())
                self._size = QRectF(4, 4, icon_size, icon_size)
                self._icon_size = icon_size
                
                if name == 'monitor_capture':
                    icon_path = theme.monitor_capture
                elif name == 'monitor_playback':
                    icon_path = theme.monitor_playback
                else:
                    icon_path = ":/canvas/dark/" + name

            case _:
                self._size = QRectF(0, 0, 0, 0)
                _logger.warning(f"set_icon({str(box_type)}, {name})"
                                " - unsupported icon requested")
                return

        self._renderer = QSvgRenderer(icon_path, canvas.scene)
        self._renderer.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        self.setSharedRenderer(self._renderer)
        self.update()
        
    def update_zoom(self, scale: float):
        pass

    def type(self) -> CanvasItemType:
        return CanvasItemType.ICON

    def is_null(self) -> bool:
        return False

    def set_pos(self, x: int, y: int):
        self._size = QRectF(x, y, self._icon_size, self._icon_size)

    def boundingRect(self):
        return self._size

    def paint(self, painter: QPainter, option, widget):
        if not self._renderer:
            QGraphicsSvgItem.paint(self, painter, option, widget) # type:ignore
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, False)
        self._renderer.render(painter, self._size)
        painter.restore()

# ------------------------------------------------------------------------------------------------------------



