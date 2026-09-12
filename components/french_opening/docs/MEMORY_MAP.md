# Memory map — `french_opening`

## Expanded ROM allocations

- ROM `0x2E9000-0x2E9FFF` / `$EE:9000-$9FFF`: reserved opening-helper region.
  The active helper is 37 bytes at `0x2E9000-0x2E9024` / `$EE:9000-$9024`.
- ROM `0x2EA000-0x2EBFFF` / `$EE:A000-$BFFF`: relocated title-arrangement
  stream. It uses the stock compression container with literal packets only;
  stock `$C1:0014` expands it to WRAM `$7E:5000`.
- `$EF` is deliberately unused by this component. `mana_tree_original` owns
  extended runtime resources/hooks there.

## Patched stock resources / hooks

These are offsets inside the **decompressed stock title-code resource**, not
new ROM allocations:

- decompressed offset `$0845`: renderer fragment replaced by a JSL to
  `$EE:9000` plus same-footprint branch/padding;
- decompressed offset `$2D8D`: arrangement-loader fragment changed from source
  `$C7:B480` to `$EE:A000`, while preserving the stock `$C1:0014` call;
- the startup-credit list pointer and dwell constant are located by unique
  signatures and patched in the same decompressed title-code resource.

The recompressed title code remains in its original fixed-capacity stock block
at ROM `0x077C00`; the opening font remains in its original fixed-capacity block
at ROM `0x07C1C0`. The original arrangement block at ROM `0x07B480` is left
untouched.

## Font / WRAM conventions

Opening-font tile `$7A` (former `Z`) is authored in `assets/opening_font.png` as
a one-cell startup-credit `É`. Accent tiles `$7D-$7F` remain the scrolling-text
overlays. No additional ROM allocation is involved.

The component allocates no private persistent WRAM. `$7E:5000` is the stock
title-arrangement decompression destination.
