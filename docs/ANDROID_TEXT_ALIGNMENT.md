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
global text-ID sequence. `systxt` is preserved under `sources/android/`. Since Round 46 it is consumed only by a narrow explicit review allow-list for chest/system messages; it is **not** added to the generic dialogue candidate index, which remains `scrtxt`-only.

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

These were deliberately left unresolved during the pilot rather than forced even
though parts of their text matched perfectly. The old `dialogues_pilot.json` snapshot
is no longer versioned; the decisions that survived the review are represented by the
current alignment/recipe data.

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

the legacy generated Round-2 review report (no longer versioned) contains 23 alignment units from
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

the legacy generated Round-3 review report (no longer versioned) extends the same method to 33
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

the legacy generated Round-4 review report (no longer versioned) contains 37 additional units
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

## 12. Reproducible current workflow

Historical pilot/review CLI modes have been retired. Their validated identities remain
encoded as structural correspondence data used by the canonical aligner. The active
commands are:

```bash
python3 tools/import_android_text.py --only intro [--check]
python3 tools/import_android_text.py --only dialogue-auto [--check]
python3 tools/import_android_text.py --only dialogue-format-mass --rom <clean-USA-ROM> [--check]
```

`dialogue-auto` rebuilds the reviewed SNES/Android identity report from
`assets/dialogues.json`, `scrtxt_en.bin` and `scrtxt_fr.bin`.
`dialogue-format-mass` recomputes alignment in memory and generates the playable French
corpus; it does not consume an existing `dialogues_auto.json` or
`translations/dialogues_french.json`. Historical round reports are no longer inputs.

## 13. Round-5 stress test: auditing non-monotonic events

the legacy generated Round-5 review report (no longer versioned) contains 55 review units across
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

The current conservative pass maps **1,571 / 1,838 semantic source IDs (85.5%)**.
It also carries layout/punctuation source IDs inside already reviewed multi-token
blocks. **275 semantic phrases remain unresolved** and are preserved in
`dialogues_unmapped.csv` rather than forced. `$0103` and `$017F` are user-validated
as visually complete Android adaptations, but their omitted SNES-only fragments stay
unmapped and therefore do not inflate this alignment count.

As a calibration check, the generic automatic session pass independently makes
156 attempts on source IDs covered by the reviewed rounds and recovers the
reviewed Android location in all 156 cases: **zero calibration conflicts**.
The remaining reviewed cases exercise deliberate segmentation/reorder/short-line
situations and stay authoritative user-validated mappings.

The unresolved set currently breaks down into:

- 193 with insufficient English lexical confidence;
- 79 with a plausible candidate but insufficient local context/segmentation
  confidence;
- 26 exact Android-English duplicate sets whose French blocks differ;
- 6 strong but insufficiently separated candidates;
- 2 explicitly validated no-equivalent cases.

These categories are intentionally conservative and are suitable for later
manual or structure-specific work.

### Structural review round 6: staging and split choices

A sixth structural-review round records **30 correspondence units**. One source ID was
already mapped by the previous pass, so it recovers **29 additional semantic source IDs**
that the lexical matcher correctly left unresolved. These are not weaker fuzzy matches: identity is established
from ordered Android-English scene structure plus already accepted neighboring anchors.
The evidence is reproducible as the legacy generated Round-6 review report (no longer versioned);
identity remains encoded explicitly in `tools/import_android_text.py`. Two main families are kept separate:

- **speaker/staging redistribution**: the SNES Joch running gag stores reactions such as
  `All:WHAT!?`, while Android English keeps the reaction text (`WHAT!?`) and Android
  French reattributes it with `%S(0,0)`. The same review also accepts short speaker-labelled
  lines only when their Android-English identity is exact and neighboring accepted records
  prove the scene (`Geshtar: Idiot!`, the moogle reaction triplet, the Fanha confrontation,
  etc.);
- **prompt/choice splitting**: the SNES often stores a prompt and selectable labels in
  one event row, while Android stores the prompt and each option as adjacent localization
  records. A prompt is accepted only when the Android-English option sequence and local
  ordering provide an independent anchor (for example Save/Yes/No, Neko Buy/Sell,
  Cannon destinations, or the contiguous `1..8` option run).

Round 6 raises semantic alignment from 1,471 to **1,500 / 1,838 (81.6%)**, leaving
**338** source phrases unresolved. It does not authorize generic matching of short labels
such as `Yes`, `No`, `Buy` or place names outside their proven local choice block. Some
newly identified text is still withheld from the ROM when its stock choice geometry is
unsafe; identity and renderability remain separate gates.

### Structural review round 7: ordered gaps and scene-correct short choices

Round 7 adds **18 structural correspondence units** and raises the accepted alignment to
**1,516 / 1,838 semantic source IDs (82.5%)**, leaving **322 unresolved**. The new units
continue the same two proof families rather than broadening the matcher:

- exact speaker-labelled or speaker-redistributed lines are accepted only when they fill
  a specific gap inside an already ordered Android-English scene, such as Luka `916`,
  Guard `1516`, Morie/Meria `1545/1552`, Krissie `2013/2020`, and PLAYER_NAME line `2186`;
- Cannon/Neko prompt-and-choice blocks are accepted only from their complete adjacent
  Android-English run. This also corrects two earlier globally exact short-label
  identities: SNES `Kakkara` in `$00D0` belongs to Android `1327` inside the
  `1326/1327/1328` Kakkara/Ice Country block, and the affirmative option in `$00E2`
  belongs to Android `1923` beside prompt `1921` and negative option `1922`, rather than
  to an unrelated exact `Sure!` elsewhere.

These corrections demonstrate why short labels and destinations must never be matched
in isolation. Several newly completed choice events remain excluded by the separate
layout gate because their official French labels collide with stock `CHOICE_OPTION`
anchors; no anchors are moved or guessed.


### Structural review round 8: user-reviewed PARTIEL blocks

Round 8 follows the first in-game review of PARTIEL events. It adds **16 semantic
source IDs**, raising alignment from 1,516 to **1,532 / 1,838 (85.5%)** and leaving
**267 unresolved**. The accepted identities are all demonstrated by ordered Android
English context around already accepted anchors: Picard's lighthouse (`2303-2306`),
Pandora gate (`237-240`), the ruins NPC (`300-301`), Phanna/Pamela exchanges, the
Pandora king/noble scenes, Watts `565-566`, and the party-removal notice `439-440`.
The duplicated Dyluck-soldier line in `$0121` is kept as two equivalent Android
alternative locations (`792` or `796`) because both English and French blocks are
identical; no arbitrary provenance is invented.

The same review confirms several render-vs-identity distinctions. `$00DF`'s Cannon
prompt is Android `420`, separate from options `421/422`, but remains layout-deferred
because the official French prompt/option geometry collides with stock choice anchors.
`$01D3` has a structurally credible expanded Android opening (`616/617`) but that text
still cannot be laid out safely in the stock carrier, so it stays PARTIEL. `$0167`'s
Android `1059` is the likely resegmented continuation around `PLAYER_NAME(1)`, but is
left unresolved rather than forcing a binding across the SNES WAIT/name structure.

### First SNES formatting checkpoint

`dialogues_auto.json` remains the complete correspondence layer. Translation
generation is still conservative and separate from matching, but a first
runtime-validated formatting checkpoint exists for event `$0107`:

The dedicated pilot command and its generated reports have been retired. Its runtime
validation remains relevant to event `$0107` and is preserved as an invariant of the
canonical mass formatter.
The formatter:

- regenerates the accepted alignment from the original Android EN/FR sources;
- binds `%S(index,0)` only to existing SNES `PLAYER_NAME` commands;
- refuses to cross unrelated event commands;
- removes Android-only presentation wrapping (`_`, Android line breaks and
  ideographic spaces) without rewriting translated prose;
- reflows against **two independent runtime constraints**: a conservative
  historical 240-pixel VWF target (superseded by the Round-70 runtime-validated 216-pixel safe ceiling) and `vwf_dialogues`'s validated 38-decoded-character parser
  capacity;
- budgets a dynamic player name as the worst-case 9-character VWF width and,
  after batch-1 runtime testing, reserves one additional parser-safety unit on
  any line containing `PLAYER_NAME`;
- refuses a candidate if it needs more explicit visible lines than the source
  span exposes.

The `$0107` runtime tests were what exposed the character-count constraint. The
initial 245-pixel line contained 41 decoded visible characters with a maximum
9-character name and split in game. The next candidate contained a line only
231 pixels wide but 40 decoded characters; runtime moved the final word `dans`
to the next line. Both observations match the known 38-character parser limit.
With the dual constraint, the first localized speech is formatted as 196 / 199 /
207 pixels and 32 / 35 / 36 decoded characters; the second is 217 / 114 pixels
and 36 / 19 characters. `french_dialogues` rebuilds the event from 122 to 162 bytes
and relocates it deterministically to `$E8:2000`. **The Android correspondence
and the revised dual-limit French presentation are runtime-validated.** The next
expansion step is therefore charset/structural normalization, documented in
`DIALOGUE_CHARSET_AUDIT.md`, rather than further tuning of this pilot.
### First complete-event expansion

After charset/structural normalization was established, the formatter was expanded
to the first deliberately small complete-event batch:

The dedicated batch command has been retired; these validated events are now covered
by the canonical mass generator and regression checks.

The first batch runtime test validated `$010E`, `$0116`, `$0117`, `$0118` and
`$011D` in addition to the already validated `$0107`. Event `$010F` was rejected:
with a 9-character dynamic name, the exact-capacity first line (`38` visible
characters in the original offline model) split in game. The formatter now
reserves one additional parser-safety unit on any line containing `PLAYER_NAME`.
Under that conservative rule the unmodified Android French for `$010F` needs four
lines while the stock span exposes only three, so `$010F` is deliberately left
untranslated until a separately validated extra-page mechanism exists.

The corrected batch therefore contains `$0107`, `$010E`, `$0116`, `$0117`, `$0118`
and `$011D`, producing 8 sparse translation entries. A selected event is accepted
only when **all** of its semantic source text IDs are already in the conservative
Android alignment and every mapping passes existing-command binding, exact
PLAYER_NAME rebinding and the conservative layout rules. This complete-event gate
deliberately prevents mixed English/French runtime test scenes.

## Round 11 PARTIEL follow-up

Round 11 reuses the structural patterns established by user review rather than lowering
lexical thresholds. Accepted units must be proven by the ordered Android-English scene:
exact gaps between already accepted anchors, Android sentences that expand an SNES
fragment, or consecutive SNES fragments clearly collapsed into one Android anchor.
Generic short labels, choices and destinations remain unresolved unless their local block
proves identity.

This pass raises accepted alignment to **1,563 / 1,838 semantic IDs (85.0%)**, leaving
**275 unresolved**. The simulator-filtered corpus remains 478 events but improves to
**458 complete + 20 PARTIEL**, with **1009 visible French semantic IDs** and 0 errors,
0 warnings and 0 implicit wraps. A semantically convincing `$02AE` regrouping was
explicitly left unresolved because it crosses a stock `WAIT` boundary that the formatter
refuses to bind automatically.



