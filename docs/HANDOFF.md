# Development handoff

This file records the current working checkpoint. Historical reverse-engineering detail stays in the topic-specific documentation; this page is intentionally short.

## Current checkpoint

- Reference ROM: unheadered **Secret of Mana (USA)**. The ROM is never stored or redistributed.
- Components 05 and 06 are runtime-validated and should not be refactored without a direct need.
- Component 08 owns dialogue reinsertion/relocation. Relocation to `$E8-$EC` is runtime-validated.
- Component 06 ordinary dialogue VWF remains runtime-validated. Choice rows use that same VWF path with no `CHOICE_BEGIN` renderer special case; `$0331` runtime-validates the minimal `$A1D7[]` option-start synchronization and correct magenta selection.
- Current semantic alignment: **1601 / 1838 (87.1%)**, with **237 unresolved**.
- Current simulator-filtered corpus: **526 events**, **525 complete + 1 PARTIEL**, **1138 visible semantic IDs / 1196 JSON entries**.
- Static gate: **0 errors, 0 warnings, 0 implicit wraps**.
- Choice-row VWF has two runtime-validated paths. Decorated choices keep the stock-anchor/terminal-boundary geometry. Undecorated two-option rows keep `$A1D7[]` logical for parser/storage but use private measured-end VWF/highlight boundaries; the first private visual/highlight boundary is `max(logical_first, $03) - 2`, and `$00CE`, `$00CF`, `$00D0`, `$00D1` and `$0202` are validated. Final `$00D0` geometry is 8 px -> 117 px for the first option, second option at 128 px -> 209 px, terminal cell `$1B`. The retained cell-`$11` separator-omission branch was runtime-validated on the earlier `$00D0` right-edge checkpoint before the final left compaction.

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
- Choice formatting remains conservative. `$00DF` runtime-validates the minimal later-anchor `$11 -> $12` **storage** shift. For wider undecorated two-option rows, component 06 separates logical storage anchors from visual geometry: it measures the real VWF endpoint and supplies private cell-aligned highlight bounds without rewriting `$A1D7[]`. It normally keeps one blank cell between options; if the rounded first endpoint is already cell `$11`, that extra cell is omitted.
- `$00D0` (`Désert de Kakkara / Pays de glace`) is the right-edge stress case. Before final left compaction it runtime-validated the cell-`$11` separator-omission safety branch. With the accepted two-cell private left shift it now keeps the normal separator: first option 8->117 px, second 128->209 px, terminal cell `$1B`, with no frame corruption. `$00CE`, `$00CF`, `$00D1` and `$0202` also keep the normal separator in the final geometry.
- Diagnostic warning: Potos `$0331` uses stock logical anchors `$05/$0A`. Injecting long labels while leaving those values unchanged makes `$5A $0A` rewind the decoded buffer and truncate the first label; stripping `(`/`)` does not fix the storage reset. The validated `$00D0` reproduction used logical `$03/$14` (`$03` + 17 decoded characters). This is diagnostic setup only, not a hard-coded `$00D0` rule.
- Do **not** generalize the rejected **logical-anchor** shifts `$00/$0F` or `$01/$10`; they clipped `$00CE`. The accepted left-margin rule is visual-only and keeps `$A1D7[]`/parser storage untouched.
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
**178 events** are currently excluded entirely from the mass corpus. They split into
**161 alignment-incomplete events** and **17 formatter rejects**. There are no remaining simulator rejects; the former five choice rejects are admitted by the runtime-validated measured-end model and the composed decoration/anchor fallback.

A conservative order of work is:

1. review the **17 formatter rejects**, which are mainly explicit structural conflicts
   around `PLAYER_NAME`, `WAIT`, `OP_32`, `OP_34` or `CHOICE_BEGIN` and must remain
   event-specific unless a genuinely general structure is proven;
2. resume Android-English structural alignment on the **237 unresolved semantic IDs**
   spread across the 161 alignment-incomplete events, continuing to reject weak mappings;
3. keep the short decorated-choice spacing before the terminal `)` as a separate cosmetic follow-up.

After each accepted batch, regenerate `dialogue-auto` only when semantic identity changes,
regenerate `dialogue-format-mass`, require 0 errors / 0 warnings / 0 implicit wraps, rebuild
only modified components, recombine `all.ips`, and preserve the active HTML review badges.
