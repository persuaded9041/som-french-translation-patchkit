# Shared French charset

`shared/french_charset/` is the canonical source of French direct character
codes and glyph artwork for the project.

## Canonical mapping

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

The full direct range ends before `$E6`.

## Source files

- `charset.json` — canonical mapping and profiles.
- `french_glyphs.png` — editable 18 × 8×12 glyph atlas.
- `charset.py` — validation/loading helpers used by builders.

## Current consumers

- `02_9char_names`: naming-safe profile `$D4-$E0`; threshold `$E1`.
- `03_game_select`: same `$D4-$E0` profile; threshold `$E1`.
- `05_intro_vwf_french`: full `$D4-$E5` profile; threshold `$E6`.

The Name Entry screen deliberately does not overwrite `$E1-$E5`, because those
font slots are still used by original graphics in that screen. Runtime testing
showed that overwriting them causes graphical corruption. Accented names using
`$D4-$E0` are nevertheless stored directly and have been validated to render
correctly later in normal game dialogue.

## Rules for future components

1. Do not create a private conflicting French mapping.
2. Reuse canonical codes whenever the engine context allows them.
3. Reuse/derive glyph artwork from this shared source.
4. Add named subsets/profiles instead of copying tables.
5. Extend the canonical definition first when adding a genuinely new character.
6. Keep standalone patches self-sufficient even when this requires identical
   ROM writes generated from the shared source.
