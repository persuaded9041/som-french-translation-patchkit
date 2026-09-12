# Development handoff — Round 85.28 generated-output cleanup

Operational handoff. The accompanying archive is authoritative over GitHub.

## Current state

- Reference ROM: unheadered **Secret of Mana (USA)**, `0x200000`, SHA-256 `4c15013131351e694e05f22e38bb1b3e4031dedac77ec75abecebe8520d82d5f`. Never redistribute it.
- Android semantic alignment: **1798 / 1838 (97.8%)**, with 40 deliberately unresolved carriers.
- Playable dialogue corpus: **701 complete events, 0 PARTIEL**, **1947 sparse translation entries**.
- Exclusions: `$0269`, `$02DE`, `$0603`, all routing-audited unused/orphan stock events.
- Static simulation: **0 errors / 0 warnings / 0 implicit runtime wraps**.
- Ordinary line contract: **<= 38 decoded glyphs** and **<= 216 px**. `WAIT != NEWLINE`.
- Manual dialogue supplements: **17 = 15 translated + 2 validated structural suppressions**.
- Round-84 Name Entry remains locked and runtime-validated. Round-85 post-audit dialogue additions are accepted for development; targeted runtime validation is deferred to the next full playthrough.

## Canonical dialogue provenance

`dialogue-format-mass` must be able to regenerate the complete playable French corpus without an existing `translations/dialogues_french.json`. Translated prose comes from the original Android resources at generation time. Never solve a formatter/layout problem by copying French prose from a previously generated dialogue JSON into Python or a recipe.

Canonical inputs are:

- `assets/dialogues.json` — clean-USA SNES event source;
- `sources/android/scrtxt_en.bin` — Android-English identity layer;
- `sources/android/scrtxt_fr.bin` — Android-French localized prose;
- reviewed structural recipes under `mappings/android/`;
- `translations/dialogues_manual_supplements.json` only for genuine reviewed non-Android material/suppressions;
- clean USA ROM for VWF metrics during mass formatting.

Active structural recipe files:

- `dialogues_reviewed_alignment_recipes.json`;
- `dialogues_redistribution_recipes.json`;
- `dialogues_mapping_layout_recipes.json`;
- `dialogues_layout_search_recipes.json`;
- `dialogues_coverage_repair_recipes.json`;
- `dialogues_choice_layout_recipes.json`.

Recipes may store identities, Android token references, SNES carriers, punctuation, case transforms, offsets and layout/control operations. They must **not** store translated prose. `tools/check_text_source_hygiene.py` enforces the key provenance constraints.

Generated outputs/reports include `translations/dialogues_french.json`, `mappings/android/dialogues_auto.json`, `dialogues_unmapped.csv`, `dialogues_format_mass.json` and `dialogues_format_mass_excluded.csv`. They are not source dependencies.

Round 85.28 removes `translations/dialogues_french.json`, `translations/text_resources_french.json` and `mappings/android/text_resources_android.json` from the tracked checkpoint and ignores them in `.gitignore`. They are deterministic review outputs and are regenerated only when explicitly requested. Normal component/root builds must succeed with all three absent.

## Active tool surface

`tools/import_android_text.py` now exposes only:

```bash
python3 tools/import_android_text.py --only intro
python3 tools/import_android_text.py --only dialogue-auto
python3 tools/import_android_text.py --only dialogue-format-mass --rom "Secret of Mana (USA).sfc"
```

Historical pilot/review/batch modes were removed. Their useful runtime/identity decisions were consolidated into the canonical alignment and structural recipe layers. Round 85.7 moved reviewed identity tables out of executable Python. Round 85.8 then split the former monolithic importer into `tools/dialogue_pipeline/` modules while keeping `tools/import_android_text.py` as the stable CLI facade. Round 85.9 established the first optimized serial path. Round 85.10 keeps the same architecture and removes a second set of small, measurable sources of repeated work without changing serialized outputs.

Current module boundaries:

- `common.py` — Android binary decoding and shared source/alignment helpers;
- `policies.py` — reviewed non-prose policy constants;
- `alignment.py` — Android/SNES automatic alignment and reviewed-identity integration;
- `recipes.py` — structural recipe loading, validation and Android-token rendering;
- `formatter.py` — dialogue formatting, layout repair, simulation gating and mass-generation orchestration.

