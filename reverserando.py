# by strotlog 2024
# this one is more just a demonstration of really simple note modification. it's not even random. intervalrando.py will probably sound much better!

import json
import random
import sys

all = json.load(open("music.json", "r"))

notenames = "C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"

def bytevalue(notename):
    octave = int(notename[-1])
    keyname = notename[:-1]
    keynum = notenames.index(keyname)
    return 0x80 + (octave-1)*12 + keynum

if len(sys.argv) < 2:
    print("Error: Must specify a ROM file whose MUSIC WILL BE OVERWRITTEN")
    exit(1)

rom_file_to_write = open(sys.argv[1], "r+b") # <- read, write, and it's binary

for _, songset in enumerate(all['songsets']):
    for _, song in enumerate(songset['songs']):
        for i, voice in enumerate(song['voices']):
            if i >= 3:
                break # only randomize 5 voices for now
            voice_notes = []
            for _, section in enumerate(voice['sections']):
                if 'empty' not in section:
                    for _, note in enumerate(section['notes']):
                        if 'note' in note:
                            voice_notes.append(note)

                        if 'subsection' in note:
                            for _, subsecnote in enumerate(note['subsection']['notes']):
                                voice_notes.append(subsecnote)
            for note_whose_address_to_use, note_whose_note_to_use in zip(voice_notes, reversed(voice_notes)):
                rom_file_to_write.seek(int(note_whose_address_to_use['address']['rom'], 16))
                rom_file_to_write.write(bytes([bytevalue(note_whose_note_to_use['note'])]))

print('Done. Your ROM was modified.')
