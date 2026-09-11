# Stock dialogue/event format

This document records the mechanisms currently used by
`components/french_dialogues` for deterministic extraction and reinsertion. The
goal is to preserve the stock event structure exactly while exposing translatable
source text under `assets/` and keeping French edits separately under `translations/`.

The first edited-event experiment (`$0107`) is runtime-validated. The first
complete-event batch also runtime-validated `$010E`, `$0116`, `$0117`, `$0118` and
`$011D`. `$010F` exposed an exact-capacity `PLAYER_NAME` parser edge case; its
generated sentence-aware extra page is now runtime-validated and forms the basis
for the larger batch-2 candidate.

## Runtime layout rule for dynamic names

`vwf_dialogues` has a 38-unit private parser contract, but batch-1 runtime testing
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

`french_dialogues` intentionally excludes event `$0400` from its default asset because
that translated intro payload is owned by `french_intro`. It remains
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
boundary. The translated intro remains at `$E6`. `french_dialogues` consumes this
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
2. the `vwf_dialogues` parser's runtime-validated capacity of **38 decoded
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

`french_dialogues` reconstructs every selected event from the clean-USA canonical
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

Because fallback reads the live stock tables, the intro component pair remains owner of its
validated `$0400-$040F` pointer rewrites. `french_dialogues` does not duplicate or
freeze those pointers.

The relocation path is runtime-validated: unchanged event `$0107` was executed
from `$E8:2000` without changing its script bytes, and dynamic name insertion,
VWF rendering, line breaks, WAIT behavior and continuation all remained correct.
The temporary force probe has been removed; relocation now occurs only for
genuine translated-event growth.

Relocated event text must still use `vwf_dialogues`'s VWF path. The shared parser
caller gate and renderer caller gate therefore retain their validated structural
checks and add only the reserved relocation-bank range `$E8-$EC`. Existing `$C9/$CA` behavior is unchanged, and the added `$E8-$EC` bank range is
runtime-validated.

With no dialogue translations, no dialogue-charset writes are emitted by `french_dialogues`.
Once at least one translation changes source text, the builder installs the
`dialogue_french` `$D3-$E7` glyph span plus the same context-sensitive DTE router
as `vwf_dialogues`.

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
respecting the same 216-pixel safe-width and 38-parser-unit limits. If no safe sentence
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
  `\u000b`). `french_dialogues` compiles it to stock `TEXT_CLEAR` only. The existing
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
interactive WAITs. `vwf_dialogues` sends choice rows through its ordinary VWF path. Decorated
rows retain the validated stock `$A1D7[]` anchor/terminal behavior; undecorated two-option
rows can now use separately measured private visual/highlight boundaries while leaving
`$A1D7[]` logical and untouched. Potos runtime tests validate this compact path on `$00CE`,
`$00CF`, `$00D0`, `$00D1` and `$0202`. In the final two-cell-left geometry `$00D0` keeps the
normal separator and ends at private terminal cell `$1B`; the retained cell-`$11`
separator-omission fallback was separately runtime-validated on its earlier right-edge stress
checkpoint. The `$00DF` minimal rightward later-anchor storage shift also remains validated.
The 560-event corpus as a whole still requires full-game playthrough validation.

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
line, where `vwf_dialogues` renders the `nn` prefilled `$80` cells before the text.
The formatter now reserves those same proven padding cells against the first
generated line's 38-unit and 216-pixel safe-width budgets; following wrapped lines return to
the normal full budget. Android `▽` is removed only when the event itself proves a
`CHOICE_BEGIN` / `CHOICE_END` block. Choice recovery always keeps the first stock
`CHOICE_OPTION` anchor; after a simulator rejection, a later absolute anchor may move only
rightward to the minimum decoded-storage position required not to overwrite the preceding
localized label. Mid-line `TEXT_X` remains excluded rather than inferred. The canonical
outer `( ... )` choice decoration is presentation-only: it is preserved whenever the normal
event passes the simulator, but after a width/layout rejection the formatter may retry once
without the proven opening/closing parentheses and their adjacent horizontal padding. The
strip operation itself leaves all choice commands unchanged; if overlap still remains, it
may compose with the same later-anchor-only storage repair. A generated `\f` page transition
may end the prompt carrier immediately before a proven `CHOICE_BEGIN` after the opening
decoration has been stripped; this serializes only the validated `WAIT $00 + TEXT_CLEAR`
transition, not a printable trailing glyph. Every candidate is accepted only if the entire
event then returns to 0 errors / 0 warnings / 0 implicit wraps. A trailing `PLAYER_NAME` placeholder accidentally absorbed by alignment lookahead may be ignored
for binding only when the actual future event tokens prove the same `PLAYER_NAME`
after linear `WAIT`/`TEXT_CLEAR`/`OP_32`/`COMPLETE_ACTIONS` controls; the command itself
stays in its original SNES position.

