# Development handoff — Round 72

Operational handoff only. Historical evidence remains in `docs/ANDROID_TEXT_ALIGNMENT.md`,
`docs/DIALOGUE_FORMAT.md`, `docs/TEXT_RESEARCH_NOTES.md`, and the archived review files.

## Current checkpoint

- Reference ROM: unheadered **Secret of Mana (USA)**, `0x200000`, SHA-256 `4c15013131351e694e05f22e38bb1b3e4031dedac77ec75abecebe8520d82d5f`. Never store or redistribute it.
- Current state: **Round 72 — automatic 216 px completion**.
- Android semantic alignment: **1798 / 1838 (97.8%)**, 40 unresolved semantic IDs. Do not inflate identity to reach 100%.
- Playable dialogue corpus: **701 events = 701 complete + 0 PARTIEL**.
- Translation output: **1810 accepted semantic source IDs / 1943 active sparse JSON entries**.
- Exclusions: only `$0269`, `$02DE`, `$0603`, all routing-audited unused/orphan stock content.
- Simulation: **0 errors / 0 warnings / 0 implicit runtime wraps**.
- Reachable dialogue coverage: **100% French** under the canonical routing audit.

## Locked dialogue state

All user-reviewed Round 67/68/69 translation identities, wording, suppressions and scene redistributions are locked. Do not reopen them as part of unrelated work. Important exact locks include:

- `$013A/C9:40D7`: validated suppression.
- `$04E1`: Round-67 Thanatos redistribution; do not reopen.
- `$04E2`: preserve the accepted `CA:32C5/CA:32D7` speaker redistribution and subsequent Round-69 completion.
- `$035F/C9:D1B8`: manual payload is exactly `Dryade`.
- `$04E8/CA:437D`: manual `Héhéhéhé !`.
- `$010C/C9:30F5`, `$02FC/C9:CB28`, `$0558/CA:6629`: validated suppressions.
- `$0555`, `$0429`, `$05F8`: preserve the original Android-FR scene text; layout may be generated, wording must not be silently rewritten.
- `WAIT != NEWLINE`. A wait never advances the live dialogue cursor by itself.

## Runtime VWF contract — validated

Round 70 identified the long-line Potos artifact as a parser-capacity problem, not a compositor defect. Component 06 now grants `+10` dialogue parser units, restoring **38 decoded glyphs per physical line**. Runtime tests on `pressentiment`, `lumière` and `cascade` validate that the former delayed/shifted 35th glyph is fixed.

Independent stress tests establish two separate ordinary-dialogue constraints:

- **38 decoded glyphs maximum per line**;
- **216 px VWF advance maximum per line**.

A 216-px / 38-glyph line was validated on physical lines 1, 2 and 3 and immediately before a page transition. Do not collapse these into one character-count approximation. Choice rows are not judged by the ordinary 216-px padded-row rule; they use their separately validated absolute-anchor/highlight geometry.

The abandoned Round-70 compositor `STA -> ORA` experiment remains absent. It produced no visible change and is only a deferred diagnostic hypothesis.

## Round 72 automatic layout generation

The Android-FR generator owns the 216-px / 38-glyph presentation contract. It regenerates all 701 playable events without hard-coded French fixes. Generic rules include:

- word wrapping under 216 px and 38 decoded glyphs;
- conservative accounting for a live preceding `PLAYER_NAME`;
- deterministic generated page transitions at source-derived word boundaries, accepted only when simulator score strictly improves and the whole event becomes clean;
- reuse of an immediately following stock `WAIT $00 + TEXT_CLEAR` instead of duplicating a generated transition;
- generated fresh-page handling when a three-line prompt would otherwise leave no row for a following stock choice decoration;
- choice-specific geometry checks rather than applying the ordinary 216-px padded-row ceiling to choice rows.

Do not replace these mechanisms with event-specific French strings. Temporary hard-coded strings are acceptable only for isolated diagnostics and must never enter canonical generated assets.

## Validation baseline

The Round-72 checkpoint passed:

```text
701 translated events simulated
0 errors
0 warnings
0 implicit runtime wraps
6 informational WAIT $00 third-line review risks
Round-67 targeted locks: OK
Round-68 scene redistributions: OK
Round-69 semantic completion: OK
text-source hygiene: OK
713-event round-trip + 2048-script structural scan: OK
redistribution recipes: OK
```

The full mass-import command remains the canonical regeneration path, although repeated end-to-end invocations may be slow in hosted environments. Do not weaken deterministic validation merely to shorten a run.

After dialogue-related changes, the usual checks remain:

```bash
python3 tools/import_android_text.py --only dialogue-format-mass \
  --rom "Secret of Mana (USA).sfc" --check
python3 tools/check_round67_targeted_dialogues.py
python3 tools/check_round68_scene_redistributions.py
python3 tools/check_round69_dialogue_completion.py
python3 tools/check_text_source_hygiene.py
python3 tools/check_text_roundtrip.py "Secret of Mana (USA).sfc" --scan-all-events
python3 tools/simulate_dialogues.py "Secret of Mana (USA).sfc" \
  -o dialogue_preview.html --issues-csv dialogue_preview_issues.csv \
  --preserve-tags mappings/android/dialogue_preview_state.json
```

Rebuild only changed components, then recombine stored component IPS files. Never include a ROM in an archive.

## Next session — item translation procedure only

The next topic is **translation of item/special names**, but the next session must begin with **procedure design and discussion only**. Do not start translating or inserting item text until the user explicitly approves the workflow.

The canonical clean-ROM family already exists in `assets/text_resources.json`. The likely initial target is resource IDs `$0B9-$0C5` (`item/special names`, 13 entries), documented in `docs/TEXT_RESOURCES.md`. A sparse `translations/text_resources_french.json` does not yet exist, and live growth/repacking of the 513-resource table is intentionally not enabled.

Before implementation, inspect the Android sources and existing extraction code and propose a reproducible pipeline covering at least:

1. how SNES resource identities map to Android source entries, without guessing from French strings alone;
2. which Android source container(s) provide the authoritative French item names and how provenance will be retained;
3. whether names fit in-place or require pointer-table/blob repacking, relocation, or UI/runtime changes;
4. how width/character-set/menu constraints will be measured for every consumer of these resources;
5. the sparse translation JSON schema and deterministic import/check command;
6. which component should own insertion so every component remains independently rebuildable;
7. round-trip, source-hygiene, build and runtime review tests;
8. an HTML review sheet showing SNES USA, Android EN identity evidence, Android FR proposal and relevant constraints before any bulk insertion.

Preserve the project policy used for dialogue work: canonical sources remain source-only; translated prose must be regenerated from upstream Android data or explicit reviewed supplements rather than duplicated as hidden hard-coded strings.
