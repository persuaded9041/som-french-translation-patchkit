# Next steps

Component 06 is at a runtime-validated VWF checkpoint. The renderer scope covers
ordinary event dialogue in `$C9/$CA`; GAME SELECT remains stock. The shared
44-byte parser buffer supports 38 logical glyphs, the pixel-aware preflight
prevents right-edge clipping, interruption/WAIT progression is converted to
physical cells, and the exact-tag post-outline repair is validated on `$C9/$CA`.

The stock glyph-addressing block `$C0:168A-$16B0` remains intentionally intact.
Shared VWF primitives and their ownership are documented at repository level and
in `ARCHITECTURE.md`; do not duplicate those descriptions here.

## Immediate next work

1. Build an editable, deterministic extraction/reinsertion pipeline for stock
   dialogue text. Preserve control codes, DTE semantics, dynamic names and event
   structure byte-exactly unless a source text is intentionally changed.
2. Start with extraction and round-trip verification against the clean USA ROM
   before translating or relocating dialogue data. A no-edit round trip must be
   demonstrably deterministic.
3. Keep renderer/VWF changes separate from text-pipeline changes so failures can
   be isolated and runtime-tested in small checkpoints.

## Deferred presentation improvement

The clipping-safety wrap is validated, but a word can still be split when the
remaining physical width ends inside it. Later, add word-aware pre-wrap: when the
next whole word does not fit in the remaining pixels but does fit on a fresh
line, break before the word. Do not weaken the current pre-consumption clipping
safety or split/rewind dynamic temporary sources or DTE tokens to implement it.

## Build discipline

All components are normal discovered components of the root aggregate builder. T

If a future investigation intentionally reuses a previously
validated global instead of rebuilding a component, that is a test procedure,
not repository behavior and should not be encoded in component documentation.

Any runtime-affecting change still requires an independent component build and a
combined-build/runtime check before becoming a checkpoint. The commercial ROM is
a local build input only and must never be committed or included in release
archives.
