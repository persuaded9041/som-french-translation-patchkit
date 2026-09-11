# French editable default player-name prefill

French content overlay for `name_entry_prefill`. It proposes the official
French character names while leaving the ordinary Name Entry editor fully
active: the player may erase, replace or accept each proposed name.

## Dependencies

This component requires both:

- `name_entry_prefill`, which owns the one-shot hook and generic editable
  prefill mechanism;
- `french_name_entry_extended`, which owns the French four-row keyboard and the
  accented glyph row used by `Popoï`.

Their transitive dependency on `name_entry_extended` is resolved automatically
by the root builder.

## Canonical data

`assets/name_entry_defaults_fr.json` is the only source of French default-name
text:

```json
{
  "boy": "Randy",
  "girl": "Prim",
  "sprite": "Popoï"
}
```

These names are authored directly in the component JSON. They are not extracted
from Android or another game binary.

## Runtime overlay

The generic prefill token format handles uppercase and lowercase rows. The
French overlay replaces the helper at `$C7:4630` with a compatible decoder that
adds token class `$C0-$DF` for the French fourth row. It also replaces the three
8-byte records at `$C7:46D0` with the French JSON data.

The Name Entry hook at `$C7:5039`, stock selector/insertion calls and all ordinary
editing handlers remain owned by `name_entry_prefill`. The fourth row itself,
its glyphs and its navigation remain owned by `french_name_entry_extended`.

## Validation

Runtime validation is complete on a clean USA ROM with the composed dependency
stack:

- `Randy`, `Prim`, `Popoï` appear initially;
- `ï` renders and is inserted as a real editable Name Entry character;
- deletion, replacement and confirmation behave exactly like manual input;
- the four-row French selector remains aligned and navigable.

A temporary diagnostic also put `Popoï` in the first/`boy` slot and was
runtime-validated, proving the fourth-row `ï` path works immediately on the
first Name Entry screen. That diagnostic value is not canonical data and is not
kept in the component or release patches.
