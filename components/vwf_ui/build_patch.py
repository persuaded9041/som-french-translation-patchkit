#!/usr/bin/env python3
"""Build standalone UI VWF extensions.

Current runtime-validated backend: Watts Forge current-weapon row.
The component is independent of `vwf_dialogues`; only byte-identical shared VWF
infrastructure is reused.
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
DECODED_COUNT = 0xA1CE
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

def make_ui_renderer() -> bytes:
    """Render only an explicitly tagged Forge or top-level Ring invocation.

    Ring, Forge, shop merchandise rows, the exact D9 shop/forge-response
    backend and the stock type-2 money window keep the stock parser/decoded
    buffer. The exact battle/status banner submits use parser mode 3 and retain
    their already-decoded 49-byte private buffer. Currency text is never translated here: standalone `vwf_ui` renders
    whatever two-glyph currency unit the source component provides (`GP` on a
    clean USA ROM, `PO` when `french_resources` is present). Presentation-only gaps
    are handled by the shared VWF geometry helpers. Forge keeps its separately
    validated suffix compaction.
    """
    a = MiniAssembler(UI_RENDER_CPU)

    # Exact continuity gate: all UI families must come from the event-engine
    # renderer caller. Ring/Forge then require bank $00; the shop response family
    # requires the separately tagged bank $D9 path.
    a.emit(0xC2, 0x20)
    a.emit(0xA3, 0x01)
    a.emit(0xC9, 0x52, 0x11)
    a.emit(0xE2, 0x20)
    a.rel8(0xD0, "reject")

    # Capture the family before consuming it. X is an ephemeral backend
    # selector: 0=Ring, 1=Forge, 2=D9 shop/forge response,
    # 3=shop merchandise row, 4=type-2 money window, 5=battle/status banner.
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

    a.label("kind_bank")
    a.emit(0xE0, 0x02, 0x00)
    a.rel8(0xF0, "bank_shop")
    a.emit(0xE0, 0x04, 0x00)
    a.rel8(0xF0, "bank_money")
    a.emit(0xE0, 0x05, 0x00)
    a.rel8(0xF0, "bank_battle")
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

    width_table = make_width_table(base)
    submit_wrapper = make_submit_wrapper()
    shop_dispatch_wrapper = make_shop_dispatch_wrapper()
    shop_suffix_gap_helper = make_shop_suffix_gap_helper()
    battle_submit_50 = make_battle_submit_wrapper(BATTLE_SUBMIT_50_WRAPPER_CPU, 0x637D, 0xA3)
    battle_submit_51 = make_battle_submit_wrapper(BATTLE_SUBMIT_51_WRAPPER_CPU, 0x637F, 0x9F)
    renderer = make_ui_renderer()
    if len(submit_wrapper) > SUBMIT_WRAPPER_RESERVED_SIZE:
        raise SystemExit("UI VWF submit wrapper too large")
    if len(renderer) > UI_RENDER_RESERVED_SIZE:
        raise SystemExit(f"UI VWF renderer too large: {len(renderer):#x}")
    if len(shop_dispatch_wrapper) > SHOP_DISPATCH_WRAPPER_RESERVED_SIZE:
        raise SystemExit("UI VWF shop dispatch wrapper too large")
    if len(battle_submit_50) > BATTLE_SUBMIT_WRAPPER_RESERVED_SIZE or len(battle_submit_51) > BATTLE_SUBMIT_WRAPPER_RESERVED_SIZE:
        raise SystemExit("UI VWF battle submit wrapper too large")
    if UI_RENDER_FILE + len(renderer) > SHOP_SUFFIX_GAP_HELPER_FILE:
        raise SystemExit("UI VWF renderer overlaps shop suffix-gap helper")
    if SHOP_SUFFIX_GAP_HELPER_FILE + len(shop_suffix_gap_helper) > WIDTH_TABLE_FILE:
        raise SystemExit("UI VWF shop suffix-gap helper overlaps width table")

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
    print("Standalone UI VWF; includes exact C0:637D/637F battle-banner backend; all localized content remains source-owned")


if __name__ == "__main__":
    main()
