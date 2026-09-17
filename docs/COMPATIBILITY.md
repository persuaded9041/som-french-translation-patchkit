# Compatibility audit

All selected components are rebuilt from the same clean USA ROM before an
aggregate build. Their IPS write maps are then compared byte-for-byte.

## Shared French glyph writes

`french_menus` installs the naming-safe `$D4-$E0` subset. `french_name_entry_extended`
installs that same French subset plus the disjoint shared glyphs `$D3=♪`,
`$E6=°` and `$E7=;`, while deliberately leaving `$E1-$E5` untouched because
Name Entry uses those slots for graphics. `name_entry_extended` itself owns no
French glyph data. `french_intro` installs the
unchanged French `$D4-$E5` range. `vwf_dialogues` / `french_dialogues` use the full extended
dialogue span `$D3-$E7`. Identical overlapping glyph bytes all come from
`shared/charset/french_glyphs.png`.

## Direct-glyph / DTE routing

`french_menus` retains its historical standalone immediate `$E1` threshold and
`french_intro` keeps `$C0:16F6 = $E6` standalone; `vwf_intro` no longer writes the DTE threshold.

`french_name_entry_extended` uses the small `shared/name_entry/dte.py` router when layered on
`name_entry_extended`. Ordinary event sources still use `$E1`; the relocated Name Entry resource in bank `$E4`
and the stock `PLAYER_NAME` scratch stream at `$7E:A22F` use `$E8`, allowing
`$E6/$E7` on the character grid and inside a selected name without reinterpreting
normal DTE bytes. This route is runtime-validated. If the French Name Entry overlay is combined with a later legacy charset
component but without `vwf_dialogues` / `french_dialogues`, the root combiner stores the historical max
threshold in the router's `$C7:4C86` base-config byte and restores its JML after
all standalone patches have been applied.

`vwf_dialogues` / `french_dialogues` replace the same stock four-byte decision at
`$C0:16F5-$16F8` with the later, byte-identical full context router from
`shared/dialogue/dte.py`:

- non-dialogue parser callers: `$E6`;
- event `$0400`: `$E6`;
- ordinary event-engine dialogue when the dialogue profile is enabled: `$E8`;
- `name_entry_extended` resource in bank `$E4` when the French overlay is present: `$E8`.

The event-engine caller is identified by the established `$114B` stacked return
address, so GAME SELECT does not enter the dialogue `$E8` path. Event `$0400`
uses `vwf_intro`'s configured intro runtime end when present and the clean-USA
`$0E44` end otherwise. Thus `$E6/$E7` can be direct dialogue glyphs without
changing the intro's 25 private DTE pairs.

In aggregate builds containing `vwf_dialogues` / `french_dialogues`, their full router supersedes both the
legacy immediate-threshold byte and `french_name_entry_extended`'s smaller name-only hook.
Without `vwf_dialogues` / `french_dialogues`, `french_name_entry_extended`'s router preserves the historical max-threshold
merge through its base-config byte. Without any router, the original immediate
max-threshold merge remains unchanged.


## Dependent Name Entry overlays

`name_entry_extended` is the generic base and owns the 9-character engine,
exactly three rows (uppercase/lowercase/symbols), three-row navigation/layout using the physical selector states `$60/$70/$80`,
and the relocated `$E4:4000` resource. Its stock English help is extracted
directly from the clean USA ROM at build time. `french_name_entry_extended` and
`name_entry_prefill` both declare `requires: ["name_entry_extended"]`. The root
builder expands selected dependencies automatically and verifies that every
dependency has an earlier `build_order`.

`french_name_entry_extended` intentionally overrides the generic navigation, initial selector (`$C7:5019=$50`) and
private layout to expose a fourth row, and owns the `$E4:40B4-$41FF` tail (the point
where generic English help begins). Its fourth row + localized help currently
extend through `$E4:4188`, beyond the generic payload end at `$E4:415C`; the
remaining reserved tail is zero in the builder image and need not be encoded in
the standalone IPS. Differing overlaps are explicitly declared in the component
manifest and are accepted only for that dependency/range; undeclared differing
overlaps remain fatal. The combined generic+French bytes reproduce the former
runtime-validated four-row French Name Entry exactly after checksum
recomputation.