Round 72 adds a reproducibility layer for the reviewed decoration decisions that had already been accepted in the generated checkpoint. `mappings/android/dialogues_choice_layout_recipes.json` records only the exact event/opening/closing carrier identities; it contains no French prose. These reviewed strips are reapplied even when the newer choice-specific simulator geometry would make the decorated row simulator-clean. If restoring the stock choice-row newline would otherwise create a fresh page, only the owning Android-FR mapping is reformatted with the existing compact wrapper before stripping. This preserves the reviewed output while keeping extraction/insertion fully source-derived.

`PLAYER_NAME` presentation mismatches are normalized only when the SNES structure
proves that no event command needs to be invented or moved. An exact leading
Android-French `%S(n,0) :` speaker label is removed when the mapped SNES source
contains no `PLAYER_NAME` at all; the remaining localized prose is unchanged.
Conversely, if Android French places literal text on both sides of an existing
`PLAYER_NAME`, a directly adjacent source text token may act as a carrier only when
it is punctuation/whitespace-only and therefore non-semantic. One additional carrier
case exposes a physically adjacent `PLAYER_NAME` already present immediately before
the punctuation-only token; it is accepted only when Android French proves that exact
extra leading placeholder.

Android may also reassign the same spoken line to a different party slot. When French
and SNES contain the **same number of dynamic placeholders in the same positions** but
the numeric indices differ, the formatter now rebinds each French placeholder
positionally to the already existing SNES `PLAYER_NAME` slot. This preserves the SNES
speaker/addressee identity and changes no event command. It currently unlocks `$01E7`,
`$04AA` and `$04B6`; applying the rule to the previously accepted corpus changes zero
serialized entries.

Round 28 adds a separate addressee-preservation case. When the canonical SNES span and Android EN both prove `STATIC_SPEAKER:%S(n)!/?`, Android FR may omit only the dynamic addressee while keeping the static speaker label. The formatter then preserves the already-existing SNES `PLAYER_NAME(n)` exactly where it sits and attaches only the source-proven punctuation after the localized static label. No command is created, removed, moved or reordered. This exact shape occurs in `$0112` and `$0212`.

Several conservative event-interruption fallbacks extend coverage without editing
stock control flow. Mappings spanning existing interactive `WAIT $00` boundaries
may redistribute French only at complete sentence boundaries; each boundary must
contain exactly one `WAIT $00`, optional `TEXT_CLEAR`, and may additionally contain the already-validated pure actor-action pair `OP_32`/`OP_34` + `COMPLETE_ACTIONS`. One dynamic placeholder is permitted only as an identical leading `PLAYER_NAME` immediately before the first mapped carrier; a name at or across the WAIT remains forbidden. `$04E8` is the sole mapping in the corpus with that leading-name shape, while `$0112` remains the composed action-bridge case. Every stock command remains byte-for-byte in place. `$0192` is the sole weak
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
effect byte is changed. `$010C` adds one distinct exact bridge shape: two semantic carriers
may span `OP_20..OP_27` -> one `OP_2D` effect -> `COMPLETE_ACTIONS` only when the called
clean-ROM event independently decodes to `PLAY_SOUND -> RETURN -> END`. SNES and Android EN
must contain no dynamic name. If Android FR alone inserts exactly one comma-delimited
`%S(n,0),` vocative, that vocative may be removed because there is no SNES `PLAYER_NAME`
command able to carry it; the remaining French is split only at a complete sentence boundary
and every bridge command remains unchanged. One newline may be materialized after the first
complete sentence only when the unchanged bridge would otherwise exceed same-line parser or
pixel capacity. The exact shape currently occurs once in the corpus. Finally, the already user-validated `$0511`
`sequence_block_with_android_extra` mapping uses its exact four-anchor/three-statement
shape to redistribute the existing Android French over three semantic SNES slots while
preserving the stock layout carrier. Commands remain byte-for-byte in place.

Selection is deliberately simulator-gated in two passes:

1. completely aligned events keep the established formatter/fallback chain and must
   pass the independent simulator with zero error, zero warning and zero implicit wrap;
2. alignment-incomplete events may contribute only their **already accepted** Android
   mappings. Every unmapped semantic source ID is omitted from the sparse French JSON, so
   clean-USA English remains visible for that carrier. Structural commands/layout remain
   canonical. Direct formatting is the default; when the unresolved carrier is explicitly
   `validated_no_equivalent` or `validated_android_omission`, the already-established
   whole-event compact wrapper may remove formatter-added presentation line breaks. For an
   explicit `validated_android_omission` only, an already accepted semantic mapping may also
   remain stock/layout-deferred when serializing its French would require an unsupported
   command crossing or a different canonical `PLAYER_NAME` stream. This never changes the
   accepted identity mapping, never fills the omitted carrier, and still may not add, remove
   or move any event command; the mixed FR/EN result must resimulate cleanly. A broader
   layout-deferral prototype was rejected because it would admit `$0204`, whose Android French
   genuinely redistributes content rather than exposing a pure layout problem.

