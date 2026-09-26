# Memory map - name_entry_extended

All ROM offsets assume the clean unheadered USA ROM. No private WRAM is used.

| ROM offset | SNES address | Purpose |
|---:|---:|---|
| `0x00319C` | `$C0:319C` | Maximum name length = 9 |
| `0x00334D-0x00334E` | `$C0:334D-$334E` | Up-handler pointer -> `$3583` |
| `0x003363-0x003364` | `$C0:3363-$3364` | Down-handler pointer -> `$3595` |
| `0x0033BE-0x0033C0` | `$C0:33BE-$33C0` | Name Entry resource -> `$E4:4000` |
| `0x003583-0x0035AE` | `$C0:3583-$35AE` | Three-row Up/Down navigation handlers in the former stock resource area |
| `0x074E00-0x074E6A` | `$C7:4E00-$4E6A` | Private 107-byte three-row layout script |
| `0x075019` | `$C7:5019` | Stock initial vertical selector `$60` retained |
| `0x07502A` | `$C7:502A` | Naming grid/lookup parameter `$0C` |
| `0x0750A6-0x0750B7` | `$C7:50A6-$50B7` | Character lookup redirected to `$E4:4000` |
| `0x07759D-0x0775A9` | `$C7:759D-$75A9` | 9-character Name Entry layout/control bytes |
| `0x07781C-0x077821` | `$C7:781C-$7821` | Pointer trio `$74EA,$4E00,$74EA` |
| `0x244000-0x2441FF` | `$E4:4000-$41FF` | Reserved Name Entry resource window; standalone generic data currently occupies the prefix through `$E4:414C` |

## Selector states

`$A15A` uses exactly three vertical states in the generic component:

```text
$60 uppercase
$70 lowercase
$80 symbols
```

Up/Down changes the state by `$10` and wraps across those three states.
`french_name_entry_extended` overrides the navigation/layout, adds a new `$50`
top row and therefore uses `$50/$60/$70/$80`.
