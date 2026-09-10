# Development handoff — Round 69

Operational handoff only. Historical evidence remains in `docs/ANDROID_TEXT_ALIGNMENT.md`, `docs/DIALOGUE_FORMAT.md`, `docs/TEXT_RESEARCH_NOTES.md`, and `mappings/android/dialogues_review_round*.json/html`.

## Current checkpoint

- Reference ROM: unheadered **Secret of Mana (USA)**, `0x200000`, SHA-256 `4c15013131351e694e05f22e38bb1b3e4031dedac77ec75abecebe8520d82d5f`. Never store or redistribute it.
- Android semantic alignment: **1798 / 1838 (97.8%)**, **40 unresolved**. Round 69 deliberately does not inflate identity.
- Simulator-clean payload: **701 events = 701 complete + 0 PARTIEL**.
- Translation output: **1810 accepted semantic source IDs / 1946 JSON entries**.
- Manual supplements: **18 = 16 translated + 2 validated suppressions + 0 pending**.
- Exclusions: **3 alignment-incomplete**, all routing-audited unused/orphan stock content: `$0269`, `$02DE`, `$0603`.
- Simulation: **0 errors / 0 warnings / 0 implicit wraps**.
- Playable-dialogue coverage: **100% French for dialogue reachable through the canonical routing audit**. The former 15 provenance-only PARTIEL events are now promoted to complete after scene-level semantic review; their provenance remains explicit in `user_validated_visually_complete_events`. The 3 unreachable stock strings remain intentionally excluded.

## Round 69 decisions

Round 69 finishes the remaining actionable dialogue resegmentation without adding weak Android identities. Resegmentation data contains no French prose: `mappings/android/dialogues_redistribution_recipes.json` stores only Android-FR ID/token references plus layout/control metadata, and `tools/import_android_text.py` reconstructs every redistributed carrier directly from `sources/android/scrtxt_fr.bin`. The deterministic layouts live in `mappings/android/dialogues_redistribution_recipes.json`.

- `$010C`: complete the Android-FR scene redistribution; preserve the validated empty `C9:30F5` suppression.
- `$015A`: reconstruct Android FR 255–256 across the two stock `PLAYER_NAME(1)` positions: Elman greets the girl, then the girl replies about finding Durac.
- `$01C5`: the whole Android EN/FR block 436–438 proves the choice scene. Keep the Android FR wording (`Continuer` / `Sortir`) and shift only the second choice anchor to avoid overlap. The older isolated-carrier idea is superseded; no manual identity is created.
- `$0204/$0205`: treat as one scene. Preserve Android FR 839/842/843/844/824/825 and redistribute across the SNES carriers. This supersedes the older Round-66 *active placement* of the `C9:902F` manual text while preserving its provenance record. Omit the now-redundant `PLAYER_NAME(0)` before `C9:90DE`.
- `$0227`: `C9:97FE = "Quoi ? Durac a été..."`; `C9:9827` begins a new box with `Non ! Je suis sûre qu'il va bien, %S(1,0).`; omit the stock `PLAYER_NAME(1)` immediately before `C9:9827` because the translated carrier emits it internally.
- `$04E2`: keep the Round-67 `CA:32C5/CA:32D7` speaker decision. Resolve the five formerly deferred carriers from Android FR: `CA:3335`, `CA:3359`, `CA:3362`, `CA:33E4`, `CA:3423`; `CA:345F` carries the second sentence of Android 1291. Do not reopen `$04E1` or `$013A/C9:40D7`.
- `$04E5`: combine `CA:3C59 + CA:3C75` into the single Android-FR Zico line; `CA:3C75` is empty.
- `$04E6`: `CA:3FB0 = "C'est certain ! L'Épée les attire ici !"`; `CA:3FC1` carries `Tant que %S(0,0) sera au village...`; omit the redundant stock name trigger and the later empty-page `WAIT $00` identified by the simulator.
- `$04E9`: put the complete Android-FR sentence on `CA:48DC`; empty `CA:4925`.
- `$04FD`: move `%S(0,0)` into `CA:4E2C` and keep the surrounding stock `PLAYER_NAME(2)` ordering needed by the scene.
- `$0559`: reconstruct Android 2147 with `%S(2,0) : %S(1,0)... Ça va ?` in the final carrier; omit the two redundant earlier stock name triggers.
- `$0592`: serialize Android FR 1023/1031 with explicit page structure and no separate stock sprite-name label.
- `$05B4`: the carrier is only the numeric code `“ 6 3 4 ”`; admit it unchanged. Do **not** inject the called-event text that Android combines with this shared tail.

