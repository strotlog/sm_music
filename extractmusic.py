# by strotlog 2024

import collections
from dataclasses import dataclass, field
import hashlib
import json
import os
import sys
from typing import Any, Sequence


def myhex(integer: int, padto: int = 0) -> str:
    """ like 'hex()' but no 0x """
    str = hex(integer)[2:]
    while len(str) < padto:
        str = "0" + str
    return str


def rom_offset_from_snes_addr_string(snes_addr_string: str) -> int:
    if snes_addr_string[0] == "$":
        snes_addr_string = snes_addr_string[1:]
    (bank, highwithin) = snes_addr_string.split(":")
    bank = int(bank, 16)
    highwithin = int(highwithin, 16)
    return (bank - 0x80) * 0x8000 + (highwithin - 0x8000)


def snes_addr_string_from_rom_offset(rom_offset: int) -> str:
    bank = rom_offset // 0x8000
    offset_in_bank = rom_offset % 0x8000
    bank += 0x80
    offset_in_bank += 0x8000
    return "$" + hex(bank)[2:] + ":" + hex(offset_in_bank)[2:]


def rom_read(rom: bytes, addr: str, length: int) -> bytes:
    start = rom_offset_from_snes_addr_string(addr)
    return rom[start:(start+length)]


def uint16at(bytearr: Sequence[int], offset: int) -> int:
    """ little endian """
    return bytearr[offset] + bytearr[offset+1]*256


def spc_data_block(rom: bytes, header_fileaddr: int) -> tuple[int, bytes]:
    length = uint16at(rom, header_fileaddr)
    spc_dest = uint16at(rom, header_fileaddr+2)
    return (spc_dest, rom[(header_fileaddr+4): (header_fileaddr+4+length)])


def indentme(indent: int, string: str) -> str:
    # 2 spaces per level
    return (' ' * 2 * indent) + string


standard_song_sets = {
        0x00: "Default",
        0x03: "Title",
        0x06: "Zebes Asleep",
        0x09: "Crateria Indoor",
        0x0C: "Crateria Outdoor with Power Bombs",
        0x0F: "Green Brinstar",
        0x12: "Red Brinstar",
        0x15: "Upper Norfair",
        0x18: "Lower Norfair",
        0x1B: "Maridia",
        0x1E: "Tourian",
        0x21: "Mother Brain",
        0x24: "Ridley etc",
        0x27: "Kraid etc",
        0x2A: "Botwoon/Spore",
        0x2D: "Ceres",
        0x30: "Wrecked Ship",
        0x33: "Zebes Exploding",
        0x36: "Intro",
        0x39: "Death Cry",
        0x3C: "Credits",
        0x3F: "VFX intro 1",
        0x42: "VFX intro 2",
        0x45: "Tourian version of Enemy Incoming and Kraid",
        0x48: "Tourian version of Crateria Outdoor with Power Bombs",
}

# commands with no special processing for now
g_simple_command_lengths = {
                     0xE0: 2,
                     0xE1: 2,
                     0xE2: 3,
                     0xE3: 4,
                     0xE5: 2,
                     0xE6: 3,
                     0xE7: 2,
                     0xE8: 3,
                     0xE9: 2,
                     0xEA: 2,
                     0xEB: 3,
                     0xED: 2,
                     0xEE: 3,
                     0xF0: 2,
                     0xF1: 4,
                     0xF2: 4,
                     0xF4: 2,
                     0xF5: 4,
                     0xF7: 4,
                     0xF8: 4,
                     0xF9: 4,
                     0xFA: 2,
                     0xFB: 2,  # FB = "skip next byte (unused)"
                     0xFC: 1,  # hmm. "skip all new notes (unused)"
                     0xFD: 1,  # hmm.   "stop sound effects and disable music note processing (unused)"
                     0xFE: 1,  # hmm. "resume sound effects and  enable music note processing (unused)"
                     # not really going to worry much about what happens with these last 4.
                     # could break if they do really occur
}

