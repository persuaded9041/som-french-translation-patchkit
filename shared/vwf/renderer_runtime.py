"""Shared low-level VWF renderer runtime used by dialogue and UI VWF.

This module is the executable source for the renderer helpers that are common to
``vwf_dialogues`` and ``vwf_ui``.  Both standalone components install the same
validated bytes from here; the component builder must not carry a second copy of
these helpers.
"""
from __future__ import annotations

from shared.core.asm import lo24
from shared.vwf.row_renderer import ROW_RENDERER_CALL

CHAR_START_FILE = 0x001686
FONT_ROW_FILE = 0x0016A4
CHAR_END_FILE = 0x0016B1
OUTLINE_POST_FILE = 0x001168
CHAR_START_HELPER_FILE = 0x2D7180
CHAR_END_HELPER_FILE = 0x2D70C0
FONT_ROW_HELPER_FILE = 0x2D7100
WIDTH_TABLE_FILE = 0x2D7200
OUTLINE_POST_HELPER_FILE = 0x2D7280
CHUNK_COMMIT_HELPER_FILE = 0x2D7340
CHUNK_CELLS_SNAPSHOT_FILE = 0x2D7380
EVENT_RENDER_SCOPE_HELPER_FILE = 0x2D73B0
CHOICE_VISUAL_HELPER_FILE = 0x2D7880
CHOICE_VISUAL_HELPER_CPU = 0xED7880
CHOICE_TRACKER_HELPER_FILE = 0x2D7910
CHOICE_TRACKER_HELPER_CPU = 0xED7910

CHAR_START_SIGNATURE = bytes.fromhex("BD A4 A1 E8")
FONT_ROW_SIGNATURE = bytes.fromhex("BF 00 DC D2")
CHAR_END_SIGNATURE = bytes.fromhex("FA CE 76 A1 D0 CF")
OUTLINE_POST_SIGNATURE = bytes.fromhex("A2 00 00 8E")

CHAR_START_HOOK = bytes.fromhex("5C 80 71 ED")
FONT_ROW_HOOK = bytes.fromhex("22 00 71 ED")
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


def make_event_render_scope_helper() -> bytes:
    """Return carry set only for the renderer invocation tagged as event text.

    The renderer at $C0:1664 is shared by the event engine, GAME SELECT and a
    third non-event caller.  The entry helper tags only the exact event-engine
    caller ($C0:1150, whose JSR return address on the stack is $1152) and only
    for stock event banks $C9/$CA and `french_dialogues` relocated banks $E8-$EC.
    Internal hooks then consume this private
    flag instead of guessing from shared global state.
    """
    return bytes.fromhex(
        "AD 85 93 F0 02 38 6B 18 6B"  # LDA $9385 / BEQ no / SEC RTL / CLC RTL
    )


