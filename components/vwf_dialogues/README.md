# Dialogue VWF

Adds variable-width rendering to stock event dialogue while leaving GAME SELECT and other users of the shared stock renderer fixed-width.

## Scope

- The runtime-validated stock path activates only for the real event-engine renderer call `$C0:1150 -> $C0:1664` in banks `$C9/$CA`.
- The same caller gate also accepts `$E8-$EC`, reserved exclusively for `french_dialogues` relocated event scripts; this relocated-dialogue path is runtime-validated with event `$0107` at `$E8:2000`.
- The parser bridge activates structurally for the event-parser caller `$114B`; GAME SELECT remains stock.
- The shared private buffer allows up to 38 logical decoded characters while physical output remains limited to the stock 32-cell / 256-pixel bitmap.
- `$C0:168A-$C0:16B0` remains intact.
- Interruptions/WAIT use generic VWF-width-to-physical-cell conversion plus exact sub-cell continuation: a partial final 8-pixel cell is preserved and reused when the next renderer invocation proves it is continuing the same physical line.
- The post-outline repair remains runtime-validated for tagged `$C9/$CA` dialogue; the same exact renderer tag is used for relocated `$E8-$EC` scripts.
- Pixel-aware preflight prevents source glyphs from being consumed past the physical right edge; the `You have a sword` clipping case is runtime-validated as repaired.
- Ordinary dialogue chunks start the private VWF bitmap at pixel cursor `1`, preserving the left outline of glyphs drawn against the dialogue window's left edge. A proven same-line interrupted continuation overrides that default with the exact saved sub-cell phase, so the 1 px inset is not accumulated after `WAIT`.

## Interactive choice rows

Choice rows use the ordinary dialogue VWF renderer; there is no separate
`CHOICE_BEGIN` renderer and logical `$A1D7[]` parser/storage anchors are never
rewritten. Decorated rows keep stock anchor/highlight geometry. Undecorated
two-option rows use the runtime-validated measured-end visual geometry with a
two-cell private left compaction and the right-edge separator fallback. Private
visual boundaries live at `$7E:93BD-$93BF` and are consumed only by the small
`$C0:1B5F` highlight-geometry hook.

The Potos validation matrix, exact endpoint arithmetic and the `$05/$0A` test
harness trap are documented in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
The known one-cell cosmetic gap before the closing `)` on some short decorated
rows remains intentionally deferred.

## Component-specific behavior

`vwf_dialogues` keeps its event-engine gating, dialogue parser integration, interruption handling, pixel-aware right-edge protection and post-outline repair. Charset, metrics/framing, text-buffer bridge, compositor, stock-font row renderer and outline preparation are shared with `vwf_intro`. The `dialogue_french` `$D3-$E7` glyph span and context-sensitive DTE router are also installed from shared canonical helpers so standalone builds remain self-contained.

The post-outline repair is gated by the exact `vwf_dialogues` renderer tag `$9385 == $01`, which excludes `vwf_intro`'s intro use of the same scratch byte.

## Technical documentation

Detailed implementation notes intentionally live outside this README:

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): renderer design, scope and invariants.
- [`docs/MEMORY_MAP.md`](docs/MEMORY_MAP.md): ROM/WRAM hooks and scratch allocations.
- [`docs/EVENT_INTERRUPTION_NOTES.md`](docs/EVENT_INTERRUPTION_NOTES.md): interrupted-chunk/event hand-off behavior.

`build_patch.py` is the executable source of truth; ASM files are readable references for generated code.
