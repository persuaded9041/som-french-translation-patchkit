# Memory map

## Allocations / shared writes

- ROM `0x074400-0x07442C` / `$C7:4400-$442C`: 45-byte relocated GAME SELECT label resource.
- ROM `0x074700-0x07472E` / `$C7:4700-$472E`: runtime-validated Window Settings fixed-font source resource, 46 cells + `$00`.
- ROM `0x074730-0x074759` / `$C7:4730-$4759`: Window Settings ten-span placement list, 42 bytes.
- ROM `0x074D32-0x074D3B` / `$C7:4D32-$4D3B`: 10-byte runtime-validated GAME FILE money-spacing helper (`JSR $54B0; LDA #$80; STA $9C00,X; INX; RTS`).
- ROM `0x074D40-0x074DBE` / `$C7:4D40-$4DBE`: relocated GAME FILE/save-menu resource (127 bytes with current translation).
- ROM `0x074DC0-0x074DE2` / `$C7:4DC0-$4DE2`: Action Settings fixed-font label resource, 34 cells + `$00` terminator = 35 bytes.
- ROM `0x074DE3-0x074DFC` / `$C7:4DE3-$4DFC`: Action Settings six-span placement list, 26 bytes.
- ROM `0x2D8000-0x2D83FF` / `$ED:8000-$83FF`: GAME SELECT welcome/help allocation. Current payload is 181 bytes.
- ROM `0x2D8400-0x2D8470` / `$ED:8400-$8470`: GAME FILE save-help payload, 113 bytes.
- ROM `0x2D8500-0x2D857B` / `$ED:8500-$857B`: Action Settings help payload, 124 bytes.
- ROM `0x2D8600-0x2D86A2` / `$ED:8600-$86A2`: Window Settings three-line help payload, 163 bytes.
- ROM `0x12DFF0-0x12E08B`: 13 shared French glyphs.
- ROM `0x0016F6`: standalone direct/DTE threshold `$E1`.

## GAME FILE/save-menu stock text locations

These locations are both extraction sources and active runtime mirrors. The full
`C7:7340-C7:73BB` resource is also relocated to `C7:4D40` so `FILE_LABEL` can
expand safely, but runtime testing proved that another GAME FILE path still
reads the stock fields. The builder therefore keeps both paths synchronized
without shifting any stock boundary.

| ROM offset | Purpose | Current capacity |
|---:|---|---:|
| `0x077341` | file-screen `SELECT` | 7 cells in the relocated build (6 stock + adjacent padding) |
| `0x077349` | stock `FILE` | 4 cells; mirrored as `Fich`, while relocated copy contains full `Fichier` |
| `0x077350` | `SAVE  POINT` | 11 cells |
| `0x077374` | `MONEY` | 6 cells in the relocated build (5 stock + adjacent padding) |
| `0x077394` | `GP` | 2 cells |
| `0x077398` | `COUNTER` | **15 cells** before the dynamic value; runtime-validated `Sauvegardes` uses 11 |
| `0x0773AA` | `MANA POWER` | **15 cells**, source-owned `Graines de Mana`; presentation is runtime-validated by the exact `vwf_ui` GAME FILE backend |
| `0x077805` | `Empty` | 5 cells |
| `0x0033B8` | pointer to save-help text (`$C0:348D`) | 3 bytes |
| `0x00348D-0x0034F8` | two-line save help block | 108 bytes |

The builder preserves every validated stock field boundary above and mirrors
the translation-JSON-backed values there. `FILE_LABEL` is the exception only in
content length: the stock field receives its first four encoded cells, while
its segment is expanded inside the relocated resource to full `Fichier`. The
save-help payload is separately relocated to `ED:8400` and is no longer limited
by the 108-byte stock block.

## GAME FILE relocation hooks

