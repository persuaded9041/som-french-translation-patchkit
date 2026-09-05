"""Shared runtime VWF framing selector source for components 05 and 06.

The selector receives one stock 8-bit font row in A and the corresponding
12-byte stock-font row offset in X.  It returns the same row shifted left by
the runtime-validated framing amount.  X and the accumulator width are left
unchanged.

Components 05 and 06 install the selectors contiguously in bank C7. The
shared stock-row renderer calls this one runtime copy for both paths; component
06 no longer carries duplicate selector payloads in bank ED.
"""
from __future__ import annotations

from .asm65816 import lo24

SHARED_FRAMING_CPU = 0xC744C0
SHARED_FRAMING_FILE = 0x0744C0
SHARED_FRAMING_RESERVED_SIZE = 0xA0


def _resolve_rel8(
    code: bytearray, labels: dict[str, int], branches: list[tuple[int, str]]
) -> bytes:
    for pos, target in branches:
        rel = labels[target] - (pos + 1)
        if not -128 <= rel <= 127:
            raise ValueError(f"branch out of range to {target}: {rel}")
        code[pos] = rel & 0xFF
    return bytes(code)


def make_framing_selector() -> bytes:
    """Lowercase selector; its post-z branch targets the immediately following selector."""
    code = bytearray()
    labels: dict[str, int] = {}
    branches: list[tuple[int, str]] = []

    def emit(*vals: int) -> None:
        code.extend(vals)

    def label(name: str) -> None:
        labels[name] = len(code)

    def br(op: int, target: str) -> None:
        emit(op, 0)
        branches.append((len(code) - 1, target))

    emit(0xE0, 0x0C, 0x00)             # CPX #$000C (a row0)
    br(0x90, "done")                    # before a => unchanged
    emit(0xE0, 0x44, 0x01)             # CPX #$0144 (after z)
    br(0xB0, "punctuation")             # after z => next selector

    emit(0xE0, 0x6C, 0x00)             # i row0
    br(0x90, "shift_one")               # a-h
    emit(0xE0, 0x78, 0x00)             # j row0
    br(0x90, "shift_three")             # i
    emit(0xE0, 0x84, 0x00)             # k row0
    br(0x90, "shift_two")               # j
    emit(0xE0, 0x90, 0x00)             # l row0
    br(0x90, "shift_one")               # k
    emit(0xE0, 0x9C, 0x00)             # m row0
    br(0x90, "shift_three")             # l
    emit(0xE0, 0xF0, 0x00)             # t row0
    br(0x90, "shift_one")               # m-s
    emit(0xE0, 0xFC, 0x00)             # u row0
    br(0x90, "shift_two")               # t

    label("shift_one")
    emit(0x0A)
    br(0x80, "done")
    label("shift_two")
    emit(0x0A, 0x0A)
    br(0x80, "done")
    label("shift_three")
    emit(0x0A, 0x0A, 0x0A)
    label("done")
    emit(0x6B)

    # The branch above deliberately targets one byte past this selector.  The
    # caller must place the punctuation selector immediately after it.
    label("punctuation")
    return _resolve_rel8(code, labels, branches)


def make_punctuation_framing_selector(batch2_cpu: int) -> bytes:
    """Small post-lowercase dispatcher, parameterized only by its batch-2 target."""
    code = bytearray()
    labels: dict[str, int] = {}
    branches: list[tuple[int, str]] = []

    def emit(*vals: int) -> None:
        code.extend(vals)

    def label(name: str) -> None:
        labels[name] = len(code)

    def br(op: int, target: str) -> None:
        emit(op, 0)
        branches.append((len(code) - 1, target))

    emit(0xE0, 0x44, 0x01)             # CPX #$0144 ($9B / A row0)
    br(0x90, "done")                    # before uppercase => unchanged
    br(0x80, "batch2")                  # A and later => fixed JML trampoline
    label("done")
    emit(0x6B)
    emit(0xEA, 0xEA, 0xEA, 0xEA)
    label("batch2")
    emit(0x5C, *lo24(batch2_cpu))       # JML batch-2 selector
    if labels["batch2"] != 0x0C:
        raise SystemExit("VWF punctuation batch-2 trampoline moved from +$0C")
    return _resolve_rel8(code, labels, branches)


def make_punctuation_framing_batch2_selector() -> bytes:
    """Uppercase, punctuation and French-glyph framing selector."""
    code = bytearray()
    labels: dict[str, int] = {}
    branches: list[tuple[int, str]] = []

    def emit(*vals: int) -> None:
        code.extend(vals)

    def label(name: str) -> None:
        labels[name] = len(code)

    def br(op: int, target: str) -> None:
        emit(op, 0)
        branches.append((len(code) - 1, target))

    emit(0xE0, 0xA4, 0x01)             # I row0
    br(0x90, "shift_one")               # A-H
    emit(0xE0, 0xB0, 0x01)             # J row0
    br(0x90, "shift_three")             # I
    emit(0xE0, 0x7C, 0x02)             # after Z
    br(0x90, "shift_one")               # J-Z

    emit(0xE0, 0xF4, 0x02)             # $BF row0
    br(0x90, "done")                    # $B5-$BE unchanged
    emit(0xE0, 0x30, 0x03)             # $C4 row0
    br(0x90, "done")                    # $BF-$C3 unchanged
    emit(0xE0, 0x3C, 0x03)             # $C5 row0
    br(0x90, "shift_one")               # C4
    emit(0xE0, 0x48, 0x03)             # $C6 row0
    br(0x90, "shift_one")               # C5
    emit(0xE0, 0x60, 0x03)             # $C8 row0
    br(0x90, "done")                    # C6-C7
    emit(0xE0, 0x6C, 0x03)             # $C9 row0
    br(0x90, "shift_two")               # C8
    emit(0xE0, 0x84, 0x03)             # $CB row0
    br(0x90, "done")                    # C9-CA
    emit(0xE0, 0x90, 0x03)             # $CC row0
    br(0x90, "shift_two")               # CB
    emit(0xE0, 0x9C, 0x03)             # $CD row0
    br(0x90, "shift_one")               # CC
    emit(0xE0, 0xF0, 0x03)             # $D4 row0
    br(0x90, "done")                    # CD-D3 unchanged
    emit(0xE0, 0xB0, 0x04)             # $E4 row0
    br(0x90, "shift_one")               # D4-E3

    label("done")
    emit(0x6B)
    label("shift_one")
    emit(0x0A, 0x6B)
    label("shift_two")
    emit(0x0A, 0x0A, 0x6B)
    label("shift_three")
    emit(0x0A, 0x0A, 0x0A, 0x6B)
    return _resolve_rel8(code, labels, branches)


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
