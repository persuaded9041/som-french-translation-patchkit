# Shop / forge text

`assets/shop_text.json` contains nine stock response strings used by the
shop/forge code.  They are not part of the normal `$C9/$CA` event tables and
were therefore absent from the first repository-wide inventory.

## Storage and execution

The strings live as a contiguous mini-event pool at `$D9:FE20-$FEF3`.  Each
record has the same stock script wrapper:

```text
$7F $52 <stock encoded text> $00
```

The bank-C0 shop/forge code loads one of nine 16-bit D9 pointers into `X`.
The display paths at `$C0:7EA6` and `$C0:7FB9` then set the live event bank
`$1D03` to `$D9`, copy `X` to `$1D01`, and invoke the stock event engine at
`$C0:0092`.

The extractor derives the record pointers from those actual `LDX #$xxxx` code
references rather than treating `$D9:FE20` as an arbitrary text address.  It
also validates both event-dispatch sequences and the physical contiguity of the
nine mini-scripts.

## Canonical asset

The root extractor writes:

```text
assets/shop_text.json
```

The JSON intentionally contains only stable IDs and readable clean-USA source
text.  Script prefixes, pointers and terminators are structural data recovered
from the reference ROM.

This family is source-only for now. Each source string ID is the address of its first text byte (for example `$D9:FE22`), while the two-byte mini-event wrapper remains structural. A `shop_text_french.json` file will be added only when this family is actually translated.

## Validation

`tools/check_text_roundtrip.py` verifies:

- all nine code references;
- both D9 event-dispatch paths;
- all nine mini-event records;
- the complete 212-byte `$D9:FE20-$FEF3` script pool byte-for-byte.
