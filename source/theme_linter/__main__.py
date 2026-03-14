import configparser
import logging
from pathlib import Path
import sys

from qtpy.QtGui import QColor

sys.path.insert(0, str(Path(__file__).parents[1]))

from patchbay.patchcanvas import theme, theme_manager

from color import Color, compare_colors

_logger = logging.getLogger(__name__)


def qcolor_name(qcolor: QColor) -> str:
    if qcolor.alphaF() == 1.0:
        return qcolor.name()

    alphaf = '%.2f' % qcolor.alphaF()
    while alphaf.endswith('0'):
        alphaf = alphaf[:-1]
        if alphaf[-1] == '.':
            alphaf += '0'
            break

    return f'{qcolor.name()} ** {alphaf}'

def tuple_key(input: tuple[str, str]) -> str:
    return f'[{input[0]}]{input[1]}'

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
    th.read_theme(thd, theme_path, for_linter=True)    
    aliases = dict[str, str]()
    colors = dict[str, Color]()

    rwt_aliases: dict = thdn.get('aliases', {})
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
    aliases_colors = dict[str, set[str]]()
    for alias, color_name in aliases.items():
        exst = aliases_colors.get(color_name)
        if exst is None:
            aliases_colors[color_name] = {alias}
        else:
            aliases_colors[color_name].add(alias)
        
        color = colors.get(color_name)
        if color is None:
            color = Color(color_name)
            colors[color_name] = color

    for section_name, section in conf.items():
        if section_name in ('Theme', 'aliases'):
            continue
        
        for key, value in section.items():
            if not (key.endswith('-color')
                    or key in ('background', 'background2')):
                continue

            for word in value.split():
                if word in aliases:
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
                    continue
                
                color_name = qcolor_.name()
                
                if word.startswith(('#', '-#', 'rgb(', 'rgba(')):
                    if qcolor_.alphaF() != 1.0:
                        new_col_name = qcolor_name(qcolor_)
                        _logger.warning(
                            f'color {word} has an alpha channel, '
                            f'prefer to use {new_col_name}')
                        thdn[section_name][key] = value.replace(word, new_col_name)
                    color = colors.get(color_name)
                    if color is None:
                        color = Color(color_name)
                        colors[color_name] = color
                        
                    color.exists_in.add(f'[{section_name}]{key}')
    
    for color_name, color in colors.items():
        if not color.exists_in:
            continue

        multi_uses = '\n    '.join(color.exists_in)

        if color_name in aliases_colors.keys():
            multi_alias = '|'.join(aliases_colors[color_name])
            _logger.warning(
                f'{color_name} is used in\n    {multi_uses}\n'
                f'        could be replaced by alias {multi_alias}')
        elif len(color.exists_in) >= 2:
            _logger.warning(
                f'{color_name} is used in\n    {multi_uses}\n'
                '        It would be better to choose an alias')
    
    compare_colors(colors)

    # print('--- USED COLORS ---')
    # sorted_colors = sorted(colors.keys())
    # for scol in sorted_colors:
    #     if scol in aliases_colors.keys():
    #         print(scol, '|'.join(aliases_colors[scol]))
    #     else:
    #         print(scol)
        
    #     for oth, ratio in colors[scol].equivalents:
    #         ratio_str = '%.2f' % ratio
    #         aliases = aliases_colors.get(oth)
    #         if aliases is None:
    #             print(f'    = {oth} * {ratio_str}')
    #         else:
    #             for alias_ in aliases:
    #                 print(f'    = {alias_} * {ratio_str}')            

    for thchild in th.all_childs():
        for attr in theme._DEFAULT_STYLE_ATTRS.keys():
            value = thchild._attrs.get(attr)
            if value is None:
                continue
            if thchild._parent.get_value_of(attr) == value:
                _logger.warning(f'[{thchild._path}]{attr} already defined')

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