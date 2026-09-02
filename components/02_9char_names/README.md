# 02 — 9-character names + French accent row

This standalone component extends Secret of Mana's Name Entry screen while keeping the clean unheadered USA ROM as its only ROM dependency.

## Behavior

- Names can contain up to **9 characters** instead of 6.
- Four selectable rows are displayed:
  1. `ABCDEFGHIJKLMNOPQRSTUVWXYZ`
  2. `abcdefghijklmnopqrstuvwxyz`
  3. digits / punctuation / symbols
  4. `Çàâçéèêëîïôùû`
- The cursor opens on the uppercase row and moves across all four rows.
- Blank cells on the accent row are encoded as `$80` spaces and count toward the 9-character limit.
- Accented characters use the native Secret of Mana codes `$D4-$E0`.
- The lower help text is sourced from `assets/naming_help.csv`.

## Build

```bash
python3 build_patch.py "Secret of Mana (USA).sfc" -o build/patch.ips
```

Required base ROM SHA-256: `4c15013131351e694e05f22e38bb1b3e4031dedac77ec75abecebe8520d82d5f`.

## Editable sources

- `assets/naming_characters.txt`: four visible character rows.
- `assets/naming_help.csv`: French help lines.
- `src/patch_data.py`: exact machine-code/data payloads consumed by the Python builder.
- `src/*.asm`: readable 65C816/data representation of the same changes.
- `docs/MEMORY_MAP.md`: ROM allocations and hooks.

The Python builder does not require an external 65C816 assembler; the ASM files are maintained as readable source maps of the emitted changes.

## French charset

The naming screen uses only the naming-safe part of the shared French charset:

```text
$D4 Ç  $D5 à  $D6 â  $D7 ç  $D8 é  $D9 è  $DA ê
$DB ë  $DC î  $DD ï  $DE ô  $DF ù  $E0 û
```

`$E1-$E5` (`À É Î Œ œ`) are not installed by this module because those font slots are used by original Name Entry graphics.

## Name Entry resource

The generated resource is relocated to `$E4:4000`:

```text
+$0000  uppercase row     60 bytes
+$003C  lowercase row     60 bytes
+$0078  symbols row       60 bytes
+$00B4  accent row        60 bytes
+$00F0  French help text  variable
+...    16 zero guard bytes
```

Each row contains 30 two-byte cells. The builder supplies framing/terminator cells automatically; the editable files contain only the useful text/characters.
