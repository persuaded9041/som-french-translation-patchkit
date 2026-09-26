# Extended player-name entry

Generic, localization-independent Name Entry foundation. It owns the functional
9-character extension and a three-row keyboard; it owns no French prose or
French glyph data.

## Runtime changes

- raises the maximum player-name length from 6 to **9** at `$C0:319C`;
- reuses the former stock Name Entry resource area at `$C0:3583-$35AE` for
  compact three-row Up/Down handlers;
- relocates the character/help resource from `$C0:3583` to `$E4:4000`;
- installs the private three-row layout at `$C7:4E00-$4E6A`;
- redirects the selection lookup to the relocated `$E4` resource;
- keeps the stock initial selector `$60` and wraps only across `$60/$70/$80`
  (uppercase/lowercase/symbols).

No private WRAM is allocated. `french_name_entry_extended` deliberately
overrides the navigation/layout/resource tail to add a fourth `$50` row.

## Canonical inputs

- `assets/naming_characters.txt` — uppercase/lowercase/symbol rows;
- clean USA ROM — stock English help text and expected stock bytes;
- `src/patch_data.py` — emitted machine-code/data payloads.

`src/*.asm` is the readable 65C816/data representation used for maintenance; it
is not a second generated-input path.

The stock English help is extracted directly from the clean USA ROM. The only
functional wording change is `6 LETTERS` -> `9 LETTERS`; the validated relocated
copy also omits the decorative quotes around `ATTACK`.

## Relocated resource

`$E4:4000` contains three 60-byte rows followed by the English help and a
16-byte zero guard:

```text
+$0000  uppercase row
+$003C  lowercase row
+$0078  symbols row
+$00B4  English help
+...    16 zero guard bytes
```

Each row has 26 selectable entries plus generated framing/terminator cells. The
whole `$E4:4000-$41FF` window is reserved for the Name Entry stack so dependent
overlays can replace the tail safely.

## Dependency / build

This component has no dependencies. `french_name_entry_extended` and
`name_entry_prefill` depend on it.

```bash
python3 components/default_name_entry_extended/build_patch.py "Secret of Mana (USA).sfc"
python3 build.py "Secret of Mana (USA).sfc" name-entry
```

See `docs/MEMORY_MAP.md` for exact offsets.
