"""Shared stock-outline preparation for VWF components 05 and 06.

The stock outline routine at $C0:162C shifts each 8-pixel bitmap row left with
ROL at $C0:163D. Carry is left behind by the preceding row's LSR, so ROL can
inject that previous-row bit into the next row. VWF rendering can expose edge
pixels more often than the stock fixed-width font; both VWF components therefore
use ASL here so every row starts with a zero shift-in bit.

This one-byte patch was already runtime-validated through component 05. Keeping
it in one shared installer also makes component 06 standalone match the outline
preparation used by aggregate builds.
"""
from __future__ import annotations

OUTLINE_SHIFT_FILE = 0x00163D
STOCK_ROL = 0x2A
VWF_ASL = 0x0A


def validate_stock(rom: bytes | bytearray) -> None:
    if rom[OUTLINE_SHIFT_FILE] != STOCK_ROL:
        raise SystemExit("Unexpected stock outline ROL at ROM $00163D")


def install(rom: bytearray) -> None:
    rom[OUTLINE_SHIFT_FILE] = VWF_ASL
