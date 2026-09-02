# 9-character names

Extends player names from 6 to 9 characters and adds uppercase, lowercase and symbol pages.

This component is standalone and targets only the clean unheadered US ROM.

## Build

```bash
python3 build_patch.py "Secret of Mana (USA).sfc" -o build/patch.ips
```

Required base SHA-256: `4c15013131351e694e05f22e38bb1b3e4031dedac77ec75abecebe8520d82d5f`.

Reference standalone IPS SHA-256: `e793dc519b3239d714038a34c6bffdb6ff93f08becc8baac90f960107447817c`.

## Editable sources

- `assets/`: data/text/font inputs used by the builder.
- `src/`: assembly-oriented map of the machine-code/data changes.
- `tools/`: extraction/support scripts when present.
- `docs/`: component memory map and validation notes.

## Compatibility

Character pages and help text are generated from assets/naming_characters.txt and assets/naming_help.csv.

For cross-component rules, see the package-level `docs/COMPATIBILITY.md`.

## French help-text CSV

`assets/naming_help.csv` is the editable reinsertion source for the three help
lines displayed at the bottom of the Name Entry screen. It uses exactly two
columns, `id,text`, with sequential IDs `NAME_HELP_1`, `NAME_HELP_2`, etc.

Current French text:

```text
Choisissez une lettre avec la Croix Directionnelle.
Appuyez sur le bouton B pour valider. Le nom peut faire
9 lettres maximum. Appuyez sur Start pour continuer.
```

The builder adds the stock leading blank cell to each display line and encodes
CSV row boundaries as the original `$7F` line separator.
