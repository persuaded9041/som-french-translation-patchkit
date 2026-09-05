# Secret of Mana - French translation patch kit

This repository contains independent components for the French re-translation of Secret of Mana, based on the US ROM.

This project was developed with assistance from ChatGPT by OpenAI for code review, 
documentation, reverse-engineering analysis, and implementation support.

Every component targets the same clean, unheadered USA ROM and can be
built alone. `build.py` rebuilds selected components from their editable
sources, audits their writes, and emits a combined IPS.

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
6. `06_dialogue_vwf` - development component for variable-width normal in-game dialogue rendering; technical status and handoff live inside the component.
7. `07_intro_skip` - hold R for about two seconds during the introduction to skip directly to the waterfall scene.

Component metadata lives in `components/*/component.json`. The aggregate builder
discovers components from these manifests; adding a component does not require a
hard-coded component list in the root scripts.

No generated `.ips` file is stored in this repository. Each `build_patch.py`
reconstructs its standalone IPS from the clean USA ROM plus the component's
editable sources/assets.

## Shared code and charset

`shared/rom.py` contains the canonical base-ROM identity and common SNES checksum
helpers. `shared/ips.py` contains the generic IPS reader/writer used for aggregate
builds. `shared/components.py` discovers component manifests and
`shared/compatibility.py` owns cross-component merge rules.

`shared/french_charset/` is the canonical source for French direct-glyph codes
and artwork. Name Entry, GAME SELECT, intro VWF and dialogue VWF consume this definition while
each standalone IPS still writes the bytes required for independent operation.
See `docs/SHARED_CHARSET.md`.

## Build

Install the Python dependency:

```bash
python3 -m pip install -r requirements.txt
```

Build all components into one IPS:

```bash
python3 build.py "Secret of Mana (USA).sfc" all -o build/all.ips
```

The explicit `all` is optional:

```bash
python3 build.py "Secret of Mana (USA).sfc" -o build/all.ips
```

Build a subset:

```bash
python3 build.py "Secret of Mana (USA).sfc" tree names game-select -o build/custom.ips
```

List discovered component names:

```bash
python3 build.py --list
```

Optionally emit a patched ROM for local testing:

```bash
python3 build.py "Secret of Mana (USA).sfc" all \
  -o build/all.ips \
  --patched-rom "build/Secret of Mana (USA) - French.sfc"
```

Generated ROMs and IPS files are build products only and must not be committed.

## Compatibility policy

Components remain standalone, so byte-identical writes can be intentional. The
aggregate builder reconstructs every selected component in a temporary directory
and audits the resulting IPS write maps before combining them.

Allowed overlaps are:

- byte-identical functional writes required by standalone components;
- checksum bytes, which are recomputed once on the combined ROM;
- the shared French direct-glyph threshold at ROM `0x0016F6`.

Name Entry and GAME SELECT declare the `basic_french` profile (`$E1` threshold);
intro VWF and dialogue VWF declare `full_french` (`$E6`). Thresholds belong to the profiles in
`shared/french_charset/charset.json`, and the aggregate builder selects the
highest one required by the chosen components. Any other differing functional
overlap aborts the build.

See `docs/COMPATIBILITY.md` and `docs/MEMORY_MAP.md`. Component-specific renderer notes stay under each component; for dialogue VWF start with `components/06_dialogue_vwf/README.md`.
