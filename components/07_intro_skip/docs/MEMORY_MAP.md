# Memory map — 07_intro_skip

| Range | Size | Purpose | Status |
| --- | ---: | --- | --- |
| ROM `$C0:012C-$012F` | 4 bytes | Event-engine hook to component helper | Runtime-validated |
| ROM `$C0:AC34-$AC37` | 4 bytes | Per-NMI R-release reset hook | Runtime-validated |
| ROM `$CA:FFC0-$FFC7` | 8 bytes | Clean transition to waterfall, omitting Mode 7 flyover | Runtime-validated |
| ROM `$ED:7400-$74FF` | 256 bytes reserved | Intro gate, R hold timer, NMI release helper and event-pointer redirect | Runtime-validated |
| WRAM `$7E:938A` | 1 byte | Start frame for current R hold | Runtime-validated, `$CA` intro scope only |
| WRAM `$7E:938B` | 1 byte | R-hold active flag | Runtime-validated, `$CA` intro scope only |

The timer samples stock NMI frame counter `$7E:00F4`. `$7E:938A-$938B` are
unused by component 05's intro VWF renderer, whose local scratch occupies
`$7E:9380-$9389` and whose parser buffer is `$7E:9390-$93BB`. Component 06 also uses `$7E:938A-$938B` for its width-table index, including
ordinary `$CA` event dialogue. During translated intro event `$0400`, component
05 intercepts the renderer before component 06 reaches its entry hook, keeping
the lifetimes mutually exclusive.

The NMI release helper lives at `$ED:7490+`. It only clears `$7E:938B` when a
hold is active and R is no longer held, then restores the overwritten stock
`LDA $000E / AND $000F` sequence before returning to `$C0:AC3A`.
