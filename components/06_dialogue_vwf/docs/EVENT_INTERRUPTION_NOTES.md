# Dialogue VWF — event interruption

This document records the stock control flow that explains why proportional text
must convert decoded character counts to physical cell counts before an event
interruption resumes the same dialogue window.

## Reference event

Event `$0106` contains two useful runtime-validation boundaries. Around the second
one:

```text
C9:28CB  80 B1 81 89 94 80    " Wait "
C9:28D1  32 04 C8             movement/action command
C9:28D4  08                    wait for current actions
C9:28D5  95 90 C8             "up!"
```

`$32` is not the WAIT. It schedules movement/action. `$08` later waits until the
current actions finish.

The earlier `Guys!` boundary also includes dynamic text in the same parser
invocation: `$57 00` inserts the current hero name and `$C5` adds `:` before the
literal `Hey! ` bytes. With a hero named `A`, the decoded chunk is therefore
`"A:Hey! "`, not merely `"Hey! "`.

## Stock hand-off

The C1 event interpreter hands text to the C0 text engine through
`$001D01-$001D03`. The C0 parser fills `$7E:A1A4` and increments `$A1CE` for each
decoded character.

When the parser reaches an ordinary event command such as `$32`, it stops before
that command and writes its address back to `$001D01`. For the `" Wait "` chunk:

```text
$001D03 = $C9
$001D01 = $28D1
$A1CE   = $06
```

The text engine then renders and commits the chunk. C1 resumes at `$32`, executes
the movement, processes `$08`, and eventually starts a new text-engine invocation
at `up!` in the same dialogue window.

## Why fixed-width progression fails for VWF

Stock progression transfers/allocates one 8-pixel column per iteration and uses
`$A1CE` to decide how many iterations belong to the chunk. This works in the
original renderer because:

```text
decoded character count == physical 8-pixel column count
```

Component 06 composes glyphs at a cumulative pixel cursor, so the two quantities
differ. With current validated metrics:

```text
" Wait "   = 30 px -> 4 physical cells
"A:Hey! "  = 44 px -> 6 physical cells
```

If stock progression receives the decoded counts (6 and 7 respectively), the
persistent tile/window position advances too far before the next text invocation.

The correction must therefore happen before progression. Rewinding placement
after transfer/allocation would separate already-written graphics from the
associated tilemap state.

## Why the final `$9382` cursor cannot be used directly

The stock renderer still processes 32 slots. Unused decoded-buffer slots contain
`$80` spaces, so the private pixel cursor continues advancing after useful text.
For `" Wait "`, the useful width is 30 px but the remaining 26 padded spaces add
104 px.

The generic solution saves the real decoded count at renderer entry and captures
the cursor exactly when the slot index first reaches that count, before padding
can affect the saved width.

## Generic runtime-validated solution

Component 06 uses no event-specific address or opcode checks:

```text
renderer entry:
    $938E = $A1CE & $7F
    $938F = 0

first slot where X == $938E:
    $938F = ceil(useful_pixel_cursor / 8)

renderer completion:
    if bank == $C9 and line-break bit is clear:
        $A1CE = $938F
```

Normal line-break chunks retain their stock progression count. Counts outside the
32-slot renderer contract also fall back to stock behavior. A full 32-character /
256-pixel chunk is handled explicitly when the 8-bit pixel cursor wraps to zero.

Runtime validation in event `$0106` confirms that the same generic mechanism:

- aligns `A:Hey! Guys!` correctly at 44 px -> 6 cells;
- aligns `Wait up!` correctly at 30 px -> 4 cells;
- preserves the movement and `$08` wait timing;
- preserves the surrounding dialogue and line-break behavior in the tested scene.

Component 05 uses the same architectural principle for its intro-specific `$28`
WAIT: convert VWF pixel width to physical cells after rendering and before stock
progression. Its parser/rendering path is different, so the implementation is not
shared.
