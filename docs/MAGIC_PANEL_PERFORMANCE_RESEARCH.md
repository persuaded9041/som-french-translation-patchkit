# Magic lower-panel VWF performance research — 2026-09-20

## Baseline

This investigation starts from the runtime-validated general VWF performance
baseline:

- Ring true decoded-count rendering (Stage 1);
- generic row-scope inline fast path (Stage 2A);
- cached glyph phase/Y fast path (Stage 2B);
- safe packed/unrolled generic compositor (Stage 2C-R1; original 2C rejected);
- bounded post-outline repair (Stage 3A).

Those general optimizations are frozen for this investigation.  The target here
is only the dedicated `Niv. magies` lower-panel 3x480px renderer at `$ED:8E00`.
The localized content, stock availability/ID capture, six-pass menu lifecycle,
DMA timing and direct `$C7:4560/$4C90` primitives remain unchanged.

## Root cause found

The stock lower panel is six physical 30-cell passes:

- row 0 left / row 0 right;
- row 1 left / row 1 right;
- row 2 left / row 2 right.

The promoted full-row renderer reconstructs a complete 60-cell / 480px logical
row for each physical pass, then slices either cells 0..29 or cells 30..59.
Therefore every visible French sentence is currently VWF-rasterized twice.

For the current 42 localization-owned records there are 2214 glyphs total.  The
baseline rasterizes 4428 glyphs across left+right passes before stock conversion.
This duplicate rasterization is the dominant avoidable cost found so far.

## Performance Stage 1 — runtime-validated — skip irrelevant left-side raster work on right pass

This runtime-validated stage deliberately keeps the stock six-pass flow and does not cache a
bitmap across passes yet.

On the left/even pass, behavior is byte-for-byte algorithmically unchanged: the
complete logical row is rasterized.

On the right/odd pass, the source string and 16-bit logical cursor are still
walked from the beginning, preserving exact positioning, but the expensive
12-row glyph compositor is skipped while the cursor is below 224 px.  Rastering
starts two cells before the actual 240px split.

The 16px safety margin is conservative.  The validated compositor can affect at
most the current bitmap cell plus one spill cell.  A glyph whose cursor is below
224 px therefore cannot contribute to source cell 30 (the first cell copied into
the right physical pass).  Starting at 224 px preserves two full cells of margin
before the 240px split.

With the current 42 records:

- right-pass raster glyphs skipped: 1560 / 2214 (70.46%);
- right-pass glyphs still rasterized: 654;
- total duplicate glyph raster work: 4428 -> 2868 glyphs;
- reduction in glyph raster calls across both halves: 35.23%.

Short rows whose final width never reaches the right half correctly rasterize no
glyphs on the right pass; their copied right-half bitmap remains blank.

## Scope / non-goals

This Stage 1 implementation does **not** change:

- the 42 `Nom : description` records at `$ED:9200`;
- captured stock IDs / unlock gating;
- the 480px logical cursor or VWF metrics;
- the left pass;
- the six stock waits / converter / DMA / tail lifecycle;
- the right-half copy geometry;
- any Ring/dialogue/Status/skill-row VWF path.

Stage 2 below supersedes that remaining duplicate-raster limitation by reusing
the already-converted non-DMA half produced during the left pass, while still
preserving all six stock DMA submissions.


## Performance Stage 2 — runtime-validated — reuse the stock converter's non-DMA half

Stage 1 proved that duplicate right-pass rasterization is a real performance
cost.  Stage 2 removes that duplicate render entirely and also avoids the second
stock bitmap conversion for each valid visible row.

The key stock property is stronger than initially assumed: `$C0:2366` consumes
all **64** 12-byte source cells at `$7E:9000-$92FF` and produces 64 packed 4bpp
cells at `$7E:9400-$9BFF`.  The magic-panel DMA size remains `$A191=$03C0`, so
only the first **30** packed cells / 960 bytes are submitted on each physical
pass.

Because the split is exactly 30 cells and therefore parity-preserving:

- source cells 0..29 pack to `$9400-$97BF`;
- source cells 30..59 pack to `$97C0-$9B7F`;
- source cells 60..63 occupy the final non-DMA tail.

On a valid left pass Stage 2 therefore no longer clears logical cells 30..63.
The unchanged stock converter packs the complete 480px row.  DMA still reads
only `$9400-$97BF`, so the visible left result is unchanged, while the already
converted right half survives at `$97C0-$9B7F`.

The stock lifecycle between the paired passes does not write this output range:
`$C0:1664` rebuilds `$9000`, `$C0:28FF` only waits, and `$C0:23BA/$25CC` only
program DMA registers.  Thus the right-half packed data remains valid.

On the following valid right pass `$ED:8E00` copies the 960 cached bytes
`$97C0-$9B7F -> $9400-$97BF`, restores the observable stock converter exit state
(`X=$0800`, `Y=$0300`, `A8=$00`, carry clear), then jumps to the stock converter
RTS at `$C0:2386`.  The surrounding stock wait/DMA/tail sequence is untouched.

This means, for a fully visible three-row panel:

- long-row VWF rasterizations: **6 -> 3** (exactly one per sentence);
- full `$C0:2366` conversions: **6 -> 3**;
- right passes become one 960-byte packed copy plus the unchanged stock DMA;
- the six physical stock DMA submissions and their destinations remain exactly
  unchanged.

Static proof performed before runtime validation:

- 100 randomized 64-cell bitmaps confirm that the first 960 packed bytes are
  independent of source cells 30..63;
- 100 randomized bitmaps confirm packed full-row bytes for cells 30..59 are
  byte-identical to a fresh conversion after shifting those 30 cells down to
  source cells 0..29;
- the reconstructed converter exits at `X=$0800`, `Y=$0300`; the fast path
  explicitly reproduces those live register values before returning;
- no new WRAM or ROM data allocation is introduced: `$97C0-$9B7F` is merely
  reused between the already-paired stock passes.

Locked / non-emitted rows still take the conservative explicit blank path; no
unlock condition or captured ID logic changes.


## Validation state

- **Magic Stage 1:** runtime-validated by the user on 2026-09-20; retained as historical proof but superseded by Stage 2.
- **Magic Stage 2:** runtime-validated by the user on 2026-09-20 and promoted as the current lower-panel implementation.
- Performance work on this panel is frozen at Stage 2 for the current baseline.
