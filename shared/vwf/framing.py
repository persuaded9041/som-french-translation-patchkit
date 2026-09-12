"""Shared runtime VWF framing selector source for `vwf_intro`, `vwf_dialogues`, and `vwf_ui`.

The selector receives one stock 8-bit font row in A and the corresponding
12-byte stock-font row offset in X.  It returns the same row shifted left by
the runtime-validated framing amount.  X and the accumulator width are left
unchanged.

`vwf_intro`, `vwf_dialogues`, and `vwf_ui` install the selectors contiguously in bank C7. The
shared stock-row renderer calls this one runtime copy for both paths; `vwf_dialogues` no longer carries duplicate selector payloads in bank ED.
"""
from __future__ import annotations

from shared.core.asm import MiniAssembler, lo24

SHARED_FRAMING_CPU = 0xC744C0
SHARED_FRAMING_FILE = 0x0744C0
SHARED_FRAMING_RESERVED_SIZE = 0xA0


def make_framing_selector() -> bytes:
    """Lowercase selector; its post-z branch targets the immediately following selector."""
    a = MiniAssembler(0)
    a.emit(0xE0, 0x0C, 0x00)             # CPX #$000C (a row0)
    a.rel8(0x90, "done")                 # before a => unchanged
    a.emit(0xE0, 0x44, 0x01)             # CPX #$0144 (after z)
    a.rel8(0xB0, "punctuation")          # after z => next selector

    a.emit(0xE0, 0x6C, 0x00)             # i row0
    a.rel8(0x90, "shift_one")            # a-h
    a.emit(0xE0, 0x78, 0x00)             # j row0
    a.rel8(0x90, "shift_three")          # i
    a.emit(0xE0, 0x84, 0x00)             # k row0
    a.rel8(0x90, "shift_two")            # j
    a.emit(0xE0, 0x90, 0x00)             # l row0
    a.rel8(0x90, "shift_one")            # k
    a.emit(0xE0, 0x9C, 0x00)             # m row0
    a.rel8(0x90, "shift_three")          # l
    a.emit(0xE0, 0xF0, 0x00)             # t row0
    a.rel8(0x90, "shift_one")            # m-s
    a.emit(0xE0, 0xFC, 0x00)             # u row0
    a.rel8(0x90, "shift_two")            # t

    a.label("shift_one")
    a.emit(0x0A)
    a.rel8(0x80, "done")
    a.label("shift_two")
    a.emit(0x0A, 0x0A)
    a.rel8(0x80, "done")
    a.label("shift_three")
    a.emit(0x0A, 0x0A, 0x0A)
    a.label("done")
    a.emit(0x6B)

    # This target is deliberately one byte past the selector. The caller places
    # the punctuation selector immediately after it.
    a.label("punctuation")
    return a.resolve()


def make_punctuation_framing_selector(batch2_cpu: int) -> bytes:
    """Small post-lowercase dispatcher, parameterized only by its batch-2 target."""
    a = MiniAssembler(0)
    a.emit(0xE0, 0x44, 0x01)             # CPX #$0144 ($9B / A row0)
    a.rel8(0x90, "done")                 # before uppercase => unchanged
    a.rel8(0x80, "batch2")               # A and later => fixed JML trampoline
    a.label("done")
    a.emit(0x6B)
    a.emit(0xEA, 0xEA, 0xEA, 0xEA)
    a.label("batch2")
    batch2_offset = len(a.data)
    a.emit(0x5C, *lo24(batch2_cpu))       # JML batch-2 selector
    if batch2_offset != 0x0C:
        raise RuntimeError("VWF punctuation batch-2 trampoline moved from +$0C")
    return a.resolve()


