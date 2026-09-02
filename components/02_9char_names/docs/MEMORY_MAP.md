# Memory map — 02_9char_names

All ROM offsets assume the clean unheadered USA ROM.

| ROM offset | SNES address | Purpose |
|---:|---:|---|
| `0x0016F6` | `$C0:16F6` | Direct-glyph/DTE threshold `$E1` for naming-safe French `$D4-$E0` |
| `0x00319C` | `$C0:319C` | Maximum name length = 9 |
| `0x00334D` | `$C0:334D` | Up-handler pointer -> `$3583` |
| `0x003363` | `$C0:3363` | Down-handler pointer -> `$3595` |
| `0x0033BE` | `$C0:33BE` | Name Entry resource -> `$E4:4000` |
| `0x003583+` | `$C0:3583+` | Four-row Up/Down navigation handlers |
| `0x074E00-0x074E6D` | `$C7:4E00-$4E6D` | Private 110-byte four-row layout script |
| `0x075019` | `$C7:5019` | Initial vertical selector `$50` (uppercase row) |
| `0x07502A` | `$C7:502A` | Naming grid/lookup parameter |
| `0x0750A6+` | `$C7:50A6+` | Character lookup -> `$E4:4000` |
| `0x0750E8` | `$C7:50E8` | Selection-map origin (`#$48`) aligned with raised grid |
| `0x07759D+` | `$C7:759D+` | Name Entry layout/control bytes |
| `0x07781C-0x077821` | `$C7:781C-$7821` | Pointer trio `$74EA,$4E00,$74EA` |
| `0x12DFF0-0x12E08B` | font data | 13 shared French glyphs `$D4-$E0` |
| `0x244000-0x2441FF` | `$E4:4000-$41FF` | Reserved generated four-row character/help resource |

## Selector states

`$A15A` uses these four vertical states:

```text
$50 uppercase
$60 lowercase
$70 symbols
$80 accents
```

The window itself was moved upward by one 16-pixel character row. The initial
selector and selection-map lookup are adjusted consistently so cursor position
and selected character refer to the same visible row.

## Shared charset overlap

The `$D4-$E0` font bytes intentionally overlap the identical writes made by
`03_game_select`. When combined with `05_intro_vwf_french`, the intro extends
the direct range through `$E5`; the root combiner resolves the shared decoder
threshold to `$E6`.
