#!/usr/bin/python3
import logging
from pathlib import Path

from qtpy.QtCore import Qt
from qtpy.QtGui import QColor, QFont, QImage, QFontDatabase

from . import theme_cache
from .theme_utils import to_qcolor, ThemeFile
from .theme_structs import BorderSide
from .style_attributer import StyleAttributer


_logger = logging.getLogger(__name__)

    
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
        ThemeFile.path = theme_file_path

    @classmethod
    def load_cache(cls):
        theme_cache.load()

    @classmethod
    def save_cache(cls):
        theme_cache.load()

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