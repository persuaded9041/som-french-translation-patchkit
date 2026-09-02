# Secret of Mana (USA) — French translation patch kit

This repository groups five independent components for the French Secret of
Mana project. Every component targets the same clean, unheadered USA ROM and
can be applied alone. `build.py` can combine any subset safely.

## Required base ROM

- Secret of Mana (USA), unheadered
- size: `0x200000` bytes
- SHA-256: `4c15013131351e694e05f22e38bb1b3e4031dedac77ec75abecebe8520d82d5f`

The ROM itself is deliberately not included.

## Shared French charset

`shared/french_charset/` is the canonical source for French direct-glyph codes
and artwork. Name Entry, GAME SELECT and the intro VWF all consume this shared
definition instead of maintaining private mappings/assets. Standalone IPS files
still install the bytes they require so each component remains independently
applicable. See `docs/SHARED_CHARSET.md`.

## Components

1. `01_japanese_mana_tree` — restores the original Japanese Mana Tree artwork.
2. `02_9char_names` — 9-character names, four character rows, French accent row and French help text.
3. `03_game_select` — French GAME SELECT labels/help, dynamic frame widths and French accented glyphs.
4. `04_french_opening` — French startup credits/opening text; helper at `$EE:9000` for VWF compatibility.
5. `05_intro_vwf_french` — French new-game introduction with VWF, private DTE and accented glyphs.

Each component contains a standalone `patch.ips`, a reproducible Python builder,
editable assets, technical source maps and component documentation.

## Build one or more components

All components:

```bash
python3 build.py "Secret of Mana (USA).sfc" all -o build/all.ips
```

Optional patched ROM for testing:

```bash
python3 build.py "Secret of Mana (USA).sfc" all \
  -o build/all.ips \
  --patched-rom "build/Secret of Mana (USA) - French.sfc"
```

Selected components:

```bash
python3 build.py "Secret of Mana (USA).sfc" tree names game-select -o build/custom.ips
```

Short names: `tree`, `names`, `game-select`, `opening`, `intro-vwf`.

## Compatibility policy

Components remain standalone, so some byte-identical writes are intentional:

- expanded-ROM/header housekeeping;
- the canonical `$D4-$E0` French glyphs used by Name Entry and GAME SELECT and
  shared with the intro VWF;
- direct-glyph threshold `$E1` for Name Entry/GAME SELECT versus `$E6` for the
  intro VWF, which extends the same charset through `$E5`.

When intro VWF is combined with Name Entry and/or GAME SELECT, `build.py`
explicitly resolves the threshold to `$E6`. Any other differing functional
overlap aborts the build.

## Verification

```bash
python3 verify.py
python3 rebuild_verify.py "Secret of Mana (USA).sfc"
```

`verify.py` checks hashes, the shared charset and component overlaps.
`rebuild_verify.py` rebuilds all five standalone IPS files from source and
compares them byte-for-byte with the packaged checkpoints.
