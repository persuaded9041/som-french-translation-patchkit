# Battle text extraction

`assets/battle_text.json` contains the stock battle/status message pool in bank
`$C0`.

The engine has an **88-entry 16-bit pointer table** at `$C0:5DBB`. The table
ends exactly where the physical string pool begins at `$C0:5E6B`. The pool runs
to `$C0:6380` and contains **109 null-terminated records / 1302 bytes** including
terminators.

All 88 table pointers resolve to distinct record starts. The remaining **21
records** are not missing or unused padding: battle code addresses them directly
instead of through the table. The extractor therefore follows the physical pool,
not only the 88 indexed entries.

Most records contain ordinary stock text. Three records contain low control
bytes; the JSON preserves those bytes as explicit hexadecimal placeholders:

- `Cave{2A}in`
- `{50}`
- `{51}`

This keeps the source representation readable without pretending that the
control bytes are printable glyphs.

`tools/check_text_roundtrip.py` validates both the 176-byte pointer table and
the complete 1302-byte physical pool against the clean USA ROM.
