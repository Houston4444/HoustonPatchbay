#!/usr/bin/python3
import logging
import os
from pathlib import Path
import pickle
from typing import TYPE_CHECKING, TypeAlias, TypedDict, Union, Optional

from qtpy.QtCore import Qt
from qtpy.QtGui import (QColor, QPen, QFont, QBrush, QFontMetricsF,
                         QImage, QFontDatabase)

from . import xdg

_logger = logging.getLogger(__name__)

TitleCache: TypeAlias = dict[str, dict[str, dict[int, list[dict[str, int]]]]]


def _to_qcolor(color: str) -> Optional[QColor]:
    ''' convert a color given with a string to a QColor.
    returns None if color has a incorrect value.'''
    if not isinstance(color, str):
        return None

    intensity_ratio = 1.0
    opacity_ratio = 1.0
    
    if color.startswith('-'):
        color = color.partition('-')[2].strip()
        intensity_ratio = - 1.0

    if '*' in color:
        words = color.split('*')
        next_for_opac = False
        
        for i, word in enumerate(words):
            if i == 0:
                color = word.strip()
                continue
            
            if not word:
                next_for_opac = True
                continue
            
            if next_for_opac:
                try:
                    opacity_ratio *= float(word.strip())
                except:
                    pass
            
                next_for_opac = False
                continue
            
            try:
                intensity_ratio *= float(word.strip())
            except:
                pass
    
    if color.startswith('rgb(') and color.endswith(')'):
        try:
            channels = [int(c.strip()) for c in
                        color.partition('(')[2].rpartition(')')[0].split(',')]
            assert len(channels) == 3
            qcolor = QColor(*channels)
        except:
            return None
    
    elif color.startswith('rgba(') and color.endswith(')'):
        try:
            values = [c.strip() for c in
                      color.partition('(')[2].rpartition(')')[0].split(',')]
            assert len(values) == 4
            qcolor = QColor(*[int(v) for v in values[:3]],
                            int(float(values[3]) * 255)) # type:ignore
        except:
            return None
    
    else:
        qcolor = QColor(color)

    if not qcolor.isValid():
        return None

    if intensity_ratio == 1.0 and opacity_ratio == 1.0:
        return qcolor
    
    if intensity_ratio < 0.0:
        qcolor = QColor(
            255 - qcolor.red(), 255 - qcolor.green(),
            255 - qcolor.blue(), qcolor.alpha())
    
    if opacity_ratio != 1.0:
        qcolor.setAlphaF(opacity_ratio * qcolor.alphaF())
    
    return qcolor.lighter(int(100 * intensity_ratio))

def rail_float(value, mini: float, maxi: float) -> float:
    return max(min(float(value), float(maxi)), float(mini))

def rail_int(value, mini: int, maxi: int) -> int:
    return max(min(int(value), int(maxi)), int(mini))


