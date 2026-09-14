# HANDOFF — Secret of Mana FR — dialogue corpus frozen after third exhaustive pass

Date: 2026-09-14

This archive is authoritative over GitHub. The reference ROM is **Secret of Mana (USA), unheadered** and must never be redistributed.

## Current promoted dialogue state

The third and final independent exhaustive playable-dialogue pass is complete. It reviewed the accepted playable corpus event-by-event in 12 lots, focusing on cross-event continuity, real dialogue-box state, event-command timing, speaker attribution, Android-FR redistribution, small carriers, choices and possible side effects from the first two passes.

**No dialogue change was required in any of the 12 lots.** The strict global validation proves that the generated dialogue document is byte-for-byte identical to the clean second-pass checkpoint.

Final verified state:

- **701/701** accepted playable events simulator-clean
- **1959 translated carriers**
- Android alignment identity **1798/1838**
- **0 errors / 0 warnings / 0 implicit wraps**
- speaker-label guardrail: **0 findings**
- rolling-scroll discovery guardrail: **0 new candidates**
- redistribution: **302 active carriers**, 0 simulator-filtered
- manual supplements: **17 carriers = 15 translations + 2 suppressions**
- source round-trip: **713 events / 87,487 bytes**
- all **2048 stock event scripts** parse successfully
- source hygiene clean
- cold regeneration byte-identical
- double build reproducible

Final SHA-256:

- `translations/dialogues_french.json`: `3e4cacd926e31d6dfe9f9021d1026c4f71dc68ccd88ce4481749e47764d2b7d9`
- `patches/french_dialogues.ips`: `dfc94882e4162052ccd7195839ef7ef7f5a89f1bec51847d905ca6b05ad2de31`
- `patches/all.ips`: `49eb639aa0117d603c5cd6c92ba617f6c853da68cead59c34cf970658e94fd23`

## Third-pass non-regression proof

Against the exact promoted starting checkpoint:

- starting carriers: **1959**
- final carriers: **1959**
- changed carriers: **0**
- carriers added: **0**
- carriers removed: **0**
- top-level semantic/source metadata changes: **0**

A fresh cold `dialogue-format-mass` regeneration reproduced the promoted JSON byte-for-byte. Full simulation with the normal worst-case name and with `WWWWWWWWW` both produced 701 events, 0 errors, 0 warnings and 0 implicit wraps. The three global WAIT-$00 third-line review risks are historical reviewed informational cases, not new findings.

Two independent rebuilds of `french_dialogues.ips` are byte-identical to each other and to the promoted patch. Two independent recombinations of `all.ips` likewise match the promoted patch exactly.


## Core invariants

- Android FR remains the primary prose source.
- No localized French prose is hard-coded in formatter/layout recipes.
- `WAIT != NEWLINE`.
- Maximum 3 live lines, <=216 px, <=38 decoded characters.
- Dynamic names must remain valid for the 9-character worst case.
- `$0360` remains neutralized.
- `$035F / C9:D1B8` remains `Dryade fera réagir l'orbe !`.
- Android `%S(...)` vocatives remain real `PLAYER_NAME` commands.
- `$066D / CA:8D4B` remains the explicitly validated WAIT-only controlled-scroll case; controlled scrolling is a manual layout decision, not a global rewrite rule.
- Existing choice/highlight geometry and timed event commands must be preserved unless a concrete runtime defect is demonstrated.

## Canonical dialogue inputs

`translations/dialogues_french.json` is a generated, fingerprint-validated cache/review artifact, not canonical prose provenance. Canonical dialogue generation uses the Android EN/FR sources, clean-USA extraction, reviewed alignment/redistribution metadata, manual supplements and structural/layout recipes.

The active dialogue recipe surface under `recipes/android/` remains:

- `dialogues_reviewed_alignment.json`
- `dialogues_redistribution.json`
- `dialogues_formatting.json`
- `dialogues_review.json`

## Status / next work

The playable dialogue corpus is now **frozen**. Do not run another exhaustive dialogue pass unless a concrete in-game, serialization, source-identity, caller/sub-event or layout defect is observed.

The next planned project subject remains the **items/objects translation procedure**, beginning with design/discussion before changing translation data.
