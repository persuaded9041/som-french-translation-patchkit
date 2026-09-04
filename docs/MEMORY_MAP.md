# Global memory map

Major allocations used by the patch kit. Ranges marked as reserved are kept free
for the owning component even when the current generated payload is shorter.

| Component | ROM | CPU/SNES | Purpose |
|---|---:|---:|---|
| 9-char names | `0x074E00-0x074E6D` | `$C7:4E00-$4E6D` | private four-row Name Entry layout script |
| 9-char names | `0x244000-0x2441FF` | `$E4:4000-$41FF` | reserved generated character/help resource |
| GAME SELECT | `0x074400-0x07442C` | `$C7:4400-$442C` | 45-byte relocated label resource |
| GAME FILE | `0x074D40-0x074DBE` | `$C7:4D40-$4DBE` | relocated save/load-menu resource for expanded `Fichier` label |
| GAME SELECT | `0x2D8000-0x2D83FF` | `$ED:8000-$83FF` | relocated GAME SELECT welcome/help text |
| GAME FILE | `0x2D8400-0x2DFFFF` | `$ED:8400-$FFFF` | relocated GAME FILE save-help text / reserved component text space |
| French opening | `0x2E8000-0x2E8FFF` | `$EE:8000-$8FFF` | reserved relocated title-arrangement region |
| French opening | `0x2E9000-0x2EFFFF` | `$EE:9000-$FFFF` | reserved opening-helper region |
| Mana Tree | `0x2FC000-0x2FF5FF` | `$EF:C000-$F5FF` | Japanese Mana Tree resource |
| Mana Tree | `0x2FF800-0x2FF89F` | `$EF:F800-$F89F` | 160-byte resource-loader helper |
| intro VWF | `0x074285-0x0743FE` | `$C7:4285-$43FE` | reserved VWF renderer/parser code region |
| intro VWF | `0x074440-0x0744BF` | `$C7:4440-$44BF` | 128-byte width table |
| intro VWF | `0x0744C0-0x074CBF` | `$C7:44C0-$4CBF` | 128 × 12-byte compact glyph table |
| intro VWF | `0x074D00-0x074D31` | `$C7:4D00-$4D31` | 25-pair private DTE table |
| intro VWF | WRAM | `$7E:9390-$93BB` | 44-byte private parser buffer |

The GAME FILE relocation uses the stock-`$FF` gap after the intro VWF DTE allocation and ends before the Name Entry layout at `C7:4E00`. GAME SELECT's relocated label block ends before the intro VWF width table. New allocations
must be checked against both the reserved ranges above and the actual IPS write
maps produced by all components.

`04_french_opening` also repurposes tile `$7A` inside its existing opening-font resource as a one-cell `É` for startup credits. This is a font-slot convention rather than a new ROM or WRAM allocation; the scrolling-text accent tiles `$7D-$7F` remain unchanged.

GAME FILE also uses three in-place code/data edits: ROM `0x0753C9` / `$C7:53C9` and `0x075AF1` / `$C7:5AF1` change the dynamic level prefix from `L` to `N` (`$A6 -> $A8`), and ROM `0x077585` / `$C7:7585` changes the FILE-frame descriptor from `$03` (6 text cells) to `$04` (8 text cells). These are not new allocations.

## 06_dialogue_vwf — stock-glyph-addressing / limited VWF development

