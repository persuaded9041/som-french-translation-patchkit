"""Context-sensitive direct-glyph/DTE boundary for ordinary event dialogue.

The translated intro (`french_intro`) keeps its runtime-validated $E6 DTE
boundary and 25 private DTE pairs. `vwf_dialogues` / `french_dialogues` may enable an $E8
boundary only for real event-engine dialogue, making $E6/$E7 direct glyphs
there without changing intro decoding or GAME SELECT.
"""
from __future__ import annotations

from shared.core.asm import MiniAssembler, lo16, lo24
from shared.charset import DIALOGUE_DTE_THRESHOLD, FULL_DTE_THRESHOLD
from shared.vwf.text_buffer import (
    DIALOGUE_CONFIG_CPU,
    DIALOGUE_MARKER,
    INTRO_CONFIG_CPU,
    INTRO_MARKER,
    INTRO_START,
    PARSER_MODE,
)

DTE_ROUTE_FILE = 0x0016F5
DTE_ROUTE_CPU = 0xC016F5
DTE_ROUTE_SIGNATURE = bytes.fromhex("C9 D3 B0 14")
DTE_ROUTE_HELPER_FILE = 0x074570
DTE_ROUTE_HELPER_CPU = 0xC74570
DTE_ROUTE_RESERVED_SIZE = 0x80
DIALOGUE_DTE_CONFIG_FILE = 0x074C85
DIALOGUE_DTE_CONFIG_CPU = 0xC74C85
DIALOGUE_DTE_MARKER = DIALOGUE_DTE_THRESHOLD
EVENT_PARSER_RETURN = 0x114B
STOCK_INTRO_END = 0x0E44


def _assemble_router() -> bytes:
    a = MiniAssembler(DTE_ROUTE_HELPER_CPU)

    def jml(cpu: int) -> None:
        a.emit(0x5C, *lo24(cpu))

    # Preserve the source byte. When `vwf_dialogues` is installed, reuse the
    # parser mode already selected by the shared VWF buffer initializer:
    # mode 2 is real dialogue ($E8 threshold), mode 1 is the translated intro
    # ($E6 threshold). This avoids re-deriving context midway through parsing.
    # `french_dialogues` standalone has no parser-mode owner, so only trust this
    # scratch byte when the `vwf_dialogues` runtime marker is present.
    a.emit(0x48)                          # PHA source byte (8-bit)
    # `name_entry_extended` (with `french_name_entry_extended` in localized builds) relocates the Name Entry character/help resource to bank
    # $E4. That bank is reserved exclusively for the resource, so render its
    # grid bytes with the dialogue-style $E8 boundary. This keeps $E6/$E7 as
    # direct ° / ; instead of stock DTE pairs while leaving all other parser
    # contexts unchanged.
    a.emit(0x8B)                          # PHB
    a.emit(0x68)                          # PLA -> current DB; source stays stacked
    a.emit(0xC9, 0xE4)
    a.rel8(0xF0, "dialogue_saved")
    a.emit(0xAF, *lo24(DIALOGUE_CONFIG_CPU))
    a.emit(0xC9, DIALOGUE_MARKER)
    a.rel8(0xD0, "fallback_caller")
    a.emit(0xAF, *lo24(0x7E0000 + PARSER_MODE))
    a.emit(0xC9, 0x02)
    a.rel8(0xF0, "dialogue_saved")
    a.emit(0xC9, 0x01)
    a.rel8(0xF0, "base_saved")

    # Standalone `french_dialogues`, or non-VWF parser context: inspect the parser
    # caller and live event source as before. The event parser's JSR return
    # ($114B) remains on the stack for the whole decode.
    a.label("fallback_caller")
    a.emit(0xC2, 0x20)                    # REP #$20
    a.emit(0xA3, 0x02)                    # LDA 2,S (caller return under saved byte)
    a.emit(0xC9, *lo16(EVENT_PARSER_RETURN))
    a.rel8(0xD0, "base16")               # not event-engine parser
    a.emit(0xE2, 0x20)                    # SEP #$20

    # Extended dialogue profile is opt-in. Without `vwf_dialogues` / `french_dialogues`, preserve the
    # established full-French $E6 boundary everywhere.
    a.emit(0xAF, *lo24(DIALOGUE_DTE_CONFIG_CPU))
    a.emit(0xC9, DIALOGUE_DTE_MARKER)
    a.rel8(0xD0, "base_saved")

    # Only event $0400 keeps $E6 when the extended dialogue profile is active.
    # C9 and relocated E8-EC dialogue can go straight to the $E8 decision.
    a.emit(0xAF, *lo24(0x001D03))
    a.emit(0xC9, 0xCA)
    a.rel8(0xD0, "dialogue_saved")

    # When `vwf_intro` is present, use its configured intro runtime end. In an
    # 08-only build, fall back to the clean-USA $0400 end ($0E44).
    a.emit(0xAF, *lo24(INTRO_CONFIG_CPU))
    a.emit(0xC9, INTRO_MARKER)
    a.rel8(0xD0, "stock_intro_end")
    a.emit(0xC2, 0x20)
    a.emit(0xAF, *lo24(0x001D01))
    a.emit(0xC9, *lo16(INTRO_START))
    a.rel8(0x90, "dialogue16")
    a.emit(0xCF, *lo24(INTRO_CONFIG_CPU + 1))
    a.rel8(0x90, "base16_saved")
    a.rel8(0x80, "dialogue16")

    a.label("stock_intro_end")
    a.emit(0xC2, 0x20)
    a.emit(0xAF, *lo24(0x001D01))
    a.emit(0xC9, *lo16(INTRO_START))
    a.rel8(0x90, "dialogue16")
    a.emit(0xC9, *lo16(STOCK_INTRO_END))
    a.rel8(0x90, "base16_saved")

    a.label("dialogue16")
    a.emit(0xE2, 0x20)
    a.label("dialogue_saved")
    a.emit(0x68)                          # PLA source byte
    a.emit(0xC9, DIALOGUE_DTE_THRESHOLD)
    a.rel8(0xB0, "upper_dte")
    jml(0xC016F9)                         # continue stock lower/direct/control tests

    a.label("base16")
    a.emit(0xE2, 0x20)
    a.label("base_saved")
    a.emit(0x68)
    a.emit(0xC9, FULL_DTE_THRESHOLD)
    a.rel8(0xB0, "upper_dte")
    jml(0xC016F9)

    a.label("base16_saved")
    a.emit(0xE2, 0x20)
    a.rel8(0x80, "base_saved")

    a.label("upper_dte")
    jml(0xC0170D)                         # stock upper-DTE expansion path
    return a.resolve()


