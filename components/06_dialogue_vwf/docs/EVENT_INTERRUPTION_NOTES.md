# Dialogue VWF — event interruption / `Wait up!` investigation

This note preserves a deferred runtime investigation. None of the diagnostics described here are present in the current component source.

## Symptom

With the continuous `$C9` VWF renderer working correctly for the temporary `space=4`, `i=3`, `l=3`, `other=8` metrics, one dialogue still displays a conspicuously large gap in `Wait   up!`.

A screenshot comparison against the clean US ROM showed that `up!` begins at the same horizontal position in both versions. The VWF makes the preceding `Wait ` shorter, but the resumed `up!` stays at the stock fixed-width X coordinate.

This strongly separates the symptom from the general cumulative-cursor / cross-tile compositor, which renders the surrounding dialogue correctly.

## Script observation

The affected dialogue was traced to event `$0106`, around bank `$C9` / `$C9:28A0` in the investigated ROM. The relevant stream is effectively:

`... " Wait " -> event command $32 -> "up!" ...`

The interruption is therefore associated with event command `$32`, not an inline horizontal-position command identified in the text itself.

An earlier hypothesis focused on opcode `$28` (`WAIT`) because component `05_intro_vwf_french` already has a validated VWF resume case around an intro WAIT. That analogy was useful, but it did not explain this dialogue.

## Experiments and results

### `$A1CE` synchronization

A renderer-end diagnostic tried to synchronize `$A1CE` to `ceil(pixel_cursor / 8)` before the event interruption.

Runtime result: **no visible change** to the gap.

Conclusion: `$A1CE` is not sufficient to control the resumed horizontal position here. Static inspection also suggests it behaves primarily as a prepared-character / line-state counter in this part of the pipeline rather than the final pixel destination.

### Event `$32` handling in `$C0:13A3`

A diagnostic added `$32` continuation logic to the progression hook at `$C0:13A3`.

Runtime result: the `$CA` post-new-game intro glitched badly.

Saving/restoring A/X/P did not remove the regression. The progression hook is therefore treated as timing-sensitive: keep it as the already validated stock-equivalent `INC $A181 / INC $A1D0` trampoline unless a future investigation has very strong evidence and explicit runtime instrumentation.

### Event `$32` handling at renderer end

Moving the `$32` experiment to the existing renderer-end hook removed the intro regression, proving that this hook location is much safer for dialogue-only experiments.

However, synchronizing `$A1CE` there still had **no effect** on `Wait   up!`.

### `$A17C` probe

`$A17C` was considered as a possible stock horizontal/cell coordinate because nearby stock code initializes and advances it in a way compatible with cell progression. A probe intended to alter the resumed position did not improve the symptom.

This was not sufficient to prove a complete model of `$A17C`; it only means the attempted intervention was not a useful correction.

## Current conclusion

Do not special-case the word `Wait`, `up!`, `i`, or `l`.

The most plausible remaining explanation is that event command `$32` splits the text into separate rendering chunks and the engine resumes the later chunk from stock event/window state that is independent of the private VWF `pixel_cursor`. The exact state responsible has not yet been identified.

The current clean checkpoint intentionally leaves the original gap unchanged rather than carrying speculative resume code.

## Recommended future investigation

If this issue is resumed later, prefer runtime tracing over further blind patches:

1. break on the event `$0106` sequence around `$C9:28A0`;
2. record the final horizontal-related state after rendering `Wait `;
3. step through command `$32` until the first character of `up!` is prepared;
4. watch writes to `$A17C`, `$A176`, `$A196`, `$A1CE`, the destination `Y`, and any related window/text state discovered on that path;
5. compare those values between the clean ROM and the VWF ROM;
6. only after identifying the actual resume coordinate, design a generic event-boundary bridge.

A correct future fix should be based on the event/text pipeline, not on literal strings or individual letters.
