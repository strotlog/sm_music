from typing import Sequence, TypedDict


class Note(TypedDict):
    note: str
    address: dict[str, str]


class Subsection(TypedDict):
    notes: Sequence[Note]


class SsContainer(TypedDict):
    subsection: Subsection


class Section(TypedDict):
    sectionId: str
    notes: Sequence[Note | SsContainer]


class Voice(TypedDict):
    id: int
    sections: Sequence[Section]


class Song(TypedDict):
    id: str
    voices: Sequence[Voice]


class SongSet(TypedDict):
    id: str
    vanillaMatchingSongSetName: str
    songs: Sequence[Song]


class MusicJson(TypedDict):
    romname: str
    romsha1hash: str
    songsets: Sequence[SongSet]
