# Memory map - name_entry_extended

All ROM offsets assume the clean unheadered USA ROM.

| ROM offset | SNES address | Purpose |
|---:|---:|---|
| `0x0016F5-0x0016F8` | `$C0:16F5-$16F8` | Name Entry / PLAYER_NAME-aware direct/DTE router hook |
| `0x00319C` | `$C0:319C` | Maximum name length = 9 |
| `0x00334D` | `$C0:334D` | Up-handler pointer -> `$3583` |
| `0x003363` | `$C0:3363` | Down-handler pointer -> `$3595` |
| `0x0033BE` | `$C0:33BE` | Name Entry resource -> `$E4:4000` |
| `0x003583+` | `$C0:3583+` | Four-row Up/Down navigation handlers |
| `0x0745F0-0x07462F` | `$C7:45F0-$462F` | Reserved 64-byte Name Entry / PLAYER_NAME DTE helper region |
| `0x074C86` | `$C7:4C86` | Base DTE threshold for `name_entry_extended` router (`$E1` standalone) |
| `0x074E00-0x074E6D` | `$C7:4E00-$4E6D` | Private 110-byte four-row layout script |
| `0x075019` | `$C7:5019` | Initial vertical selector `$50` (uppercase row) |
| `0x07502A` | `$C7:502A` | Naming grid/lookup parameter |
| `0x0750A6+` | `$C7:50A6+` | Character lookup -> `$E4:4000` |
| `0x07759D+` | `$C7:759D+` | Name Entry layout/control bytes |
| `0x07781C-0x077821` | `$C7:781C-$7821` | Pointer trio `$74EA,$4E00,$74EA` |
| `0x12DFE4-0x12DFEF` | font data | Shared glyph `$D3=♪` |
| `0x12DFF0-0x12E08B` | font data | 13 shared French glyphs `$D4-$E0` |
| `0x12E0C8-0x12E0DF` | font data | Shared glyphs `$E6=°`, `$E7=;` |
| `0x244000-0x2441FF` | `$E4:4000-$41FF` | Reserved generated four-row character/help resource |

## Selector states

`$A15A` uses these four vertical states:

```text
$50 uppercase
$60 lowercase
$70 symbols
$80 French / extended characters
```

The window itself was moved upward by one 16-pixel character row. The initial
selector and selection-map lookup are adjusted consistently so cursor position
and selected character refer to the same visible row.

## Name Entry / PLAYER_NAME DTE routing

The stock `PLAYER_NAME` command copies twelve bytes to `$7E:A22F` and parses
that temporary source before returning to the event stream. At the shared DTE
hook, that source is recognizable by DB=`$7E` and the post-read Y range
`$A230-$A23B`.

The relocated Name Entry resource in bank `$E4` and that temporary PLAYER_NAME
source use threshold `$E8`; all other sources use the base threshold stored at
`$C7:4C86`. The root combiner raises that base value when a
legacy component such as 05 requires a wider direct range, preserving the
historical max-threshold behavior without corrupting the router JML.

When `vwf_dialogues` / `french_dialogues` are present, their later full dialogue router owns `$C0:16F5` instead;
`name_entry_extended`'s private helper remains unused and harmless.
