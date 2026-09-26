# Global memory map

Major allocations used by the patch kit. Ranges marked as reserved are kept free
for the owning component even when the current generated payload is shorter.

| Component | ROM | CPU/SNES | Purpose |
|---|---:|---:|---|
| extended Name Entry | `0x074E00-0x074E6A` | `$C7:4E00-$4E6A` | private generic three-row Name Entry layout script; French overlay expands through `$4E6D` |
| extended Name Entry | `0x244000-0x2441FF` | `$E4:4000-$41FF` | generic 3-row character/help resource; `$40B4-$41FF` is overlaid by `french_name_entry_extended` with row 4 + French help |
| name prefill | `0x074630-0x0746A0` | `$C7:4630-$46A0` | 113-byte generic editable default-name one-shot helper |
| French name prefill | `0x074630-0x0746B1` | `$C7:4630-$46B1` | dependent French-capable helper overlay; adds fourth-row token class |
| name prefill | `0x0746D0-0x0746E7` | `$C7:46D0-$46E7` | three 8-byte default-name records (length + up to 7 tokens); French overlay replaces them |
| name prefill | `0x075039-0x07503C` | `$C7:5039-$503C` | Name Entry init-tail hook |
| GAME SELECT | `0x074400-0x07442C` | `$C7:4400-$442C` | 45-byte relocated label resource |
| French controller buttons | `0x002116-0x002118` | `$C0:2116-$2118` | `french_gfx`: skip USA-only palette override (`JSR $212F` -> three NOPs) |
| French controller buttons | `0x12D8F0-0x12D92F` | `$D2:D8F0-$D2:D92F` | `french_gfx`: shared 16×16 controller-button graphic generated from indexed PNG |
| French controller buttons | `0x12DBCC-0x12DBE3` | `$D2:DBCC-$DBE3` | `french_gfx`: exact French X/A/Y/B 2bpp palette ramps |
| French direction marker | `0x07FB20-0x07FB3F` | `$C7:FB20-$FB3F` | `french_gfx`: 4bpp West direction tile (`W` → `O`) |
| French HP indicators | `0x128A00-0x128ABF` | `$D2:8A00-$8ABF` | `french_gfx`: two compressed menu-icon variants (`HP` → `PV`) |
| French MP indicators | `0x129B40-0x129BFF` | `$D2:9B40-$9BFF` | `french_gfx`: two compressed menu-icon variants (`MP` → `PM`) |
| French level indicator | `0x12C420-0x12C47F` | `$D2:C420-$C47F` | `french_gfx`: compressed `LVL` → `NIV` indicator |
| French alternate inn sign | `0x1D1500-0x1D153F`, `0x1D1580-0x1D15BF` | `$DD:1500-$153F`, `$DD:1580-$15BF` | `french_gfx`: split 4bpp `Inn` → `Aub`; intervening range remains stock |
| French Potos inn sign | `0x1F5460-0x1F54DF` | `$DF:5460-$54DF` | `french_gfx`: 4bpp `Inn` → `Aub` |
| Japanese warp hexagram | `0x1DB840-0x1DB85F` | `$DD:B840-$DD:B85F` | `default_uncensored_hexagram`: first restored 4bpp warp-circle tile |
| Japanese warp hexagram | `0x1DB900-0x1DB93F` | `$DD:B900-$DD:B93F` | `default_uncensored_hexagram`: second and third restored 4bpp warp-circle tiles; `0x1DB860-0x1DB8FF` remains untouched |
| Window Settings | `0x074700-0x07472E` | `$C7:4700-$472E` | runtime-validated 46-cell fixed-font source + terminator |
| Window Settings | `0x074730-0x074759` | `$C7:4730-$4759` | ten-span fixed-font placement list |
| GAME FILE money spacing | `0x074D32-0x074D3B` | `$C7:4D32-$4D3B` | 10-byte helper preserving the fixed 16-cell money upload while inserting one separator before the currency suffix |
| GAME FILE | `0x074D40-0x074DBE` | `$C7:4D40-$4DBE` | relocated save/load-menu resource for expanded `Fichier` label |
| Action Settings | `0x074DC0-0x074DFC` | `$C7:4DC0-$4DFC` | runtime-validated fixed-font French label resource (35 bytes) + six-span placement list (26 bytes); remains below Name Entry private layout |
| GAME SELECT | `0x2D8000-0x2D83FF` | `$ED:8000-$83FF` | relocated GAME SELECT welcome/help text |
| GAME FILE | `0x2D8400-0x2D8470` | `$ED:8400-$8470` | relocated GAME FILE save-help text |
| Action Settings | `0x2D8500-0x2D857B` | `$ED:8500-$857B` | relocated fixed-font help block |
| Window Settings | `0x2D8600-0x2D86A2` | `$ED:8600-$86A2` | relocated three-line fixed-font help block |
| Status VWF | `0x2D8700-0x2D8A3F` | `$ED:8700-$8A3F` | exact `vwf_ui` Status converter/slot/copy helpers; only the ten characteristic labels |
| Status full labels | `0x2D8B00-0x2D8BA1` | `$ED:8B00-$8BA1` | `french_menus` ten 16-byte direct-glyph records plus `53 56` source marker |
| weapon/magic skill-row format | `0x074F00-0x074F3F` | `$C7:4F00-$4F3F` | `vwf_ui` runtime-validated compact progress formatter + fixed separator (`$4F00-$4F22`) and scoped 8-row submit wrapper (`$4F30-$4F3F`) |
| weapon/magic skill-row VWF | `0x2D8C00-0x2D8DFF` | `$ED:8C00-$8DFF` | `vwf_ui` runtime-validated scoped name-only VWF overlay; dynamically finds compact prefix in decoded row and falls through to validated Status helper on non-match |
| magic lower-panel stock-flow helpers | `0x074F40-0x074FDF` | `$C7:4F40-$4FDF` | `vwf_ui`: exact six-pass batch clone `$4F40-$4FB4`, reset stub `$4FC0-$4FC7`, capture stub `$4FD0-$4FD7`; preserves stock wait/DMA/tail lifecycle |
| magic lower-panel VWF dispatcher | `0x2D8E00-0x2D90FF` | `$ED:8E00-$90FF` | `vwf_ui` reserved exact-caller 3x480px renderer; current payload 642 bytes, non-magic calls fall through to `$ED:8C00` |
| magic lower-panel ID helpers | `0x2D9140-0x2D91FF` | `$ED:9140-$91FF` | `vwf_ui`: stock-emitted ID capture/Lumina remap helper `$9140-$918E` and reset/invalidate helper `$91C0-$91D4` |
| French magic lower-panel rows | `0x2D9200-0x2D9F23` | `$ED:9200-$9F23` | `french_resources`: 42 × 80-byte complete Android-FR `Nom : description` records through `$9F1F`, followed by runtime marker `MFV1` at `$9F20-$9F23` |
| Weapon/magic help candidate | `0x2DA000-0x2DA1FF` | `$ED:A000-$A1FF` | `french_menus`: two reserved 256-byte pages; weapon payload 153 bytes, magic payload 152 bytes; runtime pending |
| French battle/status text | `0x2E6000-0x2E6FFF` | `$EE:6000-$6FFF` | reserved relocated battle/status text pool owned by `french_resources`; current payload 1573 bytes including four runtime template prefixes |
| French opening helper | `0x2E9000-0x2E9FFF` | `$EE:9000-$9FFF` | reserved helper region; current 37-byte renderer helper is `$EE:9000-$9024` |
| French opening arrangement | `0x2EA000-0x2EBFFF` | `$EE:A000-$BFFF` | literal-only stock-format stream, loaded through `$C1:0014` |
| French shop/forge text | `0x19FE20-0x19FEF3` | `$D9:FE20-$FEF3` | rebuilt nine-record mini-event pool inside the original 212-byte allocation; current French payload uses 179 bytes and rewrites the nine stock bank-C0 `LDX` operands |
| Mana Tree | `0x2FC000-0x2FF5FF` | `$EF:C000-$F5FF` | 0x3600-byte Japanese Mana Tree resource (`$D2A9`) |
| Mana Tree | `0x2FF800-0x2FF89F` | `$EF:F800-$F89F` | 160-byte resource-loader helper; `$D2A9` only, otherwise stock fall-through |
| intro VWF | `0x074285-0x07437C` | `$C7:4285-$437C` | intro VWF renderer using the runtime-validated shared compositor |
| shared VWF parser | `0x0743D0-0x0743E7` | `$C7:43D0-$43E7` | byte-identical private/stock parser-write helper installed by `vwf_intro` / `vwf_dialogues` |
| shared VWF parser classifier | `0x074900-0x07493F` | `$C7:4900-$493F` | shared 64-byte reserve for dialogue/battle private-parser mode classification; battle mode is dormant without exact UI tag `$AC` |
| intro VWF | `0x074440-0x0744BF` | `$C7:4440-$44BF` | 128-byte width table |
| shared VWF framing | `0x0744C0-0x074557` | `$C7:44C0-$4557` | 152-byte runtime framing selector bundle shared by `vwf_intro` / `vwf_dialogues` |
| shared VWF row renderer | `0x074560-0x07456C` | `$C7:4560-$456C` | 13-byte stock-font row load + framing + compositor helper installed byte-identically by `vwf_intro` / `vwf_dialogues` |
| shared VWF outline prep | `0x00163D` | `$C0:163D` | one-byte `ROL` -> `ASL` preparation installed byte-identically by `vwf_intro` / `vwf_dialogues` |
| dialogue DTE router | `0x074570-0x0745EE` | `$C7:4570-$45EE` | 127-byte context-sensitive `$E6/$E8` direct/DTE decision helper installed byte-identically by `vwf_dialogues` / `french_dialogues`; bank `$E4` Name Entry resource uses `$E8` |
| Name Entry DTE router | `0x0745F0-0x07462F` | `$C7:45F0-$462F` | 64-byte Name Entry / PLAYER_NAME helper region owned by `french_name_entry_extended` |
| shared VWF parser | `0x074AC0-0x074C01` | `$C7:4AC0-$4C01` | shared caller-gated buffer init / previous-char / capacity helpers (with gaps); capacity helper ends at `$4C01` |
| French intro | `0x074C40-0x074C6B` | `$C7:4C40-$4C6B` | intro-private DTE loader |
| French intro + intro VWF | `0x0A0002-0x0A001F` | `$C9:F802-$F81F` | byte-identical 15-pointer rewrite for relocated stock events `$0401-$040F` |
| French intro | `0x12DFF0-0x12E0C7` | `$D2:DFF0-$E0C7` | canonical `$D4-$E5` French glyph span |
| dialogue French glyphs | `0x12DFE4-0x12E0DF` | `$D2:DFE4-$E0DF` | `dialogue_french` `$D3-$E7` span installed byte-identically by dialogue/resource components where needed; contains the intro `$D4-$E5` subset |
| shared VWF/config | `0x074C80-0x074C86` | `$C7:4C80-$4C86` | intro marker/end (`05`), dialogue VWF marker (`06`), dialogue-DTE `$E8` marker, Name Entry base threshold (`02`) |
| shared VWF compositor | `0x074C90-0x074CCE` | `$C7:4C90-$4CCE` | byte-identical 8×12 shift/merge/spill helper installed by `vwf_intro` / `vwf_dialogues` |
| shared UI VWF config | `0x074C87` | `$C7:4C87` | `vwf_ui` marker `$09`; shared capacity/renderer infrastructure stays dormant without it |
| GAME FILE Mana VWF | `0x074C88-0x074C8E` | `$C7:4C88-$4C8E` | exact 7-byte trampoline: `JSL $ED:7F40 / JMP $C7:5464`; only the fourth GAME FILE generator pointer is redirected here |
| French intro | `0x074D00-0x074D31` | `$C7:4D00-$4D31` | 25-pair private DTE table |
| French intro | `0x0A0C02-0x0A0E8A` | `$CA:0C02-$0E8A` | rebuilt translated event `$0400` |
| French intro + intro VWF | `0x0AFF70-0x0AFFB7` | `$CA:FF70-$FFB7` | byte-identical relocation of unchanged stock events `$0401-$040F` |
| intro VWF | WRAM | `$7E:9380-$9389` | intro-only VWF scratch state |
| shared VWF parser | WRAM | `$7E:9390-$93BB` | 44-byte decoded-text private buffer shared by intro/dialogue modes |
| battle banner parser | WRAM | `$7E:9390-$93C0` | exact `$AC` battle mode extends the same private buffer by five mutually-exclusive scratch bytes, for 49 parser bytes total; `$93C1` remains UI tag |
| magic lower-panel VWF scratch | WRAM | `$7E:93C7-$93C9`, `$7E:93CE-$93CF`, `$7E:93F2-$93F5` | `vwf_ui` exact lower-panel path only: half flag / width temp, 16-bit 480px cursor, three captured stock IDs + capture count; lifetimes are mutually exclusive with Status/skill helpers |
| intro skip | `0x00012C-0x00012F` | `$C0:012C-$012F` | runtime-validated active-text observer hook to `$ED:7488` |
| intro skip | `0x0016EA-0x0016ED` | `$C0:16EA-$16ED` | runtime-validated live-parser commit hook to `$CA:FFC8` |
| intro skip | `0x02C786-0x02C789` | `$C2:C786-$C789` | runtime-validated normal-loop hold/WAIT hook to `$ED:7400` |
| intro skip | `0x0AFFC0-0x0AFFFF` | `$CA:FFC0-$FFFF` | private skip tail `$FFC0-$FFC7` + 55-byte parser helper `$FFC8-$FFFE`; `$FFFF` remains free |
| dialogue text relocation | `0x01E794-0x01E799` | `$C1:E794-$E799` | runtime-validated sparse-event resolver hook; installed only when relocation is used |
| dialogue text relocation | `0x280000-0x2817FF` | `$E8:0000-$17FF` | sparse 2048-entry 24-bit relocation table |
| dialogue text relocation | `0x281800-0x281FFF` | `$E8:1800-$1FFF` | reserved event-loader resolver helper; current helper is 83 bytes at `$E8:1800-$1852` |
| dialogue text relocation | `0x282000-0x2CFFFF` | `$E8:2000-$EC:FFFF` | reserved deterministic relocated-event pool |
| dialogue VWF | `0x2D7040-0x2D72EE` | `$ED:7040-$72EE` | caller gate, render/advance helpers, width table and runtime-validated Stage-3A bounded post-outline repair (fixed blocks with intentional gaps) |
| dialogue VWF | `0x2D7340-0x2D73AA` | `$ED:7340-$73AA` | physical-cell commit/snapshot helpers; runtime-validated Stage-3A guarantees `$938F` before outline while preserving the validated progression/continuation decisions |
| dialogue VWF | `0x2D73B0-0x2D73B8` | `$ED:73B0-$73B8` | runtime-validated renderer-active scope helper |
| intro skip / dialogue parser merge | `0x2D73C0-0x2D73CF` | `$ED:73C0-$73CF` | 16-byte aggregate dispatcher for shared `$C0:16EA`: parser mode 2 -> dialogue preflight `$ED:7500`, otherwise -> intro-skip parser helper `$CA:FFC8` |
| intro skip | `0x2D7400-0x2D74FF` | `$ED:7400-$74FF` | owned validated reserve: C2 helper `$7400-$7484`, gap `$7485-$7487`, C0 observer `$7488-$74F5`, gap `$74F6-$74FF` |
| dialogue VWF | `0x2D7500-0x2D77FF` | `$ED:7500-$77FF` | pixel-aware parser preflight, glyph-fit helper and framed-right-edge table; gaps reserved to `vwf_dialogues` |
| dialogue VWF | `0x2D7930-0x2D79F9` | `$ED:7930-$79F9` | exact interrupted same-line VWF continuation restore/capture helpers; deliberately placed after choice helpers and before shared dispatcher |
| dialogue_background (standalone v1) | `0x1FA908+` | `$DF:A908+` | ownership/lifecycle/HDMA helper payload; aggregate-disabled until this temporary allocation is formally reserved |
| dialogue_background (standalone v1) | WRAM | `$7E:93D0-$93F1` | cached ordinary/type-2 rectangles, active/owner state and WH0/WH1 HDMA table; **known overlap with `vwf_dialogues` `$93D0-$93DF` continuation state**, therefore not aggregate-safe |
| shared UI/dialogue dispatcher | `0x2D7A00-0x2D7A7F` | `$ED:7A00-$7A7F` | byte-identical renderer-entry dispatcher installed by `vwf_dialogues` / `vwf_ui` |
| shared VWF generic fast path | `0x2D7A80-0x2D7AFF` | `$ED:7A80-$7AFF` | Stage-2B runtime-validated character-phase/Y prep `$7A80-$7A9C` + Stage-2C-R1 runtime-validated safe packed/unrolled hot font-row compositor `$7AB0-$7AF2`; installed byte-identically by `vwf_dialogues` / `vwf_ui`; direct `$C7:4560/$4C90` callers remain unchanged |
| UI VWF renderer | `0x2D7B00-0x2D7CFF` | `$ED:7B00-$7CFF` | `vwf_ui` standalone non-dialogue UI renderer reserve (Forge backend first) |
| UI VWF metrics | `0x2D7D00-0x2D7D7F` | `$ED:7D00-$7D7F` | `vwf_ui` validated 128-entry advance table |
| UI VWF Forge wrapper | `0x2D7E00-0x2D7E7F` | `$ED:7E00-$7E7F` | exact Forge-row submit wrapper (`$00:19D0`) |
| UI VWF shop wrapper | `0x2D7E80-0x2D7EFF` | `$ED:7E80-$7EFF` | exact D9 shop/forge response submit wrapper |
| UI VWF battle wrappers | `0x2D7F00-0x2D7F3F` | `$ED:7F00-$7F3F` | two exact `$C0:637D/$637F` battle-banner submit wrappers; runtime-validated `$AC` path |


