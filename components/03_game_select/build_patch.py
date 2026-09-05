#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Stock GAME SELECT label resource in bank C7.
# Relocate the resource inside bank C7 because the descriptor stores
# only a 16-bit pointer and the translated fields no longer fit the stock blob.
MENU_RESOURCE_RELOC_OFFSET = 0x074400  # C7:4400, stock free space
MENU_RESOURCE_RELOC_PTR = 0x4400
MENU_DESCRIPTOR_TEXT_PTR_OFFSET = 0x07780A

# The D-pad label occupies eight decoded cells after the initial prefix.
# Keeping this segment at eight preserves its two stock placements.
SELECT_SLOT_CELLS = 8

# Three type-1 records in menu #0 describe the framed text fields.  The high
# byte of their packed size is the horizontal size; each unit corresponds to
# two decoded character cells.
FRAME_WIDTH_OFFSETS = {
    "GAME_SELECT": 0x07756D,
    "NEW_GAME":    0x077572,
    "GAME_FILE":   0x077577,
}
STOCK_FRAME_WIDTHS = {
    "GAME_SELECT": 0x07,
    "NEW_GAME":    0x05,
    "GAME_FILE":   0x06,
}

# The native menu resource is exactly 45 source bytes including its final $00.
# Changing this physical size desynchronizes the
# help-text rendering, so the builder preserves the 45-byte layout exactly.
MENU_RESOURCE_SAFE_SOURCE_SIZE = 45
WELCOME_POINTER_OFFSET = 0x0033B5       # stock pointer = C0:33F0
WELCOME_RELOC_OFFSET = 0x2D8000         # SNES ED:8000
WELCOME_RELOC_SNES = 0xED8000

# GAME FILE / save-menu text uses two stock runtime paths.  The full resource
# is relocated so FILE_LABEL can grow from the 4-cell stock "FILE" to the
# 7-cell French "Fichier", but several labels are still consumed directly
# from C7:7340 by another path.  Keep both copies synchronized.
GAME_FILE_STOCK_RESOURCE_OFFSET = 0x077340
GAME_FILE_STOCK_RESOURCE_END = 0x0773BC      # next resource begins at C7:73BC
GAME_FILE_STOCK_RESOURCE_PTR = 0x7340
GAME_FILE_RELOC_OFFSET = 0x074D40             # C7:4D40, stock $FF free space
GAME_FILE_RELOC_PTR = 0x4D40
GAME_FILE_POINTER_OFFSETS = (0x077810, 0x077816)
# FILE label frame descriptor: stock width $03 = 6 cells.  Fichier needs
# 7 visible cells plus the native margin; use the runtime-validated $04 = 8 cells.
GAME_FILE_FILE_FRAME_WIDTH_OFFSET = 0x077585
GAME_FILE_FILE_FRAME_STOCK_WIDTH = 0x03
GAME_FILE_FILE_FRAME_NEW_WIDTH = 0x04
GAME_FILE_FILE_SEGMENT_START = 0x077349
GAME_FILE_FILE_SEGMENT_END = 0x07734F         # FILE + one blank + $00

# Dynamic slot level prefix. Two GAME FILE rendering paths write the stock
# single-cell "L" directly into the menu text buffer. French uses "N"
# (Niveau), which is a same-width, one-byte substitution in both paths.
GAME_FILE_LEVEL_LABEL_OFFSETS = (0x0753C9, 0x075AF1)
GAME_FILE_LEVEL_LABEL_STOCK = 0xA6  # L

