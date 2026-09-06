# Stock dialogue/event format

This document records the mechanisms currently used by
`components/08_dialogue_text` for deterministic extraction and reinsertion. The
goal is to preserve the stock event structure exactly while exposing translatable
source text under `assets/` and keeping French edits separately under `translations/`.

The first edited-event experiment (`$0107`) is runtime-validated. The first
complete-event batch also runtime-validated `$010E`, `$0116`, `$0117`, `$0118` and
`$011D`. `$010F` exposed an exact-capacity `PLAYER_NAME` parser edge case; its
generated sentence-aware extra page is now runtime-validated and forms the basis
for the larger batch-2 candidate.

## Runtime layout rule for dynamic names

Component 06 has a 38-unit private parser contract, but batch-1 runtime testing
showed that a line modeled as exactly 38 visible characters with a maximum
9-character `PLAYER_NAME` can still split. The offline formatter therefore treats
each dynamic-name placeholder as nine visible characters **plus one conservative
parser-safety unit** for line-capacity decisions. Pixel width is still budgeted
separately using the worst-case 9-character name width.

This rule makes `$010F` require four safe lines while the original SNES span
exposes three. The runtime-validated batch-1 generator therefore rejects it rather
than shortening the translation or relying on an implicit fourth-line scroll. The
separate extra-page path handles this case by inserting an explicit stock page
transition; both the transition and its sentence-aware placement are runtime-validated
on `$010F`.

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

The patchkit keeps `$D4-$E5` as the canonical 18-character French range.
Ordinary translated dialogue uses the `dialogue_french` extension `$D3-$E7`
(`♪`, French range, `°`, `;`) and a context-sensitive `$E8` event-dialogue DTE
boundary. The translated intro remains at `$E6`. Component 08 consumes this
shared encoding but does not own the VWF renderer.

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
| current Android-derived formatted tokens | 37 |

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

The original edited-event checkpoint used event `$0107`, kept its source pointer
`$C9:2B08`, and rebuilt a short probe in place. Runtime testing validated:

- edited text decoding/encoding;
- the preserved `$57 00` dynamic player-name command;
- line breaks and WAIT sequencing;
- compatibility with the existing dialogue VWF;
- normal continuation after the dialogue.

`assets/dialogues.json` remains permanently source-only. The validated `$0107`
translation and later runtime candidates live only in `translations/dialogues_french.json`.

## 7.1 Offline wrapping constraints

Dialogue layout has **two independent limits** that the formatter must respect:

1. a conservative VWF pixel target (currently **240 pixels**);
2. the component-06 parser's runtime-validated capacity of **38 decoded
   characters per chunk/line**.

The second limit was exposed by the `$0107` runtime pilot. The initial generated
line `Oh, c'est toi, <9-char name>. Tout à l'heure,` is 41 decoded visible
characters with a maximum-length name; runtime split it despite its VWF width
being only 245 pixels. After the first reflow, the line
`l'heure, j'ai vu une grande lumière dans` measured only 231 pixels but contained
40 decoded characters, and runtime moved `dans` to the next line. Both failures
therefore match the known **38-character parser capacity**, rather than proving a
smaller physical pixel width.

The offline formatter now enforces both constraints before emitting a line.
`PLAYER_NAME` is conservatively counted as nine visible characters as well as at
its worst-case VWF pixel width. This prevents the runtime parser from creating a
fourth physical line behind the formatter's back. The resulting 38-character
checkpoint for `$0107` is **runtime-validated**: the three-line first box, the
dynamic player name, WAIT transition and following text all display and progress
correctly in game.

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

With no dialogue translations, no dialogue-charset writes are emitted by component 08.
Once at least one translation changes source text, the builder installs the
`dialogue_french` `$D3-$E7` glyph span plus the same context-sensitive DTE router
as component 06.

## 8.1 First complete-event formatting batch

`tools/import_android_text.py --only dialogue-format-batch1 --rom <clean-USA-ROM>`
regenerates the current sparse French dialogue file from the original Android
EN/FR sources and the accepted whole-game alignment. The selected events are:

- `$0107` — existing runtime-validated waterfall-village pilot;
- `$010E` — early village dialogue;
- `$0116`, `$0117`, `$0118`, `$011D` — complete early village NPC speeches.

