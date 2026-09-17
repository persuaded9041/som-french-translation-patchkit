# Memory map

`french_intro` reserves no private WRAM. Runtime/parser scratch is owned by
`vwf_intro`.

## ROM hooks / in-place edits

| ROM file offset | CPU address | Purpose |
| --- | --- | --- |
| `0x0016F6` | `$C0:16F6` | direct/DTE threshold `$D3 -> $E6` for the intro French profile |
| `0x001719-0x00171C` | `$C0:1719-$171C` | stock DTE table load replaced by intro-private loader call |
| `0x0A0002-0x0A001F` | `$C9:F802-$F81F` | 15 event pointers `$0401-$040F`, redirected to `$CA:FF70-$FFB7` |
| `0x12DFF0-0x12E0C7` | `$D2:DFF0-$E0C7` | canonical `full_french` glyph span `$D4-$E5` (18 × 12 bytes) |

Standalone checksum/header bytes are build metadata and are omitted from this
functional map.

## ROM code / data

| ROM file offset | CPU address | Purpose |
| --- | --- | --- |
| `0x074C40-0x074C6B` | `$C7:4C40-$4C6B` | 44-byte intro-private DTE loader; reserved window ends before `$C7:4C80` shared VWF config |
| `0x074D00-0x074D31` | `$C7:4D00-$4D31` | 25-pair (50-byte) private intro DTE table; exact allocation ends before the `$C7:4D32` GAME FILE money-spacing helper |
| `0x0A0C02-0x0A0E8A` | `$CA:0C02-$0E8A` | rebuilt French event `$0400`; exclusive validated end `$0E8B` |
| `0x0AFF70-0x0AFFB7` | `$CA:FF70-$FFB7` | unchanged stock events `$0401-$040F`, relocated; reserve stops before `$CA:FFC0` `intro_skip` helper |

The relocation bytes and pointer updates intentionally overlap byte-identically
with `vwf_intro`, which also moves the following stock events when used
standalone so its validated `$0C02-$0E8B` runtime window remains exclusive.
