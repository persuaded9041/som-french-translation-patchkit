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

These files encode reviewed project decisions and must remain versioned:

- `dialogues_reviewed_alignment.json` — user-validated SNES/Android identity/provenance recipes;
- `dialogues_redistribution.json` — prose-free whole-scene Android-FR resegmentation recipes;
- `dialogues_coverage_repair.json` — prose-free coverage repair recipes;
- `dialogues_mapping_layout.json` — mapping-local Android-token/layout recipes;
- `dialogues_layout_search.json` — reviewed structural layout-search operations;
- `dialogues_choice_layout.json` — reviewed choice-layout decisions;
- `text_resources_layout.json` — prose-free text-resource layout recipes.

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

`translations/dialogues_french.json` and `translations/text_resources_french.json` follow
the same rule: deterministic review outputs, never build sources.

## Manual supplement review sheet

`reports/android/dialogues_manual_supplements.html` is a deterministic on-demand review rendering of
`translations/dialogues_manual_supplements.json`. It is ignored by Git and is not read by
any build or regression check. Generate it only when a human review sheet is useful.

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