# Field offsets inside C7:7340.  These capacities include adjacent stock
# padding cells that were runtime-validated for the French labels.  The same
# fields are written both into the relocated resource and back into the stock
# resource because GAME FILE uses both paths at runtime.
GAME_FILE_RESOURCE_FIELDS = {
    "FILE_SELECT": (0x077341, 7),
    "SAVE_POINT":  (0x077350, 11),
    "MONEY":       (0x077374, 6),
    "GP":          (0x077394, 2),
    "COUNTER":     (0x077398, 8),
    "MANA_POWER":  (0x0773AA, 10),
}
# FILE_LABEL is special: the stock path has only four cells, so it receives
# the first four encoded cells ("Fich" for the current translation), while the
# relocated path contains the complete label.
GAME_FILE_FILE_STOCK_CAPACITY = 4
GAME_FILE_EXTERNAL_FIELDS = {
    "EMPTY":       (0x077805, 5),
}
SAVE_HELP_POINTER_OFFSET = 0x0033B8     # stock pointer = C0:348D
SAVE_HELP_RELOC_OFFSET = 0x2D8400        # SNES ED:8400
SAVE_HELP_RELOC_SNES = 0xED8400
SAVE_HELP_RELOC_LIMIT = 0x2E0000         # end of component reserved bank


ASCII_TO_SOM = {" ": 0x80}
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
from shared.french_charset import BASIC_FRENCH_CHARS, glyph_bytes, profile_mapping, profile_threshold
from shared.rom import validate_base_rom, update_checksum, expand_rom, ROM_SIZE_OFFSET
from shared.ips import make_ips
from shared.interface_text import (
    load_document as load_interface_text,
    verify_against_rom as verify_interface_text,
)
from shared.menu_text import (
    load_document as load_menu_text,
    verify_against_rom as verify_menu_text,
)
from shared.translation_json import load_translation, require

ACCENT_TO_SOM = profile_mapping("basic_french")
ASCII_TO_SOM.update(ACCENT_TO_SOM)
ASCII_TO_SOM.update({chr(ord("a") + i): 0x81 + i for i in range(26)})
ASCII_TO_SOM.update({chr(ord("A") + i): 0x9B + i for i in range(26)})
ASCII_TO_SOM.update({str(i): 0xB5 + i for i in range(10)})
ASCII_TO_SOM.update({
    ".": 0xBF, ",": 0xC0, "/": 0xC1, "'": 0xC2,
    '"': 0xC3,  # handled specially below to alternate opening/closing quote
    "-": 0xC6, "%": 0xC7, "!": 0xC8, "&": 0xC9,
    "?": 0xCA, "(": 0xCB, ")": 0xCC, "#": 0xCD,
})



# Stock US 8x12 font. Character $80 begins at ROM $12DC00.
FONT_BASE = 0x12DC00
GLYPH_HEIGHT = 12
ACCENT_FIRST = ACCENT_TO_SOM[BASIC_FRENCH_CHARS[0]]
ROOT = Path(__file__).resolve().parent

# The stock text decoder treats $D3-$FF as DTE dictionary bytes.
# For this project, $D4-$E0 become ordinary glyph codes, so the DTE
# threshold moves to $E1. The original US script does not use these
# DTE values as text.
DTE_COMPARE_IMMEDIATE_OFFSET = 0x0016F6
DTE_STOCK_THRESHOLD = 0xD3
DTE_NEW_THRESHOLD = profile_threshold("basic_french")

def load_accent_glyphs() -> bytes:
    """Load the canonical shared GAME SELECT French glyph profile."""
    try:
        return glyph_bytes(BASIC_FRENCH_CHARS)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc




def encode_text(text: str, context: str) -> bytes:
    out = bytearray()
    quote_open = True
    for pos, ch in enumerate(text):
        if ch == '"':
            out.append(0xC3 if quote_open else 0xC4)
            quote_open = not quote_open
            continue
        if ch not in ASCII_TO_SOM:
            raise SystemExit(
                f"Unsupported character {ch!r} in {context} at position {pos}. "
                "The GAME SELECT builder supports ASCII plus the shared basic_french profile."
            )
        out.append(ASCII_TO_SOM[ch])
    if not quote_open:
        raise SystemExit(f"Unbalanced double quote in {context}")
    return bytes(out)



