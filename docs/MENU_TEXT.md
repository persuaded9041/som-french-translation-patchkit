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

## Status strings

The same asset also extracts:

- 16 status-condition names at `$C7:7A8E`;
- 8 status templates at `$C7:7B24`;
- 8 weapon-type names at `$C7:7B6D`;
- `TYPE`, `ENERGY ORB` and `/` at `$C7:7BA5`.

An eight-entry pointer table at `$C7:7BB7` is validated against the eight weapon
names. Status-template parameters such as `$5C $12` and `$5C $16` are preserved
as `{5C12}` / `{5C16}` instead of being mis-decoded as text.

The source JSON exposes logical translatable fragments with ROM-position IDs rather than copying the complete padding-heavy menu blobs. Layout spaces, dashes, dynamic placeholders and button glyphs remain structural ROM data. The two direct GAME FILE level-prefix bytes at `$C7:53C9` and `$C7:5AF1` are also inventoried because component 03 proves they are rendered text. Existing component-03 French labels live in `translations/menu_text_french.json`.
