# Memory map

## ROM hooks / in-place edits

| ROM file offset | CPU address | Purpose |
| --- | --- | --- |
| `0x00163D` | `$C0:163D` | outline shift: `ROL` -> `ASL` so rows do not consume carry from the previous row |
| `0x001664-0x001667` | `$C0:1664-$1667` | intro-only VWF renderer hook |
| `0x0016B8-0x0016BB` | `$C0:16B8-$16BB` | private-buffer initialization hook |
| `0x0016C6-0x0016CF` | `$C0:16C6-$16CF` | intro parser-capacity hook |
| `0x0016F6` | `$C0:16F6` | direct/DTE threshold `$D3 -> $E6` for the shared French charset |
| `0x001719-0x00171C` | `$C0:1719-$171C` | intro DTE-loader hook |
| `0x0017CE-0x0017D1` | `$C0:17CE-$17D1` | parser private-write hook |
| `0x0018DE-0x0018E1` | `$C0:18DE-$18E1` | previous-character private-read hook |

All hooks fall back to stock behavior outside translated intro event `$0400`.

## ROM code / data allocations

| ROM file offset | CPU address | Purpose |
| --- | --- | --- |
| `0x074285-0x0743B8` | `$C7:4285-$43B8` | intro VWF renderer |
| `0x0743D0-0x0743FE` | `$C7:43D0-$43FE` | parser private-write helper |
| `0x074440-0x0744BF` | `$C7:4440-$44BF` | 128-byte VWF advance table |
| `0x0744C0-0x074ABF` | `$C7:44C0-$4ABF` | 128 × 12-byte compact glyph table |
| `0x074AC0-0x074AFF` | `$C7:4AC0-$4AFF` | private-buffer initialization helper |
| `0x074B40-0x074B6B` | `$C7:4B40-$4B6B` | previous-character helper |
| `0x074BC0-0x074BE4` | `$C7:4BC0-$4BE4` | intro parser-capacity helper |
| `0x074C40-0x074C6B` | `$C7:4C40-$4C6B` | intro DTE-loader helper |
| `0x074D00-0x074D31` | `$C7:4D00-$4D31` | 25-pair private DTE table |
| `0x0A0C02-0x0A0E8A` | `$CA:0C02-$0E8A` | rebuilt translated event `$0400` in the current generated build |
| `0x0AFF70-0x0AFFB7` | `$CA:FF70-$FFB7` | unchanged stock events `$0401-$040F`, relocated because translated `$0400` grows into their former area |

The relocated stock-event block ends before `07_intro_skip` at `$CA:FFC0`.
The current generated event `$0400` ends at pointer `$0E8B`; the last occupied byte is therefore `$CA:0E8A`.

## WRAM

| Address | Purpose |
| --- | --- |
| `$7E:9380-$9389` | intro-only VWF scratch state |
| `$7E:9390-$93BB` | private 44-byte parser buffer |

These WRAM ranges are used only while translated intro event `$0400` runs. Component 06 now also supports ordinary `$CA` event dialogue, but the overlap remains safe: component 05 intercepts event `$0400` at `$C0:1664` and exits before component 06 reaches its `$C0:167D` renderer-entry hook.