## Round 18 speaker/resegmentation follow-up

Round 18 follows the already-established speaker-reattribution pattern instead of
lowering lexical thresholds. It restores the final Joch `All:Surprise...` reaction
from Android EN 2457, resolves the ordered Gnome 993-999 sequence, the split
Sergo/guard exchange at 1508-1509, the locally disambiguated television `...Gzzz...`
at 2349, and the Pamela/Chris resegmentation in Android 2032-2055. The Android
French `%S(0,0) :` label on the Joch reactions is treated as Android presentation
metadata because the corresponding SNES `All:` carrier has no PLAYER_NAME command;
no new runtime speaker command is invented.

The accepted alignment is now **1,571 / 1,838 semantic IDs (85.5%)**, leaving
**267 unresolved**. The simulator-filtered output remains **478 events**, now
**466 complete + 12 PARTIEL**, with **1,023 visible French semantic IDs / 1,086 JSON
entries**, 0 errors, 0 warnings, 0 implicit wraps and 0 WAIT $00 third-line-scroll
risks. `$0023` requires one generated validated-style page boundary after its longer
French reaction; `$03E9` and `$055E` expose two new instances of the already-audited
WAIT $00 third-line hazard and therefore use the same explicit newline-carrier to
TEXT_CLEAR test-candidate repair.


## Round 20 Cannon Travel / choice-destination structural review

Round 20 uses ordered destination labels as structural anchors for the heavily rewritten
Cannon Travel dialogue. The Android prompt text is not required to resemble the SNES
prompt lexically: identity is established from the ordered Android-English block
`prompt -> destination option(s) -> destination response`, cross-checked against the
SNES choice branches. Android commonly merges the stock shared `Just slide into the
cannon!` event into each destination response; the importer therefore splits the
official French response back across the destination-specific SNES event and the shared
`$00FC` carrier instead of duplicating it.

The same ordered-choice method resolves the `$01D6` donation prompt and the `$01EE`
Yes/No options. `$01D6` and `$01EE` use fresh-page choice presentation when required by
the three-line runtime window. `$00DF` remains PARTIEL despite accepted semantic identity
because `Temple de l'Eau` does not fit the stock option-anchor span; no CHOICE_OPTION
anchor is moved automatically.

This review raises the conservative alignment to **1,593 / 1,838 semantic IDs (86.7%)**,
leaving **245 unresolved**. The simulator-filtered corpus reaches **496 events**, with
**486 complete + 10 PARTIEL**, **1,043 visible French semantic IDs / 1,104 JSON entries**,
and still reports 0 errors, 0 warnings, 0 implicit wraps and 0 WAIT $00 third-line-scroll
risks.


## Round 21 conservative PARTIEL resegmentation

Round 21 resolves three cases using only structural Android-English evidence and the
official Android French strings. `$01E5` binds Android 668 to the existing
`PLAYER_NAME(1) + joined again!` carrier. `$0609` treats Android 415 as the merged
`Haunted Forest ↑ / ↓ Gaia's Navel` unit and redistributes its two French labels across
the stock `$D1/$D2` glyph row without translating or moving the arrows. `$0167` expands
the earlier 1058 evidence to the contiguous 1058/1059 block and redistributes the exact
French text around the existing `WAIT $00` + `PLAYER_NAME(1)` bridge; neither command is
moved or invented.

The conservative alignment is now **1,596 / 1,838 semantic IDs (86.8%)**, leaving
**242 unresolved**. All three events pass the formatter and independent simulator, so
the 496-event corpus becomes **489 complete + 7 PARTIEL**, with **1,046 visible French
semantic IDs / 1,104 JSON entries**, 0 errors, 0 warnings and 0 implicit wraps. The
existing `$0167` explicit post-WAIT newline remains a runtime-test candidate rather than
being promoted by static simulation alone.


## Round 22 branch/staging PARTIEL resegmentation

Round 22 resolves three additional PARTIEL events without manual French. `$01DD` uses
Android EN 616 as the shared Sprite warning, 619 as the female-address branch, and 620
as the exact two-`PLAYER_NAME(1)` reply; Android FR 616/619/620 is redistributed only
through those existing SNES carriers. `$07FE` binds the ending wake-up staging to Android
3399/3401/3406 and preserves the stock `PLAYER_NAME(0)` while reusing the Android FR
staging pieces. `$02AE` binds the two Amar fragments around the existing timed `WAIT $10`
to Android 1630. Because WAIT does not advance the cursor, the formatter keeps the first
Android-FR piece on one physical line, emits one explicit newline before the unchanged
`WAIT $10`, then places the remaining official French on the following two lines.

The conservative alignment is now **1,601 / 1,838 semantic IDs (87.1%)**, leaving
**237 unresolved**. The corpus remains **496 simulator-clean events** and becomes
**492 complete + 4 PARTIEL**, with **1,051 visible French semantic IDs / 1,106 JSON
entries**, 0 errors, 0 warnings and 0 implicit wraps. `$01DD`, `$02AE` and `$07FE` remain
`TO REVIEW`; this round is statically clean but not runtime-validated. The remaining
PARTIEL events are `$00DF`, `$01DC`, `$0278` and `$0331`.


## Round 23 user-validated Android omission at $01DC

Round 23 does not create a new semantic mapping. A corpus-wide Android-English check
confirms that Android 728 ends with the three-person platform/bridge instruction and
Android 729 immediately starts the following Niccolo scene. The final SNES-only
`PLAYER_NAME(0) + C9:804A` reaction (`...? Platform? / Let's go see it!`) therefore has
no Android identity or official Android-French equivalent.

The user explicitly validated treating that pair as one Android-adaptation omission.
`C9:804A` remains unmapped and suppressed, so alignment coverage stays **1,601 / 1,838
semantic IDs (87.1%)**, with **237 unresolved**. The translated serializer additionally
omits only the stock `PLAYER_NAME(0)` immediately before `C9:804A`, guarded by exact
source-token adjacency; the canonical source asset is unchanged and no generic command
removal rule is introduced.

The corpus remains **496 simulator-clean events** but becomes **493 complete + 3 PARTIEL**,
with **1,051 visible French semantic IDs / 1,106 JSON entries**, 0 errors, 0 warnings and
0 implicit wraps. The sole remaining PARTIEL event is `$0278`; `$00DF` and `$0331` are complete under the validated choice-anchor and parameterized-inn rules.


## Choice-VWF geometry follow-up

After runtime validation of `vwf_dialogues`'s option-start and terminal-boundary synchronization,
`french_dialogues` may preserve a long localized choice label by moving only a **later**
`CHOICE_OPTION` to the right. The first anchor remains stock; the new coordinate is exactly
the minimum decoded cell after the preceding label, must remain below 32, and the final event
must still pass the independent zero-error / zero-warning / zero-wrap simulator gate. The
Potos diagnostic using `Temple de l'Eau / Pandora` runtime-validates `$00DF`'s concrete
`$03/$11 -> $03/$12` geometry. No manual French or runtime `$A1D7[]` rewrite is involved.

This removes `$00DF` from PARTIEL and also admits four previously excluded complete events
(`$020F`, `$0310`, `$0314`, `$0319`) under the same static gate. A later conservative choice-row
recovery pass admits eleven more events without moving the first option anchor: it restores a
stock `NEWLINE + (` row suffix lost by Android prose reflow, may materialize one newline before a
standalone decorative `(` carrier, and may compose decoration stripping with the already validated
later-anchor-only shift. Semantic alignment remains **1,601 / 1,838 (87.1%)**, because these are
layout changes rather than new identity mappings.

At the choice-geometry checkpoint, the corpus was **528 simulator-clean events**, **527 complete + 1 PARTIEL**, with
**1,161 visible semantic IDs / 1,222 JSON entries**. `$0278` is the sole PARTIEL event because
its two SNES-only controller carriers are staged for manual translation; `$0331` is complete
through the reviewed parameterized Android-ID-110 inn template. The newly admitted measured-end
choice rows (`$00CE/$00CF/$00D0/$00D1/$0202`) are now backed by the runtime-validated `vwf_dialogues`
geometry and the updated offline simulator/serializer model.

## Round 24 exact segmentation and contextual exact duplicates

Round 24 resumes the unresolved-ID backlog without lowering lexical confidence. It adds two
structural identity rules. First, contiguous spans of one to three SNES semantic elements may
match one to three consecutive non-empty Android-English anchors when their normalized English
is **exactly identical**. Ordinary 1:1 exact matches stay on the simpler path; differing
segmentations are accepted only when every duplicate Android segmentation yields the same
complete, non-empty French localization, and overlapping exact SNES-span proposals remain
unresolved rather than being ranked. A single existing conservative context-expansion pass is
then rerun because these exact spans are legitimate new anchors; no threshold changes.

Second, exact English duplicates whose French differs may be disambiguated only by already
owned event-local anchors. Exactly one duplicate must either lie inside a nearby monotonic
bracket (at most 12 non-empty Android anchors) or be the unique immediately adjacent anchor.
The pass is non-cascading. Before enablement this rule reproduced **23 / 23** already accepted
contextual duplicate selections with **0 conflicts**. A generic short-string exact rule remains
forbidden: existing validated mappings provide counterexamples such as `Kakkara`, `Sure!` and
`Okay`, where global uniqueness does not prove scene identity.

The result is **1646 / 1838 semantic IDs (89.6%)**, leaving **192 unresolved**: +32 aligned
semantic IDs. Ten previously excluded complete events become simulator-clean (`$018A`, `$01CB`,
`$023D`, `$028A`, `$02A2`, `$02F8`, `$0378`, `$03A5`, `$03D5`, `$07FD`). They remain
`NEW` + `TO REVIEW` pending runtime/playthrough validation. Five other events become complete
at the identity layer but stop at the formatter structural gate: `$0041`, `$0205`, `$02CD`,
`$03EA`, `$03F0`. The corpus therefore reaches **538 simulator-clean events, 537 complete +
1 PARTIEL**, with **1176 visible semantic IDs / 1237 JSON entries** and 0 errors, 0 warnings,
0 implicit wraps. Exclusions are **146 alignment-incomplete + 20 formatter rejects**.

The 1222 previously generated translation entries remain byte-for-byte unchanged. Round 24
adds only 15 visible entries. `$0103/C9:26A8` gains a proven semantic identity but remains
suppressed in translated serialization because `$0103`'s existing French-only adaptation was
already runtime-validated with that carrier omitted; semantic knowledge must not silently
rewrite a validated runtime layout. `$0278` remains the sole PARTIEL event.



## PARTIEL mixed-language policy checkpoint

