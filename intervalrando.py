# by strotlog 2024

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
            if i >= 4:
                break # only randomize 4 voices for now
            firstNote = True
            prevOriginalNote = 0x0
            prevModifiedNote = 0x0
            for _, section in enumerate(voice['sections']):
                if 'empty' not in section:
                    for _, note in enumerate(section['notes']):
                        if 'note' in note:
                            if firstNote:
                                firstNote = False
                                prevOriginalNote = bytevalue(note['note'])
                                prevModifiedNote = prevOriginalNote
                            else:
                                origInterval = bytevalue(note['note']) - prevOriginalNote
                                newInterval = random.choice([-1, 1]) * origInterval
                                if prevModifiedNote + newInterval >= 0xc8 or prevModifiedNote + newInterval < 0x80:
                                    newInterval = -newInterval
                                prevOriginalNote = bytevalue(note['note'])
                                prevModifiedNote = prevModifiedNote + newInterval
                                if prevModifiedNote >= 0xc8 or prevModifiedNote < 0x80:
                                    prevModifiedNote = (0x80 + 0xc8)//2 # THIS IS A HACK idk why it goes out of range to 0x10e without this
                                rom_file_to_write.seek(int(note['address']['rom'], 16))
                                rom_file_to_write.write(bytes([prevModifiedNote]))

                        if 'subsection' in note:
                            for _, subsecnote in enumerate(note['subsection']['notes']):
                                    if 'note' in subsecnote:
                                        if firstNote:
                                            firstNote = False
                                            prevOriginalNote = bytevalue(subsecnote['note'])
                                            prevModifiedNote = prevOriginalNote
                                        else:
                                            origInterval = bytevalue(subsecnote['note']) - prevOriginalNote
                                            newInterval = random.choice([-1, 1]) * origInterval
                                            if prevModifiedNote + newInterval >= 0xc8 or prevModifiedNote + newInterval < 0x80:
                                                newInterval = -newInterval
                                            prevOriginalNote = bytevalue(subsecnote['note'])
                                            prevModifiedNote = prevModifiedNote + newInterval
                                            if prevModifiedNote >= 0xc8 or prevModifiedNote < 0x80:
                                                prevModifiedNote = (0x80 + 0xc8)//2 # THIS IS A HACK idk why it goes out of range to 0x10e without this
                                            rom_file_to_write.seek(int(subsecnote['address']['rom'], 16))
                                            rom_file_to_write.write(bytes([prevModifiedNote]))

print('Done. Your ROM was modified.')
