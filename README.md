### Changes the notes in Super Metroid

I did not originate this idea, that was ironrusty or jooniejoone. Rusty made several tests that sounded eerie and interesting. Something special about this game perhaps.

Basically, this is a very simple "music rando" with 2 parts: music extraction (should work on romhacks and various randos in addition to vanilla), and music randomization, which is very simple.

The result of extraction is not stored here because it's sort of like a "sheet music" of Kenji Yamamoto and Minako Hamano's work.

## Requirements (there's only one):
- Python 3

To use:

```sh
$ python extractmusic.py SuperMetroid.sfc > music.json
$ cp SuperMetroid.sfc RomToBeModified.sfc
$ python <name of any of the rando scripts>.py RomToBeModified.sfc
```

Please don't overwrite your actual backup copy of the real ROM. No warranties.

### Future

Next obvious thing would be more randomizing .py's with different algorithms.

The JSON format might change a bit. This tool could turn web-based to increase options complexity and usability. Let me know what features you think might be most useful. One thing that's been requested was more than one version of item fanfare.
