# Round 85.6 — provenance hygiene + measured safe caches

This checkpoint follows the Round-85.5 architecture cleanup with only small, measured, deterministic improvements.

## Provenance hygiene

The parameterized inn formatter no longer stores either the Android-English sentence or the Android-French prompt as literals. It identifies Android slot 110 structurally, derives/removes its leading numeric price, then derives the sentence/prompt boundary directly from the current Android-FR payload. The generated dialogue corpus remains byte-identical.

## Profiling

A lightweight complete-run profile was used because CPython `cProfile` distorted the ~25 s workload beyond three minutes.

Baseline cleaned mass run: ~24.6–25.2 s in this environment.

Measured alignment hotspots before caching:

- `_auto_metrics`: 468,948 calls / ~5.1 s cumulative;
- `_auto_source_rom_position`: 882,533 calls / ~0.8 s cumulative;
- complete automatic alignment: ~9.3 s.

Safe pure caches retained:

- `normalize_alignment_text` (`lru_cache`);
- `_auto_metrics` (`lru_cache`);
- `_auto_source_rom_position` (`lru_cache`).

Observed after caching:

- `dialogue-auto`: ~5.1–5.3 s;
- complete `dialogue-format-mass`: ~21.8 s;
- generated `dialogues_auto.json`, unmapped CSV and `dialogues_french.json` remain byte-identical.

## Rejected optimization

A per-simulation `_line_metrics` cache was benchmarked because the simulator performs roughly 1.3 million metric calls. Although semantically safe, tuple-key construction made the full mass run slower (~30.4 s), so the change was completely reverted.

## Policy

Do not add broader caching or multiprocessing without a new measured hotspot and byte-identical verification. In particular, do not weaken simulation or turn generated outputs into cache inputs.