Structural-review mappings are still subject to the same formatter/simulator gate. For
Android prompt/choice splits, the prompt may be rebound separately from already anchored
options while preserving the stock `CHOICE_BEGIN/CHOICE_OPTION/CHOICE_END` commands.
Speaker-reattributed Joch reactions may receive a page boundary only across the exact
proven `OP_20` bridge and only after clean whole-event resimulation. Mapping identity
never bypasses choice geometry.

Current deterministic result: **608 simulator-clean events / 1516 visible semantic
source IDs** (1596 JSON entries). This comprises 584 events treated as complete plus 24 PARTIEL events. `$0103`, `$017F` and `$01DC` are explicitly user-validated as complete Android adaptations; their validated omitted carriers remain suppressed independently of later semantic-alignment improvements. `$0602` is also presented as complete after runtime review found no visible missing/English content; unresolved `CA:85DD` remains tracked and the event serialization is unchanged. `$01DC` additionally drops the exact final stock `PLAYER_NAME(0)` bound to suppressed `C9:804A`. `$0042`, `$010C`, `$01B6`, `$04E8` and `$0558` are mixed FR/EN PARTIEL events whose unresolved carriers remain stock English; `$010C/C9:30F5` is an explicit `validated_android_omission`, and three already mapped `$010C` carriers remain stock/layout-deferred because their French would require unsupported structural rebinding; in `$04E8`, `CA:437D` (`...SHRIEK!`) remains explicitly `validated_no_equivalent` while the surrounding proven mappings render in French. `$0278` is the manual-supplement PARTIEL event and its two controller-specific SNES carriers are staged in the manual supplement JSON; `$02B0` is now complete after its final long contained Android-English unit was proven. `$00DF` is no longer layout-deferred: its second option moves minimally from `$11` to `$12`, a geometry change runtime-validated with `Temple de l'Eau / Pandora`; `$01EE` remains rendered through its structurally proven fresh-page choice carrier.

The current conservative choice-row recovery adds 11 complete events (`$0062`, `$0081`, `$00DB`, `$00DC`, `$00E2`, `$01B0`, `$01B3`, `$01DF`, `$0200`, `$0318`, `$065F`) without moving a first option anchor. It may restore a source-proven final `NEWLINE + (` suffix lost by Android prose reflow, materialize one newline before a standalone decorative `(` carrier when dynamic stock output consumed the choice row, and compose outer-decoration stripping with the already validated later-anchor-only shift. Every candidate still has to pass clean whole-event simulation.

The remaining excluded-event split is now **84 alignment-incomplete + 5 formatter-rejected + 7 simulator-rejected events**.
The latest semantic-alignment pass remains deliberately identity-first. Exact normalized English may
now bind across a different 1-3/1-3 SNES/Android segmentation when every exact Android copy
yields the same complete French localization and no source-span overlap is ambiguous. Exact
English duplicates with different French may be selected only from a tight event-local bracket
or a unique immediately adjacent owned anchor; calibration reproduced 23/23 existing accepted
choices with zero conflicts. A later isolated-contained-extension rule additionally
accepts a long SNES carrier only when its normalized token sequence occurs contiguously
inside the best longer Android-English record, with 100% source-token coverage, source
length >=35 normalized characters, lexical score >=76, character similarity >=68%,
and a >=30-point runner-up margin. Calibration reproduced 535/535 eligible accepted
mappings with zero conflicts. Together the current rules raise semantic alignment to
**1706 / 1838 (92.8%)**.
They do not bypass this formatter: `$0205`, `$02CD` and `$03F0` remain formatter rejects.
Round 32 instead admits `$0041` and `$03EA` only as strict PARTIEL safe-subsets, leaving
their refused structural mappings stock rather than weakening the semantic or command binder.


