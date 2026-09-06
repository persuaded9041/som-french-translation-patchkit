# Android text alignment research

This document records the current method for aligning clean-USA SNES text with
the original Android English/French resources. Coverage is deliberately small:
certainty is preferred over automatic breadth.

## 1. Confirmed `scrtxt` container structure

Both supplied `scrtxt_en.bin` and `scrtxt_fr.bin` use the same binary layout:

```text
uint32_le entry_count
uint32_le string_pool_size
entry_count times:
    uint32_le text_id
    uint32_le pool_offset
UTF-8 NUL-terminated string pool
```

For the current files:

- `entry_count = 3500`;
- IDs are contiguous `1..3500` and table records are sorted by ID;
- offsets are relative to the start of the string pool;
- pool offset `0` contains an initial NUL byte and ID 1 starts at offset 1;
- strings are tightly packed: each next offset starts immediately after the
  previous NUL terminator;
- English and French expose exactly the same 3500 IDs.

Hashes:

- `scrtxt_en.bin`: `4d4508560967b6ce4d6cf992f29e84e2775ed4accc74d87c3fd4269044b75ae5`
- `scrtxt_fr.bin`: `cd837aaf53a7979d0e84910e8cda3bd67427f4a3cbddadc351811378d7e7d696`

The IDs are therefore a stable Android resource namespace, but this does **not**
mean that one Android ID is always one indivisible translation unit.


### Separate `systxt` namespace

The supplied `systxt_en.bin` / `systxt_fr.bin` pair uses the same binary
container shape but contains 1300 contiguous IDs `100000..101299`, disjoint from
`scrtxt` IDs `1..3500`. The observed content is system/interface-oriented. This
strongly supports a top-level Android resource-family split rather than one
global text-ID sequence. `systxt` is preserved under `sources/android/` but is
out of scope for the current dialogue pilot.

## 2. Important slot behavior

The English file contains 2973 non-empty entries and 527 empty entries. If each
non-empty English entry is treated as an anchor and the following English-empty
IDs up to the next non-empty entry are treated as its available interval, the
observed interval widths are:

| Width | Count |
|---:|---:|
| 1 | 2464 |
| 2 | 493 |
| 3 | 14 |
| 4 | 2 |

French uses at least one following English-empty slot in 56 of these intervals.
There is also one observed interval where the French anchor ID itself is empty
but a following slot contains the localized text (`584 -> 585`).

Examples strongly support the working interpretation that empty English IDs can
serve as localization expansion slots:

- English ID `2431` contains the complete Jehk training sentence; French uses
  both `2431` and formerly-empty `2432`.
- English ID `2676` contains the complete ocean/Meria sentence; French uses
  `2676`, `2677` and `2678`.
- English ID `584` is non-empty, while French `584` is empty and French `585`
  carries the localized continuation.

This is an empirical grouping rule, not yet a promise that every empty slot has
the same runtime purpose. For import work, the safe unit is therefore the
**English anchor interval**, not blindly `French[English_ID]`.

## 3. What the Android ID order tells us

The ID namespace does not mirror SNES ROM addresses or SNES event IDs globally.
High-confidence matches jump between distant Android ranges even when SNES event
IDs are adjacent.

Local scene order is much stronger. In coherent scenes, Android IDs usually
preserve dialogue order even when wording changed. A broad exploratory pass found
167 SNES events with at least two strong unique lexical anchors; 160 of those
kept the strong anchors in strictly increasing Android-ID order. This is useful
context evidence, but the seven exceptions are enough to prohibit a global
"event order = Android order" rule.

The end of `scrtxt` is a useful structural example: IDs around `3399-3500`
contain the new-game/waterfall sequence, mobile credit records, four repeated
copies of the eight intro paragraphs (`3445-3476`), then the waterfall scene.
The repeated intro blocks alone prove that exact text matching cannot choose an
ID without contextual evidence.

Current conclusion: Android IDs behave like resource/script slots with strong
**local** ordering, not a simple transform of SNES event number, address, or
story chronology.

## 4. Matching signals

The pilot uses multiple independent signals:

1. **English lexical similarity** after case/layout/punctuation normalization.
2. **SNES-token coverage**: how much of the SNES wording appears in the Android
   English candidate, useful when Android expanded a sentence.
3. **Candidate margin** over the next-best Android English string.
4. **Local order** inside a coherent scene/event run.
5. **Slot structure**, including English-empty/French-empty bridge IDs.
6. **Distinctive names and wording** such as Elliott/Timothy, Sergo, Mana terms,
   place names, etc.