`import_android_text.py` is intentionally small and should not reacquire formatter/alignment internals.

A from-scratch mass generation currently reproduces `translations/dialogues_french.json` **byte-for-byte**: 701 complete events / 1947 entries. Reviewed layout-search recipes are tried before generic fallback searches when applicable; every applied recipe is independently simulated, and the historical generic/exhaustive fallback remains available if a recipe no longer fits current Android-derived text.

Round 85.9 prepares the canonical `assets/dialogues.json` text/event index once for the internal shared formatting hot path instead of rebuilding the same index thousands of times. Round 85.10 makes all formatter-owned lookups consistently use that prepared index, prepares repeated source/Android spans once per alignment session, reuses ranking results inside one immutable candidate index, prepares positional-neighborhood evidence once per alignment pass, and keys lexical metric reuse by the normalized strings that actually define the metric. On the checkpoint environment, five canonical mass checks measured **5.72 / 5.78 / 5.86 / 5.77 / 5.84 s** (median **5.78 s**) while all dialogue outputs remained byte-identical. `dialogue-auto` remains fully recomputed from Android/SNES sources and is not replaced by a generated-output cache.

For clean temporary verification, all outputs can be redirected:

```bash
python3 tools/import_android_text.py --only dialogue-format-mass \
  --rom "Secret of Mana (USA).sfc" \
  --output /tmp/dialogues_french.json \
  --format-report /tmp/dialogues_format_mass.json \
  --excluded-csv /tmp/dialogues_format_mass_excluded.csv
```

## Checks after dialogue pipeline changes

```bash
python3 tools/import_android_text.py --only dialogue-format-mass \
  --rom "Secret of Mana (USA).sfc" --check
python3 tools/check_dialogue_regressions.py
python3 tools/check_dialogue_redistribution_recipes.py
python3 tools/check_manual_dialogue_supplements.py
python3 tools/check_text_source_hygiene.py
python3 tools/check_text_roundtrip.py "Secret of Mana (USA).sfc" --scan-all-events
```

Do not reopen dialogue wording/identity without a concrete regression. Do not start object/item translation during maintenance work.

## Next work

The next maintenance phase is a **component-by-component audit**. Do not add new functionality as part of this pass unless a concrete regression requires it. The goal is to make every component easier to understand, reproduce, combine and maintain before starting another feature phase.

Audit one component at a time. For each component:

1. **Understand the active implementation.** Read its `README.md`, `component.json`, builder, ASM/source, assets and any component-specific documentation. Record what it actually changes in the ROM today, which ROM/WRAM ranges and hooks it uses, which inputs are canonical, which outputs are generated, and whether it has assumptions about other components. Prefer the current implementation over historical descriptions.
2. **Remove dead or superseded material.** Look for unused files, obsolete test/prototype scripts, dead branches, stale constants/comments, temporary assets, duplicated helpers and historical artifacts that no longer participate in build/tests/documentation. Verify references before deleting anything.
3. **Simplify the component documentation.** Its README should primarily describe the current architecture, inputs, outputs, memory allocations, build/test commands and important constraints. Do not turn it into a round-by-round changelog. Keep only genuinely useful research notes that prevent known bad paths from being repeated.
4. **Audit ASM and memory documentation.** Check documented CPU addresses, ROM offsets, hooks, reserved ranges, WRAM usage, bank assumptions and ASM comments against the actual generated code. Keep `docs/MEMORY_MAP.md` synchronized. Correct stale documentation even when runtime behavior is already validated.
5. **Check standalone/combinable behavior.** Each component should, where technically possible, build and work from a clean USA ROM by itself and remain composable with the other components. Pay special attention to global hooks, extended-ROM banks, callbacks and loaders shared indirectly with another component.
6. **Check reproducibility.** Build from the real source assets rather than relying on an existing generated output. Generated IPS/JSON/binaries must not silently become canonical inputs. Where useful, temporarily remove generated outputs and confirm they can be rebuilt.
7. **Look for simplifications and sensible optimizations.** Profile only when something is measurably slow. Prefer removing redundant work or obsolete historical constraints over clever micro-optimizations. Any retained optimization must remain deterministic, readable and maintainable. Do not sacrifice component independence for build speed.
8. **Validate before moving on.** Run the standalone build and relevant checks. If logic did not change, compare the IPS byte-for-byte when meaningful. If logic deliberately changed, document why the IPS changed. Rebuild/combine the full project after any change that touches runtime hooks or shared memory. For substantial runtime changes, produce a standalone test IPS and obtain runtime validation before declaring the change final.

