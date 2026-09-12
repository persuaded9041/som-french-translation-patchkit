# Development handoff — Round 85.10 dialogue pipeline optimization

Operational handoff. The accompanying archive is authoritative over GitHub.

## Current state

- Reference ROM: unheadered **Secret of Mana (USA)**, `0x200000`, SHA-256 `4c15013131351e694e05f22e38bb1b3e4031dedac77ec75abecebe8520d82d5f`. Never redistribute it.
- Android semantic alignment: **1798 / 1838 (97.8%)**, with 40 deliberately unresolved carriers.
- Playable dialogue corpus: **701 complete events, 0 PARTIEL**, **1947 sparse translation entries**.
- Exclusions: `$0269`, `$02DE`, `$0603`, all routing-audited unused/orphan stock events.
- Static simulation: **0 errors / 0 warnings / 0 implicit runtime wraps**.
- Ordinary line contract: **<= 38 decoded glyphs** and **<= 216 px**. `WAIT != NEWLINE`.
- Manual dialogue supplements: **17 = 15 translated + 2 validated structural suppressions**.
- Round-84 Name Entry remains locked and runtime-validated. Round-85 post-audit dialogue additions are accepted for development; targeted runtime validation is deferred to the next full playthrough.

## Canonical dialogue provenance

`dialogue-format-mass` must be able to regenerate the complete playable French corpus without an existing `translations/dialogues_french.json`. Translated prose comes from the original Android resources at generation time. Never solve a formatter/layout problem by copying French prose from a previously generated dialogue JSON into Python or a recipe.

Canonical inputs are:

- `assets/dialogues.json` — clean-USA SNES event source;
- `sources/android/scrtxt_en.bin` — Android-English identity layer;
- `sources/android/scrtxt_fr.bin` — Android-French localized prose;
- reviewed structural recipes under `mappings/android/`;
- `translations/dialogues_manual_supplements.json` only for genuine reviewed non-Android material/suppressions;
- clean USA ROM for VWF metrics during mass formatting.

Active structural recipe files:

- `dialogues_reviewed_alignment_recipes.json`;
- `dialogues_redistribution_recipes.json`;
- `dialogues_mapping_layout_recipes.json`;
- `dialogues_layout_search_recipes.json`;
- `dialogues_coverage_repair_recipes.json`;
- `dialogues_choice_layout_recipes.json`.

Recipes may store identities, Android token references, SNES carriers, punctuation, case transforms, offsets and layout/control operations. They must **not** store translated prose. `tools/check_text_source_hygiene.py` enforces the key provenance constraints.

Generated outputs/reports include `translations/dialogues_french.json`, `mappings/android/dialogues_auto.json`, `dialogues_unmapped.csv`, `dialogues_format_mass.json` and `dialogues_format_mass_excluded.csv`. They are not source dependencies.

## Active tool surface

`tools/import_android_text.py` now exposes only:

```bash
python3 tools/import_android_text.py --only intro
python3 tools/import_android_text.py --only dialogue-auto
python3 tools/import_android_text.py --only dialogue-format-mass --rom "Secret of Mana (USA).sfc"
```

Historical pilot/review/batch modes were removed. Their useful runtime/identity decisions were consolidated into the canonical alignment and structural recipe layers. Round 85.7 moved reviewed identity tables out of executable Python. Round 85.8 then split the former monolithic importer into `tools/dialogue_pipeline/` modules while keeping `tools/import_android_text.py` as the stable CLI facade. Round 85.9 established the first optimized serial path. Round 85.10 keeps the same architecture and removes a second set of small, measurable sources of repeated work without changing serialized outputs.

Current module boundaries:

- `common.py` — Android binary decoding and shared source/alignment helpers;
- `policies.py` — reviewed non-prose policy constants;
- `alignment.py` — Android/SNES automatic alignment and reviewed-identity integration;
- `recipes.py` — structural recipe loading, validation and Android-token rendering;
- `formatter.py` — dialogue formatting, layout repair, simulation gating and mass-generation orchestration.

`import_android_text.py` is intentionally small and should not reacquire formatter/alignment internals.

A from-scratch mass generation currently reproduces `translations/dialogues_french.json` **byte-for-byte**: 701 complete events / 1947 entries. Reviewed layout-search recipes are tried before generic fallback searches when applicable; every applied recipe is independently simulated, and the historical generic/exhaustive fallback remains available if a recipe no longer fits current Android-derived text.

Round 85.9 prepares the canonical `assets/dialogues.json` text/event index once for the internal shared formatting hot path instead of rebuilding the same index thousands of times. Round 85.10 makes all formatter-owned lookups consistently use that prepared index, prepares repeated source/Android spans once per alignment session, reuses ranking results inside one immutable candidate index, prepares positional-neighborhood evidence once per alignment pass, and keys lexical metric reuse by the normalized strings that actually define the metric. On the checkpoint environment, five canonical mass checks measured **5.72 / 5.78 / 5.86 / 5.77 / 5.84 s** (median **5.78 s**) while all dialogue outputs remained byte-identical. `dialogue-auto` remains fully recomputed from Android/SNES sources and is not replaced by a generated-output cache.

For clean temporary verification, all outputs can be redirected:

```bash
python3 tools/import_android_text.py --only dialogue-format-mass \
  --rom "Secret of Mana (USA).sfc" \
  --output /tmp/dialogues_french.json \
  --format-report /tmp/dialogues_format_mass.json \
  --excluded-csv /tmp/dialogues_format_mass_excluded.csv
```

## Checks after dialogue pipeline changes

```bash
python3 tools/import_android_text.py --only dialogue-format-mass \
  --rom "Secret of Mana (USA).sfc" --check
python3 tools/check_dialogue_regressions.py
python3 tools/check_dialogue_redistribution_recipes.py
python3 tools/check_manual_dialogue_supplements.py
python3 tools/check_text_source_hygiene.py
python3 tools/check_text_roundtrip.py "Secret of Mana (USA).sfc" --scan-all-events
```

Do not reopen dialogue wording/identity without a concrete regression. Do not start object/item translation during maintenance work.

## Next work

Round 85.10 is the optimized serial reference path. Do not add multiprocessing merely because the target PC has many threads: the remaining measured work is dominated by real alignment/scoring and independent simulation rather than obvious repeated-work hotspots, and the serial mass run is already around six seconds. Re-profile only after a functional pipeline change or if generation becomes materially slower. Any future `--jobs N` experiment must remain optional, deterministic and byte-identical to this serial reference.

## French opening builder performance

`components/french_opening/build_patch.py` now keeps the same exact optimal
compression/tie-breaking while avoiding redundant Python-level match scans.
Standalone `french-opening` rebuild time dropped from ~14.7 s to ~3.3 s in the
maintenance benchmark; the generated IPS is byte-identical. See
`docs/OPTIMIZATION_FRENCH_OPENING.md`.
