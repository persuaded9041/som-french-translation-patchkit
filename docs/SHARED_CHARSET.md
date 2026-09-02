# Shared French charset

`shared/french_charset/` is the canonical source of French direct character codes for the project.

## Canonical mapping

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
| `$E1` | À |
| `$E2` | É |
| `$E3` | Î |
| `$E4` | Œ |
| `$E5` | œ |

The full direct range ends immediately before `$E6`, so consumers of all 18 characters use `$E6` as the DTE boundary.

## Source files

- `charset.json`: machine-readable mapping and named profiles.
- `french_glyphs.png`: canonical editable 18 × 8x12 glyph atlas.
- `charset.py`: validation/loading helpers used by builders.

## Current consumers

- `03_game_select`: profile `game_select`, first 13 characters (`$D4-$E0`). It intentionally retains standalone threshold `$E1` to reproduce the validated IPS exactly.
- `05_intro_vwf_french`: profile `full_french`, all 18 characters (`$D4-$E5`), threshold `$E6`.

Both standalone patches still write the first 13 glyph bytes to the ROM because each patch must work alone. This is a runtime duplication required by modularity, not a duplicated source asset.

## Rules for future components

1. Do not create another private mapping for French accented characters.
2. Reuse the canonical character codes whenever the engine context allows direct glyph codes.
3. Reuse the canonical artwork or derive component-specific graphics from it.
4. If a component needs a subset, add a named profile to `charset.json` rather than copying the table.
5. If a new French character is required, extend this shared definition first and update verification.
6. Keep standalone patches self-sufficient at runtime even if that requires identical ROM writes.

The naming-screen accent extension and the future main-dialogue VWF should therefore consume this shared charset.
