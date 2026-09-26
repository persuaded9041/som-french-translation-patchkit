# intro_skip — validated hold-R introduction skip

`intro_skip` is the runtime-validated skip component for translated new-game
event `$0400`. It replaces the former legacy/experimental implementation.

## Final behavior

During the normal narrative portion of the French intro, hold **R continuously
for 120 normal-loop ticks**. Releasing R before the counter reaches zero cancels
the request completely; a later hold starts again from the full 120 ticks.
Separated short presses therefore do not accumulate.

When the hold completes, the skip is committed at an already validated safe
point:

- inside a live text carrier, the live parser cursor is redirected to the
  private tail at `$CA:FFC0`;
- during a stock timed `WAIT` (`$D0 == $82`), the normal-loop helper prepares
  the same tail and lets the untouched C1 `WAIT` handler expire naturally.

The tail closes the current text, resets to waterfall room `$0000`, balances the
intro `$CFF8` context, then jumps to stock event `$0106`:

```text
51 18 00 2A F8 11 06 00
```

The final Mode-7/flyover phase beginning at `$CA:0E82 = 1D 7F` is deliberately
outside the validated scope. The component is validated across the eight normal
narrative text/WAIT phases before that transition.

## Dependencies

The runtime proof was performed on the translated/VWF intro. The manifest only
requires `default_vwf_intro`; the runtime gate is self-contained and only arms
inside the translated `$0400` normal-intro window. This keeps the behavior in
the default aggregate without forcing the French intro payload into it.

Standalone component IPS files are still authored against the clean unheadered
USA ROM, as required by the patchkit; `requires` controls composition/rebuild
order.

## Validated architecture

Three hooks are used; there is **no NMI hook**:

- `$C0:012C` → `$ED:7488`: active-text observer/initializer;
- `$C0:16EA` → `$CA:FFC8`: live parser commit point for mid-text departure in the standalone/runtime-proven stack;
- `$C2:C786` → `$ED:7400`: normal-loop hold/decrement logic and safe timed-WAIT commit.

`vwf_dialogues` also owns `$C0:16EA` for its mode-2 pixel-aware parser preflight.
The aggregate builder therefore has one explicit merge rule: when both components
are selected, `$C0:16EA` points to the 16-byte dispatcher at `$ED:73C0`. Parser
mode 2 jumps unchanged to `$ED:7500`; all other modes jump to the validated
`intro_skip` helper `$CA:FFC8`. The standalone `intro_skip` IPS keeps the direct
validated hook, and the dispatcher is inert.

Input is read from the game's synchronized pad-1 copy `$7E:0042`, with R at bit
`$10`. The 16-bit state at `$7E:938A-$938B` uses:

- `$FFFF`: inactive / no continuous hold;
- `$0001-$FFFE`: countdown in progress;
- `$0000`: hold completed, pending commit.

Helpers are kept entirely inside the pre-existing `$ED:7400-$74FF` component
reservation. This is important: two earlier generalization attempts glitched at
boot because their growing C7 helper overflowed into the shared VWF routine at
`$C7:43D0-$43E7`. The validated implementation deliberately relocates the
extensible helpers to ED and leaves that C7 region untouched.

See:

- `../../docs/INTRO_SKIP_VALIDATION.md` — complete proof ladder and rejected variants;
- `../../docs/INTRO_EVENT_ARCHITECTURE.md` — event-engine / intro reverse engineering;
- `docs/MEMORY_MAP.md` — exact final allocations.

## Source of truth

`build_patch.py` is the canonical emitter. `src/intro_skip.asm` is a readable
mirror of the same validated logic. The builder contains size/allocation guards
so future edits cannot silently overflow `$ED:7400-$74FF` or `$CA:FFC0-$FFFF`.
