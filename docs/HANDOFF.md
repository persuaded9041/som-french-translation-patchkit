# Development handoff — Round 76

Operational handoff only. Historical evidence remains in `docs/ANDROID_TEXT_ALIGNMENT.md`,
`docs/DIALOGUE_FORMAT.md`, `docs/TEXT_RESEARCH_NOTES.md`, and the archived review files.

## Current checkpoint

- Reference ROM: unheadered **Secret of Mana (USA)**, `0x200000`, SHA-256 `4c15013131351e694e05f22e38bb1b3e4031dedac77ec75abecebe8520d82d5f`. Never store or redistribute it.
- Current state: **Round 76 — semantic component naming cleanup**. Dialogue payload remains the locked Round-72 automatic 216 px build.
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

Round 70 identified the long-line Potos artifact as a parser-capacity problem, not a compositor defect. `vwf_dialogues` now grants `+10` dialogue parser units, restoring **38 decoded glyphs per physical line**. Runtime tests on `pressentiment`, `lumière` and `cascade` validate that the former delayed/shifted 35th glyph is fixed.

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
- choice-specific geometry checks rather than applying the ordinary 216-px padded-row ceiling to choice rows;
- seven reviewed Round-72 outer-decoration removals reapplied from `mappings/android/dialogues_choice_layout_recipes.json`. The recipes contain only event/carrier identities. For `$0062` and `$00CF`, where semantic wrapping would otherwise create a fresh-page choice row, the same Android-FR prompt is deterministically retried with the compact wrapper before the reviewed parentheses are stripped.

The reproducibility amendment is intentional: `dialogue-format-mass` must regenerate the reviewed choice presentation, including the absence of the stripped parentheses, without relying on a previously generated `dialogues_french.json`. Do not replace these mechanisms with event-specific French strings. Temporary hard-coded strings are acceptable only for isolated diagnostics and must never enter canonical generated assets.

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

The full mass-import command remains the canonical regeneration path, although repeated end-to-end invocations may be slow in hosted environments. The committed `translations/dialogues_french.json` and `mappings/android/dialogues_format_mass.json` must both pass `--check`; a diff after regeneration is a checkpoint bug, not an expected local variation. Do not weaken deterministic validation merely to shorten a run.

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

## Round 77 — split `french_intro` / `vwf_intro`

The former hybrid `vwf_intro` component has been split by responsibility without changing the aggregate ROM. `french_intro` now owns the validated French event-$0400 payload, layout metadata, French glyph installation, `$E6` intro DTE threshold, private 25-pair intro DTE table/loader, and the event-$0401-$040F relocation required by the enlarged payload. `vwf_intro` now owns only the intro VWF runtime: renderer hook, private parser bridge, width/framing/compositor/outline path, WAIT cursor repair, and the validated intro runtime window.

Both components independently relocate unchanged stock events `$0401-$040F` to `$CA:FF70-$FFB7`. This overlap is intentionally byte-identical: `french_intro` needs the space for its enlarged `$0400`, while `vwf_intro` needs the following events outside its standalone runtime window. The VWF runtime window remains the already validated `$CA:0C02-$0E8A` (exclusive end `$0E8B`). `french_intro` asserts that its generated payload still ends exactly at `$0E8B`; changing that endpoint requires explicit runtime revalidation rather than silently widening the gate.

`vwf_intro` no longer installs French glyphs, changes the direct/DTE threshold, loads translation JSON, owns `intro_layout.json`, or installs the private DTE table. Its width table is generated against a virtual copy of the stock font with the canonical shared French glyph atlas inserted, preserving the exact validated metrics without taking ownership of the glyph bytes.

The split was verified structurally: after checksum recomputation, `french_intro.ips + vwf_intro.ips` reproduces the former Round-76 `vwf_intro.ips` byte-for-byte. A full 11-component rebuild produces an `all.ips` byte-for-byte identical to Round 76 (SHA-256 `5f909cd9b6f6c4d5aeb64cfc0634b5f3c4ffb850039c8a494efe745b0cc79478`; final SNES checksum `$177D`). The dialogue payload remains locked at Round 72 and is unchanged.

The canonical component list is now:

