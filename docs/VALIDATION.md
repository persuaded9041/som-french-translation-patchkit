# Validation state

## Runtime-validated standalone components

- Japanese Mana Tree restoration.
- 9-character Name Entry with French help text and four rows.
- French GAME SELECT.
- French opening/credits with integration-safe helper relocation.
- French intro VWF.

Standalone IPS SHA-256 values:

- Japanese Mana Tree: `424a15e1f08be4207054d99c83d0f69a5ec5cf2d9acf3160d7b35eeb35060027`
- 9-character names + French accent row: `31cdc4c829130194a54020c87c2d1bb56cc908372d2024aac1aaebb230196f9f`
- GAME SELECT: `ede4084d40087fbaeb6622edeb9e976e4a70477ff1ba06cc5bafd610fb5b86d2`
- French opening: `ba9145ff516e48dfe838c1258bd9aa1841be6a2aa4c85e75af663f018313c14b`
- French intro VWF: `36d419d9ad83e98cbc0b34ff41f11ef2941992ac223dc1cfc4d8b21ccdf37758`

## Name Entry runtime checkpoint

The current `02_9char_names` checkpoint was validated after iterative runtime
fixes. Confirmed behavior includes:

- correct four-row layout;
- cursor starts on uppercase and navigates exactly four rows;
- selected character matches the visible row;
- no bottom-right graphical corruption;
- French `$D4-$E0` accents display and can be entered;
- accented player names render correctly when later inserted into normal game dialogue;
- French CSV help text displays correctly.

## Reproducibility / compatibility

- all five builders reproduce their packaged IPS files byte-for-byte;
- `verify.py` validates the shared French charset and overlap rules;
- all 31 non-empty combinations build without undeclared functional collision.

The newly regenerated **all-components preset** is statically verified against
those rules. It should still receive a normal runtime smoke test after integration
before being treated as a frozen combined checkpoint.
