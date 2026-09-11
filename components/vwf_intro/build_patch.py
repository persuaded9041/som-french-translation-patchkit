#!/usr/bin/env python3
"""Build the standalone new-game intro VWF runtime IPS patch.

This component owns the intro VWF renderer/runtime only. French text, glyph
installation, event-$0400 payload rebuilding, and the intro-private DTE table
are owned by `french_intro`.
"""

from __future__ import annotations

from pathlib import Path
import argparse
import struct
import sys

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from shared.asm65816 import MiniAssembler, lo16, lo24  # noqa: E402
from shared.french_charset import CHAR_TO_CODE, FULL_FRENCH_CHARS, glyph_bytes  # noqa: E402
from shared.ips import make_ips  # noqa: E402
from shared.rom import update_checksum, validate_base_rom  # noqa: E402
from shared.vwf_compositor import validate_stock as validate_shared_compositor_stock, install as install_shared_compositor  # noqa: E402
from shared.vwf_framing import SHARED_FRAMING_CPU, validate_stock as validate_shared_framing_stock, install as install_shared_framing  # noqa: E402
from shared.vwf_geometry import left_compact_glyph  # noqa: E402
from shared.vwf_metrics import apply_validated_framing, validated_advance  # noqa: E402
from shared.vwf_outline import validate_stock as validate_shared_outline_stock, install as install_shared_outline  # noqa: E402
from shared.vwf_row_renderer import ROW_RENDERER_CALL, validate_stock as validate_shared_row_renderer_stock, install as install_shared_row_renderer  # noqa: E402
from shared.vwf_text_buffer import (  # noqa: E402
    PARSER_WRITE_CPU,
    PARSER_WRITE_HELPER,
    validate_stock as validate_shared_text_buffer_stock,
    install_common as install_shared_text_buffer,
    enable_intro as enable_intro_private_buffer,
)

CODE_FILE = 0x074285
CODE_CPU = 0xC74285
WIDTH_CPU = 0xC74440
FONT_BASE = 0x12DC00

# This is the runtime-validated exclusive upper bound used by Round 75/76.
# `french_intro` asserts that its generated payload still ends exactly here.
INTRO_START = 0x0C02
INTRO_RUNTIME_END = 0x0E8B

EVENT_POINTER_TABLE = 0x09F800
RELOC_FIRST_EVENT = 0x0401
RELOC_LAST_EVENT = 0x040F
RELOC_SOURCE_START = 0x0E44
RELOC_SOURCE_END = 0x0E8C
RELOC_TARGET_START = 0xFF70

FRENCH_CHARS = FULL_FRENCH_CHARS
ASCII_TO_SOM = {" ": 0x80}
ASCII_TO_SOM.update({chr(ord("a") + i): 0x81 + i for i in range(26)})
ASCII_TO_SOM.update({chr(ord("A") + i): 0x9B + i for i in range(26)})
ASCII_TO_SOM.update({".": 0xBF, ",": 0xC0, "'": 0xC2})
ASCII_TO_SOM.update({ch: CHAR_TO_CODE[ch] for ch in FRENCH_CHARS})
INTRO_RENDER_CODES = frozenset(ASCII_TO_SOM.values())


def relocate_following_events(base: bytes, rom: bytearray) -> None:
    """Move $0401-$040F out of the validated intro VWF runtime window.

    `french_intro` performs the exact same relocation so both standalone
    components remain safe and their aggregate overlap is byte-identical.
    """
    relocate_len = RELOC_SOURCE_END - RELOC_SOURCE_START
    source_file = 0x0A0000 + RELOC_SOURCE_START
    target_file = 0x0A0000 + RELOC_TARGET_START
    if any(value != 0xFF for value in rom[target_file : target_file + relocate_len]):
        raise SystemExit("Expected CA:$FF70 relocation area to be empty")
    rom[target_file : target_file + relocate_len] = rom[source_file : source_file + relocate_len]
    delta = RELOC_TARGET_START - RELOC_SOURCE_START
    for event_id in range(RELOC_FIRST_EVENT, RELOC_LAST_EVENT + 1):
        pointer_offset = EVENT_POINTER_TABLE + event_id * 2
        old_pointer = struct.unpack_from("<H", base, pointer_offset)[0]
        if not (RELOC_SOURCE_START <= old_pointer < RELOC_SOURCE_END):
            raise SystemExit(f"Unexpected event ${event_id:04X} pointer: ${old_pointer:04X}")
        struct.pack_into("<H", rom, pointer_offset, old_pointer + delta)


