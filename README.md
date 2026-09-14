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

`french_dialogues` uses the **simulator-filtered Android-FR mass pass** during a normal standalone build. `translations/dialogues_french.json` is a generated local performance cache/review artifact, never canonical provenance: a fingerprint-valid copy is reused, otherwise the same pipeline regenerates and persists it from canonical Android/source inputs. The current promoted corpus contains **701 simulator-clean playable events / 1959 translated carriers**, with **701 complete + 0 PARTIEL**. Semantic Android alignment remains **1798 / 1838 (97.8%)**, with **40 unresolved semantic IDs**; the only exclusions remain the three routing-audited unused/orphan events `$0269`, `$02DE`, `$0603`. Independent simulation reports **0 errors / 0 warnings / 0 implicit runtime wraps**. Manual-JP, validated-suppression and shared-prefix provenance remains explicit in the canonical metadata. `$035F/C9:D1B8` is the validated runtime-complete message `Dryade fera réagir l'orbe !`; the shared `$0360` suffix remains neutralized.

`french_resources` follows the same provenance rule: `reports/android/text_resources_android.json` is an optional review output, while `translations/text_resources_french.json` is a generated local performance cache/review artifact. A fingerprint-valid copy is reused; otherwise the component regenerates and persists it from the clean-USA text-resource extraction, `recipes/android/text_resources_layout.json`, and Android `systxt_en/fr.bin`. Neither file is canonical provenance.

### Recipe layout

Dialogue recipe data is consolidated by responsibility under `recipes/android/`: `dialogues_reviewed_alignment.json`, `dialogues_redistribution.json`, `dialogues_formatting.json`, and `dialogues_review.json`. The formatting/review files store source-backed structural operations, semantic fingerprints and layout separators, not localized French prose. See `recipes/android/README.md`.

## Dialogue checkpoint

**The second exhaustive dialogue pass is the promoted canonical dialogue state.** It covers all **701 accepted playable events** in 12 lots and was followed by a full cleanup/non-regression validation.

The exact second-pass starting and final JSONs both contain **1959 carriers**. Exactly **46 explicitly reviewed carriers changed**; the other **1913 carriers are byte-for-byte unchanged**. No carriers were added or removed. Structural metadata changes are limited to the validated events documented in `docs/HANDOFF.md` and `checkpoints/SECOND_PASS_POST_VALIDATION.md`.

A fresh cold regeneration reproduces `translations/dialogues_french.json` with SHA-256 `3e4cacd926e31d6dfe9f9021d1026c4f71dc68ccd88ce4481749e47764d2b7d9`. Promoted dialogue-data hash remains `dfc94882e4162052ccd7195839ef7ef7f5a89f1bec51847d905ca6b05ad2de31` for `french_dialogues.ips`. After the runtime-validated `vwf_dialogues` left-inset / exact interrupted-chunk continuation fix, the promoted combined `all.ips` SHA-256 is `9fc13efe50b7e315dab7238ee2142d9e245ea51ae9e51768a6ad9f6e42248029`. A forced double rebuild is byte-identical to these promoted patches.

See `docs/HANDOFF.md` for the current handoff and `checkpoints/SECOND_PASS_POST_VALIDATION.md` for the final non-regression proof.

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
