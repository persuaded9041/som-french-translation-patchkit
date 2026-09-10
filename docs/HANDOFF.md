# Development handoff — Round 67

Operational handoff only. Historical round-by-round evidence lives in `docs/ANDROID_TEXT_ALIGNMENT.md`, `docs/DIALOGUE_FORMAT.md`, `docs/TEXT_RESEARCH_NOTES.md`, and `mappings/android/dialogues_review_round*.json`.

## Current checkpoint

- Reference ROM: unheadered **Secret of Mana (USA)**, `0x200000`, SHA-256 `4c15013131351e694e05f22e38bb1b3e4031dedac77ec75abecebe8520d82d5f`. Never store or redistribute it.
- Android semantic alignment: **1798 / 1838 (97.8%)**, **40 unresolved**.
- Simulator-clean payload: **695 events = 669 complete + 26 PARTIEL**.
- Translation output: **1687 accepted semantic source IDs / 1783 JSON entries**.
- Manual supplements: **18 = 16 translated + 2 validated suppressions + 0 pending**.
- Exclusions: **6 alignment-incomplete + 2 formatter-rejected + 1 simulator-rejected**.
- Simulation: **0 errors / 0 warnings / 0 implicit wraps**.
- `patches/08_dialogue_text.ips` SHA-256: `748783c60087f3a892d3e82ae58b4321ecf7676bbc9599eb376ddadf576a1281`.
- `patches/all.ips` SHA-256: `8e35b4c5d2ebab9c05d80e0ac0f70d72b77d5237f3fba0a9e1f026fdbc476cb8`.
- Patched ROM SHA-256: `06796a0387908f3d468850636c57ec8860f65ee5e266a43f167e11a9322fdda4`. Independent application of `all.ips` to the clean USA ROM is byte-identical to the builder result.

## Round 67 decisions

- `$013A/C9:40D7`: **validated suppression**. The Western follow-up has no distinct SNES-JP counterpart and Android FR omits it. Serialize the carrier empty and omit **only** its immediately following `WAIT $00`; preserve the following `TEXT_CLEAR/RETURN`.
- `$04E1`: the Thanatos monologue is redistributed from complete Android FR IDs **3252–3257** across `CA:2BED`, `CA:2C3A`, and `CA:2C93`. Keep the earlier Round-63 suppression of standalone `CA:2C84` and its immediate `WAIT $00`; preserve the following `TEXT_CLEAR` and the existing end-of-scene `PLAYER_NAME` fixes. Do not reopen `$04E1`.
- `$04E2`: `CA:32C5 = " : Non ! / C'est pas possible !"` and `CA:32D7 = "Ils se sont sûrement échappés !"`. Android FR assigns both to `%S(2,0)`: change the translation-side `PLAYER_NAME(1)` before `CA:32C5` to `PLAYER_NAME(2)` and omit the redundant `PLAYER_NAME(2)` before `CA:32D7`. Five carriers remain deferred: `CA:3335`, `CA:3359`, `CA:3362`, `CA:33E4`, `CA:3423`. Use `mappings/android/dialogue_04E2_android_fr_round67.html`.
- `$035F/C9:D1B8`: manual surcharge is strictly **`Dryade`**. Exact carrier evidence is only `ドリアード` / `Dryad` / `Dryade`; never restore `Dryade fera réagir l'orbe !`.

## Source and mapping rules

- Android **English `scrtxt`** is the identity layer. Android FR supplies localization and can prove resegmentation/omission, but does not create identity by itself. `systxt` is not a generic dialogue identity source.
- Do not restart generic lexical identity search merely to raise **1798/1838** without genuinely new provenance. Prefer PARTIEL / TO REVIEW / negative evidence to weak mapping.
- Original **SNES-JP** is the primary semantic source when available. Never put Android-JP text in `original_jp`. `tools/extract_japanese_dialogue.py` is analysis-only and must refuse uncertain 1:1 regional carrier mappings.
- Manual supplements remain outside Android identity. Suppression is allowed only when explicitly validated and structurally exact.
- `WAIT != NEWLINE`. A pause does not advance the live dialogue cursor. Only explicit newline or `TEXT_CLEAR` changes line/page position.
- Do not weaken formatter/simulator guards to increase coverage. Components 05/06 are runtime-validated; do not refactor without direct need.

## Locked / do-not-reopen cases

