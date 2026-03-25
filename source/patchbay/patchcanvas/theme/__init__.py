#!/usr/bin/python3
import logging
import os
from pathlib import Path
import pickle
from typing import TYPE_CHECKING, Iterator, TypeAlias, TypedDict, Optional

from qtpy.QtCore import Qt
from qtpy.QtGui import (QColor, QPen, QFont, QBrush, QFontMetricsF,
                         QImage, QFontDatabase)

from .. import xdg

from .theme_utils import to_qcolor, rail_int, rail_float
from .theme_structs import BorderSide, Margin, BoxStyler

_logger = logging.getLogger(__name__)

TitleCache: TypeAlias = dict[str, dict[int, list[dict[str, int]]]]
    
_DEFAULT_STYLE_ATTRS = {
    'background': QColor('black'),
    'background2': QColor(),
    'background-image': QImage(),
    'border-color': QColor('white'),
    'border-mode': 'default',
    'border-radius': 0,
    'border-sides': BorderSide.FULL | BorderSide.FULL_ON_SIDE,
    'border-style': Qt.PenStyle.SolidLine,
    'border-width': 1,
    'box-footer': 0,
    'font-name': "Deja Vu Sans",
    'font-size': 11,
    'font-width': QFont.Weight.Normal,
    'grid-min-width': 100,
    'grid-min-height': 100,
    'icon-size': 24,
    'margin-bottom': 3,
    'margin-free-side': 3,
    'margin-ports-side': 3,
    'margin-sides': 3,
    'margin-top': 3,
    'margin-top-side': 3,
    'output-align': 'left',
    'port-in-offset': 0,
    'port-in-offset-mode': 'bore',
    'port-out-offset': 0,
    'port-out-offset-mode': 'bore',
    'port-spacing': 2,
    'port-type-spacing': 2,
    'text-color': QColor('white'),
    'visible': False,
    'drilled': False
}


