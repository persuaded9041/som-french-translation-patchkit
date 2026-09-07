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
The evidence is reproducible as `mappings/android/dialogues_review_round6.json`;
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

```bash
python3 tools/import_android_text.py --only dialogue-format-pilot \
  --rom "Secret of Mana (USA).sfc"
python3 tools/import_android_text.py --only dialogue-format-pilot \
  --rom "Secret of Mana (USA).sfc" --check
```

The historical pilot now writes its three translated entries to
`mappings/android/dialogues_format_pilot_translation.json` plus the reproducible
trace report `dialogues_format_pilot.json`, so rerunning the pilot cannot overwrite
the current translation batch. The runtime validation remains restricted to
event `$0107`.
The formatter:

- regenerates the accepted alignment from the original Android EN/FR sources;
- binds `%S(index,0)` only to existing SNES `PLAYER_NAME` commands;
- refuses to cross unrelated event commands;
- removes Android-only presentation wrapping (`_`, Android line breaks and
  ideographic spaces) without rewriting translated prose;
- reflows against **two independent runtime constraints**: a conservative
  240-pixel VWF target and component 06's validated 38-decoded-character parser
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
and 36 / 19 characters. Component 08 rebuilds the event from 122 to 162 bytes
and relocates it deterministically to `$E8:2000`. **The Android correspondence
and the revised dual-limit French presentation are runtime-validated.** The next
expansion step is therefore charset/structural normalization, documented in
`DIALOGUE_CHARSET_AUDIT.md`, rather than further tuning of this pilot.
### First complete-event expansion

After charset/structural normalization was established, the formatter was expanded
to the first deliberately small complete-event batch:

```bash
python3 tools/import_android_text.py --only dialogue-format-batch1 \
  --rom "Secret of Mana (USA).sfc"
python3 tools/import_android_text.py --only dialogue-format-batch1 \
  --rom "Secret of Mana (USA).sfc" --check
```

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

After runtime validation of component 06's option-start and terminal-boundary synchronization,
component 08 may preserve a long localized choice label by moving only a **later**
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

The current corpus is **521 simulator-clean events**, **520 complete + 1 PARTIEL**, with
**1,122 visible semantic IDs / 1,179 JSON entries**. `$0278` is the sole PARTIEL event because
its two SNES-only controller carriers are staged for manual translation; `$0331` is complete
through the reviewed parameterized Android-ID-110 inn template. Newly admitted choice events
remain runtime-unvalidated individually until ordinary playthrough review.
