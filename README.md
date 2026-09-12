# Secret of Mana - French translation patch kit

This repository contains independent components for the French re-translation of Secret of Mana, based on the US ROM.

This project was developed with assistance from ChatGPT by OpenAI for code review, 
documentation, reverse-engineering analysis, and implementation support.

Every component targets the same clean, unheadered USA ROM and can be
rebuilt independently within the repository. `build.py` can rebuild only the components currently being worked
on, stores their standalone IPS files under `patches/`, and can combine those
reusable patches into `patches/all.ips` without rebuilding unchanged components.

## Required base ROM

- Secret of Mana (USA), unheadered
- size: `0x200000` bytes
- SHA-256: `4c15013131351e694e05f22e38bb1b3e4031dedac77ec75abecebe8520d82d5f`

The ROM itself is deliberately not included.

## Components

- `mana_tree_original` - restores the original Japanese Mana Tree artwork.
- `name_entry_extended` - generic 9-character Name Entry foundation with exactly three rows: uppercase/lowercase/symbols; stock English help is read directly from the USA ROM.
- `french_name_entry_extended` - French overlay for the extended Name Entry: expands the generic keyboard to four rows, adds the accented/extended row, French help text, glyphs and name-specific DTE routing.
- `name_entry_prefill` - editable default-name prefill driven by a component-local JSON (`Randi`, `Primm`, `Popoi`); requires `name_entry_extended` for lowercase/grid support.
- `french_name_entry_prefill` - French default-name overlay (`Randy`, `Prim`, `Popoï`), with its own JSON and fourth-row token support; requires `name_entry_prefill` + `french_name_entry_extended`.
- `french_menus` - French GAME SELECT and GAME FILE text pipeline, dynamic frame widths and French accented glyphs.
- `french_opening` - French startup credits/opening text.
- `french_intro` - validated French new-game event `$0400` payload, private intro DTE and accented glyphs.
- `vwf_intro` - new-game intro VWF renderer/runtime, private parser buffer and validated intro window; owns no translation.
- `vwf_dialogues` - runtime-validated variable-width renderer for stock `$C9/$CA` event dialogue and `french_dialogues` relocated `$E8-$EC` events under the same caller gate; interactive choice rows use the same VWF path; stock/decorated fallback geometry plus private measured-end geometry and the long-row right-edge compaction rule are runtime-validated on the Potos test path.
- `intro_skip` - hold R for about two seconds during the introduction to skip directly to the waterfall scene.
- `french_dialogues` - deterministic source/translation reinsertion for all stock text-bearing event scripts except intro `$0400`, with in-place rebuilds and deterministic expanded-ROM relocation for growth.
- `vwf_ui` - standalone VWF extensions for non-dialogue UI paths; the first runtime-validated backend is Watts' Forge weapon row, with exact builder tagging, dynamic suffix compaction and a local +3 logical-line margin.
- `french_resources` - deterministic reinsertion of reviewed French `$CA` name resources (magic, spirits, weapons, equipment, items, enemies and locations), with a fingerprint-validated local French JSON cache regenerated from the clean-ROM resource inventory, reviewed Android identity recipe and Android EN/FR sources when stale or absent.

Component metadata lives in `components/*/component.json`. Public component IDs are semantic and intentionally unnumbered. The aggregate builder discovers components from these manifests and applies their explicit `build_order`; folder names therefore do not control patch precedence. Adding a component does not require a hard-coded component list in the root scripts.

Standalone component IPS files may be kept in `patches/` as reusable build
snapshots. Each `build_patch.py` can reconstruct its patch from the clean USA ROM plus
the repository's canonical root text/translation assets and any component-local
non-text assets it owns. The aggregate builder
never needs to rebuild an unchanged component when its stored IPS is available.

## Clean-ROM extraction cache

ROM-derived text documents are cached locally under the ignored root `assets/`
directory. They are never canonical project inputs:

- when an `assets/*.json` cache exists, builders/checks validate and reuse it;
- when it is missing, the document is extracted deterministically from the clean USA ROM and written to `assets/`;
- a full rebuild warms all eight root caches once, while a targeted component build creates only what it needs.

`python3 tools/text/extract.py <ROM>` remains available to explicitly refresh or inspect the complete cache.

Regenerate the complete inventory deterministically from the clean USA ROM with:

```bash
python3 tools/text/extract.py "Secret of Mana (USA).sfc"
```

