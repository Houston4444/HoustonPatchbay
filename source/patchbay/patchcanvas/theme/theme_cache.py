import logging
import pickle
from typing import TypeAlias

from .. import xdg


_logger = logging.getLogger(__name__)

TitleCache: TypeAlias = dict[str, dict[int, list[dict[str, int]]]]

# if for some reason cache may be incompatible with this version
# of the patchbay, we need to discard the cache files.
CACHE_VERSION = (1, 4)

title_templates_cache: dict[str, dict[str, dict[str, TitleCache]]] = \
    {'CACHE_VERSION': CACHE_VERSION} # type:ignore
font_metrics_cache: dict[str, dict[str, dict[str, dict[str, float]]]] = \
    {'CACHE_VERSION': CACHE_VERSION} # type:ignore


def load():
    cache_file = xdg.xdg_cache_home() / 'HoustonPatchbay' / 'patchbay_titles'
    if not cache_file.is_file():
        return

    with open(cache_file, 'rb') as f:
        try:
            title_templates_cache_ = pickle.load(f)
            assert title_templates_cache_['CACHE_VERSION'] == CACHE_VERSION
            title_templates_cache.clear()
            title_templates_cache.update(title_templates_cache_)
        except:
            _logger.warning(f"failed to load cache {cache_file}")
            return

    font_cache_file = xdg.xdg_cache_home() / 'HoustonPatchbay' / 'patchbay_fonts'
    if not font_cache_file.is_file():
        return

    with open(font_cache_file, 'rb') as f:
        try:
            font_metrics_cache_ = pickle.load(f)
            assert font_metrics_cache_['CACHE_VERSION'] == CACHE_VERSION
            font_metrics_cache.clear()
            font_metrics_cache.update(font_metrics_cache_)
        except:
            _logger.error(f"failed to load font cache {font_cache_file}")
            return

def save():
    cache_dir = xdg.xdg_cache_home() / 'HoustonPatchbay'
    if not cache_dir.is_dir():
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
        except:
            return

    with open(cache_dir / 'patchbay_titles', 'wb') as f:
        pickle.dump(title_templates_cache, f)

    with open(cache_dir / 'patchbay_fonts', 'wb') as f:
        pickle.dump(font_metrics_cache, f)
        
def get_font_metrics_cache(
        font_name: str, font_size: str, font_width: str) -> dict[str, float]:
    if not font_name in font_metrics_cache.keys():
        font_metrics_cache[font_name] = \
            dict[str, dict[str, dict[str, float]]]()

    if not font_size in font_metrics_cache[font_name].keys():
        font_metrics_cache[font_name][font_size] = \
            dict[str, dict[str, float]]()

    if not font_width in font_metrics_cache[font_name][font_size].keys():
        font_metrics_cache[font_name][font_size][font_width] = \
            dict[str, float]()

    return font_metrics_cache[font_name][font_size][font_width]

def get_title_templates_cache(
        font_name: str, font_size: str, font_width: str) -> TitleCache:
    if not font_name in title_templates_cache.keys():
        title_templates_cache[font_name] = \
            dict[str, dict[str, TitleCache]]()

    if not font_size in title_templates_cache[font_name].keys():
        title_templates_cache[font_name][font_size] = dict[str, TitleCache]()

    if not font_width in title_templates_cache[font_name][font_size].keys():
        title_templates_cache[font_name][font_size][font_width] = TitleCache()

    return title_templates_cache[font_name][font_size][font_width]