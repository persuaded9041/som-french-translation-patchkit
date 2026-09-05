# 08_dialogue_text

Deterministic extraction/reinsertion of stock event dialogue. Component 06 owns
the runtime VWF renderer; component 08 owns event text data and reconstruction.
No VWF metric, framing rule or compositor is defined here.

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
- `translations/dialogues_french.json`: sparse French translations, currently empty.

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

A future translation is separate and needs only the translated subset:

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
remain structural source tokens and are not duplicated in translation files.
Exact original text bytes are also not stored: unchanged tokens are reparsed
from the clean USA ROM so stock DTE choices are preserved byte-for-byte.
Translated ordinary text is encoded deterministically; DTE recompression is
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
