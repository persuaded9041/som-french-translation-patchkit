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
# Keep the resource below the shared VWF width-table allocation at C7:4440.
MENU_RESOURCE_RELOC_LIMIT = 0x074440
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
WELCOME_RELOC_LIMIT = 0x2D8400          # stop before GAME FILE save help

# GAME FILE / save-menu text uses two stock runtime paths.  The full resource
# is relocated so FILE_LABEL can grow from the 4-cell stock "FILE" to the
# the translated 7-cell FILE label, but several labels are still consumed directly
# from C7:7340 by another path.  Keep both copies synchronized.
GAME_FILE_STOCK_RESOURCE_OFFSET = 0x077340
GAME_FILE_STOCK_RESOURCE_END = 0x0773BC      # next resource begins at C7:73BC
GAME_FILE_STOCK_RESOURCE_PTR = 0x7340
GAME_FILE_RELOC_OFFSET = 0x074D40             # C7:4D40, stock $FF free space
GAME_FILE_RELOC_PTR = 0x4D40
GAME_FILE_POINTER_OFFSETS = (0x077810, 0x077816)
# FILE label frame descriptor: stock width $03 = 6 cells. The translated label needs
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

# GAME FILE money total uses a hybrid 16-cell dynamic/static layout. The
# dynamic renderer always uploads columns 0..15; column 16 remains the second
# glyph from the C7:7394 resource template. Stock lays out 8 leading blanks +
# 7 amount cells + the first currency glyph. French keeps the currency anchor
# unchanged but needs one separator cell, so it uses 7 leading blanks + 7
# amount cells + an explicit blank + the first currency glyph. The tiny helper
# below preserves the mandatory 16-cell dynamic span.
GAME_FILE_MONEY_LEADING_BLANKS_OFFSET = 0x07549A  # LDY #$0008 at C7:549A
GAME_FILE_MONEY_LEADING_BLANKS_STOCK = bytes.fromhex("a0 08 00")
GAME_FILE_MONEY_LEADING_BLANKS_FRENCH = bytes.fromhex("a0 07 00")
GAME_FILE_MONEY_FORMAT_CALL_OFFSET = 0x0754A6     # JSR $54B0
GAME_FILE_MONEY_FORMAT_CALL_STOCK = bytes.fromhex("20 b0 54")
GAME_FILE_MONEY_SPACING_HELPER_OFFSET = 0x074D32  # C7:4D32
GAME_FILE_MONEY_SPACING_HELPER_PTR = 0x4D32
GAME_FILE_MONEY_SPACING_HELPER_LIMIT = 0x074D3C   # 10-byte helper; 4D3C-4D3F stay free
GAME_FILE_MONEY_PREFIX_GLYPH_OFFSET = 0x0754AA     # operand of LDA #$A1 at C7:54A9
GAME_FILE_MONEY_PREFIX_GLYPH_STOCK = 0xA1          # G

