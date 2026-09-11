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

## Planned next work: item/special names

The next translation family to study is resource IDs `$0B9-$0C5` (13 item/special names).
**No translation or insertion procedure is approved yet.** The next session must first compare
the SNES resource table with the available Android source containers, establish identity/provenance,
measure every relevant display constraint, and decide whether in-place serialization is sufficient or
whether deterministic repacking/relocation is required.

The intended architecture is the same as elsewhere in the repository: clean-ROM data stays in
`assets/`, Android upstream material stays in `sources/android/`, and French output should be generated
into a sparse `translations/text_resources_french.json` only after the mapping/import procedure has been
reviewed. Avoid embedding French item names directly in component code or one-off scripts.

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

## Round 72 Android-FR pre-insertion audit

The Android-FR mapping scaffold is now followed by a deterministic, insertion-free
layout/encoding audit:

```bash
python3 tools/audit_text_resource_layout.py "Secret of Mana (USA).sfc"
python3 tools/audit_text_resource_layout.py "Secret of Mana (USA).sfc" --check
```

Generated review material:

- `mappings/android/text_resources_layout_audit.json`;
- `mappings/android/text_resources_layout_audit.html`;
- `mappings/android/text_resource_names_geometry_review.html` (focused name-only review).

The audit treats the maximum line/line-count observed in the clean USA resources as a
**conservative review envelope only**. It is not claimed to be a renderer hard limit.
Current result over the 475 mapped Android-FR resources is 302 inside the observed
stock envelope, 170 requiring geometry review, and 3 blocked by the current direct/DTE
profile.

### Stock-DTE compression makes in-place storage viable

Direct-byte French serialization was misleadingly large because the stock CA family
itself uses DTE. `shared.stock_text.encode_text_with_stock_dte()` now provides a
translation-only encoder that reuses only the stock DTE pairs that remain DTE under
the ordinary/full-French runtime boundary: lower `$60-$7C` plus upper `$E6-$FF`.
The DTE table is not modified and decoded text is unchanged.

With representation-only normalization (`U+3000 -> space`, straight double quotes to
the stock directional quote glyphs), every currently profile-compatible mapped
translation plus untouched stock fallbacks serializes to **7,304 bytes**, compared
with the stock allocation of **7,315 bytes**. Therefore the resource table/blob can be
rebuilt **in place** without touching the data immediately following the stock blob;
relocation is not required for storage capacity.

Three Android-FR enemy names remain intentionally untranslated by the current test
path because they contain `°` (`Double n°1`, `Double n°2`, `Double n°3`). In the shared
charset `°` is direct code `$E6`, while ordinary non-event CA resources currently use
`$E6` as the start of the upper stock-DTE range. Do not silently substitute another
character. Either prove a CA-resource-specific `$E8` routing context later or keep
those three stock names until a safe solution exists.

### Experimental name-only IPS

`tools/build_text_resources_test_patch.py` builds a **research-only autonomous IPS
against the clean USA ROM**. It first applies the current `patches/all.ips`, then
rebuilds the CA table/blob in place with only selected resource categories. It refuses
to cross the original 7,315-byte allocation and skips translations incompatible with
the current `$E6` runtime profile instead of guessing.

Default categories are all mapped name families (magic, Mana spirits, weapons,
helmets, armor, accessories, items, enemies and locations). Current default result:
**349 translated names**, **3 profile-skipped `n°` enemy names**, blob **7,056 bytes**
(`-259` bytes versus stock). This is for visual/runtime testing only; it is not yet a
production component and must not be folded into `all.ips` until menu geometry is
reviewed.
