# French native menus

Translates selected native `$C7` menus while preserving their stock rendering
model unless a change has been runtime-proven necessary.

## Current promoted scope

### GAME SELECT / GAME FILE

### GAME FILE currency suffix

The save/load GAME FILE money total uses a hybrid stock renderer. Its dynamic
font upload always rewrites exactly 16 cells (columns 0..15): stock uses eight
leading blanks, seven amount cells, then the first glyph of `GP`, hard-coded as
`G` by `LDA #$A1` at `$C7:54A9`. Column 16 is not part of that upload and keeps
the second glyph from the `C7:7394` resource template. Runtime probes proved the
split (`PO` -> `GO`, `XO` -> `GO`, `XX` -> `GX`).

The runtime-validated French layout keeps the stock currency anchor but changes
the dynamic 16-cell payload to seven leading blanks + seven amount cells + one
explicit blank + currency glyph 0. A 10-byte helper at `$C7:4D32` wraps the stock
`$C7:54B0` formatter, inserts the separator at dynamic column 14, then returns to
the existing `$C7:54A9` write. That first currency glyph is still derived from
the same JSON-backed two-cell `C7:7394` translation; column 16 remains the second
JSON/template glyph. The result is `1234567 PO` with `PO` at its original anchor
and no localized text embedded in Python/ASM.


- GAME SELECT labels use IDs from root `assets/menu_text.json`.
- GAME SELECT welcome/help and GAME FILE save help use IDs from root
  `assets/interface_text.json`.
- French text is stored sparsely in root `translations/menu_text_french.json`
  and `translations/interface_text_french.json`.
- GAME SELECT frame widths are derived from encoded character-cell counts.
- The GAME FILE resource is relocated to `$C7:4D40` so `Fichier` can fit, while
  fields still read through the stock path are mirrored in place.
- The FILE frame descriptor at `$C7:7585` uses the runtime-validated width `$04`
  (8 text cells).
- GAME SELECT welcome/help is relocated to `$ED:8000-$83FF`; the two-line GAME
  FILE save help uses `$ED:8400+`. The builder keeps those allocations disjoint.
- The dynamic slot level prefix is translated from `L` to `N` without changing
  the slot layout; both stock source positions have stable IDs.
- `COUNTER` is translation-backed as `Sauvegardes`; the row has 15 safe label cells and the 11-character wording is runtime-validated.
- `MANA POWER` is translation-backed as the full 15-cell `Graines de Mana`. `french_menus` owns only the source payload; the exact GAME FILE VWF presentation is owned by `vwf_ui`, which leaves the dynamic seed count stock.

### Window Settings / Choix de fenêtre

The native Window Edit screen is now runtime-validated entirely on the **stock
fixed-font renderer**. The rejected VWF experiment is not part of the promoted
component. The final translated layout is:

- title: `Choix de fenêtre`;
- horizontal D-pad legend: `Fond` on the left and right;
- vertical D-pad legend: `Bordure` above and below;
- help:
  - `Choisissez le fond : gauche/droite, bordure : haut/bas.`
  - `Réglez la couleur : maintenez A, Y ou X et gauche/droite.`
  - `Appuyez sur B pour valider, Select pour annuler.`

The stock text/placement cursor is sensitive to resource length. Runtime probes
showed that widening the frame alone shifts later text by two cells, and adding
new label spans after the title makes the source cursor consume those labels as
title/help data. The promoted architecture therefore advances **frame width,
resource and placement list together**:

- relocated source resource: `$C7:4700-$472E`;
- relocated placement list: `$C7:4730-$4759`;
- title frame width: `$C7:75CA`, `$07 -> $09` (18 fixed cells);
- text pointer: `$C7:7828`, `$73BC -> $4700`;
- placement pointer: `$C7:782C`, `$7506 -> $4730`;
- help block relocated to `$ED:8600+`.

`Fond`, `Bordure`, the full title and the compact stock fallback are all stored
in `translations/menu_text_french.json`; no localized prose is embedded in the
builder. The final source ordering deliberately ends placement parsing on the
`Bordure` span so the stock source cursor lands exactly on the title source.

### Action Settings / Actions des personnages

The four fixed-font grid labels are runtime-validated in French:

- `ATTACK` -> `Attaquer`
- `KEEP AWAY` -> `S'éloigner`
- `APPROACH` -> `S'approcher`
- `GUARD` -> `Défendre`

This screen deliberately **does not use `vwf_ui`**. A VWF experiment was
rejected after it disturbed the pixel/tile-indexed layout of the help line and
right-hand gauge panel.

The validated fixed-font solution mirrors the stock/French-SNES architecture:

- the left frame keeps its USA stock width `$18`;
- the checkerboard and right-hand window remain stock;
- `Défendre` starts one fixed-font cell (8 px) farther left;
- the four labels are repacked into a **34-cell** relocated resource at
  `$C7:4DC0`, with a relocated placement list at `$C7:4DE3`;
- two 2-cell overlaps already present in the translation payload are reused so
  the resource stays at the 34-cell size proven safe by the official French
  Rev 1 ROM;
- the dynamic gauge source base is adjusted `$2180 -> $2184` at `$C7:6C77`;
- the two top-help redraw bases are adjusted `$2090 -> $2094` and
  `$2108 -> $210C` at `$C7:6D57/$6D5C`.