# Field offsets inside C7:7340.  These capacities include adjacent stock
# padding cells that were runtime-validated for the French labels.  The same
# fields are written both into the relocated resource and back into the stock
# resource because GAME FILE uses both paths at runtime.
GAME_FILE_RESOURCE_FIELDS = {
    "FILE_SELECT": (0x077341, 7),
    "SAVE_POINT":  (0x077350, 11),
    "MONEY":       (0x077374, 6),
    "GP":          (0x077394, 2),
    # COUNTER begins at row column 1 and its dynamic value is at column 16,
    # leaving 15 safe fixed cells for the translated label.
    "COUNTER":     (0x077398, 15),
    "MANA_POWER":  (0x0773AA, 15),
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
SAVE_HELP_RELOC_LIMIT = 0x2D8500         # stop before Action Settings help

# Action Settings top-help block. Keep it on the stock fixed renderer and
# relocate the complete three-row block so translated row lengths may change
# without shifting unrelated C0 resources. The third row (0..8 gauge scale)
# remains the canonical USA source text.
ACTION_HELP_POINTER_OFFSET = 0x0033C1      # stock pointer = C0:3620
ACTION_HELP_POINTER_STOCK = 0xC03620
ACTION_HELP_RELOC_OFFSET = 0x2D8500        # SNES ED:8500
ACTION_HELP_RELOC_SNES = 0xED8500
ACTION_HELP_RELOC_LIMIT = 0x2D8600

# Action Settings uses a compact four-slot C7 text resource.  The official
# French SNES localization proves that these slots may be repacked and their
# placement descriptors resized independently.  Our longer labels need 39
# bytes including the terminator, so relocate them into the remaining clean
# $FF gap immediately after the GAME FILE allocation.
ACTION_RESOURCE_RELOC_OFFSET = 0x074DC0       # C7:4DC0
ACTION_RESOURCE_RELOC_PTR = 0x4DC0
ACTION_RESOURCE_RELOC_LIMIT = 0x074E00        # before Name Entry private layout
# The compact Action Settings resource and its placement list are relocated
# together in C7:4DC0-4DFF.  The shared-fragment layout below is 35 bytes
# including the terminator and its six-span placement list is 26 bytes.
ACTION_PLACEMENT_RELOC_OFFSET = 0x074DE3
ACTION_PLACEMENT_RELOC_PTR = 0x4DE3
ACTION_DESCRIPTOR_TEXT_PTR_OFFSET = 0x077822  # menu descriptor #4, stock $73DF
ACTION_DESCRIPTOR_PLACEMENT_PTR_OFFSET = 0x077826
ACTION_DESCRIPTOR_PLACEMENT_PTR_STOCK = 0x7538
ACTION_DESCRIPTOR_TEXT_PTR_STOCK = 0x73DF
ACTION_PLACEMENT_OFFSET = 0x077538            # four 4-byte text spans + $03,$00
ACTION_PLACEMENT_STOCK = bytes.fromhex(
    "00 04 50 82 03 05 60 D6 05 04 74 56 01 03 84 AC 03 00"
)
# First frame record in C7:7606. Keep its stock width exactly: the official
# French Rev 1 ROM uses the same $18 geometry, and widening it to $19 was
# runtime-observed to pollute the adjacent right-hand window.
ACTION_LEFT_FRAME_WIDTH_OFFSET = 0x07760A
ACTION_LEFT_FRAME_WIDTH_STOCK = 0x18
# The 34-cell localized Action Settings resource consumes one additional
# fixed-font source unit compared with the 32-cell USA resource.  The dynamic
# gauge value shown between the blue brackets consequently moves by one tile
# unit (+$04).  The official French Rev 1 ROM makes the same compensation in
# the corresponding routine ($2180 -> $2184).
ACTION_GAUGE_TILE_BASE_OFFSET = 0x076C78  # low byte of LDA #$2180 at C7:6C77
ACTION_GAUGE_TILE_BASE_STOCK = bytes.fromhex("80 21")
ACTION_GAUGE_TILE_BASE_FRENCH = bytes.fromhex("84 21")
# The same extra fixed-font unit also shifts the two source-tile bases used
# when the top Action Settings help line is redrawn.  The official French
# Rev 1 ROM applies the exact same +$04 compensation:
#   C7:6D57  LDX #$2090 -> #$2094
#   C7:6D5C  LDX #$2108 -> #$210C
# Without it, runtime tests show a one-tile displacement on the KEEP GAUGE
# prompt and a trailing translated GUARD fragment prefixed to the stock prompt...
ACTION_HELP_TILE_BASE_1_OFFSET = 0x076D58  # immediate word after LDX at C7:6D57
ACTION_HELP_TILE_BASE_1_STOCK = bytes.fromhex("90 20")
ACTION_HELP_TILE_BASE_1_FRENCH = bytes.fromhex("94 20")
ACTION_HELP_TILE_BASE_2_OFFSET = 0x076D5D  # immediate word after LDX at C7:6D5C
ACTION_HELP_TILE_BASE_2_STOCK = bytes.fromhex("08 21")
ACTION_HELP_TILE_BASE_2_FRENCH = bytes.fromhex("0C 21")


ASCII_TO_SOM = {" ": 0x80}
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
from shared.charset import BASIC_FRENCH_CHARS, glyph_bytes, profile_mapping, profile_threshold
from shared.core.rom import validate_base_rom, update_checksum, expand_rom, ROM_SIZE_OFFSET
from shared.core.ips import make_ips
from shared.text.interface import (
    load_document as load_interface_text,
    verify_against_rom as verify_interface_text,
    group_entries as interface_group_entries,
)
from shared.text.menu import (
    load_document as load_menu_text,
    verify_against_rom as verify_menu_text,
)
from shared.text.translation_json import load_translation, require
from shared.extracted.assets import load_or_extract_interface, load_or_extract_menu  # noqa: E402

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
        if ch == "“":
            if not quote_open:
                raise SystemExit(f"Unexpected opening quote in {context} at position {pos}")
            out.append(0xC3)
            quote_open = False
            continue
        if ch == "”":
            if quote_open:
                raise SystemExit(f"Unexpected closing quote in {context} at position {pos}")
            out.append(0xC4)
            quote_open = True
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
ACTION_SETTINGS_IDS = {
    "ATTACK": "C7:73E0",
    "KEEP_AWAY": "C7:73E7",
    "APPROACH": "C7:73F1",
    "GUARD": "C7:73F9",
}
ACTION_HELP_IDS = {
    "HELP_1": "C0:3620",
    "HELP_2": "C0:3654",
    "GAUGE_SCALE": "C0:368F",
}


def load_french_rows(base: bytes) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    interface = load_or_extract_interface(base, PROJECT_ROOT / "assets" / "interface_text.json")
    menu = load_or_extract_menu(base, PROJECT_ROOT / "assets" / "menu_text.json")
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
        action_rows = {
            name: require(menu_fr, [text_id], context="Action Settings")[0]
            for name, text_id in ACTION_SETTINGS_IDS.items()
        }
        action_help_rows = {
            "HELP_1": require(interface_fr, [ACTION_HELP_IDS["HELP_1"]], context="Action Settings help")[0],
            "HELP_2": require(interface_fr, [ACTION_HELP_IDS["HELP_2"]], context="Action Settings help")[0],
        }
        canonical_action_help = {
            entry["id"]: entry["source"]
            for entry in interface_group_entries(interface, "action_settings.help")
        }
        action_help_rows["GAUGE_SCALE"] = canonical_action_help[ACTION_HELP_IDS["GAUGE_SCALE"]]
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    return rows, game_file_rows, action_rows, action_help_rows


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


def build_game_file_money_spacing_helper() -> bytes:
    """Return the runtime-validated GAME FILE money-spacing helper.

    65C816 at $C7:4D32:
      JSR $54B0       ; write the seven formatted amount cells
      LDA #$80        ; fixed-font blank
      STA $9C00,X     ; separator in dynamic column 14
      INX             ; preserve 16-cell dynamic span; caller writes currency[0]
      RTS

    The following stock code at $C7:54A9 still writes currency[0] from the
    JSON-backed C7:7394 field, and column 16 remains currency[1] from the
    static template. No localized prose is embedded here.
    """
    return bytes.fromhex("20 b0 54 a9 80 9d 00 9c e8 60")


def apply_game_file_sources(base: bytes, rom: bytearray, rows: dict[str, str]) -> None:
    resource = build_game_file_resource(base, rows)
    reloc_end = GAME_FILE_RELOC_OFFSET + len(resource)
    # Stop before the standalone 9-char names allocation at C7:4E00.
    if reloc_end > 0x074E00:
        raise SystemExit("Relocated GAME FILE resource exceeded C7:4D40-C7:4DFF")
    if any(b != 0xFF for b in base[GAME_FILE_RELOC_OFFSET:reloc_end]):
        raise SystemExit("GAME FILE relocation target C7:4D40 is not stock $FF free space")
    rom[GAME_FILE_RELOC_OFFSET:reloc_end] = resource

    # Runtime-validated money spacing. The native renderer DMA always rewrites
    # exactly 16 dynamic character cells (columns 0..15). Merely reducing the
    # leading blank count makes the dynamic string 15 cells long and the
    # renderer clears column 15, producing `P O`. Keep the 16-cell span by
    # moving the amount left one cell and inserting an explicit separator at
    # dynamic column 14 before the existing JSON-derived currency[0] write.
    helper = build_game_file_money_spacing_helper()
    if GAME_FILE_MONEY_SPACING_HELPER_OFFSET + len(helper) > GAME_FILE_MONEY_SPACING_HELPER_LIMIT:
        raise SystemExit("GAME FILE money-spacing helper exceeds C7:4D32-C7:4D3B")
    if any(b != 0xFF for b in base[GAME_FILE_MONEY_SPACING_HELPER_OFFSET:GAME_FILE_MONEY_SPACING_HELPER_OFFSET + len(helper)]):
        raise SystemExit("Expected free space for GAME FILE money-spacing helper is not empty")
    if base[GAME_FILE_MONEY_LEADING_BLANKS_OFFSET:GAME_FILE_MONEY_LEADING_BLANKS_OFFSET + 3] != GAME_FILE_MONEY_LEADING_BLANKS_STOCK:
        raise SystemExit("Unexpected stock GAME FILE money leading-blank setup at C7:549A")
    if base[GAME_FILE_MONEY_FORMAT_CALL_OFFSET:GAME_FILE_MONEY_FORMAT_CALL_OFFSET + 3] != GAME_FILE_MONEY_FORMAT_CALL_STOCK:
        raise SystemExit("Unexpected stock GAME FILE money formatter call at C7:54A6")
    rom[GAME_FILE_MONEY_SPACING_HELPER_OFFSET:GAME_FILE_MONEY_SPACING_HELPER_OFFSET + len(helper)] = helper
    rom[GAME_FILE_MONEY_LEADING_BLANKS_OFFSET:GAME_FILE_MONEY_LEADING_BLANKS_OFFSET + 3] = GAME_FILE_MONEY_LEADING_BLANKS_FRENCH
    rom[GAME_FILE_MONEY_FORMAT_CALL_OFFSET:GAME_FILE_MONEY_FORMAT_CALL_OFFSET + 3] = bytes((0x20, GAME_FILE_MONEY_SPACING_HELPER_PTR & 0xFF, GAME_FILE_MONEY_SPACING_HELPER_PTR >> 8))

    # Expand the small FILE frame from 6 to 8 text cells. The menu descriptor
    # uses the same two-cells-per-width-unit convention as GAME SELECT.
    if base[GAME_FILE_FILE_FRAME_WIDTH_OFFSET] != GAME_FILE_FILE_FRAME_STOCK_WIDTH:
        raise SystemExit(
            f"Unexpected stock FILE frame width at ${GAME_FILE_FILE_FRAME_WIDTH_OFFSET:06X}: "
            f"${base[GAME_FILE_FILE_FRAME_WIDTH_OFFSET]:02X}"
        )
    rom[GAME_FILE_FILE_FRAME_WIDTH_OFFSET] = GAME_FILE_FILE_FRAME_NEW_WIDTH

    # The GAME FILE total-money renderer hard-codes the first glyph of the
    # stock "GP" suffix as an immediate "G" at C7:54A9. The second glyph
    # remains the static template cell at column 16. Keep this stock hybrid path
    # synchronized by deriving the immediate from the first encoded cell of the
    # same JSON translation used for C7:7394.
    if base[GAME_FILE_MONEY_PREFIX_GLYPH_OFFSET] != GAME_FILE_MONEY_PREFIX_GLYPH_STOCK:
        raise SystemExit(
            f"Unexpected stock GAME FILE money-prefix glyph at ${GAME_FILE_MONEY_PREFIX_GLYPH_OFFSET:06X}: "
            f"${base[GAME_FILE_MONEY_PREFIX_GLYPH_OFFSET]:02X}"
        )
    money_unit = encode_text(rows["GP"], "GP")
    if len(money_unit) != 2:
        raise SystemExit("GP/currency translation must remain exactly two encoded cells")
    rom[GAME_FILE_MONEY_PREFIX_GLYPH_OFFSET] = money_unit[0]

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


def build_action_settings_resource(rows: dict[str, str]) -> tuple[bytes, bytes]:
    """Build the native fixed-font Action Settings resource in 34 cells.

    The official French Rev 1 ROM proves that this screen safely supports a
    34-cell C7 text resource.  The four approved labels need 38 cells if packed
    independently, which shifts the following help-text tile allocation and
    exposes stale glyphs in the adjacent right-hand panel.

    Keep the resource at the proven 34-cell size by reusing two 2-cell overlaps
    already present in the translation data.  The overlap requirements are
    checked from the JSON payload at build time rather than hard-coding French
    prose in this executable source:

    * the last two cells of KEEP_AWAY must equal the last two cells of ATTACK;
    * the first two cells of APPROACH must equal the first two cells of KEEP_AWAY.

    Resource layout (34 cells, plus terminator):
      ATTACK | KEEP_AWAY[:-2] | APPROACH[2:] + pad | GUARD

    Placement format, as proven directly by C0:23CF-$2434, is:
      $00 prefix,
      repeated [width_units, source_tile, destination_lo, destination_hi],
      $00 terminator.

    One width unit represents two fixed-font source cells.  Source tiles
    advance by four per unit; destinations advance by two bytes per unit.
    """
    encoded = {key: encode_text(rows[key], f"ACTION_{key}") for key in (
        "ATTACK", "KEEP_AWAY", "APPROACH", "GUARD"
    )}
    expected_lengths = {"ATTACK": 8, "KEEP_AWAY": 10, "APPROACH": 11, "GUARD": 8}
    for key, expected_length in expected_lengths.items():
        if len(encoded[key]) != expected_length:
            raise SystemExit(
                f"Action Settings 34-cell layout expects {key} to encode to "
                f"{expected_length} cells; got {len(encoded[key])}"
            )

    shared_suffix = encoded["ATTACK"][-2:]
    if encoded["KEEP_AWAY"][-2:] != shared_suffix:
        raise SystemExit(
            "Action Settings 34-cell layout requires KEEP_AWAY[-2:] == ATTACK[-2:]"
        )
    shared_prefix = encoded["KEEP_AWAY"][:2]
    if encoded["APPROACH"][:2] != shared_prefix:
        raise SystemExit(
            "Action Settings 34-cell layout requires APPROACH[:2] == KEEP_AWAY[:2]"
        )

    attack = encoded["ATTACK"]
    keep_stem = encoded["KEEP_AWAY"][:-2]
    approach_tail = encoded["APPROACH"][2:]
    if len(approach_tail) & 1:
        approach_tail += bytes((ASCII_TO_SOM[" "],))
    guard = encoded["GUARD"]

    fragments = (attack, keep_stem, approach_tail, guard)
    if any(len(fragment) & 1 for fragment in fragments):
        raise SystemExit("Action Settings packed fragments must have even cell counts")
    resource = b"".join(fragments)
    if len(resource) != 34:
        raise SystemExit(f"Action Settings resource must be 34 cells, got {len(resource)}")
    resource += b"\x00"

    attack_start = 0
    keep_start = len(attack)
    approach_start = keep_start + len(keep_stem)
    guard_start = approach_start + len(approach_tail)

    def source_tile(source_cell: int) -> int:
        if source_cell & 1:
            raise SystemExit("Action Settings source fragments must start on even cells")
        return 0x50 + (source_cell // 2) * 4

    # Native destinations from the clean-USA placement table:
    #   ATTACK    $0382
    #   KEEP AWAY $05D6
    #   APPROACH  $0156
    #   GUARD     $03AC
    # Appended fragments advance one tilemap entry (2 bytes) for every
    # two-character source unit.  GUARD is intentionally one fixed-font cell
    # (8 px) left of stock so its 8-cell translation fits without widening the
    # left frame.
    spans = (
        (len(attack) // 2, attack_start, 0x0382),
        (len(keep_stem) // 2, keep_start, 0x05D6),
        (1, len(attack) - 2, 0x05DE),
        (1, keep_start, 0x0156),
        (len(approach_tail) // 2, approach_start, 0x0158),
        (len(guard) // 2, guard_start, 0x03AA),
    )
    placement = bytearray((0x00,))
    for width_units, source_cell, destination in spans:
        placement.extend((
            width_units,
            source_tile(source_cell),
            destination & 0xFF,
            (destination >> 8) & 0xFF,
        ))
    placement.append(0x00)
    return resource, bytes(placement)


def build_action_help(rows: dict[str, str]) -> bytes:
    encoded: list[bytes] = []
    for key in ("HELP_1", "HELP_2"):
        payload = encode_text(rows[key], f"Action Settings {key}")
        if len(payload) > 58:
            raise SystemExit(
                f"Action Settings {key} encodes to {len(payload)} cells; fixed help renderer supports at most 58"
            )
        encoded.append(payload)
    gauge = encode_text(rows["GAUGE_SCALE"], "Action Settings GAUGE_SCALE")
    encoded.append(gauge)
    return b"\x7f".join(encoded) + b"\x00"


def apply_action_help(base: bytes, rom: bytearray, rows: dict[str, str]) -> None:
    if int.from_bytes(base[ACTION_HELP_POINTER_OFFSET:ACTION_HELP_POINTER_OFFSET + 3], "little") != ACTION_HELP_POINTER_STOCK:
        raise SystemExit("Unexpected clean-USA Action Settings help pointer")
    payload = build_action_help(rows)
    end = ACTION_HELP_RELOC_OFFSET + len(payload)
    if end > ACTION_HELP_RELOC_LIMIT:
        raise SystemExit("Action Settings help exceeded reserved ED:8500-ED:85FF region")
    if any(b != 0x00 for b in rom[ACTION_HELP_RELOC_OFFSET:end]):
        raise SystemExit("Action Settings help relocation target ED:8500-ED:85FF is not clean expanded-ROM space")
    rom[ACTION_HELP_RELOC_OFFSET:end] = payload
    rom[ACTION_HELP_POINTER_OFFSET:ACTION_HELP_POINTER_OFFSET + 3] = ACTION_HELP_RELOC_SNES.to_bytes(3, "little")


def apply_action_settings(base: bytes, rom: bytearray, rows: dict[str, str]) -> None:
    if int.from_bytes(base[ACTION_DESCRIPTOR_TEXT_PTR_OFFSET:ACTION_DESCRIPTOR_TEXT_PTR_OFFSET + 2], "little") != ACTION_DESCRIPTOR_TEXT_PTR_STOCK:
        raise SystemExit("Unexpected clean-USA Action Settings text pointer")
    if base[ACTION_PLACEMENT_OFFSET:ACTION_PLACEMENT_OFFSET + len(ACTION_PLACEMENT_STOCK)] != ACTION_PLACEMENT_STOCK:
        raise SystemExit("Unexpected clean-USA Action Settings placement table")
    if int.from_bytes(base[ACTION_DESCRIPTOR_PLACEMENT_PTR_OFFSET:ACTION_DESCRIPTOR_PLACEMENT_PTR_OFFSET + 2], "little") != ACTION_DESCRIPTOR_PLACEMENT_PTR_STOCK:
        raise SystemExit("Unexpected clean-USA Action Settings placement pointer")
    if base[ACTION_LEFT_FRAME_WIDTH_OFFSET] != ACTION_LEFT_FRAME_WIDTH_STOCK:
        raise SystemExit("Unexpected clean-USA Action Settings left-frame width")
    if base[ACTION_GAUGE_TILE_BASE_OFFSET:ACTION_GAUGE_TILE_BASE_OFFSET + 2] != ACTION_GAUGE_TILE_BASE_STOCK:
        raise SystemExit("Unexpected clean-USA Action Settings gauge tile base")
    if base[ACTION_HELP_TILE_BASE_1_OFFSET:ACTION_HELP_TILE_BASE_1_OFFSET + 2] != ACTION_HELP_TILE_BASE_1_STOCK:
        raise SystemExit("Unexpected clean-USA Action Settings help tile base #1")
    if base[ACTION_HELP_TILE_BASE_2_OFFSET:ACTION_HELP_TILE_BASE_2_OFFSET + 2] != ACTION_HELP_TILE_BASE_2_STOCK:
        raise SystemExit("Unexpected clean-USA Action Settings help tile base #2")

    resource, placement = build_action_settings_resource(rows)
    resource_end = ACTION_RESOURCE_RELOC_OFFSET + len(resource)
    placement_end = ACTION_PLACEMENT_RELOC_OFFSET + len(placement)
    if resource_end > ACTION_PLACEMENT_RELOC_OFFSET or placement_end > ACTION_RESOURCE_RELOC_LIMIT:
        raise SystemExit("Action Settings resource/placement exceeded C7:4DC0-C7:4DFF")
    if any(b != 0xFF for b in base[ACTION_RESOURCE_RELOC_OFFSET:placement_end]):
        raise SystemExit("Action Settings relocation target C7:4DC0-C7:4DFF is not stock $FF free space")

    rom[ACTION_RESOURCE_RELOC_OFFSET:resource_end] = resource
    rom[ACTION_PLACEMENT_RELOC_OFFSET:placement_end] = placement
    rom[ACTION_DESCRIPTOR_TEXT_PTR_OFFSET:ACTION_DESCRIPTOR_TEXT_PTR_OFFSET + 2] = ACTION_RESOURCE_RELOC_PTR.to_bytes(2, "little")
    rom[ACTION_DESCRIPTOR_PLACEMENT_PTR_OFFSET:ACTION_DESCRIPTOR_PLACEMENT_PTR_OFFSET + 2] = ACTION_PLACEMENT_RELOC_PTR.to_bytes(2, "little")
    # Keep the stock left-frame width. Runtime tests showed that widening this
    # frame disturbs the dynamic value displayed in the adjacent right panel.
    # The GUARD label instead starts one fixed-font cell (8 px) farther left in
    # the placement table, which provides the missing room without touching either
    # window's geometry.
    rom[ACTION_LEFT_FRAME_WIDTH_OFFSET] = ACTION_LEFT_FRAME_WIDTH_STOCK
    # Keep the dynamic gauge value aligned with the extra fixed-font unit in
    # the 34-cell localized resource.  This mirrors the official French Rev 1
    # localization and prevents the blue brackets from selecting the leading
    # blank tile instead of the digit.
    rom[ACTION_GAUGE_TILE_BASE_OFFSET:ACTION_GAUGE_TILE_BASE_OFFSET + 2] = ACTION_GAUGE_TILE_BASE_FRENCH
    # Keep both top-help redraw paths on the same shifted source-tile base.
    # This mirrors French Rev 1 and prevents stale/blank tiles from preceding
    # either Action Settings prompt after selecting the grid or cancelling Y.
    rom[ACTION_HELP_TILE_BASE_1_OFFSET:ACTION_HELP_TILE_BASE_1_OFFSET + 2] = ACTION_HELP_TILE_BASE_1_FRENCH
    rom[ACTION_HELP_TILE_BASE_2_OFFSET:ACTION_HELP_TILE_BASE_2_OFFSET + 2] = ACTION_HELP_TILE_BASE_2_FRENCH


def apply_sources(base: bytes, rows: dict[str, str], game_file_rows: dict[str, str], action_rows: dict[str, str], action_help_rows: dict[str, str]) -> tuple[bytearray, int]:
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
    # editable 8x12 glyph atlas in shared/charset/french_glyphs.png.
    glyph_start = FONT_BASE + (ACCENT_FIRST - 0x80) * GLYPH_HEIGHT
    glyph_blob = load_accent_glyphs()
    rom[glyph_start:glyph_start + len(glyph_blob)] = glyph_blob

    # Relocate the label resource and derive all three frame widths directly
    # from the translated text so field segmentation and window geometry stay aligned.
    menu_resource, frame_widths = build_menu_resource(rows)
    if MENU_RESOURCE_RELOC_OFFSET + len(menu_resource) > MENU_RESOURCE_RELOC_LIMIT:
        raise SystemExit("Relocated GAME SELECT resource exceeded reserved C7:4400-C7:443F")
    rom[MENU_RESOURCE_RELOC_OFFSET:MENU_RESOURCE_RELOC_OFFSET + len(menu_resource)] = menu_resource
    rom[MENU_DESCRIPTOR_TEXT_PTR_OFFSET:MENU_DESCRIPTOR_TEXT_PTR_OFFSET + 2] = MENU_RESOURCE_RELOC_PTR.to_bytes(2, "little")

    for key, offset in FRAME_WIDTH_OFFSETS.items():
        if base[offset] != STOCK_FRAME_WIDTHS[key]:
            raise SystemExit(
                f"Unexpected stock {key} frame width at ${offset:06X}: ${base[offset]:02X}"
            )
        rom[offset] = frame_widths[key]

    # GAME FILE/save-menu strings share this decoder/font.  The full resource
    # is relocated for the expanded FILE label, while the stock label fields are mirrored in
    # place for the second runtime path.  Save help is relocated separately.
    apply_game_file_sources(base, rom, game_file_rows)

    # Action Settings: keep every frame and the 4x4 grid byte-for-byte stock.
    # Only repack/relocate the four translated fixed-width labels.
    apply_action_settings(base, rom, action_rows)
    apply_action_help(base, rom, action_help_rows)

    # Relocate the long help text now, so its translation will no longer be
    # constrained by the 156-byte stock allocation at C0:33F0.
    welcome = build_welcome(rows)
    if WELCOME_RELOC_OFFSET + len(welcome) > WELCOME_RELOC_LIMIT:
        raise SystemExit("WELCOME text exceeded the reserved ED:8000-ED:83FF region")
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

    rows, game_file_rows, action_rows, action_help_rows = load_french_rows(base)
    patched, checksum = apply_sources(base, rows, game_file_rows, action_rows, action_help_rows)
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
    print(f"GAME FILE money spacing: {len(build_game_file_money_spacing_helper())}-byte helper at C7:${GAME_FILE_MONEY_SPACING_HELPER_PTR:04X}; 7 amount-prefix blanks + separator")
    print(f"GAME FILE save-help pointer: ${int.from_bytes(patched[SAVE_HELP_POINTER_OFFSET:SAVE_HELP_POINTER_OFFSET+3], 'little'):06X}")
    print(f"GAME FILE save-help payload: {len(build_save_help(game_file_rows))} bytes at ROM ${SAVE_HELP_RELOC_OFFSET:06X}")
    action_resource, action_placement = build_action_settings_resource(action_rows)
    print(f"ACTION SETTINGS resource: {len(action_resource)} bytes at C7:${ACTION_RESOURCE_RELOC_PTR:04X}")
    print(f"ACTION SETTINGS placement: {len(action_placement)} bytes at C7:${ACTION_PLACEMENT_RELOC_PTR:04X}; stock frame width $18, GUARD -8 px")
    print(f"ACTION SETTINGS help: {len(build_action_help(action_help_rows))} bytes at SNES ${ACTION_HELP_RELOC_SNES:06X}")
    menu_resource, widths = build_menu_resource(rows)
    print(f"GAME SELECT resource: {len(menu_resource)} bytes at C7:${MENU_RESOURCE_RELOC_PTR:04X}")
    print("GAME SELECT layout: native 45-byte resource; no additional DTE compression")
    for key in ("GAME_SELECT", "NEW_GAME", "GAME_FILE"):
        print(f"{key} frame width: ${widths[key]:02X} ({widths[key] * 2} text cells)")


if __name__ == "__main__":
    main()
