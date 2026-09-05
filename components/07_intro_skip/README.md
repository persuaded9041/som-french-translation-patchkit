# Skippable new-game introduction

Adds an R-triggered skip control to the post-character-creation introduction.

## Behavior

The runtime-validated hook at `$C0:012C` limits itself to translated event `$0400` by requiring live event bank `$CA` and pointer range `$0C02 <= pointer < $0E8B`.

Holding **R** continuously for 120 NMI frames (about two seconds on the NTSC reference ROM) redirects the live event pointer to `$CA:FFC0`. The timer is non-blocking and resets immediately when R is released.

The private script follows the stock end of event `$0400` while omitting only the `$1D $7F` Mode 7 world-map flyover:

```text
51 18 00 2A F8 11 06 00
```

Runtime validation confirms normal arrival at the waterfall, no repeated scene and correct dialogue-frame transitions.

## Sources

- `src/intro_skip.asm`: readable 65C816 representation.
- `docs/MEMORY_MAP.md`: component-local ROM/WRAM allocations.

The timer uses `$7E:938A-$938B`; its lifetime is mutually exclusive with the VWF scratch usage documented by components 05/06.
