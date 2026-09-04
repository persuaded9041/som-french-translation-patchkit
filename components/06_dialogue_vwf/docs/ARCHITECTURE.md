# Dialogue VWF architecture

This document records the runtime-validated architecture and the invariants that
must be preserved while component `06_dialogue_vwf` is still scoped to `$C9`.
Historical event-resume experiments are intentionally kept out of this file; see
`EVENT_INTERRUPTION_NOTES.md`.

## Renderer contract

Keep the stock block `$C0:168A-$C0:16B0` intact. It remains responsible for:

1. decoded character code to glyph index;
2. `$80`-based index normalization;
3. multiply-by-12 addressing;
4. reading the 12-row glyph from `$D2:DC00`.

Component 06 only changes where the already selected row is composed.

For `$C9` text:

- `pixel_cursor` is continuous in pixels;
- destination `Y = floor(pixel_cursor / 8) * 12`;
- each row is composed at `pixel_cursor & 7`;
- pixels are merged into the current 12-byte cell and spilled into the next one;
- no forced 8 px realignment is allowed.

The per-character start helper must stay at **`$ED:7180`**. A previous move to
`$ED:7190` caused almost all dialogue to disappear.

## Width table

The 128-entry table at `$ED:7200-$ED:727F` contains advances for decoded codes
`$80-$FF`.

The table index is zero-extended through `$7E:938A-$938B` while accumulator A
stays in its existing width. This detail is runtime-critical:

- using X without explicitly clearing its high byte caused selective glyph loss;
- using `REP/SEP` in `dialogue_char_end` disturbed the hidden B byte of A and
  caused severe rendering loss.

Runtime tests have exercised drawn advances of 3, 4, 5, 6, 7 and 8 px.

## Framing selection

Lowercase framing is selected at `$ED:71B0-$ED:71E7`. The punctuation dispatch
starts at `$ED:71E8`.

The punctuation batch-2 `JML` trampoline is pinned at **`$ED:71F4`**. The builder
asserts this exact address. A previous one-byte shortening moved it to
`$ED:71F3` while dispatch still entered at `$ED:71F4`, preventing the ROM from
starting.

Always generate 65816 relative branches from labels/resolution logic. A stale
hard-coded `BNE` once landed in the middle of `LDA $A1A4,X / INX` and broke GAME
SELECT.

The extended selector at `$ED:72F0-$ED:733F` handles validated uppercase,
punctuation and French framing while leaving `$B5-$BE` and `$CD-$D3` on the
generic path unless explicitly handled elsewhere.

## Outline repair

The stock outline routine `JSR $162C` must execute normally. The validated repair
hooks **after** it at `$C0:1168` and uses `$ED:7280-$ED:72E9`.

Do not hook `$C0:1165`: that replaces the stock outline call and removes most of
the black contour.

## Progression hook

`$C0:13A3` remains a stock-equivalent trampoline:

```text
INC $A181
INC $A1D0
```

It currently contains no event-resume logic. Attempts to use it as an ad-hoc
bridge for interrupted text have caused regressions and belong only in the event
investigation notes.

## Rejected renderer approaches

Do not reintroduce these without a new, evidence-based investigation:

- relocating the entire stock renderer;
- replacing the stock glyph lookup;
- custom-to-stock handoff in the middle of a line;
- forced tile-boundary realignment;
- the old generic `left_shift[128]` implementation;
- treating an old `i=7/l=7` crash as a renderer limit (a clean rebuild worked);
- direct manipulation of stock progression/tile state merely to repair the
  event-interruption gap.

The current architecture was chosen because it preserves the stock glyph path
while giving the compositor an independent cumulative pixel coordinate.
