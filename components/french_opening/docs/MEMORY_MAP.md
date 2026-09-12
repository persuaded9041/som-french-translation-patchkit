# Memory map

- ROM `0x2E9000-0x2E9FFF` / `$EE:9000-$9FFF`: opening renderer helper region. The current helper is much smaller than the reserved range.
- ROM `0x2EA000-0x2EBFFF` / `$EE:A000-$BFFF`: relocated title-arrangement stream. It uses the stock compression container but literal packets only; the stock `$C1:0014` loader/decompressor still expands it to WRAM `$7E:5000`.
- `$EF` is deliberately unused by this component. `mana_tree_original` owns runtime resources/hooks in that bank.

- Opening font tile `$7A` (the otherwise-unused `Z` slot) is authored directly in `assets/opening_font.png` as a one-cell startup-credit `É`; accent tiles `$7D-$7F` remain unchanged. This uses no additional ROM/WRAM allocation.
