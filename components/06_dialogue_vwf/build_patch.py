#!/usr/bin/env python3
"""Build the runtime-validated dialogue VWF checkpoint.

The pixel-aware parser preflight that prevents right-edge glyph loss is now
runtime-validated on the known early-game overflow case. The stock
$C0:168A-$C0:16B0 character-to-glyph lookup remains intact. Component
06 composes the already-selected stock row at a cumulative pixel cursor, reads
advances from the validated 128-entry table at $ED:7200, and frames glyphs only
through the small validated selectors.

Validated lowercase framing is a-h/k/m-s/u-z=1 px, i/l=3 px, j/t=2 px. Lowercase
advances follow the shared validated policy: ink_width + 1 black separator pixel.

Handled punctuation uses the runtime-validated visual spacing policy of one black
pixel before the ink and one after it for the already validated set. Colon $C5 is runtime-validated at shift 1 / advance 7, giving two black pixels before and three after its 2 px ink.
The canonical French $D4-$E5 framing/metrics are also runtime-validated. $CD is deliberately excluded from all active special handling and follows the generic
conservative path.

The post-stock outline-boundary repair is runtime-validated and runs only after
the stock outline routine returns. The width-table lookup keeps A in 8-bit mode
and zero-extends the glyph index through private WRAM $7E:938A-$938B.

The runtime-validated generic interruption path saves the true decoded count,
snapshots the cumulative VWF width before padded renderer slots, and converts
interrupted event-render `$C9/$CA` chunks to physical 8-pixel cells before stock progression.
The decoded-text path uses the shared 44-byte private buffer and a 38-slot renderer. New >32-character line-break chunks are also converted before stock progression so the stock transfer loop never exceeds its 32 physical bitmap cells.
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
from shared.asm65816 import MiniAssembler, lo24  # noqa: E402
from shared.rom import ROM_SIZE_OFFSET, expand_rom, update_checksum, validate_base_rom  # noqa: E402
from shared.french_charset import FIRST_CODE, FULL_DTE_THRESHOLD, FULL_FRENCH_CHARS, glyph_bytes  # noqa: E402
from shared.vwf_geometry import ink_bounds  # noqa: E402
from shared.vwf_metrics import (  # noqa: E402
    apply_validated_framing,
    validated_advance,
    validated_left_shift,
)
from shared.vwf_framing import (  # noqa: E402
    validate_stock as validate_shared_framing_stock,
    install as install_shared_framing,
)
from shared.vwf_compositor import (  # noqa: E402
    validate_stock as validate_shared_compositor_stock,
    install as install_shared_compositor,
)
from shared.vwf_row_renderer import (  # noqa: E402
    ROW_RENDERER_CALL,
    validate_stock as validate_shared_row_renderer_stock,
    install as install_shared_row_renderer,
)
from shared.vwf_outline import (  # noqa: E402
    validate_stock as validate_shared_outline_stock,
    install as install_shared_outline,
)
from shared.vwf_text_buffer import (  # noqa: E402
    validate_stock as validate_shared_text_buffer_stock,
    install_common as install_shared_text_buffer,
    enable_dialogue as enable_dialogue_private_buffer,
)

RENDER_ENTRY_FILE = 0x00167D
CHAR_START_FILE = 0x001686
FONT_ROW_FILE = 0x0016A4
CHAR_END_FILE = 0x0016B1
OUTLINE_POST_FILE = 0x001168

ENTRY_HELPER_FILE = 0x2D7040
CHAR_START_HELPER_FILE = 0x2D7180
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

# Dialogue-only parser preflight.  The hook replaces the stock source-byte
# fetch at $C0:16EA, but gates on shared parser mode 2 and replays the exact
# stock load/increment for intro, GAME SELECT and every non-dialogue caller.
PARSER_FETCH_FILE = 0x0016EA
PARSER_FETCH_SIGNATURE = bytes.fromhex("B9 00 00 C8")
PARSER_FETCH_HELPER_FILE = 0x2D7500
PARSER_FETCH_HELPER_CPU = 0xED7500
WRAP_GLYPH_HELPER_FILE = 0x2D7700
WRAP_GLYPH_HELPER_CPU = 0xED7700
RIGHT_EDGE_TABLE_FILE = 0x2D7780
RIGHT_EDGE_TABLE_CPU = 0xED7780
PARSER_FETCH_HOOK = bytes([0x5C, *lo24(PARSER_FETCH_HELPER_CPU)])

# Parser-phase reuse of the renderer scratch range.  The parser and renderer
# are never active at the same time; renderer entry reinitializes its own state.
WRAP_CURSOR = 0x7E9382          # 16-bit cumulative VWF advance
WRAP_BUDGET = 0x7E9384          # 16-bit physical pixels still available
WRAP_LAST_VALID = 0x7E9386      # safe source-space checkpoint exists
WRAP_LAST_SOURCE = 0x7E9387     # 16-bit source pointer after that space
WRAP_LAST_COUNT = 0x7E9389      # decoded count before that space
WRAP_TEST_CURSOR = 0x7E938A     # 16-bit speculative cursor
WRAP_FIT_FLAG = 0x7E938C        # glyph helper result scratch
WRAP_PAIR_FIT = 0x7E938D        # DTE pair aggregate fit flag
WRAP_DTE_PAIR = 0x7E938E        # 16-bit decoded DTE pair

# The stock parser leaves the decoded character count in the low seven bits
# of $A1CE. The renderer saves it in private WRAM before the 38-slot loop and
# snapshots the useful VWF width before padded $80 slots inflate the cursor.

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


def make_wrap_glyph_helper() -> bytes:
    """Test one decoded glyph against the current physical pixel budget.

    Input A is one decoded $80-$FF glyph code.  The helper always advances the
    speculative 16-bit cursor at ``WRAP_TEST_CURSOR`` by the validated VWF
    advance and returns carry set iff all non-zero framed pixels of this glyph
    still fit within ``WRAP_BUDGET``.  Using the framed right edge rather than
    the advance is intentional: a final black separator pixel may legally land
    just beyond the last physical pixel without clipping visible ink.
    """
    a = MiniAssembler(WRAP_GLYPH_HELPER_CPU)

    a.emit(0xDA)                              # PHX
    a.emit(0xC2, 0x20)                       # REP #$20
    a.emit(0x29, 0xFF, 0x00)                 # zero-extend decoded code
    a.emit(0x38)                              # SEC
    a.emit(0xE9, 0x80, 0x00)                 # SBC #$0080 -> 0..127
    a.emit(0xAA)                              # TAX
    a.emit(0xE2, 0x20)                       # SEP #$20
    a.emit(0xBF, *lo24(0xED0000 | (RIGHT_EDGE_TABLE_CPU & 0xFFFF)))
    a.emit(0xC9, 0xFF)                       # blank glyph / space?
    a.rel8(0xF0, "blank")

    a.emit(0x1A)                              # right edge + 1 = visible extent
    a.emit(0xC2, 0x20)                       # REP #$20
    a.emit(0x29, 0xFF, 0x00)
    a.emit(0x18)                              # CLC
    a.emit(0x6F, *lo24(WRAP_TEST_CURSOR))     # ADC.l speculative cursor
    a.emit(0xCF, *lo24(WRAP_BUDGET))          # CMP.l pixel budget
    a.rel8(0x90, "fits16")                  # BCC
    a.rel8(0xF0, "fits16")                  # BEQ

    a.emit(0xE2, 0x20)                       # SEP #$20
    a.emit(0xA9, 0x00)
    a.emit(0x8F, *lo24(WRAP_FIT_FLAG))
    a.rel8(0x80, "advance")

    a.label("fits16")
    a.emit(0xE2, 0x20)                       # SEP #$20
    a.emit(0xA9, 0x01)
    a.emit(0x8F, *lo24(WRAP_FIT_FLAG))
    a.rel8(0x80, "advance")

    a.label("blank")
    a.emit(0xA9, 0x01)                       # no visible pixels can clip
    a.emit(0x8F, *lo24(WRAP_FIT_FLAG))

    a.label("advance")
    a.emit(0xBF, *lo24(0xED7200))            # validated advance table, X-indexed
    a.emit(0xC2, 0x20)                       # REP #$20
    a.emit(0x29, 0xFF, 0x00)
    a.emit(0x18)
    a.emit(0x6F, *lo24(WRAP_TEST_CURSOR))
    a.emit(0x8F, *lo24(WRAP_TEST_CURSOR))
    a.emit(0xE2, 0x20)                       # SEP #$20
    a.emit(0xFA)                              # PLX
    a.emit(0xAF, *lo24(WRAP_FIT_FLAG))
    a.rel8(0xF0, "no_fit")
    a.emit(0x38, 0x6B)                       # SEC / RTL
    a.label("no_fit")
    a.emit(0x18, 0x6B)                       # CLC / RTL
    return a.resolve()


def make_parser_fetch_helper() -> bytes:
    """Preflight dialogue text before the stock parser consumes a source token.

    Stock fixed-width decoding can safely consume one source glyph per remaining
    physical cell. The 38-character VWF extension deliberately grants six extra
    logical parser units, so on a partially used line the parser can otherwise
    consume glyphs whose pixels no longer fit and permanently advance the source
    pointer past them.

    Mode 2 keeps a 16-bit VWF cursor and the true remaining physical pixel budget.
    Direct glyphs and DTE pairs are tested before Y advances. When an overflowing
    token is reached and a safe source-space checkpoint exists, the helper rewinds
    to that checkpoint, truncates/clears the private buffer, and reuses the
    stock $C0:17B0 line-finalization path.  Without a safe space it simply ends the
    line before the offending token, so no source glyph is lost.  Dynamic-name
    temporary sources keep stock control flow; they are never rewound across the
    source-bank switch.
    """
    a = MiniAssembler(PARSER_FETCH_HELPER_CPU)

    def jml(cpu: int) -> None:
        a.emit(0x5C, *lo24(cpu))

    # The hook is global but component 06 owns only shared parser mode 2.
    a.emit(0xAF, *lo24(0x7E9380))             # LDA.l PARSER_MODE
    a.emit(0xC9, 0x02)
    a.rel8(0xF0, "dialogue")
    a.label("stock")
    a.emit(0xB9, 0x00, 0x00, 0xC8)           # stock LDA $0000,Y / INY
    jml(0xC016EE)

    a.label("dialogue")
    a.emit(0xE0, 0x00, 0x00)                 # CPX #$0000
    a.rel8(0xD0, "load")

    # New parser invocation: derive the real physical budget from the same
    # stock state that feeds $A1CA, but keep it in pixels instead of glyphs.
    a.emit(0xA9, 0x00)
    a.emit(0x8F, *lo24(WRAP_CURSOR))
    a.emit(0x8F, *lo24(WRAP_CURSOR + 1))
    a.emit(0x8F, *lo24(WRAP_LAST_VALID))
    a.emit(0xAF, *lo24(0x7EA16A))
    a.emit(0x38)
    a.emit(0xEF, *lo24(0x7EA181))             # SBC.l current physical cell
    a.emit(0x8F, *lo24(WRAP_BUDGET))
    a.emit(0xA9, 0x00)
    a.emit(0x8F, *lo24(WRAP_BUDGET + 1))
    a.emit(0xC2, 0x20)
    a.emit(0xAF, *lo24(WRAP_BUDGET))
    a.emit(0x0A, 0x0A, 0x0A)                 # cells * 8
    a.emit(0x8F, *lo24(WRAP_BUDGET))
    a.emit(0xE2, 0x20)

    a.label("load")
    a.emit(0xB9, 0x00, 0x00)                 # peek source token; Y unchanged
    a.emit(0xC9, 0x7F)
    a.rel8(0xF0, "accept_raw")               # explicit stock line break
    a.emit(0xC9, DTE_NEW_THRESHOLD)
    a.rel8(0x90, "not_upper_dte")           # BCC
    a.rel16(0x82, "dte_upper")
    a.label("not_upper_dte")
    a.emit(0xC9, 0x80)
    a.rel8(0xB0, "direct")
    a.emit(0xC9, 0x5F)
    a.rel8(0x90, "control")                 # BCC
    a.rel16(0x82, "dte_lower")

    # Event/control token.
    a.label("control")
    # Do not ever rewind a later word across a control
    # that may alter parser source/state or have event-engine side effects.
    a.emit(0xA9, 0x00)
    a.emit(0x8F, *lo24(WRAP_LAST_VALID))
    a.label("accept_raw")
    a.emit(0xB9, 0x00, 0x00, 0xC8)
    jml(0xC016EE)

    a.label("direct")
    # Ordinary source spaces become safe word-boundary checkpoints, except at
    # chunk start and while stock dynamic-source bit $08 is active.
    a.emit(0xC9, 0x80)
    a.rel8(0xD0, "direct_test")
    a.emit(0xAF, *lo24(0x001D00))
    a.emit(0x89, 0x08)                       # BIT #$08
    a.rel8(0xD0, "direct_test")
    a.emit(0xE0, 0x00, 0x00)
    a.rel8(0xF0, "direct_test")
    a.emit(0xA9, 0x01)
    a.emit(0x8F, *lo24(WRAP_LAST_VALID))
    a.emit(0xC2, 0x20)
    a.emit(0x98)                              # TYA
    a.emit(0x1A)                              # source resumes after this space
    a.emit(0x8F, *lo24(WRAP_LAST_SOURCE))
    a.emit(0xE2, 0x20)
    a.emit(0x8A)                              # TXA low byte = decoded count
    a.emit(0x8F, *lo24(WRAP_LAST_COUNT))

    a.label("direct_test")
    a.emit(0xC2, 0x20)
    a.emit(0xAF, *lo24(WRAP_CURSOR))
    a.emit(0x8F, *lo24(WRAP_TEST_CURSOR))
    a.emit(0xE2, 0x20)
    a.emit(0xB9, 0x00, 0x00)
    a.emit(0x22, *lo24(WRAP_GLYPH_HELPER_CPU))
    a.rel8(0xB0, "direct_commit")            # BCS: visible ink fits
    a.emit(0xAF, *lo24(0x001D00))
    a.emit(0x89, 0x08)
    a.rel8(0xD0, "direct_commit")            # don't split temporary dynamic source
    a.rel16(0x82, "overflow")

    a.label("direct_commit")
    a.emit(0xC2, 0x20)
    a.emit(0xAF, *lo24(WRAP_TEST_CURSOR))
    a.emit(0x8F, *lo24(WRAP_CURSOR))
    a.emit(0xE2, 0x20)
    a.emit(0xB9, 0x00, 0x00, 0xC8)
    jml(0xC016EE)

    # DTE source bytes expand to two decoded glyphs.  Preflight the pair
    # atomically so a line boundary can never consume only half of one token.
    a.label("dte_lower")
    a.emit(0xDA)                              # PHX parser decoded index
    a.emit(0xC2, 0x20)
    a.emit(0x29, 0xFF, 0x00)
    a.emit(0x38)
    a.emit(0xE9, 0x60, 0x00)
    a.emit(0x0A)
    a.emit(0xAA)
    a.emit(0xBF, *lo24(0xC77299))
    a.emit(0x8F, *lo24(WRAP_DTE_PAIR))
    a.emit(0xE2, 0x20)
    a.emit(0xFA)
    a.rel16(0x82, "dte_test")

    a.label("dte_upper")
    a.emit(0xDA)
    a.emit(0xC2, 0x20)
    a.emit(0x29, 0xFF, 0x00)
    a.emit(0x38)
    a.emit(0xE9, 0xC3, 0x00)                 # exact stock DTE addressing basis
    a.emit(0x0A)
    a.emit(0xAA)
    a.emit(0xBF, *lo24(0xC77299))
    a.emit(0x8F, *lo24(WRAP_DTE_PAIR))
    a.emit(0xE2, 0x20)
    a.emit(0xFA)

    a.label("dte_test")
    a.emit(0xC2, 0x20)
    a.emit(0xAF, *lo24(WRAP_CURSOR))
    a.emit(0x8F, *lo24(WRAP_TEST_CURSOR))
    a.emit(0xE2, 0x20)
    a.emit(0xA9, 0x01)
    a.emit(0x8F, *lo24(WRAP_PAIR_FIT))

    a.emit(0xAF, *lo24(WRAP_DTE_PAIR))
    a.emit(0x22, *lo24(WRAP_GLYPH_HELPER_CPU))
    a.rel8(0xB0, "dte_first_ok")
    a.emit(0xA9, 0x00)
    a.emit(0x8F, *lo24(WRAP_PAIR_FIT))
    a.label("dte_first_ok")
    a.emit(0xAF, *lo24(WRAP_DTE_PAIR + 1))
    a.emit(0x22, *lo24(WRAP_GLYPH_HELPER_CPU))
    a.rel8(0xB0, "dte_second_ok")
    a.emit(0xA9, 0x00)
    a.emit(0x8F, *lo24(WRAP_PAIR_FIT))
    a.label("dte_second_ok")
    a.emit(0xAF, *lo24(WRAP_PAIR_FIT))
    a.rel8(0xD0, "dte_commit")
    a.emit(0xAF, *lo24(0x001D00))
    a.emit(0x89, 0x08)
    a.rel8(0xD0, "dte_commit")
    a.rel16(0x82, "overflow")

    a.label("dte_commit")
    # A DTE token can safely become a word-wrap checkpoint when its second
    # decoded glyph is a space: keeping the first glyph and resuming after the
    # source token is then source-aligned. Never attempt a midpoint rewind for
    # a DTE whose first glyph is the space.
    a.emit(0xAF, *lo24(0x001D00))
    a.emit(0x89, 0x08)
    a.rel8(0xD0, "dte_no_space_checkpoint")
    a.emit(0xAF, *lo24(WRAP_DTE_PAIR + 1))
    a.emit(0xC9, 0x80)
    a.rel8(0xD0, "dte_no_space_checkpoint")
    a.emit(0xA9, 0x01)
    a.emit(0x8F, *lo24(WRAP_LAST_VALID))
    a.emit(0xC2, 0x20)
    a.emit(0x98)                              # TYA
    a.emit(0x1A)                              # resume after the DTE source token
    a.emit(0x8F, *lo24(WRAP_LAST_SOURCE))
    a.emit(0xE2, 0x20)
    a.emit(0x8A)                              # keep first decoded glyph only
    a.emit(0x1A)
    a.emit(0x8F, *lo24(WRAP_LAST_COUNT))
    a.label("dte_no_space_checkpoint")

    a.emit(0xC2, 0x20)
    a.emit(0xAF, *lo24(WRAP_TEST_CURSOR))
    a.emit(0x8F, *lo24(WRAP_CURSOR))
    a.emit(0xE2, 0x20)
    a.emit(0xB9, 0x00, 0x00, 0xC8)
    jml(0xC016EE)

    a.label("overflow")
    a.emit(0xAF, *lo24(WRAP_LAST_VALID))
    a.rel8(0xF0, "hard_break")
    a.emit(0xAF, *lo24(WRAP_LAST_COUNT))
    a.rel8(0xF0, "hard_break")               # never wrap to an empty leading-space line

    # Rewind to the word after the last safe source-space.  The renderer still
    # visits all 38 private slots, so erase every discarded decoded byte back to
    # $80 padding before truncating the useful count.
    a.emit(0x8F, *lo24(0x7EA1CE))
    a.emit(0xC2, 0x20)
    a.emit(0xAF, *lo24(WRAP_LAST_SOURCE))
    a.emit(0xA8)                              # TAY
    a.emit(0xE2, 0x20)
    a.emit(0xAF, *lo24(WRAP_LAST_COUNT))
    a.emit(0xC2, 0x20)
    a.emit(0x29, 0xFF, 0x00)
    a.emit(0xAA)                              # X = first discarded slot
    a.emit(0xE2, 0x20)
    a.emit(0xA9, 0x80)
    a.label("clear_discarded")
    a.emit(0x9F, *lo24(0x7E9390))            # STA.l private buffer,X
    a.emit(0xE8)
    a.emit(0xE0, 0x26, 0x00)                 # clear through slot 37
    a.rel8(0x90, "clear_discarded")

    a.label("hard_break")
    jml(0xC017B0)                              # stock line-finalization, Y not consumed
    return a.resolve()


WRAP_GLYPH_HELPER = make_wrap_glyph_helper()
PARSER_FETCH_HELPER = make_parser_fetch_helper()


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
    emit(0xA9, 0x26, 0x8D, 0x76, 0xA1) # 38 decoded slots on private-buffer path
    emit(0x5C, 0x82, 0x16, 0xC0)       # JML $C01682

    label("replay")
    emit(0xA9, 0x20, 0x8D, 0x76, 0xA1) # stock callers keep 32 slots
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
    # Y = floor(pixel_cursor/8)*12. Since cursor&$F8 is already tile*8,
    # tile*12 is simply masked_cursor + masked_cursor/2.
    emit(0xAD, 0x82, 0x93, 0x29, 0xF8, 0x00)
    emit(0x8D, 0x86, 0x93)             # masked cursor (tile*8) scratch
    emit(0x4A, 0x18, 0x6D, 0x86, 0x93, 0xA8)  # tile*12 -> Y
    emit(0xE2, 0x20, 0xFA)             # SEP #$20 / PLX
    emit(0xBD, 0x90, 0x93, 0xE8)       # private decoded buffer / INX
    br(0x80, "loaded")

    label("replay")
    emit(0xBD, 0xA4, 0xA1, 0xE8)       # non-event stock buffer / INX

    label("loaded")
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

# Framing selector source is shared with component 05.  Component 06 keeps
# the existing runtime locations so this refactor does not alter its validated
# execution path.


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


ENTRY_HELPER = make_entry_helper()
CHAR_START_HELPER = make_char_start_helper()
CHAR_END_HELPER = make_char_end_helper()
CHUNK_CELLS_SNAPSHOT_HELPER = make_chunk_cells_snapshot_helper()
CHUNK_COMMIT_HELPER = make_chunk_commit_helper()
FONT_ROW_HELPER = make_font_row_helper()


def make_outline_post_helper() -> bytes:
    """Repair horizontal outline pixels lost across 8-pixel cell boundaries.

    This runtime-validated helper is entered at $C0:1168, after the stock
    JSR $162C has returned; that call must remain intact for the stock outline.

    The repair itself is bank-neutral. Runtime-validated scope gating requires
    the exact component-06 renderer-active tag value ($7E:9385 == $01), so
    ordinary tagged $C9/$CA dialogue is eligible while component 05's translated
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

    emit(0xAF, 0x85, 0x93, 0x7E)       # LDA.l $7E9385: component-06 tag / intro advance
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


