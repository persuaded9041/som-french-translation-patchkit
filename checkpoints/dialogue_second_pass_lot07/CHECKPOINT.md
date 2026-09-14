# Dialogue second pass — Lot 07 checkpoint

Range: $029B -> $02E3 (60 canonical accepted events).

Validated changes:
- $02B3 / C9:B941 — visual reflow only.
- $02BE / C9:BBEF — visual reflow only.
- $02CE / C9:BE80 — dynamic-name-safe visual reflow; `%S(0,0)` remains dynamic.
- $02D5 / C9:C158 — validated two-page reflow preserving prose and event timing.
- $02D6 / C9:C2A9 — visual reflow only.
- $02D9 / C9:C390 — visual reflow only.

Validation:
- 701 simulator-clean playable events / 1959 translated carriers.
- 0 errors / 0 warnings / 0 implicit wraps.
- Android identity 1798/1838 unchanged.
- Redistribution: 302 active carriers.
- 713 dialogue source events round-trip exactly / 87,487 bytes.
- all 2048 stock scripts parse.
- carrier comparison vs lot 06: exactly 6 changed carriers, all validated above.
- forced `french_dialogues` rebuild twice: byte-identical.
- complete IPS recombination twice: byte-identical.

Hashes:
- translations/dialogues_french.json: 7a56522faa11cf80ba7c8f8c47be0c8007894038d67f2e1e2e1bf30fec04aa69
- patches/french_dialogues.ips: bce5462ecb50af245c6337ccaa397e47f95314704507856770a16342c1e7aa8b
- patches/all.ips: ba36f070a445833c8226f4a7464e3bc2c4b928f9d9e202de1387365939eb7014

No ROM is included in the checkpoint archive.
