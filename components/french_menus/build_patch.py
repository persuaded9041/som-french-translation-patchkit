#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
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

# Window Settings stays entirely on the stock fixed-font renderer.  The
# translated title and axis legend need a larger pair-aligned source resource,
# so relocate the native C7 text resource and placement list together.  The
# frame width, source cursor and resource length are deliberately kept in sync;
# changing only one of them was runtime-proven to corrupt the following help.
WINDOW_HELP_POINTER_OFFSET = 0x0033BB      # stock pointer = C0:34F9
WINDOW_HELP_POINTER_STOCK = 0xC034F9
WINDOW_HELP_RELOC_OFFSET = 0x2D8600        # SNES ED:8600
WINDOW_HELP_RELOC_SNES = 0xED8600
WINDOW_HELP_RELOC_LIMIT = 0x2D8700

WINDOW_RESOURCE_STOCK_OFFSET = 0x0773BC    # starts `X Y A B R G  ...`
WINDOW_RESOURCE_PREFIX_CELLS = 13          # control legend + two source blanks
WINDOW_RESOURCE_PREFIX_STOCK = bytes.fromhex(
    "b2 80 b3 80 9b 80 9c 80 ac 80 a1 80 80"
)
WINDOW_RESOURCE_RELOC_OFFSET = 0x074700     # C7:4700, clean-USA $FF gap
WINDOW_RESOURCE_RELOC_PTR = 0x4700
WINDOW_RESOURCE_RELOC_LIMIT = 0x07472F      # current resource ends at C7:472E
WINDOW_PLACEMENT_RELOC_OFFSET = 0x074730    # C7:4730
WINDOW_PLACEMENT_RELOC_PTR = 0x4730
WINDOW_PLACEMENT_RELOC_LIMIT = 0x07475A     # current table ends at C7:4759
WINDOW_DESCRIPTOR_TEXT_PTR_OFFSET = 0x077828
WINDOW_DESCRIPTOR_TEXT_PTR_STOCK = 0x73BC
WINDOW_DESCRIPTOR_PLACEMENT_PTR_OFFSET = 0x07782C
WINDOW_DESCRIPTOR_PLACEMENT_PTR_STOCK = 0x7506
WINDOW_FRAME_WIDTH_OFFSET = 0x0775CA
WINDOW_FRAME_WIDTH_STOCK = 0x07              # 14 cells
WINDOW_FRAME_WIDTH_FRENCH = 0x09             # 18 cells

# Keep the original C7:73C9/C7:73D1 shadow fields French as well.  The primary
# rendered title is the relocated JSON-backed title; the compact fallback is
# intentionally separate JSON data so no localized prose lives in Python.
WINDOW_SELECT_OFFSET = 0x0773C9
WINDOW_SELECT_CAPACITY = 7
WINDOW_SELECT_STOCK = bytes.fromhex("ad 9f a6 9f 9d ae 80")  # `SELECT `
WINDOW_TITLE_FIXED_OFFSET = 0x0773D1
WINDOW_TITLE_FIXED_CAPACITY = 13
WINDOW_TITLE_FIXED_STOCK = bytes.fromhex(
    "b1 a3 a8 9e a9 b1 80 80 9f 9e a3 ae 80"  # `WINDOW  EDIT `
)

# Native six one-unit colour-button placements, converted to the span format
# already used by GAME SELECT.  Added axis labels reuse the same native format.
WINDOW_CONTROL_PLACEMENTS = (
    (1, 0x58, 0x00E2),
    (1, 0x60, 0x00E8),
    (1, 0x54, 0x0162),
    (1, 0x64, 0x0168),
    (1, 0x50, 0x01E2),
    (1, 0x5C, 0x01E8),
)
WINDOW_HORIZONTAL_DESTINATIONS = (0x0348, 0x0358)
WINDOW_VERTICAL_DESTINATIONS = (0x0290, 0x0410)
WINDOW_AXIS_SLOT_CELLS = 8
WINDOW_TITLE_SLOT_CELLS = 17                 # 16-char title + one trailing cell

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


# Weapon / magic skill-menu headings. These are fixed-width native segments
# inside the two stock C7 resources. Keep every segment at its original length
# and pad shorter localized labels with stock blank cells so no descriptor,
# placement or following resource moves.
SKILL_MENU_RANGES = {
    "C7:745E": (0x07745E, 12),  # WEAPON SKILL
    "C7:7478": (0x077478, 11),  # MAGIC SKILL
    "C7:7486": (0x077486, 12),  # MAGIC  SKILL
    "C7:749F": (0x07749F, 12),  # WEAPON SKILL
}

# Status / Characteristics screen. Keep the stock fixed-font renderer and all
# stock geometry. The two characteristic-label rows remain exactly 60/40
# decoded cells; the status-condition pool is repacked inside its original C7
# allocation and only its 16 local pointers are updated. No VWF is involved.
STATUS_LABELS_POINTER_OFFSET = 0x0033CD          # stock 24-bit pointer C7:7A28
STATUS_LABELS_POINTER_STOCK = 0xC77A28
STATUS_LABELS_OFFSET = 0x077A28
STATUS_LABELS_ROW1_CELLS = 60
STATUS_LABELS_ROW2_CELLS = 40
STATUS_LABELS_BLOCK_END = 0x077A8E              # condition pool starts here