OUTLINE_POST_HELPER = make_outline_post_helper()

def make_width_table(base: bytes) -> bytes:
    """Build the canonical validated VWF advance table.

    The policy lives in ``shared.vwf_metrics`` so components 05 and 06 can
    generate the same metrics while keeping their different runtime glyph
    selection paths.
    """
    table = bytearray(128)
    font = bytearray(base[FONT_BASE:FONT_BASE + 128 * 12])
    french = glyph_bytes(FULL_FRENCH_CHARS)
    french_start = (ACCENT_FIRST - 0x80) * 12
    font[french_start:french_start + len(french)] = french

    for code in range(0x80, 0x100):
        rows = font[(code - 0x80) * 12:(code - 0x80 + 1) * 12]
        table[code - 0x80] = validated_advance(code, rows)

    return bytes(table)


def make_right_edge_table(base: bytes) -> bytes:
    """Return the framed rightmost ink column for every decoded glyph.

    ``$FF`` marks a completely blank glyph.  The parser preflight uses this
    alongside the validated advance table so a trailing separator pixel does
    not cause a premature wrap when the visible ink still fits exactly.
    """
    font = bytearray(base[FONT_BASE:FONT_BASE + 128 * 12])
    french = glyph_bytes(FULL_FRENCH_CHARS)
    french_start = (ACCENT_FIRST - 0x80) * 12
    font[french_start:french_start + len(french)] = french

    table = bytearray()
    for code in range(0x80, 0x100):
        rows = font[(code - 0x80) * 12:(code - 0x80 + 1) * 12]
        framed = apply_validated_framing(code, rows)
        bounds = ink_bounds(framed)
        table.append(0xFF if bounds is None else bounds[1])
    return bytes(table)