- `mana_tree_original`
- `name_entry_extended`
- `french_menus`
- `french_opening`
- `french_intro`
- `vwf_intro`
- `vwf_dialogues`
- `intro_skip`
- `french_dialogues`
- `vwf_ui`
- `french_resources`

## Round 76 — semantic component naming cleanup

Component IDs are now semantic and intentionally unnumbered. The migration is structural only: no renderer, translation payload, event data, or ROM behavior is intentionally changed. The canonical component IDs are:

- `mana_tree_original`
- `name_entry_extended`
- `french_menus`
- `french_opening`
- `french_intro`
- `vwf_intro`
- `vwf_dialogues`
- `intro_skip`
- `french_dialogues`
- `vwf_ui`
- `french_resources`

Aggregate precedence no longer depends on directory-name sorting. Every `component.json` carries an explicit integer `build_order`, and `shared/components.py` sorts by that field before building or combining patches. This preserves the validated historical merge order while allowing semantic folder names.

The naming families are deliberate: `french_*` owns translated payloads, while `vwf_*` owns VWF/runtime rendering. Round 77 completed that separation for the intro: `french_intro` owns the French payload/DTE/glyph side and `vwf_intro` owns only the renderer/runtime side.

The Ring Menu has also been observed in runtime to already render with VWF under the current `vwf_ui` foundation, likely through a shared path reached by the Forge work. Treat that as an observation to characterize, not as permission to broaden the UI gate: before changing Ring Menu code, trace and prove the exact existing builder/submit path and determine why VWF is already active.

The rename checkpoint was rebuilt from the clean USA ROM and compared against the pre-rename Round-75 baseline. All ten standalone IPS files are byte-for-byte identical to their former counterparts, and `all.ips` is also identical (SHA-256 `5f909cd9b6f6c4d5aeb64cfc0634b5f3c4ffb850039c8a494efe745b0cc79478`; final SNES checksum `$177D`). Text-source hygiene and the complete 2048-event structural/source round-trip audit also pass. This is therefore a naming/build-order cleanup, not a ROM-content checkpoint.

## Round 75 — standalone `vwf_ui` foundation

The Watts Forge long-name issue is now runtime-validated as solved and has been
cleaned into a new independent component: `vwf_ui` (`vwf-ui`). It has **no
component dependency**; it only installs byte-identical helpers from `shared/`.

Validated Forge chain and behavior:

- `$D0:D3B0-$D3C4` is the current-weapon `WEAPON_NAME` builder. The probe that
  replaced `$D0:D3C4 STA $19D3` with `STZ $19D3` forced every row to
  `Gant d'aura`, proving the left field.
- `$D0:D82F+` is the Forge suffix builder. Replacing its literal `$D0` arrow
  with `$CF` changed `→` to `←`, proving the suffix.
- a one-shot tag is now armed only at the exact submit of the Forge mini-event
  `$00:19D0` (X=`$19D0`, bank `$00`, immediately before `$D0:D5D7`). The earlier
  `WEAPON_NAME` helper remains stock. This prevents the tag from leaking into Watts'
  ordinary dialogue. The correct event bank at the renderer is `$1D03=$00`; CPU
  DB=`$7E` is a separate runtime fact.
- VWF rendering of the current weapon name is runtime-validated.
- fixed logical `TEXT_X` anchors 16/21 were the reason long French names were
  overwritten before rendering. The clean layout uses safe logical slots 20/25
  and compacts the whole `→... price GP` suffix at render time so it follows the
  actual VWF name width with one decoded space.
- the stock logical line budget needs extra headroom even when pixels remain.
  The exact Forge-submit-tagged path now receives **+3** logical units. +1 fixed the
  observed final `P` of `GP`; +3 was then stress-tested successfully with a
  temporary 19-character weapon name (`Glaive d'orichalque`). The temporary
  rename is **not** part of the component.
- `Fendeuse de dragon →... 25000GP` is runtime-validated on one line with the
  suffix positioned relative to the VWF-rendered name; a 19-character stress name
  also passed with the +3 budget.
- standalone `vwf_ui` is runtime-validated on a clean USA ROM: Forge weapon names
  render correctly in VWF, GAME SELECT remains stock/non-glitched, and Watts'
  ordinary dialogue remains stock/non-VWF.

