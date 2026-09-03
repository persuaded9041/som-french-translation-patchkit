# Shared French charset

`shared/french_charset/` is the canonical source for the French direct-glyph
codes and glyph artwork used by this patchkit.

It defines the character codes allocated by the project for French text. This
is a patchkit convention: it is not intended to describe every character used
by the original game or every character that could exist in a French charset.

## Canonical patchkit mapping

When the full French profile is active, the patchkit uses the direct-glyph
range `$D4-$E5` as follows:

| Code | Character | Code | Character |
|---|---|---|---|
| `$D4` | Ç | `$DD` | ï |
| `$D5` | à | `$DE` | ô |
| `$D6` | â | `$DF` | ù |
| `$D7` | ç | `$E0` | û |
| `$D8` | é | `$E1` | À |
| `$D9` | è | `$E2` | É |
| `$DA` | ê | `$E3` | Î |
| `$DB` | ë | `$E4` | Œ |
| `$DC` | î | `$E5` | œ |

These 18 characters are the direct French glyphs currently required by the
project. New characters should only be added when a component genuinely needs
them and when the affected engine context has free direct-glyph codes available.

With the complete `$D4-$E5` range enabled, `$E6` is the first code available to
the DTE parser. Components that use a smaller direct-glyph profile may use an
earlier DTE threshold.

## Profiles

The shared definition currently exposes two profiles.

### `basic_french`

Direct-glyph range: `$D4-$E0`  
DTE threshold: `$E1`

| Code | Character |
|---|---|
| `$D4` | Ç |
| `$D5` | à |
| `$D6` | â |
| `$D7` | ç |
| `$D8` | é |
| `$D9` | è |
| `$DA` | ê |
| `$DB` | ë |
| `$DC` | î |
| `$DD` | ï |
| `$DE` | ô |
| `$DF` | ù |
| `$E0` | û |

This profile deliberately stops at `$E0`. In the Name Entry screen, the
original graphics stored in font slots `$E1-$E5` must be preserved; replacing
them causes graphical corruption.

### `full_french`

Direct-glyph range: `$D4-$E5`  
DTE threshold: `$E6`

This profile contains all 18 characters from the canonical patchkit mapping and
is used in contexts where `$E1-$E5` are available for French glyphs.

## Source files

- `charset.json` - canonical character mapping and profiles, including each profile
  DTE threshold.
- `french_glyphs.png` - editable 18-glyph 8×12 atlas in the exact order of the
  `full_french` profile.
- `charset.py` - loading, validation, mapping, profile, and glyph-conversion
  helpers used by component builders.

## Current consumers

- `02_9char_names` - uses the `basic_french` profile (`$D4-$E0`) and a `$E1` DTE threshold.
- `03_game_select` - uses the `basic_french` profile (`$D4-$E0`) and a `$E1` DTE
  threshold.
- `05_intro_vwf_french` - uses the `full_french` profile (`$D4-$E5`) and a
  `$E6` DTE threshold.

The same direct character codes are intentionally reused across components so
that identical French characters keep the same encoding whenever the engine
context permits it. Standalone components may therefore emit identical ROM
writes derived from this shared definition.

## Rules for future components

1. Do not introduce a private French mapping that conflicts with this shared
   definition.
2. Reuse the canonical direct-glyph codes whenever the target engine context
   makes those codes available.
3. Reuse or derive glyph artwork from `french_glyphs.png` rather than creating
   independent copies of the same glyphs.
4. Add a named profile when a component needs only a subset of the canonical
   mapping.
5. Extend the canonical mapping only when a genuinely new character is needed,
   after checking that the required direct-glyph code is safe in every affected
   context.
6. Keep standalone patches self-sufficient even when this requires identical
   ROM writes generated from the shared source.