class StyleAttributer:
    def __init__(self, path: str, parent=None):
        self.subs = list[str]()

        self._border_color = None
        self._border_width = None
        self._border_style = None
        self._border_radius = None
        self._background_color = None
        self._background2_color = None
        self._background_image = None
        self._text_color = None
        self._font_name = None
        self._font_size = None
        self._font_width = None

        self._port_offset = None
        self._port_in_offset = None
        self._port_out_offset = None
        self._port_in_offset_mode = None
        self._port_out_offset_mode = None
        self._port_spacing = None
        self._port_type_spacing = None
        self._box_footer = None
        self._icon_size = None

        self._grid_min_width = None
        self._grid_min_height = None

        self._path = path
        self._parent = parent

        self._fill_pen = None
        self._font = None
        self._font_metrics_cache: Optional[dict[str, float]] = None
        self._titles_templates_cache: Optional[TitleCache] = None
        
        if TYPE_CHECKING:
            assert isinstance(self._parent, StyleAttributer)

    def set_attribute(self, attribute: str, value):
        err = False
        match attribute:
            case 'border-color':
                self._border_color = _to_qcolor(value)
                if self._border_color is None:
                    err = True
                    
            case 'border-width':
                if isinstance(value, (int, float)):
                    self._border_width = rail_float(value, 0, 20)
                else:
                    err = True
                    
            case 'border-style':
                if isinstance(value, str):
                    value = value.lower()
                    match value:
                        case 'solid'|'normal':
                            self._border_style = Qt.PenStyle.SolidLine
                        case 'nopen'|'none':
                            self._border_style = Qt.PenStyle.NoPen
                        case 'dash':
                            self._border_style = Qt.PenStyle.DashLine
                        case 'dashdot':
                            self._border_style = Qt.PenStyle.DashDotLine
                        case 'dashdotdot':
                            self._border_style = Qt.PenStyle.DashDotDotLine
                        case _:
                            err = True
                else:
                    err = True

            case 'border-radius':
                if isinstance(value, (int, float)):
                    self._border_radius = rail_float(value, 0, 50)
                else:
                    err = True

            case 'background':
                self._background_color = _to_qcolor(value)
                if self._background_color is None:
                    err = True
                    
            case 'background2':
                self._background2_color = _to_qcolor(value)
                if self._background2_color is None:
                    err = True

            case 'background-image':
                image_path = (Theme.theme_file_path.parent
                              / 'images' / str(value))
                if image_path.is_file():
                    self._background_image = QImage(str(image_path))
                    self._background_image.setDevicePixelRatio(3.0)
                    if self._background_image.isNull():
                        self._background_image = None
                else:
                    self._background_image = None
            
            case 'text-color':
                self._text_color = _to_qcolor(value)
                if self._text_color is None:
                    err = True
                    
            case 'font-name':
                if isinstance(value, str):
                    self._font_name = value

                    # add the font to database if it is an embedded font
                    for ext in ('ttf', 'otf'):
                        embedded_path = (Theme.theme_file_path.parent
                                        / 'fonts' / f"{value}.{ext}")
                        if embedded_path.is_file():
                            QFontDatabase.addApplicationFont(
                                str(embedded_path))
                            break
                    
                else:
                    err = True
                    
            case 'font-size':
                if isinstance(value, (int, float)):
                    self._font_size = rail_int(value, 1, 200)
                else:
                    err = True
                    
            case 'font-width':
                if isinstance(value, (int, float)):
                    self._font_width = rail_int(value, 0, 99)
                elif isinstance(value, str):
                    value = value.lower()
                    if value == 'normal':
                        self._font_state = QFont.Weight.Normal
                    elif value == 'bold':
                        self._font_state = QFont.Weight.Bold
                    else:
                        err = True
                else:
                    err = True
            
            case 'port-offset':
                if isinstance(value, (int, float)):
                    self._port_offset = rail_float(value, -20, 20)
                else:
                    err = True
            
            case 'port-in-offset':
                if isinstance(value, (int, float)):
                    self._port_in_offset = rail_float(value, -20, 20)
                else:
                    err = True
                    
            case 'port-out-offset':
                if isinstance(value, (int, float)):
                    self._port_out_offset = rail_float(value, -20, 20)
                else:
                    err = True
            
            case 'port-in-offset-mode':
                if isinstance(value, str):
                    self._port_in_offset_mode = value
                else:
                    err = True

            case 'port-out-offset-mode':
                if isinstance(value, str):
                    self._port_out_offset_mode = value
                else:
                    err = True
            
            case 'port-spacing':
                if isinstance(value, (int, float)):
                    self._port_spacing = rail_float(value, 0, 100)
                else:
                    err = True
            
            case 'port-type-spacing':
                if isinstance(value, (int, float)):
                    self._port_type_spacing = rail_float(value, 0, 100)
                else:
                    err = True

            case 'box-footer':
                if isinstance(value, (int, float)):
                    self._box_footer = rail_float(value, 0, 50)
                else:
                    err = True

            case 'icon-size':
                if isinstance(value, (int, float)):
                    self._icon_size = rail_float(value, 8, 1024)
                else:
                    err = True

            case 'grid-min-width':
                if isinstance(value, (int, float)):
                    self._grid_min_width = rail_float(value, 1, 100000)
                else:
                    err = True
                    
            case 'grid-min-height':
                if isinstance(value, (int, float)):
                    self._grid_min_height = rail_float(value, 1, 100000)
                else:
                    err = True

            case _:
                _logger.error(f"{self._path}: unknown key: {attribute}")

        if err:
            _logger.error(
                f"{self._path}: invalid value for {attribute}: {str(value)}")

    def set_style_dict(self, context: str, style_dict: dict):
        if context:
            begin, point, end = context.partition('.')
            
            if begin not in self.subs:
                _logger.error(f"{self._path}: invalid ignored key: {begin}")
                return
            self.__getattribute__(begin).set_style_dict(end, style_dict)
            return
        
        for key, value in style_dict.items():
            self.set_attribute(key, value)
    
    def get_value_of(self, attribute: str, orig_path='', needed_attribute=''):
        '''return the value of given attribute for this theme section.
        if this value is not present in this theme section,
        it will look into parent sections.
        Note that for 'selected' section, it will look in 'selected' section
        of parent before looking in parent section.'''
        if attribute not in self.__dir__():
            _logger.error(f"get_value_of, invalide attribute: {attribute}")
            return None
        
        if not orig_path:
            orig_path = self._path

        for path_end in ('selected',):
            if TYPE_CHECKING:
                assert isinstance(self, UnselectedStyleAttributer)
            
            if (orig_path.endswith('.' + path_end)
                    and path_end in self.subs
                    and self._path + '.' + path_end != orig_path):
                return self.selected.get_value_of(
                    attribute, self._path, needed_attribute)

        if self.__getattribute__(attribute) is None:
            if (needed_attribute
                    and self.__getattribute__(needed_attribute) is not None):
                return None
                
            if self._parent is None:
                _logger.error(
                    f"get value of: {self._path} None value and no parent")
                return None

            return self._parent.get_value_of(
                attribute, orig_path, needed_attribute)

        return self.__getattribute__(attribute)
    
    @property
    def fill_pen(self) -> QPen:
        if self._fill_pen is None:
            if TYPE_CHECKING:
                self._fill_pen = QPen()
            else:
                self._fill_pen = QPen(
                    QBrush(self.get_value_of('_border_color')),
                    self.get_value_of('_border_width'),
                    self.get_value_of('_border_style'))
        
        return self._fill_pen
    
    @property
    def border_radius(self) -> float:
        return self.get_value_of('_border_radius') # type:ignore
    
    @property
    def background_color(self) -> QColor:
        return self.get_value_of('_background_color') # type:ignore
    
    @property
    def background2_color(self) -> Optional[QColor]:
        return self.get_value_of('_background2_color', # type:ignore
                                 needed_attribute='_background_color')
    
    @property
    def background_image(self) -> QImage:
        return self.get_value_of('_background_image') # type:ignore

    @property
    def text_color(self) -> QColor:
        return self.get_value_of('_text_color') # type:ignore
    
    @property
    def font(self) -> QFont:
        if self._font is None:
            self._font = QFont(self.get_value_of('_font_name'))
            self._font.setPixelSize(
                int(self.get_value_of('_font_size'))) # type:ignore
            self._font.setWeight(
                int(self.get_value_of('_font_width'))) # type:ignore
        return self._font
        
    def _get_font_metrics_cache(self) -> dict[str, float]:        
        font_name = str(self.get_value_of('_font_name'))
        font_size = str(self.get_value_of('_font_size'))
        font_width = str(self.get_value_of('_font_width'))
        
        if not font_name in Theme.font_metrics_cache.keys():
            Theme.font_metrics_cache[font_name] = \
                dict[str, dict[str, dict[str, float]]]()
        
        if not font_size in Theme.font_metrics_cache[font_name].keys():
            Theme.font_metrics_cache[font_name][font_size] = \
                dict[str, dict[str, float]]()
        
        if not font_width in Theme.font_metrics_cache[font_name][font_size].keys():
            Theme.font_metrics_cache[font_name][font_size][font_width] = \
                dict[str, float]()
        
        return Theme.font_metrics_cache[font_name][font_size][font_width]
            
    def get_text_width(self, string: str) -> float:
        if self._font_metrics_cache is None:
            self._font_metrics_cache = self._get_font_metrics_cache()
        
        if string in self._font_metrics_cache.keys():
            return self._font_metrics_cache[string]

        tot_size = 0.0
        for s in string:
            if s in self._font_metrics_cache.keys():
                tot_size += self._font_metrics_cache[s]
            else:
                letter_size = QFontMetricsF(self.font).horizontalAdvance(s)
                self._font_metrics_cache[s] = letter_size
                tot_size += letter_size
        
        self._font_metrics_cache[string] = tot_size
        
        return tot_size
    
    @property
    def port_in_offset(self) -> float:
        return self.get_value_of('_port_in_offset') # type:ignore
    
    @property
    def port_out_offset(self) -> float:
        return self.get_value_of('_port_out_offset') # type:ignore
    
    @property
    def port_in_offset_mode(self) -> str:
        return self.get_value_of('_port_in_offset_mode') # type:ignore
    
    @property
    def port_out_offset_mode(self) -> str:
        return self.get_value_of('_port_out_offset_mode') # type:ignore
    
    @property
    def port_spacing(self) -> float:
        return self.get_value_of('_port_spacing') # type:ignore
    
    @property
    def port_type_spacing(self) -> float:
        return self.get_value_of('_port_type_spacing') # type:ignore

    @property    
    def icon_size(self) -> float:
        return self.get_value_of('_icon_size') # type:ignore
    
    @property
    def grid_min_width(self) -> float:
        return self.get_value_of('_grid_min_width') # type:ignore
    
    @property
    def grid_min_height(self) -> float:
        return self.get_value_of('_grid_min_height') # type:ignore
    
    def _get_titles_templates_cache(self) -> TitleCache:
        font_name = str(self.get_value_of('_font_name'))
        font_size = str(self.get_value_of('_font_size'))
        font_width = str(self.get_value_of('_font_width'))
        
        if not font_name in Theme.title_templates_cache.keys():
            Theme.title_templates_cache[font_name] = \
                dict[str, dict[str, TitleCache]]()
        
        if not font_size in Theme.title_templates_cache[font_name].keys():
            Theme.title_templates_cache[font_name][font_size] = \
                dict[str, TitleCache]()
        
        if not font_width in Theme.title_templates_cache[font_name][font_size].keys():
            Theme.title_templates_cache[font_name][font_size][font_width] = \
                TitleCache()
        
        return Theme.title_templates_cache[font_name][font_size][font_width]
            
    def save_title_templates(
            self, title: str, handle_gui: bool, icon_size: int, templates: list):
        if self._titles_templates_cache is None:
            self._titles_templates_cache = self._get_titles_templates_cache()

        if not title in self._titles_templates_cache:
            self._titles_templates_cache[title] = {}

        gui_key = 'with_gui' if handle_gui else 'without_gui'
        
        if not gui_key in self._titles_templates_cache[title]:
            self._titles_templates_cache[title][gui_key] = {}

        self._titles_templates_cache[title][gui_key][icon_size] = templates
    
    def get_title_templates(
            self, title: str, handle_gui: bool, icon_size: int) -> list[dict[str, int]]:
        if self._titles_templates_cache is None:
            self._titles_templates_cache = self._get_titles_templates_cache()
        
        gui_key = 'with_gui' if handle_gui else 'without_gui'
    
        if (title in self._titles_templates_cache
                and gui_key in self._titles_templates_cache[title]
                and icon_size in self._titles_templates_cache[title][gui_key]):
            return self._titles_templates_cache[title][gui_key][icon_size]
        
        return []
    