7. **Dialogue structure and placeholders**. Dynamic-name and split/merged cases
   are not imported until their command boundaries are explicitly understood.
8. **Neighbor context** before and after the candidate.

No single numeric score is sufficient. A textually perfect duplicate remains
ambiguous when context cannot distinguish its copies.

### Confidence policy

- `very_high`: lexical evidence is unique or nearly unique **and** a coherent
  local scene/order/structure independently supports it.
- `manual_review`: duplicate match, one-to-many/many-to-one segmentation,
  placeholder mismatch, weak context, or any contradiction between signals.

Only `very_high` mappings may eventually feed automatic translation generation.
The current pilot still disables dialogue translation generation entirely while
slot merging and SNES dialogue layout policy are being validated.

## 5. Pilot A: event `$0106`, waterfall conversation

This is the strongest initial scene because a long local sequence aligns in the
same order. The larger SNES event begins with split text chunks corresponding to
Android `3477-3481`, then the five selected prose blocks below correspond to
`3482, 3484, 3486, 3488, 3490`.

Between them, Android IDs `3483, 3485, 3487, 3489` are empty in both English and
French. The SNES event also contains newline-only text tokens between these
spoken blocks. That repeated structural pattern is independent evidence in
addition to lexical similarity.

| SNES ID | Android anchor | Lexical score | SNES-token coverage | Margin | French non-empty IDs |
|---|---:|---:|---:|---:|---|
| `C9:2900` | 3482 | 96.2 | 100% | 57.2 | 3482 |
| `C9:294C` | 3484 | 100.0 | 100% | 56.2 | 3484 |
| `C9:299C` | 3486 | 97.2 | 100% | 51.7 | 3486 |
| `C9:29E8` | 3488 | 89.3 | 100% | 43.4 | 3488 |
| `C9:2A3D` | 3490 | 100.0 | 100% | 48.2 | 3490 |

