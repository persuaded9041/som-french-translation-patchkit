# Stock dialogue/event format

This document records the mechanisms currently used by
`components/08_dialogue_text` for deterministic extraction and reinsertion. The
goal is to preserve the stock event structure exactly while exposing translatable
source text under `assets/` and keeping French edits separately under `translations/`.

The first edited-event experiment (`$0107`) has been runtime-validated. The
current checkpoint deliberately removes that translation again and concentrates
on broad no-edit extraction/reinsertion coverage.

## 1. Event pointer tables and exact spans

The clean unheadered USA ROM stores 2048 stock event scripts in banks `$C9` and
`$CA`.

- Event IDs `$0000-$03FF` use 1024 little-endian 16-bit pointers beginning at
  ROM `0x090000` / CPU `$C9:0000`.
- Event IDs `$0400-$07FF` use the first 1024 pointers beginning at ROM
  `0x0A0000` / CPU `$CA:0000`.
- Each value is a same-bank 16-bit address, not a file offset.
- The `$CA` pointer table continues after those 1024 event pointers with
  non-event text/resource pointers. Those resources are not extracted by the
  current dialogue asset.

For ordinary events, the next pointer gives the exact physical span.

Two boundary cases are handled explicitly:

- `$03FF`: `$C9` has no following event pointer/sentinel. In the clean USA ROM
  the terminal event is exactly `14 FD 00`; the extractor validates that
  sequence and treats it as a three-byte script rather than consuming unrelated
  data that follows it.
- `$07FF`: the following `$CA` table entry is the first non-event resource
  pointer, so it provides an exact upper bound for the last event span.

An **event span** contains both text and control commands. Dialogue text is only
one part of that byte stream.

Component 08 intentionally excludes event `$0400` from its default asset because
that translated intro event is owned by `05_intro_vwf_french`. It remains
parseable/extractable explicitly for research.

## 2. Text byte classes

The stock text parser distinguishes these byte classes:

| Bytes | Role |
|---|---|
| `$50-$5F` | text/control commands |
| `$60-$7C` | lower stock DTE codes |
| `$7D` | begin special ending-text mode |
| `$7E` | end special ending-text mode |
| `$7F` | line break |
| `$80-$D2` | direct stock glyphs |
| `$D3-$FF` | upper stock DTE codes |

The stock DTE pair table is at `$C7:7299` / ROM `0x077299`. The codec knows how
to expand both DTE ranges into readable source text. Exact unchanged encoding is
recovered from the clean USA ROM during verification/reinsertion rather than
duplicated in the canonical source JSON.

No DTE byte is actually present in the ordinary text tokens of the 2048 stock
event scripts scanned in the reference ROM; the support is kept because the
same stock text format uses DTE elsewhere and those non-event resources are a
future extraction target.

The patchkit's canonical `full_french` charset moves the direct/DTE boundary to
`$E6`, making `$D4-$E5` direct French glyph codes for future translated text.
Component 08 consumes that shared definition but does not alter the VWF renderer.

## 3. Event/control commands

The extractor walks the complete event byte stream, so it must know the encoded
length of every command encountered before it can safely find subsequent text.

The initial four-event checkpoint covered only a subset. Reverse-engineering of
the event interpreter established the additional one-byte layouts needed for
opcodes `$01`, `$07`, `$09` and `$0A`; `$0B-$0D` are also represented as their
established one-byte layouts. Generic `OP_XX` names are kept where a semantic
name is not established; any argument bytes remain explicit as `args`.

Text-command layouts currently represented include:

- `$50-$53`: one byte;
- `$54-$57`: opcode + one argument;
- `$58`: one byte;
- `$59-$5A`: opcode + one argument;
- `$5B`: one byte;
- `$5C`: opcode + one argument;
- `$5D-$5F`: one byte.

Other event command lengths required by the stock scripts are encoded in
`shared/dialogue_codec.py`, including the variable `$2D` form. Unsupported opcodes still
abort extraction. The codec does not infer a length from surrounding bytes.

With these layouts, every event `$0000-$07FF` in the clean USA ROM parses
structurally without an unknown-layout fallback.

## 4. Special ending text

Byte `$7D` switches to the ending/credits text representation and `$7E` closes
it. Inside that mode, bytes are interpreted as the ending text payload rather
than as ordinary event/text opcodes; `$7F` remains a line break.

This distinction matters for event `$04FD`, whose credits contain ordinary ASCII
values that would otherwise collide numerically with event command opcodes.
The current ROM contains 19 such ending-text blocks in that event, all preserved
as explicit `ending_text` tokens.

## 5. Source representation, version 4

`assets/dialogues.json` stores complete selected events as ordered structural
tokens. It is now a **clean-ROM source asset only**; French text lives separately
in `translations/dialogues_french.json`.

### Ordinary `text`

```json
{
  "type": "text",
  "id": "C9:2B09",
  "source": "Did you see that, "
}
```

The globally unique `id` is the SNES address of the first encoded source byte.
`source` is immutable clean-ROM text. Exact raw bytes are deliberately omitted:
when no translation exists for an ID, serialization recovers the original token
bytes from a fresh parse of the validated USA ROM, preserving stock DTE/direct
choices byte-for-byte.

Future French edits are sparse entries in `translations/dialogues_french.json`:

```json
{
  "id": "C9:2B09",
  "text": "..."
}
```

Only translated text is newly encoded. DTE recompression for newly translated
ordinary text remains deferred.

### `ending_text`