Every semantic source text token in a selected event must be covered by an
accepted mapping. This is stricter than merely formatting whichever mappings
happen to pass: the generator aborts instead of creating a half-translated event.
The 8 translated text tokens across these six events have been runtime-tested
successfully. They grow and are relocated deterministically in ascending event
order from `$E8:2000`.

`$010F` was part of the first runtime attempt but is not part of the validated
batch-1 baseline. With a 9-character hero name its line
`Te voilà, <nom> ! Bob et Ness sont` hit the exact capacity boundary and split in
game. The conservative dynamic-name parser reserve therefore makes the Android
French require four safe lines.

## 8.2 Explicit extra-page formatting

`tools/import_android_text.py --only dialogue-format-page-pilot --rom <clean-USA-ROM>`
keeps the six runtime-validated batch-1 events and adds `$010F`. The generated
page transition itself is **runtime-validated**: a form-feed marker `\f` in the
translation compiles to the stock `WAIT $00` + `TEXT_CLEAR` sequence, waits for
player input, clears the box, renders the next page and then continues the event
normally. Canonical `assets/dialogues.json` remains structurally unchanged.
Leading, trailing or repeated page-break markers are rejected.

The first validated `$010F` checkpoint used a mechanically balanced 2+2 layout.
The later sentence-aware placement is also **runtime-validated** and is now the
reference rule. When prose needs an additional page, it now searches for a complete
sentence boundary (`.`, `!`, `?`, or ellipsis) for which both sides fit within
three safe lines. It chooses the latest such boundary, so a complete sentence
may use all three lines of the current page rather than being split merely to
avoid a one-line following page. Each page is then balanced internally while
respecting the same 240-pixel and 38-parser-unit limits. If no safe sentence
boundary exists, the previous deterministic balanced distribution remains a
conservative fallback. The runtime-validated pilot itself uses one generated extra
page. The mass generator may use a second transition only for the stricter case where
two complete-sentence boundaries yield three independently safe pages; it never
creates an arbitrary three-page split.

For `$010F`, the runtime-validated sentence-aware layout is:

```text
Te voilà, <nom> !
Bob et Ness sont revenus
tout pâles tout à l'heure.

[WAIT $00 + TEXT_CLEAR]

Il s'est passé quelque chose ?
```

The four lines measure 134 / 151 / 147 / 179 pixels and use 22 / 24 / 26 / 30
parser units under the conservative nine-character dynamic-name assumption. Both
the transition and this 3+1 sentence-boundary placement are runtime-validated.

## 8.3 Historical batch checkpoints

The earlier pilot/batch CLI modes remain available to reproduce focused runtime
checkpoints, but their generated reports are no longer committed. The canonical
current output is the simulator-filtered mass pass described below.

## 8.4 Semantic line-layout refinements

The mass formatter now applies several deterministic layout-only rules to the
Android French prose before VWF wrapping. They never rewrite translated words:

- after a completed sentence, a new capitalized speaker label ending in `:`
  starts on a fresh physical line (`... Pamela :` -> newline before `Pamela :`);
- a dash attribution after a completed quoted sentence starts on a fresh line
  (`.” - Transports Canon.` -> newline before `-`);
- standalone punctuation tokens such as `!`, `?`, `;` or `:` are attached to
  the preceding word as one unbreakable wrap atom, so punctuation cannot become
  an orphan third line;
- when a canonical source chunk begins with a newline immediately after an
  existing stock `WAIT`, that legacy rolling-window blank line is removed and
  the translated chunk emits a clear-only marker (`\v`, serialized as JSON
  `\u000b`). Component 08 compiles it to stock `TEXT_CLEAR` only. The existing
  `WAIT` therefore remains the player pause while the following localized page
  starts cleanly at its first content line.

Speaker/attribution hard-line boundaries are also preferred as page boundaries
when the block no longer fits within three lines. If both sides fit on one page,
the boundary remains only a line break.

The formatter also applies a soft semantic reflow inside an otherwise valid
three-line page:

- complete sentences (`.`, `!`, `?`, ellipsis) are kept on fresh lines whenever
  each sentence can be wrapped independently and the whole block still fits in
  at most three physical lines. This may deliberately use a third line instead
  of packing the start of the next sentence onto the previous line;
- a single comma inside one two-line sentence is a weaker candidate. It is used
  only when both clauses independently fit on one line, both retain substantial
  visual width, and the comma split materially improves line balance. Sentences
  with multiple commas are left to the normal wrapper rather than guessing which
  comma is semantic.

