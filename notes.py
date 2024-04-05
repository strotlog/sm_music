NOTE_NAMES = ("C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B")


def bytevalue(notename: str) -> int:
    octave = int(notename[-1])
    keyname = notename[:-1]
    keynum = NOTE_NAMES.index(keyname)
    return 0x80 + (octave-1)*12 + keynum
