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
- `french_resources` - deterministic reinsertion of reviewed French `$CA` name resources (magic, spirits, weapons, equipment, items, enemies and locations) from `translations/text_resources_french.json`.

Component metadata lives in `components/*/component.json`. Public component IDs are semantic and intentionally unnumbered. The aggregate builder discovers components from these manifests and applies their explicit `build_order`; folder names therefore do not control patch precedence. Adding a component does not require a hard-coded component list in the root scripts.

Standalone component IPS files may be kept in `patches/` as reusable build
snapshots. Each `build_patch.py` can reconstruct its patch from the clean USA ROM plus
the repository's canonical root text/translation assets and any component-local
non-text assets it owns. The aggregate builder
never needs to rebuild an unchanged component when its stored IPS is available.

## Canonical text assets

ROM-derived text sources live at the repository root instead of being
re-discovered independently by each component. The clean-USA inventory is split
by stock storage/rendering mechanism:

- `assets/dialogues.json` - the 713 text-bearing event scripts owned by `french_dialogues`;
- `assets/intro_event.json` - the eight stock text parts from event `$0400`, kept
  separate because `french_intro` owns that translated payload;
- `assets/text_resources.json` - all 513 non-event `$CA` text resources;
- `assets/interface_text.json` - 27 help/status rows from the nine-entry
  `$C0:33B5` 24-bit interface pointer-table family;
- `assets/menu_text.json` - 66 logical native `$C7` menu/status source elements;
- `assets/battle_text.json` - the complete 109-record `$C0` battle-message pool;
- `assets/shop_text.json` - nine `$D9` shop/forge response mini-event strings;
- `assets/opening_text.json` - user-visible strings from the compressed startup/title arrangement.

Regenerate the complete inventory deterministically from the clean USA ROM with:

```bash
python3 tools/extract_text.py "Secret of Mana (USA).sfc"
```

Or regenerate one family with `--only dialogues|resources|interface|menu|battle|shop|opening|intro`.
Verify all source/no-op round-trips and parse every event script with:

```bash
python3 tools/check_text_roundtrip.py "Secret of Mana (USA).sfc" --scan-all-events
```

Audit that components have not reintroduced CSV/BIN prose sources or parallel translation paths:

```bash
python3 tools/check_text_source_hygiene.py
```

All files under `assets/` are now **clean-ROM source only**. Every translatable
source element carries a globally unique position-based ID. Ordinary data uses
its SNES address (`C0:33F0`, `CA:98E1`, ...); compressed opening text uses the
container address plus decompressed offset (`C7:B480+09F9`).

French text lives separately under `translations/` in sparse `*_french.json`
files. The validated translations formerly stored in component CSV/BIN inputs for
`french_name_entry_extended`, `french_menus`, `french_opening`, and `french_intro` have been migrated there.

`french_dialogues` consumes `translations/dialogues_french.json`, generated by the
**simulator-filtered Android-FR mass pass**. At the current Round-72 checkpoint it contains
**701 simulator-clean playable events / 1810 accepted semantic source IDs / 1943 active sparse
translation entries**: **701 complete + 0 PARTIEL**. Semantic Android alignment remains
**1798 / 1838 (97.8%)**, with **40 unresolved semantic IDs**; the only exclusions are the three
routing-audited unused/orphan events `$0269`, `$02DE`, `$0603`. Independent simulation reports
**0 errors / 0 warnings / 0 implicit runtime wraps**. Manual-JP, validated-suppression and
shared-prefix provenance remains explicit in the canonical metadata. `$035F/C9:D1B8` remains
strictly `Dryade`; never restore `Dryade fera réagir l'orbe !`.

## Dialogue checkpoint

