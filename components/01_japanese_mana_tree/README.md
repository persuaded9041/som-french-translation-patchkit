# Japanese Mana Tree restoration

Restores the original Japanese Mana Tree graphic resource while keeping the US title/logo path.

This component is standalone and targets only the clean unheadered US ROM.

## Build

```bash
python3 build_patch.py "Secret of Mana (USA).sfc" -o build/patch.ips
```

Required base SHA-256: `4c15013131351e694e05f22e38bb1b3e4031dedac77ec75abecebe8520d82d5f`.

## Editable sources

- `assets/mana_tree_jp.bin`: Japanese Mana Tree resource used by the builder.
- `src/tree_restoration.asm`: assembly/source-map representation of the hook, relocated resource and loader helper.
- `tools/extract_mana_tree.py`: extraction helper for rebuilding the internal asset from the Japanese ROM.
- `docs/MEMORY_MAP.md`: component ROM allocations and hooks.

## Compatibility

The helper and resource behavior were isolated from Secret of Mana Plus 2.1. No opening-translation behavior is included.

For cross-component rules, see the package-level `docs/COMPATIBILITY.md`.
