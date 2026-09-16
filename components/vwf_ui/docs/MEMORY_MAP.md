# `vwf_ui` memory map

`vwf_ui` is standalone. It installs the same low-level VWF infrastructure as
`vwf_intro` / `vwf_dialogues`, but owns only proven non-dialogue UI identities.

## Private / UI-owned ranges

| Range | Purpose |
|---|---|
| `$C7:4C87` | UI-VWF config marker `$09` |
| `$ED:7A00-$7A2F` | shared UI/dialogue renderer dispatcher; recognizes Forge `$A7` and Ring `$A8`; installed byte-identically by `vwf_dialogues` / `vwf_ui` |
| `$ED:7B00-$7BC8` | current `vwf_ui` renderer; `$7B00-$7CFF` remains reserved for UI renderer growth |
| `$ED:7D00-$7D7F` | 128-byte validated VWF advance table |
| `$ED:7E00-$7E42` | exact shared `$00:19D0` submit wrapper; `$7E00-$7E7F` remains reserved |
| `$7E:93C1` | one-shot UI family tag: `$A7` Forge, `$A8` top-level Ring Menu |

The renderer has **no additional private `$93C3-$93C9` state**. It reuses the
shared VWF runtime scratch (`$7E:9382`, `$9385`, `$938E-$938F`) and the shared
private render buffer `$7E:9390-$93BB` only after stock parsing has completed.
It does not enable the private parser mode used by `vwf_intro` / `vwf_dialogues`.

The component also installs the standard byte-identical shared VWF hooks/helpers
listed in root `docs/MEMORY_MAP.md`, including the renderer-entry dispatcher,
framing/compositor/row helpers, capacity helper, outline support and the
`dialogue_french` glyph span `$D2:DFE4-$E0DF`.

## Shared submit classification

| Condition at `$D0:D3D2` | Tag | Capacity | Renderer behavior |
|---|---:|---:|---|
| `$1847 == 0` | `$A8` Ring | stock remainder +4, max 33 stock units | copy continuous Ring title unchanged, then VWF |
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
