# Global memory map

Major allocations used by the patch kit.

| Component | ROM | CPU/SNES | Purpose |
|---|---:|---:|---|
| 9-char names | `0x244000` | `$E4:4000` | three naming pages + help text |
| GAME SELECT | `0x074400` | `$C7:4400` | 45-byte relocated label resource |
| GAME SELECT | `0x2D8000` | `$ED:8000` | relocated help text |
| French opening | `0x2E8000` | `$EE:8000` | relocated title arrangement |
| French opening | `0x2E9000` | `$EE:9000` | fixed-width opening helper |
| Mana Tree | `0x2FC000` | `$EF:C000` | Japanese Mana Tree resource |
| Mana Tree | `0x2FF800` | `$EF:F800` | resource-loader helper |
| intro VWF | `0x074285` | `$C7:4285` | VWF renderer/code |
| intro VWF | `0x074440` | `$C7:4440` | width table |
| intro VWF | `0x0744C0` | `$C7:44C0` | compact glyph table |
| intro VWF | `0x074D00` | `$C7:4D00` | private DTE table |
| intro VWF | WRAM | `$7E:9390-$93BB` | 44-byte private parser buffer |

The GAME SELECT label block ends before the intro VWF width table. The opening helper was deliberately moved out of bank C7 so that the intro VWF owns `$C7:4285` without collision.