`$03AA` is now admitted by a narrow canonical-binding fix: trailing `PLAYER_NAME` lookahead may cross `OP_34` in the same way it already crossed `OP_32`, `WAIT`, `TEXT_CLEAR` and `COMPLETE_ACTIONS`. This only recognizes an already existing linear action context; it does not create, remove, move or retarget any command. `$01F6` is admitted by a separate exact Android-slot proof: French-only slot 697 starts with `%S(1,0)`, which belongs to the following English anchor 698 rather than preceding anchor 696; reassigning that one French slot makes both neighboring `PLAYER_NAME` sequences exactly match their already-aligned SNES streams. After the ordinary compact wrapper, the only remaining blocking defect is a same-line decoded-capacity wrap after `WAIT $00`; one explicit newline before `C9:8AE8` is accepted only as the unique immediate complete-sentence candidate that resimulates the entire event with zero errors, warnings and implicit wraps. `$01F6` remains `TO REVIEW` until runtime validation. `french_dialogues`'s simulator/serializer path now understands the measured-end choice geometry validated on `$00CE`, `$00CF`, `$00D0`, `$00D1` and `$0202`: `$A1D7[]` stays logical for storage, the first private visual/highlight boundary is `max(logical_first, $03) - 2`, a full blank cell is normally kept between measured endpoints, and the separately validated cell-`$11` fallback omits that extra cell only when a late first endpoint would otherwise threaten the right edge. Final `$00D0` now starts farther left, keeps the normal separator and ends at private terminal cell `$1B`. The rejected `$00CE` first-anchor-left probes (`$00/$0F`, `$01/$10`) remain diagnostic-only and must never be generated by the formatter. The generated translation contains explicit page transitions encoded as `WAIT $00` + `TEXT_CLEAR`; their exact count is generated-data dependent and is not a compatibility invariant. The
current layout refinement also replaces legacy leading blank
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
placement in many accepted mappings. `$0101` now has a runtime-reviewed explicit
three-line layout because a formatter-added fourth live line caused a fast scroll
that the older simulator did not detect.
`french_dialogues` relocates 515 growing events at the Round-32 checkpoint; the final relocated payload
now extends into `$E9`; the highest current relocated payload still remains well inside the runtime-validated reserved `$E8-$EC` pool.

`mappings/android/dialogues_format_mass.json` records every accepted/rejected
stage and `mappings/android/dialogues_format_mass_excluded.csv` gives a reviewable
row for every semantic source phrase belonging to an excluded event. This mass
output is a runtime candidate until a full playthrough is completed.

## 8.7 WAIT $00 rolling-window preservation

The stock dialogue box is a rolling three-line window. After an interactive
`WAIT $00`, one or two lines from the previous state can legitimately remain
visible while later text is appended. This can look like duplicated prose in a
static page-by-page preview, but it is presentation state rather than evidence
that the underlying dialogue text is duplicated.

The formatter therefore **does not automatically remove exact carry-over after
`WAIT $00`**. It does not insert `TEXT_CLEAR`, replace newline-only scroll
tokens, or remove trailing layout tokens merely to make consecutive simulator
states look unique. Timed waits such as `WAIT $02/$04/$08/$0C/...` are likewise
left untouched.

An earlier checkpoint had presentation repairs for `$00E3`, `$00FB`, `$0136`,
`$016D`, `$01BD`, `$0263`, `$0265`, `$026A`, `$029C`, `$02A7`, `$02AA`,
`$03EE`, `$04AC` and `$0511`. A later audit established that those repairs were
all driven by normal stock `WAIT $00` carry-over, so they are no longer applied.
If one of these events still appears wrong at runtime, it must be investigated
individually from source/event evidence rather than deduplicated automatically.

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

## Runtime-validated `$0106` fresh-page exception

Runtime testing found one presentation bug that the static rolling-window preview can
represent but cannot classify as wrong by itself. After the two-line French page ending
with `un fantôme qui rôde...`, the stock event executes `WAIT $00`, then carries a
newline-only text token at `C9:2994`, then begins the next speaker at `C9:299C`. With
only two visible lines before the pause, that newline consumes physical line 3 and the
following prose immediately scrolls, making the next page advance too quickly.

The validated correction is deliberately local: keep the stock `WAIT $00` unchanged and
compile only `C9:2994` as `TEXT_CLEAR` (`\v`). The next speaker then starts at line 1
on a fresh page. This does **not** restore the former generic WAIT-overlap cleanup.

For the next combined runtime test, the round13 review-only detector identified eight exact
matches of the same physical hazard: `$00FB/C9:2447`, `$0134/C9:3D03`,
`$016D/C9:4ECF`, `$01CA/C9:743D`, `$029C/C9:B1AD`, `$03EE/C9:F1E5`,
`$04A1/CA:197E`, and `$04EA/CA:4A6B`. At the user's request these eight carriers are
now compiled as `TEXT_CLEAR` while every stock `WAIT $00` remains unchanged. They are
**batch test candidates**, not runtime-validated exceptions, and remain TO REVIEW until
playthrough validation.
## Runtime-validated WAIT cursor semantics and explicit NEWLINE repair

Runtime testing on `$0106` established that `WAIT` pauses rendering **without moving the text cursor**. The previous simulator had incorrectly finalized the current line at every WAIT, so some formatter layouts appeared correct in HTML even though the serialized event lacked the required `$7F` NEWLINE. This explained `$0106` (`dites !` + `Houla !`) and the timed `...` sequence in `$0103`.

The simulator now keeps the live line across WAIT. The formatter materializes the already-reviewed intended boundaries as explicit `$7F` bytes in `$0103`, `$0106`, `$0136`, `$0167`, `$016D`, `$016E`, `$01C3`, `$0228`, `$0259`, `$026A`, `$055E`, and `$059B`. WAIT bytes remain unchanged. `$026A` requires a fresh-page `TEXT_CLEAR` rather than a simple newline because its two-line retained state plus the following two-line prose would otherwise scroll before the next pause. These repairs are layout-only batch-test candidates until runtime review, except the previously validated `$0106/C9:2994` fresh-page fix.