def validate_helper_layout() -> None:
    """Reject generated helper growth that would overlap the next fixed block."""
    blocks = (
        ("entry helper", ENTRY_HELPER_FILE, len(ENTRY_HELPER), CHAR_END_HELPER_FILE),
        ("char-end helper", CHAR_END_HELPER_FILE, len(CHAR_END_HELPER), FONT_ROW_HELPER_FILE),
        ("font-row helper", FONT_ROW_HELPER_FILE, len(FONT_ROW_HELPER), CHAR_START_HELPER_FILE),
        ("char-start helper", CHAR_START_HELPER_FILE, len(CHAR_START_HELPER), WIDTH_TABLE_FILE),
        ("width table", WIDTH_TABLE_FILE, 128, OUTLINE_POST_HELPER_FILE),
        ("outline helper", OUTLINE_POST_HELPER_FILE, len(OUTLINE_POST_HELPER), CHUNK_COMMIT_HELPER_FILE),
        ("chunk commit helper", CHUNK_COMMIT_HELPER_FILE, len(CHUNK_COMMIT_HELPER), CHUNK_CELLS_SNAPSHOT_FILE),
        ("chunk snapshot helper", CHUNK_CELLS_SNAPSHOT_FILE, len(CHUNK_CELLS_SNAPSHOT_HELPER), EVENT_RENDER_SCOPE_HELPER_FILE),
        ("event-render scope helper", EVENT_RENDER_SCOPE_HELPER_FILE, len(EVENT_RENDER_SCOPE_HELPER), 0x2D7400),
        ("parser-fetch helper", PARSER_FETCH_HELPER_FILE, len(PARSER_FETCH_HELPER), WRAP_GLYPH_HELPER_FILE),
        ("wrap-glyph helper", WRAP_GLYPH_HELPER_FILE, len(WRAP_GLYPH_HELPER), RIGHT_EDGE_TABLE_FILE),
        ("right-edge table", RIGHT_EDGE_TABLE_FILE, 128, 0x2D8000),
    )
    for label, start, size, next_start in blocks:
        if start + size > next_start:
            raise SystemExit(
                f"Dialogue VWF {label} overlaps next fixed block: "
                f"0x{start:06X}+0x{size:X} > 0x{next_start:06X}"
            )

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
        bounds = ink_bounds(rows)
        if bounds is None or bounds[0] != validated_left_shift(code):
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
        bounds = ink_bounds(rows)
        if bounds is None:
            raise SystemExit(f"Empty lowercase glyph for ${code:02X}")
        left, right = bounds
        expected = min(8, (right - left + 1) + 1)
        width = width_table[code - 0x80]
        if width != expected:
            raise SystemExit(f"Unexpected ink-width+1 metric for ${code:02X}")
        framed_right = right - validated_left_shift(code)
        if width != framed_right + 2:
            raise SystemExit(f"Missing framed separator for ${code:02X}")

    # Runtime-validated uppercase A-Z: stock geometry is homogeneous except I.
    for code in range(0x9B, 0xB5):
        rows = font[(code - 0x80) * 12:(code - 0x80 + 1) * 12]
        bounds = ink_bounds(rows)
        if bounds is None:
            raise SystemExit(f"Empty uppercase glyph for ${code:02X}")
        left, right = bounds
        expected_left = 3 if code == 0xA3 else 1
        expected_width = 2 if code == 0xA3 else 6
        if left != expected_left or (right - left + 1) != expected_width:
            raise SystemExit(f"Unexpected uppercase stock geometry for ${code:02X}")
        if validated_left_shift(code) != expected_left:
            raise SystemExit(f"Shared uppercase framing policy mismatch for ${code:02X}")
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
        bounds = ink_bounds(rows)
        if bounds is None or bounds[0] != stock_left:
            raise SystemExit(f"Unexpected punctuation left bearing for ${code:02X}")
        left, right = bounds
        if validated_left_shift(code) != shift:
            raise SystemExit(f"Shared punctuation framing policy mismatch for ${code:02X}")
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
    bounds = ink_bounds(rows)
    if bounds != (3, 4):
        raise SystemExit("Unexpected colon stock geometry for $C5")
    if width_table[code - 0x80] != 7:
        raise SystemExit("Unexpected validated colon metric for $C5")
    if validated_left_shift(code) != 1:
        raise SystemExit("Shared colon framing policy mismatch for $C5")
    framed_left = bounds[0] - 1
    framed_right = bounds[1] - 1
    if framed_left != 2 or width_table[code - 0x80] - framed_right - 1 != 3:
        raise SystemExit("Validated colon does not preserve 2 px left / 3 px right framing")

    # Runtime-validated shared French charset. $D4-$E3 share a 1 px left bearing and
    # 6 px ink width; Œ/œ ($E4/$E5) are genuinely full-width.
    for code in range(0xD4, 0xE6):
        rows = font[(code - 0x80) * 12:(code - 0x80 + 1) * 12]
        bounds = ink_bounds(rows)
        expected_bounds = (0, 7) if code >= 0xE4 else (1, 6)
        expected_advance = 8 if code >= 0xE4 else 7
        expected_shift = 0 if code >= 0xE4 else 1
        if validated_left_shift(code) != expected_shift:
            raise SystemExit(f"Shared French framing policy mismatch for ${code:02X}")
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
        bounds = ink_bounds(rows)
        if bounds is None:
            continue
        expected = min(8, bounds[1] + 2)
        if width_table[code - 0x80] != expected:
            raise SystemExit(f"Unexpected conservative metric for ${code:02X}")

    # The private-buffer renderer has 38 logical slots; physical output remains 32 cells, and every generated advance must remain in the
    # 1..8 px range expected by the generic physical-cell snapshot helper.
    if len(width_table) != 128 or not all(1 <= width <= 8 for width in width_table):
        raise SystemExit("Unexpected dialogue width-table bounds")