Or regenerate one family with `--only dialogues|resources|interface|menu|battle|shop|opening|intro`.
Verify all source/no-op round-trips and parse every event script with:

```bash
python3 tools/text/check_roundtrip.py "Secret of Mana (USA).sfc" --scan-all-events
```

Audit that components have not reintroduced CSV/BIN prose sources or parallel translation paths:

```bash
python3 tools/text/check_source_hygiene.py
```

All files under `assets/` are now **clean-ROM source only**. Every translatable
source element carries a globally unique position-based ID. Ordinary data uses
its SNES address (`C0:33F0`, `CA:98E1`, ...); compressed opening text uses the
container address plus decompressed offset (`C7:B480+09F9`).

French text lives separately under `translations/` in sparse `*_french.json`
files. The validated translations formerly stored in component CSV/BIN inputs for
`french_name_entry_extended`, `french_menus`, `french_opening`, and `french_intro` have been migrated there.

`french_dialogues` uses the **simulator-filtered Android-FR mass pass** during a normal standalone build. `translations/dialogues_french.json` is a generated local performance cache/review artifact, never canonical provenance: a fingerprint-valid copy is reused, otherwise the same pipeline regenerates and persists it from canonical Android/source inputs. The current corpus contains **701 simulator-clean playable events / 1815 accepted semantic source IDs / 1947 active sparse translation entries**: **701 complete + 0 PARTIEL**. Semantic Android alignment remains **1798 / 1838 (97.8%)**, with **40 unresolved semantic IDs**; the only exclusions are the three routing-audited unused/orphan events `$0269`, `$02DE`, `$0603`. Independent simulation reports **0 errors / 0 warnings / 0 implicit runtime wraps**. Manual-JP, validated-suppression and shared-prefix provenance remains explicit in the canonical metadata. `$035F/C9:D1B8` remains strictly `Dryade`; never restore `Dryade fera réagir l'orbe !`.

`french_resources` follows the same provenance rule: `reports/android/text_resources_android.json` is an optional review output, while `translations/text_resources_french.json` is a generated local performance cache/review artifact. A fingerprint-valid copy is reused; otherwise the component regenerates and persists it from the clean-USA text-resource extraction, `recipes/android/text_resources_layout.json`, and Android `systxt_en/fr.bin`. Neither file is canonical provenance.

## Dialogue checkpoint

The current development checkpoint is **Round 85 — post-audit dialogue coverage/layout cleanup**. Round 84 Name Entry remains fully runtime-validated and locked. Round 85 re-audits dialogue coverage, restores missing Android-FR scene units, improves generic carrier-boundary and live-PLAYER_NAME reflow, and adds the source-derived Android 2151–2155 transition at `$0559`. The user accepts this state for continued development; detailed runtime validation of the newly audited dialogue cases is deferred to the next complete playthrough.
Dialogue identity remains **1798 / 1838 (97.8%)**; the remaining unresolved Android
IDs are not reopened by this checkpoint. The playable dialogue corpus contains
**701 events = 701 complete + 0 PARTIEL**, with **1815 accepted semantic source IDs /
1947 active sparse translation entries**. The only exclusions are the three
routing-audited unused/orphan stock events `$0269`, `$02DE`, `$0603`.

Independent simulation reports **0 errors / 0 warnings / 0 implicit runtime wraps**.
The runtime-validated dialogue contract is **<= 38 decoded glyphs** and **<= 216 px
advance** for ordinary dialogue lines. `vwf_dialogues` contains the validated parser
capacity correction that removes the delayed/shifted 35th-glyph artifact.

The deterministic Android-FR generation pipeline owns the 216-px reflow and all
reviewed dialogue serialization. No French prose was hard-coded to solve the migration: wrapping, generated
page transitions, live `PLAYER_NAME` prefix accounting, stock transition reuse and
choice-specific layout handling are generic and independently simulator-gated.
A reproducibility amendment stores the seven reviewed outer-choice-decoration removals
in `recipes/android/dialogues_choice_layout.json`; that file contains only
canonical event/carrier identities, never French text. When one of those reviewed rows
would otherwise force a fresh page, the owning Android-backed prompt is retried with the
existing compact wrapper before the decoration is removed. Thus a fresh
`dialogue-format-mass` run reproduces the reviewed choice presentation instead of
silently restoring stock parentheses. Reviewed Round 67/68/69 identities, wording and
scene redistributions remain locked.

