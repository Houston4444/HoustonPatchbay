#!/bin/env python3

"""
This executable converts all .adoc files in this 'source' folder
to .html files with asciidoctor executable.
All is already built when you download the source code
to prevent the asciidoctor dependency.
"""

 
import os
from pathlib import Path
import subprocess


def get_adoc_mtime(adoc: Path) -> float:
    '''return the last modification of a .adoc file
    or its included files. 0 if it does not exists.'''
    if not adoc.exists():
        return 0.0
    mtime = adoc.stat().st_mtime
    
    parts_name = '.'.join(adoc.name.split('.')[:-1] + ['parts'])
    parts_dir = adoc.parent / parts_name
    if parts_dir.exists():
        for adoc_sub in parts_dir.iterdir():
            if not adoc_sub.name.endswith('.adoc'):
                continue
            mtime = max(adoc_sub.stat().st_mtime, mtime)
    
    return mtime

def process_conversion():
    source_dir = Path(__file__).parent
    manual_dir = source_dir.parent
    
    css_path = source_dir / 'patchbay_manual.css'
    css_mtime = css_path.stat().st_mtime
    langs = set[str]()
    
    # convert .adoc files to .html at the good path
    for adoc in source_dir.iterdir():
        if not adoc.name.endswith('.adoc'):
            continue

        langs.add(adoc.name[:2])
        adoc_out_rel = Path(*adoc.name[:-5].split('.')) / 'index.html'
        adoc_out = manual_dir / adoc_out_rel
        
        if adoc_out.exists():
            if adoc_out.stat().st_mtime > max(get_adoc_mtime(adoc), css_mtime):
                # target is newer than all sources, skip it
                continue

        adoc_out.parent.mkdir(parents=True, exist_ok=True)
        print(f'asciidoctor -d book {adoc} -o {adoc_out}')
        subprocess.run(['asciidoctor', '-d', 'book', adoc, '-o', adoc_out])
        
        # substitute variables in html, 
        # they are used to simplify the file hierarchy.
        # With them, no need to specify as ../ as deep is the folder
        # to access images folder or translated html.
        dots = ''.join(['../' for i in range(1, len(adoc.name.split('.')))])
        path_no_lang = adoc_out_rel.relative_to(adoc_out_rel.parents[-2])
        subprocess.run(
            ['sed', '-i', '-e', f's|XXX_IMAGES_XXX|{dots}images/patchbay|g', '-e',
             f's|XXX_LANG_SWITCH_\\([a-z]*\\)_XXX|{dots}\\1/{path_no_lang}|g', adoc_out])

    # find all english present files
    en_packages = list[Path]()
    for root, dirs, files in os.walk(manual_dir / 'en'):
        for file in files:
            if file == 'index.html':
                en_packages.append(Path(root).relative_to(manual_dir / 'en'))

    # link absent htmls in a lang to english html
    for lang in langs:
        if lang == 'en':
            continue

        for en_package in en_packages:
            html_file = manual_dir / lang / en_package / 'index.html'
            if not html_file.exists():
                html_file.parent.mkdir(exist_ok=True, parents=True)
                html_en_file = manual_dir / 'en' / en_package / 'index.html'
                subprocess.run(['ln', '-s', '-r', html_en_file, html_file])
                
if __name__ == '__main__':
    process_conversion()