At the end of each component audit, summarize what was removed or simplified, any corrected memory/ASM documentation, any optimization retained or rejected, and the standalone/combined validation status. Make a checkpoint when the audit causes meaningful repository or runtime changes. Do not mix several major runtime refactors into one checkpoint.

Suggested order, starting with relatively isolated components and using them to establish the audit method:

1. `mana_tree_original` (`01_japanese_mana_tree`);
2. the Name Entry components (`02_9char_names` / generated French variants);
3. `game_select` / French menu-selection components;
4. `french_opening` — mostly a verification/documentation pass after the Round-85.13 literal-stream cleanup;
5. `vwf_intro` / French intro components;
6. `vwf_dialogues`;
7. dialogue/text reinsertion components;
8. `vwf_ui`;
9. remaining resource/menu/helper components.

For this phase, begin with **`mana_tree_original`**. It is a good first audit target because it is small enough to inspect completely but has a global resource-loader hook and `$EF` allocations that must be documented precisely.

### Component audit progress

`mana_tree_original` has completed its audit pass. Its standalone IPS and the complete combined `all.ips` remain byte-for-byte identical to the Round-85.13 snapshots. The audit removed only a redundant rewrite of 29 trailing `$FF` bytes already present in the validated tree resource and an unused ASM constant; it also clarified the `$C1:4CF6` global hook, `$D2A9` resource-ID gate, `$EF:C000/$EF:F800` allocations, and absence of private WRAM. The stale root `MEMORY_MAP` entry claiming that `french_opening` still occupied `$EF:8000-$BFFF` was removed; Round 85.13 opening data lives in `$EE`.

`name_entry_extended` has now completed the second audit pass. The active architecture is the generic three-row 9-character foundation: maximum length at `$C0:319C`, compact Up/Down handlers in the former `$C0:3583-$35AE` resource area, private layout at `$C7:4E00-$4E6A`, selection lookup redirected to the relocated `$E4:4000` resource, stock `$60` initial selector, and no private WRAM. The audit removed an obsolete 153-byte English-help limit left over from the old stale-tail concern; the French dependent overlay’s useful localized payload extends beyond the current generic payload, so no English tail survives composition. Documentation now records exact hook/range boundaries. Runtime bytes are unchanged: standalone `name_entry_extended.ips` and the complete `all.ips` remain byte-for-byte identical to the previous snapshots. Dependency builds with `french_name_entry_extended` and `name_entry_prefill` pass the declared overlap audit.

`french_name_entry_extended` has now completed the third component audit pass. The runtime architecture remains unchanged: it overlays the generic base with validated selector states `$50/$60/$70/$80`, the fourth French row, localized help/glyphs, and the small bank-`$E4` / `PLAYER_NAME` DTE router. The stale ASM comment claiming that `$80` was the added row was corrected to `$50`. Static navigation/layout bytes were moved out of the builder into `src/patch_data.py`, matching the organization of the generic component while keeping `src/*.asm` as readable maintenance mirrors. Documentation now distinguishes the 52-byte live DTE helper from its 64-byte reserved slot and records the real resource-overlay behavior: useful French bytes extend through `$E4:4188`, beyond the generic payload end `$E4:415C`; zero tail bytes in clean expanded ROM are not emitted into IPS records. Runtime bytes remain unchanged.

`name_entry_prefill` has now completed the fourth component audit pass. The runtime architecture remains unchanged: the four-byte Name Entry init tail at `$C7:5039` jumps once to the 113-byte helper at `$C7:4630-$46A0`, which feeds configured characters through the stock `$C7:50E0` selector and `$C7:5124` insertion paths, then restores the original grid cursor. The three component-local 8-byte records at `$C7:46D0-$46E7` contain one length byte plus up to seven upper/lowercase tokens; this record limit is intentionally separate from the editor's nine-character capacity. `$A1CD` is only transient loop scratch and is cleared before return. The audit replaced the duplicated raw helper hex blob in `build_patch.py` with structured `MiniAssembler` emission matching the existing readable ASM mirror, and corrected the ASM comment that incorrectly described an 8-byte record as being "per character" rather than per role. Runtime bytes remain unchanged: standalone `name_entry_prefill.ips` is byte-for-byte identical to the previous snapshot (SHA-256 `306ba2d5fc160b63d7a778eaecea4223cafe757b27de93ea826c196e1673ad59`). The generic dependency stack reports 0 identical / 4 declared overlap bytes; the complete four-component Name Entry stack reports 162 identical / 303 declared overlap bytes. Source hygiene passes, and the complete `all.ips` remains byte-for-byte identical at SHA-256 `a12f3540ba2f086c9833b2503c49ca509957cf8b6cebf106ff98cca729cb290b`.