def make_char_start_helper() -> bytes:
    """Use ordinary cumulative VWF plus private visual geometry for wide choices.

    The stock choice table `$A1D7[]` remains the parser/storage coordinate system.
    At an exact option/terminal boundary, `$ED:7880` decides whether to keep the
    stock anchor or use the runtime-validated private measured-end geometry.
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

    emit(0x22, 0xB0, 0x73, 0xED)       # exact `vwf_dialogues` event-render scope
    br(0x90, "replay")
    emit(0x22, 0x80, 0x73, 0xED)       # snapshot useful chunk cells

    # While a stock choice is active, find the exact option/terminal boundary
    # matching the current decoded slot.  X becomes the boundary index 0..N.
    emit(0xAF, 0x00, 0x1D, 0x00)
    br(0x10, "choice_sync_done")
    emit(0xDA)                          # preserve decoded-character X
    emit(0x8A)
    emit(0x8D, 0x86, 0x93)             # current decoded slot
    emit(0xAF, 0xD4, 0xA1, 0x7E)       # option count
    br(0xF0, "choice_sync_restore")
    emit(0xC2, 0x20)
    emit(0x29, 0xFF, 0x00)
    emit(0xEA)                          # include terminal boundary index
    emit(0xAA)
    emit(0xE2, 0x20)

    label("choice_sync_scan")
    emit(0xBF, 0xD7, 0xA1, 0x7E)
    emit(0xCD, 0x86, 0x93)
    br(0xF0, "choice_sync_apply")
    emit(0xCA)
    br(0x10, "choice_sync_scan")
    br(0x80, "choice_sync_restore")

    label("choice_sync_apply")
    emit(0x22, *lo24(CHOICE_VISUAL_HELPER_CPU))

    label("choice_sync_restore")
    emit(0xFA)
    label("choice_sync_done")

    emit(0xDA)
    emit(0xC2, 0x20)
    emit(0xAD, 0x82, 0x93, 0x29, 0xF8, 0x00)
    emit(0x8D, 0x86, 0x93)
    emit(0x4A, 0x18, 0x6D, 0x86, 0x93, 0xA8)
    emit(0xE2, 0x20, 0xFA)
    emit(0xBD, 0x90, 0x93, 0xE8)
    br(0x80, "loaded")

    label("replay")
    emit(0xBD, 0xA4, 0xA1, 0xE8)

    label("loaded")
    emit(0x5C, 0x8A, 0x16, 0xC0)
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
    emit(0x22, 0xB0, 0x73, 0xED)       # tagged event-render scope: exact caller + C9/CA/E8-EC
    br(0x90, "stock_tail")             # BCC -> stock loop tail

    emit(0xBD, 0x8F, 0x93)             # current private decoded byte ($9390 + X - 1)
    emit(0x29, 0x7F)                   # glyph index 0..127, A stays 8-bit
    emit(0x8D, 0x8A, 0x93)             # WIDTH_INDEX low
    emit(0x9C, 0x8B, 0x93)             # WIDTH_INDEX high = 0 (8-bit STZ)
    emit(0xDA)                          # PHX: preserve decoded-character X
    emit(0xAE, 0x8A, 0x93)             # LDX WIDTH_INDEX (X remains 16-bit)
    emit(0xBF, 0x00, 0x72, 0xED)       # LDA.l $ED7200,X
    emit(0xFA)                          # PLX
    emit(0x18, 0x6D, 0x82, 0x93)       # cursor += A
    emit(0x8D, 0x82, 0x93)
    emit(0x22, *lo24(CHOICE_TRACKER_HELPER_CPU))  # remember last real-glyph end for choices

    label("stock_tail")
    # Stock tail; leave final flags from DEC just like original.
    emit(0xA9, 0x00, 0xCE, 0x76, 0xA1)
    emit(0xF0, 0x04)
    emit(0x5C, 0x86, 0x16, 0xC0)
    emit(0x5C, 0x40, 0x73, 0xED)       # final slot -> generic chunk commit

    return _resolve_rel8(code, labels, branches)


def make_choice_visual_helper() -> bytes:
    """Apply runtime-validated measured-end geometry to undecorated two-option rows.

    Decorated short choices are detected structurally from the stock closing `)`
    at decoded[terminal] and fall back to the pre-existing stock-anchor geometry.
    """
    code = bytearray(); labels = {}; branches = []
    def emit(*v): code.extend(v)
    def label(n): labels[n] = len(code)
    def br(op,t): emit(op,0); branches.append((len(code)-1,t))

    emit(0xAD,0xD4,0xA1,0xC9,0x02); br(0xD0,'stock')

    # If decoded[terminal] is the stock closing parenthesis, keep the canonical
    # decorated-choice path and invalidate private highlight geometry.
    emit(0xDA)
    emit(0xAE,0xD9,0xA1)              # terminal logical boundary
    emit(0xBD,0x90,0x93)              # decoded[terminal]
    emit(0xFA)
    emit(0xC9,0xCC); br(0xD0,'nodecor')
    emit(0x9C,0xC0,0x93)
    br(0x80,'stock')

    label('nodecor')
    emit(0xE0,0x00,0x00); br(0xF0,'first')
    emit(0xE0,0x01,0x00); br(0xF0,'second')
    emit(0xE0,0x02,0x00); br(0xF0,'terminal')
    br(0x80,'stock')

    label('first')
    # The logical first anchor remains untouched for parser/storage, but the
    # measured-end visual/highlight geometry may start two cells farther left.
    # Clamp the logical anchor to at least $03 first, then apply the validated
    # private left compaction.  This keeps long undecorated rows farther from
    # the right edge while decorated short choices still fall back structurally.
    emit(0xAD,0x86,0x93,0xC9,0x03); br(0xB0,'first_ok')
    emit(0xA9,0x03)
    label('first_ok')
    emit(0x3A,0x3A)
    emit(0x8D,0xBD,0x93)
    emit(0x0A,0x0A,0x0A,0x8D,0x82,0x93)
    emit(0x9C,0xBC,0x93)              # no measured endpoint yet
    emit(0x9C,0xC0,0x93)              # private highlight invalid until terminal
    emit(0x6B)

    label('second')
    # Normally keep one full blank cell after ceil(last real-glyph end / 8).
    # If the rounded endpoint has already reached visual cell $11 (136 px),
    # use that rounded endpoint directly instead.  This generic right-edge
    # safety branch was runtime-validated on the $00D0 stress case before the
    # later two-cell private left compaction was adopted.  In the current
    # geometry $00D0 itself starts farther left and therefore keeps the normal
    # separator, but the proven late-end fallback remains as a structural guard.
    emit(0xAD,0xBC,0x93,0x18,0x69,0x07); br(0xB0,'stock')
    emit(0x29,0xF8)
    emit(0xC9,0x88); br(0xB0,'second_store')
    emit(0x18,0x69,0x08)
    label('second_store')
    emit(0x8D,0x82,0x93)
    emit(0x4A,0x4A,0x4A,0x8D,0xBE,0x93)
    emit(0x6B)

    label('terminal')
    emit(0xAD,0xBC,0x93,0x18,0x69,0x07); br(0xB0,'stock')
    emit(0x29,0xF8,0x8D,0x82,0x93)
    emit(0x4A,0x4A,0x4A,0x8D,0xBF,0x93)
    emit(0xA9,0x01,0x8D,0xC0,0x93)
    emit(0x6B)

    label('stock')
    emit(0xAD,0x86,0x93,0x0A,0x0A,0x0A,0x8D,0x82,0x93,0x6B)
    return _resolve_rel8(code, labels, branches)


def make_choice_tracker_helper() -> bytes:
    """Record the end cursor after the most recent non-space glyph in a two-option row."""
    code = bytearray(); labels = {}; branches = []
    def emit(*v): code.extend(v)
    def label(n): labels[n] = len(code)
    def br(op,t): emit(op,0); branches.append((len(code)-1,t))

    emit(0xAF,0x00,0x1D,0x00); br(0x10,'ret')
    emit(0xAD,0xD4,0xA1,0xC9,0x02); br(0xD0,'ret')
    emit(0xBD,0x8F,0x93,0xC9,0x80); br(0xF0,'ret')
    emit(0xAD,0x82,0x93,0x8D,0xBC,0x93)
    label('ret'); emit(0x6B)
    return _resolve_rel8(code, labels, branches)


def make_chunk_cells_snapshot_helper() -> bytes:
    """Capture the useful decoded chunk as a count of 8-pixel cells.

    X is the current renderer slot. At the start of the first padded slot,
    X equals the decoded-character count saved from `$A1CE`. The pixel cursor
    still contains only useful glyph advances at that exact moment, so convert
    it to `ceil(width / 8)` before the 38-slot private-buffer loop can add padding.

    The helper is also called once at final commit. That covers a full 38-slot
    chunk with no padded slot. Any non-empty useful cursor that lands exactly
    on 256 px wraps to zero in the 8-bit cursor and therefore maps to 32 cells.
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
    emit(0xAD, 0x8E, 0x93)             # empty chunk or wrapped 256-pixel chunk?
    br(0xF0, "store")                  # count=0 -> zero cells
    emit(0xA9, 0x20)                   # supported non-empty wrap = 256 px
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

    Non-line-break chunks keep the runtime-validated generic conversion. For
    line-break chunks at the old <=32-character contract, preserve the validated
    stock behavior. A newly possible 33..38-character line-break chunk must be
    converted too, otherwise the stock progression loop would try to process
    more than the 32 physical bitmap cells.
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

    emit(0x22, 0xB0, 0x73, 0xED)       # tagged event-render scope
    br(0x90, "return")

    emit(0xAD, 0x8E, 0x93)             # saved decoded count
    emit(0xC9, 0x27)                   # at most 38 decoded glyphs
    br(0xB0, "return")                 # unexpected count -> stock behavior

    emit(0xAD, 0xCE, 0xA1)             # stock line-end flag
    br(0x10, "convert")                # non-line-break: validated conversion
    emit(0xAD, 0x8E, 0x93)             # line-break chunk
    emit(0xC9, 0x21)                   # <=32 stays on validated stock path
    br(0x90, "return")

    label("convert")
    # A full 38-character chunk has no first padded slot; snapshot once here.
    emit(0x22, 0x80, 0x73, 0xED)       # JSL $ED7380

    emit(0xAD, 0xCE, 0xA1)
    emit(0x29, 0x80)                    # preserve line-end bit
    emit(0x0D, 0x8F, 0x93)             # OR physical VWF cell count
    emit(0x8D, 0xCE, 0xA1)

    label("return")
    emit(0xA9, 0x00)                   # stock char-end return A value
    emit(0x5C, 0xB7, 0x16, 0xC0)       # JML $C016B7 (RTS)

    return _resolve_rel8(code, labels, branches)