def make_punctuation_framing_batch2_selector() -> bytes:
    """Uppercase, punctuation and French-glyph framing selector."""
    a = MiniAssembler(0)
    a.emit(0xE0, 0xA4, 0x01)             # I row0
    a.rel8(0x90, "shift_one")            # A-H
    a.emit(0xE0, 0xB0, 0x01)             # J row0
    a.rel8(0x90, "shift_three")          # I
    a.emit(0xE0, 0x7C, 0x02)             # after Z
    a.rel8(0x90, "shift_one")            # J-Z

    a.emit(0xE0, 0xF4, 0x02)             # $BF row0
    a.rel8(0x90, "done")                 # $B5-$BE unchanged
    a.emit(0xE0, 0x30, 0x03)             # $C4 row0
    a.rel8(0x90, "done")                 # $BF-$C3 unchanged
    a.emit(0xE0, 0x3C, 0x03)             # $C5 row0
    a.rel8(0x90, "shift_one")            # C4
    a.emit(0xE0, 0x48, 0x03)             # $C6 row0
    a.rel8(0x90, "shift_one")            # C5
    a.emit(0xE0, 0x60, 0x03)             # $C8 row0
    a.rel8(0x90, "done")                 # C6-C7
    a.emit(0xE0, 0x6C, 0x03)             # $C9 row0
    a.rel8(0x90, "shift_two")            # C8
    a.emit(0xE0, 0x84, 0x03)             # $CB row0
    a.rel8(0x90, "done")                 # C9-CA
    a.emit(0xE0, 0x90, 0x03)             # $CC row0
    a.rel8(0x90, "shift_two")            # CB
    a.emit(0xE0, 0x9C, 0x03)             # $CD row0
    a.rel8(0x90, "shift_one")            # CC
    a.emit(0xE0, 0xF0, 0x03)             # $D4 row0
    a.rel8(0x90, "done")                 # CD-D3 unchanged
    a.emit(0xE0, 0xB0, 0x04)             # $E4 row0
    a.rel8(0x90, "shift_one")            # D4-E3

    a.label("done")
    a.emit(0x6B)
    a.label("shift_one")
    a.emit(0x0A, 0x6B)
    a.label("shift_two")
    a.emit(0x0A, 0x0A, 0x6B)
    a.label("shift_three")
    a.emit(0x0A, 0x0A, 0x0A, 0x6B)
    return a.resolve()


FRAMING_SELECTOR = make_framing_selector()
SHARED_PUNCTUATION_CPU = SHARED_FRAMING_CPU + len(FRAMING_SELECTOR)
PUNCTUATION_SELECTOR_SIZE = 16
SHARED_BATCH2_CPU = SHARED_PUNCTUATION_CPU + PUNCTUATION_SELECTOR_SIZE
PUNCTUATION_FRAMING_SELECTOR = make_punctuation_framing_selector(SHARED_BATCH2_CPU)
if len(PUNCTUATION_FRAMING_SELECTOR) != PUNCTUATION_SELECTOR_SIZE:
    raise RuntimeError("Unexpected shared punctuation-selector size")
PUNCTUATION_FRAMING_BATCH2_SELECTOR = make_punctuation_framing_batch2_selector()
SHARED_FRAMING_BUNDLE = (
    FRAMING_SELECTOR + PUNCTUATION_FRAMING_SELECTOR + PUNCTUATION_FRAMING_BATCH2_SELECTOR
)
SHARED_FRAMING_CALL = bytes([0x22, *lo24(SHARED_FRAMING_CPU)])


def validate_stock(base: bytes) -> None:
    region = base[SHARED_FRAMING_FILE:SHARED_FRAMING_FILE + SHARED_FRAMING_RESERVED_SIZE]
    if len(region) != SHARED_FRAMING_RESERVED_SIZE or any(value != 0xFF for value in region):
        raise SystemExit("Expected stock-$FF space for shared VWF framing selector")
    if len(SHARED_FRAMING_BUNDLE) > SHARED_FRAMING_RESERVED_SIZE:
        raise SystemExit(
            f"Shared VWF framing selector is too large: {len(SHARED_FRAMING_BUNDLE):#x} > "
            f"{SHARED_FRAMING_RESERVED_SIZE:#x}"
        )


def install(rom: bytearray) -> None:
    rom[SHARED_FRAMING_FILE:SHARED_FRAMING_FILE + len(SHARED_FRAMING_BUNDLE)] = SHARED_FRAMING_BUNDLE