These are presentation preferences, not new safety requirements. If semantic
reflow makes an otherwise valid complete event fail the independent simulator,
the mass generator retries that whole event with the previous compact wrapper.
Only a simulator-clean result is accepted. This preserves coverage while making
semantic layout strictly opportunistic.

These refinements are downstream of semantic Android matching and upstream of
the independent byte-stream simulator. They never rewrite translated prose and
remain subject to zero-error, zero-warning and zero-implicit-wrap simulation.

Representative runtime testing validates the semantic line-placement rules (fresh
speaker turns, punctuation attachment, sentence-first reflow, weak single-comma
balancing and dash attribution) and the clear-only cleanup of legacy blank lines after
interactive WAITs. The complete 392-event corpus still requires full-game playthrough
validation.

## 8.5 Independent HTML simulation

`tools/simulate_dialogues.py` provides a downstream audit of the final serialized event bytes. It independently reapplies the dialogue `$E8` decoder, PLAYER_NAME expansion, validated VWF metrics, 38-glyph capacity, 256-pixel visible-ink preflight, explicit page controls and the three-line page limit. The standalone HTML renders the actual 8x12 glyph bitmaps and flags implicit runtime wraps or unsupported layout commands. See `docs/DIALOGUE_SIMULATOR.md`.

## 8.6 Simulator-filtered mass generation

`tools/import_android_text.py --only dialogue-format-mass --rom <clean-USA-ROM>`
is the current large-corpus generator. It does not use the number of explicit
English source lines as a hard layout budget: ordinary prose may use the full
validated three-line physical dialogue page. Mappings that need four to six safe lines may insert one already-validated
`WAIT $00 + TEXT_CLEAR` page transition, with sentence-boundary pagination preferred.
A second transition is permitted only when two complete-sentence boundaries produce
three independently safe pages of at most three lines each.

Before that selection, two narrow structural cases are handled without changing
localized wording. Android `←` / `→` sign markers are removed only when the same
SNES event already carries the corresponding direct `$CF` / `$D0` glyph. The
independent simulator also understands `TEXT_X $nn` only at the start of a fresh
line, where component 06 renders the `nn` prefilled `$80` cells before the text.
The formatter now reserves those same proven padding cells against the first
generated line's 38-unit and 240-pixel budgets; following wrapped lines return to
the normal full budget. `▽`, choices and mid-line `TEXT_X` remain excluded rather than inferred. A trailing
`PLAYER_NAME` placeholder accidentally absorbed by alignment lookahead may be ignored
for binding only when the actual future event tokens prove the same `PLAYER_NAME`
after linear `WAIT`/`TEXT_CLEAR`/`OP_32`/`COMPLETE_ACTIONS` controls; the command itself
stays in its original SNES position.

Two additional `PLAYER_NAME` presentation mismatches are normalized only when the
SNES structure proves that no event command needs to be invented or moved. An exact
leading Android-French `%S(n,0) :` speaker label is removed when the mapped SNES
source contains no `PLAYER_NAME` at all; the remaining localized prose is unchanged.
Conversely, if Android French places literal text on both sides of an existing
`PLAYER_NAME`, a directly adjacent source text token may act as a carrier only when
it is punctuation/whitespace-only and therefore non-semantic. The current accepted corpus uses the first rule in 21 mappings and the carrier
rule in 8 mappings. One additional carrier case exposes a physically adjacent
`PLAYER_NAME` already present immediately before the punctuation-only token; it is
accepted only when Android French proves that exact extra leading placeholder.

Several conservative event-interruption fallbacks extend coverage without editing
stock control flow. Seven mappings spanning existing interactive `WAIT $00` boundaries
may redistribute French only at complete sentence boundaries; each boundary must
contain exactly one `WAIT $00` plus optional `TEXT_CLEAR`. `$0192` is the sole weak
clause exception: its two source slots are independently complete sentences and the
French comma is accepted only because it is followed by the explicit continuation
connector `alors`. `$016E` separately crosses exactly one existing timed `WAIT $08`
at a complete sentence boundary; that timed wait remains byte-for-byte unchanged.

