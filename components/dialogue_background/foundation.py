"""Stock dialogue-background visual foundation used by dialogue_background.

This module contains only the already runtime-proven foundation promoted from
Stages 1-5 of the standalone transparency experiments:

* replace every stock dither fill source with transparent 2bpp pixels;
* configure fixed-color ADD+HALF for BG1/BG2/backdrop, excluding BG3/OBJ;
* enable color Window 1; and
* keep the validated X calibration used by the dynamic HDMA window.

The final component lifecycle/geometry logic lives in build_patch.py.
"""
from __future__ import annotations

# HiROM CPU $D2:D480 -> unheadered file $12:D480.
PATTERN_TABLE_FILE = 0x12D480
PATTERN_STYLE_SIZE = 0x80
PATTERN_STYLE_COUNT = 8
PATTERN_TABLE_SIZE = PATTERN_STYLE_SIZE * PATTERN_STYLE_COUNT
PATTERN_TABLE_END = PATTERN_TABLE_FILE + PATTERN_TABLE_SIZE

# Stock map display-settings PPU writer in CPU bank C2.
CGWSEL_IMMEDIATE_FILE = 0x02AAD8
CGADSUB_LOAD_FILE = 0x02AADC
COLDATA_WINDOW_INIT_FILE = 0x02AAE1
WINDOW_LOGIC_RESET_FILE = 0x02AAC1

STOCK_CGWSEL_IMMEDIATE = bytes.fromhex("02")
STOCK_CGADSUB_LOAD = bytes.fromhex("A5 23")
STOCK_COLDATA_WINDOW_INIT = bytes.fromhex(
    "9C 32 21 A9 00 8D 26 21 8D 28 21 A9 FF"
)
STOCK_WINDOW_LOGIC_RESET = bytes.fromhex("9C 2A 21 9C 2B 21")

# Fixed-color source, ADD+HALF on BG1/BG2/backdrop, BG3/OBJ excluded.
STAGE2_CGWSEL_IMMEDIATE = bytes.fromhex("00")
STAGE2_CGADSUB_LOAD = bytes.fromhex("A9 63")
STAGE2_COLDATA_WINDOW_INIT = bytes.fromhex(
    "A9 E0 8D 32 21 9C 26 21 9C 28 21 A9 FF"
)

# Color Window 1 only; $2130=$10 confines the addend to that color window.
STAGE3_COLOR_WINDOW_ENABLE = bytes.fromhex("A9 20 8D 25 21 EA")
STAGE3_CGWSEL_IMMEDIATE = bytes.fromhex("10")
STAGE3_COLDATA_WINDOW_INIT = bytes.fromhex(
    "A9 E0 8D 32 21 A9 10 8D 26 21 A9 EF 8D 27 21 9C 28 21 EA"
)

# Runtime-validated fully-open horizontal calibration: X=15..240.
STAGE4_COLDATA_WINDOW_INIT = bytes.fromhex(
    "A9 E0 8D 32 21 A9 0F 8D 26 21 A9 F0 8D 27 21 9C 28 21 EA"
)
STAGE4_INITIAL_CGADSUB = bytes.fromhex("A9 00")

# Final frame lifecycle hook sites reused by the ownership-based component.
STAGE5_FRAME_OPEN_HOOK_FILE = 0x000A37
STAGE5_FRAME_OPEN_GUARD = bytes.fromhex("8D 57 A1 8D 66 A1")
STAGE5_FRAME_CLOSE_HOOK_FILE = 0x0008D7
STAGE5_FRAME_CLOSE_GUARD = bytes.fromhex("9C 5E A1 9C 6D A1")

EVENT_EPILOGUE_FILE = 0x00021F
STOCK_EVENT_EPILOGUE_PREFIX = bytes.fromhex("A9 00 8F 13 1D 00")

