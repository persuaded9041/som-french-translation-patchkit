# Development handoff

This file records the current working checkpoint. Historical reverse-engineering detail stays in the topic-specific documentation; this page is intentionally short.

## Current checkpoint

- Reference ROM: unheadered **Secret of Mana (USA)**. The ROM is never stored or redistributed.
- Components 05 and 06 are runtime-validated and should not be refactored without a direct need.
- Component 08 owns dialogue reinsertion/relocation. Relocation to `$E8-$EC` is runtime-validated.
- Component 06 ordinary dialogue VWF remains runtime-validated. Choice rows use that same VWF path with no `CHOICE_BEGIN` renderer special case; `$0331` runtime-validates the minimal `$A1D7[]` option-start synchronization and correct magenta selection.
- Current semantic alignment: **1601 / 1838 (87.1%)**, with **237 unresolved**.
- Current simulator-filtered corpus: **521 events**, **520 complete + 1 PARTIEL**, **1122 visible semantic IDs / 1179 JSON entries**.
- Static gate: **0 errors, 0 warnings, 0 implicit wraps**.
- Choice-row VWF now has two runtime-validated paths. Decorated choices keep the stock-anchor/terminal-boundary geometry. Undecorated two-option rows keep `$A1D7[]` logical for parser/storage but use private measured-end VWF/highlight boundaries; `$00CE`, `$00CF`, `$00D1` and `$0202` are validated. `$00D0` remains excluded because its right option reaches too close to the bitmap edge and can corrupt the frame while highlighted.

## Alignment rules

Android English is the identity layer. Android French may redistribute or rewrite text across adjacent slots.

Accepted structural evidence includes:

- ordered neighboring Android-English blocks;
- speaker/staging redistribution (`All:` on SNES may be expressed differently on Android);
- SNES fragments merged into one larger Android-English record;
- prompt + choice options split into adjacent Android records;
- Cannon Travel blocks identified from ordered destination labels first, then traced back to their rewritten prompt/response.

Never globally match short labels such as Yes/No, Buy/Sell, destinations, cries or other generic strings. Do not translate manually through the Android mapping layer and do not force weak mappings. The only manual-text staging area is `translations/dialogues_manual_supplements.json`, restricted to user-validated SNES carriers proven absent from Android.

Semantic identity and layout safety are separate gates. A proven mapping may remain hidden if its stock carrier or choice anchors cannot render the official French safely.

## Runtime/layout findings to preserve

- `WAIT` is pause-only: it **does not imply NEWLINE**. Text resumes on the same live line unless an explicit `$7F` or `TEXT_CLEAR` occurs.
- `$0106/C9:2994 -> TEXT_CLEAR` is runtime-validated: after its two-line ghost page, the following speaker must start on a fresh page.
- The explicit post-WAIT newline fixes observed on `$0103` and `$0106` are runtime-validated.
- The additional WAIT/newline/TEXT_CLEAR batch remains `TO REVIEW` until combined runtime testing; do not silently promote it to validated.
- Do not restore the old generic WAIT-overlap deduplication. Exact carry-over after `WAIT $00` can be normal rolling-window presentation.
- The live-window guard prevents formatter-added aesthetic line breaks from pushing a line into the next rolling-window state. `$0083` (`Gestahl : Ha ! Imbécile !`) is the canonical example.
- `$01DC` is user-validated as a complete Android adaptation: Android 729 starts the following Niccolo scene directly after 728, so the final SNES-only `PLAYER_NAME(0) + C9:804A` reaction is omitted as one unit. This is the only current structural command omission and is guarded by exact adjacency.
- Choice formatting remains conservative. `$00DF` runtime-validates the minimal later-anchor `$11 -> $12` storage shift. For wider undecorated two-option rows, component 06 now separates logical storage anchors from visual geometry: it measures the real VWF endpoint, keeps one blank cell between options, and supplies private cell-aligned highlight bounds without rewriting `$A1D7[]`.
- Do **not** generalize first-option shifts to the left. The rejected `$00CE` `$00/$0F` and `$01/$10` diagnostics clipped the first label. The validated compact path instead enforces a safe first visual cell of at least `$03`.
- Runtime-validated compact cases are `$00CE`, `$00CF`, `$00D1` and `$0202`. `$00D0` remains excluded: `Désert de Kakkara / Pays de glace` renders but the right option sits too close to the bitmap edge and highlighting can corrupt the frame. A separate right-edge margin rule is still required.
- Decorated short choices fall back structurally when decoded[terminal] is the stock `)` glyph. `Acheter / Vendre` and `Oui / Non` are runtime-validated controls. A minor cosmetic follow-up remains: one additional blank cell before the closing `)` would look better.

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

The PARTIEL pass is effectively complete. `$0278` is deliberately the sole remaining
PARTIEL event because its two controller-specific SNES lines are proven absent from Android
and are waiting for an explicit human French translation in
`translations/dialogues_manual_supplements.json`. Do not try to resolve them through the
Android mapping layer.

The next useful phase is the **excluded-event backlog**, which is distinct from PARTIEL:
**183 events** are currently excluded entirely from the mass corpus. They split into
**161 alignment-incomplete events**, **17 formatter rejects**, and **5 simulator rejects**.

A conservative order of work is:

1. finish the remaining choice reject `$00D0` by adding a separately runtime-validated right-edge safety margin. The generic measured-end primitive is already validated on `$00CE`, `$00CF`, `$00D1` and `$0202`; those four can be admitted by component 08 once the formatter/simulator is taught the new geometry. Keep `$00D0` excluded until its frame-corruption case is solved;
2. then review the **17 formatter rejects**, which are mainly explicit structural conflicts
   around `PLAYER_NAME`, `WAIT`, `OP_32`, `OP_34` or `CHOICE_BEGIN` and must remain
   event-specific unless a genuinely general structure is proven;
3. resume Android-English structural alignment on the **237 unresolved semantic IDs**
   spread across the 161 alignment-incomplete events, continuing to reject weak mappings.

After each accepted batch, regenerate `dialogue-auto` only when semantic identity changes,
regenerate `dialogue-format-mass`, require 0 errors / 0 warnings / 0 implicit wraps, rebuild
only modified components, recombine `all.ips`, and preserve the active HTML review badges.
