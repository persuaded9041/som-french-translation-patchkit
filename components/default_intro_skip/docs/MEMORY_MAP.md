# Memory map — intro_skip (runtime-validated final implementation)

The former pre-restart/NMI implementation has been removed. These are the
current validated allocations for the 120-tick continuous-R hold skip.

| Range | Size | Purpose | Status |
| --- | ---: | --- | --- |
| ROM `$C0:012C-$012F` | 4 bytes | JML to active-text observer `$ED:7488` | Runtime validated |
| ROM `$C0:16EA-$16ED` | 4 bytes | standalone JML to `$CA:FFC8`; aggregate merge routes through `$ED:73C0` when `vwf_dialogues` is present | Direct intro path runtime validated; aggregate dispatcher statically audited |
| ROM `$C2:C786-$C789` | 4 bytes | JML to normal-loop hold/WAIT helper `$ED:7400` | Runtime validated |
| ROM `$CA:FFC0-$FFC7` | 8 bytes | private command-only waterfall tail | Runtime validated |
| ROM `$CA:FFC8-$FFFE` | 55 bytes | live-parser completed-hold commit helper | Runtime validated |
| ROM `$ED:73C0-$73CF` | 16 bytes | aggregate parser-fetch dispatcher: mode 2 -> `$ED:7500`, otherwise -> `$CA:FFC8` | Inert in standalone patch; aggregate compatibility path |
| ROM `$ED:7400-$7484` | 133 bytes | normal-loop R hold/decrement + timed-WAIT commit | Runtime validated |
| ROM `$ED:7485-$7487` | 3 bytes | gap | Free inside component reserve |
| ROM `$ED:7488-$74F5` | 110 bytes | active-text timer init/arm/cancel observer | Runtime validated |
| ROM `$ED:74F6-$74FF` | 10 bytes | gap | Free inside component reserve |
| WRAM `$7E:938A-$938B` | 2 bytes | 16-bit hold countdown / state sentinel | Runtime validated during translated `$0400` |

The component continues to reserve the full `$ED:7400-$74FF` block. No code is
placed in the formerly problematic C7 free-space vicinity: the shared VWF helper
at `$C7:43D0-$43E7` and menu/UI allocations at `$C7:4400+` remain untouched.

`$7E:938A-$938B` overlaps scratch used by `vwf_dialogues` outside the intro.
This is safe under the validated lifetime split: `vwf_intro` intercepts translated
`$0400` before the ordinary dialogue renderer path. The component remains safe
in the default aggregate because its own runtime gate limits it to that
translated normal-intro window; `french_intro` still owns the payload itself.