Those three `+$04` tile-base compensations are also present in the official
French Rev 1 ROM. Runtime validation covered the full sequence: initial grid,
selecting a grid position / gauge level, and cancelling with `Y` back to the
initial prompt.

The two fixed-font help sentences are now translated and runtime-validated:

- `C0:3620` -> `Choisissez le type d'action. Validez avec “Attaque”.`
- `C0:3654` -> `Jusqu'où charger la jauge ? Validez avec “Attaque”.`

They are stored in `translations/interface_text_french.json`, relocated as one
three-row block to `$ED:8500+`, and remain on the stock 29-column fixed renderer.
The third row `C0:368F` (`0 1 2 3 4 5 6 7 8`) is structural and stays unchanged.

## Other runtime-validated menu/help changes

- GAME FILE save help now uses `Appuyez sur “Attaque” pour sauver, “Retour” pour annuler.`; this avoids hard-coding physical B/Y mappings after controls may have been rebound.
- Name Entry keeps physical `B` and `Start` deliberately because it is reached before control remapping is available. Its first line is now `Choisissez un caractère avec la croix directionnelle.`
- Status / Caractéristiques money total now prefixes its separately rendered currency unit with the otherwise-free byte `$C7:7B69`, and redirects the local unit pointer `$CE:E9BC` from `$7B6A` to `$7B69`. This yields `1234567 GP` standalone and `1234567 PO` in the aggregate without VWF, relocation, or duplicating the localized unit.
- GAME FILE total money now renders `1234567 PO` with the currency suffix anchored exactly where stock placed `GP`. The first glyph remains JSON-derived at `$C7:54A9`; the second remains the `C7:7394` template glyph in column 16. The 10-byte `$C7:4D32` helper inserts only the separator while preserving the renderer's mandatory 16-cell dynamic upload.
- GAME FILE `COUNTER -> Sauvegardes` and `MANA POWER -> Graines de Mana` are runtime-validated. The latter remains a 15-cell JSON source field; only `vwf_ui` changes its presentation.
- Rejected money probes (`PPO`, `P O`, and the misaligned-hook black screen) are historical only and are not part of the promoted patch. Their failure established the fixed 16-cell dynamic window documented in `docs/HANDOFF.md` and the component memory map.

## Status / Caractéristiques — fixed fallback + exact VWF source

The fixed-font Status path is now understood and its safe fallback remains in
place. `french_menus` still emits the original 60-cell + 40-cell source rows at
`$C7:7A28-$7A8D`, with `Intell.` and `% précis.` in the two fields that exceed
the stock 10-cell source slots. The USA-only hard-coded `ON` / `CE` suffixes are
blanked exactly as in French Rev 1.

For aggregate builds, this component also owns a full-label source table at
`$ED:8B00-$8B9F`: ten fixed 16-byte records (length + direct glyphs). The
current full forms include `Intelligence` and `% précision`. Marker
`$ED:8BA0-$8BA1 = 53 56` identifies that exact table. `vwf_ui` may consume it,
but no French prose is embedded in the generic VWF component.

The exact VWF probe using the short forms was runtime-validated. The current
long-form candidate is pending runtime validation. The 16 condition names remain
repacked inside `$C7:7A8E-$7B23`; templates, weapon types, `Type` and `Sphères`
keep their stock starts. `$C7:7B6A` (`GP -> PO`) remains owned by
`french_resources`. `Épée` uses the shared `full_french` direct-glyph profile;
no VWF is required for that weapon type.

## Sources

- root `assets/menu_text.json`: canonical clean-USA menu/status source cache;
- root `assets/interface_text.json`: canonical clean-USA help source cache;
- root `translations/menu_text_french.json`: reviewed native-menu labels;
- root `translations/interface_text_french.json`: reviewed help/status labels;
- `docs/MEMORY_MAP.md`: allocations, hooks and fixed-address adjustments.

The root extractor regenerates source JSONs from a clean USA ROM:

```bash
python3 tools/text/extract.py "Secret of Mana (USA).sfc" --only menu
python3 tools/text/extract.py "Secret of Mana (USA).sfc" --only interface
```

`build_patch.py` verifies both source assets against the ROM and binds French
strings by position-based source ID. It uses the shared `full_french` charset
profile, including direct `$E2 = É`.

## Build and validation

```bash
python3 components/french_menus/build_patch.py "Secret of Mana (USA).sfc" -o /tmp/french_menus.ips
python3 build.py "Secret of Mana (USA).sfc" french-menus --combine
```

The builder is the executable source of the patch. There is no parallel ASM
patch source to synchronize: fixed addresses and assembly-level adjustments are
documented here and in `docs/MEMORY_MAP.md`, while translated prose remains in
root translation JSON files.

## Weapon / magic default help — candidate 2026-09-26

The user approved the JP/Android-backed wording. `french_menus` now owns the
six source-ID-bound rows in `translations/interface_text_french.json`.
Pointers `$C0:33C4/$33C7` target `$ED:A000/$A100`; each block reserves 256 bytes
(153/152 used). Stock three-line fixed rendering and all descriptions remain
unchanged. Runtime validation is pending; promoted IPS files remain untouched.
Candidate artifacts and full provenance/checks: `docs/SKILL_MENU_HELP_RESEARCH.md`
and `build/candidates/skill-help-20260926/` at the repository root.
