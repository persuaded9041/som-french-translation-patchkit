# Memory map

## Allocations / shared writes

- ROM `0x074400-0x07442C` / `$C7:4400-$442C`: 45-byte relocated GAME SELECT label resource.
- ROM `0x074D40-0x074DBE` / `$C7:4D40-$4DBE`: relocated GAME FILE/save-menu resource (127 bytes with current `Fichier` translation).
- ROM `0x2D8000-0x2DFFFF` / `$ED:8000-$FFFF`: reserved GAME SELECT/help-text region.
- ROM `0x12DFF0-0x12E08B`: 13 shared French glyphs.
- ROM `0x0016F6`: standalone direct/DTE threshold `$E1`.

## GAME FILE/save-menu stock text locations

These locations are both extraction sources and active runtime mirrors. The full `C7:7340-C7:73BB` resource is also relocated to `C7:4D40` so `FILE_LABEL` can expand safely, but runtime testing proved that another GAME FILE path still reads the stock fields. The builder therefore keeps both paths synchronized without shifting any stock boundary.

| ROM offset | Purpose | Current capacity |
|---:|---|---:|
| `0x077341` | file-screen `SELECT` | 7 cells in the relocated build (6 stock + adjacent padding) |
| `0x077349` | stock `FILE` | 4 cells; mirrored as `Fich`, while relocated copy contains full `Fichier` |
| `0x077350` | `SAVE  POINT` | 11 cells |
| `0x077374` | `MONEY` | 6 cells in the relocated build (5 stock + adjacent padding) |
| `0x077394` | `GP` | 2 cells |
| `0x077398` | `COUNTER` | 8 cells in the relocated build (7 stock + adjacent padding) |
| `0x0773AA` | `MANA POWER` | 10 cells |
| `0x077805` | `Empty` | 5 cells |
| `0x0033B8` | pointer to save-help text (`$C0:348D`) | 3 bytes |
| `0x00348D-0x0034F8` | two-line save help block | 108 bytes |

The builder preserves every validated stock field boundary above and mirrors the translation-JSON-backed values there. `FILE_LABEL` is the exception only in content length: the stock field receives its first four encoded cells (`Fich` currently), while its segment is expanded inside the relocated resource to full `Fichier`. The save-help payload is separately relocated to `ED:8400` and is no longer limited by the 108-byte stock block.

## GAME FILE relocation hooks

- ROM `0x0753C9` / `$C7:53C9`: dynamic GAME FILE level prefix glyph `$A6` (`L`) -> `$A8` (`N`).
- ROM `0x075AF1` / `$C7:5AF1`: second GAME FILE rendering path level prefix glyph `$A6` (`L`) -> `$A8` (`N`).
- ROM `0x077585` / `$C7:7585`: FILE/Fichier frame width `$03 -> $04` (6 -> 8 text cells).
- ROM `0x077810-0x077811` / `$C7:7810-$7811`: resource pointer `$7340 -> $4D40`.
- ROM `0x077816-0x077817` / `$C7:7816-$7817`: second state/resource pointer `$7340 -> $4D40`.
- Stock resource source: ROM `0x077340-0x0773BB` (`$C7:7340-$73BB`). `FILE_SELECT`, `FILE_LABEL` prefix, `SAVE_POINT`, `MONEY`, `GP`, `COUNTER`, and `MANA_POWER` are mirrored in place because a runtime path still reads them there.
