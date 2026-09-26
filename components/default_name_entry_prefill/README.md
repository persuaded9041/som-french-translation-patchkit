# Editable default player-name prefill

Prefills the extended Name Entry editor with configurable default names while
leaving the ordinary editor fully active. The player can erase, replace or
accept the proposed name exactly as if the characters had been entered by hand.

## Dependency

`name_entry_prefill` **requires `name_entry_extended`**. The dependency is
intentional: the default names contain lowercase characters, and the clean USA
ROM exposes only the stock uppercase Name Entry row. The generic extended
component owns lowercase/grid support; this component owns only the prefill
mechanism and its JSON data.

Selecting `name_entry_prefill` through the root builder automatically selects
`name_entry_extended` as well.

## Canonical data

`assets/name_entry_defaults.json` is the only source of default-name text for
this component:

```json
{
  "boy": "Randi",
  "girl": "Primm",
  "sprite": "Popoi"
}
```

The names are intentionally authored directly; they are not extracted from
Android or another localization. Each record has one length byte plus seven
token slots, so this prefill format accepts at most 7 characters even though
the extended editor itself accepts up to 9. The current defaults fit without
truncation. `french_name_entry_prefill` is a separate dependent overlay with
its own JSON; the generic component remains the sole owner of these USA
defaults.

## Runtime architecture

The Name Entry initialization at `$C7:5039` ends by clearing `$A1CC`, the
current name length. `name_entry_prefill` replaces only that final
`STZ $A1CC / RTL` with a one-shot jump to `$C7:4630`.

The helper does not invent a second name editor and does not write a finished
name directly into save/player structures. Instead, each configured character
is fed through the existing Name Entry selection/insertion path:

- `$C7:50E0` resolves the selected grid cell to the same glyph tile pair used by
  manual input;
- `$C7:5124` inserts/draws that pair in the editable name field;
- `$A157` and `$A1CC` are advanced exactly as the normal input handler does.

The original grid cursor is restored when the prefill is complete. `$A1CD` is
used only as a transient loop counter and is cleared before returning; no
persistent private WRAM is allocated. The proposed text therefore remains
normal editable Name Entry state: deletion and ordinary confirmation keep
using the game's existing handlers.

`build_patch.py` emits the helper with the repository's small label-aware
65C816 assembler. `src/prefill.asm` is the readable maintenance mirror of that
instruction sequence, not a second binary source.

## Validation status

Runtime validation is complete for the dependency-composed generic stack:
`name_entry_extended + name_entry_prefill` shows the three-row keyboard with
aligned selection and editable `Randi` / `Primm` / `Popoi` defaults. The
French defaults are intentionally owned by the separate
`french_name_entry_prefill` overlay.
