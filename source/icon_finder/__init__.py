import logging
import xdg


_logger = logging.getLogger(__name__)
_all_icons = dict[str, str]()

def _kind_match(input: str) -> str:
    return input.replace('_', ' ').replace('-', ' ').lower()

def _parse():
    for path in xdg.xdg_data_dirs():
        hicolor = path / 'icons' / 'hicolor'
        if not hicolor.is_dir():
            continue
        
        for sizes_dir in hicolor.iterdir():
            if not sizes_dir.is_dir():
                continue
            
            apps_dir = sizes_dir / 'apps'
            if not apps_dir.is_dir():
                continue
            
            for image_file in apps_dir.iterdir():
                if not image_file.is_file():
                    continue
                icon_name = image_file.name.rpartition('.')[0]
                icon_ref = _kind_match(icon_name.rpartition('.')[2])
                if icon_ref in _all_icons:
                    continue
                
                _all_icons[icon_ref] = icon_name
                
    for path in xdg.xdg_data_dirs():
        pixmaps = path / 'pixmaps'
        if not pixmaps.is_dir():
            continue
        
        for image_file in pixmaps.iterdir():
            if not image_file.is_file():
                continue
            icon_name = image_file.name.rpartition('.')[0]
            icon_ref = _kind_match(icon_name)
            if icon_ref in _all_icons:
                continue
            _all_icons[icon_ref] = icon_name

def get_icon_name_for(app_name: str) -> str:
    return _all_icons.get(_kind_match(app_name), '')

def refresh():
    _all_icons.clear()
    _parse()


# at module import, icon dirs are parsed and _all_icons is written
try:
    _parse()
except Exception as e:
    _logger.warning(f'Failed to parse icon dirs\n{str(e)}')
    
