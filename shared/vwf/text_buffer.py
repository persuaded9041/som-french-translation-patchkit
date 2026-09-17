"""Shared decoded-text/private-capacity bridge for VWF `vwf_intro`, `vwf_dialogues`, and `vwf_ui`.

The stock text engine owns only 33 bytes at $7E:A1A4-$A1C4. Bytes $A1C5+
are live engine state, so a 38-character parser cannot safely extend that
buffer in place.  This module installs one byte-identical set of parser hooks
that can route selected event-engine invocations to the already validated
44-byte private buffer at $7E:9390-$93BB; exact battle mode 3 extends that same
contiguous span through $93C0 for 49 parser bytes.

`vwf_intro` enables mode 1 for the intro runtime window containing event $0400. `vwf_dialogues`
enables mode 2 for ordinary event-engine text in stock banks $C9/$CA and
for `french_dialogues` relocated event banks $E8-$EC. `vwf_ui` keeps parser mode
stock for its ordinary UI families, but its exact battle/status tag `$AC` selects
private parser mode 3 and the 49-byte span `$7E:9390-$93C0`. The common capacity
hook also provides exact one-shot UI-family margins (Forge +3; top-level Ring
Menu +4). GAME SELECT
also calls the stock parser initializer, so activation is structurally gated by
the caller return address ($114B from JSR $C0:16B8 at $C0:1149).
"""
from __future__ import annotations

from shared.core.asm import MiniAssembler, lo16, lo24
from .ui import (
    UI_CONFIG_CPU,
    UI_MARKER,
    UI_TAG,
    FORGE_UI_MAGIC,
    RING_UI_MAGIC,
    BATTLE_UI_MAGIC,
)

# Stock hooks shared by `vwf_intro` and `vwf_dialogues`.
BUFFER_INIT_FILE = 0x0016B8
CAPACITY_FILE = 0x0016C6
PARSER_WRITE_FILE = 0x0017CE
PREV_CHAR_FILE = 0x0018DE

BUFFER_INIT_SIGNATURE = bytes.fromhex("A2 00 00 A9")
CAPACITY_SIGNATURE = bytes.fromhex("AD 6A A1 38 ED 81 A1 8D CA A1")
PARSER_WRITE_SIGNATURE = bytes.fromhex("9D A4 A1 E8")
PREV_CHAR_SIGNATURE = bytes.fromhex("BF A4 A1 7E")

# Shared helper locations. These are stock-$FF free space already adjacent to
# `vwf_intro`'s existing C7 allocations, so `vwf_intro` need not expand ROM.
PARSER_WRITE_CPU = 0xC743D0
PARSER_WRITE_FILE_HELPER = 0x0743D0
BUFFER_INIT_CPU = 0xC74AC0
BUFFER_INIT_FILE_HELPER = 0x074AC0
PREV_CHAR_CPU = 0xC74B40
PREV_CHAR_FILE_HELPER = 0x074B40
CAPACITY_CPU = 0xC74BC0
CAPACITY_FILE_HELPER = 0x074BC0
MODE_CLASSIFIER_CPU = 0xC74900
MODE_CLASSIFIER_FILE = 0x074900
MODE_CLASSIFIER_RESERVED_SIZE = 0x40

# Runtime configuration lives in a small stock-$FF gap between the intro runtime helper ranges and the intro-private DTE table owned by `french_intro`.
INTRO_CONFIG_CPU = 0xC74C80
INTRO_CONFIG_FILE = 0x074C80
DIALOGUE_CONFIG_CPU = 0xC74C84
DIALOGUE_CONFIG_FILE = 0x074C84
INTRO_MARKER = 0x05
DIALOGUE_MARKER = 0x06
INTRO_START = 0x0C02

