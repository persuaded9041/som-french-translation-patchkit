# Memory map

## ROM hooks / in-place edits

| ROM file offset | CPU address | Purpose |
| --- | --- | --- |
| `0x00163D` | `$C0:163D` | outline shift: `ROL` -> `ASL` |
| `0x001664-0x001667` | `$C0:1664-$1667` | intro-only VWF renderer hook |
| `0x0016B8-0x0016BB` | `$C0:16B8-$16BB` | shared private-buffer initialization hook |
| `0x0016C6-0x0016CF` | `$C0:16C6-$16CF` | shared parser-capacity hook |
| `0x0017CE-0x0017D1` | `$C0:17CE-$17D1` | shared parser private-write hook |
| `0x0018DE-0x0018E1` | `$C0:18DE-$18E1` | shared previous-character source hook |

`vwf_intro` no longer owns `$C0:16F6` (French direct/DTE threshold) or
`$C0:1719` (intro-private DTE loader); those belong to `french_intro`.

## ROM code / data allocations

| ROM file offset | CPU address | Purpose |
| --- | --- | --- |
| `0x074285-0x07437C` | `$C7:4285-$437C` | intro VWF renderer |
| `0x0743D0-0x0743E7` | `$C7:43D0-$43E7` | shared parser write helper |
| `0x074440-0x0744BF` | `$C7:4440-$44BF` | 128-byte VWF advance table |
| `0x0744C0-0x074557` | `$C7:44C0-$4557` | shared runtime framing selector bundle |
| `0x074560-0x07456C` | `$C7:4560-$456C` | shared stock-font row renderer helper |
| `0x074AC0-0x074B3B` | `$C7:4AC0-$4B3B` | shared private-buffer initializer |
| `0x074B40-0x074B5A` | `$C7:4B40-$4B5A` | shared previous-character helper |
| `0x074BC0-0x074BE9` | `$C7:4BC0-$4BE9` | shared capacity helper |
| `0x074C80-0x074C82` | `$C7:4C80-$4C82` | intro VWF marker + exclusive end `$0E8B` |
| `0x074C90-0x074CCE` | `$C7:4C90-$4CCE` | shared 8×12 compositor |
| `0x0AFF70-0x0AFFB7` | `$CA:FF70-$FFB7` | unchanged stock events `$0401-$040F`, relocated |

## WRAM

| Address | Purpose |
| --- | --- |
| `$7E:9380-$9389` | intro-only VWF scratch / shared compositor scratch |
| `$7E:9390-$93BB` | private 44-byte parser buffer |
