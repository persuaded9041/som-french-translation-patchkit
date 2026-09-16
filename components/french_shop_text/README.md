# french_shop_text — French D9 shop / forge responses

Translates the nine short shop/forge response mini-events stored in the stock
`$D9:FE20-$FEF3` pool.  This is a text/data component only: it does not widen parser ownership.
Standalone, the messages keep the stock fixed-width renderer; in aggregate with
`vwf_ui`, the separately gated Shop `$A9` backend renders the same stock-decoded
rows with VWF.

## Canonical inputs

- `assets/shop_text.json` — clean-USA source extraction and stable source IDs;
- `recipes/android/shop_text_mapping.json` — reviewed Android identity/provenance
  with no French prose;
- `translations/shop_text_french.json` — six direct Android-FR payloads;
- `translations/shop_text_reviewed_overrides.json` — three explicitly reviewed
  SNES adaptations.

The builder verifies every `direct` translation against the original Android
EN/FR binary tables before insertion.  Reviewed adaptations stay in their own
JSON and are never hard-coded in Python.

## Runtime / storage model

Every record remains a tiny event script:

```text
$7F $52 <text> $00
```

The nine records are rebuilt contiguously from `$D9:FE20`; the nine stock
`LDX #pointer` references in bank C0 are updated to the new record starts.  The
translated pool is currently **179 / 212 bytes**, so no relocation is required.

These D9 scripts execute through the event-engine parser but are intentionally
outside `vwf_dialogues`' bank gate. The component therefore installs the
byte-identical shared `dialogue_french` glyph span and event-context DTE router
so French direct glyphs decode correctly. If `vwf_ui` is installed, its exact
Shop `$A9` identity renders these rows through the shared VWF backend after the
stock parse; no private parser mode or extra capacity is enabled.

The validated parser-safe line budget remains **28 visible characters**. The
builder rejects line breaks and any translated response over that limit, even
when the aggregate build will render the row proportionally.

## Build

```bash
python3 build.py "Secret of Mana (USA).sfc" french-shop --combine
```

Use `tools/text/generate_shop_text_preview.py` to generate the review HTML.
