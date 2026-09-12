# Skippable new-game introduction

Adds the runtime-validated **hold R to skip** control to translated new-game
intro event `$0400`. It owns no translation text.

## Runtime contract

The event-engine hook at `$C0:012C` activates only when the live event is in
bank `$CA` and `$0C02 <= pointer < $0E8B`, the exact validated `$0400` window.
Holding **R** continuously for 120 NMI frames redirects the live event pointer
to the private script at `$CA:FFC0`. The timer is non-blocking, so the intro
continues while the button is held; releasing R cancels the hold immediately.

A tiny hook at `$C0:AC34` also observes physical R release once per NMI. This
prevents two shorter presses from accumulating if the event-engine hook happens
not to execute during the release interval. Both hooks restore the stock
instructions they replace before returning to stock code.

The private script is command-only data:

```text
51 18 00 2A F8 11 06 00
```

It follows the validated stock end-of-intro cleanup while omitting only the
`$1D $7F` Mode 7 world-map flyover, then arrives directly at the waterfall.

## Ownership

- ROM reserve: `$ED:7400-$74FF`; active code currently occupies
  `$ED:7400-$7487` and `$ED:7490-$74AD`.
- Private event: `$CA:FFC0-$FFC7`.
- Temporary WRAM: `$7E:938A-$938B`, only during translated intro `$0400`.
- No prose or generated translation asset belongs to this component.

The WRAM reuse is deliberately mutually exclusive with `vwf_dialogues`;
`vwf_intro` intercepts `$0400` before the dialogue renderer can use the same
scratch bytes. See `docs/MEMORY_MAP.md` for exact ranges.

## Sources

- `build_patch.py`: canonical executable emitter.
- `src/intro_skip.asm`: readable 65C816 mirror/reference.
- `docs/MEMORY_MAP.md`: component-local ROM/WRAM ownership.