Alignment-incomplete events are now reconsidered automatically on every `dialogue-format-mass` run. Accepted Android EN/FR mappings are formatted in French, while genuinely unresolved semantic carriers are deliberately omitted from the sparse French JSON so their original SNES English remains visible in-game. This makes missing alignment directly observable during playtesting without inventing identity or translation. A mixed event is admitted only when its direct serialization remains clean in the independent simulator (0 errors, 0 warnings, 0 implicit wraps), and it is always marked `PARTIEL` / `TO REVIEW`. Future alignment or formatter improvements are therefore picked up automatically on the next mass pass.

At this checkpoint the corpus is **547 simulator-clean events: 544 complete + 3 PARTIEL**, with **1199 visible semantic IDs / 1260 JSON entries**. The PARTIEL events are `$01B6`, `$0278` and `$02B0`. `$0602` still has unresolved `CA:85DD`, but runtime review found no visible missing/English content, so it is explicitly treated as visually complete with unchanged serialization. `$01B6` and `$02B0` visibly mix proven French with unresolved stock English; `$0278` remains the special manual-supplement case for its Android-absent controller instructions. Exclusions fall to **132 alignment-incomplete + 25 formatter rejects**, with 0 simulator rejects. Semantic alignment itself remains **1646 / 1838 (89.6%)**, 192 unresolved.


## High-leverage near-complete-event checkpoint

A later pass prioritizes events that retain many already-proven French carriers behind one unresolved semantic ID. Four additional conservative identity rules were calibrated against the accepted corpus before enablement: raw-carrier contextual exact duplicates (27/27, 0 conflicts), short exact matches inside punctuation-only tight brackets (35/35, 0 conflicts), a unique free semantic Android anchor inside a tight owned bracket with lexical/token-coverage floors (495/495, 0 conflicts), and long isolated global high-coverage matches with a 20-point runner-up margin (483/483, 0 conflicts). Proposal collisions remain unresolved.

This adds 13 semantic IDs and raises alignment to **1646 / 1838 (89.6%)**, leaving **192 unresolved**. Six complete events become simulator-clean: `$0084`, `$0110`, `$014A`, `$02D4`, `$0367`, `$0373`; all are `NEW` + `TO REVIEW`. The mass corpus is **547 events = 544 complete + 3 PARTIEL**, with **1199 visible semantic IDs / 1260 JSON entries**, 0 errors, 0 warnings and 0 implicit wraps. The 541 previously accepted events serialize byte-for-byte identically and the previous 1242 translation entries are unchanged. Exclusions are **132 alignment-incomplete + 25 formatter rejects**.

## Round 25 second high-leverage structural pass

The second high-leverage pass re-ranked the remaining near-complete events by unresolved
semantic-ID count and by already-proven French carriers retained behind those gaps. Eight
missing IDs were accepted from Android-English structural evidence only. The pass does not
add a looser generic lexical rule and does not use Android French as identity evidence.

The accepted units are deliberately narrow: three SNES speaker-prefix fragments are joined
through their existing `PLAYER_NAME` command to the already aligned Android record (`$002F`,
`$0133`, `$0180`); `$01B5` expands the already-owned Android 577 unit over the preceding
SNES fragment that contains the first half of the same English sentence; `$028B`, `$01E7`,
`$04B6` and `$04FD` use uniquely ordered scene continuations bracketed by already accepted
Android anchors. A proposed `$015A` remap was rejected because it contradicted previously
accepted calibration evidence, so the existing mapping remains untouched.

Alignment rises to **1654 / 1838 semantic IDs (90.0%)**, leaving **184 unresolved**. Re-running
the ordinary context-expansion machinery after the new anchors produced no additional safe
cascading matches. Four newly complete events are immediately formatter/simulator-clean:
`$002F`, `$0133`, `$0180` and `$028B`. Together they release **21 semantic source IDs** into
the visible French corpus. The other four newly complete identity-layer events (`$01B5`,
`$01E7`, `$04B6`, `$04FD`) remain formatter rejects because of pre-existing structural or
`PLAYER_NAME` localization mismatches; no formatter-specific workaround is forced in this
alignment pass.

The mass corpus is therefore **551 simulator-clean events = 548 complete + 3 PARTIEL**, with
**1220 visible semantic source IDs / 1281 JSON entries**, 0 errors, 0 warnings and 0 implicit
wraps. Exclusions are now **124 alignment-incomplete + 29 formatter rejects**.


## Round 26 contained-extension + positional placeholder pass

A follow-up pass added one global identity rule for long version extensions. It applies only
when the complete normalized SNES token sequence occurs **contiguously** inside the best
longer Android-English record, the SNES source is at least 35 normalized characters, source
token coverage is 100%, lexical score is at least 76, character similarity is at least 68%,
and the best candidate leads the runner-up by at least 30 points. The Android anchor must be
free and proposal collisions are rejected. Calibration against already accepted one-carrier
mappings reproduced **535/535 eligible cases with 0 conflicts**.

The rule adds five semantic IDs: `$00D4/C9:1C75`, `$0223/C9:9737`, `$02B0/C9:B77B`,
`$0384/C9:D951` and `$039E/C9:DFC4`. `$00D4`, `$0223` and `$039E` become newly complete;
`$02B0` moves from PARTIEL to complete; `$0384` still has another unresolved carrier and
therefore remains alignment-incomplete. Semantic alignment becomes **1659 / 1838 (90.3%)**,
with **179 unresolved** and **121 alignment-incomplete events**.

The same pass also added a formatter-only `PLAYER_NAME` rule. Android may assign the same
spoken line to a different party-slot index than the SNES script. When Android French and the
canonical SNES binding contain exactly the same number of placeholders in the same positions,
but only their numeric indices differ, each French placeholder is rebound positionally to the
existing SNES `PLAYER_NAME` slot. No command is created, removed, moved or reordered. Applying
the rule to the previously accepted corpus changes zero existing translation entries. It makes
`$01E7`, `$04AA` and `$04B6` simulator-clean.

The resulting mass corpus is **557 simulator-clean events = 555 complete + 2 PARTIEL**
(`$01B6`, `$0278`), with **1250 visible semantic source IDs / 1314 JSON entries**. The prior
1281 translation entries remain byte-for-byte unchanged; exactly 33 entries are added. The
independent simulator remains at **0 errors / 0 warnings / 0 implicit wraps**. Exclusions are
now **121 alignment-incomplete + 26 formatter rejects**.


## Round 27 short exact + French-only turn filtering

A new short-exact rule accepts a globally unique normalized Android-English exact only when its sole occurrence is immediately adjacent to an already-owned Android anchor in the same SNES dialogue session. Calibration reproduces **37/37** eligible accepted historical mappings with **0 conflicts**. It adds three semantic IDs (`$0558/CA:6549`, `$05F8/CA:8368`, `$05F8/CA:854C`) without using Android French as identity evidence.

Formatter-side cleanup now distinguishes French prose continuation stored in English-empty Android slots from a later **new dynamic player turn**. French continuation prose is preserved. If a later English-empty slot begins `%S(n,0) : ...` and dropping only that new turn restores the exact SNES placeholder sequence, the turn is treated as Android-only and is not attached to the SNES mapping. This makes `$04B3` complete and allows `$0384` to serialize as a clean PARTIEL while preserving the necessary French continuation of Android 1797. `$0592` benefits from the same ownership correction but remains formatter-rejected for an independent speaker/layout issue.

A second narrow formatter fallback preserves an existing leading SNES `PLAYER_NAME` plus `!` or `?` when Android EN proves the same leading dynamic addressee but Android FR omits it. No command is created, deleted or moved. `$0108` is the accepted case.

The Round-26 translation corpus is preserved byte-for-byte: **1314/1314 prior entries unchanged, 0 removed, 14 added**. At that checkpoint semantic alignment was **1662 / 1838 (90.4%)**, with **176 unresolved**. The mass corpus is **560 simulator-clean events = 557 complete + 3 PARTIEL** (`$01B6`, `$0278`, `$0384`), with **1264 visible semantic source IDs / 1328 JSON entries** and exclusions of **120 alignment-incomplete + 24 formatter rejects**.

## Round 28 PLAYER_NAME-context exacts and structural formatter release

Round 28 keeps Android English as the sole identity layer and adds two final conservative automatic identity rules. Exact Android-English duplicate families may be treated as equivalent alternatives when their complete French localization units differ only by `%S(n,0)` index; the SNES `PLAYER_NAME` slot remains authoritative, so no speaker identity is inferred from French. The index-only extension has **1/1** eligible historical accepted mapping and **0 conflicts**, with the stronger invariant that every Android-English candidate is an exact duplicate and the complete French units are identical after canonicalizing only the dynamic index. A second rule accepts a raw carrier exact obscured only by adjacent `PLAYER_NAME` context when the raw source is at least ten normalized characters, the Android-English exact is globally unique, and that anchor is immediately adjacent to an already-owned anchor in the same SNES session. Calibration reproduces **36/36** eligible accepted mappings with **0 conflicts**.

These rules add exactly four semantic identities without changing any previously accepted mapping target: `C9:0FA2`, `C9:107E`, `C9:5A8C` and `CA:31C2`. Alignment therefore reaches **1666 / 1838 (90.6%)**, with **172 unresolved**. The new identities do not bypass formatter safety: `$0040` remains formatter-rejected, while `$0186` and `$04E2` still have other unresolved carriers.

Formatter-side, `$0112` and `$0212` preserve an existing SNES dynamic addressee when both SNES and Android EN prove `STATIC_SPEAKER:%S(n)!/?` but Android FR omits only `%S(n)`. `$0112` also composes the established complete-sentence distribution across `WAIT $00` with an already-validated pure actor-action `OP_32 + COMPLETE_ACTIONS` bridge; all stock commands remain in place. `$0042` becomes a simulator-clean PARTIEL, leaving only `C9:1057` stock English.

The Round-27 translation corpus is preserved byte-for-byte: **1328/1328 prior entries unchanged, 0 removed, 25 added**. The Round-27 mass result is **563 simulator-clean events = 559 complete + 4 PARTIEL** (`$0042`, `$01B6`, `$0278`, `$0384`), with **1289 visible semantic source IDs / 1353 JSON entries** and exclusions of **118 alignment-incomplete + 23 formatter rejects**.


## Round 29 validated-no-equivalent PARTIEL release

Round 29 changes **no semantic mapping**: alignment stays at **1666 / 1838 (90.6%)**, with **172 unresolved**. The two `validated_no_equivalent` identities remain frozen: `$0204/C9:902F` has no confident standalone Android-English anchor, and `$04E8/CA:437D` (`...SHRIEK!`) is not equated with Android 175 (`Uwahahaha!`).

The formatter now admits one previously excluded structural shape: an already accepted multi-carrier mapping may distribute complete French sentences across exactly one existing `WAIT $00` while preserving a single identical leading `PLAYER_NAME`, but only when that command is immediately before the first mapped carrier and no dynamic name occurs at/across the WAIT. A full-corpus scan finds exactly **1** eligible mapping: `$04E8`, SNES `CA:45DB + CA:461D` ↔ Android EN 128-129. Every stock command remains unchanged.

