# french_resources — French resources

Owns the reviewed French non-dialogue text resources that belong to game content rather than renderer geometry. This now includes the `$CA` resource table/blob, the validated weapon descriptions, the 42 full-width magic lower-panel `Nom : description` rows, the nine `$D9` shop/forge response mini-events, the two fixed shop currency literals, and the reviewed `$C0` battle/status text content.

## Ownership

This component translates:

- magic names and Mana spirit names;
- the 42 complete Android-FR magic lower-panel rows consumed by the dedicated `vwf_ui` 3x480px renderer;
- weapon, helmet, armor, accessory and item/special names;
- the 72 weapon-description resources, with the Android family separators mapped correctly and the validated SNES 30-cell segment geometry;
- enemy and location names;
- the nine validated top-level Ring Menu labels (`$0C6-$0CE`);
- the two reviewed system messages (`$1FF-$200`);
- reviewed battle/status text from `assets/battle_text.json` (0 pending manual translations / 0 pending layout adaptations);
- the nine shop/forge response mini-events in `$D9:FE20-$FEF3`;
- the shop-price currency literal (`D0:D894` merchandise price), translated `GP -> PO`.

It does **not** own dialogue events or UI VWF rendering. `vwf_ui` owns presentation only. The D9 responses retain the stock event parser and the validated 28-visible-character capacity even when `vwf_ui` renders them proportionally through tag `$A9`. Battle/status content is displayed through the separate exact `$AC` battle-banner backend in `vwf_ui`.

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

### Battle/status text

- `assets/battle_text.json` — clean-USA 109-record physical pool;
- `recipes/android/battle_text_mapping.json` — reviewed SNES/Android identity and runtime strategy;
- `sources/android/systxt_en.bin` / `systxt_fr.bin` — Android identity/French payload;
- `translations/battle_text_reviewed_overrides.json` — eleven reviewed SNES/JP adaptations.

The 8 records that lacked an Android equivalent now have reviewed JP-derived French translations in the surcharge file.
`C0:62E2` is now the reviewed JP-derived `Rétablissement échoué !`. `C0:62F3`
is a reviewed compact adaptation: the stock runtime still supplies the dynamic
subject and the stored suffix is ` s'est rétabli !`. The dormant vanilla calls
for both records remain intentionally unfixed; see `docs/BATTLE_TEXT.md`.

### Fixed literals

`translations/french_resources_reviewed_literals.json` contains the reviewed shop-price `D0:D894` `GP -> PO` replacement. The Status total-money literal `C7:7B6A` is owned by `french_menus`.

## Storage/runtime architecture

The complete 513-entry pointer table at `$CA:0800-$0C01` is rebuilt in resource-ID order. The text blob begins at `$CA:98E1` and must remain inside the original 7,315-byte allocation through `$CA:B573`; no relocation is used. The current reviewed blob is 7,171 bytes, leaving 144 bytes inside the stock allocation.

The nine D9 response scripts remain tiny stock event scripts of the form `$7F $52 <text> $00`. They are rebuilt contiguously from `$D9:FE20`; the nine stock bank-C0 `LDX #pointer` operands are updated to the rebuilt starts. The translated pool is 179 / 212 bytes, leaving 33 bytes free, so no relocation is used.

Battle/status prose does require relocation. The 107 text records are rebuilt in
expanded bank `$EE` from `$EE:6000`, with a reserved ceiling at `$EE:6FFF`; the
current relocated pool is 1573 bytes. The stock `$C0:637D/$637F` event scripts stay
in place. All pointer-table and direct code references are rewritten to the relocated
offsets, while `vwf_ui` remains responsible only for the exact banner presentation path.

Standalone French use installs the same byte-identical `dialogue_french` glyph span and event-context DTE router used by the dialogue components. This single installation now serves both the `$CA` resources and D9 shop text.

## Weapon / magic descriptions — runtime-validated

### Weapon descriptions

The 72 weapon descriptions are promoted in the ordinary `$CA` resource blob.
Android inserts one separator after each family of nine weapons; the mapping now
skips those eight separators instead of treating the Android range as 72
contiguous IDs. Runtime validation proved the SNES renderer consumes fixed
30-character segments separated by `$7F`, so non-empty Android prose is collapsed
to one logical sentence, given the stock one-cell inset, then sliced at exact
30-character boundaries. The 12 blank descriptions preserve their stock blank
payload byte-for-byte.

### Magic lower-panel descriptions

The stock `13+24`-cell two-segment layout cannot preserve the complete Android-FR
wording. The 42 complete `Nom : description` rows therefore live in expanded bank
`$ED:9200-$9F1F` as fixed 80-byte direct-glyph records. `MFV1` at
`$ED:9F20-$9F23` is the runtime source marker consumed by `vwf_ui`. The build
collapses Android layout whitespace only; it does not shorten wording. The widest
row is currently 445 px and the build enforces a 472 px ceiling for the validated
480 px renderer.

This component still owns **content only**. `vwf_ui` captures the stock-emitted
magic IDs, preserves stock unlock gating and renders the 3x480 px panel. When the
marker is absent, standalone `vwf_ui` falls back to the stock presentation.

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
