# Non-event text resources

The stock `$CA` pointer table does not stop after the 1024 `$CA` event scripts.
Entries `$0400-$0600` form a second family of **513 null-terminated text
resources**. They are not NPC/story event scripts and therefore stay separate
from `assets/dialogues.json`.

The canonical source extraction is `assets/text_resources.json` and is
generated together with the dialogue asset by:

```bash
python3 tools/text/extract.py "Secret of Mana (USA).sfc"
```

## Physical layout

- pointer table: ROM `$0A0800-$0A0C01` (`513 * 2 = 1026` bytes);
- first string pointer: `$CA:98E1`;
- resources: IDs `$000-$200` inclusive;
- each string ends with `$00`;
- in the clean USA ROM every next pointer is exactly the byte after the previous
  string terminator;
- the complete stock string blob is 7,315 bytes including terminators.

This lets the checker rebuild both the complete 513-entry pointer table and the
complete string blob and require byte-for-byte equality, not merely equivalent
decoded text.

## Categories

The ordered resource ranges are:

| IDs | Category | Count |
|---|---|---:|
| `$000-$029` | magic names | 42 |
| `$02A-$031` | Mana spirit names | 8 |
| `$032-$079` | weapon names | 72 |
| `$07A-$08E` | helmet names | 21 |
| `$08F-$0A3` | armor names | 21 |
| `$0A4-$0B8` | accessory names | 21 |
| `$0B9-$0C5` | item/special names | 13 |
| `$0C6-$0CE` | menu/status labels | 9 |
| `$0CF-$14E` | enemy names | 128 |
| `$14F-$196` | weapon descriptions | 72 |
| `$197-$1C0` | magic descriptions | 42 |
| `$1C1-$1DF` | location names | 31 |
| `$1E0-$1FE` | unused/empty slots | 31 |
| `$1FF-$200` | system messages | 2 |

The final two strings are the stock messages for using the Magic Rope and
calling Flammie where those actions are unavailable.

## JSON representation

Each resource is source-only and carries a stable ROM-position ID plus the stock
resource index used by the game:

```json
{
  "id": "CA:98E1",
  "resource_id": "000",
  "category": "magic_name",
  "source": "EARTH SLIDE"
}
```

`id`, `resource_id`, `category` and `source` are checked against a fresh clean-ROM
extraction. Pointers and raw source bytes are deliberately omitted.

French localization is generated from the reviewed Android identity recipe rather than
maintained as independent hand-authored prose. `tools/text/import_android_resources.py`
rebuilds both `reports/android/text_resources_android.json` and
`translations/text_resources_french.json` for review. Those two files are generated
outputs: the production `french_resources` component reconstructs the same mapping and
French payload in memory from `assets/text_resources.json`,
`recipes/android/text_resources_layout.json`, and Android `systxt_en/fr.bin`.

For unchanged or unsupported resources the serializer recovers the exact source bytes
from the clean USA ROM, so fallback serialization remains byte-identical.

## Current production insertion

`french_resources` is the production component for the reviewed **name families** only:
magic, Mana spirits, weapons, helmets, armor, accessories, reviewed item/special names,
enemies and locations. It rebuilds the full pointer table/blob in place and is included
in the aggregate patch. Descriptions and menu/status labels are not currently inserted
by this component even when Android identities exist.

The current production build translates **349 resources**. Three mapped enemy names
(`Double n°1`, `Double n°2`, `Double n°3`) deliberately remain stock because `°` uses
direct code `$E6` while ordinary non-event `$CA` resources still treat `$E6` as the
start of their upper DTE range. No substitution is guessed.

Stock-DTE compression keeps the selected name-family build at **7,056 bytes** versus
the original **7,315-byte** allocation. The rebuilt blob therefore remains entirely
in place at `$CA:98E1-$B470`; the allocation ends at `$CA:B573`. No resource relocation
is used.

Do not add new object/item wording during component-maintenance audits. New families or
wording changes first require the normal identity/provenance and display-geometry review.

## Validation

Run the clean-source round-trip check:

```bash
python3 tools/text/check_roundtrip.py \
  "Secret of Mana (USA).sfc" --scan-all-events
```

Current clean-USA guarantees:

- 513/513 resources decode structurally;
- 7,315/7,315 stock string bytes round-trip exactly;
- the 1,026-byte pointer table round-trips exactly;
- translation-free reinsertion is byte-for-byte identical;
- two fresh source extractions produce byte-identical JSON.

Verify the generated Android mapping/review payload with:

```bash
python3 tools/text/import_android_resources.py --check
```

The current mapping contains 475 mapped resources, 34 deliberately excluded resources
and 4 unresolved locations. The component filters that mapping to its reviewed name
families and applies the current encoding profile.

## Layout/encoding review tool

`tools/text/audit_resource_layout.py` remains a review tool for mapped resources:

```bash
python3 tools/text/audit_resource_layout.py "Secret of Mana (USA).sfc"
python3 tools/text/audit_resource_layout.py "Secret of Mana (USA).sfc" --check
```

Its stock-derived line/line-count envelope is conservative review evidence, not a
claimed renderer hard limit. It is especially useful before enabling additional resource
families. Production insertion itself is owned solely by `french_resources`; the old
experimental aggregate-patch builder was removed once this component became canonical.
