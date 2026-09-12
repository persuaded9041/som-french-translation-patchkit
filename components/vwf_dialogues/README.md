# Dialogue VWF

Adds variable-width rendering to stock event dialogue while leaving GAME SELECT and other users of the shared stock renderer fixed-width.

## Scope

- The runtime-validated stock path activates only for the real event-engine renderer call `$C0:1150 -> $C0:1664` in banks `$C9/$CA`.
- The same caller gate also accepts `$E8-$EC`, reserved exclusively for `french_dialogues` relocated event scripts; this relocated-dialogue path is runtime-validated with event `$0107` at `$E8:2000`.
- The parser bridge activates structurally for the event-parser caller `$114B`; GAME SELECT remains stock.
- The shared private buffer allows up to 38 logical decoded characters while physical output remains limited to the stock 32-cell / 256-pixel bitmap.
- `$C0:168A-$C0:16B0` remains intact.
- Interruptions/WAIT use generic VWF-width-to-physical-cell conversion.
- The post-outline repair remains runtime-validated for tagged `$C9/$CA` dialogue; the same exact renderer tag is used for relocated `$E8-$EC` scripts.
- Pixel-aware preflight prevents source glyphs from being consumed past the physical right edge; the `You have a sword` clipping case is runtime-validated as repaired.

## Interactive choice rows

Choice rows keep the same private-buffer, continuous-cursor VWF renderer as ordinary event dialogue; there is still no special `CHOICE_BEGIN` renderer.

`$A1D7[]` remains the logical parser/storage geometry and is never rewritten. For ordinary decorated choices, detected structurally when the decoded terminal slot contains the stock closing `)` (`$CC`), `vwf_dialogues` keeps the previously validated stock-anchor VWF/highlight path.

For undecorated two-option rows, `vwf_dialogues` uses the runtime-validated measured-end geometry:

- the first visible option starts at `max(logical_first, $03) - 2`, so the private visual/highlight span can begin two cells farther left while logical storage stays unchanged;
- after each non-space glyph is rendered, the live VWF endpoint is remembered;
- the next option normally starts at `ceil(endpoint / 8) + 1` whole cell, preserving one blank 8-pixel cell;
- when that rounded first-option endpoint has already reached cell `$11` (136 px), the extra blank cell is omitted, keeping the next option at the rounded endpoint and protecting the right edge;
- the terminal visual boundary is `ceil(final_endpoint / 8)`;
- private visual boundaries at `$93BD-$93BF` drive the stock magenta span through a small geometry hook at `$C0:1B5F`;
- logical `$A1D7[]` anchors continue to serve decoded storage and parser resets.

This separation is runtime-validated on Potos reproductions of `$00CE`, `$00CF`, `$00D0`, `$00D1` and `$0202`, including both magenta selections. With the final two-cell private left compaction, `$00D0` now starts `Désert de Kakkara` at 8 px, reaches 117 px, keeps the normal blank separator, starts `Pays de glace` at 128 px and finishes at 209 px; its terminal private boundary is cell `$1B`. The retained cell-`$11` separator-omission branch was separately runtime-validated on the earlier `$00D0` right-edge checkpoint before this left compaction and remains a generic safety fallback. Ordinary decorated `Acheter / Vendre` and `Oui / Non` choices remain on the stock-anchor fallback and are unchanged.

A minor cosmetic issue is also deferred: short decorated choices could use one more blank cell before the closing `)`. This predates the compact wide-row path and is not part of the current fix.

## Component-specific behavior

`vwf_dialogues` keeps its event-engine gating, dialogue parser integration, interruption handling, pixel-aware right-edge protection and post-outline repair. Charset, metrics/framing, text-buffer bridge, compositor, stock-font row renderer and outline preparation are shared with `vwf_intro`.

The post-outline repair is gated by the exact `vwf_dialogues` renderer tag `$9385 == $01`, which excludes `vwf_intro`'s intro use of the same scratch byte.

## Technical documentation

Detailed implementation notes intentionally live outside this README:

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): renderer design, scope and invariants.
- [`docs/MEMORY_MAP.md`](docs/MEMORY_MAP.md): ROM/WRAM hooks and scratch allocations.
- [`docs/EVENT_INTERRUPTION_NOTES.md`](docs/EVENT_INTERRUPTION_NOTES.md): interrupted-chunk/event hand-off behavior.

`build_patch.py` is the executable source of truth; ASM files are readable references for generated code.
