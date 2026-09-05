# French GAME SELECT / GAME FILE

Translates the GAME SELECT front-end and exposes the related GAME FILE/save-menu text through editable CSV sources. The existing GAME SELECT work computes frame widths from editable text, relocates its help text and installs 13 French accented glyphs.

This component is standalone and targets only the clean unheadered US ROM.

## Current scope

- `assets/game_select_text.csv`: translated GAME SELECT labels and welcome/help text.
- `assets/game_file_text.csv`: French GAME FILE/save-menu labels and save help.
- The full GAME FILE/save-menu resource is relocated from `C7:7340` to `C7:4D40` so `FILE_LABEL` can grow from stock `FILE` to `Fichier`. Runtime testing also showed that another GAME FILE path still reads several labels from the original `C7:7340` block, so those CSV-backed fields are mirrored in place as well. The stock field boundaries are preserved; only the relocated copy contains the complete `Fichier`. The small FILE frame descriptor at `C7:7585` is widened from `$03` (6 text cells) to the runtime-validated `$04` (8 text cells).
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

The main GAME FILE resource is copied from stock `C7:7340-C7:73BB` to free space at `C7:4D40`, then rebuilt from the CSV. Its two menu-resource table references at `C7:7810` and `C7:7816` are redirected to the relocated copy. Runtime testing proved that these redirects do not cover every GAME FILE read path: `FILE_SELECT`, `SAVE_POINT`, `MONEY`, `GP`, `COUNTER`, and `MANA_POWER` must also be written at their stock locations. `FILE_LABEL` keeps the four-cell `Fich` prefix in the stock block while the relocated copy contains full `Fichier`. `EMPTY` remains an external in-place field. The FILE frame width byte at `C7:7585` is changed from `$03` to `$04` (6 to 8 text cells). The save-help text is relocated to `ED:8400`, with its pointer at `C0:33B8` updated accordingly. This mixed stock/relocated GAME FILE path, the frame change and the `L` -> `N` level-prefix substitution are runtime-validated.

For cross-component rules, see the package-level `docs/COMPATIBILITY.md`.