`french_name_entry_prefill` is a second-level dependent overlay. It requires both
`name_entry_prefill` and `french_name_entry_extended`, so selecting it also
selects the generic Name Entry base transitively. It intentionally overrides
`$C7:4630-$46A0` of the generic prefill helper and the records at
`$C7:46D0-$46E7`; its 130-byte helper continues through `$C7:46B1` in otherwise
unused clean-ROM space and adds token class `$C0-$DF` for the fourth row. The
records come from its own French JSON (`Randy`, `Prim`, `Popoï`). It does not
own the hook or the fourth-row glyph/layout resource and allocates no private
WRAM.
The complete dependency-composed Name Entry stack is runtime-validated, including
a first-screen diagnostic that exercised `Popoï` immediately and confirmed the
real fourth-row `ï` insertion path. The diagnostic is not part of canonical data.

## Opening-font local glyph

`french_opening` keeps tile `$7A` of its title-screen font as the stock `Z`. The final startup-credit `É` is rendered as stock `E` plus acute tile `$7D` on the row above. Its fade synchronization is local to the opening arrangement's existing credit-only CGRAM HDMA tables (`15/8` -> validated `7/16` scanline split), so it consumes no shared French charset code and introduces no new ROM/WRAM allocation or cross-component merge rule.

The relocated opening arrangement lives entirely in bank `$EE` and keeps the stock `$C1:0014` resource-loader/decompressor path. This is deliberate compatibility with `mana_tree_original`, whose runtime resource hook owns extended-bank `$EF` resources. The combined architecture was runtime-validated.

## Allocations

The principal ROM/WRAM allocations are documented in `docs/MEMORY_MAP.md` and
in each component's technical documentation. New code/data must be placed only
after checking those ranges against all existing components.

## dialogue_background standalone status

`dialogue_background` is a promoted runtime-validated standalone component, but its manifest deliberately sets `aggregate_enabled: false`. The root builder therefore allows targeted reconstruction while excluding it from `all` / `--combine`.

The v1 bytes intentionally preserve the validated Stage-11 test candidate. That means its temporary `$7E:93D0-$93F1` state overlaps `vwf_dialogues` interrupted-continuation state at `$7E:93D0-$93DF`, and HDMA channel 6 / color-window ownership has not yet been composed with map effects. Do not combine `dialogue_background` with the aggregate until those two integration problems have been resolved and runtime-tested.


## Intro payload / VWF split

`french_intro` and `vwf_intro` are separate owners. `french_intro` owns the translated event `$0400`, French glyph/DTE profile and private intro DTE loader/table. `vwf_intro` owns only the VWF renderer/parser runtime. Both independently relocate stock events `$0401-$040F` to `$CA:FF70-$FFB7`; those pointer/data writes are byte-identical and therefore need no special merge rule.

The validated VWF runtime window remains `$CA:0C02-$0E8A` (exclusive end `$0E8B`). `french_intro` rejects any generated payload whose endpoint differs from `$0E8B`, preventing translation/layout changes from silently widening or shrinking the runtime gate. `vwf_intro` computes its width table against a virtual font containing the canonical French glyph atlas, but does not install those glyph bytes itself.

After checksum recomputation, applying `french_intro` and `vwf_intro` together reproduces the former hybrid Round-76 `vwf_intro` patch byte-for-byte.

## Intro skip compatibility / validated status

`intro_skip` is now the runtime-validated 120-tick continuous-R hold skip for
translated event `$0400`. It explicitly requires `french_intro` and `vwf_intro`,
matching the configuration used during the proof ladder.

The promoted implementation uses three hooks and no NMI interception:

- `$C0:012C -> $ED:7488` while text is active;
- standalone `$C0:16EA -> $CA:FFC8` to consume a completed request from the live parser;
- `$C2:C786 -> $ED:7400` for normal-loop hold/decrement logic and safe timed-WAIT commit.

`vwf_dialogues` independently uses `$C0:16EA` for parser mode 2. The aggregate
compatibility layer therefore resolves that one shared hook to `$ED:73C0`: mode 2
JMLs to the unchanged dialogue helper `$ED:7500`, while every other mode JMLs to
`$CA:FFC8`. The standalone patches retain their own direct hooks; the dispatcher
is activated only after aggregate composition.

R is read from synchronized pad state `$7E:0042` bit `$10`. `$7E:938A-$938B`
is one 16-bit state/countdown (`$FFFF` inactive, `$0000` completed). Release before
zero resets the full duration, so separated presses cannot accumulate. The private
tail `$CA:FFC0-$FFC7` closes text, resets to waterfall room `$0000`, balances
`$CFF8`, and jumps to stock `$0106`.