# Parser-private mode byte. It is needed only while decoding; `vwf_intro`
# later reuses $9380 as its rendered-character count after parsing has ended.
PARSER_MODE = 0x9380
PRIVATE_BUFFER = 0x9390
PRIVATE_BUFFER_SIZE = 0x002C  # 44 bytes: intro/dialogue validated path
BATTLE_PRIVATE_BUFFER_SIZE = 0x0031  # 49 bytes: 48 visible + following control
BATTLE_PARSER_MODE = 0x03
STOCK_BUFFER = 0xA1A4

# C0:1149 JSR $16B8 leaves $114B on the stack. GAME SELECT's JSR at $2359
# leaves $235B instead and must never enter the private parser path.
EVENT_PARSER_RETURN = 0x114B


def _assemble_mode_classifier() -> bytes:
    """Return parser mode 0/2/3 after the exact event-parser caller gate.

    Battle mode is armed only by vwf_ui's one-shot battle tag.  Dialogue mode
    preserves the existing C9/CA/E8-EC classification. Intro mode is resolved
    by the caller before entering this helper so it keeps priority unchanged.
    """
    a = MiniAssembler(MODE_CLASSIFIER_CPU)

    a.emit(0xAF, *lo24(UI_CONFIG_CPU))
    a.emit(0xC9, UI_MARKER)
    a.rel8(0xD0, "dialogue")
    a.emit(0xAF, *lo24(0x7E0000 | UI_TAG))
    a.emit(0xC9, BATTLE_UI_MAGIC)
    a.rel8(0xD0, "dialogue")
    a.emit(0xA9, BATTLE_PARSER_MODE)
    a.emit(0x6B)

    a.label("dialogue")
    a.emit(0xAF, *lo24(DIALOGUE_CONFIG_CPU))
    a.emit(0xC9, DIALOGUE_MARKER)
    a.rel8(0xD0, "stock")
    a.emit(0xAF, *lo24(0x001D03))
    a.emit(0xC9, 0xC9)
    a.rel8(0xF0, "dialogue_active")
    a.emit(0xC9, 0xCA)
    a.rel8(0xF0, "dialogue_active")
    a.emit(0xC9, 0xE8)
    a.rel8(0x90, "stock")
    a.emit(0xC9, 0xED)
    a.rel8(0xB0, "stock")

    a.label("dialogue_active")
    a.emit(0xA9, 0x02)
    a.emit(0x6B)
    a.label("stock")
    a.emit(0xA9, 0x00)
    a.emit(0x6B)
    return a.resolve()


