# Android alignment mappings

This directory stores reviewed correspondence metadata between canonical USA
SNES text IDs and original Android text IDs.

It is intentionally separate from both source and translation data:

```text
assets/            clean-USA canonical source
sources/android/   untouched upstream Android binaries
mappings/android/  cross-version correspondence/evidence
translations/      generated or validated French text bound to SNES IDs
```

Current files:

- `dialogues_pilot.json`: first validated pilot, including explicit duplicate
  ambiguity examples;
- `dialogues_review_round2.json`: 23 user-validated scene-level units;
- `dialogues_review_round3.json`: 33 user-validated scene-level units;
- `dialogues_review_round4.json`: 37 user-validated diversity-focused units;
- `dialogues_review_round5.json`: user-validated 55-unit stress-test batch, plus explicit unmatched-source observations;
- `dialogues_auto.json`: conservative whole-dialogue correspondence output;
- `dialogues_unmapped.csv`: unresolved semantic SNES phrases with the best Android-English candidates for review;
- `dialogue_charset_audit.csv`: unsupported-character inventory for the accepted Android-French mappings, after layout/placeholder normalization;
- `dialogues_format_pilot_translation.json` / `dialogues_format_pilot.json`: reproducible historical `$0107` runtime checkpoint;
- `dialogues_format_batch1.json`: trace report for the current seven-event formatting candidate.

The whole-game mapping is not consumed wholesale by component 08. The current
`translations/dialogues_french.json` contains only seven semantically complete,
formatter-compatible events selected from it. Android English is the primary identity
layer; French wording may be adapted or redistributed across adjacent slots.
The automatic pass currently resolves 1,471 / 1,838 semantic dialogue source
IDs (80.0%) and deliberately leaves 367 unresolved.

Regenerate or verify the checkpoints with:

```bash
python3 tools/import_android_text.py --only dialogue-pilot --check
python3 tools/import_android_text.py --only dialogue-review --check
python3 tools/import_android_text.py --only dialogue-review-round3 --check
python3 tools/import_android_text.py --only dialogue-review-round4 --check
python3 tools/import_android_text.py --only dialogue-review-round5 --check
python3 tools/import_android_text.py --only dialogue-auto --check
python3 tools/audit_android_dialogue_charset.py --check
python3 tools/import_android_text.py --only dialogue-format-pilot --rom <clean-USA-ROM> --check
python3 tools/import_android_text.py --only dialogue-format-batch1 --rom <clean-USA-ROM> --check
```
