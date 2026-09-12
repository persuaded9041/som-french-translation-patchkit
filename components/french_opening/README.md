# French opening and credits

Translates the startup credits and scrolling opening story while preserving the
original fixed-width title-screen renderer.

## Sources

- root `assets/opening_text.json`: clean-USA strings extracted from the compressed
  startup/title arrangement.
- root `translations/opening_text_french.json`: sparse French prologue/credit
  translations already validated by this component.
- `assets/opening_font.png`: editable 128×16, 32-tile opening font atlas.
- `src/opening_hook.asm`: readable representation of the renderer helper emitted by Python.
- `docs/MEMORY_MAP.md`: component ROM allocations and hooks.

Opening source IDs use the compressed container address plus deterministic
decompressed offset, for example `C7:B480+09F9`. The fifth French credit has no
clean-USA source position and therefore uses the explicit target-only ID
`new:opening.credit.translation`.

## Accent handling

The scrolling prologue keeps the validated overlay mechanism: `$7D` acute,
`$7E` grave and `$7F` circumflex. Accented `E` characters are rendered as a
normal `E` plus an accent tile on the row above.

Startup credits instead use a dedicated one-cell `É` in opening-font tile `$7A`
(the original `Z` slot), because the overlay mechanism is unsuitable for their
fade. The current text does not use `Z`; the builder rejects a literal `Z`
rather than displaying the wrong glyph.

The `É` artwork is authored directly in `assets/opening_font.png`; translated
credit text is UTF-8 JSON in `translations/opening_text_french.json`.

This `$7A` reservation is local to the opening font and does not alter the
shared French charset used by other components.

## Arrangement storage and build performance

The modified title arrangement is relocated to ROM `$EE:A000`. It remains in the
stock Secret of Mana compression container and is still loaded through the stock
`$C1:0014` resource decompressor into WRAM `$7E:5000`, but the payload is encoded
with literal packets only.

This is intentional. The arrangement is only about 7 KiB, expanded ROM space is
available, and searching for an optimal LZ parse at every build added substantial
host-side cost without providing a useful runtime benefit here. Literal-packet
encoding is deterministic O(n), remains fully regenerable when the opening text
changes, and preserves the game's normal resource-loading protocol.

A direct raw-ROM-to-WRAM copy was tested and worked standalone, but conflicted at
runtime when combined with `mana_tree_original`, which also hooks the stock
resource-loading/decompression path. Keeping `$C1:0014` fixed that interaction;
the combined build was runtime-validated.