Future formatter changes must not infer a newline from WAIT itself. A desired line transition must be serialized explicitly and then pass the corrected simulator with zero errors, warnings and implicit wraps.

### Round 22 `$02AE` timed-WAIT resegmentation candidate

Android EN 1630 merges the two SNES Amar fragments separated by stock `WAIT $10`; Android
FR 1630 is likewise one rewritten localization unit. The round22 formatter is deliberately
event-specific: it keeps `WAIT $10` unchanged, splits the exact Android French only at a
complete-sentence boundary, requires the pre-WAIT piece to fit on one physical line, and
emits one explicit newline before the timed pause so the post-WAIT piece starts on the next
physical line. The final event independently simulates with no implicit wrap. This is a
`TO REVIEW` layout candidate, not a generalized timed-WAIT rule or a runtime-validated fix.



## Runtime-reviewed `$0101` live fourth-line overflow

Runtime capture on `$0101` showed that the official French `Aïe... Pfiouh.` had
been split by the formatter into two physical lines. Together with `Pas moyen de
remonter !` and `Comment je vais faire ?`, this created four lines before the
next `WAIT $00`; the live fourth line therefore scrolled the first line away and
made the final sentence appear in a rapid follow-up state. Stock English keeps
`Ouch! Phew..!` on one line.

The correction keeps the Android French wording unchanged and removes only that
formatter-added break: `Aïe... Pfiouh.` stays on one physical line, followed by
`Pas moyen de remonter !` and `Comment je vais faire ?` on lines 2 and 3. No
WAIT, TEXT_CLEAR, actor command, or semantic mapping is changed.

The simulator now also emits the review-only diagnostic
`UNPAUSED_LIVE_LINE_SCROLL_RISK` when text begins a fourth non-empty live line
before the next pause. This catches the failure at the moment the cursor enters
the scrolling line, even if a WAIT arrives before that fourth line is formally
finished. The diagnostic does not rewrite events automatically. After the
`$0101` correction, the current corpus has 15 unique review candidates:
`$0106`, `$01D3`, `$01DC`, `$01DD`, `$01F6`, `$0259`, `$0263`, `$0289`,
`$02D2`, `$02EE`, `$036F`, `$04A1`, `$04EA`, `$059B`, and `$066D`.
`$036F` and `$04EA` each contain two occurrences.

## Round 31 structural formatter rules

The high-leverage Round-31 pass adds three deliberately narrow formatter behaviors. None creates semantic identity.

- A structurally reviewed **2-SNES / 1-Android** unit may distribute official French across one exact stock `WAIT $10`. The timed wait is preserved byte-for-byte. `$02AE` keeps the historical newline before the wait; `$042D` keeps its canonical newline after the wait. The formatter explicitly rejects an invented `TEXT_CLEAR` in the latter shape.
- One Android anchor may distribute across exactly two SNES text carriers separated solely by one stock `TEXT_X` when the first stock carrier already ends in `NEWLINE` and Android French contains exactly two non-empty lines. Both localized pieces must fit independently; the stock newline and `TEXT_X` stay unchanged. The generic shape is also recognized on `$0041`, which remains formatter-rejected for its independent `OP_38` crossing, so the rule does not opportunistically promote that event.
- In a PARTIEL event with an immediately following `validated_no_equivalent` or `validated_android_omission` hole, a trailing `PLAYER_NAME` used only as alignment lookahead may be returned to that stock hole when the canonical token stream proves exact adjacency and French does not own the same trailing placeholder. `$0558` uses this to keep `CA:6629` stock English. Its remaining pure `UNPAUSED_SCROLL` defect is handled only by the pre-existing simulator-selected sentence-boundary pagination repair; the unique clean candidate inserts the page boundary after `Où suis-je ? / Ah !`.

After these changes the deterministic corpus is **568 simulator-clean events / 1362 visible semantic source IDs / 1430 JSON entries**: **562 complete + 6 PARTIEL** (`$0042`, `$010C`, `$01B6`, `$0278`, `$04E8`, `$0558`). The exclusion split is **113 alignment-incomplete + 23 formatter rejects**. The entire Round-30 translation remains byte-for-byte unchanged (**1397/1397 entries, 0 removed**) and 33 entries are added.

## Round 32 generic structural safe-subset PARTIEL

Round 32 adds **no semantic identity**: alignment remains **1670 / 1838 (90.9%)**, with 168 unresolved IDs. Instead, the mass formatter can preserve a semantically accepted carrier in stock English when serialization fails only at an already-recognized unsupported structural/`PLAYER_NAME` boundary. The whole mapping is deferred; no text is split across the refused bridge, no stock command is moved/created/removed, and at least one independent French mapping must remain. These generic candidates receive **no compact, pagination, choice-anchor or other adaptive rescue**: the direct mixed event itself must independently simulate with 0 errors, 0 warnings and 0 implicit wraps. `$015A` and `$0204` are explicitly excluded because their known problems are semantic/resegmentation hazards rather than mere layout refusal.

