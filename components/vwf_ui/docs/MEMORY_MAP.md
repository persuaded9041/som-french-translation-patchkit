# `vwf_ui` memory map

`vwf_ui` is standalone. It installs the same low-level VWF infrastructure as
`vwf_intro` / `vwf_dialogues`, but owns only the non-dialogue UI dispatcher state
and its Forge backend.

## Private / UI-owned ranges

| Range | Purpose |
|---|---|
| `$C7:4C87` | UI-VWF config marker `$09` |
| `$ED:7A00-$7A2B` | 44-byte shared UI/dialogue renderer dispatcher; installed byte-identically by `vwf_dialogues` / `vwf_ui` |
| `$ED:7B00-$7BAD` | current 174-byte `vwf_ui` renderer; `$7B00-$7CFF` remains reserved for UI renderer growth |
| `$ED:7D00-$7D7F` | 128-byte validated VWF advance table |
| `$ED:7E00-$7E26` | current 39-byte exact Forge-row submit wrapper; `$7E00-$7E7F` remains reserved |
| `$7E:93C1` | one-shot exact Forge-submit UI tag (`$A7`) |

The renderer has **no additional private `$93C3-$93C9` state**. It reuses the
shared VWF runtime scratch (`$7E:9382`, `$9385`, `$938E-$938F`) and the shared
private render buffer `$7E:9390-$93BB` only after stock parsing has completed.
It does not enable the private parser mode used by `vwf_intro` / `vwf_dialogues`.

The component also installs the standard byte-identical shared VWF hooks/helpers
listed in root `docs/MEMORY_MAP.md`, including the renderer-entry dispatcher hook,
framing/compositor/row helpers, capacity helpers, outline support and the
`dialogue_french` glyph span `$D2:DFE4-$E0DF`.

## Forge-specific stock patches

| Range | Purpose |
|---|---|
| `$D0:D3D2-$D3D7` | replace the exact `LDA #$0000 / JSR $D5D7` Forge-row submit with `JSL $ED:7E00 / NOP / NOP` |
| `$D0:D83A` | move arrow `TEXT_X` from logical slot 16 to safe slot 20 |
| `$D0:D878` | move price `TEXT_X` from logical slot 21 to safe slot 25 |

The submit wrapper arms the one-shot tag only for mini-event `$00:19D0`; the
earlier `WEAPON_NAME` writer is deliberately left stock. The shared capacity
helper adds +3 logical units only while both the ROM marker and exact tag are
active. At render time the suffix from logical slots 20..31 is compacted so the
arrow begins one decoded space after the actual VWF-rendered weapon-name end.
