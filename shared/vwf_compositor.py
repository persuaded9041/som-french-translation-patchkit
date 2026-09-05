"""Shared 8x12 VWF row compositor for components 05 and 06.

Input contract (65816, 8-bit accumulator mode):

- A: one already-selected / already-framed 8-pixel glyph row;
- Y: destination row offset inside the tile-major $7E:9000 bitmap;
- $7E:9382: cumulative pixel cursor.

The helper returns A containing the current-cell half ORed with the existing
$9000,Y byte. It also merges any right-side spill into $900C,Y. X and Y are
preserved, and the hidden B byte of the accumulator is never touched.

Both components install these exact bytes independently so standalone patches
remain self-contained while aggregate builds see only a byte-identical overlap.
"""
from __future__ import annotations

from .asm65816 import MiniAssembler, lo16, lo24

COMPOSITOR_CPU = 0xC74C90
COMPOSITOR_FILE = 0x074C90
COMPOSITOR_RESERVED_SIZE = 0x50

PIXEL_CURSOR = 0x9382
BIT_SHIFT = 0x9383
SHIFT_COUNT = 0x9384
SOURCE_ROW = 0x9388
CURRENT_ROW = 0x9389


def _assemble() -> bytes:
    a = MiniAssembler(COMPOSITOR_CPU)

    a.emit(0x8D, *lo16(SOURCE_ROW))             # STA SOURCE_ROW
    a.emit(0xAD, *lo16(PIXEL_CURSOR))           # LDA pixel cursor
    a.emit(0x29, 0x07)                          # cursor & 7
    a.emit(0x8D, *lo16(BIT_SHIFT))              # STA BIT_SHIFT
    a.rel8(0xF0, "aligned")                     # BEQ aligned

    # current = source >> shift, merged with any previous spill.
    a.emit(0x8D, *lo16(SHIFT_COUNT))            # SHIFT_COUNT = shift
    a.emit(0xAD, *lo16(SOURCE_ROW))
    a.label("right_loop")
    a.emit(0x4A)                                 # LSR A
    a.emit(0xCE, *lo16(SHIFT_COUNT))             # DEC SHIFT_COUNT
    a.rel8(0xD0, "right_loop")
    a.emit(0x19, *lo16(0x9000))                  # ORA $9000,Y
    a.emit(0x8D, *lo16(CURRENT_ROW))             # save current half

    # spill = source << (8-shift), merged into next 12-byte tile cell.
    a.emit(0xA9, 0x08)
    a.emit(0x38)                                 # SEC
    a.emit(0xED, *lo16(BIT_SHIFT))               # SBC BIT_SHIFT
    a.emit(0x8D, *lo16(SHIFT_COUNT))
    a.emit(0xAD, *lo16(SOURCE_ROW))
    a.label("left_loop")
    a.emit(0x0A)                                 # ASL A
    a.emit(0xCE, *lo16(SHIFT_COUNT))
    a.rel8(0xD0, "left_loop")
    a.emit(0x19, *lo16(0x900C))                  # ORA $900C,Y
    a.emit(0x99, *lo16(0x900C))                  # STA $900C,Y
    a.emit(0xAD, *lo16(CURRENT_ROW))             # return current half
    a.emit(0x6B)                                 # RTL

    a.label("aligned")
    a.emit(0xAD, *lo16(SOURCE_ROW))
    a.emit(0x6B)                                 # RTL
    return a.resolve()


COMPOSITOR = _assemble()
COMPOSITOR_CALL = bytes([0x22, *lo24(COMPOSITOR_CPU)])


def validate_stock(base: bytes) -> None:
    region = base[COMPOSITOR_FILE:COMPOSITOR_FILE + COMPOSITOR_RESERVED_SIZE]
    if len(region) != COMPOSITOR_RESERVED_SIZE or any(value != 0xFF for value in region):
        raise SystemExit("Expected stock-$FF space for shared VWF row compositor")
    if len(COMPOSITOR) > COMPOSITOR_RESERVED_SIZE:
        raise SystemExit(
            f"Shared VWF row compositor is too large: {len(COMPOSITOR):#x} > "
            f"{COMPOSITOR_RESERVED_SIZE:#x}"
        )


def install(rom: bytearray) -> None:
    rom[COMPOSITOR_FILE:COMPOSITOR_FILE + len(COMPOSITOR)] = COMPOSITOR
