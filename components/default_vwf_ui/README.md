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


## Validated one-line left inset

Fresh Ring `$A8`, Forge `$A7`, Shop `$A9` and merchandise `$AA` rows start at **x=1 px** instead of x=0. This preserves the first glyph's left black outline at the window edge. MONEY `$AB` deliberately remains at x=0 because its small centered window has separate validated geometry. Merchandise price placement is unchanged because its later `TEXT_X` command resynchronizes exactly to the 164-px price anchor.

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
- `french_resources` therefore keeps the D9 family's validated maximum of 28 visible
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

Merchandise `$AA` bounds its final VWF character loop to the stock parser's
actual decoded count (`$938E`) rather than consuming the synthetic `$80` tail
of the 38-byte private render buffer. This is deliberately merchandise-only.
For `Haubert magique` plus its five-digit price, the old padding pass advanced
the 8-bit pixel cursor through 252 px back to 0; the final aligned padding space
then wrote zero rows over bitmap cell 0 and erased the initial `H`. The bitmap
is already cleared before rendering, so skipping this artificial tail is
lossless and leaves Ring, Forge, D9 and MONEY behavior unchanged.

## Runtime-validated type-2 MONEY presentation

The total-money row is recognized structurally as bank `$7E`, window type 2,
and source pointer in `$A1E0-$A1EB`, then receives UI tag `$AB`. The live money
buffer remains stock-sized; `vwf_ui` does not rewrite any glyph. Its presentation
changes are VWF rendering, a 3-pixel separator before the final two currency
glyphs, and widening the type-2 window from 9 to 11 cells.

Opening and closing geometry are stored separately by the stock game. Width 11
opens one cell farther left than stock, so the independent type-2 close X seed at
`$C7:7140` is changed from `$0A` to `$09`. Without that matching close seed, the
new left frame column remained on screen after closing. The 11-cell width,
3-pixel separator, and `$09` close seed are all runtime-validated.

## Status / Characteristics exact-label backend

The Status characteristic panel has a separate, ultra-localized bitmap path.
The global hook at `$C0:2366` accepts only menu ID `$08`, source bank `$C7`, a
post-parse pointer inside the exact `$C7:7A28-$7A8E` characteristic resource,
the validated French blanking of the USA `ON` / `CE` suffixes, and the
`french_menus` source marker `$ED:8BA0-$8BA1 = 53 56`. Every other call replays
the overwritten stock prologue and resumes the untouched converter.

`vwf_ui` owns no Status prose. `french_menus` owns ten 16-byte direct-glyph
records at `$ED:8B00-$8B9F`; the exact renderer reads the record length and
composites only that label into the stock 32-cell chunk. Values, red bars,
condition strings, templates and every other menu text remain on their stock
paths. The full forms `Intelligence`, `% précision` and `Déf. magique` are
runtime-validated. The backend remains limited to these ten labels.

## Runtime-validated weapon / magic skill-row name VWF

The weapon/magic level lists keep their validated fixed headings `Niv. armes`
and `Niv. magies`, with stock placement geometry at `$C7:754A/$7558`. The
compact progress presentation remains runtime-validated: the two row-only
formatter calls at `$C7:664A` / `$C7:665D` go through `$C7:4F00-$4F22`, so
one-digit values omit the stock leading blank and exactly one fixed separator
blank is appended before the dynamic name. Validated forms include `5:0 Nom`
and `5:10 Nom`.

The final name-only VWF architecture is runtime-validated. The two exact 8-row
submits at `$C7:65B0` / `$C7:6615` pass through `$C7:4F30`, which scopes
`$7E:93CD=$5A` around the synchronous stock `$C7:5D9A` render and clears the
scope immediately on return. The global `$C0:2366` hook now reaches the
magic lower-panel dispatcher `$ED:8E00` first; every non-magic caller jumps
immediately to `$ED:8C00`, which requires that exact skill scope and then dynamically scans the decoded `$7E:A1A4` row for the compact
`digit : digit [digit] blank` prefix. The prefix is deliberately **not** assumed
to begin at decoded cell 0.

On a match, the discovered cell is the true name boundary in both the decoded
row and `$7E:9000` bitmap. The fixed numeric prefix is preserved, only the old
fixed-font name cells are cleared, and the already-decoded weapon/magic name is
re-rendered using the ordinary validated UI VWF metrics before returning to the
stock 4bpp packer. Every non-match jumps directly into the unchanged Status
classifier at `$ED:8700`. No menu-ID 5/6 gate is required; the exact synchronous
batch scope plus the dynamically discovered row prefix is the validated identity.

The failed predecessor assumed the prefix began at `$A1A4+0`, which explains why
the names remained fixed. The proof sequence and root cause are documented in
`docs/WEAPON_MAGIC_SKILL_ROW_VWF_RESEARCH.md`. `vwf_ui` owns no weapon/magic
name prose: `french_resources` remains the source of localized weapon and
mana-spirit names.

## Runtime-validated magic lower-panel performance

Performance work is tracked separately in `docs/MAGIC_PANEL_PERFORMANCE_RESEARCH.md`.
Magic Stage 2 is promoted: each complete 480px row is rasterized and converted
once on the left pass; the paired right pass reuses the already-packed 960-byte
right half from `$7E:97C0-$9B7F`. The six stock DMA submissions, captured IDs,
unlock gating and localized content are unchanged. Magic Stage 1 is superseded.

## Runtime-validated magic lower-panel full-row VWF

The three spell-description rows in `Niv. magies` use a separate exact path from
the 8-row skill-name grid above. Stock physically submits **six** 30-cell halves,
arranged as three visible rows × two side-by-side passes. Runtime probes proved
one pass is 30 cells / 240 px (`$A191=$03C0`), so a pair is one 60-cell / 480 px
logical row.

