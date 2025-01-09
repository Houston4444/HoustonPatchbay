# List of possible ideas for the patchbay

Some of them could be done fastly, other ones with a very long effort, sometimes it's hard to evaluate needed time. It is highly unlikely that all these ideas will be realised one day. But if you can develop in Python, making one of theses features, (or another good idea) would be very welcome (of course we need to talk before).

## Matrix connections (long)

The PatchbayManager could also manage a Matrix connections view (a bit like Ardour does). A widget in the tool bar could switch between patchbay/matrix view. The matrix design could follow the patchcanvas theme style.
This should be developped in a folder named 'matrix' (for example), in the patchbay folder. This feature doesn't interfers much with the rest of code, so it is a good project for someone else than me. 

## Zones (long)

The idea is that user can defines zones in the canvas, maybe like when selecting boxes with a key modifier. Theses zones could be colored with a semi-transparent color (behind the boxes). Then, box positions will be defined in the zone, and the zone position in the canvas. Keys for 'zone' already exists in the saved group positions. User could have possibility to move the zone. Zones could appear/disappear with boxes (experience will say).

## Vu-meters next to the ports (long)

This needs a C++ JACK client, and probably connect each port with meter to a new jack port. I am not sure it is really doable nicely, and if it is very resource-intensive.

## Views (quick)

Add a widget to the tool bar to can change the view (box positions), but also can restore the previous one. This is fast to do, because it already manages this while changing port types filter (AUDIO|MIDI|CV). Currently, view ID is a flag, we just need to affect higher bytes to different views and it should works.

## Arrange (middle)

Sometimes, because boxes positions are saved, and depending on the situation some boxes can be very far from others, and connections are not the same, it would be nice to say to the program "Please auto-arrange the boxes". The idea IS NOT to make something automatic changing at each box or connection added/moved, it would be a nightmare, but a simple script to execute.
The problematic is that there is not only one way to auto-arrange the boxes, and the best arrangment is this one the user makes. There could be many different ways to auto-arrange, many different scripts. With the Views feature, we could have "auto-arrange in a new view", and have possibility to restore the previous view.

## PipeWire Video Ports

All is in the title. The program should say if this feature is enable. We need to make new style for Video ports, modify themes, add filter check box, etc... 

## Write Metadatas or rename ports differently (not so long, but needs attention)

Currently, the patchbay only READS* the following JACK metadatas:
* pretty name (for ports)
* client icon (for boxes)
* port order
* port group

Add possibility to write metadatas opens a Pandora's box. Several questions then arise :
* Once JACK is stopped/restarted, all metadatas are lost, so, should the program rewrite them ? If yes, should it write only the metadatas it created itself ?
* What to do if metadatas already exists ? They are probably created by the JACK client itself, which is in a better position than our program to know what metadatas to write.
* Should we write port order if we can change it ? A program is not supposed to re-organize its tracks in its GUI if theses metadatas change.

The possibility to have things internally saved in config but not affecting metadatas also exists. For example, rename a port in the patchbay could save the port display name in the config. It already exists for portgroups, if we follow portgroups template for pretty-name, it would works this way:

* the port has no pretty-name metadata, the normal name is used
* If this port is renamed by user, config saves the new display name with a key above_metadata=False
* If pretty-name metadata is affected, this new pretty-name is used
* If user renames the port, config saves the new display name with a key above_metadata=True
* User should have the possibility to forget its custom display name

This method has the advantage of not disturbing the rest of the ecosystem. At the opposite, changing a name and have this name displayed in other DAWS is nice.

*the patchbay module has no JACK client, but it is connected to a JACK client in the main program (RaySession or Patchance).

