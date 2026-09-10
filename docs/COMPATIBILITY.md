# Compatibility audit

All selected components are rebuilt from the same clean USA ROM before an
aggregate build. Their IPS write maps are then compared byte-for-byte.

## Shared French glyph writes

`03_game_select` installs the naming-safe `$D4-$E0` subset. `02_9char_names`
installs that same French subset plus the disjoint shared glyphs `$D3=♪`,
`$E6=°` and `$E7=;`, while deliberately leaving `$E1-$E5` untouched because
Name Entry uses those slots for graphics. `05_intro_vwf_french` installs the
unchanged French `$D4-$E5` range. Components 06/08 use the full extended
dialogue span `$D3-$E7`. Identical overlapping glyph bytes all come from
`shared/french_charset/french_glyphs.png`.

## Direct-glyph / DTE routing

Component 03 retains its historical standalone immediate `$E1` threshold and
component 05 remains unchanged standalone with `$C0:16F6 = $E6`.

Component 02 now uses the small `shared/name_dte.py` router standalone. Ordinary
event sources still use `$E1`; the relocated Name Entry resource in bank `$E4`
and the stock `PLAYER_NAME` scratch stream at `$7E:A22F` use `$E8`, allowing
`$E6/$E7` on the character grid and inside a selected name without reinterpreting
normal DTE bytes. This route is runtime-validated. If 02 is combined with a later legacy charset
component but without 06/08, the root combiner stores the historical max
threshold in the router's `$C7:4C86` base-config byte and restores its JML after
all standalone patches have been applied.

Components 06/08 replace the same stock four-byte decision at
`$C0:16F5-$16F8` with the later, byte-identical full context router from
`shared/dialogue_dte.py`:

- non-dialogue parser callers: `$E6`;
- event `$0400`: `$E6`;
- ordinary event-engine dialogue when the dialogue profile is enabled: `$E8`;
- component-02 Name Entry resource in bank `$E4`: `$E8`.

The event-engine caller is identified by the established `$114B` stacked return
address, so GAME SELECT does not enter the dialogue `$E8` path. Event `$0400`
uses component 05's configured translated end when present and the clean-USA
`$0E44` end otherwise. Thus `$E6/$E7` can be direct dialogue glyphs without
changing the intro's 25 private DTE pairs.

In aggregate builds containing 06/08, their full router supersedes both the
legacy immediate-threshold byte and component 02's smaller name-only hook.
Without 06/08, component 02's router preserves the historical max-threshold
merge through its base-config byte. Without any router, the original immediate
max-threshold merge remains unchanged.

## Opening-font local glyph

`04_french_opening` reserves tile `$7A` of its own title-screen font for the one-cell startup-credit `É`. This is local to the opening font, does not consume a shared French charset code, and introduces no new ROM/WRAM allocation or cross-component merge rule. The component builder rejects literal `Z` text because that opening-font slot is no longer available as `Z`.

## Allocations

The principal ROM/WRAM allocations are documented in `docs/MEMORY_MAP.md` and
in each component's technical documentation. New code/data must be placed only
after checking those ranges against all existing components.


## Intro skip compatibility

`07_intro_skip` hooks `$C0:012C-$012F`, a runtime-validated execution point during the translated new-game introduction. While event `$0400` is in live event bank `$CA` and pointer range `$0C02-$0E8A`, holding R (`$4218` bit `$10`) continuously for 120 NMI frames redirects the live event pointer to `$CA:FFC0-$FFC7`. That private script mirrors the stock end of `$0400` while omitting only the `$1D $7F` Mode 7 world-map flyover. Runtime testing confirms the non-blocking hold, reset on release, direct arrival at the waterfall, and correct dialogue-frame transitions.

The component reserves `$ED:7400-$74FF` for its input and NMI helpers, between the extended-ROM allocations of components 06 and 03. It samples the stock frame counter at `$7E:00F4` and reuses `$7E:938A-$938B` only during translated intro event `$0400`. Component 05 intercepts that event before component 06 reaches its renderer-entry hook, so component 06 does not use its overlapping width-index scratch during the intro. The NMI hook at `$C0:AC34-$AC37` clears the active-hold flag whenever R is released so separate presses cannot accumulate if the event-engine hook misses the release interval.


## Header/checksum writes

Standalone builders may write ROM-size/header metadata and their own SNES
checksum. Checksum-byte overlaps are build metadata, not functional collisions.
The aggregate builder recomputes one checksum after all selected components and
merge rules have been applied.

## Policy

- byte-identical functional overlap required for standalone operation: allowed;
- checksum overlap: allowed and recomputed;
- legacy threshold-byte overlap with the context-sensitive dialogue router: allowed and resolved;
- any other differing functional overlap: build failure.

The normal maintenance target is the modified component by itself plus the full
all-components build. Partial combinations are only tested when a specific
compatibility concern justifies them.

## Shared VWF parser buffer bridge

Components `05_intro_vwf_french` and `06_dialogue_vwf` independently install the
same parser hooks and helper bytes generated by `shared/vwf_text_buffer.py`. These
functional overlaps are therefore byte-identical and pass the normal overlap
audit without a special merge rule.

