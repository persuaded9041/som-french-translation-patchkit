# Skippable new-game introduction

Adds an R-triggered skip control to the post-character-creation introduction.

## Behavior

The current implementation is runtime-validated in game.

The hook at `$C0:012C` runs during the long introduction. Component 07 limits
itself to translated event `$0400` by requiring live event bank `$CA` and
pointer range `$0C02 <= pointer < $0E8B`. Runtime testing identifies bit `$10`
at `$4218` as **R** in this context.

R must remain continuously held for 120 NMI frames (about two seconds on the
NTSC reference ROM). The timer is non-blocking: the introduction continues
running while R is held. Releasing R resets the hold immediately, including on
frames where the event-engine hook does not run.

The timer samples the stock frame counter at `$7E:00F4` and stores its starting
frame plus an active flag in `$7E:938A-$938B`. Component 05 does not use those
bytes during its intro renderer. Component 06 can use the same addresses for
ordinary `$C9/$CA` dialogue, but translated event `$0400` is intercepted by
component 05 before component 06 reaches its renderer entry, so the lifetimes
remain mutually exclusive. A small hook at `$C0:AC34` clears the active
flag on NMI when R is released, preventing separate presses from accumulating.

After 120 continuous frames, the live event pointer is redirected to
`$CA:FFC0`. The private script follows the stock end of event `$0400` while
omitting only the `$1D $7F` Mode 7 world-map flyover:

`51 18 00 2A F8 11 06 00`

This closes the active text window, enters room `$00`, balances the intro `F8`
counter with `$2A $F8`, then continues at waterfall event `$0106`. Runtime
validation confirms normal arrival at the waterfall, no repeated scene, and
correct dialogue-frame transitions.

## Build

```bash
python3 build_patch.py "Secret of Mana (USA).sfc"
```

## Sources

- `src/intro_skip.asm`: readable 65C816 representation;
- `../../shared/asm65816.py`: shared minimal label/branch emitter used by the Python builder;
- `docs/MEMORY_MAP.md`: component-local ROM/WRAM allocations.
