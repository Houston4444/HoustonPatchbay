import json
from typing import Any


def from_json_to_str(input_dict: dict[str, Any]) -> str:
    '''for a canvas json dict ready to be saved,
    return a str containing the json contents with a 2 chars indentation
    and xy pos grouped on the same line.'''

    PATH_OPENING = 0
    PATH_IN = 1
    PATH_CLOSING = 2

    json_str = json.dumps(input_dict, indent=2)
    final_str = ''
    
    path = list[str]()
    path_step = PATH_IN
    
    for line in json_str.splitlines():
        strip = line.strip()
        
        if line.endswith(('{', '[')):
            path_name = ''
            if strip.startswith('"') and strip[:-1].endswith('": '):
                path_name = strip[1:-4]

            n_spaces = 0
            for c in line:
                if c != ' ':
                    break
                n_spaces += 1
            
            path = path[:(n_spaces // 2)]
            path.append(path_name)
            path_step = PATH_OPENING
        
        elif line.endswith(('],', ']', '},', '}')):
            path_step = PATH_CLOSING
        
        else:
            path_step = PATH_IN
        
        if len(path) > 1 and path[1] == 'views' and path[-1] == 'pos':
            # set box pos in one line
            if path_step == PATH_OPENING:
                final_str += line
            
            elif path_step == PATH_CLOSING:
                final_str += strip
                final_str += '\n'
                
            else:
                final_str += strip
                if line.endswith(','):
                    final_str += ' '
                
        elif len(path) >= 6 and path[1] == 'portgroups':
            # organize portgroups
            if len(path) == 6:
                if path_step == PATH_OPENING:
                    final_str += line
                    
                elif path_step == PATH_CLOSING:
                    final_str += strip
                    final_str += '\n'
                
                else:
                    # only concerns "above_metadatas"
                    final_str += line[1:]
            
            elif len(path) == 7 and path[-1] == 'port_names':
                if path_step == PATH_OPENING:
                    final_str += strip
                
                elif path_step == PATH_CLOSING:
                    final_str += strip
                    if line.endswith(','):
                        final_str += '\n'
                
                else:
                    final_str += strip
                    if line.endswith(','):
                        final_str += '\n'
                        for i in range(26):
                            final_str += ' '
            
            else:
                final_str += strip
                if strip.endswith(','):
                    final_str += ' '
            
        else:
            final_str += line
            final_str += '\n'

        if path_step == PATH_CLOSING:
            path = path[:-1]

    return final_str