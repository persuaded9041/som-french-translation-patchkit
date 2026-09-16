# `vwf_ui` memory map

`vwf_ui` is standalone. It installs the same low-level VWF infrastructure as
`vwf_intro` / `vwf_dialogues`, but owns only proven non-dialogue UI identities.

## Private / UI-owned ranges

| Range | Purpose |
|---|---|
| `$C7:4C87` | UI-VWF config marker `$09` |
| `$ED:7A00-$7A6E` | shared UI/dialogue renderer dispatcher; recognizes Forge `$A7`, Ring `$A8`, D9 Shop `$A9`, merchandise `$AA`, and type-2 money `$AB`; MONEY additionally requires exact event-engine caller return `$1152`; installed byte-identically by `vwf_dialogues` / `vwf_ui` |
| `$ED:7B00-$7C5E` | current `vwf_ui` renderer; `$7B00-$7CFF` remains reserved for UI renderer growth |
| `$ED:7D00-$7D7F` | 128-byte validated VWF advance table |
| `$ED:7E00-$7E52` | exact shared `$00:19D0` Ring/Forge/shop-row submit wrapper; `$7E00-$7E7F` remains reserved |
| `$ED:7E80-$7EA4` | exact `$D9` shop/forge response submit wrapper; `$7E80-$7EFF` remains reserved |
| `$7E:93C1` | UI family tag: `$A7` Forge, `$A8` top-level Ring Menu, `$A9` D9 shop/forge response, `$AA` merchandise row, `$AB` exact type-2 money window |

The renderer has **no additional private `$93C3-$93C9` state**. It reuses the
shared VWF runtime scratch (`$7E:9382`, `$9385`, `$938E-$938F`) and the shared
private render buffer `$7E:9390-$93BB` only after stock parsing has completed.
This remains true for the Shop `$A9` path: it does not enable the private parser
mode used by `vwf_intro` / `vwf_dialogues`.

The component also installs the standard byte-identical shared VWF hooks/helpers
listed in root `docs/MEMORY_MAP.md`, including the renderer-entry dispatcher,
framing/compositor/row helpers, capacity helper, outline support and the
`dialogue_french` glyph span `$D2:DFE4-$E0DF`.

## Shared submit classification

| Condition at `$D0:D3D2` | Tag | Capacity | Renderer behavior |
|---|---:|---:|---|
| `$1847 == 0` | `$A8` Ring | stock remainder +4, max 33 stock units | copy continuous Ring title unchanged, then VWF |
| `$1847 == 1/2` | `$AA` merchandise | stock | copy stock row unchanged, then VWF; runtime-validated |
| `$1847 == 3` | `$A7` Forge | stock remainder +3 | validated suffix compaction, then VWF |
| `$1847 == 1/2` or other | none | stock | stock fallback |

The wrapper clears `$93C1` before classification, preventing stale one-shot state.
The Ring +4 budget exactly fills the stock 33-byte decoded buffer and does not
extend it.

## Forge-specific stock patches

| Range | Purpose |
|---|---|
| `$D0:D3D2-$D3D7` | replace `LDA #$0000 / JSR $D5D7` with the classifier/submit wrapper `JSL $ED:7E00 / NOP / NOP` |
| `$D0:D83A` | Forge arrow `TEXT_X`: logical slot 16 -> safe slot 20 |
| `$D0:D878` | Forge price `TEXT_X`: logical slot 21 -> safe slot 25 |

The arrow/price changes matter only when mode 3 selects the Forge backend. Ring
mode 0 never executes the suffix mover.

## Shop / Forge response classification

At stock submit sites `$C0:7EA6` and `$C0:7FB9`, the wrapper at `$ED:7E80`
checks the 16-bit D9 event pointer. Only `$FE20 <= X < $FEF4` arms Shop tag
`$A9`; any other pointer through those sites clears the tag and stays stock.
The renderer then additionally requires `$1D03 == $D9`.

The Shop backend uses the stock parser capacity unchanged and performs only the
post-parse stock-buffer -> private-render-buffer copy before VWF rendering. The
validated text-data contract therefore remains 28 visible characters maximum.

## Currency / type-2 MONEY presentation

Currency bytes are not owned by `vwf_ui`. On a clean USA ROM the merchandise
price and total-money source strings end in `GP`; `french_resources` changes
those exact two-glyph literals to `PO` from
`translations/french_resources_reviewed_literals.json`.

`vwf_ui` owns geometry only:

- merchandise `$AA`: 164-px price resync plus a 4-px separator before the final
  two source glyphs;
- MONEY `$AB`: 3-px separator before the final two source glyphs and type-2
  window width `$C7:714C` 9 -> 11 cells;
- no source/private-buffer glyph rewrite and no buffer growth.

## Shared low-level renderer identity

`$7E:9385` now distinguishes owners: `$01` dialogue, `$02` UI. Shared VWF
row/font/outline hooks accept exactly 1/2; intro values 3..8 are excluded. The
shared chunk-commit helper calls dialogue continuation `$ED:7990` only when the
identity is `$01`. This removes the former standalone Sell-menu reset where
`vwf_ui` jumped to an uninstalled dialogue-only helper.

