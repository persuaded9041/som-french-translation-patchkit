# French opening and credits

Translates the startup credits and opening story while preserving the fixed-width renderer.

This component is standalone and targets only the clean unheadered US ROM.

## Build

```bash
python3 build_patch.py "Secret of Mana (USA).sfc" -o build/patch.ips
```

Required base SHA-256: `4c15013131351e694e05f22e38bb1b3e4031dedac77ec75abecebe8520d82d5f`.

## Editable sources

- `assets/`: text, credits and font inputs used by the builder.
- `src/opening_hook.asm`: readable 65C816 representation of the renderer helper emitted by Python.
- `docs/MEMORY_MAP.md`: component ROM allocations and hooks.

## Compatibility

The helper lives at `$EE:9000`, separate from the intro VWF code at `$C7:4285`.

For cross-component rules, see the package-level `docs/COMPATIBILITY.md`.