def make_font_row_helper() -> bytes:
    """Dispatch one stock font row through the shared renderer when active.

    The stock $C0:16A4 LDA is overwritten by the JSL hook. For caller-tagged
    event dialogue, the shared C7 helper now owns the complete stock-row load,
    framing and composition sequence. Non-event callers replay only the stock
    LDA and return unchanged.
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

    emit(0x22, 0xB0, 0x73, 0xED)       # tagged event-render scope
    br(0x90, "stock")                 # BCC stock
    emit(*ROW_RENDERER_CALL)            # shared stock row + framing + compositor
    emit(0x6B)                          # return current half for stock STA

    label("stock")
    emit(0xBF, 0x00, 0xDC, 0xD2)       # replay overwritten stock LDA
    emit(0x6B)

    return _resolve_rel8(code, labels, branches)


def make_outline_post_helper() -> bytes:
    """Repair horizontal outline pixels lost across 8-pixel cell boundaries.

    This runtime-validated helper is entered at $C0:1168, after the stock
    JSR $162C has returned; that call must remain intact for the stock outline.

    The repair itself is bank-neutral. Runtime-validated scope gating requires
    the exact `vwf_dialogues` renderer-active tag value ($7E:9385 == $01), so
    ordinary tagged $C9/$CA or relocated $E8-$EC dialogue is eligible while `vwf_intro`'s intro
    intro remains excluded: under that mutually-exclusive scope $9385 holds a
    validated glyph advance in the range 3..8, never the tag value 1.

    Scan the already rendered $9000-$917F bitmap. If ink touches the left/right
    edge of a source cell, add the corresponding one-pixel outline contribution
    to the neighboring output tile. Then replay the stock tail.
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

    emit(0xAF, 0x85, 0x93, 0x7E)       # LDA.l $7E9385: `vwf_dialogues` tag / intro advance
    emit(0xC9, 0x01)                   # exact dialogue-active tag only
    br(0xD0, "replay")              # intro (3..8), inactive (0), other -> stock tail

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

