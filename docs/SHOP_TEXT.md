# Shop / forge text

`assets/shop_text.json` contains nine stock response strings used by the
shop/forge code. They are not part of the normal `$C9/$CA` event tables.
The French implementation is owned by `french_shop_text`.

## Storage and execution

The strings live as a contiguous mini-event pool at `$D9:FE20-$FEF3`. Each
record has the same stock script wrapper:

```text
$7F $52 <encoded text> $00
```

The bank-C0 shop/forge code loads one of nine 16-bit D9 pointers into `X`.
The display paths at `$C0:7EA6` and `$C0:7FB9` then set the live event bank
`$1D03` to `$D9`, copy `X` to `$1D01`, and invoke the stock event engine at
`$C0:0092`.

The extractor derives the record pointers from those actual `LDX #$xxxx` code
references rather than treating `$D9:FE20` as an arbitrary text address. It
also validates both event-dispatch sequences and the physical contiguity of the
nine clean-USA mini-scripts.

## Canonical source and French provenance

The clean-ROM source cache is:

```text
assets/shop_text.json
```

Each source string ID is the address of its first clean-USA text byte (for
example `$D9:FE22`); the two-byte mini-event wrapper remains structural.

French data is split by provenance:

- `translations/shop_text_french.json` — six direct Android-FR payloads;
- `translations/shop_text_reviewed_overrides.json` — three explicitly reviewed
  SNES adaptations;
- `recipes/android/shop_text_mapping.json` — Android identity/provenance only,
  with no localized French prose.

The builder verifies every `direct` French entry against the original Android
EN/FR string tables. The three reviewed adaptations are deliberately separate:

- `$D9:FE4B`: `Vous n'avez plus de place !`;
- `$D9:FEB7`: `Il faut une sphère de plus !`;
- `$D9:FED3`: `Cette arme est au maximum !`.

## Renderer and capacity

These mini-events execute through the stock event parser but are outside the
`vwf_dialogues` bank gate, so their renderer remains the stock fixed-width
8-pixel path. `french_shop_text` installs the same byte-identical
`dialogue_french` glyph span and event-context DTE router used by the dialogue
components so direct French glyphs decode correctly in bank D9 without turning
this UI family into VWF.

The validated stock budget is **28 visible characters / 224 px**. The builder
rejects line breaks or a response over 28 characters. The current French pool
compresses to **179 bytes** including wrappers and terminators, leaving **33
bytes free** inside the original 212-byte allocation; no relocation is used.
The nine bank-C0 `LDX` operands are rewritten to the rebuilt contiguous record
starts.

## Validation

`tools/text/check_roundtrip.py` continues to verify the clean-USA family:

- all nine code references;
- both D9 event-dispatch paths;
- all nine mini-event records;
- the complete 212-byte stock `$D9:FE20-$FEF3` script pool byte-for-byte.

`french_shop_text` adds build-time validation of Android provenance, fixed-width
capacity, DTE encodability, pool size and reference rewriting.

Generate the review sheet with:

```bash
python3 tools/text/generate_shop_text_preview.py \
  "Secret of Mana (USA).sfc" -o /tmp/shop_text_french_preview.html
```
