# Shared French character set

This directory is the single source of truth for French direct glyph codes used by text-oriented components.

`charset.json` defines the canonical character-to-byte mapping. `french_glyphs.png` is the canonical editable 18-glyph 8x12 atlas. `charset.py` validates and exposes both to component builders.

Canonical range: `$D4-$E5`. When the full range is active, the DTE threshold is `$E6`.

Profiles currently used:

- `game_select`: `$D4-$E0` (13 glyphs), preserving the runtime-validated standalone GAME SELECT patch and its `$E1` DTE threshold.
- `full_french`: `$D4-$E5` (18 glyphs), used by the intro VWF with `$E6` as the DTE threshold.

A component may install the same glyph bytes into ROM when it must remain independently applicable. The source definition is nevertheless shared here, preventing code assignments or artwork from silently diverging.

Future components such as the naming screen and main dialogue VWF should consume this definition rather than creating another private accented-character table.
