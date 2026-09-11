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
| intro VWF | `0x074285-0x07437C` | `$C7:4285-$437C` | intro VWF renderer using the runtime-validated shared compositor |
| shared VWF parser | `0x0743D0-0x0743E7` | `$C7:43D0-$43E7` | byte-identical private/stock parser-write helper installed by `vwf_intro` / `vwf_dialogues` |
| intro VWF | `0x074440-0x0744BF` | `$C7:4440-$44BF` | 128-byte width table |
| shared VWF framing | `0x0744C0-0x074557` | `$C7:44C0-$4557` | 152-byte runtime framing selector bundle shared by `vwf_intro` / `vwf_dialogues` |
| shared VWF row renderer | `0x074560-0x07456C` | `$C7:4560-$456C` | 13-byte stock-font row load + framing + compositor helper installed byte-identically by `vwf_intro` / `vwf_dialogues` |
| dialogue DTE router | `0x074570-0x0745EE` | `$C7:4570-$45EE` | 127-byte context-sensitive `$E6/$E8` direct/DTE decision helper installed byte-identically by `vwf_dialogues` / `french_dialogues`; bank `$E4` Name Entry resource uses `$E8` |
| Name Entry DTE router | `0x0745F0-0x07462F` | `$C7:45F0-$462F` | 64-byte reserved Name Entry / PLAYER_NAME helper region used by 02 standalone |
| shared VWF parser | `0x074AC0-0x074BE9` | `$C7:4AC0-$4BE9` | shared caller-gated buffer init / previous-char / capacity helpers (with gaps) |
| intro VWF | `0x074C40-0x074C6B` | `$C7:4C40-$4C6B` | intro-private DTE loader |
| shared VWF/config | `0x074C80-0x074C86` | `$C7:4C80-$4C86` | intro marker/end (`05`), dialogue VWF marker (`06`), dialogue-DTE `$E8` marker, Name Entry base threshold (`02`) |
| shared VWF compositor | `0x074C90-0x074CCE` | `$C7:4C90-$4CCE` | byte-identical 8×12 shift/merge/spill helper installed by `vwf_intro` / `vwf_dialogues` |
| shared UI VWF config | `0x074C87` | `$C7:4C87` | `vwf_ui` marker `$09`; shared capacity/renderer infrastructure stays dormant without it |
| intro VWF | `0x074D00-0x074D31` | `$C7:4D00-$4D31` | 25-pair private DTE table |
| intro VWF | `0x0A0C02-0x0A0E8A` | `$CA:0C02-$0E8A` | rebuilt translated event `$0400` in the current generated build |
| intro VWF | `0x0AFF70-0x0AFFB7` | `$CA:FF70-$FFB7` | relocated unchanged stock events `$0401-$040F` |
| intro VWF | WRAM | `$7E:9380-$9389` | intro-only VWF scratch state |
| shared VWF parser | WRAM | `$7E:9390-$93BB` | 44-byte decoded-text private buffer shared by intro/dialogue modes |
| intro skip | `0x00012C-0x00012F` | `$C0:012C-$012F` | runtime-validated event-engine hook and R trigger, gated to translated event `$0400` |
| intro skip | `0x0000AC34-0x0000AC37` | `$C0:AC34-$AC37` | per-NMI R-release reset hook |
| intro skip | `0x0AFFC0-0x0AFFC7` | `$CA:FFC0-$FFC7` | runtime-validated R-triggered end-of-intro cleanup + direct-waterfall event |
| dialogue text relocation | `0x01E794-0x01E799` | `$C1:E794-$E799` | runtime-validated sparse-event resolver hook; installed only when relocation is used |
| dialogue text relocation | `0x280000-0x2817FF` | `$E8:0000-$17FF` | sparse 2048-entry 24-bit relocation table |
| dialogue text relocation | `0x281800-0x281FFF` | `$E8:1800-$1FFF` | reserved event-loader resolver helper |
| dialogue text relocation | `0x282000-0x2CFFFF` | `$E8:2000-$EC:FFFF` | reserved deterministic relocated-event pool |
| dialogue VWF | `0x2D7340-0x2D73AA` | `$ED:7340-$73AA` | runtime-validated generic interrupted-chunk physical-cell commit/snapshot helpers |
| dialogue VWF | `0x2D73B0-0x2D73B8` | `$ED:73B0-$73B8` | runtime-validated renderer-active scope helper |
| intro skip | `0x2D7400-0x2D74FF` | `$ED:7400-$74FF` | reserved intro-skip input helper region |
| dialogue VWF | `0x2D7500-0x2D77FF` | `$ED:7500-$77FF` | pixel-aware parser preflight, glyph-fit helper and framed-right-edge table; gaps reserved to `vwf_dialogues` |
| shared UI/dialogue dispatcher | `0x2D7A00-0x2D7A7F` | `$ED:7A00-$7A7F` | byte-identical renderer-entry dispatcher installed by `vwf_dialogues` / `vwf_ui` |
| UI VWF renderer | `0x2D7B00-0x2D7CFF` | `$ED:7B00-$7CFF` | `vwf_ui` standalone non-dialogue UI renderer reserve (Forge backend first) |
| UI VWF metrics | `0x2D7D00-0x2D7D7F` | `$ED:7D00-$7D7F` | `vwf_ui` validated 128-entry advance table |
| UI VWF Forge wrapper | `0x2D7E00-0x2D7E7F` | `$ED:7E00-$7E7F` | exact Forge-row submit wrapper (`$00:19D0`) |