def _assemble_buffer_init() -> bytes:
    a = MiniAssembler(BUFFER_INIT_CPU)

    a.emit(0x9C, *lo16(PARSER_MODE))       # STZ parser mode

    # Structural caller gate: event-engine parser only.
    a.emit(0xC2, 0x20)                     # REP #$20
    a.emit(0xA3, 0x01)                     # LDA 1,S
    a.emit(0xC9, *lo16(EVENT_PARSER_RETURN))
    a.emit(0xE2, 0x20)                     # SEP #$20
    a.rel8(0xD0, "stock_init")

    # `vwf_intro` intro mode has priority when its config marker is present.
    a.emit(0xAF, *lo24(INTRO_CONFIG_CPU))
    a.emit(0xC9, INTRO_MARKER)
    a.rel8(0xD0, "generic_check")
    a.emit(0xAF, *lo24(0x001D03))
    a.emit(0xC9, 0xCA)
    a.rel8(0xD0, "generic_check")
    a.emit(0xC2, 0x20)
    a.emit(0xAF, *lo24(0x001D01))
    a.emit(0xC9, *lo16(INTRO_START))
    a.rel8(0x90, "generic_check_16")
    a.emit(0xCF, *lo24(INTRO_CONFIG_CPU + 1))
    a.rel8(0x90, "intro_active")

    a.label("generic_check_16")
    a.emit(0xE2, 0x20)
    a.label("generic_check")
    # Shared external classifier keeps this already-tight helper below 128 bytes
    # while adding the exact battle one-shot mode.
    a.emit(0x22, *lo24(MODE_CLASSIFIER_CPU))
    a.rel8(0xF0, "stock_init")             # A=0 -> stock
    a.rel8(0x80, "private_init")           # A=2/3 -> selected private mode

    a.label("intro_active")
    a.emit(0xE2, 0x20)                     # pointer comparison was 16-bit
    a.emit(0xA9, 0x01)                     # mode 1 = intro validated path

    a.label("private_init")
    a.emit(0x8D, *lo16(PARSER_MODE))
    a.emit(0xA2, *lo16(0x0000))
    a.emit(0xA9, 0x80)
    a.label("private_loop")
    a.emit(0x9D, *lo16(PRIVATE_BUFFER))
    a.emit(0xE8)
    a.emit(0xE0, *lo16(PRIVATE_BUFFER_SIZE))
    a.rel8(0xD0, "private_loop")

    # Battle banner may borrow the five contiguous bytes immediately before
    # UI_TAG.  Dialogue choice scratch uses them only in mutually exclusive
    # dialogue mode, so intro/dialogue retain their byte-identical 44-byte span.
    a.emit(0xAD, *lo16(PARSER_MODE))
    a.emit(0xC9, BATTLE_PARSER_MODE)
    a.rel8(0xD0, "private_done")
    a.emit(0xA9, 0x80)
    a.label("battle_tail_loop")
    a.emit(0x9D, *lo16(PRIVATE_BUFFER))
    a.emit(0xE8)
    a.emit(0xE0, *lo16(BATTLE_PRIVATE_BUFFER_SIZE))
    a.rel8(0xD0, "battle_tail_loop")

    a.label("private_done")
    a.emit(0x5C, *lo24(0xC016C6))

    a.label("stock_init")
    a.emit(0xA2, *lo16(0x0000))
    a.emit(0xA9, 0x80)
    a.label("stock_loop")
    a.emit(0x9D, *lo16(STOCK_BUFFER))
    a.emit(0xE8)
    a.emit(0xE0, *lo16(0x0021))
    a.rel8(0xD0, "stock_loop")
    a.emit(0x5C, *lo24(0xC016C6))
    return a.resolve()

def _assemble_parser_write() -> bytes:
    a = MiniAssembler(PARSER_WRITE_CPU)
    a.emit(0x48)                             # PHA decoded byte
    a.emit(0xAD, *lo16(PARSER_MODE))
    a.rel8(0xF0, "stock")
    a.emit(0x68)
    a.emit(0x9D, *lo16(PRIVATE_BUFFER))
    a.emit(0xE8)
    a.emit(0x5C, *lo24(0xC017D2))
    a.label("stock")
    a.emit(0x68)
    a.emit(0x9D, *lo16(STOCK_BUFFER))
    a.emit(0xE8)
    a.emit(0x5C, *lo24(0xC017D2))
    return a.resolve()


def _assemble_prev_char() -> bytes:
    a = MiniAssembler(PREV_CHAR_CPU)
    # Stock LDA.l is 16-bit here; temporarily inspect the mode in 8-bit A.
    a.emit(0xE2, 0x20)
    a.emit(0xAD, *lo16(PARSER_MODE))
    a.rel8(0xF0, "stock8")
    a.emit(0xC2, 0x20)
    a.emit(0xBF, *lo24(0x7E0000 | PRIVATE_BUFFER))
    a.emit(0x5C, *lo24(0xC018E2))
    a.label("stock8")
    a.emit(0xC2, 0x20)
    a.emit(0xBF, *lo24(0x7E0000 | STOCK_BUFFER))
    a.emit(0x5C, *lo24(0xC018E2))
    return a.resolve()