`french_dialogues` keeps in-place reinsertion for rebuilt events that still fit
their clean-USA span. Growth is now handled by a sparse 24-bit relocation table
and the reserved `$E8-$EC` pool above. Unrelocated IDs still read the live stock
pointer tables, preserving the `french_intro` / `vwf_intro` pair's ownership of `$0400-$040F`. The
relocation path is runtime-validated: unchanged event `$0107` executed from
`$E8:2000` with normal dynamic-name insertion, VWF rendering, line breaks and
WAIT behavior. The temporary force probe has been removed; normal builds
relocate only translated events that genuinely outgrow their clean-USA span.

`vwf_intro` / `vwf_dialogues` contain the minimal validated extension needed to accept
`$E8-$EC` under their existing structural event-parser / renderer caller gates.
Their validated `$C9/$CA` behavior is otherwise unchanged.

The GAME FILE relocation uses the stock-`$FF` gap after the French-intro DTE allocation and ends before the Name Entry layout at `C7:4E00`. GAME SELECT's relocated label block ends before the intro VWF width table. New allocations
must be checked against both the reserved ranges above and the actual IPS write
maps produced by all components.

`french_opening` keeps opening-font tile `$7A` as the stock `Z`. Startup-credit `É` is rendered as stock `E` plus acute tile `$7D` on the immediately preceding tile row. The wrapper lives in existing decompressed-title-code padding at CPU `$BCED`; the credit-only CGRAM HDMA tables are adjusted in place to cover both rows. This introduces no new ROM/WRAM allocation, and the prologue accent tiles `$7D-$7F` remain unchanged.

