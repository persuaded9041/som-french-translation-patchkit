# Development handoff — Round 85.3 maintenance checkpoint

Operational handoff. The archive accompanying this file is authoritative over GitHub.
Historical investigation remains available in specialist docs and Git history. The active
working tree has now been pruned so old generated review snapshots are no longer treated as
pipeline inputs.

## Current checkpoint

- Reference ROM: unheadered **Secret of Mana (USA)**, `0x200000`, SHA-256 `4c15013131351e694e05f22e38bb1b3e4031dedac77ec75abecebe8520d82d5f`. Never store or redistribute it.
- Current state: **Round 85.3 — repository cleanup after the post-audit dialogue checkpoint**.
- The user accepts this checkpoint for continued development. Full runtime validation of the newly audited dialogue cases is **deferred to the next complete playthrough**; do not describe these new cases as individually runtime-validated yet.
- Android semantic alignment remains **1798 / 1838 (97.8%)**. Do not force identity merely to reach 100%.
- Playable dialogue corpus: **701 events = 701 complete + 0 PARTIEL**.
- Current generated mass-format output: **1815 accepted semantic source IDs / 1947 sparse translation entries**.
- Exclusions remain `$0269`, `$02DE`, `$0603`, all routing-audited unused/orphan stock content.
- Static simulation baseline remains **0 errors / 0 warnings / 0 implicit runtime wraps** for the accepted corpus.
- Manual dialogue supplements: **17 entries = 15 translated + 2 validated structural suppressions**. `$0204/C9:902F` is no longer manual: its payload is reproduced from the proven Android-FR redistribution.
- Ordinary dialogue limits remain **38 decoded glyphs** and **216 px VWF advance** per physical line. `WAIT != NEWLINE`.

## Round 85 post-audit dialogue changes

Round 85 re-opened semantic coverage despite the former Round-72/84 assumption that the dialogue
payload was complete. The audit compared SNES carriers, Android EN identity, Android FR scene order,
existing redistributions, suppressions, and the actually generated `dialogues_french.json`.
Previously user-approved suppressions were intentionally rechecked rather than trusted automatically.

The resulting source-derived repairs cover 20 affected events in the review artifact. Important
families include:

- `$0103`: waterfall sword scene reconstructed from Android FR 3413–3434, including `hisse !`, the ghost sequence, sword handoff and return-to-village continuation.
- `$016D`, `$016E`, `$017F`, `$036D`, `$04E4`, `$052E`, `$0011`, `$015C`, `$04B3`, `$055E`: missing Android-FR units restored through deterministic coverage recipes.
- `$0399`, `$04E1`, `$0511`, `$0586`, `$0587`: partial Android-FR scene losses repaired without manual French prose.
- `$01DA`: local Android-FR scene wording restored without perturbing the broader historical alignment branch.
- `$03BA/$03BB`: corrected Android-FR redistribution ownership.
- `$0559`: Android 2151–2155 mini-transition added before `$0555`: three pause pages, Durac's `La salle derrière cet autel ! Vite !`, then dynamic `PLAYER_NAME(0) : Allons-y !`.

`mappings/android/dialogues_coverage_repair_recipes.json` and
`mappings/android/dialogues_redistribution_recipes.json` remain structural/source-ID recipes; French
prose continues to come from `sources/android/scrtxt_fr.bin`.

### Layout solver amendments

The audit exposed several bad-but-simulator-clean line-break choices. The current generator now
prefers source/carrier boundaries over arbitrary internal phrase breaks, while preserving dynamic
name bindings. In particular:

- a break must not detach leading punctuation such as `:` from the preceding `PLAYER_NAME`;
- when necessary, a carrier-boundary break may be materialized before the live `PLAYER_NAME` so
  `name + punctuation + beginning of reply` stays together;
- `live_player_name_prefix_reflow` reflows the whole soft sentence rather than reflowing only the
  first already-wrapped line and then appending stale continuation lines. This fixes orphan words
  such as `CA:1042` (`va` alone), and similarly improves `sa / mère !`-style artifacts;
