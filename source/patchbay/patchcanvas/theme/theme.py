#!/usr/bin/python3
import logging
from pathlib import Path
from typing import Any

from qtpy.QtCore import Qt
from qtpy.QtGui import QColor, QFont, QImage, QFontDatabase

from . import theme_cache
from .theme_utils import to_qcolor, ThemeFile
from .style_attributer import StyleAttributer
from .style_attributers import (
    BoxStyleAttributer, PortStyleAttributer, LineStyleAttributer,
    UnselectedStyleAttributer, GuiButtonStyleAttributer,
    GridStyleAttributer, IconTheme)


_logger = logging.getLogger(__name__)

    
_DEFAULT_STYLE_ATTRS = {
    'background': QColor('black'),
    'background2': QColor(),
    'background-image': QImage(),
    'border-color': QColor('white'),
    'border-mode': 'default',
    'border-radius': 0,
    'border-style': Qt.PenStyle.SolidLine,
    'border-width': 1,
    'font-name': "Deja Vu Sans",
    'font-size': 11,
    'font-weight': QFont.Weight.Normal,
    'grid-min-width': 100,
    'grid-min-height': 100,
    'icon-size': 24,
    'margin-bottom': 3,
    'margin-free-side': 3,
    'margin-ports-side': 3,
    'margin-sides': 3,
    'margin-top': 3,
    'margin-top-side': 3,
    'padding-bottom': 3,
    'padding-free-side': 3,
    'padding-ports-side': 3,
    'padding-sides': 3,
    'padding-top': 3,
    'padding-top-side': 3,
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


class Theme(StyleAttributer):
    theme_file_path = Path()

    def __init__(self):
        super().__init__('')

        # fallbacks values for all (ugly style, but better than nothing)
        self._attrs = _DEFAULT_STYLE_ATTRS

        self.scene_background_color = QColor('black')
        self.scene_background_image = QImage()
        self.monitor_color = QColor(190, 158, 0)
        self.port_height = 16

        self.port_grouped_width = 19
        self.box_spacing = 4
        self.box_spacing_horizontal = 24
        self.hardware_rack_width = 5
        self.port_type_colors = dict[str, QColor]()

        self.icon = IconTheme()

        self.aliases = dict[str, Any]()

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
        self.monitor_decoration = UnselectedStyleAttributer(
            '.monitor_decoration', self)
        self.gui_button = GuiButtonStyleAttributer('.gui_button', self)
        self.grid = GridStyleAttributer('.grid', self)

        self.subs += [
            'box', 'box_wrapper', 'box_header_line', 'box_shadow',
            'box_header', 'box_ports_border', 'portgroup', 'port', 'line',
            'rubberband', 'hardware_rack', 'monitor_decoration',
            'gui_button', 'grid']

    @classmethod
    def set_file_path(cls, theme_file_path: Path):
        ThemeFile.path = theme_file_path

    @classmethod
    def load_cache(cls):
        theme_cache.load()

    @classmethod
    def save_cache(cls):
        theme_cache.save()

    def _read_body_attr(self, body_key: str, body_value):
        match body_key:
            case 'port-height'|'box-spacing-horizontal' \
                    |'hardware-rack-width' | 'port-grouped-width':
                if not isinstance(body_value, int):
                    return
                self.__setattr__(body_key.replace('-', '_'), body_value)

            case 'box-spacing':
                # box_spacing must be an even number
                if not isinstance(body_value, int):
                    return
                self.box_spacing = 2 * (body_value // 2)

            case 'background':
                scene_bg_color = to_qcolor(body_value)
                if scene_bg_color is None:
                    scene_bg_color = QColor('black')
                self.scene_background_color = scene_bg_color

            case 'background-image':
                if not isinstance(body_value, str):
                    return

                background_path = \
                    ThemeFile.path.parent / 'images' / body_value
                if background_path.is_file():
                    try:
                        self.scene_background_image = QImage(
                            str(background_path))
                        if self.scene_background_image.isNull():
                            _logger.error(
                                f"background {background_path} "
                                "is not a valid image")
                            self.scene_background_image = None
                    except:
                        _logger.error(
                            f"background {background_path} "
                            "is not a valid image")
                else:
                    _logger.error(
                        "Unable to find background-image "
                        f"\"{background_path}\"")

            case 'monitor-color':
                monitor_color = to_qcolor(body_value)
                if monitor_color is None:
                    monitor_color = QColor(190, 158, 0)
                self.monitor_color = monitor_color
                
            case _:
                _logger.warning(
                    f'Theme [body]{body_key} is unknown '
                    'and will have no effect')

    def read_theme(self, theme_dict: dict[str, dict], theme_file_path: Path,
                   for_linter=False):
        '''theme_file_path is only used here to find external resources'''
        _logger.info(f'start to read theme {theme_dict}, {theme_file_path}')
        if not isinstance(theme_dict, dict):
            _logger.error("invalid dict read error")
            return

        # set some specific default values
        self.box_header.set_attribute('margin', 0.0)
        self.gui_button._attrs['text-color'] = QColor()

        ThemeFile.path = theme_file_path
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
                                "failed to install font "
                                f"from file {str(font_path)}")

        self.aliases.clear()

        # first read if there are any aliases
        for key, value in theme_dict.items():
            if key != 'aliases':
                continue

            port_types = ('audio', 'midi', 'cv', 'alsa', 'video')

            if not isinstance(value, dict):
                _logger.error(f"'{key}' must contains a dictionnary, ignored")
                continue

            for alias_key, alias_value in value.items():
                if not isinstance(alias_key, str):
                    _logger.error(
                        "alias key must be a string. "
                        f"Ignore: {str(alias_key)}")
                    continue

                self.aliases[alias_key] = str(alias_value)
                if alias_key in port_types:
                    port_color = to_qcolor(alias_value)
                    if port_color is None:
                        port_color = QColor('black')
                    port_color = port_color.toRgb()
                    self.port_type_colors[alias_key] = port_color

            for port_type in port_types:
                if self.port_type_colors.get(port_type) is None:
                    _logger.error(f"An alias named '{port_type}' is needed")
                    self.port_type_colors[port_type] = QColor()

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
                    self._read_body_attr(body_key, body_value)
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
            if sub_attributer is not None:
                sub_attributer.set_style_dict(end, value)