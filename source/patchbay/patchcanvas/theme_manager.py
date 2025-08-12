
import configparser
from dataclasses import dataclass
import logging
import os
import shutil
from pathlib import Path
from typing import Optional

from qtpy.QtCore import QTimer

from .theme import Theme
from .init_values import CanvasSceneMissing, canvas, CallbackAct
from .xdg import xdg_data_dirs, xdg_data_home

_logger = logging.Logger(__name__)


@dataclass
class ThemeData:
    ref_id: str
    name: str
    editable: bool
    file_path: str


class ThemeManager:
    def __init__(self, theme_paths: tuple[Path]) -> None:
        if canvas.scene is None:
            raise CanvasSceneMissing
        
        self.current_theme = None
        self.current_theme_file = Path()
        self.theme_paths = theme_paths

        self._last_modified = 0.0

        self._theme_file_timer = QTimer()
        self._theme_file_timer.setInterval(400)
        self._theme_file_timer.timeout.connect(self._check_theme_file_modified)

    @staticmethod
    def default_theme_paths(source_theme_dir: Optional[Path]=None) -> list[Path]:
        ''' do not use now ! While HoustonPatchbay is a submodule and not a lib
            sharing the same paths for various programs create package conflicts
            in distributions.'''
        APP_NAME = 'HoustonPatchbay'
        path_list = list[Path]()
        
        path_list.append(xdg_data_home() / APP_NAME / 'themes')
        
        if source_theme_dir is not None and source_theme_dir not in path_list:
            path_list.append(source_theme_dir)
        
        for p in xdg_data_dirs():
            path_list.append(p / APP_NAME / 'themes')
                
        return path_list

    def _check_theme_file_modified(self):
        if (not self.current_theme_file.name
                or not self.current_theme_file.exists()):
            self._theme_file_timer.stop()
            return
        
        try:
            last_modified = os.path.getmtime(self.current_theme_file)
        except:
            self._theme_file_timer.stop()
            return

        if last_modified == self._last_modified:
            return
        
        if not self._update_theme():
            self._last_modified = last_modified

    def _update_theme(self) -> bool:
        conf = configparser.ConfigParser()
        try:
            # we don't need the file_list
            # it is just a convenience to mute conf.read
            file_list = conf.read(self.current_theme_file)
        except configparser.DuplicateOptionError as e:
            _logger.error(str(e))
            return False
        except:
            _logger.error(f"failed to open {self.current_theme_file}")
            return False
        
        theme_dict = self._convert_configparser_object_to_dict(conf)
        self._last_modified = os.path.getmtime(self.current_theme_file)
        
        del canvas._theme
        canvas._theme = Theme()
        canvas._theme.read_theme(theme_dict, self.current_theme_file)
        canvas.scene.update_theme()
        
        theme_ref = self.current_theme_file.parent.name
        canvas.callback(CallbackAct.THEME_CHANGED, theme_ref)
        return True
    
    @staticmethod
    def _convert_configparser_object_to_dict(
            conf: configparser.ConfigParser) -> dict:
        def type_convert(value):
            '''return an int, a float, or the unchanged given value'''
            try:
                value = int(value)
            except:
                try:
                    value = float(value)
                except:
                    return value
            return value

        return_dict = {}
        for key, value in conf.items():
            if key == 'DEFAULT':
                continue

            assert isinstance(value, configparser.SectionProxy)
            new_dict = {}

            for skey, svalue in value.items():
                assert isinstance(svalue, str)
                
                if svalue.startswith('(') and svalue.endswith(')'):
                    new_value = svalue[1:-1].split(', ')
                    new_value = tuple([type_convert(v) for v in new_value])
                elif svalue.startswith('[') and svalue.endswith(']'):
                    new_value = svalue[1:-1].split(', ')
                    new_value = [type_convert(v) for v in new_value]
                else:
                    new_value = type_convert(svalue)
                new_dict[skey] = new_value
            return_dict[key] = new_dict
        
        return return_dict
    
    def get_theme(self) -> str:
        return self.current_theme_file.parent.name
    
    def set_theme(self, theme_name: str) -> bool:
        self.current_theme = theme_name

        for theme_path in self.theme_paths:
            theme_file_path = theme_path.joinpath(theme_name, 'theme.conf')
            if theme_file_path.exists():
                self.current_theme_file = theme_file_path
                break
        else:
            _logger.error(f"Unable to find theme {theme_name}")
            return False

        theme_is_valid = self._update_theme()
        if not theme_is_valid:
            return False
        
        self.activate_watcher(os.access(self.current_theme_file, os.R_OK))
        return True
    
    def set_fallback_theme(self):
        del canvas._theme
        canvas._theme = Theme()
        canvas.scene.update_theme()

    def list_themes(self) -> list[ThemeData]:
        themes_set = set[str]()
        conf = configparser.ConfigParser()
        theme_classes = list[ThemeData]()
        lang = os.getenv('LANG')
        lang_short = ''
        if len(lang) >= 2:
            lang_short = lang[:2]
        
        for search_path in self.theme_paths:
            if not search_path.exists():
                continue
            
            editable = bool(os.access(search_path, os.W_OK))
            
            for file_path in search_path.iterdir():
                if file_path.name in themes_set:
                    continue

                full_path = search_path.joinpath(file_path, 'theme.conf')
                if not full_path.is_file():
                    continue

                try:
                    conf.read(str(full_path))
                except configparser.DuplicateOptionError as e:
                    _logger.error(str(e))
                    continue
                except:
                    # TODO
                    continue
    
                name = file_path.name

                # Search the theme name in the theme file
                # It may be translated
                if 'Theme' in conf.keys():
                    conf_theme = conf['Theme']
                    if 'Name' in conf_theme.keys():
                        name = conf_theme['Name']
                    
                    name_lang_key = f'Name[{lang_short}]'
                    
                    if name_lang_key in conf_theme.keys():
                        name = conf_theme[name_lang_key]

                conf.clear()                
                themes_set.add(file_path.name)
                
                theme_classes.append(
                    ThemeData(file_path.name, name, editable, str(full_path)))

        return theme_classes
    
    def copy_and_load_current_theme(self, new_name: str) -> int:
        '''returns 0 if ok, 1 if no editable dir exists, 2 if copy fails'''
        current_theme_dir = self.current_theme_file.parent        
        editable_dir = Path()
        
        # find the first editable patchbay_themes directory
        # creating it if it doesn't exists
        for search_path in self.theme_paths:
            if search_path.exists():
                if not search_path.is_dir():
                    continue
                
                if os.access(search_path, os.W_OK):
                    editable_dir = search_path
                    break
            else:
                try:
                    search_path.mkdir(parents=True)
                except:
                    continue
                editable_dir = search_path
                break
        
        if not editable_dir.name:
            return 1

        new_dir = editable_dir.joinpath(new_name)
        
        try:
            shutil.copytree(current_theme_dir, new_dir)
        except:
            return 2
        
        self.current_theme_file = new_dir.joinpath('theme.conf')
        
        conf = configparser.ConfigParser()
        try:
            # we don't need the file_list
            # it is just a convenience to mute conf.read
            file_list = conf.read(self.current_theme_file)
            
            # rename the theme in its file with the new name
            # remove all translated names to prevent them to pass over
            # the new name.
            if 'Theme' in conf.keys():
                conf_theme = conf['Theme']
                conf_theme['Name'] = new_name
                for key in conf_theme.keys():
                    if key.lower().startswith('name[') and key.endswith(']'):
                        conf_theme.pop(key)

            with open(self.current_theme_file, 'w') as f:
                conf.write(f)
            conf.clear()
        except:
            _logger.error(
                f'Impossible to rename Theme in file {self.current_theme_file}')

        self._update_theme()
        return 0
    
    def activate_watcher(self, yesno: bool):
        if yesno:
            self._theme_file_timer.start()
        else:
            self._theme_file_timer.stop()