A generated trailing `\f` at the end of a mapped carrier is likewise not allowed to invent a page command. It is directly serializable only in the two existing codec-proven choice-adjacent shapes (immediate `CHOICE_BEGIN`, or `TEXT_X` + decorative `(` carrier + `CHOICE_BEGIN`); otherwise the whole mapping can only remain stock under the same strict safe-subset gate.

This generic rule is exercised by **12 PARTIEL events / 30 deferred semantic IDs**. `$01DA` additionally uses one exact reviewed layout deferral, and `$023C` is admitted as an alignment-incomplete PARTIEL through the existing validated choice geometry without generic deferral. `$05F8` is intentionally rejected: even after all recognized bridges remain stock, direct simulation still reports wraps inside stock/deferred regions, so making it pass would require altering content that the safe-subset rule promises not to touch.

The Round-31 translation is preserved byte-for-byte (**1430/1430 entries unchanged, 0 removed**) and **70 entries are added**. The deterministic corpus becomes **582 simulator-clean events / 1428 visible semantic source IDs / 1500 JSON entries**: **562 complete + 20 PARTIEL**. Exclusions are **110 alignment-incomplete + 4 formatter-rejected + 8 simulator-rejected events**.

## Round 33 contextual review and direct-simulator safe-subset

Round 33 raises semantic alignment to **1696 / 1838 (92.3%)**, leaving **142 unresolved**. All new identities are explicit Android-English structural/user reviews; Android French remains payload only. The user validated the candidate batch through a contextual HTML sheet that shows SNES USA, Android EN, Android FR and neighboring Android context. That presentation is now the preferred review UI for ambiguous future mappings and does not authorize a generic short-exact rule.

The formatter adds one second-stage conservative fallback after ordinary formatting / generic structural safe-subset still fails direct simulation. The stock event must itself simulate clean; at most three **whole mappings** may be left stock; each candidate must individually reduce the direct simulator defect score; and the deterministic smallest subset must make the remaining mixed event directly reach 0 errors, 0 warnings and 0 implicit wraps. No command, mapping identity, bridge, compact repair or adaptive pagination is modified. It is currently exercised by exactly **2 events / 5 mapped IDs**: `$04E2` defers `CA:32C5`, `CA:3362`, `CA:3423`, and `$0592` defers `CA:750D`, `CA:752E`.

`$05B4/CA:7864 -> Android 1887` is an accepted identity but deliberately remains formatter-rejected/stock. Android 1887 combines the `634` line with the `...! Enter!` tail that SNES `$05B4` obtains through a call to `$03A7`; direct insertion would duplicate that translated called tail. This requires an explicit cross-event resegmentation if revisited.

The Round-32 translation is preserved byte-for-byte (**1500/1500 entries unchanged, 0 removed**) and **86 entries are added**. The deterministic corpus is **598 simulator-clean events / 1506 visible semantic source IDs / 1586 JSON entries**: **574 complete + 24 PARTIEL**. Exclusions are **94 alignment-incomplete + 5 formatter-rejected + 7 simulator-rejected events**.

## Round 34 additive structural pass

Round 34 adds ten explicit semantic mappings and does not change formatter behavior. All ten newly completed events format through the existing rules and pass direct simulation without safe-subset fallback. The Round-33 translation is preserved exactly (**1586/1586 entries unchanged, 0 removed**) and 10 entries are added.

The deterministic corpus is now **608 simulator-clean events / 1516 visible semantic source IDs / 1596 JSON entries**: **584 complete + 24 PARTIEL**. Exclusions are **84 alignment-incomplete + 5 formatter-rejected + 7 simulator-rejected events**. The independent simulator remains at **0 errors / 0 warnings / 0 implicit wraps**.



## Round 45 reviewed resegmentation

Round 45 adds two exact serializer paths and no generic formatting behavior. `$01B6` reconstructs Android EN 584 across two SNES carriers separated by the stock Watts movement/text-close/text-open bridge. Android FR has moved the shortcut introduction into already-owned slot 583 and keeps only the post-movement continuation in FR-only slot 585, so `C9:6AD2` is empty and `C9:6B5A` receives the continuation while every bridge command remains stock.

