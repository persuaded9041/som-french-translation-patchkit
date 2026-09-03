# French GAME SELECT / GAME FILE

Translates the GAME SELECT front-end and exposes the related GAME FILE/save-menu text through editable CSV sources. The existing GAME SELECT work computes frame widths from editable text, relocates its help text and installs 13 French accented glyphs.

This component is standalone and targets only the clean unheadered US ROM.

## Current scope

- `assets/game_select_text.csv`: translated GAME SELECT labels and welcome/help text.
- `assets/game_file_text.csv`: French GAME FILE/save-menu labels and save help.
- The main GAME FILE/save-menu resource is relocated from `C7:7340` to `C7:4D40`. This allows `FILE_LABEL` to grow from the stock `FILE` to `Fichier` while preserving the native resource structure. The small FILE frame descriptor at `C7:7585` is widened from `$03` (6 text cells) to `$04` (8 text cells), leaving room for the full label without extending into the following dynamic slot text. A `$05` / 10-cell test displayed the following `L` inside the FILE frame and was rejected at runtime.
- The two-line GAME FILE save help is relocated to `ED:8400`; its encoded source is therefore no longer limited to the 108-byte stock block. The current French text has been validated in game.
- The dynamic slot level prefix is translated from `L` to `N` (for `Niveau`) in both rendering paths. This remains a one-cell substitution and does not change the validated slot layout.
- The stock menu decoder/font is shared by both screens. The current component does **not** add a VWF to GAME SELECT or GAME FILE: GAME SELECT frame widths are derived from encoded character-cell counts.

The save-slot location name (for example `POTOS VILLAGE`), player name, level/HP and numeric values are dynamic data and are not part of `game_file_text.csv`. Location-name translation belongs to the game data that supplies those names, not to this static menu resource.

## Build

```bash
python3 build_patch.py "Secret of Mana (USA).sfc" -o build/patch.ips
```

Extract the stock GAME FILE/save-menu strings from a clean US ROM:

```bash
python3 build_patch.py "Secret of Mana (USA).sfc" \
  --extract-game-file assets/game_file_text.csv
```

## Editable sources

- `assets/game_select_text.csv`: GAME SELECT text inputs.
- `assets/game_file_text.csv`: GAME FILE/save-menu text inputs.
- `../../shared/french_charset/`: canonical French character mapping and glyph atlas.
- `src/game_select_text.asm`: assembly/data map of the component changes.
- `docs/MEMORY_MAP.md`: component ROM allocations, hooks and stock GAME FILE text locations.

## Compatibility

The 45-byte GAME SELECT menu resource size is invariant. This standalone patch uses the shared `basic_french` charset profile (`$D4-$E0`) and `$E1` as its decoder threshold. When combined with intro VWF, the root builder resolves the shared threshold to `$E6`.

The main GAME FILE resource is copied from stock `C7:7340-C7:73BB` to free space at `C7:4D40`, then rebuilt from the CSV. Its two menu-resource table references at `C7:7810` and `C7:7816` are redirected to the relocated copy. `FILE_SELECT`, `MONEY`, and `COUNTER` use one adjacent stock padding cell; `FILE_LABEL` is expanded structurally to `Fichier`. The FILE frame width byte at `C7:7585` is changed from `$03` to `$04` (6 to 8 text cells). The save-help text is relocated to `ED:8400`, with its pointer at `C0:33B8` updated accordingly. The GAME FILE text/frame changes and the `L` -> `N` level-prefix substitution have been validated in game. A `$05` / 10-cell FILE frame was tested and rejected because it pulled the following dynamic level prefix into the frame.

For cross-component rules, see the package-level `docs/COMPATIBILITY.md`.
