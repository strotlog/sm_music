# by strotlog 2024
# this one is more just a demonstration of really simple note modification.
# it's not even random. intervalrando.py will probably sound much better!

import json
import sys

from json_data_structures import MusicJson, Note
from notes import bytevalue


def main() -> None:
    if len(sys.argv) < 2:
        print("Error: Must specify a ROM file whose MUSIC WILL BE OVERWRITTEN")
        exit(1)

    with open("music.json", "r") as music_json_file:
        all: MusicJson = json.load(music_json_file)

    rom_file_to_write = open(sys.argv[1], "r+b")  # <- read, write, and it's binary

    for songset in all['songsets']:
        for song in songset['songs']:
            for i, voice in enumerate(song['voices']):
                if i >= 3:
                    break  # only randomize 5 voices for now
                voice_notes: list[Note] = []
                for section in voice['sections']:
                    if 'empty' not in section:
                        for note in section['notes']:
                            if 'note' in note:
                                voice_notes.append(note)

                            if 'subsection' in note:
                                for subsecnote in note['subsection']['notes']:
                                    voice_notes.append(subsecnote)
                for note_whose_address_to_use, note_whose_note_to_use in zip(voice_notes, reversed(voice_notes)):
                    rom_file_to_write.seek(int(note_whose_address_to_use['address']['rom'], 16))
                    rom_file_to_write.write(bytes([bytevalue(note_whose_note_to_use['note'])]))

    rom_file_to_write.close()
    print('Done. Your ROM was modified.')


if __name__ == "__main__":
    main()
