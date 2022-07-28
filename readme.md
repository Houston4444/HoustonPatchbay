What is it ?
------------

This a patchbay for JACK used by RaySession and Patchance, usable by other python Qt5 softwares.

This is not a program itself, it is used as a git submodule in RaySession and Patchance.
The 'patchbay' folder is linked into the source code of theses projects.

How to implement this ?
------------

To use it, look how it is implemented:
in Raysession:
* src/gui/ray_patchbay_manager

in Patchance:
* src/patchance_patchbay_manager


You will need to add a graphicsview to your window promoting its class with PatchGraphicsView.
Inherits the classes PatchbayManager and Callbacker.
when all is ready to be instantiate, run PatchbayManager.app_init().

to use it with JACK, connect all the JACK events to the methods decorated with @later_by_batches (no matter the thread)

This module also contains the following widgets:
* canvas options dialog
* Jack server widgets (containing Zoom Widget, samplerate, buffersize, xruns, DSP load and label if JACK not running)
* filter frame (used to search a box with pattern, also containing Audio|Midi filters)
* global context menu
* Port Info Dialog

all theses widgets are optional or heritable.

Just after the QApplication initialization, install the translator for the patchbay (see patchance.py)

and... ask questions ! I won't spend time to document this if nobody else use it ;).
Note that the API can change if other programs need it, that's why it is a git submodule and not a python lib (git submodule are always related to a version).