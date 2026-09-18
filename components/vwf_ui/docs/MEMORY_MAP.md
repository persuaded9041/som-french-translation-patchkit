# `vwf_ui` memory map

`vwf_ui` is standalone. It installs the same low-level VWF infrastructure as
`vwf_intro` / `vwf_dialogues`, but owns only proven non-dialogue UI identities.

## Private / UI-owned ranges

| Range | Purpose |
|---|---|
| `$C7:4C87` | UI-VWF config marker `$09` |
| `$C7:4C88-$4C8E` | exact GAME FILE Mana trampoline `JSL $ED:7F40 / JMP $C7:5464`; reached only via generator pointer `$C7:5F95` |
| `$ED:7A00-$7A76` | shared UI/dialogue renderer dispatcher; recognizes Forge `$A7`, Ring `$A8`, D9 Shop `$A9`, merchandise `$AA`, type-2 money `$AB`, exact battle/status `$AC`, and exact GAME FILE Mana `$AD`; MONEY additionally requires exact event-engine caller return `$1152`; installed byte-identically by `vwf_dialogues` / `vwf_ui` |
| `$ED:7B00-$7C89` | current `vwf_ui` renderer; `$7B00-$7CFF` remains reserved for UI renderer growth |
| `$ED:7D00-$7D7F` | 128-byte validated VWF advance table |
| `$ED:7E00-$7E52` | exact shared `$00:19D0` Ring/Forge/shop-row submit wrapper; `$7E00-$7E7F` remains reserved |
| `$ED:7E80-$7EA4` | exact `$D9` shop/forge response submit wrapper; `$7E80-$7EFF` remains reserved |
| `$ED:7F00-$7F3F` | two exact battle/status submit wrappers for `$C0:637D={50}` / `$C0:637F={51}` |
| `$ED:7F40-$7FA4` | exact GAME FILE Mana pair-aligned submit wrapper; `$7F40-$7FFF` reserved for this backend/future exact UI helpers |
| `$7E:9390-$93C0` | battle parser mode 3 private decoded buffer, 49 bytes; the five bytes above the ordinary 44-byte span are borrowed only during `$AC` |
| `$7E:93C1` | UI family tag: `$A7` Forge, `$A8` top-level Ring Menu, `$A9` D9 shop/forge response, `$AA` merchandise row, `$AB` exact type-2 money window, `$AC` exact battle/status banner, `$AD` exact GAME FILE Mana label |

The renderer has **no additional private `$93C3-$93C9` state**. It reuses the
shared VWF runtime scratch (`$7E:9382`, `$9385`, `$938E-$938F`). Ring, Forge,
Shop, merchandise and MONEY reuse `$7E:9390-$93BB` only after stock parsing has
completed. Battle `$AC` is the narrow exception: shared parser mode 3 decodes
directly into `$7E:9390-$93C0` before rendering. The five extra bytes are
mutually exclusive with dialogue-choice scratch and `$93C1` remains the UI tag.

The component also installs the standard byte-identical shared VWF hooks/helpers
listed in root `docs/MEMORY_MAP.md`, including the renderer-entry dispatcher,
framing/compositor/row helpers, capacity helper, outline support and the
`dialogue_french` glyph span `$D2:DFE4-$E0DF`.

## Shared submit classification

| Condition at `$D0:D3D2` | Tag | Capacity | Renderer behavior |
|---|---:|---:|---|
| `$1847 == 0` | `$A8` Ring | stock remainder +4, max 33 stock units | copy continuous Ring title unchanged, then VWF |
| `$1847 == 1/2` | `$AA` merchandise | stock | copy stock row unchanged, then VWF only through the real decoded count (`$938E`); avoids synthetic-tail cursor wrap back onto bitmap cell 0 |
| `$1847 == 3` | `$A7` Forge | stock remainder +3 | validated suffix compaction, then VWF |
| other | none | stock | stock fallback |

The wrapper clears `$93C1` before classification, preventing stale one-shot state.
The Ring +4 budget exactly fills the stock 33-byte decoded buffer and does not
extend it.

## Forge-specific stock patches