The stock `$C0:16B8` parser initializer is shared by the event engine and GAME
SELECT. The bridge reads the untouched stacked return address and activates only
for `$114B` (event-engine call from `$C0:1149`); GAME SELECT's `$235B` call
remains stock. The private buffer is `$7E:9390-$93BB`; the stock `$A1A4` buffer
is not extended because `$A1C5-$A1C7` are live engine state. Component 05 owns
its intro marker/end bytes at `$C7:4C80-$4C82`; component 06 owns marker `$06` at
`$C7:4C84`.

## Shared VWF row compositor

Components `05_intro_vwf_french` and `06_dialogue_vwf` independently install the
same 63-byte renderer-neutral compositor generated by `shared/vwf_compositor.py`
at `$C7:4C90-$4CCE`. The overlap is byte-identical and requires no special merge
rule.

Both components derive glyph rows from the stock `$D2:DC00` font and install the
same framing selector bundle at `$C7:44C0-$4557`. They also install the same runtime-validated 13-byte `$C7:4560-$456C` helper,
which performs stock row load -> framing -> shared compositor. Component 06 reaches it
only after its caller-gated renderer-scope check; non-event callers replay the
stock row load. Parser/event scope remains separate from this primitive.

## Shared VWF outline preparation

Components `05_intro_vwf_french` and `06_dialogue_vwf` both install the same
one-byte stock-outline preparation from `shared/vwf_outline.py`: `$C0:163D` is
changed from `ROL` to `ASL`, preventing carry from one source row from being
injected into the next. The overlap is byte-identical, so both standalone and
aggregate builds use the same preparation.

## Dialogue VWF compatibility

`06_dialogue_vwf` independently installs the `dialogue_french` `$D3-$E7`
span and the context-sensitive DTE router, so its standalone IPS does not depend
on component 05. The shared `$D4-$E5` glyph bytes remain byte-identical.

Component 06 enables its core VWF only when the shared `$C0:1664` renderer was
called by the event engine at `$C0:1150` and the live event bank is `$C9` or
`$CA`. This caller-based gate is runtime-validated and is required because GAME
SELECT also calls `$C0:1664`; bank/state checks alone are not safe discriminators.

Component 05 still owns translated intro event `$0400`: it intercepts that event
at `$C0:1664` and exits before component 06 reaches `$C0:167D`. This keeps the
shared `$7E:9380+` scratch mutually exclusive even though component 06 now also
handles ordinary `$CA` event dialogue. Component 07's `$938A-$938B` intro timer
is protected by the same early interception.

Renderer architecture, metrics, caller discrimination and generic event-
interruption handling belong to `components/06_dialogue_vwf/docs/`, not to this
cross-component compatibility document.

## Dialogue text compatibility

`08_dialogue_text` remains the owner of event-script source/reinsertion data, not of the
VWF renderer itself. The first edited-event checkpoint (`$0107`) was
runtime-validated with the existing dialogue VWF, including dynamic player-name
insertion, line breaks and WAIT sequencing. The canonical `assets/dialogues.json` contains clean-USA source only.
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
`translations/dialogues_manual_supplements.json` pending manual French translation. `$00DF` is complete through the runtime-validated minimal
later-choice anchor shift. `$0103`, `$017F` and `$01DC` are separately user-validated as
visually complete Android adaptations and no longer carry a PARTIEL badge. `$0602` is also
badge-free after runtime review found no visible missing/English content; unresolved `CA:85DD`
remains tracked without altering the event bytes. `$01DC` has one
explicit structural exception: its final stock `PLAYER_NAME(0)` is omitted together with
Android-absent `C9:804A`. The shared inn prompt is complete through a parameterized Android
ID 110 template while the stock numeric price carriers remain dynamic.
Interactive choice rows use component 06's ordinary VWF path with stock `CHOICE_OPTION`
/ `$A1D7[]` selection geometry untouched. Resynchronizing VWF option starts to those stock
boundaries is runtime-validated on `$0331`; the current follow-up additionally uses the
existing terminal boundary to keep a preserved closing parenthesis outside the final
magenta span. The full mass corpus still requires the planned playthrough.

Growth has a runtime-validated relocation path. Component 08 can install a sparse
24-bit event-address table and dispatcher hook, then pack only overlong rebuilt
events into reserved banks `$E8-$EC`. A zero sparse-table entry falls back to
the *live* stock `$C9/$CA` tables, so component 05 remains authoritative for its
validated `$0400-$040F` pointer rewrites. Event `$0400` is still excluded from
the component-08 asset.

Relocated dialogue must keep the same VWF/parser behavior. Components 05 and 06
therefore share one minimal bank-gate extension: their existing caller-gated
private parser path and component-06 renderer path continue to accept stock
`$C9/$CA`, and additionally accept only component-08's reserved `$E8-$EC` range.
The `$C9/$CA` behavior is unchanged. The `$E8-$EC` path was runtime-validated
with unchanged event `$0107` executing from `$E8:2000`, including dynamic name
insertion, VWF rendering, line breaks and WAIT behavior. The temporary force
probe has now been removed: normal builds relocate only events that genuinely
outgrow their source span.

When translated dialogue is present, component 08 installs the same
`dialogue_french` `$D3-$E7` glyph span and context-sensitive router as component
06; component 05 remains on its separate `$D4-$E5` / `$E6` intro profile. The root extractor continues to structurally parse all 2048 stock event scripts
and commits the 713 text-bearing events excluding `$0400`. The 513 following
`$CA` non-event resources are now extracted separately to
`assets/text_resources.json` and are not owned by the dialogue VWF runtime.
