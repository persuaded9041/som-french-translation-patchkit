#!/usr/bin/env python3
"""Build standalone exact-scope UI VWF extensions.

Runtime-validated families are independently gated (Forge, Ring, shop, MONEY,
battle/status and the exact GAME FILE Mana label). The component is independent
of `vwf_dialogues`; only byte-identical shared VWF infrastructure is reused.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from shared.core.asm import MiniAssembler, lo24  # noqa: E402
from shared.charset import CHAR_TO_CODE, DIALOGUE_FRENCH_CHARS, glyph_bytes  # noqa: E402
from shared.core.ips import make_ips  # noqa: E402
from shared.core.rom import ROM_SIZE_OFFSET, expand_rom, update_checksum, validate_base_rom  # noqa: E402
from shared.vwf.compositor import validate_stock as validate_compositor, install as install_compositor  # noqa: E402
from shared.vwf.framing import validate_stock as validate_framing, install as install_framing  # noqa: E402
from shared.vwf.metrics import validated_advance  # noqa: E402
from shared.vwf.outline import validate_stock as validate_outline, install as install_outline  # noqa: E402
from shared.vwf.row_renderer import validate_stock as validate_row_renderer, install as install_row_renderer  # noqa: E402
from shared.vwf.renderer_runtime import validate_stock as validate_renderer_runtime, install as install_renderer_runtime  # noqa: E402
from shared.vwf.text_buffer import validate_stock as validate_text_buffer, install_common as install_text_buffer  # noqa: E402
from shared.vwf.ui import (  # noqa: E402
    validate_stock as validate_ui_dispatch,
    install_dispatcher,
    enable_ui,
    UI_RENDER_CPU,
    UI_TAG,
    FORGE_UI_MAGIC,
    RING_UI_MAGIC,
    SHOP_UI_MAGIC,
    SHOP_ROW_UI_MAGIC,
    MONEY_UI_MAGIC,
    BATTLE_UI_MAGIC,
    GAME_FILE_MANA_UI_MAGIC,
    SHOP_SUFFIX_GAP_HELPER_CPU,
    SHOP_SUFFIX_GAP_HELPER_FILE,
    DISPATCH_CPU,
)

ROM_TARGET_SIZE = 0x300000
FONT_BASE = 0x12DC00
DIALOGUE_CHARS = DIALOGUE_FRENCH_CHARS
GLYPH_FIRST = min(CHAR_TO_CODE[ch] for ch in DIALOGUE_CHARS)

FORGE_SUBMIT_FILE = 0x10D3D2
FORGE_SUBMIT_SIGNATURE = bytes.fromhex("A9 00 00 20 D7 D5")
FORGE_SUBMIT_HELPER = 0xC00095
ARROW_TEXT_X_ARG_FILE = 0x10D83A
PRICE_TEXT_X_ARG_FILE = 0x10D878
EXPECTED_ARROW_X = 0x10
EXPECTED_PRICE_X = 0x15
SAFE_ARROW_SLOT = 0x14  # 20: 19-char max name + one logical space
SAFE_PRICE_SLOT = 0x19  # 25: preserves a readable gap before price in stock decode

UI_RENDER_FILE = 0x2D7B00
UI_RENDER_RESERVED_SIZE = 0x200
WIDTH_TABLE_FILE = 0x2D7D00
SUBMIT_WRAPPER_CPU = 0xED7E00
SUBMIT_WRAPPER_FILE = 0x2D7E00
SUBMIT_WRAPPER_RESERVED_SIZE = 0x80

SHOP_DISPATCH_SITES = (0x007EA6, 0x007FB9)
SHOP_DISPATCH_SIGNATURE = bytes.fromhex("A9 D9 8D 03 1D 8E 01 1D 22 92 00 C0")
SHOP_DISPATCH_WRAPPER_CPU = 0xED7E80
SHOP_DISPATCH_WRAPPER_FILE = 0x2D7E80
SHOP_DISPATCH_WRAPPER_RESERVED_SIZE = 0x80
SHOP_POOL_START = 0xFE20
SHOP_POOL_END = 0xFEF4

BATTLE_SUBMIT_50_FILE = 0x005BEA
BATTLE_SUBMIT_51_FILE = 0x005BF8
BATTLE_SUBMIT_50_SIGNATURE = bytes.fromhex("A0 7D 63 8C 01 1D A9 C0 8D 03 1D 64 A3 60")
BATTLE_SUBMIT_51_SIGNATURE = bytes.fromhex("A0 7F 63 8C 01 1D A9 C0 8D 03 1D 64 9F 60")
BATTLE_SUBMIT_50_WRAPPER_CPU = 0xED7F00
BATTLE_SUBMIT_50_WRAPPER_FILE = 0x2D7F00
BATTLE_SUBMIT_51_WRAPPER_CPU = 0xED7F20
BATTLE_SUBMIT_51_WRAPPER_FILE = 0x2D7F20
BATTLE_SUBMIT_WRAPPER_RESERVED_SIZE = 0x20

# GAME FILE Mana-power row. The fourth generator entry in C7:5F8F points to
# C7:5464 on a clean USA ROM. Route only that one generator through a tiny C7
# trampoline, then through a private ED wrapper which replays the stock builder
# after submitting a pair-aligned 16-cell VWF tile upload for the 15-cell label.
GAME_FILE_MANA_GENERATOR_PTR_FILE = 0x075F95
GAME_FILE_MANA_GENERATOR_PTR_STOCK = bytes.fromhex("64 54")
GAME_FILE_MANA_TRAMPOLINE_CPU = 0xC74C88
GAME_FILE_MANA_TRAMPOLINE_FILE = 0x074C88
GAME_FILE_MANA_TRAMPOLINE_SIZE = 7
GAME_FILE_MANA_WRAPPER_CPU = 0xED7F40
GAME_FILE_MANA_WRAPPER_FILE = 0x2D7F40
GAME_FILE_MANA_WRAPPER_RESERVED_SIZE = 0xC0
GAME_FILE_MANA_SOURCE_CPU = 0xC773AA
GAME_FILE_MANA_SOURCE_CELLS = 15
GAME_FILE_MANA_PRIVATE_BUFFER = 0x9C00
GAME_FILE_MANA_VRAM_DEST = 0x6820
GAME_FILE_MANA_DMA_SIZE = 0x0200

# C7:7147 is the stock per-window-type geometry table consumed by C0:0D8B.
# Each type owns a two-byte (height, width) pair.  Type 2 (MONEY) is stock
# `02 09`: two rows, nine text cells. VWF presentation adds a narrow visual
# separator before the final two-glyph currency unit and needs extra right
# breathing room. Runtime review showed 10 cells too tight at the right edge,
# so use 11 cells. The live source buffer remains unchanged and the currency
# glyphs themselves remain owned by the source text component.
MONEY_WINDOW_WIDTH_FILE = 0x07714C
EXPECTED_MONEY_WINDOW_WIDTH = 0x09
FRENCH_MONEY_WINDOW_WIDTH = 0x0B

# MONEY close geometry is seeded independently from the opening geometry by
# C0:0D8B when $A170 == $51.  The type-2 horizontal close seed is the low byte
# at C7:7140.  Stock width 9 expands around the fixed opening centre to a final
# left bound of cell 10, matching the stock close seed $0A.  Width 11 expands
# one cell farther left (cell 9), so retaining $0A leaves that new left frame
# column on screen after MONEY_CLOSE.  Shift only the type-2 close seed left by
# one cell; all other window types and the opening centre remain stock.
MONEY_CLOSE_X_FILE = 0x077140
EXPECTED_MONEY_CLOSE_X = 0x0A
FRENCH_MONEY_CLOSE_X = 0x09

PRIVATE_BUFFER = 0x9390
STOCK_BUFFER = 0xA1A4
PIXEL_CURSOR = 0x9382
RENDER_ACTIVE = 0x9385
SAVED_COUNT = 0x938E
PHYSICAL_CELLS = 0x938F

# Status / Characteristics exact-label VWF probe.  The generic menu parser
# still owns source decoding and chunk scheduling; only the stock bitmap ->
# SNES-tile conversion call is intercepted, and only for the exact C7:7A28
# characteristics resource while french_menus' validated blank suffix state is
# present.  All dynamic values, bars and every other menu resource fall through
# to the untouched stock converter.
STATUS_BITMAP_CONVERT_HOOK_FILE = 0x002366
STATUS_BITMAP_CONVERT_HOOK_SIGNATURE = bytes.fromhex("A2 00 00 A0")
STATUS_BITMAP_CONVERT_RESUME_CPU = 0xC0236C
STATUS_BITMAP_CONVERT_RTS_CPU = 0xC02386
STATUS_VWF_HELPER_CPU = 0xED8700
STATUS_VWF_HELPER_FILE = 0x2D8700
STATUS_VWF_HELPER_RESERVED_SIZE = 0x200
STATUS_VWF_RENDER_SLOT_CPU = 0xED8900
STATUS_VWF_RENDER_SLOT_FILE = 0x2D8900
STATUS_VWF_RENDER_SLOT_RESERVED_SIZE = 0xC0
STATUS_VWF_COPY_CELLS_CPU = 0xED89C0
STATUS_VWF_COPY_CELLS_FILE = 0x2D89C0
STATUS_VWF_COPY_CELLS_RESERVED_SIZE = 0x80
STATUS_VWF_LABEL_TABLE_CPU = 0xED8B00
STATUS_VWF_LABEL_RECORD_SIZE = 16
STATUS_VWF_LABEL_MARKER_CPU = 0xED8BA0
STATUS_VWF_LABEL_MARKER_WORD = 0x5653  # little-endian bytes 53 56 ("SV")
STATUS_SOURCE_CPU = 0xC77A28
STATUS_SOURCE_END_PTR = 0x7A8F
STATUS_MENU_ID = 0x08
STATUS_SUFFIX_CONSTITUTION_CPU = 0xC76764
STATUS_SUFFIX_INTELLIGENCE_CPU = 0xC76771
STATUS_SUFFIX_BLANK_WORD = 0x8080
STATUS_TEMP_BITMAP_OFFSET = 0x0180  # $9180, immediately after the stock 32-cell $9000 bitmap
STATUS_TEMP_BITMAP_BYTES = 11 * 12  # 10-cell slot + one compositor spill cell
STATUS_WIDTH_TABLE_CPU = 0xED7D00

# UI-private scratch used only while the exact status-label converter hook is
# active.  $93C1 remains the ordinary UI family tag; dialogue-choice scratch
# ends at $93C0 and dialogue continuation state begins at $93D0.
STATUS_SRC_OFFSET = 0x93C2       # 16-bit source offset into ED:8B00 VWF label table
STATUS_CHAR_COUNT = 0x93C4
STATUS_GLYPH = 0x93C5
STATUS_ROW_COUNT = 0x93C6
STATUS_COPY_SRC_CELL = 0x93C7
STATUS_COPY_DST_CELL = 0x93C8
STATUS_COPY_CELL_COUNT = 0x93C9
STATUS_COPY_BYTE_COUNT = 0x93CA
STATUS_MUL_TEMP = 0x93CB          # 16-bit arithmetic temporary ($93CB-$93CC)
DECODED_COUNT = 0xA1CE

# Weapon / magic skill-list presentation. The stock row builder emits
#   level ':' two-character progress field dynamic-name
# where a one-digit progress field is left-padded with a blank and there is no
# separator before the name. The localized presentation instead emits the
# shortest progress value followed by exactly one fixed blank, then VWF-renders
# only the already-decoded dynamic name. The numeric prefix remains stock font.
#
# C7:6619 and C7:664E are exact row-only helpers used by the weapon and magic
# lists respectively. Their trailing `JSR $5AFC / RTS` is left structurally
# intact: only the JSR target is redirected to a small same-bank helper.
SKILL_PROGRESS_FORMAT_HELPER_CPU = 0xC74F00
SKILL_PROGRESS_FORMAT_HELPER_FILE = 0x074F00
SKILL_PROGRESS_FORMAT_HELPER_RESERVED_SIZE = 0x30
SKILL_PROGRESS_FORMAT_CALLS = (
    0x07664A,  # C7:664A, weapon-list progress formatter
    0x07665D,  # C7:665D, magic-list progress formatter
)
SKILL_PROGRESS_FORMAT_CALL_STOCK = bytes.fromhex("20 FC 5A")

# C0:2366 is already the exact Status bitmap-converter interception point.
# Route it first through the runtime-validated skill-row classifier at ED:8C00.
# Non-matching calls jump byte-for-byte into the validated Status helper at
# ED:8700. The exact weapon/magic batch is scoped by $7E:93CD=$5A; within that
# scope the helper dynamically searches the decoded row for the compact
# `digit : digit [digit] blank name...` prefix instead of assuming cell 0.
SKILL_VWF_HELPER_CPU = 0xED8C00
SKILL_VWF_HELPER_FILE = 0x2D8C00
SKILL_VWF_HELPER_RESERVED_SIZE = 0x200
SKILL_DIGIT_FIRST = 0xB5
SKILL_DIGIT_AFTER_LAST = 0xBF
SKILL_COLON = 0xC5
SKILL_BLANK = 0x80
SKILL_PREFIX_SCAN_MAX = 28
SKILL_BITMAP_BYTES = 0x0180
SKILL_ROW_SCOPE = 0x93CD
SKILL_ROW_MAGIC = 0x5A
SKILL_SUBMIT_WRAPPER_CPU = 0xC74F30
SKILL_SUBMIT_WRAPPER_FILE = 0x074F30
SKILL_SUBMIT_WRAPPER_RESERVED_SIZE = 0x10
SKILL_SUBMIT_CALLS = (
    0x0765B0,  # magic-list 8-row batch -> JSR $5D9A
    0x076615,  # weapon-list 8-row batch -> JSR $5D9A
)
SKILL_SUBMIT_CALL_STOCK = bytes.fromhex("20 9A 5D")

# Magic lower-panel full-row VWF.  The stock panel is physically six 30-cell
# DMA passes arranged as three visible rows x two side-by-side halves.  The
# validated presentation renders one 60-cell / 480px logical row, then slices
# its bitmap back into the two stock 30-cell passes.  Runtime identity comes
# from an exact cloned C7:6512 submit and IDs captured directly from stock's
# own magic-description builder/availability logic.  Localized row content is
# owned by french_resources at ED:9200 and guarded by a source marker.
MAGIC_PANEL_PREP_CALL_FILE = 0x07649E      # JSR $6BCF
MAGIC_PANEL_PREP_CALL_STOCK = bytes.fromhex("20 CF 6B")
MAGIC_PANEL_COPY_CALL_FILE = 0x076501      # JSR $6AB7
MAGIC_PANEL_COPY_CALL_STOCK = bytes.fromhex("20 B7 6A")
MAGIC_PANEL_SUBMIT_CALL_FILE = 0x07650E    # JSR $6512
MAGIC_PANEL_SUBMIT_CALL_STOCK = bytes.fromhex("20 12 65")

MAGIC_PANEL_BATCH_HELPER_CPU = 0xC74F40
MAGIC_PANEL_BATCH_HELPER_FILE = 0x074F40
MAGIC_PANEL_BATCH_HELPER_RESERVED_SIZE = 0x80
MAGIC_PANEL_RESET_STUB_CPU = 0xC74FC0
MAGIC_PANEL_RESET_STUB_FILE = 0x074FC0
MAGIC_PANEL_RESET_STUB_RESERVED_SIZE = 0x10
MAGIC_PANEL_CAPTURE_STUB_CPU = 0xC74FD0
MAGIC_PANEL_CAPTURE_STUB_FILE = 0x074FD0
MAGIC_PANEL_CAPTURE_STUB_RESERVED_SIZE = 0x10

MAGIC_PANEL_DISPATCH_CPU = 0xED8E00
MAGIC_PANEL_DISPATCH_FILE = 0x2D8E00
MAGIC_PANEL_DISPATCH_RESERVED_SIZE = 0x300
MAGIC_PANEL_CAPTURE_HELPER_CPU = 0xED9140
MAGIC_PANEL_CAPTURE_HELPER_FILE = 0x2D9140
MAGIC_PANEL_CAPTURE_HELPER_RESERVED_SIZE = 0x80
MAGIC_PANEL_RESET_HELPER_CPU = 0xED91C0
MAGIC_PANEL_RESET_HELPER_FILE = 0x2D91C0
MAGIC_PANEL_RESET_HELPER_RESERVED_SIZE = 0x40
MAGIC_PANEL_DATA_CPU = 0xED9200
MAGIC_PANEL_RECORD_COUNT = 42
MAGIC_PANEL_RECORD_SIZE = 80
MAGIC_PANEL_MARKER_CPU = MAGIC_PANEL_DATA_CPU + MAGIC_PANEL_RECORD_COUNT * MAGIC_PANEL_RECORD_SIZE
MAGIC_PANEL_MARKER = b"MFV1"

MAGIC_PANEL_ID0 = 0x93F2
MAGIC_PANEL_CAPTURE_COUNT = 0x93F5
MAGIC_PANEL_LONG_CURSOR = 0x93CE       # 16-bit ($93CE-$93CF)
MAGIC_PANEL_HALF_FLAG = 0x93C7
MAGIC_PANEL_WIDTH_TEMP = 0x93C8       # 16-bit ($93C8-$93C9)
MAGIC_PANEL_BITMAP_BYTES = 64 * 12
MAGIC_PANEL_HALF_BYTES = 30 * 12
MAGIC_PANEL_RIGHT_SOURCE = 0x9000 + MAGIC_PANEL_HALF_BYTES
MAGIC_PANEL_PASS_DESTS = (0x6500, 0x66E0, 0x68C0, 0x6AA0, 0x6C80, 0x6E60)


def _emit_mul12_from_a16(a: MiniAssembler) -> None:
    """A16 *= 12 using status-private WRAM; X/Y and the stack are untouched."""
    a.emit(0x0A, 0x0A)                              # *4
    a.emit(0x8D, STATUS_MUL_TEMP & 0xFF, STATUS_MUL_TEMP >> 8)
    a.emit(0x0A)                                    # *8
    a.emit(0x18)                                    # CLC
    a.emit(0x6D, STATUS_MUL_TEMP & 0xFF, STATUS_MUL_TEMP >> 8)  # + *4 => *12


def make_skill_progress_format_helper() -> bytes:
    """Compact one/two-digit skill progress and append one fixed blank.

    Input matches stock C7:5AFC: Y16 is the numeric value and X16 is the next
    byte in the transient $7E:9C00 row buffer. Reuse the stock decimal splitter
    at C7:5D17, but omit its leading blank when the tens digit is zero. Always
    append one $80 blank after the value, so rows become `5:0 name` /
    `5:52 name` instead of `5: 0name` / `5:52name`.
    """
    a = MiniAssembler(SKILL_PROGRESS_FORMAT_HELPER_CPU)
    a.emit(0x20, 0x17, 0x5D)                       # JSR $5D17 (stock decimal split)
    a.emit(0xAD, 0x38, 0xA2)                       # LDA $A238 (tens glyph or 0)
    a.rel8(0xD0, "two_digits")
    a.emit(0xAD, 0x39, 0xA2)                       # one digit: write ones only
    a.emit(0x9D, 0x00, 0x9C)
    a.emit(0xE8)
    a.rel8(0x80, "gap")
    a.label("two_digits")
    a.emit(0x9D, 0x00, 0x9C)                       # tens
    a.emit(0xE8)
    a.emit(0xAD, 0x39, 0xA2)                       # ones
    a.emit(0x9D, 0x00, 0x9C)
    a.emit(0xE8)
    a.label("gap")
    a.emit(0xA9, SKILL_BLANK)                      # exactly one cell before name
    a.emit(0x9D, 0x00, 0x9C)
    a.emit(0xE8)
    a.emit(0x60)
    return a.resolve()


def make_skill_submit_wrapper() -> bytes:
    """Scope skill-name VWF around the exact stock 8-row submit.

    C7:65B0 and C7:6615 are the magic/weapon list batch submits. The row
    builder has already assembled all eight transient strings at $7E:9C00.
    Keep a private scope byte live for the synchronous C7:5D9A parse/render
    loop, then clear it on return.
    """
    a = MiniAssembler(SKILL_SUBMIT_WRAPPER_CPU)
    a.emit(0xA9, SKILL_ROW_MAGIC)
    a.emit(0x8F, *lo24(0x7E0000 | SKILL_ROW_SCOPE))
    a.emit(0x20, 0x9A, 0x5D)                       # stock JSR $5D9A
    a.emit(0xA9, 0x00)
    a.emit(0x8F, *lo24(0x7E0000 | SKILL_ROW_SCOPE))
    a.emit(0x60)
    return a.resolve()


def make_skill_vwf_converter_dispatch() -> bytes:
    """VWF-render only weapon/magic list names, then resume stock tile packing.

    Runtime probes proved that the exact compact prefix is present in the
    decoded $A1A4 row but is not anchored at cell 0.  The exact 8-row batch
    scope therefore gates this helper first, then the helper scans up to 28
    decoded cells for `d:d blank` or `d:dd blank`.  On a match X becomes the
    real name-start cell: the fixed prefix is left untouched, only the old
    fixed-font name bitmap is cleared, and the already-decoded name is rendered
    proportionally using the ordinary validated UI metrics.  Every non-match
    jumps directly into the unchanged Status classifier at ED:8700.
    """
    a = MiniAssembler(SKILL_VWF_HELPER_CPU)

    # Exact synchronous skill-list batch scope.  The submit wrapper keeps this
    # live across all eight C7:5D9A iterations and clears it only on return.
    a.emit(0xE2, 0x20)                              # SEP #$20 (A8)
    a.emit(0xAF, *lo24(0x7E0000 | SKILL_ROW_SCOPE))
    a.emit(0xC9, SKILL_ROW_MAGIC)
    a.rel8(0xF0, "scope_ok")
    a.emit(0x5C, *lo24(STATUS_VWF_HELPER_CPU))
    a.label("scope_ok")

    # Probe 03/04 validated this dynamic decoded-row prefix search.
    a.emit(0xC2, 0x10)                              # REP #$10 (X/Y16)
    a.emit(0xA2, 0x00, 0x00)                       # LDX #0
    a.label("scan")

    a.emit(0xBF, *lo24(0x7E0000 | STOCK_BUFFER))   # digit
    a.emit(0xC9, SKILL_DIGIT_FIRST)
    a.rel8(0x90, "next")
    a.emit(0xC9, SKILL_DIGIT_AFTER_LAST)
    a.rel8(0xB0, "next")

    a.emit(0xBF, *lo24(0x7E0000 | (STOCK_BUFFER + 1)))  # ':'
    a.emit(0xC9, SKILL_COLON)
    a.rel8(0xD0, "next")

    a.emit(0xBF, *lo24(0x7E0000 | (STOCK_BUFFER + 2)))  # first progress digit
    a.emit(0xC9, SKILL_DIGIT_FIRST)
    a.rel8(0x90, "next")
    a.emit(0xC9, SKILL_DIGIT_AFTER_LAST)
    a.rel8(0xB0, "next")

    # d:d blank -> name starts scan+4.
    a.emit(0xBF, *lo24(0x7E0000 | (STOCK_BUFFER + 3)))
    a.emit(0xC9, SKILL_BLANK)
    a.rel8(0xF0, "single")

    # d:dd blank -> name starts scan+5.
    a.emit(0xC9, SKILL_DIGIT_FIRST)
    a.rel8(0x90, "next")
    a.emit(0xC9, SKILL_DIGIT_AFTER_LAST)
    a.rel8(0xB0, "next")
    a.emit(0xBF, *lo24(0x7E0000 | (STOCK_BUFFER + 4)))
    a.emit(0xC9, SKILL_BLANK)
    a.rel8(0xD0, "next")
    a.emit(0xE8, 0xE8, 0xE8, 0xE8, 0xE8)           # X += 5
    a.rel8(0x80, "have_name_cell")

    a.label("single")
    a.emit(0xE8, 0xE8, 0xE8, 0xE8)                 # X += 4
    a.rel8(0x80, "have_name_cell")

    a.label("next")
    a.emit(0xE8)
    a.emit(0xE0, SKILL_PREFIX_SCAN_MAX, 0x00)
    a.rel8(0x90, "scan")
    a.emit(0x5C, *lo24(STATUS_VWF_HELPER_CPU))      # no exact prefix

    a.label("have_name_cell")
    # X is the true decoded/bitmap name-start cell.
    a.emit(0x8E, STATUS_SRC_OFFSET & 0xFF, STATUS_SRC_OFFSET >> 8)

    # Reject cell 32+ (outside the representable 32-cell stock row bitmap).
    a.emit(0xE0, 0x20, 0x00)
    a.rel8(0x90, "cell_ok")
    a.emit(0x5C, *lo24(STATUS_VWF_HELPER_CPU))
    a.label("cell_ok")

    # pixel_cursor = name_cell * 8.
    a.emit(0xC2, 0x20)                              # REP #$20
    a.emit(0x8A)                                    # TXA
    a.emit(0x0A, 0x0A, 0x0A)                       # *8
    a.emit(0xE2, 0x20)                              # SEP #$20
    a.emit(0x8D, PIXEL_CURSOR & 0xFF, PIXEL_CURSOR >> 8)

    # char_count = decoded_count - name_start.
    a.emit(0xAF, *lo24(0x7E0000 | DECODED_COUNT))
    a.emit(0x29, 0x7F)
    a.emit(0x38)                                    # SEC
    a.emit(0xED, STATUS_SRC_OFFSET & 0xFF, STATUS_SRC_OFFSET >> 8)
    a.rel8(0x90, "count_bad")                       # BCC underflow
    a.rel8(0xF0, "count_bad")                       # BEQ empty
    a.emit(0x8D, STATUS_CHAR_COUNT & 0xFF, STATUS_CHAR_COUNT >> 8)
    a.rel8(0x80, "count_ok")
    a.label("count_bad")
    a.emit(0x5C, *lo24(STATUS_VWF_HELPER_CPU))
    a.label("count_ok")

    # Clear old fixed-font name bitmap from name_cell*12 through the end.
    a.emit(0xC2, 0x20)                              # A16
    a.emit(0xAD, STATUS_SRC_OFFSET & 0xFF, STATUS_SRC_OFFSET >> 8)
    _emit_mul12_from_a16(a)
    a.emit(0xAA)                                    # X = bitmap byte offset
    a.emit(0xA9, 0x00, 0x00)
    a.label("clear_name")
    a.emit(0x9F, *lo24(0x7E9000))                   # STA.l $7E9000,X
    a.emit(0xE8, 0xE8)
    a.emit(0xE0, SKILL_BITMAP_BYTES & 0xFF, SKILL_BITMAP_BYTES >> 8)
    a.rel8(0xD0, "clear_name")
    a.emit(0xE2, 0x20)                              # A8

    a.label("char_loop")
    # Fetch one already-decoded glyph from the true dynamic source offset.
    a.emit(0xAE, STATUS_SRC_OFFSET & 0xFF, STATUS_SRC_OFFSET >> 8)
    a.emit(0xBF, *lo24(0x7E0000 | STOCK_BUFFER))
    a.emit(0x8D, STATUS_GLYPH & 0xFF, STATUS_GLYPH >> 8)
    a.emit(0xEE, STATUS_SRC_OFFSET & 0xFF, STATUS_SRC_OFFSET >> 8)

    # X = (glyph-$80)*12 in the stock/french font.
    a.emit(0xC2, 0x20)
    a.emit(0xAD, STATUS_GLYPH & 0xFF, STATUS_GLYPH >> 8)
    a.emit(0x29, 0xFF, 0x00)
    a.emit(0x38)
    a.emit(0xE9, 0x80, 0x00)
    _emit_mul12_from_a16(a)
    a.emit(0xAA)

    # Y = floor(pixel_cursor/8)*12 in stock bitmap $9000.
    a.emit(0xE2, 0x20)
    a.emit(0xAD, PIXEL_CURSOR & 0xFF, PIXEL_CURSOR >> 8)
    a.emit(0x4A, 0x4A, 0x4A)
    a.emit(0xC2, 0x20)
    a.emit(0x29, 0xFF, 0x00)
    _emit_mul12_from_a16(a)
    a.emit(0xA8)
    a.emit(0xE2, 0x20)

    # Same compositor already used by the validated UI VWF paths.
    a.emit(0xA9, 0x0C)
    a.emit(0x8D, STATUS_ROW_COUNT & 0xFF, STATUS_ROW_COUNT >> 8)
    a.label("row_loop")
    a.emit(0x22, *lo24(0xC74560))
    a.emit(0x99, 0x00, 0x90)                       # DB remains $7E
    a.emit(0xE8, 0xC8)
    a.emit(0xCE, STATUS_ROW_COUNT & 0xFF, STATUS_ROW_COUNT >> 8)
    a.rel8(0xD0, "row_loop")

    # Validated ordinary UI VWF advance table.
    a.emit(0xAD, STATUS_GLYPH & 0xFF, STATUS_GLYPH >> 8)
    a.emit(0x29, 0x7F)
    a.emit(0xC2, 0x20)
    a.emit(0x29, 0xFF, 0x00)
    a.emit(0xAA)
    a.emit(0xE2, 0x20)
    a.emit(0xBF, *lo24(STATUS_WIDTH_TABLE_CPU))
    a.emit(0x18)
    a.emit(0x6D, PIXEL_CURSOR & 0xFF, PIXEL_CURSOR >> 8)
    a.emit(0x8D, PIXEL_CURSOR & 0xFF, PIXEL_CURSOR >> 8)

    a.emit(0xCE, STATUS_CHAR_COUNT & 0xFF, STATUS_CHAR_COUNT >> 8)
    a.rel8(0xD0, "char_loop")

    # Replay replaced C0:2366 prologue, then untouched stock tile packing.
    a.emit(0xE2, 0x20)
    a.emit(0xC2, 0x10)
    a.emit(0xA2, 0x00, 0x00)
    a.emit(0xA0, 0x00, 0x00)
    a.emit(0x5C, *lo24(STATUS_BITMAP_CONVERT_RESUME_CPU))
    return a.resolve()

def make_magic_panel_reset_helper() -> bytes:
    """Invalidate captured magic IDs before stock rebuilds the lower panel."""
    a = MiniAssembler(MAGIC_PANEL_RESET_HELPER_CPU)
    a.emit(0xA9, 0xFF)
    for addr in (MAGIC_PANEL_ID0, MAGIC_PANEL_ID0 + 1, MAGIC_PANEL_ID0 + 2):
        a.emit(0x8F, *lo24(0x7E0000 | addr))
    a.emit(0xA9, 0x00)
    a.emit(0x8F, *lo24(0x7E0000 | MAGIC_PANEL_CAPTURE_COUNT))
    a.emit(0x6B)  # RTL
    return a.resolve()


def make_magic_panel_reset_stub() -> bytes:
    """Run the private reset, then preserve stock C7:6BCF preparation."""
    a = MiniAssembler(MAGIC_PANEL_RESET_STUB_CPU)
    a.emit(0x22, *lo24(MAGIC_PANEL_RESET_HELPER_CPU))
    a.emit(0x20, 0xCF, 0x6B)
    a.emit(0x60)
    return a.resolve()


def make_magic_panel_capture_helper() -> bytes:
    """Capture the exact stock magic-description IDs in emission order.

    Stock uses raw $A1D0 values 42..47 for Lumina and subtracts six before
    indexing the shared special magic resources. Mirror that mapping here so
    captured IDs always address the canonical 0..41 French row table.
    """
    a = MiniAssembler(MAGIC_PANEL_CAPTURE_HELPER_CPU)
    a.emit(0xAF, *lo24(0x7E0000 | MAGIC_PANEL_CAPTURE_COUNT))
    a.emit(0xC9, 0x00)
    a.rel8(0xF0, "slot0")
    a.emit(0xC9, 0x01)
    a.rel8(0xF0, "slot1")
    a.emit(0xC9, 0x02)
    a.rel8(0xF0, "slot2")
    a.rel8(0x80, "done")
    for slot in range(3):
        a.label(f"slot{slot}")
        a.emit(0xAF, *lo24(0x7E0000 | 0xA1D0))
        a.emit(0xC9, 0x2A)                    # raw Lumina starts at 42
        a.rel8(0x90, f"mapped{slot}")
        a.emit(0x38)                          # SEC
        a.emit(0xE9, 0x06)                    # 42..47 -> 36..41
        a.label(f"mapped{slot}")
        a.emit(0x8F, *lo24(0x7E0000 | (MAGIC_PANEL_ID0 + slot)))
        a.rel8(0x80, "inc")
    a.label("inc")
    a.emit(0xAF, *lo24(0x7E0000 | MAGIC_PANEL_CAPTURE_COUNT))
    a.emit(0x1A)
    a.emit(0x8F, *lo24(0x7E0000 | MAGIC_PANEL_CAPTURE_COUNT))
    a.label("done")
    a.emit(0x6B)
    return a.resolve()


def make_magic_panel_capture_stub() -> bytes:
    """Capture A1D0 at the exact stock copy call, then replay C7:6AB7."""
    a = MiniAssembler(MAGIC_PANEL_CAPTURE_STUB_CPU)
    a.emit(0x22, *lo24(MAGIC_PANEL_CAPTURE_HELPER_CPU))
    a.emit(0x20, 0xB7, 0x6A)
    a.emit(0x60)
    return a.resolve()


def make_magic_panel_batch_helper() -> tuple[bytes, int]:
    """Clone stock C7:6512 + C7:5D9A and return its unique C0:2ADB return.

    Keeping the stock six-pass lifecycle, waits, DMA and tail processing avoids
    the menu lockups observed in the rejected direct-DMA experiment.  The unique
    JSL return address is the exact-caller discriminator used by the global
    bitmap-converter dispatcher, which keeps GAME SELECT isolated.
    """
    a = MiniAssembler(MAGIC_PANEL_BATCH_HELPER_CPU)
    a.emit(0xDA)
    a.emit(0xA2, 0x00, 0x65); a.emit(0x8E, 0x8C, 0xA1)
    a.emit(0xA2, 0xC0, 0x03); a.emit(0x8E, 0x91, 0xA1)
    a.emit(0xA2, 0xE0, 0x01); a.emit(0x8E, 0x99, 0xA1)
    a.emit(0xA9, 0x06); a.emit(0x8D, 0x71, 0xA1)
    a.emit(0xFA)
    a.label("batch")
    a.emit(0x9E, 0x00, 0x9C)
    a.emit(0xA9, 0x7E); a.emit(0x8F, *lo24(0x001D03))
    a.emit(0xC2, 0x20); a.emit(0xA9, 0x00, 0x9C); a.emit(0x8F, *lo24(0x001D01))
    a.emit(0xE2, 0x20)
    a.emit(0x9C, 0xC5, 0xA1)
    a.emit(0xA9, 0x01); a.emit(0x1C, 0x12, 0xA2)
    a.emit(0xA9, 0x00); a.emit(0x8F, *lo24(0x001D00))
    jsl_2adb_cpu = a.pc
    a.emit(0x22, *lo24(0xC02ADB))
    a.emit(0x22, *lo24(0xC02AEA))
    a.emit(0x22, *lo24(0xC02ADF))
    a.emit(0xC2, 0x20)
    a.emit(0xAD, 0x8C, 0xA1); a.emit(0x18); a.emit(0x6D, 0x99, 0xA1); a.emit(0x8D, 0x8C, 0xA1)
    a.emit(0xE2, 0x20)
    a.emit(0xCE, 0x71, 0xA1); a.rel8(0xD0, "batch")
    a.emit(0x22, *lo24(0xC02AE3))
    a.emit(0xAD, 0x02, 0xA2); a.emit(0x48)
    a.emit(0xA9, 0x06); a.emit(0x8D, 0x02, 0xA2)
    a.emit(0x22, *lo24(0xC757DC))
    a.emit(0x68); a.emit(0x8D, 0x02, 0xA2)
    a.emit(0xA9, 0x40); a.emit(0x0C, 0x0A, 0xA2)
    a.emit(0x60)
    return a.resolve(), (jsl_2adb_cpu + 3) & 0xFFFF


def make_magic_panel_dispatch(expected_return: int) -> bytes:
    """Render three complete 480px `Nom : description` rows, stock-flow safe.

    The stock panel submits six 30-cell halves.  IDs are captured from stock's
    own availability-controlled builder.  Each logical row is VWF-rasterized
    across 60 cells, then sliced after rasterization into the left/right stock
    passes.  Missing IDs render an explicit blank row; this covers locked
    elementals and Dryad's gated third Mana spell without stale bitmap reuse.

    Non-magic C0:2366 calls jump straight into the already-validated skill-row
    dispatcher.  Even the exact magic caller falls back to the stock converter
    when french_resources' source marker is absent, keeping vwf_ui standalone
    content-neutral.
    """
    a = MiniAssembler(MAGIC_PANEL_DISPATCH_CPU)
    a.emit(0xE2, 0x20)                              # A8
    a.emit(0xC2, 0x20)
    a.emit(0xA3, 0x05)                              # stacked return low word
    a.emit(0xC9, expected_return & 0xFF, expected_return >> 8)
    a.emit(0xE2, 0x20)
    a.rel8(0xD0, "not_magic")
    a.emit(0xA3, 0x07)                              # stacked program bank
    a.emit(0xC9, 0xC7)
    a.rel8(0xD0, "not_magic")
    a.rel8(0x80, "caller_ok")
    a.label("not_magic")
    a.emit(0x5C, *lo24(SKILL_VWF_HELPER_CPU))

    a.label("caller_ok")
    # Runtime content gate: only french_resources owns/installs the row table.
    for offset, value in enumerate(MAGIC_PANEL_MARKER):
        a.emit(0xAF, *lo24(MAGIC_PANEL_MARKER_CPU + offset))
        a.emit(0xC9, value)
        a.rel8(0xD0, "marker_fail")
    a.rel8(0x80, "magic")
    a.label("marker_fail")
    a.rel16(0x82, "fallback_stock")

    a.label("magic")
    a.emit(0xC2, 0x30)                              # A/X/Y16
    for idx, dest in enumerate(MAGIC_PANEL_PASS_DESTS):
        row = idx // 2
        half = idx & 1
        a.emit(0xAD, 0x8C, 0xA1)
        a.emit(0xC9, dest & 0xFF, dest >> 8)
        a.rel8(0xD0, f"next_pass_{idx}")
        a.emit(0xE2, 0x20)
        a.emit(0xA9, half)
        a.emit(0x8D, MAGIC_PANEL_HALF_FLAG & 0xFF, MAGIC_PANEL_HALF_FLAG >> 8)
        a.emit(0xAF, *lo24(0x7E0000 | (MAGIC_PANEL_ID0 + row)))
        a.emit(0xC9, MAGIC_PANEL_RECORD_COUNT)
        a.rel8(0x90, f"id_ok_{idx}")
        a.rel16(0x82, "blank_known_row")
        a.label(f"id_ok_{idx}")
        # X = id * 80 = id * (16 + 64).
        a.emit(0xC2, 0x20)
        a.emit(0x29, 0xFF, 0x00)
        a.emit(0x0A, 0x0A, 0x0A, 0x0A)             # *16
        a.emit(0x8D, STATUS_MUL_TEMP & 0xFF, STATUS_MUL_TEMP >> 8)
        a.emit(0x0A, 0x0A)                         # *64
        a.emit(0x18)
        a.emit(0x6D, STATUS_MUL_TEMP & 0xFF, STATUS_MUL_TEMP >> 8)
        a.emit(0xAA)
        a.rel16(0x82, "record_ready")
        a.label(f"next_pass_{idx}")
    a.rel16(0x82, "fallback_stock")

    # Missing logical row inside one of the six proven passes: blank it instead
    # of letting stale stock bitmap data duplicate another spell.
    a.label("blank_known_row")
    a.emit(0xC2, 0x20)
    a.emit(0xA9, 0x00, 0x00)
    a.emit(0xA2, 0x00, 0x00)
    a.label("blank_clear")
    a.emit(0x9F, *lo24(0x7E9000))
    a.emit(0xE8, 0xE8)
    a.emit(0xE0, MAGIC_PANEL_BITMAP_BYTES & 0xFF, MAGIC_PANEL_BITMAP_BYTES >> 8)
    a.rel8(0x90, "blank_clear")
    a.emit(0xE2, 0x20)
    a.emit(0xC2, 0x10)
    a.emit(0xA2, 0x00, 0x00)
    a.emit(0xA0, 0x00, 0x00)
    a.emit(0x5C, *lo24(STATUS_BITMAP_CONVERT_RESUME_CPU))

    # Conservative stock conversion for marker absence or unexpected geometry.
    a.label("fallback_stock")
    a.emit(0xE2, 0x20)
    a.emit(0xC2, 0x10)
    a.emit(0xA2, 0x00, 0x00)
    a.emit(0xA0, 0x00, 0x00)
    a.emit(0x5C, *lo24(STATUS_BITMAP_CONVERT_RESUME_CPU))

    a.label("record_ready")
    a.emit(0xE2, 0x20)
    a.emit(0xBF, *lo24(MAGIC_PANEL_DATA_CPU))        # record length, indexed by X
    a.emit(0x8D, STATUS_CHAR_COUNT & 0xFF, STATUS_CHAR_COUNT >> 8)
    a.emit(0xE8)
    a.emit(0x8E, STATUS_SRC_OFFSET & 0xFF, STATUS_SRC_OFFSET >> 8)

    # Clear the full 64-cell source bitmap consumed by the stock converter.
    a.emit(0xC2, 0x20)
    a.emit(0xA9, 0x00, 0x00)
    a.emit(0xA2, 0x00, 0x00)
    a.label("clear_full")
    a.emit(0x9F, *lo24(0x7E9000))
    a.emit(0xE8, 0xE8)
    a.emit(0xE0, MAGIC_PANEL_BITMAP_BYTES & 0xFF, MAGIC_PANEL_BITMAP_BYTES >> 8)
    a.rel8(0x90, "clear_full")

    # 16-bit pixel cursor; +1px preserves the validated left outline inset.
    a.emit(0xA9, 0x01, 0x00)
    a.emit(0x8D, MAGIC_PANEL_LONG_CURSOR & 0xFF, MAGIC_PANEL_LONG_CURSOR >> 8)
    a.emit(0xE2, 0x20)

    a.label("chars")
    a.emit(0xAE, STATUS_SRC_OFFSET & 0xFF, STATUS_SRC_OFFSET >> 8)
    a.emit(0xBF, *lo24(MAGIC_PANEL_DATA_CPU))
    a.emit(0x8D, STATUS_GLYPH & 0xFF, STATUS_GLYPH >> 8)
    a.emit(0xE8)
    a.emit(0x8E, STATUS_SRC_OFFSET & 0xFF, STATUS_SRC_OFFSET >> 8)

    # X = (glyph-$80) * 12.
    a.emit(0xC2, 0x20)
    a.emit(0xAD, STATUS_GLYPH & 0xFF, STATUS_GLYPH >> 8)
    a.emit(0x29, 0xFF, 0x00)
    a.emit(0x38)
    a.emit(0xE9, 0x80, 0x00)
    _emit_mul12_from_a16(a)
    a.emit(0xAA)

    # Y = floor(long_cursor/8) * 12.
    a.emit(0xAD, MAGIC_PANEL_LONG_CURSOR & 0xFF, MAGIC_PANEL_LONG_CURSOR >> 8)
    a.emit(0x4A, 0x4A, 0x4A)
    _emit_mul12_from_a16(a)
    a.emit(0xA8)

    # Shared row compositor only needs cursor modulo 8 in the low byte.
    a.emit(0xE2, 0x20)
    a.emit(0xAD, MAGIC_PANEL_LONG_CURSOR & 0xFF, MAGIC_PANEL_LONG_CURSOR >> 8)
    a.emit(0x8D, PIXEL_CURSOR & 0xFF, PIXEL_CURSOR >> 8)
    a.emit(0xA9, 0x0C)
    a.emit(0x8D, STATUS_ROW_COUNT & 0xFF, STATUS_ROW_COUNT >> 8)
    a.label("glyph_rows")
    a.emit(0x22, *lo24(0xC74560))
    a.emit(0x99, 0x00, 0x90)
    a.emit(0xE8, 0xC8)
    a.emit(0xCE, STATUS_ROW_COUNT & 0xFF, STATUS_ROW_COUNT >> 8)
    a.rel8(0xD0, "glyph_rows")

    # Zero-extend validated width and add it to the 16-bit logical cursor.
    a.emit(0xAD, STATUS_GLYPH & 0xFF, STATUS_GLYPH >> 8)
    a.emit(0x29, 0x7F)
    a.emit(0xC2, 0x20)
    a.emit(0x29, 0xFF, 0x00)
    a.emit(0xAA)
    a.emit(0xE2, 0x20)
    a.emit(0xBF, *lo24(STATUS_WIDTH_TABLE_CPU))
    a.emit(0x8D, MAGIC_PANEL_WIDTH_TEMP & 0xFF, MAGIC_PANEL_WIDTH_TEMP >> 8)
    a.emit(0x9C, (MAGIC_PANEL_WIDTH_TEMP + 1) & 0xFF, (MAGIC_PANEL_WIDTH_TEMP + 1) >> 8)
    a.emit(0xC2, 0x20)
    a.emit(0xAD, MAGIC_PANEL_LONG_CURSOR & 0xFF, MAGIC_PANEL_LONG_CURSOR >> 8)
    a.emit(0x18)
    a.emit(0x6D, MAGIC_PANEL_WIDTH_TEMP & 0xFF, MAGIC_PANEL_WIDTH_TEMP >> 8)
    a.emit(0x8D, MAGIC_PANEL_LONG_CURSOR & 0xFF, MAGIC_PANEL_LONG_CURSOR >> 8)
    a.emit(0xE2, 0x20)
    a.emit(0xCE, STATUS_CHAR_COUNT & 0xFF, STATUS_CHAR_COUNT >> 8)
    a.rel8(0xD0, "chars")

    # Split the 60-cell logical bitmap into two stock 30-cell DMA passes.
    a.emit(0xAD, MAGIC_PANEL_HALF_FLAG & 0xFF, MAGIC_PANEL_HALF_FLAG >> 8)
    a.rel8(0xD0, "right_half")

    # Left pass: cells 0..29 remain in place; clear cells 30..63.
    a.emit(0xC2, 0x20)
    a.emit(0xA9, 0x00, 0x00)
    a.emit(0xA2, MAGIC_PANEL_HALF_BYTES & 0xFF, MAGIC_PANEL_HALF_BYTES >> 8)
    a.label("clear_tail_left")
    a.emit(0x9F, *lo24(0x7E9000))
    a.emit(0xE8, 0xE8)
    a.emit(0xE0, MAGIC_PANEL_BITMAP_BYTES & 0xFF, MAGIC_PANEL_BITMAP_BYTES >> 8)
    a.rel8(0x90, "clear_tail_left")
    a.rel8(0x80, "resume")

    # Right pass: copy logical cells 30..59 down to stock cells 0..29.
    a.label("right_half")
    a.emit(0xC2, 0x20)
    a.emit(0xA2, 0x00, 0x00)
    a.label("copy_right")
    a.emit(0xBF, *lo24(0x7E0000 | MAGIC_PANEL_RIGHT_SOURCE))
    a.emit(0x9F, *lo24(0x7E9000))
    a.emit(0xE8, 0xE8)
    a.emit(0xE0, MAGIC_PANEL_HALF_BYTES & 0xFF, MAGIC_PANEL_HALF_BYTES >> 8)
    a.rel8(0x90, "copy_right")
    a.emit(0xA9, 0x00, 0x00)
    a.emit(0xA2, MAGIC_PANEL_HALF_BYTES & 0xFF, MAGIC_PANEL_HALF_BYTES >> 8)
    a.label("clear_tail_right")
    a.emit(0x9F, *lo24(0x7E9000))
    a.emit(0xE8, 0xE8)
    a.emit(0xE0, MAGIC_PANEL_BITMAP_BYTES & 0xFF, MAGIC_PANEL_BITMAP_BYTES >> 8)
    a.rel8(0x90, "clear_tail_right")

    a.label("resume")
    a.emit(0xE2, 0x20)
    a.emit(0xC2, 0x10)
    a.emit(0xA2, 0x00, 0x00)
    a.emit(0xA0, 0x00, 0x00)
    a.emit(0x5C, *lo24(STATUS_BITMAP_CONVERT_RESUME_CPU))
    return a.resolve()


def make_status_vwf_render_slot() -> bytes:
    """Render one exact Status label into temporary bitmap $9180.

    Input: A8 = slot index 0..9.  Localized prose remains owned by
    french_menus in ten fixed-size direct-glyph records at ED:8B00; vwf_ui
    consumes only the record length and glyph bytes.
    """
    a = MiniAssembler(STATUS_VWF_RENDER_SLOT_CPU)

    a.emit(0xE2, 0x20)                              # SEP #$20
    a.emit(0xC2, 0x10)                              # REP #$10 (16-bit X/Y)
    a.emit(0x8D, STATUS_GLYPH & 0xFF, STATUS_GLYPH >> 8)  # save slot id temporarily

    # Clear 11 temporary logical cells (10-cell slot + one spill cell).
    a.emit(0xC2, 0x20)                              # REP #$20
    a.emit(0xA9, 0x00, 0x00)
    a.emit(0xA2, STATUS_TEMP_BITMAP_OFFSET & 0xFF, STATUS_TEMP_BITMAP_OFFSET >> 8)
    a.label("clear_temp")
    a.emit(0x9D, 0x00, 0x90)                       # STA $9000,X
    a.emit(0xE8, 0xE8)                              # INX / INX
    a.emit(0xE0, (STATUS_TEMP_BITMAP_OFFSET + STATUS_TEMP_BITMAP_BYTES) & 0xFF,
           ((STATUS_TEMP_BITMAP_OFFSET + STATUS_TEMP_BITMAP_BYTES) >> 8) & 0xFF)
    a.rel8(0xD0, "clear_temp")
    a.emit(0xE2, 0x20)                              # SEP #$20

    # Resolve slot -> 16-byte localization-owned VWF record.  Byte 0 is the
    # direct-glyph count; bytes 1..15 are the label payload.
    a.emit(0xAD, STATUS_GLYPH & 0xFF, STATUS_GLYPH >> 8)
    a.emit(0xC2, 0x20)                              # REP #$20
    a.emit(0x29, 0xFF, 0x00)
    a.emit(0x0A, 0x0A, 0x0A, 0x0A)                # slot * 16
    a.emit(0xAA)                                    # TAX = record offset
    a.emit(0x1A)                                    # INC A -> first glyph offset
    a.emit(0x8D, STATUS_SRC_OFFSET & 0xFF, STATUS_SRC_OFFSET >> 8)
    a.emit(0xE2, 0x20)
    a.emit(0xBF, *lo24(STATUS_VWF_LABEL_TABLE_CPU)) # LDA.l record length,X
    a.emit(0x8D, STATUS_CHAR_COUNT & 0xFF, STATUS_CHAR_COUNT >> 8)
    a.emit(0xA9, 0x01)
    a.emit(0x8D, PIXEL_CURSOR & 0xFF, PIXEL_CURSOR >> 8)  # same validated +1px inset

    a.label("char_loop")
    # Fetch one direct glyph from french_menus' full-label table.
    a.emit(0xAE, STATUS_SRC_OFFSET & 0xFF, STATUS_SRC_OFFSET >> 8)  # LDX src offset
    a.emit(0xBF, *lo24(STATUS_VWF_LABEL_TABLE_CPU))  # LDA.l ED:8B00,X
    a.emit(0x8D, STATUS_GLYPH & 0xFF, STATUS_GLYPH >> 8)
    a.emit(0xEE, STATUS_SRC_OFFSET & 0xFF, STATUS_SRC_OFFSET >> 8)  # INC low offset

    # X = (glyph - $80) * 12, stock-font row offset.
    a.emit(0xC2, 0x20)                              # REP #$20
    a.emit(0xAD, STATUS_GLYPH & 0xFF, STATUS_GLYPH >> 8)
    a.emit(0x29, 0xFF, 0x00)
    a.emit(0x38)
    a.emit(0xE9, 0x80, 0x00)
    _emit_mul12_from_a16(a)
    a.emit(0xAA)                                    # TAX

    # Y = temp base + floor(pixel_cursor / 8) * 12.
    a.emit(0xE2, 0x20)                              # SEP #$20
    a.emit(0xAD, PIXEL_CURSOR & 0xFF, PIXEL_CURSOR >> 8)
    a.emit(0x4A, 0x4A, 0x4A)
    a.emit(0xC2, 0x20)
    a.emit(0x29, 0xFF, 0x00)
    _emit_mul12_from_a16(a)
    a.emit(0x18)
    a.emit(0x69, STATUS_TEMP_BITMAP_OFFSET & 0xFF, STATUS_TEMP_BITMAP_OFFSET >> 8)
    a.emit(0xA8)                                    # TAY
    a.emit(0xE2, 0x20)

    # Composite all 12 font rows through the already-validated shared helper.
    a.emit(0xA9, 0x0C)
    a.emit(0x8D, STATUS_ROW_COUNT & 0xFF, STATUS_ROW_COUNT >> 8)
    a.label("row_loop")
    a.emit(0x22, *lo24(0xC74560))                   # JSL shared stock-row VWF helper
    a.emit(0x99, 0x00, 0x90)                       # STA $9000,Y
    a.emit(0xE8, 0xC8)                              # INX / INY
    a.emit(0xCE, STATUS_ROW_COUNT & 0xFF, STATUS_ROW_COUNT >> 8)
    a.rel8(0xD0, "row_loop")

    # Advance the local pixel cursor with vwf_ui's validated width table.
    a.emit(0xAD, STATUS_GLYPH & 0xFF, STATUS_GLYPH >> 8)
    a.emit(0x29, 0x7F)                              # code $80-$FF -> index 0-$7F
    a.emit(0xC2, 0x20)
    a.emit(0x29, 0xFF, 0x00)
    a.emit(0xAA)
    a.emit(0xE2, 0x20)
    a.emit(0xBF, *lo24(STATUS_WIDTH_TABLE_CPU))      # LDA.l $ED:7D00,X
    a.emit(0x18)
    a.emit(0x6D, PIXEL_CURSOR & 0xFF, PIXEL_CURSOR >> 8)
    a.emit(0x8D, PIXEL_CURSOR & 0xFF, PIXEL_CURSOR >> 8)

    a.emit(0xCE, STATUS_CHAR_COUNT & 0xFF, STATUS_CHAR_COUNT >> 8)
    a.rel8(0xD0, "char_loop")
    a.emit(0x60)                                    # RTS (same-bank local subroutine)
    return a.resolve()


def make_status_vwf_copy_cells() -> bytes:
    """Copy contiguous 12-byte bitmap cells from temporary slot to stock chunk."""
    a = MiniAssembler(STATUS_VWF_COPY_CELLS_CPU)
    a.emit(0xE2, 0x20)                              # SEP #$20
    a.emit(0xC2, 0x10)                              # REP #$10

    # X = $9180 + src_cell * 12.
    a.emit(0xAD, STATUS_COPY_SRC_CELL & 0xFF, STATUS_COPY_SRC_CELL >> 8)
    a.emit(0xC2, 0x20)
    a.emit(0x29, 0xFF, 0x00)
    _emit_mul12_from_a16(a)
    a.emit(0x18)
    a.emit(0x69, 0x80, 0x91)
    a.emit(0xAA)

    # Y = $9000 + dst_cell * 12.
    a.emit(0xE2, 0x20)
    a.emit(0xAD, STATUS_COPY_DST_CELL & 0xFF, STATUS_COPY_DST_CELL >> 8)
    a.emit(0xC2, 0x20)
    a.emit(0x29, 0xFF, 0x00)
    _emit_mul12_from_a16(a)
    a.emit(0x18)
    a.emit(0x69, 0x00, 0x90)
    a.emit(0xA8)

    # byte_count = cell_count * 12 (max 120, so one byte is sufficient).
    a.emit(0xE2, 0x20)
    a.emit(0xAD, STATUS_COPY_CELL_COUNT & 0xFF, STATUS_COPY_CELL_COUNT >> 8)
    a.emit(0xC2, 0x20)
    a.emit(0x29, 0xFF, 0x00)
    _emit_mul12_from_a16(a)
    a.emit(0xE2, 0x20)
    a.emit(0x8D, STATUS_COPY_BYTE_COUNT & 0xFF, STATUS_COPY_BYTE_COUNT >> 8)

    a.label("copy_loop")
    a.emit(0xBD, 0x00, 0x00)                       # LDA $0000,X (DBR=$7E)
    a.emit(0x99, 0x00, 0x00)                       # STA $0000,Y
    a.emit(0xE8, 0xC8)
    a.emit(0xCE, STATUS_COPY_BYTE_COUNT & 0xFF, STATUS_COPY_BYTE_COUNT >> 8)
    a.rel8(0xD0, "copy_loop")
    a.emit(0x60)
    return a.resolve()


def make_status_vwf_converter_hook() -> bytes:
    """Exact Status-label bitmap hook; all non-matching calls replay stock."""
    a = MiniAssembler(STATUS_VWF_HELPER_CPU)

    # Gate on exact Status resource identity.  A20F==8 alone is not enough: the
    # menu setup renders another resource first, so also require C7 source bank
    # and the post-parse pointer to remain inside C7:7A28-$7A8E.
    a.emit(0xE2, 0x20)                              # SEP #$20
    a.emit(0xAF, *lo24(0x7EA20F))
    a.emit(0xC9, STATUS_MENU_ID)
    a.rel8(0xD0, "reject")
    a.emit(0xAF, *lo24(0x7E1D03))
    a.emit(0xC9, 0xC7)
    a.rel8(0xD0, "reject")
    a.emit(0xC2, 0x20)                              # REP #$20
    a.emit(0xAF, *lo24(0x7E1D01))
    a.emit(0xC9, 0x28, 0x7A)
    a.rel8(0x90, "reject")                         # pointer < $7A28
    a.emit(0xC9, STATUS_SOURCE_END_PTR & 0xFF, STATUS_SOURCE_END_PTR >> 8)
    a.rel8(0xB0, "reject")                         # pointer >= $7A8F

    # Activate only alongside french_menus' already-runtime-validated removal
    # of the USA-only hard-coded `ON` / `CE` suffixes.  This keeps vwf_ui
    # standalone on a clean USA ROM completely stock for this screen without
    # embedding any localized prose in the generic renderer component.
    a.emit(0xAF, *lo24(STATUS_SUFFIX_CONSTITUTION_CPU))
    a.emit(0xC9, STATUS_SUFFIX_BLANK_WORD & 0xFF, STATUS_SUFFIX_BLANK_WORD >> 8)
    a.rel8(0xD0, "reject")
    a.emit(0xAF, *lo24(STATUS_SUFFIX_INTELLIGENCE_CPU))
    a.emit(0xC9, STATUS_SUFFIX_BLANK_WORD & 0xFF, STATUS_SUFFIX_BLANK_WORD >> 8)
    a.rel8(0xD0, "reject")
    # french_menus owns the full-label table and exact marker.  Requiring it
    # prevents this generic component from ever reading unowned expanded-ROM
    # bytes when used standalone or with an older french_menus patch.
    a.emit(0xAF, *lo24(STATUS_VWF_LABEL_MARKER_CPU))
    a.emit(0xC9, STATUS_VWF_LABEL_MARKER_WORD & 0xFF, STATUS_VWF_LABEL_MARKER_WORD >> 8)
    a.rel8(0xD0, "reject")
    a.emit(0xE2, 0x20)
    a.emit(0xAF, *lo24(0x7EA1A0))
    a.emit(0xC9, 0x04)
    a.rel8(0xB0, "reject")
    a.rel8(0x80, "status")

    a.label("reject")
    # Replay the four overwritten bytes plus the remainder of LDY #$0000, then
    # return to the untouched stock converter at C0:236C.
    a.emit(0xE2, 0x20)                              # M8 as stock
    a.emit(0xC2, 0x10)                              # X/Y16 as stock
    a.emit(0xA2, 0x00, 0x00)                       # LDX #$0000
    a.emit(0xA0, 0x00, 0x00)                       # LDY #$0000
    a.emit(0x5C, *lo24(STATUS_BITMAP_CONVERT_RESUME_CPU))

    a.label("status")
    # Clear the stock 32-cell (32*12=$180) source bitmap.  We populate exact
    # slot fragments below, then hand the finished bitmap back to the original
    # C0:236C pair-packed 4bpp converter unchanged.
    a.emit(0xC2, 0x10)                              # X/Y16
    a.emit(0xC2, 0x20)                              # A16
    a.emit(0xA9, 0x00, 0x00)
    a.emit(0xA2, 0x00, 0x00)
    a.label("clear_chunk")
    a.emit(0x9D, 0x00, 0x90)
    a.emit(0xE8, 0xE8)
    a.emit(0xE0, 0x80, 0x01)
    a.rel8(0xD0, "clear_chunk")
    a.emit(0xE2, 0x20)

    # Dispatch by the stock parser chunk index.  Slots 3 and 9 straddle the
    # fixed 32-cell chunk boundary; render each slot as a whole into $9180 then
    # copy only the cells belonging to the current chunk.
    a.emit(0xAF, *lo24(0x7EA1A0))
    a.emit(0xC9, 0x00)
    a.rel8(0xD0, "check1")
    a.rel16(0x82, "chunk0")
    a.label("check1")
    a.emit(0xC9, 0x01)
    a.rel8(0xD0, "check2")
    a.rel16(0x82, "chunk1")
    a.label("check2")
    a.emit(0xC9, 0x02)
    a.rel8(0xD0, "check3")
    a.rel16(0x82, "chunk2")
    a.label("check3")
    a.rel16(0x82, "chunk3")

    def emit_slot(slot: int, src_cell: int, dst_cell: int, cell_count: int) -> None:
        a.emit(0xA9, src_cell)
        a.emit(0x8D, STATUS_COPY_SRC_CELL & 0xFF, STATUS_COPY_SRC_CELL >> 8)
        a.emit(0xA9, dst_cell)
        a.emit(0x8D, STATUS_COPY_DST_CELL & 0xFF, STATUS_COPY_DST_CELL >> 8)
        a.emit(0xA9, cell_count)
        a.emit(0x8D, STATUS_COPY_CELL_COUNT & 0xFF, STATUS_COPY_CELL_COUNT >> 8)
        a.emit(0xA9, slot)
        a.emit(0x20, STATUS_VWF_RENDER_SLOT_CPU & 0xFF, (STATUS_VWF_RENDER_SLOT_CPU >> 8) & 0xFF)
        a.emit(0x20, STATUS_VWF_COPY_CELLS_CPU & 0xFF, (STATUS_VWF_COPY_CELLS_CPU >> 8) & 0xFF)

    a.label("chunk0")
    emit_slot(0, 0, 0, 10)
    emit_slot(1, 0, 10, 10)
    emit_slot(2, 0, 20, 10)
    emit_slot(3, 0, 30, 2)
    a.rel16(0x82, "convert_stock")

    a.label("chunk1")
    emit_slot(3, 2, 0, 8)
    emit_slot(4, 0, 8, 10)
    emit_slot(5, 0, 18, 10)
    a.rel16(0x82, "convert_stock")

    a.label("chunk2")
    emit_slot(6, 0, 0, 10)
    emit_slot(7, 0, 10, 10)
    emit_slot(8, 0, 20, 10)
    emit_slot(9, 0, 30, 2)
    a.rel16(0x82, "convert_stock")

    a.label("chunk3")
    emit_slot(9, 2, 0, 8)

    a.label("convert_stock")
    a.emit(0xE2, 0x20)
    a.emit(0xC2, 0x10)
    a.emit(0xA2, 0x00, 0x00)
    a.emit(0xA0, 0x00, 0x00)
    a.emit(0x5C, *lo24(STATUS_BITMAP_CONVERT_RESUME_CPU))
    return a.resolve()


def make_width_table(base: bytes) -> bytes:
    table = bytearray(128)
    font = bytearray(base[FONT_BASE:FONT_BASE + 128 * 12])
    french = glyph_bytes(DIALOGUE_CHARS)
    french_start = (GLYPH_FIRST - 0x80) * 12
    font[french_start:french_start + len(french)] = french
    for code in range(0x80, 0x100):
        rows = font[(code - 0x80) * 12:(code - 0x80 + 1) * 12]
        table[code - 0x80] = validated_advance(code, rows)
    return bytes(table)


def make_submit_wrapper() -> bytes:
    """Classify the exact $00:19D0 submit into narrow UI families.

    The caller at $D0:D3D2 is shared by the Ring Menu engine and Watts' Forge.
    Do not arm VWF merely because this submit site was reached.  `$1847` is the
    already-proven Ring subsystem mode byte at this exact call site:

    - mode 0: top-level Ring Menu title row -> Ring one-shot tag;
    - modes 1/2: shop merchandise name + price row -> dedicated shop-row tag;
    - mode 3: Watts Forge row -> Forge one-shot tag;
    - any unexpected value: no UI tag, stock fallback.

    This wrapper then reproduces $D0:D5D7 exactly enough to submit bank $00 /
    pointer $19D0.  Classification happens before parser initialization so the
    shared capacity helper can grant the family-specific local margin.
    """
    a = MiniAssembler(SUBMIT_WRAPPER_CPU)

    # Exact caller reaches us in 16-bit A/X mode with X=$19D0.  Clear the tag
    # first so modes 1/2 can never inherit a previous one-shot UI invocation.
    a.emit(0xE2, 0x20)                                # SEP #$20
    a.emit(0xA9, 0x00)
    a.emit(0x8F, *lo24(0x7E0000 | UI_TAG))

    a.emit(0xAF, *lo24(0x7E1847))                     # Ring subsystem mode
    a.emit(0xC9, 0x00)
    a.rel8(0xF0, "ring")
    a.emit(0xC9, 0x01)
    a.rel8(0xF0, "shop_row")
    a.emit(0xC9, 0x02)
    a.rel8(0xF0, "shop_row")
    a.emit(0xC9, 0x03)
    a.rel8(0xF0, "forge")
    a.rel8(0x80, "classified")

    a.label("ring")
    a.emit(0xA9, RING_UI_MAGIC)
    a.emit(0x8F, *lo24(0x7E0000 | UI_TAG))
    a.rel8(0x80, "classified")

    a.label("shop_row")
    a.emit(0xA9, SHOP_ROW_UI_MAGIC)
    a.emit(0x8F, *lo24(0x7E0000 | UI_TAG))
    a.rel8(0x80, "classified")

    a.label("forge")
    a.emit(0xA9, FORGE_UI_MAGIC)
    a.emit(0x8F, *lo24(0x7E0000 | UI_TAG))

    a.label("classified")
    # Reproduce $D0:D5D7 with event bank forced to the original #$00.
    a.emit(0xC2, 0x10)                                # REP #$10
    a.emit(0xA9, 0x00)                                # event bank $00
    a.emit(0x48)                                      # PHA
    a.emit(0xDA)                                      # PHX
    a.emit(0xA9, 0x01)
    a.emit(0x2C, 0x04, 0x1D)                          # BIT $1D04
    a.rel8(0xF0, "no_cancel")
    a.emit(0x22, *lo24(FORGE_SUBMIT_HELPER))          # JSL $C0:0095
    a.label("no_cancel")
    a.emit(0xFA)                                      # PLX
    a.emit(0x68)                                      # PLA => $00
    a.emit(0x8D, 0x03, 0x1D)                          # STA $1D03
    a.emit(0x8E, 0x01, 0x1D)                          # STX $1D01
    a.emit(0xC2, 0x20)                                # REP #$20
    a.emit(0xA9, 0x00, 0x00)                          # match original A result
    a.emit(0x6B)                                      # RTL
    return a.resolve()



def make_shop_dispatch_wrapper() -> bytes:
    """Arm a one-shot VWF tag only for the known D9 shop/forge mini-event pool.

    Both stock shop display paths arrive with X holding the 16-bit mini-event
    pointer, then execute the same 12-byte D9 event-engine submit sequence.  Keep
    that mechanism intact while classifying only pointers inside $D9:FE20-FEF3.
    Any unexpected D9 pointer through the same sites explicitly clears the tag
    and therefore retains stock rendering.
    """
    a = MiniAssembler(SHOP_DISPATCH_WRAPPER_CPU)

    a.emit(0xC2, 0x10)                                # REP #$10: compare 16-bit X
    a.emit(0xA9, 0x00)
    a.emit(0x8F, *lo24(0x7E0000 | UI_TAG))           # clear stale one-shot tag
    a.emit(0xE0, SHOP_POOL_START & 0xFF, SHOP_POOL_START >> 8)  # CPX #$FE20
    a.rel8(0x90, "submit")                           # below pool => stock
    a.emit(0xE0, SHOP_POOL_END & 0xFF, SHOP_POOL_END >> 8)      # CPX #$FEF4
    a.rel8(0xB0, "submit")                           # at/above pool => stock
    a.emit(0xA9, SHOP_UI_MAGIC)
    a.emit(0x8F, *lo24(0x7E0000 | UI_TAG))

    a.label("submit")
    # Replay the stock D9 event-engine submit exactly.
    a.emit(0xA9, 0xD9)
    a.emit(0x8D, 0x03, 0x1D)
    a.emit(0x8E, 0x01, 0x1D)
    a.emit(0x22, 0x92, 0x00, 0xC0)
    a.emit(0x6B)
    return a.resolve()


def make_battle_submit_wrapper(origin: int, event_pointer: int, clear_addr: int) -> bytes:
    """Arm battle-banner VWF, then replay one exact stock C0 event submit.

    The two stock helpers differ only by event script ($637D/$637F) and the
    transient status byte they clear.  Keeping two tiny wrappers avoids any
    broad classifier or caller inference.
    """
    a = MiniAssembler(origin)
    a.emit(0xA9, BATTLE_UI_MAGIC)
    a.emit(0x8F, *lo24(0x7E0000 | UI_TAG))
    a.emit(0xA0, event_pointer & 0xFF, (event_pointer >> 8) & 0xFF)
    a.emit(0x8C, 0x01, 0x1D)
    a.emit(0xA9, 0xC0)
    a.emit(0x8D, 0x03, 0x1D)
    a.emit(0x64, clear_addr & 0xFF)
    a.emit(0x6B)
    return a.resolve()

def make_shop_suffix_gap_helper() -> bytes:
    """Add a 4-pixel visual separator before the shop row's final 2-glyph unit.

    Content is deliberately opaque: on a clean USA ROM the final two glyphs are
    ``GP``; with ``french_resources`` they are ``PO``.  The shop row is identified
    only by the already-proven Ring subsystem modes 1/2, and the currency
    boundary is the last two decoded glyphs (`X + 2 == saved_count`).
    """
    a = MiniAssembler(SHOP_SUFFIX_GAP_HELPER_CPU)
    a.emit(0xAF, *lo24(0x7E1847))                     # Ring subsystem mode
    a.emit(0xC9, 0x01)
    a.rel8(0xF0, "shop")
    a.emit(0xC9, 0x02)
    a.rel8(0xD0, "return")

    a.label("shop")
    a.emit(0x8A)                                      # TXA: current decoded slot
    a.emit(0x18)                                      # +2 == saved decoded count?
    a.emit(0x69, 0x02)
    a.emit(0xCD, SAVED_COUNT & 0xFF, (SAVED_COUNT >> 8) & 0xFF)
    a.rel8(0xD0, "return")
    a.emit(0xAD, PIXEL_CURSOR & 0xFF, (PIXEL_CURSOR >> 8) & 0xFF)
    a.emit(0x18)
    a.emit(0x69, 0x04)                                # 4 px visual separator
    a.emit(0x8D, PIXEL_CURSOR & 0xFF, (PIXEL_CURSOR >> 8) & 0xFF)

    a.label("return")
    a.emit(0x6B)
    return a.resolve()

def make_game_file_mana_wrapper() -> bytes:
    """VWF-render only the 15-cell GAME FILE Mana label.

    The stock resource starts the visible label on global cell 91, i.e. the
    right half of the 90/91 packed graphics pair. Start the upload one cell
    earlier at VRAM $6820 and use a 9-pixel cursor inset (8 px blank cell +
    the validated 1-pixel outline margin). This preserves stock pair ordering
    and leaves the dynamic Mana value, which begins at $6920, untouched.

    Content remains source-owned: copy exactly 15 cells from C7:73AA, so a
    clean USA standalone build renders the stock source while french_menus
    naturally supplies its reviewed 15-cell translation payload.
    """
    a = MiniAssembler(GAME_FILE_MANA_WRAPPER_CPU)
    a.emit(0x08)                                      # PHP
    a.emit(0x8B)                                      # PHB
    a.emit(0xE2, 0x20)                                # SEP #$20
    a.emit(0xC2, 0x10)                                # REP #$10
    a.emit(0xA2, 0x00, 0x00)                          # LDX #0
    a.label("copy_source")
    a.emit(0xBF, *lo24(GAME_FILE_MANA_SOURCE_CPU))
    a.emit(0x9F, *lo24(0x7E0000 | GAME_FILE_MANA_PRIVATE_BUFFER))
    a.emit(0xE8)                                      # INX
    a.emit(0xE0, GAME_FILE_MANA_SOURCE_CELLS, 0x00)   # CPX #15
    a.rel8(0xD0, "copy_source")
    a.emit(0xA9, 0x00)
    a.emit(0x8F, *lo24(0x7E0000 | (GAME_FILE_MANA_PRIVATE_BUFFER + GAME_FILE_MANA_SOURCE_CELLS)))

    # Reproduce the stock menu-text submit state for one 16-cell pair-aligned
    # tile span. The 16th graphical cell is the leading blank; only 15 source
    # characters are decoded/rendered.
    a.emit(0xC2, 0x20)                                # REP #$20
    a.emit(0xA9, GAME_FILE_MANA_VRAM_DEST & 0xFF, GAME_FILE_MANA_VRAM_DEST >> 8)
    a.emit(0x8F, *lo24(0x7EA18C))
    a.emit(0xA9, GAME_FILE_MANA_DMA_SIZE & 0xFF, GAME_FILE_MANA_DMA_SIZE >> 8)
    a.emit(0x8F, *lo24(0x7EA191))
    a.emit(0xA9, GAME_FILE_MANA_PRIVATE_BUFFER & 0xFF, GAME_FILE_MANA_PRIVATE_BUFFER >> 8)
    a.emit(0x8F, *lo24(0x001D01))
    a.emit(0xE2, 0x20)                                # SEP #$20
    a.emit(0xA9, 0x7E)
    a.emit(0x8F, *lo24(0x001D03))
    a.emit(0xA9, 0x00)
    a.emit(0x8F, *lo24(0x001D00))
    a.emit(0x8F, *lo24(0x7EA1C5))
    a.emit(0xAF, *lo24(0x7EA212))
    a.emit(0x09, 0x01)                                # ORA #$01
    a.emit(0x8F, *lo24(0x7EA212))

    a.emit(0xA9, GAME_FILE_MANA_UI_MAGIC)
    a.emit(0x8F, *lo24(0x7E0000 | UI_TAG))
    a.emit(0x22, *lo24(0xC02ADB))
    a.emit(0x22, *lo24(0xC02AEA))
    a.emit(0x22, *lo24(0xC02ADF))
    a.emit(0xAB)                                      # PLB
    a.emit(0x28)                                      # PLP
    a.emit(0x6B)                                      # RTL
    return a.resolve()


def make_ui_renderer() -> bytes:
    """Render only an explicitly tagged, runtime-proven UI invocation.

    Ring, Forge, shop merchandise rows, the exact D9 shop/forge-response
    backend and the stock type-2 money window keep the stock parser/decoded
    buffer. The exact battle/status banner submits use parser mode 3 and retain
    their already-decoded 49-byte private buffer. GAME FILE Mana is prepared by
    its exact generator wrapper and uses selector 6 with true decoded count.
    Currency text is never translated here: standalone `vwf_ui` renders
    whatever two-glyph currency unit the source component provides (`GP` on a
    clean USA ROM, `PO` when `french_resources` is present). Presentation-only gaps
    are handled by the shared VWF geometry helpers. Forge keeps its separately
    validated suffix compaction.
    """
    a = MiniAssembler(UI_RENDER_CPU)

    # GAME FILE Mana is submitted through the exact C0:2ADB/2AEA/2ADF menu-text
    # pipeline and reaches this renderer from a different stock caller than the
    # event-engine UI families. Prove that one-shot tag first, then require its
    # exact caller return address. Every other UI family keeps the validated
    # event-engine return-address gate.
    a.emit(0xAF, *lo24(0x7E0000 | UI_TAG))
    a.emit(0xC9, GAME_FILE_MANA_UI_MAGIC)
    a.rel8(0xF0, "game_file_caller")
    a.emit(0xC2, 0x20)
    a.emit(0xA3, 0x01)
    a.emit(0xC9, 0x52, 0x11)
    a.emit(0xE2, 0x20)
    a.rel8(0xF0, "identity_ready")
    a.rel16(0x82, "reject")

    a.label("game_file_caller")
    a.emit(0xC2, 0x20)
    a.emit(0xA3, 0x01)
    a.emit(0xC9, 0x5E, 0x23)
    a.emit(0xE2, 0x20)
    a.rel8(0xF0, "identity_ready")
    a.rel16(0x82, "reject")

    a.label("identity_ready")
    # Capture the family before consuming it. X is an ephemeral backend
    # selector: 0=Ring, 1=Forge, 2=D9 shop/forge response,
    # 3=shop merchandise row, 4=type-2 money window, 5=battle/status banner,
    # 6=GAME FILE Mana label.
    a.emit(0xAF, *lo24(0x7E0000 | UI_TAG))
    a.emit(0xC9, FORGE_UI_MAGIC)
    a.rel8(0xF0, "kind_forge")
    a.emit(0xC9, RING_UI_MAGIC)
    a.rel8(0xF0, "kind_ring")
    a.emit(0xC9, SHOP_ROW_UI_MAGIC)
    a.rel8(0xF0, "kind_shop_row")
    a.emit(0xC9, SHOP_UI_MAGIC)
    a.rel8(0xF0, "kind_shop")
    a.emit(0xC9, MONEY_UI_MAGIC)
    a.rel8(0xF0, "kind_money")
    a.emit(0xC9, BATTLE_UI_MAGIC)
    a.rel8(0xF0, "kind_battle")
    a.emit(0xC9, GAME_FILE_MANA_UI_MAGIC)
    a.rel8(0xF0, "kind_game_file")
    a.rel8(0x80, "reject")

    a.label("kind_ring")
    a.emit(0xC2, 0x10)
    a.emit(0xA2, 0x00, 0x00)
    a.rel8(0x80, "kind_bank")
    a.label("kind_forge")
    a.emit(0xC2, 0x10)
    a.emit(0xA2, 0x01, 0x00)
    a.rel8(0x80, "kind_bank")
    a.label("kind_shop")
    a.emit(0xC2, 0x10)
    a.emit(0xA2, 0x02, 0x00)
    a.rel8(0x80, "kind_bank")
    a.label("kind_shop_row")
    a.emit(0xC2, 0x10)
    a.emit(0xA2, 0x03, 0x00)
    a.rel8(0x80, "kind_bank")
    a.label("kind_money")
    a.emit(0xC2, 0x10)
    a.emit(0xA2, 0x04, 0x00)
    a.rel8(0x80, "kind_bank")
    a.label("kind_battle")
    a.emit(0xC2, 0x10)
    a.emit(0xA2, 0x05, 0x00)
    a.rel8(0x80, "kind_bank")
    a.label("kind_game_file")
    a.emit(0xC2, 0x10)
    a.emit(0xA2, 0x06, 0x00)

    a.label("kind_bank")
    a.emit(0xE0, 0x02, 0x00)
    a.rel8(0xF0, "bank_shop")
    a.emit(0xE0, 0x04, 0x00)
    a.rel8(0xF0, "bank_money")
    a.emit(0xE0, 0x05, 0x00)
    a.rel8(0xF0, "bank_battle")
    a.emit(0xE0, 0x06, 0x00)
    a.rel8(0xF0, "bank_money")
    a.emit(0xAF, *lo24(0x001D03))
    a.emit(0xC9, 0x00)
    a.rel8(0xD0, "reject")
    a.rel8(0x80, "accepted")
    a.label("bank_shop")
    a.emit(0xAF, *lo24(0x001D03))
    a.emit(0xC9, 0xD9)
    a.rel8(0xD0, "reject")
    a.rel8(0x80, "accepted")
    a.label("bank_money")
    a.emit(0xAF, *lo24(0x001D03))
    a.emit(0xC9, 0x7E)
    a.rel8(0xD0, "reject")
    a.rel8(0x80, "accepted")
    a.label("bank_battle")
    # The $C0:637D/$637F helpers only open/close the banner.  The actual
    # battle/status message is copied to $7E:FF69 and parsed/rendered from
    # WRAM, so continuity must require the live source bank $7E here.
    a.emit(0xAF, *lo24(0x001D03))
    a.emit(0xC9, 0x7E)
    a.rel8(0xD0, "reject")
    a.rel8(0x80, "accepted")

    a.label("reject")
    a.emit(0xA9, 0x00)
    a.emit(0x8F, *lo24(0x7E0000 | UI_TAG))
    a.emit(0x5C, *lo24(DISPATCH_CPU))

    a.label("accepted")
    a.emit(0xA9, 0x00)
    a.emit(0x8F, *lo24(0x7E0000 | UI_TAG))
    a.emit(0xDA)                                      # preserve selector
    # Shared low-level renderer scope. Value 2 is reserved for UI VWF; value 1
    # remains owned by vwf_dialogues. Shared hooks accept exactly 1/2, while
    # dialogue-only continuation capture is gated to value 1.
    a.emit(0xA9, 0x02)
    a.emit(0x8F, *lo24(0x7E0000 | RENDER_ACTIVE))
    a.emit(0xAF, *lo24(0x7E0000 | DECODED_COUNT))
    a.emit(0x29, 0x7F)
    a.emit(0x8F, *lo24(0x7E0000 | SAVED_COUNT))
    a.emit(0xA9, 0x00)
    a.emit(0x8F, *lo24(0x7E0000 | PHYSICAL_CELLS))
    a.emit(0x8F, *lo24(0x7E0000 | PIXEL_CURSOR))

    # Ring/Forge/shop/MONEY are decoded by the stock parser and need the usual
    # render-time copy. Battle selector 5 was already decoded directly into the
    # extended private buffer by shared parser mode 3, so preserve it verbatim.
    a.emit(0xFA)                                      # PLX selector
    a.emit(0xE0, 0x05, 0x00)                         # CPX #5: battle banner
    a.rel8(0xF0, "private_ready")
    a.emit(0xDA)                                      # keep selector across copy loops

    a.emit(0xC2, 0x10)
    a.emit(0xA2, 0x00, 0x00)
    a.emit(0xA9, 0x80)
    a.label("clear_private")
    a.emit(0x9F, *lo24(0x7E0000 | PRIVATE_BUFFER))
    a.emit(0xE8)
    a.emit(0xE0, 0x26, 0x00)
    a.rel8(0xD0, "clear_private")

    a.emit(0xA2, 0x00, 0x00)
    a.label("copy_stock")
    a.emit(0xBF, *lo24(0x7E0000 | STOCK_BUFFER))
    a.emit(0x9F, *lo24(0x7E0000 | PRIVATE_BUFFER))
    a.emit(0xE8)
    a.emit(0xE0, 0x20, 0x00)
    a.rel8(0xD0, "copy_stock")
    a.emit(0xFA)                                      # PLX selector

    a.label("private_ready")
    # Select post-parse presentation only. Currency bytes are deliberately never
    # inspected or rewritten here; french_resources owns source content.

    # The one-line UI banner shares the same left-edge outline geometry as
    # ordinary dialogue.  Start Ring / Forge / D9 shop-response / merchandise
    # VWF one pixel inside the bitmap so the stock outline has a real column
    # on the left of the first glyph.  MONEY keeps its separately validated
    # centered-window geometry at x=0.  Merchandise price geometry is also
    # unchanged because its later TEXT_X resync still sets the exact 164-px
    # price anchor.
    a.emit(0xE0, 0x04, 0x00)                         # CPX #4: MONEY selector
    a.rel8(0xF0, "left_inset_done")
    a.emit(0xE0, 0x06, 0x00)                         # CPX #6: GAME FILE Mana
    a.rel8(0xD0, "normal_left_inset")
    a.emit(0xA9, 0x09)                               # one blank 8px cell + 1px outline inset
    a.emit(0x8F, *lo24(0x7E0000 | PIXEL_CURSOR))
    a.rel8(0x80, "left_inset_done")
    a.label("normal_left_inset")
    a.emit(0xA9, 0x01)
    a.emit(0x8F, *lo24(0x7E0000 | PIXEL_CURSOR))     # fresh UI line starts at +1 px
    a.label("left_inset_done")

    a.emit(0xE0, 0x01, 0x00)
    a.rel8(0xF0, "forge_only")
    a.rel16(0x82, "render_common")

    a.label("forge_only")
    # Forge only: find the true end of the current weapon name before safe logical slot 20.
    a.emit(0xA2, 0x13, 0x00)
    a.label("scan_name_end")
    a.emit(0xBD, PRIVATE_BUFFER & 0xFF, (PRIVATE_BUFFER >> 8) & 0xFF)
    a.emit(0xC9, 0x80)
    a.rel8(0xD0, "name_end")
    a.emit(0xCA)
    a.emit(0xE0, 0xFF, 0xFF)
    a.rel8(0xD0, "scan_name_end")
    a.emit(0xA2, 0xFF, 0xFF)

    a.label("name_end")
    # destination = last glyph + 2 => one decoded space before arrow.
    a.emit(0xC2, 0x20)
    a.emit(0x8A, 0x1A, 0x1A, 0xA8)
    a.emit(0xE2, 0x20)

    # Move the complete suffix logical slots 20..31 as one unit.
    a.emit(0xA2, 0x14, 0x00)
    a.label("compact_suffix")
    a.emit(0xBD, PRIVATE_BUFFER & 0xFF, (PRIVATE_BUFFER >> 8) & 0xFF)
    a.emit(0x99, PRIVATE_BUFFER & 0xFF, (PRIVATE_BUFFER >> 8) & 0xFF)
    a.emit(0xE8, 0xC8)
    a.emit(0xE0, 0x20, 0x00)
    a.rel8(0xD0, "compact_suffix")

    a.emit(0xA9, 0x80)
    a.label("clear_tail")
    a.emit(0x99, PRIVATE_BUFFER & 0xFF, (PRIVATE_BUFFER >> 8) & 0xFF)
    a.emit(0xC8)
    a.emit(0xC0, 0x26, 0x00)
    a.rel8(0xD0, "clear_tail")

    # Shop merchandise and MONEY rows need no post-parse byte mutation.
    # Their source currency unit remains exactly what the owning text component
    # supplied; shared geometry adds only visual spacing.

    a.label("render_common")
    # Merchandise rows are different from the other UI families here: their
    # decoded row can end close enough to the 8-bit pixel-cursor wrap that
    # rendering the artificial $80 padding out to all 38 private slots wraps
    # back to x=0.  An aligned trailing space then commits zeroes over cell 0,
    # erasing the first glyph (observed on `Haubert magique`).  The bitmap is
    # already cleared below, so merchandise needs to render only the glyphs the
    # stock parser actually decoded.  Keep the validated 38-slot behavior for
    # Ring / Forge / D9 / MONEY.
    a.emit(0xE0, 0x03, 0x00)                         # CPX #3: merchandise selector
    a.rel8(0xF0, "render_true_count")
    a.emit(0xE0, 0x05, 0x00)                         # CPX #5: battle banner
    a.rel8(0xF0, "render_true_count")
    a.emit(0xE0, 0x06, 0x00)                         # CPX #6: GAME FILE Mana
    a.rel8(0xD0, "render_full_private")
    a.label("render_true_count")
    a.emit(0xAD, SAVED_COUNT & 0xFF, (SAVED_COUNT >> 8) & 0xFF)
    a.emit(0x8D, 0x76, 0xA1)                         # render true decoded count only
    a.rel8(0x80, "render_count_ready")
    a.label("render_full_private")
    a.emit(0xA9, 0x26)
    a.emit(0x8D, 0x76, 0xA1)                         # 38 private slots
    a.label("render_count_ready")

    # Clear 32-cell bitmap, then enter the generic VWF renderer at the stock
    # character loop.  Merchandise no longer renders its synthetic tail spaces.
    a.emit(0xA2, 0x00, 0x00)
    a.emit(0xA9, 0x00)
    a.label("clear_bitmap")
    a.emit(0x9E, 0x00, 0x90)
    a.emit(0xE8)
    a.emit(0xE0, 0x80, 0x01)
    a.rel8(0xD0, "clear_bitmap")
    a.emit(0x5C, *lo24(0xC01682))
    return a.resolve()

def build(base: bytes) -> bytes:
    validate_base_rom(base)
    validate_text_buffer(base)
    validate_ui_dispatch(base)
    validate_framing(base)
    validate_compositor(base)
    validate_row_renderer(base)
    validate_renderer_runtime(base)
    validate_outline(base)

    if base[FORGE_SUBMIT_FILE:FORGE_SUBMIT_FILE + len(FORGE_SUBMIT_SIGNATURE)] != FORGE_SUBMIT_SIGNATURE:
        raise SystemExit("Unexpected clean-US Forge row submit sequence")
    if base[ARROW_TEXT_X_ARG_FILE] != EXPECTED_ARROW_X:
        raise SystemExit("Unexpected clean-US Forge arrow TEXT_X")
    if base[PRICE_TEXT_X_ARG_FILE] != EXPECTED_PRICE_X:
        raise SystemExit("Unexpected clean-US Forge price TEXT_X")
    if base[MONEY_WINDOW_WIDTH_FILE] != EXPECTED_MONEY_WINDOW_WIDTH:
        raise SystemExit(
            f"Unexpected clean-US type-2 money-window width: "
            f"${base[MONEY_WINDOW_WIDTH_FILE]:02X}"
        )
    if base[MONEY_CLOSE_X_FILE] != EXPECTED_MONEY_CLOSE_X:
        raise SystemExit(
            f"Unexpected clean-US type-2 money close X: "
            f"${base[MONEY_CLOSE_X_FILE]:02X}"
        )
    for site in SHOP_DISPATCH_SITES:
        if base[site:site + len(SHOP_DISPATCH_SIGNATURE)] != SHOP_DISPATCH_SIGNATURE:
            raise SystemExit(f"Unexpected clean-US shop/forge D9 dispatch at C0:${site:04X}")
    if base[BATTLE_SUBMIT_50_FILE:BATTLE_SUBMIT_50_FILE + len(BATTLE_SUBMIT_50_SIGNATURE)] != BATTLE_SUBMIT_50_SIGNATURE:
        raise SystemExit("Unexpected clean-US battle banner $50 submit helper")
    if base[BATTLE_SUBMIT_51_FILE:BATTLE_SUBMIT_51_FILE + len(BATTLE_SUBMIT_51_SIGNATURE)] != BATTLE_SUBMIT_51_SIGNATURE:
        raise SystemExit("Unexpected clean-US battle banner $51 submit helper")
    if base[GAME_FILE_MANA_GENERATOR_PTR_FILE:GAME_FILE_MANA_GENERATOR_PTR_FILE + 2] != GAME_FILE_MANA_GENERATOR_PTR_STOCK:
        raise SystemExit("Unexpected clean-US GAME FILE Mana generator pointer")
    if any(b != 0xFF for b in base[GAME_FILE_MANA_TRAMPOLINE_FILE:GAME_FILE_MANA_TRAMPOLINE_FILE + GAME_FILE_MANA_TRAMPOLINE_SIZE]):
        raise SystemExit("Expected stock-$FF GAME FILE Mana VWF trampoline space")
    if base[STATUS_BITMAP_CONVERT_HOOK_FILE:STATUS_BITMAP_CONVERT_HOOK_FILE + len(STATUS_BITMAP_CONVERT_HOOK_SIGNATURE)] != STATUS_BITMAP_CONVERT_HOOK_SIGNATURE:
        raise SystemExit("Unexpected clean-US C0:2366 bitmap converter prologue")
    for site in SKILL_PROGRESS_FORMAT_CALLS:
        if base[site:site + len(SKILL_PROGRESS_FORMAT_CALL_STOCK)] != SKILL_PROGRESS_FORMAT_CALL_STOCK:
            raise SystemExit(f"Unexpected clean-US skill progress formatter call at C7:${site - 0x70000:04X}")
    for site in SKILL_SUBMIT_CALLS:
        if base[site:site + len(SKILL_SUBMIT_CALL_STOCK)] != SKILL_SUBMIT_CALL_STOCK:
            raise SystemExit(f"Unexpected clean-US skill-list batch submit at C7:${site - 0x70000:04X}")
    if any(
        b != 0xFF
        for b in base[
            SKILL_PROGRESS_FORMAT_HELPER_FILE:
            SKILL_PROGRESS_FORMAT_HELPER_FILE + SKILL_PROGRESS_FORMAT_HELPER_RESERVED_SIZE
        ]
    ):
        raise SystemExit("Expected stock-$FF C7:4F00 skill-format helper space")
    if any(
        b != 0xFF
        for b in base[
            SKILL_SUBMIT_WRAPPER_FILE:
            SKILL_SUBMIT_WRAPPER_FILE + SKILL_SUBMIT_WRAPPER_RESERVED_SIZE
        ]
    ):
        raise SystemExit("Expected stock-$FF C7:4F30 skill-list submit-wrapper space")

    for site, expected, label in (
        (MAGIC_PANEL_PREP_CALL_FILE, MAGIC_PANEL_PREP_CALL_STOCK, "magic lower-panel prep"),
        (MAGIC_PANEL_COPY_CALL_FILE, MAGIC_PANEL_COPY_CALL_STOCK, "magic lower-panel copy"),
        (MAGIC_PANEL_SUBMIT_CALL_FILE, MAGIC_PANEL_SUBMIT_CALL_STOCK, "magic lower-panel submit"),
    ):
        if base[site:site + len(expected)] != expected:
            raise SystemExit(f"Unexpected clean-US {label} call at C7:${site - 0x70000:04X}")
    for start, size, label in (
        (MAGIC_PANEL_BATCH_HELPER_FILE, MAGIC_PANEL_BATCH_HELPER_RESERVED_SIZE, "C7:4F40 magic batch helper"),
        (MAGIC_PANEL_RESET_STUB_FILE, MAGIC_PANEL_RESET_STUB_RESERVED_SIZE, "C7:4FC0 magic reset stub"),
        (MAGIC_PANEL_CAPTURE_STUB_FILE, MAGIC_PANEL_CAPTURE_STUB_RESERVED_SIZE, "C7:4FD0 magic capture stub"),
    ):
        if any(b != 0xFF for b in base[start:start + size]):
            raise SystemExit(f"Expected stock-$FF {label} space")

    width_table = make_width_table(base)
    submit_wrapper = make_submit_wrapper()
    shop_dispatch_wrapper = make_shop_dispatch_wrapper()
    shop_suffix_gap_helper = make_shop_suffix_gap_helper()
    battle_submit_50 = make_battle_submit_wrapper(BATTLE_SUBMIT_50_WRAPPER_CPU, 0x637D, 0xA3)
    battle_submit_51 = make_battle_submit_wrapper(BATTLE_SUBMIT_51_WRAPPER_CPU, 0x637F, 0x9F)
    game_file_mana_wrapper = make_game_file_mana_wrapper()
    renderer = make_ui_renderer()
    status_vwf_hook = make_status_vwf_converter_hook()
    status_vwf_render_slot = make_status_vwf_render_slot()
    status_vwf_copy_cells = make_status_vwf_copy_cells()
    skill_progress_format = make_skill_progress_format_helper()
    skill_submit_wrapper = make_skill_submit_wrapper()
    skill_vwf_dispatch = make_skill_vwf_converter_dispatch()
    magic_panel_batch_helper, magic_panel_expected_return = make_magic_panel_batch_helper()
    magic_panel_reset_stub = make_magic_panel_reset_stub()
    magic_panel_capture_stub = make_magic_panel_capture_stub()
    magic_panel_capture_helper = make_magic_panel_capture_helper()
    magic_panel_reset_helper = make_magic_panel_reset_helper()
    magic_panel_dispatch = make_magic_panel_dispatch(magic_panel_expected_return)
    if len(submit_wrapper) > SUBMIT_WRAPPER_RESERVED_SIZE:
        raise SystemExit("UI VWF submit wrapper too large")
    if len(renderer) > UI_RENDER_RESERVED_SIZE:
        raise SystemExit(f"UI VWF renderer too large: {len(renderer):#x}")
    if len(shop_dispatch_wrapper) > SHOP_DISPATCH_WRAPPER_RESERVED_SIZE:
        raise SystemExit("UI VWF shop dispatch wrapper too large")
    if len(battle_submit_50) > BATTLE_SUBMIT_WRAPPER_RESERVED_SIZE or len(battle_submit_51) > BATTLE_SUBMIT_WRAPPER_RESERVED_SIZE:
        raise SystemExit("UI VWF battle submit wrapper too large")
    if len(game_file_mana_wrapper) > GAME_FILE_MANA_WRAPPER_RESERVED_SIZE:
        raise SystemExit("UI VWF GAME FILE Mana wrapper too large")
    if UI_RENDER_FILE + len(renderer) > SHOP_SUFFIX_GAP_HELPER_FILE:
        raise SystemExit("UI VWF renderer overlaps shop suffix-gap helper")
    if SHOP_SUFFIX_GAP_HELPER_FILE + len(shop_suffix_gap_helper) > WIDTH_TABLE_FILE:
        raise SystemExit("UI VWF shop suffix-gap helper overlaps width table")
    if len(status_vwf_hook) > STATUS_VWF_HELPER_RESERVED_SIZE:
        raise SystemExit(f"Status VWF converter hook too large: {len(status_vwf_hook):#x}")
    if len(status_vwf_render_slot) > STATUS_VWF_RENDER_SLOT_RESERVED_SIZE:
        raise SystemExit(f"Status VWF slot renderer too large: {len(status_vwf_render_slot):#x}")
    if len(status_vwf_copy_cells) > STATUS_VWF_COPY_CELLS_RESERVED_SIZE:
        raise SystemExit(f"Status VWF cell copier too large: {len(status_vwf_copy_cells):#x}")
    if len(skill_progress_format) > SKILL_PROGRESS_FORMAT_HELPER_RESERVED_SIZE:
        raise SystemExit(f"Skill progress formatter too large: {len(skill_progress_format):#x}")
    if len(skill_submit_wrapper) > SKILL_SUBMIT_WRAPPER_RESERVED_SIZE:
        raise SystemExit(f"Skill-list submit wrapper too large: {len(skill_submit_wrapper):#x}")
    if len(skill_vwf_dispatch) > SKILL_VWF_HELPER_RESERVED_SIZE:
        raise SystemExit(f"Skill-list VWF helper too large: {len(skill_vwf_dispatch):#x}")

    for payload, limit, label in (
        (magic_panel_batch_helper, MAGIC_PANEL_BATCH_HELPER_RESERVED_SIZE, "Magic-panel batch helper"),
        (magic_panel_reset_stub, MAGIC_PANEL_RESET_STUB_RESERVED_SIZE, "Magic-panel reset stub"),
        (magic_panel_capture_stub, MAGIC_PANEL_CAPTURE_STUB_RESERVED_SIZE, "Magic-panel capture stub"),
        (magic_panel_capture_helper, MAGIC_PANEL_CAPTURE_HELPER_RESERVED_SIZE, "Magic-panel capture helper"),
        (magic_panel_reset_helper, MAGIC_PANEL_RESET_HELPER_RESERVED_SIZE, "Magic-panel reset helper"),
        (magic_panel_dispatch, MAGIC_PANEL_DISPATCH_RESERVED_SIZE, "Magic-panel VWF dispatcher"),
    ):
        if len(payload) > limit:
            raise SystemExit(f"{label} too large: {len(payload):#x} > {limit:#x}")

    rom = expand_rom(base, ROM_TARGET_SIZE)
    # Shared infrastructure: standalone-safe and byte-identical with `vwf_intro` / `vwf_dialogues`.
    install_text_buffer(rom)
    install_dispatcher(rom)
    install_framing(rom)
    install_compositor(rom)
    install_row_renderer(rom)
    install_renderer_runtime(rom, width_table)
    install_outline(rom)
    enable_ui(rom)

    # Ensure shared French glyph slots exist when UI resources use them.
    french = glyph_bytes(DIALOGUE_CHARS)
    glyph_start = FONT_BASE + (GLYPH_FIRST - 0x80) * 12
    rom[glyph_start:glyph_start + len(french)] = french

    # GAME FILE Mana exact identity. Redirect only the fourth generator entry
    # through a free C7 trampoline; the trampoline calls the private VWF submit
    # wrapper and then jumps back to the stock C7:5464 generator.
    game_file_mana_trampoline = bytes([0x22, *lo24(GAME_FILE_MANA_WRAPPER_CPU), 0x4C, 0x64, 0x54])
    if len(game_file_mana_trampoline) != GAME_FILE_MANA_TRAMPOLINE_SIZE:
        raise SystemExit("Unexpected GAME FILE Mana trampoline size")
    rom[GAME_FILE_MANA_TRAMPOLINE_FILE:GAME_FILE_MANA_TRAMPOLINE_FILE + len(game_file_mana_trampoline)] = game_file_mana_trampoline
    rom[GAME_FILE_MANA_GENERATOR_PTR_FILE:GAME_FILE_MANA_GENERATOR_PTR_FILE + 2] = (GAME_FILE_MANA_TRAMPOLINE_CPU & 0xFFFF).to_bytes(2, "little")

    # Forge-specific exact identity/layout.
    rom[FORGE_SUBMIT_FILE:FORGE_SUBMIT_FILE + len(FORGE_SUBMIT_SIGNATURE)] = bytes([0x22, *lo24(SUBMIT_WRAPPER_CPU), 0xEA, 0xEA])
    rom[ARROW_TEXT_X_ARG_FILE] = SAFE_ARROW_SLOT
    rom[PRICE_TEXT_X_ARG_FILE] = SAFE_PRICE_SLOT
    # Currency presentation geometry: type-2 MONEY gains right breathing room.
    # Width 11 expands one cell farther left than stock, so move the independent
    # MONEY_CLOSE seed left by the same one cell to erase the full opened frame.
    # The source string remains stock-sized and is never translated by vwf_ui.
    rom[MONEY_WINDOW_WIDTH_FILE] = FRENCH_MONEY_WINDOW_WIDTH
    rom[MONEY_CLOSE_X_FILE] = FRENCH_MONEY_CLOSE_X
    rom[UI_RENDER_FILE:UI_RENDER_FILE + len(renderer)] = renderer
    rom[SHOP_SUFFIX_GAP_HELPER_FILE:SHOP_SUFFIX_GAP_HELPER_FILE + len(shop_suffix_gap_helper)] = shop_suffix_gap_helper
    rom[WIDTH_TABLE_FILE:WIDTH_TABLE_FILE + len(width_table)] = width_table
    rom[SUBMIT_WRAPPER_FILE:SUBMIT_WRAPPER_FILE + len(submit_wrapper)] = submit_wrapper
    shop_hook = bytes([0x22, *lo24(SHOP_DISPATCH_WRAPPER_CPU)]) + bytes([0xEA]) * (len(SHOP_DISPATCH_SIGNATURE) - 4)
    for site in SHOP_DISPATCH_SITES:
        rom[site:site + len(SHOP_DISPATCH_SIGNATURE)] = shop_hook
    rom[SHOP_DISPATCH_WRAPPER_FILE:SHOP_DISPATCH_WRAPPER_FILE + len(shop_dispatch_wrapper)] = shop_dispatch_wrapper

    for site, signature, wrapper_cpu in (
        (BATTLE_SUBMIT_50_FILE, BATTLE_SUBMIT_50_SIGNATURE, BATTLE_SUBMIT_50_WRAPPER_CPU),
        (BATTLE_SUBMIT_51_FILE, BATTLE_SUBMIT_51_SIGNATURE, BATTLE_SUBMIT_51_WRAPPER_CPU),
    ):
        hook = bytes([0x22, *lo24(wrapper_cpu), 0x60])
        hook += bytes([0xEA]) * (len(signature) - len(hook))
        rom[site:site + len(signature)] = hook
    rom[BATTLE_SUBMIT_50_WRAPPER_FILE:BATTLE_SUBMIT_50_WRAPPER_FILE + len(battle_submit_50)] = battle_submit_50
    rom[BATTLE_SUBMIT_51_WRAPPER_FILE:BATTLE_SUBMIT_51_WRAPPER_FILE + len(battle_submit_51)] = battle_submit_51
    rom[GAME_FILE_MANA_WRAPPER_FILE:GAME_FILE_MANA_WRAPPER_FILE + len(game_file_mana_wrapper)] = game_file_mana_wrapper

    # Weapon/Magic skill-list presentation. Replace only the two row-local
    # progress-format calls, preserving each helper's following RTS. The new
    # formatter removes a leading blank from one-digit values and appends one
    # separator blank before the dynamic name.
    for site in SKILL_PROGRESS_FORMAT_CALLS:
        rom[site:site + 3] = bytes([
            0x20,
            SKILL_PROGRESS_FORMAT_HELPER_CPU & 0xFF,
            (SKILL_PROGRESS_FORMAT_HELPER_CPU >> 8) & 0xFF,
        ])
    rom[
        SKILL_PROGRESS_FORMAT_HELPER_FILE:
        SKILL_PROGRESS_FORMAT_HELPER_FILE + len(skill_progress_format)
    ] = skill_progress_format

    # Scope name-VWF around only the two exact 8-row weapon/magic list submits.
    for site in SKILL_SUBMIT_CALLS:
        rom[site:site + 3] = bytes([
            0x20,
            SKILL_SUBMIT_WRAPPER_CPU & 0xFF,
            (SKILL_SUBMIT_WRAPPER_CPU >> 8) & 0xFF,
        ])
    rom[
        SKILL_SUBMIT_WRAPPER_FILE:
        SKILL_SUBMIT_WRAPPER_FILE + len(skill_submit_wrapper)
    ] = skill_submit_wrapper

    # Magic lower-panel exact wrappers preserve the stock availability builder,
    # capture only IDs the stock code actually emits, and clone the stock six-pass
    # submit lifecycle.  The global bitmap hook reaches the exact-caller magic
    # dispatcher first; every non-magic call falls through to the already-validated
    # skill-row -> Status chain.
    rom[MAGIC_PANEL_PREP_CALL_FILE:MAGIC_PANEL_PREP_CALL_FILE + 3] = bytes([
        0x20,
        MAGIC_PANEL_RESET_STUB_CPU & 0xFF,
        (MAGIC_PANEL_RESET_STUB_CPU >> 8) & 0xFF,
    ])
    rom[MAGIC_PANEL_COPY_CALL_FILE:MAGIC_PANEL_COPY_CALL_FILE + 3] = bytes([
        0x20,
        MAGIC_PANEL_CAPTURE_STUB_CPU & 0xFF,
        (MAGIC_PANEL_CAPTURE_STUB_CPU >> 8) & 0xFF,
    ])
    rom[MAGIC_PANEL_SUBMIT_CALL_FILE:MAGIC_PANEL_SUBMIT_CALL_FILE + 3] = bytes([
        0x20,
        MAGIC_PANEL_BATCH_HELPER_CPU & 0xFF,
        (MAGIC_PANEL_BATCH_HELPER_CPU >> 8) & 0xFF,
    ])
    rom[MAGIC_PANEL_BATCH_HELPER_FILE:MAGIC_PANEL_BATCH_HELPER_FILE + len(magic_panel_batch_helper)] = magic_panel_batch_helper
    rom[MAGIC_PANEL_RESET_STUB_FILE:MAGIC_PANEL_RESET_STUB_FILE + len(magic_panel_reset_stub)] = magic_panel_reset_stub
    rom[MAGIC_PANEL_CAPTURE_STUB_FILE:MAGIC_PANEL_CAPTURE_STUB_FILE + len(magic_panel_capture_stub)] = magic_panel_capture_stub
    rom[MAGIC_PANEL_CAPTURE_HELPER_FILE:MAGIC_PANEL_CAPTURE_HELPER_FILE + len(magic_panel_capture_helper)] = magic_panel_capture_helper
    rom[MAGIC_PANEL_RESET_HELPER_FILE:MAGIC_PANEL_RESET_HELPER_FILE + len(magic_panel_reset_helper)] = magic_panel_reset_helper
    rom[MAGIC_PANEL_DISPATCH_FILE:MAGIC_PANEL_DISPATCH_FILE + len(magic_panel_dispatch)] = magic_panel_dispatch

    rom[STATUS_BITMAP_CONVERT_HOOK_FILE:STATUS_BITMAP_CONVERT_HOOK_FILE + 4] = bytes([0x5C, *lo24(MAGIC_PANEL_DISPATCH_CPU)])
    rom[SKILL_VWF_HELPER_FILE:SKILL_VWF_HELPER_FILE + len(skill_vwf_dispatch)] = skill_vwf_dispatch
    rom[STATUS_VWF_HELPER_FILE:STATUS_VWF_HELPER_FILE + len(status_vwf_hook)] = status_vwf_hook
    rom[STATUS_VWF_RENDER_SLOT_FILE:STATUS_VWF_RENDER_SLOT_FILE + len(status_vwf_render_slot)] = status_vwf_render_slot
    rom[STATUS_VWF_COPY_CELLS_FILE:STATUS_VWF_COPY_CELLS_FILE + len(status_vwf_copy_cells)] = status_vwf_copy_cells

    rom[ROM_SIZE_OFFSET] = 0x0C
    update_checksum(rom)
    return make_ips(base, bytes(rom))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("-o", "--output", type=Path, default=ROOT / "build" / "patch.ips")
    args = parser.parse_args()
    base = args.rom.resolve().read_bytes()
    patch = build(base)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(patch)
    print(f"IPS: {args.output}")
    print("Standalone UI VWF; includes exact GAME FILE Mana, battle-banner and existing UI backends; all localized content remains source-owned")


if __name__ == "__main__":
    main()