The current development checkpoint is **Round 84 — Name Entry prefill cleanup / fully runtime-validated checkpoint**. The generic three-row Name Entry/prefill, French four-row Name Entry, and the French defaults `Randy`, `Prim`, `Popoï` are runtime-validated; the dedicated first-screen `Popoï` diagnostic also validated the real fourth-row `ï` path immediately at Name Entry startup. Round 84 is cleanup-only and keeps the validated Round-83 production patch bytes. The dialogue payload itself remains the locked **Round 72 — automatic 216 px completion** state.
Dialogue identity remains **1798 / 1838 (97.8%)**; the remaining unresolved Android
IDs are not reopened by this checkpoint. The playable dialogue corpus contains
**701 events = 701 complete + 0 PARTIEL**, with **1810 accepted semantic source IDs /
1943 active sparse translation entries**. The only exclusions are the three
routing-audited unused/orphan stock events `$0269`, `$02DE`, `$0603`.

Independent simulation reports **0 errors / 0 warnings / 0 implicit runtime wraps**.
The runtime-validated dialogue contract is **<= 38 decoded glyphs** and **<= 216 px
advance** for ordinary dialogue lines. `vwf_dialogues` contains the validated parser
capacity correction that removes the delayed/shifted 35th-glyph artifact.

Round 72 also moves the 216-px reflow into the deterministic Android-FR generation
pipeline. No French prose was hard-coded to solve the migration: wrapping, generated
page transitions, live `PLAYER_NAME` prefix accounting, stock transition reuse and
choice-specific layout handling are generic and independently simulator-gated.
A reproducibility amendment stores the seven reviewed outer-choice-decoration removals
in `mappings/android/dialogues_choice_layout_recipes.json`; that file contains only
canonical event/carrier identities, never French text. When one of those reviewed rows
would otherwise force a fresh page, the owning Android-backed prompt is retried with the
existing compact wrapper before the decoration is removed. Thus a fresh
`dialogue-format-mass` run reproduces the reviewed choice presentation instead of
silently restoring stock parentheses. Reviewed Round 67/68/69 identities, wording and
scene redistributions remain locked.

Restructured dialogue prose is **not stored in clear text** outside the canonical
sources. `mappings/android/dialogues_redistribution_recipes.json` contains Android-FR
ID/token references plus layout/control metadata, and `tools/import_android_text.py`
rebuilds translated carriers directly from `sources/android/scrtxt_fr.bin`. Genuine
non-Android French remains isolated in
`translations/dialogues_manual_supplements.json`.

Operational material:

- `docs/HANDOFF.md` — authoritative current state and next work;
- `docs/DIALOGUE_FORMAT.md` / `docs/DIALOGUE_SIMULATOR.md` — formatting/runtime model;
- `mappings/android/dialogues_manual_supplements.html` — manual provenance review;
- `mappings/android/dialogues_redistribution_recipes.json` — source-derived scene recipes.
- `mappings/android/dialogues_choice_layout_recipes.json` — structural-only reviewed choice-layout recipes; no localized prose.

Historical Round 69/70/71 investigation remains documented in the specialist docs and
`docs/ROUND71_216PX_AUTOMATION_AUDIT.md`; those historical counters are not the current
checkpoint.

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

`tools/simulate_dialogues.py` is the user-validated static guardrail: it
re-decodes the final serialized event bytes and independently checks DTE,
`PLAYER_NAME`, VWF geometry, parser capacity, wraps, page controls and the rolling
window. Detailed rules and the conservative structural fallbacks are documented in
`docs/DIALOGUE_FORMAT.md` and `docs/DIALOGUE_SIMULATOR.md`.

`tools/extract_japanese_dialogue.py` is the analysis-only bridge from a canonical
USA dialogue carrier ID (for example `C9:916F`) to original **SNES-JP** evidence.
It identifies the owning USA event, reads the same event ID from a user-supplied
clean Japanese ROM, decodes the original SFC Japanese text codec, and refuses to
invent a one-to-one carrier when regional scripts are resegmented. Its regression
checker is `tools/check_japanese_dialogue_extractor.py`; usage and confidence
levels are documented in `docs/JAPANESE_DIALOGUE_EXTRACTION.md`. It is not part of
the build and never creates Android identity.

For the current development checkpoint and next work, see `docs/HANDOFF.md`. The accepted non-dialogue UI-VWF architecture and extension rules are summarized in `docs/UI_VWF.md`. The rejected Watts forge experiments and the runtime proof chain remain in `docs/FORGE_VWF_RESEARCH.md`; read both files before extending `vwf_ui`.

