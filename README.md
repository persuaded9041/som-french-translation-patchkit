# Secret of Mana (USA) — French translation patch kit

This archive groups five independent, runtime-validated components for the French Secret of Mana project. Every component targets the same clean, unheadered US ROM and can be applied alone. `build.py` can combine any subset safely.

## Required base ROM

- Secret of Mana (USA), unheadered
- size: `0x200000` bytes
- SHA-256: `4c15013131351e694e05f22e38bb1b3e4031dedac77ec75abecebe8520d82d5f`

The ROM itself is deliberately not included in this archive.

## Components

1. `01_japanese_mana_tree` — restores the original Japanese Mana Tree artwork.
2. `02_9char_names` — 9-character names and three character pages.
3. `03_game_select` — French GAME SELECT labels/help, dynamic frame widths and French accented glyphs.
4. `04_french_opening` — French startup credits/opening text; helper moved to `$EE:9000` for VWF compatibility.
5. `05_intro_vwf_french` — French new-game introduction with VWF, private DTE and accented glyphs.

Each component contains:

- `patch.ips`: standalone validated patch;
- `build_patch.py`: source builder;
- `assets/`: editable/generated source assets;
- `src/`: assembly-oriented technical documentation;
- `tools/`: extraction/support tools when applicable;
- `docs/`: memory map and validation notes.

## Build one or more components

Apply all components and create a combined IPS:

```bash
python3 build.py "Secret of Mana (USA).sfc" all -o build/all.ips
```

Create a patched ROM for testing as well:

```bash
python3 build.py "Secret of Mana (USA).sfc" all \
  -o build/all.ips \
  --patched-rom "build/Secret of Mana (USA) - French.sfc"
```

Combine only selected components:

```bash
python3 build.py "Secret of Mana (USA).sfc" tree game-select intro-vwf -o build/custom.ips
```

Available short names: `tree`, `names`, `game-select`, `opening`, `intro-vwf`.

## Compatibility policy

Every component remains standalone. Therefore a few writes are intentionally shared:

- ROM-size/checksum header writes are per-component standalone housekeeping. The combined builder recalculates the checksum once at the end.
- GAME SELECT and intro VWF both install the same 13 French accented glyphs. Those bytes are identical. Keeping them in both components is required so either patch works alone.
- GAME SELECT writes decoder threshold `$E1` at ROM `0x0016F6`; intro VWF writes `$E6`, because it reserves five additional direct glyphs. When both are selected, `build.py` explicitly resolves this byte to `$E6`.

No other differing functional overlap is allowed. `build.py` aborts on undeclared collisions.

## Verification

Run:

```bash
python3 verify.py
```

It checks the SHA-256 of all five standalone IPS files and audits their byte-level overlaps.

See `docs/COMPATIBILITY.md`, `docs/MEMORY_MAP.md` and `docs/VALIDATION.md` for details.
