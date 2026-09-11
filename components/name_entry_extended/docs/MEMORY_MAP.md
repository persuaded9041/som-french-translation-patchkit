# Memory map - name_entry_extended

All ROM offsets assume the clean unheadered USA ROM.

| ROM offset | SNES address | Purpose |
|---:|---:|---|
| `0x00319C` | `$C0:319C` | Maximum name length = 9 |
| `0x00334D` | `$C0:334D` | Up-handler pointer -> `$3583` |
| `0x003363` | `$C0:3363` | Down-handler pointer -> `$3595` |
| `0x0033BE` | `$C0:33BE` | Name Entry resource -> `$E4:4000` |
| `0x003583+` | `$C0:3583+` | Three-row Up/Down navigation handlers |
| `0x074E00-0x074E6A` | `$C7:4E00-$4E6A` | Private 107-byte three-row layout script |
| `0x075019` | `$C7:5019` | Stock initial vertical selector `$60` retained (uppercase row) |
| `0x07502A` | `$C7:502A` | Naming grid/lookup parameter |
| `0x0750A6+` | `$C7:50A6+` | Character lookup -> `$E4:4000` |
| `0x07759D+` | `$C7:759D+` | 9-character Name Entry layout/control bytes |
| `0x07781C-0x077821` | `$C7:781C-$7821` | Pointer trio `$74EA,$4E00,$74EA` |
| `0x244000-0x2441FF` | `$E4:4000-$41FF` | Reserved generic three-row character/help resource |

## Selector states

`$A15A` uses exactly three vertical states in the generic component:

```text
$60 uppercase
$70 lowercase
$80 symbols
```

Up/Down wraps across those three states. `french_name_entry_extended` overrides
the navigation/layout and adds a new `$50` top row and uses `$50/$60/$70/$80`.
