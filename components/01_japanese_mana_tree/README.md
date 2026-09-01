# Japanese Mana Tree restoration

Restores the original Japanese Mana Tree graphic resource while keeping the US title/logo path.

This component is standalone and targets only the clean unheadered US ROM.

## Build

```bash
python3 build_patch.py "Secret of Mana (USA).sfc" -o build
```

Required base SHA-256: `4c15013131351e694e05f22e38bb1b3e4031dedac77ec75abecebe8520d82d5f`.

Reference standalone IPS SHA-256: `424a15e1f08be4207054d99c83d0f69a5ec5cf2d9acf3160d7b35eeb35060027`.

## Editable sources

- `assets/`: data/text/font inputs used by the builder.
- `src/`: assembly-oriented map of the machine-code/data changes.
- `tools/`: extraction/support scripts when present.
- `docs/`: component memory map and validation notes.

## Compatibility

The helper and resource behavior were isolated from Secret of Mana Plus 2.1. No opening-translation behavior is included.

For cross-component rules, see the package-level `docs/COMPATIBILITY.md`.
