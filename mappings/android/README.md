# Android alignment mappings

This directory stores reproducible correspondence and formatting evidence between the
canonical USA SNES text IDs and the original Android text resources. It stays separate
from source and translated data:

```text
assets/            clean-USA canonical source
sources/android/   untouched upstream Android binaries
mappings/android/  cross-version correspondence/evidence
translations/      generated/validated French text bound to SNES IDs
```

Authoritative current outputs:

- `dialogues_auto.json`: conservative whole-dialogue SNES <-> Android-English mapping;
- `dialogues_unmapped.csv`: the 367 semantic SNES phrases deliberately left unresolved;
- `dialogue_charset_audit.csv`: Android-French character inventory;
- `dialogues_format_mass.json`: full formatter/simulator decision trace;
- `dialogues_format_mass_excluded.csv`: every semantic phrase left out of the current
  mass patch, with its exclusion reason.

The manually reviewed `dialogues_pilot.json` and `dialogues_review_round2..5.json` files
are retained as calibration/regression evidence for the automatic matcher. Superseded
formatting checkpoint reports are not committed; their historical CLI modes can regenerate
them when needed. Component 08 consumes only `translations/dialogues_french.json`.

The accepted alignment resolves 1,471 / 1,838 semantic source IDs (80.0%) and leaves
367 unresolved rather than forcing weak matches. Of 704 semantic text events, 431 are
completely aligned, 417 pass the formatter, and 404 pass the simulator, covering 719
semantic source IDs. The remaining 14 formatter rejects and 13 simulator rejects stay
stock English; every current simulator reject is an interactive choice whose translated
labels would overlap stock option anchors or exceed the selectable row. Android English is the primary identity layer, while Android French may adapt or
redistribute wording across adjacent localization slots.

Regenerate/check the current authoritative stages with:

```bash
python3 tools/import_android_text.py --only dialogue-auto --check
python3 tools/audit_android_dialogue_charset.py --check
python3 tools/import_android_text.py --only dialogue-format-mass --rom <clean-USA-ROM> --check
python3 tools/simulate_dialogues.py <clean-USA-ROM> -o dialogue_preview.html --issues-csv dialogue_preview_issues.csv
```
