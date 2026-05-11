#!/usr/bin/python3

import os
from pathlib import Path
import sys

RESOURCE_DIRS = ('scalable', 'app_icons', 'scalables',
                    'fonts', 'cursors')

def _generate_rc():
    contents = '<RCC version="1.0">\n'
    contents += '   <qresource prefix="/">\n'

    os.chdir(os.path.dirname(sys.argv[0]))

    for resource_dir in RESOURCE_DIRS:
        for root, dirs, files in os.walk(resource_dir):
            #exclude hidden files and dirs
            files = [f for f in files if not f.startswith('.')]
            dirs[:] = [d for d in dirs if not d.startswith('.')]

            for file in files:
                contents += '       <file>%s/%s</file>\n' % (root, file)

    contents += '   </qresource>\n'
    contents += '</RCC>\n'

    with open('resources.qrc', 'w') as f:
        f.write(contents)

def _generate_modules():
    res = Path(__file__).parents[1] / 'source' / 'resources'
    res.mkdir(exist_ok=True)
    
    scalables = Path(__file__).parent / 'scalables'
    scalables.mkdir(exist_ok=True)

    scalables_dict = dict[str, dict[str, str]]()

    for theme in 'dark', 'light':
        theme_path = scalables / theme
        print(theme_path)
        for root, dirs, files in os.walk(theme_path):
            #exclude hidden files and dirs
            files = [f for f in files if not f.startswith('.')]
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            for file in files:
                file_path = Path(root) / file
                if not file_path.name.endswith(('.svg', '.svgz')):
                    continue

                folder = file_path.parent.name
                folder_dict = scalables_dict.get(folder)
                if folder_dict is None:
                    folder_dict = scalables_dict[folder] = dict[str, str]()
                name = \
                    file_path.name.partition('.')[0].upper().replace('-', '_')
                folder_dict[name] = str(file_path.relative_to(theme_path))

    # print(scalables_dict)
    lines = ['from pathlib import Path',
             '']
    for folder, folder_dict in scalables_dict.items():
        lines.append('')
        lines.append(f'class {folder}:')
        for name, path in folder_dict.items():
            lines.append(f'    {name} = "{path}"')
    
    generated_resources = Path(__file__).parents[1] / 'source' / 'resources'
    generated_scalables = generated_resources / 'scalables'
    generated_scalables.mkdir(parents=True, exist_ok=True)
    
    with open(generated_scalables / '__init__.py', 'w') as f:
        f.write('\n'.join(lines))    


if __name__ == '__main__':
    _generate_rc()
    _generate_modules()

