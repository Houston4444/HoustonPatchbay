#!/bin/env python3

'''This script checks if there are differences in file organization
between english version and others. It doesn't means that theses
differences are really problematic, but something is to update somewhere,
probably for a translator.

It never edits files, it only prints some log.'''


from pathlib import Path
from typing import Iterator, TypeAlias

IndexType: TypeAlias = tuple[str, ...]


def sub_index(filename: str) -> IndexType:
    '''split identifier for a .adoc file. Identifier is the prefix
    before the first '_'. for example, if filename is 02C_tralala.adoc,
    the output will be ('02', 'C')'''
    index = list[str]()
    current = ''
    
    for c in filename.partition('_')[0]:
        if current == '':
            current = c
        else:
            if current.isdigit() is c.isdigit():
                current = current + c
            else:
                index.append(current)            
                current = c
    
    index.append(current)
    return tuple(index)

class AdocParser:
    def __init__(self, index: IndexType = (), filename=''):
        self.index = index
        self.filename = filename
        self.childs = dict[IndexType, AdocParser]()
    
    def __repr__(self) -> str:
        if self.filename == '':
            return 'AdocParser(MAIN)'
        return f'AdocParser({self.filename})'
    
    def add_child(self, index: IndexType, filename: str):
        if len(index) <= len(self.index):
            print(f"can't add child, {index=} {self.index=}")
            return
        
        for i, idstr in enumerate(index):
            if i < len(self.index) and self.index[i] != idstr:
                print(f'attempt to add_child {index=} to {self.index=}')
                return
        
        if len(index) == len(self.index) + 1:
            self.childs[index] = AdocParser(index, filename)
            return
        
        child = self.childs.get(index[:len(self.index)+1])
        if child is None:
            print(f'attempt to add sub child before child {index=} {self.index=}')
            return
        child.add_child(index, filename)
        
    def parse(self) -> Iterator[tuple[IndexType, str]]:
        for index, adoc_parser in self.childs.items():
            yield index, adoc_parser.filename
            yield from adoc_parser.parse()
    
    def get(self, filename: str, index: IndexType | None =None) -> 'AdocParser | None':
        if index is None:
            index = sub_index(filename)
            
        if len(index) == len(self.index) + 1:
            return self.childs.get(index)
        
        child = self.childs.get(index[:len(self.index) + 1])
        if child is not None:
            return child.get(filename, index)

    def check_includes(self, path: Path):
        full_path = path / self.filename
        if not full_path.exists():
            print(f'failed to check includes for {full_path}, does not exists')
            return

        with open(full_path, 'r') as f:
            contents = f.read()
        
        includes = set[str]()
        for line in contents.splitlines():
            if line.startswith('include::') and line.endswith('.adoc[]'):
                includes.add(line.partition('[')[0].rpartition('::')[2])
        
        for adoc_parser in self.childs.values():
            if adoc_parser.filename not in includes:
                print(f'{path.name}:{adoc_parser.filename} NOT INCLUDED in {self.filename}')
            else:
                adoc_parser.check_includes(path)


if __name__ == '__main__':
    this_dir = Path(__file__).parent    
    main_adocs = dict[str, AdocParser]()

    # fill the main_adoc_parser with all present files in english version
    for file in this_dir.iterdir():
        if not (file.name.startswith('en') and file.name.endswith('.adoc')):
            continue

        module = file.name[3:-5]
        main_adocs[module] = AdocParser()
        en_parts_dir = this_dir / f'en.{module}.parts'
        if en_parts_dir.exists():
            filenames = [f.name for f in en_parts_dir.iterdir()
                         if f.is_file() and f.name.endswith('.adoc')]
            id_filenames = dict[IndexType, str]()
            for filename in filenames:
                id_filenames[sub_index(filename)] = filename

            for i in range(1 + max([len(idx) for idx in id_filenames])):
                for index, filename in id_filenames.items():
                    if len(index) == i:
                        main_adocs[module].add_child(index, filename)
    
    for file in this_dir.iterdir():
        if not file.name.endswith('.adoc'):
            continue
        with open(file, 'r') as f:
            contents = f.read()
        
        module = file.name[3:-5]
        includes = set[str]()

        # check all the .adoc files in /source
        for line in contents.splitlines():
            if line.startswith('include::') and line.endswith('.adoc[]'):
                includes.add(line.partition('[')[0].rpartition('/')[2])
                
        for include in includes:        
            parser = main_adocs[module].get(include)
            if parser is None:
                print(f'Unknown include {include}')
                continue
            
            name_base = file.name.rpartition('.')[0]
            parser.check_includes(file.parent / f'{name_base}.parts')

                        
                        
                    
        

