# Memory map

- ROM `0x014CF6-0x014CF9` / `$C1:4CF6-$4CF9`: replaces the stock `JML $7E:AF0B` with `JML $EF:F800`.
- ROM `0x2FC000-0x2FF5FF` / `$EF:C000-$F5FF`: canonical 0x3600-byte Japanese Mana Tree resource (`$D2A9`).
- ROM `0x2FF800-0x2FF89F` / `$EF:F800-$F89F`: 160-byte resource-loader helper. It intercepts only resource ID `$D2A9`; every other ID falls through to the original `$7E:AF0B` loader path.
- WRAM: no private allocation. The helper uses the stock resource-loader state and calls the stock `$C1:0014` loader/decompressor.
