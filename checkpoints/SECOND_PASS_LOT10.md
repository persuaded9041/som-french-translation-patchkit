Secret of Mana FR — second exhaustive dialogue pass — lot 10 checkpoint
Date: 2026-09-14
Canonical lot: $03C5 -> $04B6 (60 accepted events)

Validated changes:
- $0429 / CA:1012: visual reflow only; Android FR prose unchanged.
- $0429 / CA:11C9: visual reflow only; Android FR prose unchanged.
- $04B6: insert TEXT_CLEAR before PLAYER_NAME(2) / CA:237E, after the existing stock WAIT $00; no WAIT or prose added.

Cold regeneration:
- 701 simulator-clean events
- 1959 translated carriers
- Android identity 1798/1838
- 3 validated exclusions

Validation:
- full simulation: 701 events, 0 errors, 0 warnings, 0 implicit wraps
- 3 known WAIT $00 third-line scroll review risks remain globally
- targeted $0429/$04B6 with WWWWWWWWW: 0 errors, 0 warnings, 0 implicit wraps; $04B6 no WAIT-scroll risk
- round-trip: 713 events / 87,487 bytes
- 2048 stock scripts parsable
- source hygiene OK
- strict delta vs lot 9: only CA:1012 + CA:11C9 text carriers changed; one structural insertion added for $04B6
- french_dialogues.ips rebuilt twice byte-identically
- all.ips recombined twice byte-identically

SHA-256:
- translations/dialogues_french.json: 320a48fa835a15e4cc8cb428d8e2a279f4ae8ca751327b0f71357c8e36affcf0
- patches/french_dialogues.ips: fc35b22a6cb667e78f78abc11db43821fb303d89970186ef612851c3bc99a77b
- patches/all.ips: 8b4e39a89294ac2e796b78e4033ee80824857bf9e7253ae4417903d8ddf3ee30

Reference ROM is never included in this checkpoint.
