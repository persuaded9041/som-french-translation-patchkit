# Android dialogue mapping data

This directory deliberately contains only data that is still useful to the active
pipeline or to current regression checks. Historical review snapshots belong in Git
history, not in the working tree.

```text
assets/            clean-USA canonical source
sources/android/   untouched upstream Android binaries
mappings/android/  active recipes, reproducible mapping/cache data, current guardrail reports
translations/      generated or explicitly validated French bound to SNES IDs
```

## Canonical structural inputs

These files encode reviewed project decisions and must remain versioned:

- `dialogues_redistribution_recipes.json` — prose-free whole-scene Android-FR resegmentation recipes;
- `dialogues_coverage_repair_recipes.json` — prose-free coverage repair recipes;
- `dialogues_choice_layout_recipes.json` — reviewed choice-layout decisions;
- `text_resources_layout.json` — prose-free text-resource layout recipes.

Genuinely non-Android French prose belongs only in
`translations/dialogues_manual_supplements.json`.

## Reproducible mapping / current guardrail data

These are generated from canonical inputs, but are still retained because current
checks or downstream tooling consume them:

- `dialogues_auto.json` — conservative SNES ↔ Android-English semantic alignment;
- `dialogues_unmapped.csv` — unresolved semantic carriers emitted with that alignment;
- `dialogues_format_mass.json` — formatter/simulator decision trace;
- `dialogues_format_mass_excluded.csv` — current unused/orphan exclusions;
- `text_resources_android.json` — Android text-resource identity/provenance trace.

They are **not** permission to use generated French output as an input. In particular,
`translations/dialogues_french.json` remains a generated product and may be absent from
a clean checkout in the future.

The next maintenance step is to reduce the remaining checker/importer coupling to these
generated mapping files so they can eventually become optional caches or outputs.

## Small persistent review state

- `dialogue_preview_state.json` stores intentionally persistent preview tags/badges.
- `dialogues_manual_supplements.html` is the one current human-readable provenance
  sheet retained for the active manual-supplement set. It is deterministically generated
  and may later move to fully ephemeral output once its checker no longer requires an
  on-disk reference copy.

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
python3 tools/import_android_text.py --only dialogue-auto --check
python3 tools/check_dialogue_redistribution_recipes.py
python3 tools/check_manual_dialogue_supplements.py
python3 tools/generate_manual_dialogue_supplements_html.py --check
python3 tools/import_android_text.py --only dialogue-format-mass --rom <clean-USA-ROM> --check
python3 tools/check_dialogue_regressions.py
python3 tools/check_text_source_hygiene.py
python3 tools/check_text_roundtrip.py <clean-USA-ROM> --scan-all-events
```

Optional reports should be written only when needed, for example:

```bash
python3 tools/audit_android_dialogue_charset.py --output /tmp/dialogue_charset_audit.csv
python3 tools/import_android_resources.py --html /tmp/text_resources_android_review.html
python3 tools/audit_text_resource_layout.py <clean-USA-ROM> \
  --json /tmp/text_resources_layout_audit.json \
  --html /tmp/text_resources_layout_audit.html
```

## Non-event `$CA` system resources

`tools/import_android_resources.py` remains the deterministic Android `systxt` bridge for
`assets/text_resources.json`. It emits `text_resources_android.json` plus
`translations/text_resources_french.json`; optional HTML review output is ephemeral.