Rejected Forge experiments stay rejected: `$D9`, `$C0:CB3C`, broad Forge-mode
gates, renderer-time `$FF69`, global parser hooks, `$C0:588E`, raster probes,
private-buffer-38 parser substitution, and event-pointer-gated capacity checks.
See `docs/FORGE_VWF_RESEARCH.md`.

`vwf_ui` is intentionally the future home for other proven non-dialogue VWF
paths (Ring Menu, item-acquisition UI, etc.). Each new path must get a narrow
identity gate; do not turn it into a global menu VWF switch.

The shared renderer entry now uses a byte-identical dispatcher installed by
`vwf_dialogues` and `vwf_ui`. `vwf_dialogues`'s dialogue classifier at `$ED:7040` remains
its owner; `vwf_ui` owns its own renderer at `$ED:7B00+`. On stock fallbacks
the dispatcher explicitly clears `$7E:9385`, preventing stale UI-VWF state from
corrupting GAME SELECT or other fixed-width callers. The shared stock-capacity
helper contains a dormant `vwf_ui` branch, enabled only by the `$C7:4C87=$09`
config marker plus the exact one-shot UI tag. Builds without `vwf_ui` preserve
prior behavior.

## Round 73 historical cleanup checkpoint

Round 73 deliberately contained no accepted Forge VWF change. Its safe hashes and
failed-probe history are retained in version history and in
`docs/FORGE_VWF_RESEARCH.md`; they are **not** the current production state.

## Next work — extend `vwf_ui` to other interface paths

The Forge backend is **finished and locked** unless a regression is demonstrated. The next
phase is to extend VWF coverage to other non-dialogue UI paths, one family at a time. Start
with `docs/UI_VWF.md`; do not infer that a renderer hook shared with the Forge is sufficient
identity by itself.

Recommended order:

1. **Ring Menu text** — inventory the exact builders/submit paths that produce fixed-width
   labels or resource names, then prove one narrow path with a harmless visual probe.
2. **Item-acquisition / pickup UI** — identify the builder used when an item/resource name is
   shown after pickup, including any quantity/status suffixes and fixed anchors.
3. Only after those are understood, consider other fixed-width UI families such as equipment,
   shop/status rows or context messages.

Rules for every new backend:

- preserve the locked dialogue path and do not broaden `vwf_dialogues`;
- `vwf_ui` stays standalone and owns rendering/layout only, never French resource text;
- `french_resources` stays standalone and owns reviewed `$CA` name translation only;
- prove the exact builder/submit identity before enabling VWF; prefer one-shot tags;
- preserve stock parser/buffer unless the target path itself proves a need for more capacity;
- clear UI-VWF state on every stock fallback so unrelated callers cannot inherit it;
- test the new backend with **09 alone on a clean USA ROM**, then with **all.ips**;
- regression-test GAME SELECT, Watts dialogue, Forge row, ordinary dialogues, and any UI family
  sharing the same low-level hooks.

The Forge investigation history is retained in `docs/FORGE_VWF_RESEARCH.md`; the reusable
extension contract is in `docs/UI_VWF.md`.

## Character-name review — concluded

The character-name research phase is complete. The user validated the conclusion that the
official French character names are sufficiently good to keep despite localization
disparities. Do **not** start a general character-renaming pass from this research. Only
correct a future demonstrable typo/inconsistency if it is reviewed separately.

## Current resource-name runtime state

The Android system-resource mapping remains deterministic at **475 mapped** resources.
The translated-name insertion now has a production component: `french_resources`.
It deterministically consumes the reviewed name-family subset of
`translations/text_resources_french.json` and is included in `all.ips`. The previously known
Watts/Matango long-weapon-name blocker is solved independently by `vwf_ui`.

The Forge fix does not hard-code French prose and does not own resource translation. It
only fixes the rendering/layout path, so the same UI component can support future proven
non-dialogue text paths.


## Round 75 — `french_resources` production integration

The clean Round-74 rebuild initially omitted the former research-only resource-name IPS because
it was not represented by a component manifest. This regression is fixed by the new standalone
`french_resources` component. `build.py --combine` now includes it automatically, so future
aggregate rebuilds cannot silently drop the reviewed French weapon/item/equipment/enemy/location
name resources. `vwf_ui` remains independent and owns no translations.

