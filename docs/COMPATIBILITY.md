# Compatibility audit

All selected components are rebuilt from the same clean USA ROM before an
aggregate build. Their IPS write maps are then compared byte-for-byte.

## Shared French glyph writes

`02_9char_names` and `03_game_select` install the naming-safe French range
`$D4-$E0`. `05_intro_vwf_french` installs those same 13 glyphs plus `$E1-$E5`.
The common glyph bytes are identical because all three builders consume
`shared/french_charset`.

These duplicated writes are intentional: each component must remain usable on a
clean USA ROM without requiring another component.

## Direct-glyph threshold

ROM `0x0016F6` is a declared merge point:

- Name Entry standalone: `$E1` (`$D4-$E0` direct).
- GAME SELECT standalone: `$E1` (`$D4-$E0` direct).
- intro VWF standalone: `$E6` (`$D4-$E5` direct).

The values are declared in the relevant `component.json` files as
`direct_glyph_threshold`. For an aggregate build,
`shared/compatibility.py` applies the highest selected threshold, so a build that
contains intro VWF uses `$E6`.

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