Direct semantic wrapping of the resulting PARTIEL still enters the rolling fourth/fifth line near the final `Hey, wait!` exchange. For an event containing an explicit `validated_no_equivalent` hole only, the PARTIEL pass may therefore reuse the already-established whole-event compact wrapper used by complete events. This changes only formatter-added line breaks, never identity or control flow, and is accepted only after independent zero-error/zero-warning/zero-wrap simulation. `$04E8` then becomes simulator-clean with `CA:437D` deliberately absent from the sparse French JSON, so the original USA `...SHRIEK!` remains visible.

`$0204` is deliberately **not** admitted by this rule. Its remaining formatter failures expose a different problem: Android French redistributes the Water Palace ritual explanation across IDs 824 and 839-844 (including Android-only dynamic-speaker material). A generic placeholder-strip would produce semantically shifted/duplicated dialogue. Any future `$0204` release therefore needs a dedicated reviewed French resegmentation while keeping Android English as the identity layer.

The Round-28 translation corpus is preserved byte-for-byte: **1353/1353 prior entries unchanged, 0 removed, 23 added**. The mass corpus becomes **564 simulator-clean events = 559 complete + 5 PARTIEL** (`$0042`, `$01B6`, `$0278`, `$0384`, `$04E8`), with **1310 visible semantic source IDs / 1376 JSON entries**. Exclusions fall to **117 alignment-incomplete + 23 formatter rejects**.

## Round 30 validated Android omission without identity inflation

Round 30 adds **no mapping**. Semantic alignment therefore stays at **1666 / 1838 (90.6%)**, with **172 unresolved**. `C9:30F5` in `$010C` is now classified as `validated_android_omission`, based solely on existing Round-2 Android-English evidence: the accepted `C9:3104 -> Android 62` mapping explicitly records that Android omits the preceding standalone SNES `ELLIOTT:You!` fragment. Android French is not used to prove or infer an identity.

The formatter may admit such an event as PARTIEL while preserving the omission in stock English. In `$010C`, three already accepted mappings are additionally reported as layout-deferred and kept stock because their French would require unsupported command crossing or a different `PLAYER_NAME` stream. One other accepted mapping (`C9:317D + C9:319E -> Android 117`) crosses a unique, independently proven sound/effect bridge whose call target is sound-only and returning; the Android-FR-only comma vocative is removed because SNES and Android EN have no dynamic name there, and the remaining French is split at a complete sentence boundary without changing bridge commands.

The Round-29 translation corpus is preserved byte-for-byte: **1376/1376 prior entries unchanged, 0 removed, 21 added**. The mass corpus becomes **565 simulator-clean events = 559 complete + 6 PARTIEL** (`$0042`, `$010C`, `$01B6`, `$0278`, `$0384`, `$04E8`), with **1331 visible semantic source IDs / 1397 JSON entries**. Exclusions fall to **116 alignment-incomplete + 23 formatter rejects**. `$0204` remains excluded because its Android French redistributes semantic content; no generic French-vocative stripping or broad layout-deferral rule is accepted.


## Round 31 high-leverage structural review

Round 31 resolves four semantic IDs through explicit Android-English scene structure, not French wording. `$0186/C9:591B` owns consecutive Android EN anchors 343+344 before the already anchored 345-352 block. `$0384/C9:D913` maps only to Android EN 1796; the already accepted `C9:D951 -> 1797` ownership is left untouched. In `$042D`, `CA:14AB + CA:14BA` jointly correspond to Android EN 3306 around the stock `WAIT $10`; the neighboring `%S(2,0): Uwaa!` remains Android 3307.

`$0558/CA:6629` is deliberately **not** mapped. Android EN 2188 (`%S0: You can move!?`) is followed by empty 2189 and then the next accepted scene anchor 2190, so there is no Android-English anchor for the SNES `%S(2,0) :We can too!`. It is therefore classified `validated_android_omission`; Android French is not used as identity evidence.

Semantic alignment reaches **1670 / 1838 (90.9%)**, leaving **168 unresolved**. Automatic calibration still reports **163 attempts / 162 reproductions / 0 conflicts** on reviewed IDs. The Round-30 translation corpus is preserved byte-for-byte (**1397/1397 unchanged, 0 removed**) and exactly **33** newly liberated entries are added across `$0186` (10), `$0384` (1), `$042D` (12) and `$0558` (10). The mass corpus is **568 simulator-clean events = 562 complete + 6 PARTIEL**, with **1362 visible semantic source IDs / 1430 JSON entries** and exclusions of **113 alignment-incomplete + 23 formatter rejects**.


## Round 32 structural safe-subset PARTIEL release

Round 32 changes **no Android-English identity**. Semantic alignment remains **1670 / 1838 (90.9%)**, with **168 unresolved**; automatic calibration remains **163 attempts / 162 reproductions / 0 conflicts** on reviewed IDs. The gain is formatter-side only.

When a semantically accepted mapping fails solely because the canonical binder refuses an already-recognized command/`PLAYER_NAME` boundary, the mass pass may now keep that **whole mapping** stock while emitting independent proven mappings in French. This generic structural safe-subset is deliberately strict: at least one French mapping must remain, no stock command or semantic identity changes, and the direct mixed event must pass with **0 errors / 0 warnings / 0 implicit wraps** before any adaptive/compact repair. `$015A` and `$0204` are hard-blocked because their known issues involve semantic/resegmentation ambiguity. An unserializable generated trailing page break is handled the same way unless it is already in one of the two codec-proven choice-adjacent shapes.

The generic rule is exercised by **12 PARTIEL events / 30 deferred semantic IDs**. Together with the reviewed `$01DA` deferral and `$023C` mixed-choice release, Round 32 admits 14 additional events: `$0041`, `$013A`, `$01B5`, `$01B9`, `$01DA`, `$0227`, `$023C`, `$038D`, `$03EA`, `$04E3`, `$04E5`, `$04E7`, `$0555`, `$0559`. `$05F8` remains excluded even though it has 63 aligned carriers: after all recognized bridges are left stock, direct simulation still wraps in stock/deferred regions, so accepting it would require modifying the very content the safe-subset policy protects.

The entire Round-31 translation is byte-for-byte preserved (**1430/1430 entries unchanged, 0 removed**) and **70 entries are added**. The mass corpus becomes **582 simulator-clean events = 562 complete + 20 PARTIEL**, with **1428 visible semantic source IDs / 1500 JSON entries**. Exclusions are **110 alignment-incomplete + 4 formatter-rejected + 8 simulator-rejected events**.

## Round 33 contextual structural review

Round 33 adds **26 explicit Android-English identities** and raises semantic alignment to **1696 / 1838 (92.3%)**, leaving **142 unresolved**. Automatic calibration remains **163 attempts / 162 reproductions / 0 conflicts** on reviewed IDs. Android French is still never used as identity evidence.

The largest reviewed blocks are `$04E1`, `$04E2` and `$04E6`; the user then validated a contextual HTML review sheet covering `$0111`, `$0194`, `$02F1`, `$02F2`, `$03A6`, `$03A7`, `$04AB`, `$059D`, `$05B1`, `$05B2`, `$05B3`, `$05B4` and `$066F`. The validation sheet presents SNES USA, proposed Android EN anchors, Android FR payload and surrounding Android context. Use that UI again for future ambiguous/manual mapping batches rather than asking for validation from bare IDs.

`$05B4/CA:7864 -> 1887` is identity-valid but intentionally not inserted: Android 1887 combines the `634` text with the `...! Enter!` tail that SNES obtains by calling `$03A7`. A naive insertion would duplicate the translated tail. Keep this distinction between **accepted semantic identity** and **safe serialization**.

Round 33 preserves **1500/1500 Round-32 translation entries byte-for-byte**, removes none, and adds 86. The simulator-filtered corpus reaches **598 events = 574 complete + 24 PARTIEL**, with **1506 visible semantic source IDs / 1586 JSON entries** and exclusions of **94 alignment-incomplete + 5 formatter-rejected + 7 simulator-rejected**.

## Round 34 tight local structural follow-up

Round 34 adds **10 explicit Android-English identities** without introducing any new automatic rule. The accepted cases are small events whose Android-English identity is fixed by tight neighboring scene anchors or a unique local scene match: `$00B6/2478`, `$00BC/2494`, `$013B/874`, `$013F/875`, `$0151/311`, `$0158/296`, `$01C0/482`, `$02E2/2548`, `$0390/1811` and `$03E7/2343`.

Two examples show the intended evidence threshold. `$013B` has exact Android-English duplicates at 479 and 874, but only 874 lies in the already-established Luka run 872–876; `$0390` is the unique near-exact Gold-City-resident line at 1811, directly between neighboring accepted anchors 1808–1810 and 1812. These are explicit structural identities, not a generalized duplicate/fuzzy rule. Automatic calibration remains **163 attempts / 162 reproductions / 0 conflicts**.

The accepted alignment is **1706 / 1838 (92.8%)**, leaving **132 unresolved**. The Round-33 translation remains byte-for-byte unchanged (**1586/1586 entries, 0 removed**) and 10 entries are added. Duplicate-provenance or reused-subevent cases `$0145`, `$018B`, `$01EA`, `$0218`, `$02A9`, `$0557`, `$0115` and `$0122` remain intentionally unmapped pending contextual user review.

## Round 35 ROM-neighborhood duplicate disambiguation

The Round-34 review exposed a useful distinction: an exact English duplicate can be ambiguous lexically while still having strong **local provenance**. A first experiment using strict monotonic brackets was rejected because accepted mappings demonstrate real local Android reorderings. The retained rule therefore treats nearby accepted SNES carriers as a weighted Android-position **cloud**, not as a required increasing interval.

For an unmapped carrier whose normalized Android-English text has multiple exact copies with different Android-FR payloads, the rule may consider the duplicates only when the source contains at least **three normalized words**. It gathers up to 12 already accepted carrier mappings within `0x300` ROM bytes, weights evidence by SNES distance (plus a small same-event bonus), and scores each Android duplicate by proximity to those neighbors' Android anchors. A conservative winner margin is required, and all candidates for a pass are evaluated from a frozen pre-pass mapping set so the rule cannot self-reinforce by cascading. Android French is used only to determine whether duplicate copies have materially distinct localization payloads; it never selects the identity.

The rule is leave-one-out calibrated on accepted mappings where exact Android-English duplicates have **different French payloads**, which is the subset where choosing the wrong duplicate matters. Of 33 historical mappings in that audit, 22 produce a confident prediction and all **22/22 reproduce the accepted Android identity, with 0 conflicts**; the rule abstains on the other 11. This calibration is recorded separately from the established generic **163 attempts / 162 reproductions / 0 conflicts** calibration.

Round 35 applies the rule to four previously unresolved carriers: `$0145/C9:455F -> 241`, `$018B/C9:5BE5 -> 328`, `$0218/C9:956E -> 1198`, and `$0557/CA:64F6 -> 2174`. `$0557` also exercises the existing French-only trailing-player-turn filter: Android 2174 includes a mobile-only `%S(0,0)` continuation that has no corresponding SNES `PLAYER_NAME`, so only the SNES-carried Dyluck text is inserted.

