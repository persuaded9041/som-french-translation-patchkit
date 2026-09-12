# french_dialogues memory map

`french_dialogues` owns event-data writes and the relocation mechanism. It does
not own the VWF renderer or private dialogue WRAM.

| Purpose | File offset | CPU address | Notes |
|---|---:|---:|---|
| dialogue DTE router | `0x074570-0x0745EE` | `$C7:4570-$45EE` | 127-byte shared context-sensitive direct/DTE router |
| dialogue DTE marker | `0x074C85` | `$C7:4C85` | shared `$E8` dialogue-DTE marker |
| French dialogue glyphs | `0x12DFE4-0x12E0DF` | `$D2:DFE4-$E0DF` | canonical `dialogue_french` `$D3-$E7` glyph span |
| event resolver hook | `0x01E794-0x01E799` | `$C1:E794-$E799` | 6-byte stock dispatcher replacement, only meaningful when relocation exists |
| sparse relocation table | `0x280000-0x2817FF` | `$E8:0000-$17FF` | 2048 × 3-byte entries; zero bank byte means stock fallback |
| resolver helper reserve | `0x281800-0x281FFF` | `$E8:1800-$1FFF` | current helper is 83 bytes at `$E8:1800-$1852` |
| relocated event pool | `0x282000-0x2CFFFF` | `$E8:2000-$EC:FFFF` | deterministic growth-only payload packing; events never cross banks |

In-place event rewrites remain in their original `$C9/$CA` spans and therefore
are not represented as one contiguous allocation here.

The expanded-ROM relocation table/helper/pool is installed only when at least
one rebuilt event outgrows its original clean-USA span. Unrelocated events keep
the live stock pointer path, preserving `french_intro` / `vwf_intro` ownership of
`$0400-$040F`.

No private WRAM is allocated by this component.
