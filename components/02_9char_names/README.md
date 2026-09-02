# 02 — 9-character names + French accent row

This standalone component extends Secret of Mana's Name Entry screen while
keeping the clean unheadered USA ROM as its only ROM dependency.

## Runtime-validated behavior

- Names can contain up to **9 characters** instead of 6.
- Four selectable rows are displayed:
  1. `ABCDEFGHIJKLMNOPQRSTUVWXYZ`
  2. `abcdefghijklmnopqrstuvwxyz`
  3. digits / punctuation / symbols
  4. `Çàâçéèêëîïôùû`
- The cursor opens on the uppercase row and moves correctly across all four rows.
- Selecting a visible character inserts that exact character.
- Blank cells on the accent row are encoded as `$80`, i.e. **spaces**; they are
  selectable and count toward the 9-character limit.
- Accented characters selected here are stored with their real Secret of Mana
  codes `$D4-$E0`. They have been runtime-validated to appear correctly when the
  player's name is inserted into normal game dialogue.
- The lower help text is sourced from `assets/naming_help.csv`.

## Build

```bash
python3 build_patch.py "Secret of Mana (USA).sfc" -o build/patch.ips
```

Required base ROM SHA-256:

`4c15013131351e694e05f22e38bb1b3e4031dedac77ec75abecebe8520d82d5f`

Runtime-validated component IPS SHA-256:

`31cdc4c829130194a54020c87c2d1bb56cc908372d2024aac1aaebb230196f9f`

With the canonical repository sources, the builder reproduces that IPS exactly.

## Editable sources

- `assets/naming_characters.txt` — the four visible character rows.
- `assets/naming_help.csv` — the three French help lines.
- `src/patch_data.py` — exact machine-code/data payloads used by the builder.
- `src/*.asm` — commented 65C816/source-map representation of those changes.
- `docs/MEMORY_MAP.md` — ROM allocations and hooks.
- `docs/VERIFICATION.md` — static and runtime validation status.

The assembly files are intentionally human-readable documentation/source maps;
the Python builder emits the exact known-good bytes without requiring an
external 65C816 assembler.

## French charset

The naming screen deliberately uses only the **naming-safe** part of the shared
French charset:

```text
$D4 Ç  $D5 à  $D6 â  $D7 ç  $D8 é  $D9 è  $DA ê
$DB ë  $DC î  $DD ï  $DE ô  $DF ù  $E0 û
```

These glyphs come from `shared/french_charset` and are the same canonical
characters used by the other French text components.

`$E1-$E5` (`À É Î Œ œ` in the full shared charset) are intentionally **not**
installed by this module because those font slots are still used by original
Name Entry graphics. This avoids the graphical corruption observed during
runtime testing.

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

Each row contains 30 two-byte cells. The builder supplies framing/terminator
cells automatically; the editable files contain only the useful text/characters.