class UnselectedStyleAttributer(StyleAttributer):
    def __init__(self, path: str, parent=None):
        StyleAttributer.__init__(self, path, parent=parent)
        self.selected = StyleAttributer(path + '.selected', self)
        self.subs.append('selected')


class BoxStyleAttributer(UnselectedStyleAttributer):
    def __init__(self, path: str, parent):
        UnselectedStyleAttributer.__init__(self, path, parent)
        self.hardware = UnselectedStyleAttributer(path + '.hardware', self)
        self.client = UnselectedStyleAttributer(path + '.client', self)
        self.monitor = UnselectedStyleAttributer(path + '.monitor', self)
        self.subs += ['hardware', 'client', 'monitor']


class PortStyleAttributer(UnselectedStyleAttributer):
    def __init__(self, path: str, parent):
        UnselectedStyleAttributer.__init__(self, path, parent)
        self.audio = UnselectedStyleAttributer(path + '.audio', self)
        self.midi = UnselectedStyleAttributer(path + '.midi', self)
        self.cv = UnselectedStyleAttributer(path + '.cv', self)
        self.alsa = UnselectedStyleAttributer(path + '.alsa', self)
        self.video = UnselectedStyleAttributer(path + '.video', self)
        self.subs += ['audio', 'midi', 'cv', 'video', 'alsa']


