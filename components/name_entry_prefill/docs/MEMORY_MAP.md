# Memory map - name_entry_prefill

| ROM | CPU/SNES | Purpose |
|---:|---:|---|
| `0x074630-0x0746A0` | `$C7:4630-$46A0` | one-shot editable-name prefill helper |
| `0x0746D0-0x0746E7` | `$C7:46D0-$46E7` | three fixed 8-byte default-name records |
| `0x075039-0x07503C` | `$C7:5039-$503C` | Name Entry init tail: `JML $C7:4630` |

The clean-USA bytes in `$C7:4630-$46A0` and `$C7:46D0-$46E7` are `$FF` and are
reserved by this component. No WRAM allocation is permanent. `$A1CD` is used
only as a short-lived loop counter during the one-shot initialization and is
cleared before returning; the stock confirmation path later uses it independently.

The hook replaces the stock four bytes `9C CC A1 6B` (`STZ $A1CC / RTL`). The
helper itself performs the same `STZ $A1CC` before inserting the configured
characters and returns with `RTL`.
