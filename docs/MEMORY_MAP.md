# Global memory map

Major allocations used by the patch kit. Ranges marked as reserved are kept free
for the owning component even when the current generated payload is shorter.

| Component | ROM | CPU/SNES | Purpose |
|---|---:|---:|---|
| 9-char names | `0x074E00-0x074E6D` | `$C7:4E00-$4E6D` | private four-row Name Entry layout script |
| 9-char names | `0x244000-0x2441FF` | `$E4:4000-$41FF` | reserved generated character/help resource |
| GAME SELECT | `0x074400-0x07442C` | `$C7:4400-$442C` | 45-byte relocated label resource |
| GAME SELECT | `0x2D8000-0x2DFFFF` | `$ED:8000-$FFFF` | reserved relocated help-text region |
| French opening | `0x2E8000-0x2E8FFF` | `$EE:8000-$8FFF` | reserved relocated title-arrangement region |
| French opening | `0x2E9000-0x2EFFFF` | `$EE:9000-$FFFF` | reserved opening-helper region |
| Mana Tree | `0x2FC000-0x2FF5FF` | `$EF:C000-$F5FF` | Japanese Mana Tree resource |
| Mana Tree | `0x2FF800-0x2FF89F` | `$EF:F800-$F89F` | 160-byte resource-loader helper |
| intro VWF | `0x074285-0x0743FE` | `$C7:4285-$43FE` | reserved VWF renderer/parser code region |
| intro VWF | `0x074440-0x0744BF` | `$C7:4440-$44BF` | 128-byte width table |
| intro VWF | `0x0744C0-0x074CBF` | `$C7:44C0-$4CBF` | 128 × 12-byte compact glyph table |
| intro VWF | `0x074D00-0x074D31` | `$C7:4D00-$4D31` | 25-pair private DTE table |
| intro VWF | WRAM | `$7E:9390-$93BB` | 44-byte private parser buffer |

The Name Entry layout begins after the intro VWF DTE allocation. GAME SELECT's
relocated label block ends before the intro VWF width table. New allocations
must be checked against both the reserved ranges above and the actual IPS write
maps produced by all components.

`04_french_opening` also repurposes tile `$7A` inside its existing opening-font resource as a one-cell `É` for startup credits. This is a font-slot convention rather than a new ROM or WRAM allocation; the scrolling-text accent tiles `$7D-$7F` remain unchanged.