Restructured dialogue prose is **not stored in clear text** outside the canonical
sources. All canonical Android structural decisions live under `recipes/android/`. Generated review/audit material belongs under `reports/android/` and is never a build input.

The active structural recipe layer is split by responsibility:

- `dialogues_reviewed_alignment.json` — reviewed SNES/Android identities and structural provenance;
- `dialogues_redistribution.json` — scene/carrier redistribution from Android tokens;
- `dialogues_mapping_layout.json` — mapping-local token/layout reconstruction;
- `dialogues_layout_search.json` — reviewed carrier/offset layout operations;
- `dialogues_coverage_repair.json` — source-derived coverage repairs;
- `dialogues_choice_layout.json` — reviewed choice geometry/layout operations.

These files contain IDs, token references, punctuation and structural operations only.
Actual localized prose is read from `sources/android/scrtxt_fr.bin` on every generation.
Genuine non-Android French remains isolated in `translations/dialogues_manual_supplements.json`.
`translations/dialogues_french.json` is a generated local cache that may be kept during development; it is never required as canonical input and can always be regenerated. `reports/android/dialogues_auto.json`, the unmapped/exclusion CSVs and the mass-format reports remain generated-on-demand review outputs.

Operational material:

- `docs/HANDOFF.md` — authoritative current state and next work;
- `docs/DIALOGUE_FORMAT.md` / `docs/DIALOGUE_SIMULATOR.md` — formatting/runtime model;
- `reports/android/dialogues_manual_supplements.html` — generated manual-provenance review sheet (ignored; regenerate on demand);
- `recipes/android/dialogues_redistribution.json` — source-derived scene recipes.
- `recipes/android/dialogues_choice_layout.json` — structural-only reviewed choice-layout recipes; no localized prose.

Historical investigation is retained only where it still documents active runtime invariants or rejected paths worth preserving; obsolete round-specific audit snapshots have been removed.

Dialogue formatting follows the runtime-validated 216-pixel safe-width / 38-parser-unit /
3-line limits. Extra pages use the validated `WAIT $00` + `TEXT_CLEAR` transition,
with sentence boundaries preferred; timed waits are preserved. Dynamic
`PLAYER_NAME`, proven `TEXT_X` geometries and existing event interruptions are handled
only by explicitly proven structural rules. Stock rolling-window persistence after
interactive `WAIT $00` is preserved rather than deduplicated automatically. Unsupported
structures are rejected rather than guessed. Choice rows use the ordinary VWF renderer;
option-start and terminal-boundary synchronization keep the stock magenta geometry aligned,
and `french_dialogues` may minimally move only a later option anchor when decoded text would
otherwise be overwritten. The 701-event corpus as a whole still requires the planned
full-game playthrough; the Round-52 structural changes are runtime-validated; the Round-54 exact recoveries and the Round-57 omission/suppression changes are pending runtime validation.

`tools/dialogue/simulate.py` is the user-validated static guardrail: it
re-decodes the final serialized event bytes and independently checks DTE,
`PLAYER_NAME`, VWF geometry, parser capacity, wraps, page controls and the rolling
window. Detailed rules and the conservative structural fallbacks are documented in
`docs/DIALOGUE_FORMAT.md` and `docs/DIALOGUE_SIMULATOR.md`.

`tools/dialogue/extract_japanese.py` is the analysis-only bridge from a canonical
USA dialogue carrier ID (for example `C9:916F`) to original **SNES-JP** evidence.
It identifies the owning USA event, reads the same event ID from a user-supplied
clean Japanese ROM, decodes the original SFC Japanese text codec, and refuses to
invent a one-to-one carrier when regional scripts are resegmented. Its regression
checker is `tools/dialogue/check_japanese_extractor.py`; usage and confidence
levels are documented in `docs/JAPANESE_DIALOGUE_EXTRACTION.md`. It is not part of
the build and never creates Android identity.

For the current development checkpoint and next work, see `docs/HANDOFF.md`. `docs/MAINTENANCE_NEXT.md` tracks the remaining maintenance work. The dialogue pipeline cleanup/modularization is complete, and Round 85.10 establishes the optimized serial reference path (~5.8 s median mass generation in the checkpoint environment) without changing Android/SNES provenance or serialized outputs. The accepted non-dialogue UI-VWF architecture and extension rules are summarized in `docs/UI_VWF.md`. The rejected Watts forge experiments and the runtime proof chain remain in `docs/FORGE_VWF_RESEARCH.md`; read both files before extending `vwf_ui`.