GAME FILE also keeps its translation-JSON-backed stock label fields synchronized in place at `C7:7340-C7:73BB`, because runtime validation showed that one menu path still reads them even after the two table pointers are redirected to `C7:4D40`. The four-cell stock FILE field contains the `Fich` prefix; the relocated resource contains full `Fichier`. Additional in-place edits at ROM `0x0753C9` / `$C7:53C9` and `0x075AF1` / `$C7:5AF1` change the dynamic level prefix from `L` to `N` (`$A6 -> $A8`), and ROM `0x077585` / `$C7:7585` changes the FILE-frame descriptor from `$03` (6 text cells) to `$04` (8 text cells). The runtime-validated money layout also uses the 10-byte helper at `$C7:4D32-$4D3B`; this is the only newly allocated GAME FILE code in that gap.

Window Settings is fixed-font-only. Its runtime-validated source resource lives at `$C7:4700-$472E`, with the ten-span placement list at `$C7:4730-$4759`. Descriptor text/placement pointers at `$C7:7828/$782C` are redirected to `$4700/$4730`, and `$C7:75CA` changes `$07->$09` so `Choix de fenêtre` fits in an 18-cell frame. The placement order is structural: horizontal `Fond` spans are emitted before vertical `Bordure` spans so the native source cursor ends at the title start. The help pointer `$C0:33BB` is redirected to `$ED:8600`. The earlier VWF experiment and unsynchronized frame/resource probes are rejected.

