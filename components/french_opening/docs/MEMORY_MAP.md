# Memory map

- ROM `0x2E8000-0x2E8FFF` / `$EE:8000-$8FFF`: reserved relocated arrangement region.
- ROM `0x2E9000-0x2EFFFF` / `$EE:9000-$FFFF`: reserved opening-helper region (current helper: 37 bytes).

- Opening font tile `$7A` (the otherwise-unused `Z` slot) is authored directly in `assets/opening_font.png` as a one-cell startup-credit `É`; accent tiles `$7D-$7F` remain unchanged. This uses no additional ROM/WRAM allocation.
