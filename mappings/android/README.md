# Android dialogue alignment mappings

This directory stores reproducible correspondence and formatter evidence between canonical USA SNES dialogue carriers and the original Android text resources.

```text
assets/            clean-USA canonical source
sources/android/   untouched upstream Android binaries
mappings/android/  alignment / review / formatter evidence
translations/      generated or validated French bound to SNES IDs
```

## Current authoritative outputs

- `dialogues_auto.json` — conservative SNES ↔ Android-English semantic alignment;
- `dialogues_unmapped.csv` — semantic SNES carriers still without Android identity;
- `dialogues_format_mass.json` — formatter/simulator decision trace;
- `dialogues_format_mass_excluded.csv` — events/carriers excluded from the current mass pass and why;
- `dialogue_charset_audit.csv` — Android-French character inventory;
- `dialogue_preview_state.json` — persistent `NEW`, `MODIFIED` and `TO REVIEW` badges for HTML previews.

Component 08 consumes only `translations/dialogues_french.json`. Round-specific `dialogues_review_round*.json` files are accepted/reproducible evidence, not alternate translation sources. Historical methodology and round summaries live in `docs/ANDROID_TEXT_ALIGNMENT.md`; current operational state lives in `docs/HANDOFF.md`.

## Current Round 62 state

- alignment: **1798 / 1838 (97.8%)**, **40 unresolved**;
- simulator-clean corpus: **691 events = 668 complete + 23 PARTIEL**;
- **1678 accepted semantic source IDs / 1772 translation JSON entries**;
- exclusions: **10 alignment-incomplete + 2 formatter-rejected + 1 simulator-rejected**;
- simulation: **0 errors / 0 warnings / 0 implicit wraps**;
- Round 63 keeps Android identity frozen and validates suppression of the standalone `$04E1/CA:2C84` USA page. Its JP/US/FR provenance stays in the manual supplement file; only the adjacent `WAIT $00` is omitted with the empty carrier, while `TEXT_CLEAR` and `CA:2C93` remain.

Round 47 changes no semantic mapping, French payload or IPS relative to Round 46. It formalizes negative evidence for 14 carriers in `dialogues_review_round47.json` by combining the event-call graph, map-trigger table `$084000` and map-object pointer table `$087000`.

Round 48 changes formatting/payload admission only, not Android identity. `dialogues_review_round48.json` records seven exact Android-FR-only vocative removals, exact `$0127` pagination, and the live Tasnica `$02E1/C9:C56C` as `validated_android_omission`. The seven vocative repairs never create or move a SNES `PLAYER_NAME`; they only remove a dynamic addressee introduced by Android FR where both Android EN and the SNES carrier lack one. Round 49 also changes no identity and adds no generic formatter rule. `dialogues_review_round49.json` records the exact `$02CD` FR-only speaker-label removal, the exact `$03F0` sound-bridge distribution, the two clear-only `$04E9` page resets, and the deliberate refusal to force `$0205`. Round 50 again adds no identity and is now runtime-validated: `dialogues_review_round50.json` only resegments the already-owned `$01CE` prompt/Yes unit at canonical choice boundaries; `$0040` and `$04FD` are admitted through stricter simulator models, not new mappings. Round 51 is a zero-ROM-diff residual audit: `dialogues_review_round51.json` formalizes `$0278/C9:A730`, `$0278/C9:A74E` and `$0323/C9:CE5A` as `validated_android_omission`, while `$0330/C9:CEA3` and `$0331/C9:CEB3` are `validated_contextual_template` because their meaning depends on the caller-supplied inn price and no single Android record independently owns them. Round 52, now runtime-validated, adds no identity and no generic formatter rule: `dialogues_review_round52.json` records six exact already-owned structural distributions across `$01B5`, `$01B9`, `$04E6` and `$04E7`; only stock WAIT/action bridges and two reviewed layout-only page clears are used. Round 53 is a zero-ROM-diff Android-FR exhaustion audit: `dialogues_review_round53.json` proves that all 62 FR-nonempty/EN-empty `scrtxt` entries are accounted for (58 already owned, 4 unowned but non-actionable), while `dialogues_review_round53_context.html` classifies all 40 residual SNES semantic carriers for easy later filtering. Round 54 keeps that identity state frozen and adds five exact serialization records in `dialogues_review_round54.json`: `$0040`, `$0041`, `$013A`, `$0559`, `$0592`. No generic formatter rule is widened. The unified `dialogues_android_exhaustion_status.html` explicitly separates Android-not-found carriers from Android-found-but-deferred PARTIEL work. Round 55 changes no ROM byte and adds `dialogues_review_worklist.html`, whose default filter shows only the 34 events / 89 carriers that still require action. Eight informational events are hidden by default but remain searchable; their exact classifications are versioned in `dialogues_review_round55.json`.

`validated_no_equivalent`, `validated_android_omission` and `validated_contextual_template` are intentionally **not Android identities**. They prevent repeatedly reconsidering already-proved negative/contextual cases while leaving them in the unresolved count. After Round 51, every one of the 40 unresolved semantic IDs is accounted for by reviewed negative/contextual evidence, a user-validated visually complete Android adaptation, or an explicit handoff lock; there is no remaining free lexical candidate pool under the current policy.

