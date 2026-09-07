# Dialogue VWF

Adds variable-width rendering to stock event dialogue while leaving GAME SELECT and other users of the shared stock renderer fixed-width.

## Scope

- The runtime-validated stock path activates only for the real event-engine renderer call `$C0:1150 -> $C0:1664` in banks `$C9/$CA`.
- The same caller gate also accepts `$E8-$EC`, reserved exclusively for component-08 relocated event scripts; this relocated-dialogue path is runtime-validated with event `$0107` at `$E8:2000`.
- The parser bridge activates structurally for the event-parser caller `$114B`; GAME SELECT remains stock.
- The shared private buffer allows up to 38 logical decoded characters while physical output remains limited to the stock 32-cell / 256-pixel bitmap.
- `$C0:168A-$C0:16B0` remains intact.
- Interruptions/WAIT use generic VWF-width-to-physical-cell conversion.
- The post-outline repair remains runtime-validated for tagged `$C9/$CA` dialogue; the same exact renderer tag is used for relocated `$E8-$EC` scripts.
- Pixel-aware preflight prevents source glyphs from being consumed past the physical right edge; the `You have a sword` clipping case is runtime-validated as repaired.

## Interactive choice rows

Choice rows keep the same private-buffer, continuous-cursor VWF renderer as ordinary
event dialogue. The runtime-validated highlight fix does **not** add a second renderer, move
`CHOICE_OPTION` coordinates, rewrite `$A1D7[]`, or hook the stock magenta routine.

Component 06 uses the stock choice-active bit only at character start. When the current
decoded slot exactly matches one of the option starts already stored in `$A1D7[]`, the
cumulative VWF cursor is resynchronized to `slot * 8` pixels. Text remains fully VWF
between option starts. Runtime testing on `$0331` confirms that this keeps `Oui / Non` VWF
while the stock magenta selection follows the selected option.

The runtime-validated follow-up also recognizes the terminal boundary appended by
`CHOICE_END`. A preserved stock closing parenthesis therefore starts at the first cell
outside the final highlighted span instead of sharing the last option's compact VWF tiles.
When formatting removes the outer decoration for width, no glyph occupies that terminal
slot and this extra boundary is inert.

The formatter/simulator remains conservative. Component 08 may now move only a later
`CHOICE_OPTION` right to the minimum decoded-cell position needed to avoid overwriting the
preceding VWF label; `$00DF` runtime-validates `$11 -> $12`. Component 06 needs no new
choice mode for this: it consumes the resulting stock-format anchor table normally.

## Component-specific behavior

Component 06 keeps its event-engine gating, dialogue parser integration, interruption handling, pixel-aware right-edge protection and post-outline repair. Charset, metrics/framing, text-buffer bridge, compositor, stock-font row renderer and outline preparation are shared with component 05.

The post-outline repair is gated by the exact component-06 renderer tag `$9385 == $01`, which excludes component 05's intro use of the same scratch byte.

## Technical documentation

Detailed implementation notes intentionally live outside this README:

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): renderer design, scope and invariants.
- [`docs/MEMORY_MAP.md`](docs/MEMORY_MAP.md): ROM/WRAM hooks and scratch allocations.
- [`docs/EVENT_INTERRUPTION_NOTES.md`](docs/EVENT_INTERRUPTION_NOTES.md): interrupted-chunk/event hand-off behavior.
- [`docs/NEXT_STEPS.md`](docs/NEXT_STEPS.md): current handoff and remaining work.

`build_patch.py` is the executable source of truth; ASM files are readable references for generated code.
