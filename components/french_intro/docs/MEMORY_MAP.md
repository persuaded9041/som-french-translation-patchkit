# Memory map

## ROM hooks / in-place edits

| ROM file offset | CPU address | Purpose |
| --- | --- | --- |
| `0x0016F6` | `$C0:16F6` | direct/DTE threshold `$D3 -> $E6` for the full French charset |
| `0x001719-0x00171C` | `$C0:1719-$171C` | intro-private DTE loader hook |

## ROM code / data

| ROM file offset | CPU address | Purpose |
| --- | --- | --- |
| `0x074C40-...` | `$C7:4C40-...` | intro DTE loader helper |
| `0x074D00-0x074D31` | `$C7:4D00-$4D31` | 25-pair private intro DTE table |
| `0x0A0C02-0x0A0E8A` | `$CA:0C02-$0E8A` | rebuilt French event `$0400` |
| `0x0AFF70-0x0AFFB7` | `$CA:FF70-$FFB7` | unchanged stock events `$0401-$040F`, relocated |

The relocation bytes and pointer updates intentionally overlap byte-identically
with `vwf_intro`, which also needs the following events moved out of its
validated `$0C02-$0E8B` runtime window when used standalone.
