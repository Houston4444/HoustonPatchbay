# HoustonPatchbay Manual

Here are the source and the html manual in multiple languages.

The manual is written in the asciidoctor format, allowing to generate html pages easily with a very light syntax (like markdown, with additions).

The manual is already generated in html to avoid the asciidoctor dependency.

## Translate it !

If you want to translate this manual, it would be better to first translate the program itself, but you are welcome !
* Create an account on Codeberg.org
* Fork the **HoustonPatchbay** project
* download your fork
* go to `manual/source` directory, copy `en.patchbay.adoc` to `XX.patchbay.adoc` and `en.patchbay.parts` to `XX.patchbay.parts` (replacing `XX` with the 2 letters identifying your language).
* translate the new .adoc files
* still from `manual/source`, run `./html_all.py`, it will convert your .adoc files to .html pages
* in the project directory, run `git add .`
* run `git checkout -b manual_tr_XX`
* run `git commit -m "translate manual in XX"`
* run `git push origin manual_tr_XX`
* In Codeberg website, submit your pull request (it should appears)
