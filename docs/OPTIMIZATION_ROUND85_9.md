# Round 85.9 — dialogue pipeline optimization

Round 85.9 optimizes the already-modular Round-85.8 dialogue pipeline without changing translation provenance, layout policy, simulator acceptance, or serialized outputs.

## Changes retained

### Shared normalized-token cache

Automatic alignment already cached normalized strings and pair metrics. Many unique comparison pairs still rebuilt token tuples/sets for the same ~9,700 normalized strings. `_auto_metric_tokens()` now memoizes those token views. This is deterministic and contains no translated payload.

### Reviewed layout recipes before failed generic scans

The formatter previously attempted `_try_single_carrier_boundary_newline()` before applying already-reviewed layout-search recipes. On the current corpus those generic searches fail for the recipe-owned events and consumed about 5.3 seconds in profiling, dominated by `$05F8`.

Reviewed recipes are now attempted first where applicable. They are still independently simulated. If a recipe no longer applies, control falls through to the historical generic repair/search path; no fallback capability was removed. `$05F8` keeps its validated live PLAYER_NAME-prefix reflow prerequisite before applying its reviewed plan.

### Prepared immutable source index inside the formatter

`shared.dialogue_translation.event_text_index()` was called 8,536 times during a representative mass run and spent close to ten seconds repeatedly indexing the same immutable parsed `assets/dialogues.json`.

A private `_format_event_text_index()` caches only the last source-document object used by formatting internals. The public `event_text_index()` remains unchanged and uncached for extraction/checking callers. A different document object immediately rebuilds the formatting index.

## Rejected/avoided approaches

- No generated `dialogues_french.json`, `dialogues_auto.json`, or report is used as a source/cache dependency.
- No Android-derived prose was hardcoded.
- No simulator rule was weakened or bypassed.
- No multiprocessing was added: after removal of redundant serial work, the complete mass run is already around seven seconds in this environment and the remaining work is comparatively coarse/real.
- `cProfile` heavily distorted the mass workload, so final decisions used lightweight timing wrappers around major phases/functions plus real wall-clock runs.

## Measurements

Same environment, same Round-85.8 inputs:

- initial Round-85.8 mass run: **21.68 s**;
- after normalized-token memoization alone: about **21.14 s**;
- after recipe-first fallback ordering: about **16.46 s**;
- after prepared formatting index: **6.90 / 7.05 / 6.96 s**, median **6.96 s**.

A representative lightweight profile of the final state attributed roughly ~3.9 s to automatic alignment and ~1.36 s to 993 event simulations. No similarly dominant accidental repeated-work hotspot remained.

## Required invariants

Round 85.9 is valid only while:

- `dialogues_auto.json` and `dialogues_unmapped.csv` reproduce byte-for-byte;
- `dialogues_french.json`, `dialogues_format_mass.json`, and `dialogues_format_mass_excluded.csv` reproduce byte-for-byte;
- generation succeeds with `translations/dialogues_french.json` absent;
- dialogue regression/provenance/supplement/round-trip checks pass;
- rebuilding every component leaves all IPS files byte-identical to Round 85.8.
