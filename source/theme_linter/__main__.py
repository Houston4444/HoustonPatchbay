import configparser
import logging
from pathlib import Path
import sys

from qtpy.QtGui import QColor

sys.path.insert(0, str(Path(__file__).parents[1]))

from patchbay.patchcanvas import theme, theme_manager, canvas

_logger = logging.getLogger(__name__)


def qcolor_name(qcolor: QColor) -> str:
    if qcolor.alphaF() == 1.0:
        return qcolor.name()

    alphaf = '%.3f' % qcolor.alphaF()
    while alphaf.endswith('0'):
        alphaf = alphaf[:-1]
        if alphaf[-1] == '.':
            alphaf += '0'
            break

    return f'{qcolor.name()} ** {alphaf}'

def read_theme(theme_path: Path):
    # tm = theme_manager.ThemeManager(
    #     (Path(__file__).parents[2] / 'themes',), outside=True)
    # tm.set_theme(theme_name)

    conf = configparser.ConfigParser()
    try:
        # we don't need the file_list
        # it is just a convenience to mute conf.read
        file_list = conf.read(theme_path)
    except configparser.DuplicateOptionError as e:
        _logger.error(str(e))
        return
    except:
        _logger.error(f"failed to open {theme_path}")
        return

    thd = theme_manager.ThemeManager._convert_configparser_object_to_dict(conf)
    thdn = {}
    for key, value in thd.items():
        thdn[key] = {}
        for kkey, vvalue in value.items():
            thdn[key][kkey] = vvalue
    
    th = theme.Theme()
    th.read_theme(thd, theme_path)    
    
    colors = dict[str, list[tuple[str, str]]]()
    aliases = dict[str, str]()

    rwt_aliases: dict = thdn['aliases']
    for section_name, section in conf.items():
        if section_name != 'aliases':
            continue
        
        for key, value in section.items():
            qcolor = theme._to_qcolor(value)
            if qcolor is None:
                _logger.warning(f'alias "{key}" is not a color')
                continue
            aliases[key] = qcolor_name(qcolor)
            rwt_aliases[key] = qcolor_name(qcolor)
    
    print(aliases)
    

    for section_name, section in conf.items():
        if section_name in ('Theme', 'aliases'):
            continue
        
        for key, value in section.items():
            if not (key.endswith('-color')
                    or key in ('background', 'background2')):
                continue

            for word in value.split():
                if word in aliases:
                    colors[aliases[word]] = []
                    _logger.debug(
                        f"Ignored word '{word}' in [{section_name}]{section} : "
                        f"it is an alias")
                    break
                
                if '*' in word:
                    continue

                try:
                    float(word)
                except:
                    pass
                else:
                    continue

                try:
                    qcolor_ = QColor(word)
                    assert qcolor_.isValid()
                except:
                    _logger.info(f"ignore  '{word}', not a color")
                
                color_name = qcolor_.name()
                color = colors.get(color_name)

                if color is None:
                    colors[color_name] = [(section_name, key)]
                else:
                    _logger.warning(
                        f"[{section_name}]{key} : {word}. Color already used in\n"
                        f"  {color}.\n"
                        "    Use an alias")
                    color.append((section_name, key))
    
    print('--- USED COLORS ---')
    sorted_colors = sorted(colors.keys())
    for scol in sorted_colors:
        col_aliases = list[str]()
        for alias, col in aliases.items():
            if col == scol:
                col_aliases.append(alias)

        print(scol, '|'.join(col_aliases))

    return thdn

def write_theme(thd: dict, theme_path: Path):
    conf = configparser.ConfigParser()
    out_path = theme_path.parent / 'theme.new.conf'

    for key, value in thd.items():
        conf[key] = value

    try:
        with open(out_path, 'w') as f:
            conf.write(f)
    except BaseException as e:
        _logger.error(f'Failed to write {out_path}\n{str(e)}')
    else:
        _logger.warning(f'File written: {out_path}')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        _logger.error("Put a theme file as argument, please !")
        sys.exit(1)

    theme_name = sys.argv[1]
    theme_path = Path(__file__).parents[2] / 'themes' / theme_name / 'theme.conf'
    
    thd = read_theme(theme_path)
    write_theme(thd, theme_path)