# Clean USA completes the two 12-letter labels CONSTITUTION / INTELLIGENCE
# outside the 10-cell text resource.  The status renderer writes literal
# pairs "ON" and "CE" into the tilemap when processing slots 2 and 3.
# French Rev 1 keeps the exact same branches but changes both immediate words
# to two spaces.  Mirror that localized behavior so translated 10-cell labels
# do not inherit the USA suffixes.
STATUS_SUFFIX_CONSTITUTION_OFFSET = 0x076764  # operands of LDA #$A8A9 at C7:6763
STATUS_SUFFIX_INTELLIGENCE_OFFSET = 0x076771  # operands of LDA #$9F9D at C7:6770
STATUS_SUFFIX_CONSTITUTION_STOCK = bytes.fromhex("A9 A8")  # "ON" in text-byte order
STATUS_SUFFIX_INTELLIGENCE_STOCK = bytes.fromhex("9D 9F")  # "CE" in text-byte order
STATUS_SUFFIX_BLANK = bytes.fromhex("80 80")
STATUS_LABEL_ROW1_PLACEMENTS = (
    ("STRENGTH", 0),
    ("AGILITY", 10),
    ("CONSTITUTION", 20),
    ("INTELLIGENCE", 30),
    ("WISDOM", 40),
    ("ATTACK", 50),
)
STATUS_LABEL_ROW2_PLACEMENTS = (
    ("HIT_PERCENT", 0),
    ("DEFENSE", 10),
    ("EVADE_PERCENT", 20),
    ("MAGIC_DEFENSE", 30),
)

STATUS_CONDITION_POINTER_TABLE_OFFSET = 0x0033D0
STATUS_CONDITION_POOL_OFFSET = 0x077A8E
STATUS_CONDITION_POOL_END = 0x077B24
STATUS_CONDITION_IDS = (
    "C7:7A8E", "C7:7A9A", "C7:7AA3", "C7:7AAC",
    "C7:7AB5", "C7:7AC1", "C7:7ACB", "C7:7AD2",
    "C7:7ADC", "C7:7AE2", "C7:7AEC", "C7:7AF3",
    "C7:7AFC", "C7:7B07", "C7:7B13", "C7:7B1B",
)

# Most templates keep their stock start addresses. EXP / NEXT LEVEL are the
# one deliberate exception: their two adjacent stock records C7:7B39-$7B52
# form one 26-byte region. The reviewed full French strings fit that region
# exactly when repacked back-to-back, so we keep the stock fixed-font renderer
# and patch only the local LDY immediate that selects the second record.
STATUS_TEMPLATE_RANGES = {
    "C7:7B24": (0x077B24, 0x077B2D),
    "C7:7B2D": (0x077B2D, 0x077B33),
    "C7:7B33": (0x077B33, 0x077B39),
    "C7:7B53": (0x077B53, 0x077B61),
    "C7:7B61": (0x077B61, 0x077B6A),
}
STATUS_EXP_NEXT_REGION_START = 0x077B39
STATUS_EXP_NEXT_REGION_END = 0x077B53
STATUS_NEXT_LEVEL_POINTER_OPERAND_OFFSET = 0x076963  # LDY #$7B41 at C7:6962
STATUS_NEXT_LEVEL_POINTER_STOCK = bytes.fromhex("41 7B")

# Status money line: the translated ``Argent {5C12}`` record compresses to
# eight bytes including its terminator, leaving the final stock byte at
# C7:7B69 available as presentation-only padding immediately before the
# localized unit literal at C7:7B6A. Point the unit submit one byte earlier so
# the stock parser emits one fixed-font blank, then continues into GP/PO.
# french_menus owns only this separator/pointer; french_resources remains the
# sole owner of the actual ``GP -> PO`` content at C7:7B6A.
STATUS_MONEY_SEPARATOR_OFFSET = 0x077B69
STATUS_MONEY_SEPARATOR = 0x80
STATUS_MONEY_UNIT_POINTER_OPERAND_OFFSET = 0x0769BC  # LDY #$7B6A at CE:E9BB
STATUS_MONEY_UNIT_POINTER_STOCK = bytes.fromhex("6A 7B")
STATUS_MONEY_UNIT_POINTER_SPACED = bytes.fromhex("69 7B")
STATUS_WEAPON_RANGES = {
    "C7:7B6D": (0x077B6D, 0x077B74),
    "C7:7B74": (0x077B74, 0x077B7A),
    "C7:7B7A": (0x077B7A, 0x077B7E),
    "C7:7B7E": (0x077B7E, 0x077B84),
    "C7:7B84": (0x077B84, 0x077B89),
    "C7:7B89": (0x077B89, 0x077B93),
    "C7:7B93": (0x077B93, 0x077B9D),
    "C7:7B9D": (0x077B9D, 0x077BA5),
}
STATUS_MISC_RANGES = {
    "C7:7BA5": (0x077BA5, 0x077BAA),
    "C7:7BAA": (0x077BAA, 0x077BB5),
}

STATUS_LABEL_IDS = {
    "STRENGTH": "new:status.label.strength",
    "AGILITY": "new:status.label.agility",
    "CONSTITUTION": "new:status.label.constitution",
    "INTELLIGENCE": "new:status.label.intelligence",
    "WISDOM": "new:status.label.wisdom",
    "ATTACK": "new:status.label.attack",
    "HIT_PERCENT": "new:status.label.hit_percent",
    "DEFENSE": "new:status.label.defense",
    "EVADE_PERCENT": "new:status.label.evade_percent",
    "MAGIC_DEFENSE": "new:status.label.magic_defense",
}
STATUS_LABEL_FIXED_FALLBACK_IDS = {
    "INTELLIGENCE": "new:status.label.intelligence.fixed",
    "HIT_PERCENT": "new:status.label.hit_percent.fixed",
    "MAGIC_DEFENSE": "new:status.label.magic_defense.fixed",
}

# Full, localization-owned Status labels for the exact vwf_ui backend.  The
# fixed-font stock screen continues to consume the safe 10-cell fallback rows
# at C7:7A28.  Aggregate builds may render these full direct-glyph records
# instead, without embedding French prose in the generic VWF component.
STATUS_VWF_LABEL_TABLE_OFFSET = 0x2D8B00       # SNES ED:8B00
STATUS_VWF_LABEL_RECORD_SIZE = 16              # length byte + up to 15 glyphs
STATUS_VWF_LABEL_COUNT = 10
STATUS_VWF_LABEL_MARKER_OFFSET = 0x2D8BA0      # SNES ED:8BA0
STATUS_VWF_LABEL_MARKER = bytes.fromhex("53 56")  # "SV" / Status VWF source
STATUS_LABEL_ORDER = (
    "STRENGTH", "AGILITY", "CONSTITUTION", "INTELLIGENCE", "WISDOM",
    "ATTACK", "HIT_PERCENT", "DEFENSE", "EVADE_PERCENT", "MAGIC_DEFENSE",
)


