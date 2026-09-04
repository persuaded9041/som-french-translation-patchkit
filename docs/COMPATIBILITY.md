# Compatibility audit

All selected components are rebuilt from the same clean USA ROM before an
aggregate build. Their IPS write maps are then compared byte-for-byte.

## Shared French glyph writes

`02_9char_names` and `03_game_select` install the naming-safe French range
`$D4-$E0`. `05_intro_vwf_french` and `06_dialogue_vwf` install those same 13 glyphs plus `$E1-$E5`.
The common glyph bytes are identical because all four builders consume
`shared/french_charset`.

These duplicated writes are intentional: each component must remain usable on a
clean USA ROM without requiring another component.

## Opening-font local glyph

`04_french_opening` reserves tile `$7A` of its own title-screen font for the one-cell startup-credit `É`. This is local to the opening font, does not consume a shared French charset code, and introduces no new ROM/WRAM allocation or cross-component merge rule. The component builder rejects literal `Z` text because that opening-font slot is no longer available as `Z`.

## Direct-glyph threshold

ROM `0x0016F6` is a declared merge point:

- Name Entry standalone: `$E1` (`$D4-$E0` direct).
- GAME SELECT standalone: `$E1` (`$D4-$E0` direct).
- intro VWF standalone: `$E6` (`$D4-$E5` direct).
- dialogue VWF standalone: `$E6` (`$D4-$E5` direct).

The relevant `component.json` files declare a `shared_charset_profile`. Each profile owns its DTE threshold in `shared/french_charset/charset.json`. For an aggregate build, `shared/compatibility.py` applies the highest selected threshold, so any build containing a `full_french` consumer uses `$E6`.

## Allocations

The principal ROM/WRAM allocations are documented in `docs/MEMORY_MAP.md` and
in each component's technical documentation. New code/data must be placed only
after checking those ranges against all existing components.

## Header/checksum writes

Standalone builders may write ROM-size/header metadata and their own SNES
checksum. Checksum-byte overlaps are build metadata, not functional collisions.
The aggregate builder recomputes one checksum after all selected components and
merge rules have been applied.

## Policy

- byte-identical functional overlap required for standalone operation: allowed;
- checksum overlap: allowed and recomputed;
- declared direct-glyph threshold overlap: allowed and resolved;
- any other differing functional overlap: build failure.

The normal maintenance target is the modified component by itself plus the full
all-components build. Partial combinations are only tested when a specific
compatibility concern justifies them.

## 06_dialogue_vwf

The renderer-entry hook at `$C0:167D` and progression hook at `$C0:13A3` are
runtime-validated insertion points. `$001D03 == $C9` is runtime-validated as a
stable development scope at the progression stage; it deliberately does not
claim to cover every future dialogue because event text also exists in `$CA`.

The runtime-validated architecture preserves the original
`$C0:168A-$C0:16B0` character-to-glyph lookup/render path. Component 06 derives
the destination tile from a private cumulative pixel cursor, intercepts only the
already-selected font row, and performs shift/spill composition across 12-byte
cells. Its 128-entry advance-table lookup and complete lowercase framing are
runtime-validated.

The lowercase entries in that advance table are runtime-validated.
Using the component-05 rule `ink_width + 1` against the validated framed
geometry gives `a-h/k/m-q/s/u-z=7`, `i/l=3`, `j=4`, `r=6`, `t=5`. No hook,
framing helper, compositor logic, WRAM allocation or scope is changed.
Uppercase `A-Z` is runtime-validated at `A-H/J-Z=7` and `I=3`. `$B5-$BE` are the digits `0-9` and remain satisfactory at their stock widths. Other non-lowercase metrics remain conservative unless explicitly calibrated.

The punctuation groups `$BF-$C4`, `$C6-$CC` are runtime-validated. Colon `$C5` is validated at `shift=1, advance=7` (2 px left / 3 px right). `$CD` is excluded from all active special handling
and must remain on the stock/default conservative path.

Component 06 now independently installs the canonical full French glyph range `$D4-$E5` and writes the `$E6` direct/DTE threshold, matching component 05 byte-for-byte in aggregate builds. Its French framing is runtime-validated at `$D4-$E3 = shift 1 / advance 7`, `$E4/$E5 = shift 0 / advance 8`. Component 06 continues to use its WRAM scratch only under `$C9`, while component 05 uses its private intro state under the mutually exclusive `$CA` scope. The
`$C0:13A3` progression trampoline remains stock-equivalent and contains no
event-resume logic.

The known `Wait up!` event-boundary spacing issue is intentionally unresolved
and has no active patch code. See
`components/06_dialogue_vwf/docs/EVENT_INTERRUPTION_NOTES.md`.


The runtime-validated outline repair uses a `$C9`-scoped hook at `$C0:1168`, after
the stock outline `JSR $162C` returns, plus helper `$ED:7280-$ED:72E9` and
WRAM scratch `$7E:938C-$938D`. The rejected `$C0:1165` hook is absent.
