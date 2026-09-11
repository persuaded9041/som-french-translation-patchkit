# Japanese Mana Tree restoration

Restores the original Japanese Mana Tree graphic resource while keeping the US title/logo path.

## Editable sources

- `assets/mana_tree_jp.bin`: Japanese Mana Tree resource used by the builder.
- `src/tree_restoration.asm`: readable representation of the hook, relocated resource and loader helper.
- `tools/extract_mana_tree.py`: helper for extracting the resource from a local Japanese ROM.
- `docs/MEMORY_MAP.md`: component ROM allocations and hooks.

The helper/resource behavior was isolated from Secret of Mana Plus 2.1; no opening-translation behavior is included.
