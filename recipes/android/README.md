# Android structural recipes

This directory deliberately contains only data that is still useful to the active
pipeline or to current regression checks. Historical review snapshots belong in Git
history, not in the working tree.

```text
assets/            clean-USA canonical source
sources/android/   untouched upstream Android binaries
recipes/android/  canonical structural recipes
reports/android/  ignored on-demand review/audit outputs
translations/      generated or explicitly validated French bound to SNES IDs
```

## Canonical structural inputs

The active recipe surface is intentionally small. Dialogue recipes are grouped by responsibility instead of historical round/stage files:

- `dialogues_reviewed_alignment.json` — user-validated SNES/Android identity and provenance;
- `dialogues_redistribution.json` — prose-free whole-scene Android-FR resegmentation;
- `dialogues_formatting.json` — intermediate formatting recipes, with sections `mapping_layout`, `layout_search`, `choice_layout`, and `coverage_repair`;
- `dialogues_review.json` — late validated replay, with sections `final_layout`, `final_structure`, `post_structure_layout`, and `review_delta`;
- `text_resources_layout.json` — prose-free non-dialogue text-resource layout recipes;
- `battle_text_mapping.json` — reviewed battle/status SNES↔Android identity plus runtime composition strategy; French payload remains in Android binaries or explicit reviewed surcharges.

The consolidated files preserve the former section schemas and application order. They contain no localized prose; Android-FR words are still read from `sources/android/scrtxt_fr.bin` during generation. Historical per-stage recipe files belong in Git history, not the working tree.

A rule-liveness pass also removed 15 obsolete/superseded rule units from the consolidated data. The current files intentionally contain only rules that still participate in the canonical generation path; see `reports/RECIPES_CLEANUP.md` for the audited removals and the few apparent overlaps that are intentionally retained.

Genuinely non-Android French prose belongs only in
`translations/dialogues_manual_supplements.json`.

## Generated reports

The following are deterministic **on-demand outputs** under `reports/android/` and are ignored by Git:

- `dialogues_auto.json` — conservative SNES ↔ Android-English semantic alignment;
- `dialogues_unmapped.csv` — unresolved semantic carriers emitted with that alignment;
- `dialogues_format_mass.json` — formatter/simulator decision trace;
- `dialogues_format_mass_excluded.csv` — current unused/orphan exclusions;
- `text_resources_android.json` — Android text-resource identity/provenance trace.

No checker or component build requires these files to exist. Regression checks regenerate
the relevant documents in memory from canonical inputs. Materialize the files only for
inspection, diffs or review.

`translations/dialogues_french.json` and `translations/text_resources_french.json` are
deterministic local performance caches/review outputs, never canonical sources. Builders
reuse them only through fingerprint-validated cache layers and regenerate them from
canonical inputs when absent, edited or stale.

## Manual supplement review sheet

`reports/android/dialogues_manual_supplements.html` is a deterministic on-demand
review rendering of the minimal manual manifest plus canonical USA source text from
`assets/dialogues.json`. It is ignored by Git and is not read by any build or
regression check. Generate it only when a human review sheet is useful.

## Generated on demand, not versioned

Historical round HTML, pilot snapshots, charset CSVs, resource-layout audit HTML/JSON,
and focused review pages are no longer kept in the repository. Generate them into a
working/output path when needed. `.gitignore` prevents the former default report paths
from being accidentally recommitted.

## Current state

- Android-English semantic alignment: **1798 / 1838 (97.8%)**, **40 deliberately unresolved**.
- Reachable dialogue corpus: **701 complete events, 0 PARTIEL**.
- Reachable dialogue coverage under the audited routing graph: **100% French**.
- The three alignment-incomplete exclusions remain audited unused/orphan content:
  `$0269`, `$02DE`, `$0603`.

`docs/HANDOFF.md` is authoritative for the current operational state.

## Current regeneration / checks

```bash
python3 tools/dialogue/check_redistribution_recipes.py
python3 tools/dialogue/check_manual_supplements.py
python3 tools/dialogue/generate_manual_supplements_html.py
python3 tools/dialogue/check_regressions.py --rom <clean-USA-ROM>
python3 tools/text/check_source_hygiene.py
python3 tools/text/check_roundtrip.py <clean-USA-ROM> --scan-all-events
```

Materialize dialogue alignment/format reports only when needed, preferably outside the repository:

```bash
python3 tools/dialogue/import_android.py --only dialogue-auto \
  --output /tmp/dialogues_auto.json --unmapped-csv /tmp/dialogues_unmapped.csv
python3 tools/dialogue/import_android.py --only dialogue-format-mass --rom <clean-USA-ROM> \
  --output /tmp/dialogues_french.json \
  --format-report /tmp/dialogues_format_mass.json \
  --excluded-csv /tmp/dialogues_format_mass_excluded.csv
```

Optional reports should likewise be written only when needed, for example:

```bash
python3 tools/dialogue/audit_charset.py --output /tmp/dialogue_charset_audit.csv
python3 tools/text/import_android_resources.py --html /tmp/text_resources_android_review.html
python3 tools/text/audit_resource_layout.py <clean-USA-ROM> \
  --json /tmp/text_resources_layout_audit.json \
  --html /tmp/text_resources_layout_audit.html
```

## Non-event `$CA` system resources

`tools/text/import_android_resources.py` remains the deterministic Android `systxt` bridge for
`assets/text_resources.json`. It can emit `reports/android/text_resources_android.json` plus
`translations/text_resources_french.json`; optional HTML review output is ephemeral.
