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
    - mode 3: Watts Forge row -> Forge one-shot tag;
    - modes 1/2 (and any unexpected value): no UI tag, stock fallback.

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
    a.emit(0xC9, 0x03)
    a.rel8(0xF0, "forge")
    a.rel8(0x80, "classified")

    a.label("ring")
    a.emit(0xA9, RING_UI_MAGIC)
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


def make_ui_renderer() -> bytes:
    """Render only an explicitly tagged Forge or top-level Ring invocation.

    Both backends keep the stock parser and decoded buffer. The Ring backend
    copies the decoded row unchanged. The Forge backend additionally performs
    its already runtime-validated suffix compaction before entering the shared
    low-level VWF renderer.
    """
    a = MiniAssembler(UI_RENDER_CPU)

    # Exact continuity gate: event-engine renderer caller + low-WRAM event bank.
    a.emit(0xC2, 0x20)
    a.emit(0xA3, 0x01)
    a.emit(0xC9, 0x52, 0x11)
    a.emit(0xE2, 0x20)
    a.rel8(0xD0, "reject")
    a.emit(0xAF, *lo24(0x001D03))
    a.emit(0xC9, 0x00)
    a.rel8(0xD0, "reject")
    a.rel8(0x80, "accepted")

    a.label("reject")
    a.emit(0xA9, 0x00)
    a.emit(0x8F, *lo24(0x7E0000 | UI_TAG))
    a.emit(0x5C, *lo24(DISPATCH_CPU))

    a.label("accepted")
    # Capture the one-shot family before consuming it. Dispatcher reaches this
    # routine only for one of the two recognized magic values. X is made 16-bit
    # below anyway, so use it as an ephemeral backend selector: 0=Ring, 1=Forge.
    a.emit(0xAF, *lo24(0x7E0000 | UI_TAG))
    a.emit(0xC9, FORGE_UI_MAGIC)
    a.rel8(0xF0, "accepted_forge")
    a.emit(0xC2, 0x10)
    a.emit(0xA2, 0x00, 0x00)                         # Ring selector
    a.rel8(0x80, "accepted_kind")
    a.label("accepted_forge")
    a.emit(0xC2, 0x10)
    a.emit(0xA2, 0x01, 0x00)                         # Forge selector
    a.label("accepted_kind")
    a.emit(0xA9, 0x00)
    a.emit(0x8F, *lo24(0x7E0000 | UI_TAG))
    a.emit(0xDA)                                      # preserve selector
    # Shared low-level renderer scope.  Value 1 is the already validated active
    # marker used by the generic row/outline helpers.
    a.emit(0xA9, 0x01)
    a.emit(0x8F, *lo24(0x7E0000 | RENDER_ACTIVE))
    a.emit(0xAF, *lo24(0x7E0000 | DECODED_COUNT))
    a.emit(0x29, 0x7F)
    a.emit(0x8F, *lo24(0x7E0000 | SAVED_COUNT))
    a.emit(0xA9, 0x00)
    a.emit(0x8F, *lo24(0x7E0000 | PHYSICAL_CELLS))
    a.emit(0x8F, *lo24(0x7E0000 | PIXEL_CURSOR))

    # Render-time private copy only. Parser stays on the stock $A1A4 buffer.
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

    # Restore the explicit backend selector captured from UI_TAG. Ring rows
    # already contain their complete decoded title and must never run through
    # the Forge suffix mover.
    a.emit(0xFA)                                      # PLX: 0=Ring, 1=Forge
    a.emit(0xE0, 0x01, 0x00)
    a.rel8(0xD0, "render_common")

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

    a.label("render_common")
    # Clear 32-cell bitmap, then enter the generic VWF renderer at the stock
    # character loop.  38 private slots are safe; unused tail bytes are spaces.
    a.emit(0xA2, 0x00, 0x00)
    a.emit(0xA9, 0x00)
    a.label("clear_bitmap")
    a.emit(0x9E, 0x00, 0x90)
    a.emit(0xE8)
    a.emit(0xE0, 0x80, 0x01)
    a.rel8(0xD0, "clear_bitmap")
    a.emit(0xA9, 0x26)
    a.emit(0x8D, 0x76, 0xA1)
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

    width_table = make_width_table(base)
    submit_wrapper = make_submit_wrapper()
    renderer = make_ui_renderer()
    if len(submit_wrapper) > SUBMIT_WRAPPER_RESERVED_SIZE:
        raise SystemExit("UI VWF submit wrapper too large")
    if len(renderer) > UI_RENDER_RESERVED_SIZE:
        raise SystemExit(f"UI VWF renderer too large: {len(renderer):#x}")

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
    rom[UI_RENDER_FILE:UI_RENDER_FILE + len(renderer)] = renderer
    rom[WIDTH_TABLE_FILE:WIDTH_TABLE_FILE + len(width_table)] = width_table
    rom[SUBMIT_WRAPPER_FILE:SUBMIT_WRAPPER_FILE + len(submit_wrapper)] = submit_wrapper

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
    print("Standalone UI VWF; Forge path enabled; no component dependency")


if __name__ == "__main__":
    main()