`french_name_entry_prefill` has now completed the fifth component audit pass. The overlay remains deliberately narrow: it owns only the 130-byte French-capable helper at `$C7:4630-$46B1` and the three French 8-byte records at `$C7:46D0-$46E7`; the generic component still owns the `$C7:5039` hook and `french_name_entry_extended` still owns the fourth-row keyboard/glyphs. The audit removed `src/prefill_fr.asm`, which contained comments only and was neither an executable source nor a faithful ASM mirror. The README and compatibility notes now document the exact overlap boundary (`$C7:4630-$46A0`), the extra non-overlapping helper tail (`$46A1-$46B1`), the `$C0-$DF` fourth-row token class, the seven-character record limit, and the absence of private WRAM. Runtime bytes remain unchanged; standalone and full Name Entry composition are byte-identical to the previous checkpoint, and the complete `all.ips` remains byte-identical.

`french_menus` has now completed the sixth component audit pass. The validated fixed-width GAME SELECT / GAME FILE runtime remains unchanged: the 45-byte GAME SELECT label resource lives at `$C7:4400-$442C`, its current derived frame widths remain `$07/$05/$06`, GAME FILE is rebuilt at `$C7:4D40-$4DBE` with the stock-path mirrors preserved, FILE/Fichier keeps the validated `$04` frame width, and the two direct level-prefix writes remain `N`. The component owns the shared `basic_french` `$D4-$E0` glyph subset and its historical standalone `$E1` DTE threshold, but allocates no private WRAM. The audit removed `src/game_select_text.asm`, which was a hand-maintained non-executable map duplicating values already owned by the builder and memory documentation. Builder guardrails now reflect the actual combined allocation boundaries: GAME SELECT relocation must stay below `$C7:4440`, WELCOME is bounded to `$ED:8000-$83FF`, and GAME FILE save help owns `$ED:8400-$FFFF`. These guardrail/documentation changes do not alter current output. Standalone `french_menus.ips` remains byte-for-byte identical (SHA-256 `aaab8a8bb33279b99249959afb335b72c95c9d6a14db25769593413c5bd7c8db`), source hygiene passes, and the complete `all.ips` remains byte-for-byte identical at SHA-256 `a12f3540ba2f086c9833b2503c49ca509957cf8b6cebf106ff98cca729cb290b`.

`french_opening` has now completed the seventh component audit pass. The runtime-validated presentation remains unchanged. Canonical prose still comes from root `assets/opening_text.json` plus `translations/opening_text_french.json`, and the editable opening font remains `components/french_opening/assets/opening_font.png`; generated IPS/ROM/layout outputs are not inputs. The active 37-byte renderer helper occupies `$EE:9000-$9024` inside the reserved `$EE:9000-$9FFF` region, while the regenerated arrangement remains a literal-only stock compression stream in `$EE:A000-$BFFF` loaded by the stock `$C1:0014` path into `$7E:5000`. The audit corrected the stale `$EE:8000` comment in `src/opening_hook.asm`, documented the actual title-code patch points (decompressed offsets `$0845` and `$2D8D`), made the two `$EE` reservation ends explicit builder constants instead of magic literals, and simplified the component README/memory map around current canonical inputs, hooks and constraints. Historical optimization documentation was retained because the optimized LZ compressor is still active for title-code/font blocks and the failed raw-copy experiment remains important compatibility knowledge. Runtime bytes remain unchanged: standalone `french_opening.ips` is byte-for-byte identical (SHA-256 `e041bad47c0707c06140eb26598b1575bbe0c88bdc00889b76d24f21001bea82`), source hygiene passes, and the complete `all.ips` remains byte-for-byte identical at SHA-256 `a12f3540ba2f086c9833b2503c49ca509957cf8b6cebf106ff98cca729cb290b`.

