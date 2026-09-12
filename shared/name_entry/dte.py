"""Name-buffer-specific direct-glyph/DTE boundary for `french_name_entry_extended`.

Name Entry stores the selected bytes directly in the player-name buffer. When
an event executes PLAYER_NAME, the stock parser copies twelve bytes to the
private $7E:A22F scratch source and parses that temporary stream with the same
DTE decision used for ordinary event text.

The extended Name Entry row can therefore use $D3=♪, $E6=° and $E7=; without
changing ordinary event decoding: only bytes read from the temporary player-
name source use the dialogue-style $E8 direct/DTE boundary. All other parser
sources use a configurable legacy boundary ($E1 standalone, raised by the root
combiner when another legacy charset component such as `french_intro` requires it).
"""
from __future__ import annotations

from shared.core.asm import MiniAssembler, lo24
from shared.charset import BASIC_DTE_THRESHOLD, DIALOGUE_DTE_THRESHOLD

NAME_DTE_ROUTE_FILE = 0x0016F5
NAME_DTE_ROUTE_CPU = 0xC016F5
NAME_DTE_ROUTE_SIGNATURE = bytes.fromhex("C9 D3 B0 14")
NAME_DTE_HELPER_FILE = 0x0745F0
NAME_DTE_HELPER_CPU = 0xC745F0
NAME_DTE_RESERVED_SIZE = 0x40
NAME_DTE_BASE_CONFIG_FILE = 0x074C86
NAME_DTE_BASE_CONFIG_CPU = 0xC74C86

# The PLAYER_NAME handler at C0:182B copies 12 bytes to $7E:A22F and switches
# the parser source there. At the DTE hook Y has already advanced past the byte
# just read, so actual name bytes correspond to Y=$A230..$A23B inclusive.
PLAYER_NAME_SOURCE_BANK = 0x7E
PLAYER_NAME_Y_AFTER_FIRST = 0xA230
PLAYER_NAME_Y_AFTER_LAST = 0xA23B


def _assemble_router() -> bytes:
    a = MiniAssembler(NAME_DTE_HELPER_CPU)

    def jml(cpu: int) -> None:
        a.emit(0x5C, *lo24(cpu))

    # Preserve the source byte while checking whether the parser is consuming
    # the PLAYER_NAME scratch stream in bank $7E.
    a.emit(0x48)                              # PHA source byte (M=8)
    a.emit(0x8B)                              # PHB
    a.emit(0x68)                              # PLA -> current DB
    # The relocated Name Entry character/help resource lives alone in bank
    # $E4. Its grid bytes must use the same extended $E8 boundary so $E6/$E7
    # render as ° / ; instead of stock DTE pairs.
    a.emit(0xC9, 0xE4)
    a.rel8(0xF0, "extended_saved")
    a.emit(0xC9, PLAYER_NAME_SOURCE_BANK)
    a.rel8(0xD0, "base_saved")

    a.emit(0xC2, 0x20)                        # REP #$20
    a.emit(0x98)                              # TYA (already advanced)
    a.emit(0xC9, PLAYER_NAME_Y_AFTER_FIRST & 0xFF, PLAYER_NAME_Y_AFTER_FIRST >> 8)
    a.rel8(0x90, "base16_saved")              # below name scratch
    a.emit(0xC9, (PLAYER_NAME_Y_AFTER_LAST + 1) & 0xFF, (PLAYER_NAME_Y_AFTER_LAST + 1) >> 8)
    a.rel8(0xB0, "base16_saved")              # at/after terminator

    a.emit(0xE2, 0x20)                        # SEP #$20
    a.label("extended_saved")
    a.emit(0x68)                              # PLA source byte
    a.emit(0xC9, DIALOGUE_DTE_THRESHOLD)      # $E8: ♪/°/; stay direct
    a.rel8(0xB0, "upper_dte")
    jml(0xC016F9)                             # stock direct/control tests

    a.label("base16_saved")
    a.emit(0xE2, 0x20)
    a.label("base_saved")
    a.emit(0x68)                              # PLA source byte
    a.emit(0xCF, *lo24(NAME_DTE_BASE_CONFIG_CPU))  # CMP long configured boundary
    a.rel8(0xB0, "upper_dte")
    jml(0xC016F9)

    a.label("upper_dte")
    jml(0xC0170D)                             # stock upper-DTE expansion path
    return a.resolve()


NAME_DTE_HELPER = _assemble_router()
NAME_DTE_HOOK = bytes([0x5C, *lo24(NAME_DTE_HELPER_CPU)])


def validate_stock(base: bytes) -> None:
    if base[NAME_DTE_ROUTE_FILE:NAME_DTE_ROUTE_FILE + len(NAME_DTE_ROUTE_SIGNATURE)] != NAME_DTE_ROUTE_SIGNATURE:
        raise SystemExit("Unexpected clean-US direct/DTE decision signature for Name Entry router")
    region = base[NAME_DTE_HELPER_FILE:NAME_DTE_HELPER_FILE + NAME_DTE_RESERVED_SIZE]
    if len(region) != NAME_DTE_RESERVED_SIZE or any(value != 0xFF for value in region):
        raise SystemExit("Expected stock-$FF space for Name Entry DTE router")
    if base[NAME_DTE_BASE_CONFIG_FILE] != 0xFF:
        raise SystemExit("Expected stock-$FF Name Entry DTE base config byte")
    if len(NAME_DTE_HELPER) > NAME_DTE_RESERVED_SIZE:
        raise SystemExit(
            f"Name Entry DTE router is too large: {len(NAME_DTE_HELPER):#x} > "
            f"{NAME_DTE_RESERVED_SIZE:#x}"
        )


def install(rom: bytearray, *, base_threshold: int = BASIC_DTE_THRESHOLD) -> None:
    rom[NAME_DTE_ROUTE_FILE:NAME_DTE_ROUTE_FILE + len(NAME_DTE_HOOK)] = NAME_DTE_HOOK
    rom[NAME_DTE_HELPER_FILE:NAME_DTE_HELPER_FILE + len(NAME_DTE_HELPER)] = NAME_DTE_HELPER
    rom[NAME_DTE_BASE_CONFIG_FILE] = base_threshold
