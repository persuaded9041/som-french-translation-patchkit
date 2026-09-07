# Development handoff

This file records the current working checkpoint. Historical reverse-engineering detail stays in the topic-specific documentation; this page is intentionally short.

## Current checkpoint

- Reference ROM: unheadered **Secret of Mana (USA)**. The ROM is never stored or redistributed.
- Components 05 and 06 are runtime-validated and should not be refactored without a direct need.
- Component 08 owns dialogue reinsertion/relocation. Relocation to `$E8-$EC` is runtime-validated.
- Component 06 ordinary dialogue VWF remains runtime-validated. Choice rows use that same VWF path with no `CHOICE_BEGIN` renderer special case; `$0331` runtime-validates the minimal `$A1D7[]` option-start synchronization and correct magenta selection.
- Current semantic alignment: **1601 / 1838 (87.1%)**, with **237 unresolved**.
- Current simulator-filtered corpus: **500 events**, **498 complete + 2 PARTIEL**, **1066 visible French semantic IDs / 1119 JSON entries**.
- Static gate: **0 errors, 0 warnings, 0 implicit wraps**.
- Choice-row VWF is runtime-validated end-to-end on the Potos test path: option starts and the existing `CHOICE_END` terminal boundary are synchronized to stock `$A1D7[]` geometry, so the magenta selection remains aligned and a preserved closing parenthesis stays outside the final highlighted span. Component 08 may minimally move only a later choice anchor right when decoded French would otherwise be overwritten.

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
- Choice formatting remains conservative. The VWF/highlight primitive and terminal-boundary handling are runtime-validated; `$00DF` additionally runtime-validates the minimal `$11 -> $12` later-anchor shift required to preserve `Temple de l'Eau` without changing the first anchor or the magenta routine.
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

Choice-row VWF is now runtime-validated on the Potos `$0331` test path: option starts are
resynchronized to stock `$A1D7[]` boundaries, the magenta highlight follows the selection,
and the CHOICE_END terminal boundary keeps a preserved closing `)` outside the final
highlighted span. GAME SELECT remains stock-safe.

Component 08 now owns the minimal decoded-row geometry fallback. It keeps the first
`CHOICE_OPTION` stock and may move only a later option to the right when the preceding
official-French label would otherwise be overwritten by the stock absolute decoded-cell
reset. `$00DF` runtime-validates the concrete `$03/$11 -> $03/$12` case with
`Temple de l'Eau / Pandora`. The full corpus gains four additional simulator-clean events
(`$020F`, `$0310`, `$0314`, `$0319`); these four remain static candidates until ordinary
playthrough/runtime review.