`french_intro` has now completed the eighth component audit pass. The validated event `$0400` text, layout, WAIT/CLEAR timing and private DTE scheme remain unchanged. Canonical prose still comes only from root `assets/intro_event.json` plus `translations/intro_event_french.json`; component-local `assets/text/intro_layout.json` contains structural word-count/page metadata only. The audit completed the component memory map by documenting the 15 relocated-event pointer writes at `$C9:F802-$F81F` and the canonical `$D4-$E5` glyph installation at `$D2:DFF0-$E0C7`, in addition to the existing `$C7:4C40` loader, `$C7:4D00` private DTE table, `$CA:0C02-$0E8A` rebuilt event and `$CA:FF70-$FFB7` relocation. The builder now has explicit non-binary reservation guards preventing the 44-byte DTE loader from reaching shared VWF config at `$C7:4C80`, the 50-byte private table from reaching GAME FILE at `$C7:4D40`, or the following-event relocation from reaching `intro_skip` at `$CA:FFC0`. `RELOC_SOURCE_START` now derives from the stock intro endpoint instead of duplicating the same literal. No private WRAM belongs to this component; that runtime state remains owned by `vwf_intro`. Runtime bytes remain unchanged: standalone `french_intro.ips` is byte-for-byte identical (SHA-256 `9bc4f66d56da0cf9c4a7c82a121a24d7b9b7e56e4e6653863114a73c975cd8c2`), the selected `french_intro`/`vwf_intro` overlap audit reports 101 identical + 4 declared bytes, source hygiene passes, and the complete `all.ips` remains byte-for-byte identical at SHA-256 `a12f3540ba2f086c9833b2503c49ca509957cf8b6cebf106ff98cca729cb290b`.

`vwf_intro` has now completed the ninth component audit pass. The runtime-validated intro-only VWF behavior remains unchanged: `$C0:1664` gates the renderer to bank `$CA` and `$0C02-$0E8A`, the renderer/advance table remain at `$C7:4285-$437C` / `$C7:4440-$44BF`, shared parser/framing/row/compositor helpers remain byte-identical with `vwf_dialogues`, and the private decoded buffer remains `$7E:9390-$93BB` with intro scratch at `$7E:9380-$9389`. The audit completed the component memory map by documenting the 15 `$0401-$040F` pointer rewrites at `$C9:F802-$F81F`, which are performed byte-identically by `french_intro`, and clarified that the relocated stock block `$CA:FF70-$FFB7` must remain below `intro_skip` at `$CA:FFC0`. The builder now mirrors `french_intro` with an explicit relocation-limit guard and a named stock intro endpoint constant; these are non-binary maintenance guards only. The concise README now separates runtime ownership from the virtual-font metric-generation trick and translation ownership. Runtime bytes remain unchanged: standalone `vwf_intro.ips` is byte-for-byte identical to the previous snapshot (SHA-256 `320d02c25cd9dbe762079ab2eb51b0e0fe32ac3ced2b834dba9d5e13cdd6192a`).

`vwf_dialogues` has now completed the tenth component audit pass. The runtime-validated event/dialogue renderer remains unchanged: the renderer is still caller-gated to the event-engine `$C0:1150 -> $1664` path and stock `$C9/$CA` or relocated `$E8-$EC` event banks; GAME SELECT and other shared-renderer callers stay fixed-width. Parser mode 2 still uses the shared 44-byte `$7E:9390-$93BB` buffer with the 38-glyph contract, pixel-aware source preflight, generic interrupted-chunk physical-cell conversion, exact-tag post-outline repair and the existing measured-end two-option choice geometry. The audit found documentation drift rather than a runtime defect: the shared capacity helper is 66 bytes at `$C7:4BC0-$4C01` (not 42 bytes ending at `$4BE9`), the char-end helper is 53 bytes at `$ED:70C0-$70F4`, and the char-start helper is 90 bytes at `$ED:7180-$71D9`. The local/root memory maps now also record the shared `$C0:163D` outline-preparation byte, the `$C7:4570-$45EE` DTE router, the `dialogue_french` `$D2:DFE4-$E0DF` glyph span and the shared renderer dispatcher at `$ED:7A00-$7A2B`. The same shared-capacity range correction was propagated to `components/vwf_intro/docs/MEMORY_MAP.md` so the two audited VWF components no longer disagree. One concrete maintenance guard was tightened: the choice-tracker block at `$ED:7910-$792A` is now bounded by the real next allocation, shared dispatcher start `$ED:7A00`, instead of the overly permissive `$ED:8000`; current bytes are unchanged. The README was shortened by moving detailed Potos endpoint arithmetic to `ARCHITECTURE.md`, and stale numeric component-name comments were replaced with semantic names. Standalone `vwf_dialogues.ips` remains byte-for-byte identical (SHA-256 `32f2754dedb1721afc826d70afe42abe9f8c9bfa1a106ac870650e5bf044fe20`), source hygiene passes, the complete combination still reports 6537 identical + 655 declared/special overlap bytes, and `all.ips` remains byte-for-byte identical at SHA-256 `a12f3540ba2f086c9833b2503c49ca509957cf8b6cebf106ff98cca729cb290b`.

