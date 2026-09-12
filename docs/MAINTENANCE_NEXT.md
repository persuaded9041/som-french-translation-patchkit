# Maintenance target — Round 85.10 optimized serial dialogue pipeline

`docs/HANDOFF.md` is the authoritative operational state.

## Cleanup completed

- `artifacts/` and obsolete generated review snapshots are gone.
- historical pilot/review/batch CLI modes have been removed from `import_android_text.py`.
- old round-specific formatter payloads were migrated to structural Android-token recipes.
- layout-search decisions already reviewed by the user are represented as structural strategy/carrier/offset recipes with simulator validation and exhaustive fallback.
- `dialogues_french.json` is proven regenerable from scratch and remains a generated output only.
- temporary mass runs can redirect translation, report and exclusion CSV outputs outside the repository.
- text-source hygiene now checks the dialogue recipe/provenance architecture.

## Source / recipe / output model

**Sources:** clean-USA assets, Android EN/FR binaries, clean USA ROM metrics.

**Human-reviewed structural inputs:** the six dialogue recipe JSON families plus the small manual-supplement file for genuine non-Android exceptions.

**Generated outputs:** `dialogues_french.json`, `dialogues_auto.json`, unmapped/exclusion CSVs and mass-format reports. None should be required to generate another output.

## Profiling checkpoint

Round 85.6 measured the cleaned canonical path. Pure memoization of alignment normalization/metrics/ROM-position decoding reduced `dialogue-auto` from about 9.3 s to about 5.2 s and the complete mass run from about 25.2 s to about 21.8 s in the checkpoint environment, with byte-identical outputs. A per-simulation line-metrics cache was rejected because it regressed the mass run to about 30.4 s.

## Refactor checkpoint after Round 85.6

Before further performance work, reviewed alignment history was moved out of executable Python into `dialogues_reviewed_alignment_recipes.json`. The importer no longer embeds `DIALOGUE_REVIEW_ROUND*` tables or round-named active helpers. Redistribution and mapping-layout recipes now share one Android-token renderer and one recipe-document validator. Static call-graph audit reports every top-level importer function reachable from the active CLI. Outputs remain byte-identical.


## Round 85.8 modular split

The historical `tools/import_android_text.py` monolith is now a thin compatibility CLI facade (~500 lines). Dialogue internals live under `tools/dialogue_pipeline/`: `common.py`, `policies.py`, `alignment.py`, `recipes.py`, and `formatter.py`. The split is mechanical: algorithms and serialized outputs are unchanged. Existing user commands remain valid. Checkers now target the owning modules instead of importing private helpers from the CLI facade, and text-source hygiene scans the whole pipeline package.

This is the final planned maintainability refactor before performance work. Do not fragment `formatter.py` further unless profiling or a concrete maintenance problem gives a clear module boundary; avoid decomposition for line-count aesthetics alone.

## Round 85.9 optimization result

Profiling the modular Round-85.8 path found two dominant forms of repeated work:

1. Reviewed layout-search events still ran generic carrier-boundary searches first, even though those searches were known to fail before the validated structural recipe was reached. Round 85.9 tries the independently simulated reviewed recipe first, then falls back to the previous generic sequence if the recipe has drifted. This especially removes repeated multi-second scans on `$05F8`.
2. The shared formatter rebuilt the complete `text ID -> event/token` index of the immutable canonical dialogue source thousands of times. Round 85.9 keeps a one-document private formatting index while leaving public `event_text_index()` behavior unchanged.

A small cache of tokenized normalized alignment strings was also retained; it avoids repeated `split()/set` work across the same normalized Android/SNES strings.

Measured checkpoint results in this environment:

- Round 85.8 mass baseline: about **21.68 s**;
- Round 85.9 mass runs: **6.90 / 7.05 / 6.96 s** (median **6.96 s**);
- all five dialogue outputs remain byte-identical;
- all 14 component patches and `all.ips` remain byte-identical.

The remaining profile is no longer dominated by accidental repeated work: alignment is roughly ~4 s and independent simulation ~1.3 s on a representative run. Stop here rather than complicating the pipeline for small gains. Multiprocessing is not warranted at this checkpoint; reconsider only after a future functional change or on evidence from the actual i5-10600K target.
## Round 85.10 second conservative optimization pass

A second profile of Round 85.9 found several smaller but still clear sources of redundant serial work. The retained changes are intentionally local and maintenance-friendly:

- `_auto_align_session()` prepares each short SNES span and Android span once per session instead of rebuilding the same strings across the dynamic-programming grid;
- `_AutoCandidateIndex.rank()` reuses rankings for the same normalized source/limit inside one immutable candidate index;
- repeated positional tie-break probes flatten their immutable context records once per pass instead of rebuilding the same evidence list for every target;
- lexical metric caching is keyed by normalized source/candidate forms, which are the actual inputs to the metric;
- alignment hot paths that already hold normalized strings call the normalized metric helper directly;
- formatter-internal source-index lookups consistently use the existing prepared immutable formatting index.

No simulator state or acceptance rule was changed. An incremental simulator-metrics redesign was deliberately avoided because it would increase maintenance risk for a comparatively small remaining hotspot. No multiprocessing or generated-output cache was introduced.

Measured mass `--check` runs in the checkpoint environment: **5.72 / 5.78 / 5.86 / 5.77 / 5.84 s**, median **5.78 s**. A strict run with `translations/dialogues_french.json` physically absent rebuilt the exact 264,463-byte file in **5.64 s**. All five dialogue outputs and all component IPS files remain byte-identical to Round 85.9.

## Next step

Treat Round 85.10 as the serial performance reference. Further optimization should require a new concrete hotspot or a material slowdown; do not pursue simulator incremental-state changes or multiprocessing merely for benchmark aesthetics.
