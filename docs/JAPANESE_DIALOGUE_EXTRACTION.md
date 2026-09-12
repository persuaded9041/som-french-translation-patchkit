# Japanese SNES dialogue extraction

`tools/extract_japanese_dialogue.py` is an **analysis-only** helper for recovering
original dialogue text from a clean unheadered **Seiken Densetsu 2 (Japan)** ROM.
It never participates in the build and must never be used as Android identity
evidence.

Its normal input is a canonical USA dialogue carrier ID from
`assets/dialogues.json`, for example `C9:916F`. The tool uses that USA position
only to identify the owning event. It then reads the **same event ID** from the
Japanese ROM and decodes the original SFC event text with the Japanese codec.
It does **not** assume that USA and Japanese physical offsets are equal.

## Usage

```bash
python3 tools/extract_japanese_dialogue.py "Seiken Densetsu 2 (Japan).sfc" C9:916F
```

Machine-readable output:

```bash
python3 tools/extract_japanese_dialogue.py "Seiken Densetsu 2 (Japan).sfc" C9:916F --json
```

Inspect every Japanese text block in a known event directly:

```bash
python3 tools/extract_japanese_dialogue.py "Seiken Densetsu 2 (Japan).sfc" --event 0278
```

Regression check:

```bash
python3 tools/check_japanese_dialogue_extractor.py "Seiken Densetsu 2 (Japan).sfc"
```

The ROM is accepted only when it is exactly the documented clean, unheadered JP
ROM (`0x200000` bytes; SHA-256
`7fd1747eb4333f502d5fe6df7267342e4b4a399ab65b57f0a139e5f9fc02ab9d`).
No ROM data is written to the repository.

## Matching policy

The script deliberately separates **event identity** from **carrier identity**.
The USA carrier proves which event to inspect; a single Japanese carrier is
reported only when structure proves it strongly enough:

- `exact_event_structure`: same token/command structure, including command args;
- `unique_text_in_event`: each regional event contains exactly one text block;
- `same_structure_command_args_differ`: token layout and command names match but
  regional command arguments differ;
- `resegmented_or_ambiguous`: no one-to-one carrier is asserted. The script
  prints every Japanese text block in the event for human review instead.

The last case is intentional. Event `$0278`, for example, stores the two USA
controller-help carriers inside one combined Japanese text block. Returning the
whole JP event is safer than inventing a USA-to-JP carrier mapping.

## Japanese codec

`shared/dialogue/japanese.py` contains the recovered original-SFC dialogue
character tables and decoder. Direct bytes `$80-$FF` use the default 128-entry
page. Prefixes `$60-$67`, `$68-$6B` and `$6C-$6F` select 1-8 / 1-4 / 1-4
characters through the overlapping S1/S2/S3 shifted pages; `$7F` is newline.
Event commands are parsed with the shared stock command definitions from
`shared/dialogue/codec.py`.

The regression checker locks known exact source material from `$0207`, `$0208`,
`$024F` and `$035F`, and locks `$0278` as deliberately resegmented. It also
structurally parses every JP event whose physical end is established by the next
pointer.

## Limits

- This is a source-recovery aid, **not** a translator and not an Android matcher.
- A Japanese string must not be put in `original_jp` merely because it looks
  plausible; use the structural evidence reported by this tool and retain human
  review for ambiguous/resegmented cases.
- Android JP is never consulted or substituted for SNES-JP text.
- Japanese event `$03FF` is intentionally rejected: the C9 pointer table has no
  following sentinel establishing its physical end in the JP ROM. The helper
  fails instead of guessing that boundary.
- Event numbers themselves can diverge between regional scripts, especially in later `$CA` scenes. Round 62 proves one such case: USA `$04E1/CA:2C84` belongs to the Thanatos scene whose exact JP evidence is in event `$0070/C9:1539`. The normal same-event-ID lookup therefore finds no JP carrier here. Treat this as a conservative failure and use independently proven regional event evidence; never infer a cross-region event renumbering automatically.
- `$7D...$7E` ending-text blocks are retained as raw event data; that special
  renderer is outside this helper's dialogue-decoding scope.