g_simple_end_commands = set({
    # interestingly, all of these commands are just 1 byte, and undo something set up by a command
    # whose byte is one less than these end (aka stop) bytes.
    # for example, command 0xE4 "end static vibrato", affects only command 0xE3, "static vibrato"
    0xE4,  # end static vibrato
    0xEC,  # end tremolo
    0xF6,  # end static echo
})


@dataclass
class SpcState:
    volume: int = 0
    ring_length: int = 0
    note_length_tics: int = 1
    tic_length_seconds: float = 0.1
    simple_properties: dict[str | int, int | Sequence[int]] = field(default_factory=dict)


def instrument(instrumentId: int) -> str:
    if instrumentId < 0x18:
        return "global" + hex(instrumentId)
    else:
        return "custom" + hex(instrumentId)


def dump_note(spc_ram: bytes, addr: int, state: SpcState) -> dict[str, Any]:
    """```
    {
        note: C7,
        duration: quarter,
        properties: {
            most recent relevant commands
        },
        addresses: {...}
    }
    ```"""
    overall = spc_ram[addr] - 0x80
    possible = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
    note = possible[overall % 12]
    octave = (overall // 12) + 1
    ret: dict[str, Any] = collections.OrderedDict()
    ret["note"] = note + str(octave)
    ret["duration_sec_appx"] = round(state.note_length_tics * state.tic_length_seconds, 1)
    ret["properties"] = collections.OrderedDict()
    instrument_id = state.simple_properties['e0']
    assert isinstance(instrument_id, int)
    ret["properties"]["instrumentInfov1"] = instrument(instrument_id)
    ret["properties"]["volume"] = state.volume
    ret["properties"]["note_length_tics"] = state.note_length_tics
    ret["properties"]["tic_length_seconds"] = state.tic_length_seconds
    for key, value in state.simple_properties.items():
        ret["properties"][key] = value
    return ret


def dump_percussion_note(spc_ram: bytes, addr: int, state: SpcState) -> dict[str, Any]:
    ret: dict[str, Any] = {}
    ret["percussion"] = True
    ret["duration_sec_appx"] = round(state.note_length_tics * state.tic_length_seconds, 1)
    if 0xFA not in state.simple_properties:
        raise Exception("Percussion note played without having set percussion instruments base index(command 0xFA)!")
    # e.g. command 0xCA is basically "play first percussion instrument",
    # and first percussion instrument is the instrument at the percussion instruments base index

    #      command 0xCB is          "play second percussion instrument",
    # i.e. play instrument = (percussion instruments base index) + 1
    percussion_index = state.simple_properties[0xFA]
    assert isinstance(percussion_index, int)
    ret["instrumentinfoV1"] = instrument((spc_ram[addr] - 0xCA) + percussion_index)
    ret["properties"] = collections.OrderedDict()
    ret["properties"]["volume"] = state.volume
    ret["properties"]["note_length_tics"] = state.note_length_tics
    ret["properties"]["tic_length_seconds"] = state.tic_length_seconds
    for key, value in state.simple_properties.items():
        ret["properties"][key] = value
    return ret


def dump_tie(spc_ram: bytes, addr: int, state: SpcState) -> dict[str, Any]:
    ret: dict[str, Any] = {}
    ret["tie"] = True
    ret["duration_sec_appx"] = round(state.note_length_tics * state.tic_length_seconds, 1)
    ret["properties"] = collections.OrderedDict()
    ret["properties"]["volume"] = state.volume
    ret["properties"]["note_length_tics"] = state.note_length_tics
    ret["properties"]["tic_length_seconds"] = state.tic_length_seconds
    return ret


def dump_rest(spc_ram: bytes, addr: int, state: SpcState) -> dict[str, Any]:
    ret: dict[str, Any] = {}
    ret["tie"] = True
    ret["duration_sec_appx"] = round(state.note_length_tics * state.tic_length_seconds, 1)
    ret["properties"] = collections.OrderedDict()
    ret["properties"]["note_length_tics"] = state.note_length_tics
    ret["properties"]["tic_length_seconds"] = state.tic_length_seconds
    return ret


def address_tuple(
    addr: int, spc_start_addr: int, rom_equiv_of_spc_start_addr: int, spc_engine_begin_romaddr: int
) -> dict[str, str]:
    # TODO: comment how this math works
    if addr >= spc_start_addr:
        romaddr = (addr - spc_start_addr) + rom_equiv_of_spc_start_addr
    else:
        romaddr = (addr - 0x1500) + spc_engine_begin_romaddr
    return collections.OrderedDict({
        "spcRam": hex(addr),
        "snes": snes_addr_string_from_rom_offset(romaddr),
        "rom": hex(romaddr)
    })


def stateful_process_track_command(
    spc_ram: bytes, addr: int, state: SpcState | None
) -> tuple[dict[str, Any] | None, int, SpcState]:
    """ -> optional note json, length of command, opaque state object """
    if spc_ram[addr] == 0xEF:
        raise Exception("implementation error: caller must process repeated subsections")  # but not any other commands
    if state is None:
        state = SpcState()
    command_length = 1
    note = None
    if spc_ram[addr] >= 1 and spc_ram[addr] < 0x80:
        # set note length, also read next byte to know if it's part of this command.
        # if it is, it sets volume and ring length, too
        state.note_length_tics = spc_ram[addr]
        if spc_ram[addr+1] < 0x80:
            # maybe could extract this from global spc ram rather than hard coding?
            ring_length_table = [0x32, 0x65, 0x7f, 0x98, 0xb2, 0xcb, 0xe5, 0xfc]
            volume_table = [
                0x19, 0x32, 0x4c, 0x65, 0x72, 0x7f, 0x9c, 0x98, 0xa5, 0xb2, 0xbf, 0xcb, 0xd8, 0xe5, 0xf2, 0xfc
            ]
            state.ring_length = ring_length_table[(spc_ram[addr+1] & 0x70) >> 4]
            state.volume = volume_table[spc_ram[addr+1] & 0x0f]
            command_length = 2
    # TODO: can we detect playing of samples?
    # or more importantly, any instruments that get played as notes when actually other pitches mean other instruments.
    # does that happen in sm? thunder?
    elif spc_ram[addr] >= 0x80 and spc_ram[addr] < 0xC8:  # play a note!
        note = dump_note(spc_ram, addr, state)
    elif spc_ram[addr] >= 0xCA and spc_ram[addr] < 0xE0:  # percussion note
        note = dump_percussion_note(spc_ram, addr, state)
    elif spc_ram[addr] == 0xC8:  # tie
        note = dump_tie(spc_ram, addr, state)
    elif spc_ram[addr] == 0xC9:  # rest
        note = dump_rest(spc_ram, addr, state)
    elif spc_ram[addr] == 0xEF:  # play subsection
        command_length = 4
    elif spc_ram[addr] == 0xFF:
        raise Exception("Unknown voice command 0xFF")
    elif spc_ram[addr] in g_simple_command_lengths:
        command_length = g_simple_command_lengths[spc_ram[addr]]
    elif spc_ram[addr] in g_simple_end_commands:
        command_length = 1
    elif spc_ram[addr] == 0xF3:  # end slide
        command_length = 1
    else:
        raise Exception(f"Code error: byte value {hex(spc_ram[addr])} is not handled")

    # track the state
    if spc_ram[addr] in g_simple_command_lengths:
        # if parameter to the command is just 1 byte long, save it as a single byte (non-array)
        # otherwise, save the params as an array of 0, or 2, or 3, ... etc length of bytes
        if command_length == 2:
            state.simple_properties[hex(spc_ram[addr])[2:]] = spc_ram[addr+1]
        else:
            state.simple_properties[hex(spc_ram[addr])[2:]] = [int(b) for b in spc_ram[(addr+1):(addr+command_length)]]
    elif spc_ram[addr] in g_simple_end_commands:
        # e.g. command 0xE4 (end vibrato) removes the vibrato property from 0xE4-1 = command 0xE3 (static vibrato)
        if spc_ram[addr]-1 in state.simple_properties:
            del (state.simple_properties[spc_ram[addr]-1])
        else:
            # print(f"Debug: (warning? but it happens) Command {spc_ram[addr]}"
            #       f"attempted to end command {spc_ram[addr]-1}, but the latter wasn't in the current state")
            pass
    elif spc_ram[addr] == 0xF3:  # end slide (command 0xF1 or 0xF2)
        # (probably doesn't affect "pitch slide" aka command 0xF9, though)
        if 0xF1 in state.simple_properties:
            del (state.simple_properties[0xF1])
        if 0xF2 in state.simple_properties:
            del (state.simple_properties[0xF2])

    return (note, command_length, state)


def main() -> None:
    if len(sys.argv) < 2:
        print("Error: Must specify a ROM file")
        exit(1)

    file = open(sys.argv[1], "rb")
    rombytes = file.read()
    filenameonly = os.path.basename(sys.argv[1])
    filesha1 = hashlib.sha1(rombytes).hexdigest()

    # verify that the music handling function works the way we think it does, by bailing out if it has been modified
    firstsection = rom_read(rombytes, "$80:8F0C", 24)
    # firstsection to midsection has a 3 byte gap, which is where the MSU patch would overwrite a vanilla
    # STA with a JSR to the MSU routine. allow this.
    midsection = rom_read(rombytes, "$80:8F2A", 73)
    # next gap is basically just the pointer to the music table embedded in the function, which we allow
    # to be repointed
    finalsection = rom_read(rombytes, "$80:8F7C", 39)  # rest of function
    sha1 = hashlib.sha1(firstsection + midsection + finalsection).hexdigest()
    if sha1 != "a5b4992b133ff9847b1219b54b6f370249b62f78":
        print("Error: Function $80:8F0C 'Handle music queue' is NOT vanilla")
        exit(1)

    table_addr_bytes = rom_read(rombytes, "$80:8F73", 3)
    table_addr = myhex(table_addr_bytes[2], 2) + ":" + myhex(table_addr_bytes[1], 2) + myhex(table_addr_bytes[0], 2)
    # print(f"Debug: Detected music pointer table at ${table_addr}")
    current_table_rom_addr = rom_offset_from_snes_addr_string(table_addr)

    # 3 address spaces:
    # SPC RAM: 0x5957
    # SNES A-bus $CF:be0d
    # rom file (e.g. 0x27be0d)_

    # type checker was not convinced that these were initialized before referenced
    rom_equiv_of_spc_start_addr = 0xdeadbeef
    spc_engine_begin_romaddr = 0xc0ffee

    # begin json and output it kinda manually while we process
    print("{")
    print(f'"romname": "{filenameonly}",')
    print(f'"romsha1hash": "{filesha1}",')
    print('"songsets": [')
    indent = 1

    is_valid_music = True
    while is_valid_music:  # loop over song sets
        # develop a hierarchical structure for the data before we can start processing actual music commands
        # order is very important as a lot of data is stored contiguously in ROM
        # song_set : OrderedDict:
        #   key : song SPC address   ==> value : section of song
        #   section of song : OrderedDict
        #     key : section SPC address   ==> value : voice of section
        #     voice of section : OrderedDict
        #       key : voice SPC address   ==> value : final output data TODO tbd structure
        # songset_song_section_voice[song SPC addr][section SPC addr][voice SPC addr]

        # set of voice end boundaries (== set of voice start pointers)
        voice_end_boundaries: set[int] = set()

        song_set_pointer_bytes = rombytes[current_table_rom_addr:(current_table_rom_addr+3)]
        if song_set_pointer_bytes[2] < 0x80 or song_set_pointer_bytes[1] < 0x80:
            is_valid_music = False
            break
        current_block_fileaddr = rom_offset_from_snes_addr_string(myhex(song_set_pointer_bytes[2], 2) + ":" +
                                                                  myhex(song_set_pointer_bytes[1], 2) +
                                                                  myhex(song_set_pointer_bytes[0], 2))

        spc_global_ram = b""
        spc_initial_song_pointers: Sequence[int] = []
        try:
            # skip the first 4 sections because we don't care about the first blocks
            # (they are sound data: sample table, sample data, instrument table, note length table)

            # TODO inspect the data following the main spc engine (and i mean even following the G4 hallway track).
            # it seems to include the title screen melody, yet the "Title" song set data includes this too,
            # in i'm guessing both of its 2 different songs already. possibly duplicitive, wonder if it's used,
            # wonder if a romhack could call on data structured in this way while also making it unique
            # rather than duplicative
            for i in range(4):
                (dest, block) = spc_data_block(rombytes, current_block_fileaddr)
                if dest == 0x1500:
                    # this 'song set pointer' actually includes the SPC engine. requires special
                    # processing to extract the global tracks
                    spc_global_ram = bytes(0x1500) + block
                    spc_engine_begin_romaddr = current_block_fileaddr+4
                if dest == 0x5820:
                    # this 'song set pointer' actually includes the main song pointer list, including
                    # the only time we see the global songs' pointers into spc_global_ram
                    rom_equiv_of_spc_start_addr = current_block_fileaddr+4
                    spc_initial_song_pointers = block
                if len(spc_global_ram) > 0 and len(spc_initial_song_pointers) > 0:
                    # finished data gathering for special case
                    break
                current_block_fileaddr += 4 + len(block)
            # read 5th block (typical case)
            (spc_start_addr, block) = spc_data_block(rombytes, current_block_fileaddr)
        except BaseException:
            raise
            print("Debug: Found invaild song set via some exception. Done.")
            is_valid_music = False
            break

        if len(spc_global_ram) > 0 and len(spc_initial_song_pointers) > 0:
            # special construction of ram. there should be global songs and song set specific
            # songs (even if duplicative) in this data
            spc_start_addr = 0x5820
            if spc_start_addr < len(spc_global_ram):
                print("Error: Not implemented: SPC engine overlaps beginning of changeable songs area")
                # would need new math
                is_valid_music = False
                break
            spc_ram = spc_global_ram + bytes(spc_start_addr - len(spc_global_ram)) + block
        else:
            # normal case (all song sets except for song set 0)
            rom_equiv_of_spc_start_addr = current_block_fileaddr + 4
            current_block_fileaddr += (4 + len(block))
            if rombytes[current_block_fileaddr:(current_block_fileaddr+4)] != b"\x00\x00\x00\x15":
                # print(f"Debug: SPC block at reversed 24 bit SNES pointer {song_set_pointer_bytes} did not match " +
                #       f"expected terminator 0000, 1500 at detected end (rom addr {hex(current_block_fileaddr)})")
                is_valid_music = False
                break
            # simulate SPC ram so we can access it without using offsets
            # (still, ideally access only the area which is within this song set)
            spc_ram = bytes(spc_start_addr) + block

        is_a_song_pointer = True
        songset_song_section_voice: dict[int, Any] = collections.OrderedDict()
        spc_address_of_next_pointer_to_a_song = spc_start_addr
        while is_a_song_pointer:
            if spc_address_of_next_pointer_to_a_song in songset_song_section_voice:
                # this address doesn't have a song pointer, the only only way we know is that it's pointed
                # to by an already-seen song pointer
                is_a_song_pointer = False
                break
            songset_song_section_voice[uint16at(spc_ram, spc_address_of_next_pointer_to_a_song)] = \
                collections.OrderedDict()
            spc_address_of_next_pointer_to_a_song += 2

        for song_ptr, _ in songset_song_section_voice.items():  # loop over songs (in the song set)
            spc_address_of_next_pointer_to_a_sectioncommand = song_ptr
            while uint16at(spc_ram, spc_address_of_next_pointer_to_a_sectioncommand) != 0:
                section_pointer = uint16at(spc_ram, spc_address_of_next_pointer_to_a_sectioncommand)
                if section_pointer == 0x00ff:
                    spc_address_of_next_pointer_to_a_sectioncommand += 4  # skip processing loop point
                else:
                    songset_song_section_voice[song_ptr][section_pointer] = collections.OrderedDict()
                    spc_address_of_next_pointer_to_a_sectioncommand += 2

            for song_section, _ in songset_song_section_voice[song_ptr].items():
                # each song section has 1-8 voices, which will each in turn have a list of music commands
                spc_address_of_next_voice = song_section
                for i in range(8):
                    voice_start_ptr = uint16at(spc_ram, spc_address_of_next_voice)
                    if voice_start_ptr == 0:
                        songset_song_section_voice[song_ptr][song_section]["0000-v#" + str(i)] = None
                    else:
                        songset_song_section_voice[song_ptr][song_section][voice_start_ptr] = {"end_spc_ptr": None}
                        voice_end_boundaries.add(voice_start_ptr)
                    spc_address_of_next_voice += 2

        # TODO: update comment
        # now we have completed, for the song set: all song pointers (top level)
        #                                          all section pointers (mid level pointed to by song pointers)
        #                                          all voice pointers (bottom level pointed to by section pointers)
        # in a breadth-first way, we've also taken stock of where all the voices start. why?
        # these are the only ways we'll know where a voice command list ends:
        # 1) a 00 command is encountered,
        # 2) the command list runs right into a different command list, OR
        # 3) the command list runs into another song's beginning
        # (detection of all 3 is required!)

        # processing voices!
        for song_ptr, _ in songset_song_section_voice.items():
            for song_section, _ in songset_song_section_voice[song_ptr].items():
                for voice_start_ptr, _ in songset_song_section_voice[song_ptr][song_section].items():
                    if isinstance(voice_start_ptr, str) and voice_start_ptr[0:4] == "0000":
                        continue  # empty voice
                    assert isinstance(voice_start_ptr, int)
                    addr = voice_start_ptr
                    # find the end of this voice section by lightly parsing the voice section's commands
                    while (
                        spc_ram[addr] != 0 and
                        (addr == voice_start_ptr or addr not in voice_end_boundaries) and
                        addr not in songset_song_section_voice
                    ):
                        command_length = 1
                        if spc_ram[addr] >= 1 and spc_ram[addr] < 0x80:
                            # set note length, also read next byte to know if it's part of this command
                            if spc_ram[addr+1] < 0x80:
                                command_length = 2
                        elif spc_ram[addr] >= 0x80 and spc_ram[addr] < 0xC8:  # play a note
                            pass
                        elif spc_ram[addr] >= 0xCA and spc_ram[addr] < 0xE0:  # percussion note
                            pass
                        elif spc_ram[addr] == 0xC8:  # tie
                            pass
                        elif spc_ram[addr] == 0xC9:  # rest
                            pass
                        elif spc_ram[addr] == 0xEF:  # play subsection
                            command_length = 4
                        elif spc_ram[addr] == 0xFF:
                            raise Exception("Unknown voice command 0xFF")
                        elif spc_ram[addr] in g_simple_command_lengths:
                            command_length = g_simple_command_lengths[spc_ram[addr]]
                        elif spc_ram[addr] in g_simple_end_commands:
                            command_length = 1
                        elif spc_ram[addr] == 0xF3:
                            # end slide (probably doesn't affect "pitch slide" aka command 0xF9, though)
                            command_length = 1
                        else:
                            raise Exception(f"Code error: byte value {hex(spc_ram[addr])} is not handled")
                        addr += command_length
                    # record the spc address of end of this voice section
                    songset_song_section_voice[song_ptr][song_section][voice_start_ptr]["end_spc_ptr"] = addr

        # reorganize
        # FROM song -> section -> voice
        #  TO  song -> voice -> section
        reorganized: dict[int, list[dict[int | str, dict[str, Any]]]] = collections.OrderedDict()
        for song_ptr, _ in songset_song_section_voice.items():
            used_voices = [False, False, False, False, False, False, False, False]
            for song_section, _ in songset_song_section_voice[song_ptr].items():
                used_voices_this_section = [
                    str(vp)[0:4] != "0000" for vp in songset_song_section_voice[song_ptr][song_section].keys()
                ]
                used_voices = [value or used_voices_this_section[i] for (i, value) in enumerate(used_voices)]
            max_voices = 8
            for i, voice_is_used in reversed(list(enumerate(used_voices))):
                if not voice_is_used:
                    max_voices -= 1
                else:
                    # this is the rightmost voice that gets used in the song,
                    # preserve any unused voices to its left(unlikely, but possible)
                    break
            # song is an array of voices, each has/is 1 OrderedDict
            # representing the voice's sections by voice section pointer
            reorganized[song_ptr] = [collections.OrderedDict() for _ in range(max_voices)]
            for song_section, _ in songset_song_section_voice[song_ptr].items():
                for i, (voice_start_pointer, _) in enumerate(
                    songset_song_section_voice[song_ptr][song_section].items()
                ):
                    if i >= max_voices:  # guaranteed to be nulls anyway
                        break
                    # in "reorganized", this "voice_start_pointer"
                    # really means "voice_section_start_ptr". i.e., where the note etc. commands are
                    reorganized[song_ptr][i][voice_start_pointer] = (
                        songset_song_section_voice[song_ptr][song_section][voice_start_pointer]
                    )

            # print(json.dumps(reorganized))

        songset_id = current_table_rom_addr - rom_offset_from_snes_addr_string(table_addr)
        if songset_id != 0:
            print(indentme(indent, "},"))  # end previous song set w/ comma if this isn't the first one
        print(indentme(indent, "{"))  # for song set
        indent += 1
        print(indentme(indent, f'"id": "{myhex(songset_id, 2)}",'))  # 00, 03, 06, ..., 0C, ... etc.
        if songset_id in standard_song_sets:
            # TODO more heuristics to make sure it's the real song set?
            print(indentme(indent, f'"vanillaMatchingSongSetName": "{standard_song_sets[songset_id]}",'))
        print(indentme(indent, '"songs": ['))
        indent += 1

        for song_index, (song_ptr, _) in enumerate(reorganized.items()):
            if song_index != 0:
                print(indentme(indent, "},"))  # end previous song w/ comma if this isn't the first one
            print(indentme(indent, "{"))
            indent += 1
            song_id = song_index + 5 if song_ptr > 0x5820 else song_index
            print(indentme(indent, f'"id": "{myhex(song_id, 2)}",'))
            print(indentme(indent, '"voices": ['))
            indent += 1
            for (i, _) in enumerate(reorganized[song_ptr]):
                # init a new voice
                if i != 0:
                    print(indentme(indent, "},"))  # end previous voice w/ comma if this isn't the first one
                print(indentme(indent, "{"))
                indent += 1
                print(indentme(indent, f'"id": {i},'))
                print(indentme(indent, '"sections": ['))
                indent += 1

                state = None

                for section_index, (voice_section_start_ptr, _) in enumerate(reorganized[song_ptr][i].items()):
                    if section_index != 0:
                        print(indentme(indent, "},"))  # end previous section w/ comma if this isn't the first one
                    print(indentme(indent, "{"))
                    if isinstance(voice_section_start_ptr, str) and voice_section_start_ptr[0:4] == "0000":
                        indent += 1
                        print(indentme(indent, '"empty": true'))
                        indent -= 1
                        continue  # empty voice

                    # TODO: verify this:
                    # is every string in this container supposed to start with 0000?
                    assert isinstance(voice_section_start_ptr, int), f"{voice_section_start_ptr!r}"

                    indent += 1
                    print(indentme(
                        indent,
                        f'"sectionId": "song{myhex(songset_id, 2)}{myhex(song_id, 2)}voice{i}section{section_index}",'
                    ))
                    print(indentme(indent, '"notes": ['))
                    indent += 1

                    addr = voice_section_start_ptr
                    wehaveSuppressedFirstComma = False
                    while addr < reorganized[song_ptr][i][voice_section_start_ptr]["end_spc_ptr"]:
                        if spc_ram[addr] == 0xEF:
                            # special case: command is "play repeated subsection"
                            subsection_addr = spc_ram[addr+1] + 256*spc_ram[addr+2]
                            if wehaveSuppressedFirstComma:
                                print(',')
                            else:
                                wehaveSuppressedFirstComma = True
                            print(indentme(indent, '{ "subsection": { "notes": ['))
                            indent += 1
                            wehaveSuppressedFirstCommaForSubsection = False
                            while spc_ram[subsection_addr] != 0:  # subsections must be 0-terminated
                                (kindaJson, length, state) = stateful_process_track_command(
                                    spc_ram, subsection_addr, state
                                )
                                if kindaJson is not None and "note" in kindaJson:
                                    kindaJson["address"] = address_tuple(subsection_addr,
                                                                         spc_start_addr,
                                                                         rom_equiv_of_spc_start_addr,
                                                                         spc_engine_begin_romaddr)
                                    if wehaveSuppressedFirstCommaForSubsection:
                                        print(", ")
                                    else:
                                        wehaveSuppressedFirstCommaForSubsection = True
                                    print(indentme(indent, json.dumps(kindaJson)), end='')
                                    # no newline, wait and see if comma is needed
                                subsection_addr += length
                                # firstSubsectionNote = False
                            addr += 4
                            indent -= 1
                            print('')  # newline after last subsection note
                            print(indentme(indent, "]}}"), end='')
                            # end subsection, no newline, wait and see if comma is needed
                        else:
                            # general case
                            (kindaJson, length, state) = stateful_process_track_command(spc_ram, addr, state)
                            if kindaJson is not None and "note" in kindaJson:
                                kindaJson["address"] = address_tuple(addr,
                                                                     spc_start_addr,
                                                                     rom_equiv_of_spc_start_addr,
                                                                     spc_engine_begin_romaddr)
                                if wehaveSuppressedFirstComma:
                                    print(',')
                                else:
                                    wehaveSuppressedFirstComma = True
                                print(indentme(indent, json.dumps(kindaJson)), end='')
                                # no newline, wait and see if comma is needed
                            addr += length

                    print('')  # newline after last note
                    indent -= 1
                    print(indentme(indent, "]"))  # end of note array
                    indent -= 1

                print(indentme(indent, "}"))  # end of last section (in voice) (no comma)
                indent -= 1
                print(indentme(indent, "]"))  # end of section array
                indent -= 1

            print(indentme(indent, "}"))  # end of last voice (in song) (no comma)
            indent -= 1
            print(indentme(indent, "]"))  # end voice array
            indent -= 1

        print(indentme(indent, "}"))  # end of last song (in set) (no comma)
        indent -= 1
        print(indentme(indent, "]"))  # end song array
        indent -= 1
        current_table_rom_addr += 3  # move to next song set

    print(indentme(indent, "}"))  # end of last song set (no comma)
    print("]")  # end songsets
    print("}")  # end json


if __name__ == "__main__":
    main()