ASCII_TO_SOM = {" ": 0x80}
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
from shared.charset import FULL_FRENCH_CHARS, glyph_bytes, profile_mapping, profile_threshold
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
from shared.text.stock import encode_text_with_stock_dte
from shared.extracted.assets import load_or_extract_interface, load_or_extract_menu  # noqa: E402

ACCENT_TO_SOM = profile_mapping("full_french")
ASCII_TO_SOM.update(ACCENT_TO_SOM)
ASCII_TO_SOM.update({chr(ord("a") + i): 0x81 + i for i in range(26)})
ASCII_TO_SOM.update({chr(ord("A") + i): 0x9B + i for i in range(26)})
ASCII_TO_SOM.update({str(i): 0xB5 + i for i in range(10)})
ASCII_TO_SOM.update({
    ".": 0xBF, ",": 0xC0, "/": 0xC1, "'": 0xC2,
    '"': 0xC3,  # handled specially below to alternate opening/closing quote
    ":": 0xC5, "-": 0xC6, "%": 0xC7, "!": 0xC8, "&": 0xC9,
    "?": 0xCA, "(": 0xCB, ")": 0xCC, "#": 0xCD,
})



# Stock US 8x12 font. Character $80 begins at ROM $12DC00.
FONT_BASE = 0x12DC00
GLYPH_HEIGHT = 12
ACCENT_FIRST = ACCENT_TO_SOM[FULL_FRENCH_CHARS[0]]
ROOT = Path(__file__).resolve().parent

# The stock text decoder treats $D3-$FF as DTE dictionary bytes.
# For this project, $D4-$E0 become ordinary glyph codes, so the DTE
# threshold moves to $E1. The original US script does not use these
# DTE values as text.
DTE_COMPARE_IMMEDIATE_OFFSET = 0x0016F6
DTE_STOCK_THRESHOLD = 0xD3
DTE_NEW_THRESHOLD = profile_threshold("full_french")
# Status strings deliberately use only DTE codes valid under both the standalone
# basic-French $E1 boundary and the aggregate full-French $E6 fallback boundary.
STATUS_DTE_THRESHOLD = profile_threshold("full_french")

