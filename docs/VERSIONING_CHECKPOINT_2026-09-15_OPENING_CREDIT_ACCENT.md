# Versioning checkpoint — opening credit `É` overlay + synchronized fade

Date: 2026-09-15  
Status: **runtime-validated / promoted**

This checkpoint promotes the final `french_opening` startup-credit treatment.
It is based on the clean archive that was authoritative over GitHub.

## Promoted behavior

- opening-font tile `$7A` is restored to the stock `Z`;
- `Traduction : E.CHAUVIRÉ` uses ordinary `E` on the normal credit row;
- acute tile `$7D` is rendered on the tile row immediately above;
- a two-record wrapper at decompressed title-code CPU `$BCED` renders overlay +
  normal row through stock `$8820`;
- a final blank overlay record clears the accent row;
- the credit-only CGRAM HDMA segmentation is `120+7+16+1` rather than
  `120+15+8+1`, extending the same stock fade band upward by one tile row while
  preserving the 144-scanline total and lower boundary;
- stock `$8B5D`, 31-step fade loops and 180-frame French dwell remain unchanged;
- arrangement remains a literal-only stock-format stream at `$EE:A000` loaded
  by stock `$C1:0014`;
- opening helper remains at `$EE:9000`;
- no `$EF` allocation was added.

## Runtime proof ladder

1. **Stage A:** two-row geometry only. Runtime result: accent correctly placed,
   fade absent, reproducing the historical behavior. Validated.
2. **Stage B:** only the credit-specific HDMA scanline split changed from
   `15/8` to `7/16`. Runtime result: accent retained correct placement and faded
   correctly with the credit. User verdict: **perfect**.

The corrected root cause is therefore spatial HDMA/CGRAM coverage: the stock
animated band covered only the normal 8-pixel credit row. The historical accent
was one tile row above and outside that band.

## Non-regression / build proof

The cleaned source was rebuilt after documentation cleanup. The resulting
standalone and combined patches are byte-identical to the runtime-approved
Stage B artifacts:

- `patches/french_opening.ips` SHA-256:
  `c7b0b0e8b821a6f9dbbfc6b4591c5ebada18c0df1a4320fb3b1dbd15010b2d27`
- `patches/all.ips` SHA-256:
  `74e66682ede9226cf5d14cbe681b8f917f4a4cbf87055403a888485889280079`

Compared with the pre-accent clean baseline, every standalone component IPS is
byte-identical except `french_opening.ips`; consequently only
`french_opening.ips` and aggregate `all.ips` differ. `intro_skip` and dialogue
patches are untouched.

Detailed reverse engineering: `OPENING_CREDIT_ACCENT_RESEARCH.md`.
