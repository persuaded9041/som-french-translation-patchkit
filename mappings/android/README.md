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
- `dialogues_unmapped.csv`: the 237 semantic SNES phrases deliberately left unresolved;
- `dialogue_charset_audit.csv`: Android-French character inventory;
- `dialogues_format_mass.json`: full formatter/simulator decision trace;
- `dialogues_format_mass_excluded.csv`: every semantic phrase left out of the current
  mass patch, with its exclusion reason.

The manually reviewed `dialogues_pilot.json` and `dialogues_review_round2..5.json` files
are retained as calibration/regression evidence for the automatic matcher.
`dialogues_review_round6.json` through `dialogues_review_round22.json` record the current structural-review evidence separately
from the generated auto-alignment output. Superseded
formatting checkpoint reports are not committed; their historical CLI modes can regenerate
them when needed. Component 08 consumes only `translations/dialogues_french.json`.

`dialogue_preview_state.json` is the single active review-state snapshot for the HTML
preview. It preserves unread `NEW`, `MODIFIED` and `TO REVIEW` badges across technical
regenerations. Older round-numbered preview-state and one-off layout-audit snapshots were
removed during cleanup; their accepted conclusions are documented in the dialogue docs and
implemented by the current formatter/simulator.

The accepted alignment resolves 1,601 / 1,838 semantic source IDs (87.1%) and leaves
237 unresolved rather than forcing weak matches. The established complete-event path
contains 498 events treated as complete. A simulator-gated partial pass accepts 2 PARTIEL events while
suppressing 3 still-unresolved semantic IDs from visible dialogue, so PARTIEL scenes remain
French-only even when semantically incomplete. The current corpus therefore contains
500 events / 1066 visible French semantic source IDs / 1119 JSON entries. The remaining exclusions are 171 alignment-incomplete events, 17 formatter
rejects and 16 simulator rejects. Unresolved choice geometry remains rejected rather
than guessed; `$0202` remains separately rejected for visible-bitmap overflow.
Android English is the primary identity layer, while Android French may adapt or
redistribute wording across adjacent localization slots.


Round 21 resolves three conservative PARTIEL resegmentation cases without manual French:
`$01E5` binds the existing `PLAYER_NAME(1)` carrier to Android 668, `$0609` splits the
merged Android 415 direction row back across the stock `$D1/$D2` glyph structure, and
`$0167` redistributes Android 1058/1059 around the stock `WAIT $00` + `PLAYER_NAME(1)`
bridge. All localized wording comes directly from Android French; structural commands are
kept in place and the final event bytes remain simulator-gated.

Round 22 resolves `$01DD`, `$02AE` and `$07FE` from structural Android-English evidence
only. It preserves both dynamic-name command sequences, preserves `$02AE`'s stock
`WAIT $10`, and uses only Android-French text already present in slots 616/619/620,
1630 and 3399/3401/3406. All three remain `TO REVIEW` until runtime validation.

Round 23 records the user-validated Android omission at `$01DC`: Android 729 starts the
following Niccolo scene immediately after 728, so the final SNES-only
`PLAYER_NAME(0) + C9:804A` reaction is omitted as one exact structural unit.
No semantic mapping or manual French is invented for the missing reply.

Round 11 applies the same user-derived PARTIEL logic to ordered local Android-English
blocks: exact neighboring gaps, Android expansion of a SNES fragment, and multiple
consecutive SNES fragments collapsed into one Android anchor. It adds 31 semantic IDs
to the visible corpus while deliberately leaving short generic choices/destinations and
layout-unsafe bindings unresolved.

The structural reviews add two high-confidence correspondence families that the
lexical matcher intentionally cannot infer by itself: Android speaker/staging
redistribution and SNES prompt+choice blocks split into adjacent Android localization
records. Round 6 records 30 structural units. Round 7 adds 18 more ordered-block units,
including two provenance corrections where globally exact short labels (`Kakkara` and
`Sure!`) belonged to the wrong Android scene. That checkpoint left **322 semantic source IDs unresolved**; subsequent structural reviews reduce the current total to **237**. Short choice labels are never matched globally without their
ordered prompt/options context. Semantic identity remains separate from layout safety:
newly completed Cannon/Neko choice events may still be simulator-rejected when their
French labels conflict with stock `CHOICE_OPTION` anchors.

Regenerate/check the current authoritative stages with:

```bash
python3 tools/import_android_text.py --only dialogue-review-round6 --check
python3 tools/import_android_text.py --only dialogue-review-round7 --check
python3 tools/import_android_text.py --only dialogue-auto --check
python3 tools/audit_android_dialogue_charset.py --check
python3 tools/import_android_text.py --only dialogue-format-mass --rom <clean-USA-ROM> --check
python3 tools/simulate_dialogues.py <clean-USA-ROM> -o dialogue_preview.html --issues-csv dialogue_preview_issues.csv
```