- ROM `0x0753C9` / `$C7:53C9`: dynamic GAME FILE level prefix glyph `$A6` (`L`) -> `$A8` (`N`).
- ROM `0x07549A-0x07549C` / `$C7:549A-$549C`: `LDY #$0008 -> #$0007`, moving the seven amount cells one dynamic column left.
- ROM `0x0754A6-0x0754A8` / `$C7:54A6-$54A8`: stock `JSR $54B0` redirected to the helper at `$C7:4D32`. The helper calls `$54B0`, writes one fixed-font blank (`$80`) at dynamic column 14, increments `X`, and returns; the stock continuation then writes currency glyph 0 at column 15.
- ROM `0x0754AA` / `$C7:54AA`: operand of `LDA #$A1` at `$C7:54A9`; stock GAME FILE total-money path hard-codes the first `G` of `GP`. The builder derives this byte from the first glyph of translation ID `C7:7394` (`PO` -> `P`). Runtime probes proved the split path: changing only the resource to `PO` rendered `GO`, `XO` rendered `GO`, and `XX` rendered `GX`.
- ROM `0x075AF1` / `$C7:5AF1`: second GAME FILE rendering path level prefix glyph `$A6` (`L`) -> `$A8` (`N`).
- The money renderer's DMA is fixed at `$0200` bytes = 16 fixed-font characters, so dynamic columns 0..15 are always overwritten. The validated layout is therefore `7 blanks + 7 amount cells + separator + currency[0]`; static column 16 remains `currency[1]` from the JSON-backed template. This yields `1234567 PO` without moving the currency anchor.
- Historical rejected probes are not present in the source: an off-by-one hook caused a black screen; shortening the dynamic string to 15 cells produced `P O`; leaving a stale cell exposed produced `PPO`. These failures established why the promoted helper must preserve all 16 dynamic cells.

- ROM `0x077585` / `$C7:7585`: FILE/Fichier frame width `$03 -> $04` (6 -> 8 text cells).
- ROM `0x077810-0x077811` / `$C7:7810-$7811`: resource pointer `$7340 -> $4D40`.
- ROM `0x077816-0x077817` / `$C7:7816-$7817`: second state/resource pointer `$7340 -> $4D40`.
- Stock resource source: ROM `0x077340-0x0773BB` (`$C7:7340-$73BB`).

## Window Settings — runtime-validated fixed-font path

This page deliberately uses no VWF. Runtime validation established that its
frame width and source-resource cursor are coupled in two-cell units. The final
layout keeps them synchronized and renders `Choix de fenêtre`, `Fond` and
`Bordure` through native fixed-font spans.

- ROM `0x077828-0x077829` / `$C7:7828-$7829`: text pointer `$73BC -> $4700`;
- ROM `0x07782C-0x07782D` / `$C7:782C-$782D`: placement pointer `$7506 -> $4730`;
- ROM `0x0775CA` / `$C7:75CA`: title frame width `$07 -> $09` (14 -> 18 cells);
- relocated source `$C7:4700-$472E`: control labels, 8-cell `Fond` span, 8-cell `Bordure` span, then 17-cell title slot;
- relocated placement `$C7:4730-$4759`: six native A/R/Y/G/X/B spans plus `Fond` left/right and `Bordure` top/bottom;
- stock shadow `$C7:73C9` contains `Choisir`; `$C7:73D1` contains compact JSON fallback `Réglage`;
- help pointer ROM `0x0033BB-0x0033BD`: `$C0:34F9 -> $ED:8600`.

Rejected probes are not source: the VWF hook corrupted the whole screen; frame
widening without resource growth produced a stray `Ch` and wrapped help; an
initial `Fond/Bordure` resource appended after the title advanced the native
source cursor and corrupted title/help/frame data.

## Action Settings — runtime-validated fixed-font path

This page deliberately keeps the stock fixed-width renderer. The VWF experiment
is rejected and is not part of the component.

### Relocated data

- text descriptor pointer at ROM `0x077822-0x077823` / `$C7:7822-$7823`:
  `$73DF -> $4DC0`;
- placement descriptor pointer at ROM `0x077826-0x077827` / `$C7:7826-$7827`:
  `$7538 -> $4DE3`;
- relocated resource: `$C7:4DC0-$4DE2`, 34 cells + terminator;
- relocated placement list: `$C7:4DE3-$4DFC`, six spans + terminator.

The 34-cell layout reuses two 2-cell overlaps through the placement table. The
builder derives and validates those overlaps from `translations/menu_text_french.json`;
localized prose is not hard-coded in Python/ASM.

