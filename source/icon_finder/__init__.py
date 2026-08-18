import logging
import threading
import time
import xdg


_logger = logging.getLogger(__name__)
_all_icons = dict[str, str]()
'''dict containing program name as key and icon file name as value'''
_st_mtimes = dict[str, float]()
'''dict containing file path as key and last modification time as value'''
_no_icon_apps = set[str]()
'''Stock app names without icon found, to avoid useless files parsing'''
_last_parse_time = [0.0]
'''Stock last parse time in a one element list, to avoid 'global' usage'''


_parse_thread: threading.Thread


def _kind_match(input: str) -> str:
    return input.replace('_', ' ').replace('-', ' ').lower()

def _parse_desktop_files():
    parsed_desktops = set[str]()
    
    for path in [xdg.xdg_data_home()] + xdg.xdg_data_dirs():
        apps_dir = path / 'applications'
        if not apps_dir.is_dir():
            continue
        
        # remember last modification time of applications folder
        # skip if no change since last parse
        st_mtime = apps_dir.stat().st_mtime
        if st_mtime == _st_mtimes.get(str(apps_dir)):
            continue
        _st_mtimes[str(apps_dir)] = st_mtime
        
        for desktop_file in apps_dir.iterdir():
            if desktop_file.name in parsed_desktops:
                continue
            
            if not desktop_file.name.endswith('.desktop'):
                continue
            
            parsed_desktops.add(desktop_file.name)
            
            # remember last modification time of .desktop file
            # skip if no change since last parse
            st_mtime = desktop_file.stat().st_mtime
            if st_mtime == _st_mtimes.get(str(desktop_file)):
                continue
            _st_mtimes[str(desktop_file)] = st_mtime
            
            app_name, icon_name = '', ''
            
            try:
                with open(desktop_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.startswith('Name='):
                            app_name = line.partition('=')[2].strip()
                        elif line.startswith('Icon='):
                            icon_name = line.partition('=')[2].strip()
                        elif (line.startswith('[')
                                and line.strip() != '[Desktop Entry]'):
                            break
                        if app_name and icon_name:
                            break
            except:
                continue
            
            if app_name:
                _all_icons[_kind_match(app_name)] = icon_name
    
    _last_parse_time[0] = time.time()

def _try_parse_desktop_files():
    try:
        _parse_desktop_files()
    except Exception as e:
        _logger.warning(
            f'Failed to parse desktop files to find icons\n{str(e)}')

def get_icon_name_for(app_name: str) -> str:
    if _parse_thread.is_alive():
        # still parsing .desktop files, wait
        _parse_thread.join()
    
    if app_name in _no_icon_apps:
        return app_name.lower()

    ret = _all_icons.get(_kind_match(app_name))
    if ret is None:
        if time.time() - _last_parse_time[0] < 1.0:
            # parse has been done less than 1 second ago
            return app_name.lower()

        # This app could have been installed after this program startup
        # re-parse .desktop files to find it (it should be quite fast 
        # because only modified files are checked)
        _try_parse_desktop_files()
        ret = _all_icons.get(_kind_match(app_name))
        if ret is None:
            _no_icon_apps.add(app_name)
            return app_name.lower()
    return ret
    

# at module import, desktop files are parsed in another thread.
# The complete parse may have a duration > 200ms,
# but it really depends on the hard drive speed (SSD or HDD).
_parse_thread = threading.Thread(target=_try_parse_desktop_files)
_parse_thread.start()

