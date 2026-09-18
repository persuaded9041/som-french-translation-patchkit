# Native menu/status text extraction

`assets/menu_text.json` covers stock strings in bank `$C7` that are outside the
513-entry `$CA` resource table and outside the separate interface/help pointer
family.

## Menu resources

Nine null-terminated text resources occupy `$C7:7313-$C7:74E9`. Their use is
confirmed by the first word of the stock **11 × 3-word menu descriptor table**
at `$C7:780A`. Some descriptors share a text resource; `$74EA` is the stock
empty/no-text resource.

The nine extracted resources cover:

- GAME SELECT labels;
- GAME FILE header/fields;
- Window Edit labels;
- Action Settings labels;
- Controller Edit labels;
- Weapon Skill labels;
- Magic Skill labels;
- the stock Name Entry alphabet.

`Empty` is a separate five-glyph fixed field immediately before the descriptor
table at `$C7:7805`; it is not null-terminated and is extracted explicitly.

## Action Settings — promoted fixed-font localization

The `menu.action_settings` entries are runtime-valid and promoted through
`french_menus`:

- `$C7:73E0` `ATTACK` -> `Attaquer`
- `$C7:73E7` `KEEP AWAY` -> `S'éloigner`
- `$C7:73F1` `APPROACH` -> `S'approcher`
- `$C7:73F9` `GUARD` -> `Défendre`

The page remains on the stock fixed-width renderer. The final solution repacks
the labels into a proven-safe 34-cell resource and adjusts the three dependent
tile bases exactly as the official French Rev 1 ROM does. A VWF attempt for
this screen is rejected and must not be restored.

See `components/french_menus/README.md` and `docs/MEMORY_MAP.md` for the exact
allocation/offsets.

## GAME FILE promoted labels

The GAME FILE fields promoted through `french_menus` include `Fichier`, `Argent`,
`PO`, `Sauvegardes`, and `Graines de Mana`. `Sauvegardes` occupies 11 of the 15
fixed cells available before its dynamic value. `Graines de Mana` occupies all 15
source cells at `C7:73AA`; its display is runtime-validated through the exact,
pair-aligned GAME FILE backend in `vwf_ui`, while the dynamic Mana value remains stock.

The GAME FILE total-money renderer is hybrid: stock code writes the first currency
glyph inside a fixed 16-cell dynamic upload, while the second glyph remains in
the resource-backed template column immediately to its right. The runtime-validated
French layout preserves that architecture but inserts one explicit blank before
the first currency glyph, yielding `1234567 PO` without moving the `PO` anchor.
The first glyph is still derived from JSON ID `C7:7394`; no localized unit text is
hard-coded in renderer logic. See `docs/HANDOFF.md` and the component memory map.

## Status strings

The same asset also extracts:

- 16 status-condition names at `$C7:7A8E`;
- 8 status templates at `$C7:7B24`;
- 8 weapon-type names at `$C7:7B6D`;
- `TYPE`, `ENERGY ORB` and `/` at `$C7:7BA5`.

An eight-entry pointer table at `$C7:7BB7` is validated against the eight weapon
names. Status-template parameters such as `$5C $12` and `$5C $16` are preserved
as `{5C12}` / `{5C16}` instead of being mis-decoded as text.

The reviewed French translations are already recorded in
`translations/menu_text_french.json`, including the 16 condition names, status
templates, weapon types and `Type` / `Sphères`. They remain **translation-only**
until the corresponding Status renderer is explicitly promoted and runtime
validated.

The source JSON exposes logical translatable fragments with ROM-position IDs
rather than copying complete padding-heavy menu blobs. Layout spaces, dashes,
dynamic placeholders and button glyphs remain structural ROM data. The two
direct GAME FILE level-prefix bytes at `$C7:53C9` and `$C7:5AF1` are also
inventoried because `french_menus` proves they are rendered text.
