# Secret of Mana FR — second exhaustive dialogue pass — final checkpoint

Date: 2026-09-14

## Scope

- 12 lots, covering all 701 accepted playable dialogue events.
- Lot sizes: 60 events for lots 1–11, 42 events for lot 12.
- Reference ROM: Secret of Mana (USA), unheadered; never redistributed.

## Final state

- 701/701 playable events simulator-clean.
- 1959 translated carriers.
- Android identity: 1798/1838.
- 0 errors / 0 warnings / 0 implicit wraps.
- Dynamic speaker-label newline audit: 0 findings.
- Rolling-scroll discovery audit: 0 remaining candidates under the current reviewed guardrail.
- Redistribution: 302 active carriers; 0 simulator-filtered.
- Round-trip: 713 events / 87,487 bytes.
- 2048 stock scripts parsable.
- Manual supplement schema: v3 minimal; 17 carriers; 15 translations + 2 suppressions.
- Source hygiene: clean.

## Delta from the second-pass starting checkpoint

The exact starting hashes were re-read from the handoff archive and match the declared baseline:

- dialogues_french.json: `4c71ee39ef1c10acbff1934401afdb4ded788bb525b7282c5a8227606863be82`
- french_dialogues.ips: `006281fc3240ccef2ab10abe0d3a307ed274d13ab58d62a52503776c64b06c79`
- all.ips: `a4510f1675a9b0be80518961338d847b3218f296dfa74032954b6b79570dc2e4`

Carrier-level comparison between the starting and final `dialogues_french.json`:

- 1959 carriers at start.
- 1959 carriers at finish.
- 46 carriers changed.
- 0 carriers added.
- 0 carriers removed.

Every carrier delta belongs to a lot explicitly reviewed/validated during the second pass. Per-lot strict comparisons were performed before each checkpoint.

Structural comparison against the starting translation document:

- structural-command insertions: 15 -> 20 event records; 5 newly validated records, 0 removed;
- structural-command overrides: 27 -> 29 event records; additions correspond to validated vocative omissions, with the existing `$0112` record extended rather than duplicated;
- choice-option position overrides: unchanged (19 -> 19).

No unexpected structural removal was found.

## Controlled scrolling

`$066D / CA:8D4B` is explicitly validated as a WAIT-only controlled-scroll case and is regression-locked. The generic full simulation still reports three known WAIT-$00 third-line review risks globally; these are reviewed/known cases, not simulation errors or warnings. The dedicated rolling-scroll discovery scan finds 0 new candidates.

## Final reproducibility

A final cold regeneration was run from the canonical Android EN/FR sources plus clean-USA extraction, followed by regression checks, manual-supplement validation, redistribution validation, source hygiene, complete round-trip checks, complete simulation, speaker-label audit and rolling-scroll candidate audit.

`french_dialogues.ips` was then rebuilt twice independently and the two files were byte-identical. `all.ips` was recombined twice and the two files were byte-identical.

Final SHA-256:

- `translations/dialogues_french.json`: `3e4cacd926e31d6dfe9f9021d1026c4f71dc68ccd88ce4481749e47764d2b7d9`
- `patches/french_dialogues.ips`: `dfc94882e4162052ccd7195839ef7ef7f5a89f1bec51847d905ca6b05ad2de31`
- `patches/all.ips`: `49eb639aa0117d603c5cd6c92ba617f6c853da68cead59c34cf970658e94fd23`

This checkpoint contains no ROM.
