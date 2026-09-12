# HANDOFF — Round 85.39 (persistent generated translation caches)

## Round 85.39 — persistent `text_resources_french.json` cache

`translations/text_resources_french.json` now follows the same local-cache contract as `dialogues_french.json`. A normal `french_resources` build reuses the file only when `build/cache/text_resources_french.meta.json` proves that the clean USA ROM, extracted source-resource document, Android `systxt_en/fr.bin`, reviewed `recipes/android/text_resources_layout.json`, generator code and cached payload all match. Missing, edited or stale caches are regenerated and rewritten atomically from canonical inputs. `reports/android/text_resources_android.json` remains an optional review report and is never consumed by the build. The explicit `tools/text/import_android_resources.py <ROM>` path seeds the same cache metadata when materializing the default French JSON.

This is performance/workflow-only: `french_resources.ips` remains SHA-256 `dc585b3d94a9179136e975b717befa2259a83a76ab7de51227a045acf5490d84`, and `all.ips` remains SHA-256 `a12f3540ba2f086c9833b2503c49ca509957cf8b6cebf106ff98cca729cb290b`.

Operational handoff. The accompanying archive is authoritative over GitHub.


## Round 85.38 — persistent `dialogues_french.json` cache

`translations/dialogues_french.json` is now retained automatically after normal `french_dialogues` generation and reused on later builds when a fingerprint proves it is still valid. The cache fingerprint covers the clean USA ROM, the extracted source dialogue document, Android EN/FR dialogue sources, dialogue recipes/manual supplements, and the relevant shared dialogue/VWF/charset generator code. A missing, edited or stale cache is regenerated from canonical inputs and rewritten atomically. Cache metadata lives under `build/cache/dialogues_french.meta.json`; deleting either cache file is safe and merely forces regeneration. The explicit `tools/dialogue/import_android.py --only dialogue-format-mass` path seeds the same cache metadata when writing the default translation path.

Measured locally on this checkpoint: first standalone generation about 6.3 s; fingerprint-valid cache reuse about 1.1 s. Cache behavior is maintenance/performance-only: `french_dialogues.ips` and `all.ips` remain byte-for-byte identical to Round 85.37.

Operational handoff. The accompanying archive is authoritative over GitHub.


## Round 85.37 — automatic ignored `assets/` cache

The root `assets/` directory remains entirely unversioned, but missing deterministic clean-USA extraction
documents are now persisted automatically instead of existing only in memory. Each `load_or_extract_*()`
helper validates/reuses its JSON cache when present; otherwise it extracts from the supplied clean USA ROM,
writes the JSON atomically, and returns it. A full rebuild warms all eight root caches once; targeted builds
remain lazy and create only the files they consume. `.gitignore` uses `/assets/**` so component-local
`components/*/assets/` sources remain versioned. `tools/text/extract.py` remains the explicit refresh/research CLI.

This is cache/maintenance-only: all component IPS and `all.ips` remain byte-for-byte identical.

Operational handoff. The accompanying archive is authoritative over GitHub.


## Round 85.36 — root `assets/*.json` removed from version control

The eight root JSON assets are deterministic clean-USA ROM extractions and are ignored caches rather than
canonical inputs. Round 85.37 supersedes the original memory-only fallback by persisting missing caches.


## Round 85.35 — minimal manual dialogue supplements

`translations/dialogues_manual_supplements.json` is reduced from the old provenance-heavy v2 review schema to a minimal v3 build manifest. Each translated carrier now stores only `id` + `text`; each validated structural deletion stores only `id` + `suppress: true`. Event ownership, canonical USA source text, active status and policy reason are derived at load time from `assets/dialogues.json` and the exact manual allow-lists. The manifest shrinks from ~20 KB to ~1.6 KB while preserving the same 17 decisions (15 translations + 2 suppressions).

