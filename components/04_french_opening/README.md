# French opening and credits

Translates the startup credits and scrolling opening story while preserving the original fixed-width title-screen renderer.

## Editable sources

- `assets/opening_text.csv`: scrolling prologue text.
- `assets/opening_credits.csv`: five startup-credit lines.
- `assets/opening_font.png`: editable 128×16, 32-tile opening font atlas.
- `src/opening_hook.asm`: readable representation of the renderer helper emitted by Python.
- `docs/MEMORY_MAP.md`: component ROM allocations and hooks.

## Accent handling

The scrolling prologue keeps the validated overlay mechanism: `$7D` acute, `$7E` grave and `$7F` circumflex. Accented `E` characters are rendered as a normal `E` plus an accent tile on the row above.

Startup credits instead use a dedicated one-cell `É` in opening-font tile `$7A` (the original `Z` slot), because the overlay mechanism is unsuitable for their fade. The current text does not use `Z`; the builder rejects a literal `Z` rather than displaying the wrong glyph.

The `É` artwork is authored directly in `assets/opening_font.png`, and `opening_credits.csv` accepts `É` directly in UTF-8.

This `$7A` reservation is local to the opening font and does not alter the shared French charset used by other components.
