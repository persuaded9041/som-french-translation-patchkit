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

- `assets/`: data/text/font inputs used by the builder.
- `src/`: assembly-oriented map of the machine-code/data changes.
- `tools/`: extraction/support scripts when present.
- `docs/`: component memory map and validation notes.

## Compatibility

The 45-byte menu resource size is invariant. When combined with intro VWF, the decoder threshold is upgraded to $E6; the shared 13 glyphs are byte-identical.

For cross-component rules, see the package-level `docs/COMPATIBILITY.md`.