Action Settings keeps the stock left frame width `$18` and stock checkerboard/right-panel geometry. Its four translated fixed-font labels are repacked into the 34-cell resource at `$C7:4DC0`; the six-span placement list at `$C7:4DE3` reuses two 2-cell overlaps and moves `Défendre` one fixed-font cell (8 px) left. Three source-tile bases are adjusted in place, matching the official French Rev 1 ROM: `$C7:6C77` `$2180->$2184` for the right-hand gauge value, `$C7:6D57` `$2090->$2094` and `$C7:6D5C` `$2108->$210C` for the two top-help redraw paths. This screen deliberately remains fixed-font; the VWF experiment is rejected.

## french_gfx — shared controller-button localization

`french_gfx` uses only existing stock regions and reserves no free space. The
16×16 indexed PNG is converted at build time to four 8×8 2bpp tiles in stock
TL/TR/BL/BR order. The four palette ramps are exact French Rev 1 BGR15 data.
The only code edit skips the USA-only palette-collapsing subroutine call at
`$C0:2116`; no screen-specific renderer or WRAM state is added. The feature is
binary-validated, runtime-validated and promoted.

## vwf_dialogues — global allocation view

`vwf_intro`, `vwf_dialogues`, and `vwf_ui` install byte-identical shared parser/capacity hooks/helpers in
`$C0:16B8/$16C6/$17CE/$18DE` and `$C7:43D0/$4AC0+`. The helper classifies the
parser caller structurally (`$114B` event engine vs `$235B` GAME SELECT) and
uses `$7E:9390-$93BB` for private VWF decoding. Component-owned config bytes at
`$C7:4C80-$4C84` select intro mode 1 or dialogue mode 2.

