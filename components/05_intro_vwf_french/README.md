# French intro VWF

Adds the French new-game introduction with variable-width rendering, private
DTE, accents and a private parser buffer.

## Sources

- root `assets/intro_event.json`: the eight clean-USA text parts extracted from
  stock event `$0400` with position-based IDs.
- root `translations/intro_event_french.json`: the eight already validated
  French intro translations.
- `assets/text/intro_layout.json`: component-local line/page layout metadata,
  keyed by the same source IDs.
- `src/intro_vwf.asm`: readable representation of component-specific code/data
  emitted by Python.
- `docs/MEMORY_MAP.md`: component ROM/WRAM allocations and hooks.

Shared charset and VWF primitives live under `../../shared/` and are documented
by the root README and `docs/SHARED_CHARSET.md`.

## Component-specific behavior

Component 05 keeps its own intro parser, DTE, layout, event gating and WAIT
handling. Its renderer uses the shared stock font, metrics/framing, private
text-buffer bridge, compositor, row renderer and outline preparation also used
by component 06.

The shared VWF path and private-buffer architecture are runtime-validated.
Component 05 does not carry a private preframed glyph table.
