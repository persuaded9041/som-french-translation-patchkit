# French intro VWF

Adds the French new-game introduction with variable-width rendering, private DTE, accents and a private 44-byte parser buffer.

This component is standalone and targets only the clean unheadered US ROM.

## Build

```bash
python3 build_patch.py "Secret of Mana (USA).sfc" -o build
```

Required base SHA-256: `4c15013131351e694e05f22e38bb1b3e4031dedac77ec75abecebe8520d82d5f`.

Reference standalone IPS SHA-256: `36d419d9ad83e98cbc0b34ff41f11ef2941992ac223dc1cfc4d8b21ccdf37758`.

## Editable sources

- `assets/`: component-specific intro text/layout inputs used by the builder.
- `../../shared/french_charset/`: canonical French character mapping and 18-glyph atlas used by this builder.
- `src/`: assembly-oriented map of the machine-code/data changes.
- `tools/`: extraction/support scripts when present.
- `docs/`: component memory map and validation notes.

## Compatibility

This component consumes the shared full French charset profile (`$D4-$E5`) and therefore uses `$E6` as its direct/DTE boundary. GAME SELECT consumes the first 13 characters from the same canonical source.

For cross-component rules, see the package-level `docs/COMPATIBILITY.md`.