The validated runtime window ends before `$CA:0E82 = 1D 7F`; the final Mode-7 /
flyover engine is deliberately outside scope. The C1 timed-WAIT handler remains
untouched.

The final helpers are kept inside the owned `$ED:7400-$74FF` reserve with explicit
builder size guards so intro-skip code cannot overflow into shared VWF code at
`$C7:43D0-$43E7`. See `docs/INTRO_SKIP_VALIDATION.md`.


## Header/checksum writes

Standalone builders may write ROM-size/header metadata and their own SNES
checksum. Checksum-byte overlaps are build metadata, not functional collisions.
The aggregate builder recomputes one checksum after all selected components and
merge rules have been applied.

## Policy

- byte-identical functional overlap required for standalone operation: allowed;
- checksum overlap: allowed and recomputed;
- legacy threshold-byte overlap with the context-sensitive dialogue router: allowed and resolved;
- `$C0:16EA` `vwf_dialogues` / `intro_skip` parser-fetch overlap: allowed only through the explicit `$ED:73C0` aggregate dispatcher merge rule;
- any other differing functional overlap: build failure.

The normal maintenance target is the modified component by itself plus the full
all-components build. Partial combinations are only tested when a specific
compatibility concern justifies them.

## Shared VWF parser buffer bridge

Components `vwf_intro` and `vwf_dialogues` independently install the
same parser hooks and helper bytes generated by `shared/vwf/text_buffer.py`. These
functional overlaps are therefore byte-identical and pass the normal overlap
audit without a special merge rule.

The stock `$C0:16B8` parser initializer is shared by the event engine and GAME
SELECT. The bridge reads the untouched stacked return address and activates only
for `$114B` (event-engine call from `$C0:1149`); GAME SELECT's `$235B` call
remains stock. The private buffer is `$7E:9390-$93BB`; the stock `$A1A4` buffer
is not extended because `$A1C5-$A1C7` are live engine state. `vwf_intro` owns
its intro marker/end bytes at `$C7:4C80-$4C82`; `vwf_dialogues` owns marker `$06` at
`$C7:4C84`.

## Shared VWF row compositor

Components `vwf_intro` and `vwf_dialogues` independently install the
same 63-byte renderer-neutral compositor generated by `shared/vwf/compositor.py`
at `$C7:4C90-$4CCE`. The overlap is byte-identical and requires no special merge
rule.

Both components derive glyph rows from the stock `$D2:DC00` font and install the
same framing selector bundle at `$C7:44C0-$4557`. They also install the same runtime-validated 13-byte `$C7:4560-$456C` helper,
which performs stock row load -> framing -> shared compositor. `vwf_dialogues` reaches it
only after its caller-gated renderer-scope check; non-event callers replay the
stock row load. Parser/event scope remains separate from this primitive.

## Shared VWF outline preparation

Components `vwf_intro` and `vwf_dialogues` both install the same
one-byte stock-outline preparation from `shared/vwf/outline.py`: `$C0:163D` is
changed from `ROL` to `ASL`, preventing carry from one source row from being
injected into the next. The overlap is byte-identical, so both standalone and
aggregate builds use the same preparation.

## Dialogue VWF compatibility

`vwf_dialogues` independently installs the `dialogue_french` `$D3-$E7`
span and the context-sensitive DTE router, so its standalone IPS does not depend
on `french_intro`. The shared `$D4-$E5` glyph bytes remain byte-identical.

`vwf_dialogues` enables its core VWF only when the shared `$C0:1664` renderer was
called by the event engine at `$C0:1150` and the live event bank is `$C9` or
`$CA`. This caller-based gate is runtime-validated and is required because GAME
SELECT also calls `$C0:1664`; bank/state checks alone are not safe discriminators.

`french_intro` owns the translated payload of event `$0400`; `vwf_intro` owns its VWF runtime path and intercepts that event
at `$C0:1664` and exits before `vwf_dialogues` reaches `$C0:167D`. This keeps the
shared `$7E:9380+` scratch mutually exclusive even though `vwf_dialogues` now also
handles ordinary `$CA` event dialogue. The validated `intro_skip` `$938A-$938B` countdown remains structurally separated by the same early interception and is used only during translated `$0400`.

Renderer architecture, metrics, caller discrimination and generic event-
interruption handling belong to `components/vwf_dialogues/docs/`, not to this
cross-component compatibility document.

## Dialogue text compatibility