Detailed JP/FR comparison notes, ROM hashes and raw evidence are no longer duplicated in the active build input. The optional manual-supplement HTML reconstructs event IDs and canonical USA text from the source asset and displays the final manual decision only. `tools/dialogue/check_manual_supplements.py` validates the minimal schema, exact carrier set, codec encodability and the two allow-listed suppressions.

This is source/maintenance-only: `french_dialogues.ips` and `patches/all.ips` remain byte-for-byte identical to Round 85.34.

## Round 85.34 — tools/library boundary and layout

`tools/` is now a CLI-only surface organized by domain:

- `tools/dialogue/` — dialogue generation/report materialization, simulation, JP extraction and dialogue-specific checks/audits;
- `tools/text/` — clean-ROM text extraction/round-trip checks, Android `$CA` resource report materialization and text-source/layout audits.

Reusable generation code required by component builders no longer lives under `tools/`. The deterministic dialogue engine moved to `shared/dialogue/pipeline/`, and Android resource mapping/translation generation moved to `shared/text/android_resources.py`. Component builders import only `shared.*`; no component or shared module imports `tools.*`. Android scrtxt/systxt decoding is centralized in `shared/text/android_strings.py`. Old flat `tools/*.py` compatibility wrappers are intentionally not retained.

The migration is organization-only: all 14 standalone component IPS files and `patches/all.ips` remain byte-for-byte identical to Round 85.33.

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
- reviewed structural recipes under `recipes/android/`;
- `translations/dialogues_manual_supplements.json` only for genuine reviewed non-Android material/suppressions;
- clean USA ROM for VWF metrics during mass formatting.

Active structural recipe files:

- `dialogues_reviewed_alignment.json`;
- `dialogues_redistribution.json`;
- `dialogues_mapping_layout.json`;
- `dialogues_layout_search.json`;
- `dialogues_coverage_repair.json`;
- `dialogues_choice_layout.json`.

Recipes may store identities, Android token references, SNES carriers, punctuation, case transforms, offsets and layout/control operations. They must **not** store translated prose. `tools/text/check_source_hygiene.py` enforces the key provenance constraints.

Generated outputs/reports include `translations/dialogues_french.json`, `reports/android/dialogues_auto.json`, `reports/android/dialogues_unmapped.csv`, `reports/android/dialogues_format_mass.json` and `reports/android/dialogues_format_mass_excluded.csv`. They are not canonical source dependencies. `dialogues_french.json` is now retained as a fingerprint-validated local performance cache: a valid copy is reused, while an absent/stale copy is regenerated and persisted automatically.

Round 85.28 removed the generated dialogue/resource translation JSONs from the tracked checkpoint. Round 85.30 completes that policy for the dialogue alignment/formatter reports: `dialogues_auto.json`, `dialogues_unmapped.csv`, `dialogues_format_mass.json` and `dialogues_format_mass_excluded.csv` are now ignored and absent too. `check_dialogue_regressions.py` regenerates alignment + mass-format documents in memory from canonical inputs, and `audit_android_dialogue_charset.py` regenerates alignment in memory by default. No normal check path requires these generated files. The `french_dialogues` build may consume `dialogues_french.json` only as a fingerprint-validated cache; canonical inputs remain sufficient to regenerate it.

## Active tool surface

`tools/dialogue/import_android.py` now exposes only:

```bash
python3 tools/dialogue/import_android.py --only intro
python3 tools/dialogue/import_android.py --only dialogue-auto
python3 tools/dialogue/import_android.py --only dialogue-format-mass --rom "Secret of Mana (USA).sfc"
```

Historical pilot/review/batch modes were removed. Their useful runtime/identity decisions were consolidated into the canonical alignment and structural recipe layers. Round 85.7 moved reviewed identity tables out of executable Python. Round 85.8 then split the former monolithic importer into `shared/dialogue/pipeline/` modules while keeping `tools/dialogue/import_android.py` as the stable CLI facade. Round 85.9 established the first optimized serial path. Round 85.10 keeps the same architecture and removes a second set of small, measurable sources of repeated work without changing serialized outputs.

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
python3 tools/dialogue/import_android.py --only dialogue-format-mass \
  --rom "Secret of Mana (USA).sfc" \
  --output /tmp/dialogues_french.json \
  --format-report /tmp/dialogues_format_mass.json \
  --excluded-csv /tmp/dialogues_format_mass_excluded.csv
