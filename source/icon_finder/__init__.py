import logging
import threading
import xdg


_logger = logging.getLogger(__name__)
_all_icons = dict[str, str]()
_parse_thread: threading.Thread


def _kind_match(input: str) -> str:
    return input.replace('_', ' ').replace('-', ' ').lower()

def _parse_desktop_files():
    parsed_desktops = set[str]()
    
    for path in xdg.xdg_data_dirs():
        apps_dir = path / 'applications'
        if not apps_dir.is_dir():
            continue
        for desktop_file in apps_dir.iterdir():
            if desktop_file.name in parsed_desktops:
                continue
            
            if not desktop_file.name.endswith('.desktop'):
                continue
            
            parsed_desktops.add(desktop_file.name)
            
            try:
                with open(desktop_file, 'r') as f:
                    contents = f.read(65535)
            except:
                continue
            
            lines = contents.splitlines()
            app_name, icon_name = '', ''
            
            for line in lines:
                if line.startswith('Name='):
                    app_name = line.partition('=')[2]
                elif line.startswith('Icon='):
                    icon_name = line.partition('=')[2]
                
                if app_name and icon_name:
                    break
            
            if app_name:
                _all_icons[_kind_match(app_name)] = icon_name

def _try_parse_desktop_files():
    try:
        _parse_desktop_files()
    except Exception as e:
        _logger.warning(
            f'Failed to parse desktop files to find icons\n{str(e)}')

def get_icon_name_for(app_name: str) -> str:
    if _parse_thread.is_alive():
        _parse_thread.join()
    
    return _all_icons.get(_kind_match(app_name), '')


# at module import, desktop files are parsed in another thread.
# The complete parse may have a duration of > 100ms at first startup,
# then > 50ms, but it really depends on the hard drive speed (SSD or HDD).
_parse_thread = threading.Thread(target=_try_parse_desktop_files)
_parse_thread.start()