- true sentence/page boundaries remain preserved and all candidates remain simulator-gated.

These are generic formatter rules. Do not replace them with event-specific French strings.

## Runtime-validation status

The existing pre-Round-85 runtime-validated contracts remain valid, including the VWF parser fix,
216 px / 38-glyph limits, choice geometry architecture, Name Entry stack, Forge/UI-VWF gates and
all earlier explicitly validated scenes.

The **new Round-85 post-audit dialogue changes are accepted for development but not yet individually
runtime-validated**. The user explicitly chose to defer that validation until playing the complete
game. A targeted checklist was produced during the audit; the highest-risk scenes are `$0103`,
`$0559`, `$04E1`, `$0511`, `$0586`, `$0587`, `$01DA`. If a future playthrough reports a regression,
re-open only the affected rule/event and preserve the source-derived pipeline.

## Name Entry state — keep locked

The Round-84 Name Entry stack remains fully runtime-validated and should not be reopened absent a
regression:

- `name_entry_extended`: generic 3-row keyboard;
- `french_name_entry_extended`: French 4th row;
- `name_entry_prefill`: editable stock-US defaults;
- `french_name_entry_prefill`: `Randy`, `Prim`, `Popoï`;
- real `ï` in `Popoï` validated from the first Name Entry screen.

## Manual-supplement policy after audit

Do not replace a manual supplement merely because an Android line elsewhere has the same meaning.
A replacement is allowed only when it is the **same dialogue unit or a proven redistribution of the
same scene**. This audit specifically rejected false substitutions for `$02E1` and `$04E8` even
though unrelated Android lines had similar meaning.

The two `suppressed` manual entries (`$013A/C9:40D7` and `$04E1/CA:2C84`) remain useful provenance
locks for validated structural omissions and must not be removed casually.

## Canonical regeneration / checks

Canonical full dialogue regeneration remains:

```bash
source .venv/bin/activate
python3 tools/import_android_text.py --only dialogue-format-mass \
  --rom "Secret of Mana (USA).sfc"
```

It is currently slow enough to dominate iteration time. Do **not** weaken deterministic checks to
make it faster.

After dialogue-related changes, preserve the usual checks:

```bash
python3 tools/import_android_text.py --only dialogue-format-mass \
  --rom "Secret of Mana (USA).sfc" --check
python3 tools/check_dialogue_regressions.py
python3 tools/check_dialogue_redistribution_recipes.py
python3 tools/check_manual_dialogue_supplements.py
python3 tools/check_text_source_hygiene.py
python3 tools/check_text_roundtrip.py "Secret of Mana (USA).sfc" --scan-all-events
```

The Round-85 recipe checker baseline includes **18 redistribution events**. Manual supplements are
**17 = 15 translated + 2 suppressed**.

Stored patch baseline: `patches/all.ips` remains SHA-256 `f4f8e8450882f8520b618814e53c043cf935462b6d29dbd31ed697fa48ed9ec0` and yields the accepted `$8E10` aggregate ROM. A fresh full rebuild currently changes only `french_dialogues.ips` (`7d45be25…` stored -> `9066ac6d…` rebuilt), which changes the aggregate checksum to `$84C5`. This is a pre-existing source/output reproducibility mismatch exposed during maintenance; do not overwrite the stored baseline until the dialogue-generation/build path is reconciled.

## NEXT WORK — simplify dialogue generation, then optimize

Do **not** start object/item translation yet. Repository cleanup is complete enough to simplify the active dialogue-generation path next.

Priority order:

1. simplify `import_android_text.py` / dialogue generation so canonical inputs, optional
   reproducible caches and outputs are explicit;
2. prove `translations/dialogues_french.json` can be regenerated when absent and is never
   consumed as an input;
3. reduce coupling of regression checks to generated `mappings/android/*.json` where practical;
4. only then profile the simplified path and add memoization/other optimizations;
5. revisit multiprocessing only if profiling still identifies coarse event-local CPU work.

`patches/` is deliberately retained for now. `artifacts/` and obsolete generated mapping/review
reports have been removed.
