# vwf_ui — UI VWF

Standalone variable-width-font extensions for user-interface text paths that are
not owned by the intro or ordinary event dialogue. The component reuses the
shared VWF primitives but keeps each UI family behind an explicit one-shot
identity gate.

## Runtime-validated Forge backend

The Watts weapon-upgrade row remains the reference backend:

- `$D0:D3B0-$D3C4` builds the current `WEAPON_NAME` at `$7E:19D2-$19D3`;
- `$D0:D82F+` builds the `→ ... GP` suffix;
- the exact shared submit at `$D0:D3D2` reaches mini-event `$00:19D0`;
- when the Ring subsystem mode byte is `$1847 == 3`, the submit wrapper arms
  one-shot tag `$7E:93C1=$A7` (Forge);
- the stock parser/buffer stays in use and receives only the proven **+3**
  logical-unit margin;
- safe logical suffix anchors 20/25 are compacted at render time so the arrow
  follows the actual VWF width of the current weapon name.

This path was runtime-validated previously with long French weapon names, the
complete `GP` suffix, GAME SELECT fallback and ordinary Watts dialogue.

## Runtime-validated Ring Menu title backend

The top-level Ring Menu title banner shares the same `$00:19D0` submit but must
not use Forge suffix geometry. Runtime tracing established the chain:

`Ring Menu -> C0:6943 -> D0:D397 -> $00:19D0 -> stock parser -> C0:167D -> vwf_ui`

The former corruption of long labels was explained exactly: Forge's overlapping
slot-20..31 suffix move was being applied to a continuous Ring title. A space at
slot 20 propagated spaces and hid the final words; a non-space propagated that
glyph (`Choix des fenêtres deeeee...`).

The production isolation is now explicit at the shared submit site:

- `$1847 == 0` -> one-shot tag `$7E:93C1=$A8` (top-level Ring Menu title);
- `$1847 == 1/2` -> one-shot tag `$7E:93C1=$AA` (shop merchandise row);
- `$1847 == 3` -> one-shot tag `$7E:93C1=$A7` (Forge);
- any unexpected value -> no UI tag, stock fallback.

The Ring renderer copies the stock decoded row unchanged and enters the shared
VWF backend without any Forge compaction. Its capacity is raised by exactly
**+4** units. The stock fresh-line remainder is 29, so this yields exactly 33
units: the complete stock `$7E:A1A4-$A1C4` buffer, sufficient for **32 visible
characters plus the following control**. The buffer is not enlarged and the
private 38-character dialogue parser is not used.

This exact +4 case is required by `Niveaux des armes et de la magie` (32 visible
characters). The corruption fix, the dedicated Ring/Forge tag isolation and the final
+4 boundary restoring the last `e` are all runtime-validated. Shorter Ring labels
continue through the same narrow mode-0 gate.


## Runtime-validated Shop / Forge response backend

The nine `$D9:FE20-$FEF3` shop/forge response mini-events now have a third
strict UI identity, independent from Ring and Forge geometry. The two proven
stock submit sites `$C0:7EA6` and `$C0:7FB9` arm one-shot tag
`$7E:93C1=$A9` only when `X` points inside that exact D9 pool, then replay the
stock `$D9` event-engine submit. The renderer additionally requires the normal
event-engine caller and `$1D03 == $D9`.

This Shop path is intentionally **render-only VWF**:

- the stock event parser and stock `$7E:A1A4-$A1C4` decoded buffer remain in use;
- no private parser mode is enabled and no parser capacity is extended;
- the decoded row is copied to the shared private render buffer only after parsing;
- no Forge suffix compaction is applied;
- `french_shop_text` therefore keeps its validated maximum of 28 visible
  characters even though the final glyphs are rendered proportionally.

A later experiment that tried to exceed the stock parser capacity was rejected
after runtime failures (`'objet !` only for the long inventory message and an
empty sphere message). That experiment is fully reverted; do not reintroduce a
Shop private-parser mode without new evidence.


## Runtime-validated shop merchandise backend

The shop buy/sell merchandise row shares `$00:19D0` with Ring and Forge, but
`$1847 == 1/2` has its own one-shot identity `$AA`. Runtime validation on
`Noix magique ... 500 PO` proved that item names can use the same render-only
VWF without inheriting Forge suffix compaction. The stock parser and decoded
buffer remain unchanged.

Currency **content is source-owned**. `vwf_ui` never tests for `GP`, never
writes `PO`, and never changes the source string. On clean USA standalone it
therefore renders `GP`; with `french_resources` it renders `PO`. The component
owns only presentation geometry: the merchandise price resync is 164 px and a
4-pixel separator is inserted before the final two currency glyphs.

## Runtime-validated type-2 MONEY presentation

The total-money row is recognized structurally as bank `$7E`, window type 2,
and source pointer in `$A1E0-$A1EB`, then receives UI tag `$AB`. The live money
buffer remains stock-sized; `vwf_ui` does not rewrite any glyph. Its only
changes are VWF rendering, a 3-pixel separator before the final two currency
glyphs, and widening the type-2 window from 9 to 11 cells. The final 11-cell
geometry and 3-pixel separator are runtime-validated.

## Standalone dependency fix

The Sell-menu reset was traced to a real shared-runtime dependency. The shared
chunk-commit helper called the dialogue-only continuation helper at `$ED:7990`
for every active VWF render. `vwf_ui` standalone does not install `$ED:7990`, so
a merchandise/MONEY chunk that took the conversion path jumped into empty
expanded-ROM bytes and reset the game. Adding `vwf_dialogues` masked the bug by
providing that helper, exactly matching the runtime diagnostic.

The fix gives low-level renderer state explicit identities: `$9385=$01` for
`vwf_dialogues`, `$9385=$02` for `vwf_ui`; intro scratch values remain 3..8.
Shared row/font/outline hooks accept only identities 1/2, while the `$ED:7990`
continuation call is now restricted to identity 1. Thus `vwf_ui` remains truly
standalone without duplicating or depending on dialogue continuation code.

## State and fallbacks

The shared dispatcher at `$C0:167D` recognizes the explicit UI families Forge
`$A7`, Ring `$A8`, D9 Shop response `$A9`, shop merchandise `$AA`, and the
structurally identified type-2 money window `$AB` when the ROM config marker
`$C7:4C87=$09` is installed. The renderer consumes the tag immediately. All
unowned calls replay stock behavior and clear the shared low-level VWF-active
state so unrelated UI callers cannot inherit it.

`vwf_ui` owns no translated prose. Ring/item translations and the two shop
currency literals remain in `french_resources`; `vwf_ui` consumes only the
resulting source bytes and owns presentation geometry.

For the extension procedure and regression checklist, read `docs/UI_VWF.md`.

Build standalone:

```bash
python3 build.py "Secret of Mana (USA).sfc" vwf-ui
```