## Round 72 addendum — Android system-resource mapping scaffold

A deterministic Android-FR mapping layer now exists for the canonical 513 non-event
`$CA` text resources. The mapping layer remains the deterministic source/provenance scaffold. Production reinsertion of the reviewed **name families** is now owned by `french_resources`; descriptions, menu labels and parameterized system-message families remain outside that component.

Generated files:

- `mappings/android/text_resources_layout.json` — prose-free reviewed identity recipes;
- `mappings/android/text_resources_android.json` — generated SNES ↔ Android `systxt` provenance;
- `mappings/android/text_resources_android_review.html` — human-readable review;
- `translations/text_resources_french.json` — sparse generated French payload bound to
  canonical SNES position IDs.

Regenerate or verify with:

```bash
python3 tools/import_android_resources.py \
  --html mappings/android/text_resources_android_review.html
python3 tools/import_android_resources.py --check
```

Current result: **475 mapped / 4 unresolved / 34 deliberately excluded**. Full mapped
families are magic names (42), Mana spirits (8), weapon names (72), helmets (21),
armor (21), accessories (21), menu labels (9), enemies (128), weapon descriptions (72)
and magic descriptions (42). Item names map 12/13; `$0C5` is a stock `?` whose
positional Android slot is blank and is intentionally not claimed. Locations map 27/31.
The four unresolved location resources are `$1D7 SAGE'S CAVE`, `$1D9 TREE PALACE`,
`$1DA LOST CONTINENT`, `$1DD EMPIRE CASTLE`.

Identity rules are intentionally conservative. Stable resource families use explicit
reviewed ordered blocks, which allows known SNES→Android renames without fuzzy guessing.
Irregular boss/location families use exact Android-English identity inside bounded ranges;
duplicate labels are accepted only when occurrence order is explicit (`Mech Rider`) or
all candidate French payloads are identical. System resources `$1FF-$200` remain excluded
because Android uses parameterized templates there and they require a separate formatting
study before any reinsertion.

`translations/text_resources_french.json` is now consumed by `french_resources` for the
reviewed name families only (magic/spirit/weapon/equipment/item/enemy/location names).
Descriptions, menu labels and system-message families remain outside that production component
until their UI/formatting constraints are separately validated.

## Round 72 addendum — CA resource geometry/DTE insertion study

The next insertion study is now scaffolded without changing the production component
set or canonical dialogue output.

- `tools/audit_text_resource_layout.py` measures every mapped Android-FR CA resource
  against conservative clean-USA observed envelopes and checks runtime-profile charset
  compatibility.
- `shared.stock_text.encode_text_with_stock_dte()` reuses only stock DTE pairs valid
  under the ordinary/full-French `$E6` boundary. This removes the apparent storage
  growth caused by direct-byte-only encoding.
- Safe mapped subset dry run: **7,304 bytes vs 7,315 stock**, so deterministic in-place
  table/blob rebuilding is storage-feasible and no relocation is required.
- Audit state: **302 inside observed stock envelope / 170 geometry-review / 3 current
  profile blocks**. The envelope is not a proven UI hard limit.
- The three profile-blocked entries are enemy names `Double n°1`, `Double n°2`,
  `Double n°3`; direct `°=$E6` conflicts with the non-event upper-DTE boundary. They
  stay stock in the experimental test path; do not transliterate them silently.
- `tools/build_text_resources_test_patch.py` creates a clean-USA autonomous,
  research-only name test IPS by applying the current `all.ips` and then rebuilding
  the CA table/blob in place. Default result: **349 translated names**, 3 skipped,
  **7,056-byte blob**. This tool refuses any write beyond the original resource blob.
- `mappings/android/text_resource_names_geometry_review.html` contains only the name
  cases that exceed the observed US envelope or are profile-blocked.

Next: runtime-review the experimental names in item/magic/equipment/shop/status/battle
contexts. Use the focused HTML to prioritize long rows. Only after those geometries are
understood should a production resource component or formatting rules be approved.
Do not modify Round-72 dialogues while doing this work.
