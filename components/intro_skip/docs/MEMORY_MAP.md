# Memory map — intro_skip

| Range | Size | Purpose | Status |
| --- | ---: | --- | --- |
| ROM `$C0:012C-$012F` | 4 bytes | Event-engine hook to `$ED:7400`; helper reproduces the overwritten `PHP / SEP #$20 / REP #$10` prologue before returning at `$C0:0131` | Runtime-validated |
| ROM `$C0:AC34-$AC37` | 4 bytes | Per-NMI release hook to `$ED:7490`; helper restores the complete overwritten `LDA $000E / AND $000F` sequence before returning at `$C0:AC3A` | Runtime-validated |
| ROM `$CA:FFC0-$FFC7` | 8 bytes | Clean transition to waterfall, omitting the Mode 7 flyover | Runtime-validated |
| ROM `$ED:7400-$7487` | 136 bytes | Intro gate, non-blocking R-hold timer and event-pointer redirect | Runtime-validated |
| ROM `$ED:7488-$748F` | 8 bytes | Reserved gap before NMI helper | Free inside component reserve |
| ROM `$ED:7490-$74AD` | 30 bytes | Per-NMI physical-release helper | Runtime-validated |
| ROM `$ED:74AE-$74FF` | 82 bytes | Remaining component reserve | Free inside component reserve |
| WRAM `$7E:938A` | 1 byte | NMI frame at which the current R hold began | Runtime-validated, translated intro only |
| WRAM `$7E:938B` | 1 byte | R-hold active flag | Runtime-validated, translated intro only |

The component owns the full ROM reservation `$ED:7400-$74FF`, although only the
ranges listed above currently contain code. The builder checks the whole reserve
is unused on the clean expanded ROM and prevents the two generated helpers from
growing into one another or beyond `$ED:74FF`.

The timer samples the stock NMI frame counter `$7E:00F4`. `$7E:938A-$938B` are
unused by `vwf_intro`'s intro VWF renderer, whose local scratch occupies
`$7E:9380-$9389` and whose parser buffer is `$7E:9390-$93BB`. `vwf_dialogues`
uses `$7E:938A-$938B` as part of its ordinary event-render scratch, but
`vwf_intro` intercepts translated event `$0400` before `vwf_dialogues` reaches
its renderer entry. Their lifetimes are therefore mutually exclusive.

The NMI helper only clears `$7E:938B` when a hold is active and R is physically
released. This prevents separate presses from accumulating even if the
event-engine hook is not sampled during the release interval.
