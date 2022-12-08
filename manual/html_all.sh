#!/bin/bash

if ! which asciidoctor >/dev/null;then
    echo "asciidoctor is missing, please install it"
    exit 1
fi

cd `dirname "$0"`

for lang in en fr;do
    cd $lang

    echo "-> html: $lang/manual.adoc"
    asciidoctor -d book manual.adoc

    if [[ "$lang" == en ]];then
        echo "-> html: en/theme_edit.adoc"
        asciidoctor -d book theme_edit.adoc
    fi

    cd ..
done
