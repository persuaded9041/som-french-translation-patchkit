# French intro VWF

Adds the French new-game introduction with variable-width rendering, private DTE, accents and a private 44-byte parser buffer.

This component is standalone and targets only the clean unheadered US ROM.

## Build

```bash
python3 build_patch.py "Secret of Mana (USA).sfc" -o build/patch.ips
```


## Editable sources

- `assets/`: component-specific intro text/layout inputs used by the builder.
- `../../shared/french_charset/`: canonical French character mapping and 18-glyph atlas.
- `src/intro_vwf.asm`: readable 65C816 representation of the code/data emitted by Python.
- `../../shared/asm65816.py`: shared minimal label/branch emitter used by the Python builder.
- `docs/MEMORY_MAP.md`: component ROM/WRAM allocations and hooks.

## Compatibility

This component consumes the shared full French charset profile (`$D4-$E5`) and therefore uses `$E6` as its direct/DTE boundary. GAME SELECT consumes the first 13 characters from the same canonical source.

For cross-component rules, see the package-level `docs/COMPATIBILITY.md`.
