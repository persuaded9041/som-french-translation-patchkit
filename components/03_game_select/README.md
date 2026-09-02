# French GAME SELECT

Translates GAME SELECT, computes frame widths from editable text, relocates help text and installs 13 French accented glyphs.

This component is standalone and targets only the clean unheadered US ROM.

## Build

```bash
python3 build_patch.py "Secret of Mana (USA).sfc" -o build/patch.ips
```

Required base SHA-256: `4c15013131351e694e05f22e38bb1b3e4031dedac77ec75abecebe8520d82d5f`.

## Editable sources

- `assets/`: component-specific text inputs used by the builder.
- `../../shared/french_charset/`: canonical French character mapping and glyph atlas.
- `src/game_select_text.asm`: assembly/data map of the component changes.
- `docs/MEMORY_MAP.md`: component ROM allocations and hooks.

## Compatibility

The 45-byte menu resource size is invariant. This standalone patch uses the shared `game_select` charset profile (`$D4-$E0`) and `$E1` as its decoder threshold. When combined with intro VWF, the root builder resolves the shared threshold to `$E6`.

For cross-component rules, see the package-level `docs/COMPATIBILITY.md`.
