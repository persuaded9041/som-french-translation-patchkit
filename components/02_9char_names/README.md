# 9-character names

Extends player names from 6 to 9 characters and adds uppercase, lowercase and symbol pages.

This component is standalone and targets only the clean unheadered US ROM.

## Build

```bash
python3 build_patch.py "Secret of Mana (USA).sfc" -o build/patch.ips
```

Required base SHA-256: `4c15013131351e694e05f22e38bb1b3e4031dedac77ec75abecebe8520d82d5f`.

Reference standalone IPS SHA-256: `dc20f8994d78968863311543212dde5c9c8ee9befa97d58f79dd834d8156e77f`.

## Editable sources

- `assets/`: data/text/font inputs used by the builder.
- `src/`: assembly-oriented map of the machine-code/data changes.
- `tools/`: extraction/support scripts when present.
- `docs/`: component memory map and validation notes.

## Compatibility

Character pages and help text are generated from assets/naming_characters.txt and assets/naming_help.txt.

For cross-component rules, see the package-level `docs/COMPATIBILITY.md`.