| Range | Purpose |
| --- | --- |
| `0x0013A3-0x0013A8` (`$C0:13A3-$13A8`) | Runtime-validated stock-equivalent progression hook. |
| `0x00167D-0x001680` (`$C0:167D-$1680`) | Runtime-validated renderer-entry trampoline; resets the private `$C9` pixel cursor. |
| `0x001168-0x00116B` (`$C0:1168-$116B`) | Runtime-validated post-stock-outline hook for `$C9` boundary repair; stock `$C0:162C` has already executed. |
| `0x001686-0x001689` (`$C0:1686-$1689`) | Runtime-validated per-character destination-position hook; stock glyph-index code begins immediately afterwards at `$C0:168A`. |
| `0x0016B1-0x0016B6` (`$C0:16B1-$16B6`) | Runtime-validated variable-width cursor advance and stock loop-termination hook. |
| `0x2D7010-0x2D7019` (`$ED:7010-$ED:7019`) | Stock-equivalent progression trampoline. |
| `0x2D7040-0x2D7053` (`$ED:7040-$ED:7053`) | Renderer initialization helper. |
| `0x2D7180-0x2D71A9` (`$ED:7180-$ED:71A9`) | Dialogue VWF per-character `Y` helper derived from the continuous pixel cursor. |
| `0x2D7280-0x2D72E9` (`$ED:7280-$ED:72E9`) | Runtime-validated `$C9` cross-cell outline-boundary helper. |
| `0x2D71B0-0x2D71E7` (`$ED:71B0-$ED:71E7`) | Dialogue VWF lowercase framing selector; placed after the validated char-start routine and before the width table. |
| `0x2D71E8-0x2D71F7` (`$ED:71E8-$ED:71F7`) | Dialogue VWF punctuation selector / dispatch; runtime-validated; `$BF-$C2` stay unshifted to preserve their 1 px left gap. |
| `0x2D72F0-0x2D733F` (`$ED:72F0-$ED:733F`) | Dialogue VWF extended post-lowercase selector; preserves validated A-Z/punctuation handling, leaves `$B5-$BE` and `$CD-$D3` generic, and hosts the runtime-validated French `$D4-$E5` framing. |
| `0x2D70C0-0x2D70F2` (`$ED:70C0-$ED:70F2`) | Dialogue VWF table-driven cursor advance / stock loop-termination helper. |
| WRAM `$7E:9382` | Private 8-bit dialogue pixel cursor, shared only under mutually exclusive `$C9`/`$CA` scopes with component 05. |
| `0x2D7200-0x2D727F` (`$ED:7200-$ED:727F`) | Dialogue VWF 128-entry advance table. |
| WRAM `$7E:9386-$9387` | Temporary multiply-by-12 scratch for destination `Y`. |
| WRAM `$7E:938A-$938B` | Zero-extended dialogue width-table index, `$C9` scope only. |

The current dialogue VWF does not replace the stock glyph-addressing block `$C0:168A-$C0:16B0`. Its advances are read from the runtime-validated 128-entry table at `$ED:7200-$ED:727F`; the zero-extended table index uses `$7E:938A-$938B` only in the `$C9` dialogue scope.

### 06_dialogue_vwf — table-driven limited VWF

In addition to the other runtime-validated dialogue hooks, component 06 hooks
`0x0016A4-0x0016A7` (`$C0:16A4-$16A7`) to a helper at
`0x2D7100` (`$ED:7100`) for row shifting and cross-tile spill composition.
Temporary WRAM `$7E:9383-$9384` and `$7E:9388-$9389` is used only in the `$C9`
dialogue scope and remains mutually exclusive with component 05's `$CA` intro
use.

Runtime status: the continuous-cursor limited VWF, the 128-entry advance-table lookup, drawn-glyph advances from 3 through 8 px, complete lowercase framing/metrics, A-Z, the post-stock outline repair, and punctuation including colon `$C5` are runtime-tested. `$B5-$BE` are digits `0-9` and keep their satisfactory stock widths. `$CD` remains completely excluded from special handling. The canonical French range `$D4-$E5` is runtime-validated at `$D4-$E3=shift 1/advance 7`, `$E4/$E5=shift 0/advance 8`. The framing selector remains at `$ED:71B0-$ED:71E7`, and the validated char-start helper remains fixed at `$ED:7180`. The separate `Wait up!` event-boundary spacing issue is intentionally deferred and contributes no active code or allocation; see `components/06_dialogue_vwf/docs/EVENT_INTERRUPTION_NOTES.md`.