See `docs/TEXT_INVENTORY.md` for coverage, `docs/TRANSLATIONS.md` for the source/translation
model and ID scheme, `docs/ANDROID_TEXT_ALIGNMENT.md` for the Android English/French alignment method and conservative whole-dialogue mapping, `docs/TEXT_COMPONENT_AUDIT.md` for component
ownership and legacy-source cleanup, and `docs/TEXT_RESEARCH_NOTES.md` for the
reverse-engineering trail behind the inventory.

## Shared code and charset

`shared/rom.py` contains the canonical base-ROM identity and common SNES checksum
helpers. `shared/ips.py` contains the generic IPS reader/writer used for aggregate
builds. `shared/asm65816.py` provides the tiny label-aware emitter used by Python
builders that generate 65C816 routines. `shared/vwf_geometry.py` contains the
renderer-neutral 8×12 glyph measurement/left-compaction primitives shared by
the intro and dialogue VWF builders. `shared/vwf_metrics.py` contains the
canonical validated framing/advance policy used by both VWF builders.
`shared/vwf_framing.py` is the common runtime-selector source; its readable
65816 reference is `shared/vwf_framing.asm`. Both VWF components install the
same selector bundle at `$C7:44C0-$4557`.
`shared/vwf_text_buffer.py` generates the
byte-identical private decoded-text buffer bridge used by `vwf_intro` and `vwf_dialogues`;
its readable 65816 reference is `shared/vwf_text_buffer.asm`.
`shared/vwf_compositor.py` generates the byte-identical 8x12 shift/merge/spill
primitive now shared by both VWF renderers; its readable reference is
`shared/vwf_compositor.asm`. `shared/vwf_row_renderer.py` adds the runtime-validated
shared stock-font row load + framing + compositor helper used by both VWF paths;
`shared/vwf_row_renderer.asm` is its readable reference. `shared/vwf_outline.py`
owns the common stock-outline `ROL -> ASL` preparation installed by both VWF
components; `shared/vwf_outline.asm` documents that one-byte fix.
`shared/translation_json.py` binds sparse language files to canonical source IDs.
`shared/dialogue_codec.py` owns the stock event/dialogue parser and deterministic serializer used by root text tools and `french_intro` / `french_dialogues`. `shared/dialogue_relocation.py` owns the validated sparse expanded-ROM event relocation mechanism consumed by `french_dialogues`. `shared/dialogue_translation.py` owns the conservative Android-French normalization, PLAYER_NAME rebinding and dual-limit VWF/38-character offline formatter. Keeping these modules under `shared/` avoids cross-component Python imports.
`shared/text_ids.py` defines the position-based source-ID scheme. `shared/components.py` discovers component
manifests and `shared/compatibility.py` owns cross-component merge rules.

`shared/french_charset/` is the canonical source for French direct-glyph codes
and artwork. Name Entry, GAME SELECT, French intro payload, intro VWF, dialogue VWF and dialogue text rendering consume this definition while
each standalone IPS still writes the bytes required for independent operation.
See `docs/SHARED_CHARSET.md`.

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
`shared/dialogue_dte.py`. This avoids changing `french_intro`'s private intro DTE table.
Any other differing functional overlap aborts the build.

See `docs/COMPATIBILITY.md` and `docs/MEMORY_MAP.md`. Component-specific renderer notes stay under each component; for dialogue VWF start with `components/vwf_dialogues/README.md`. The stock event/dialogue format notes are in `docs/DIALOGUE_FORMAT.md`; the 513 non-event resources are documented in `docs/TEXT_RESOURCES.md`. The repository-wide text map is `docs/TEXT_INVENTORY.md`, with family details in `docs/INTERFACE_TEXT.md`, `docs/MENU_TEXT.md`, `docs/BATTLE_TEXT.md` and `docs/OPENING_TEXT.md`. `french_dialogues` build details remain in `components/french_dialogues/README.md`.
