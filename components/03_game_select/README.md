# French GAME SELECT

Translates GAME SELECT, computes frame widths from editable text, relocates help text and installs 13 French accented glyphs.

This component is standalone and targets only the clean unheadered US ROM.

## Build

```bash
python3 build_patch.py "Secret of Mana (USA).sfc" -o build/patch.ips
```

Required base SHA-256: `4c15013131351e694e05f22e38bb1b3e4031dedac77ec75abecebe8520d82d5f`.

Reference standalone IPS SHA-256: `ede4084d40087fbaeb6622edeb9e976e4a70477ff1ba06cc5bafd610fb5b86d2`.

## Editable sources

- `assets/`: component-specific text inputs used by the builder.
- `../../shared/french_charset/`: canonical French character mapping and glyph atlas used by this builder.
- `src/`: assembly-oriented map of the machine-code/data changes.
- `tools/`: extraction/support scripts when present.
- `docs/`: component memory map and validation notes.

## Compatibility

The 45-byte menu resource size is invariant. This standalone patch uses the shared `game_select` charset profile (`$D4-$E0`) and keeps its validated `$E1` decoder threshold. When combined with intro VWF, the root builder upgrades the threshold to `$E6`.

For cross-component rules, see the package-level `docs/COMPATIBILITY.md`.
