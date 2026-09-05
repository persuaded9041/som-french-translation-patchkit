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


## Intro skip compatibility

`07_intro_skip` hooks `$C0:012C-$012F`, a runtime-validated execution point during the translated new-game introduction. While event `$0400` is in live event bank `$CA` and pointer range `$0C02-$0E8A`, holding R (`$4218` bit `$10`) continuously for 120 NMI frames redirects the live event pointer to `$CA:FFC0-$FFC7`. That private script mirrors the stock end of `$0400` while omitting only the `$1D $7F` Mode 7 world-map flyover. Runtime testing confirms the non-blocking hold, reset on release, direct arrival at the waterfall, and correct dialogue-frame transitions.

The component reserves `$ED:7400-$74FF` for its input and NMI helpers, between the extended-ROM allocations of components 06 and 03. It samples the stock frame counter at `$7E:00F4` and reuses `$7E:938A-$938B` only under the `$CA` intro scope; component 06 uses those bytes only under mutually exclusive `$C9` dialogue scope. The NMI hook at `$C0:AC34-$AC37` clears the active-hold flag whenever R is released so separate presses cannot accumulate if the event-engine hook misses the release interval.


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

## Dialogue VWF compatibility

`06_dialogue_vwf` independently installs the canonical `full_french` range
`$D4-$E5` and the `$E6` direct/DTE threshold so its standalone IPS does not
depend on component 05. In aggregate builds those glyph writes are byte-identical
and the threshold is resolved by the shared charset profile.

Its current runtime scope is `$C9`; component `05_intro_vwf_french` uses its
private VWF state under `$CA`. Their current WRAM scratch reuse is therefore
mutually exclusive, but **broadening component 06 beyond `$C9` requires a new
compatibility audit** before that assumption can be kept.

Renderer architecture, metrics, rejected experiments and the deferred event
interruption investigation belong to `components/06_dialogue_vwf/docs/`, not to
this cross-component compatibility document.
