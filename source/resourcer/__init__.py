import logging
from pathlib import Path

from qtpy.QtGui import QPixmap, QIcon, QFontDatabase, QGuiApplication


_logger = logging.getLogger(__name__)
_dark_pixmaps_cache = dict[str, QPixmap]()
_light_pixmaps_cache = dict[str, QPixmap]()
resources_paths = [Path(__file__).parents[2] / 'resources']


def _get_path(rel_path: str, dark=True) -> Path:
    img_path = Path()
    
    for resources_path_ in resources_paths:
        scalables = resources_path_ / 'scalables'
        if not scalables.is_dir():
            continue

        if dark:
            img_path = scalables / 'dark' / rel_path
        else:
            img_path = scalables / 'light' / rel_path

        if not img_path.is_file():
            if dark:
                img_path = scalables / 'light' / rel_path
            else:
                img_path = scalables / 'dark' / rel_path
        
        if img_path.is_file():
            return img_path
    
    _logger.warning(f'No scalable found: {rel_path}')
    return img_path

def pixmap(rel_path: str, dark=True) -> QPixmap:
    images_cache = _dark_pixmaps_cache if dark else _light_pixmaps_cache
    if rel_path in images_cache:
        return images_cache[rel_path]

    img_path = _get_path(rel_path, dark=dark)
    if not img_path.is_file():
        _logger.warning(
            f'Failed to find scalable pixmap {rel_path} {dark=}')
        return QPixmap()

    try:
        pixmap = QPixmap(str(img_path))
    except:
        _logger.warning(f'Failed to find pixmap in resources: {rel_path}')
        pixmap = QPixmap()
        
    images_cache[rel_path] = pixmap
    return pixmap

def icon(rel_path: str, dark=True) -> QIcon:
    return QIcon(pixmap(rel_path, dark=dark))

def main_icon() -> QIcon:
    app_name = QGuiApplication.applicationName().lower()
    for resources_path_ in resources_paths:
        main_icon_svg = \
            resources_path_ / 'main_icon' / 'scalable' / f'{app_name}.svg'
        if main_icon_svg.is_file():
            return QIcon(str(main_icon_svg))
    return QIcon()

def icon_path(rel_path: str, dark=True) -> str:
    return str(_get_path(rel_path, dark=dark))

def install_fonts():
    for resources_path_ in resources_paths:
        fonts_dir = resources_path_ / 'fonts'
        if not fonts_dir.is_dir():
            continue
        
        for font_file in fonts_dir.iterdir():
            if font_file.is_file() and font_file.name.endswith('.ttf'):
                QFontDatabase.addApplicationFont(str(font_file))
