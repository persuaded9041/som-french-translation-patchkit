#!/usr/bin/env python3
"""Build the runtime-validated continuous dialogue VWF checkpoint.

The stock $C0:168A-$C0:16B0 character-to-glyph lookup remains intact. Component
06 composes the already-selected stock row at a cumulative pixel cursor, reads
advances from the validated 128-entry table at $ED:7200, and frames glyphs only
through the small validated selectors.

Validated lowercase framing is a-h/k/m-s/u-z=1 px, i/l=3 px, j/t=2 px. Lowercase
advances follow component 05's rule on framed geometry: ink_width + 1 black
separator pixel.

Handled punctuation uses the runtime-validated visual spacing policy of one black
pixel before the ink and one after it for the already validated set. Colon $C5 is runtime-validated at shift 1 / advance 7, giving two black pixels before and three after its 2 px ink.
The canonical French $D4-$E5 framing/metrics are also runtime-validated. $CD is deliberately excluded from all active special handling and follows the generic
conservative path.

The post-stock outline-boundary repair is runtime-validated and runs only after
the stock outline routine returns. The width-table lookup keeps A in 8-bit mode
and zero-extends the glyph index through private WRAM $7E:938A-$938B.

The runtime-validated generic interruption path saves the true decoded count,
snapshots the cumulative VWF width before padded renderer slots, and converts
non-line-break event-render `$C9/$CA` chunks to physical 8-pixel cells before stock progression.
It contains no event-address or WAIT-opcode special cases.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from shared.ips import make_ips  # noqa: E402
from shared.rom import ROM_SIZE_OFFSET, expand_rom, update_checksum, validate_base_rom  # noqa: E402
from shared.french_charset import FIRST_CODE, FULL_DTE_THRESHOLD, FULL_FRENCH_CHARS, glyph_bytes  # noqa: E402

RENDER_ENTRY_FILE = 0x00167D
CHAR_START_FILE = 0x001686
FONT_ROW_FILE = 0x0016A4
CHAR_END_FILE = 0x0016B1
OUTLINE_POST_FILE = 0x001168

ENTRY_HELPER_FILE = 0x2D7040
CHAR_START_HELPER_FILE = 0x2D7180
FRAMING_SELECTOR_FILE = 0x2D71B0
PUNCTUATION_FRAMING_FILE = 0x2D71E8
PUNCTUATION_FRAMING_BATCH2_FILE = 0x2D72F0

DTE_COMPARE_IMMEDIATE_OFFSET = 0x0016F6
DTE_STOCK_THRESHOLD = 0xD3
DTE_NEW_THRESHOLD = FULL_DTE_THRESHOLD
FONT_BASE = 0x12DC00
ACCENT_FIRST = FIRST_CODE

CHAR_END_HELPER_FILE = 0x2D70C0
FONT_ROW_HELPER_FILE = 0x2D7100
ROM_TARGET_SIZE = 0x300000

WIDTH_TABLE_FILE = 0x2D7200
OUTLINE_POST_HELPER_FILE = 0x2D7280
CHUNK_COMMIT_HELPER_FILE = 0x2D7340
CHUNK_CELLS_SNAPSHOT_FILE = 0x2D7380
EVENT_RENDER_SCOPE_HELPER_FILE = 0x2D73B0

# The stock parser leaves the decoded character count in the low seven bits
# of $A1CE. The renderer saves it in private WRAM before the fixed 32-slot loop
# and snapshots the useful VWF width before padded $80 slots inflate the cursor.

RENDER_ENTRY_SIGNATURE = bytes.fromhex("A9 20 8D 76 A1")
CHAR_START_SIGNATURE = bytes.fromhex("BD A4 A1 E8")
FONT_ROW_SIGNATURE = bytes.fromhex("BF 00 DC D2")
CHAR_END_SIGNATURE = bytes.fromhex("FA CE 76 A1 D0 CF")
OUTLINE_POST_SIGNATURE = bytes.fromhex("A2 00 00 8E")

RENDER_ENTRY_HOOK = bytes.fromhex("5C 40 70 ED")
CHAR_START_HOOK = bytes.fromhex("5C 80 71 ED")
FONT_ROW_HOOK = bytes.fromhex("22 00 71 ED")  # JSL $ED7100; stock STA follows
CHAR_END_HOOK = bytes.fromhex("5C C0 70 ED EA EA")
OUTLINE_POST_HOOK = bytes.fromhex("5C 80 72 ED")


def _resolve_rel8(
    code: bytearray, labels: dict[str, int], branches: list[tuple[int, str]]
) -> bytes:
    """Resolve generated 65816 8-bit relative branches and freeze the payload."""
    for pos, target in branches:
        rel = labels[target] - (pos + 1)
        if not -128 <= rel <= 127:
            raise ValueError(f"branch out of range to {target}: {rel}")
        code[pos] = rel & 0xFF
    return bytes(code)


def _lowercase_left_shift(code: int) -> int:
    """Return the runtime-validated lowercase framing shift for a decoded byte."""
    if not 0x81 <= code <= 0x9A:
        return 0
    if code in (0x89, 0x8C):  # i, l
        return 3
    if code in (0x8A, 0x94):  # j, t
        return 2
    return 1


def _ink_bounds(rows: bytes) -> tuple[int, int] | None:
    """Return inclusive left/right ink columns for an 8-pixel stock glyph."""
    columns = [x for row in rows for x in range(8) if row & (0x80 >> x)]
    if not columns:
        return None
    return min(columns), max(columns)


def make_event_render_scope_helper() -> bytes:
    """Return carry set only for the renderer invocation tagged as event text.

    The renderer at $C0:1664 is shared by the event engine, GAME SELECT and a
    third non-event caller.  The entry helper tags only the exact event-engine
    caller ($C0:1150, whose JSR return address on the stack is $1152) and only
    for stock event banks $C9/$CA.  Internal hooks then consume this private
    flag instead of guessing from shared global state.
    """
    return bytes.fromhex(
        "AD 85 93 F0 02 38 6B 18 6B"  # LDA $9385 / BEQ no / SEC RTL / CLC RTL
    )


EVENT_RENDER_SCOPE_HELPER = make_event_render_scope_helper()


def make_entry_helper() -> bytes:
    """Initialize VWF state only for the exact event-engine renderer caller.

    $C0:1664 has three stock JSR callers. At $C0:167D no renderer-local value
    has been pushed yet, so the original JSR return address is still at 1,S:

      $1152 = event engine ($C0:1150)
      $235E = GAME SELECT ($C0:235C)
      $CB3E = other non-event caller ($C0:CB3C)

    Tag only $1152 and then accept event banks $C9/$CA. Component 05 intercepts
    its translated intro before this point, so its private $CA renderer remains
    isolated. $9385 is shared with component 05 only under mutually exclusive
    scopes (intro glyph-advance scratch there, renderer-active flag here).
    """
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

    emit(0x9C, 0x85, 0x93)             # STZ $9385: renderer-active flag

    # No renderer-local pushes have happened yet. Read the 16-bit return
    # address left by the caller's JSR $1664 without altering the stack.
    emit(0xC2, 0x20)                   # REP #$20
    emit(0xA3, 0x01)                   # LDA 1,S
    emit(0xC9, 0x52, 0x11)             # event-engine JSR stores $1152
    emit(0xE2, 0x20)                   # SEP #$20
    br(0xD0, "replay")

    emit(0xAF, 0x03, 0x1D, 0x00)       # LDA.l $001D03
    emit(0xC9, 0xC9)
    br(0xF0, "activate")
    emit(0xC9, 0xCA)
    br(0xD0, "replay")

    label("activate")
    emit(0xA9, 0x01, 0x8D, 0x85, 0x93) # active = 1
    emit(0xAD, 0xCE, 0xA1, 0x29, 0x7F, 0x8D, 0x8E, 0x93)  # save count
    emit(0x9C, 0x8F, 0x93)             # clear physical-cell result
    emit(0x9C, 0x82, 0x93)             # STZ pixel cursor
    emit(0xA2, 0x00, 0x00)             # LDX #$0000
    emit(0x9E, 0x00, 0x90, 0xE8, 0xE0, 0x80, 0x01, 0xD0, 0xF7)  # clear bitmap

    label("replay")
    emit(0xA9, 0x20, 0x8D, 0x76, 0xA1) # replay stock LDA/STA
    emit(0x5C, 0x82, 0x16, 0xC0)       # JML $C01682
    return _resolve_rel8(code, labels, branches)


def make_char_start_helper() -> bytes:
    # For a tagged event-render invocation, every character uses the true cumulative pixel cursor: Y is
    # floor(pixel_cursor / 8) * 12 while the stock glyph lookup remains intact.
    # Keep branch targets symbolic so the stock fallback always lands at the
    # beginning of the stock `LDA $A1A4,X / INX` replay.
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

    emit(0x22, 0xB0, 0x73, 0xED)       # tagged event-render scope: exact caller + C9/CA
    br(0x90, "replay")                 # BCC replay
    emit(0x22, 0x80, 0x73, 0xED)       # JSL $ED7380: snapshot useful chunk cells

    emit(0xDA)                          # PHX
    emit(0xC2, 0x20)                   # REP #$20
    emit(0xAD, 0x82, 0x93, 0x29, 0xFF, 0x00)  # pixel_cursor
    emit(0x4A, 0x4A, 0x4A)             # /8
    emit(0x0A, 0x0A, 0x8D, 0x86, 0x93) # tile*4 scratch
    emit(0x0A, 0x18, 0x6D, 0x86, 0x93, 0xA8)  # tile*12 -> Y
    emit(0xE2, 0x20, 0xFA)             # SEP #$20 / PLX

    label("replay")
    emit(0xBD, 0xA4, 0xA1, 0xE8)       # stock LDA / INX
    emit(0x5C, 0x8A, 0x16, 0xC0)       # untouched stock glyph path

    return _resolve_rel8(code, labels, branches)


def make_char_end_helper() -> bytes:
    # PLX restores the decoded-character index *after* INX. When tagged active, read the
    # current decoded byte, zero-extend its 7-bit glyph index through two bytes
    # of private WRAM scratch, then load the 8-bit advance from extended ROM.
    #
    # Keep A in 8-bit mode here: the stock row loop relies on the hidden B byte
    # of the 65816 accumulator.
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

    emit(0xFA)                          # stock PLX
    emit(0x22, 0xB0, 0x73, 0xED)       # tagged event-render scope: exact caller + C9/CA
    br(0x90, "stock_tail")             # BCC -> stock loop tail

    emit(0xBD, 0xA3, 0xA1)             # current decoded byte
    emit(0x29, 0x7F)                   # glyph index 0..127, A stays 8-bit
    emit(0x8D, 0x8A, 0x93)             # WIDTH_INDEX low
    emit(0x9C, 0x8B, 0x93)             # WIDTH_INDEX high = 0 (8-bit STZ)
    emit(0xDA)                          # PHX: preserve decoded-character X
    emit(0xAE, 0x8A, 0x93)             # LDX WIDTH_INDEX (X remains 16-bit)
    emit(0xBF, 0x00, 0x72, 0xED)       # LDA.l $ED7200,X
    emit(0xFA)                          # PLX
    emit(0x18, 0x6D, 0x82, 0x93)       # cursor += A
    emit(0x8D, 0x82, 0x93)

    label("stock_tail")
    # Stock tail; leave final flags from DEC just like original.
    emit(0xA9, 0x00, 0xCE, 0x76, 0xA1)
    emit(0xF0, 0x04)
    emit(0x5C, 0x86, 0x16, 0xC0)
    emit(0x5C, 0x40, 0x73, 0xED)       # final slot -> generic chunk commit

    return _resolve_rel8(code, labels, branches)


def make_chunk_cells_snapshot_helper() -> bytes:
    """Capture the useful decoded chunk as a count of 8-pixel cells.

    X is the current renderer slot. At the start of the first padded slot,
    X equals the decoded-character count saved from `$A1CE`. The pixel cursor
    still contains only useful glyph advances at that exact moment, so convert
    it to `ceil(width / 8)` before the fixed 32-slot loop can add padding.

    The helper is also called once at final commit. That covers the count=32
    case, where there is no padded slot and the 8-bit cursor can wrap from 256
    px to zero; a non-empty zero cursor at X=32 therefore means 32 cells.
    """
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

    emit(0x8A)                          # TXA (low byte; X itself is preserved)
    emit(0xCD, 0x8E, 0x93)             # CMP saved decoded count
    br(0xD0, "return")

    emit(0xAD, 0x82, 0x93)             # useful pixel cursor
    br(0xD0, "nonzero")
    emit(0xAD, 0x8E, 0x93)             # empty chunk or wrapped 32-char chunk?
    br(0xF0, "store")                  # count=0 -> zero cells
    emit(0xA9, 0x20)                   # only possible non-empty wrap = 256 px
    br(0x80, "store")

    label("nonzero")
    emit(0x29, 0x07)                   # any sub-cell remainder?
    br(0xF0, "aligned")
    emit(0xAD, 0x82, 0x93)
    emit(0x4A, 0x4A, 0x4A)             # floor(width / 8)
    emit(0x1A)                          # +1 => ceil(width / 8)
    br(0x80, "store")

    label("aligned")
    emit(0xAD, 0x82, 0x93)
    emit(0x4A, 0x4A, 0x4A)

    label("store")
    emit(0x8D, 0x8F, 0x93)             # physical cells for this decoded chunk

    label("return")
    emit(0x6B)                          # RTL

    return _resolve_rel8(code, labels, branches)


def make_chunk_commit_helper() -> bytes:
    """Convert `$A1CE` to physical VWF cells before stock progression.

    This is deliberately independent of event opcodes and script addresses.
    The decoded count was captured at renderer entry and the cell count comes
    from the actual cumulative advances of the decoded buffer, including DTE
    expansion and dynamically inserted names. Preserve `$A1CE`'s line-end bit.
    """
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

    emit(0x22, 0xB0, 0x73, 0xED)       # tagged event-render scope: exact caller + C9/CA
    br(0x90, "return")

    emit(0xAD, 0xCE, 0xA1)             # stock line-end flag
    br(0x30, "return")                 # line break: preserve validated stock progression

    emit(0xAD, 0x8E, 0x93)             # saved decoded count
    emit(0xC9, 0x21)                   # renderer contract is at most 32 slots
    br(0xB0, "return")                 # unexpected count -> stock behavior

    # For count=32 there was no first padded slot, so snapshot once now with
    # X=32 and the cursor positioned immediately after the last useful glyph.
    emit(0x22, 0x80, 0x73, 0xED)       # JSL $ED7380

    emit(0xAD, 0xCE, 0xA1)             # preserve only stock line-end flag
    emit(0x29, 0x80)
    emit(0x0D, 0x8F, 0x93)             # OR physical VWF cell count
    emit(0x8D, 0xCE, 0xA1)

    label("return")
    emit(0xA9, 0x00)                   # stock char-end return A value
    emit(0x5C, 0xB7, 0x16, 0xC0)       # JML $C016B7 (RTS)

    return _resolve_rel8(code, labels, branches)

def make_framing_selector() -> bytes:
    """Return the stock-selected row with validated framing transforms.

    A is the 8-bit stock row and X is the stock 12-byte font-row offset.
    No registers or accumulator-width flags are changed. Lowercase a-z keeps
    its runtime-validated framing. Rows after z are delegated to the small
    punctuation selector at $ED:71E8.
    """
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
    br(0xB0, "punctuation")             # after z => punctuation selector

    # All lowercase glyphs default to a 1-pixel left frame. Exceptions are
    # selected by their contiguous 12-byte stock-font row ranges.
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
    # u-z fall through to shift_one.

    label("shift_one")
    emit(0x0A)                          # ASL x1
    br(0x80, "done")

    label("shift_two")
    emit(0x0A, 0x0A)                    # ASL x2
    br(0x80, "done")

    label("shift_three")
    emit(0x0A, 0x0A, 0x0A)             # ASL x3

    label("done")
    emit(0x6B)                          # RTL

    # Deliberately place an external branch label exactly one byte past the
    # validated 56-byte lowercase selector. $ED:71E8 is the adjacent free
    # slot containing the punctuation selector.
    label("punctuation")
    return _resolve_rel8(code, labels, branches)


def make_punctuation_framing_selector() -> bytes:
    """Dispatch every post-lowercase glyph through the fixed batch-2 trampoline.

    The validated trampoline JML remains byte-for-byte pinned at $ED:71F4.
    Uppercase and later glyphs are routed to the extended selector at
    $ED:72F0, where A-Z framing is handled and all previously validated
    punctuation behavior is preserved. Glyphs before uppercase still return
    unchanged here.
    """
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
    emit(0x6B)                          # RTL
    emit(0xEA, 0xEA, 0xEA, 0xEA)       # layout pad; JML must start at +$0C
    label("batch2")
    code += bytes.fromhex("5C F0 72 ED")  # JML $ED72F0
    if labels["batch2"] != 0x0C:
        raise SystemExit("Punctuation batch-2 trampoline moved from $ED:71F4")
    return _resolve_rel8(code, labels, branches)


def make_punctuation_framing_batch2_selector() -> bytes:
    """Return validated framing for uppercase, punctuation and French glyphs.

    Uppercase A-Z geometry follows the letter rule already validated
    for lowercase: compact ink to the left edge, then advance by ink_width + 1.
    Stock A-H/J-Z have a 1 px left bearing; I has a 3 px bearing.

    $B5-$BE remain untouched. Existing punctuation behavior is preserved:
    $BF-$C3 and $C6/$C7/$C9/$CA unshifted, $C4/$CC shifted 1 px,
    $C8/$CB shifted 2 px. Colon $C5 is validated at shift 1 / advance 7.
    $CD and $CE-$D3 remain untouched. Canonical French glyphs $D4-$E3 shift
    left 1 px; full-width $E4/$E5 (Œ/œ) remain unshifted.
    """
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

    # Uppercase A-Z ($9B-$B4). All compact by 1 px except I by 3 px.
    emit(0xE0, 0xA4, 0x01)             # CPX #$01A4 ($A3 / I row0)
    br(0x90, "shift_one")              # A-H
    emit(0xE0, 0xB0, 0x01)             # CPX #$01B0 ($A4 / J row0)
    br(0x90, "shift_three")            # I
    emit(0xE0, 0x7C, 0x02)             # CPX #$027C ($B5 row0, after Z)
    br(0x90, "shift_one")              # J-Z

    # $B5-$BE are deliberately untouched for now.
    emit(0xE0, 0xF4, 0x02)             # CPX #$02F4 ($BF row0)
    br(0x90, "done")
    # $BF-$C3 all keep stock framing. ($C3 is also unshifted.)
    emit(0xE0, 0x30, 0x03)             # CPX #$0330 ($C4 row0)
    br(0x90, "done")
    emit(0xE0, 0x3C, 0x03)             # CPX #$033C ($C5 row0)
    br(0x90, "shift_one")              # C4: stock bearing 2 -> keep 1
    emit(0xE0, 0x48, 0x03)             # CPX #$0348 ($C6 row0)
    br(0x90, "shift_one")               # C5 colon runtime-validated
    emit(0xE0, 0x60, 0x03)             # CPX #$0360 ($C8 row0)
    br(0x90, "done")                    # C6-C7 unchanged
    emit(0xE0, 0x6C, 0x03)             # CPX #$036C ($C9 row0)
    br(0x90, "shift_two")              # C8 !: stock bearing 3 -> keep 1
    emit(0xE0, 0x84, 0x03)             # CPX #$0384 ($CB row0)
    br(0x90, "done")                    # C9-CA keep 1 px stock margin
    emit(0xE0, 0x90, 0x03)             # CPX #$0390 ($CC row0)
    br(0x90, "shift_two")              # CB (: stock bearing 3 -> keep 1
    emit(0xE0, 0x9C, 0x03)             # CPX #$039C ($CD row0)
    br(0x90, "shift_one")              # CC ): stock bearing 2 -> keep 1
    emit(0xE0, 0xF0, 0x03)             # CPX #$03F0 ($D4 row0)
    br(0x90, "done")                    # $CD-$D3 untouched
    emit(0xE0, 0xB0, 0x04)             # CPX #$04B0 ($E4 / Œ row0)
    br(0x90, "shift_one")              # $D4-$E3: canonical 1 px bearing
    # $E4/$E5 are full-width and remain unshifted.

    label("done")
    emit(0x6B)                          # RTL
    label("shift_one")
    emit(0x0A, 0x6B)                    # ASL x1; RTL
    label("shift_two")
    emit(0x0A, 0x0A, 0x6B)             # ASL x2; RTL
    label("shift_three")
    emit(0x0A, 0x0A, 0x0A, 0x6B)       # ASL x3; RTL
    return _resolve_rel8(code, labels, branches)


def make_font_row_helper() -> bytes:
    """Return the stock-selected font row repositioned at cursor & 7.

    The caller is in 8-bit accumulator mode. The high accumulator byte B is
    the stock 12-row loop counter, so this helper deliberately uses only
    8-bit A operations and never XBA/REP on A. X/Y are preserved.
    """
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

    # Reproduce the overwritten stock load first. B remains untouched.
    emit(0xBF, 0x00, 0xDC, 0xD2)       # LDA.l $D2DC00,X
    emit(0x48)                          # PHA source row
    emit(0x22, 0xB0, 0x73, 0xED)       # tagged event-render scope: exact caller + C9/CA
    br(0x90, "stock")

    emit(0x68)                          # source row
    # Selection is factored out only to recover ROM space. The selector
    # receives the same A/X values and returns the framed row immediately at
    # this already runtime-validated application point.
    emit(0x22, 0xB0, 0x71, 0xED)       # JSL $ED71B0

    label("store_source")
    emit(0x8D, 0x88, 0x93)             # SOURCE_ROW
    emit(0xAD, 0x82, 0x93, 0x29, 0x07) # cursor & 7
    emit(0x8D, 0x83, 0x93)             # BIT_SHIFT
    br(0xF0, "aligned")

    # current = source >> shift
    emit(0x8D, 0x84, 0x93)             # SHIFT_COUNT=shift
    emit(0xAD, 0x88, 0x93)
    label("right_loop")
    emit(0x4A)                          # LSR A
    emit(0xCE, 0x84, 0x93)             # DEC SHIFT_COUNT
    br(0xD0, "right_loop")
    emit(0x19, 0x00, 0x90)             # ORA $9000,Y (previous spill)
    emit(0x8D, 0x89, 0x93)             # CURRENT_ROW

    # spill = source << (8-shift), merged into next 12-byte tile cell.
    emit(0xA9, 0x08, 0x38, 0xED, 0x83, 0x93)  # 8-shift
    emit(0x8D, 0x84, 0x93)
    emit(0xAD, 0x88, 0x93)
    label("left_loop")
    emit(0x0A)                          # ASL A
    emit(0xCE, 0x84, 0x93)
    br(0xD0, "left_loop")
    emit(0x19, 0x0C, 0x90)             # ORA $900C,Y
    emit(0x99, 0x0C, 0x90)             # STA $900C,Y
    emit(0xAD, 0x89, 0x93)             # return current half for stock STA
    emit(0x6B)

    label("aligned")
    emit(0xAD, 0x88, 0x93)
    emit(0x6B)

    label("stock")
    emit(0x68)
    emit(0x6B)

    return _resolve_rel8(code, labels, branches)


ENTRY_HELPER = make_entry_helper()
CHAR_START_HELPER = make_char_start_helper()
CHAR_END_HELPER = make_char_end_helper()
CHUNK_CELLS_SNAPSHOT_HELPER = make_chunk_cells_snapshot_helper()
CHUNK_COMMIT_HELPER = make_chunk_commit_helper()
FRAMING_SELECTOR = make_framing_selector()
PUNCTUATION_FRAMING_SELECTOR = make_punctuation_framing_selector()
PUNCTUATION_FRAMING_BATCH2_SELECTOR = make_punctuation_framing_batch2_selector()
FONT_ROW_HELPER = make_font_row_helper()


def make_outline_post_helper() -> bytes:
    """Repair horizontal outline pixels lost across 8-pixel cell boundaries.

    This runtime-validated helper is entered at $C0:1168, after the stock
    JSR $162C has returned; that call must remain intact for the stock outline.

    For the currently validated $C9 outline path, scan the already rendered
    $9000-$917F bitmap. If ink touches
    the left/right edge of a source cell, add the corresponding one-pixel outline
    contribution to the neighboring output tile. Then replay the stock tail.
    """
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

    emit(0xAF, 0x03, 0x1D, 0x00)       # LDA.l $001D03
    emit(0xC9, 0xC9)                   # CMP #$C9
    br(0xD0, "replay")              # non-C9: stock tail only

    emit(0x9C, 0x8C, 0x93)             # STZ OUTLINE_TILE
    emit(0xA2, 0x00, 0x00)             # LDX #$0000 source offset
    emit(0xA0, 0x00, 0x00)             # LDY #$0000 output offset

    label("tile_loop")
    emit(0xA9, 0x0C)                   # 12 rows
    emit(0x8D, 0x8D, 0x93)             # OUTLINE_ROWS

    label("row_loop")
    emit(0xBD, 0x00, 0x90)             # LDA $9000,X
    emit(0x89, 0x80)                   # BIT #$80
    br(0xF0, "check_right")
    emit(0xAD, 0x8C, 0x93)             # tile index
    br(0xF0, "check_right")         # no previous tile for tile 0
    emit(0xB9, 0xE4, 0x93)             # previous tile: $9404+Y-32
    emit(0x09, 0x01)
    emit(0x99, 0xE4, 0x93)

    label("check_right")
    emit(0xBD, 0x00, 0x90)             # reload source row
    emit(0x89, 0x01)                   # BIT #$01
    br(0xF0, "next_row")
    emit(0xAD, 0x8C, 0x93)
    emit(0xC9, 0x1F)                   # last of 32 cells?
    br(0xF0, "next_row")
    emit(0xB9, 0x24, 0x94)             # next tile: $9404+Y+32
    emit(0x09, 0x80)
    emit(0x99, 0x24, 0x94)

    label("next_row")
    emit(0xE8)                          # next source row
    emit(0xC8, 0xC8)                   # output row stride = 2
    emit(0xCE, 0x8D, 0x93)
    br(0xD0, "row_loop")

    emit(*([0xC8] * 8))                # 24 -> 32-byte output tile stride
    emit(0xEE, 0x8C, 0x93)
    emit(0xAD, 0x8C, 0x93)
    emit(0xC9, 0x20)
    br(0xD0, "tile_loop")

    label("replay")
    # $C0:1168 starts here in stock: LDX #0; STX $A191; STX $A173;
    # INC $A15D; RTS. The stock JSR $162C has already executed.
    emit(0xA2, 0x00, 0x00)
    emit(0x8E, 0x91, 0xA1)
    emit(0x8E, 0x73, 0xA1)
    emit(0xEE, 0x5D, 0xA1)
    emit(0x5C, 0x74, 0x11, 0xC0)

    return _resolve_rel8(code, labels, branches)


OUTLINE_POST_HELPER = make_outline_post_helper()


def make_width_table(base: bytes) -> bytes:
    """Build the editable dialogue advance table with a guaranteed 1 px gap.

    Lowercase a-z are already runtime-validated with explicit left framing.  For
    that framed range, use the same metric rule as component 05: ``ink_width +
    1``.  The ink width is measured from the clean stock bitmap before shifting;
    left framing changes its position, not its width.

    Runtime-validated punctuation $BF-$C4 and $C6-$CC uses one black pixel before
    the ink and one after it. Colon $C5 is runtime-validated with two black
    pixels before its 2 px ink and three after it, therefore a 7 px advance. $CD is not
    a special case and follows the generic conservative metric path. Other non-lowercase glyphs
    deliberately stay on the previous conservative baseline: rightmost ink
    column + 2, capped at 8 px. Space remains 4 px.
    """
    table = bytearray([8] * 128)
    font = bytearray(base[FONT_BASE:FONT_BASE + 128 * 12])
    french = glyph_bytes(FULL_FRENCH_CHARS)
    french_start = (ACCENT_FIRST - 0x80) * 12
    font[french_start:french_start + len(french)] = french

    table[0x80 - 0x80] = 4  # space

    for code in range(0x81, 0x100):
        rows = font[(code - 0x80) * 12:(code - 0x80 + 1) * 12]
        bounds = _ink_bounds(rows)
        if bounds is None:
            continue

        left, right = bounds
        if (0x81 <= code <= 0x9A or 0x9B <= code <= 0xB4
                or 0xD4 <= code <= 0xE5):
            table[code - 0x80] = min(8, (right - left + 1) + 1)
        elif code == 0xC5:
            table[code - 0x80] = min(8, (right - left + 1) + 5)
        elif (
            0xBF <= code <= 0xC4
            or code in (0xC6, 0xC7, 0xC8, 0xC9, 0xCA, 0xCB, 0xCC)
        ):
            # Runtime-validated punctuation spacing: one black pixel before
            # the ink and one after it. `$CD` is intentionally not included.
            table[code - 0x80] = min(8, (right - left + 1) + 2)
        else:
            table[code - 0x80] = min(8, right + 2)

    return bytes(table)



def validate_metrics(base: bytes, width_table: bytes) -> None:
    # Keep the stock glyph-selection path immutable.
    if base[0x00168A:0x0016A4] != bytes.fromhex(
        "DA C2 20 29 FF 00 38 E9 80 00 0A 0A 8D C7 A1 0A 18 6D C7 A1 AA E2 20 A9 0C EB"
    ):
        raise SystemExit("Unexpected stock code->glyph addressing path")

    # Verify the stock lowercase left bearings used by the validated framing selector.
    font = bytearray(base[FONT_BASE:FONT_BASE + 128 * 12])
    french = glyph_bytes(FULL_FRENCH_CHARS)
    french_start = (ACCENT_FIRST - 0x80) * 12
    font[french_start:french_start + len(french)] = french
    for code in range(0x81, 0x9B):
        rows = font[(code - 0x80) * 12:(code - 0x80 + 1) * 12]
        bounds = _ink_bounds(rows)
        if bounds is None or bounds[0] != _lowercase_left_shift(code):
            raise SystemExit(f"Unexpected stock left bearing for ${code:02X}")

    if len(width_table) != 128:
        raise SystemExit("Dialogue width table must contain exactly 128 entries")
    if width_table[0x00] != 4:
        raise SystemExit("Dialogue space metric mismatch")

    expected_lowercase = {
        **{code: 7 for code in range(0x81, 0x89)},
        0x89: 3,  # i
        0x8A: 4,  # j
        0x8B: 7,  # k
        0x8C: 3,  # l
        **{code: 7 for code in range(0x8D, 0x92)},
        0x92: 6,  # r
        0x93: 7,  # s
        0x94: 5,  # t
        **{code: 7 for code in range(0x95, 0x9B)},
    }
    for code, expected in expected_lowercase.items():
        if width_table[code - 0x80] != expected:
            raise SystemExit(f"Unexpected lowercase metric for ${code:02X}")

    # Verify the lowercase rule directly from ink bounds, and verify that the
    # validated framing leaves exactly one full black separator column after
    # each framed glyph.
    for code in range(0x81, 0x9B):
        rows = font[(code - 0x80) * 12:(code - 0x80 + 1) * 12]
        bounds = _ink_bounds(rows)
        if bounds is None:
            raise SystemExit(f"Empty lowercase glyph for ${code:02X}")
        left, right = bounds
        expected = min(8, (right - left + 1) + 1)
        width = width_table[code - 0x80]
        if width != expected:
            raise SystemExit(f"Unexpected ink-width+1 metric for ${code:02X}")
        framed_right = right - _lowercase_left_shift(code)
        if width != framed_right + 2:
            raise SystemExit(f"Missing framed separator for ${code:02X}")

    # Runtime-validated uppercase A-Z: stock geometry is homogeneous except I.
    for code in range(0x9B, 0xB5):
        rows = font[(code - 0x80) * 12:(code - 0x80 + 1) * 12]
        bounds = _ink_bounds(rows)
        if bounds is None:
            raise SystemExit(f"Empty uppercase glyph for ${code:02X}")
        left, right = bounds
        expected_left = 3 if code == 0xA3 else 1
        expected_width = 2 if code == 0xA3 else 6
        if left != expected_left or (right - left + 1) != expected_width:
            raise SystemExit(f"Unexpected uppercase stock geometry for ${code:02X}")
        expected_advance = expected_width + 1
        if width_table[code - 0x80] != expected_advance:
            raise SystemExit(f"Unexpected validated uppercase metric for ${code:02X}")

    # Runtime-validated punctuation spacing: handled punctuation keeps exactly
    # one black pixel before its framed ink and one after it. Colon $C5 is an
    # isolated validated case with two black pixels on the left and three on the right. `$CD` remains
    # entirely outside special handling.
    punctuation_geometry = {
        0xBF: (1, 0, 4),  # .
        0xC0: (1, 0, 4),  # ,
        0xC1: (1, 0, 7),  # /
        0xC2: (1, 0, 4),  # apostrophe
        0xC3: (1, 0, 7),  # opening quote
        0xC4: (2, 1, 7),  # closing quote
        0xC6: (1, 0, 8),  # -
        0xC7: (1, 0, 8),  # %
        0xC8: (3, 2, 5),  # !
        0xC9: (1, 0, 8),  # &
        0xCA: (1, 0, 8),  # ?
        0xCB: (3, 2, 5),  # (
        0xCC: (2, 1, 5),  # )
    }
    for code, (stock_left, shift, expected_width) in punctuation_geometry.items():
        rows = font[(code - 0x80) * 12:(code - 0x80 + 1) * 12]
        bounds = _ink_bounds(rows)
        if bounds is None or bounds[0] != stock_left:
            raise SystemExit(f"Unexpected punctuation left bearing for ${code:02X}")
        left, right = bounds
        width = width_table[code - 0x80]
        if width != expected_width or width != min(8, (right - left + 1) + 2):
            raise SystemExit(f"Unexpected punctuation left-gap metric for ${code:02X}")
        framed_left = left - shift
        framed_right = right - shift
        if framed_left != 1:
            raise SystemExit(f"Missing punctuation left separator for ${code:02X}")
        if width < 8 and width != framed_right + 2:
            raise SystemExit(f"Missing punctuation right separator for ${code:02X}")


    # Runtime-validated colon: stock ink occupies columns 3-4. Shift left by
    # one pixel to columns 2-3 and advance by 7, leaving 2 black pixels before
    # the ink and 3 after it.
    code = 0xC5
    rows = font[(code - 0x80) * 12:(code - 0x80 + 1) * 12]
    bounds = _ink_bounds(rows)
    if bounds != (3, 4):
        raise SystemExit("Unexpected colon stock geometry for $C5")
    if width_table[code - 0x80] != 7:
        raise SystemExit("Unexpected validated colon metric for $C5")
    framed_left = bounds[0] - 1
    framed_right = bounds[1] - 1
    if framed_left != 2 or width_table[code - 0x80] - framed_right - 1 != 3:
        raise SystemExit("Validated colon does not preserve 2 px left / 3 px right framing")

    # Runtime-validated shared French charset. $D4-$E3 share a 1 px left bearing and
    # 6 px ink width; Œ/œ ($E4/$E5) are genuinely full-width.
    for code in range(0xD4, 0xE6):
        rows = font[(code - 0x80) * 12:(code - 0x80 + 1) * 12]
        bounds = _ink_bounds(rows)
        expected_bounds = (0, 7) if code >= 0xE4 else (1, 6)
        expected_advance = 8 if code >= 0xE4 else 7
        if bounds != expected_bounds:
            raise SystemExit(f"Unexpected canonical French geometry for ${code:02X}: {bounds}")
        if width_table[code - 0x80] != expected_advance:
            raise SystemExit(f"Unexpected validated French metric for ${code:02X}")

    # Remaining non-lowercase glyphs retain the conservative stock-geometry baseline.
    metric_specials = {0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9, 0xCA, 0xCB, 0xCC}
    for code in list(range(0xB5, 0xBF)) + list(range(0xC3, 0x100)):
        if code in metric_specials or 0xD4 <= code <= 0xE5:
            continue
        rows = font[(code - 0x80) * 12:(code - 0x80 + 1) * 12]
        bounds = _ink_bounds(rows)
        if bounds is None:
            continue
        expected = min(8, bounds[1] + 2)
        if width_table[code - 0x80] != expected:
            raise SystemExit(f"Unexpected conservative metric for ${code:02X}")

    # The renderer has 32 slots and every generated advance must remain in the
    # 1..8 px range expected by the generic physical-cell snapshot helper.
    if len(width_table) != 128 or not all(1 <= width <= 8 for width in width_table):
        raise SystemExit("Unexpected dialogue width-table bounds")


def build(base: bytes) -> bytes:
    validate_base_rom(base)
    width_table = make_width_table(base)
    for offset, signature, name in (
        (RENDER_ENTRY_FILE, RENDER_ENTRY_SIGNATURE, "renderer entry"),
        (CHAR_START_FILE, CHAR_START_SIGNATURE, "character start"),
        (FONT_ROW_FILE, FONT_ROW_SIGNATURE, "font-row load"),
        (CHAR_END_FILE, CHAR_END_SIGNATURE, "character end"),
        (OUTLINE_POST_FILE, OUTLINE_POST_SIGNATURE, "post-outline state"),
    ):
        if base[offset:offset + len(signature)] != signature:
            raise SystemExit(f"Unexpected clean-US {name} signature")

    validate_metrics(base, width_table)
    rom = expand_rom(base, ROM_TARGET_SIZE)
    if base[DTE_COMPARE_IMMEDIATE_OFFSET] != DTE_STOCK_THRESHOLD:
        raise SystemExit(
            f"Unexpected stock DTE threshold at 0x{DTE_COMPARE_IMMEDIATE_OFFSET:06X}: "
            f"${base[DTE_COMPARE_IMMEDIATE_OFFSET]:02X}"
        )
    rom[DTE_COMPARE_IMMEDIATE_OFFSET] = DTE_NEW_THRESHOLD
    french_glyphs = glyph_bytes(FULL_FRENCH_CHARS)
    glyph_start = FONT_BASE + (ACCENT_FIRST - 0x80) * 12
    rom[glyph_start:glyph_start + len(french_glyphs)] = french_glyphs
    rom[RENDER_ENTRY_FILE:RENDER_ENTRY_FILE + len(RENDER_ENTRY_HOOK)] = RENDER_ENTRY_HOOK
    rom[CHAR_START_FILE:CHAR_START_FILE + len(CHAR_START_HOOK)] = CHAR_START_HOOK
    rom[FONT_ROW_FILE:FONT_ROW_FILE + len(FONT_ROW_HOOK)] = FONT_ROW_HOOK
    rom[CHAR_END_FILE:CHAR_END_FILE + len(CHAR_END_HOOK)] = CHAR_END_HOOK
    rom[OUTLINE_POST_FILE:OUTLINE_POST_FILE + len(OUTLINE_POST_HOOK)] = OUTLINE_POST_HOOK

    for offset, payload in (
        (ENTRY_HELPER_FILE, ENTRY_HELPER),
        (CHAR_START_HELPER_FILE, CHAR_START_HELPER),
        (FRAMING_SELECTOR_FILE, FRAMING_SELECTOR),
        (PUNCTUATION_FRAMING_FILE, PUNCTUATION_FRAMING_SELECTOR),
        (PUNCTUATION_FRAMING_BATCH2_FILE, PUNCTUATION_FRAMING_BATCH2_SELECTOR),
        (CHAR_END_HELPER_FILE, CHAR_END_HELPER),
        (FONT_ROW_HELPER_FILE, FONT_ROW_HELPER),
        (WIDTH_TABLE_FILE, width_table),
        (OUTLINE_POST_HELPER_FILE, OUTLINE_POST_HELPER),
        (CHUNK_COMMIT_HELPER_FILE, CHUNK_COMMIT_HELPER),
        (CHUNK_CELLS_SNAPSHOT_FILE, CHUNK_CELLS_SNAPSHOT_HELPER),
        (EVENT_RENDER_SCOPE_HELPER_FILE, EVENT_RENDER_SCOPE_HELPER),
    ):
        rom[offset:offset + len(payload)] = payload

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
    print("Caller-gated $C9/$CA event-dialogue VWF + generic interrupted-chunk cell conversion")


if __name__ == "__main__":
    main()
