# Dialogue VWF architecture

This document is the authoritative technical description of the runtime-validated
`$C9` dialogue renderer. Event-interruption control flow is detailed separately in
`EVENT_INTERRUPTION_NOTES.md`; ROM/WRAM ownership is in `MEMORY_MAP.md`.

## Scope

Component 06 is active only when `$001D03 == $C9`. Outside that bank every hook
falls back to the original renderer behavior.

The component keeps the stock block `$C0:168A-$C0:16B0` intact. Stock code remains
responsible for:

1. decoded character code to glyph index;
2. `$80`-based index normalization;
3. multiply-by-12 glyph addressing;
4. reading the 12-row glyph from `$D2:DC00`.

Component 06 changes placement/composition of the already selected glyph row.

## Continuous pixel cursor

For `$C9` text:

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

## Interrupted chunks and physical progression

Stock dialogue uses `$A1CE` first as a decoded-character count and later as the
number of physical 8-pixel columns to transfer/allocate. Those quantities are
equivalent in the original fixed-width renderer but not in a VWF.

The generic runtime-validated path therefore converts only interrupted,
non-line-break `$C9` chunks before stock progression:

1. renderer entry saves `$A1CE & $7F` in `$7E:938E` and clears `$7E:938F`;
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

The stock progression code at `$C0:13A3` is no longer hooked. This is intentional:
all VWF-specific correction is complete before the original progression path
runs.

## Invariants

When changing this component, preserve these constraints unless a new runtime
investigation proves otherwise:

- keep `$C0:168A-$C0:16B0` intact;
- keep the stock outline call at `$C0:1165` intact;
- keep A in 8-bit mode through the width-table lookup and stock row loop;
- resolve generated relative branches from labels rather than hard-coded offsets;
- do not reintroduce a progression hook for interrupted chunks;
- do not special-case event addresses or WAIT/movement opcodes;
- audit WRAM ownership before broadening scope beyond `$C9`.
