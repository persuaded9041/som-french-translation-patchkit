# French extended Name Entry overlay

French localization layer for `name_entry_extended`.

## Dependency

This component **requires `name_entry_extended`**. It does not own or duplicate
the 9-character engine, lowercase row, generic symbols or character lookup.

The generic component deliberately exposes **three** rows. This overlay expands
the keyboard window/navigation to **four** rows and adds the French repertoire.

## Owned content

- four-row navigation/layout override;
- fourth-row French/extended characters: `Çàâçéèêëîïôùû♪°;`;
- the validated French Name Entry help from
  `translations/interface_text_french.json`;
- canonical shared glyph artwork required by those character codes;
- Name Entry / `PLAYER_NAME`-specific DTE routing so `$D3`, `$D4-$E0`, `$E6`
  and `$E7` remain direct glyphs in the relocated grid and selected names.

`assets/name_entry_extension.json` is the component-local data source for the
fourth-row repertoire. French prose remains in the canonical root translation
JSON, not in the component asset.

## Composition invariant

When applied after `name_entry_extended`, this overlay reproduces the historical
runtime-validated four-row French Name Entry bytes exactly after checksum
recomputation. The dependent overrides for navigation, private layout, and
`$E4:40B4-$41FF` are declared in `component.json`; differing overlap outside
declared dependency overlays remains a build error.