## Identity and namespace policy

Android **English** is the identity layer. Android French may supply localization payload, reveal a localization error, or prove strict equivalence between already-English-identical occurrences; it cannot create identity by itself.

The generic automatic candidate index is **`scrtxt`-only**. Android `systxt` is used only in explicit reviewed records:

- `$067E/$067F -> systxt 101254` for the parameterized money-chest identity;
- `$0687` keeps `scrtxt` identity 469 while `systxt 101256` corrects the FR payload to `Corde magique`;
- `$0689` keeps `scrtxt` identity 769 while `systxt 101255` supplies `Fouet en cuir`.

`systxt_en` 101255/101256 are already French, so they are localization-correction evidence only and must never be treated as English identity anchors.

Manual supplements also do not count as Android alignment. `$035F` therefore remains identity-unresolved even though Round 60 validates the exact manual payload `Dryade`; the expanded payload `Dryade fera réagir l'orbe !` remains withdrawn. Round 63 marks `$04E1/CA:2C84` as a validated manual suppression because its JP source is explicitly resegmented; it still does not create or change Android identity.

## Matcher policy

Short generic strings are never promoted globally without structural evidence. Automatic rules are non-cascading where documented and must remain calibrated at 0 conflicts. Current accepted-history calibration:

- generic: **165 attempts / 164 reproductions / 0 conflicts**;
- ROM-neighborhood exact duplicate: **25/25 / 0 conflicts**;
- strict EN+FR-equivalent duplicate: **35/35 / 0 conflicts**;
- isolated one-carrier fuzzy: **188/188 / 0 conflicts**;
- dense local extension: **5/5 / 0 conflicts**.

Do not weaken thresholds merely to reduce the unresolved count. For reused subevents, short duplicates, map/NPC scripts and scene-dependent carriers, prefer full caller/trigger/object reconstruction and contextual manual review.

## Round 62 targeted review

`dialogues_review_worklist_round63.html` is the current user-facing queue: 22 action events / 65 action carriers. It includes the full Android-FR context for `$0227/C9:97FE` (IDs 217-219; 220 empty). Exact user-reviewed redistributions resolve `$038D`, `$03EA` and `$04E3`, and recover `CA:31EE/CA:3218` inside still-PARTIEL `$04E2`. The manual review sheet `dialogues_manual_supplements_round63.html` records `$04E1/CA:2C84` as SUPPRIMÉ; note that the user-supplied `$013A` event label was not the canonical owner of that carrier, so `$013A/C9:40D7` remains unchanged.

## Regeneration / checks

```bash
for r in 31 33 34 39 40 41 42 43 44 45 46 47 48 49 50 51 52 53 54; do
  python3 tools/import_android_text.py --only dialogue-review-round$r --check || exit 1
done
python3 tools/import_android_text.py --only dialogue-auto --check
python3 tools/audit_android_dialogue_charset.py --check
python3 tools/import_android_text.py --only dialogue-format-mass --rom <clean-USA-ROM> --check
python3 tools/simulate_dialogues.py <clean-USA-ROM> -o dialogue_preview.html \
  --issues-csv dialogue_preview_issues.csv \
  --preserve-tags mappings/android/dialogue_preview_state.json
python3 tools/check_dialogue_review_worklist.py --check
python3 tools/check_manual_dialogue_supplements.py
python3 tools/generate_manual_dialogue_supplements_html.py --check
python3 tools/check_round62_dialogue_review.py
```

See `docs/HANDOFF.md` before starting new alignment work.


## Round 56 omission review

`dialogues_omission_review_round56.json` records carrier-scoped user decisions; supplying an event ID in review never authorizes changes to unrelated carriers in that event. `dialogues_omission_review_round56.html` provides full SNES-USA context plus Android EN/FR and, for the explicitly deferred Japanese-comparison cases, the recovered Android-JP strings. Round 56 suppresses only `$0042/C9:1057` (plus its exact immediately-following `WAIT $00`) and `$010C/C9:30F5`; it creates no Android identity.

## Round 57/58 SNES-JP omission and manual-review state

Round 57 compares reviewed Android omissions with the original Japanese SNES ROM supplied
locally by the user. Genuine JP-SNES content remains outside Android identity and is staged
through `translations/dialogues_manual_supplements.json`; three exact carriers absent as
distinct JP-SNES lines are locally suppressed. See `dialogues_omission_review_round57.{json,html}`.

Round 58 is ROM-neutral and changes the manual supplement file to format v2. Each carrier
stores `original_jp`, canonical `original_en`, official SNES-FR Rev 1 `original_fr`, and a
review-only `translation_fr` proposal. Pending proposals serialize the USA source until user
approval. `dialogues_manual_supplements_round63.html` is the current deterministic side-by-side review
sheet. Android JP must never be substituted for an unproven SNES-JP transcription.