`C9:29E8` is intentionally instructive: Android adds wording ("seeing" and "a
long time ago"), reducing character similarity, but every normalized SNES token
is still covered, the next candidate is far behind, and it sits exactly between
four independently strong scene anchors. This is why context can raise a
non-exact lexical match to very high confidence.

No French text from these IDs is committed to `translations/dialogues_french.json`
yet.

## 6. Pilot B: event `$002C`, Sergo follow-up

Two consecutive SNES blocks match Android English IDs `2675` and `2676`
byte-for-word after layout/case normalization, with large candidate margins.
The alignment itself is very high confidence.

The second anchor demonstrates why French extraction must be separate from
English alignment: English `2676` is followed by empty IDs `2677-2678`, while
French uses all three IDs `2676-2678`. The eventual importer must deliberately
merge/reflow that localized unit; taking only French ID `2676` would be
incomplete.

## 7. Explicitly ambiguous examples

The pilot keeps failure cases visible rather than forcing a result:

- SNES `C9:089B` (`Revived Mana Sword!`) exactly matches both Android `3314`
  and `3360`; text alone cannot choose.
- SNES `C9:0C19` (Krissie boost line) exactly matches Android `2667` and `2793`.
- SNES `C9:0B03` is one SNES text block, while Android splits the same content
  into `2449+2450`; the same pair is duplicated again at `2463+2464`.

These remain `manual_review` in `mappings/android/dialogues_pilot.json` even
though parts of their text match perfectly.

## 8. User validation of the first pilot

The first 10-row visual CSV review was validated by the user: all proposed
source/translation texts correspond semantically. This validates the pilot
**alignment method**, not SNES layout formatting. Android line wrapping remains
source data only; SNES-specific wrapping/reflow is a separate later step.

The three deliberately ambiguous duplicate cases remain ambiguous as Android
**locations**, but their duplicate copies carry identical French text in the
current Android resource. The ambiguity therefore matters for structural
provenance even when it does not change the recovered translation prose.

## 9. Round-2 validation

`mappings/android/dialogues_review_round2.json` contains 23 alignment units from
three scenes. The complete batch was visually validated by the user.

It established several representations beyond simple 1:1 pairs:

- SNES text fragments separated by `PLAYER_NAME` -> one Android anchor;
- one SNES text token -> several Android anchors;
- several SNES text tokens -> one Android anchor;
- Android English anchor intervals with following localization slots;
- a scene block where French content is redistributed between adjacent IDs.

The validation also established an important policy rule: **Android English is
the identity layer**. When SNES USA -> Android English is very-high-confidence
from lexical and structural/context evidence, a freely adapted French line does
not invalidate that mapping. For example Android English ID `61` is an exact
match for the SNES Elliott line while French ID `61` is `Bob : Reste là !`; the
user confirmed that this is a valid localization correspondence in context.

Likewise, event `$0138` (Luka/Undine directions) demonstrates that French may
redistribute scene content across adjacent IDs even when Android English aligns
1:1 and in order. Such cases are kept as sequence blocks rather than forcing a
false per-ID French equivalence.

This validates separation of the workflow into two layers:

1. establish SNES -> Android-English identity with high confidence;
2. recover the French localization unit/block from the corresponding Android
   slot structure, without requiring literal French wording.

SNES-specific wrapping/reflow remains a later, separate deterministic step.

## 10. Round-3 validation

`mappings/android/dialogues_review_round3.json` extends the same method to 33
units across three additional scenes. The complete batch was visually validated
by the user:

- event `$04E0`: Jema / Pure Land directions, Android `2654-2664`;
- event `$066D`: Santa Claus / Frost Gigas aftermath, Android `1851-1863`;
- event `$0511`: Resistance meeting before the Emperor truce, Android
  `1983-1998` with gaps and Android-only material.

The first two scenes are deliberately strong controls: almost every unit is an
exact normalized English match and the anchors form coherent ordered local runs.
They also exercise `PLAYER_NAME` and SNES event-action splits.

Event `$0511` tests a harder structural case. Android English ID `1988` contains
a sentence that has no extracted SNES-USA counterpart, and Android `1996` adds a
Dyluck sentence after three SNES statements aligned to `1993-1995`. French
redistributes the local conversation across `1993-1996`. The importer therefore
records this as `sequence_block_with_android_extra`; it does **not** invent a
SNES ID for Android-only prose and does not force a per-ID French mapping.

The Resistance block also confirms that extra Android/localization detail is
not by itself evidence of a bad alignment when the surrounding Android-English
identity is strong. A later release may preserve dialogue detail that the SNES
USA script condensed.

## 11. Round-4 diversity batch

`mappings/android/dialogues_review_round4.json` contains 37 additional units
chosen for structural diversity rather than raw coverage:

- event `$022E`: Gnome joins after Tropicallo, Android `1034-1046`;
- event `$0581`: Undine grants magic and the Pole Dart, Android `956-972`;
- event `$04B3`: Emperor trap / Sheex reveal, Android `2681-2690` then
  `2723-2727`.

This batch deliberately exercises several cases needed by a future automatic
aligner:

- `PLAYER_NAME` placeholders embedded between separate SNES text tokens;
- one Android speech line spanning SNES text chunks separated by event-action
  commands;
- layout-only SNES text tokens around semantic dialogue;
- English-empty Android localization slots used by longer French prose;
- a large Android-ID jump inside one SNES event while the local narrative order
  remains coherent;
- minor English version edits that preserve distinctive vocabulary and full
  scene context.

Examples of localization-slot behavior include Android English anchor `965`,
whose following empty slot `966` is used by French to continue the Ice Saber
explanation, and anchor `2686`, whose English-empty slot `2688` carries extra
French Sheex dialogue. These are recovered as complete anchor intervals rather
than truncated at the English anchor ID.

Round 4 was visually accepted in full by the user. All 37 units are now
recorded as `user_validated`.

## 12. Reproducible checkpoint

`tools/import_android_text.py` keeps translation generation separate from
alignment research:

```bash
# Existing runtime-validated intro generation
python3 tools/import_android_text.py --only intro
python3 tools/import_android_text.py --only intro --check

# Validated pilot alignment checkpoint
python3 tools/import_android_text.py --only dialogue-pilot
python3 tools/import_android_text.py --only dialogue-pilot --check

# User-validated round 2
python3 tools/import_android_text.py --only dialogue-review
python3 tools/import_android_text.py --only dialogue-review --check

# User-validated round 3
python3 tools/import_android_text.py --only dialogue-review-round3
python3 tools/import_android_text.py --only dialogue-review-round3 --check

# User-validated round-4 diversity batch
python3 tools/import_android_text.py --only dialogue-review-round4
python3 tools/import_android_text.py --only dialogue-review-round4 --check

# Final pre-automation stress-test review
python3 tools/import_android_text.py --only dialogue-review-round5
python3 tools/import_android_text.py --only dialogue-review-round5 --check
```

The dialogue modes read `assets/dialogues.json`, `scrtxt_en.bin` and
`scrtxt_fr.bin`, recompute the evidence and slot intervals, and write only under
`mappings/android/`. `translations/dialogues_french.json`, component 08 and the
existing build outputs remain unchanged.

## 13. Round-5 stress test: auditing non-monotonic events

`mappings/android/dialogues_review_round5.json` contains 55 review units across
five SNES events selected specifically because a strong-anchor scan did **not**
produce one globally increasing Android-ID sequence for the whole event. Two
additional SNES source strings are recorded explicitly as unmatched rather than
being forced onto weak candidates.

The main structural result is that the SNES **event** is too coarse to be the
automatic aligner's ordering unit. Four of the five apparent failures are
explained by one SNES event spanning multiple narrative/text subscenes that the
Android resource stores in different ID blocks:

- `$0112`: the Mantis Ant rescue/tutorial line is Android `123`, then the Mana
  Sword/Jema exposition resumes in Android `13-27`;
- `$036A`: Scorpion Army aftermath is `1154-1155`, while the following party
  suggestion is Android `489`;
- `$04E4`: white-dragon discovery is `1448-1452`, then the Truffle/Flammie
  conversation is `1372-1383`;
- `$04E8`: goblin capture/rescue runs through `134-186`, then the post-rescue
  girl conversation is `125-132`.

Inside each coherent subscene, ordering remains strong. `TEXT_CLOSE` / later
`TEXT_OPEN` transitions and substantial event-action boundaries frequently
coincide with the Android-block reset, although they must be treated as evidence
rather than a universal hard rule because Android can also merge speech across
SNES event actions.

Event `$0204` is the important genuine exception. SNES places the instruction
`C9:9076` ("The world has 8 palaces...") **after** the Mana Seed ritual, but its
unique Android-English equivalent is ID `824`, which belongs before ritual IDs
`839, 842, 843, 844`. This is a real local narrative reorder, not an alternate
fuzzy candidate. SNES `C9:902F` ("You'll be able to gain power ... wherever you
are") has no confident standalone Android-English anchor in the same block; the
mobile script compresses/redistributes the surrounding explanation.

A second unmatched stress case is SNES `CA:437D` (`...SHRIEK!`) in `$04E8`. A
nearby Android exclamation is semantically different, so the source remains
unassigned. This is the desired behavior for a conservative aligner.

Round 5 also deliberately includes short/generic strings such as `Hey!` and
`Oooh!`. They are only proposed where a much stronger surrounding sequence
fixes their location; they must never be auto-accepted from lexical score alone.

## 14. Automation design established by round-5 validation

Round 5 was accepted in full. The correspondence evidence established the following design for the first conservative automatic aligner. Its ordering model should
operate on **local dialogue/subscene runs**, not whole SNES events, and sequence
alignment must allow Android insertions, SNES omissions and rare local moves.

Recommended automatic evidence hierarchy:

1. find distinctive high-margin Android-English anchors;
2. use them to establish a local Android block for a SNES dialogue run;
3. align neighboring source units monotonically **within that local block**;
4. normalize and compare dynamic placeholders/commands explicitly;
5. accept generic or duplicate strings only when both neighboring anchors fix
   their position;
6. allow insertion/deletion gaps without shifting the rest of the scene;
7. detect order contradictions such as `$0204` and downgrade them to block/review
   handling rather than forcing monotonicity;
8. recover French through the validated English-anchor slot interval or sequence
   block only after English identity has been established.

The first automated pass should still emit three classes: automatic
`very_high`, review-required candidates, and unresolved/unmatched entries. It
should generate correspondence metadata before it is allowed to feed sparse
`translations/dialogues_french.json`. SNES line wrapping, page breaks and VWF
layout remain a separate deterministic formatting pass.

## 15. Implemented conservative whole-dialogue aligner

Round 5 was visually accepted in full. The five reviewed batches now cover 180
source IDs when the three pilot duplicate/alternative cases are included. The
first whole-dialogue automatic pass is implemented as:

```bash
python3 tools/import_android_text.py --only dialogue-auto
python3 tools/import_android_text.py --only dialogue-auto --check
```

It deterministically generates:

- `mappings/android/dialogues_auto.json`: accepted correspondence blocks,
  evidence, recovered French localization slots, coverage statistics and the
  unresolved set;
- `mappings/android/dialogues_unmapped.csv`: only unresolved **semantic** SNES
  phrases, with the best two Android-English candidates for later review.

The aligner requires `RapidFuzz`, declared in the repository `requirements.txt`.
It is used for candidate search/scoring only; the five user-reviewed rounds remain
independent calibration evidence.

### Implemented ordering model

The automatic unit is a local SNES dialogue session delimited by
`TEXT_OPEN`/`TEXT_CLOSE`, not a complete SNES event. Within a session the aligner:

1. finds unique/high-margin Android-English anchors;
2. chooses a local Android anchor window from a monotonic seed chain;
3. performs bounded sequence alignment allowing 1-3 SNES semantic text tokens
   against 1-3 Android-English anchors;
4. accepts only high lexical/context evidence;
5. performs conservative same-session and immediately-neighboring-session
   expansion from already accepted anchors;
6. accepts a remaining exact duplicate only when every duplicate Android anchor
   resolves to the same complete French localization interval.

`PLAYER_NAME` commands are rendered as `%S(index,0)` for comparison. Importantly,
**every** SNES text token acts as a placeholder boundary, even a punctuation-only
`...` token that normalizes to no words. This prevents a dynamic name belonging
to one punctuation fragment from leaking into the comparison span of the next
spoken phrase.

The genuine `$0204` reorder remains valid because strong unique lexical identity
can establish an anchor outside the otherwise local monotonic run. The two
round-5 source strings explicitly validated as having no confident standalone
equivalent (`C9:902F`, `CA:437D`) are hard safety exclusions and remain unmapped.

### Current whole-dialogue coverage

`assets/dialogues.json` contains 2,143 text tokens. Of these, 1,838 contain
semantic words/digits after comparison normalization; 305 are layout or
punctuation-only tokens and are not counted as phrases requiring Android
matching.

The current conservative pass maps **1,471 / 1,838 semantic source IDs (80.0%)**.
It also carries six punctuation/layout source IDs inside already user-validated
multi-token blocks, for 1,477 mapped source IDs total. **367 semantic phrases
remain unresolved** and are preserved in `dialogues_unmapped.csv` rather than
forced.

As a calibration check, the generic automatic session pass independently makes
156 attempts on source IDs covered by the reviewed rounds and recovers the
reviewed Android location in all 156 cases: **zero calibration conflicts**.
The remaining reviewed cases exercise deliberate segmentation/reorder/short-line
situations and stay authoritative user-validated mappings.

The unresolved set currently breaks down into:

- 221 with insufficient English lexical confidence;
- 103 with a plausible candidate but insufficient local context/segmentation
  confidence;
- 34 exact Android-English duplicate sets whose French blocks differ;
- 7 strong but insufficiently separated candidates;
- 2 explicitly validated no-equivalent cases.

These categories are intentionally conservative and are suitable for later
manual or structure-specific work.

### First SNES formatting checkpoint

`dialogues_auto.json` remains the complete correspondence layer. Translation
generation is still conservative and separate from matching, but a first
runtime-validated formatting checkpoint exists for event `$0107`:

```bash
python3 tools/import_android_text.py --only dialogue-format-pilot \
  --rom "Secret of Mana (USA).sfc"
python3 tools/import_android_text.py --only dialogue-format-pilot \
  --rom "Secret of Mana (USA).sfc" --check
```

This generates only the three `$0107` entries in
`translations/dialogues_french.json` plus the reproducible formatting report in
`mappings/android/dialogues_format_pilot.json`. The first formatting checkpoint
is intentionally restricted to event `$0107`.
The formatter:

- regenerates the accepted alignment from the original Android EN/FR sources;
- binds `%S(index,0)` only to existing SNES `PLAYER_NAME` commands;
- refuses to cross unrelated event commands;
- removes Android-only presentation wrapping (`_`, Android line breaks and
  ideographic spaces) without rewriting translated prose;
- reflows against **two independent runtime constraints**: a conservative
  240-pixel VWF target and component 06's validated 38-decoded-character parser
  capacity;
- budgets a dynamic player name as both the worst-case 9-character VWF width and
  nine decoded visible characters;
- refuses a candidate if it needs more explicit visible lines than the source
  span exposes.

The `$0107` runtime tests were what exposed the character-count constraint. The
initial 245-pixel line contained 41 decoded visible characters with a maximum
9-character name and split in game. The next candidate contained a line only
231 pixels wide but 40 decoded characters; runtime moved the final word `dans`
to the next line. Both observations match the known 38-character parser limit.
With the dual constraint, the first localized speech is formatted as 196 / 199 /
207 pixels and 32 / 35 / 36 decoded characters; the second is 217 / 114 pixels
and 36 / 19 characters. Component 08 rebuilds the event from 122 to 162 bytes
and relocates it deterministically to `$E8:2000`. **The Android correspondence
and the revised dual-limit French presentation are runtime-validated.** The next
expansion step is therefore charset/structural normalization, documented in
`DIALOGUE_CHARSET_AUDIT.md`, rather than further tuning of this pilot.
