#!/bin/env python3
 
import os
from pathlib import Path
import subprocess

if __name__ == '__main__':
    print(f'{__file__=}')
    source_dir = Path(__file__).parent
    manual_dir = source_dir.parent
    
    langs = set[str]()
    
    # convert .adoc files to .html at the good path
    for adoc in source_dir.iterdir():
        if not adoc.name.endswith('.adoc'):
            continue
        langs.add(adoc.name[:2])
        adoc_out = manual_dir / Path(adoc.name[:-5].replace('.', '/')) / 'index.html'
        adoc_out.parent.mkdir(parents=True, exist_ok=True)
        print(f'asciidoctor -d book {adoc} -o {adoc_out}')
        subprocess.run(['asciidoctor', '-d', 'book', adoc, '-o', adoc_out])

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