The guard is intentionally narrower than "nearest duplicate". `$02A9` remains unresolved because Android 1577 and 1583 both inhabit the same Sandship cluster. Short/generic strings such as `What the...!`, `PHANNA:...`, `...Gzzz...` and `Water Palace` are not eligible even if the neighborhood score favors one occurrence. Reusable cannon/sign sub-events around `$0609-$060C` are a concrete counterexample to treating raw ROM adjacency as identity.

After this pass semantic alignment is **1710 / 1838 (93.0%)**, leaving **128 unresolved**. Round 35 preserves **1596/1596 Round-34 translation entries byte-for-byte**, removes none and adds four. The simulator-filtered corpus is **612 events = 588 complete + 24 PARTIEL**, with **1520 visible semantic source IDs / 1600 JSON entries** and exclusions of **80 alignment-incomplete + 5 formatter-rejected + 7 simulator-rejected**.

## Round 36 strict EN+FR-equivalent duplicate tie-break

Round 36 distinguishes semantic candidate identity from duplicate occurrence provenance. When two or more Android candidates have **byte-for-byte identical raw English anchor text and the same complete French localization interval**, those copies are treated as one semantic payload for candidate-margin purposes. French equality never creates the identity: the SNES -> Android-English match must first satisfy the conservative lexical gate (normalized source length >=24, lexical score >=90, source-token coverage >=80%, character similarity >=90%, and >=20 points over the next distinct EN+FR payload). This recognition reproduces **35/35 accepted calibration mappings with 0 conflicts**.

If that payload has several equivalent Android occurrences, one occurrence is selected only as a provenance tie-break from a **frozen** set of pre-existing concrete mappings. Up to 12 nearby ROM carriers within `0x300` contribute to a weighted Android-position cloud, with same-event evidence strongly preferred. Neither newly accepted mappings nor newly concretized equivalent alternatives can become anchors during the same pass. The original alternatives remain traceable in `android_equivalent_alternative_anchor_groups`.

The rule adds `$0115/C9:36B9 -> 99`, `$0122/C9:398B -> 799`, `$01D7/C9:7C87 -> 635`, and `$02BD/C9:BB6F -> 1619`. It also assigns concrete provenance to **100 existing equivalent-alternative records / 102 SNES IDs** without changing their localized payload. Three non-strict cases remain alternatives: `C9:0FA2`, `C9:107E` and `C9:6F3C`.

Same-event structure outranks the broad ROM cloud. This explicitly preserves `$01E5/C9:82B9 -> 668`, `$02AA/C9:B63C -> 1482`, and the reviewed `$024B/C9:9EC0 -> 1229`; a coarse physical-neighborhood winner is not allowed to rewrite those stronger proven origins.

After this pass semantic alignment is **1714 / 1838 (93.3%)**, leaving **124 unresolved**. Round 36 preserves **1600/1600 Round-35 translation entries byte-for-byte**, removes none and adds four. The simulator-filtered corpus is **616 events = 592 complete + 24 PARTIEL**, with **1524 visible semantic source IDs / 1604 JSON entries** and exclusions of **76 alignment-incomplete + 5 formatter-rejected + 7 simulator-rejected**.

## Round 37 isolated one-carrier ROM-neighborhood fuzzy alignment

Round 37 adds a deliberately narrow fuzzy rule for events containing exactly **one semantic SNES carrier**. It is meant for paraphrases whose Android-English identity is strongly supported by the surrounding scene even though they fall below the existing global lexical gates. Candidate ranking is by **distinct Android-English payload**, so repeated identical copies do not consume the lexical margin. Exact-English duplicate sets with materially different Android-FR payloads are excluded from this rule, and an Android anchor already concretely owned by an unrelated mapping is not reused generically.

All proposals are evaluated from a **frozen pre-pass mapping set**, so newly accepted Round-37 mappings cannot provide evidence for another Round-37 proposal. The normal branch requires normalized source length >=20, lexical score >=75, source-token coverage >=70%, character similarity >=70%, >=20 points over the next distinct English payload, positional score >=0.25 and mean Android-anchor distance <=160. A close-paraphrase branch requires lexical >=80, coverage >=65%, character similarity >=85%, margin >=20, positional score >=0.5 and mean distance <=80. The positional support uses the already-calibrated nearby-ROM Android block model; it is corroborating evidence, never a replacement for Android-English identity.

Leave-one-out calibration on accepted mappings that satisfy these gates produces **190/190 reproductions with 0 conflicts**. Round 37 accepts eight new identities: `$00D5/C9:1CB2 -> 74`, `$0183/C9:5875 -> 386`, `$0195/C9:5FAF -> 400`, `$01E1/C9:81A5 -> 767`, `$0221/C9:96E6 -> 210`, `$0225/C9:979A -> 211`, `$0272/C9:A5F1 -> 1341`, and `$03AE/C9:E38F -> 1949`. `$0272` is the close-paraphrase branch (`GONTMA` in SNES versus `Ognatam` in Android); the other seven use the standard branch.

The free-anchor guard intentionally rejects tempting reuse such as `$0269/C9:A49C -> 1400`, because Android 1400 is already concretely owned by `$0276/C9:A679`. Divergent exact duplicates such as `$01EA` and `$02A9` remain outside this rule.

After this pass semantic alignment is **1722 / 1838 (93.7%)**, leaving **116 unresolved**. Round 37 preserves **1604/1604 Round-36 translation entries byte-for-byte**, removes none and adds eight. The simulator-filtered corpus is **624 events = 600 complete + 24 PARTIEL**, with **1532 visible semantic source IDs / 1612 JSON entries** and exclusions of **68 alignment-incomplete + 5 formatter-rejected + 7 simulator-rejected**.

## Round 38 dense local Android-extension alignment

Round 38 follows the Round-37 one-carrier pass with a still narrower rule for **unique Android-English lines that expand a shorter SNES line inside an exceptionally dense local scene block**. Round-37 mappings are treated as accepted prior-pass context, but all Round-38 proposals are evaluated from one frozen context and cannot cascade among themselves. Android FR remains payload only and never participates in candidate identity.

Eligibility requires exactly one semantic carrier in the SNES event, normalized SNES length >=25 characters and >=6 words, a globally unique normalized Android-English candidate that is longer than the SNES line, lexical score >=65, source-token coverage >=85%, >=8 points over the next distinct Android-English payload, positional score >=1.5, mean Android-anchor distance <=40, and at least 8 nearby mapped neighbors. This is intentionally a local-scene extension rule, not a general lowering of fuzzy thresholds.

Accepted-history calibration yields **5/5 reproductions with 0 conflicts**. The rule adds exactly two mappings: `$0226/C9:97D6 -> Android 216` (`My son Dyluck...`, expanded on Android with the “lives next door” clause) and `$03C5/C9:E76C -> Android 2026` (the SNES fifteen-years line is contained semantically inside a longer Android sentence pair). Both are strongly bracketed by already mapped local scene anchors.

After this pass semantic alignment is **1724 / 1838 (93.8%)**, leaving **114 unresolved**. Round 38 preserves **1612/1612 Round-37 translation entries byte-for-byte**, removes none and adds two. The simulator-filtered corpus is **626 events = 602 complete + 24 PARTIEL**, with **1534 visible semantic source IDs / 1614 JSON entries** and exclusions of **66 alignment-incomplete + 5 formatter-rejected + 7 simulator-rejected**.



## Round 39 full-context reused-carrier review and stock-English payload exception

Round 39 adds no automatic matcher. Four previously unresolved carriers are accepted from user-reviewed full SNES-US context. `$019C/C9:61D3 -> 385` chooses one of the strictly EN+FR-identical Pandora guard copies (381/385) by adjacent scene position. `$01EA/C9:86C6 -> 759` and `$02A9/C9:B5CE -> 1583` are both **one reused SNES subevent -> two Android call-site records** cases: the chosen Android ID supplies the shared localization payload, while the alternate call-site ID remains documented rather than being treated as a competing identity.

`$0689/CA:8F20 -> 769` is different: Android English identity is structurally proved by the event's item command, but Android French is wrong. The stock `$0689` script grants `OP_1E A4`, the Whip/Leather Whip weapon (`$24` after the weapon-class offset); `$0687` is the actual Magic Rope chest and grants `OP_1E 46`, item `$06`. Android FR incorrectly gives both Android 469 (Magic Rope) and 769 (Leather Whip) the same Leather-Whip chest sentence. For this exact user-validated exception, the mass formatter keeps Android 769 as identity but serializes the canonical USA `CA:8F20` source text `Found the Whip!`. This is passed through the normal `french_dialogues` data serializer/relocation system and adds no runtime mechanism.

This exception does **not** make Android FR an identity source and does not generalize to merely awkward translations. A stock-English override requires independently proven Android-English identity plus explicit user validation that the corresponding Android-FR payload is erroneous.

After Round 39, alignment is **1728 / 1838 (94.0%)**, leaving **110 unresolved**. The **1614/1614** Round-38 translation entries remain byte-for-byte unchanged, 0 are removed and 4 are added. The simulator-filtered corpus is **630 events = 606 complete + 24 PARTIEL**, with **1538 visible semantic IDs / 1618 JSON entries** and exclusions **62 alignment-incomplete + 5 formatter-rejected + 7 simulator-rejected**.


## Round 40 explicit multi-carrier structural review

Round 40 does not lower or add a generic fuzzy threshold. Fourteen remaining semantic IDs are accepted as explicit structural reviews where the Android-English scene is locally locked, including exact local call-site disambiguation and Android/SNES segmentation differences. `$00C0/C9:1A33 -> 2508` fills the sole missing Mammon line in the accepted Gold City 2505-2512 run. `$011B/C9:3801 -> 35` selects the second banishment duplicate because it follows the same Yes/No departure prompt as SNES `$011A`. `$023C/C9:9D5F -> 1205` and `C9:9D7C -> 1206` complete the Neko block immediately before the already proven 1207-1209 Save/Buy/Sell choices. `$0114/C9:364B+C9:369A -> 90` joins the two SNES halves of the Elder banishment speech. `$02C0/C9:BC60+C9:BC72 -> 2629` joins the two Karon's Ferry sign carriers. `$03ED/C9:F13C -> 2364+2365+2366` and `C9:F18D -> 2367` reconstruct the contiguous debate/static block after accepted 2362+2363. `$0555/CA:632B+PLAYER_NAME(1)+CA:6337 -> 2157`, `CA:63F1 -> 2165`, and `CA:6423 -> 2166+2167` reconstruct the contiguous Thanatos/Dyluck exchange.