Uses the same `id` + immutable `source` model around the stock `$7D ... $7E`
mode. The ID points to the first payload byte; the delimiters remain structural
and are recovered from the clean ROM.

### `command`

Commands remain structural and are not translation entries:

```json
{"type": "command", "name": "TEXT_OPEN"}
{"type": "command", "name": "WAIT", "args": "10"}
{"type": "command", "name": "PLAY_SOUND", "args": "02 16 0F 88"}
```

The opcode is reconstructed from `name`; only actual command arguments are
stored.

### `glyph`

Stock direct slots `$CE-$D2` whose textual meanings are not established remain
one-byte hexadecimal glyph tokens, for example:

```json
{"type": "glyph", "code": "CE"}
```

### Event metadata

Only `event_id` is stored per event. Bank, pointer, file offset, source size,
hashes and raw byte dumps are all re-derived from the clean ROM. The top-level
`source_rom_sha256` documents the single reference ROM targeted by the asset.

The checker freshly reparses every selected event and compares text IDs/source,
token boundaries, commands and glyphs before requiring byte-identical source
serialization.

## 6. Coverage and deterministic round-trip

The default extractor scans all 2048 event scripts and commits only scripts that
contain at least one `text` or `ending_text` token, excluding owned event `$0400`.

Current committed asset:

| Coverage | Count |
|---|---:|
| stock event scripts structurally scanned | 2048 |
| text-bearing events committed | 713 |
| committed events in `$C9` | 587 |
| committed events in `$CA` | 126 |
| ordinary `text` blocks inside those events | 2,143 |
| `ending_text` blocks | 19 |
| bytes in committed event spans | 87,487 |
| unmapped raw direct-glyph tokens | 20 |
| currently translated dialogue tokens | 0 |

The 713 figure is therefore a count of **event scripts containing text**, not a
count of dialogue lines or speech boxes. One event can contain many independent
text blocks separated by WAITs, names, choices or other commands.

The `$CA` pointer table continues with 513 non-event text resources after the
2048 event-script pointers. They are not missing NPC/story dialogue and are kept
out of `dialogues.json`; the root extractor now writes them separately to
`assets/text_resources.json`. See `docs/TEXT_RESOURCES.md`.

Two different no-translation checks succeed for all 713 committed events:

- **source round-trip**: structured source tokens reconstruct the clean event span;
- **translation-free reinsertion**: serialization with no French entry reconstructs the same span.

Both cover all 87,487 selected bytes byte-for-byte.

For structural auditing, an `--all-events` extraction was also round-tripped
through both paths: all 2048 scripts, 96,182 bytes total, are byte-identical.

The extractor itself is deterministic: two fresh extractions from the same clean
ROM produce byte-identical JSON.

## 7. Runtime checkpoint history

The first checkpoint edited only event `$0107`, kept its source pointer
`$C9:2B08`, and rebuilt it in place. Runtime testing validated:

- edited text decoding/encoding;
- the preserved `$57 00` dynamic player-name command;
- line breaks and WAIT sequencing;
- compatibility with the existing dialogue VWF;
- normal continuation after the dialogue.

That test translation was removed after validation. `assets/dialogues.json` is now permanently source-only; future dialogue work belongs in `translations/dialogues_french.json`.

## 8. Current builder behavior

Component 08 reconstructs every selected event from the clean-USA canonical
structure. When a translated event is no larger than its source span, it remains at
its stock address; a shorter event is padded with `$00` END bytes and all stock
pointers remain unchanged.

Growth now has a deterministic relocation path:

- the stock event dispatcher at `$C1:E794` is hooked only when at least one event
  is relocated;
- `$E8:0000-$E8:17FF` is a sparse 2048-entry table of 24-bit event addresses;
- a zero bank byte falls back to the live stock `$C9/$CA` tables;
- `$E8:1800-$E8:1FFF` is reserved for the small resolver helper;
- relocated scripts are packed by ascending event ID from `$E8:2000` through
  `$EC:FFFF`, never crossing a 64 KiB bank boundary.

Because fallback reads the live stock tables, component 05 remains owner of its
validated `$0400-$040F` pointer rewrites. Component 08 does not duplicate or
freeze those pointers.

The relocation path is runtime-validated: unchanged event `$0107` was executed
from `$E8:2000` without changing its script bytes, and dynamic name insertion,
VWF rendering, line breaks, WAIT behavior and continuation all remained correct.
The temporary force probe has been removed; relocation now occurs only for
genuine translated-event growth.

Relocated event text must still use component 06's VWF path. The shared parser
caller gate and renderer caller gate therefore retain their validated structural
checks and add only the reserved relocation-bank range `$E8-$EC`. Existing `$C9/$CA` behavior is unchanged, and the added `$E8-$EC` bank range is
runtime-validated.

With no dialogue translations, no French charset writes are emitted by component 08. Once
at least one translation entry changes source text, the builder installs the canonical
`full_french` direct glyphs and `$E6` threshold as before.

## 9. Deliberately deferred work

The following are not yet generalized:

- DTE compression/optimization for newly translated text;
- relocation/repacking policy for *translated and growing* non-event `$CA` text
  resources; extraction and byte-identical no-op reinsertion are already covered
  by `assets/text_resources.json`;
- semantic names for opcodes whose byte lengths are known but whose role is not
  needed for safe round-trip;
- textual mappings for raw direct slots `$CE-$D2`.

These should be added from engine/ROM evidence, not inferred from local examples.
