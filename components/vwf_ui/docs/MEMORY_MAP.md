# vwf_ui memory map

`vwf_ui` is standalone and shares only byte-identical VWF infrastructure with
`vwf_intro` / `vwf_dialogues`.

| Range | Purpose |
|---|---|
| `$C7:4C87` | `vwf_ui` UI-VWF config marker `$09` |
| `$ED:7A00+` | shared renderer-entry dispatcher installed identically by `vwf_dialogues` / `vwf_ui` |
| `$ED:7B00-$7CFF` | `vwf_ui` UI renderer reserve |
| `$ED:7D00-$7D7F` | 128-byte validated VWF advance table |
| `$ED:7E00-$7E7F` | exact Forge-row submit wrapper (`$00:19D0`) |
| `$7E:93C1` | one-shot exact Forge-submit UI tag |
| `$7E:93C3-$93C9` | `vwf_ui` renderer-only temporary state |

The renderer also reuses the shared `$7E:9382+` compositor scratch and
`$7E:9390-$93BB` private text buffer **only after stock parsing has completed**.
It does not enable shared private parser mode.

## Forge patches

- the exact Forge-row submit sequence (X=`$19D0`, bank `$00`, immediately before
  `$D0:D5D7`) is redirected to the `vwf_ui` wrapper. The wrapper arms the
  one-shot tag only for that mini-event; the earlier `WEAPON_NAME` helper remains stock.
- Forge suffix `TEXT_X` arguments are moved from logical slots 16/21 to 20/25 so
  19-character French weapon names survive stock decoding.
- shared stock-capacity helper adds +3 only while both the `vwf_ui` ROM marker
  and exact one-shot tag are active.
- renderer compacts logical suffix slots 20..31 leftward so the arrow begins one
  decoded space after the actual weapon-name end under VWF.
