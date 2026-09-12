# Intro VWF

Owns the variable-width renderer/runtime used only by new-game event `$0400`.
It owns no translated prose, French glyph installation or private intro DTE.
Those belong to `french_intro`.

## Runtime ownership

- renderer hook at `$C0:1664-$1667`, gated to bank `$CA` and the validated
  event window `$0C02-$0E8A`;
- intro renderer at `$C7:4285-$437C` and its 128-byte advance table at
  `$C7:4440-$44BF`;
- byte-identical shared parser-buffer, framing, row-renderer, compositor and
  outline infrastructure also installed by `vwf_dialogues`;
- private decoded-text buffer `$7E:9390-$93BB` plus intro scratch
  `$7E:9380-$9389`;
- WAIT-resume conversion from VWF pixels back to physical 8-pixel cells when
  the next event opcode is WAIT;
- standalone relocation of unchanged stock events `$0401-$040F` from
  `$CA:0E44-$0E8B` to `$CA:FF70-$FFB7`, with their 15 pointers rewritten at
  `$C9:F802-$F81F` so `$0400` retains its validated VWF runtime window.

`french_intro` performs the same `$0401-$040F` relocation independently. The
resulting pointer/data writes are intentionally byte-identical when the two
components are combined.

## Metrics without glyph ownership

The advance table is generated against a temporary copy of the stock font with
the canonical shared French glyph atlas inserted. This preserves the validated
Round-75/76 metrics while leaving the actual `$D4-$E5` glyph installation and
DTE threshold to `french_intro`.

The shared parser bridge keeps the validated logical capacity of 38 visible
glyphs plus one following control unit. Outside the exact event-engine intro
gate, all hooks fall back to stock behavior.

See `docs/MEMORY_MAP.md` for exact ROM/WRAM ranges and `src/intro_vwf.asm` for a
readable reference of the emitted renderer code.
