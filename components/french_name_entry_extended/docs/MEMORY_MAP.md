# Memory map - french_name_entry_extended

All ROM offsets assume the clean unheadered USA ROM. This component is an
overlay and requires `name_entry_extended`.

| ROM offset | SNES address | Purpose |
|---:|---:|---|
| `0x003583-0x0035AE` | `$C0:3583-$35AE` | Override generic 3-row navigation with 4-row navigation |
| `0x0016F5-0x0016F8` | `$C0:16F5-$16F8` | Name Entry / PLAYER_NAME-aware direct/DTE router hook |
| `0x0745F0-0x074623` | `$C7:45F0-$4623` | 52-byte Name Entry / PLAYER_NAME DTE helper |
| `0x074624-0x07462F` | `$C7:4624-$462F` | Reserved tail of the 64-byte helper slot |
| `0x074C86` | `$C7:4C86` | Base DTE threshold for the name-specific router (`$E1` standalone overlay context) |
| `0x074E00-0x074E6D` | `$C7:4E00-$4E6D` | Override generic 3-row private layout with validated 4-row layout |
| `0x075019` | `$C7:5019` | Override generic/stock initial selector `$60` -> `$50` for four-row geometry |
| `0x12DFE4-0x12DFEF` | font data | Shared glyph `$D3=♪` |
| `0x12DFF0-0x12E08B` | font data | 13 shared French glyphs `$D4-$E0` |
| `0x12E0C8-0x12E0DF` | font data | Shared glyphs `$E6=°`, `$E7=;` |
| `0x2440B4-0x244188` | `$E4:40B4-$4188` | Fourth row + French help useful payload |
| `0x244189-0x2441FF` | `$E4:4189-$41FF` | Reserved Name Entry tail (zero in the builder image; clean-zero bytes are omitted from standalone IPS) |

The first three character rows and all generic Name Entry engine/selection hooks
remain owned by `name_entry_extended`.