def assemble_vwf(intro_end_ptr: int) -> bytes:
    """Assemble the intro-only VWF routine."""
    a = MiniAssembler(CODE_CPU)

    a.emit(0xAF, *lo24(0x001D03))
    a.emit(0xC9, 0xCA)
    a.rel8(0xF0, "bank_ok")
    a.emit(0xAD, *lo16(0xA1CE))
    a.emit(0x29, 0x7F)
    a.emit(0x5C, *lo24(0xC01669))

    a.label("bank_ok")
    a.emit(0xC2, 0x20)
    a.emit(0xAF, *lo24(0x001D01))
    a.emit(0xC9, *lo16(INTRO_START))
    a.rel8(0xB0, "low_ok")
    a.emit(0xE2, 0x20)
    a.emit(0xAD, *lo16(0xA1CE))
    a.emit(0x29, 0x7F)
    a.emit(0x5C, *lo24(0xC01669))

    a.label("low_ok")
    a.emit(0xC9, *lo16(intro_end_ptr))
    a.rel8(0x90, "range_ok")
    a.emit(0xE2, 0x20)
    a.emit(0xAD, *lo16(0xA1CE))
    a.emit(0x29, 0x7F)
    a.emit(0x5C, *lo24(0xC01669))

    a.label("range_ok")
    a.emit(0xE2, 0x20)

    a.emit(0xAD, *lo16(0xA1CE))
    a.emit(0x29, 0x7F)
    a.rel8(0xD0, "have_count")
    a.emit(0xAD, *lo16(0xA1CE))
    a.emit(0x29, 0x7F)
    a.emit(0x5C, *lo24(0xC01669))

    a.label("have_count")
    a.emit(0x8D, *lo16(0x9380))
    a.emit(0xAD, *lo16(0xA1CE))
    a.emit(0x29, 0x80)
    a.emit(0x8D, *lo16(0x9381))

    a.emit(0xA2, *lo16(0x0000))
    a.label("clear")
    a.emit(0x9E, *lo16(0x9000))
    a.emit(0xE8)
    a.emit(0xE0, *lo16(0x0180))
    a.rel8(0xD0, "clear")

    a.emit(0x9C, *lo16(0x9382))
    a.emit(0xA2, *lo16(0x0000))

    a.label("char_loop")
    a.emit(0x8A)
    a.emit(0xCD, *lo16(0x9380))
    a.rel8(0xD0, "char_body")
    a.rel16(0x82, "done")

    a.label("char_body")
    a.emit(0xBD, *lo16(0x9390))
    a.emit(0xE8)
    a.emit(0xDA)

    a.emit(0xC2, 0x20)
    a.emit(0x29, *lo16(0x00FF))
    a.emit(0x38)
    a.emit(0xE9, *lo16(0x0080))
    a.emit(0xAA)
    a.emit(0xE2, 0x20)

    a.emit(0xBF, *lo24(WIDTH_CPU))
    a.emit(0x8D, *lo16(0x9385))

    a.emit(0xC2, 0x20)
    a.emit(0x8A)
    a.emit(0x0A)
    a.emit(0x0A)
    a.emit(0x8D, *lo16(0x9386))
    a.emit(0x0A)
    a.emit(0x18)
    a.emit(0x6D, *lo16(0x9386))
    a.emit(0xAA)

    a.emit(0xC2, 0x20)
    a.emit(0xAD, *lo16(0x9382))
    a.emit(0x29, *lo16(0x00FF))
    a.emit(0x4A)
    a.emit(0x4A)
    a.emit(0x4A)
    a.emit(0x0A)
    a.emit(0x0A)
    a.emit(0x8D, *lo16(0x9386))
    a.emit(0x0A)
    a.emit(0x18)
    a.emit(0x6D, *lo16(0x9386))
    a.emit(0xA8)

    a.emit(0xE2, 0x20)
    a.emit(0xA9, 0x0C)
    a.emit(0x8D, *lo16(0x9386))

    a.label("row_loop")
    a.emit(*ROW_RENDERER_CALL)
    a.emit(0xE8)
    a.emit(*([0xEA] * 8))
    a.emit(0x99, *lo16(0x9000))
    a.emit(0xC8)
    a.emit(0xCE, *lo16(0x9386))
    a.rel8(0xD0, "row_loop")

    a.emit(0xFA)
    a.emit(0xAD, *lo16(0x9382))
    a.emit(0x18)
    a.emit(0x6D, *lo16(0x9385))
    a.emit(0x8D, *lo16(0x9382))
    a.rel16(0x82, "char_loop")

    a.label("done")
    a.emit(0xC2, 0x20)
    a.emit(0xAF, *lo24(0x001D01))
    a.emit(0xAA)
    a.emit(0xE2, 0x20)
    a.emit(0xBF, *lo24(0xCA0000))
    a.emit(0xC9, 0x28)
    a.rel8(0xD0, "done_return")

    a.emit(0xAD, *lo16(0x9382))
    a.emit(0x18)
    a.emit(0x69, 0x07)
    a.emit(0x4A)
    a.emit(0x4A)
    a.emit(0x4A)
    a.emit(0x09, 0x00)
    a.emit(0x0D, *lo16(0x9381))
    a.emit(0x8D, *lo16(0xA1CE))

    a.label("done_return")
    a.emit(0x5C, *lo24(0xC016B7))
    return a.resolve()


