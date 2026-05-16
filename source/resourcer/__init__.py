import logging
from pathlib import Path

from qtpy.QtGui import QPixmap, QIcon, QFontDatabase


_logger = logging.getLogger(__name__)
_dark_pixmaps_cache = dict[str, QPixmap]()
_light_pixmaps_cache = dict[str, QPixmap]()
resources_path = Path(__file__).parents[2] / 'resources'
scalables = resources_path / 'scalables'


def _get_path(rel_path: str, dark=True) -> Path:
    if dark:
        img_path = scalables / 'dark' / rel_path
    else:
        img_path = scalables / 'light' / rel_path

    if not img_path.is_file():
        if dark:
            img_path = scalables / 'light' / rel_path
        else:
            img_path = scalables / 'dark' / rel_path
    
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

def icon_path(rel_path: str, dark=True) -> str:
    return str(_get_path(rel_path, dark=dark))

def install_fonts():
    fonts_dir = resources_path / 'fonts'
    for font_file in fonts_dir.iterdir():
        if font_file.is_file() and font_file.name.endswith('.ttf'):
            QFontDatabase.addApplicationFont(str(font_file))
