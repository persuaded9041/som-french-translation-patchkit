# Shared French character set

This directory is the single source of truth for French direct-glyph codes used
by text-oriented components.

`charset.json` defines the canonical character-to-byte mapping.
`french_glyphs.png` is the canonical editable 18-glyph 8×12 atlas.
`charset.py` validates and exposes both to component builders.

Canonical full range: `$D4-$E5`. When the full range is active, the direct-glyph
/DTE threshold is `$E6`.

Profiles:

- `basic_french`: `$D4-$E0` (13 glyphs), threshold `$E1`.
- `full_french`: `$D4-$E5` (18 glyphs), threshold `$E6`.

Current consumers:

- `02_9char_names` uses the `basic_french`/naming-safe `$D4-$E0` subset.
- `03_game_select` uses the same `$D4-$E0` subset.
- `05_intro_vwf_french` uses the complete `$D4-$E5` range.

Name Entry intentionally stops at `$E0`: `$E1-$E5`
are still used by graphics on that screen. This is a screen-specific limitation,
not a different character mapping.

Standalone components may install identical glyph bytes in ROM because each must
work independently. The editable source remains centralized here so assignments
and artwork cannot silently diverge.