```

## Checks after dialogue pipeline changes

```bash
python3 tools/dialogue/check_regressions.py --rom "Secret of Mana (USA).sfc"
python3 tools/dialogue/check_redistribution_recipes.py
python3 tools/dialogue/check_manual_supplements.py
python3 tools/text/check_source_hygiene.py
python3 tools/text/check_roundtrip.py "Secret of Mana (USA).sfc" --scan-all-events
```

Do not reopen dialogue wording/identity without a concrete regression. Do not start object/item translation during maintenance work.

## Next work

The component-by-component audit and the folder-by-folder `shared/` audit are complete. Continue repository-wide consolidation only: root documentation/manifests, tools organization, generated-output policy and dead historical references. Do not reopen runtime-validated functionality without a concrete regression, and do not begin the next translation feature phase during this maintenance pass.

## Round 85.31 — recipes/reports layout cleanup

- Moved the seven canonical Android structural inputs from `mappings/android/` to `recipes/android/` and removed the redundant `_recipes` suffix from their filenames.
- Removed the old `mappings/` root entirely.
- Generated Android JSON/CSV/HTML review outputs now default to `reports/android/`, which is ignored and non-canonical.
- Normal builds/checks consume only canonical inputs from `recipes/android/`; no generated report is required.

## Round 85.32 — shared-library refactor

- Replaced the flat `shared/` module pile with responsibility-based packages: `core/`, `build/`, `text/`, `dialogue/`, `vwf/`, `name_entry/` and `charset/`.
- Renamed modules inside those packages to remove redundant prefixes (`vwf_*`, `dialogue_*`, `*_text`) where the package already supplies the context.
- Moved readable ASM mirrors beside their executable Python modules. They remain documentation/reference, not parallel build sources.
- Kept aggregate compatibility rules outside `core/` because they intentionally depend on domain-specific charset/Name Entry knowledge.
- Removed two unreferenced public helper functions (`decode_japanese_text` and `decode_text_bytes_with_dte_threshold`) after repository-wide reference checks.
- Added `shared/README.md` documenting ownership and dependency direction. No compatibility aliases for the former flat import paths are retained; all repository consumers use the new package paths directly.


## Round 85.33 — shared folder-by-folder audit

- Audited `core/`, `build/`, `charset/`, `text/`, `dialogue/`, `name_entry/` and `vwf/` individually after the Round-85.32 package split.
- `core/` required no structural refactor and remains dependency-clean.
- `build/components.py` now validates manifest field types, duplicate dependencies, override ranges/reasons and override dependency ownership during discovery.
- `charset/charset.py` now validates canonical glyph/code/profile invariants at import time and uses a precomputed atlas index.
- Dialogue-only structural translation metadata moved from `text/translation_json.py` to `dialogue/structure.py`; the generic text binder is generic again.
- Event command-length decoding is centralized in `dialogue/codec.py` and reused by the Japanese extractor and simulator.
- Formatter-facing helpers in `dialogue/translation.py` that are intentionally consumed outside the module now have public names instead of underscore-prefixed imports.
- `vwf/framing.py` now uses `shared.core.asm.MiniAssembler`; the emitted framing bundle remains byte-identical. `vwf/renderer_runtime.py` is now the executable source of the helpers shared by `vwf_dialogues` and `vwf_ui`, replacing the former generated-code + frozen-hex duplication, and checks every shared ED-bank helper against the next reserved allocation.
- No runtime behavior or patch payload was intentionally changed; all patches must remain byte-for-byte identical to Round 85.32.