`french_dialogues` remains the owner of event-script source/reinsertion data, not of the
VWF renderer itself. The first edited-event checkpoint (`$0107`) was
runtime-validated with the existing dialogue VWF, including dynamic player-name
insertion, line breaks and WAIT sequencing. The canonical clean-USA dialogue extraction (`assets/dialogues.json` when materialized) contains clean-USA source only.
The runtime-validated pagination baseline includes `$010F`: dynamic-name lines
reserve one parser safety unit, and its four safe lines use a sentence-aware
3+1 split with generated `WAIT $00` + `TEXT_CLEAR`. The current simulator-filtered
mass pass contains **608 simulator-clean events / 1516 visible semantic source
IDs / 1596 JSON entries**: **584 complete + 24 PARTIEL**. It resimulates with 0 errors,
0 warnings and 0 implicit wraps. Generic structural and Round-33 direct-simulator safe-subset
PARTIEL events preserve deferred mapped carriers byte-for-byte in stock English under strict
direct-simulation gates; neither fallback changes identity or stock commands. Accepted mappings may render in French while unresolved reviewed holes remain stock
English in PARTIEL events; `$0278` additionally remains PARTIEL because its two SNES-only
controller carriers are user-validated absent from Android and are staged in
`translations/dialogues_manual_supplements.json`; its current carriers are all resolved (15 translations + 2 validated suppressions). `$00DF` is complete through the runtime-validated minimal
later-choice anchor shift. `$0103`, `$017F` and `$01DC` are separately user-validated as
visually complete Android adaptations and no longer carry a PARTIEL badge. `$0602` is also
badge-free after runtime review found no visible missing/English content; unresolved `CA:85DD`
remains tracked without altering the event bytes. `$01DC` has one
explicit structural exception: its final stock `PLAYER_NAME(0)` is omitted together with
Android-absent `C9:804A`. The shared inn prompt is complete through a parameterized Android
ID 110 template while the stock numeric price carriers remain dynamic.
Interactive choice rows use `vwf_dialogues`'s ordinary VWF path with stock `CHOICE_OPTION`
/ `$A1D7[]` selection geometry untouched. Resynchronizing VWF option starts to those stock
boundaries is runtime-validated on `$0331`; the current follow-up additionally uses the
existing terminal boundary to keep a preserved closing parenthesis outside the final
magenta span. The full mass corpus still requires the planned playthrough.

Growth has a runtime-validated relocation path. `french_dialogues` can install a sparse
24-bit event-address table and dispatcher hook, then pack only overlong rebuilt
events into reserved banks `$E8-$EC`. A zero sparse-table entry falls back to
the *live* stock `$C9/$CA` tables, so `vwf_intro` remains authoritative for its
validated `$0400-$040F` pointer rewrites. Event `$0400` is still excluded from
the `french_dialogues` asset.

Relocated dialogue must keep the same VWF/parser behavior. `vwf_intro` and `vwf_dialogues`
therefore share one minimal bank-gate extension: their existing caller-gated
private parser path and `vwf_dialogues` renderer path continue to accept stock
`$C9/$CA`, and additionally accept only `french_dialogues`'s reserved `$E8-$EC` range.
The `$C9/$CA` behavior is unchanged. The `$E8-$EC` path was runtime-validated
with unchanged event `$0107` executing from `$E8:2000`, including dynamic name
insertion, VWF rendering, line breaks and WAIT behavior. The temporary force
probe has now been removed: normal builds relocate only events that genuinely
outgrow their source span.

When translated dialogue is present, `french_dialogues` installs the same
`dialogue_french` `$D3-$E7` glyph span and context-sensitive router as component
06; `vwf_intro` remains on its separate `$D4-$E5` / `$E6` intro profile. The root extractor continues to structurally parse all 2048 stock event scripts
and commits the 713 text-bearing events excluding `$0400`. The 513 following
`$CA` non-event resources are now extracted separately to
`assets/text_resources.json` and are not owned by the dialogue VWF runtime.

## vwf_ui — standalone non-dialogue UI VWF

`vwf_ui` is intentionally independent of `vwf_dialogues`. Both components
install the same shared renderer-entry dispatcher at `$C0:167D` / `$ED:7A00`;
the overlap is byte-identical. The dispatcher selects `vwf_ui` only when its
ROM config marker `$C7:4C87=$09` and exact one-shot UI tag are both present.
Otherwise it delegates to `vwf_dialogues` when `$C7:4C84=$06`, or replays the stock
32-cell renderer entry when neither owner is active.
 For the structurally detected type-2 MONEY family, `$AB` is synthesized only
