# French editable default player-name prefill

French content overlay for `name_entry_prefill`. It proposes the validated
French default names while leaving the normal Name Entry editor fully active:
the player may erase, replace or accept each proposed name.

## Dependencies and ownership

This component requires both `name_entry_prefill` and
`french_name_entry_extended`; their dependency on `name_entry_extended` is
resolved transitively by the root builder.

Ownership remains deliberately split:

- `name_entry_prefill` owns the one-shot Name Entry hook at `$C7:5039` and the
  stock insertion-path integration;
- `french_name_entry_extended` owns the four-row French keyboard, glyphs and
  navigation;
- this overlay owns only the French-capable prefill helper and French default
  records.

It allocates no private WRAM. Like the generic helper, it uses `$A1CD` only as a
transient loop counter and clears it before returning.

## Canonical input

`assets/name_entry_defaults_fr.json` is the only source of the French default
names:

```json
{
  "boy": "Randy",
  "girl": "Prim",
  "sprite": "Popoï"
}
```

These names are authored component data, not generated output and not extracted
from Android. Each record is 8 bytes (one length byte plus at most seven token
slots), so the prefill format accepts at most 7 characters even though the
editor accepts up to 9.

The fourth-row character mapping is read from the canonical extension-row asset
owned by `french_name_entry_extended`; no duplicate accented alphabet is stored
here.

## ROM changes

Built against the clean USA ROM, the standalone IPS contains only this overlay:

- `$C7:4630-$46B1` (`0x074630-0x0746B1`): 130-byte French-capable prefill helper;
- `$C7:46D0-$46E7` (`0x0746D0-0x0746E7`): three 8-byte French default-name records.

When composed, `$C7:4630-$46A0` intentionally replaces the generic helper and
`$C7:46D0-$46E7` replaces the generic records. The extra helper bytes
`$C7:46A1-$46B1` occupy otherwise unused clean-ROM space.

The token classes are:

- `$00-$1F`: uppercase row;
- `$80-$9F`: lowercase row;
- `$C0-$DF`: French fourth row.

For the fourth row the helper reads the live selector base at `$C7:5019`
(`$50` under `french_name_entry_extended`) and adds `$30`, yielding selector
state `$80`. The existing `$C7:50E0` / `$C7:5124` Name Entry routines still
perform glyph selection and insertion.

`build_patch.py` is the executable source for the helper and records. There is
no second ASM binary source to keep synchronized.

## Build and validation

Standalone overlay build:

```bash
python3 components/french_name_entry_prefill/build_patch.py \
  "Secret of Mana (USA).sfc" \
  -o /tmp/french_name_entry_prefill.ips
```

The standalone IPS is intentionally not usable by itself at runtime because its
declared dependencies provide the hook and fourth-row keyboard. Use the root
builder to compose the dependency stack.

The complete four-component Name Entry stack is runtime-validated: `Randy`,
`Prim`, and `Popoï` appear as editable defaults; `ï` follows the real fourth-row
insertion path; deletion, replacement, confirmation and four-row navigation
remain normal. A temporary first-screen `Popoï` diagnostic used during runtime
validation is not canonical data and is not retained.
