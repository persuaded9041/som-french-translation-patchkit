# Japanese Mana Tree restoration

Restores the original Japanese Mana Tree graphic resource while keeping the USA title/logo path unchanged. The component is standalone and owns no translated text.

## Architecture

The clean USA ROM already jumps through a resource-loader trampoline at `$C1:4CF6`. This component redirects that one `JML` to a private helper at `$EF:F800`. The helper handles only resource ID `$D2A9` (the Mana Tree resource); all other resource IDs immediately continue through the original `$7E:AF0B` path.

For `$D2A9`, the helper points the stock `$C1:0014` loader/decompressor at the relocated Japanese resource in `$EF:C000-$F5FF`. No WRAM region is reserved by this component.

## Inputs

- `assets/mana_tree_jp.bin` — canonical 0x3600-byte Japanese Mana Tree resource. The builder validates its SHA-256.
- `src/tree_restoration.asm` — readable source-map representation of the hook, resource placement and exact helper bytes. `build_patch.py` remains the executable builder.

The component does not consume generated project outputs.

## Build and validation

From the repository root:

```bash
python3 components/mana_tree_original/build_patch.py "Secret of Mana (USA).sfc" \
  -o /tmp/mana_tree_original.ips
```

Or through the aggregate builder:

```bash
python3 build.py "Secret of Mana (USA).sfc" mana_tree_original
python3 build.py "Secret of Mana (USA).sfc" mana_tree_original --combine
```

The standalone builder requires the clean, unheadered USA ROM and expands it to 3 MiB. See `docs/MEMORY_MAP.md` for the component allocations and the root `docs/COMPATIBILITY.md` for project-wide overlap rules.

## Compatibility constraint

The `$C1:4CF6` hook is global, but its private logic is resource-ID gated. `french_opening` deliberately keeps its relocated title arrangement in bank `$EE` and uses the stock `$C1:0014` protocol; this combination is runtime-validated.
