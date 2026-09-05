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

The parser initializer at `$C0:16B8` is also shared: event engine calls it from
`$C0:1149` (stacked return `$114B`) and GAME SELECT from `$C0:2359` (return
`$235B`). Components 05 and 06 now install one byte-identical private-buffer
bridge. Component 06 enables dialogue mode only for `$114B` plus live bank
`$C9/$CA`; GAME SELECT therefore keeps its stock `$A1A4` parser buffer even if
shared global bank state is stale. This 38-character parser-capacity extension is runtime-validated.

Component 05 hooks `$C0:1664` itself for translated intro event `$0400`. When its
bank/pointer gate matches, it renders the intro and exits to `$C0:16B7`; therefore
component 06's entry at `$C0:167D` is never reached for that event. For other
`$CA` events component 05 falls back to stock `$C0:1669`, allowing component 06
to perform the caller-based test normally.

## Private decoded buffer and stock glyph-selection path

The stock decoded buffer cannot be enlarged in place: `$A1C5/$A1C6` are active
parser state and `$A1C7` is renderer scratch. Dialogue mode therefore decodes to
the same 44-byte private buffer `$7E:9390-$93BB` already validated by component
05. A fresh line gets 39 parser units (38 glyphs + following control); on a
partially used line the stock remaining-line capacity is increased by six and
capped at 39.

Component 06 still keeps `$C0:168A-$C0:16B0` intact. The per-character hook now
loads the decoded byte from `$9390,X` for tagged dialogue invocations before
entering that untouched stock code. Stock code remains responsible for:

1. decoded character code to glyph index;
2. `$80`-based index normalization;
3. multiply-by-12 glyph addressing;
4. reading the 12-row glyph from `$D2:DC00`.

Component 06 changes placement/composition of the already selected glyph row.

## Shared row compositor

The runtime-validated shared-compositor refactor moves only the renderer-neutral 8x12 row
composition primitive into `shared/vwf_compositor.py`. Both components install
the same 63 bytes at `$C7:4C90`. Input is an already-selected/already-framed row
in 8-bit A, destination row offset in Y, and the cumulative cursor at `$9382`;
the helper merges the current-cell half and writes right-side spill to the next
12-byte tile cell.

For component 06 those 63 bytes are byte-for-byte the previously runtime-validated
composition sequence formerly embedded in `$ED:7100`. The framing/advance policy
lives in `shared/vwf_metrics.py`, and the common runtime selector lives at
`$C7:44C0-$4557`. The stock-font/framing path is runtime-validated in component
05.

The runtime-validated shared row renderer adds a 13-byte helper at `$C7:4560`: it
reads `$D2:DC00,X`, applies the shared framing selector, then calls the shared
compositor. Component 05 calls it directly from its 12-row loop. Component 06's
`$ED:7100` wrapper first checks the already validated renderer-active tag and
then calls the same helper; non-event callers replay the stock font-row load.
The former duplicate `$ED:71B0/$71E8/$72F0` framing payloads are no longer
installed.

## Continuous pixel cursor

For a tagged event-render invocation:

- `pixel_cursor` is continuous in pixels;
- destination `Y = floor(pixel_cursor / 8) * 12`;
- each row is composed at `pixel_cursor & 7`;
- pixels are ORed into the current 12-byte cell and spilled into the next cell;
- the full `$7E:9000-$917F` bitmap is cleared before rendering because adjacent
  glyphs can share cells;
- no forced 8 px realignment is used between glyphs.

The per-character start helper remains fixed at `$ED:7180`. The old `$ED:71F4`
punctuation trampoline is no longer part of the runtime path because framing is
now provided by the shared C7 selector bundle.

## Width table and framing

The 128-entry table at `$ED:7200-$ED:727F` contains advances for decoded codes
`$80-$FF`. The lookup zero-extends the glyph index through `$7E:938A-$938B` while
keeping accumulator A in 8-bit mode, which preserves the stock row-loop contract.

Runtime-validated advances span 3 through 8 px. Lowercase, uppercase, supported
punctuation, and the shared French `$D4-$E5` glyphs use the framing/metrics listed
in the component README. `$CD` remains on the generic conservative path.

Both components install the same selector bundle generated by
`shared/vwf_framing.py` at `$C7:44C0-$4557`. Component 06 reaches it through
the shared `$C7:4560` stock-row renderer; its former `$ED` selector copies are
retired in the runtime-validated shared-row checkpoint.

