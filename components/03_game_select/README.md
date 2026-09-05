# French GAME SELECT / GAME FILE

Translates GAME SELECT and GAME FILE/save-menu text through editable CSV sources while keeping the stock fixed-width menu renderer.

## Current scope

- `assets/game_select_text.csv`: GAME SELECT labels and welcome/help text.
- `assets/game_file_text.csv`: GAME FILE/save-menu labels and save help.
- GAME SELECT frame widths are derived from encoded character-cell counts.
- The GAME FILE resource is relocated to `$C7:4D40` so `Fichier` can fit, while fields still read through the stock path are mirrored in place.
- The FILE frame descriptor at `$C7:7585` uses the runtime-validated width `$04` (8 text cells).
- The two-line save help is relocated to `$ED:8400`.
- The dynamic slot level prefix is translated from `L` to `N` without changing the slot layout.

Dynamic location names, player names, levels, HP and numeric values are supplied by game data and are not part of `game_file_text.csv`.

## Editable sources

- `assets/game_select_text.csv`
- `assets/game_file_text.csv`
- `src/game_select_text.asm`: readable data/code map of the emitted changes.
- `docs/MEMORY_MAP.md`: allocations, hooks and stock GAME FILE text locations.

The component uses the shared `basic_french` charset profile. Cross-component charset/threshold resolution is documented at repository level.

## GAME FILE extraction helper

To regenerate the editable GAME FILE CSV from a clean US ROM:

```bash
python3 components/03_game_select/build_patch.py "Secret of Mana (USA).sfc" \
  --extract-game-file components/03_game_select/assets/game_file_text.csv
```