EVENT_RENDER_SCOPE_HELPER = make_event_render_scope_helper()
CHAR_START_HELPER = make_char_start_helper()
CHAR_END_HELPER = make_char_end_helper()
CHOICE_VISUAL_HELPER = make_choice_visual_helper()
CHOICE_TRACKER_HELPER = make_choice_tracker_helper()
CHUNK_CELLS_SNAPSHOT_HELPER = make_chunk_cells_snapshot_helper()
CHUNK_COMMIT_HELPER = make_chunk_commit_helper()
FONT_ROW_HELPER = make_font_row_helper()
OUTLINE_POST_HELPER = make_outline_post_helper()


def _validate_layout() -> None:
    blocks = (
        ("char-end helper", CHAR_END_HELPER_FILE, CHAR_END_HELPER, FONT_ROW_HELPER_FILE),
        ("font-row helper", FONT_ROW_HELPER_FILE, FONT_ROW_HELPER, CHAR_START_HELPER_FILE),
        ("char-start helper", CHAR_START_HELPER_FILE, CHAR_START_HELPER, WIDTH_TABLE_FILE),
        ("outline-post helper", OUTLINE_POST_HELPER_FILE, OUTLINE_POST_HELPER, CHUNK_COMMIT_HELPER_FILE),
        ("chunk-commit helper", CHUNK_COMMIT_HELPER_FILE, CHUNK_COMMIT_HELPER, CHUNK_CELLS_SNAPSHOT_FILE),
        ("chunk snapshot helper", CHUNK_CELLS_SNAPSHOT_FILE, CHUNK_CELLS_SNAPSHOT_HELPER, EVENT_RENDER_SCOPE_HELPER_FILE),
        ("event-render scope helper", EVENT_RENDER_SCOPE_HELPER_FILE, EVENT_RENDER_SCOPE_HELPER, 0x2D7400),
        ("choice visual helper", CHOICE_VISUAL_HELPER_FILE, CHOICE_VISUAL_HELPER, CHOICE_TRACKER_HELPER_FILE),
        ("choice tracker helper", CHOICE_TRACKER_HELPER_FILE, CHOICE_TRACKER_HELPER, 0x2D7A00),
    )
    for label, start, payload, limit in blocks:
        if start + len(payload) > limit:
            raise RuntimeError(
                f"Shared VWF {label} overlaps the next allocation: "
                f"{start + len(payload):#x} > {limit:#x}"
            )
    if WIDTH_TABLE_FILE + 128 > OUTLINE_POST_HELPER_FILE:
        raise RuntimeError("Shared VWF width table overlaps the outline-post helper")


