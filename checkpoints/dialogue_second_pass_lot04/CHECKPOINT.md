# Dialogue second exhaustive pass — Lot 04 checkpoint

Validated lot range: `$0175` -> `$01CA` (60 canonical events).

Validated changes:
- `$0189 / C9:5B49`: balanced two-line reflow; Android-FR prose unchanged.
- `$0190 / C9:5D30`: balanced three-line reflow; Android-FR prose unchanged.
- `$0192 / C9:5EA9`: removed orphan `soldat !` line by reviewed reflow; Android-FR prose unchanged.
- `$01A5 / C9:63A6`: balanced three-line reflow; Android-FR prose unchanged.
- `$01C3 / C9:70BF`: reflow after stock `WAIT $10`; timing/commands unchanged.
- `$01C5 / C9:7107`: stock `PLAYER_NAME(1)` and `:` now continue on the same live line; choice remains on the following page.

Non-regression delta from Lot 03: exactly 6 translated carriers changed: `C9:5B49`, `C9:5D30`, `C9:5EA9`, `C9:63A6`, `C9:70BF`, `C9:7107`.

Validation:
- 701 simulator-clean translated events; 1959 translated carriers.
- 0 simulator errors, 0 warnings, 0 implicit runtime wraps.
- 302 active redistribution carriers.
- source round-trip: 713 dialogue events / 87,487 bytes.
- all 2048 stock scripts parse.
- source hygiene, manual supplements, redistribution recipes and dialogue regressions pass.
- forced `french_dialogues` rebuild + combine performed twice; outputs byte-identical.

Hashes:
- `translations/dialogues_french.json`: `f078fa2833c58234434d38085c3f6e21747aa41d59f590985826f82eb7f12089`
- `patches/french_dialogues.ips`: `3d7e8b0650b1b36cd8f7847f095770bf01b3d6b1db3468614189d6d4600eb88f`
- `patches/all.ips`: `60f670bcbe88857697cf8c7358ed833efb0fa65e9740570991f8335212305179`

Reference ROM is Secret of Mana (USA), unheadered. It is not included in the archive.
