import logging
from pathlib import Path

from qtpy.QtGui import QPixmap


_logger = logging.getLogger(__name__)
_dark_images_cache = dict[str, QPixmap]()
_light_images_cache = dict[str, QPixmap]()
resources_path = Path(__file__).parents[2] / 'resources'

def pixmap(rel_path: str, dark=True) -> QPixmap:
    images_cache = _dark_images_cache if dark else _light_images_cache
    if rel_path in images_cache:
        return images_cache[rel_path]
    
    img_path = resources_path / rel_path
    try:
        pixmap = QPixmap(str(img_path))
    except:
        _logger.warning(f'Failed to find pixmap in resources: {rel_path}')
        pixmap = QPixmap()
        
    images_cache[rel_path] = pixmap
    return pixmap