Three two-text mappings from a single Android unit cross only proven `OP_32`/`OP_34`
actor actions and `COMPLETE_ACTIONS`, with a complete source sentence before the action
and a complete French sentence at the split. `$066D` adds one narrow
semantic/layout-only/semantic form: the middle newline carrier remains stock while the
two complete French sentences are bound around actor actions and a clean-ROM call whose
callee is independently proven text-free, branch-free and returning. `$01C3` recognizes
only its exact sound-call -> vertical-shake -> timed `WAIT $10` -> stop-shake ->
sound-call sequence; both callees are independently sound-only returning scripts and no
effect byte is changed. Finally, the already user-validated `$0511`
`sequence_block_with_android_extra` mapping uses its exact four-anchor/three-statement
shape to redistribute the existing Android French over three semantic SNES slots while
preserving the stock layout carrier. Commands remain byte-for-byte in place.

Selection is deliberately two-stage and event-complete:

1. every semantic source ID in the event must already have an accepted Android
   alignment, and every mapping must bind/format without crossing an unsupported
   structural command;
2. the fully serialized candidate event must pass `tools/simulate_dialogues.py`
   with zero error, zero warning and zero implicit runtime wrap. Unsupported
   geometry therefore excludes the whole event instead of being guessed.

Current deterministic result: 704 semantic text events -> 431 completely aligned
-> 415 formatter candidates -> **392 simulator-clean events / 675 translated
source IDs** (692 JSON entries). The excluded-event split is 273 incomplete
alignments, 16 formatter rejects and 23 simulator rejects; every remaining simulator
reject contains unsupported choice layout. Sixty-two generated page transitions
occur in the accepted corpus. The current layout refinement also replaces legacy leading blank
scroll lines with clear-only `TEXT_CLEAR` transitions when the structure is proven.
After the historical compact-wrapper fallback has failed, events whose **only**
remaining simulator defect is `UNPAUSED_SCROLL` may try one additional page at a
proven sentence/semantic boundary inside an existing mapping. The candidate is
kept only after a completely clean event resimulation; this currently admits
`$0277`, `$0289`, `$02D2` and `$038E`. A separate narrowly gated repair admits `$02FD` and `$059B`: only after all
earlier fallbacks fail with a parser wrap plus unpaused scroll does it insert one
line break at an adjacent complete-sentence boundary and one semantic page transition.
The canonical boundary must contain only proven `OP_32`/`OP_34` actor actions and
`COMPLETE_ACTIONS`, and the whole event must then resimulate cleanly. Soft parser
wraps and decoded-capacity hard wraps use the same final proof. Events with unsupported
commands are not eligible.
Five accepted mappings contain speaker-after-sentence hard-line hints and one
contains a dash-attribution hint. The current semantic reflow changes line
placement in many accepted mappings; event `$0101` is presently the only event
that needs the automatic compact-layout fallback after simulator rejection.
Component 08 relocates 347 growing events; the final relocated payload still
fits entirely in the first `$E8` relocation bank in the current candidate.

`mappings/android/dialogues_format_mass.json` records every accepted/rejected
stage and `mappings/android/dialogues_format_mass_excluded.csv` gives a reviewable
row for every semantic source phrase belonging to an excluded event. This mass
output is a runtime candidate until a full playthrough is completed.

## 8.7 Exact rolling-window overlap cleanup

A later visual audit of the side-by-side simulator found a distinct layout case:
a stock interactive `WAIT $00` can leave one or two lines from the previous
three-line rolling window visible at the start of the next simulated state. This
is normal stock engine behavior, but after French reflow it can produce visually
redundant pages such as `Temple souterrain.` or two `dragon blanc...` lines
appearing unchanged in both states.

The mass generator now performs a conservative post-format pass driven by the
independent simulator. It only acts when the next state after an **interactive
`WAIT $00`** begins with an exact non-empty suffix of the previous state. It then
tries one source-structure-preserving repair: either a clear-only `TEXT_CLEAR`
before the next translated chunk, replacement of a newline-only stock scroll
token with `TEXT_CLEAR`, or removal of a trailing newline-only token when no
further prose follows. The repair is retained only if resimulation strictly
reduces the duplicated-line count and still has zero errors, zero warnings and
zero implicit wraps. Timed waits such as `WAIT $04` / `WAIT $08` are never
changed.

The rule is runtime-validated. The current mass output applies eight repairs in
`$0136`, `$016D`, `$0263`, `$0265`, `$026A`, `$03EE`, `$04AC` and `$0511`; the
simulator reports zero remaining exact carry-over after `WAIT $00`.

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


## 10. Charset audit

See `DIALOGUE_CHARSET_AUDIT.md` before expanding Android-derived formatting.