def make_vwf_font(base: bytearray) -> tuple[bytes, bytes, bytes]:
    """Build the validated width/framing tables without installing French glyphs.

    Metrics are calculated against a virtual copy of the stock font with the
    canonical shared French glyphs inserted. This preserves the exact Round 75
    width table while leaving glyph ownership entirely to `french_intro`.
    """
    virtual_font = bytearray(base[FONT_BASE : FONT_BASE + 128 * 12])
    try:
        french_glyphs = glyph_bytes(FRENCH_CHARS)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    accent_first = min(CHAR_TO_CODE[ch] for ch in FRENCH_CHARS)
    glyph_start = (accent_first - 0x80) * 12
    virtual_font[glyph_start : glyph_start + len(french_glyphs)] = french_glyphs

    framed = bytearray()
    advances = bytearray()
    for glyph_index in range(128):
        code = glyph_index + 0x80
        rows = virtual_font[glyph_index * 12 : (glyph_index + 1) * 12]
        if code in INTRO_RENDER_CODES:
            framed.extend(apply_validated_framing(code, rows))
            advances.append(validated_advance(code, rows))
        else:
            compact_rows, ink_width = left_compact_glyph(rows)
            framed.extend(compact_rows)
            advances.append(min(8, ink_width + 1) if ink_width else 4)
    return bytes(advances), bytes(framed), bytes(virtual_font)


def main(source_rom: Path, output_path: Path, patched_rom: Path | None = None) -> None:
    base = bytearray(source_rom.read_bytes())
    validate_base_rom(base)
    rom = bytearray(base)

    relocate_following_events(base, rom)

    code = assemble_vwf(INTRO_RUNTIME_END)
    advances, expected_framed_font, virtual_font = make_vwf_font(base)

    if any(advances[code_value - 0x80] == 1 for code_value in INTRO_RENDER_CODES):
        raise SystemExit("Intro glyph advance collides with `vwf_dialogues` active tag value $01")
    if CODE_CPU + len(code) > PARSER_WRITE_CPU:
        raise SystemExit(f"VWF code overlaps shared parser helper: {len(code):#x} bytes")
    if PARSER_WRITE_CPU + len(PARSER_WRITE_HELPER) > WIDTH_CPU:
        raise SystemExit(f"Shared parser helper is too large: {len(PARSER_WRITE_HELPER):#x} bytes")

    payload = code
    payload += bytes([0xFF]) * (PARSER_WRITE_CPU - (CODE_CPU + len(code)))
    payload += PARSER_WRITE_HELPER
    payload += bytes([0xFF]) * (WIDTH_CPU - (PARSER_WRITE_CPU + len(PARSER_WRITE_HELPER)))
    payload += advances

    if WIDTH_CPU + len(advances) != SHARED_FRAMING_CPU:
        raise SystemExit("Intro width table no longer ends at shared framing selector")

    for code_value in INTRO_RENDER_CODES:
        glyph_index = code_value - 0x80
        start = glyph_index * 12
        expected = expected_framed_font[start:start + 12]
        actual = apply_validated_framing(code_value, virtual_font[start:start + 12])
        if actual != expected:
            raise SystemExit(f"Shared runtime framing mismatch for intro code ${code_value:02X}")

    if any(value != 0xFF for value in rom[CODE_FILE : CODE_FILE + len(payload)]):
        raise SystemExit("Expected VWF free-space area at $C7:4285 to be empty")
    validate_shared_text_buffer_stock(base)
    validate_shared_framing_stock(base)
    validate_shared_compositor_stock(base)
    validate_shared_row_renderer_stock(base)
    validate_shared_outline_stock(base)

    if rom[0x1664:0x1668] != bytes.fromhex("ad ce a1 29"):
        raise SystemExit("Stock renderer signature mismatch at ROM $001664")
    rom[0x1664:0x1668] = bytes.fromhex("5c 85 42 c7")

    rom[CODE_FILE : CODE_FILE + len(payload)] = payload
    install_shared_text_buffer(rom)
    install_shared_framing(rom)
    install_shared_compositor(rom)
    install_shared_row_renderer(rom)
    install_shared_outline(rom)
    enable_intro_private_buffer(rom, INTRO_RUNTIME_END)

    checksum = update_checksum(rom)
    complement = checksum ^ 0xFFFF
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(make_ips(base, rom))
    if patched_rom:
        patched_rom.parent.mkdir(parents=True, exist_ok=True)
        patched_rom.write_bytes(rom)

    print(f"Intro VWF runtime window: ${INTRO_START:04X}-${INTRO_RUNTIME_END:04X}")
    print(f"Checksum: {checksum:04X}; complement: {complement:04X}")
    print(f"Patch written to: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the standalone intro VWF runtime patch.")
    parser.add_argument("rom", type=Path, help="clean unheadered Secret of Mana (USA) ROM")
    parser.add_argument("-o", "--output", type=Path, default=ROOT / "build" / "patch.ips", help="output IPS path")
    parser.add_argument("--patched-rom", type=Path, help="optional patched ROM output")
    args = parser.parse_args()
    main(args.rom, args.output, args.patched_rom)