def load_accent_glyphs() -> bytes:
    """Load the canonical shared GAME SELECT French glyph profile."""
    try:
        return glyph_bytes(FULL_FRENCH_CHARS)
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
                "The GAME SELECT builder supports ASCII plus the shared full_french profile."
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
WINDOW_EDIT_IDS = {
    "SELECT": "C7:73C9",
    "TITLE": "C7:73D1",
    "HORIZONTAL": "new:window_edit.axis.horizontal",
    "VERTICAL": "new:window_edit.axis.vertical",
    "FALLBACK": "new:window_edit.compact_fallback",
}
WINDOW_HELP_IDS = {
    "HELP_1": "C0:34F9",
    "HELP_2": "C0:3521",
    "HELP_3": "C0:3550",
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

# Three fixed-font help rows per menu, via C0:33B5 entries 5/6.
# Reserve one expanded-ROM page each; no renderer or description-table changes.
SKILL_HELP_BLOCKS = (
    (0x0033C4, 0xC7784C, 0x2DA000, ("C7:784C", "C7:7874", "C7:78A8")),
    (0x0033C7, 0xC778D4, 0x2DA100, ("C7:78D4", "C7:78FB", "C7:7933")),
)


def load_french_rows(base: bytes) -> tuple[dict[str, str], dict[str, str], dict[str, str], dict[str, str], dict[str, str], dict[str, str], dict[str, str], dict[str, object]]:
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
        window_rows = {
            name: require(menu_fr, [text_id], context="Window Settings")[0]
            for name, text_id in WINDOW_EDIT_IDS.items()
        }
        window_help_rows = {
            name: require(interface_fr, [text_id], context="Window Settings help")[0]
            for name, text_id in WINDOW_HELP_IDS.items()
        }
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

        skill_menu_rows = {
            text_id: require(menu_fr, [text_id], context="Weapon/Magic skill labels")[0]
            for text_id in SKILL_MENU_RANGES
        }
        for _, _, _, text_ids in SKILL_HELP_BLOCKS:
            skill_menu_rows.update(zip(
                text_ids,
                require(interface_fr, list(text_ids), context="Weapon/Magic skill help"),
                strict=True,
            ))

        status_labels = {
            name: require(interface_fr, [text_id], context="Status labels")[0]
            for name, text_id in STATUS_LABEL_IDS.items()
        }
        status_fixed_labels = dict(status_labels)
        for name, text_id in STATUS_LABEL_FIXED_FALLBACK_IDS.items():
            status_fixed_labels[name] = require(
                interface_fr, [text_id], context="Status fixed-font fallbacks"
            )[0]

        status_rows: dict[str, object] = {
            "LABELS": status_labels,
            "FIXED_LABELS": status_fixed_labels,
            "CONDITIONS": require(menu_fr, list(STATUS_CONDITION_IDS), context="Status conditions"),
            "TEMPLATES": {
                text_id: require(menu_fr, [text_id], context="Status templates")[0]
                for text_id in (*STATUS_TEMPLATE_RANGES, "C7:7B39", "C7:7B41")
            },
            "WEAPONS": {
                text_id: require(menu_fr, [text_id], context="Status weapon types")[0]
                for text_id in STATUS_WEAPON_RANGES
            },
            "MISC": {
                text_id: require(menu_fr, [text_id], context="Status misc labels")[0]
                for text_id in STATUS_MISC_RANGES
            },
        }
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    return rows, game_file_rows, window_rows, window_help_rows, action_rows, action_help_rows, skill_menu_rows, status_rows


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


def build_window_help(rows: dict[str, str]) -> bytes:
    encoded: list[bytes] = []
    for key in ("HELP_1", "HELP_2", "HELP_3"):
        payload = encode_text(rows[key], f"Window Settings {key}")
        if len(payload) > 58:
            raise SystemExit(
                f"Window Settings {key} encodes to {len(payload)} cells; fixed help renderer supports at most 58"
            )
        encoded.append(payload)
    return b"\x7f".join(encoded) + b"\x00"


def _source_tile_for_cell(cell: int) -> int:
    # Native fixed-font source tiles advance by $04 per two source cells.
    return 0x50 + (cell // 2) * 4


def build_window_resource(base: bytes, rows: dict[str, str]) -> tuple[bytes, bytes]:
    prefix = base[
        WINDOW_RESOURCE_STOCK_OFFSET:
        WINDOW_RESOURCE_STOCK_OFFSET + WINDOW_RESOURCE_PREFIX_CELLS
    ]
    if prefix != WINDOW_RESOURCE_PREFIX_STOCK:
        raise SystemExit("Unexpected clean-USA Window Settings resource prefix")

    horizontal = encode_text(rows["HORIZONTAL"], "Window Settings horizontal axis")
    vertical = encode_text(rows["VERTICAL"], "Window Settings vertical axis")
    title = encode_text(rows["TITLE"], "Window Settings title")
    if len(horizontal) > WINDOW_AXIS_SLOT_CELLS:
        raise SystemExit("Window Settings horizontal label exceeds 8 fixed cells")
    if len(vertical) > WINDOW_AXIS_SLOT_CELLS:
        raise SystemExit("Window Settings vertical label exceeds 8 fixed cells")
    if len(title) > WINDOW_TITLE_SLOT_CELLS - 1:
        raise SystemExit("Window Settings title exceeds 16 visible fixed cells")

    # Runtime-validated visual slots preserve the proven source anchors: one
    # leading cell before the horizontal label, no leading cell before the
    # vertical label, then right-padding to the native 8-cell source spans.
    horizontal_lead = 1
    if horizontal_lead + len(horizontal) > WINDOW_AXIS_SLOT_CELLS:
        raise SystemExit("Window Settings horizontal label no longer fits its validated source anchor")
    horizontal_slot = (
        b"\x80" * horizontal_lead
        + horizontal
        + b"\x80" * (WINDOW_AXIS_SLOT_CELLS - horizontal_lead - len(horizontal))
    )
    vertical_slot = vertical + b"\x80" * (WINDOW_AXIS_SLOT_CELLS - len(vertical))
    title_slot = title + b"\x80" * (WINDOW_TITLE_SLOT_CELLS - len(title))

    horizontal_start = WINDOW_RESOURCE_PREFIX_CELLS
    vertical_start = horizontal_start + WINDOW_AXIS_SLOT_CELLS
    title_start = vertical_start + WINDOW_AXIS_SLOT_CELLS
    resource = prefix + horizontal_slot + vertical_slot + title_slot + b"\x00"

    horizontal_tile = _source_tile_for_cell(horizontal_start)
    vertical_tile = _source_tile_for_cell(vertical_start)
    expected_title_tile = _source_tile_for_cell(title_start)
    if (horizontal_tile, vertical_tile, expected_title_tile) != (0x68, 0x78, 0x88):
        raise SystemExit("Unexpected Window Settings source-tile layout")

    records = list(WINDOW_CONTROL_PLACEMENTS)
    # End the placement list on the vertical span.  C0:23CF leaves the native
    # source cursor after that span, at $88, exactly where the frame script
    # expects the relocated title to begin.
    for destination in WINDOW_HORIZONTAL_DESTINATIONS:
        records.append((4, horizontal_tile, destination))
    for destination in WINDOW_VERTICAL_DESTINATIONS:
        records.append((4, vertical_tile, destination))

    placement = bytearray((0x00,))
    for width_units, source_tile, destination in records:
        placement.extend((
            width_units,
            source_tile,
            destination & 0xFF,
            (destination >> 8) & 0xFF,
        ))
    placement.append(0x00)
    return resource, bytes(placement)


def apply_window_settings(base: bytes, rom: bytearray, rows: dict[str, str], help_rows: dict[str, str]) -> None:
    if base[WINDOW_SELECT_OFFSET:WINDOW_SELECT_OFFSET + WINDOW_SELECT_CAPACITY] != WINDOW_SELECT_STOCK:
        raise SystemExit("Unexpected clean-USA Window Settings SELECT slot")
    if base[WINDOW_TITLE_FIXED_OFFSET:WINDOW_TITLE_FIXED_OFFSET + WINDOW_TITLE_FIXED_CAPACITY] != WINDOW_TITLE_FIXED_STOCK:
        raise SystemExit("Unexpected clean-USA Window Settings compact title slot")
    if int.from_bytes(base[WINDOW_HELP_POINTER_OFFSET:WINDOW_HELP_POINTER_OFFSET + 3], "little") != WINDOW_HELP_POINTER_STOCK:
        raise SystemExit("Unexpected clean-USA Window Settings help pointer")
    if int.from_bytes(base[WINDOW_DESCRIPTOR_TEXT_PTR_OFFSET:WINDOW_DESCRIPTOR_TEXT_PTR_OFFSET + 2], "little") != WINDOW_DESCRIPTOR_TEXT_PTR_STOCK:
        raise SystemExit("Unexpected clean-USA Window Settings text pointer")
    if int.from_bytes(base[WINDOW_DESCRIPTOR_PLACEMENT_PTR_OFFSET:WINDOW_DESCRIPTOR_PLACEMENT_PTR_OFFSET + 2], "little") != WINDOW_DESCRIPTOR_PLACEMENT_PTR_STOCK:
        raise SystemExit("Unexpected clean-USA Window Settings placement pointer")
    if base[WINDOW_FRAME_WIDTH_OFFSET] != WINDOW_FRAME_WIDTH_STOCK:
        raise SystemExit("Unexpected clean-USA Window Settings frame width")
    if any(value != 0xFF for value in base[WINDOW_RESOURCE_RELOC_OFFSET:WINDOW_PLACEMENT_RELOC_LIMIT]):
        raise SystemExit("Expected clean-USA $FF Window Settings relocation gap at C7:4700-4759")

    # Runtime-validated compact shadow fields.
    select_payload = encode_text(rows["SELECT"], "Window Settings SELECT")
    if len(select_payload) > WINDOW_SELECT_CAPACITY:
        raise SystemExit("Window Settings SELECT exceeds compact stock slot")
    rom[WINDOW_SELECT_OFFSET:WINDOW_SELECT_OFFSET + WINDOW_SELECT_CAPACITY] = (
        select_payload + b"\x80" * (WINDOW_SELECT_CAPACITY - len(select_payload))
    )
    fallback_payload = encode_text(rows["FALLBACK"], "Window Settings compact fallback")
    if len(fallback_payload) > WINDOW_TITLE_FIXED_CAPACITY:
        raise SystemExit("Window Settings compact fallback exceeds stock title slot")
    rom[WINDOW_TITLE_FIXED_OFFSET:WINDOW_TITLE_FIXED_OFFSET + WINDOW_TITLE_FIXED_CAPACITY] = (
        fallback_payload + b"\x80" * (WINDOW_TITLE_FIXED_CAPACITY - len(fallback_payload))
    )

    resource, placement = build_window_resource(base, rows)
    if WINDOW_RESOURCE_RELOC_OFFSET + len(resource) > WINDOW_RESOURCE_RELOC_LIMIT:
        raise SystemExit("Window Settings resource exceeded C7:4700-472E")
    if WINDOW_PLACEMENT_RELOC_OFFSET + len(placement) > WINDOW_PLACEMENT_RELOC_LIMIT:
        raise SystemExit("Window Settings placement exceeded C7:4730-4759")
    rom[WINDOW_RESOURCE_RELOC_OFFSET:WINDOW_RESOURCE_RELOC_OFFSET + len(resource)] = resource
    rom[WINDOW_PLACEMENT_RELOC_OFFSET:WINDOW_PLACEMENT_RELOC_OFFSET + len(placement)] = placement
    rom[WINDOW_DESCRIPTOR_TEXT_PTR_OFFSET:WINDOW_DESCRIPTOR_TEXT_PTR_OFFSET + 2] = WINDOW_RESOURCE_RELOC_PTR.to_bytes(2, "little")
    rom[WINDOW_DESCRIPTOR_PLACEMENT_PTR_OFFSET:WINDOW_DESCRIPTOR_PLACEMENT_PTR_OFFSET + 2] = WINDOW_PLACEMENT_RELOC_PTR.to_bytes(2, "little")
    rom[WINDOW_FRAME_WIDTH_OFFSET] = WINDOW_FRAME_WIDTH_FRENCH

    help_payload = build_window_help(help_rows)
    if WINDOW_HELP_RELOC_OFFSET + len(help_payload) > WINDOW_HELP_RELOC_LIMIT:
        raise SystemExit("Window Settings help exceeded reserved ED:8600-ED:86FF region")
    rom[WINDOW_HELP_RELOC_OFFSET:WINDOW_HELP_RELOC_OFFSET + len(help_payload)] = help_payload
    rom[WINDOW_HELP_POINTER_OFFSET:WINDOW_HELP_POINTER_OFFSET + 3] = WINDOW_HELP_RELOC_SNES.to_bytes(3, "little")


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



def _build_status_label_row(
    labels: dict[str, str], placements: tuple[tuple[str, int], ...], cells: int, context: str
) -> bytes:
    row = bytearray([0x80] * cells)
    occupied = [False] * cells
    for name, start in placements:
        payload = encode_text(labels[name], f"{context} {name}")
        end = start + len(payload)
        if start < 0 or end > cells:
            raise SystemExit(f"{context} {name} exceeds its fixed-font row")
        if any(occupied[start:end]):
            raise SystemExit(f"{context} {name} overlaps another fixed-font label")
        row[start:end] = payload
        occupied[start:end] = [True] * len(payload)
    return bytes(row)


def build_status_labels(rows: dict[str, object]) -> bytes:
    labels = rows["FIXED_LABELS"]
    if not isinstance(labels, dict):
        raise SystemExit("Internal error: malformed Status fixed-label set")
    row1 = _build_status_label_row(
        labels, STATUS_LABEL_ROW1_PLACEMENTS, STATUS_LABELS_ROW1_CELLS, "Status row 1"
    )
    row2 = _build_status_label_row(
        labels, STATUS_LABEL_ROW2_PLACEMENTS, STATUS_LABELS_ROW2_CELLS, "Status row 2"
    )
    payload = row1 + b"\x7F" + row2 + b"\x00"
    if len(payload) != STATUS_LABELS_BLOCK_END - STATUS_LABELS_OFFSET:
        raise SystemExit("Internal error: Status characteristic block changed physical size")
    return payload


def build_status_vwf_label_table(rows: dict[str, object]) -> bytes:
    """Build ten fixed-size direct-glyph records for the exact Status VWF path."""
    labels = rows["LABELS"]
    if not isinstance(labels, dict):
        raise SystemExit("Internal error: malformed Status VWF label set")
    out = bytearray()
    for name in STATUS_LABEL_ORDER:
        text = labels[name]
        if not isinstance(text, str):
            raise SystemExit(f"Internal error: non-string Status label {name}")
        payload = encode_text(text, f"Status VWF {name}")
        capacity = STATUS_VWF_LABEL_RECORD_SIZE - 1
        if len(payload) > capacity:
            raise SystemExit(
                f"Status VWF {name} needs {len(payload)} glyphs; record capacity is {capacity}"
            )
        out.append(len(payload))
        out.extend(payload)
        out.extend([0x80] * (capacity - len(payload)))
    expected = STATUS_VWF_LABEL_COUNT * STATUS_VWF_LABEL_RECORD_SIZE
    if len(out) != expected:
        raise SystemExit("Internal error: Status VWF label table changed physical size")
    return bytes(out)


def _encode_status_text(base: bytes, text: str, context: str) -> bytes:
    try:
        return encode_text_with_stock_dte(
            base, text, upper_dte_threshold=STATUS_DTE_THRESHOLD
        )
    except ValueError as exc:
        raise SystemExit(f"{context}: {exc}") from exc


def _encode_status_template(base: bytes, text: str, context: str) -> bytes:
    out = bytearray()
    cursor = 0
    for match in re.finditer(r"\{5C([0-9A-Fa-f]{2})\}", text):
        if match.start() > cursor:
            out += _encode_status_text(base, text[cursor:match.start()], context)
        out += bytes((0x5C, int(match.group(1), 16)))
        cursor = match.end()
    if cursor < len(text):
        tail = text[cursor:]
        if "{" in tail or "}" in tail:
            raise SystemExit(f"{context}: unsupported control syntax in {text!r}")
        out += _encode_status_text(base, tail, context)
    elif "{" in text[cursor:] or "}" in text[cursor:]:
        raise SystemExit(f"{context}: unsupported control syntax in {text!r}")
    # Reject braces that were not consumed by a supported {5Cxx} control.
    stripped = re.sub(r"\{5C[0-9A-Fa-f]{2}\}", "", text)
    if "{" in stripped or "}" in stripped:
        raise SystemExit(f"{context}: unsupported control syntax in {text!r}")
    return bytes(out)


def build_status_condition_pool(base: bytes, rows: dict[str, object]) -> tuple[bytes, bytes]:
    conditions = rows["CONDITIONS"]
    if not isinstance(conditions, list) or len(conditions) != len(STATUS_CONDITION_IDS):
        raise SystemExit("Internal error: malformed Status condition set")
    pool = bytearray()
    pointers = bytearray()
    for index, text in enumerate(conditions):
        if not isinstance(text, str):
            raise SystemExit("Internal error: non-string Status condition")
        pointer = (STATUS_CONDITION_POOL_OFFSET & 0xFFFF) + len(pool)
        pointers += pointer.to_bytes(2, "little")
        pool += _encode_status_text(base, text, f"Status condition {index}") + b"\x00"
    capacity = STATUS_CONDITION_POOL_END - STATUS_CONDITION_POOL_OFFSET
    if len(pool) > capacity:
        raise SystemExit(
            f"Status condition pool needs {len(pool)} bytes; stock allocation is {capacity}"
        )
    pool += b"\x00" * (capacity - len(pool))
    return bytes(pool), bytes(pointers)


def _write_status_fixed_records(
    base: bytes,
    rom: bytearray,
    rows: dict[str, object],
    key: str,
    ranges: dict[str, tuple[int, int]],
    *,
    controls: bool = False,
) -> None:
    values = rows[key]
    if not isinstance(values, dict):
        raise SystemExit(f"Internal error: malformed Status {key.lower()} set")
    for text_id, (start, end) in ranges.items():
        text = values[text_id]
        if not isinstance(text, str):
            raise SystemExit(f"Internal error: non-string Status value {text_id}")
        payload = (
            _encode_status_template(base, text, f"Status {text_id}")
            if controls else _encode_status_text(base, text, f"Status {text_id}")
        ) + b"\x00"
        capacity = end - start
        if len(payload) > capacity:
            raise SystemExit(
                f"Status {text_id} needs {len(payload)} bytes; stock slot is {capacity}"
            )
        rom[start:start + len(payload)] = payload


def _write_status_exp_next_pair(
    base: bytes, rom: bytearray, rows: dict[str, object]
) -> int:
    values = rows["TEMPLATES"]
    if not isinstance(values, dict):
        raise SystemExit("Internal error: malformed Status templates set")

    exp_text = values["C7:7B39"]
    next_text = values["C7:7B41"]
    if not isinstance(exp_text, str) or not isinstance(next_text, str):
        raise SystemExit("Internal error: malformed Status EXP / NEXT LEVEL text")

    exp_payload = _encode_status_template(base, exp_text, "Status C7:7B39") + b"\x00"
    next_payload = _encode_status_template(base, next_text, "Status C7:7B41") + b"\x00"
    capacity = STATUS_EXP_NEXT_REGION_END - STATUS_EXP_NEXT_REGION_START
    if len(exp_payload) + len(next_payload) > capacity:
        raise SystemExit(
            "Status EXP / NEXT LEVEL pair needs "
            f"{len(exp_payload) + len(next_payload)} bytes; shared stock region is {capacity}"
        )

    if (
        base[
            STATUS_NEXT_LEVEL_POINTER_OPERAND_OFFSET:
            STATUS_NEXT_LEVEL_POINTER_OPERAND_OFFSET + 2
        ]
        != STATUS_NEXT_LEVEL_POINTER_STOCK
    ):
        raise SystemExit("Unexpected clean-USA Status NEXT LEVEL pointer immediate")

    next_start = STATUS_EXP_NEXT_REGION_START + len(exp_payload)
    next_ptr = 0x7B39 + len(exp_payload)
    rom[STATUS_EXP_NEXT_REGION_START:STATUS_EXP_NEXT_REGION_END] = b"\x00" * capacity
    rom[STATUS_EXP_NEXT_REGION_START:next_start] = exp_payload
    rom[next_start:next_start + len(next_payload)] = next_payload
    rom[
        STATUS_NEXT_LEVEL_POINTER_OPERAND_OFFSET:
        STATUS_NEXT_LEVEL_POINTER_OPERAND_OFFSET + 2
    ] = next_ptr.to_bytes(2, "little")
    return next_ptr


def apply_skill_menu_labels(base: bytes, rom: bytearray, rows: dict[str, str]) -> None:
    """Translate the four native Weapon/Magic skill-menu heading segments in place."""
    for text_id, (offset, capacity) in SKILL_MENU_RANGES.items():
        payload = encode_text(rows[text_id], f"Weapon/Magic skill label {text_id}")
        if len(payload) > capacity:
            raise SystemExit(
                f"{text_id} encodes to {len(payload)} cells; stock fixed slot capacity is {capacity}."
            )
        rom[offset:offset + capacity] = payload + b"\x80" * (capacity - len(payload))


def apply_status_screen(base: bytes, rom: bytearray, rows: dict[str, object]) -> None:
    if int.from_bytes(base[STATUS_LABELS_POINTER_OFFSET:STATUS_LABELS_POINTER_OFFSET + 3], "little") != STATUS_LABELS_POINTER_STOCK:
        raise SystemExit("Unexpected clean-USA Status characteristic-label pointer")

    labels = build_status_labels(rows)
    rom[STATUS_LABELS_OFFSET:STATUS_LABELS_BLOCK_END] = labels

    # Keep full reviewed labels in a localization-owned expanded-ROM table.
    # vwf_ui may consume this exact table in aggregate builds; standalone
    # french_menus continues to display only the safe fixed-font fallbacks.
    vwf_labels = build_status_vwf_label_table(rows)
    rom[
        STATUS_VWF_LABEL_TABLE_OFFSET:
        STATUS_VWF_LABEL_TABLE_OFFSET + len(vwf_labels)
    ] = vwf_labels
    rom[
        STATUS_VWF_LABEL_MARKER_OFFSET:
        STATUS_VWF_LABEL_MARKER_OFFSET + len(STATUS_VWF_LABEL_MARKER)
    ] = STATUS_VWF_LABEL_MARKER

    if base[STATUS_SUFFIX_CONSTITUTION_OFFSET:STATUS_SUFFIX_CONSTITUTION_OFFSET + 2] != STATUS_SUFFIX_CONSTITUTION_STOCK:
        raise SystemExit("Unexpected clean-USA Status CONSTITUTION hard-coded suffix")
    if base[STATUS_SUFFIX_INTELLIGENCE_OFFSET:STATUS_SUFFIX_INTELLIGENCE_OFFSET + 2] != STATUS_SUFFIX_INTELLIGENCE_STOCK:
        raise SystemExit("Unexpected clean-USA Status INTELLIGENCE hard-coded suffix")
    rom[STATUS_SUFFIX_CONSTITUTION_OFFSET:STATUS_SUFFIX_CONSTITUTION_OFFSET + 2] = STATUS_SUFFIX_BLANK
    rom[STATUS_SUFFIX_INTELLIGENCE_OFFSET:STATUS_SUFFIX_INTELLIGENCE_OFFSET + 2] = STATUS_SUFFIX_BLANK

    condition_pool, condition_pointers = build_status_condition_pool(base, rows)
    rom[STATUS_CONDITION_POOL_OFFSET:STATUS_CONDITION_POOL_END] = condition_pool
    rom[
        STATUS_CONDITION_POINTER_TABLE_OFFSET:
        STATUS_CONDITION_POINTER_TABLE_OFFSET + len(condition_pointers)
    ] = condition_pointers

    _write_status_fixed_records(base, rom, rows, "TEMPLATES", STATUS_TEMPLATE_RANGES, controls=True)
    _write_status_exp_next_pair(base, rom, rows)

    # Insert one fixed-font separator between the dynamic amount and the
    # currency unit on this Status screen only.  The translated MONEY/Argent
    # template must terminate before C7:7B69 so that this byte is unreachable
    # from the label submit and can safely prefix the separate unit submit.
    if rom[STATUS_MONEY_SEPARATOR_OFFSET - 1] != 0x00:
        raise SystemExit(
            "Status Argent template no longer leaves C7:7B69 free for money spacing"
        )
    if (
        base[
            STATUS_MONEY_UNIT_POINTER_OPERAND_OFFSET:
            STATUS_MONEY_UNIT_POINTER_OPERAND_OFFSET + 2
        ]
        != STATUS_MONEY_UNIT_POINTER_STOCK
    ):
        raise SystemExit("Unexpected clean-USA Status money-unit pointer immediate")
    rom[STATUS_MONEY_SEPARATOR_OFFSET] = STATUS_MONEY_SEPARATOR
    rom[
        STATUS_MONEY_UNIT_POINTER_OPERAND_OFFSET:
        STATUS_MONEY_UNIT_POINTER_OPERAND_OFFSET + 2
    ] = STATUS_MONEY_UNIT_POINTER_SPACED

    _write_status_fixed_records(base, rom, rows, "WEAPONS", STATUS_WEAPON_RANGES)
    _write_status_fixed_records(base, rom, rows, "MISC", STATUS_MISC_RANGES)


def apply_skill_help(base: bytes, rom: bytearray, rows: dict[str, str]) -> None:
    # Both stock lower frames have 6 tile rows by 30 columns: three text
    # rows, each containing 60 fixed glyphs. Keep a two-cell safety margin.
    for frame_offset in (0x07761C, 0x07764D):
        if base[frame_offset:frame_offset + 5] != bytes.fromhex("01 c0 04 06 1e"):
            raise SystemExit("Unexpected Weapon/Magic help frame geometry")
    for pointer_offset, stock_pointer, target, text_ids in SKILL_HELP_BLOCKS:
        if int.from_bytes(base[pointer_offset:pointer_offset + 3], "little") != stock_pointer:
            raise SystemExit("Unexpected Weapon/Magic help source pointer")
        encoded = [encode_text(rows[text_id], text_id) for text_id in text_ids]
        if any(not row or len(row) > 58 for row in encoded):
            raise SystemExit("Weapon/Magic help rows require 1..58 fixed cells")
        payload = b"\x7f".join(encoded) + b"\x00"
        if target + 0x100 > len(rom) or len(payload) > 0x100:
            raise SystemExit("Weapon/Magic help exceeds its reserved page")
        if any(rom[target:target + 0x100]):
            raise SystemExit("Weapon/Magic help relocation page is not empty")
        rom[target:target + len(payload)] = payload
        rom[pointer_offset:pointer_offset + 3] = (target + 0xC00000).to_bytes(3, "little")


def apply_sources(base: bytes, rows: dict[str, str], game_file_rows: dict[str, str], window_rows: dict[str, str], window_help_rows: dict[str, str], action_rows: dict[str, str], action_help_rows: dict[str, str], skill_menu_rows: dict[str, str], status_rows: dict[str, object]) -> tuple[bytearray, int]:
    rom = expand_rom(base)

    # Turn $D4-$E5 into normal character codes for the stock text
    # decoder, while keeping $E6-$FF on the original DTE path.
    if base[DTE_COMPARE_IMMEDIATE_OFFSET] != DTE_STOCK_THRESHOLD:
        raise SystemExit(
            f"Unexpected stock DTE threshold at ${DTE_COMPARE_IMMEDIATE_OFFSET:06X}: "
            f"${base[DTE_COMPARE_IMMEDIATE_OFFSET]:02X}"
        )
    rom[DTE_COMPARE_IMMEDIATE_OFFSET] = DTE_NEW_THRESHOLD

    # Replace the 18 otherwise-unused direct-glyph slots $D4-$E5 with the
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

    # Window Settings: fixed-font-only relocated source/placement architecture.
    # Frame width and source length are advanced together to preserve the stock cursor.
    apply_window_settings(base, rom, window_rows, window_help_rows)

    # Action Settings: keep every frame and the 4x4 grid byte-for-byte stock.
    # Only repack/relocate the four translated fixed-width labels.
    apply_action_settings(base, rom, action_rows)
    apply_action_help(base, rom, action_help_rows)

    # Weapon/Magic skill headings: four short fixed-font segments in their stock slots.
    apply_skill_menu_labels(base, rom, skill_menu_rows)
    apply_skill_help(base, rom, skill_menu_rows)

    # Status / Characteristics: fixed-font data-only promotion. No VWF hooks.
    apply_status_screen(base, rom, status_rows)

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

    rows, game_file_rows, window_rows, window_help_rows, action_rows, action_help_rows, skill_menu_rows, status_rows = load_french_rows(base)
    patched, checksum = apply_sources(base, rows, game_file_rows, window_rows, window_help_rows, action_rows, action_help_rows, skill_menu_rows, status_rows)
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
    window_resource, window_placement = build_window_resource(base, window_rows)
    print(f"WINDOW SETTINGS title: {window_rows['TITLE']!r}; fixed-font frame width ${WINDOW_FRAME_WIDTH_FRENCH:02X}")
    print(f"WINDOW SETTINGS resource: {len(window_resource)} bytes at C7:${WINDOW_RESOURCE_RELOC_PTR:04X}")
    print(f"WINDOW SETTINGS placement: {len(window_placement)} bytes at C7:${WINDOW_PLACEMENT_RELOC_PTR:04X}; Fond left/right, Bordure top/bottom")
    print(f"WINDOW SETTINGS help: {len(build_window_help(window_help_rows))} bytes at SNES ${WINDOW_HELP_RELOC_SNES:06X}")
    action_resource, action_placement = build_action_settings_resource(action_rows)
    print(f"ACTION SETTINGS resource: {len(action_resource)} bytes at C7:${ACTION_RESOURCE_RELOC_PTR:04X}")
    print(f"ACTION SETTINGS placement: {len(action_placement)} bytes at C7:${ACTION_PLACEMENT_RELOC_PTR:04X}; stock frame width $18, GUARD -8 px")
    print(f"ACTION SETTINGS help: {len(build_action_help(action_help_rows))} bytes at SNES ${ACTION_HELP_RELOC_SNES:06X}")
    print(f"WEAPON/MAGIC skill headings: fixed-font stock slots -> {skill_menu_rows['C7:745E']!r} / {skill_menu_rows['C7:7478']!r}")
    status_pool, _status_ptrs = build_status_condition_pool(base, status_rows)
    status_used = sum(
        len(_encode_status_text(base, text, "Status condition summary")) + 1
        for text in status_rows["CONDITIONS"]
    )
    print("STATUS labels: fixed fallback 60+40 cells at C7:$7A28 + full VWF source at ED:$8B00")
    print(f"STATUS conditions: repacked in C7:$7A8E-$7B23 ({status_used}/{STATUS_CONDITION_POOL_END-STATUS_CONDITION_POOL_OFFSET} bytes used before zero fill)")
    next_ptr = 0x7B39 + len(_encode_status_template(base, status_rows["TEMPLATES"]["C7:7B39"], "Status EXP summary")) + 1
    print(f"STATUS EXP/NEXT LEVEL: full fixed-font labels repacked in C7:$7B39-$7B52; NEXT LEVEL now starts at C7:${next_ptr:04X}")
    print("STATUS remaining templates/weapon types/misc: stock starts and geometry preserved")
    menu_resource, widths = build_menu_resource(rows)
    print(f"GAME SELECT resource: {len(menu_resource)} bytes at C7:${MENU_RESOURCE_RELOC_PTR:04X}")
    print("GAME SELECT layout: native 45-byte resource; no additional DTE compression")
    for key in ("GAME_SELECT", "NEW_GAME", "GAME_FILE"):
        print(f"{key} frame width: ${widths[key]:02X} ({widths[key] * 2} text cells)")


if __name__ == "__main__":
    main()