after also proving the exact event-engine renderer return address `$1152`; this
keeps non-event users of the same `$A1E0-$A1EB` WRAM span out of the UI backend
and prevents recursive reclassification after a renderer rejection.

The shared text-buffer capacity helper is likewise installed byte-identically by
`vwf_intro` / `vwf_dialogues` / `vwf_ui`. Existing Ring/Forge/D9/merchandise/MONEY UI paths do not enter private parser mode. The exact battle-banner `$AC` path is the sole UI exception: parser mode 3 uses a 49-byte private span for those two proven submits only.
At the exact shared `$00:19D0` submit, mode `$1847==3` arms the Forge one-shot tag
(+3 logical units), mode `$1847==0` arms the distinct top-level Ring Menu tag
(+4 logical units = the full 33-byte stock buffer, allowing 32 visible characters
plus the following control), and modes `$1847==1/2` arm the merchandise-row tag
`$AA` while retaining stock parser capacity. Unexpected values arm no UI tag.
Separately, the exact D9 shop submit sites `$C0:7EA6/$7FB9` arm Shop tag `$A9`
only for pointers inside `$D9:FE20-$FEF3`; that path keeps stock parser capacity.
The exact battle helpers `$C0:5BEA/$5BF8` arm `$AC` only for event scripts
`$C0:637D/$637F`. The battle engine then copies the actual message to `$7E:FF69`;
battle-only parser mode 3 decodes from bank `$7E` into `$9390-$93C0`, and the
renderer continuity gate also requires `$1D03=$7E`. The corrected `$AC` backend
is runtime-validated standalone and with `french_resources`.

The accepted Forge backend still patches only the proven suffix geometry and compacts
slots 20..31 at render time. The Ring backend renders its decoded title row unchanged;
it never executes Forge suffix compaction. The earlier `WEAPON_NAME` helper remains
stock. The dispatcher clears `$7E:9385` on stock fallback, which is required for
GAME SELECT compatibility. Low-level renderer identity is explicit: `$01` is
owned by `vwf_dialogues`, `$02` by `vwf_ui`; intro scratch values 3..8 are not
accepted by the shared row/font scope. The shared chunk-commit helper calls the
dialogue-only continuation routine at `$ED:7990` only for identity `$01`, so
standalone `vwf_ui` has no hidden dependency on `vwf_dialogues`.

The Ring title isolation was runtime-proven after tracing the shared submit chain and
reproducing the former corruption caused by applying Forge's overlapping suffix move to
long Ring labels. Future UI families must follow `docs/UI_VWF.md` and receive their own
narrow identity instead of reusing an existing tag value.

The type-2 MONEY frame is also symmetric again after widening: `$C7:714C=$0B`
opens an 11-cell frame, while the independent close seed `$C7:7140=$09` starts
the close one cell farther left than stock. This exact pair is runtime-validated;
do not change one without re-checking the other.

## french_resources — French resources + D9 shop/forge responses

`french_resources` owns the rebuilt `$CA` pointer table/blob for the reviewed name families, nine top-level Ring Menu titles `$0C6-$0CE` and the two reviewed system messages `$1FF-$200`; the two fixed shop currency literals `$C7:7B6A` / `$D0:D894`; the nine `$D9:FE20-$FEF3` shop/forge mini-event records; and the localized content of the `$C0` battle/status pool. No separate `french_shop_text` component is generated.

The component installs the shared `dialogue_french` glyph span and context-sensitive DTE router. D9 responses retain their validated stock parser/capacity. Battle/status text is rebuilt from reviewed Android provenance and relocated to `$EE:6000+`; `$C0:62E2` now uses the reviewed JP-derived `Rétablissement échoué !`; the 8 formerly unresolved records are now reviewed JP-derived French surcharges. `$C0:62F3` now uses the reviewed compact suffix ` s'est rétabli !` after the stock dynamic subject. The stock `$C0:637D/$637F` display scripts remain in place.

The rebuilt `$CA` blob remains 7,103 / 7,315 bytes and now contains 360 translated resources. The rebuilt D9 pool remains 179 / 212 bytes. The current relocated battle pool is 1,573 bytes. `GP -> PO` remains sourced only from `translations/french_resources_reviewed_literals.json`; `vwf_ui` owns presentation only. The exact battle-banner `$AC` rendering path is runtime-validated, including the WRAM source-bank continuity fix `$ED:7B83: C0 -> 7E`.