def _assemble_capacity() -> bytes:
    a = MiniAssembler(CAPACITY_CPU)
    a.emit(0xAD, *lo16(PARSER_MODE))
    a.rel8(0xF0, "stock")
    a.emit(0xC9, 0x01)
    a.rel8(0xF0, "intro")
    a.emit(0xC9, BATTLE_PARSER_MODE)
    a.rel8(0xF0, "battle")

    # Dialogue mode keeps the stock remaining-line calculation but grants ten
    # extra parser units. Runtime calibration on $0107 proved that the stock
    # fresh-line remainder is 29 units here, so +10 is required to expose the
    # intended 39-unit budget = 38 visible glyphs plus the following control.
    # Cap at 39 for defensive consistency.
    a.emit(0xAD, *lo16(0xA16A))
    a.emit(0x38)
    a.emit(0xED, *lo16(0xA181))
    a.emit(0x18)
    a.emit(0x69, 0x0A)
    a.emit(0xC9, 0x28)                     # >= 40?
    a.rel8(0x90, "store")
    a.emit(0xA9, 0x27)
    a.rel8(0x80, "store")

    a.label("intro")
    # Preserve `vwf_intro`'s runtime-validated fixed intro capacity exactly.
    a.emit(0xA9, 0x27)
    a.rel8(0x80, "store")

    a.label("battle")
    # 49 parser units = 48 decoded visible bytes plus the following control.
    a.emit(0xA9, BATTLE_PRIVATE_BUFFER_SIZE)
    a.rel8(0x80, "store")

    a.label("stock")
    a.emit(0xAD, *lo16(0xA16A))
    a.emit(0x38)
    a.emit(0xED, *lo16(0xA181))

    # `vwf_ui` keeps the stock parser/buffer and grants only the exact local
    # margin required by the one-shot UI family tag. Forge keeps its runtime-
    # validated +3 budget. The top-level Ring Menu gets +4: the stock fresh
    # remainder is 29 units, so 33 units exactly fill the stock 33-byte buffer
    # and allow 32 visible characters plus the following control. No UI path
    # is permitted to exceed the stock buffer.
    a.emit(0x48)                              # PHA stock remaining count
    a.emit(0xAF, *lo24(UI_CONFIG_CPU))
    a.emit(0xC9, UI_MARKER)
    a.rel8(0xD0, "stock_no_ui")
    a.emit(0xAF, *lo24(0x7E0000 | UI_TAG))
    a.emit(0xC9, FORGE_UI_MAGIC)
    a.rel8(0xF0, "forge_ui")
    a.emit(0xC9, RING_UI_MAGIC)
    a.rel8(0xD0, "stock_no_ui")
    a.emit(0x68)                              # PLA count
    a.emit(0x18)                              # CLC
    a.emit(0x69, 0x04)                        # +4 exact Ring Menu margin
    a.emit(0xC9, 0x22)                        # >= 34 would exceed stock buffer
    a.rel8(0x90, "store")
    a.emit(0xA9, 0x21)                        # cap at 33 stock bytes
    a.rel8(0x80, "store")
    a.label("forge_ui")
    a.emit(0x68)                              # PLA count
    a.emit(0x18)                              # CLC
    a.emit(0x69, 0x03)                        # +3 validated Forge margin
    a.rel8(0x80, "store")
    a.label("stock_no_ui")
    a.emit(0x68)

    a.label("store")
    a.emit(0x8D, *lo16(0xA1CA))
    a.emit(0x6B)
    return a.resolve()


MODE_CLASSIFIER_HELPER = _assemble_mode_classifier()
BUFFER_INIT_HELPER = _assemble_buffer_init()
PARSER_WRITE_HELPER = _assemble_parser_write()
PREV_CHAR_HELPER = _assemble_prev_char()
CAPACITY_HELPER = _assemble_capacity()

BUFFER_INIT_HOOK = bytes([0x5C, *lo24(BUFFER_INIT_CPU)])
PARSER_WRITE_HOOK = bytes([0x5C, *lo24(PARSER_WRITE_CPU)])
PREV_CHAR_HOOK = bytes([0x5C, *lo24(PREV_CHAR_CPU)])
CAPACITY_HOOK = bytes([0x22, *lo24(CAPACITY_CPU), 0xEA, 0xEA, 0xEA, 0xEA, 0xEA, 0xEA])


