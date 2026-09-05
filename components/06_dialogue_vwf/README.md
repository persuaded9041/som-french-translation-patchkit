# Dialogue VWF

Adds variable-width rendering to stock event dialogue while leaving GAME SELECT and other users of the shared stock renderer fixed-width.

## Runtime-validated scope

- VWF activates only for the real event-engine renderer call `$C0:1150 -> $C0:1664` in banks `$C9/$CA`.
- The parser bridge activates structurally for the event-parser caller `$114B`; GAME SELECT remains stock.
- The shared private buffer allows up to 38 logical decoded characters while physical output remains limited to the stock 32-cell / 256-pixel bitmap.
- `$C0:168A-$C0:16B0` remains intact.
- Interruptions/WAIT use generic VWF-width-to-physical-cell conversion.
- The post-outline repair is runtime-validated for tagged `$C9/$CA` dialogue.
- Pixel-aware preflight prevents source glyphs from being consumed past the physical right edge; the `You have a sword` clipping case is runtime-validated as repaired.

One presentation improvement remains deliberately deferred: when no safe word boundary is available, a word may still be split across lines. A future pass should move the whole next word to a fresh line when it fits there.

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
