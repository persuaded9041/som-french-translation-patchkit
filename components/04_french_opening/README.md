# French opening and credits

Translates the startup credits and opening story while preserving the original fixed-width title-screen renderer.

This component is standalone and targets only the clean, unheadered US ROM.

## Build

```bash
python3 build_patch.py "Secret of Mana (USA).sfc" -o build/patch.ips
```

## Editable sources

- `assets/opening_text.csv` - the scrolling prologue text.
- `assets/opening_credits.csv` - the five startup-credit lines.
- `assets/opening_font.png` - the editable 128×16, 32-tile opening font atlas used by both the scrolling text and startup credits.
- `src/opening_hook.asm` - readable 65C816 representation of the renderer helper emitted by Python.
- `docs/MEMORY_MAP.md` - component ROM allocations and hooks.

## Accents and the startup-credit É

The scrolling prologue keeps the validated overlay-accent mechanism already used by this component: `$7D` acute, `$7E` grave and `$7F` circumflex. An accented `E` in `opening_text.csv` is therefore still rendered as a normal `E` plus an accent tile on the row above.

That mechanism is not suitable for startup credits because their fade applies to the credit row itself. The credits instead use a dedicated one-cell `É` stored in opening-font tile `$7A`, which was the `Z` slot. The current French opening and credits do not use `Z`, so the builder reserves `$7A` for `É` and rejects a literal `Z` rather than silently displaying the wrong glyph.

The `É` artwork is authored directly in `assets/opening_font.png`; it is not generated in Python. The current 8×8 design is the runtime-validated compressed-height version, with its middle horizontal stroke raised by one pixel for a more balanced shape.

`opening_credits.csv` is the source of truth for the credit text. `É` may be entered directly in UTF-8 and is automatically encoded as `$7A`.

## Compatibility

The helper lives at `$EE:9000`, separate from the intro VWF code at `$C7:4285`. The modified arrangement is relocated to `$EE:8000`.

The `$7A` reservation is local to the opening font and adds no ROM or WRAM allocation. It does not change the shared French charset used by Name Entry, GAME SELECT or intro VWF.

For cross-component rules, see the package-level `docs/COMPATIBILITY.md`.
