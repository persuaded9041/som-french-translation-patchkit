# Android dialogue mapping evidence

This directory contains reproducible correspondence, formatter decisions, review evidence and scene-redistribution metadata for component 08.

```text
assets/            clean-USA canonical source
sources/android/   untouched upstream Android binaries
mappings/android/  alignment / formatter / review evidence
translations/      generated or validated French bound to SNES IDs
```

## Current Round 69 state

- Android-English semantic alignment: **1798 / 1838 (97.8%)**, **40 deliberately unresolved**.
- Simulator-clean payload: **701 events = 701 complete + 0 PARTIEL**.
- Translation output: **1810 accepted semantic source IDs / 1946 JSON entries**.
- Exclusions: **3 alignment-incomplete**, all canonical-routing-audited unused/orphan content: `$0269`, `$02DE`, `$0603`.
- Simulation: **0 errors / 0 warnings / 0 implicit wraps**.
- Reachable dialogue coverage under the audited routing graph: **100% French**.

`docs/HANDOFF.md` is the authoritative operational state. Round-specific review files are historical evidence and must not be used as the current queue or current counters.

## Authoritative files

- `dialogues_auto.json` — conservative SNES ↔ Android-English semantic alignment.
- `dialogues_unmapped.csv` — semantic SNES carriers without Android identity.
- `dialogues_format_mass.json` — formatter/simulator decision trace.
- `dialogues_format_mass_excluded.csv` — the three current unused/orphan exclusions and their reasons.
- `dialogues_redistribution_recipes.json` — **prose-free** recipes for reviewed whole-scene Android-FR resegmentations.
- `dialogue_charset_audit.csv` — Android-French character inventory.
- `dialogue_preview_state.json` — persistent preview badges.
- `dialogues_manual_supplements.html` — generated human-readable review/provenance sheet for the manual supplement JSON.

Component 08 consumes only `translations/dialogues_french.json`. The importer rebuilds reviewed resegmentations directly from `sources/android/scrtxt_fr.bin`; French prose must not be stored in `dialogues_redistribution_recipes.json`. Any genuinely non-Android dialogue French belongs exclusively in `translations/dialogues_manual_supplements.json`.

## Identity policy

Android **English** is the identity layer. Android French supplies localization payload but does not create semantic identity by itself. Manual supplements and whole-scene redistributions likewise do not increase the 1798/1838 alignment count.

The generic automatic candidate index is `scrtxt`-only. Reviewed `systxt` exceptions remain limited to the documented item/chest corrections. Short generic strings are never promoted globally without structural evidence; do not weaken matcher thresholds merely to reduce the unresolved count.

`validated_no_equivalent`, `validated_android_omission` and `validated_contextual_template` are negative/contextual evidence, not Android identities. The 40 unresolved semantic IDs are intentionally retained where identity is not independently proven.

## Manual and redistributed text provenance

`translations/dialogues_manual_supplements.json` contains **18 records = 16 validated translations + 2 validated suppressions + 0 pending**. `$035F/C9:D1B8` is strictly `Dryade`; the older expanded proposal remains withdrawn.

Reviewed Android-FR restructurings are represented only as recipes containing Android IDs/token references, `PLAYER_NAME` references, punctuation and layout/control metadata. `tools/check_dialogue_redistribution_recipes.py` rejects prose in that manifest and verifies the generated payload.

## Historical evidence

`dialogues_review_round*.json`, omission-review JSON and older HTML review snapshots document how earlier decisions were reached. They are evidence only. Historical methodology and detailed round summaries live in `docs/ANDROID_TEXT_ALIGNMENT.md` and `docs/DIALOGUE_FORMAT.md`.

## Current regeneration / checks

```bash
python3 tools/import_android_text.py --only dialogue-auto --check
python3 tools/audit_android_dialogue_charset.py --check
python3 tools/check_dialogue_redistribution_recipes.py
python3 tools/check_manual_dialogue_supplements.py
python3 tools/generate_manual_dialogue_supplements_html.py --check
python3 tools/import_android_text.py --only dialogue-format-mass --rom <clean-USA-ROM> --check
python3 tools/check_round67_targeted_dialogues.py
python3 tools/check_round68_scene_redistributions.py
python3 tools/check_round69_dialogue_completion.py
python3 tools/check_text_source_hygiene.py
python3 tools/check_text_roundtrip.py <clean-USA-ROM> --scan-all-events
python3 tools/simulate_dialogues.py <clean-USA-ROM> -o dialogue_preview.html \
  --issues-csv dialogue_preview_issues.csv \
  --preserve-tags mappings/android/dialogue_preview_state.json
```

Use `docs/HANDOFF.md` before changing dialogue alignment or serialization.