- `$04E1`: Round 67 resolves the remaining monologue; preserve only the deliberate `CA:2C84` suppression.
- `$013A/C9:40D7`: validated suppression; empty carrier + immediate `WAIT $00` omission only.
- `$035F/C9:D1B8`: `Dryade` only.
- `$0204/C9:902F`: validated manual translation only; do not release the event's other ambiguous Android resegmentation.
- `$04E8/CA:437D`: validated manual `Héhéhéhé !`; preserve unrelated PARTIEL repairs.
- `$010C/C9:30F5`, `$02FC/C9:CB28`, `$0558/CA:6629`: earlier exact user-approved SNES-JP-led suppressions.
- `$05F8`: deliberately blocked. `$015A`: rejected remap frozen. `$001E`: no Android identity; layout-only newline. `$0323`: do not remap the dynamic 30-GP inn parameter to the distinct Android Neko/meow variant. `$0602/CA:85DD`: semantically unresolved but visually complete.

## Current hard/deferred cases

These are layout/structure work, not generic source-discovery work:

- `$04E2`: five carriers listed above; this is the immediate priority.
- `$0205`: formatter-rejected; Android FR condenses two SNES carriers across `PLAYER_NAME(0) + WAIT $00 + TEXT_CLEAR`.
- `$05B4`: formatter-rejected by design; identity-only shared tail.
- `$0429`: sole simulator-rejected event; Android-FR redistribution crosses several `WAIT`/`PLAYER_NAME` boundaries.
- `$04E5`: known cursor/scroll geometry problems.
- `$04E6`: only the elder-hesitation bridge is validated; larger redistribution remains PARTIEL.
- `$04E9`: preserve the validated PARTIEL tail; Android FR condenses `CA:48DC + CA:4925` into one unsplittable sentence.
- `$0559/Android 2147`, `$0592/Android 1031`, `$04FD`, `$0227`: identity is known but exact serialization remains structurally unsafe.

## Best next work

1. Continue `$04E2` from `mappings/android/dialogue_04E2_android_fr_round67.html`, limited to `CA:3335`, `CA:3359`, `CA:3362`, `CA:33E4`, `CA:3423`.
2. Preserve the Round-67 `PLAYER_NAME(2)` resegmentation around `CA:32C5/CA:32D7`.
3. Use `mappings/android/dialogues_review_worklist_round67_simplified.html` for the remaining non-manual queue (**15 events / 55 carriers**).
4. Do not reopen `$04E1` or `$013A/C9:40D7`.

## Review files

- `mappings/android/dialogue_04E2_android_fr_round67.html` — complete Android EN/FR view for the five remaining `$04E2` carriers.
- `mappings/android/dialogues_review_worklist_round67_simplified.html` — current non-manual review queue.
- `mappings/android/dialogues_manual_supplements_round67.html` — manual JP/USA/official-FR provenance; no pending approvals.
- `dialogue_preview.html` / generated checkpoint copy — full static simulator preview.

## Regeneration / checks

After an accepted semantic/formatter change:

```bash
for r in 31 33 34 39 40 41 42 43 44 45 46 47 48 49 50 51 52 53 54; do
  python3 tools/import_android_text.py --only dialogue-review-round$r --check || exit 1
done
python3 tools/import_android_text.py --only dialogue-auto --check
python3 tools/audit_android_dialogue_charset.py --check
python3 tools/import_android_text.py --only dialogue-format-mass \
  --rom "Secret of Mana (USA).sfc" --check
python3 tools/generate_android_residual_html.py --check
python3 tools/generate_android_exhaustion_html.py --check
python3 tools/check_dialogue_review_worklist.py --check
python3 tools/check_manual_dialogue_supplements.py
python3 tools/generate_manual_dialogue_supplements_html.py --check
python3 tools/check_round62_dialogue_review.py
python3 tools/check_round63_04e1_suppression.py
python3 tools/check_round64_nonfound_manual_reviews.py
python3 tools/check_round65_manual_approvals.py
python3 tools/check_round66_0204_manual_approval.py
python3 tools/check_round67_targeted_dialogues.py
python3 tools/check_text_source_hygiene.py
python3 tools/check_text_roundtrip.py "Secret of Mana (USA).sfc" --scan-all-events
# When the clean JP reference ROM is available locally:
python3 tools/check_japanese_dialogue_extractor.py "Seiken Densetsu 2 (Japan).sfc"
python3 tools/simulate_dialogues.py "Secret of Mana (USA).sfc" \
  -o dialogue_preview.html \
  --issues-csv dialogue_preview_issues.csv \
  --preserve-tags mappings/android/dialogue_preview_state.json
```

Rebuild **only changed components**, normally component 08, then recombine stored component IPS files. For user testing provide one autonomous `all.ips` against a clean unheadered USA ROM plus the relevant review HTML. Never include any ROM in an archive.