def validate_stock(base: bytes) -> None:
    for offset, signature, label in (
        (BUFFER_INIT_FILE, BUFFER_INIT_SIGNATURE, "buffer init"),
        (CAPACITY_FILE, CAPACITY_SIGNATURE, "decoder capacity"),
        (PARSER_WRITE_FILE, PARSER_WRITE_SIGNATURE, "parser write"),
        (PREV_CHAR_FILE, PREV_CHAR_SIGNATURE, "previous-character read"),
    ):
        if base[offset:offset + len(signature)] != signature:
            raise SystemExit(f"Unexpected clean-US shared VWF {label} signature")

    for start, size, label in (
        (MODE_CLASSIFIER_FILE, MODE_CLASSIFIER_RESERVED_SIZE, "parser-mode classifier"),
        (PARSER_WRITE_FILE_HELPER, 0x30, "parser-write helper"),
        (BUFFER_INIT_FILE_HELPER, 0x80, "buffer-init helper"),
        (PREV_CHAR_FILE_HELPER, 0x40, "previous-char helper"),
        (CAPACITY_FILE_HELPER, 0x70, "capacity helper"),
        (INTRO_CONFIG_FILE, 0x05, "VWF parser config"),
    ):
        if any(value != 0xFF for value in base[start:start + size]):
            raise SystemExit(f"Expected stock-$FF space for shared VWF {label}")

    limits = (
        (len(MODE_CLASSIFIER_HELPER), MODE_CLASSIFIER_RESERVED_SIZE, "parser-mode classifier"),
        (len(PARSER_WRITE_HELPER), 0x30, "parser-write helper"),
        (len(BUFFER_INIT_HELPER), 0x80, "buffer-init helper"),
        (len(PREV_CHAR_HELPER), 0x40, "previous-char helper"),
        (len(CAPACITY_HELPER), 0x70, "capacity helper"),
    )
    for size, limit, label in limits:
        if size > limit:
            raise SystemExit(f"Shared VWF {label} is too large: {size:#x} > {limit:#x}")


def install_common(rom: bytearray) -> None:
    rom[BUFFER_INIT_FILE:BUFFER_INIT_FILE + len(BUFFER_INIT_HOOK)] = BUFFER_INIT_HOOK
    rom[CAPACITY_FILE:CAPACITY_FILE + len(CAPACITY_HOOK)] = CAPACITY_HOOK
    rom[PARSER_WRITE_FILE:PARSER_WRITE_FILE + len(PARSER_WRITE_HOOK)] = PARSER_WRITE_HOOK
    rom[PREV_CHAR_FILE:PREV_CHAR_FILE + len(PREV_CHAR_HOOK)] = PREV_CHAR_HOOK

    for offset, payload in (
        (MODE_CLASSIFIER_FILE, MODE_CLASSIFIER_HELPER),
        (PARSER_WRITE_FILE_HELPER, PARSER_WRITE_HELPER),
        (BUFFER_INIT_FILE_HELPER, BUFFER_INIT_HELPER),
        (PREV_CHAR_FILE_HELPER, PREV_CHAR_HELPER),
        (CAPACITY_FILE_HELPER, CAPACITY_HELPER),
    ):
        rom[offset:offset + len(payload)] = payload


def enable_intro(rom: bytearray, intro_end_ptr: int) -> None:
    if not INTRO_START < intro_end_ptr <= 0xFFFF:
        raise ValueError(f"invalid intro end pointer: {intro_end_ptr:#x}")
    rom[INTRO_CONFIG_FILE] = INTRO_MARKER
    rom[INTRO_CONFIG_FILE + 1:INTRO_CONFIG_FILE + 3] = bytes(lo16(intro_end_ptr))


def enable_dialogue(rom: bytearray) -> None:
    rom[DIALOGUE_CONFIG_FILE] = DIALOGUE_MARKER