`vwf_dialogues` uses renderer hooks in bank `$C0` and helper/table space in the
`$ED:7040-$73B8`, `$ED:7500-$792A` and `$ED:7930-$79F9` areas. Choice rows use the same renderer path as ordinary dialogue. `$9381` is parser-local historical scratch only; it is not a renderer/choice tag and the validated +1 px renderer inset is established directly at renderer entry unless exact continuation state overrides it. The measured-end two-option path additionally uses `$7E:93BC-$93C0` for private visual/highlight boundaries while leaving stock `$A1D7[]` logical and untouched. Core renderer scratch remains `$7E:9382-$938F`.
These bytes are used only for caller-tagged event-render
invocations in stock banks `$C9/$CA` and validated reserved banks `$E8-$EC`. `vwf_intro`
intercepts translated intro event `$0400` before `vwf_dialogues` reaches its entry
hook, so their overlapping WRAM scratch remains mutually exclusive.

The complete hook-by-hook allocation, fixed addresses and scratch ownership are
documented in `components/default_vwf_dialogues/docs/MEMORY_MAP.md`. This root map
intentionally avoids duplicating renderer status and calibration details.

`intro_skip` now runtime-validates `$7E:938A-$938B` as one 16-bit continuous-hold countdown (`$FFFF` inactive, `$0000` completed) during translated event `$0400`, and owns `$ED:7400-$74FF` for its two helpers. `vwf_intro` intercepts this event before ordinary `vwf_dialogues`, preserving the existing scratch-lifetime separation. See `docs/INTRO_SKIP_VALIDATION.md`.


