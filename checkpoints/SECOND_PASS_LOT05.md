# Second exhaustive dialogue pass — Lot 05 checkpoint

Canonical range: `$01CB` → `$0228` (60 accepted events).

Validated changes:
- `$01E5 / C9:8256`: layout-only reflow; Android FR prose unchanged.
- `$01ED / C9:8846`: layout-only reflow; Android FR prose unchanged.
- `$01ED / C9:8892`: layout-only reflow; Android FR prose unchanged.
- `$0212 / C9:944F + C9:9456`: preserve `Gemma :` carrier, omit stock `PLAYER_NAME(0)`, derive the remainder from Android FR slot 902 with structural speaker-label stripping, and replay the validated layout. No localized prose in recipe data.
- `$0223 / C9:9737`: layout-only reflow; Android FR prose unchanged.

Validation:
- dialogue-format-mass: 701 simulator-clean events / 1959 translated source tokens
- regressions: pass
- source hygiene: pass
- forced `french_dialogues` rebuild + full IPS combination performed twice; outputs byte-identical

Hashes:
- `translations/dialogues_french.json`: `b2f712945f0a302b698949b8d2bc7beac302d5d8e243d8ea818fb1b3c6f1cd33`
- `patches/french_dialogues.ips`: `0b2384536ca348645e9792747b1a9c2b2fa6f9181090bd926468098344e992e4`
- `patches/all.ips`: `fc48e3780456274f61a6578e113731541b63215e9292f3059188221fd0d805a8`

The reference ROM is not included in this checkpoint.
