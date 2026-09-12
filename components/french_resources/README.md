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

## Canonical inputs and generated review outputs

The normal standalone build regenerates the Android mapping and French payload
**in memory** from:

- `assets/text_resources.json` — clean-USA 513-resource source inventory;
- `mappings/android/text_resources_layout.json` — reviewed identity/layout recipe;
- `sources/android/systxt_en.bin` — Android identity layer;
- `sources/android/systxt_fr.bin` — Android French prose.

`mappings/android/text_resources_android.json` and
`translations/text_resources_french.json` are deterministic **generated review
artifacts** produced by `tools/import_android_resources.py`; neither is required
by the component builder.

Verify/regenerate them with:

```bash
python3 tools/import_android_resources.py --check
```

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
