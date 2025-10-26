#!/bin/bash

# This is a little script for refresh raysession.pro and update .ts files.
# TRANSLATOR: if you want to translate the program, you don't need to run it !

contents=""

this_script=`realpath "$0"`
locale_root=`dirname "$this_script"`
code_root=`dirname "$locale_root"`
cd "$code_root/resources/ui/"

for file in *.ui;do
    contents+="FORMS += ../resources/ui/$file
"
done


cd "$code_root/source/patchbay"

for file in *;do
    if [[ "$file" =~ .py$ ]];then
        if cat "$file"|grep -q _translate;then
            contents+="SOURCES += ../source/patchbay/${file}
"
        fi
    elif [ -d "$file" ];then
        dir="$file"
        [ "$dir" == ui ] && continue
        # cd "$dir"
        for file in $dir/*.py;do
            if cat "$file"|grep -q _translate;then
                contents+="SOURCES += ../source/patchbay/${file}
"
            fi
        done
    fi
done
# for file in *.py;do
#     if cat "$file"|grep -q _translate;then
#         contents+="SOURCES += ../patchbay/${file}
# "
#     fi
# done

# cd patchcanvas

# for file in *.py;do
#     if cat "$file"|grep -q _translate;then
#         contents+="SOURCES += ../patchbay/patchcanvas/${file}
# "
#     fi
# done

contents+="
TRANSLATIONS += patchbay_en.ts
TRANSLATIONS += patchbay_fr.ts
"

echo "$contents" > "$locale_root/patchbay.pro"

pylupdate5 "$locale_root/patchbay.pro"