class LineStyleAttributer(UnselectedStyleAttributer):
    def __init__(self, path: str, parent):
        UnselectedStyleAttributer.__init__(self, path, parent)
        self.audio = UnselectedStyleAttributer(path + '.audio', self)
        self.midi = UnselectedStyleAttributer(path + '.midi', self)
        self.alsa = UnselectedStyleAttributer(path + '.alsa', self)
        self.video = UnselectedStyleAttributer(path + '.video', self)
        self.disconnecting = StyleAttributer(path + '.disconnecting', self)
        self.subs += ['audio', 'midi', 'alsa', 'video', 'disconnecting']


class GuiButtonStyleAttributer(StyleAttributer):
    def __init__(self, path: str, parent):
        StyleAttributer.__init__(self, path, parent)
        self.gui_visible = StyleAttributer('.gui_visible', self)
        self.gui_hidden = StyleAttributer('.gui_hidden', self)
        self.subs += ['gui_visible', 'gui_hidden']


class GridStyleAttributer(StyleAttributer):
    def __init__(self, path: str, parent=None):
        StyleAttributer.__init__(self, path, parent)
        self._grid_min_width = 100.0
        self._grid_min_height = 100.0
        
        self.technical_grid = StyleAttributer('.technical_grid', self)
        self.grid = StyleAttributer('.grid', self)
        self.chessboard = StyleAttributer('.chessboard', self)
        self.subs += ['technical_grid', 'grid', 'chessboard']


