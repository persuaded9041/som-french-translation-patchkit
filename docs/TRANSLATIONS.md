# Translation sources

The repository separates **clean-ROM extraction**, **upstream localization sources**, **review/provenance recipes**, and **French payload data**.

## Layout and ownership

```text
assets/          optional reproducible caches extracted from the clean USA ROM
sources/         immutable upstream sources (currently Android EN/FR binaries)
recipes/         identity, provenance and structural/layout decisions
translations/    French payload JSON and fingerprint-validated generated caches
components/      code/layout only; no localized gameplay prose in Python/ASM
```

`assets/*.json` are convenient local caches, not canonical inputs: if absent, the relevant builder/check extracts them deterministically from the clean USA ROM. They never contain translated text.

French gameplay prose belongs in JSON/data sources, never in component code. `tools/text/check_source_hygiene.py` enforces the architecture and also scans component Python/ASM for multi-word localized prose copied from translation payloads.

## Stable text IDs

Every source element uses a position-derived identity. Ordinary uncompressed data uses a SNES HiROM address, for example:

```text
C0:33F0
CA:98E1
D9:FE22
```

Compressed opening strings use the compressed container address plus deterministic decompressed offset, for example `C7:B480+09F9`. Target-language-only additions use the explicit exceptional `new:` namespace, currently `new:opening.credit.translation`.

## French payload families

The main data files are:

- `translations/interface_text_french.json` — Name Entry, GAME SELECT/GAME FILE and Window Settings help plus reviewed translation-only Status characteristic labels;
- `translations/menu_text_french.json` — GAME SELECT/GAME FILE labels, runtime-validated Window Settings + Action Settings labels, and reviewed translation-only Status labels;
  GAME FILE IDs `C7:7398` / `C7:73AA` are the promoted `Sauvegardes` / `Graines de Mana`. Currency ID `C7:7394` remains the single text source for `PO`: `french_menus` derives dynamic currency glyph 0 from that JSON value while template glyph 1 remains resource-backed; the promoted spacing helper and `vwf_ui` GAME FILE backend contain geometry/routing only.
- `translations/opening_text_french.json` — opening prologue and startup credits;
- `translations/intro_event_french.json` — new-game intro paragraphs;
- `translations/text_resources_reviewed_overrides.json` — sparse, explicitly reviewed SNES-specific `$CA` resource wording layered over Android FR;
- `translations/french_resources_reviewed_literals.json` — reviewed fixed literals owned by `french_resources` (`GP -> PO`);
- `translations/shop_text_french.json` — six direct Android-FR D9 shop/forge responses;
- `translations/shop_text_reviewed_overrides.json` — three reviewed SNES-specific D9 adaptations;
- `translations/battle_text_reviewed_overrides.json` — reviewed battle/status SNES/JP adaptations, including the eight manually translated records without a solid Android equivalent;
- `translations/dialogues_manual_supplements.json` — small explicit manual dialogue exceptions/suppressions;
- `translations/dialogues_french.json` — fingerprint-validated generated local cache/review artifact for the frozen dialogue corpus;
- `translations/text_resources_french.json` — fingerprint-validated generated local cache/review artifact for the Android-derived `$CA` resource mapping.

The two generated cache files above are not canonical prose provenance. A normal build may reuse them only when their fingerprints match the canonical source/provenance inputs; otherwise they are regenerated and persisted automatically.

## Current dialogue state

Dialogue work remains frozen. **Menu/resource translation is also intentionally paused at this handoff** while work proceeds on the separate `french_gfx` component. Its first controller-button asset is runtime-validated and promoted. The untranslated menu/resource backlog remains future work and must not be silently resumed while `french_gfx` work continues:

- native menu/status translation-only rows still require explicit renderer promotion;
- `weapon_description` / `magic_description` remain unpromoted review families;
- no global dialogue audit should be restarted.

Previous dialogue baseline:

- 701/701 accepted playable events simulator-clean;
- 1959 translated carriers;
- Android identity 1798/1838 (97.8%); 40 deliberately unresolved semantic IDs;
- 0 errors / 0 warnings / 0 implicit runtime wraps;
- only the routing-audited unused/orphan events `$0269`, `$02DE`, `$0603` remain excluded.

Do not edit dialogue payloads or Android dialogue mapping as part of resource work.

## `$CA` resource localization

`french_resources` generates Android-backed resource translations from:

```text
assets/text_resources.json                 clean-USA identity/source cache
recipes/android/text_resources_layout.json reviewed identity/layout recipe
sources/android/systxt_en.bin              Android identity bridge
sources/android/systxt_fr.bin              Android French source
translations/text_resources_reviewed_overrides.json
```

`translations/text_resources_french.json` is the generated cache/review view of that process. Reviewed SNES wording belongs only in `text_resources_reviewed_overrides.json`; do not edit the generated cache as canonical input.

The current promoted component inserts 360 `$CA` resources and keeps the rebuilt resource blob inside the original 7315-byte allocation. Additional families require explicit provenance, encoding, size and renderer/layout review before promotion. See `docs/TEXT_RESOURCES.md`.

## Battle/status localization

`french_resources` also owns the localized content of `assets/battle_text.json`.
Identity and runtime strategy are reviewed in `recipes/android/battle_text_mapping.json`;
French mapped payload comes directly from Android `systxt_fr.bin`. The sparse
`translations/battle_text_reviewed_overrides.json` file contains only deliberate
SNES/JP adaptations. The eight formerly manual rows are now translated and
reviewed; there are no remaining `needs_manual_translation` payloads. The formerly
layout-pending `C0:62F3` also has its reviewed compact SNES adaptation in this
surcharge file.

## D9 shop/forge localization

All nine D9 response mini-events are now owned by `french_resources`; there is no `french_shop_text` component. Direct Android-FR payloads and reviewed SNES adaptations remain separate JSON inputs, with identity checks in `recipes/android/shop_text_mapping.json`.

## Validation

Run at minimum:

```bash
python3 tools/text/check_source_hygiene.py
python3 tools/text/check_roundtrip.py "Secret of Mana (USA).sfc" --scan-all-events
python3 tools/text/import_android_resources.py --check
```

For new `$CA` resource families, also run `tools/text/audit_resource_layout.py` and perform runtime review of the actual UI/context that displays each newly promoted family.