def build(base: bytes) -> bytes:
    validate_base_rom(base)
    width_table = make_width_table(base)
    right_edge_table = make_right_edge_table(base)
    for offset, signature, name in (
        (RENDER_ENTRY_FILE, RENDER_ENTRY_SIGNATURE, "renderer entry"),
        (CHAR_START_FILE, CHAR_START_SIGNATURE, "character start"),
        (FONT_ROW_FILE, FONT_ROW_SIGNATURE, "font-row load"),
        (CHAR_END_FILE, CHAR_END_SIGNATURE, "character end"),
        (OUTLINE_POST_FILE, OUTLINE_POST_SIGNATURE, "post-outline state"),
        (PARSER_FETCH_FILE, PARSER_FETCH_SIGNATURE, "parser source fetch"),
    ):
        if base[offset:offset + len(signature)] != signature:
            raise SystemExit(f"Unexpected clean-US {name} signature")

    validate_metrics(base, width_table)
    if len(right_edge_table) != 128 or any(edge != 0xFF and edge > 7 for edge in right_edge_table):
        raise SystemExit("Unexpected dialogue framed-right-edge table")
    validate_helper_layout()
    validate_shared_text_buffer_stock(base)
    validate_shared_framing_stock(base)
    validate_shared_compositor_stock(base)
    validate_shared_row_renderer_stock(base)
    validate_shared_outline_stock(base)
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
    rom[PARSER_FETCH_FILE:PARSER_FETCH_FILE + len(PARSER_FETCH_HOOK)] = PARSER_FETCH_HOOK
    install_shared_text_buffer(rom)
    install_shared_framing(rom)
    install_shared_compositor(rom)
    install_shared_row_renderer(rom)
    install_shared_outline(rom)
    enable_dialogue_private_buffer(rom)

    for offset, payload in (
        (ENTRY_HELPER_FILE, ENTRY_HELPER),
        (CHAR_START_HELPER_FILE, CHAR_START_HELPER),
        (CHAR_END_HELPER_FILE, CHAR_END_HELPER),
        (FONT_ROW_HELPER_FILE, FONT_ROW_HELPER),
        (WIDTH_TABLE_FILE, width_table),
        (OUTLINE_POST_HELPER_FILE, OUTLINE_POST_HELPER),
        (CHUNK_COMMIT_HELPER_FILE, CHUNK_COMMIT_HELPER),
        (CHUNK_CELLS_SNAPSHOT_FILE, CHUNK_CELLS_SNAPSHOT_HELPER),
        (EVENT_RENDER_SCOPE_HELPER_FILE, EVENT_RENDER_SCOPE_HELPER),
        (PARSER_FETCH_HELPER_FILE, PARSER_FETCH_HELPER),
        (WRAP_GLYPH_HELPER_FILE, WRAP_GLYPH_HELPER),
        (RIGHT_EDGE_TABLE_FILE, right_edge_table),
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
    print("Caller-gated $C9/$CA dialogue VWF with runtime-validated pixel-aware right-edge wrap")


if __name__ == "__main__":
    main()
