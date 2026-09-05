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
- `translations/dialogues_french.json`: currently empty, ready for the future
  dialogue translation phase.

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

The first implemented mapping is the new-game intro. Android
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

The `scrtxt` parser is intentionally generic; only the ID-to-SNES mapping is
intro-specific for now. Additional Android dialogue/script mappings should be
added incrementally after their correspondence with the SNES source inventory is
established.
