# Name Entry source map

Human-readable source equivalents for the exact payloads emitted by
`build_patch.py` / `patch_data.py`.

- `core.asm`: 9-character limit, handler/resource redirects.
- `navigation.asm`: generic three-row Up/Down states; the stock `$60` initial cursor position is intentionally retained.
- `selection.asm`: grid parameter and relocated character lookup.
- `layout.asm`: generic three-row keyboard geometry and layout pointer redirection.

`french_name_entry_extended` is a dependent overlay that replaces only the
navigation/layout pieces needed to expose a fourth row and then supplies the
localized fourth-row resource/help/glyph routing.