`intro_skip` has now completed the eleventh component audit pass. The runtime-validated behavior is unchanged: `$C0:012C` gates only bank `$CA` / pointer `$0C02-$0E8A`, holding R for 120 NMI frames redirects to the command-only cleanup script `$CA:FFC0-$FFC7`, and `$C0:AC34` clears an active hold on physical release so separate presses cannot accumulate. The audit made the component map precise: the 256-byte `$ED:7400-$74FF` reservation currently contains a 136-byte input helper at `$ED:7400-$7487` and a 30-byte NMI helper at `$ED:7490-$74AD`, with the remaining bytes intentionally free inside the reserve. The hook documentation now records the exact overwritten stock sequences restored by each helper and replaces the stale “component 05” wording with semantic `vwf_intro` ownership. The builder was maintenance-refactored only: helper/return SNES addresses now use named constants instead of duplicated literals, with generated hook bytes unchanged. Temporary `$7E:938A-$938B` reuse remains intro-only and mutually exclusive with `vwf_dialogues` because `vwf_intro` intercepts `$0400` first. Runtime bytes remain unchanged: standalone `intro_skip.ips` is byte-for-byte identical to the previous snapshot (SHA-256 `560a164906c05e895cef5c0b826e0dea5ad5a54e9cced589dd83ffff8258035d`).

`french_dialogues` has now completed the twelfth component audit pass (Round 85.25). The important architectural cleanup is that the normal standalone builder no longer consumes `translations/dialogues_french.json` as an input. It directly invokes the same canonical `make_dialogue_format_mass()` pipeline in memory from `assets/dialogues.json`, Android EN/FR binaries, reviewed structural recipes, manual supplements and the clean USA ROM. `--translation` remains only as an explicit diagnostic override. A strict test physically removed the generated JSON before building; the resulting standalone IPS remained byte-for-byte identical. A fresh CLI mass generation also reproduces the checked-in JSON byte-for-byte (701 accepted events / 1815 semantic source IDs / 1947 entries / 3 exclusions), proving the artifact remains fully derivable rather than canonical. `shared.translation_json` now exposes an in-memory `resolve_translation()` validator so the builder does not serialize/re-read a temporary JSON. `tools/check_text_source_hygiene.py` now guards against reintroducing a default generated-output dependency. The component README was reduced from historical formatter detail to current ownership, canonical inputs, relocation architecture and validation commands, and a component-local memory map was added. The shared relocation map now records the current 83-byte resolver helper at `$E8:1800-$1852` inside its `$E8:1800-$1FFF` reservation. Runtime dialogue wording, identities, serialization and relocation bytes are unchanged.