_validate_layout()


def validate_stock(base: bytes) -> None:
    for off, sig, label in (
        (CHAR_START_FILE, CHAR_START_SIGNATURE, "character start"),
        (FONT_ROW_FILE, FONT_ROW_SIGNATURE, "font row"),
        (CHAR_END_FILE, CHAR_END_SIGNATURE, "character end"),
        (OUTLINE_POST_FILE, OUTLINE_POST_SIGNATURE, "post-outline"),
    ):
        if base[off:off + len(sig)] != sig:
            raise SystemExit(f"Unexpected clean-US shared VWF {label} signature")


def install(rom: bytearray, width_table: bytes) -> None:
    if len(width_table) != 128:
        raise ValueError("shared VWF runtime width table must contain 128 bytes")
    rom[CHAR_START_FILE:CHAR_START_FILE + len(CHAR_START_HOOK)] = CHAR_START_HOOK
    rom[FONT_ROW_FILE:FONT_ROW_FILE + len(FONT_ROW_HOOK)] = FONT_ROW_HOOK
    rom[CHAR_END_FILE:CHAR_END_FILE + len(CHAR_END_HOOK)] = CHAR_END_HOOK
    rom[OUTLINE_POST_FILE:OUTLINE_POST_FILE + len(OUTLINE_POST_HOOK)] = OUTLINE_POST_HOOK
    for off, payload in (
        (CHAR_START_HELPER_FILE, CHAR_START_HELPER),
        (CHAR_END_HELPER_FILE, CHAR_END_HELPER),
        (FONT_ROW_HELPER_FILE, FONT_ROW_HELPER),
        (WIDTH_TABLE_FILE, width_table),
        (OUTLINE_POST_HELPER_FILE, OUTLINE_POST_HELPER),
        (CHUNK_COMMIT_HELPER_FILE, CHUNK_COMMIT_HELPER),
        (CHUNK_CELLS_SNAPSHOT_FILE, CHUNK_CELLS_SNAPSHOT_HELPER),
        (EVENT_RENDER_SCOPE_HELPER_FILE, EVENT_RENDER_SCOPE_HELPER),
        (CHOICE_VISUAL_HELPER_FILE, CHOICE_VISUAL_HELPER),
        (CHOICE_TRACKER_HELPER_FILE, CHOICE_TRACKER_HELPER),
    ):
        rom[off:off + len(payload)] = payload