See `docs/TEXT_INVENTORY.md` for coverage, `docs/TRANSLATIONS.md` for the source/translation
model and ID scheme, `docs/ANDROID_TEXT_ALIGNMENT.md` for the Android English/French alignment method and conservative whole-dialogue mapping, `docs/TEXT_COMPONENT_AUDIT.md` for component
ownership and legacy-source cleanup, and `docs/TEXT_RESEARCH_NOTES.md` for the
reverse-engineering trail behind the inventory.

## Shared library

Reusable project code is organized by responsibility under `shared/` rather than
in one flat module namespace. The main packages are `core/`, `build/`, `text/`,
`dialogue/`, `vwf/`, `name_entry/` and `charset/`. See `shared/README.md` for
ownership, dependency direction and the executable-source/ASM-reference policy.

`shared/charset/` remains the canonical editable source for French direct-glyph
codes and artwork. See also `docs/SHARED_CHARSET.md`.

## Build

For VS Code/Pylance, the repository includes `pyrightconfig.json` so root `shared.*` imports resolve without editor-specific path settings.

Install the Python dependency:

```bash
python3 -m pip install -r requirements.txt
```

The normal incremental workflow keeps one standalone patch per component in
`patches/`, named after the component directory. For example:

```text
patches/french_intro.ips
patches/vwf_intro.ips
patches/vwf_dialogues.ips
```

Rebuild only the components currently being modified:

```bash
python3 build.py "Secret of Mana (USA).sfc" french-intro vwf-intro
```

The same command accepts component IDs instead of short names. To rebuild every
component patch:

```bash
python3 build.py "Secret of Mana (USA).sfc" all
```

Once all component IPS files exist, combine the stored patches without
rebuilding any component:

```bash
python3 build.py "Secret of Mana (USA).sfc" --combine
```

This writes `patches/all.ips`. During normal development, rebuild one or more
components and refresh the global patch in a single command:

```bash
python3 build.py "Secret of Mana (USA).sfc" vwf-dialogues --combine
```

Only `vwf_dialogues.ips` is rebuilt; all other component patches are reused.
The compatibility audit is then run over the complete stored set before
`all.ips` is produced. This also catches shared-code changes that require a
second component to be rebuilt: incompatible stale overlaps abort instead of
being silently merged.

A different patch directory or combined output may be selected when needed:

```bash
python3 build.py "Secret of Mana (USA).sfc" vwf-dialogues \
  --patch-dir /tmp/som-patches --combine -o /tmp/all.ips
```

List discovered component names:

```bash
python3 build.py --list
```

Optionally emit a patched ROM while combining:

```bash
python3 build.py "Secret of Mana (USA).sfc" --combine \
  --patched-rom "build/Secret of Mana (USA) - French.sfc"
```

ROM files remain local build products and must never be committed or
redistributed. The `patches/` directory is intentionally not ignored so its IPS
files can be versioned when desired.

## Compatibility policy

Components remain standalone, so byte-identical writes can be intentional. The
aggregate builder audits the stored standalone IPS write maps before combining
them. Component builders still target the clean base ROM independently.

Allowed overlaps are:

- byte-identical functional writes required by standalone components;
- checksum bytes, which are recomputed once on the combined ROM;
- the legacy direct/DTE-threshold byte when a dialogue DTE router supersedes it.

Name Entry and GAME SELECT keep `basic_french`; the intro keeps the validated
`full_french` `$E6` boundary. Dialogue VWF/text use `dialogue_french`, which adds
`♪`, `°` and `;` and selects `$E8` only for real event-engine dialogue through
`shared/dialogue/dte.py`. This avoids changing `french_intro`'s private intro DTE table.
Any other differing functional overlap aborts the build.

See `docs/COMPATIBILITY.md` and `docs/MEMORY_MAP.md`. Component-specific renderer notes stay under each component; for dialogue VWF start with `components/vwf_dialogues/README.md`. The stock event/dialogue format notes are in `docs/DIALOGUE_FORMAT.md`; the 513 non-event resources are documented in `docs/TEXT_RESOURCES.md`. The repository-wide text map is `docs/TEXT_INVENTORY.md`, with family details in `docs/INTERFACE_TEXT.md`, `docs/MENU_TEXT.md`, `docs/BATTLE_TEXT.md` and `docs/OPENING_TEXT.md`. `french_dialogues` build details remain in `components/french_dialogues/README.md`.