class IconTheme:
    def __init__(self):
        src = ':/canvas/dark/'
        self.hardware_capture = src + 'microphone.svg'
        self.hardware_playback = src + 'audio-headphones.svg'
        self.hardware_grouped = src + 'pb_hardware.svg'
        self.hardware_midi = src + 'DIN-5.svg'
        self.monitor_capture = src + 'monitor_capture.svg'
        self.monitor_playback = src + 'monitor_playback.svg'
        
    def read_theme(self, theme_file: Path):
        icons_dir = theme_file.parent / 'icons'
        if not icons_dir.is_dir():
            return
        
        for key in ('hardware_capture', 'hardware_playback', 'hardware_grouped',
                    'hardware_midi', 'monitor_capture', 'monitor_playback'):
            icon_path = icons_dir / f'{key}.svg'
            if icon_path.is_file():
                self.__setattr__(key, str(icon_path))


class FontMetricsCacheType(TypedDict):
    CACHE_VERSION: tuple[int, int]


class Theme(StyleAttributer):
    theme_file_path = Path()
    
    # if for some reason cache may be incompatible with this version
    # of the patchbay, we need to discard the cache files. 
    CACHE_VERSION = (1, 3)
    
    title_templates_cache: dict[str, dict[str, dict[str, TitleCache]]] = \
        {'CACHE_VERSION': CACHE_VERSION} # type:ignore
    font_metrics_cache: dict[str, dict[str, dict[str, dict[str, float]]]] = \
        {'CACHE_VERSION': CACHE_VERSION} # type:ignore 
        # CACHE_VERSION is the only one tuple[int, int]

    def __init__(self):
        StyleAttributer.__init__(self, '')

        # fallbacks values for all (ugly style, but better than nothing)
        self._border_color = QColor('white')
        self._border_width = 1
        self._border_style = Qt.PenStyle.SolidLine
        self._border_radius = 0
        self._background_color = QColor('black')
        self._background2_color = QColor('black')
        self._background_image = QImage()
        self._text_color = QColor('white')
        self._font_name = "Deja Vu Sans"
        self._font_size = 11
        self._font_width = QFont.Weight.Normal # QFont.Weight.Normal is 50

        self._port_spacing = 2
        self._port_type_spacing = 2
        self._port_offset = 0
        self._port_in_offset = 0
        self._port_out_offset = 0
        self._port_in_offset_mode = 'bore'
        self._port_out_offset_mode = 'bore'
        self._box_footer = 0
        self._icon_size = 24

        self.scene_background_color = QColor('black')
        self.scene_background_image = QImage()
        self.monitor_color = QColor(190, 158, 0)
        self.port_height = 16
        
        self.port_grouped_width = 19
        self.box_spacing = 4
        self.box_spacing_horizontal = 24
        self.magnet = 12
        self.hardware_rack_width = 5
        self.thumbnail_port_colors = 'background'

        self.icon = IconTheme()

        self.aliases = {}

        self.box = BoxStyleAttributer('.box', self)
        self.box_wrapper = BoxStyleAttributer('.box_wrapper', self)
        self.box_header_line = BoxStyleAttributer('.box_header_line', self)
        self.box_shadow = BoxStyleAttributer('.box_shadow', self)
        self.portgroup = PortStyleAttributer('.portgroup', self)
        self.port = PortStyleAttributer('.port', self)
        self.line = LineStyleAttributer('.line', self)
        self.rubberband = StyleAttributer('.rubberband', self)
        self.hardware_rack = UnselectedStyleAttributer('.hardware_rack', self)
        self.monitor_decoration = UnselectedStyleAttributer('.monitor_decoration', self)
        self.gui_button = GuiButtonStyleAttributer('.gui_button', self)
        self.grid = GridStyleAttributer('.grid', self)
        
        self.subs += ['box', 'box_wrapper', 'box_header_line', 'box_shadow',
                      'portgroup', 'port', 'line',
                      'rubberband', 'hardware_rack',
                      'monitor_decoration', 'gui_button', 'grid']
    
    @classmethod
    def set_file_path(cls, theme_file_path: Path):
        cls.theme_file_path = theme_file_path
    
    @classmethod
    def load_cache(cls):
        cache_file = xdg.xdg_cache_home() / 'HoustonPatchbay' / 'patchbay_titles'
        if not os.path.isfile(cache_file):
            return

        with open(cache_file, 'rb') as f:
            try:
                title_templates_cache = pickle.load(f)
                # assert isinstance(title_templates_cache, dict)
                # assert 'CACHE_VERSION' in title_templates_cache.keys()
                # assert isinstance(title_templates_cache['CACHE_VERSION'], tuple)
                assert title_templates_cache['CACHE_VERSION'] == cls.CACHE_VERSION
                cls.title_templates_cache = title_templates_cache
            except:
                _logger.warning(f"failed to load cache {cache_file}")
                return
        
        font_cache_file = xdg.xdg_cache_home() / 'HoustonPatchbay' / 'patchbay_fonts'
        if not os.path.isfile(font_cache_file):
            return

        with open(font_cache_file, 'rb') as f:
            try:
                font_metrics_cache = pickle.load(f)
                assert font_metrics_cache['CACHE_VERSION'] == cls.CACHE_VERSION
                cls.font_metrics_cache = font_metrics_cache
            except:
                _logger.error(f"failed to load font cache {font_cache_file}")
                return
    
    @classmethod
    def save_cache(cls):
        cache_dir = xdg.xdg_cache_home() / 'HoustonPatchbay'
        if not cache_dir.is_dir():
            try:
                os.makedirs(cache_dir)
            except:
                return

        with open(cache_dir / 'patchbay_titles', 'wb') as f:
            pickle.dump(cls.title_templates_cache, f)
        
        with open(cache_dir / 'patchbay_fonts', 'wb') as f:
            pickle.dump(cls.font_metrics_cache, f)
    
    def read_theme(self, theme_dict: dict[str, dict], theme_file_path: Path):
        '''theme_file_path is only used here to find external resources''' 
        if not isinstance(theme_dict, dict):
            _logger.error("invalid dict read error")
            return
        
        Theme.set_file_path(theme_file_path)
        self.icon.read_theme(theme_file_path)

        # install all fonts from theme 'fonts' directory
        fonts_dir = Path(theme_file_path).parent / 'fonts'
        if fonts_dir.is_dir():
            for font_path in fonts_dir.iterdir():
                if str(font_path).endswith(('.otf', '.ttf')):
                    try:
                        QFontDatabase.addApplicationFont(str(font_path))
                    except:
                        _logger.warning(
                            f"failed to install font from file {str(font_path)}")
        
        self.aliases.clear()
        
        # first read if there are any aliases
        for key, value in theme_dict.items():
            if key != 'aliases':
                continue
            
            if not isinstance(value, dict):
                _logger.error(f"'{key}' must contains a dictionnary, ignored")
                continue
            
            for alias_key, alias_value in value.items():
                if not isinstance(alias_key, str):
                    _logger.error(
                        f"alias key must be a string. Ignore: {str(alias_key)}")
                    continue
                
                self.aliases[alias_key] = str(alias_value)
            
            break
        
        # read and parse the dict
        for key, value in theme_dict.items():
            if key in ('aliases', 'Theme'):
                continue
            
            begin, point, end = key.partition('.')
            
            if not isinstance(value, dict):
                _logger.error(f"'{key}' must contains a dictionnary, ignored")
                continue
            
            if begin not in ['body'] + self.subs:
                _logger.error(f"invalid ignored block key: [{key}]")
                continue
            
            # replace alias with alias value
            for sub_key, sub_value in value.items():
                if not isinstance(sub_value, str):
                    continue
                
                for alias_key, alias_value in self.aliases.items():
                    if alias_key not in sub_value:
                        continue
                    
                    if sub_value == alias_key:
                        value[sub_key] = alias_value
                        break
                    
                    new_words = list[str]()

                    for word in sub_value.split(' '):
                        if word == alias_key:
                            new_words.append(alias_value)
                        else:
                            new_words.append(word)
                    
                    value[sub_key] = ' '.join(new_words)
            
            if key == 'body':
                for body_key, body_value in value.items():
                    match body_key:
                        case 'port-height'|'box-spacing-horizontal' \
                                |'magnet'|'hardware-rack-width':
                            if not isinstance(body_value, int):
                                continue
                            body_key: str
                            self.__setattr__(body_key.replace('-', '_'), body_value)

                        case 'box-spacing':
                            # box_spacing must be an even number 
                            if not isinstance(body_value, int):
                                continue
                            self.box_spacing = 2 * (body_value // 2)

                        case 'background':
                            scene_bg_color = _to_qcolor(body_value)
                            if scene_bg_color is None:
                                scene_bg_color = QColor('black')
                            self.scene_background_color = scene_bg_color

                        case 'background-image':
                            if not isinstance(body_value, str):
                                continue
                            
                            background_path = \
                                theme_file_path.parent / 'images' / body_value
                            if background_path.is_file():
                                try:
                                    self.scene_background_image = QImage(str(background_path))
                                    if self.scene_background_image.isNull():
                                        _logger.error(
                                            f"background {background_path} is not a valid image")
                                        self.scene_background_image = None
                                except:
                                    _logger.error(
                                        f"background {background_path} is not a valid image")
                            else:
                                _logger.error(
                                    f"Unable to find background-image \"{background_path}\"")

                        case 'monitor-color':
                            monitor_color = _to_qcolor(body_value)
                            if monitor_color is None:
                                monitor_color = QColor(190, 158, 0)
                            self.monitor_color = monitor_color
                        
                        case 'thumbnail_port_colors':
                            self.thumbnail_port_colors = str(body_value)

                continue

            sub_attributer = self.__getattribute__(begin)
            if TYPE_CHECKING:
                assert isinstance(sub_attributer, StyleAttributer)
            sub_attributer.set_style_dict(end, value)