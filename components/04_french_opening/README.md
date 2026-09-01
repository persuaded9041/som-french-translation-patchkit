# French opening and credits

Translates the startup credits and opening story while preserving the validated fixed-width renderer.

This component is standalone and targets only the clean unheadered US ROM.

## Build

```bash
python3 build_patch.py "Secret of Mana (USA).sfc" -o build
```

Required base SHA-256: `4c15013131351e694e05f22e38bb1b3e4031dedac77ec75abecebe8520d82d5f`.

Reference standalone IPS SHA-256: `ba9145ff516e48dfe838c1258bd9aa1841be6a2aa4c85e75af663f018313c14b`.

## Editable sources

- `assets/`: data/text/font inputs used by the builder.
- `src/`: assembly-oriented map of the machine-code/data changes.
- `tools/`: extraction/support scripts when present.
- `docs/`: component memory map and validation notes.

## Compatibility

The helper was moved from $C7:4285 to $EE:9000 specifically to remove the collision with intro VWF. Its behavior is otherwise unchanged.

For cross-component rules, see the package-level `docs/COMPATIBILITY.md`.
