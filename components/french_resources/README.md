# french_resources — French resources

Owns the reviewed French non-dialogue text resources that belong to game content rather than renderer geometry. This now includes the `$CA` resource table/blob, the nine `$D9` shop/forge response mini-events, and the two fixed shop currency literals.

## Ownership

This component translates:

- magic names and Mana spirit names;
- weapon, helmet, armor, accessory and item/special names;
- enemy and location names;
- the nine validated top-level Ring Menu labels (`$0C6-$0CE`);
- the nine shop/forge response mini-events in `$D9:FE20-$FEF3`;
- the two shop currency literals (`C7:7B6A` total money and `D0:D894` merchandise price), translated `GP -> PO`.

It does **not** own dialogue events or UI VWF rendering. `vwf_ui` owns presentation only. The D9 responses retain the stock event parser and the validated 28-visible-character capacity even when `vwf_ui` renders them proportionally through tag `$A9`.

## Canonical inputs and provenance

### `$CA` resources

- `assets/text_resources.json` — optional clean-USA extraction cache;
- `recipes/android/text_resources_layout.json` — reviewed identity/layout recipe;
- `sources/android/systxt_en.bin` / `systxt_fr.bin` — Android identity/French source;
- `translations/text_resources_reviewed_overrides.json` — reviewed SNES-specific `$CA` adaptations;
- `translations/text_resources_french.json` — fingerprint-validated generated cache, never canonical provenance.

### D9 shop/forge responses

- `assets/shop_text.json` — clean-USA source extraction and stable IDs;
- `recipes/android/shop_text_mapping.json` — reviewed Android identity/provenance;
- `translations/shop_text_french.json` — six direct Android-FR payloads;
- `translations/shop_text_reviewed_overrides.json` — three reviewed SNES adaptations.

Every direct shop translation is rechecked against the original Android EN/FR binary tables. The three reviewed adaptations remain separate JSON data; no localized French shop prose is hard-coded in Python.

### Fixed literals

`translations/french_resources_reviewed_literals.json` contains the two reviewed `GP -> PO` replacements. Their clean-USA source bytes and fixed length are validated before insertion.

## Storage/runtime architecture

The complete 513-entry pointer table at `$CA:0800-$0C01` is rebuilt in resource-ID order. The text blob begins at `$CA:98E1` and must remain inside the original 7,315-byte allocation through `$CA:B573`; no relocation is used. The current reviewed blob is 7,103 bytes and ends at `$CA:B49F`.

The nine D9 response scripts remain tiny stock event scripts of the form `$7F $52 <text> $00`. They are rebuilt contiguously from `$D9:FE20`; the nine stock bank-C0 `LDX #pointer` operands are updated to the rebuilt starts. The translated pool is 179 / 212 bytes, leaving 33 bytes free, so no relocation is used.

Standalone French use installs the same byte-identical `dialogue_french` glyph span and event-context DTE router used by the dialogue components. This single installation now serves both the `$CA` resources and D9 shop text.

## Extending translated resource families

The Android mapping already contains 72 `weapon_description` and 42
`magic_description` resources, but these families are not yet promoted by the
component. Additions must be reviewed in the actual target UI before extending
`DEFAULT_CATEGORIES` or otherwise selecting new IDs. The conservative current
layout audit classifies weapon descriptions as 38 inside the stock envelope / 34
geometry review and magic descriptions as 2 inside / 40 geometry review. Size
alone is therefore not sufficient evidence.

Keep new wording data-driven: Android-backed text remains generated from the
existing mapping inputs, while deliberate SNES-specific adaptations belong in
`translations/text_resources_reviewed_overrides.json`. Never add localized prose
to `build_patch.py` or ASM. `tools/text/check_source_hygiene.py` enforces that
constraint.

## Build

```bash
python3 build.py "Secret of Mana (USA).sfc" french-resources --combine
```

No separate `french_shop_text` component exists and no `french_shop_text.ips` is generated. `tools/text/generate_shop_text_preview.py` remains the review-sheet generator for the D9 family.

See `docs/MEMORY_MAP.md`, root `docs/TEXT_RESOURCES.md`, and root `docs/SHOP_TEXT.md` for exact write maps and provenance.
