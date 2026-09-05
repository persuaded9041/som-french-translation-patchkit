# Memory map

## ROM hooks / in-place edits

| ROM file offset | CPU address | Purpose |
| --- | --- | --- |
| `0x00163D` | `$C0:163D` | outline shift: `ROL` -> `ASL` so rows do not consume carry from the previous row |
| `0x001664-0x001667` | `$C0:1664-$1667` | intro-only VWF renderer hook |
| `0x0016B8-0x0016BB` | `$C0:16B8-$16BB` | shared private-buffer initialization hook |
| `0x0016C6-0x0016CF` | `$C0:16C6-$16CF` | shared parser-capacity hook |
| `0x0016F6` | `$C0:16F6` | direct/DTE threshold `$D3 -> $E6` for the shared French charset |
| `0x001719-0x00171C` | `$C0:1719-$171C` | intro DTE-loader hook |
| `0x0017CE-0x0017D1` | `$C0:17CE-$17D1` | shared parser private-write hook |
| `0x0018DE-0x0018E1` | `$C0:18DE-$18E1` | shared previous-character source hook |

All hooks fall back to stock behavior outside translated intro event `$0400`.

## ROM code / data allocations

| ROM file offset | CPU address | Purpose |
| --- | --- | --- |
| `0x074285-0x07437C` | `$C7:4285-$437C` | intro VWF renderer; delegates row composition to runtime-validated shared helper |
| `0x0743D0-0x0743E7` | `$C7:43D0-$43E7` | shared parser write helper |
| `0x074440-0x0744BF` | `$C7:4440-$44BF` | 128-byte VWF advance table |
| `0x0744C0-0x074557` | `$C7:44C0-$4557` | shared 152-byte runtime framing selector bundle |
| `0x074560-0x07456C` | `$C7:4560-$456C` | shared stock-font row load + framing + compositor helper |
| `0x074AC0-0x074B3B` | `$C7:4AC0-$4B3B` | shared caller-gated private-buffer initializer |
| `0x074B40-0x074B5A` | `$C7:4B40-$4B5A` | shared previous-character source helper |
| `0x074BC0-0x074BE9` | `$C7:4BC0-$4BE9` | shared intro/dialogue/stock capacity helper |
| `0x074C40-0x074C6B` | `$C7:4C40-$4C6B` | intro DTE-loader helper |
| `0x074C80-0x074C82` | `$C7:4C80-$4C82` | component-05 intro private-buffer marker + exclusive end pointer |
| `0x074C90-0x074CCE` | `$C7:4C90-$4CCE` | shared 63-byte 8×12 row compositor, installed byte-identically by components 05/06 |
| `0x074D00-0x074D31` | `$C7:4D00-$4D31` | 25-pair private DTE table |
| `0x0A0C02-0x0A0E8A` | `$CA:0C02-$0E8A` | rebuilt translated event `$0400` in the current generated build |
| `0x0AFF70-0x0AFFB7` | `$CA:FF70-$FFB7` | unchanged stock events `$0401-$040F`, relocated because translated `$0400` grows into their former area |

The relocated stock-event block ends before `07_intro_skip` at `$CA:FFC0`.
The current generated event `$0400` ends at pointer `$0E8B`; the last occupied byte is therefore `$CA:0E8A`.

## WRAM

| Address | Purpose |
| --- | --- |
| `$7E:9380-$9389` | intro-only VWF scratch state; `$9383/$9384/$9388/$9389` follow the shared compositor contract |
| `$7E:9390-$93BB` | private 44-byte parser buffer |

`$7E:9390-$93BB` is now the shared decoded-text private buffer for components 05
and 06. Parser mode `$7E:9380` is 1 for the translated intro and 2 for component-06
dialogue decoding; component 05 reuses `$9380` as its character count only after
parsing has finished. Renderer scratch remains mutually exclusive because component
05 intercepts event `$0400` before component 06 reaches `$C0:167D`.
