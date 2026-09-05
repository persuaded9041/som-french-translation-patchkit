# ROM text inventory

This document summarizes the canonical clean-USA text sources extracted at the
repository root. Detailed reverse-engineering notes are preserved in
`TEXT_RESEARCH_NOTES.md`; translation-file conventions are in `TRANSLATIONS.md`.

## Canonical root assets

| Asset | Stock family | Extracted units |
| --- | --- | ---: |
| `assets/dialogues.json` | component-08 event scripts | 713 events / 2162 text tokens |
| `assets/intro_event.json` | event `$0400`, owned by component 05 | 8 text parts |
| `assets/text_resources.json` | post-event `$CA` resources | 513 resources |
| `assets/interface_text.json` | `$C0:33B5` 24-bit help/status family | 9 blocks / 27 rows |
| `assets/menu_text.json` | native `$C7` menu/status strings | 66 logical source elements |
| `assets/battle_text.json` | `$C0` battle-message pool | 109 records |
| `assets/shop_text.json` | `$D9` shop/forge mini-events | 9 records |
| `assets/opening_text.json` | compressed startup/title arrangement | 24 records |

Together these assets currently expose **2918 globally unique source text
elements**. The ID uniqueness is checked automatically.

`dialogues.json` deliberately excludes `$0400`, because component 05 owns that
event. `intro_event.json` inventories its eight source text parts without
changing component ownership.

## Source versus translation

Everything under `assets/` is a deterministic extraction of the clean USA ROM.
It contains source text only. French text lives separately under
`translations/` and is bound by the stable source ID rather than by a component
CSV row number or a semantic label.

Direct source data uses SNES-position IDs such as `C0:33F0` or `CA:98E1`.
Compressed opening strings use the source block plus decompressed offset, such as
`C7:B480+09F9`. See `TRANSLATIONS.md` for the complete convention.

## Extraction and validation

Regenerate all source assets with:

```bash
python3 tools/extract_text.py "Secret of Mana (USA).sfc"
```

Or use `--only dialogues|resources|interface|menu|battle|shop|opening|intro`.

Validate all families, the event parser, source round-trips, global IDs and the
currently committed French translation bindings with:

```bash
python3 tools/check_text_roundtrip.py \
  "Secret of Mana (USA).sfc" --scan-all-events
```

Current dialogue/resource round-trips remain byte-for-byte exact over 87,487
event bytes and 7,315 CA-resource bytes respectively, including the complete
1,026-byte resource pointer table.

## Scope

The inventory targets **user-visible static string data**. It does not promote
an arbitrary ROM byte run merely because the stock codec can decode it into
English-looking characters. Code, graphics, compressed opaque data and dynamic
WRAM-built text require a proven display/reference path before being added.

The deep audit that produced this rule, including the discovery of the D9
shop/forge family and the searches that did not yield additional static
families, is documented in `TEXT_RESEARCH_NOTES.md` so it can be resumed later.


## Component ownership

A repository-wide component audit found no additional prose source in components
01, 06 or 07. Component 01 owns graphics/resource data, component 06 owns runtime
dialogue rendering only, and component 07's private event consists only of event
commands. Components 02-05/08 are the only current component consumers of the
root source/translation JSON architecture. See `TEXT_COMPONENT_AUDIT.md` for the
file-by-file audit and the remaining intentional component-local data assets.
