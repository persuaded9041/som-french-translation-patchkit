# 08_dialogue_text

Deterministic extraction/reinsertion of stock event dialogue. Component 06 owns
the runtime VWF renderer; component 08 owns event text data and reconstruction.
No VWF metric, framing rule or compositor is defined here.
The stock event codec and relocation helper live in `shared/dialogue_codec.py` and `shared/dialogue_relocation.py`; component 08 consumes them rather than exposing Python modules for other components to import.

## Validated base

The first edited-event experiment used `$0107` and was runtime-validated with
dynamic player-name insertion, line breaks, WAIT sequencing and the existing
VWF. The French probe is not committed.

The relocation path is also runtime-validated: unchanged `$0107` was forced to
`$E8:2000` and behaved normally. That force probe has been removed; relocation
now occurs only when a translated event genuinely outgrows its clean-USA span.

## Source and translation files

Canonical source text is repository-wide:

- `assets/dialogues.json`: clean-USA source only;
- `translations/dialogues_french.json`: sparse French translations. The
  sentence-aware `$010F` extra-page layout is runtime-validated. The current
  batch-2 candidate expands this to 37 formatted text tokens across 27 explicit
  complete events (`$0107-$0155` selection; see the generated batch report).
  `$010A`, `$010F`, `$013C` and `$014B` use one generated `\f` page marker,
  which component 08 compiles to the validated `WAIT $00` + `TEXT_CLEAR`
  transition.

`dialogues.json` uses format version 4. The extractor parses all stock event
scripts `$0000-$07FF`, selects every text-bearing event except `$0400` (owned by
component 05), and assigns each translatable text token the SNES address of its
first source byte.

Example:

```json
{
  "event_id": "000B",
  "tokens": [
    {"type": "command", "name": "TEXT_OPEN"},
    {"type": "text", "id": "C9:089B", "source": "Revived Mana Sword!"},
    {"type": "command", "name": "PLAY_SOUND", "args": "02 16 0F 88"},
    {"type": "command", "name": "WAIT", "args": "10"},
    {"type": "command", "name": "TEXT_CLOSE"},
    {"type": "command", "name": "RETURN"},
    {"type": "command", "name": "END"}
  ]
}
```

A translation remains separate and needs only the translated subset:

```json
{
  "format_version": 1,
  "language": "fr",
  "source_asset": "dialogues.json",
  "groups": [
    {
      "group": "dialogues",
      "entries": [
        {"id": "C9:089B", "text": "..."}
      ]
    }
  ]
}
```

Commands, arguments, dynamic names, choices, WAITs and unmapped direct glyphs
remain structural source tokens and are not duplicated in translation files. One
generated layout exception is supported for extra-page formatting: a form-feed
(`\f`) inside translated ordinary text compiles to the stock `WAIT $00` +
`TEXT_CLEAR` page-transition sequence. The transition and sentence-aware placement are runtime-validated on `$010F`;
the formatter prefers complete-sentence page boundaries. It is never treated as
a printable glyph.
Exact original text bytes are also not stored: unchanged tokens are reparsed
from the clean USA ROM so stock DTE choices are preserved byte-for-byte.
Translated ordinary text is encoded deterministically. The dialogue charset uses `♪=$D3`, the shared French `$D4-$E5` range, `°=$E6` and `;=$E7`; a context-sensitive parser router keeps the intro at `$E6` and uses `$E8` only for real event dialogue. DTE recompression is
still intentionally deferred.

## Coverage and round-trip

Current source inventory for component 08:

- all 2048 stock event scripts structurally parse;
- 713 text-bearing events are committed (`587` in `$C9`, `126` in `$CA`);
- 87,487 bytes of selected event spans round-trip byte-for-byte;
- the audit round-trip of all 2048 scripts covers 96,182 bytes;
- `$04FD` ending-text mode is supported;
- `$0400` remains parseable but is extracted separately as `assets/intro_event.json`.

The 513 following `$CA` non-event resources are separate in
`assets/text_resources.json`.

## Extraction and validation

```bash
python3 tools/extract_text.py "Secret of Mana (USA).sfc"
python3 tools/check_text_roundtrip.py \
  "Secret of Mana (USA).sfc" --scan-all-events
```

Research-only subsets can still be extracted with `--only dialogues --event ...`
or `--all-events`.

Build only this component with:

```bash
python3 build.py "Secret of Mana (USA).sfc" dialogue-text
```

Then combine it with the stored IPS files for unchanged components:

```bash
python3 build.py "Secret of Mana (USA).sfc" --combine
```

## Relocation

A translated event that still fits its clean-USA pointer span is rebuilt in
place. If it grows beyond that span, component 08 packs it deterministically in
the reserved `$E8-$EC` pool and redirects only that event through a sparse
2048-entry 24-bit table. A zero entry falls back to the live stock `$C9/$CA`
pointer tables, so component 05 remains authoritative for its `$0400-$040F`
pointer changes.

Components 05/06 contain only the minimal, already validated extension needed to
accept component-08 relocation banks `$E8-$EC` under their existing event-engine
caller gates; their stock `$C9/$CA` VWF behavior is unchanged.

## Intentional limits

- Event `$03FF` uses its explicitly validated three-byte stock terminal span.
- Event `$07FF` uses the first following `$CA` resource pointer as its exact upper boundary.
- Unknown command layouts fail rather than being guessed.
- Dialogue DTE recompression is deferred; source/no-translation round-trips still
  preserve the original encoding exactly.

## Android formatting batches

The historical `$0107` checkpoint remains reproducible without overwriting the
current translation file:

```bash
python3 tools/import_android_text.py --only dialogue-format-pilot \
  --rom <clean-USA-ROM>
```

It writes `mappings/android/dialogues_format_pilot_translation.json` plus the
trace report `dialogues_format_pilot.json`. `%S(0,0)` is rebound to the existing
`PLAYER_NAME $00` command rather than encoded as prose. The dual 240-pixel /
38-decoded-character wrap for `$0107` is **runtime-validated**, including dynamic
name insertion, WAIT transition and normal continuation.

The current translation file is generated by the first complete-event expansion:

```bash
python3 tools/import_android_text.py --only dialogue-format-batch1 \
  --rom <clean-USA-ROM>
```

The corrected batch contains `$0107`, `$010E`, `$0116`, `$0117`, `$0118` and
`$011D` (8 translated source tokens) and is runtime-validated. `$010F` was removed
from that baseline after its 9-character `PLAYER_NAME` line split at the exact
parser-capacity boundary. Lines containing a dynamic name now reserve one additional
parser-safety unit.

The sentence-aware extra-page checkpoint remains reproducible without replacing
the current batch translation with:

```bash
python3 tools/import_android_text.py --only dialogue-format-page-pilot \
  --rom <clean-USA-ROM>
```

It writes a historical translation snapshot under `mappings/android/`. Its
`$010F` 3+1 placement is runtime-validated: the first page ends at
`l'heure.`, then the final question is shown after `WAIT $00` + `TEXT_CLEAR`.

The current larger candidate is generated with:

```bash
python3 tools/import_android_text.py --only dialogue-format-batch2 \
  --rom <clean-USA-ROM>
```

Batch 2 freezes 27 complete events and 37 formatted source tokens. Only `$010A`,
`$010F`, `$013C` and `$014B` are authorized to insert one extra page. The other
selected events must fit their existing line budget. Generation still aborts for
unmapped semantic text, unsupported command crossings or placeholder mismatches.