These mappings remain Android-English identities; Android French only supplies the payload after identity is established. Round 40 does not let the reviewed additions cascade into a weaker matcher. The accepted-history population for the pre-existing Round-37 isolated-fuzzy gate grows from 188 to **190/190 reproductions**, still **0 conflicts**, solely because the reviewed corpus now contributes two additional eligible historical cases; the gate itself is unchanged.

After Round 40, semantic alignment is **1742 / 1838 (94.8%)**, leaving **96 unresolved**. The **1618/1618** Round-39 translation entries remain byte-for-byte unchanged, 0 are removed and 14 are added. The simulator-filtered corpus is **635 events = 612 complete + 23 PARTIEL**, with **1552 visible semantic IDs / 1632 JSON entries** and exclusions **57 alignment-incomplete + 5 formatter-rejected + 7 simulator-rejected**. `$0555` is semantically complete but remains PARTIEL only because five already mapped carriers are deliberately layout-deferred.

## Round 41 user-validated full-context follow-up

Round 41 adds no automatic matcher rule. The user validates the determinate recommendations from the Round-40 contextual HTML: `$0013/C9:0923 -> 389`, where Android EN paraphrases the captured anti-witch troops as soundly defeated inside the same Pandora/Elinee block; `$028E/C9:AC32 -> 1505`, where Android extends the Republic secret sandship line with its Fire Palace mission in the same Sandship block; and reusable Cannon Travel RETURN labels `$060A/CA:86B5 -> 421` / `$060B/CA:86C3 -> 422`. Reusing 421/422 is intentional because the SNES subevents are reusable labels and the Android pair is the matching destination-label block.

The same HTML intentionally offered no unique recommendation for `$0235` (`What the...!`) or `$03CF` (`PHANNA:...`): several Android occurrences remain plausible and their French differs or their scene-state provenance is unproven. User validation therefore does not force either case; both remain TO REVIEW pending trigger/caller/map-state evidence.

After Round 41, semantic alignment is **1746 / 1838 (95.0%)**, leaving **92 unresolved**. All **1632/1632** Round-40 translation entries remain byte-for-byte unchanged, 0 are removed and 4 are added. The simulator-filtered corpus is **639 events = 616 complete + 23 PARTIEL**, with **1556 visible semantic IDs / 1636 JSON entries** and exclusions **53 alignment-incomplete + 5 formatter-rejected + 7 simulator-rejected**. Automatic calibration remains **163 attempts / 162 reproductions / 0 conflicts**; the accepted-history exact-duplicate audit now reproduces **23/23 with 0 conflicts**.

## Round 42 user-validated non-text provenance follow-up

Round 42 resolves the four carriers reviewed in the dedicated contextual HTML without introducing any automatic matcher rule. `$0235/C9:9B74 -> 951` is no longer a short-text guess: map `$0115`'s walk-on trigger enters `$0232 -> $0235` on the Tonpole/Biting-Lizard encounter map, and Android 951 is immediately followed by the Gloves-Orb reward at 952. `$03CF/C9:E993 -> 1976` is fixed by direct map-object provenance: map `$007E` object #4 points to `$03CF`, is active only at event flag `$3A == 2`, and sits in the same state block as already aligned 1971-1975.

`$0521/CA:5CE6 -> 2203` is a cross-event segmentation case rather than a fuzzy match. The SNES executes `$04D4` first (`Welcome. The Emperor awaits you.`) and then the `$0521` carrier (`To your right, please.`); Android 2203 stores their exact normalized concatenation, while 2204 is a strict EN+FR duplicate. The exact allow-listed `called_prefix_android_merge_suffix` formatter path keeps the already translated `$04D4` call and serializes only the official French suffix into `CA:5CE6`. `$01D5/C9:7C25 -> 605` is a reused-subevent response; Android 605 and 608 are strict EN+FR duplicates, and 605 is retained as the representative anchor while the identical 608 provenance remains documented.

After Round 42, semantic alignment is **1750 / 1838 (95.2%)**, leaving **88 unresolved**. All **1636/1636** Round-41 translation entries remain byte-for-byte unchanged, 0 are removed and 4 are added. The simulator-filtered corpus is **643 events = 620 complete + 23 PARTIEL**, with **1560 visible semantic IDs / 1640 JSON entries** and exclusions **49 alignment-incomplete + 5 formatter-rejected + 7 simulator-rejected**. Generic automatic calibration remains **163 attempts / 162 reproductions / 0 conflicts**; the ROM-neighborhood exact-duplicate accepted-history audit is now **25/25 reproductions / 0 conflicts**.



## Round 43 user-validated structural families

Round 43 adds **26 explicit Android-English identities** and no generic matcher. The accepted evidence comes from reconstructed SNES control flow rather than lexical score alone: `$022F` joins two carriers around `PLAYER_NAME(2)` into Android 1005; `$02B9` resolves Android 1618 on the `Salamando ... gone!` branch while preserving the shared prefix used by already aligned `$02BD -> 1619`; `$0358-$035E` plus shared `$0360` reconstruct the seven actual elemental-orb reaction paths against Android 2839/2844/2852/2857/2865/2870/2881; `$0500-$0507` plus shared `$0509` reconstruct the eight `Received ... Orb!` weapon-reward paths against Android 952/122/1008/631/901/934/786/1164; and `$07FA/$07FB/$07FF` reconstruct the plural/name game-over variants against Android 6/7.

`$035F/C9:D1B8` (`Dryad`) remains **unmapped in Android identity** because no Android-English counterpart has been found. A separate user-authorized temporary manual French supplement (`Dryade fera réagir l'orbe !`) was allowed through the normal PARTIEL + simulator gate at this historical checkpoint. Manual payload is deliberately not alignment evidence. **Superseded in Round 59:** exact SNES-JP transcription proves this carrier itself is only `ドリアード`, so the expanded payload was withdrawn. **Round 60:** the user validates the minimal manual payload `Dryade`; Android identity remains unmapped.

The formatter changes are exact allow-listed redistributions only: max-name-safe pagination for `$022F`, shared-branch redistribution for `$02B9`, shared magic suffix distribution for the orb reactions, shared weapon-orb suffix distribution, and the two game-over frames. They neither introduce nor weaken an automatic identity rule.

After Round 43, semantic Android alignment is **1776 / 1838 (96.6%)**, leaving **62 unresolved**. All **1640/1640** Round-42 translation entries remain byte-for-byte unchanged, 0 are removed and 27 are added (26 Android-identified entries plus the one temporary Dryad supplement). The simulator-filtered corpus is **666 events = 642 complete + 24 PARTIEL**, with **1585 visible semantic IDs / 1667 JSON entries** and exclusions **26 alignment-incomplete + 5 formatter-rejected + 7 simulator-rejected**. Generic calibration remains **163 attempts / 162 reproductions / 0 conflicts**; exact duplicate is **25/25**, strict-equivalent duplicate **35/35**, and the unchanged isolated fuzzy gate is now calibrated on **188/188 reproductions / 0 conflicts**. The historical fuzzy population shrinks mechanically from 190 because `C9:D239` and `C9:D31C` are no longer eligible once the new orb-family context is frozen; no accepted mapping conflicts.


## Round 44 determinate structural identities

Round 44 adds **14 explicit Android-English identities** under the user's standing authorization to accept no-doubt cases; it introduces no generic matcher. The six direct/local cases are `$0012/C9:090A -> 378`, `$001F/C9:0983 -> 2451`, `$0126/C9:3A39 -> 3438`, `$025F/C9:A255 -> 1362`, `$02E6/C9:C68A -> 2567`, and `$03AC/C9:E32D -> 1950`. The remaining eight identities are standard parameterized inn callers: `$0320 -> 110`, `$0321 -> 229`, `$0322 -> 502`, `$0324 -> 1365`, `$0325 -> 1907`, `$0326 -> 1961`, `$0327 -> 2319`, `$0328 -> 2498`. `$0323` remains unresolved because Android 194 is explicitly the Neko-specific 30-GP `purrrfect / Meow?` variant rather than the shared standard prompt.

`$001E/C9:0970` is intentionally **not** assigned an Android ID. The SNES shared `JEHK:Sage Joch` carrier precedes four destination subevents already aligned to Android 2453/2455/2458/2461, and each Android FR destination owns `Maître Jach` itself. The formatter therefore reduces only this unresolved shared prefix to its required newline layout and leaves the event PARTIEL. Likewise `$035F/C9:D1B8` remains identity-unmapped; at this historical checkpoint its temporary manual localization was corrected from `Dryad` to the source-consistent French name `Dryade`, yielding `Dryade fera réagir l'orbe !` without treating FR terminology as identity evidence. **Round 59 later supersedes that expanded payload** because exact JP shows the carrier contains only the name `ドリアード`; **Round 60** explicitly validates only the minimal manual payload `Dryade`.

The `$0126` identity is exact but needs an allow-listed serialization: stock `PLAYER_NAME(0)` remains in place, then ` :` and an explicit newline precede the official Android-FR sentence. This passes the independent simulator with a nine-character maximum player name and no implicit wrap.

After Round 44, semantic Android alignment is **1790 / 1838 (97.4%)**, leaving **48 unresolved**. The simulator-filtered corpus is **673 events = 648 complete + 25 PARTIEL**, with **1592 visible semantic IDs / 1674 JSON entries** and exclusions **19 alignment-incomplete + 5 formatter-rejected + 7 simulator-rejected**. Compared with Round 43, **1666/1667** old translation entries are byte-for-byte unchanged, one is intentionally corrected (`Dryad` -> `Dryade`), seven are added and none removed. Generic calibration remains **163 attempts / 162 reproductions / 0 conflicts**; exact duplicate remains **25/25**, strict-equivalent duplicate **35/35**, and the unchanged isolated one-carrier fuzzy gate is now **187/187 / 0 conflicts** because one additional historical probe ceases to satisfy positional eligibility after the new structural anchors are frozen.


## Round 45 no-doubt structural pass

Round 45 adds no generic rule. Under the user's standing authorization for cases with no remaining identity doubt, four exact structural units are accepted: `$00C4/C9:1A62 -> 1626`; `$01B6/C9:6AD2 + C9:6B5A -> 584` with Android-FR redistribution through FR-only slot 585; `$01DA/C9:7E64 + C9:7E72 + C9:7E81 -> 676+677`; and `$04F0/CA:4D71 -> 2541`. The first is disambiguated from exact duplicate 1689 by the Kakkara/King-Amar scene, the second by the unchanged Watts shortcut call/movement sequence, the third by the contiguous naming scene and its existing PLAYER_NAME commands, and the fourth by map-object table `$0018` on the Tasnica entrance map.

The `$01DA` unit is a reviewed Android-FR resegmentation. `C9:7E64` was already mapped to 676 before Round 45; the new unit resolves `C9:7E72` and `C9:7E81` and groups the whole 676/677 exchange. Android FR deliberately omits the third repetition of `%S(0,0)`, so the serializer preserves the first two stock `PLAYER_NAME(0)` commands and suppresses only the third immediately before empty `C9:7E81`. This is an exact allow-list, not a generic permission to remove dynamic-name commands.

