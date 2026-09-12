# french_resources — French `$CA` resource names

Rebuilds the reviewed French **name-family** resources in the stock 513-entry
non-event `$CA` text-resource table.

## Ownership

This component currently translates only these reviewed families:

- magic names;
- Mana spirit names;
- weapon names;
- helmets, armor and accessories;
- item/special names already present in the reviewed Android mapping;
- enemy names;
- location names.

It does **not** own dialogue events, descriptions, menu/status labels or UI VWF
rendering. No new object/item translation should be added during component
maintenance audits.

## Canonical inputs and local generated cache

The normal standalone build derives the Android mapping and French payload from:

- `assets/text_resources.json` — optional materialized cache of the clean-USA 513-resource inventory;
- `recipes/android/text_resources_layout.json` — reviewed identity/layout recipe;
- `sources/android/systxt_en.bin` — Android identity layer;
- `sources/android/systxt_fr.bin` — Android French prose.

`translations/text_resources_french.json` is a deterministic **local performance
cache/review artifact**, never canonical provenance. Its validity is tied to a
fingerprint of the clean ROM, extracted source inventory, reviewed layout recipe,
Android `systxt` inputs and generator code. A missing, stale or edited cache is
regenerated automatically and persisted for later builds.

`reports/android/text_resources_android.json` remains an optional review report and is
never consumed by the build. To materialize/refresh both review outputs explicitly:

```bash
python3 tools/text/import_android_resources.py "Secret of Mana (USA).sfc"
```

Deleting `translations/text_resources_french.json` or
`build/cache/text_resources_french.meta.json` is always safe; the next build recreates
them from canonical inputs.

## Storage/runtime architecture

The complete 513-entry pointer table at `$CA:0800-$0C01` is rebuilt in resource-ID
order. The text blob begins at `$CA:98E1` and must remain inside the original
7,315-byte stock allocation through `$CA:B573`; no relocation is used.

Translations reuse stock DTE pairs where safe. For standalone clean-USA use the
component also installs the byte-identical shared `dialogue_french` glyph span and
context-sensitive DTE router used by the dialogue components. Those writes are
intentional compatible overlaps in aggregate builds.

The current reviewed name-family build translates 349 resources, leaves three
`n°` enemy names stock because `°` conflicts with the ordinary `$CA` `$E6` DTE
boundary, and produces a 7,056-byte blob ending at `$CA:B470`.

See `docs/MEMORY_MAP.md` for exact writes and root `docs/TEXT_RESOURCES.md` for the
resource-family format/provenance.