DTE_ROUTE_HELPER = _assemble_router()
DTE_ROUTE_HOOK = bytes([0x5C, *lo24(DTE_ROUTE_HELPER_CPU)])


def validate_stock(base: bytes) -> None:
    if base[DTE_ROUTE_FILE:DTE_ROUTE_FILE + len(DTE_ROUTE_SIGNATURE)] != DTE_ROUTE_SIGNATURE:
        raise SystemExit("Unexpected clean-US direct/DTE decision signature")
    region = base[DTE_ROUTE_HELPER_FILE:DTE_ROUTE_HELPER_FILE + DTE_ROUTE_RESERVED_SIZE]
    if len(region) != DTE_ROUTE_RESERVED_SIZE or any(value != 0xFF for value in region):
        raise SystemExit("Expected stock-$FF space for dialogue DTE router")
    if base[DIALOGUE_DTE_CONFIG_FILE] != 0xFF:
        raise SystemExit("Expected stock-$FF dialogue DTE config byte")
    if len(DTE_ROUTE_HELPER) > DTE_ROUTE_RESERVED_SIZE:
        raise SystemExit(
            f"Dialogue DTE router is too large: {len(DTE_ROUTE_HELPER):#x} > "
            f"{DTE_ROUTE_RESERVED_SIZE:#x}"
        )


def install(rom: bytearray) -> None:
    rom[DTE_ROUTE_FILE:DTE_ROUTE_FILE + len(DTE_ROUTE_HOOK)] = DTE_ROUTE_HOOK
    rom[DTE_ROUTE_HELPER_FILE:DTE_ROUTE_HELPER_FILE + len(DTE_ROUTE_HELPER)] = DTE_ROUTE_HELPER


def enable_extended_dialogue(rom: bytearray) -> None:
    rom[DIALOGUE_DTE_CONFIG_FILE] = DIALOGUE_DTE_MARKER
