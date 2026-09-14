# Secret of Mana FR — exhaustive dialogue audit complete

Date: 2026-09-14

The second exhaustive playable-dialogue audit is complete across 12 lots / 701 accepted playable events.

## Final validation

- 701/701 events simulator-clean
- 1959 translated carriers
- Android identity: 1798/1838
- 0 errors
- 0 warnings
- 0 implicit wraps
- 0 speaker-label newline findings
- 0 remaining rolling-scroll candidates
- 302 active redistribution carriers
- 713-event / 87,487-byte source round-trip OK
- all 2048 stock event scripts parse
- source hygiene and dialogue regressions OK

## Reproducibility

Two consecutive complete builds produced identical hashes:

- dialogues_french.json: `4c71ee39ef1c10acbff1934401afdb4ded788bb525b7282c5a8227606863be82`
- french_dialogues.ips: `006281fc3240ccef2ab10abe0d3a307ed274d13ab58d62a52503776c64b06c79`
- all.ips: `a4510f1675a9b0be80518961338d847b3218f296dfa74032954b6b79570dc2e4`

The final global scan restored four earlier validated rolling-scroll layouts ($00AA, $0112, $0180, $01B9) and the lot-1 dynamic-speaker/fresh-page fixes ($0020, $0021, $0023), which had been reintroduced by older late recipes.