Semantic alignment becomes **1796 / 1838 (97.7%)**, leaving **42 unresolved**. The corpus becomes **675 events = 652 complete + 23 PARTIEL**, with **1597 visible semantic IDs / 1681 JSON entries** and exclusions **17 alignment-incomplete + 5 formatter-rejected + 7 simulator-rejected**. Six previously unresolved IDs become aligned; Round-45 provenance covers seven source carriers because `C9:7E64` was already aligned and is regrouped. Compared with Round 44, **1670/1674** old translation entries are byte-for-byte unchanged, four existing `$01DA` strings are reflowed only, seven entries are added, and none removed. Generic calibration mechanically becomes **164 attempts / 163 reproductions / 0 conflicts** because `C9:1984` re-enters the eligible reproducible set once the Kakkara context is frozen. Exact duplicate remains **25/25**, strict-equivalent duplicate **35/35**, isolated fuzzy **188/188**, and local extension **5/5**, all with 0 conflicts and unchanged thresholds.


## Round 46 explicit `systxt` chest review

Round 46 adds no automatic matcher and does not merge Android namespaces. Two previously unresolved SNES money-chest subevents are accepted against the separate system-text namespace: `$067E/CA:8E72 -> systxt 101254` and `$067F/CA:8E8F -> systxt 101254`. The Android-English record is the parameterized chest message `Found $0d GP!`; SNES call structure plus `OP_36 E8 03` / `OP_36 32 00` proves the fixed 1000/50 amounts. The formatter substitutes those fixed values into the official French template rather than inventing a runtime parameter. The adjacency of `systxt` 101254-101256 as the money/Leather-Whip/Magic-Rope chest block disambiguates 101254 from duplicate system message 100177.

The two item chests use a stricter split between identity and localization evidence. `$0687/CA:8EEF` remains identity-mapped to **`scrtxt` EN 469** (`Found the 『Magic Rope』!`), independently proven by `OP_1E 46` granting item `$06`. `$0689/CA:8F20` remains identity-mapped to **`scrtxt` EN 769** (`Found the Leather Whip!`), independently proven by `OP_1E A4` granting weapon `$24`. Their `scrtxt` French payloads/workaround are corrected from `systxt` 101256 (`Corde magique`) and 101255 (`Fouet en cuir`) respectively. Crucially, `systxt_en` 101255/101256 are already French text, so they are **never treated as Android-English identity**; they are localization-correction evidence only after `scrtxt` identity is fixed.

This supersedes the Round-39 `$0689` stock-English exception without weakening the rule that Android English is the identity layer. The generic `_AutoCandidateIndex` remains `scrtxt`-only, and non-`scrtxt` reviewed records are excluded from generic calibration. Round-46 semantic alignment becomes **1798 / 1838 (97.8%)**, leaving **40 unresolved**. Corpus: **677 events = 654 complete + 23 PARTIEL**, **1599 visible semantic IDs / 1683 JSON entries**, exclusions **15 alignment-incomplete + 5 formatter-rejected + 7 simulator-rejected**. Compared with Round 45, **1679/1681** old translation entries are unchanged, `CA:8EEF` and `CA:8F20` are corrected, `CA:8E72` and `CA:8E8F` are added, and none are removed. Generic calibration becomes **165 attempts / 164 reproductions / 0 conflicts** because the already-proven `$0687` `scrtxt` identity is now represented by an explicit reviewed record; matcher thresholds and algorithms are unchanged.


## Round 47 non-text negative-evidence audit

Round 47 changes no semantic identity and no translation. It formalizes negative evidence for 14 still-unresolved carriers using the event-call graph plus the canonical ROM map-trigger (`$084000`) and map-object-pointer (`$087000`) tables. Six carriers are `validated_no_equivalent` (`$00EE`, `$00F1`, `$00F3`, `$0269`, `$02DE`, `$0603`); eight are `validated_android_omission` (`$0042`, `$0207`, `$0208`, `$024F`, and four `$02FC` diary carriers).

These statuses must never be promoted to Android IDs merely to increase coverage. `validated_no_equivalent` means the reviewed routing/provenance does not yield a unique Android-English counterpart; `validated_android_omission` means the SNES branch/scene is proved but the corresponding Android scene omits that carrier. The reproducible audit is the reproducible Round-47 classification encoded by the importer (legacy JSON no longer versioned). Alignment therefore remains **1798/1838 (97.8%)** with **40 unresolved**.


## Round 48 exact formatter recovery + Tasnica omission audit

Round 48 adds **no Android identity** and no automatic matcher. It addresses already-proven mappings that were excluded only because Android French introduced dynamic vocatives absent from both Android English and the SNES command stream. Seven exact carrier/Android-ID records remove only that Android-FR-only `%S(...)` vocative: `$0119/C9:37AF -> 109`, `$0127/C9:3AC3 -> 914`, `$01B5/C9:68BA -> 574`, `$0227/C9:9827 -> 218`, `$0295/C9:AF50 -> 1518`, `$04E6/CA:40AF -> 87`, `$04E7/CA:4126 -> 91`. No SNES `PLAYER_NAME` command is created, moved or removed. The rule is an explicit allow-list, not a generic formatter heuristic.

`$0127` additionally receives an exact-token-gated pagination repair: page transitions are inserted only after the reviewed sentence boundaries `ici...` and `Quoi ?!`, and a `TEXT_CLEAR`-only transition follows the existing stock `WAIT $08`. Both stock `PLAYER_NAME(0)` commands, timed wait and actor actions remain in stock order. `$0119`, `$0127` and `$0295` become simulator-clean complete events; `$01B5`, `$0227`, `$04E6` and `$04E7` remain PARTIEL but each admits one additional French carrier.

Round 48 also freezes `$02E1/C9:C56C` (`We'll smash the Empire!`) as `validated_android_omission`. Map `$001A` object #0 at ROM `$089538` directly selects the live Tasnica event under the same `$3C` state family as `$02E2-$02E7`; Android 2539-2577 covers the corresponding Tasnica NPC block but contains no equivalent line. It remains unresolved and receives no Android ID or French payload.

Alignment therefore remains **1798 / 1838 (97.8%)**, with **40 unresolved**. The formatter-filtered corpus grows from 677 to **680 events = 657 complete + 23 PARTIEL**, with **1613 visible semantic IDs / 1697 JSON entries** and exclusions **15 alignment-incomplete + 4 formatter-rejected + 5 simulator-rejected**. Compared with Round 47, all **1683/1683** previous translation entries remain byte-for-byte unchanged, **14 entries are added**, and none are removed or modified. Static simulation remains **0 errors / 0 warnings / 0 implicit wraps**.


## Round 49 exact formatter/simulator recovery

Round 49 adds **no Android identity**, no automatic matcher and no namespace change. Semantic alignment therefore stays **1798 / 1838 (97.8%)**, with **40 unresolved**. The pass operates only on already-accepted mappings: `$02CD` removes one exact Android-FR-only `%S(0,0) :` label absent from both Android EN and the entire SNES event command stream; `$03F0` distributes Android 2361 across the exact three stock sound carriers; and `$04E9` gains seven French carriers after two exact clear-only resets following existing `WAIT $00` pauses. `$04E9/CA:48DC+CA:4925 -> Android 895` remains deliberately layout-deferred because Android FR condenses the two SNES statements into one unsplittable sentence. `$0205` is likewise left formatter-rejected rather than forcing a clause split across `PLAYER_NAME(0) + WAIT $00 + TEXT_CLEAR`.

Compared with Round 48, **1697/1697 previous translation entries remain byte-for-byte unchanged**, **11 entries are added**, and none are removed or modified. The simulator-filtered corpus becomes **683 events = 659 complete + 24 PARTIEL**, with **1624 visible semantic IDs / 1708 JSON entries** and exclusions **15 alignment-incomplete + 2 formatter-rejected + 4 simulator-rejected**. Static simulation remains **0 errors / 0 warnings / 0 implicit wraps**. Exact evidence is recorded in the legacy generated Round-49 review report (no longer versioned).


## Round 50 exact segmentation without new identity

Round 50 adds **no Android ID** and no automatic identity rule. Alignment remains **1798 / 1838 (97.8%)**, with **40 unresolved**. The only mapping change is a segmentation refinement inside the already-proven `$01CE` unit: Android EN 536 is the donation prompt, 537 is the affirmative choice, and already-accepted 538 is the negative choice. The stock `CHOICE_BEGIN` / `CHOICE_OPTION` boundaries therefore split the previous 536+537 many-to-many ownership into `C9:7827 -> 536` and `C9:7856 -> 537`. the importer's Round-50 reviewed structural evidence (legacy JSON no longer versioned) records this as **user-validated** structural evidence; it does not create new identity coverage.

The other Round-50 gains are simulator/formatting admission only. `$0040` becomes PARTIEL through the proven forward/equal `TEXT_X` decoded-index model while its dynamic-name-mismatched `C9:0F75` remains stock. `$04FD` becomes PARTIEL only because all 19 special `ending_text` blocks remain byte-identical to the clean USA event. `$01CE` receives one exact layout-only `TEXT_CLEAR` at newline-only `C9:7824` after its existing `WAIT $00`. `$0429` remains excluded rather than accepting a multi-part layout workaround around unresolved Android-FR `PLAYER_NAME` redistribution.

Compared with Round 49, **1708/1708** existing translation entries remain byte-for-byte unchanged, **23 entries are added**, none removed or modified. Corpus: **686 events = 660 complete + 26 PARTIEL**, **1646 visible semantic IDs / 1731 JSON entries**; exclusions **15 alignment-incomplete + 2 formatter-rejected + 1 simulator-rejected**; accepted-event simulation **0 errors / 0 warnings / 0 implicit wraps**. The user subsequently runtime-validated the Round-50 admissions `$0040`, `$01CE` and `$04FD`; the Round-49 `$02CD`, `$03F0` and `$04E9` candidates are treated as validated in the same checkpoint. `$0429` remains intentionally excluded.


## Round 51 residual unresolved audit

Round 51 changes **no Android identity, no French payload, no formatter rule and no ROM byte**. Semantic alignment stays **1798 / 1838 (97.8%)**, with **40 unresolved**; the simulator-filtered corpus remains **686 events = 660 complete + 26 PARTIEL**, **1646 visible semantic IDs / 1731 JSON entries**, with exclusions **15 alignment-incomplete + 2 formatter-rejected + 1 simulator-rejected**. `patches/all.ips` is byte-for-byte identical to the runtime-validated Round-50 patch.

The purpose of the round is to close the last five *unclassified* entries in the residual 40 without inflating the mapping count. `$0278/C9:A730` (`Press START to see the map.`) and `$0278/C9:A74E` (`L/R buttons change modes.`) were already user-validated as Android-absent manual-supplement carriers; Round 51 formalizes them as `validated_android_omission`. `$0323/C9:CE5A` is likewise `validated_android_omission`: the stock caller is the standard shared **30-GP** inn path, while Android `scrtxt` has exact standard prompts for 5, 10, 15, 50, 100, 120, 150 and 200 GP and **no** `One night is 30 GP. Want to stay?` record. Android 194 (`30 GP a night would be purrrfect. Meow?`) is the distinct Neko/meow prompt and remains explicitly forbidden as a substitute.

