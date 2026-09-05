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

1. `01_japanese_mana_tree` - restores the original Japanese Mana Tree artwork.
2. `02_9char_names` - 9-character names, four character rows, French accent row and French help text.
3. `03_game_select` - French GAME SELECT and GAME FILE text pipeline, dynamic frame widths and French accented glyphs.
4. `04_french_opening` - French startup credits/opening text.
5. `05_intro_vwf_french` - French new-game introduction with VWF, private DTE and accented glyphs.
6. `06_dialogue_vwf` - runtime-validated variable-width renderer for stock `$C9/$CA` event dialogue and component-08 relocated `$E8-$EC` events under the same caller gate.
7. `07_intro_skip` - hold R for about two seconds during the introduction to skip directly to the waterfall scene.
8. `08_dialogue_text` - deterministic source/translation reinsertion for all stock text-bearing event scripts except intro `$0400`, with in-place rebuilds and deterministic expanded-ROM relocation for growth.

Component metadata lives in `components/*/component.json`. The aggregate builder
discovers components from these manifests; adding a component does not require a
hard-coded component list in the root scripts.

Standalone component IPS files may be kept in `patches/` as reusable build
snapshots. Each `build_patch.py` can reconstruct its patch from the clean USA ROM plus
the repository's canonical root text/translation assets and any component-local
non-text assets it owns. The aggregate builder
never needs to rebuild an unchanged component when its stored IPS is available.

## Canonical text assets

ROM-derived text sources live at the repository root instead of being
re-discovered independently by each component. The clean-USA inventory is split
by stock storage/rendering mechanism:

- `assets/dialogues.json` - the 713 text-bearing event scripts owned by component 08;
- `assets/intro_event.json` - the eight stock text parts from event `$0400`, kept
  separate because component 05 owns that event;
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
files. The validated translations formerly stored in component CSV/BIN inputs
for components 02-05 have been migrated there, and component 08 is ready to use
`translations/dialogues_french.json` when dialogue translation begins.

See `docs/TEXT_INVENTORY.md` for coverage, `docs/TRANSLATIONS.md` for the source/translation
model and ID scheme, `docs/TEXT_COMPONENT_AUDIT.md` for component ownership and
legacy-source cleanup, and `docs/TEXT_RESEARCH_NOTES.md` for the reverse-engineering
trail behind the inventory.

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
byte-identical private decoded-text buffer bridge used by components 05 and 06;
its readable 65816 reference is `shared/vwf_text_buffer.asm`.
`shared/vwf_compositor.py` generates the byte-identical 8x12 shift/merge/spill
primitive now shared by both VWF renderers; its readable reference is
`shared/vwf_compositor.asm`. `shared/vwf_row_renderer.py` adds the runtime-validated
shared stock-font row load + framing + compositor helper used by both VWF paths;
`shared/vwf_row_renderer.asm` is its readable reference. `shared/vwf_outline.py`
owns the common stock-outline `ROL -> ASL` preparation installed by both VWF
components; `shared/vwf_outline.asm` documents that one-byte fix.
`shared/translation_json.py` binds sparse language files to canonical source IDs.
`shared/dialogue_codec.py` owns the stock event/dialogue parser and deterministic serializer used by root text tools and components 05/08. `shared/dialogue_relocation.py` owns the validated sparse expanded-ROM event relocation mechanism consumed by component 08. Keeping these modules under `shared/` avoids cross-component Python imports.
`shared/text_ids.py` defines the position-based source-ID scheme. `shared/components.py` discovers component
manifests and `shared/compatibility.py` owns cross-component merge rules.

`shared/french_charset/` is the canonical source for French direct-glyph codes
and artwork. Name Entry, GAME SELECT, intro VWF, dialogue VWF and dialogue text rendering consume this definition while
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
patches/05_intro_vwf_french.ips
patches/06_dialogue_vwf.ips
```

Rebuild only the components currently being modified:

```bash
python3 build.py "Secret of Mana (USA).sfc" intro-vwf dialogue-vwf
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
python3 build.py "Secret of Mana (USA).sfc" dialogue-vwf --combine
```

Only `06_dialogue_vwf.ips` is rebuilt; all other component patches are reused.
The compatibility audit is then run over the complete stored set before
`all.ips` is produced. This also catches shared-code changes that require a
second component to be rebuilt: incompatible stale overlaps abort instead of
being silently merged.

A different patch directory or combined output may be selected when needed:

```bash
python3 build.py "Secret of Mana (USA).sfc" dialogue-vwf \
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
- the shared French direct-glyph threshold at ROM `0x0016F6`.

Name Entry and GAME SELECT declare the `basic_french` profile (`$E1` threshold);
intro VWF, dialogue VWF and translated dialogue data declare `full_french` (`$E6`). Thresholds belong to the profiles in
`shared/french_charset/charset.json`, and the aggregate builder selects the
highest one required by the chosen components. Any other differing functional
overlap aborts the build.

See `docs/COMPATIBILITY.md` and `docs/MEMORY_MAP.md`. Component-specific renderer notes stay under each component; for dialogue VWF start with `components/06_dialogue_vwf/README.md`. The stock event/dialogue format notes are in `docs/DIALOGUE_FORMAT.md`; the 513 non-event resources are documented in `docs/TEXT_RESOURCES.md`. The repository-wide text map is `docs/TEXT_INVENTORY.md`, with family details in `docs/INTERFACE_TEXT.md`, `docs/MENU_TEXT.md`, `docs/BATTLE_TEXT.md` and `docs/OPENING_TEXT.md`. Component-08 build details remain in `components/08_dialogue_text/README.md`.