class StyleAttributer:
    def __init__(self, path: str,
                 parent: 'StyleAttributer | None' =None):
        self.subs = list[str]()

        self._attrs = {}
 
        self._path = path
        self._parent = parent

        self._fill_pen = None
        self._font = None
        self._font_metrics_cache: Optional[dict[str, float]] = None
        self._titles_templates_cache: TitleCache | None = None

        if TYPE_CHECKING:
            assert isinstance(self._parent, StyleAttributer)

    def child(self, path: str) -> 'StyleAttributer | None':
        begin, _, end = path.partition('.')
        if begin not in self.subs:
            return
        
        child_: StyleAttributer = self.__getattribute__(begin)
        if not end:
            return child_
        
        return child_.child(end)

    def childs(self) -> 'Iterator[StyleAttributer]':
        for sub in self.subs:
            yield self.__getattribute__(sub)

    def all_childs(self) -> 'Iterator[StyleAttributer]':
        for sub in self.subs:
            child = self.__getattribute__(sub)
            yield child
            for sub_ in child.all_childs():
                yield sub_

    def inherit(self, other: 'StyleAttributer'):
        for key, value in other._attrs.items():
            self._attrs[key] = value

        for sub_ in self.subs:
            if sub_ in other.subs:
                self.child(sub_).inherit(other.child(sub_))

    @property
    def log_path(self):
        return f'[{self._path[1:]}]'

    def clear(self):
        self._attrs.clear()
        for child in self.childs():
            child.clear()

    def set_attribute(self, attribute: str, value: str | float):
        err = False
        match attribute:
            case 'inherits':
                ...
            case 'border-color'|'text-color'|'background'|'background2':
                self._attrs[attribute] = to_qcolor(value)
                if self._attrs.get(attribute) is None:
                    err = True
        
            case 'background-image':
                image_path = (
                    Theme.theme_file_path.parent / 'images' / str(value))
                image = None
                if image_path.is_file():
                    image = QImage(str(image_path))
                    image.setDevicePixelRatio(3.0)
                    if image.isNull():
                        _logger.error(
                            f'{self._path}:{attribute} : '
                            f'Failed to load {image_path} as an image')
                        image = None
                else:
                    _logger.error(
                        f"{self.log_path}{attribute} can not find image at {image_path}")
                self._attrs[attribute] = image

            case 'border-width'|'border-radius'|'font-size'| \
                    'port-offset'|'port-in-offset'|'port-out-offset'| \
                    'port-spacing'|'port-type-spacing'|'box-footer' | \
                    'icon-size'|'grid-min-width'|'grid-min-height'| \
                    'margin'|'margin-top'|'margin-bottom'|'margin-sides'|\
                    'margin-ports-side'|'margin-free-side'|'margin-top-side':
                if isinstance(value, (int, float)):
                    match attribute:
                        case 'border-width':
                            min_, max_ = 0, 20
                        case 'border-radius'|'box-footer':
                            min_, max_ = 0, 50
                        case 'margin'|'margin-top'|'margin-bottom'|\
                                'margin-sides'|'margin-ports-side'|\
                                'margin-free-side'|'margin-top-side':
                            min_, max_ = -50, 50
                        case 'font-size':
                            min_, max_ = 1, 200
                        case 'port-spacing'|'port-type-spacing':
                            min_, max_ = 0, 100
                        case 'icon-size':
                            min_, max_ = 8, 1024
                        case 'grid-min-width'|'grid-min-height':
                            min_, max_ = 1, 100000
                        case _:
                            min_, max_ = -20, 20
                    self._attrs[attribute] = rail_float(value, min_, max_)

                    match attribute:
                        # theses attributes redefine others
                        case 'port-offset':
                            self._attrs['port-in-offset'] = \
                                self._attrs['port-out-offset'] = \
                                    self._attrs[attribute]
                        case 'margin':
                            for key in ('top', 'bottom', 'sides',
                                        'ports-side', 'free-side', 'top-side'):
                                self._attrs[f'margin-{key}'] = \
                                    self._attrs[attribute]
                else:
                    err = True
            
            case 'border-style':
                if isinstance(value, str):
                    value = value.lower()
                    match value:
                        case 'solid'|'normal':
                            border_style = Qt.PenStyle.SolidLine
                        case 'nopen'|'none':
                            border_style = Qt.PenStyle.NoPen
                        case 'dash':
                            border_style = Qt.PenStyle.DashLine
                        case 'dashdot':
                            border_style = Qt.PenStyle.DashDotLine
                        case 'dashdotdot':
                            border_style = Qt.PenStyle.DashDotDotLine
                        case _:
                            border_style = None
                            
                    if border_style is None:
                        err = True
                    else:
                        self._attrs[attribute] = border_style
                else:
                    err = True
                    
            case 'font-name':
                if isinstance(value, str):
                    self._attrs[attribute] = value

                    # add the font to database if it is an embedded font
                    for ext in ('ttf', 'otf'):
                        embedded_path = (
                            Theme.theme_file_path.parent
                            / 'fonts' / f"{value}.{ext}")
                        if embedded_path.is_file():
                            QFontDatabase.addApplicationFont(
                                str(embedded_path))
                            break
                else:
                    err = True
            
            case 'font-width':
                if isinstance(value, (int, float)):
                    self._attrs[attribute] = rail_int(value, 0, 99)
                elif isinstance(value, str):
                    value = value.lower()
                    if value == 'normal':
                        self._attrs[attribute] = QFont.Weight.Normal
                    elif value == 'bold':
                        self._attrs[attribute] = QFont.Weight.Bold
                    else:
                        err = True
                else:
                    err = True
                    
            case 'border-mode'|'output-align'|'port-offset-mode'|\
                    'port-in-offset-mode'|'port-out-offset-mode':
                if isinstance(value, str):
                    self._attrs[attribute] = value

                    if attribute == 'port-offset-mode':
                        self._attrs['port-in-offset-mode'] = \
                            self._attrs['port-out-offset-mode'] = \
                                self._attrs['port-offset-mode']
                else:
                    err = True
            
            case 'visible'|'drilled':
                if isinstance(value, str):
                    hcb = value.lower() not in ('false', 'no')
                elif isinstance(value, (int, float)):
                    hcb = bool(value)
                else:
                    _logger.error(f'[{self._path}]{attribute} : '
                                  f'"{value}" is not a valid value')
                    return
                
                self._attrs[attribute] = hcb
            
            case 'border-sides':
                self._attrs[attribute] = BorderSide.from_text(value)
            
            case _:
                _logger.error(f"{self.log_path}{attribute} unknown key !")

        if err:
            _logger.error(
                f"{self._path}: invalid value for {attribute}: {str(value)}")

    def set_style_dict(self, context: str, style_dict: dict):
        if context:
            begin, point, end = context.partition('.')

            if begin not in self.subs:
                _logger.error(f"{self._path}: invalid ignored key: {begin}")
                return
            
            self.child(begin).set_style_dict(end, style_dict)
            return

        for key, value in style_dict.items():
            self.set_attribute(key, value)

    def get_value_of(self, attribute: str, orig_path='', needed_attribute=''):
        '''return the value of given attribute for this theme section.
        if this value is not present in this theme section,
        it will look into parent sections.
        Note that for 'selected' section, it will look in 'selected' section
        of parent before looking in parent section.'''
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

        if self._attrs.get(attribute) is None:
        # if self.__getattribute__(attribute) is None:
            if (needed_attribute
                    and self._attrs.get(needed_attribute) is not None):
                return None

            if self._parent is None:
                _logger.error(
                    f"get value of: {self._path} None value and no parent")
                return None

            return self._parent.get_value_of(
                attribute, orig_path, needed_attribute)

        return self._attrs.get(attribute)

    @property
    def fill_pen(self) -> QPen:
        if self._fill_pen is None:
            if TYPE_CHECKING:
                self._fill_pen = QPen()
            else:
                self._fill_pen = QPen(
                    QBrush(self.get_value_of('border-color')),
                    self.get_value_of('border-width'),
                    self.get_value_of('border-style'))

        return self._fill_pen

    @property
    def border_radius(self) -> float:
        return self.get_value_of('border-radius') # type:ignore

    @property
    def background_color(self) -> QColor:
        return self.get_value_of('background') # type:ignore

    @property
    def background2_color(self) -> QColor | None:
        return self.get_value_of('background2', # type:ignore
                                 needed_attribute='background')

    @property
    def background_image(self) -> QImage:
        return self.get_value_of('background-image') # type:ignore

    @property
    def margin(self) -> Margin:
        margin = Margin()
        margin.top = self.get_value_of('margin-top') # type:ignore
        margin.bottom = self.get_value_of('margin-bottom') # type:ignore
        margin.sides = self.get_value_of('margin-sides') # type:ignore
        margin.ports_side = self.get_value_of('margin-ports-side') # type:ignore
        margin.free_side = self.get_value_of('margin-free-side') # type:ignore
        margin.top_side = self.get_value_of('margin-top-side') # type:ignore
        return margin

    @property
    def margin_empty(self) -> Margin:
        return Margin()

    @property
    def text_color(self) -> QColor:
        return self.get_value_of('text-color') # type:ignore

    @property
    def font(self) -> QFont:
        if self._font is None:
            self._font = QFont(self.get_value_of('font-name'))
            self._font.setPixelSize(
                int(self.get_value_of('font-size'))) # type:ignore
            self._font.setWeight(
                int(self.get_value_of('font-width'))) # type:ignore
        return self._font

    def _get_font_metrics_cache(self) -> dict[str, float]:
        font_name = str(self.get_value_of('font-name'))
        font_size = str(self.get_value_of('font-size'))
        font_width = str(self.get_value_of('font-width'))

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
    def border_mode(self) -> str:
        return self.get_value_of('border-mode') # type:ignore

    @property
    def border_width(self) -> float:
        '''The border width defined in theme,
        or 0.0 if there is no border'''
        if self.get_value_of('border-style') == Qt.PenStyle.NoPen:
            return 0.0
        return self.get_value_of('border-width') # type:ignore

    @property
    def output_align(self) -> str:
        return self.get_value_of('output-align') # type:ignore

    @property
    def port_in_offset(self) -> float:
        return self.get_value_of('port-in-offset') # type:ignore

    @property
    def port_out_offset(self) -> float:
        return self.get_value_of('port-out-offset') # type:ignore

    @property
    def port_in_offset_mode(self) -> str:
        return self.get_value_of('port-in-offset-mode') # type:ignore

    @property
    def port_out_offset_mode(self) -> str:
        return self.get_value_of('port-out-offset-mode') # type:ignore

    @property
    def port_spacing(self) -> float:
        return self.get_value_of('port-spacing') # type:ignore

    @property
    def port_type_spacing(self) -> float:
        return self.get_value_of('port-type-spacing') # type:ignore

    @property
    def icon_size(self) -> float:
        return self.get_value_of('icon-size') # type:ignore

    @property
    def grid_min_width(self) -> float:
        return self.get_value_of('grid-min-width') # type:ignore

    @property
    def grid_min_height(self) -> float:
        return self.get_value_of('grid-min-height') # type:ignore

    @property
    def visible(self) -> bool:
        return self.get_value_of('visible') # type:ignore

    @property
    def drilled(self) -> bool:
        return self.get_value_of('drilled') # type:ignore

    def _get_titles_templates_cache(self) -> TitleCache:
        font_name = str(self.get_value_of('font-name'))
        font_size = str(self.get_value_of('font-size'))
        font_width = str(self.get_value_of('font-width'))

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
            self, title: str, icon_size: int, templates: list):
        if self._titles_templates_cache is None:
            self._titles_templates_cache = self._get_titles_templates_cache()

        if not title in self._titles_templates_cache:
            self._titles_templates_cache[title] = {}

        self._titles_templates_cache[title][icon_size] = templates

    def get_title_templates(
            self, title: str, icon_size: int) -> list[dict[str, int]]:
        if self._titles_templates_cache is None:
            self._titles_templates_cache = self._get_titles_templates_cache()

        if (title in self._titles_templates_cache
                and icon_size in self._titles_templates_cache[title]):
            return self._titles_templates_cache[title][icon_size]

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
                    'hardware_midi', 'monitor_cap  ture', 'monitor_playback'):
            icon_path = icons_dir / f'{key}.svg'
            if icon_path.is_file():
                self.__setattr__(key, str(icon_path))


