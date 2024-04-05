# by strotlog 2024

from io import BufferedRandom
import json
import random
import sys

from json_data_structures import MusicJson, Note, Voice
from notes import bytevalue


def main() -> None:
    if len(sys.argv) < 2:
        print("Error: Must specify a ROM file whose MUSIC WILL BE OVERWRITTEN")
        exit(1)

    with open("music.json", "r") as music_json_file:
        all: MusicJson = json.load(music_json_file)

    with open(sys.argv[1], "r+b") as rom_file_to_write:  # <- read, write, and it's binary
        for songset in all['songsets']:
            for song in songset['songs']:
                for i, voice in enumerate(song['voices']):
                    if i >= 4:
                        break  # only randomize 4 voices for now
                    process_voice(rom_file_to_write, voice)

    print('Done. Your ROM was modified.')


def process_voice(rom_file_to_write: BufferedRandom, voice: Voice) -> None:
    firstNote = True
    prevOriginalNote = 0x0
    prevModifiedNote = 0x0

    def process_note(note: Note) -> None:
        nonlocal firstNote
        nonlocal prevOriginalNote
        nonlocal prevModifiedNote
        if firstNote:
            firstNote = False
            prevOriginalNote = bytevalue(note['note'])
            prevModifiedNote = prevOriginalNote
        else:
            origInterval = bytevalue(note['note']) - prevOriginalNote
            newInterval = random.choice((-1, 1)) * origInterval
            if prevModifiedNote + newInterval >= 0xc8 or prevModifiedNote + newInterval < 0x80:
                newInterval = -newInterval
            prevOriginalNote = bytevalue(note['note'])
            prevModifiedNote = prevModifiedNote + newInterval
            if prevModifiedNote >= 0xc8 or prevModifiedNote < 0x80:
                # THIS IS A HACK idk why it goes out of range to 0x10e without this
                prevModifiedNote = (0x80 + 0xc8)//2
            rom_file_to_write.seek(int(note['address']['rom'], 16))
            rom_file_to_write.write(bytes([prevModifiedNote]))

    for section in voice['sections']:
        if 'empty' not in section:
            for note in section['notes']:
                if 'note' in note:
                    process_note(note)
                if 'subsection' in note:
                    for subsecnote in note['subsection']['notes']:
                        if 'note' in subsecnote:
                            process_note(subsecnote)