## vwf_ui — non-dialogue UI VWF

`vwf_ui` reuses shared framing/compositor/stock-row helpers but owns its own
renderer. `$7E:93C1` is its only UI-private family tag: `$A7` identifies the Forge
row, `$A8` the top-level Ring Menu title row, `$A9` the exact D9 shop/forge
response family, `$AA` the buy/sell merchandise row, `$AB` the exact type-2
money window, `$AC` the exact battle/status banner, and `$AD` the exact GAME FILE
Mana label. The backend has no
additional `$93C3-$93C9` scratch. It reuses shared runtime scratch
`$7E:9382/$9385/$938E-$938F`. Ordinary UI families reuse `$7E:9390-$93BB` only
after stock parsing; battle `$AC` is the narrow exception and selects parser
mode 3, decoding directly into `$7E:9390-$93C0`.
Forge keeps its validated +3 logical margin and suffix compaction. Ring Menu mode 0
gets an exact +4 margin (33 stock units total) and renders the decoded title unchanged.
Fresh Ring `$A8`, Forge `$A7`, Shop `$A9` and merchandise `$AA` one-line rows start at
**+1 px** to preserve the first glyph's left outline; MONEY `$AB` keeps x=0.
GAME FILE `$AD` starts at **+9 px** inside a 16-cell upload: one blank 8-px cell
plus the same +1 px outline inset, preserving the stock pair-packed tile order.
The Shop `$A9` path is armed only at `$C0:7EA6/$7FB9` for pointers inside
`$D9:FE20-$FEF3`; it keeps the stock parser/capacity and applies VWF only after
parsing. Ring modes 1/2 arm dedicated merchandise tag `$AA`; that backend is
runtime-validated. Battle `$AC` is armed only by `$C0:5BEA/$5BF8`; the actual
message is copied to `$7E:FF69`, so parser mode 3 and renderer selector 5 both
operate with `$1D03=$7E`. The validated renderer fix is the one-byte continuity
check `$ED:7B83: C0 -> 7E`. GAME FILE `$AD` is armed only by the fourth
`$C7:5F8F` generator entry (`$5464 -> $4C88`), copies 15 source cells from
`$C7:73AA` to `$7E:9C00`, and uploads pair-aligned graphics to `$6820-$691F`;
the dynamic value begins at `$6920` and remains stock. Currency content is not rewritten by `vwf_ui`: standalone
renders the source `GP`, while `french_resources` supplies `PO`. `vwf_ui` owns
presentation only: merchandise price resync 168 -> 164 px plus a 4-px separator
before the final two unit glyphs; type-2 MONEY `$AB` gets a 3-px separator,
window width `$C7:714C` 9 -> 11 cells, and matching close X seed `$C7:7140`
`$0A -> $09` so the widened left frame cell is restored on close. The live money source buffer remains
`$A1E0-$A1E9`; `$A1EA` is not written. Shared renderer scratch `$9385` now uses
explicit identity `$01` for dialogue and `$02` for UI; the shared chunk commit
calls dialogue-only continuation `$ED:7990` only for `$01`, removing the former
standalone Sell-menu reset.

