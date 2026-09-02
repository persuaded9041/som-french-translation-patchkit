# Compatibility audit

All five standalone IPS files are built from the same clean USA ROM and audited
byte-for-byte before combination.

## Shared French glyph writes

`02_9char_names` and `03_game_select` both install the naming-safe French range
`$D4-$E0`. `05_intro_vwf_french` installs the same 13 glyphs plus `$E1-$E5`.
All overlapping glyph bytes are identical because they come from the same
`shared/french_charset` source.

The duplicated ROM writes are intentional: every IPS must still work alone.
The editable mapping/artwork is not duplicated.

## Direct-glyph threshold

ROM `0x0016F6` is the only differing functional overlap among these charset
consumers:

- Name Entry standalone: `$E1` (`$D4-$E0` direct).
- GAME SELECT standalone: `$E1` (`$D4-$E0` direct).
- intro VWF: `$E6` (`$D4-$E5` direct).
- any combined build containing intro VWF plus either of the first two: `$E6`.

`build.py` declares and resolves this rule explicitly.

## Name Entry allocation

The four-row Name Entry layout script lives at ROM `0x074E00-0x074E6D`
/ CPU `$C7:4E00-$4E6D`. Current overlap auditing confirms that this allocation
does not collide with GAME SELECT or intro VWF code/data.

## Opening + intro VWF

The historical collision at `$C7:4285` is already removed. The opening helper
lives at `$EE:9000`; `$C7:4285` remains owned by intro VWF.

## Header/checksum overlaps

Standalone components may independently write expanded-ROM metadata and their
own checksum. The combined builder treats those bytes as build metadata and
recalculates one final checksum after all selected patches are applied.

## Policy

- byte-identical overlap required for standalone operation: allowed;
- header/checksum overlap: allowed/recomputed;
- declared French decoder-threshold overlap: allowed/resolved;
- any other differing functional overlap: build failure.

All **31 non-empty combinations** of the five current components are checked by
the project maintenance workflow and build without undeclared collisions.
