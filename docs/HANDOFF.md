# Development handoff

This file records the current working checkpoint. Historical reverse-engineering detail stays in the topic-specific documentation; this page is intentionally short.

## Current checkpoint

- Reference ROM: unheadered **Secret of Mana (USA)**. The ROM is never stored or redistributed.
- Components 05 and 06 are runtime-validated and should not be refactored without a direct need.
- Component 08 owns dialogue reinsertion/relocation. Relocation to `$E8-$EC` is runtime-validated.
- Component 06's stock-rendered `CHOICE_BEGIN` fallback is runtime-validated on `$0331`; stock choice anchors must not be moved without dedicated analysis/runtime testing.
- Current semantic alignment: **1601 / 1838 (87.1%)**, with **237 unresolved**.
- Current simulator-filtered corpus: **496 events**, **493 complete + 3 PARTIEL**, **1051 visible French semantic IDs / 1106 JSON entries**.
- Static gate: **0 errors, 0 warnings, 0 implicit wraps**.
- This is the clean pre-choice-VWF checkpoint intended for versioning.

## Alignment rules

Android English is the identity layer. Android French may redistribute or rewrite text across adjacent slots.

Accepted structural evidence includes:

- ordered neighboring Android-English blocks;
- speaker/staging redistribution (`All:` on SNES may be expressed differently on Android);
- SNES fragments merged into one larger Android-English record;
- prompt + choice options split into adjacent Android records;
- Cannon Travel blocks identified from ordered destination labels first, then traced back to their rewritten prompt/response.

Never globally match short labels such as Yes/No, Buy/Sell, destinations, cries or other generic strings. Do not translate manually and do not force weak mappings.

Semantic identity and layout safety are separate gates. A proven mapping may remain hidden if its stock carrier or choice anchors cannot render the official French safely.

## Runtime/layout findings to preserve

- `WAIT` is pause-only: it **does not imply NEWLINE**. Text resumes on the same live line unless an explicit `$7F` or `TEXT_CLEAR` occurs.
- `$0106/C9:2994 -> TEXT_CLEAR` is runtime-validated: after its two-line ghost page, the following speaker must start on a fresh page.
- The explicit post-WAIT newline fixes observed on `$0103` and `$0106` are runtime-validated.
- The additional WAIT/newline/TEXT_CLEAR batch remains `TO REVIEW` until combined runtime testing; do not silently promote it to validated.
- Do not restore the old generic WAIT-overlap deduplication. Exact carry-over after `WAIT $00` can be normal rolling-window presentation.
- The live-window guard prevents formatter-added aesthetic line breaks from pushing a line into the next rolling-window state. `$0083` (`Gestahl : Ha ! Imbécile !`) is the canonical example.
- `$01DC` is user-validated as a complete Android adaptation: Android 729 starts the following Niccolo scene directly after 728, so the final SNES-only `PLAYER_NAME(0) + C9:804A` reaction is omitted as one unit. This is the only current structural command omission and is guarded by exact adjacency.
- Choice labels must remain compatible with stock `CHOICE_OPTION` anchors. `$00DF` has a proven Android identity but remains PARTIEL/layout-deferred because `Temple de l'Eau` does not fit safely at the stock anchors.
- Long stock-rendered choice rows can overflow near the right edge; the `Impossible ! / Bon, d'accord...` stress-test limit remains deferred.

## Current review workflow

The HTML preview uses `mappings/android/dialogue_preview_state.json` to preserve unread `NEW`, `MODIFIED` and `TO REVIEW` badges across regenerations. Do not clear or replace this state until the user has finished reviewing the current batch.

When changing dialogue mappings/layout:

1. regenerate `dialogue-auto` if semantic evidence changed;
2. regenerate `dialogue-format-mass`;
3. require 0 errors / 0 warnings / 0 implicit wraps;
4. rebuild only modified components (normally 08);
5. recombine stored component IPS files into `patches/all.ips`;
6. generate the HTML preview while preserving `mappings/android/dialogue_preview_state.json`;
7. keep new runtime candidates marked `TO REVIEW` until user validation.

Useful checks:

```bash
python3 tools/import_android_text.py --only dialogue-auto --check
python3 tools/audit_android_dialogue_charset.py --check
python3 tools/import_android_text.py --only dialogue-format-mass --rom "Secret of Mana (USA).sfc" --check
python3 tools/check_text_source_hygiene.py
python3 tools/check_text_roundtrip.py "Secret of Mana (USA).sfc" --scan-all-events
python3 tools/simulate_dialogues.py "Secret of Mana (USA).sfc" -o dialogue_preview.html \
  --preserve-tags mappings/android/dialogue_preview_state.json
```

## Recommended next work

Implement a dedicated **VWF path for interactive choice rows** in component 06. The current stock-rendered fallback remains the runtime-validated baseline and must stay available until the replacement is proven. Start from `$00DF`: its Android identity is already established, but `Temple de l'Eau` does not fit between the stock fixed-width `CHOICE_OPTION` anchors. The goal is to render choice labels with VWF while preserving the stock choice structure, option boundaries, selection/highlight behavior and event commands. Do not move `CHOICE_OPTION` anchors merely to make text fit unless a later dedicated analysis proves that safe. Keep component 05 untouched.

The `Impossible ! / Bon, d'accord...` stress test is a known stock-fallback overflow limit and is a useful later regression case, but `$00DF` should be the first focused target. The remaining PARTIEL events and current `TO REVIEW` runtime candidates may stay deferred during this renderer step.