class Theme(StyleAttributer):
    theme_file_path = Path()

    # if for some reason cache may be incompatible with this version
    # of the patchbay, we need to discard the cache files.
    CACHE_VERSION = (1, 4)

    title_templates_cache: dict[str, dict[str, dict[str, TitleCache]]] = \
        {'CACHE_VERSION': CACHE_VERSION} # type:ignore
    font_metrics_cache: dict[str, dict[str, dict[str, dict[str, float]]]] = \
        {'CACHE_VERSION': CACHE_VERSION} # type:ignore
        # CACHE_VERSION is the only one tuple[int, int]

    def __init__(self):
        StyleAttributer.__init__(self, '')

        # fallbacks values for all (ugly style, but better than nothing)
        self._attrs = _DEFAULT_STYLE_ATTRS

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
        self.box_header = BoxStyleAttributer('.box_header', self)
        self.box_ports_border = BoxStyleAttributer('.box_ports_border', self)
        self.portgroup = PortStyleAttributer('.portgroup', self)
        self.port = PortStyleAttributer('.port', self)
        self.line = LineStyleAttributer('.line', self)
        self.rubberband = StyleAttributer('.rubberband', self)
        self.hardware_rack = UnselectedStyleAttributer('.hardware_rack', self)
        self.monitor_decoration = UnselectedStyleAttributer('.monitor_decoration', self)
        self.gui_button = GuiButtonStyleAttributer('.gui_button', self)
        self.grid = GridStyleAttributer('.grid', self)

        self.subs += ['box', 'box_wrapper', 'box_header_line', 'box_shadow',
                      'box_header', 'box_ports_border', 'portgroup', 'port', 'line',
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

    def clear(self):
        'reset the current theme'
        self._attrs = _DEFAULT_STYLE_ATTRS
        for child in self.childs():
            child.clear()
            
        # set some specific default values
        self.box_header.set_attribute('margin', 0.0)
        self.gui_button._attrs['text-color'] = QColor()

    def read_theme(self, theme_dict: dict[str, dict], theme_file_path: Path,
                   for_linter=False):
        '''theme_file_path is only used here to find external resources'''
        _logger.info(f'start to read theme {theme_dict}, {theme_file_path}')
        if not isinstance(theme_dict, dict):
            _logger.error("invalid dict read error")
            return

        # reset the current theme
        self.clear()

        Theme.set_file_path(theme_file_path)
        self.icon.read_theme(theme_file_path)

        if not for_linter:
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
                        elif word == f'-{alias_key}':
                            new_words.append(f'-{alias_value}')
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
                            scene_bg_color = to_qcolor(body_value)
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
                            monitor_color = to_qcolor(body_value)
                            if monitor_color is None:
                                monitor_color = QColor(190, 158, 0)
                            self.monitor_color = monitor_color

                        case 'thumbnail_port_colors':
                            self.thumbnail_port_colors = str(body_value)
                            
                        case _:
                            _logger.warning(
                                f'Theme [body]{body_key} is unknown and will have no effect')

                continue

            inherits_name = value.get('inherits')
            if isinstance(inherits_name, str):
                this = self.child(key)
                mother = self.child(inherits_name)

                if this is None:
                    # should not happen
                    _logger.error(f'[{key}] not found to inherit')                
                elif mother is None:
                    _logger.warning(
                        f'[{key}]{value}, {inherits_name} does not exists.')
                else:
                    _logger.info(f'{key} inherits {inherits_name}')
                    this.inherit(mother)

            sub_attributer = self.child(begin)
            sub_attributer.set_style_dict(end, value)