# Translation sources

The repository separates **clean-ROM source extraction** from **language data**.

## Layout

```text
assets/          canonical text extracted from the clean USA ROM
translations/    sparse language files written by translators
```

The source files never contain translated text. French files are named after the
source asset with the `_french` suffix, for example:

```text
assets/interface_text.json
translations/interface_text_french.json
```

Translation JSONs are sparse: only entries that are actually translated need to
be present. This avoids copying thousands of unchanged English strings merely to
create a new language file.

## Stable text IDs

Every source element has a globally unique ID derived from its stock position.
For ordinary uncompressed data the ID is its canonical SNES HiROM address:

```text
C0:33F0
CA:98E1
D9:FE22
```

No secondary semantic key is stored in canonical assets: the position-derived
`id` is the single identity used to bind translations. Human-readable grouping
is provided only by the surrounding `group`/`category` structure where useful.

The startup/title arrangement is compressed, so an individual string has no
stable byte address in the physical compressed stream. Its ID therefore uses the
compressed block address plus its offset in the deterministic decompressed
arrangement:

```text
C7:B480+09F9
```

This is the only current source-ID form that is not a direct address.

A target-language-only addition has no clean-ROM position. Such entries use the
explicit `new:` namespace. The current example is:

```text
new:opening.credit.translation
```

`new:` IDs are additions, not source strings, and are deliberately exceptional.

## French JSON format

A translation file identifies its source asset and groups the translated subset:

```json
{
  "format_version": 1,
  "language": "fr",
  "source_asset": "interface_text.json",
  "groups": [
    {
      "group": "name_entry.help",
      "entries": [
        {
          "id": "C0:3584",
          "text": "Choisissez une lettre avec la Croix Directionnelle."
        }
      ]
    }
  ]
}
```

The clean English `source` remains only in `assets/`. Builders verify that every
translation ID exists in the declared source asset before using it.

## Existing migrated translations

The validated translations that previously lived in component CSV/BIN files are
now centralized as:

- `translations/interface_text_french.json`: component 02 Name Entry help and
  component 03 GAME SELECT/GAME FILE help;
- `translations/menu_text_french.json`: component 03 GAME SELECT/GAME FILE labels,
  including the two direct `L -> N` level-prefix writes;
- `translations/opening_text_french.json`: component 04 prologue and five-credit
  presentation (four translated stock credits plus the French-only translation
  credit);
- `translations/intro_event_french.json`: the eight validated component 05 intro
  paragraphs;
- `translations/dialogues_french.json`: the runtime-validated baseline is 8
  Android-derived formatted text tokens across `$0107`, `$010E`, `$0116`, `$0117`,
  `$0118` and `$011D`. `$010F` adds two text tokens plus one generated `\f` page
  marker, compiled by component 08 to the runtime-validated `WAIT $00` +
  `TEXT_CLEAR` transition. The current candidate refines its placement to a
  sentence-aware 3+1 layout.

The other extracted families intentionally have no French file yet; no new text
was translated as part of the extraction/migration work.

## Validation

`tools/check_text_roundtrip.py` verifies both the clean-ROM extraction and the
translation bindings. It also checks that source IDs are globally unique across
all canonical assets.


## Legacy source formats

The component audit found no remaining CSV or component-local translated-prose
BIN input. Original upstream translation resources may live under
`sources/<platform>/` (currently `sources/android/scrtxt_fr.bin`). The remaining
component-local `.bin`/`.txt` files are non-prose resources (Mana Tree graphics
and the naming-screen character repertoire). Run
`python3 tools/check_text_source_hygiene.py` to enforce this separation.

## Android upstream sources

Where an original French Android resource is available, it lives under
`sources/android/` and is treated as an **upstream translation source**, not as a
component-local build asset.

The intended flow is:

```text
sources/android/*
        ↓  tools/import_android_text.py
translations/*_french.json
        ↓  component builders
SNES IPS patches
```

The first implemented translation import is the new-game intro. Android
`sources/android/scrtxt_fr.bin` IDs 3445-3452 map, in order, to the eight
position-derived IDs in `assets/intro_event.json`. Android line breaks and
incidental leading/trailing whitespace are normalized because SNES page/line
layout is owned separately by
`components/05_intro_vwf_french/assets/text/intro_layout.json`.

Regenerate it with:

```bash
python3 tools/import_android_text.py --only intro
```

or verify synchronization with:

```bash
python3 tools/import_android_text.py --only intro --check
```

Dialogue work adds `sources/android/scrtxt_en.bin` as the matching bridge.
Reviewed SNES <-> Android correspondence is kept separately under
`mappings/android/`; clean-USA `assets/` and original Android binaries remain
unchanged. The first `dialogues_pilot.json` checkpoint contains only seven
very-high-confidence English anchors and explicit ambiguous examples. It does
not feed component 08 yet.

A further structural constraint is now known: French localization can use IDs
that are empty in the English container as continuation slots. Therefore the
future importer must align a SNES text to an Android **English anchor interval**
before collecting its French localized slots; it must not blindly read only the
French string at the matched English ID. See `docs/ANDROID_TEXT_ALIGNMENT.md`.

Regenerate/check the research-only pilot with:

```bash
python3 tools/import_android_text.py --only dialogue-pilot
python3 tools/import_android_text.py --only dialogue-pilot --check
```

The `scrtxt` parser remains generic. Five manually reviewed dialogue batches
validated scene/subscene ordering, localization-slot merging, placeholders,
duplicate handling and genuine local reorder cases. A conservative whole-dialogue
aligner is now available:

```bash
python3 tools/import_android_text.py --only dialogue-auto
python3 tools/import_android_text.py --only dialogue-auto --check
```

It writes `mappings/android/dialogues_auto.json` plus
`mappings/android/dialogues_unmapped.csv`. The current pass maps 1,471 / 1,838
semantic dialogue source IDs (80.0%) and leaves 367 unresolved rather than
forcing weak matches. Whole-game matching remains separate from SNES layout.
The historical `$0107` layout checkpoint is reproduced under `mappings/android/`
with `--only dialogue-format-pilot --rom <clean-USA-ROM>`. The six-event
runtime-validated baseline is reproducible with `--only dialogue-format-batch1`.
The `$010F` sentence-aware extra-page checkpoint is runtime-validated and remains
reproducible with `--only dialogue-format-page-pilot`. The current
`translations/dialogues_french.json` is generated by `--only dialogue-format-batch2`: 27
explicit complete events / 37 formatted source tokens, with an extra page allowed
only for `$010A`, `$010F`, `$013C` and `$014B`. Batch generation still aborts
rather than emitting a mixed-language scene when any selected semantic source ID
is not confidently mapped or cannot be formatted safely.
