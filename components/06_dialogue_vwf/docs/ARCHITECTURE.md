# Dialogue VWF architecture

This document is the authoritative technical description of component 06's
runtime-validated event-dialogue renderer. Event-interruption control flow is
detailed separately in `EVENT_INTERRUPTION_NOTES.md`; ROM/WRAM ownership is in
`MEMORY_MAP.md`.

## Event-render scope

The stock renderer at `$C0:1664` is shared. In the clean USA ROM its three direct
`JSR $1664` callers are:

```text
$C0:1150 -> return address $1152 : event engine
$C0:235C -> return address $235E : GAME SELECT
$C0:CB3C -> return address $CB3E : other non-event path
```

A bank check alone is unsafe because `$001D03` is shared state and may still hold
`$CA` while GAME SELECT renders. `$A15D == $01` is also not a unique dialogue
marker.

At `$C0:167D`, before the stock renderer has pushed local values, component 06
reads the caller's 16-bit return address at `1,S`. It tags the invocation as VWF
only when the stacked return is `$1152` and the live event bank is `$C9` or `$CA`.
A private flag at `$7E:9385` carries that decision through the internal renderer
hooks. Every invocation reaching component 06 clears the flag before making the
decision, so non-event calls always fall back to stock behavior.

This is runtime-validated for both sides of the boundary: `$CA` story dialogue
uses the VWF and GAME SELECT remains fixed-width.

Component 05 hooks `$C0:1664` itself for translated intro event `$0400`. When its
bank/pointer gate matches, it renders the intro and exits to `$C0:16B7`; therefore
component 06's entry at `$C0:167D` is never reached for that event. For other
`$CA` events component 05 falls back to stock `$C0:1669`, allowing component 06
to perform the caller-based test normally.

## Stock glyph-selection path

Component 06 keeps `$C0:168A-$C0:16B0` intact. Stock code remains responsible for:

1. decoded character code to glyph index;
2. `$80`-based index normalization;
3. multiply-by-12 glyph addressing;
4. reading the 12-row glyph from `$D2:DC00`.

Component 06 changes placement/composition of the already selected glyph row.

## Continuous pixel cursor

For a tagged event-render invocation:

- `pixel_cursor` is continuous in pixels;
- destination `Y = floor(pixel_cursor / 8) * 12`;
- each row is composed at `pixel_cursor & 7`;
- pixels are ORed into the current 12-byte cell and spilled into the next cell;
- the full `$7E:9000-$917F` bitmap is cleared before rendering because adjacent
  glyphs can share cells;
- no forced 8 px realignment is used between glyphs.

The per-character start helper is fixed at `$ED:7180`; the punctuation dispatcher
keeps its fixed trampoline at `$ED:71F4`. The builder asserts the latter layout.

## Width table and framing

The 128-entry table at `$ED:7200-$ED:727F` contains advances for decoded codes
`$80-$FF`. The lookup zero-extends the glyph index through `$7E:938A-$938B` while
keeping accumulator A in 8-bit mode, which preserves the stock row-loop contract.

Runtime-validated advances span 3 through 8 px. Lowercase, uppercase, supported
punctuation, and the shared French `$D4-$E5` glyphs use the framing/metrics listed
in the component README. `$CD` remains on the generic conservative path.

Lowercase framing is selected at `$ED:71B0-$71E7`; post-lowercase dispatch starts
at `$ED:71E8`; the extended uppercase/punctuation/French selector is at
`$ED:72F0-$733F`.

## Outline repair

The stock outline routine `JSR $162C` remains untouched. Component 06 hooks after
it at `$C0:1168` and uses `$ED:7280-$72E9` to restore outline pixels lost where a
VWF glyph touches an 8-pixel cell boundary.

This post-outline helper is still deliberately limited to bank `$C9`, matching
the scope in which it was runtime-validated. The core renderer now covers tagged
`$C9/$CA` event invocations; extending this secondary repair to `$CA` must preserve
component 05's intro isolation and requires its own runtime validation.

## Interrupted chunks and physical progression

Stock dialogue uses `$A1CE` first as a decoded-character count and later as the
number of physical 8-pixel columns to transfer/allocate. Those quantities are
equivalent in the original fixed-width renderer but not in a VWF.

The generic path therefore converts interrupted, non-line-break chunks before
stock progression:

1. tagged renderer entry saves `$A1CE & $7F` in `$7E:938E` and clears `$7E:938F`;
2. the fixed 32-slot renderer continues normally;
3. at the start of the first padded slot, when `X == saved_decoded_count`,
   `$ED:7380` captures `ceil(useful_pixel_width / 8)` in `$7E:938F`;
4. at renderer completion, `$ED:7340` replaces the low count in `$A1CE` with
   that physical-cell count only when the stock line-break bit is clear;
5. normal stock transfer/allocation then runs unchanged.

The snapshot is based on the actual decoded buffer, so DTE expansion and dynamic
name insertion are included automatically. No event address, movement opcode, or
WAIT opcode is recognized by component 06.

A 32-character chunk has no padded slot. Final commit therefore invokes the same
snapshot helper once with `X=32`; an exact 256 px 8-bit cursor wrap is mapped to
32 physical cells.

The stock progression code at `$C0:13A3` is intentionally unmodified: all
VWF-specific interrupted-chunk correction is complete before it runs.

## Invariants

When changing this component, preserve these constraints unless a new runtime
investigation proves otherwise:

- keep `$C0:168A-$C0:16B0` intact;
- keep the stock outline call at `$C0:1165` intact;
- identify event text from the renderer caller, not from `$001D03` or `$A15D`
  alone;
- keep GAME SELECT and the `$C0:CB3C` caller on the stock renderer path;
- preserve component 05's early ownership of translated intro event `$0400`;
- keep A in 8-bit mode through the width-table lookup and stock row loop;
- resolve generated relative branches from labels rather than hard-coded offsets;
- do not reintroduce a progression hook for interrupted chunks;
- do not special-case event addresses or WAIT/movement opcodes;
- audit the `$C9`-only outline repair separately before extending it to `$CA`.
