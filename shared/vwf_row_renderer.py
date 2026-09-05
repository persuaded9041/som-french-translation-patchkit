"""Shared stock-font VWF row renderer for components 05 and 06.

Input contract (65816, 8-bit accumulator mode):

- X: 12-byte stock-font row offset for the current glyph;
- Y: destination row offset inside the tile-major $7E:9000 bitmap;
- $7E:9382: cumulative pixel cursor.

The helper reads the stock row from $D2:DC00,X, applies the shared runtime
framing policy, then delegates shift/merge/spill to the shared compositor.
It returns A containing the current-cell half to store at $9000,Y. X and Y are
preserved and the hidden B byte of the accumulator is not modified.

Both components install these exact bytes independently so standalone patches
remain self-contained while aggregate builds see only a byte-identical overlap.
"""
from __future__ import annotations

from .asm65816 import lo24
from .vwf_framing import SHARED_FRAMING_CALL
from .vwf_compositor import COMPOSITOR_CALL

ROW_RENDERER_CPU = 0xC74560
ROW_RENDERER_FILE = 0x074560
ROW_RENDERER_RESERVED_SIZE = 0x20
STOCK_FONT_CPU = 0xD2DC00

ROW_RENDERER = bytes([
    0xBF, *lo24(STOCK_FONT_CPU),       # LDA.l $D2DC00,X
    *SHARED_FRAMING_CALL,              # JSL shared framing selector
    *COMPOSITOR_CALL,                  # JSL shared shift/merge/spill compositor
    0x6B,                              # RTL
])
ROW_RENDERER_CALL = bytes([0x22, *lo24(ROW_RENDERER_CPU)])


def validate_stock(base: bytes) -> None:
    region = base[ROW_RENDERER_FILE:ROW_RENDERER_FILE + ROW_RENDERER_RESERVED_SIZE]
    if len(region) != ROW_RENDERER_RESERVED_SIZE or any(value != 0xFF for value in region):
        raise SystemExit("Expected stock-$FF space for shared VWF stock-row renderer")
    if len(ROW_RENDERER) > ROW_RENDERER_RESERVED_SIZE:
        raise SystemExit(
            f"Shared VWF stock-row renderer is too large: {len(ROW_RENDERER):#x} > "
            f"{ROW_RENDERER_RESERVED_SIZE:#x}"
        )


def install(rom: bytearray) -> None:
    rom[ROW_RENDERER_FILE:ROW_RENDERER_FILE + len(ROW_RENDERER)] = ROW_RENDERER
