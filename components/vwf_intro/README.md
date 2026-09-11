# Intro VWF

Owns the variable-width rendering/runtime path for new-game event `$0400`.
It no longer owns any French translation payload.

## Responsibilities

- intro-only VWF renderer and exact event-window gate;
- shared private parser-buffer bridge and validated 38-character capacity;
- VWF advance table, framing, row renderer, compositor and outline preparation;
- WAIT resume cursor conversion for the intro path;
- relocation of stock events `$0401-$040F` to `$CA:FF70-$FFB7`, keeping the
  validated `$0C02-$0E8B` intro runtime window exclusive even when this
  component is applied alone.

The width table is generated against a **virtual** font containing the shared
French glyph atlas so the runtime metrics remain byte-identical to Round 75/76,
but this component does not install those glyphs or change the DTE threshold.
Those responsibilities now belong to `french_intro`.

`french_intro` independently performs the same `$0401-$040F` relocation; the
overlap is intentionally byte-identical in aggregate builds.