`french_dialogues` keeps in-place reinsertion for rebuilt events that still fit
their clean-USA span. Growth is now handled by a sparse 24-bit relocation table
and the reserved `$E8-$EC` pool above. Unrelocated IDs still read the live stock
pointer tables, preserving `vwf_intro`'s ownership of `$0400-$040F`. The
relocation path is runtime-validated: unchanged event `$0107` executed from
`$E8:2000` with normal dynamic-name insertion, VWF rendering, line breaks and
WAIT behavior. The temporary force probe has been removed; normal builds
relocate only translated events that genuinely outgrow their clean-USA span.

`vwf_intro` / `vwf_dialogues` contain the minimal validated extension needed to accept
`$E8-$EC` under their existing structural event-parser / renderer caller gates.
Their validated `$C9/$CA` behavior is otherwise unchanged.

The GAME FILE relocation uses the stock-`$FF` gap after the intro VWF DTE allocation and ends before the Name Entry layout at `C7:4E00`. GAME SELECT's relocated label block ends before the intro VWF width table. New allocations
must be checked against both the reserved ranges above and the actual IPS write
maps produced by all components.

`french_opening` also repurposes tile `$7A` inside its existing opening-font resource as a one-cell `É` for startup credits. This is a font-slot convention rather than a new ROM or WRAM allocation; the scrolling-text accent tiles `$7D-$7F` remain unchanged.

GAME FILE also keeps its translation-JSON-backed stock label fields synchronized in place at `C7:7340-C7:73BB`, because runtime validation showed that one menu path still reads them even after the two table pointers are redirected to `C7:4D40`. The four-cell stock FILE field contains the `Fich` prefix; the relocated resource contains full `Fichier`. Additional in-place edits at ROM `0x0753C9` / `$C7:53C9` and `0x075AF1` / `$C7:5AF1` change the dynamic level prefix from `L` to `N` (`$A6 -> $A8`), and ROM `0x077585` / `$C7:7585` changes the FILE-frame descriptor from `$03` (6 text cells) to `$04` (8 text cells). These are not new allocations.

## vwf_dialogues — global allocation view

`vwf_intro`, `vwf_dialogues`, and `vwf_ui` install byte-identical shared parser/capacity hooks/helpers in
`$C0:16B8/$16C6/$17CE/$18DE` and `$C7:43D0/$4AC0+`. The helper classifies the
parser caller structurally (`$114B` event engine vs `$235B` GAME SELECT) and
uses `$7E:9390-$93BB` for private VWF decoding. Component-owned config bytes at
`$C7:4C80-$4C84` select intro mode 1 or dialogue mode 2.

`vwf_dialogues` uses renderer hooks in bank `$C0` and helper/table space in the
`$ED:7040-$73B8` and `$ED:7500-$792A` areas. Choice rows use the same renderer path as ordinary dialogue; there is no `vwf_dialogues` `$9381` choice tag. The measured-end two-option path additionally uses `$7E:93BC-$93C0` for private visual/highlight boundaries while leaving stock `$A1D7[]` logical and untouched. Core renderer scratch remains `$7E:9382-$938F`.
These bytes are used only for caller-tagged event-render
invocations in stock banks `$C9/$CA` and validated reserved banks `$E8-$EC`. `vwf_intro`
intercepts translated intro event `$0400` before `vwf_dialogues` reaches its entry
hook, so their overlapping WRAM scratch remains mutually exclusive.

The complete hook-by-hook allocation, fixed addresses and scratch ownership are
documented in `components/vwf_dialogues/docs/MEMORY_MAP.md`. This root map
intentionally avoids duplicating renderer status and calibration details.

`intro_skip` runtime checkpoint reuses `$7E:938A-$938B` only during translated intro event `$0400` for a non-blocking R-hold timer. `vwf_intro` intercepts that event before `vwf_dialogues`'s renderer entry, so `vwf_dialogues` does not use its overlapping width-index scratch during the intro. A 4-byte NMI hook at `$C0:AC34-$AC37` clears the active-hold flag on physical R release so separate presses cannot accumulate. Both helpers remain inside the existing `$ED:7400-$74FF` reserve.


## vwf_ui — non-dialogue UI VWF

`vwf_ui` reuses shared framing/compositor/stock-row helpers but owns its own
renderer. `$7E:93C1` is its one-shot exact-builder tag; `$7E:93C3-$93C9` are
renderer-only scratch. It may reuse `$7E:9390-$93BB` only after stock parsing has
completed, so it does not enable the private parser mode used by `vwf_intro` / `vwf_dialogues`.
The accepted Forge path keeps the stock parser/buffer, grants +3 logical units
only under the exact tag, then compacts the suffix visually under VWF.

## french_resources — CA resource table/blob

`french_resources` rewrites the canonical 513-entry `$CA` resource pointer table and the translated
name-family payload within the original stock allocation beginning at `$CA:98E1`. The current
translated blob is 7056 bytes versus the 7315-byte stock allocation; no relocation or new ROM
allocation is used. Its French glyph/DTE infrastructure is shared byte-identically with `vwf_dialogues` / `french_dialogues`.

