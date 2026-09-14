# Second exhaustive dialogue pass — Lot 06 checkpoint

Canonical range: `$022E` → `$029A` (60 accepted events).

Validated changes:
- `$0259 / C9:A1B3`: replace the generated leading newline with a clear-only `TEXT_CLEAR` immediately after the existing stock `WAIT $08`; Android FR prose and WAIT timing unchanged.
- `$0263 / C9:A30C`: add a clear-only `TEXT_CLEAR` immediately after the existing stock `WAIT $00`; Android FR prose and WAIT timing unchanged.
- `$028A`: insert one `TEXT_CLEAR` before `PLAYER_NAME(1) / C9:A9CE`, after the existing stock `WAIT $00` and intervening actor-action bridge; no text or WAIT is added/changed.
- `$028B`: deliberately unchanged; reviewed as a valid controlled-scroll sequence.

Validation:
- dialogue-format-mass: 701 simulator-clean events / 1959 translated source tokens
- targeted worst-case player name `WWWWWWWWW`: 0 errors / 0 warnings / 0 implicit wraps
- regressions: pass
- redistribution recipes: pass (302 active carriers)
- manual supplements: pass
- source hygiene: pass
- source round-trip: 713 events / 87,487 bytes
- stock structural scan: all 2048 scripts parse
- carrier comparison vs lot 05: only `C9:A1B3` and `C9:A30C` changed; `$028A` is structural metadata only
- forced `french_dialogues` rebuild + full IPS combination performed twice; outputs byte-identical

Hashes:
- `translations/dialogues_french.json`: `38d491bb52d1798c1cc41133446a99bc42f8660fa8ca85f7c73a02afdfbe276c`
- `patches/french_dialogues.ips`: `134a07e5a524442ab8299912d98a250858812cf90dc8b126ac4c52366088186f`
- `patches/all.ips`: `cf79ed51396f65568952d9840665c556c9b5c2cfc8a53738a064940976af0ad7`

The reference ROM is not included in this checkpoint.