## french_resources — CA resources + D9 shop text + fixed literals

`french_resources` rewrites the canonical 513-entry `$CA` resource pointer table and the translated
reviewed payload (name families + nine Ring Menu titles) within the original stock allocation
beginning at `$CA:98E1`. It also owns the two reviewed shop currency literals
`$D0:D894` (`GP -> PO`) from
`translations/french_resources_reviewed_literals.json`. The current translated `$CA` blob is 7171 bytes versus the 7315-byte stock allocation;
weapon descriptions remain in place. Complete magic lower-panel rows use the separately
reserved expanded-bank table at `$ED:9200-$9F23` described above. Its French
glyph/DTE infrastructure is shared byte-identically with `vwf_dialogues` / `french_dialogues`.


### GAME FILE total-money layout

`french_menus` preserves the stock hybrid currency path but adds a runtime-validated
separator before the unit. The dynamic text renderer always uploads `$0200` bytes,
which is 16 fixed-font characters, so columns 0..15 are rewritten regardless of
the temporary string terminator. Column 16 remains the second glyph from the
`C7:7394` template.

Promoted writes:

- ROM `0x07549A-0x07549C` / `$C7:549A-$549C`: `LDY #$0008 -> #$0007`;
- ROM `0x0754A6-0x0754A8` / `$C7:54A6-$54A8`: `JSR $54B0 -> JSR $4D32`;
- ROM `0x074D32-0x074D3B` / `$C7:4D32-$4D3B`: helper `JSR $54B0; LDA #$80; STA $9C00,X; INX; RTS`;
- ROM `0x0754AA` / `$C7:54AA`: the first currency glyph remains derived from JSON translation ID `C7:7394` (`PO` -> `P`).