The two remaining carriers are not omissions but shared contextual templates. `$0330/C9:CEA3` (`One night is`) and `$0331/C9:CEB3` (`GP. Want to stay?`) are classified `validated_contextual_template`: at runtime they surround the price supplied by `$0320-$0328`, while Android stores the resulting complete prompt as separate per-price records. The existing formatter legitimately uses Android 110 only as a **serialization template** for the common French suffix; assigning 110 as the semantic identity of either shared SNES fragment would falsely turn a one-to-many contextual subroutine into a one-to-one mapping. They therefore remain in the unresolved 40 by design.

After this audit, the 40 unresolved IDs contain no free lexical candidate pool under the current policy: **14** are `validated_android_omission`, **8** are `validated_no_equivalent`, **2** are `validated_contextual_template`, **7** belong to user-validated visually complete Android adaptations/status overrides (`$0103`, `$017F`, `$01DC`, `$0602`), and the remaining **9** are explicit handoff locks (`$001E`, `$015A`, `$01C5`, `$035F`, two `$04E1` carriers, three `$05F8` carriers). Any future increase above 1798/1838 therefore requires genuinely new provenance or an explicit decision to reopen one of those locks; a new generic lexical matcher is not justified by the residual set.

Reproducible evidence is stored in the importer's Round-51 reproducible evidence (legacy JSON no longer versioned).


## Round 52 exact structural formatter recovery

Round 52 changes **no Android identity, no automatic matcher and no namespace rule**. Semantic alignment therefore remains **1798 / 1838 (97.8%)**, with the same **40 unresolved** carriers fully accounted by the Round-51 residual audit. The round instead serializes six already-owned mappings that were previously kept stock because their French payload crossed stock WAIT/action boundaries. Every case remains an explicit reviewed structural mapping. Its current serialization is expressed through `dialogues_mapping_layout_recipes.json`; no generic WAIT/action fallback is widened.

- `$01B5/C9:6921+C9:6954 -> Android 577`: Android FR already moved the axe instruction into the preceding owned slot 575. The remaining two French sentences therefore split at `J'ai compris !` around the unchanged stock `WAIT $00 / TEXT_CLOSE / action / WAIT $08 / TEXT_OPEN` scene bridge.
- `$01B9/C9:6C0F+C9:6C21 -> Android 593`: the elder reprimand remains before the stock actor action + `WAIT $04`; `Excusez-le...` resumes after it.
- `$01B9/C9:6CDD+C9:6D0D -> Android 596`: the two complete French thoughts remain on opposite sides of the stock `OP_34`. The formatter's page clear replaces only the stock leading newline immediately after an existing `WAIT $00`.
- `$01B9/C9:6DC1+C9:6DD9 -> Android 599`: newline-only `C9:6DBC`, already immediately after a stock `WAIT $00`, becomes a layout-only `TEXT_CLEAR` before the unchanged reaction action; the stock `OP_34` remains between the two French reaction sentences.
- `$04E6/CA:4074+CA:4095 -> Android 86`: Android FR turns the stock mid-sentence movement into an explicit hesitation (`Chef : ...`), so the unchanged `OP_32` naturally remains between the hesitation and `Je regrette...`.
- `$04E7/CA:4211+CA:4249 -> Android 95`: the two French farewell sentences align on the stock `WAIT $08`. `CA:4211` keeps its stock leading newline, `PLAYER_NAME(0)` remains in place, and one exact `TEXT_CLEAR` is emitted at the start of `CA:4249` after the timed wait; punctuation carrier `CA:4255` receives the official post-name continuation.

Compared with the runtime-validated Round-50 translation payload, **1731/1731 existing entries remain byte-for-byte unchanged**, **14 entries are added**, and none are removed or modified. `$01B5`, `$01B9` and `$04E7` become complete; `$04E6` remains PARTIEL only at its larger village-expulsion redistribution. Corpus: **686 simulator-clean events = 663 complete + 23 PARTIEL**, **1658 visible semantic IDs / 1745 JSON entries**, with exclusions still **15 alignment-incomplete + 2 formatter-rejected + 1 simulator-rejected**. Static simulation remains **0 errors / 0 warnings / 0 implicit wraps**. These Round-52 changes were subsequently runtime-validated by the user.


## Round 53 Android-FR residual exhaustion audit

Round 53 changes **no Android identity, no French translation payload, no formatter rule and no ROM byte**. Round 52 is now runtime-validated by the user. The purpose of this pass is to exhaust the remaining source-side possibility that Android French contains useful prose in records whose Android-English slot is empty.

The complete `scrtxt` namespace contains **62 IDs where Android EN is empty and Android FR is non-empty**. Of these, **58 are already owned** by accepted mappings because Android FR redistributes an already-proven English identity across adjacent IDs. Only **4 are unowned**: 1688 (`Ça fait rêver !`) is an Android-only Kakkara embellishment with no residual SNES carrier; 2155 (`%S(0,0) : Allons-y !`) is an Android-only Dyluck-scene interjection with no residual SNES carrier; 3260 and 3261 are FR-only Thanatos transition/body-collapse prose inside the explicitly locked `$04E1` redistribution and have no Android-English identity. None may safely create a new SNES mapping.

Combined with the Round-51 English audit, this closes Android `scrtxt` discovery under the current identity policy. Alignment therefore remains **1798 / 1838 (97.8%)**, **40 unresolved**. the importer's Round-53 deterministic residual classification (legacy JSON no longer versioned) deterministically records the FR-only audit and final categories; the legacy Round-53 context HTML (no longer versioned) exposes every residual carrier in a filterable manual-review sheet. The final residual split is **14 validated Android omissions + 8 validated no-unique-equivalent cases + 2 contextual templates + 7 runtime-validated visual Android adaptations + 9 explicit handoff locks**. No new generic matcher is justified.


## Round 54 exact payload completion after Android exhaustion

Round 53 establishes that the Android source search is exhausted under the current policy: semantic alignment remains **1798 / 1838 (97.8%)**, with all **40 residual carriers** classified by reviewed negative/contextual evidence or explicit locks. Round 54 therefore does not reopen identity discovery. It only asks whether official French already attached to proven Android identities can be serialized on exact stock structures without inventing a split or weakening the simulator.

Five exact units qualify: `$0040 -> 681`, `$0041 -> 625`, `$013A -> 848`, `$0559 -> 2146`, and `$0592 -> 1030`. `$0040` and `$0041` become complete. `$013A` remains PARTIEL because Android FR omits the second SNES sentence `C9:40D7`; that omission is now explicit rather than hiding the event as complete. `$0559` and `$0592` remain PARTIEL with their structurally incompatible follow-up Android units deferred. Android IDs 1031 and 2147, plus the previously documented `$04E3`, `$04FD`, `$0227` cases, are retained as found-but-unsafely-serializable evidence rather than forced.

No prior translation entry changes: **1745/1745** Round-52 entries are unchanged and **8** new entries are added. The resulting corpus is **686 simulator-clean events = 665 complete + 21 PARTIEL**, **1663 visible semantic IDs / 1753 JSON entries**, with **0 errors / 0 warnings / 0 implicit wraps**. The searchable the legacy Round-54 exhaustion cross-index (no longer versioned) was the Round-54 cross-index at this historical checkpoint: Round-54 recoveries, then-current PARTIEL carriers whose Android identity was already known, and the 40 Android-not-found/negative-evidence carriers were deliberately shown as separate states. For the current checkpoint, use `docs/HANDOFF.md` and the Round-67 review files.


## Round 55 review-queue cleanup (zero ROM diff)

Round 55 changes no semantic identity, translation payload, formatter/simulator behavior, IPS or ROM byte. It records the user's final review-priority decisions after Android-source exhaustion. Eight residual bookkeeping items are explicitly **no action required**: `$001E` is a covered shared Joch/Jach fragment; `$0323/$0330/$0331` are the already-covered parameterized inn price/template path; `$0269`, `$02DE` and `$0603/CA:85FC` are unreferenced/orphan stock content in the canonical routing audit; `$035F` already has the validated manual payload `Dryade fera réagir l'orbe !`. **Historical note:** Round 59 supersedes the expanded `$035F` approval after exact JP transcription showed that the carrier itself contains only `ドリアード`; Round 60 validates only the minimal manual payload `Dryade`. The Round-55 classification file is retained as historical evidence.

The strict semantic alignment remains **1798/1838** because these classifications do not invent Android identities. the legacy generated Round-55 worklist (no longer versioned) is the user-facing queue: it defaults to **34 events / 89 carriers requiring action**, with the eight no-action events retained under an informational filter. Exact classifications are stored in the importer's Round-55 classifications (legacy JSON no longer versioned).

## Round 69 — targeted scene completion and playable-dialogue closure

Round 69 adds **no new Android semantic identities**: alignment remains **1798/1838**. Instead it applies user-reviewed, deterministic regional resegmentations for `$010C`, `$015A`, `$01C5`, `$0204/$0205`, `$0227`, `$04E2`, `$04E5`, `$04E6`, `$04E9`, `$04FD`, `$0559`, `$0592`, plus the unchanged numeric `$05B4` carrier. The layouts are stored in `mappings/android/dialogues_redistribution_recipes.json` and are guarded by `tools/check_dialogue_regressions.py`.

The formatter now admits **701 simulator-clean events = 701 complete + 0 PARTIEL**, **1810 accepted semantic source IDs / 1946 JSON entries**, with **3 exclusions**, all `alignment_incomplete` because they are routing-audited unused/orphan stock content: `$0269/C9:A49C`, `$02DE/C9:C4FB`, `$0603/CA:85FC`. After scene-level semantic review, the former 15 provenance-only PARTIEL events were promoted to complete. Their manual-JP, validated-suppression, and shared-prefix provenance remains preserved in `user_validated_visually_complete_events` rather than in `partial_events`.

Accordingly, Round 69 is the first checkpoint that can claim **100% French coverage of dialogue reachable through the canonical event/map/object routing audit**, while deliberately retaining the three unreachable stock strings rather than inventing Android mappings. Full simulation remains **0 errors / 0 warnings / 0 implicit wraps**.


### Resegmentation provenance

Whole-scene and targeted resegmentations store **no translated prose**. `mappings/android/dialogues_redistribution_recipes.json` contains only Android FR IDs, token indexes, `PLAYER_NAME` placeholders, punctuation, and layout separators. The final carrier text is reconstructed from `sources/android/scrtxt_fr.bin` on every deterministic import. Non-Android French remains exclusively in `translations/dialogues_manual_supplements.json`. `tools/check_dialogue_redistribution_recipes.py` rejects alphabetic literals in the recipe manifest and verifies the regenerated payload.
