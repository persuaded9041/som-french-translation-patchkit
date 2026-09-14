# Dialogue post-audit non-regression validation

## Scope

Validation after the 12-batch exhaustive dialogue audit, comparing the final checkpoint against the original `som-cleanup.zip` handoff baseline.

## Result

**PASS — no collateral dialogue-text regression detected.**

### 1. All validated corrections remain active

- `tools/dialogue/check_regressions.py`: PASS, including targeted reviews and post-audit coverage repairs.
- Full translated simulation: **701/701 events**, **0 errors**, **0 warnings**, **0 implicit runtime wraps**.
- Speaker-label newline audit: **0 findings**.
- Rolling-scroll candidate audit: **0 findings**.
- Redistribution recipes: **302 active carriers**, PASS.
- Source hygiene: PASS.
- Source round-trip: **713 events / 87,487 bytes**, exact.
- Structural scan: **2048 scripts parse**.

Key invariants sampled directly from the final generated JSON:

- `$035F / C9:D1B8` = `Dryade fera réagir l'orbe !`.
- `$0020 / C9:09A7` = `%S(0,0) : Tiens donc...`.
- `$0021 / C9:09F8` = `%S(0,0) : Ah bon ?`.
- `$0023 / C9:0A8E` keeps `%S(0,0) :` with the phrase instead of a label-only line.
- `$00AA / C9:1573` retains the reviewed rolling-scroll marker.
- `$01DA / C9:7D47` contains the validated Android-FR wording ` : Ah bon ?! / Comment ça ?`.
- `$0295 / C9:AF50` contains the validated local adaptation `Hé, salut !` without the historical dynamic vocative.
- `$042D / CA:148B + CA:148E` explicitly materializes ` : ` and `...`.

### 2. Baseline → final carrier comparison

Baseline: **1957 carriers**. Final: **1959 carriers**.

- **1807 baseline carriers are byte-for-byte unchanged.**
- **150 existing carriers changed.**
- **2 carriers were added intentionally** (`CA:148B`, `CA:148E`).
- All **152/152 changed or added carriers** belong to events explicitly targeted/reviewed in the 12 audit reports.
- **0 changed carrier belongs only to a non-targeted event.**

Among the 150 changed existing carriers:

- **148 are layout/control/spacing-only changes**. After removing whitespace and pagination/control separators, their character payload is identical to the baseline.
- Only **2 existing carriers change actual character content**, both explicitly validated:
  - `C9:7D47`: old historical `: Hein ? Où ça ?` → Android-FR ` : Ah bon ?! / Comment ça ?`.
  - `C9:AF50`: removes the validated historical `%S(0,0)` insertion from `Hé, salut %S(0,0) !`.
- The other 2 semantic additions are the explicit `$042D` punctuation carriers noted above.

### 3. Canonical semantic/structural inputs unaffected

The following are byte-identical between the original handoff archive and the final checkpoint:

- `assets/dialogues.json`
- `recipes/android/dialogues_reviewed_alignment.json`
- `recipes/android/dialogues_redistribution.json`
- `translations/dialogues_manual_supplements.json`

Therefore this audit did not silently alter the stock source scripts, Android identity/alignment layer, redistribution mapping, or manual supplement payloads. Changes are confined to the reviewed formatting/review layers and their explicitly approved structural repairs.

### 4. WAIT/scroll risk comparison

Final simulation still reports four informational `WAIT00_THIRD_LINE_SCROLL_RISK` entries:

- `$0081`
- `$013A`
- `$01B5`
- `$028A`

These are **not new**. The original baseline had six such entries: the same four plus `$01B9` and `$0250`. The post-audit state therefore reduces this class from **6 → 4** and introduces **0 new WAIT00 third-line risk**.

All four remaining cases were manually reviewed during their respective audit batches and retained as intentional/readable flows.

## Final hashes

- `translations/dialogues_french.json`: `4c71ee39ef1c10acbff1934401afdb4ded788bb525b7282c5a8227606863be82`
- `patches/french_dialogues.ips`: `006281fc3240ccef2ab10abe0d3a307ed274d13ab58d62a52503776c64b06c79`
- `patches/all.ips`: `a4510f1675a9b0be80518961338d847b3218f296dfa74032954b6b79570dc2e4`

## Conclusion

The post-audit validation finds no evidence that the approved corrections negatively modified untargeted dialogue phrases. The final state preserves the untouched corpus byte-for-byte at carrier level, confines all changes to reviewed events, and passes the project-wide simulation, regression, provenance, redistribution, and structural checks.