### Geometry / tile-base fixes

- ROM `0x07760A` / `$C7:760A`: left frame stays at stock width `$18`;
- the GUARD label destination is one fixed-font cell (8 px) left of stock;
- ROM `0x076C77-0x076C79` / `$C7:6C77-$6C79`: `LDA #$2180 -> #$2184`;
- ROM `0x076D57-0x076D59` / `$C7:6D57-$6D59`: `LDX #$2090 -> #$2094`;
- ROM `0x076D5C-0x076D5E` / `$C7:6D5C-$6D5E`: `LDX #$2108 -> #$210C`.

The three `+$04` source-tile compensations match the official French Rev 1 ROM.
They were runtime-validated across the initial grid, gauge-selection state and
`Y` cancellation/redraw path.

## Status / Characteristics — fixed fallback + full-label VWF source

`french_menus` keeps the stock fallback geometry and additionally owns the
localized full-label records consumed by the exact `vwf_ui` Status backend.

- ROM `0x0033CD-0x0033CF` / `$C0:33CD-$33CF`: stock 24-bit label-block pointer remains `$C7:7A28`;
- ROM `0x077A28-0x077A8D` / `$C7:7A28-$7A8D`: two 60 + 40-cell fallback rows; current long fields fall back to `Intell.` / `% précis.`;
- ROM `0x0033D0-0x0033EF` / `$C0:33D0-$33EF`: 16 condition pointers updated after in-place repacking;
- ROM `0x077A8E-0x077B23` / `$C7:7A8E-$7B23`: 150-byte condition pool, 123 bytes currently used;
- ROM `0x077B24-0x077B69` / `$C7:7B24-$7B69`: translated Status templates keep stock starts/control `$5C`;
- ROM `0x077B6D-0x077BA4` / `$C7:7B6D-$7BA4`: weapon types keep stock starts; current candidate uses direct-glyph `Épée` (`$E2`);
- ROM `0x077BA5-0x077BB4` / `$C7:7BA5-$7BB4`: `Type` / `Sphères` remain in stock slots;
- ROM `0x2D8B00-0x2D8B9F` / `$ED:8B00-$8B9F`: ten 16-byte full-label records (length + up to 15 direct glyphs);
- ROM `0x2D8BA0-0x2D8BA1` / `$ED:8BA0-$8BA1`: marker `53 56` required by the exact VWF backend.

`$C7:7B6A-$7B6B` is owned by `french_menus` for the native `GP -> PO` translation;
to `french_resources`). The full-label table is inert in standalone
`french_menus`; only `vwf_ui` renders it.

## Other fixed writes

- ROM `0x07780A-0x07780B` / `$C7:780A-$780B`: GAME SELECT text pointer `$7313 -> $4400`.
- ROM `0x07756D`, `0x077572`, `0x077577`: GAME SELECT frame widths derived from translated encoded cell counts; current validated values remain `$07/$05/$06`.
- ROM `0x0033B5-0x0033B7`: GAME SELECT welcome/help pointer redirected to `$ED:8000`.
- ROM `0x0016F6`: standalone direct/DTE threshold `$D3 -> $E6` for the `full_french` glyph profile. Aggregate builds may supersede this legacy immediate with the shared context router documented in `docs/COMPATIBILITY.md`.

No private WRAM is allocated by this component.

- ROM `0x077B69` / `$C7:7B69`: one fixed-font blank used only as the Status money/unit separator; local code operand at ROM `0x0769BC` / `$CE:E9BC` changes `$7B6A -> $7B69`, so the following `PO` literal is now owned by `french_menus`.

## Weapon / magic default help — candidate 2026-09-26

The user approved the JP/Android-backed wording. `french_menus` now owns the
six source-ID-bound rows in `translations/interface_text_french.json`.
Pointers `$C0:33C4/$33C7` target `$ED:A000/$A100`; each block reserves 256 bytes
(153/152 used). Stock three-line fixed rendering and all descriptions remain
unchanged. Runtime validation is pending; promoted IPS files remain untouched.
Candidate artifacts and full provenance/checks: `docs/SKILL_MENU_HELP_RESEARCH.md`
and `build/candidates/skill-help-20260926/` at the repository root.