The resulting 16 dynamic cells are `7 blanks + 7 amount cells + separator + currency[0]`; static column 16 supplies `currency[1]`. Runtime validation confirms `1234567 PO` with the unit anchor unchanged. Earlier `PPO` / `P O` probes are rejected and absent from the baseline.


### Status / Characteristics exact-label VWF candidate

The stock fixed-font source remains intact as a standalone fallback, while the
aggregate `french_menus + vwf_ui` path may render only the ten characteristic
labels through an exact VWF backend:

- `$C7:7A28-$7A8D`: exact 60 + 40 cell fallback rows (`Intell.` / `% précis.`);
- `$C0:33D0-$33EF`: 16 condition pointers;
- `$C7:7A8E-$7B23`: repacked 150-byte condition pool (123 bytes currently used);
- `$C7:7B24-$7B69`: templates at their original starts;
- `$C7:7B6D-$7BA4`: weapon types at their original starts; current isolated candidate encodes `Épée` with direct `$E2` from `full_french`;
- `$C7:7BA5-$7BB4`: `Type` / `Sphères` in their original slots;
- `$ED:8B00-$8B9F`: ten 16-byte localization-owned VWF label records
  (length + up to 15 direct glyphs), including full `Intelligence` and
  `% précision`;
- `$ED:8BA0-$8BA1`: exact source marker `53 56` required by `vwf_ui`;
- `$ED:8700-$88FF`, `$ED:8900-$89BF`, `$ED:89C0-$8A3F`: exact Status
  converter/slot/copy helpers owned by `vwf_ui`;
- `$C0:2366-$2369`: converter trampoline to the exact-gated helper.

The full VWF forms `Intelligence`, `% précision` and `Déf. magique` are
runtime-validated. No dynamic values, bars, conditions or other menus are
routed through this backend. `$C7:7B6A-$7B6B` is owned by
`french_menus` for the native Status `GP -> PO`.

### Weapon / magic skill-row name VWF — runtime-validated

The fixed headings remain `Niv. armes` / `Niv. magies` and `$C7:754A/$7558`
remain byte-identical to the validated short-heading baseline. The promoted row
path changes only compact progress formatting and dynamic weapon/magic names:

- `$C7:664A-$664C`, `$C7:665D-$665F`: redirect the two row-specific progress
  conversions to `$C7:4F00`;
- `$C7:4F00-$4F22`: runtime-validated compact progress formatter; omit the
  stock leading blank for one-digit progress and append exactly one fixed blank
  before the name (`5:0 Nom`, `5:10 Nom`);
- `$C7:65B0-$65B2`, `$C7:6615-$6617`: runtime-validated magic/weapon 8-row
  submit redirects `JSR $5D9A -> JSR $4F30`;
- `$C7:4F30-$4F3F`: 16-byte wrapper scopes `$7E:93CD=$5A` around the complete
  synchronous stock `$C7:5D9A` render, then clears the scope;
- `$C0:2366-$2369`: route first through `$ED:8E00`; every non-magic exact-caller case immediately jumps to `$ED:8C00`;
- `$ED:8C00-$8DFF`: require the exact `$93CD=$5A` scope, then scan decoded
  `$7E:A1A4` dynamically (maximum 28 candidate cells) for `d:d ` / `d:dd `.
  The discovered name-start cell is used for both source offset and bitmap
  boundary; the fixed prefix is preserved and only the already-decoded dynamic
  name is VWF-rendered. Every reject jumps to the byte-identical validated
  Status helper `$ED:8700`.

Runtime probes proved that the compact prefix is **not anchored at cell 0**;
this was the root cause of the rejected predecessor. No menu-ID 5/6 gate is
needed in the promoted path. `french_resources` continues to own all localized
weapon and mana-spirit name content. See
`docs/WEAPON_MAGIC_SKILL_ROW_VWF_RESEARCH.md` for the proof sequence.
