from functools import cached_property
import logging
from typing import Iterator, TYPE_CHECKING

from qtpy import QT5
from qtpy.QtCore import Qt
from qtpy.QtGui import (
    QBrush, QImage, QFontDatabase, QFont, QPen, QColor, QFontMetricsF)

from . import theme_cache
from .theme_utils import to_qcolor, rail_float, rail_int, ThemeFile
from .theme_structs import Margin, BorderMode, Align

if TYPE_CHECKING:
    from .style_attributers import UslStyleAttributer


_logger = logging.getLogger(__name__)


class StyleAttributer:
    def __init__(self, path: str,
                 parent: 'StyleAttributer | None' =None):
        self.subs = list[str]()

        self._attrs = {}
 
        self._path = path
        self._parent = parent

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

            if TYPE_CHECKING:
                assert isinstance(child, StyleAttributer)

            for sub_ in child.all_childs():
                yield sub_

    def inherit(self, other: 'StyleAttributer'):
        for key, value in other._attrs.items():
            self._attrs[key] = value

        for sub_ in self.subs:
            if sub_ in other.subs:
                self.child(sub_).inherit(other.child(sub_)) # type:ignore

    @property
    def log_path(self):
        return f'[{self._path[1:]}]'

    def set_attribute(self, attribute: str, value: str | float):
        err = False
        match attribute:
            case 'inherits':
                pass
            case 'border-color'|'text-color'|'background'|'background2':
                if isinstance(value, str):
                    self._attrs[attribute] = to_qcolor(value)
                if self._attrs.get(attribute) is None:
                    err = True
        
            case 'background-image':
                image_path = (
                    ThemeFile.path.parent / 'images' / str(value))
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
                    'port-spacing'|'port-type-spacing'| \
                    'icon-size'|'grid-min-width'|'grid-min-height'| \
                    'margin'|'margin-top'|'margin-bottom'|'margin-sides'|\
                    'margin-ports-side'|'margin-free-side'|'margin-top-side':
                if isinstance(value, (int, float)):
                    match attribute:
                        case 'border-width':
                            min_, max_ = 0, 20
                        case 'border-radius':
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
                            ThemeFile.path.parent
                            / 'fonts' / f"{value}.{ext}")
                        if embedded_path.is_file():
                            QFontDatabase.addApplicationFont(
                                str(embedded_path))
                            break
                else:
                    err = True
                    
            case 'font-weight':
                if isinstance(value, str):
                    match value.lower():
                        case 'thin':
                            self._attrs[attribute] = QFont.Weight.Thin
                        case 'extralight'|'extra-light'|'extra_light':
                            self._attrs[attribute] = QFont.Weight.ExtraLight
                        case 'light':
                            self._attrs[attribute] = QFont.Weight.Light
                        case 'normal':
                            self._attrs[attribute] = QFont.Weight.Normal
                        case 'medium':
                            self._attrs[attribute] = QFont.Weight.Medium
                        case 'demibold'|'demi-bold'|'demi_bold':
                            self._attrs[attribute] = QFont.Weight.DemiBold
                        case 'bold':
                            self._attrs[attribute] = QFont.Weight.Bold
                        case 'extrabold'|'extra-bold'|'extra_bold':
                            self._attrs[attribute] = QFont.Weight.ExtraBold
                        case 'black':
                            self._attrs[attribute] = QFont.Weight.Black
                        case _:
                            err = True

                elif isinstance(value, (int, float)):
                    weight = rail_int(value, 1, 1000)
                    if QT5:
                        self._attrs[attribute] = (weight - 1)  // 10
                    else:
                        self._attrs[attribute] = weight

                else:
                    err = True
            
            case 'border-mode':
                if isinstance(value, str):
                    match value.lower():
                        case 'minimal':
                            self._attrs[attribute] = BorderMode.MINIMAL
                        case 'sides':
                            self._attrs[attribute] = BorderMode.SIDES
                        case _:
                            self._attrs[attribute] = BorderMode.DEFAULT
                else:
                    err = True
            
            case 'output-align':
                if isinstance(value, str):
                    match value.lower():
                        case 'right':
                            self._attrs[attribute] = Align.RIGHT
                        case _:
                            self._attrs[attribute] = Align.LEFT
                else:
                    err = True
            
            case 'port-offset-mode'|\
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
            
            self.child(begin).set_style_dict(end, style_dict) # type:ignore
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
                assert isinstance(self, UslStyleAttributer)

            if (orig_path.endswith('.' + path_end)
                    and path_end in self.subs
                    and self._path + '.' + path_end != orig_path):
                sel_attr = self.selected._attrs.get(attribute)
                if sel_attr is None:
                    if needed_attribute:
                        if self.selected._attrs.get(needed_attribute) is None:
                            return None
                    continue
                return sel_attr                        

        if self._attrs.get(attribute) is None:
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

    @cached_property
    def fill_pen(self) -> QPen:
        return QPen(
            QBrush(self.get_value_of('border-color')),
            self.get_value_of('border-width'),
            self.get_value_of('border-style'))

    @cached_property
    def border_radius(self) -> float:
        return self.get_value_of('border-radius') # type:ignore

    @cached_property
    def background_color(self) -> QColor:
        return self.get_value_of('background') # type:ignore

    @cached_property
    def background2_color(self) -> QColor | None:
        return self.get_value_of('background2', # type:ignore
                                 needed_attribute='background')

    @cached_property
    def background_image(self) -> QImage:
        return self.get_value_of('background-image') # type:ignore

    @cached_property
    def margin(self) -> Margin:
        margin = Margin()
        margin.top = self.get_value_of('margin-top') # type:ignore
        margin.bottom = self.get_value_of('margin-bottom') # type:ignore
        margin.sides = self.get_value_of('margin-sides') # type:ignore
        margin.ports_side = self.get_value_of('margin-ports-side') # type:ignore
        margin.free_side = self.get_value_of('margin-free-side') # type:ignore
        margin.top_side = self.get_value_of('margin-top-side') # type:ignore
        return margin

    @cached_property
    def padding(self) -> Margin:
        padding = Margin()
        padding.top = self.get_value_of('padding-top') # type:ignore
        padding.bottom = self.get_value_of('padding-bottom') # type:ignore
        padding.sides = self.get_value_of('padding-sides') # type:ignore
        padding.ports_side = self.get_value_of('padding-ports-side') # type:ignore
        padding.free_side = self.get_value_of('padding-free-side') # type:ignore
        padding.top_side = self.get_value_of('padding-top-side') # type:ignore
        return padding

    @cached_property
    def margin_empty(self) -> Margin:
        return Margin()

    @cached_property
    def text_color(self) -> QColor:
        return self.get_value_of('text-color') # type:ignore

    @cached_property
    def font(self) -> QFont:
        font = QFont(self.get_value_of('font-name'))
        font.setPixelSize(int(self.get_value_of('font-size'))) # type:ignore
        font.setWeight(int(self.get_value_of('font-weight'))) # type:ignore
        return font

    @cached_property
    def border_mode(self) -> BorderMode:
        return self.get_value_of('border-mode') # type:ignore

    @cached_property
    def border_width(self) -> float:
        '''The border width defined in theme,
        or 0.0 if there is no border'''
        if self.get_value_of('border-style') == Qt.PenStyle.NoPen:
            return 0.0
        return self.get_value_of('border-width') # type:ignore

    @cached_property
    def output_align(self) -> Align:
        return self.get_value_of('output-align') # type:ignore

    @cached_property
    def port_in_offset(self) -> float:
        return self.get_value_of('port-in-offset') # type:ignore

    @cached_property
    def port_out_offset(self) -> float:
        return self.get_value_of('port-out-offset') # type:ignore

    @cached_property
    def port_in_offset_mode(self) -> str:
        return self.get_value_of('port-in-offset-mode') # type:ignore

    @cached_property
    def port_out_offset_mode(self) -> str:
        return self.get_value_of('port-out-offset-mode') # type:ignore

    @cached_property
    def port_spacing(self) -> float:
        return self.get_value_of('port-spacing') # type:ignore

    @cached_property
    def port_type_spacing(self) -> float:
        return self.get_value_of('port-type-spacing') # type:ignore

    @cached_property
    def icon_size(self) -> float:
        return self.get_value_of('icon-size') # type:ignore

    @cached_property
    def grid_min_width(self) -> float:
        return self.get_value_of('grid-min-width') # type:ignore

    @cached_property
    def grid_min_height(self) -> float:
        return self.get_value_of('grid-min-height') # type:ignore

    @cached_property
    def visible(self) -> bool:
        return self.get_value_of('visible') # type:ignore

    @cached_property
    def drilled(self) -> bool:
        return self.get_value_of('drilled') # type:ignore

    @cached_property
    def _titles_templates_cache(self) -> theme_cache.TitleCache:
        font_name = str(self.get_value_of('font-name'))
        font_size = str(self.get_value_of('font-size'))
        font_width = str(self.get_value_of('font-weight'))

        return theme_cache.get_title_templates_cache(
            font_name, font_size, font_width)

    @cached_property
    def _font_metrics_cache(self) -> dict[str, float]:
        font_name = str(self.get_value_of('font-name'))
        font_size = str(self.get_value_of('font-size'))
        font_width = str(self.get_value_of('font-weight'))

        return theme_cache.get_font_metrics_cache(
            font_name, font_size, font_width)

    def get_text_width(self, string: str) -> float:
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
    
    def save_title_templates(
            self, title: str, icon_size: int, templates: list):
        if not title in self._titles_templates_cache:
            self._titles_templates_cache[title] = {}

        self._titles_templates_cache[title][icon_size] = templates

    def get_title_templates(
            self, title: str, icon_size: int) -> list[dict[str, int]]:
        if (title in self._titles_templates_cache
                and icon_size in self._titles_templates_cache[title]):
            return self._titles_templates_cache[title][icon_size]
        return []

