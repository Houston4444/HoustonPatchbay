from pathlib import Path

from .style_attributer import StyleAttributer


class UslStyleAttributer(StyleAttributer):
    def __init__(self, path: str, parent=None):
        super().__init__(path, parent=parent)
        self.selected = StyleAttributer(path + '.selected', self)
        self.subs.append('selected')


class BoxStyleAttributer(UslStyleAttributer):
    def __init__(self, path: str, parent):
        super().__init__(path, parent)
        self.hardware = UslStyleAttributer(path + '.hardware', self)
        self.client = UslStyleAttributer(path + '.client', self)
        self.monitor = UslStyleAttributer(path + '.monitor', self)
        self.subs += ['hardware', 'client', 'monitor']


class PortStyleAttributer(UslStyleAttributer):
    def __init__(self, path: str, parent):
        super().__init__(path, parent)
        self.audio = UslStyleAttributer(path + '.audio', self)
        self.midi = UslStyleAttributer(path + '.midi', self)
        self.cv = UslStyleAttributer(path + '.cv', self)
        self.alsa = UslStyleAttributer(path + '.alsa', self)
        self.video = UslStyleAttributer(path + '.video', self)
        self.subs += ['audio', 'midi', 'cv', 'video', 'alsa']


class LineStyleAttributer(UslStyleAttributer):
    def __init__(self, path: str, parent):
        super().__init__(path, parent)
        self.audio = UslStyleAttributer(path + '.audio', self)
        self.midi = UslStyleAttributer(path + '.midi', self)
        self.alsa = UslStyleAttributer(path + '.alsa', self)
        self.video = UslStyleAttributer(path + '.video', self)
        self.disconnecting = StyleAttributer(path + '.disconnecting', self)
        self.subs += ['audio', 'midi', 'alsa', 'video', 'disconnecting']


class GuiButtonStyleAttributer(StyleAttributer):
    def __init__(self, path: str, parent):
        super().__init__(path, parent)
        self.gui_visible = StyleAttributer('.gui_visible', self)
        self.gui_hidden = StyleAttributer('.gui_hidden', self)
        self.subs += ['gui_visible', 'gui_hidden']


class GridStyleAttributer(StyleAttributer):
    def __init__(self, path: str, parent=None):
        super().__init__(path, parent)
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

