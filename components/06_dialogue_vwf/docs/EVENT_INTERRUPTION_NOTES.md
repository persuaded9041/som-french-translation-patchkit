# Dialogue VWF — event interruption / `Wait ... up!` investigation

This document preserves a **deferred** runtime investigation so it can be resumed
without repeating the same probes. None of the experimental code described here
is present in the clean component.

## Symptom

In event `$0106`, the first dialogue contains text equivalent to:

```text
... "Wait " -> event command $32 ... -> "up!" ...
```

The VWF shortens `Wait `, but the later `up!` continues to begin at essentially
the same absolute X position as the unpatched fixed-width ROM. The result is an
excessively large visual gap.

Important terminology: the word `Wait` describes what the dialogue is saying and
the event produces a pause-like effect, but the byte interrupting these two text
chunks is `$32`; it is **not** the intro's `$28` WAIT opcode. Component
`05_intro_vwf_french` therefore provides a useful analogy but not the same event
path.

The surrounding text renders correctly, so this is not evidence against the
continuous pixel cursor, merge/spill compositor, or calibrated glyph metrics.
It is specifically a text-resume / event-boundary problem.

## Established observations

- Changing the normal space metric from 4 px to 1 px moved the first part of the
  line but did not make `up!` follow the compressed VWF width. This argues
  against hidden ordinary `$80` spaces being the cause of the gap.
- Preserving the private bitmap/pixel cursor across the interruption produced no
  visible change. The absolute origin of the resumed chunk is controlled by
  stock state outside that private compositor state.
- Directly mutating stock progression/tile state is dangerous: several probes
  corrupted or truncated text even when the arithmetic looked plausible.

## Earlier rejected probes

### `$A1CE` synchronization

A renderer-end diagnostic synchronized `$A1CE` to a cell count derived from the
VWF cursor.

Runtime result: **no visible effect** on the gap.

A later renderer-end variant was also ineffective. `$A1CE` alone is therefore
not sufficient to control the resume X coordinate in this event.

### `$32` bridge at `$C0:13A3`

Adding event-resume logic to the progression hook caused serious regressions in
the `$CA` post-new-game intro. Saving/restoring registers did not make the probe
safe.

Keep `$C0:13A3` as the validated stock-equivalent
`INC $A181 / INC $A1D0` trampoline in clean builds.

### `$A17C` probe

An early probe treated `$A17C` as a possible horizontal coordinate. It did not
improve the symptom. Later static inspection made it clear that `$A17C/$A17D/
$A17E` form coupled text/tile placement state, so interpreting one byte in
isolation was too simplistic.

### `$A181` decrement probe

A test decremented `$A181` on resumed `$C9` rendering to see whether it directly
set the chunk origin.

Runtime result: **all dialogue characters became glitched**. Do not use `$A181`
as a simple horizontal correction value.

## Reverse-engineering reference: Secret of Mana: Relocalized

The investigation then used the supplied unheadered IPS for **Secret of Mana:
Relocalized v1.7** as a comparison/reference:

<https://www.romhacking.net/hacks/4324/>

This is a reverse-engineering reference only; no Relocalized ROM or copyrighted
commercial ROM data is stored in this project.

### Relevant Relocalized hook

In the supplied v1.7 IPS, the stock area around `$C0:13A0` is replaced so that
execution enters a long helper at `$E0:2300` (`JSL $E0:2300`), then continues
with the logical progression around `$A1D0`.

Static inspection of `$E0:2300` shows that Relocalized does **not** merely apply a
one-time correction after an interruption. It consumes private renderer state
around `$98:989A/$989C`, calls its own helper around `$E0:2323` zero/one/multiple
times as required, finally increments `$A181`, clears its private state and
returns.

The helper around `$E0:2323` in turn manipulates the coupled stock state
`$A17C/$A17D/$A17E` through additional renderer-specific logic. This is the key
lesson: Relocalized's resume behavior is a consequence of a renderer and
progression system designed together, not a standalone "subtract N cells at
WAIT" patch.

### What *not* to copy from that observation

A first interpretation assumed the Relocalized hook simply called stock physical
progression fewer times according to `floor(pixel_width / 8)`. That model was
incomplete. Relocalized's private counters are produced/consumed by its own VWF
pipeline, so transplanting only the apparent progression effect into component
06 desynchronizes state.

## Relocalized-inspired probes and runtime results

### Direct `$A17D/$A17E` correction

A diagnostic subtracted two columns from `$A17D` and the corresponding amount
from `$A17E`, based on `Wait ` being 26 px in the calibrated VWF versus 40 px in
stock fixed width.

Runtime result: **dialogue display became broken/truncated**.

Conclusion: `$A17D` and `$A17E` are coupled to tile preparation/allocation and
must not be rewound blindly.

### Reduced physical progression / `$13FD`-style emulation

Another diagnostic attempted to keep an 0..7 VWF remainder and perform stock
physical progression only when accumulated glyph advances crossed 8 px. For
`Wait `, 26 px would imply three cell crossings plus a 2 px remainder instead
of five stock character cells.

Runtime result: **dialogue display became incorrect/truncated**.

Conclusion: the stock progression routine maintains more state than a simple
horizontal cell counter, and Relocalized's private renderer state cannot be
reproduced by skipping calls in component 06.

### `$A17D` only + 2 px remainder

A final narrow probe left `$A17E` untouched, moved only `$A17D` by two columns,
and initialized a 2 px private remainder for the resumed chunk.

Runtime result: the text was no longer corrupted, but **no visible change in the
position of `up!` was observed**.

Conclusion: `$A17D` by itself is not the missing absolute resume origin either.

## Current conclusion

The event command splits the text into chunks, and the resumed chunk receives an
absolute/stock-derived placement that is not controlled solely by component
06's private pixel cursor. The responsible state has **not yet been isolated**.

The important negative results are now well established:

- ordinary spaces are not the explanation;
- preserving only the private bitmap/cursor is insufficient;
- `$A1CE`, `$A181`, `$A17C` or `$A17D` are not safe standalone fixes;
- rewinding `$A17D/$A17E` together breaks tile state;
- skipping stock physical progression according to VWF width also breaks state;
- Relocalized demonstrates that correct event-resume behavior is integrated with
  its wider VWF renderer/progression architecture.

The clean checkpoint therefore leaves the stock-position gap unchanged rather
than carrying speculative code.

## Recommended way to resume the research

Prefer tracing over another patch-by-guess:

1. break on event `$0106` around the `Wait ` / `$32` / `up!` boundary;
2. record **all** text-placement state immediately before the interruption and
   immediately before the first resumed glyph;
3. trace the writes that rebuild/advance `$A17C-$A17E`, `$A181`, `$A1CE`,
   `$A1D0`, destination tile state and any window-origin state discovered on the
   path;
4. compare clean-ROM, component-06 and Relocalized execution at equivalent
   boundaries rather than comparing only static values;
5. identify which state actually establishes the resumed chunk's absolute X;
6. only then design a generic bridge based on renderer state, never on the
   literal string `Wait ` or `up!`.

Relocalized is most useful here as an architectural trace reference: reproduce
its *state relationships*, not isolated arithmetic from one helper.
