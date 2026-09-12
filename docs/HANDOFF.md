# Development handoff — Round 85

Operational handoff. The archive accompanying this file is authoritative over GitHub.
Historical investigation remains available in the specialist docs and review files, but the next
session should deliberately reduce that historical surface after proving which files are still
consumed by the build/check pipeline.

## Current checkpoint

- Reference ROM: unheadered **Secret of Mana (USA)**, `0x200000`, SHA-256 `4c15013131351e694e05f22e38bb1b3e4031dedac77ec75abecebe8520d82d5f`. Never store or redistribute it.
- Current state: **Round 85 — post-audit dialogue coverage/layout cleanup**.
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
python3 tools/check_round67_targeted_dialogues.py
python3 tools/check_round68_scene_redistributions.py
python3 tools/check_round69_dialogue_completion.py
python3 tools/check_dialogue_redistribution_recipes.py
python3 tools/check_manual_dialogue_supplements.py
python3 tools/check_text_source_hygiene.py
python3 tools/check_text_roundtrip.py "Secret of Mana (USA).sfc" --scan-all-events
```

The Round-85 recipe checker baseline includes **18 redistribution events**. Manual supplements are
**17 = 15 translated + 2 suppressed**.

Final cleanup rebuild proof: aggregate `patches/all.ips` builds from the 14 stored components to a 3 MiB ROM with SNES checksum **`$8E10`**. `patches/all.ips` SHA-256: `f4f8e8450882f8520b618814e53c043cf935462b6d29dbd31ed697fa48ed9ec0`.

## NEXT WORK — performance + repository simplification

This is the priority for the next session. Do **not** start object/item translation yet.

### 1. Profile and accelerate JSON generation

The user's development machine is an **Intel i5-10600K (6 cores / 12 threads)** and current
`dialogue-format-mass` visibly uses only one core. Before parallelizing:

1. profile the canonical command (`cProfile` and/or `py-spy`) and record the top CPU consumers;
2. separate truly event-local expensive work from global calibration/aggregation;
3. add memoization/caching first where repeated width measurement, decode/encode, formatting or
   simulation work dominates;
4. only then evaluate `multiprocessing` / `ProcessPoolExecutor` for event-independent work;
5. start around **4–6 workers**, not 12, and benchmark wall time / CPU / memory;
6. preserve deterministic ordering and byte-identical JSON/report output between 1 worker and N workers;
7. add an easy serial fallback and ideally a `--jobs N` option rather than making parallelism implicit.

No optimization is accepted if it changes `dialogues_french.json`, alignment decisions, simulation
results, recipe ownership or report ordering.

### 2. Reduce historical repository clutter

Current Round-85 archive before this cleanup contained roughly **327 files**, including **74 files
at `mappings/android/` top level**. This is now an explicit maintenance problem.

Do an evidence-based dependency audit before deleting anything. Major candidate families:

- `mappings/android/dialogues_review_round*.json` and `*_context.html`;
- old worklists (`dialogues_review_worklist_roundXX*.html`);
- Round-56/57 omission review reports;
- one-off generated review HTML/CSV files that are not build/check inputs;
- per-round checker scripts `tools/check_round62_*` through `check_round69_*` that may be
  consolidatable into one declarative regression checker;
- specialist historical docs that can be moved under a single `docs/history/` area if still useful.

Desired end state:

- root `mappings/android/` contains only canonical machine inputs/outputs needed for regeneration,
  current review artifacts, and compact provenance metadata;
- historical human-review evidence is either removed if redundant or moved to a clearly named
  archive/history directory;
- checks use declarative data wherever possible instead of accumulating a new Python script per round;
- generated review HTML/CSV should not be committed unless it is intentionally part of the handoff;
- README/HANDOFF should describe the current system, not force readers through dozens of historical
  rounds to understand what is active.

Measure file count/size before and after, and run the canonical checks/build after every cleanup
batch. Prefer several small deletion/move batches over one irreversible purge.

## Do not reopen without evidence

- Name Entry Round-84 behavior.
- Runtime-validated 216 px / 38-glyph dialogue contract.
- `WAIT != NEWLINE`.
- Choice VWF architecture and validated anchor/decoration rules.
- Forge/UI-VWF runtime-validated gates.
- Previously validated French wording merely as part of performance/repository cleanup.

Reference ROMs must never be included in archives.