`vwf_ui` has now completed the thirteenth component audit pass (Round 85.26). The runtime-validated Round-74 Forge backend remains locked and byte-identical: the exact identity is still the submit of mini-event `$00:19D0`, the earlier `WEAPON_NAME` helper remains stock, `$ED:7E00` arms the one-shot `$7E:93C1=$A7` tag, the shared dispatcher at `$ED:7A00` routes only that invocation to the UI renderer at `$ED:7B00`, and stock fallbacks clear shared VWF-active state. The parser and stock decoded buffer remain untouched; the row is copied only at render time, the suffix is compacted after the measured weapon-name end, and the shared capacity helper grants +3 logical units only under the exact UI marker/tag. The audit removed stale experiment-only constants (`FORGE_MODE`, `WIDTH_TABLE_CPU`, `SLOT_INDEX`, `GLYPH_INDEX`, `RENDER_COUNT`) and corrected the memory documentation: the current backend does **not** reserve/use `$7E:93C3-$93C9`; only `$7E:93C1` is UI-private, while rendering reuses shared `$7E:9382/$9385/$938E-$938F` plus `$7E:9390-$93BB` after parsing. The local map now records the active spans inside their reserves: dispatcher 44 bytes `$ED:7A00-$7A2B`, renderer 174 bytes `$ED:7B00-$7BAD` within `$7B00-$7CFF`, width table `$ED:7D00-$7D7F`, and submit wrapper 39 bytes `$ED:7E00-$7E26` within `$7E00-$7E7F`. It also records the exact stock Forge edits at `$D0:D3D2-$D3D7`, `$D0:D83A` and `$D0:D878`. Runtime bytes remain unchanged: standalone `vwf_ui.ips` is byte-for-byte identical (SHA-256 `2acb7eee661deea5be8df02250aa33bb82a20ffbe4ab899e01bceb6bbc84b219`), source hygiene passes, the full combination still reports 6537 identical + 655 declared/special overlap bytes, and `all.ips` remains byte-for-byte identical at SHA-256 `a12f3540ba2f086c9833b2503c49ca509957cf8b6cebf106ff98cca729cb290b`.


`french_resources` has now completed the fourteenth and final component audit pass (Round 85.27). Runtime/resource bytes remain unchanged. The major maintenance correction mirrors the Round-85.25 dialogue fix: the normal component build no longer consumes generated `mappings/android/text_resources_android.json` or `translations/text_resources_french.json`. It invokes the canonical Android resource importer in memory from `assets/text_resources.json`, reviewed `mappings/android/text_resources_layout.json`, and `sources/android/systxt_en.bin` / `systxt_fr.bin`. A strict test physically removed both generated JSON outputs before building; standalone `french_resources.ips` remained byte-for-byte identical (SHA-256 `dc585b3d94a9179136e975b717befa2259a83a76ab7de51227a045acf5490d84`). The old `tools/build_text_resources_test_patch.py` experimental aggregate builder was removed because production insertion is now owned solely by the component. Component/root documentation now reflects the current 349 translated name resources, three intentionally stock `n°` enemy names, 7,056-byte in-place blob at `$CA:98E1-$B470`, 7,315-byte stock allocation through `$CA:B573`, complete pointer table `$CA:0800-$0C01`, shared DTE router/glyph writes, and zero private WRAM/relocation. `tools/import_android_resources.py --check`, source hygiene and the 513-resource round-trip all pass. The full combination still reports 6537 identical + 655 declared/special overlap bytes, and `all.ips` remains byte-for-byte identical at SHA-256 `a12f3540ba2f086c9833b2503c49ca509957cf8b6cebf106ff98cca729cb290b`.

Component-by-component audit is complete through `french_resources` (Round 85.27). Next maintenance step, if desired: perform one final project-wide consistency/consolidation pass across root documentation, component manifests, shared helpers, generated-output policy and dead historical references. Do not reopen validated runtime features or begin new object/item translation during that sweep.

Preserve the existing project-wide invariants while auditing components: do not reopen validated dialogue wording/identity without a concrete regression; `dialogues_french.json` remains a generated output; Android EN remains the dialogue identity layer and Android FR the localized prose source; dialogue special cases remain structural recipes rather than hardcoded French; `WAIT != NEWLINE`; ordinary dialogue lines remain `<= 38` decoded glyphs and `<= 216 px`. Do not start object/item translation during this maintenance phase.

## French opening storage/build architecture

`french_opening` now stores the relocated title arrangement at `$EE:A000` in the
stock compression container using **literal packets only**. The game still loads
it through the stock `$C1:0014` decompressor into `$7E:5000`; only the expensive
host-side optimal-LZ search for this ~7 KiB arrangement was removed. The opening
text remains fully regenerated from `translations/opening_text_french.json`.

A raw-copy (`MVN`) experiment worked standalone but produced a black screen when
combined with `mana_tree_original`. The literal-stream architecture restores the
stock loader protocol and was runtime-validated both with Mana Tree and in the
full combined build. `$EF` is no longer used by `french_opening`. Standalone build
time is about 1.5-1.6 s in the maintenance environment. See
`docs/OPTIMIZATION_FRENCH_OPENING.md` and `docs/OPENING_LITERAL_STREAM_ROUND85_13.md`.