`$01DA` completes the girl's naming scene across `C9:7E64`, `C9:7E72`, `C9:7E81`. Android FR 676 keeps the first two boy-name placeholders but FR 677 omits the third repetition before `Moi, c'est...`. The serializer therefore preserves the first two `PLAYER_NAME(0)` commands and suppresses only the third command immediately before empty `C9:7E81`. This omission is recorded in `DIALOGUE_USER_VALIDATED_STRUCTURAL_OMISSIONS` and is valid only for this exact event/carrier relation. It must not be generalized. With a nine-character player name the complete event simulates with 0 errors, 0 warnings and 0 implicit wraps. Completing the event causes four already-French carriers (`C9:7D15`, `C9:7D47`, `C9:7D55`, `C9:7E12`) to be reflowed by the whole-event formatter; their semantic payload is unchanged.


## Round 48 exact Android-FR-only vocative repairs

Some official Android-FR strings introduce `%S(n,0)` as a conversational vocative even though the corresponding Android-English identity and the SNES carrier contain no dynamic addressee. Round 48 permits removal only for seven reviewed carrier/Android-ID pairs recorded in `mappings/android/dialogues_review_round48.json`. This is an exact allow-list: it must not become a generic `%S` deletion rule, and it never creates, moves or removes a SNES `PLAYER_NAME` command.

`$0127` is separately allow-listed for exact pagination because its already-proven French scene otherwise exceeds the dialogue page geometry. Two `WAIT $00 + TEXT_CLEAR` transitions are placed only at reviewed sentence boundaries, and one `TEXT_CLEAR` follows the existing stock `WAIT $08`. Actor actions, both stock `PLAYER_NAME(0)` commands and the timed wait remain in source order. The resulting Round-48 corpus is **680 simulator-clean events**, with **0 errors, 0 warnings and 0 implicit wraps**.


## Round 49 exact formatter/simulator recovery

Round 49 changes **no Android-English identity** and adds no generic matcher or formatter relaxation. `$02CD/C9:BE42 -> Android 1735+1736` is admitted only after removing the exact Android-FR-only `%S(0,0) :` speaker label; Android EN and the complete SNES event contain no `PLAYER_NAME`, so no dynamic command is created, moved or removed. The official French remainder formats to two clean lines.

`$03F0/C9:F29A+C9:F2AC+C9:F2BA -> Android 2361` is one exact machine-noise sequence. The three official French noise fragments are distributed over the three stock carriers while all three `PLAY_SOUND` commands and the stock `WAIT $10` remain byte-for-byte in place. A presentation-only newline is added to `C9:F2AC` immediately before that existing timed wait; this is deliberately explicit because `WAIT != NEWLINE`, and it removes the simulator's same-line-continuation warning without inventing a pause.

`$04E9` becomes a simulator-clean **PARTIEL**. Seven already-proven mappings render in French. `CA:4745` and `CA:4797` each receive a leading `TEXT_CLEAR` only after the exact existing `WAIT $00` that precedes them, because the official French paragraphs occupy three physical lines and otherwise inherit the retained cursor. No extra interactive wait is added. The final accepted mapping `CA:48DC+CA:4925 -> Android 895` remains stock/layout-deferred: Android FR condenses the two SNES carriers into one sentence across `WAIT $00`, so there is no complete-sentence split to serialize conservatively.

`$0205` remains formatter-rejected for the same reason: Android FR condenses two SNES carriers separated by canonical `PLAYER_NAME(0)`, `WAIT $00` and `TEXT_CLEAR` into one sentence. No forced clause split is introduced. The resulting Round-49 corpus is **683 simulator-clean events = 659 complete + 24 PARTIEL**, **1624 visible semantic IDs / 1708 JSON entries**, with exclusions **15 alignment-incomplete + 2 formatter-rejected + 4 simulator-rejected**, and the simulator reports **0 errors / 0 warnings / 0 implicit wraps**.


## Round 50 simulator-model / exact-choice recovery

Round 50 remains an identity-neutral pass. Semantic Android alignment stays **1798 / 1838 (97.8%)** with **40 unresolved**. No generic matcher, namespace expansion, formatter threshold relaxation, or automatic short-exact rule is introduced.

`$0040` is admitted as **PARTIEL** after static 65816 analysis of the stock `TEXT_X` implementation. The handler at `$C0:1883` and shared setter at `$C0:18FB` write the absolute value to both `$7E:A1CE` and `$7E:A173`; the parser later restores its decoded-buffer write index from `$A173`. The simulator therefore models only forward/equal absolute resets by retaining the already-decoded prefix and padding the clean `$80` buffer up to the requested position. Backward resets remain a hard `TEXT_X_BACKWARD_RESET_UNSUPPORTED` error because they overwrite already-decoded cells and no translated event needs that shape. This is a simulator model correction, not a formatter relaxation. `$0040/C9:0F75` remains stock/layout-deferred because its Android-FR dynamic-name structure does not match the SNES `PLAYER_NAME` commands.

`$04FD` is admitted as **PARTIEL** without simulating credits geometry. Its 19 `ending_text` blocks are accepted only if the final serialized `$7D...$7E` bytes are **exactly identical, in count/order/content, to the clean USA event**. Any changed, reordered, missing or added ending block is a hard simulator error. The ordinary ending-scene dialogue can therefore be translated while the special renderer remains protected; `CA:4E2F` stays stock/layout-deferred.

`$01CE` becomes **complete** by resegmenting an already-owned Android-English unit, not by adding identity. Android 536/537/538 is the determinate donation-prompt / Yes / No triplet. The canonical SNES stream is `C9:7827 -> CHOICE_BEGIN -> CHOICE_OPTION $04 -> C9:7856 -> CHOICE_OPTION $0B -> C9:785C -> CHOICE_END`, so Round 50 binds 536 only to `C9:7827` and 537 only to `C9:7856`; 538 was already independently accepted for `C9:785C`. The existing `WAIT $00` immediately before newline-only `C9:7824` is preserved, and that exact layout carrier alone becomes `TEXT_CLEAR`, starting the three-line French prompt on a fresh page. Money-window and choice commands are unchanged.

`$0429` remains the sole simulator-rejected event. A diagnostic mixed-FR candidate shows that it can be made statically wrap-free only by combining several presentation changes, including an English layout-only reflow of deferred `CA:110A` around the stock `PLAYER_NAME` redistribution. That is beyond the current exact semantic proof, so Round 50 deliberately leaves it excluded and exposes it in the contextual review HTML instead of forcing a repair. `$0205` and locked `$05B4` remain the two formatter rejects.

The Round-50 candidate corpus is **686 simulator-clean events = 660 complete + 26 PARTIEL**, **1646 visible semantic IDs / 1731 JSON entries**, with exclusions **15 alignment-incomplete + 2 formatter-rejected + 1 simulator-rejected**. Compared with Round 49, all **1708/1708** previous translation entries remain byte-for-byte unchanged, **23 entries are added**, and none are removed or modified. Static accepted-event simulation remains **0 errors / 0 warnings / 0 implicit wraps**.


## Round 52 exact bridge allow-list

Round 52 deliberately does **not** generalize the existing action/WAIT fallbacks. Six mappings with already-proven Android-English identity are handled only when event ID, SNES carrier sequence, Android ID sequence, canonical source text, Android EN/FR payload and every intervening command all match an exact allow-list record. Any drift becomes a hard formatter error.

The admitted bridges are `$01B5` Android 577, three `$01B9` mappings (593/596/599), `$04E6` Android 86 and `$04E7` Android 95. Stock WAIT/action commands are never moved or removed. Two layout-only newline carriers are promoted to page clears only after already-existing waits: the formatter-generated leading page reset before `$01B9/C9:6CDD`, and explicit newline-only `$01B9/C9:6DBC -> TEXT_CLEAR`; `$04E7` additionally emits one `TEXT_CLEAR` at the beginning of the goodbye carrier immediately after the stock `WAIT $08`. `WAIT` itself remains a pause, never a newline.

The mass corpus becomes **686 events = 663 complete + 23 PARTIEL**, **1658 visible semantic IDs / 1745 JSON entries**. The Round-50 baseline's **1731/1731** existing entries are unchanged and 14 are added. Accepted-event simulation remains **0 errors / 0 warnings / 0 implicit wraps**.


## Round 54 exact Android-FR completion allow-list

Round 54 runs only after the Round-53 Android source audit proved that no additional identity can be recovered under the current policy. It adds **no Android ID, no matcher, no namespace expansion and no generic formatter relaxation**. Five already-owned units are serialized only when event ID, SNES carrier set, Android ID, Android EN/FR payload and a canonical stock token window all match an exact allow-list.

- `$0040 / Android 681`: preserve both stock `PLAYER_NAME(1)` commands and serialize only ` : Moi, c'est ` / ` !` around the second name.
- `$0041 / Android 625`: split the official French at the complete sentence boundary across the unchanged `OP_38 01 + OP_10 42` bridge.
- `$013A / Android 848`: serialize the complete official French first sentence on `C9:4094`; leave `C9:40D7` stock because Android FR genuinely omits the second SNES instruction. The event therefore remains visibly PARTIEL with reason `official_android_fr_omission`.
- `$0559 / Android 2146`: fill only the punctuation/layout carriers around the existing stock `PLAYER_NAME(0)/(1)` commands; Android 2147 stays deferred because its FR introduces an extra `PLAYER_NAME(1)` not present in SNES.
- `$0592 / Android 1030`: place the official French on the available third physical line after the stock `WAIT $18`, preserving the following `WAIT $00 + TEXT_CLEAR`; Android 1031 remains deferred.

Relative to the runtime-validated Round-52 payload, **1745/1745 existing entries are byte-for-byte unchanged**, **8 entries are added**, and none are removed or modified. Corpus: **686 events = 665 complete + 21 PARTIEL**, **1663 visible semantic IDs / 1753 JSON entries**, exclusions unchanged at **15 alignment-incomplete + 2 formatter-rejected + 1 simulator-rejected**. Static simulation remains **0 errors / 0 warnings / 0 implicit wraps**. The Round-54 payload is pending runtime validation.
