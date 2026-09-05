# Non-event text resources

The stock `$CA` pointer table does not stop after the 1024 `$CA` event scripts.
Entries `$0400-$0600` form a second family of **513 null-terminated text
resources**. They are not NPC/story event scripts and therefore stay separate
from `assets/dialogues.json`.

The canonical source extraction is `assets/text_resources.json` and is
generated together with the dialogue asset by:

```bash
python3 tools/extract_text.py "Secret of Mana (USA).sfc"
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

French text will live in a separate sparse
`translations/text_resources_french.json` when translation of this family begins.
For an unchanged resource the serializer recovers the exact source bytes from the
ROM, so the translation-free path remains byte-identical.

The codec can already serialize a supplied translated string deterministically,
but **growth/repacking of the live 513-resource table is intentionally not enabled
yet**. That policy will be designed only when this family is actually translated.

## Validation

Run:

```bash
python3 tools/check_text_roundtrip.py \
  "Secret of Mana (USA).sfc" --scan-all-events
```

Current clean-USA guarantees:

- 513/513 resources decode structurally;
- 7,315/7,315 string bytes round-trip exactly;
- the 1,026-byte pointer table round-trips exactly;
- a translation-free no-op reinsertion is byte-for-byte identical;
- two fresh extractions produce byte-identical JSON.

No French translation file is committed for this family yet.
