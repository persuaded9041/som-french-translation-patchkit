# French GAME SELECT / GAME FILE

Translates GAME SELECT and GAME FILE/save-menu text while keeping the stock
fixed-width menu renderer.

## Current scope

- GAME SELECT labels use source IDs from root `assets/menu_text.json`.
- GAME SELECT welcome/help and GAME FILE save help use source IDs from root
  `assets/interface_text.json`.
- French text is stored sparsely in root `translations/menu_text_french.json`
  and `translations/interface_text_french.json`.
- GAME SELECT frame widths are derived from encoded character-cell counts.
- The GAME FILE resource is relocated to `$C7:4D40` so `Fichier` can fit, while
  fields still read through the stock path are mirrored in place.
- The FILE frame descriptor at `$C7:7585` uses the runtime-validated width `$04`
  (8 text cells).
- The two-line save help is relocated to `$ED:8400`.
- The dynamic slot level prefix is translated from `L` to `N` without changing
  the slot layout; both stock source positions have their own stable IDs.

Dynamic location names, player names, levels, HP and numeric values are supplied
by game data and are not translation entries owned by this component.

## Sources

- root `assets/menu_text.json`: canonical clean-USA menu/status source.
- root `assets/interface_text.json`: canonical clean-USA help source.
- root `translations/menu_text_french.json`: validated GAME SELECT/GAME FILE labels.
- root `translations/interface_text_french.json`: validated welcome/save-help text.
- `src/game_select_text.asm`: readable data/code map of the emitted changes.
- `docs/MEMORY_MAP.md`: allocations, hooks and stock GAME FILE text locations.

The root extractor regenerates the source JSONs from a clean USA ROM:

```bash
python3 tools/extract_text.py "Secret of Mana (USA).sfc" --only menu
python3 tools/extract_text.py "Secret of Mana (USA).sfc" --only interface
```

`build_patch.py` verifies both source assets against the ROM and binds every
French string by its position-based source ID. The component uses the shared
`basic_french` charset profile; cross-component charset/threshold resolution is
documented at repository level.