# Exact first 16 bytes of each stock style. The clean-ROM SHA validation is
# still authoritative; these guards make accidental source-layout drift obvious.
STOCK_STYLE_PREFIXES = (
    bytes.fromhex("00 AA 00 AA 00 55 00 55 00 AA 00 AA 00 55 00 55"),
    bytes.fromhex("00 EA 00 BB 00 AA 00 AE 00 BB 00 EA 00 AE 00 AA"),
    bytes.fromhex("00 77 00 EE 00 DD 00 BB 00 77 00 EE 00 DD 00 BB"),
    bytes.fromhex("00 00 00 FF 00 00 00 FF 00 00 00 FF 00 00 00 FF"),
    bytes(16),
    bytes.fromhex("00 55 00 55 00 55 00 55 00 55 00 55 00 55 00 55"),
    bytes.fromhex("00 55 00 88 00 88 00 88 00 55 00 22 00 22 00 22"),
    bytes.fromhex("00 BB 00 7D 00 3E 00 5F 00 EE 00 F5 00 E3 00 D7"),
)


def validate_pattern_table(base: bytes) -> None:
    for style, expected in enumerate(STOCK_STYLE_PREFIXES):
        start = PATTERN_TABLE_FILE + style * PATTERN_STYLE_SIZE
        actual = base[start:start + len(expected)]
        if actual != expected:
            raise SystemExit(
                f"Unexpected stock dialogue-window pattern style {style} at "
                f"file 0x{start:06X}; refusing to patch."
            )


def validate_stage2_ppu_site(base: bytes) -> None:
    guards = (
        (CGWSEL_IMMEDIATE_FILE, STOCK_CGWSEL_IMMEDIATE, "CGWSEL immediate"),
        (CGADSUB_LOAD_FILE, STOCK_CGADSUB_LOAD, "CGADSUB load"),
        (COLDATA_WINDOW_INIT_FILE, STOCK_COLDATA_WINDOW_INIT, "COLDATA/window init"),
    )
    for start, expected, label in guards:
        actual = base[start:start + len(expected)]
        if actual != expected:
            raise SystemExit(
                f"Unexpected stock {label} bytes at file 0x{start:06X}: "
                f"{actual.hex(' ')} != {expected.hex(' ')}; refusing to patch."
            )


def validate_stage3_ppu_site(base: bytes) -> None:
    actual = base[WINDOW_LOGIC_RESET_FILE:WINDOW_LOGIC_RESET_FILE + len(STOCK_WINDOW_LOGIC_RESET)]
    if actual != STOCK_WINDOW_LOGIC_RESET:
        raise SystemExit(
            f"Unexpected stock window-logic reset bytes at file 0x{WINDOW_LOGIC_RESET_FILE:06X}: "
            f"{actual.hex(' ')} != {STOCK_WINDOW_LOGIC_RESET.hex(' ')}; refusing to patch."
        )


def apply_stage1(rom: bytearray) -> None:
    rom[PATTERN_TABLE_FILE:PATTERN_TABLE_END] = bytes(PATTERN_TABLE_SIZE)


def apply_stage2_ppu_probe(rom: bytearray) -> None:
    rom[CGWSEL_IMMEDIATE_FILE:CGWSEL_IMMEDIATE_FILE + 1] = STAGE2_CGWSEL_IMMEDIATE
    rom[CGADSUB_LOAD_FILE:CGADSUB_LOAD_FILE + 2] = STAGE2_CGADSUB_LOAD
    end = COLDATA_WINDOW_INIT_FILE + len(STAGE2_COLDATA_WINDOW_INIT)
    rom[COLDATA_WINDOW_INIT_FILE:end] = STAGE2_COLDATA_WINDOW_INIT


def apply_stage3_horizontal_window(rom: bytearray) -> None:
    rom[WINDOW_LOGIC_RESET_FILE:WINDOW_LOGIC_RESET_FILE + len(STAGE3_COLOR_WINDOW_ENABLE)] = (
        STAGE3_COLOR_WINDOW_ENABLE
    )
    rom[CGWSEL_IMMEDIATE_FILE:CGWSEL_IMMEDIATE_FILE + 1] = STAGE3_CGWSEL_IMMEDIATE
    start = COLDATA_WINDOW_INIT_FILE
    end = start + len(STAGE3_COLDATA_WINDOW_INIT)
    rom[start:end] = STAGE3_COLDATA_WINDOW_INIT