GAME_SELECT_IDS = {
    "SELECT": "C7:7314",
    "GAME_SELECT": "C7:731C",
    "NEW_GAME": "C7:732A",
    "GAME_FILE": "C7:7334",
}
WELCOME_IDS = {
    "WELCOME_1": "C0:33F0",
    "WELCOME_2": "C0:340C",
    "WELCOME_3": "C0:343B",
    "WELCOME_4": "C0:3472",
}
GAME_FILE_IDS = {
    "FILE_SELECT": "C7:7341",
    "FILE_LABEL": "C7:7349",
    "SAVE_POINT": "C7:7350",
    "MONEY": "C7:7374",
    "GP": "C7:7394",
    "COUNTER": "C7:7398",
    "MANA_POWER": "C7:73AA",
    "EMPTY": "C7:7805",
    "LEVEL_PREFIX_A": "C7:53C9",
    "LEVEL_PREFIX_B": "C7:5AF1",
}
SAVE_HELP_IDS = {
    "SAVE_HELP_1": "C0:348D",
    "SAVE_HELP_2": "C0:34BE",
}


def load_french_rows(base: bytes) -> tuple[dict[str, str], dict[str, str]]:
    interface = load_interface_text(PROJECT_ROOT / "assets" / "interface_text.json")
    menu = load_menu_text(PROJECT_ROOT / "assets" / "menu_text.json")
    try:
        verify_interface_text(base, interface)
        verify_menu_text(base, menu)
        interface_fr = load_translation(
            PROJECT_ROOT / "translations" / "interface_text_french.json",
            interface,
            source_asset="interface_text.json",
        )
        menu_fr = load_translation(
            PROJECT_ROOT / "translations" / "menu_text_french.json",
            menu,
            source_asset="menu_text.json",
        )

        rows = {
            name: require(menu_fr, [text_id], context="GAME SELECT")[0]
            for name, text_id in GAME_SELECT_IDS.items()
        }
        rows.update({
            name: require(interface_fr, [text_id], context="GAME SELECT welcome")[0]
            for name, text_id in WELCOME_IDS.items()
        })
        game_file_rows = {
            name: require(menu_fr, [text_id], context="GAME FILE")[0]
            for name, text_id in GAME_FILE_IDS.items()
        }
        game_file_rows.update({
            name: require(interface_fr, [text_id], context="GAME FILE save help")[0]
            for name, text_id in SAVE_HELP_IDS.items()
        })
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    return rows, game_file_rows


def _min_even_width(text: str, context: str) -> tuple[bytes, int]:
    """Encode a framed label and reserve at least one cell on its right."""
    payload = encode_text(text, context)
    cells = len(payload) + 1
    if cells & 1:
        cells += 1
    return payload, cells