## Pixel-aware parser preflight

The shared 38-character parser capacity can exceed the 32-cell / 256-pixel
physical bitmap. Stock wrapping only counts remaining fixed-width cells, so the
extra six logical units can otherwise consume source glyphs after their visible
pixels no longer fit. Once consumed, those glyphs cannot be recovered by the
later physical-cell progression conversion.

Component 06 therefore replaces only the source fetch at `$C0:16EA-$16ED` with
a dialogue-mode preflight. Non-dialogue parser modes replay the exact stock
`LDA $0000,Y / INY`. In dialogue mode the helper derives the available pixel
budget from `($A16A-$A181)*8`, tracks cumulative validated VWF advances and tests
visible framed right edges before advancing `Y`. Direct glyphs and DTE pairs are
handled before source consumption; DTEs stay atomic and dynamic-name temporary
sources are not rewound.

On overflow, a safe ordinary-space checkpoint is preferred and discarded private
buffer slots are restored to `$80` padding before the stock `$C0:17B0` line-end
path is reused. Without such a checkpoint the line ends before the overflowing
token. The known early-game `You have a sword` clipping case is runtime-validated
as repaired by this mechanism.

This is a clipping-safety mechanism, not yet full typographic word wrapping. If a
word itself reaches the boundary with no usable preceding checkpoint, it may still
be split. Whole-word pre-wrap is intentionally deferred.

## Outline repair

The stock outline routine `JSR $162C` remains untouched. Component 06 hooks after
it at `$C0:1168` and uses `$ED:7280-$72E9` to restore outline pixels lost where a
VWF glyph touches an 8-pixel cell boundary.

The repair is runtime-validated on ordinary `$C9/$CA` dialogue. Eligibility
requires the exact component-06 renderer-active tag `$7E:9385 == $01`, which is
structurally narrower than a raw bank test: ordinary component-06 dialogue sets
exactly `$01`, inactive renderer calls leave `$00`, and component 05's
mutually-exclusive intro renderer uses the same byte only for validated glyph
advances `3..8`. Component 05's builder asserts that none of its emittable glyphs
can collide with tag value `$01`.

## Interrupted chunks and physical progression

Stock dialogue uses `$A1CE` first as a decoded-character count and later as the
number of physical 8-pixel columns to transfer/allocate. Those quantities are
equivalent in the original fixed-width renderer but not in a VWF.

The generic path therefore converts interrupted, non-line-break chunks before
stock progression:

1. tagged renderer entry saves `$A1CE & $7F` in `$7E:938E` and clears `$7E:938F`;
2. the tagged private-buffer renderer continues through 38 logical slots;
3. at the start of the first padded slot, when `X == saved_decoded_count`,
   `$ED:7380` captures `ceil(useful_pixel_width / 8)` in `$7E:938F`;
4. at renderer completion, `$ED:7340` replaces the low count in `$A1CE` with
   that physical-cell count only when the stock line-break bit is clear;
5. normal stock transfer/allocation then runs unchanged.

The snapshot is based on the actual decoded buffer, so DTE expansion and dynamic
name insertion are included automatically. No event address, movement opcode, or
WAIT opcode is recognized by component 06.

A full 38-character chunk has no padded slot. Final commit therefore invokes the
same snapshot helper once at `X=38`. An exact 256 px 8-bit cursor wrap is mapped
to 32 physical cells. Existing line-break chunks of 32 characters or fewer keep
the previously validated stock progression; only newly possible 33-38-character
line-break chunks are converted to physical cells to prevent a transfer request
above the 32-cell bitmap capacity.

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
- keep parser activation caller-gated at `$114B`; never use bank state alone for the shared `$C0:16B8` parser initializer;
- never extend the stock `$A1A4` decoded buffer into live `$A1C5+` state;
- keep A in 8-bit mode through the width-table lookup, shared row renderer/compositor and stock row loop;
- resolve generated relative branches from labels rather than hard-coded offsets;
- do not reintroduce a progression hook for interrupted chunks;
- do not special-case event addresses or WAIT/movement opcodes;
- keep the post-outline repair gated by exact component-06 tag `$9385 == $01`; do not replace it with a bank-only `$C9/$CA` test.