The promoted architecture keeps the complete stock menu lifecycle:

- `$C7:649E` is wrapped only to invalidate three private captured IDs, then calls
  stock `$C7:6BCF`;
- `$C7:6501` captures the exact `$A1D0` description ID stock just emitted, then
  calls stock `$C7:6AB7`;
- Lumina's raw stock IDs 42..47 are remapped exactly as stock does to 36..41;
- `$C7:650E` calls a clone at `$C7:4F40` which preserves stock `$C7:6512` / six-pass
  `$C7:5D9A` wait/DMA/tail behavior;
- `$C0:2366` reaches `$ED:8E00`, which accepts only the exact stacked return from
  that clone. This exact-caller gate is runtime-validated to leave GAME SELECT
  normal;
- one complete row is VWF-rasterized across up to 60 cells in `$7E:9000-$92FF`,
  then cells 0..29 and 30..59 are supplied to the two stock passes;
- stock availability remains authoritative. IDs not emitted by stock remain
  `$FF`, so locked elementals stay blank and Dryad's unavailable third spell
  produces an explicit blank row instead of stale bitmap duplication.

Localized content remains source-owned. `french_resources` installs 42 fixed
80-byte `Nom : description` records at `$ED:9200-$9F1F` plus marker `MFV1` at
`$ED:9F20`. `vwf_ui` checks that marker at runtime; without it, the exact magic
caller falls back to the stock converter, keeping standalone `vwf_ui`
content-neutral.

The complete Android-FR wording is retained. The widest current row is 445 px;
`french_resources` enforces a 472 px build-time ceiling inside the 480 px logical
row. The probe history and rejected direct-DMA / weak-gate experiments are
recorded in `docs/WEAPON_MAGIC_DESCRIPTIONS_RESEARCH.md`.

Performance work is documented separately in
`docs/MAGIC_PANEL_PERFORMANCE_RESEARCH.md`. Magic Stage 2 is runtime-validated
and promoted. It keeps the six stock DMA submissions but reuses the left pass's
non-DMA packed output `$7E:97C0-$9B7F` for the paired right pass, removing the
duplicate VWF raster and duplicate `$C0:2366` conversion for valid rows.

## Runtime-validated battle/status banner backend

The stock battle/status banner is submitted only through two tiny helpers at
`$C0:5BEA` and `$C0:5BF8`, which launch event scripts `$C0:637D={50}` and
`$C0:637F={51}`. `vwf_ui` patches only those two exact submits and arms the new
one-shot tag `$7E:93C1=$AC`; it does not enable a generic battle or bank-C0 VWF path.

Unlike the other UI families, translated battle strings can exceed the 33-byte
stock parser buffer. The shared parser therefore has a battle-only mode 3 that
uses `$7E:9390-$93C0` (49 bytes: 48 visible decoded bytes plus the following
control). Ring/Forge/D9/merchandise/MONEY retain their previous parser behavior.
At render time selector 5 preserves that already-decoded private buffer and uses
its true decoded count. `french_resources` owns all battle text and relocation;
`vwf_ui` contains no localized prose.

The actual message is copied by the battle engine to `$7E:FF69`, so parser mode
3 runs with `$1D03=$7E`. The original candidate renderer incorrectly required
`$1D03=$C0`; it therefore rejected the private parse and fell back to stock
`$A1A4`, producing name-only remnants such as `IDGET` and `LINA`. The validated
fix changes only the battle selector continuity check to `$1D03=$7E`
(`$ED:7B83`, immediate byte `$C0 -> $7E`). Both standalone `vwf_ui` and the
combined `french_resources + vwf_ui` path are runtime-validated.

## Runtime-validated GAME FILE Mana backend

The GAME FILE Mana label is an exact, non-generic backend with one-shot tag `$AD`. The fourth generator entry at `$C7:5F95` is redirected from stock `$5464` to a 7-byte trampoline at `$C7:4C88`; it calls the private wrapper `$ED:7F40-$7FA4` and then jumps back to the stock generator.

The wrapper copies exactly 15 source cells from `$C7:73AA` into the stock menu scratch buffer, so `vwf_ui` owns no localized text. With `french_menus` the JSON-backed field is `Graines de Mana`. Because this field starts on the odd half of stock graphics pair 90/91, the validated renderer begins the DMA one cell earlier at `$6820`, leaves that first cell blank, starts the VWF cursor at 9 px, and uploads the pair-aligned 16-cell span through `$691F`. The dynamic Mana value begins at `$6920` and remains stock.

The first misaligned probe that started on cell 91 is explicitly rejected: it produced swapped top/bottom half-tiles and a residual half-`G`. No other GAME FILE row is routed through VWF.

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
`$A7`, Ring `$A8`, D9 Shop response `$A9`, shop merchandise `$AA`, the
structurally identified type-2 money window `$AB`, exact battle banner `$AC`, and
exact GAME FILE Mana label `$AD` when the ROM config marker
`$C7:4C87=$09` is installed. The renderer consumes the tag immediately. All
unowned calls replay stock behavior and clear the shared low-level VWF-active
state so unrelated UI callers cannot inherit it.

`vwf_ui` owns no translated prose. Ring/item translations and the two shop
currency literals remain in `french_resources`; the GAME FILE Mana source field
remains in `french_menus`. `vwf_ui` consumes only the resulting source bytes and
owns presentation geometry/routing.

For the extension procedure and regression checklist, read `docs/UI_VWF.md`.

Build standalone:

```bash
python3 build.py "Secret of Mana (USA).sfc" vwf-ui
```
