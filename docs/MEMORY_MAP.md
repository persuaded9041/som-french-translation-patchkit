# Global memory map

Major allocations used by the patch kit. Ranges marked as reserved are kept free
for the owning component even when the current generated payload is shorter.

| Component | ROM | CPU/SNES | Purpose |
|---|---:|---:|---|
| 9-char names | `0x074E00-0x074E6D` | `$C7:4E00-$4E6D` | private four-row Name Entry layout script |
| 9-char names | `0x244000-0x2441FF` | `$E4:4000-$41FF` | reserved generated character/help resource |
| GAME SELECT | `0x074400-0x07442C` | `$C7:4400-$442C` | 45-byte relocated label resource |
| GAME FILE | `0x074D40-0x074DBE` | `$C7:4D40-$4DBE` | relocated save/load-menu resource for expanded `Fichier` label |
| GAME SELECT | `0x2D8000-0x2D83FF` | `$ED:8000-$83FF` | relocated GAME SELECT welcome/help text |
| GAME FILE | `0x2D8400-0x2DFFFF` | `$ED:8400-$FFFF` | relocated GAME FILE save-help text / reserved component text space |
| French opening | `0x2E8000-0x2E8FFF` | `$EE:8000-$8FFF` | reserved relocated title-arrangement region |
| French opening | `0x2E9000-0x2EFFFF` | `$EE:9000-$FFFF` | reserved opening-helper region |
| Mana Tree | `0x2FC000-0x2FF5FF` | `$EF:C000-$F5FF` | Japanese Mana Tree resource |
| Mana Tree | `0x2FF800-0x2FF89F` | `$EF:F800-$F89F` | 160-byte resource-loader helper |
| intro VWF | `0x074285-0x0743B8` | `$C7:4285-$43B8` | intro VWF renderer |
| intro VWF | `0x0743D0-0x0743FE` | `$C7:43D0-$43FE` | parser private-write helper |
| intro VWF | `0x074440-0x0744BF` | `$C7:4440-$44BF` | 128-byte width table |
| intro VWF | `0x0744C0-0x074ABF` | `$C7:44C0-$4ABF` | 128 × 12-byte compact glyph table |
| intro VWF | `0x074AC0-0x074C6B` | `$C7:4AC0-$4C6B` | intro-only VWF helper blocks (with intentional internal gaps) |
| intro VWF | `0x074D00-0x074D31` | `$C7:4D00-$4D31` | 25-pair private DTE table |
| intro VWF | `0x0A0C02-0x0A0E8A` | `$CA:0C02-$0E8A` | rebuilt translated event `$0400` in the current generated build |
| intro VWF | `0x0AFF70-0x0AFFB7` | `$CA:FF70-$FFB7` | relocated unchanged stock events `$0401-$040F` |
| intro VWF | WRAM | `$7E:9380-$9389` | intro-only VWF scratch state |
| intro VWF | WRAM | `$7E:9390-$93BB` | 44-byte private parser buffer |
| intro skip | `0x00012C-0x00012F` | `$C0:012C-$012F` | runtime-validated event-engine hook and R trigger, gated to translated event `$0400` |
| intro skip | `0x0000AC34-0x0000AC37` | `$C0:AC34-$AC37` | per-NMI R-release reset hook |
| intro skip | `0x0AFFC0-0x0AFFC7` | `$CA:FFC0-$FFC7` | runtime-validated R-triggered end-of-intro cleanup + direct-waterfall event |
| dialogue VWF | `0x2D7340-0x2D73AA` | `$ED:7340-$73AA` | runtime-validated generic interrupted-chunk physical-cell commit/snapshot helpers |
| dialogue VWF | `0x2D73B0-0x2D73B8` | `$ED:73B0-$73B8` | runtime-validated renderer-active scope helper |
| intro skip | `0x2D7400-0x2D74FF` | `$ED:7400-$74FF` | reserved intro-skip input helper region |

The GAME FILE relocation uses the stock-`$FF` gap after the intro VWF DTE allocation and ends before the Name Entry layout at `C7:4E00`. GAME SELECT's relocated label block ends before the intro VWF width table. New allocations
must be checked against both the reserved ranges above and the actual IPS write
maps produced by all components.

`04_french_opening` also repurposes tile `$7A` inside its existing opening-font resource as a one-cell `É` for startup credits. This is a font-slot convention rather than a new ROM or WRAM allocation; the scrolling-text accent tiles `$7D-$7F` remain unchanged.

GAME FILE also uses three in-place code/data edits: ROM `0x0753C9` / `$C7:53C9` and `0x075AF1` / `$C7:5AF1` change the dynamic level prefix from `L` to `N` (`$A6 -> $A8`), and ROM `0x077585` / `$C7:7585` changes the FILE-frame descriptor from `$03` (6 text cells) to `$04` (8 text cells). These are not new allocations.

## 06_dialogue_vwf — global allocation view

Component 06 uses in-place hooks in bank `$C0` and helper/table space in the
`$ED:7040-$73B8` area. Its renderer scratch is `$7E:9382-$938F` only for
caller-tagged event-render invocations in stock banks `$C9/$CA`. Component 05
intercepts translated intro event `$0400` before component 06 reaches its entry
hook, so their overlapping WRAM scratch remains mutually exclusive.

The complete hook-by-hook allocation, fixed addresses and scratch ownership are
documented in `components/06_dialogue_vwf/docs/MEMORY_MAP.md`. This root map
intentionally avoids duplicating renderer status and calibration details.

`07_intro_skip` runtime checkpoint reuses `$7E:938A-$938B` only during translated intro event `$0400` for a non-blocking R-hold timer. Component 05 intercepts that event before component 06's renderer entry, so component 06 does not use its overlapping width-index scratch during the intro. A 4-byte NMI hook at `$C0:AC34-$AC37` clears the active-hold flag on physical R release so separate presses cannot accumulate. Both helpers remain inside the existing `$ED:7400-$74FF` reserve.