def build_menu_resource(rows: dict[str, str]) -> tuple[bytes, dict[str, int]]:
    """Build the native 45-byte GAME SELECT resource, without DTE.

    The stock resource is structurally 45 bytes.  Its first nine bytes are the
    leading blank plus the fixed 8-cell SELECT segment.  The three framed
    fields then occupy 36 logical cells in total.  The final $00 terminator
    doubles as the last logical cell of GAME_FILE, exactly as in the stock US
    resource.  Keeping this invariant prevents the following help-text buffer
    from being desynchronised.
    """
    select = encode_text(rows["SELECT"], "SELECT")
    if len(select) > SELECT_SLOT_CELLS - 1:
        raise SystemExit(
            f"SELECT encodes to {len(select)} cells; at most {SELECT_SLOT_CELLS - 1} "
            "visible cells are supported while preserving the stock D-pad layout."
        )
    select_slot = select + b"\x80" * (SELECT_SLOT_CELLS - len(select))

    payloads: dict[str, bytes] = {}
    width_cells: dict[str, int] = {}
    for key in ("GAME_SELECT", "NEW_GAME", "GAME_FILE"):
        payload, cells = _min_even_width(rows[key], key)
        payloads[key] = payload
        width_cells[key] = cells

    # The native resource has 36 framed cells. Distribute spare pairs in
    # display order, which gives GAME_SELECT the first extra margin.
    TARGET_TOTAL_CELLS = 36
    used = sum(width_cells.values())
    if used > TARGET_TOTAL_CELLS:
        raise SystemExit(
            f"GAME SELECT framed fields require {used} cells; the native no-DTE layout "
            f"supports {TARGET_TOTAL_CELLS}. Choose shorter labels."
        )
    spare = TARGET_TOTAL_CELLS - used
    if spare & 1:
        raise SystemExit("Internal error: framed width spare space is not even")
    priority = ("GAME_SELECT", "NEW_GAME", "GAME_FILE")
    i = 0
    while spare:
        width_cells[priority[i % 3]] += 2
        spare -= 2
        i += 1

    widths = {key: width_cells[key] // 2 for key in width_cells}

    game_select = payloads["GAME_SELECT"] + b"\x80" * (width_cells["GAME_SELECT"] - len(payloads["GAME_SELECT"]))
    new_game = payloads["NEW_GAME"] + b"\x80" * (width_cells["NEW_GAME"] - len(payloads["NEW_GAME"]))

    # Stock quirk: GAME_FILE contributes one source byte fewer than its logical
    # width; the final $00 resource terminator is its last cell.
    gf_source_cells = width_cells["GAME_FILE"] - 1
    if len(payloads["GAME_FILE"]) > gf_source_cells:
        raise SystemExit("GAME_FILE does not leave room for the native final terminator cell")
    game_file = payloads["GAME_FILE"] + b"\x80" * (gf_source_cells - len(payloads["GAME_FILE"]))

    resource = b"\x80" + select_slot + game_select + new_game + game_file + b"\x00"
    if len(resource) != MENU_RESOURCE_SAFE_SOURCE_SIZE:
        raise SystemExit(
            f"Internal error: GAME SELECT resource is {len(resource)} bytes, expected exactly "
            f"{MENU_RESOURCE_SAFE_SOURCE_SIZE}."
        )
    return resource, widths


def build_welcome(rows: dict[str, str]) -> bytes:
    # Stock layout is intentionally preserved:
    # line 1, blank line, lines 2-4, then one final blank line, then $00.
    encoded = [encode_text(rows[f"WELCOME_{i}"], f"WELCOME_{i}") for i in range(1, 5)]
    return encoded[0] + b"\x7F\x7F" + encoded[1] + b"\x7F" + encoded[2] + b"\x7F" + encoded[3] + b"\x7F\x7F\x00"




def build_save_help(rows: dict[str, str]) -> bytes:
    line1 = encode_text(rows["SAVE_HELP_1"], "SAVE_HELP_1")
    line2 = encode_text(rows["SAVE_HELP_2"], "SAVE_HELP_2")
    return line1 + b"\x7F" + line2 + b"\x00"


def build_game_file_resource(base: bytes, rows: dict[str, str]) -> bytes:
    """Relocate the native C7:7340 save/load-menu resource and expand FILE_LABEL.

    The resource is otherwise kept byte-for-byte stock except for translation-backed
    fields.  The stock FILE segment is `FILE`, one blank cell and `$00`; its
    replacement keeps the same trailing blank + terminator convention, so the
    parser sees the same structure with a longer label.
    """
    stock = bytearray(base[GAME_FILE_STOCK_RESOURCE_OFFSET:GAME_FILE_STOCK_RESOURCE_END])
    if len(stock) != GAME_FILE_STOCK_RESOURCE_END - GAME_FILE_STOCK_RESOURCE_OFFSET:
        raise SystemExit("Could not read complete stock GAME FILE resource")

    file_payload = encode_text(rows["FILE_LABEL"], "FILE_LABEL")
    if not file_payload:
        raise SystemExit("FILE_LABEL may not be empty")
    replacement = file_payload + b"\x80\x00"
    rel_start = GAME_FILE_FILE_SEGMENT_START - GAME_FILE_STOCK_RESOURCE_OFFSET
    rel_end = GAME_FILE_FILE_SEGMENT_END - GAME_FILE_STOCK_RESOURCE_OFFSET
    resource = stock[:rel_start] + replacement + stock[rel_end:]
    delta = len(replacement) - (rel_end - rel_start)

    for key, (stock_offset, capacity) in GAME_FILE_RESOURCE_FIELDS.items():
        payload = encode_text(rows[key], key)
        if len(payload) > capacity:
            raise SystemExit(
                f"{key} encodes to {len(payload)} cells; current validated field capacity is {capacity}."
            )
        rel = stock_offset - GAME_FILE_STOCK_RESOURCE_OFFSET
        if stock_offset >= GAME_FILE_FILE_SEGMENT_END:
            rel += delta
        resource[rel:rel + capacity] = payload + b"\x80" * (capacity - len(payload))

    return bytes(resource)


def apply_game_file_sources(base: bytes, rom: bytearray, rows: dict[str, str]) -> None:
    resource = build_game_file_resource(base, rows)
    reloc_end = GAME_FILE_RELOC_OFFSET + len(resource)
    # Stop before the standalone 9-char names allocation at C7:4E00.
    if reloc_end > 0x074E00:
        raise SystemExit("Relocated GAME FILE resource exceeded C7:4D40-C7:4DFF")
    if any(b != 0xFF for b in base[GAME_FILE_RELOC_OFFSET:reloc_end]):
        raise SystemExit("GAME FILE relocation target C7:4D40 is not stock $FF free space")
    rom[GAME_FILE_RELOC_OFFSET:reloc_end] = resource

    # Expand the small FILE frame from 6 to 8 text cells. The menu descriptor
    # uses the same two-cells-per-width-unit convention as GAME SELECT.
    if base[GAME_FILE_FILE_FRAME_WIDTH_OFFSET] != GAME_FILE_FILE_FRAME_STOCK_WIDTH:
        raise SystemExit(
            f"Unexpected stock FILE frame width at ${GAME_FILE_FILE_FRAME_WIDTH_OFFSET:06X}: "
            f"${base[GAME_FILE_FILE_FRAME_WIDTH_OFFSET]:02X}"
        )
    rom[GAME_FILE_FILE_FRAME_WIDTH_OFFSET] = GAME_FILE_FILE_FRAME_NEW_WIDTH

    # Translate the dynamic level prefix in both direct-rendering paths.
    for key, offset in zip(("LEVEL_PREFIX_A", "LEVEL_PREFIX_B"), GAME_FILE_LEVEL_LABEL_OFFSETS, strict=True):
        if base[offset] != GAME_FILE_LEVEL_LABEL_STOCK:
            raise SystemExit(
                f"Unexpected stock GAME FILE level label at ${offset:06X}: "
                f"${base[offset]:02X}"
            )
        payload = encode_text(rows[key], key)
        if len(payload) != 1:
            raise SystemExit(f"{key} must remain exactly one encoded cell")
        rom[offset] = payload[0]

    for pointer_offset in GAME_FILE_POINTER_OFFSETS:
        stock_ptr = int.from_bytes(base[pointer_offset:pointer_offset + 2], "little")
        if stock_ptr != GAME_FILE_STOCK_RESOURCE_PTR:
            raise SystemExit(
                f"Unexpected GAME FILE resource pointer at ${pointer_offset:06X}: ${stock_ptr:04X}"
            )
        rom[pointer_offset:pointer_offset + 2] = GAME_FILE_RELOC_PTR.to_bytes(2, "little")

    # Runtime validation showed that redirecting the two table pointers is not
    # sufficient: another GAME FILE path still reads these labels from their
    # original C7:7340 locations.  Mirror the translation-backed values in place while
    # preserving every stock field boundary.
    for key, (offset, capacity) in GAME_FILE_RESOURCE_FIELDS.items():
        payload = encode_text(rows[key], key)
        if len(payload) > capacity:
            raise SystemExit(
                f"{key} encodes to {len(payload)} cells; current validated field capacity is {capacity}."
            )
        rom[offset:offset + capacity] = payload + b"\x80" * (capacity - len(payload))

    file_payload = encode_text(rows["FILE_LABEL"], "FILE_LABEL")
    stock_file = file_payload[:GAME_FILE_FILE_STOCK_CAPACITY]
    rom[GAME_FILE_FILE_SEGMENT_START:GAME_FILE_FILE_SEGMENT_START + GAME_FILE_FILE_STOCK_CAPACITY] = (
        stock_file + b"\x80" * (GAME_FILE_FILE_STOCK_CAPACITY - len(stock_file))
    )

    for key, (offset, capacity) in GAME_FILE_EXTERNAL_FIELDS.items():
        payload = encode_text(rows[key], key)
        if len(payload) > capacity:
            raise SystemExit(f"{key} encodes to {len(payload)} cells; capacity is {capacity}.")
        rom[offset:offset + capacity] = payload + b"\x80" * (capacity - len(payload))

    help_payload = build_save_help(rows)
    if SAVE_HELP_RELOC_OFFSET + len(help_payload) > SAVE_HELP_RELOC_LIMIT:
        raise SystemExit("GAME FILE save help exceeded the reserved ED:8400-ED:FFFF region")
    rom[SAVE_HELP_RELOC_OFFSET:SAVE_HELP_RELOC_OFFSET + len(help_payload)] = help_payload
    rom[SAVE_HELP_POINTER_OFFSET:SAVE_HELP_POINTER_OFFSET + 3] = SAVE_HELP_RELOC_SNES.to_bytes(3, "little")


def apply_sources(base: bytes, rows: dict[str, str], game_file_rows: dict[str, str]) -> tuple[bytearray, int]:
    rom = expand_rom(base)

    # Turn $D4-$E0 into normal character codes for the stock text
    # decoder, while keeping $E1-$FF on the original DTE path.
    if base[DTE_COMPARE_IMMEDIATE_OFFSET] != DTE_STOCK_THRESHOLD:
        raise SystemExit(
            f"Unexpected stock DTE threshold at ${DTE_COMPARE_IMMEDIATE_OFFSET:06X}: "
            f"${base[DTE_COMPARE_IMMEDIATE_OFFSET]:02X}"
        )
    rom[DTE_COMPARE_IMMEDIATE_OFFSET] = DTE_NEW_THRESHOLD

    # Replace the 13 otherwise-unused direct-glyph slots $D4-$E0 with the
    # editable 8x12 glyph atlas in shared/french_charset/french_glyphs.png.
    glyph_start = FONT_BASE + (ACCENT_FIRST - 0x80) * GLYPH_HEIGHT
    glyph_blob = load_accent_glyphs()
    rom[glyph_start:glyph_start + len(glyph_blob)] = glyph_blob

    # Relocate the label resource and derive all three frame widths directly
    # from the translated text so field segmentation and window geometry stay aligned.
    menu_resource, frame_widths = build_menu_resource(rows)
    if MENU_RESOURCE_RELOC_OFFSET + len(menu_resource) > 0x075000:
        raise SystemExit("Relocated GAME SELECT resource exceeded reserved C7:4400-C7:4FFF")
    rom[MENU_RESOURCE_RELOC_OFFSET:MENU_RESOURCE_RELOC_OFFSET + len(menu_resource)] = menu_resource
    rom[MENU_DESCRIPTOR_TEXT_PTR_OFFSET:MENU_DESCRIPTOR_TEXT_PTR_OFFSET + 2] = MENU_RESOURCE_RELOC_PTR.to_bytes(2, "little")

    for key, offset in FRAME_WIDTH_OFFSETS.items():
        if base[offset] != STOCK_FRAME_WIDTHS[key]:
            raise SystemExit(
                f"Unexpected stock {key} frame width at ${offset:06X}: ${base[offset]:02X}"
            )
        rom[offset] = frame_widths[key]

    # GAME FILE/save-menu strings share this decoder/font.  The full resource
    # is relocated for Fichier, while the stock label fields are mirrored in
    # place for the second runtime path.  Save help is relocated separately.
    apply_game_file_sources(base, rom, game_file_rows)

    # Relocate the long help text now, so its translation will no longer be
    # constrained by the 156-byte stock allocation at C0:33F0.
    welcome = build_welcome(rows)
    if WELCOME_RELOC_OFFSET + len(welcome) > 0x2E0000:
        raise SystemExit("WELCOME text exceeded the reserved ED:8000-ED:FFFF region")
    rom[WELCOME_RELOC_OFFSET:WELCOME_RELOC_OFFSET + len(welcome)] = welcome
    rom[WELCOME_POINTER_OFFSET:WELCOME_POINTER_OFFSET + 3] = WELCOME_RELOC_SNES.to_bytes(3, "little")

    rom[ROM_SIZE_OFFSET] = 0x0C  # 3 MiB physical ROM
    checksum = update_checksum(rom)
    return rom, checksum



def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Secret of Mana (USA) French GAME SELECT component")
    parser.add_argument("rom", type=Path, help="clean unheadered Secret of Mana (USA) ROM")
    parser.add_argument("-o", "--output", type=Path, default=Path("build/patch.ips"), help="output IPS")
    parser.add_argument("--patched-rom", type=Path, help="optional output ROM for local testing")
    args = parser.parse_args()

    base = args.rom.read_bytes()
    validate_base_rom(base)

    rows, game_file_rows = load_french_rows(base)
    patched, checksum = apply_sources(base, rows, game_file_rows)
    patch = make_ips(base, bytes(patched))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(patch)
    if args.patched_rom:
        args.patched_rom.parent.mkdir(parents=True, exist_ok=True)
        args.patched_rom.write_bytes(patched)

    print(f"Patch: {args.output}")
    print(f"Expanded ROM size: {len(patched):#x}")
    print(f"SNES checksum: ${checksum:04X}")
    print(f"WELCOME pointer: ${int.from_bytes(patched[WELCOME_POINTER_OFFSET:WELCOME_POINTER_OFFSET+3], 'little'):06X}")
    print(f"WELCOME payload: {len(build_welcome(rows))} bytes at ROM ${WELCOME_RELOC_OFFSET:06X}")
    print(f"GAME FILE resource pointer: C7:${GAME_FILE_RELOC_PTR:04X}")
    print(f"GAME FILE resource: {len(build_game_file_resource(base, game_file_rows))} bytes at ROM ${GAME_FILE_RELOC_OFFSET:06X}")
    print(f"GAME FILE save-help pointer: ${int.from_bytes(patched[SAVE_HELP_POINTER_OFFSET:SAVE_HELP_POINTER_OFFSET+3], 'little'):06X}")
    print(f"GAME FILE save-help payload: {len(build_save_help(game_file_rows))} bytes at ROM ${SAVE_HELP_RELOC_OFFSET:06X}")
    menu_resource, widths = build_menu_resource(rows)
    print(f"GAME SELECT resource: {len(menu_resource)} bytes at C7:${MENU_RESOURCE_RELOC_PTR:04X}")
    print("GAME SELECT layout: native 45-byte resource; no additional DTE compression")
    for key in ("GAME_SELECT", "NEW_GAME", "GAME_FILE"):
        print(f"{key} frame width: ${widths[key]:02X} ({widths[key] * 2} text cells)")


if __name__ == "__main__":
    main()
