"""Machine-code/data payloads for the Name Entry component.

The human-readable 65C816 equivalents live in the neighbouring .asm files.
Keeping the actual bytes here makes build_patch.py small and makes accidental
changes easy to audit in code review.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PatchEdit:
    offset: int
    expected: bytes
    payload: bytes
    description: str


def hx(value: str) -> bytes:
    return bytes.fromhex("".join(value.split()))


# C0:3583/C0:3595 replace the former Name Entry resource with Up/Down handlers.
# Selector states are $50/$60/$70/$80 for uppercase/lowercase/symbols/accents.
NAVIGATION_CODE = hx(
    """
    20 4A 32 AD 5A A1 38 E9 10 C9 41 B0 02 A9 80 4C A4 35
    20 4A 32 AD 5A A1 18 69 10 C9 81 90 02 A9 50 8D 5A A1
    22 3D 50 C7 20 AA 1B 60
    """
)

# SoM Plus-derived control bytes retained byte-for-byte.
LAYOUT_CONTROL = hx("02 06 1E 01 C0 04 06 1E 81 8A 00 02 0A")

# Complete private four-row Name Entry script at C7:4E00.
# It is the original three-row script with these changes:
#   $02C0 -> $0240, height 6 -> 8, plus draw command 08 AA 02.
FOUR_ROW_LAYOUT_SCRIPT = hx(
    """
    01 40 02 08 1E 01 C0 04 06 1E 81 8A 00 02 0A 00
    03 E8 02 04 10 03 08 2A 01 08 AA 01 08 2A 02 08 AA
    02 02 E4 00 0C 02 64 01 10 02 E4 01 08 01 02 00 02
    07 01 C0 04 06 1E 00 07 6C 00 04 1C 03 02 44 01 10
    02 64 01 08 02 44 02 14 02 64 02 0C 01 00 00 02 09
    41 08 01 02 07 41 28 01 02 07 41 08 02 02 07 41 28
    02 02 07 01 40 04 08 1E 00
    """
)

# Three neighbouring pointers; only the middle Name Entry pointer is redirected to C7:4E00.
LAYOUT_POINTER_TRIO = hx("EA 74 00 4E EA 74")

# Character validation/lookup code. Selected bytes are read from E4:4000.
CHARACTER_LOOKUP_CODE = hx("CC 00 BD 00 90 DA 38 E9 4E 20 4A AA E2 20 BF 00 40 E4")

STATIC_EDITS = (
    PatchEdit(0x00319C, hx("06"), hx("09"), "maximum name length = 9"),
    PatchEdit(0x00334D, hx("96 32"), hx("83 35"), "Name Edit Up handler -> C0:3583"),
    PatchEdit(0x003363, hx("96 32"), hx("95 35"), "Name Edit Down handler -> C0:3595"),
    PatchEdit(0x0033BE, hx("83 35 C0"), hx("00 40 E4"), "Name Entry resource pointer -> E4:4000"),
    PatchEdit(
        0x003583,
        hx("80 AD 9F A6 9F 9D AE 80 9B 80 A6 9F AE AE 9F AC 80 AF AD A3 A8 A1 80 AE A2 9F 80 9D A9 A8 AE AC A9 A6 80 AA 9B 9E BF 80 AA AC 9F AD"),
        NAVIGATION_CODE,
        "four-row naming navigation",
    ),
    PatchEdit(0x075019, hx("60"), hx("50"), "initial cursor vertical state = first row"),
    PatchEdit(0x07502A, hx("12"), hx("0C"), "naming grid/lookup parameter"),
    PatchEdit(
        0x0750A6,
        hx("D2 00 BD 00 90 DA 38 E9 58 20 4A AA E2 20 BF B2 74 C7"),
        CHARACTER_LOOKUP_CODE,
        "selected character lookup -> E4:4000",
    ),
    PatchEdit(
        0x07759D,
        hx("04 06 1E 81 C0 02 02 1E 81 90 00 02 07"),
        LAYOUT_CONTROL,
        "naming layout/control data",
    ),
    PatchEdit(
        0x074E00,
        bytes((0xFF,)) * len(FOUR_ROW_LAYOUT_SCRIPT),
        FOUR_ROW_LAYOUT_SCRIPT,
        "private four-row Name Entry layout script",
    ),
    PatchEdit(
        0x07781C,
        hx("AD 74 9B 75 EC 74"),
        LAYOUT_POINTER_TRIO,
        "Name Entry layout pointer -> C7:4E00",
    ),
)

assert len(NAVIGATION_CODE) == 0x2C
assert len(FOUR_ROW_LAYOUT_SCRIPT) == 110
