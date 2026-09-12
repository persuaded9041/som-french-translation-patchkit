# Maintenance target — profile the cleaned dialogue pipeline

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

## Next step: profiling and optimization

Profile `dialogue-format-mass` as it exists now. The current from-scratch run is already dramatically shorter because the cleaned process no longer repeatedly rediscovers reviewed layout cuts; treat that as an architectural consequence, not the end of profiling.

Optimization order:

1. measure the remaining hot functions on a complete canonical run;
2. eliminate redundant work and memoize pure calculations where outputs remain identical;
3. verify `dialogues_french.json` byte-identical after every change;
4. only if meaningful coarse event-local CPU work remains, benchmark deterministic `--jobs N` multiprocessing on the target i5-10600K (start around 4–6 workers);
5. keep serial generation as the reference behavior.

Do not hardcode Android-derived prose, weaken simulation/layout checks, or make generated JSON files into hidden caches.