| Range | Purpose |
|---|---|
| `$D0:D3D2-$D3D7` | replace `LDA #$0000 / JSR $D5D7` with the classifier/submit wrapper `JSL $ED:7E00 / NOP / NOP` |
| `$D0:D83A` | Forge arrow `TEXT_X`: logical slot 16 -> safe slot 20 |
| `$D0:D878` | Forge price `TEXT_X`: logical slot 21 -> safe slot 25 |

The arrow/price changes matter only when `$1847 == 3` selects the Forge backend. Ring
mode 0 never executes the suffix mover.

## Shop / Forge response classification

At stock submit sites `$C0:7EA6` and `$C0:7FB9`, the wrapper at `$ED:7E80`
checks the 16-bit D9 event pointer. Only `$FE20 <= X < $FEF4` arms Shop tag
`$A9`; any other pointer through those sites clears the tag and stays stock.
The renderer then additionally requires `$1D03 == $D9`.

The Shop backend uses the stock parser capacity unchanged and performs only the
post-parse stock-buffer -> private-render-buffer copy before VWF rendering. The
validated text-data contract therefore remains 28 visible characters maximum.


## Battle/status classification and WRAM continuity

The exact helpers `$C0:5BEA` / `$C0:5BF8` arm `$AC` while launching the tiny
`$C0:637D={50}` / `$C0:637F={51}` banner scripts. The prose itself is not read
from bank `$C0`: the battle engine copies the built message to `$7E:FF69`, sets
`$1D03=$7E`, then invokes the normal event parser. `$AC` therefore selects parser
mode 3 and fills `$7E:9390-$93C0` directly.

Renderer selector 5 must preserve that private buffer and require the live source
bank `$7E`. The former `$C0` comparison at `$ED:7B83` rejected the valid parse
and fell back to stock `$A1A4`, causing dynamic-subject messages to display only
the residual name. The production byte is `$7E`; this fix is runtime-validated
in standalone `vwf_ui` and combined `french_resources + vwf_ui`.

## GAME FILE Mana classification / pair alignment

- `$C7:5F95-$5F96`: fourth generator pointer `$5464 -> $4C88`.
- `$C7:4C88-$4C8E`: `JSL $ED:7F40 / JMP $C7:5464`.
- `$ED:7F40-$7FA4`: copy exactly 15 cells from `$C7:73AA` to `$7E:9C00`, terminate at `$9C0F`, prepare destination `$6820` / DMA `$0200`, arm `$AD`, and call the stock `$C0:2ADB/$2AEA/$2ADF` menu-text pipeline.
- Renderer selector 6 requires source bank `$7E`, exact caller return `$235E`, starts at pixel 9, and renders the true decoded count.
- `$6820-$691F` is the pair-aligned 16-cell label graphics span; `$6920` begins the stock dynamic Mana value and is never touched by this backend.

The first probe started at the odd cell 91 / `$6830` and is rejected because it split top/bottom tile halves and left a residual half-glyph.

## Currency / type-2 MONEY presentation

Currency bytes are not owned by `vwf_ui`. On a clean USA ROM the merchandise
price and total-money source strings end in `GP`; `french_resources` changes
those exact two-glyph literals to `PO` from
`translations/french_resources_reviewed_literals.json`.

`vwf_ui` owns geometry only:

- merchandise `$AA`: 164-px price resync plus a 4-px separator before the final
  two source glyphs; render-loop bound = actual decoded count, not all 38 private
  slots, so trailing `$80` padding cannot wrap the 8-bit pixel cursor to x=0 and
  erase the first item glyph;
- MONEY `$AB`: 3-px separator before the final two source glyphs, type-2
  window width `$C7:714C` 9 -> 11 cells, and independent close X seed
  `$C7:7140` `$0A -> $09` so the extra left cell is erased on close;
- no source/private-buffer glyph rewrite and no buffer growth.

## Shared low-level renderer identity

`$7E:9385` now distinguishes owners: `$01` dialogue, `$02` UI. Shared VWF
row/font/outline hooks accept exactly 1/2; intro values 3..8 are excluded. The
shared chunk-commit helper calls dialogue continuation `$ED:7990` only when the
identity is `$01`. This removes the former standalone Sell-menu reset where
`vwf_ui` jumped to an uninstalled dialogue-only helper.

