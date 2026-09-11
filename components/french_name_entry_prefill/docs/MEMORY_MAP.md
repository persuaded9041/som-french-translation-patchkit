# french_name_entry_prefill memory map

Dependent content/runtime overlay for `name_entry_prefill`.

- `$C7:4630-$C7:46B1` (`0x074630-0x0746B1`): French-capable prefill helper. Same stock insertion path as the generic helper, plus token class `$C0` for the fourth Name Entry row.
- `$C7:46D0-$C7:46E7` (`0x0746D0-0x0746E7`): three 8-byte French default-name records generated from `assets/name_entry_defaults_fr.json`.

The hook at `$C7:5039` remains owned by `name_entry_prefill`. The four-row keyboard, French glyphs and accented row remain owned by `french_name_entry_extended`.