## Round 68 decisions still locked

- `$0555`, `$0429`, `$05F8`: preserve the **original Android FR scene text** as accepted by the user. No JP-derived additions. Carriers/pages may be redistributed only to serialize that Android FR.
- `$05F8` is a whole-scene review, not new Android-English identities; identity remains 1798/1838.
- Translation-only `%S(n,0)` may serialize directly as stock `PLAYER_NAME(n)` inside reviewed translations. Canonical/source serialization is unchanged.

## Earlier locked decisions

- `$013A/C9:40D7`: validated suppression; empty carrier + immediate `WAIT $00` omission only.
- `$04E1`: Round-67 Thanatos monologue redistribution; preserve deliberate `CA:2C84` suppression and its immediate `WAIT $00` omission. **Do not reopen.**
- `$035F/C9:D1B8`: manual payload is strictly **`Dryade`**.
- `$04E8/CA:437D`: manual **`Héhéhéhé !`**.
- `$010C/C9:30F5`, `$02FC/C9:CB28`, `$0558/CA:6629`: validated suppressions remain exact.
- `$0602/CA:85DD`: semantically unresolved identity bookkeeping but runtime-validated visually complete; do not force an Android mapping.
- `WAIT != NEWLINE`. A pause never advances the live dialogue cursor by itself.

## Remaining non-playable stock exclusions

These are intentionally **not** reasons to reopen Android identity search:

- `$0269/C9:A49C` — `TRUFFLE:I'm rooting for you!`: unreferenced duplicate. The live Truffaut line is `$0276`, called from `$04E3`, already translated via Android 1400.
- `$02DE/C9:C4FB` — `Drink this medicine! / It'll fix ya right up!`: no incoming event/map/object reference in the canonical routing audit; unused Tasmanica NPC script.
- `$0603/CA:85FC` — `Topaz Falls`: unreferenced sign; Android contains no safe identity. JP confirms the place-name text but not runtime reachability.

Translate these only if a future project deliberately restores unused content. Do not map them merely to claim 1838/1838 Android identity.

## Checks

After dialogue changes:

```bash
python3 tools/import_android_text.py --only dialogue-format-mass \
  --rom "Secret of Mana (USA).sfc" --check
python3 tools/check_round67_targeted_dialogues.py
python3 tools/check_round68_scene_redistributions.py
python3 tools/check_round69_dialogue_completion.py
python3 tools/check_text_source_hygiene.py
python3 tools/check_text_roundtrip.py "Secret of Mana (USA).sfc" --scan-all-events
python3 tools/check_japanese_dialogue_extractor.py "Seiken Densetsu 2 (Japan).sfc"
python3 tools/simulate_dialogues.py "Secret of Mana (USA).sfc" \
  -o dialogue_preview.html \
  --issues-csv dialogue_preview_issues.csv \
  --preserve-tags mappings/android/dialogue_preview_state.json
```

Rebuild **only changed components**, normally component 08, then recombine stored IPS files:

```bash
python3 build.py "Secret of Mana (USA).sfc" dialogue-text --combine
```

For user testing provide one autonomous `patches/all.ips` against a clean unheadered USA ROM plus the review/preview HTML. Never include a ROM in an archive.
