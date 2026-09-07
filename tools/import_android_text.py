#!/usr/bin/env python3
"""Import or analyze French translations from original Android text resources.

The Android ``scrtxt`` reader is generic, but dialogue generation remains limited
to already-established high-confidence SNES/Android mappings. The authoritative
dialogue output is ``dialogue-format-mass``, which formats complete events and
filters them through the independent simulator. Focused pilot/batch modes remain
available only to reproduce earlier runtime-validated checkpoints.
"""
from __future__ import annotations

import argparse
from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
import unicodedata

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shared.intro_event_text import load_document as load_intro_source  # noqa: E402
from shared.dialogue_translation import (  # noqa: E402
    DIALOGUE_PAGE_LINES,
    DIALOGUE_WRAP_CHARS,
    DIALOGUE_WRAP_PIXELS,
    format_mapping as format_dialogue_mapping,
    format_mapping_across_existing_wait_boundaries,
    format_mapping_across_existing_timed_wait_boundary,
    format_mapping_across_existing_action_boundary,
    event_text_index,
    normalize_android_french,
    _sentence_boundary_positions,
    _markup_width,
    semantic_wrap_markup,
    make_dialogue_advances,
    make_translation_document as make_dialogue_translation_document,
)
from shared.dialogue_codec import parse_event  # noqa: E402
from shared.translation_json import resolve_structural_omission_token_indexes  # noqa: E402
from shared.rom import validate_base_rom  # noqa: E402

DEFAULT_SCRTXT_EN = ROOT / "sources" / "android" / "scrtxt_en.bin"
DEFAULT_SCRTXT_FR = ROOT / "sources" / "android" / "scrtxt_fr.bin"
DEFAULT_INTRO_OUTPUT = ROOT / "translations" / "intro_event_french.json"
DEFAULT_DIALOGUE_PILOT_OUTPUT = ROOT / "mappings" / "android" / "dialogues_pilot.json"
DEFAULT_DIALOGUE_REVIEW_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round2.json"
DEFAULT_DIALOGUE_REVIEW_ROUND3_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round3.json"
DEFAULT_DIALOGUE_REVIEW_ROUND4_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round4.json"
DEFAULT_DIALOGUE_REVIEW_ROUND5_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round5.json"
DEFAULT_DIALOGUE_REVIEW_ROUND6_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round6.json"
DEFAULT_DIALOGUE_REVIEW_ROUND7_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round7.json"
DEFAULT_DIALOGUE_REVIEW_ROUND8_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round8.json"
DEFAULT_DIALOGUE_REVIEW_ROUND11_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round11.json"
DEFAULT_DIALOGUE_REVIEW_ROUND18_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round18.json"
DEFAULT_DIALOGUE_REVIEW_ROUND20_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round20.json"
DEFAULT_DIALOGUE_REVIEW_ROUND21_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round21.json"
DEFAULT_DIALOGUE_REVIEW_ROUND22_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round22.json"
DIALOGUE_SOURCE = ROOT / "assets" / "dialogues.json"
DIALOGUE_MANUAL_SUPPLEMENTS = ROOT / "translations" / "dialogues_manual_supplements.json"

INTRO_ANDROID_IDS = tuple(range(3445, 3453))
INTRO_TARGET_IDS = (
    "CA:0C0D",
    "CA:0C59",
    "CA:0CB3",
    "CA:0D0C",
    "CA:0D5C",
    "CA:0DAB",
    "CA:0DFF",
    "CA:0E21",
)

# These mappings are deliberately tiny. They are a research checkpoint, not a
# whole-game heuristic. Each accepted pair is independently the best lexical
# candidate and is also supported by an ordered local scene run.
DIALOGUE_PILOT_SCENES = (
    {
        "event_id": "0106",
        "label": "waterfall conversation",
        "pairs": (
            ("C9:2900", 3482),
            ("C9:294C", 3484),
            ("C9:299C", 3486),
            ("C9:29E8", 3488),
            ("C9:2A3D", 3490),
        ),
    },
    {
        "event_id": "002C",
        "label": "Sergo follow-up",
        "pairs": (
            ("C9:0CCF", 2675),
            ("C9:0D06", 2676),
        ),
    },
)

# Examples that must remain outside automatic import despite apparently strong
# text matches. They exercise duplicate and one-to-many failure modes.
DIALOGUE_PILOT_AMBIGUOUS = (
    {
        "snes_id": "C9:089B",
        "reason": "exact Android-English duplicate; text alone cannot choose between IDs 3314 and 3360",
        "candidate_android_ids": (3314, 3360),
    },
    {
        "snes_id": "C9:0C19",
        "reason": "exact Android-English duplicate in two distinct local blocks",
        "candidate_android_ids": (2667, 2793),
    },
    {
        "snes_id": "C9:0B03",
        "reason": "one SNES text block corresponds to two adjacent Android strings, and that pair is duplicated",
        "candidate_android_ids": (2449, 2450, 2463, 2464),
    },
)

# Candidate round 2. Unlike DIALOGUE_PILOT_SCENES, these units are not yet
# accepted mappings. They are deliberately richer review cases that exercise
# placeholder reconstruction and one-to-many/many-to-one/block alignment.
# ``snes_parts`` references canonical source text IDs and explicit dynamic-name
# placeholders; no translated prose is stored here.
DIALOGUE_REVIEW_ROUND2 = (
    {
        "event_id": "010C",
        "label": "Potos village - Mana Sword aftermath",
        "units": (
            (("C9:2CBD", ("player_name", 0), "C9:2CC5"), (42,), "many_snes_parts_to_one_android", "very_high_candidate", "PLAYER_NAME is explicit between two SNES text tokens."),
            (("C9:2D10",), (44,), "one_to_one", "very_high_candidate", "Distinct speaker and wording; ordered local block."),
            (("C9:2D37",), (45,), "one_to_one", "very_high_candidate", "Distinct speaker and wording; ordered local block."),
            (("C9:2D83",), (46,), "one_to_one", "very_high_candidate", "Distinct speaker and wording; ordered local block."),
            (("C9:2DE5", ("player_name", 0), "C9:2DF5"), (47,), "many_snes_parts_to_one_android", "very_high_candidate", "Android combines speaker prefix, PLAYER_NAME and following SNES text."),
            (("C9:2E2F",), (48, 49), "one_snes_to_many_android", "very_high_candidate", "One SNES text token contains two speaker lines that Android splits."),
            (("C9:2E70", "C9:2EBD"), (50,), "many_snes_to_one_android", "very_high_candidate", "Two SNES text tokens form one Android sentence."),
            (("C9:2ED2", "C9:2EEE"), (51,), "many_snes_to_one_android", "very_high_candidate", "Two SNES text tokens form one Android sentence."),
            (("C9:2F23",), (52,), "one_to_one", "very_high_candidate", "Ordered local block."),
            (("C9:2F5B",), (53,), "one_to_one", "very_high_candidate", "Ordered local block."),
            (("C9:2FB3",), (54,), "one_to_one", "very_high_candidate", "Ordered local block."),
            (("C9:3003",), (56,), "one_to_one", "very_high_candidate", "Ordered local block; Android 55 is an empty localization slot."),
            (((("player_name", 0)), "C9:306A"), (58, 59), "one_snes_with_placeholder_to_many_android", "very_high_candidate", "SNES embeds two speakers in one text token after PLAYER_NAME; Android splits them."),
            (("C9:30A8",), (61,), "one_to_one", "manual_review_semantic", "English is an exact match, but French slot 61 ('Reste là !') is not a literal/obvious translation; verify scene semantics."),
            ((("player_name", 0), "C9:3104"), (62,), "placeholder_plus_snes_to_one_android", "very_high_candidate", "Android omits the preceding standalone SNES 'ELLIOTT:You!' fragment; this unit covers only the player line."),
            (("C9:311F",), (63,), "one_to_one", "very_high_candidate", "Distinct earthquake line."),
            (("C9:3162",), (65,), "one_to_one", "very_high_candidate", "Distinct scream; Android 64 is empty."),
            (("C9:317D", "C9:319E"), (117,), "many_snes_to_one_android", "very_high_candidate", "Android merges the two SNES monster-warning text tokens."),
            (("C9:31D4",), (119,), "one_to_one", "very_high_candidate", "Distinct tutorial line; Android 120 is an empty localization slot."),
        ),
    },
    {
        "event_id": "00B3",
        "label": "Gold City - Light Palace / tower key NPC",
        "units": (
            (("C9:16DD",), (2479,), "one_to_one", "very_high_candidate", "Three-line NPC speech begins an exact ordered run."),
            (("C9:171C",), (2480,), "one_to_one", "very_high_candidate", "Second entry of the same ordered NPC run."),
            (("C9:1767",), (2481,), "one_to_one", "very_high_candidate", "Third entry of the same ordered NPC run."),
        ),
    },
    {
        "event_id": "0138",
        "label": "Luka - Undine directions",
        "units": (
            (("C9:3EB0", "C9:3EFC", "C9:3F48"), (869, 870, 871), "block_redistribution", "block_candidate", "English aligns 1:1 in order, but French redistributes the same scene content across the three slots; validate as a block, not per ID."),
        ),
    },
)


# Round 6 records high-confidence structural correspondences discovered while
# auditing partial events. These are not lexical guesses: each unit is anchored
# by an ordered Android-English scene block and/or already accepted adjacent
# choice options. Android may reattribute a reaction speaker or split a SNES
# prompt + options across separate localization records.
DIALOGUE_REVIEW_ROUND6 = (
    {
        "event_id": "0083",
        "label": "Geshtar short speaker-labelled reaction",
        "units": (
            (("C9:13BF",), (927,), "speaker_label_alignment", "very_high_structural", "Exact Geshtar: Idiot! Android line immediately precedes already accepted Android 928 in the same trapped-player exchange."),
        ),
    },
    {
        "event_id": "0187",
        "label": "Girl warning reattributed to PLAYER_NAME",
        "units": (
            (("C9:5B12",), (359,), "speaker_reattribution", "very_high_structural", "SNES Girl: Look out! is the exact Android Look out! line; Android represents the girl with PLAYER_NAME after the naming sequence."),
        ),
    },
    {
        "event_id": "024B",
        "label": "Repeated moogle reaction triplet",
        "units": (
            (("C9:9EC0",), (1229,), "speaker_label_alignment", "very_high_structural", "Android repeats the same Moogle / laughing / crying triplet several times; 1229 begins one exact triplet and the following two SNES fragments already use the identical localized reactions."),
        ),
    },
    {
        "event_id": "02EE",
        "label": "Tiny sprite speaker-labelled exchange",
        "units": (
            (("C9:C830",), (2557,), "speaker_label_alignment", "very_high_structural", "Exact Girl: A tiny little sprite! line immediately precedes already accepted Android 2558 in the same two-line exchange."),
        ),
    },
    {
        "event_id": "04A1",
        "label": "Fanha confrontation opening speaker redistribution",
        "units": (
            (("CA:17DA",), (2897,), "speaker_label_alignment", "very_high_structural", "Exact Fanha: You made it! opens the same contiguous Android confrontation whose 2899+ lines are already aligned."),
            ((("player_name", 0), "CA:17EF"), (2898,), "speaker_reattribution", "very_high_structural", "SNES continuation is preceded by PLAYER_NAME 0 and corresponds exactly to Android PLAYER_NAME asking the same question immediately between 2897 and already accepted 2899."),
        ),
    },
    {
        "event_id": "051D",
        "label": "Soldier trap reaction speaker-labelled line",
        "units": (
            (("CA:5C6C",), (2221,), "speaker_label_alignment", "very_high_structural", "Exact Soldier: Pipe down! Android line is bracketed by already accepted Android 2220 and 2222 in the same trap sequence."),
        ),
    },
    {
        "event_id": "0020",
        "label": "Joch running gag - Tasnica",
        "units": (
            (("C9:09A7",), (2460,), "speaker_reattribution", "very_high_structural", "SNES 'All:What luck...' corresponds to Android 'What luck...'; Android FR reattributes the reaction to PLAYER_NAME. Ordered immediately before the Tasnica answer."),
            (("C9:09B9",), (2461, 2462), "one_snes_to_many_android", "very_high_structural", "Android splits the same Tasnica answer into destination + direction records; ordered scene block is exact."),
        ),
    },
    {
        "event_id": "0021",
        "label": "Joch running gag - Palace of Darkness",
        "units": (
            (("C9:09F8",), (2452,), "speaker_reattribution", "very_high_structural", "SNES 'All:WHAT!?' corresponds to Android 'WHAT!?'; Android FR reattributes the reaction to PLAYER_NAME. Android 2453 is already the accepted immediately following answer."),
        ),
    },
    {
        "event_id": "0022",
        "label": "Joch running gag - Gold Isle",
        "units": (
            (("C9:0A44",), (2454,), "speaker_reattribution", "very_high_structural", "SNES 'All:Where is Joch?' corresponds to Android 'Where is Joch?'; Android FR reattributes the reaction to PLAYER_NAME."),
            (("C9:0A58",), (2455, 2456), "one_snes_to_many_android", "very_high_structural", "Android splits the same Gold Isle answer into destination + direction records in the ordered Joch scene."),
        ),
    },
    {
        "event_id": "0023",
        "label": "Joch running gag - Moon Palace",
        "units": (
            (("C9:0A8E",), (2457,), "speaker_reattribution", "very_high_structural", "SNES 'All:Surprise...' corresponds to Android 'Surprise...'; Android FR reattributes the reaction to PLAYER_NAME. Android 2458/2459 are already the accepted following answer."),
        ),
    },
    {
        "event_id": "0050",
        "label": "Neko save prompt split from Yes/No",
        "units": (
            (("C9:10A5",), (198,), "choice_prompt_split", "very_high_structural", "Android 198/199/200 is the Save your game?/Yes/No triplet bracketed by the already aligned Neko stay block 194-196 and shop block 201-203."),
        ),
    },
    {
        "event_id": "0065",
        "label": "Neko shop prompt split from Buy/Sell",
        "units": (
            (("C9:1236",), (201,), "choice_prompt_split", "very_high_structural", "Android 201/202/203 is the contiguous Purrrfectly.../Buy/Sell triplet; option 202 is already accepted for this SNES choice."),
        ),
    },
    {
        "event_id": "0099",
        "label": "Neko initial shop question split from choice",
        "units": (
            (("C9:14FE",), (188,), "choice_prompt_split", "very_high_structural", "Android 188/189/190 is the contiguous Welcome/Need anything?/Whatcha got?/Not really choice block; option 190 is already accepted in this SNES event."),
            (("C9:1512",), (189,), "choice_option_split", "very_high_structural", "Exact Whatcha got? option immediately precedes already accepted Android 190 Not really."),
        ),
    },
    {
        "event_id": "00DF",
        "label": "Cannon Travel Water Palace/Pandora choice",
        "units": (
            (("C9:1DCF",), (420,), "choice_prompt_split", "very_high_structural", "Android 420/421/422 is the contiguous 50-GP prompt / Water Palace / Pandora block; Pandora 422 is already accepted for this event."),
            (("C9:1DED",), (421,), "choice_option_split", "very_high_structural", "Water Palace is the option immediately preceding already accepted Pandora 422 in the same Android block."),
        ),
    },
    {
        "event_id": "00E0",
        "label": "Cannon Travel Matango/Kakkara choice",
        "units": (
            (("C9:1E14",), (1773,), "choice_prompt_split", "very_high_structural", "Android 1773/1774/1775 is the contiguous 50-GP prompt / Matango / Kakkara block; Kakkara 1775 is already accepted for this event."),
            (("C9:1E3D",), (1774,), "choice_option_split", "very_high_structural", "Matango is the option immediately preceding already accepted Kakkara 1775 in the same Android block."),
        ),
    },
    {
        "event_id": "00DC",
        "label": "Pandora lodging Nope option split",
        "units": (
            (("C9:1DB6",), (271,), "choice_option_split", "very_high_structural", "Android 267/269/270/271 is the same ordered lodging exchange; Android 271 is the missing Nope option immediately after the already accepted Phew, okay option 270."),
        ),
    },
    {
        "event_id": "00E1",
        "label": "Cannon Travel Matango/Ice Country split",
        "units": (
            (("C9:1E5F",), (1653,), "choice_prompt_split", "very_high_structural", "Android 1653-1656 is the Cannon Travel prompt followed by Matango, Ice Country and Empire; this SNES state exposes Matango/Ice Country."),
            (("C9:1E98",), (1655,), "choice_option_split", "very_high_structural", "Ice Country is the Android option adjacent to Matango 1654 in the same Cannon Travel block."),
        ),
    },
    {
        "event_id": "00E3",
        "label": "Cannon Travel numbered destination list split",
        "units": (
            (("C9:1F03",), (1654, 1655, 1656), "choice_destination_list", "very_high_structural", "SNES concatenates the three destination labels into a numbered list; Android 1654/1655/1656 stores Matango, Ice Country and The Empire as three adjacent localization records."),
        ),
    },
    {
        "event_id": "01EE",
        "label": "Elinee send-outside prompt split from Yes/No",
        "units": (
            (("C9:88F7",), (763,), "choice_prompt_split", "very_high_structural", "Android 763/764/765 is the contiguous send-outside prompt / Yes / No block."),
        ),
    },
    {
        "event_id": "02A7",
        "label": "Tasnica rescue-team leaving choice",
        "units": (
            (("C9:B580",), (1579, 1580), "choice_prompt_split", "very_high_structural", "Android splits the two SNES prompt sentences into 1579/1580, immediately followed by Yes/No 1581/1582."),
        ),
    },
    {
        "event_id": "05B0",
        "label": "Eight-way numeric choice - missing six",
        "units": (
            (("CA:77FF",), (1884,), "choice_option_split", "very_high_structural", "Android 1879-1886 is the contiguous 1..8 option run; SNES options 1-5 and 7-8 were already aligned to the surrounding IDs."),
        ),
    },
    {
        "event_id": "066B",
        "label": "Be gone / Well? prompt split from Yes/No",
        "units": (
            (("CA:8A79",), (1845,), "choice_prompt_split", "very_high_structural", "Android 1845/1846/1847/1848 is the contiguous Be gone!/Well?/Yes/No block."),
            (("CA:8A8A",), (1846,), "choice_prompt_split", "very_high_structural", "Android Well? immediately precedes the Yes/No pair in the same block."),
        ),
    },
)


# Round 20 follows Cannon Travel's destination/branch structure instead of lexical similarity.
DIALOGUE_REVIEW_ROUND20 = (
    {"event_id":"00CD","label":"Cannon Travel Upper Land response","units":((("C9:1A8A",),(163,),"cannon_response_prefix","very_high_structural","Android 163 begins with the exact Upper Land response and appends the shared cannon-boarding instruction stored by SNES in event $00FC."),)},
    {"event_id":"00D1","label":"Cannon Travel Water Palace / Upper Land choice","units":((("C9:1BDE",),(155,),"choice_prompt_split","very_high_structural","The SNES choice branches to $00FD (Water Palace) and $00CD (Upper Land); Android 155 precedes destination IDs 156/157/158 in the same Cannon Travel block."),(("C9:1BFD",),(156,),"choice_option_split","very_high_structural","Water Palace is Android 156 in the same destination block."),(("C9:1C0A",),(158,),"choice_option_split","very_high_structural","Upper Land is Android 158 in the same block; this SNES state omits the intermediate Gaia's Navel option."))},
    {"event_id":"00E6","label":"Cannon Travel Kakkara return response","units":((("C9:1F92",),(1924,),"cannon_response_prefix","very_high_structural","Android 1924 begins with the same heading-back response; SNES then calls shared event $00FC."),)},
    {"event_id":"00E7","label":"Cannon Travel Matango response","units":((("C9:1FD3",),(1657,),"cannon_response_prefix","very_high_structural","$00E1 branches to $00E7 for Matango; Android 1657 follows option 1654."),)},
    {"event_id":"00E8","label":"Cannon Travel Ice Country response","units":((("C9:2000",),(1659,),"cannon_response_prefix","very_high_structural","$00E1 branches to $00E8 for Ice Country; Android 1659 is the matching response."),)},
    {"event_id":"00E9","label":"Cannon Travel Empire response","units":((("C9:203E",),(1661,),"cannon_response_prefix","very_high_structural","The three-way $00E3 choice routes its third selection to $00E9; Android 1661 follows Empire option 1656."),)},
    {"event_id":"00EA","label":"Cannon Travel Matango response","units":((("C9:207F",),(1776,),"cannon_response_prefix","very_high_structural","$00E0 branches to $00EA for Matango; Android 1776 follows option 1774."),)},
    {"event_id":"00EB","label":"Cannon Travel Kakkara response","units":((("C9:20B8",),(1779,),"cannon_response_prefix","very_high_structural","$00E0 branches to $00EB for Kakkara; Android 1779 is the desert response in that scene."),)},
    {"event_id":"00EC","label":"Cannon Travel Kakkara response","units":((("C9:20F7",),(1329,),"cannon_response_prefix","very_high_structural","$00D0 branches to $00EC for Kakkara; Android 1329 follows Kakkara option 1327."),)},
    {"event_id":"00ED","label":"Cannon Travel Ice Country response","units":((("C9:2146",),(1332,),"cannon_response_prefix","very_high_structural","$00D0 branches to $00ED for Ice Country; Android 1332 is the matching response."),)},
    {"event_id":"00EF","label":"Cannon Travel Potos response","units":((("C9:21A9",),(1257,),"cannon_response_prefix","very_high_structural","$00CF branches to $00EF for Potos; Android 1257 follows Potos option 1255."),)},
    {"event_id":"00F0","label":"Cannon Travel Gaia's Navel response","units":((("C9:21D7",),(1259,),"cannon_response_prefix","very_high_structural","$00CF branches to $00F0 for Gaia's Navel; Android 1259 is the corresponding response."),)},
    {"event_id":"00F2","label":"Cannon Travel retry Kakkara response","units":((("C9:2220",),(1330,),"cannon_response_prefix","very_high_structural","Android 1330 expands the exact SNES retry response and shares the boarding suffix."),)},
    {"event_id":"00F4","label":"Cannon Travel Water Palace response","units":((("C9:229B",),(423,),"cannon_response_prefix","very_high_structural","$00DF branches to $00F4 for Water Palace; Android 423 follows option 421."),)},
    {"event_id":"00F5","label":"Cannon Travel Pandora response","units":((("C9:22D6",),(425,),"cannon_response_prefix","very_high_structural","$00DF branches to $00F5 for Pandora; Android 425 follows option 422."),)},
    {"event_id":"00FA","label":"Cannon Travel initial boarding response","units":((("C9:2390",),(152,),"cannon_response_prefix","very_high_structural","Android 152 begins with the exact warning and appends the shared boarding instruction."),)},
    {"event_id":"00FC","label":"Cannon Travel shared boarding instruction","units":((("C9:246D",),(159,),"cannon_common_boarding_suffix","very_high_structural","SNES $00FC contains only 'Just slide into the cannon!'; Android folds that same suffix into destination responses. Android 159 is one representative proven block."),)},
    {"event_id":"00FD","label":"Cannon Travel Water Palace response","units":((("C9:2502",),(159,),"cannon_response_prefix","very_high_structural","$00CE branches to $00FD for Water Palace; Android 159 follows option 156."),)},
    {"event_id":"00FE","label":"Cannon Travel Gaia's Navel response","units":((("C9:2541",),(161,),"cannon_response_prefix","very_high_structural","$00CE branches to $00FE for Gaia's Navel; Android 161 follows option 157."),)},
    {"event_id":"01D6","label":"Dwarf elder donation prompt split before Yes/No","units":((("C9:7C5B",),(535,536),"choice_prompt_split","very_high_structural","Android 535/536 are the contiguous appeal/donation prompt immediately followed by Yes/No 537/538."),(("C9:7C74",),(537,),"choice_option_split","very_high_structural","Yes is Android 537 immediately after the donation prompt."),(("C9:7C79",),(538,),"choice_option_split","very_high_structural","No is Android 538 in the same block."))},
    {"event_id":"01EE","label":"Elinee send-outside Yes/No anchors","units":((("C9:891D",),(764,),"choice_option_split","very_high_structural","Prompt 763 is already accepted; Yes 764 follows immediately."),(("C9:8922",),(765,),"choice_option_split","very_high_structural","No 765 follows Yes 764 in the same block."))},
)


# Round 21 resolves three conservative PARTIEL resegmentation cases. Android
# English remains the identity layer; the formatter may only redistribute the
# exact Android French localization around stock SNES structural carriers.
DIALOGUE_REVIEW_ROUND21 = (
    {
        "event_id": "0167",
        "label": "Phanna sacrifice opening resegmented around WAIT and PLAYER_NAME",
        "units": (
            (("C9:4C65", ("player_name", 1), "C9:4C73"), (1058, 1059), "wait_player_resegmentation", "very_high_structural", "Android 1058/1059 is the contiguous opening immediately before accepted 1060. SNES stores the same turn as Phanna's ellipsis, WAIT $00, PLAYER_NAME(1), then the continuation; preserve both commands and redistribute only the official Android French around the existing name carrier."),
        ),
    },
    {
        "event_id": "01E5",
        "label": "Girl rejoins party placeholder join",
        "units": (
            ((("player_name", 1), "C9:82B9"), (668,), "placeholder_join", "very_high_structural", "Android 668 '%S(1,0) joined!' is exactly between accepted 666/667 and the following scene. SNES already emits PLAYER_NAME(1) immediately before the text carrier."),
        ),
    },
    {
        "event_id": "0609",
        "label": "Haunted Forest / Gaia's Navel merged Android direction row",
        "units": (
            (("CA:8690", "CA:86A5"), (415,), "paired_direction_labels", "very_high_structural", "Android 415 merges the two SNES destination labels into one ordered row with ↑/↓ markers. SNES keeps those markers as stock D1/D2 glyphs around a newline-only carrier, so only the two official French labels are redistributed."),
        ),
    },
)

# Round 22 resolves three more PARTIEL cases where Android English proves a
# branch/staging resegmentation. French text is taken only from the original
# Android localization; no manual wording is introduced.
DIALOGUE_REVIEW_ROUND22 = (
    {
        "event_id": "01DD",
        "label": "Sprite female-name branch resegmentation",
        "units": (
            (("C9:806F",), (616, 619), "branch_shared_prefix_female_address", "very_high_structural", "Android EN 616 supplies the shared Sprite warning and 619 is the immediately following female-address branch before exact girl response 620. Android FR deliberately redistributes the shared prefix across 616 and the female address into 619; combine only those official slots for the SNES female branch."),
            ((("player_name", 1), "C9:80A1", ("player_name", 1), "C9:80A9"), (620,), "double_player_name_response", "very_high_structural", "Android 620 is the exact girl-name correction between female-address branch 619 and already accepted 621. SNES stores the same response around two existing PLAYER_NAME(1) commands."),
        ),
    },
    {
        "event_id": "02AE",
        "label": "Amar Faerie Walnut timed-WAIT resegmentation",
        "units": (
            (("C9:B691", "C9:B6B9"), (1630,), "timed_wait10_resegmentation", "very_high_structural", "Android EN 1630 merges the two consecutive SNES Amar fragments around the stock WAIT $10 ('Faerie walnut... Huh...? You mean...'), immediately before exact 1631/1632. Keep WAIT $10 byte-for-byte and redistribute only complete sentences from official Android FR 1630 across its two existing text carriers."),
        ),
    },
    {
        "event_id": "07FE",
        "label": "Ending wake-up staging redistribution",
        "units": (
            (("CA:982A", ("player_name", 0), "CA:982E"), (3399, 3401, 3406), "ending_wakeup_staging", "very_high_structural", "Android EN redistributes the same ending wake-up turn over 3399 (%S(0,0)...), 3401 (wake up...) and 3406 (You must not fall now...), immediately before already accepted 3409. Android FR redistributes those slots again; preserve the stock SNES PLAYER_NAME(0) and use only the official localized pieces."),
        ),
    },
)


# Round 3 extends the validated method to two long, highly coherent scene runs
# plus one localization-heavy Resistance scene. English identity remains the
# primary acceptance signal; French wording may be adapted or redistributed.
DIALOGUE_REVIEW_ROUND3 = (
    {
        "event_id": "04E0",
        "label": "Jema - Pure Land directions after the Fortress revival",
        "units": (
            (("CA:288C", ("player_name", 0), "CA:2893"), (2654,), "placeholder_join", "very_high_candidate", "Speaker prefix + PLAYER_NAME + continuation match one Android anchor."),
            (("CA:28B6",), (2655,), "one_to_one", "very_high_candidate", "Unique exact English match in a long ordered run."),
            (("CA:28E7",), (2656,), "one_to_one", "very_high_candidate", "Unique exact English match in a long ordered run."),
            (("CA:2932",), (2657,), "one_to_one", "very_high_candidate", "Unique exact English match in a long ordered run."),
            (("CA:297D",), (2658,), "one_to_one", "very_high_candidate", "Unique exact English match in a long ordered run."),
            (("CA:29C9",), (2659,), "one_to_one", "very_high_candidate", "Unique exact English match in a long ordered run."),
            (("CA:29FE",), (2660,), "one_to_one", "very_high_candidate", "Unique exact English match in a long ordered run."),
            (("CA:2A41",), (2661,), "one_to_one", "very_high_candidate", "Unique exact English match in a long ordered run."),
            (("CA:2A92",), (2662,), "one_to_one", "very_high_candidate", "Unique exact English match in a long ordered run."),
            (("CA:2AE5",), (2663,), "one_to_one", "very_high_candidate", "Unique exact English match in a long ordered run."),
            ((("player_name", 0), "CA:2B31"), (2664,), "placeholder_join", "very_high_candidate", "PLAYER_NAME + source text match the final Android anchor of the run."),
        ),
    },
    {
        "event_id": "066D",
        "label": "Santa Claus / Frost Gigas aftermath",
        "units": (
            ((("player_name", 0), "CA:8B0F"), (1851,), "placeholder_join", "very_high_candidate", "PLAYER_NAME + source text; Android 1852 is an empty localization slot."),
            (("CA:8B2C", "CA:8B4A", "CA:8B53"), (1853,), "many_snes_to_one_android", "very_high_candidate", "SNES splits Rudolph's line around an event action; Android keeps one speech string."),
            (("CA:8B69",), (1854,), "one_to_one", "very_high_candidate", "Unique exact English match in ordered local run."),
            (("CA:8BAE",), (1855,), "one_to_one", "very_high_candidate", "Unique exact English match in ordered local run."),
            (("CA:8BF7",), (1856,), "one_to_one", "very_high_candidate", "Unique exact English match in ordered local run."),
            (("CA:8C2F",), (1857,), "one_to_one", "very_high_candidate", "Unique exact English match in ordered local run."),
            (("CA:8C6A",), (1858,), "one_to_one", "very_high_candidate", "Unique exact English match in ordered local run."),
            (("CA:8CAC",), (1859,), "one_to_one", "very_high_candidate", "Unique exact English match in ordered local run."),
            (("CA:8CFC",), (1860,), "one_to_one", "very_high_candidate", "Unique exact English match in ordered local run."),
            (("CA:8D4B",), (1861,), "one_to_one", "very_high_candidate", "Unique exact English match in ordered local run."),
            (("CA:8D8A",), (1862,), "one_to_one", "very_high_candidate", "Unique exact English match in ordered local run."),
            (("CA:8DC0",), (1863,), "one_to_one", "very_high_candidate", "Unique exact English match in ordered local run."),
        ),
    },
    {
        "event_id": "0511",
        "label": "Resistance meeting before the Emperor truce",
        "units": (
            (("CA:59E1",), (1983,), "one_to_one", "very_high_candidate", "Unique exact English match at start of ordered scene run."),
            (("CA:59F8",), (1984,), "one_to_one", "very_high_candidate", "Unique exact English match."),
            (("CA:5A14",), (1985,), "one_to_one", "very_high_candidate", "Unique exact English match."),
            (("CA:5A2F",), (1986,), "one_to_one", "very_high_candidate", "Unique exact English match."),
            (("CA:5A7F",), (1987,), "one_to_one", "very_high_candidate", "Unique exact English match; Android 1988 adds dialogue absent from the SNES source before the next anchor."),
            (("CA:5AA7",), (1990,), "one_to_one", "very_high_candidate", "Exact English identity resumes after Android-only 1988 and empty 1989."),
            (("CA:5ADE",), (1991,), "one_to_one", "very_high_candidate", "Unique exact English match."),
            (("CA:5B11",), (1992,), "one_to_one", "very_high_candidate", "Unique exact English match."),
            (("CA:5B41", "CA:5B5A", "CA:5B5F", "CA:5B70"), (1993, 1994, 1995, 1996), "sequence_block_with_android_extra", "block_candidate", "SNES has three spoken statements plus a newline token; Android has four anchors because 1996 adds a Dyluck sentence absent from SNES. French redistributes the same local conversation across 1993-1996."),
            (("CA:5BA4",), (1998,), "one_to_one", "very_high_candidate", "Unique exact English match after the sequence block; 1999 is an empty localization slot."),
        ),
    },
)


# Round 7 continues the structural PARTIEL audit. It deliberately targets
# ordered Android-English gaps and prompt/choice blocks where neighboring
# accepted IDs prove identity. It also corrects two short-label lexical matches
# whose global exact wording pointed at the wrong Android scene.
DIALOGUE_REVIEW_ROUND7 = (
    {
        "event_id": "00CE",
        "label": "Cannon Travel Water Palace / Gaia's Navel choice",
        "units": (
            (("C9:1B18",), (156,), "choice_option_split", "very_high_structural", "Android 155/156/157 is the contiguous 50-GP prompt / Water Palace / Gaia's Navel block; prompt 155 is already accepted for this exact SNES event."),
            (("C9:1B25",), (157,), "choice_option_split", "very_high_structural", "Gaia's Navel immediately follows Water Palace inside the same Android block anchored by accepted prompt 155."),
        ),
    },
    {
        "event_id": "00CF",
        "label": "Cannon Travel Potos / Gaia's Navel choice",
        "units": (
            (("C9:1B60",), (1255,), "choice_option_split", "very_high_structural", "Android 1254/1255/1256 is the contiguous prompt / Potos Village / Gaia's Navel block; prompt 1254 and Gaia's Navel 1256 are already accepted in this exact event."),
        ),
    },
    {
        "event_id": "00D0",
        "label": "Cannon Travel Kakkara / Ice Country choice",
        "units": (
            (("C9:1B85",), (1326,), "choice_prompt_split", "very_high_structural", "Android 1326/1327/1328 is the contiguous 50-GP prompt / Kakkara Desert / Ice Country block and matches this SNES destination pair in order."),
            (("C9:1BB3",), (1327,), "choice_option_split", "very_high_structural", "Kakkara belongs to Android 1327 in this ordered Kakkara/Ice Country block; this replaces the earlier globally exact but scene-wrong Kakkara anchor."),
            (("C9:1BBC",), (1328,), "choice_option_split", "very_high_structural", "Ice Country immediately follows Kakkara in the same Android 1326-1328 choice block."),
        ),
    },
    {
        "event_id": "00E2",
        "label": "Cannon Travel Kakkara yes/no choice",
        "units": (
            (("C9:1EEC",), (1922,), "choice_option_split", "very_high_structural", "Android 1921/1922/1923 is the contiguous Kakkara 50-GP prompt / negative / affirmative choice block; prompt 1921 is already accepted for this event."),
            (("C9:1EF3",), (1923,), "choice_option_split", "very_high_structural", "The affirmative SNES option belongs to Android 1923 in the same prompt block; this replaces the earlier globally exact but scene-wrong Sure! match."),
        ),
    },
    {
        "event_id": "0127",
        "label": "Luka welcome line inside ordered Water Palace exchange",
        "units": (
            (("C9:3B05",), (916,), "speaker_label_alignment", "very_high_structural", "Exact Luka: Ha ha ha...welcome! fills the only Android-English gap between already accepted 915 and 917 in the same exchange."),
        ),
    },
    {
        "event_id": "0295",
        "label": "Guard reaction before ordered ship-food exchange",
        "units": (
            (("C9:AF19",), (1516,), "speaker_label_alignment", "very_high_structural", "Exact Guard: Stop lollygagging! immediately precedes already accepted Android 1517 and 1518 in the same ship scene."),
        ),
    },
    {
        "event_id": "029C",
        "label": "Morie / Meria confrontation ordered gaps",
        "units": (
            (("C9:B0E3",), (1545,), "speaker_label_alignment", "very_high_structural", "Exact Morie: Massage my back! immediately precedes the accepted 1546-1548 exchange."),
            (("C9:B1B0",), (1552,), "speaker_reattribution", "very_high_structural", "SNES unlabeled Harrumph follows Morie's line and corresponds to Android PLAYER_NAME 1 Harrumph at 1552, bracketed by accepted 1551 and 1553."),
            (("C9:B330",), (1564,), "one_snes_to_one_android_expanded", "very_high_structural", "SNES Soldier: No way! We're with Morie! is the same ordered line as Android 1564, whose English adds the staged departure immediately after accepted 1563."),
        ),
    },
    {
        "event_id": "0318",
        "label": "Neko save-service line before Save/Buy/Sell options",
        "units": (
            (("C9:CD95",), (2377,), "choice_prompt_split", "very_high_structural", "Android 2376-2380 is the contiguous Neko greeting / save-service / Save / Buy / Sell block; 2376, 2378 and 2379 are already accepted in this exact event."),
        ),
    },
    {
        "event_id": "036D",
        "label": "Scorpion boss send-off before robot overload",
        "units": (
            (("C9:D43A",), (1156,), "speaker_label_alignment", "very_high_structural", "Exact Boss send-off line precedes Android Robot 1157 and the already accepted overload exchange 1159-1161 in the same scene."),
        ),
    },
    {
        "event_id": "03AA",
        "label": "Krissie resistance introduction ordered gaps",
        "units": (
            (("C9:E13E",), (2013,), "speaker_label_alignment", "very_high_structural", "Exact Krissie opening question immediately precedes already accepted Android 2014-2019."),
            (("C9:E234",), (2020,), "speaker_label_alignment", "very_high_structural", "Exact Krissie: You KNOW Dyluck? fills the only gap between accepted 2019 and 2021 in the same conversation."),
        ),
    },
    {
        "event_id": "0558",
        "label": "Girl awakening line in Thanatos scene",
        "units": (
            (("CA:65E8",), (2186,), "speaker_reattribution", "very_high_structural", "SNES unlabeled Where am I...? corresponds exactly to Android PLAYER_NAME 1 at 2186, between accepted Thanatos 2184 and PLAYER_NAME 0 line 2188."),
        ),
    },
)


# Round 8 focuses on user-reviewed PARTIEL events. Every mapping below is
# supported by the ordered Android-English scene around already accepted
# anchors; no French-only identity inference is used.
DIALOGUE_REVIEW_ROUND8 = (
    {
        "event_id": "00AA",
        "label": "Picard lighthouse ordered continuation",
        "units": (
            (("C9:1547",), (2303,), "one_snes_to_one_android_expanded", "very_high_structural", "Android 2303-2306 is one contiguous lighthouse speech run. 2303 expands the SNES caretaker introduction and immediately precedes accepted 2304/2305."),
            (("C9:15FE",), (2306,), "one_snes_to_one_android_expanded", "very_high_structural", "Android 2306 begins with the exact SNES ancients-power sentence and directly follows accepted 2305 in the same lighthouse run."),
        ),
    },
    {
        "event_id": "0106",
        "label": "Waterfall fragmented opening and falling scream",
        "units": (
            (("C9:2ADB",), (3494,), "one_to_one", "very_high_structural", "Exact final falling scream at Android 3494, immediately after already accepted 3492/3493."),
        ),
    },
    {
        "event_id": "0135",
        "label": "Jema Mana study continuation",
        "units": (
            (("C9:3D64",), (887,), "one_snes_to_one_android_expanded", "very_high_structural", "Android 886/887 is the contiguous Jema/Luka-followers speech. 887 starts with the complete SNES sentence and adds the Android continuation."),
        ),
    },
    {
        "event_id": "0147",
        "label": "Pandora gate introduction",
        "units": (
            (("C9:45FD",), (237,), "one_snes_to_one_android_expanded", "very_high_structural", "Android 237-240 is the exact ordered gate-guard run. 237 expands 'This is Pandora' to 'This is the Kingdom of Pandora' immediately before accepted 238-240."),
        ),
    },
    {
        "event_id": "0157",
        "label": "Pandora ruins NPC continuation",
        "units": (
            (("C9:4A31",), (301,), "one_snes_to_one_android_expanded", "very_high_structural", "Android 300/301 is the same two-part NPC speech; 301 closely matches the missing second SNES block and directly follows accepted 300."),
        ),
    },
    {
        "event_id": "0159",
        "label": "Phanna and Dyluck exchange ordered gap",
        "units": (
            (("C9:4AFE",), (305,), "one_to_one", "very_high_structural", "Exact Android-English line 305 fills the only gap between accepted 304 and 306 in the same conversation."),
        ),
    },
    {
        "event_id": "0167",
        "label": "Phanna sacrifice scene opening",
        "units": (
            (("C9:4C65",), (1058,), "speaker_label_alignment", "very_high_structural", "Android 1058 is the exact Phanna ellipsis and immediately precedes Android 1059 and the already aligned 1060-1068 scene. Android 1059 is semantically related to the following SNES line but remains layout-deferred because it resegments around PLAYER_NAME(1)."),
        ),
    },
    {
        "event_id": "0181",
        "label": "Pandora king nightmare line",
        "units": (
            (("C9:5710",), (388,), "one_snes_to_one_android_expanded", "very_high_structural", "Android 388 contains the complete SNES king nightmare/zombie sentence plus an Empire-warning expansion; it belongs to the same ordered court scene as 390-394."),
        ),
    },
    {
        "event_id": "0193",
        "label": "Nobleman breaks off arrangement",
        "units": (
            (("C9:5F2E",), (369,), "one_snes_to_one_android_expanded", "very_high_structural", "Android 369 is the same cancellation/indignation line and immediately follows accepted 368 in the Elman scene."),
        ),
    },
    {
        "event_id": "01A5",
        "label": "Pandora king victory opening",
        "units": (
            (("C9:6366", ("player_name", 0), "C9:6374"), (403,), "placeholder_join", "very_high_structural", "Android 403 combines the two SNES text fragments around PLAYER_NAME(0): 'You did it, %S(0,0)!' and the kingdom returning to normal."),
        ),
    },
    {
        "event_id": "01B2",
        "label": "Watts splendid sword continuation",
        "units": (
            (("C9:66DB",), (566,), "one_snes_to_one_android_expanded", "very_high_structural", "Android 566 contains the complete missing hope-to-forge-a-sword sentence and directly follows accepted 565."),
        ),
    },
    {
        "event_id": "01C6",
        "label": "Girl party-separation notice",
        "units": (
            (("C9:71AC", ("player_name", 1), "C9:71C1"), (440,), "adapted_system_notice", "very_high_structural", "SNES 'Separated from %S(1,0).' and Android '%S(1,0) leaves.' are the same party-removal event; Android 440 immediately follows accepted departure line 439."),
        ),
    },
    {
        "event_id": "01D3",
        "label": "Sprite naming banter opening",
        "units": (
            (("C9:7944",), (616, 617), "one_snes_to_many_android_expanded", "very_high_structural", "Android 616/617 is the expanded sprite address ending in 'Brother!' immediately before accepted Android 618, which answers that address with the player reply at Android 618."),
        ),
    },
)


# Round 4 deliberately maximizes structural variety while keeping strong
# Android-English identity. It covers elemental acquisition, multiple dynamic
# party-name placeholders, dialogue split by event actions, French continuation
# slots, and a late-game scene whose Android IDs jump between pre/post-battle
# dialogue while preserving narrative order.
DIALOGUE_REVIEW_ROUND4 = (
    {
        "event_id": "022E",
        "label": "Gnome joins the party after Tropicallo",
        "units": (
            (("C9:98F3",), (1034,), "one_to_one", "very_high_candidate", "Distinct Gnome introduction; exact ordered local anchor."),
            (("C9:992A",), (1035,), "one_to_one", "very_high_candidate", "Exact ordered local anchor."),
            ((("player_name", 2), "C9:995B"), (1036,), "placeholder_join", "very_high_candidate", "SNES PLAYER_NAME(2) + text equals the Android speaker line."),
            (("C9:998A", ("player_name", 0), "C9:99B7"), (1037,), "placeholder_join", "very_high_candidate", "SNES splits the sentence around PLAYER_NAME(0); Android stores one anchor."),
            (("C9:99BB",), (1038,), "one_to_one", "very_high_candidate", "Exact ordered local anchor."),
            ((("player_name", 0), "C9:99E9"), (1039,), "placeholder_join", "very_high_candidate", "SNES PLAYER_NAME(0) + text equals the Android speaker line."),
            (("C9:9A10",), (1040,), "one_to_one", "very_high_candidate", "Exact ordered local anchor."),
            (("C9:9A45",), (1041,), "one_to_one", "very_high_candidate", "Exact ordered local anchor; next Android slot is empty."),
            (("C9:9A69",), (1043,), "one_to_one", "very_high_candidate", "Exact ordered local anchor after event animation."),
            ((("player_name", 1), "C9:9A9A", "C9:9AA9"), (1044,), "placeholder_plus_event_split", "very_high_candidate", "One Android line spans two SNES text tokens separated by character-action commands."),
            ((("player_name", 2), "C9:9ACA"), (1045,), "placeholder_join", "very_high_candidate", "SNES PLAYER_NAME(2) + text equals the Android speaker line."),
            (("C9:9AE8",), (1046,), "one_to_one", "very_high_candidate", "Exact final anchor of the scene run."),
        ),
    },
    {
        "event_id": "0581",
        "label": "Undine grants magic and the Pole Dart",
        "units": (
            (("CA:6BD6",), (956,), "one_to_one", "very_high_candidate", "Same unique Undine introduction; Android expands 'Undine' to 'water elemental'."),
            (("CA:6C16",), (957,), "one_to_one", "very_high_candidate", "Unique ordered magic-introduction line."),
            (("CA:6C41", ("player_name", 1), "CA:6C44"), (958,), "placeholder_join", "very_high_candidate", "SNES layout token + PLAYER_NAME(1) + continuation form one Android anchor."),
            (("CA:6C81", ("player_name", 2), "CA:6C84"), (960,), "placeholder_join", "very_high_candidate", "SNES layout token + PLAYER_NAME(2) + continuation form one Android anchor."),
            ((("player_name", 0), "CA:6CC7"), (962,), "placeholder_join", "very_high_candidate", "Exact player-name question in ordered run."),
            (("CA:6CD2",), (963,), "one_to_one", "very_high_candidate", "Unique Mana Sword explanation anchor."),
            (("CA:6D1E",), (964,), "one_to_one", "very_high_candidate", "Unique Ice Saber explanation anchor; French localization rewrites the explanation."),
            (("CA:6D6B", ("player_name", 1), "CA:6D6F"), (965,), "placeholder_join_with_french_continuation", "very_high_candidate", "Android English anchor 965 is followed by empty 966, which French uses to continue the localized explanation."),
            (("CA:6DB3",), (967,), "one_to_one", "very_high_candidate", "Unique weapon-gift line."),
            (("CA:6DF9",), (968,), "one_to_one", "very_high_candidate", "Exact item-receipt text; preceding SNES newline/TEXT_X are layout commands, not semantic prose."),
            (("CA:6E19",), (969,), "one_to_one", "very_high_candidate", "Unique Undine farewell anchor."),
            (("CA:6E50",), (971,), "one_to_one", "very_high_candidate", "Exact power-acquisition notification; preceding SNES newline is layout-only."),
            ((("player_name", 2), "CA:6E79"), (972,), "placeholder_join", "very_high_candidate", "Exact player-name boast at the end of the scene."),
        ),
    },
    {
        "event_id": "04B3",
        "label": "Emperor trap and Sheex / Dark Stalker reveal",
        "units": (
            (("CA:1ECE",), (2681,), "one_to_one", "very_high_candidate", "Unique Emperor opening line."),
            (("CA:1F09",), (2682,), "one_to_one", "very_high_candidate", "Exact ordered ancient-continent line."),
            (("CA:1F57",), (2683,), "one_to_one", "very_high_candidate", "Exact ordered Mana Fortress line."),
            (("CA:1F97",), (2684,), "one_to_one", "very_high_candidate", "Exact ordered threat; Android underscore is a presentation marker."),
            (("CA:1FBC",), (2685,), "one_to_one", "very_high_candidate", "Exact short question in the same ordered run."),
            (("CA:1FE0",), (2686,), "one_to_one_with_french_continuation", "very_high_candidate", "English 2687-2688 are empty localization slots; French uses 2688 for extra Sheex detail."),
            ((("player_name", 0), "CA:2033"), (2689,), "placeholder_join", "very_high_candidate", "Exact player-name Dark Stalker reveal."),
            (("CA:2056",), (2690,), "one_to_one", "very_high_candidate", "Exact Sheex transformation challenge."),
            (("CA:208F",), (2723,), "one_to_one_with_french_continuation", "very_high_candidate", "Post-battle scene resumes at Android 2723; empty English 2724 carries extra French reaction text."),
            (("CA:20D3",), (2725,), "one_to_one", "very_high_candidate", "Unique underworld-contract line after the Android-ID jump."),
            (("CA:2128",), (2726,), "one_to_one", "very_high_candidate", "Same Mana Fortress motive; minor pronoun wording difference does not affect identity."),
            (("CA:2170",), (2727,), "one_to_one", "very_high_candidate", "Exact final threat of the ordered scene run."),
        ),
    },
)


# Round 5 is the final pre-automation stress test. It deliberately targets
# events whose strong lexical anchors are not globally monotonic in Android ID
# order. Four cases are explained by one SNES event spanning multiple Android
# subscene blocks; event $0204 contains a genuine local content reorder.
DIALOGUE_REVIEW_ROUND5 = (
    {
        "event_id": "0112",
        "label": "Mantis Ant rescue - isolated tutorial subscene",
        "units": (
            (("C9:3300",), (123,), "one_to_one_subscene", "very_high_candidate", "Exact unique rescue line. The enclosing SNES event later resets to Android ID 13 because it enters a different story subscene."),
        ),
    },
    {
        "event_id": "0112",
        "label": "Mana Sword explanation and Jema departure",
        "units": (
            (("C9:333D",), (13,), "one_to_one", "very_high_candidate", "Exact Elliott scream; starts a new Android-local block after the rescue tutorial line."),
            (("C9:3370",), (15,), "one_to_one_with_android_expansion", "very_high_candidate", "Distinct Mana Sword identification; Android adds a short concern sentence."),
            ((("player_name", 0), "C9:339F"), (16,), "placeholder_join", "very_high_candidate", "PLAYER_NAME + source fragment equals Android speaker line."),
            (("C9:33AC",), (17,), "one_to_one", "very_high_candidate", "Exact ordered lore line."),
            (("C9:33FB",), (18,), "one_to_one", "very_high_candidate", "Exact ordered lore line."),
            ((("player_name", 0), "C9:3450"), (19,), "placeholder_join", "very_high_candidate", "Exact player response after placeholder reconstruction."),
            (("C9:3465",), (20,), "one_to_one_minor_wording", "very_high_candidate", "Same distinctive sword-reenergizing sentence; Android changes the opening interjection."),
            (("C9:34B0",), (21,), "one_to_one", "very_high_candidate", "Exact ordered line."),
            ((("player_name", 0), "C9:34E5"), (22,), "duplicate_resolved_by_local_order", "very_high_candidate", "The same English question also exists at Android 832; the surrounding 15-24 block uniquely selects 22 here."),
            (("C9:34F9",), (23,), "one_to_one", "very_high_candidate", "Exact ordered destination line."),
            (("C9:3526",), (24,), "one_to_one_minor_wording", "very_high_candidate", "Two hundred is numeric on SNES and written out on Android; otherwise same sentence."),
            (("C9:3590", ("player_name", 0), "C9:359A"), (26,), "placeholder_join", "very_high_candidate", "SNES splits Timothy's line around PLAYER_NAME; Android stores one line."),
            (("C9:35C1", "C9:35F9"), (27,), "many_snes_to_one_android", "very_high_candidate", "Android merges Jema's introduction and Water Palace departure into one anchor."),
        ),
    },
    {
        "event_id": "0204",
        "label": "Water Palace Mana Seed ritual",
        "units": (
            (("C9:8EFF",), (839,), "one_to_one", "very_high_candidate", "Exact ritual instruction."),
            (("C9:8F73",), (842,), "one_to_one", "very_high_candidate", "Exact post-animation line; Android IDs 840-841 are non-prose/empty localization slots."),
            (("C9:8FA8",), (843,), "one_to_one", "very_high_candidate", "Exact seed-sealing line."),
            (("C9:8FE0",), (844,), "one_to_one", "very_high_candidate", "Exact Mana-power line. French redistributes nearby explanatory detail."),
        ),
    },
    {
        "event_id": "0204",
        "label": "Water Palace instruction genuinely relocated in Android",
        "units": (
            (("C9:9076",), (824,), "one_to_one_reordered", "very_high_candidate", "Exact unique English identity, but Android places this instruction before the ritual block (ID 824 versus 839-844) while SNES places it after. This is a genuine local reorder, not a fuzzy-match error."),
        ),
    },
    {
        "event_id": "036A",
        "label": "Scorpion Army boss aftermath",
        "units": (
            (("C9:D39D",), (1154,), "one_to_one", "very_high_candidate", "Exact Scorpion boss exit line."),
            (("C9:D3D3",), (1155,), "one_to_one_typo_normalization", "very_high_candidate", "SNES source has 'Recoverd'; Android corrects it to 'Recovered'."),
        ),
    },
    {
        "event_id": "036A",
        "label": "Water Palace follow-up after recovered seed",
        "units": (
            (("C9:D3EE",), (489,), "one_to_one_subscene_reset", "very_high_candidate", "Exact line after TEXT_CLOSE/TEXT_OPEN; Android stores this party follow-up in a different local block."),
        ),
    },
    {
        "event_id": "04E4",
        "label": "White dragon discovery",
        "units": (
            (("CA:3914",), (1448,), "one_to_one", "very_high_candidate", "Exact distinctive white-dragon line."),
            (("CA:3942",), (1449,), "one_to_one", "very_high_candidate", "Exact serpent/parents line."),
            ((("player_name", 1), "CA:3988"), (1451,), "placeholder_join", "very_high_candidate", "PLAYER_NAME(1) + source fragment equals Android line."),
            (("CA:39B2",), (1452,), "one_to_one", "very_high_candidate", "Exact Truffle suggestion; ends the discovery subscene."),
        ),
    },
    {
        "event_id": "04E4",
        "label": "Truffle raises and names Flammie",
        "units": (
            (("CA:3A05",), (1372,), "one_to_one_with_android_french_expansion", "very_high_candidate", "Exact Android-English identity; French expands the setup."),
            (("CA:3A42",), (1374, 1375), "one_snes_to_many_android", "very_high_candidate", "One SNES token contains Nobleman and Truffle lines that Android splits."),
            (("CA:3A76",), (1376,), "one_to_one", "very_high_candidate", "Exact ordered line."),
            (("CA:3AAD",), (1377,), "one_to_one", "very_high_candidate", "Exact Flammie naming question."),
            (("CA:3AE1",), (1378,), "choice_text", "very_high_candidate", "Same two choice labels; brackets/layout differ."),
            (("CA:3AF6", "CA:3B23"), (1379, 1380), "two_to_two_redistribution", "very_high_candidate", "SNES and Android split 'Hang on / I sound like an idiot / you'd agree...' at different boundaries; validate as one local block."),
            (("CA:3B5D",), (1381,), "one_to_one", "very_high_candidate", "Exact naming conclusion."),
            (("CA:3B91",), (1382,), "one_to_one", "very_high_candidate", "Exact Cannon Travel instruction; French combines some following Fire Palace detail."),
            (("CA:3BCC",), (1383,), "one_to_one", "very_high_candidate", "Exact Fire Palace destination line; French redistributes the instruction across 1382-1383."),
        ),
    },
    {
        "event_id": "04E8",
        "label": "Goblin capture and rescue",
        "units": (
            ((("player_name", 0), "CA:4261"), (134,), "duplicate_resolved_by_scene_context", "very_high_candidate", "Short 'Heeelp!' has other Android occurrences; the following 135/169+ goblin block resolves this one to 134."),
            (("CA:427A",), (135,), "short_line_resolved_by_context", "very_high_candidate", "Short exact 'Oooh!' immediately follows Android 134."),
            ((("player_name", 0), "CA:42B8"), (169,), "placeholder_join", "very_high_candidate", "Exact player capture line after placeholder reconstruction."),
            (("CA:42CA",), (170,), "one_to_one_minor_speaker", "very_high_candidate", "Goblin/Goblins speaker-number difference only."),
            (("CA:4300",), (171,), "one_to_one", "very_high_candidate", "Exact main-dish line."),
            ((("player_name", 0), "CA:433C"), (172,), "placeholder_join", "very_high_candidate", "Exact plea after placeholder reconstruction."),
            (("CA:435D",), (174,), "one_to_one_minor_speaker", "very_high_candidate", "Goblin/Goblins speaker-number difference only."),
            (("CA:43BF",), (176,), "one_to_one_minor_speaker", "very_high_candidate", "Distinct dancing line in same ordered goblin block."),
            (("CA:442E",), (178,), "short_line_resolved_by_context", "very_high_candidate", "Generic 'Hey!' accepted only because it sits between the goblin scene and the girl's next line."),
            (("CA:4442",), (180,), "short_line_resolved_by_context", "very_high_candidate", "Generic 'Hey, you!' resolved by immediate local context."),
            (("CA:445F",), (182,), "one_to_one", "very_high_candidate", "Exact distinctive girl line."),
            ((("player_name", 0), "CA:4491"), (183,), "placeholder_join", "very_high_candidate", "Exact plea after placeholder reconstruction."),
            (("CA:44A6",), (184,), "one_to_one", "very_high_candidate", "Exact quiet line."),
            (("CA:44D6",), (186,), "one_to_one", "very_high_candidate", "Exact escape line; closes the capture/rescue Android block."),
        ),
    },
    {
        "event_id": "04E8",
        "label": "Girl post-rescue conversation",
        "units": (
            ((("player_name", 0), "CA:451B"), (125,), "placeholder_join_subscene_reset", "very_high_candidate", "Exact player line; Android ID order resets from 186 to 125 at the post-rescue subscene."),
            (("CA:454F",), (126,), "one_to_one", "very_high_candidate", "Exact search/mistaken-person setup."),
            (("CA:459F",), (127,), "one_to_one_minor_wording", "very_high_candidate", "Same mistaken-identity sentence with minor word-order change."),
            ((("player_name", 0), "CA:45DB", "CA:461D"), (128, 129), "many_snes_to_many_android", "very_high_candidate", "SNES packs player interruption + girl's joke/hurry across two source tokens; Android splits at speaker boundary into 128-129."),
            ((("player_name", 0), "CA:4665"), (131,), "placeholder_join", "very_high_candidate", "Exact 'Hey, wait!' line."),
            (("CA:4677",), (132,), "one_to_one", "very_high_candidate", "Exact closing observation."),
        ),
    },
)



def read_scrtxt(path: Path) -> dict[int, str]:
    """Read an Android scrtxt binary into ``android_id -> UTF-8 text``."""
    data = path.read_bytes()
    if len(data) < 8:
        raise ValueError(f"{path}: file is too small to be a scrtxt binary")

    entry_count, pool_size = struct.unpack_from("<II", data, 0)
    table_end = 8 + entry_count * 8
    if table_end > len(data):
        raise ValueError(f"{path}: entry table extends beyond end of file")
    if table_end + pool_size != len(data):
        raise ValueError(
            f"{path}: declared pool size does not match file size "
            f"({pool_size} bytes declared, {len(data) - table_end} available)"
        )

    pool = data[table_end:]
    result: dict[int, str] = {}
    for index in range(entry_count):
        text_id, offset = struct.unpack_from("<II", data, 8 + index * 8)
        if text_id in result:
            raise ValueError(f"{path}: duplicate Android text ID {text_id}")
        if offset >= len(pool):
            raise ValueError(f"{path}: text ID {text_id} has invalid offset {offset:#x}")
        end = pool.find(b"\x00", offset)
        if end < 0:
            raise ValueError(f"{path}: text ID {text_id} is not NUL-terminated")
        try:
            result[text_id] = pool[offset:end].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"{path}: text ID {text_id} is not valid UTF-8") from exc
    return result


def require_parallel_scrtxt(english: dict[int, str], french: dict[int, str]) -> None:
    """Require English/French containers to expose the same Android ID namespace."""
    if set(english) != set(french):
        missing_fr = sorted(set(english) - set(french))
        missing_en = sorted(set(french) - set(english))
        details = []
        if missing_fr:
            details.append("missing in French: " + ", ".join(map(str, missing_fr[:10])))
        if missing_en:
            details.append("missing in English: " + ", ".join(map(str, missing_en[:10])))
        raise ValueError("Android scrtxt ID sets differ (" + "; ".join(details) + ")")


def normalize_android_prose(text: str) -> str:
    """Remove source-layout whitespace while preserving the translated prose."""
    return " ".join(text.replace("\r", " ").replace("\n", " ").split())


def make_intro_translation(scrtxt: dict[int, str]) -> dict:
    source = load_intro_source(ROOT / "assets" / "intro_event.json")
    source_ids = tuple(entry["id"] for entry in source["entries"])
    if source_ids != INTRO_TARGET_IDS:
        raise ValueError(
            "assets/intro_event.json IDs/order no longer match the validated Android intro mapping"
        )

    missing = [text_id for text_id in INTRO_ANDROID_IDS if text_id not in scrtxt]
    if missing:
        raise ValueError("Missing Android intro text ID(s): " + ", ".join(map(str, missing)))

    entries = [
        {
            "id": target_id,
            "text": normalize_android_prose(scrtxt[android_id]),
        }
        for android_id, target_id in zip(INTRO_ANDROID_IDS, INTRO_TARGET_IDS, strict=True)
    ]
    return {
        "format_version": 1,
        "language": "fr",
        "source_asset": "intro_event.json",
        "groups": [
            {
                "group": "intro.event_0400",
                "entries": entries,
            }
        ],
    }


def normalize_alignment_text(text: str) -> str:
    """Normalize English text for cross-version comparison, not for translation output."""
    text = re.sub(r"%S\([^)]*\)", " playername ", text, flags=re.IGNORECASE)
    text = text.replace("_", " ")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.casefold()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def alignment_metrics(source: str, candidate: str) -> dict[str, float]:
    """Return deliberately simple, explainable lexical metrics."""
    source_norm = normalize_alignment_text(source)
    candidate_norm = normalize_alignment_text(candidate)
    if not source_norm or not candidate_norm:
        return {"character_similarity": 0.0, "source_token_coverage": 0.0, "lexical_score": 0.0}

    character_similarity = 100.0 * SequenceMatcher(
        None, source_norm, candidate_norm, autojunk=False
    ).ratio()
    source_tokens = source_norm.split()
    candidate_tokens = set(candidate_norm.split())
    covered = sum(token in candidate_tokens for token in source_tokens)
    source_token_coverage = 100.0 * covered / len(source_tokens)
    lexical_score = character_similarity * 0.75 + source_token_coverage * 0.25
    return {
        "character_similarity": round(character_similarity, 1),
        "source_token_coverage": round(source_token_coverage, 1),
        "lexical_score": round(lexical_score, 1),
    }


def load_dialogue_text_entries(path: Path = DIALOGUE_SOURCE) -> dict[str, dict]:
    document = json.loads(path.read_text(encoding="utf-8"))
    result: dict[str, dict] = {}
    for event in document.get("events", []):
        event_id = event.get("event_id")
        for token_index, token in enumerate(event.get("tokens", [])):
            if token.get("type") != "text":
                continue
            text_id = token.get("id")
            source = token.get("source")
            if not isinstance(text_id, str) or not isinstance(source, str):
                raise ValueError(f"{path}: malformed dialogue text token in event {event_id}")
            if text_id in result:
                raise ValueError(f"{path}: duplicate dialogue text ID {text_id}")
            result[text_id] = {
                "event_id": event_id,
                "token_index": token_index,
                "source": source,
            }
    return result


def rank_android_candidates(source: str, english: dict[int, str], *, limit: int = 5) -> list[dict]:
    ranked: list[tuple[float, float, int, dict[str, float]]] = []
    for android_id, text in english.items():
        if not normalize_alignment_text(text):
            continue
        metrics = alignment_metrics(source, text)
        ranked.append(
            (
                metrics["lexical_score"],
                metrics["character_similarity"],
                android_id,
                metrics,
            )
        )
    ranked.sort(reverse=True)
    return [
        {"android_id": android_id, **metrics}
        for _, _, android_id, metrics in ranked[:limit]
    ]



# Round 11 continues the PARTIEL review using the same conservative structural
# rules as round 8. Every mapping is demonstrated by Android English and the
# ordered local scene; generic short labels/options are intentionally excluded.
DIALOGUE_REVIEW_ROUND11 = (
    {"event_id": "01DC", "label": "Pandora ruins soldiers ordered gaps", "units": (
        (("C9:7EB5",), (720,), "speaker_label_alignment", "very_high_structural", "Exact Soldier ellipsis opens Android 720-728, immediately before accepted 721/722."),
        (("C9:7FF4",), (728,), "one_to_one", "very_high_structural", "Android 728 is the exact three-person platform/bridge instruction and directly follows accepted 727."),
    )},
    {"event_id": "01ED", "label": "Elinee apology opening", "units": ((("C9:8771",), (754,), "one_to_one", "very_high_structural", "Exact Elinee apology at Android 754 immediately precedes accepted 755-758."),)},
    {"event_id": "01F5", "label": "Elinee lost magic continuation", "units": ((("C9:899F",), (761,), "one_to_one", "very_high_structural", "Exact lost-magical-power sentence at Android 761 immediately follows accepted 760."),)},
    {"event_id": "023A", "label": "Crystal Orb question opening", "units": ((("C9:9CB8",), (973,), "speaker_reattribution", "very_high_structural", "Exact Crystal Orb question at Android 973 immediately precedes accepted 974/975; Android adds PLAYER_NAME(0) attribution."),)},
    {"event_id": "0250", "label": "Matango village shambles gap", "units": ((("C9:A00D",), (1263,), "one_to_one", "very_high_structural", "Android 1263 is the exact village-in-shambles line between accepted 1262 and 1264."),)},
    {"event_id": "02B2", "label": "Amar Sea Hare and belt ordered gaps", "units": (
        (("C9:B89E",), (1642,), "one_snes_to_one_android_expanded", "very_high_structural", "Android 1642 begins with the exact Sea Hare tail/Hurrah line and adds the well action in the same Amar scene."),
        (("C9:B8F8",), (1664,), "one_snes_to_one_android_expanded", "very_high_structural", "Android 1664 begins with the exact belt reward and expands its legendary-knight description immediately before accepted 1665."),
    )},
    {"event_id": "02B4", "label": "Fire Seed missing continuation", "units": ((("C9:B9D6",), (1636,), "one_snes_to_one_android_expanded", "very_high_structural", "Android 1636 begins with the exact missing Fire Seed sentence and adds the monster consequence directly after accepted 1635."),)},
    {"event_id": "02B7", "label": "Ice Country relocation branch", "units": (
        (("C9:BA6C",), (1623,), "one_to_one", "very_high_structural", "Exact Ice Country destination at Android 1623 in the relocation NPC branch."),
        (("C9:BA7C",), (1624,), "one_to_one", "very_high_structural", "Exact warm-town sentence at Android 1624 immediately after 1623; French continuation in the following English-empty slot is retained by anchor interval policy."),
    )},
    {"event_id": "02E4", "label": "Serin legendary warrior continuation", "units": ((("C9:C62F",), (2561,), "one_snes_to_one_android_expanded", "very_high_structural", "Android 2561 begins with the exact Serin legendary-warrior sentence and adds the great-war timing, directly after accepted 2560."),)},
    {"event_id": "02F9", "label": "Sea Hare merchant ordered gaps", "units": (
        (("C9:C9D5",), (2294,), "one_snes_to_one_android_expanded", "very_high_structural", "Android 2294 begins with the exact 'not making it here' thought and expands the move-to-city idea immediately before accepted 2295."),
        (("C9:CA38",), (2296,), "one_snes_to_one_android_expanded", "very_high_structural", "Android 2296 begins with the exact 'you actually WANT one?' reaction and adds the giveaway rationale between accepted 2295 and 2297."),
    )},
    {"event_id": "0363", "label": "Sprite elder warning opening", "units": ((("C9:D1DB",), (500,), "one_snes_to_one_android_expanded", "very_high_structural", "Android 500 contains the exact leave-now/never-return warning plus 'Wait up!', immediately before accepted 501."),)},
    {"event_id": "036F", "label": "Scorpion hideout ordered gaps", "units": (
        (("C9:D563",), (1144,), "one_snes_to_one_android_expanded", "very_high_structural", "Android 1144 begins with the exact cannot-let-you-leave sentence and adds the secret-hideout reason immediately before accepted 1145."),
        (("C9:D661",), (1151, 1152, 1153), "one_snes_to_many_android", "very_high_structural", "The SNES Boys/Boss/Boys reaction is split into ordered Android 1151/1152/1153 directly after accepted 1149/1150."),
    )},
    {"event_id": "039F", "label": "Empire bizarre thoughts opening", "units": ((("C9:DFF2",), (1871,), "one_snes_to_one_android_expanded", "very_high_structural", "Android 1871 contains the exact emperor-bizarre-thoughts sentence with a conversational preface, immediately before accepted 1872."),)},
    {"event_id": "03D0", "label": "Palace of Darkness cave opening", "units": ((("C9:E9A1",), (2315,), "one_snes_to_one_android_expanded", "very_high_structural", "Android 2315 contains the exact mountain/cave/monsters directions and directly precedes accepted 2316."),)},
    {"event_id": "03DD", "label": "Jehk rejection opening", "units": ((("C9:ED6D",), (2445,), "speaker_label_alignment", "very_high_structural", "Android 2445 'Go away!' is the same Jehk rejection immediately before accepted 2446/2447; no global short-label matching is used."),)},
    {"event_id": "04A3", "label": "Thanatos Geshtar explanation", "units": ((("CA:1A1E",), (2917,), "one_snes_to_one_android_expanded", "very_high_structural", "Android 2917 begins with the same Thanatos/Geshtar question-answer and expands it, bracketed by accepted 2915/2916 and 2918/2919."),)},
    {"event_id": "04EA", "label": "Gaia Navel dwarves resegmentation", "units": ((("CA:4C1F", "CA:4C71"), (858,), "many_snes_to_one_android", "very_high_structural", "Android 858 combines the two consecutive SNES dwarf-cave/weapon/reforge fragments between accepted 857 and 859."),)},
    {"event_id": "052F", "label": "Truffle voice opening", "units": ((("CA:5FEF",), (2272,), "speaker_label_alignment", "very_high_structural", "Exact Voice: Hellooo line at Android 2272 between accepted 2271 and 2273."),)},
    {"event_id": "0532", "label": "Truffle Matango destination ending", "units": ((("CA:61D8",), (2280,), "one_to_one", "very_high_structural", "Exact Matango/southwest instruction at Android 2280 immediately after accepted 2279."),)},
    {"event_id": "0580", "label": "Gnome gained-powers system line", "units": ((("CA:6B9C",), (1048,), "system_message_equivalence", "very_high_structural", "Android 1048 'Gained Gnome's powers!' is the exact system-message equivalent immediately before accepted 1049."),)},
    {"event_id": "0582", "label": "Salamando gained-powers system line", "units": ((("CA:6F3D",), (1807,), "system_message_equivalence", "very_high_structural", "Android 1807 'Gained Salamando's powers!' is the exact system-message equivalent immediately after accepted 1806."),)},
    {"event_id": "0584", "label": "Luna power grant resegmentation", "units": ((("CA:6FD7", "CA:7005"), (2649,), "many_snes_to_one_android", "very_high_structural", "Android 2649 compresses the two consecutive SNES Luna fragments into the same take-my-powers / Mana-is-fading message between accepted 2648 and 2651."),)},
    {"event_id": "0587", "label": "Lumina introduction resegmentation", "units": ((("CA:7154", "CA:718F"), (2533,), "many_snes_to_one_android", "very_high_structural", "Android 2533 combines the two consecutive SNES Lumina introduction / king draining power / making gold fragments immediately before accepted 2536/2538."),)},
)


# Round 18 targets the same speaker/resegmentation family as the user-reviewed
# ``All:`` Joch reactions.  Every unit is anchored by Android English and the
# ordered local scene; no global short-label matching is used.
DIALOGUE_REVIEW_ROUND18 = (
    {"event_id": "0236", "label": "Gnome entrance resegmentation", "units": (
        (("C9:9B8C",), (993, 994), "one_snes_to_many_android", "very_high_structural", "SNES combines the two consecutive gnome warnings; Android EN splits them into 993/994 immediately before Android 995/996."),
        (("C9:9BCB",), (995, 996), "one_snes_to_many_android", "very_high_structural", "Exact player/gome exchange split into adjacent Android 995/996; retained explicitly because adding the preceding structural unit changes generic session segmentation."),
        (("C9:9C20",), (999,), "speaker_reaction_adaptation", "very_high_structural", "The gnome's angry reaction sits exactly between already accepted Android 998 ('Take this!') and 1001 ('I'm out of here!'); Android adapts the wording to 'Why you little--!' while preserving speaker and scene position."),
    )},
    {"event_id": "0293", "label": "Sandship Sergo/guard speaker split", "units": (
        (("C9:AEB6",), (1508, 1509), "one_snes_to_many_android_equivalent_duplicate", "very_high_structural", "SNES packs Sergo 'Fire! Fire!' and the guard reply into one token; Android EN splits them into 1508/1509. The duplicate 1513/1514 pair has identical EN/FR, so the localized semantic result is unambiguous."),
    )},
    {"event_id": "03E9", "label": "Television sleep reaction ordered duplicate", "units": (
        (("C9:F039",), (2349,), "duplicate_resolved_by_local_order", "very_high_structural", "Exact '...Gzzz...' follows already accepted Android 2347/2348 in this television sequence; the later duplicate 2355 belongs to a different programme block."),
    )},
    {"event_id": "055E", "label": "Phanna/Krissie speaker resegmentation", "units": (
        (("CA:6828",), (2034,), "speaker_reaction_adaptation", "very_high_structural", "SNES 'Hush!' and Android EN 'Shut up!' are the same reaction immediately after accepted 2032/2033 and before accepted 2035."),
        ((("player_name", 1), "CA:687F"), (2037,), "placeholder_plus_expanded_reaction", "very_high_structural", "SNES PLAYER_NAME(1)+':Liar!' is expanded by Android EN to the same player's 'T-that's... not true... You're lying!' exactly between accepted 2035 and 2038."),
        (("CA:68B1",), (2040,), "speaker_label_alignment", "very_high_structural", "Exact 'Phanna: Ooh!' / Android 2040 is bracketed by already accepted 2038 and 2041 in the same confrontation."),
        (("CA:6962", ("player_name", 0), "CA:696C"), (2048,), "speaker_prefix_placeholder_join", "very_high_structural", "SNES splits 'KRISSIE:' + PLAYER_NAME(0) + 'What's up?' across two text carriers; Android EN 2048 stores the exact combined Krissie line in the same 2032-2055 scene."),
    )},
)


def english_anchor_interval(anchor_id: int, english: dict[int, str]) -> list[int]:
    """Return an English non-empty ID plus following empty slots up to the next anchor."""
    if anchor_id not in english or not english[anchor_id]:
        raise ValueError(f"Android English ID {anchor_id} is not a non-empty anchor")
    ids = [anchor_id]
    next_id = anchor_id + 1
    while next_id in english and english[next_id] == "":
        ids.append(next_id)
        next_id += 1
    return ids


def scrtxt_parallel_stats(english: dict[int, str], french: dict[int, str]) -> dict:
    """Summarize observed slot usage without assigning semantic meaning to every empty ID."""
    require_parallel_scrtxt(english, french)
    anchors = [text_id for text_id in sorted(english) if english[text_id]]
    widths: dict[int, int] = {}
    continuation_used = 0
    root_blank_continuation_used = 0
    for anchor_id in anchors:
        interval = english_anchor_interval(anchor_id, english)
        widths[len(interval)] = widths.get(len(interval), 0) + 1
        french_nonempty = [text_id for text_id in interval if french[text_id]]
        if any(text_id != anchor_id for text_id in french_nonempty):
            continuation_used += 1
        if not french[anchor_id] and french_nonempty:
            root_blank_continuation_used += 1
    return {
        "entry_count": len(english),
        "english_nonempty_anchor_count": len(anchors),
        "english_empty_slot_count": len(english) - len(anchors),
        "english_anchor_interval_widths": {str(width): widths[width] for width in sorted(widths)},
        "intervals_where_french_uses_following_english_empty_slot": continuation_used,
        "intervals_where_french_root_is_empty_but_following_slot_is_used": root_blank_continuation_used,
    }

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_dialogue_pilot_report(
    english: dict[int, str],
    french: dict[int, str],
    *,
    english_path: Path,
    french_path: Path,
) -> dict:
    """Build the small, evidence-backed dialogue alignment checkpoint."""
    require_parallel_scrtxt(english, french)
    source = load_dialogue_text_entries()

    scenes: list[dict] = []
    for scene in DIALOGUE_PILOT_SCENES:
        event_id = scene["event_id"]
        entries: list[dict] = []
        android_ids: list[int] = []
        for snes_id, android_id in scene["pairs"]:
            if snes_id not in source:
                raise ValueError(f"Dialogue pilot source ID {snes_id} is absent from assets/dialogues.json")
            if source[snes_id]["event_id"] != event_id:
                raise ValueError(
                    f"Dialogue pilot source ID {snes_id} moved from event {event_id} "
                    f"to {source[snes_id]['event_id']}"
                )
            if android_id not in english or android_id not in french:
                raise ValueError(f"Dialogue pilot Android ID {android_id} is missing")

            ranked = rank_android_candidates(source[snes_id]["source"], english, limit=3)
            if not ranked or ranked[0]["android_id"] != android_id:
                best = ranked[0]["android_id"] if ranked else None
                raise ValueError(
                    f"Dialogue pilot {snes_id}: expected Android {android_id}, lexical best is {best}"
                )
            second_score = ranked[1]["lexical_score"] if len(ranked) > 1 else 0.0
            best = ranked[0]
            margin = round(best["lexical_score"] - second_score, 1)
            unit_ids = english_anchor_interval(android_id, english)
            french_nonempty_ids = [text_id for text_id in unit_ids if french[text_id]]
            entries.append(
                {
                    "snes_id": snes_id,
                    "android_id": android_id,
                    "confidence": "very_high",
                    "character_similarity": best["character_similarity"],
                    "source_token_coverage": best["source_token_coverage"],
                    "lexical_score": best["lexical_score"],
                    "next_candidate_margin": margin,
                    "android_unit_ids": unit_ids,
                    "french_nonempty_ids": french_nonempty_ids,
                    "requires_french_slot_merge": len(french_nonempty_ids) != 1 or french_nonempty_ids[0] != android_id,
                }
            )
            android_ids.append(android_id)

        if android_ids != sorted(android_ids) or len(set(android_ids)) != len(android_ids):
            raise ValueError(f"Dialogue pilot event {event_id}: Android IDs are not strictly ordered")

        gaps = [right - left for left, right in zip(android_ids, android_ids[1:])]
        empty_bridge_ids = [
            intermediate
            for left, right in zip(android_ids, android_ids[1:])
            for intermediate in range(left + 1, right)
            if english.get(intermediate) == "" and french.get(intermediate) == ""
        ]
        scenes.append(
            {
                "event_id": event_id,
                "label": scene["label"],
                "confidence": "very_high",
                "android_id_gaps": gaps,
                "parallel_empty_bridge_ids": empty_bridge_ids,
                "entries": entries,
            }
        )

    ambiguous: list[dict] = []
    for case in DIALOGUE_PILOT_AMBIGUOUS:
        snes_id = case["snes_id"]
        if snes_id not in source:
            raise ValueError(f"Dialogue ambiguity source ID {snes_id} is absent")
        ranked = rank_android_candidates(source[snes_id]["source"], english, limit=6)
        ambiguous.append(
            {
                "snes_id": snes_id,
                "event_id": source[snes_id]["event_id"],
                "status": "manual_review",
                "reason": case["reason"],
                "candidate_android_ids": list(case["candidate_android_ids"]),
                "top_lexical_candidates": ranked,
            }
        )

    return {
        "format_version": 1,
        "status": "pilot_alignment_only",
        "source_asset": "dialogues.json",
        "parallel_slot_observations": scrtxt_parallel_stats(english, french),
        "android_english": {
            "path": "sources/android/scrtxt_en.bin",
            "sha256": sha256(english_path),
        },
        "android_french": {
            "path": "sources/android/scrtxt_fr.bin",
            "sha256": sha256(french_path),
        },
        "policy": {
            "automatic_translation_generation": False,
            "accepted_confidence": "very_high",
            "notes": [
                "Lexical similarity is only one signal.",
                "Accepted pilot entries must also belong to a coherent ordered local scene run.",
                "Duplicate and one-to-many cases remain manual-review items even with strong text matches.",
                "French text may occupy following IDs that are empty in English; dialogue generation remains disabled until slot merging and SNES layout policy are validated.",
            ],
        },
        "scenes": scenes,
        "ambiguous": ambiguous,
    }



def render_snes_review_parts(parts: tuple, source: dict[str, dict], *, event_id: str) -> tuple[list[str], str]:
    """Render canonical SNES source parts plus explicit dynamic-name placeholders."""
    snes_ids: list[str] = []
    chunks: list[str] = []
    for part in parts:
        if isinstance(part, str):
            if part not in source:
                raise ValueError(f"Dialogue review source ID {part} is absent from assets/dialogues.json")
            if source[part]["event_id"] != event_id:
                raise ValueError(
                    f"Dialogue review source ID {part} moved from event {event_id} "
                    f"to {source[part]['event_id']}"
                )
            snes_ids.append(part)
            chunks.append(source[part]["source"])
        elif (
            isinstance(part, tuple)
            and len(part) == 2
            and part[0] == "player_name"
            and isinstance(part[1], int)
        ):
            chunks.append(f"%S({part[1]},0)")
        else:
            raise ValueError(f"Unsupported dialogue review SNES part: {part!r}")
    return snes_ids, "".join(chunks)


def android_anchor_units(anchor_ids: tuple[int, ...], english: dict[int, str]) -> list[int]:
    """Expand one or more English anchors to include their localization slots."""
    result: list[int] = []
    for anchor_id in anchor_ids:
        for text_id in english_anchor_interval(anchor_id, english):
            if text_id not in result:
                result.append(text_id)
    return result


def make_dialogue_review_report(
    english: dict[int, str],
    french: dict[int, str],
    *,
    english_path: Path,
    french_path: Path,
    batch: tuple,
    round_name: str,
    user_validated: bool,
) -> dict:
    """Build a reproducible scene-level Android dialogue review batch."""
    require_parallel_scrtxt(english, french)
    source = load_dialogue_text_entries()
    scenes: list[dict] = []
    for scene in batch:
        event_id = scene["event_id"]
        units: list[dict] = []
        previous_last_anchor: int | None = None
        for parts, android_ids, relation, proposed_confidence, note in scene["units"]:
            snes_ids, source_display = render_snes_review_parts(parts, source, event_id=event_id)
            for android_id in android_ids:
                if android_id not in english or not english[android_id]:
                    raise ValueError(
                        f"Dialogue review event {event_id}: Android English ID {android_id} is not a non-empty anchor"
                    )
            if list(android_ids) != sorted(android_ids) or len(set(android_ids)) != len(android_ids):
                raise ValueError(f"Dialogue review event {event_id}: Android anchors are not strictly ordered inside a unit")
            if previous_last_anchor is not None and android_ids[0] <= previous_last_anchor:
                raise ValueError(f"Dialogue review event {event_id}: units are not in increasing Android-ID order")
            previous_last_anchor = android_ids[-1]

            android_english = " ".join(english[text_id] for text_id in android_ids)
            metrics = alignment_metrics(source_display, android_english)
            unit_ids = android_anchor_units(android_ids, english)
            french_nonempty_ids = [text_id for text_id in unit_ids if french[text_id]]
            units.append(
                {
                    "snes_ids": snes_ids,
                    "snes_parts": [list(part) if isinstance(part, tuple) else part for part in parts],
                    "source_display": source_display,
                    "android_anchor_ids": list(android_ids),
                    "android_unit_ids": unit_ids,
                    "android_english_display": android_english,
                    "french_nonempty_ids": french_nonempty_ids,
                    "french_display": " ".join(french[text_id] for text_id in french_nonempty_ids),
                    "relation": relation,
                    "proposed_confidence": proposed_confidence,
                    "lexical_evidence": metrics,
                    "note": note,
                    "user_validation": "accepted" if user_validated else "pending",
                }
            )
        scenes.append(
            {
                "event_id": event_id,
                "label": scene["label"],
                "status": "user_validated" if user_validated else "user_review_pending",
                "units": units,
            }
        )
    return {
        "format_version": 1,
        "status": f"{round_name}_user_validated" if user_validated else f"{round_name}_user_review_pending",
        "source_asset": "dialogues.json",
        "android_english": {
            "path": "sources/android/scrtxt_en.bin",
            "sha256": sha256(english_path),
        },
        "android_french": {
            "path": "sources/android/scrtxt_fr.bin",
            "sha256": sha256(french_path),
        },
        "policy": {
            "automatic_translation_generation": False,
            "english_identity_is_primary": True,
            "notes": [
                "SNES PLAYER_NAME commands are represented explicitly as Android-style %S(index,0) placeholders for comparison only.",
                "Android anchor intervals include following English-empty localization slots.",
                "Very-high-confidence SNES-to-Android-English identity is not rejected merely because French wording is freely adapted.",
                "When French or Android segmentation crosses individual anchors, preserve and review the complete local sequence block rather than forcing a per-ID translation.",
            ],
        },
        "scenes": scenes,
    }


def make_dialogue_review_round2_report(
    english: dict[int, str],
    french: dict[int, str],
    *,
    english_path: Path,
    french_path: Path,
) -> dict:
    """Regenerate the user-validated second alignment batch."""
    return make_dialogue_review_report(
        english,
        french,
        english_path=english_path,
        french_path=french_path,
        batch=DIALOGUE_REVIEW_ROUND2,
        round_name="round2",
        user_validated=True,
    )


def make_dialogue_review_round3_report(
    english: dict[int, str],
    french: dict[int, str],
    *,
    english_path: Path,
    french_path: Path,
) -> dict:
    """Regenerate the user-validated third alignment batch."""
    return make_dialogue_review_report(
        english,
        french,
        english_path=english_path,
        french_path=french_path,
        batch=DIALOGUE_REVIEW_ROUND3,
        round_name="round3",
        user_validated=True,
    )


def make_dialogue_review_round4_report(
    english: dict[int, str],
    french: dict[int, str],
    *,
    english_path: Path,
    french_path: Path,
) -> dict:
    """Regenerate the user-validated fourth diversity batch."""
    return make_dialogue_review_report(
        english,
        french,
        english_path=english_path,
        french_path=french_path,
        batch=DIALOGUE_REVIEW_ROUND4,
        round_name="round4",
        user_validated=True,
    )


def make_dialogue_review_round5_report(
    english: dict[int, str],
    french: dict[int, str],
    *,
    english_path: Path,
    french_path: Path,
) -> dict:
    """Regenerate the user-validated final pre-automation stress-test batch."""
    document = make_dialogue_review_report(
        english,
        french,
        english_path=english_path,
        french_path=french_path,
        batch=DIALOGUE_REVIEW_ROUND5,
        round_name="round5",
        user_validated=True,
    )
    document["stress_findings"] = [
        "Four non-monotonic event-level anchor runs are explained by one SNES event spanning multiple Android subscene blocks.",
        "Event 0204 contains a genuine local reorder: SNES C9:9076 appears after the Mana Seed ritual, while its unique Android-English equivalent is ID 824, before IDs 839-844.",
        "Event-level monotonicity is therefore too coarse for automatic alignment; local dialogue/subscene order is the stronger signal.",
        "Unmatched SNES prose must remain explicit rather than being forced onto a nearby Android anchor.",
    ]
    document["unmatched_snes_observations"] = [
        {
            "event_id": "0204",
            "snes_id": "C9:902F",
            "source": "You'll be able to gain power from the Mana seed wherever you are!",
            "reason": "No confident standalone Android-English anchor was found in the local Water Palace block; nearby Android/French text compresses and redistributes this explanation.",
        },
        {
            "event_id": "04E8",
            "snes_id": "CA:437D",
            "source": "...SHRIEK!",
            "reason": "No confident English Android equivalent; the nearby Android ID 175 is a different exclamation. Leave unmapped rather than forcing a short generic match.",
        },
    ]
    return document


def make_dialogue_review_round6_report(
    english: dict[int, str],
    french: dict[int, str],
    *,
    english_path: Path,
    french_path: Path,
) -> dict:
    """Regenerate the structural review used by the current auto alignment."""
    return make_dialogue_review_report(
        english,
        french,
        english_path=english_path,
        french_path=french_path,
        batch=DIALOGUE_REVIEW_ROUND6,
        round_name="round6",
        user_validated=False,
    )


def make_dialogue_review_round7_report(
    english: dict[int, str],
    french: dict[int, str],
    *,
    english_path: Path,
    french_path: Path,
) -> dict:
    """Regenerate the next conservative structural PARTIEL review."""
    return make_dialogue_review_report(
        english,
        french,
        english_path=english_path,
        french_path=french_path,
        batch=DIALOGUE_REVIEW_ROUND7,
        round_name="round7",
        user_validated=False,
    )


def make_dialogue_review_round8_report(
    english: dict[int, str],
    french: dict[int, str],
    *,
    english_path: Path,
    french_path: Path,
) -> dict:
    """Regenerate the user-driven structural PARTIEL review."""
    return make_dialogue_review_report(
        english,
        french,
        english_path=english_path,
        french_path=french_path,
        batch=DIALOGUE_REVIEW_ROUND8,
        round_name="round8",
        user_validated=False,
    )


def make_dialogue_review_round11_report(
    english: dict[int, str],
    french: dict[int, str],
    *,
    english_path: Path,
    french_path: Path,
) -> dict:
    """Regenerate the conservative PARTIEL follow-up derived from user review patterns."""
    return make_dialogue_review_report(
        english, french, english_path=english_path, french_path=french_path,
        batch=DIALOGUE_REVIEW_ROUND11, round_name="round11", user_validated=False,
    )


def make_dialogue_review_round18_report(
    english: dict[int, str],
    french: dict[int, str],
    *,
    english_path: Path,
    french_path: Path,
) -> dict:
    """Regenerate the speaker/resegmentation PARTIEL follow-up."""
    return make_dialogue_review_report(
        english, french, english_path=english_path, french_path=french_path,
        batch=DIALOGUE_REVIEW_ROUND18, round_name="round18", user_validated=False,
    )


def make_dialogue_review_round20_report(
    english: dict[int, str],
    french: dict[int, str],
    *,
    english_path: Path,
    french_path: Path,
) -> dict:
    """Regenerate the Cannon Travel / choice-anchor structural follow-up."""
    return make_dialogue_review_report(
        english, french, english_path=english_path, french_path=french_path,
        batch=DIALOGUE_REVIEW_ROUND20, round_name="round20", user_validated=False,
    )


def make_dialogue_review_round21_report(
    english: dict[int, str],
    french: dict[int, str],
    *,
    english_path: Path,
    french_path: Path,
) -> dict:
    """Regenerate the conservative PARTIEL resegmentation follow-up."""
    return make_dialogue_review_report(
        english, french, english_path=english_path, french_path=french_path,
        batch=DIALOGUE_REVIEW_ROUND21, round_name="round21", user_validated=False,
    )


def make_dialogue_review_round22_report(
    english: dict[int, str],
    french: dict[int, str],
    *,
    english_path: Path,
    french_path: Path,
) -> dict:
    """Regenerate the branch/staging PARTIEL resegmentation follow-up."""
    return make_dialogue_review_report(
        english, french, english_path=english_path, french_path=french_path,
        batch=DIALOGUE_REVIEW_ROUND22, round_name="round22", user_validated=False,
    )


# ---- Conservative whole-dialogue Android alignment -------------------------

DEFAULT_DIALOGUE_AUTO_OUTPUT = ROOT / "mappings" / "android" / "dialogues_auto.json"
DEFAULT_DIALOGUE_UNMAPPED_CSV = ROOT / "mappings" / "android" / "dialogues_unmapped.csv"
DEFAULT_DIALOGUE_FORMAT_PILOT_OUTPUT = ROOT / "mappings" / "android" / "dialogues_format_pilot_translation.json"
DEFAULT_DIALOGUE_FORMAT_PILOT_REPORT = ROOT / "mappings" / "android" / "dialogues_format_pilot.json"
DEFAULT_DIALOGUE_FORMAT_BATCH1_OUTPUT = ROOT / "translations" / "dialogues_french.json"
DEFAULT_DIALOGUE_FORMAT_BATCH1_REPORT = ROOT / "mappings" / "android" / "dialogues_format_batch1.json"
DEFAULT_DIALOGUE_FORMAT_PAGE_PILOT_OUTPUT = ROOT / "mappings" / "android" / "dialogues_format_page_pilot_translation.json"
DEFAULT_DIALOGUE_FORMAT_PAGE_PILOT_REPORT = ROOT / "mappings" / "android" / "dialogues_format_page_pilot.json"
DEFAULT_DIALOGUE_FORMAT_BATCH2_OUTPUT = ROOT / "translations" / "dialogues_french.json"
DEFAULT_DIALOGUE_FORMAT_BATCH2_REPORT = ROOT / "mappings" / "android" / "dialogues_format_batch2.json"
DEFAULT_DIALOGUE_FORMAT_MASS_OUTPUT = ROOT / "translations" / "dialogues_french.json"
DEFAULT_DIALOGUE_FORMAT_MASS_REPORT = ROOT / "mappings" / "android" / "dialogues_format_mass.json"
DEFAULT_DIALOGUE_FORMAT_MASS_EXCLUDED_CSV = ROOT / "mappings" / "android" / "dialogues_format_mass_excluded.csv"
DIALOGUE_FORMAT_PILOT_EVENTS = ("0107",)
# First post-pilot runtime batch. Every selected event is complete: all of its
# semantic SNES text IDs are accepted by the Android aligner and pass the
# conservative structural formatter. This prevents mixed EN/FR test scenes.
DIALOGUE_FORMAT_BATCH1_EVENTS = ("0107", "010E", "0116", "0117", "0118", "011D")
DIALOGUE_FORMAT_PAGE_PILOT_EVENTS = ("0107", "010E", "010F", "0116", "0117", "0118", "011D")
DIALOGUE_FORMAT_EXTRA_PAGE_EVENTS = frozenset({"010F"})
# First larger explicit expansion after the pagination rule was runtime-validated.
# The list is intentionally frozen rather than discovered dynamically: future
# formatter changes must not silently change which events enter the patch.
DIALOGUE_FORMAT_BATCH2_EVENTS = (
    "0107", "010A", "010E", "010F", "0116", "0117", "0118", "011D",
    "012F", "0130", "0136", "0137", "0139", "013C", "013D", "0140",
    "0141", "0142", "0144", "014B", "014C", "014D", "0150", "0152",
    "0153", "0154", "0155",
)
DIALOGUE_FORMAT_BATCH2_EXTRA_PAGE_EVENTS = frozenset({"010A", "010F", "013C", "014B"})

# These two stress-test sources were explicitly reviewed and have no confident
# standalone Android-English equivalent. Automatic passes must never force them.
DIALOGUE_FORCED_UNMAPPED = {
    "C9:902F": "Round-5 validated unmatched case: nearby Android text compresses/redistributes the explanation; no confident standalone English anchor.",
    "CA:437D": "Round-5 validated unmatched case: the nearby Android exclamation is semantically different.",
}

# Reviewed structural corrections that intentionally replace an automatic
# lexical choice. The generic calibration guard remains active for every other
# reviewed source ID.
DIALOGUE_REVIEWED_AUTO_OVERRIDES = frozenset({"CA:696C"})

# The pilot proved that these duplicated Android locations carry equivalent
# English/French content even though provenance cannot select one copy. Keep the
# alternatives explicit instead of inventing a single Android ID.
DIALOGUE_VALIDATED_ALTERNATIVE_GROUPS = {
    "C9:089B": ((3314,), (3360,)),
    "C9:0C19": ((2667,), (2793,)),
    "C9:0B03": ((2449, 2450), (2463, 2464)),
    "C9:392C": ((792,), (796,)),
}

# These events were explicitly reviewed by the user as visually complete even
# though some stock SNES semantic fragments have no one-to-one Android anchor.
# Keep their exact simulator-clean French-only bytes, but do not count them as
# PARTIEL in the preview/report. This does not create mappings for the omitted
# SNES fragments and therefore does not inflate alignment coverage.
DIALOGUE_USER_VALIDATED_VISUALLY_COMPLETE_EVENTS = frozenset({"0103", "017F", "01DC"})

# $01DC has one Android-adaptation omission that includes a structural speaker
# carrier, not just semantic text. The user explicitly validated dropping the
# final stock PLAYER_NAME(0) together with C9:804A because Android 729 begins
# the following Niccolo scene directly after Android 728. The source asset stays
# canonical; this exact command is omitted only in translated serialization.
DIALOGUE_USER_VALIDATED_STRUCTURAL_OMISSIONS = (
    {
        "event_id": "01DC",
        "suppressed_semantic_ids": ["C9:804A"],
        "suppressed_commands": [
            {
                "name": "PLAYER_NAME",
                "args": "00",
                "immediately_before_text_id": "C9:804A",
            }
        ],
        "reason": "user_validated_android_adaptation_omission",
    },
)


# $0331 remains semantically PARTIEL because the generic inn prompt carrier
# C9:CEB3 has no single proven Android identity. Suppressing its visible stock
# English must nevertheless preserve its two stock NEWLINEs: runtime testing
# proved that the choice row must stay on its original third physical line for
# the stock selection/highlight geometry to target the rendered Oui/Non row.
# This is layout-only metadata, never localized prose.
DIALOGUE_USER_VALIDATED_PARTIAL_LAYOUT_PRESERVATIONS = ()


# Manual supplements are deliberately outside Android alignment.  They are
# permitted only for exact SNES carriers whose complete absence from Android
# has been explicitly reviewed.  The editable JSON initially keeps the stock
# USA prose until a human French translation is supplied.
DIALOGUE_USER_VALIDATED_ANDROID_ABSENT_MANUAL_IDS = {
    "0278": frozenset({"C9:A730", "C9:A74E"}),
}


def _load_manual_dialogue_supplements(source_document: dict) -> dict[str, dict[str, dict]]:
    document = json.loads(DIALOGUE_MANUAL_SUPPLEMENTS.read_text(encoding="utf-8"))
    if document.get("format_version") != 1 or document.get("language") != "fr":
        raise ValueError("dialogues_manual_supplements.json: unsupported format/language")
    if document.get("source_asset") != "assets/dialogues.json":
        raise ValueError("dialogues_manual_supplements.json: invalid source_asset")
    by_id, _ = event_text_index(source_document)
    result: dict[str, dict[str, dict]] = {}
    for entry in document.get("entries", []):
        if not isinstance(entry, dict):
            raise ValueError("dialogues_manual_supplements.json: entries must be objects")
        event_id = entry.get("event_id")
        text_id = entry.get("id")
        source_en = entry.get("source_en")
        text = entry.get("text")
        status = entry.get("status")
        reason = entry.get("reason")
        allowed = DIALOGUE_USER_VALIDATED_ANDROID_ABSENT_MANUAL_IDS.get(event_id, frozenset())
        if text_id not in allowed:
            raise ValueError(
                f"Manual supplement ${event_id}/{text_id}: carrier is not user-validated absent from Android"
            )
        meta = by_id.get(text_id)
        if meta is None or meta.get("event_id") != event_id:
            raise ValueError(f"Manual supplement ${event_id}/{text_id}: unknown/mismatched source carrier")
        if source_en != meta.get("source"):
            raise ValueError(f"Manual supplement ${event_id}/{text_id}: source_en is not byte-faithful to assets/dialogues.json")
        if not isinstance(text, str) or not text:
            raise ValueError(f"Manual supplement ${event_id}/{text_id}: text must be non-empty")
        if status not in {"needs_manual_translation", "translated"}:
            raise ValueError(f"Manual supplement ${event_id}/{text_id}: invalid status")
        if status == "needs_manual_translation" and text != source_en:
            raise ValueError(f"Manual supplement ${event_id}/{text_id}: pending entries must retain stock USA text")
        if reason != "user_validated_absent_from_android":
            raise ValueError(f"Manual supplement ${event_id}/{text_id}: invalid reason")
        if text_id in result.setdefault(event_id, {}):
            raise ValueError(f"Manual supplement ${event_id}/{text_id}: duplicate entry")
        result[event_id][text_id] = entry
    for event_id, allowed in DIALOGUE_USER_VALIDATED_ANDROID_ABSENT_MANUAL_IDS.items():
        actual = frozenset(result.get(event_id, {}))
        if actual != allowed:
            raise ValueError(
                f"Manual supplement ${event_id}: expected {sorted(allowed)}, got {sorted(actual)}"
            )
    return result


def _format_manual_supplement(
    source_document: dict, entry: dict, advances: dict[str, int]
) -> tuple[str, dict]:
    text_id = entry["id"]
    _, by_event = event_text_index(source_document)
    source_event = by_event[entry["event_id"]]
    source_token = next(token for token in source_event["tokens"] if token.get("id") == text_id)
    mapping = {
        "event_id": entry["event_id"],
        "snes_ids": [text_id],
        "android_ids": [],
        "confidence": "user_validated_android_absent_manual",
        "source_display": source_token.get("source", ""),
        "french_display": entry["text"],
    }
    values, report = format_dialogue_mapping(
        source_document, mapping, advances,
        allow_one_extra_page=False,
        use_physical_page_capacity=True,
        prefer_semantic_line_breaks=True,
    )
    report["manual_supplement"] = True
    report["manual_status"] = entry["status"]
    report["manual_reason"] = entry["reason"]
    return values[text_id], report


def _format_android_extra_page(
    source_document: dict, *, event_id: str, carrier_id: str, android_id: int,
    french: dict[int, str], advances: dict[str, int]
) -> tuple[str, dict]:
    by_id, _ = event_text_index(source_document)
    mapping = {
        "event_id": event_id,
        "snes_ids": [carrier_id],
        "android_ids": [android_id],
        "confidence": "user_validated_android_extra",
        "source_display": by_id[carrier_id]["source"],
        "french_display": french[android_id],
    }
    values, report = format_dialogue_mapping(
        source_document, mapping, advances,
        allow_one_extra_page=False,
        use_physical_page_capacity=True,
        prefer_semantic_line_breaks=True,
    )
    report["android_extra_page"] = True
    return values[carrier_id], report


def _parameterized_inn_prompt(english: dict[int, str], french: dict[int, str]) -> dict:
    android_id = 110
    en = english.get(android_id, "")
    fr = normalize_android_french(french.get(android_id, ""))
    if en != "One night is 5 GP. Want to stay?":
        raise ValueError("Parameterized inn template: Android EN 110 changed unexpectedly")
    if not fr.startswith("5"):
        raise ValueError("Parameterized inn template: Android FR 110 must start with the price 5")
    suffix = fr[1:]
    if not suffix.strip():
        raise ValueError("Parameterized inn template: empty French suffix")
    # Keep the dynamic numeric carrier supplied by the stock caller, then render
    # the Android-FR suffix.  One newline separates the sentence/prompt and the
    # trailing newline keeps the choice row on the next physical line.
    prompt_marker = "Voulez-vous rester dormir ?"
    if prompt_marker not in suffix:
        raise ValueError("Parameterized inn template: expected French prompt is absent")
    first, second = suffix.split(prompt_marker, 1)
    if second.strip():
        raise ValueError("Parameterized inn template: unexpected text after the French prompt")
    suffix = first.rstrip() + "\n" + prompt_marker + "\n"
    return {
        "android_id": android_id,
        "android_english": en,
        "android_french": fr,
        "prefix_translation": "",
        "suffix_translation": suffix,
        "prefix_id": "C9:CEA3",
        "suffix_id": "C9:CEB3",
    }


def _auto_metrics(source: str, candidate: str) -> dict[str, float]:
    """Fast deterministic lexical metrics used only by the automatic aligner."""
    try:
        from rapidfuzz import fuzz
    except ImportError as exc:  # pragma: no cover - user environment diagnostic
        raise ValueError(
            "Automatic dialogue alignment requires RapidFuzz; install requirements.txt"
        ) from exc

    source_norm = normalize_alignment_text(source)
    candidate_norm = normalize_alignment_text(candidate)
    if not source_norm or not candidate_norm:
        return {
            "character_similarity": 0.0,
            "source_token_coverage": 0.0,
            "lexical_score": 0.0,
        }
    character_similarity = float(fuzz.ratio(source_norm, candidate_norm))
    source_tokens = source_norm.split()
    candidate_tokens = set(candidate_norm.split())
    covered = sum(token in candidate_tokens for token in source_tokens)
    source_token_coverage = 100.0 * covered / len(source_tokens)
    lexical_score = character_similarity * 0.75 + source_token_coverage * 0.25
    return {
        "character_similarity": round(character_similarity, 1),
        "source_token_coverage": round(source_token_coverage, 1),
        "lexical_score": round(lexical_score, 1),
    }


def _auto_semantic(text: str) -> bool:
    return bool(normalize_alignment_text(text))


def _auto_make_session(event: dict, session_id: int, start: int, end: int) -> dict:
    tokens = event["tokens"]
    elements = []
    for token_index in range(start, end + 1):
        token = tokens[token_index]
        if token.get("type") == "text" and _auto_semantic(token.get("source", "")):
            elements.append(
                {
                    "token_index": token_index,
                    "id": token["id"],
                    "source": token["source"],
                }
            )
    return {
        "event_id": event["event_id"],
        "session_id": session_id,
        "start": start,
        "end": end,
        "tokens": tokens,
        "elements": elements,
    }


def _auto_sessions(document: dict) -> list[dict]:
    """Split SNES events at TEXT_OPEN/TEXT_CLOSE boundaries.

    This is deliberately a local ordering hint, not a claim that Android uses
    the same event structure. Text outside an explicit open/close pair remains a
    session of its own.
    """
    sessions: list[dict] = []
    for event in document.get("events", []):
        tokens = event.get("tokens", [])
        segment_start = 0
        session_id = 0

        def append_if_semantic(start: int, end: int) -> None:
            nonlocal session_id
            if end < start:
                return
            if any(
                token.get("type") == "text" and _auto_semantic(token.get("source", ""))
                for token in tokens[start : end + 1]
            ):
                sessions.append(_auto_make_session(event, session_id, start, end))
                session_id += 1

        for token_index, token in enumerate(tokens):
            if token.get("type") == "command" and token.get("name") == "TEXT_OPEN":
                append_if_semantic(segment_start, token_index - 1)
                segment_start = token_index + 1
            elif token.get("type") == "command" and token.get("name") == "TEXT_CLOSE":
                append_if_semantic(segment_start, token_index - 1)
                segment_start = token_index + 1
        append_if_semantic(segment_start, len(tokens) - 1)
    return sessions


def _auto_render_span(session: dict, first: int, last: int) -> str:
    """Render a SNES comparison span with adjacent dynamic-name placeholders.

    All text tokens, including punctuation-only tokens such as ``...``, act as
    placeholder boundaries. This prevents a PLAYER_NAME belonging to a preceding
    punctuation token from leaking into the next semantic phrase.
    """
    elements = session["elements"]
    tokens = session["tokens"]
    first_token = elements[first]["token_index"]
    last_token = elements[last]["token_index"]
    previous_text = next(
        (
            index
            for index in range(first_token - 1, session["start"] - 1, -1)
            if tokens[index].get("type") == "text"
        ),
        None,
    )
    next_text = next(
        (
            index
            for index in range(last_token + 1, session["end"] + 1)
            if tokens[index].get("type") == "text"
        ),
        None,
    )
    start = previous_text + 1 if previous_text is not None else session["start"]
    end = next_text - 1 if next_text is not None else session["end"]
    selected = {element["token_index"] for element in elements[first : last + 1]}
    chunks: list[str] = []
    for token_index in range(start, end + 1):
        token = tokens[token_index]
        if token.get("type") == "text":
            if token_index in selected or (
                first_token <= token_index <= last_token
                and not _auto_semantic(token.get("source", ""))
            ):
                chunks.append(token.get("source", ""))
        elif token.get("type") == "command" and token.get("name") == "PLAYER_NAME":
            try:
                player_index = int(token.get("args", "00").split()[0], 16)
            except (ValueError, IndexError):
                player_index = 0
            chunks.append(f"%S({player_index},0)")
    return "".join(chunks)


class _AutoCandidateIndex:
    def __init__(self, english: dict[int, str]):
        try:
            from rapidfuzz import process
        except ImportError as exc:  # pragma: no cover - user environment diagnostic
            raise ValueError(
                "Automatic dialogue alignment requires RapidFuzz; install requirements.txt"
            ) from exc
        self.process = process
        self.anchor_ids = [
            text_id for text_id in sorted(english) if normalize_alignment_text(english[text_id])
        ]
        self.anchor_pos = {text_id: pos for pos, text_id in enumerate(self.anchor_ids)}
        self.choices = {
            text_id: normalize_alignment_text(english[text_id]) for text_id in self.anchor_ids
        }
        self.exact: dict[str, list[int]] = {}
        for text_id, normalized in self.choices.items():
            self.exact.setdefault(normalized, []).append(text_id)
        self.english = english

    def rank(self, source: str, *, limit: int = 20) -> list[dict]:
        from rapidfuzz import fuzz

        normalized = normalize_alignment_text(source)
        if not normalized:
            return []
        candidate_ids: list[int] = list(self.exact.get(normalized, ()))
        candidate_ids.extend(
            item[2]
            for item in self.process.extract(
                normalized,
                self.choices,
                scorer=fuzz.ratio,
                limit=limit,
            )
        )
        seen: set[int] = set()
        ranked: list[dict] = []
        for text_id in candidate_ids:
            if text_id in seen:
                continue
            seen.add(text_id)
            ranked.append({"android_id": text_id, **_auto_metrics(source, self.english[text_id])})
        ranked.sort(
            key=lambda item: (item["lexical_score"], item["character_similarity"]),
            reverse=True,
        )
        return ranked


def _auto_seed(session: dict, element_index: int, index: _AutoCandidateIndex) -> tuple[dict | None, list[dict]]:
    source = _auto_render_span(session, element_index, element_index)
    normalized = normalize_alignment_text(source)
    ranked = index.rank(source)
    if not ranked:
        return None, ranked
    top = ranked[0]
    second = ranked[1]["lexical_score"] if len(ranked) > 1 else 0.0
    margin = top["lexical_score"] - second
    exact_ids = index.exact.get(normalized, ())
    length = len(normalized)
    reason = None
    if len(exact_ids) == 1 and length >= 8:
        reason = "unique_exact"
    elif (
        top["lexical_score"] >= 96
        and margin >= 12
        and length >= 16
        and top["source_token_coverage"] >= 90
    ):
        reason = "near_exact_unique"
    elif (
        top["lexical_score"] >= 90
        and margin >= 18
        and length >= 28
        and top["source_token_coverage"] >= 85
    ):
        reason = "strong_fuzzy_unique"
    if reason is None:
        return None, ranked
    return {
        **top,
        "margin": round(margin, 1),
        "normalized_length": length,
        "reason": reason,
    }, ranked


def _auto_choose_window(
    session: dict,
    seeds: list[dict | None],
    rankings: list[list[dict]],
    index: _AutoCandidateIndex,
) -> tuple[int, int, str] | None:
    strong = [
        (element_index, index.anchor_pos[seed["android_id"]], seed)
        for element_index, seed in enumerate(seeds)
        if seed is not None
    ]
    if strong:
        # Longest increasing local chain. Equal positions are permitted because
        # Android may merge multiple SNES fragments into one anchor.
        dynamic: list[tuple[float, list[int]]] = []
        for point_index, (element_index, anchor_position, seed) in enumerate(strong):
            best = (1.0 + seed["lexical_score"] / 100.0, [point_index])
            for previous_index, (
                previous_element,
                previous_position,
                _previous_seed,
            ) in enumerate(strong[:point_index]):
                if (
                    previous_element < element_index
                    and previous_position <= anchor_position
                    and anchor_position - previous_position <= 120
                ):
                    score = dynamic[previous_index][0] + 1.0 + seed["lexical_score"] / 100.0
                    if score > best[0]:
                        best = (score, dynamic[previous_index][1] + [point_index])
            dynamic.append(best)
        chain_indices = max(dynamic, key=lambda item: item[0])[1]
        positions = [strong[point_index][1] for point_index in chain_indices]
        padding = max(5, len(session["elements"]) * 2)
        return (
            max(0, min(positions) - padding),
            min(len(index.anchor_ids) - 1, max(positions) + padding),
            "seed_chain",
        )

    weak: list[tuple[int, int, dict]] = []
    for element_index, ranked in enumerate(rankings):
        if not ranked:
            continue
        top = ranked[0]
        second = ranked[1]["lexical_score"] if len(ranked) > 1 else 0.0
        length = len(normalize_alignment_text(_auto_render_span(session, element_index, element_index)))
        if (
            top["lexical_score"] >= 88
            and top["lexical_score"] - second >= 12
            and length >= 18
        ):
            weak.append((element_index, index.anchor_pos[top["android_id"]], top))
    if weak:
        _, center, _ = max(weak, key=lambda item: item[2]["lexical_score"])
        padding = max(8, len(session["elements"]) * 3)
        return (
            max(0, center - padding),
            min(len(index.anchor_ids) - 1, center + padding),
            "weak_center",
        )
    return None


def _auto_align_session(
    session: dict,
    window: tuple[int, int],
    index: _AutoCandidateIndex,
    english: dict[int, str],
) -> list[dict]:
    source_count = len(session["elements"])
    lo, hi = window
    android_ids = index.anchor_ids[lo : hi + 1]
    android_count = len(android_ids)
    negative = -1.0e18
    scores = [[negative] * (android_count + 1) for _ in range(source_count + 1)]
    previous = [[None] * (android_count + 1) for _ in range(source_count + 1)]
    scores[0][0] = 0.0
    for source_index in range(source_count + 1):
        for android_index in range(android_count + 1):
            current = scores[source_index][android_index]
            if current <= negative / 2:
                continue
            if source_index < source_count and current - 22 > scores[source_index + 1][android_index]:
                scores[source_index + 1][android_index] = current - 22
                previous[source_index + 1][android_index] = (
                    source_index,
                    android_index,
                    "skip_source",
                    1,
                    0,
                    None,
                )
            if android_index < android_count and current - 6 > scores[source_index][android_index + 1]:
                scores[source_index][android_index + 1] = current - 6
                previous[source_index][android_index + 1] = (
                    source_index,
                    android_index,
                    "skip_android",
                    0,
                    1,
                    None,
                )
            for source_width in range(1, min(3, source_count - source_index) + 1):
                source = _auto_render_span(
                    session,
                    source_index,
                    source_index + source_width - 1,
                )
                for android_width in range(1, min(3, android_count - android_index) + 1):
                    candidate_ids = android_ids[android_index : android_index + android_width]
                    candidate = " ".join(english[text_id] for text_id in candidate_ids)
                    evidence = _auto_metrics(source, candidate)
                    lexical = evidence["lexical_score"]
                    coverage = evidence["source_token_coverage"]
                    if lexical < 45:
                        continue
                    value = (
                        (lexical - 45) * 1.25
                        + (coverage - 50) * 0.15
                        - 4 * (source_width + android_width - 2)
                        - 3 * abs(source_width - android_width)
                    )
                    if lexical >= 95:
                        value += 18
                    if lexical >= 99:
                        value += 12
                    if current + value > scores[source_index + source_width][android_index + android_width]:
                        scores[source_index + source_width][android_index + android_width] = current + value
                        previous[source_index + source_width][android_index + android_width] = (
                            source_index,
                            android_index,
                            "match",
                            source_width,
                            android_width,
                            evidence,
                        )

    endpoint = max(range(android_count + 1), key=lambda position: scores[source_count][position])
    source_index = source_count
    android_index = endpoint
    operations: list[dict] = []
    while source_index or android_index:
        step = previous[source_index][android_index]
        if step is None:
            break
        old_source, old_android, operation, _source_width, _android_width, evidence = step
        if operation == "match":
            operations.append(
                {
                    "first_source": old_source,
                    "last_source": source_index - 1,
                    "first_android": old_android,
                    "last_android": android_index - 1,
                    "android_ids": android_ids[old_android:android_index],
                    "evidence": evidence,
                    "source_display": _auto_render_span(session, old_source, source_index - 1),
                }
            )
        source_index, android_index = old_source, old_android
    operations.reverse()
    return operations


def _auto_accept_session_blocks(
    session: dict,
    operations: list[dict],
    seeds: list[dict | None],
) -> list[dict]:
    matches = [operation for operation in operations if "android_ids" in operation]
    accepted: list[dict] = []
    for match_index, operation in enumerate(matches):
        evidence = operation["evidence"]
        lexical = evidence["lexical_score"]
        coverage = evidence["source_token_coverage"]
        length = len(normalize_alignment_text(operation["source_display"]))
        direct_seed = any(
            seeds[element_index] is not None
            and seeds[element_index]["android_id"] in operation["android_ids"]
            for element_index in range(operation["first_source"], operation["last_source"] + 1)
        )
        left_context = match_index > 0 and matches[match_index - 1]["last_android"] < operation["first_android"]
        right_context = (
            match_index + 1 < len(matches)
            and operation["last_android"] < matches[match_index + 1]["first_android"]
        )
        context = left_context or right_context
        confidence = None
        if direct_seed and lexical >= 70:
            confidence = "very_high_seeded"
        elif lexical >= 94 and coverage >= 88 and length >= 10:
            confidence = "very_high_lexical"
        elif lexical >= 85 and coverage >= 82 and length >= 14 and context:
            confidence = "very_high_context"
        elif lexical >= 78 and coverage >= 88 and length >= 24 and left_context and right_context:
            confidence = "very_high_bracketed"
        elif lexical >= 99 and length < 12 and left_context and right_context:
            confidence = "very_high_short_bracketed"
        if confidence is not None:
            accepted.append({**operation, "confidence": confidence})
    return accepted


def _auto_reviewed_records(source: dict[str, dict]) -> list[dict]:
    """Flatten all user-validated rounds into authoritative mapping blocks."""
    records: list[dict] = []
    for scene in DIALOGUE_PILOT_SCENES:
        for snes_id, android_id in scene["pairs"]:
            records.append(
                {
                    "event_id": scene["event_id"],
                    "snes_ids": [snes_id],
                    "android_ids": [android_id],
                    "confidence": "user_validated",
                    "provenance": "pilot",
                    "source_display": source[snes_id]["source"],
                }
            )
    for round_name, batch in (
        ("round2", DIALOGUE_REVIEW_ROUND2),
        ("round3", DIALOGUE_REVIEW_ROUND3),
        ("round4", DIALOGUE_REVIEW_ROUND4),
        ("round5", DIALOGUE_REVIEW_ROUND5),
        ("round6", DIALOGUE_REVIEW_ROUND6),
        ("round7", DIALOGUE_REVIEW_ROUND7),
        ("round8", DIALOGUE_REVIEW_ROUND8),
        ("round11", DIALOGUE_REVIEW_ROUND11),
        ("round18", DIALOGUE_REVIEW_ROUND18),
        ("round20", DIALOGUE_REVIEW_ROUND20),
        ("round21", DIALOGUE_REVIEW_ROUND21),
        ("round22", DIALOGUE_REVIEW_ROUND22),
    ):
        for scene in batch:
            for parts, android_ids, relation, _candidate_confidence, note in scene["units"]:
                snes_ids, source_display = render_snes_review_parts(parts, source, event_id=scene["event_id"])
                records.append(
                    {
                        "event_id": scene["event_id"],
                        "snes_ids": snes_ids,
                        "android_ids": list(android_ids),
                        "confidence": "very_high_structural_review" if round_name in {"round6", "round7", "round8", "round11", "round18", "round20", "round21", "round22"} else "user_validated",
                        "provenance": round_name,
                        "relation": relation,
                        "note": note,
                        "source_display": source_display,
                    }
                )
    # A later structural round may intentionally expand an earlier reviewed
    # block (round21 does this for $0167). Keep the latest whole reviewed unit
    # whenever source-ID ownership overlaps. Existing pre-round21 rounds do not
    # overlap, so this affects only explicitly superseded evidence.
    claimed: set[str] = set()
    latest_records: list[dict] = []
    for record in reversed(records):
        if claimed.intersection(record["snes_ids"]):
            continue
        latest_records.append(record)
        claimed.update(record["snes_ids"])
    latest_records.reverse()
    return latest_records


def _auto_french_unit(anchor_id: int, english: dict[int, str], french: dict[int, str]) -> tuple[str, ...]:
    return tuple(
        french[text_id]
        for text_id in english_anchor_interval(anchor_id, english)
        if french[text_id]
    )


def _auto_enrich_record(record: dict, english: dict[int, str], french: dict[int, str]) -> dict:
    android_ids = record.get("android_ids", [])
    unit_ids = android_anchor_units(tuple(android_ids), english) if android_ids else []
    french_ids = [text_id for text_id in unit_ids if french[text_id]]
    result = dict(record)
    result["android_unit_ids"] = unit_ids
    result["android_english_display"] = " ".join(english[text_id] for text_id in android_ids)
    result["french_nonempty_ids"] = french_ids
    result["french_display"] = " ".join(french[text_id] for text_id in french_ids)
    return result


def _auto_same_session_context_expand(
    sessions: list[dict],
    records: list[dict],
    index: _AutoCandidateIndex,
    english: dict[int, str],
) -> list[dict]:
    owner = {snes_id: record for record in records for snes_id in record["snes_ids"]}
    additions: list[dict] = []
    for _iteration in range(3):
        added = 0
        for session in sessions:
            elements = session["elements"]
            for element_index, element in enumerate(elements):
                if element["id"] in owner or element["id"] in DIALOGUE_FORCED_UNMAPPED:
                    continue
                source = _auto_render_span(session, element_index, element_index)
                normalized = normalize_alignment_text(source)
                length = len(normalized)
                previous_owner = None
                next_owner = None
                for search in range(element_index - 1, -1, -1):
                    if elements[search]["id"] in owner and owner[elements[search]["id"]].get("android_ids"):
                        previous_owner = owner[elements[search]["id"]]
                        break
                for search in range(element_index + 1, len(elements)):
                    if elements[search]["id"] in owner and owner[elements[search]["id"]].get("android_ids"):
                        next_owner = owner[elements[search]["id"]]
                        break
                pool: list[int] = []
                context_type = None
                if previous_owner and next_owner:
                    previous_position = max(index.anchor_pos[text_id] for text_id in previous_owner["android_ids"])
                    next_position = min(index.anchor_pos[text_id] for text_id in next_owner["android_ids"])
                    if previous_position <= next_position and next_position - previous_position <= 35:
                        pool = index.anchor_ids[previous_position : next_position + 1]
                        context_type = "bracketed"
                elif previous_owner:
                    position = max(index.anchor_pos[text_id] for text_id in previous_owner["android_ids"])
                    pool = index.anchor_ids[max(0, position - 1) : min(len(index.anchor_ids), position + 10)]
                    context_type = "after"
                elif next_owner:
                    position = min(index.anchor_pos[text_id] for text_id in next_owner["android_ids"])
                    pool = index.anchor_ids[max(0, position - 9) : min(len(index.anchor_ids), position + 2)]
                    context_type = "before"
                if not pool:
                    continue
                ranked = sorted(
                    (
                        {"android_id": text_id, **_auto_metrics(source, english[text_id])}
                        for text_id in pool
                    ),
                    key=lambda item: (item["lexical_score"], item["character_similarity"]),
                    reverse=True,
                )
                top = ranked[0]
                second_score = ranked[1]["lexical_score"] if len(ranked) > 1 else 0.0
                margin = top["lexical_score"] - second_score
                exact_local = normalize_alignment_text(english[top["android_id"]]) == normalized
                accept = False
                confidence = None
                if context_type == "bracketed":
                    if exact_local and length >= 4 and (
                        margin >= 5 or sum(item["lexical_score"] >= 99.9 for item in ranked) == 1
                    ):
                        accept = True
                        confidence = "very_high_local_exact"
                    elif top["lexical_score"] >= 88 and top["source_token_coverage"] >= 85 and length >= 14 and margin >= 7:
                        accept = True
                        confidence = "very_high_local_fuzzy"
                    elif top["lexical_score"] >= 82 and top["source_token_coverage"] >= 90 and length >= 24 and margin >= 10:
                        accept = True
                        confidence = "very_high_local_coverage"
                else:
                    if exact_local and length >= 8 and margin >= 10:
                        accept = True
                        confidence = "very_high_one_side_exact"
                    elif top["lexical_score"] >= 92 and top["source_token_coverage"] >= 90 and length >= 18 and margin >= 12:
                        accept = True
                        confidence = "very_high_one_side_fuzzy"
                if accept:
                    record = {
                        "event_id": session["event_id"],
                        "session_id": session["session_id"],
                        "snes_ids": [element["id"]],
                        "android_ids": [top["android_id"]],
                        "confidence": confidence,
                        "provenance": "automatic_local_context",
                        "source_display": source,
                        "lexical_evidence": {
                            key: top[key]
                            for key in ("character_similarity", "source_token_coverage", "lexical_score")
                        },
                        "candidate_margin": round(margin, 1),
                    }
                    owner[element["id"]] = record
                    records.append(record)
                    additions.append(record)
                    added += 1
        if not added:
            break
    return additions


def _auto_event_context_expand(
    sessions: list[dict],
    records: list[dict],
    index: _AutoCandidateIndex,
    english: dict[int, str],
) -> list[dict]:
    owner = {snes_id: record for record in records for snes_id in record["snes_ids"]}
    sessions_by_event: dict[str, list[dict]] = {}
    for session in sessions:
        sessions_by_event.setdefault(session["event_id"], []).append(session)

    def session_positions(session: dict) -> list[int]:
        positions: list[int] = []
        for element in session["elements"]:
            record = owner.get(element["id"])
            if record:
                positions.extend(
                    index.anchor_pos[text_id]
                    for text_id in record.get("android_ids", [])
                    if text_id in index.anchor_pos
                )
        return positions

    additions: list[dict] = []
    for _iteration in range(2):
        added = 0
        for event_sessions in sessions_by_event.values():
            for session_index, session in enumerate(event_sessions):
                if session_positions(session):
                    continue
                if not any(
                    element["id"] not in owner and element["id"] not in DIALOGUE_FORCED_UNMAPPED
                    for element in session["elements"]
                ):
                    continue
                previous = None
                following = None
                for search in range(session_index - 1, -1, -1):
                    positions = session_positions(event_sessions[search])
                    if positions:
                        previous = (search, positions)
                        break
                for search in range(session_index + 1, len(event_sessions)):
                    positions = session_positions(event_sessions[search])
                    if positions:
                        following = (search, positions)
                        break
                window = None
                context_type = None
                if previous and following:
                    low = max(previous[1])
                    high = min(following[1])
                    if (
                        low <= high
                        and high - low <= 45
                        and session_index - previous[0] <= 3
                        and following[0] - session_index <= 3
                    ):
                        window = (max(0, low - 2), min(len(index.anchor_ids) - 1, high + 2))
                        context_type = "event_bracketed"
                elif previous and session_index - previous[0] <= 2:
                    center = max(previous[1])
                    window = (max(0, center - 1), min(len(index.anchor_ids) - 1, center + 12))
                    context_type = "event_one_side"
                elif following and following[0] - session_index <= 2:
                    center = min(following[1])
                    window = (max(0, center - 12), min(len(index.anchor_ids) - 1, center + 1))
                    context_type = "event_one_side"
                if window is None:
                    continue
                operations = _auto_align_session(session, window, index, english)
                matches = [operation for operation in operations if "android_ids" in operation]
                for match_index, operation in enumerate(matches):
                    snes_ids = [
                        session["elements"][element_index]["id"]
                        for element_index in range(operation["first_source"], operation["last_source"] + 1)
                    ]
                    if any(snes_id in owner or snes_id in DIALOGUE_FORCED_UNMAPPED for snes_id in snes_ids):
                        continue
                    evidence = operation["evidence"]
                    lexical = evidence["lexical_score"]
                    coverage = evidence["source_token_coverage"]
                    length = len(normalize_alignment_text(operation["source_display"]))
                    confidence = None
                    if lexical >= 96 and coverage >= 90 and length >= 12:
                        confidence = "very_high_event_context_lexical"
                    elif context_type == "event_bracketed" and lexical >= 90 and coverage >= 88 and length >= 16:
                        confidence = "very_high_event_bracketed"
                    elif (
                        context_type == "event_bracketed"
                        and lexical >= 84
                        and coverage >= 92
                        and length >= 28
                        and (match_index > 0 or match_index + 1 < len(matches))
                    ):
                        confidence = "very_high_event_sequence"
                    if confidence is None:
                        continue
                    record = {
                        "event_id": session["event_id"],
                        "session_id": session["session_id"],
                        "snes_ids": snes_ids,
                        "android_ids": operation["android_ids"],
                        "confidence": confidence,
                        "provenance": "automatic_event_context",
                        "source_display": operation["source_display"],
                        "lexical_evidence": evidence,
                    }
                    records.append(record)
                    additions.append(record)
                    for snes_id in snes_ids:
                        owner[snes_id] = record
                    added += len(snes_ids)
        if not added:
            break
    return additions


def _auto_choice_near(session: dict, element: dict) -> bool:
    token_index = element["token_index"]
    for token in session["tokens"][
        max(session["start"], token_index - 2) : min(session["end"] + 1, token_index + 3)
    ]:
        if token.get("type") == "command" and token.get("name") in {
            "CHOICE_BEGIN",
            "CHOICE_OPTION",
            "CHOICE_END",
        }:
            return True
    return False


def _auto_add_exact_equivalences(
    sessions: list[dict],
    records: list[dict],
    index: _AutoCandidateIndex,
    english: dict[int, str],
    french: dict[int, str],
) -> list[dict]:
    owner = {snes_id: record for record in records for snes_id in record["snes_ids"]}
    additions: list[dict] = []
    for session in sessions:
        for element_index, element in enumerate(session["elements"]):
            snes_id = element["id"]
            if snes_id in owner or snes_id in DIALOGUE_FORCED_UNMAPPED:
                continue
            source = _auto_render_span(session, element_index, element_index)
            normalized = normalize_alignment_text(source)
            exact_ids = index.exact.get(normalized, [])
            if len(exact_ids) == 1:
                if len(normalized) >= 10 or _auto_choice_near(session, element):
                    record = {
                        "event_id": session["event_id"],
                        "session_id": session["session_id"],
                        "snes_ids": [snes_id],
                        "android_ids": list(exact_ids),
                        "confidence": "very_high_unique_exact",
                        "provenance": "automatic_exact",
                        "source_display": source,
                        "lexical_evidence": _auto_metrics(source, english[exact_ids[0]]),
                    }
                    records.append(record)
                    additions.append(record)
                    owner[snes_id] = record
            elif len(exact_ids) > 1:
                french_units = {_auto_french_unit(text_id, english, french) for text_id in exact_ids}
                if len(french_units) == 1 and next(iter(french_units), ()):
                    record = {
                        "event_id": session["event_id"],
                        "session_id": session["session_id"],
                        "snes_ids": [snes_id],
                        "android_ids": [],
                        "android_alternative_anchor_groups": [[text_id] for text_id in exact_ids],
                        "confidence": "very_high_equivalent_duplicate",
                        "provenance": "automatic_equivalent_duplicate",
                        "source_display": source,
                        "french_display": " ".join(next(iter(french_units))),
                    }
                    records.append(record)
                    additions.append(record)
                    owner[snes_id] = record
    return additions


def _auto_add_validated_alternatives(
    records: list[dict],
    source: dict[str, dict],
    english: dict[int, str],
    french: dict[int, str],
) -> None:
    owner = {snes_id for record in records for snes_id in record["snes_ids"]}
    for snes_id, alternatives in DIALOGUE_VALIDATED_ALTERNATIVE_GROUPS.items():
        if snes_id in owner:
            continue
        french_versions = []
        for group in alternatives:
            unit_ids = android_anchor_units(tuple(group), english)
            french_versions.append(tuple(french[text_id] for text_id in unit_ids if french[text_id]))
        if not french_versions or len(set(french_versions)) != 1:
            raise ValueError(f"Validated alternative Android groups diverged in French for {snes_id}")
        records.append(
            {
                "event_id": source[snes_id]["event_id"],
                "snes_ids": [snes_id],
                "android_ids": [],
                "android_alternative_anchor_groups": [list(group) for group in alternatives],
                "confidence": "user_validated_equivalent_alternatives",
                "provenance": "pilot_manual_review",
                "source_display": source[snes_id]["source"],
                "french_display": " ".join(french_versions[0]),
            }
        )


def _auto_unmapped_reason(
    snes_id: str,
    source_text: str,
    index: _AutoCandidateIndex,
    english: dict[int, str],
    french: dict[int, str],
) -> dict:
    if snes_id in DIALOGUE_FORCED_UNMAPPED:
        return {
            "reason": "validated_no_equivalent",
            "note": DIALOGUE_FORCED_UNMAPPED[snes_id],
            "top_candidates": index.rank(source_text, limit=3),
        }
    normalized = normalize_alignment_text(source_text)
    exact_ids = index.exact.get(normalized, [])
    if len(exact_ids) > 1:
        french_units = {_auto_french_unit(text_id, english, french) for text_id in exact_ids}
        if len(french_units) > 1:
            return {
                "reason": "ambiguous_exact_duplicates_with_different_french",
                "note": "Exact Android-English duplicates do not carry one identical French localization block.",
                "top_candidates": index.rank(source_text, limit=5),
            }
    ranked = index.rank(source_text, limit=3)
    if not ranked:
        return {
            "reason": "no_lexical_candidate",
            "note": "No non-empty Android-English lexical candidate.",
            "top_candidates": [],
        }
    top = ranked[0]
    second = ranked[1]["lexical_score"] if len(ranked) > 1 else 0.0
    margin = top["lexical_score"] - second
    if top["lexical_score"] >= 90 and margin < 8:
        reason = "strong_but_ambiguous"
        note = "Strong lexical similarity, but candidate separation is too small without decisive local context."
    elif top["lexical_score"] >= 80:
        reason = "insufficient_context_or_segmentation"
        note = "Plausible lexical candidate exists, but the conservative local-order/segmentation rules did not establish very-high confidence."
    else:
        reason = "insufficient_lexical_confidence"
        note = "Best Android-English candidate is too different to accept automatically."
    return {
        "reason": reason,
        "note": note,
        "top_candidates": ranked,
    }


def make_dialogue_auto_alignment(
    english: dict[int, str],
    french: dict[int, str],
    *,
    english_path: Path,
    french_path: Path,
) -> dict:
    """Align the complete canonical SNES dialogue inventory conservatively.

    This produces correspondence metadata only. It deliberately does not write
    unformatted Android French prose to ``translations/dialogues_french.json``.
    """
    require_parallel_scrtxt(english, french)
    document = json.loads(DIALOGUE_SOURCE.read_text(encoding="utf-8"))
    source = load_dialogue_text_entries()
    sessions = _auto_sessions(document)
    index = _AutoCandidateIndex(english)

    # 1. Generic automatic session pass, calibrated against but not seeded by
    # the reviewed rounds.
    auto_records: list[dict] = []
    for session in sessions:
        seeds: list[dict | None] = []
        rankings: list[list[dict]] = []
        for element_index in range(len(session["elements"])):
            seed, ranked = _auto_seed(session, element_index, index)
            seeds.append(seed)
            rankings.append(ranked)
        window = _auto_choose_window(session, seeds, rankings, index)
        if window is None:
            continue
        operations = _auto_align_session(session, (window[0], window[1]), index, english)
        for accepted in _auto_accept_session_blocks(session, operations, seeds):
            snes_ids = [
                session["elements"][element_index]["id"]
                for element_index in range(accepted["first_source"], accepted["last_source"] + 1)
            ]
            if any(snes_id in DIALOGUE_FORCED_UNMAPPED for snes_id in snes_ids):
                continue
            auto_records.append(
                {
                    "event_id": session["event_id"],
                    "session_id": session["session_id"],
                    "snes_ids": snes_ids,
                    "android_ids": accepted["android_ids"],
                    "confidence": accepted["confidence"],
                    "provenance": "automatic_session_alignment",
                    "source_display": accepted["source_display"],
                    "lexical_evidence": accepted["evidence"],
                }
            )

    # 2. User-validated rounds are authoritative. Auto blocks never override a
    # reviewed source ID; calibration check below also verifies that the generic
    # pass did not contradict any reviewed mapping it attempted.
    reviewed = _auto_reviewed_records(source)
    reviewed_ids = {snes_id for record in reviewed for snes_id in record["snes_ids"]}
    calibration_attempts = 0
    calibration_matches = 0
    calibration_conflicts: list[dict] = []
    reviewed_by_id = {snes_id: record for record in reviewed for snes_id in record["snes_ids"]}
    for record in auto_records:
        overlap = reviewed_ids.intersection(record["snes_ids"])
        if not overlap:
            continue
        calibration_attempts += len(overlap)
        for snes_id in overlap:
            expected = set(reviewed_by_id[snes_id]["android_ids"])
            observed = set(record["android_ids"])
            if expected.intersection(observed):
                calibration_matches += 1
            elif snes_id in DIALOGUE_REVIEWED_AUTO_OVERRIDES:
                # Round-specific structural evidence intentionally corrects the
                # generic lexical choice; reviewed records remain authoritative.
                continue
            else:
                calibration_conflicts.append(
                    {
                        "snes_id": snes_id,
                        "expected_android_ids": sorted(expected),
                        "automatic_android_ids": sorted(observed),
                    }
                )
    if calibration_conflicts:
        raise ValueError(
            "Automatic dialogue alignment contradicts user-validated calibration: "
            + ", ".join(item["snes_id"] for item in calibration_conflicts[:10])
        )
    records = [record for record in auto_records if not reviewed_ids.intersection(record["snes_ids"])]
    records.extend(reviewed)

    # 3. Expand only through already-established local/session context, then
    # through immediately neighboring dialogue sessions inside the same event.
    _auto_same_session_context_expand(sessions, records, index, english)
    _auto_event_context_expand(sessions, records, index, english)

    # 4. Preserve the user-reviewed pilot alternatives first, then handle other
    # safe exact cases. Exact duplicates are accepted automatically only if
    # every copy yields the same complete French localization interval.
    _auto_add_validated_alternatives(records, source, english, french)
    _auto_add_exact_equivalences(sessions, records, index, english, french)

    # Enforce single ownership for every semantic SNES text ID.
    owner: dict[str, dict] = {}
    unique_records: list[dict] = []
    for record in records:
        if any(snes_id in owner for snes_id in record["snes_ids"]):
            # This should only be possible if an automatic expansion overlaps a
            # previously accepted block; keeping first ownership is conservative.
            continue
        unique_records.append(record)
        for snes_id in record["snes_ids"]:
            owner[snes_id] = record

    source_order = {text_id: order for order, text_id in enumerate(source)}
    enriched_records: list[dict] = []
    for record in unique_records:
        if record.get("android_ids"):
            record = _auto_enrich_record(record, english, french)
        enriched_records.append(record)
    enriched_records.sort(key=lambda record: min(source_order[snes_id] for snes_id in record["snes_ids"]))

    semantic_ids = [text_id for text_id, entry in source.items() if _auto_semantic(entry["source"])]
    mapped_ids = {snes_id for record in enriched_records for snes_id in record["snes_ids"]}
    unmapped: list[dict] = []
    for snes_id in semantic_ids:
        if snes_id in mapped_ids:
            continue
        entry = source[snes_id]
        detail = _auto_unmapped_reason(snes_id, entry["source"], index, english, french)
        candidates = []
        for candidate in detail.pop("top_candidates"):
            android_id = candidate["android_id"]
            candidates.append(
                {
                    **candidate,
                    "android_english": english[android_id],
                    "french_unit_ids": [
                        text_id for text_id in english_anchor_interval(android_id, english) if french[text_id]
                    ],
                    "french_display": " ".join(
                        french[text_id]
                        for text_id in english_anchor_interval(android_id, english)
                        if french[text_id]
                    ),
                }
            )
        unmapped.append(
            {
                "event_id": entry["event_id"],
                "snes_id": snes_id,
                "source": entry["source"],
                **detail,
                "top_candidates": candidates,
            }
        )

    total_text_tokens = len(source)
    semantic_count = len(semantic_ids)
    semantic_id_set = set(semantic_ids)
    mapped_semantic_count = len(mapped_ids & semantic_id_set)
    mapped_total_count = len(mapped_ids)
    nonsemantic_count = total_text_tokens - semantic_count
    confidence_counts: dict[str, int] = {}
    provenance_counts: dict[str, int] = {}
    for record in enriched_records:
        width = len(record["snes_ids"])
        confidence_counts[record["confidence"]] = confidence_counts.get(record["confidence"], 0) + width
        provenance_counts[record["provenance"]] = provenance_counts.get(record["provenance"], 0) + width

    return {
        "format_version": 1,
        "status": "automatic_conservative_alignment",
        "source_asset": "dialogues.json",
        "android_english": {
            "path": "sources/android/scrtxt_en.bin",
            "sha256": sha256(english_path),
        },
        "android_french": {
            "path": "sources/android/scrtxt_fr.bin",
            "sha256": sha256(french_path),
        },
        "policy": {
            "english_identity_is_primary": True,
            "automatic_translation_generation": False,
            "accepted_automatic_confidence": "very_high only",
            "notes": [
                "Alignment operates on TEXT_OPEN/TEXT_CLOSE-local dialogue sessions rather than assuming whole-event Android monotonicity.",
                "Dynamic PLAYER_NAME commands are normalized to Android %S(index,0) placeholders for comparison only.",
                "French is recovered through complete English-anchor localization intervals after English identity is established.",
                "Exact duplicate Android locations may be translation-equivalent without having unique provenance; alternatives remain explicit.",
                "Unmatched or ambiguous SNES prose is retained as unmapped and is never forced onto the nearest candidate.",
                "SNES wrapping/page/layout formatting is a separate later step; Android French prose is not written to translations/dialogues_french.json here.",
            ],
        },
        "calibration": {
            "reviewed_source_id_count": len(reviewed_ids) + len(DIALOGUE_VALIDATED_ALTERNATIVE_GROUPS),
            "automatic_attempts_on_reviewed_ids": calibration_attempts,
            "automatic_matches_on_reviewed_ids": calibration_matches,
            "automatic_conflicts": 0,
        },
        "coverage": {
            "source_text_token_count": total_text_tokens,
            "semantic_source_id_count": semantic_count,
            "layout_or_punctuation_only_source_id_count": nonsemantic_count,
            "mapped_source_id_count": mapped_total_count,
            "mapped_semantic_source_id_count": mapped_semantic_count,
            "mapped_layout_or_punctuation_only_source_id_count": mapped_total_count - mapped_semantic_count,
            "unmapped_semantic_source_id_count": semantic_count - mapped_semantic_count,
            "mapped_semantic_percent": round(100.0 * mapped_semantic_count / semantic_count, 1),
            "confidence_source_id_counts": confidence_counts,
            "provenance_source_id_counts": provenance_counts,
        },
        "mappings": enriched_records,
        "unmapped": unmapped,
    }



def make_dialogue_format_selection(
    english: dict[int, str],
    french: dict[int, str],
    *,
    english_path: Path,
    french_path: Path,
    base_rom: bytes,
    selected_events: tuple[str, ...],
    group: str,
    status: str,
    report_event_key: str,
    extra_page_events: frozenset[str] = frozenset(),
) -> tuple[dict, dict]:
    """Format a conservative, explicit set of complete SNES dialogue events.

    Alignment is regenerated from the original Android sources. Every semantic
    text token in each selected event must be covered by an accepted mapping;
    mappings that cross unsupported commands, exceed the validated line budget,
    or cannot bind PLAYER_NAME exactly abort generation instead of producing a
    partially localized scene.
    """
    validate_base_rom(base_rom)
    alignment = make_dialogue_auto_alignment(
        english,
        french,
        english_path=english_path,
        french_path=french_path,
    )
    source_document = json.loads(DIALOGUE_SOURCE.read_text(encoding="utf-8"))
    source_text_by_id = {
        token["id"]: token.get("source", "")
        for event in source_document["events"]
        for token in event["tokens"]
        if token.get("type") == "text"
    }
    advances = make_dialogue_advances(base_rom)

    selected = [
        mapping
        for mapping in alignment["mappings"]
        if mapping["event_id"] in selected_events
    ]
    if not selected:
        raise ValueError("Dialogue format selection selected no accepted mappings")

    by_event = {event["event_id"]: event for event in source_document["events"]}
    mapped_ids_by_event: dict[str, set[str]] = {event_id: set() for event_id in selected_events}
    for mapping in selected:
        mapped_ids_by_event[mapping["event_id"]].update(mapping["snes_ids"])
    for event_id in selected_events:
        event = by_event.get(event_id)
        if event is None:
            raise ValueError(f"Unknown selected dialogue event ${event_id}")
        semantic_ids = {
            token["id"]
            for token in event["tokens"]
            if token.get("type") == "text" and _auto_semantic(token.get("source", ""))
        }
        missing = sorted(semantic_ids - mapped_ids_by_event[event_id])
        if missing:
            raise ValueError(
                f"Selected event ${event_id} is not completely aligned; semantic IDs missing: {missing}"
            )

    translations: dict[str, str] = {}
    formatted: list[dict] = []
    for mapping in selected:
        values, report = format_dialogue_mapping(
            source_document,
            mapping,
            advances,
            allow_one_extra_page=mapping["event_id"] in extra_page_events,
        )
        for text_id, text in values.items():
            if text_id in translations:
                raise ValueError(f"Dialogue formatter generated duplicate translation ID {text_id}")
            translations[text_id] = text
        formatted.append(report)

    source_order = {
        token["id"]: order
        for order, token in enumerate(
            token
            for event in source_document["events"]
            for token in event["tokens"]
            if token.get("type") == "text"
        )
    }
    ordered_entries = sorted(translations.items(), key=lambda item: source_order[item[0]])
    translation_document = make_dialogue_translation_document(ordered_entries, group=group)
    report_document = {
        "format_version": 1,
        "status": status,
        "source_alignment": "mappings/android/dialogues_auto.json (regenerated from Android EN/FR)",
        report_event_key: list(selected_events),
        "policy": {
            "alignment_must_already_be_accepted": True,
            "existing_event_commands_only": not bool(extra_page_events),
            "player_name_placeholders_must_match_exactly": True,
            "android_presentation_wraps_are_discarded": True,
            "snes_vwf_wrap_pixels": DIALOGUE_WRAP_PIXELS,
            "snes_parser_max_decoded_characters": DIALOGUE_WRAP_CHARS,
            "dynamic_player_name_width_assumption": "9 characters at worst-case validated glyph advance",
            "dynamic_player_name_character_assumption": "9 visible characters plus 1 conservative parser-safety unit per PLAYER_NAME",
            "source_explicit_visible_line_budget_is_not_exceeded": not bool(extra_page_events),
            "extra_page_events": sorted(extra_page_events),
            "generated_page_break_encoding": "WAIT $00 + TEXT_CLEAR",
        },
        "translation_entry_count": len(ordered_entries),
        "formatted_mappings": formatted,
    }
    if status != "runtime_validated":
        report_document["policy"]["selected_events_must_be_semantically_complete"] = True
    return translation_document, report_document


def make_dialogue_format_pilot(
    english: dict[int, str],
    french: dict[int, str],
    *,
    english_path: Path,
    french_path: Path,
    base_rom: bytes,
) -> tuple[dict, dict]:
    """Regenerate the runtime-validated $0107 formatting checkpoint."""
    return make_dialogue_format_selection(
        english,
        french,
        english_path=english_path,
        french_path=french_path,
        base_rom=base_rom,
        selected_events=DIALOGUE_FORMAT_PILOT_EVENTS,
        group="dialogues.android_format_pilot.event_0107",
        status="runtime_validated",
        report_event_key="pilot_events",
    )


def make_dialogue_format_batch1(
    english: dict[int, str],
    french: dict[int, str],
    *,
    english_path: Path,
    french_path: Path,
    base_rom: bytes,
) -> tuple[dict, dict]:
    """Generate the first complete-event expansion beyond the validated pilot."""
    return make_dialogue_format_selection(
        english,
        french,
        english_path=english_path,
        french_path=french_path,
        base_rom=base_rom,
        selected_events=DIALOGUE_FORMAT_BATCH1_EVENTS,
        group="dialogues.android_format_batch1",
        status="runtime_validated",
        report_event_key="batch_events",
    )


def make_dialogue_format_page_pilot(
    english: dict[int, str],
    french: dict[int, str],
    *,
    english_path: Path,
    french_path: Path,
    base_rom: bytes,
) -> tuple[dict, dict]:
    """Reproduce the runtime-validated sentence-aware $010F page checkpoint."""
    return make_dialogue_format_selection(
        english,
        french,
        english_path=english_path,
        french_path=french_path,
        base_rom=base_rom,
        selected_events=DIALOGUE_FORMAT_PAGE_PILOT_EVENTS,
        group="dialogues.android_format_page_pilot",
        status="runtime_validated",
        report_event_key="page_pilot_events",
        extra_page_events=DIALOGUE_FORMAT_EXTRA_PAGE_EVENTS,
    )


def make_dialogue_format_batch2(
    english: dict[int, str],
    french: dict[int, str],
    *,
    english_path: Path,
    french_path: Path,
    base_rom: bytes,
) -> tuple[dict, dict]:
    """Generate the first larger frozen event set using validated pagination."""
    return make_dialogue_format_selection(
        english,
        french,
        english_path=english_path,
        french_path=french_path,
        base_rom=base_rom,
        selected_events=DIALOGUE_FORMAT_BATCH2_EVENTS,
        group="dialogues.android_format_batch2",
        status="runtime_candidate",
        report_event_key="batch2_events",
        extra_page_events=DIALOGUE_FORMAT_BATCH2_EXTRA_PAGE_EVENTS,
    )



# WAIT $00 rolling-window cleanup is presentation-sensitive.  Keep automatic
# repairs restricted to the checkpoint that predates the round-8 partial-block
# review; newly exposed overlaps must be reviewed explicitly before changing
# stock persistence semantics.
# Do not rewrite stock WAIT $00 presentation automatically.  Exact visible
# carry-over after an interactive WAIT is a legitimate rolling-window state,
# not proof of duplicated dialogue.  Any future presentation change must be
# reviewed and implemented explicitly for that event.
DIALOGUE_RUNTIME_VALIDATED_WAIT00_OVERLAP_EVENTS = frozenset()


def _wait00_page_overlap_count(simulation) -> int:
    """Count exact visible-line carry-over after interactive WAIT $00 pauses.

    The stock dialogue box is a rolling three-line window, so WAIT $00 alone
    can leave the suffix of the previous state visible when later text starts.
    For the localized layout this is undesirable only when the *exact same
    rendered line(s)* appear again at the start of the next simulated state.
    Timed waits such as WAIT $04/$08 are deliberately ignored.
    """
    count = 0
    for box in simulation.boxes:
        pages = box.pages
        for index in range(1, len(pages)):
            previous_page = pages[index - 1]
            if previous_page.transition != "WAIT $00":
                continue
            previous = [line.text for line in previous_page.lines]
            current = [line.text for line in pages[index].lines]
            best = 0
            for size in range(1, min(len(previous), len(current), DIALOGUE_PAGE_LINES) + 1):
                overlap = previous[-size:]
                if overlap == current[:size] and any(line.strip() for line in overlap):
                    best = size
            count += best
    return count


def _wait00_repair_variants(event: dict, translations: dict[str, str]):
    """Yield conservative source-WAIT repairs for rolling-window duplicates.

    A candidate is never accepted merely from source shape: the caller must
    reserialize and resimulate it, and keep it only when the exact WAIT $00
    carry-over count decreases with no simulator regression.

    Two stock patterns are handled:
    - WAIT $00 -> later translated prose: clear before that prose;
    - WAIT $00 -> newline-only layout token -> end/close: suppress the orphan
      newline so it cannot create one final repeated rolling-window state.

    Intervening non-layout event commands are preserved in place. If a
    newline-only token exists before later prose, it becomes a clear-only text
    chunk so TEXT_CLEAR occurs at the original layout position.
    """
    tokens = event["tokens"]
    boundaries = {"WAIT", "TEXT_CLEAR", "TEXT_OPEN", "TEXT_CLOSE", "END"}
    for index, token in enumerate(tokens):
        if not (
            token.get("type") == "command"
            and token.get("name") == "WAIT"
            and token.get("args", "").strip().upper() == "00"
        ):
            continue

        layout_ids: list[str] = []
        next_text_id: str | None = None
        blocked = False
        for following in tokens[index + 1:]:
            kind = following.get("type")
            if kind == "command" and following.get("name") in boundaries:
                blocked = True
                break
            if kind != "text":
                continue
            text_id = following["id"]
            source = following.get("source", "")
            value = translations.get(text_id)
            if not source.strip():
                layout_ids.append(text_id)
                continue
            if value is not None and value.strip("\n\v\f "):
                next_text_id = text_id
                break
            # A semantic source token with no local translated bytes means the
            # binding is not simple enough for this layout-only cleanup.
            if _auto_semantic(source):
                blocked = True
                break

        if blocked and not next_text_id and not layout_ids:
            continue

        candidate = dict(translations)
        description: dict[str, object] = {
            "wait_token_index": index,
            "layout_text_ids": list(layout_ids),
            "next_text_id": next_text_id,
        }
        changed = False

        if next_text_id is not None:
            # Remove any newline-only rolling-scroll bytes. When such a token
            # exists, put the clear exactly there; otherwise prefix the next
            # translated prose chunk with the clear-only marker.
            if layout_ids:
                for layout_id in layout_ids:
                    candidate[layout_id] = ""
                candidate[layout_ids[0]] = "\v"
                description["strategy"] = "replace_layout_newline_with_text_clear"
                changed = True
            else:
                value = candidate[next_text_id]
                if not value.startswith("\v"):
                    candidate[next_text_id] = "\v" + value
                    description["strategy"] = "clear_before_next_translated_chunk"
                    changed = True
        elif layout_ids:
            # No later prose before the dialogue boundary: a newline after the
            # pause can only create a trailing rolling-window state. Drop it.
            for layout_id in layout_ids:
                if candidate.get(layout_id) != "":
                    candidate[layout_id] = ""
                    changed = True
            description["strategy"] = "drop_trailing_layout_newline"

        if changed:
            yield candidate, description



# Runtime-validated WAIT semantics: WAIT pauses without advancing the text
# cursor.  Earlier formatter/simulator revisions implicitly treated WAIT as a
# line terminator, so a small set of already-formatted scenes relied on a line
# break that was never serialized.  Materialize those intended boundaries as
# explicit dialogue NEWLINE bytes ($7F) while leaving every WAIT command intact.
#
# These are layout-only repairs: no Android/SNES semantic mapping is changed.
# ``prepend`` places NEWLINE at the start of the following text carrier;
# ``append`` places it at the end of the preceding carrier when the following
# visible object is PLAYER_NAME and there is no text carrier before it.
DIALOGUE_EXPLICIT_POST_WAIT_NEWLINES = {
    "0103": [
        ("C9:265A", "prepend"),
        ("C9:2715", "prepend"),
        ("C9:2715", "append"),
        ("C9:271E", "prepend"),
        ("C9:2723", "prepend"),
        ("C9:2740", "prepend"),
        ("C9:2753", "prepend"),
    ],
    "0106": [
        ("C9:28EB", "prepend"),
        ("C9:2ADB", "prepend"),
    ],
    "0136": [("C9:3E14", "prepend")],
    "0167": [
        ("C9:4C65", "append"),
        ("C9:4D1B", "prepend"),
    ],
    "016D": [("C9:4F84", "prepend")],
    "016E": [("C9:5233", "prepend")],
    "01C3": [("C9:70BF", "prepend")],
    "0228": [
        ("C9:9893", "prepend"),
        ("C9:98AC", "prepend"),
    ],
    "0259": [("C9:A1B3", "prepend")],
    "026A": [("C9:A4E9", "prepend_clear")],
    "055E": [
        ("CA:688A", "prepend"),
        ("CA:68FF", "prepend"),
    ],
    "059B": [("CA:76B2", "prepend")],
}


def _apply_explicit_post_wait_newlines(
    event_id: str,
    translations: dict[str, str],
    *,
    source_text_by_id: dict[str, str],
) -> list[dict]:
    """Materialize reviewed line boundaries after WAIT as literal $7F.

    A missing translation entry normally means "keep stock source bytes". For
    punctuation/layout-only carriers (notably $0103/$0228), create an explicit
    translation from the canonical source text before adding the newline so the
    visible punctuation itself remains byte-equivalent apart from the new $7F.
    """
    repairs: list[dict] = []
    for text_id, mode in DIALOGUE_EXPLICIT_POST_WAIT_NEWLINES.get(event_id, []):
        value = translations.get(text_id)
        if value is None:
            if text_id not in source_text_by_id:
                raise KeyError(f"Unknown post-WAIT newline carrier {text_id}")
            value = source_text_by_id[text_id]
        if mode == "prepend":
            if not value.startswith("\n"):
                value = "\n" + value
        elif mode == "append":
            if not value.endswith("\n"):
                value = value + "\n"
        elif mode == "prepend_clear":
            if not value.startswith("\v"):
                value = "\v" + value.lstrip("\n")
        else:
            raise ValueError(f"Unsupported post-WAIT newline mode {mode!r}")
        translations[text_id] = value
        repairs.append({
            "layout_text_id": text_id,
            "strategy": f"{mode}_explicit_newline_after_wait",
            "validation_status": "batch_test_candidate",
            "reason": "materialize line boundary previously assumed implicitly at WAIT",
        })
    return repairs

WAIT00_FRESH_PAGE_CLEAR_TARGETS = {
    "0106": ("C9:2994", "runtime_validated"),
    "00FB": ("C9:2447", "batch_test_candidate"),
    "0134": ("C9:3D03", "batch_test_candidate"),
    "016D": ("C9:4ECF", "batch_test_candidate"),
    "01CA": ("C9:743D", "batch_test_candidate"),
    "029C": ("C9:B1AD", "batch_test_candidate"),
    "03EE": ("C9:F1E5", "batch_test_candidate"),
    "04A1": ("CA:197E", "batch_test_candidate"),
    "04EA": ("CA:4A6B", "batch_test_candidate"),
    "03E9": ("C9:F036", "round18_batch_test_candidate"),
    "055E": ("CA:687A", "round18_batch_test_candidate"),
}


def _apply_targeted_wait00_fresh_page_clear(
    event_id: str, translations: dict[str, str]
) -> list[dict]:
    """Replace only audited newline-only carriers after the $0106 hazard shape.

    $0106/C9:2994 is runtime-validated. The eight round13 targets are the
    original detector batch; newly visible round18 mappings add two more exact
    detector matches ($03E9/$055E), also kept as explicit test candidates. The
    stock WAIT $00 bytes remain untouched and no generic WAIT carry-over rule is
    enabled.
    """
    target = WAIT00_FRESH_PAGE_CLEAR_TARGETS.get(event_id)
    if target is None:
        return []
    layout_id, validation_status = target
    if translations.get(layout_id) == "\v":
        return []
    translations[layout_id] = "\v"
    return [{
        "layout_text_id": layout_id,
        "strategy": "replace_stock_layout_newline_with_text_clear",
        "validation_status": validation_status,
        "reason": "fresh-page boundary for audited WAIT $00 third-line-scroll hazard",
    }]


def _repair_wait00_page_overlaps(
    *,
    base_rom: bytes,
    event: dict,
    translations: dict[str, str],
    font,
):
    """Greedily keep only simulator-proven reductions of WAIT $00 overlap."""
    from shared.dialogue_simulator import simulate_event

    current = dict(translations)
    simulation = simulate_event(
        base_rom,
        event,
        current,
        font=font,
        player_names={0: "000000000", 1: "000000000", 2: "000000000"},
    )
    repairs: list[dict] = []
    if event.get("event_id") not in DIALOGUE_RUNTIME_VALIDATED_WAIT00_OVERLAP_EVENTS:
        return current, simulation, repairs

    current_overlap = _wait00_page_overlap_count(simulation)
    if not current_overlap:
        return current, simulation, repairs

    # Rebuild candidate variants after every accepted repair because adding a
    # clear can change the simulated page sequence for later WAITs.
    progress = True
    while current_overlap and progress:
        progress = False
        for candidate, description in _wait00_repair_variants(event, current):
            candidate_simulation = simulate_event(
                base_rom,
                event,
                candidate,
                font=font,
                player_names={0: "000000000", 1: "000000000", 2: "000000000"},
            )
            blocking = [
                issue
                for issue in candidate_simulation.issues
                if issue.severity in {"error", "warning"}
            ]
            wraps = sum(
                line.implicit_wrap
                for box in candidate_simulation.boxes
                for page in box.pages
                for line in page.lines
            )
            candidate_overlap = _wait00_page_overlap_count(candidate_simulation)
            if blocking or wraps or candidate_overlap >= current_overlap:
                continue
            description = dict(description)
            description["overlap_lines_before"] = current_overlap
            description["overlap_lines_after"] = candidate_overlap
            repairs.append(description)
            current = candidate
            simulation = candidate_simulation
            current_overlap = candidate_overlap
            progress = True
            break

    return current, simulation, repairs


def _repair_live_line_scroll_risk_with_compact_wrap(
    *,
    base_rom: bytes,
    source_document: dict,
    event: dict,
    event_mappings: list[dict],
    translations: dict[str, str],
    reports: list[dict],
    advances: dict[str, int],
    french: dict[int, str],
    font,
    simulation,
):
    """Remove formatter-added line expansion that causes pre-WAIT live scroll.

    Semantic wrapping may split a short multi-sentence Android string even when
    the same official text fits in fewer physical lines.  If that extra aesthetic
    break makes the live dialogue cursor enter line 4 before the next player
    pause, retry mappings one at a time with the compact width-only wrapper.

    This never inserts WAIT/TEXT_CLEAR and never changes semantic mappings.  A
    compact candidate is kept only when independent resimulation strictly
    reduces ``UNPAUSED_LIVE_LINE_SCROLL_RISK`` with no error, warning, or
    implicit wrap.  This is the generalized form of the runtime-observed $0083
    failure where ``Gestahl : Ha ! Imbécile !`` had been expanded from one safe
    line to two and pushed the following utterance through the rolling window.
    """
    from shared.dialogue_simulator import simulate_event

    def risk_count(sim) -> int:
        return sum(issue.code == "UNPAUSED_LIVE_LINE_SCROLL_RISK" for issue in sim.issues)

    original = dict(translations)
    original_reports = list(reports)
    original_simulation = simulation
    if any(
        token.get("type") == "command" and token.get("name") in {"CHOICE_BEGIN", "CHOICE_END"}
        for token in event.get("tokens", [])
    ):
        return original, original_reports, original_simulation, []

    current = dict(translations)
    current_reports = list(reports)
    current_simulation = simulation
    current_risk = risk_count(current_simulation)
    repairs: list[dict] = []
    if not current_risk:
        return current, current_reports, current_simulation, repairs

    progress = True
    while current_risk and progress:
        progress = False
        for mapping in event_mappings:
            if str(mapping.get("relation", "")).startswith("choice"):
                continue
            try:
                compact_values, compact_report = _format_mass_mapping(
                    source_document,
                    mapping,
                    advances,
                    base_rom=base_rom,
                    french=french,
                    prefer_semantic_line_breaks=False,
                )
            except ValueError:
                continue

            matching_report_index = next((
                index for index, report in enumerate(current_reports)
                if report.get("snes_ids") == mapping.get("snes_ids")
                and report.get("android_ids") == mapping.get("android_ids")
            ), None)
            if matching_report_index is None:
                continue
            old_report = current_reports[matching_report_index]
            if compact_report.get("formatted_markup") == old_report.get("formatted_markup"):
                continue

            candidate = dict(current)
            candidate.update(compact_values)
            # Preserve the small set of already audited event-level layout
            # decisions; compacting one mapping must not silently remove them.
            _apply_user_reviewed_fragment_spacing(event["event_id"], candidate)
            _apply_targeted_wait00_fresh_page_clear(event["event_id"], candidate)
            _apply_explicit_post_wait_newlines(
                event["event_id"], candidate,
                source_text_by_id={
                    token["id"]: token.get("source", "")
                    for token in event.get("tokens", [])
                    if token.get("type") == "text"
                },
            )
            _apply_wait_semantics_layout_compat(event["event_id"], candidate)

            try:
                candidate_simulation = simulate_event(
                    base_rom,
                    event,
                    candidate,
                    font=font,
                    player_names={0: "000000000", 1: "000000000", 2: "000000000"},
                )
            except ValueError:
                continue
            blocking = [
                issue for issue in candidate_simulation.issues
                if issue.severity in {"error", "warning"}
            ]
            wraps = sum(
                line.implicit_wrap
                for box in candidate_simulation.boxes
                for page in box.pages
                for line in page.lines
            )
            candidate_risk = risk_count(candidate_simulation)
            if blocking or wraps or candidate_risk >= current_risk:
                continue

            updated_report = dict(compact_report)
            updated_report["live_line_compact_fallback"] = True
            updated_report["live_line_risk_before"] = current_risk
            updated_report["live_line_risk_after"] = candidate_risk
            current_reports[matching_report_index] = updated_report
            repairs.append({
                "snes_ids": mapping.get("snes_ids", []),
                "android_ids": mapping.get("android_ids", []),
                "strategy": "compact_semantic_wrap_to_preserve_pre_wait_window",
                "formatted_markup_before": old_report.get("formatted_markup"),
                "formatted_markup_after": compact_report.get("formatted_markup"),
                "risk_before": current_risk,
                "risk_after": candidate_risk,
            })
            current = candidate
            current_simulation = candidate_simulation
            current_risk = candidate_risk
            progress = True
            break

    # A partial reduction is not enough to justify changing presentation.  If
    # compacting cannot eliminate the complete pre-WAIT live-scroll defect,
    # keep the original event and leave it TO REVIEW.
    if current_risk:
        return original, original_reports, original_simulation, []
    return current, current_reports, current_simulation, repairs


def _repair_pure_unpaused_scroll(
    *,
    base_rom: bytes,
    source_document: dict,
    event: dict,
    event_mappings: list[dict],
    translations: dict[str, str],
    reports: list[dict],
    advances: dict[str, int],
    font,
    simulation,
):
    """Try one semantic extra page when the only failure is four-line scroll.

    Complete events can overflow the rolling three-line window even though
    each Android/SNES mapping is independently within its own line budget.  Do
    not invent a cross-mapping split: only retry one existing mapping with the
    already validated WAIT $00 + TEXT_CLEAR pagination, and only when that
    mapping has a real sentence/semantic boundary.  Keep a candidate solely if
    the independently serialized event resimulates with no errors, warnings or
    implicit wraps.

    This deliberately ignores events that also contain unsupported layout
    commands or runtime wraps; those need separate structural work.
    """
    from shared.dialogue_simulator import simulate_event

    blocking = [
        issue for issue in simulation.issues
        if issue.severity in {"error", "warning"}
    ]
    wraps = sum(
        line.implicit_wrap
        for box in simulation.boxes
        for page in box.pages
        for line in page.lines
    )
    if wraps or not blocking or {issue.code for issue in blocking} != {"UNPAUSED_SCROLL"}:
        return translations, reports, simulation, []

    clean_candidates: list[tuple[tuple[int, int, int], dict, list[dict], object, dict]] = []
    for mapping_index, mapping in enumerate(event_mappings):
        try:
            values, mapping_report = format_dialogue_mapping(
                source_document,
                mapping,
                advances,
                allow_one_extra_page=True,
                use_physical_page_capacity=True,
                prefer_semantic_line_breaks=True,
                force_one_extra_page=True,
            )
        except ValueError:
            continue
        if mapping_report.get("page_break_strategy") not in {
            "semantic_hard_boundary",
            "sentence_boundary",
        }:
            continue

        candidate = dict(translations)
        candidate.update(values)
        candidate_simulation = simulate_event(
            base_rom,
            event,
            candidate,
            font=font,
            player_names={0: "000000000", 1: "000000000", 2: "000000000"},
        )
        candidate_blocking = [
            issue for issue in candidate_simulation.issues
            if issue.severity in {"error", "warning"}
        ]
        candidate_wraps = sum(
            line.implicit_wrap
            for box in candidate_simulation.boxes
            for page in box.pages
            for line in page.lines
        )
        if candidate_blocking or candidate_wraps:
            continue

        content_counts = [
            sum(bool(line.text.strip()) for line in page.lines)
            for box in candidate_simulation.boxes
            for page in box.pages
        ]
        nonempty_counts = [count for count in content_counts if count]
        final_fullness = nonempty_counts[-1] if nonempty_counts else 0
        minimum_fullness = min(nonempty_counts) if nonempty_counts else 0
        # Prefer a fuller final page (avoid a one-line orphan tail), then the
        # best minimum page fill, then the earliest safe mapping boundary.
        score = (final_fullness, minimum_fullness, -mapping_index)

        candidate_reports = [
            mapping_report if report.get("snes_ids") == mapping.get("snes_ids") else report
            for report in reports
        ]
        repair = {
            "snes_ids": list(mapping.get("snes_ids", [])),
            "android_ids": list(mapping.get("android_ids", [])),
            "strategy": mapping_report.get("page_break_strategy"),
            "page_line_counts": mapping_report.get("page_line_counts", []),
        }
        clean_candidates.append(
            (score, candidate, candidate_reports, candidate_simulation, repair)
        )

    if not clean_candidates:
        return translations, reports, simulation, []
    _, candidate, candidate_reports, candidate_simulation, repair = max(
        clean_candidates, key=lambda item: item[0]
    )
    return candidate, candidate_reports, candidate_simulation, [repair]


def _repair_cross_mapping_sentence_overflow(
    *,
    base_rom: bytes,
    source_document: dict,
    event: dict,
    event_mappings: list[dict],
    translations: dict[str, str],
    reports: list[dict],
    advances: dict[str, int],
    font,
    simulation,
):
    """Repair one proven sentence boundary spanning adjacent mappings.

    A few complete Android mappings correspond to consecutive SNES text tokens
    that the runtime concatenates on the same parser line even though the first
    localized mapping ends a complete sentence and the next starts a new one.
    Only handle the narrow failure signature where that concatenation causes an
    implicit parser wrap (soft or decoded-capacity hard wrap) plus a four-line
    unpaused scroll.  The candidate must:

    * begin at an adjacent mapping boundary separated only by proven
      ``OP_32``/``OP_34`` actor actions and ``COMPLETE_ACTIONS``;
    * follow terminal sentence punctuation in the previous localized mapping;
    * add exactly one explicit newline before the next localized mapping;
    * paginate that next mapping only at a proven semantic/sentence boundary;
    * independently resimulate with no errors, warnings, or implicit wraps.

    Unsupported commands or any other simulator defect keep the event excluded.
    """
    from shared.dialogue_simulator import simulate_event

    blocking = [
        issue for issue in simulation.issues
        if issue.severity in {"error", "warning"}
    ]
    codes = {issue.code for issue in blocking}
    if codes not in ({
        "IMPLICIT_RUNTIME_WRAP",
        "UNPAUSED_SCROLL",
    }, {
        "IMPLICIT_RUNTIME_HARD_WRAP",
        "UNPAUSED_SCROLL",
    }):
        return translations, reports, simulation, []

    clean_candidates: list[tuple[tuple[int, int, int], dict, list[dict], object, dict]] = []
    for mapping_index in range(1, len(event_mappings)):
        previous = event_mappings[mapping_index - 1]
        mapping = event_mappings[mapping_index]

        # The validated cross-mapping repair is only safe across the same
        # event-interruption family already proven for component 06: actor
        # actions followed by COMPLETE_ACTIONS. Do not bridge arbitrary event
        # commands merely because a candidate happens to resimulate.
        by_id, by_event = event_text_index(source_document)
        previous_indexes = [by_id[text_id]["token_index"] for text_id in previous.get("snes_ids", [])]
        mapping_indexes = [by_id[text_id]["token_index"] for text_id in mapping.get("snes_ids", [])]
        if not previous_indexes or not mapping_indexes:
            continue
        previous_last = max(previous_indexes)
        mapping_first = min(mapping_indexes)
        if mapping_first <= previous_last:
            continue
        bridge = event["tokens"][previous_last + 1:mapping_first]
        if not bridge:
            continue
        bridge_names = []
        bridge_safe = True
        for token in bridge:
            if token.get("type") != "command":
                bridge_safe = False
                break
            name = token.get("name")
            if name not in {"OP_32", "OP_34", "COMPLETE_ACTIONS"}:
                bridge_safe = False
                break
            bridge_names.append(name)
        if not bridge_safe or not ({"OP_32", "OP_34"} & set(bridge_names)):
            continue

        previous_text = "".join(
            translations.get(text_id, "") for text_id in previous.get("snes_ids", [])
        ).rstrip(" \n\f\v")
        if not previous_text or previous_text[-1] not in ".!?…":
            continue

        try:
            values, mapping_report = format_dialogue_mapping(
                source_document,
                mapping,
                advances,
                allow_one_extra_page=True,
                use_physical_page_capacity=True,
                prefer_semantic_line_breaks=True,
                force_one_extra_page=True,
            )
        except ValueError:
            continue
        if mapping_report.get("page_break_strategy") not in {
            "semantic_hard_boundary",
            "sentence_boundary",
        }:
            continue

        first_id = next(
            (text_id for text_id in mapping.get("snes_ids", []) if text_id in values),
            None,
        )
        if first_id is None or values[first_id].startswith(("\n", "\f", "\v")):
            continue

        values = dict(values)
        values[first_id] = "\n" + values[first_id]
        candidate = dict(translations)
        candidate.update(values)
        candidate_simulation = simulate_event(
            base_rom,
            event,
            candidate,
            font=font,
            player_names={0: "000000000", 1: "000000000", 2: "000000000"},
        )
        candidate_blocking = [
            issue for issue in candidate_simulation.issues
            if issue.severity in {"error", "warning"}
        ]
        candidate_wraps = sum(
            line.implicit_wrap
            for box in candidate_simulation.boxes
            for page in box.pages
            for line in page.lines
        )
        if candidate_blocking or candidate_wraps:
            continue

        mapping_report = dict(mapping_report)
        mapping_report["formatted_markup"] = "\n" + mapping_report["formatted_markup"]
        mapping_report["inserted_cross_mapping_sentence_break"] = True
        mapping_report["formatted_entries"] = [
            {
                "id": entry["id"],
                "text": values.get(entry["id"], entry["text"]),
            }
            for entry in mapping_report.get("formatted_entries", [])
        ]

        content_counts = [
            sum(bool(line.text.strip()) for line in page.lines)
            for box in candidate_simulation.boxes
            for page in box.pages
        ]
        nonempty_counts = [count for count in content_counts if count]
        final_fullness = nonempty_counts[-1] if nonempty_counts else 0
        minimum_fullness = min(nonempty_counts) if nonempty_counts else 0
        score = (final_fullness, minimum_fullness, -mapping_index)

        candidate_reports = [
            mapping_report if report.get("snes_ids") == mapping.get("snes_ids") else report
            for report in reports
        ]
        repair = {
            "previous_snes_ids": list(previous.get("snes_ids", [])),
            "snes_ids": list(mapping.get("snes_ids", [])),
            "android_ids": list(mapping.get("android_ids", [])),
            "strategy": mapping_report.get("page_break_strategy"),
            "page_line_counts": mapping_report.get("page_line_counts", []),
            "inserted_leading_newline": True,
            "boundary_commands": bridge_names,
        }
        clean_candidates.append(
            (score, candidate, candidate_reports, candidate_simulation, repair)
        )

    if not clean_candidates:
        return translations, reports, simulation, []
    _, candidate, candidate_reports, candidate_simulation, repair = max(
        clean_candidates, key=lambda item: item[0]
    )
    return candidate, candidate_reports, candidate_simulation, [repair]




def _is_safe_text_free_returning_call(base_rom: bytes, token: dict) -> bool:
    """Prove one OP_20..OP_27 call is linear, text-free and returning."""
    name = token.get("name", "")
    match = re.fullmatch(r"OP_2([0-7])", name)
    if match is None:
        return False
    args = token.get("args", "").split()
    if len(args) != 1:
        return False
    target_event_id = (int(match.group(1), 16) << 8) | int(args[0], 16)
    try:
        called = parse_event(base_rom, target_event_id)
    except ValueError:
        return False
    if any(item.get("type") == "text" for item in called.get("tokens", [])):
        return False
    allowed = {"OP_31", "OP_32", "OP_34", "COMPLETE_ACTIONS", "WAIT", "RETURN", "END"}
    names = [
        item.get("name")
        for item in called.get("tokens", [])
        if item.get("type") == "command"
    ]
    if any(item not in allowed for item in names):
        return False
    return len(names) >= 2 and names[-2:] == ["RETURN", "END"]


def _is_safe_sound_only_returning_call(base_rom: bytes, token: dict) -> bool:
    """Prove one OP_20..OP_27 call only plays sound and returns."""
    name = token.get("name", "")
    match = re.fullmatch(r"OP_2([0-7])", name)
    if match is None:
        return False
    args = token.get("args", "").split()
    if len(args) != 1:
        return False
    target_event_id = (int(match.group(1), 16) << 8) | int(args[0], 16)
    try:
        called = parse_event(base_rom, target_event_id)
    except ValueError:
        return False
    if any(item.get("type") == "text" for item in called.get("tokens", [])):
        return False
    names = [
        item.get("name")
        for item in called.get("tokens", [])
        if item.get("type") == "command"
    ]
    return names == ["PLAY_SOUND", "RETURN", "END"]


def _format_mapping_across_shake_effect_boundary(
    source_document: dict,
    mapping: dict,
    advances: dict[str, int],
    *,
    base_rom: bytes,
    prefer_semantic_line_breaks: bool,
) -> tuple[dict[str, str], dict]:
    """Split two sentences around the stock timed shake-effect sequence.

    This deliberately recognizes only the exact linear shape already present
    in event $01C3: sound call, vertical-shake effect, timed WAIT, stop-shake
    effect, sound call. The commands are preserved byte-for-byte; only the two
    mapped text slots are formatted independently around the existing effect.
    """
    snes_ids = mapping.get("snes_ids", [])
    if len(snes_ids) != 2:
        raise ValueError("Shake-effect boundary requires exactly two SNES text IDs")
    if "%S(" in mapping.get("source_display", "") or "%S(" in mapping.get("french_display", ""):
        raise ValueError("Shake-effect boundary does not handle PLAYER_NAME")

    by_id, by_event = event_text_index(source_document)
    metas = [by_id.get(text_id) for text_id in snes_ids]
    if any(meta is None for meta in metas):
        raise ValueError("Shake-effect boundary references an unknown SNES text ID")
    assert all(meta is not None for meta in metas)
    if len({meta["event_id"] for meta in metas}) != 1:
        raise ValueError("Shake-effect boundary cannot cross events")
    indexes = [meta["token_index"] for meta in metas]
    if indexes != sorted(indexes):
        raise ValueError("Shake-effect boundary IDs are not in token order")

    event = by_event[metas[0]["event_id"]]
    if any(
        token.get("type") == "command"
        and token.get("name") in {"CHOICE_BEGIN", "CHOICE_OPTION", "CHOICE_END"}
        for token in event["tokens"]
    ):
        raise ValueError("Shake-effect boundary stays disabled in choice events")

    bridge = event["tokens"][indexes[0] + 1:indexes[1]]
    if len(bridge) != 5 or any(token.get("type") != "command" for token in bridge):
        raise ValueError("Shake-effect boundary does not match the proven five-command shape")
    first_call, shake_on, wait, shake_off, second_call = bridge
    if not _is_safe_sound_only_returning_call(base_rom, first_call):
        raise ValueError("Shake-effect boundary first call is not a proven sound-only return")
    if shake_on.get("name") != "OP_2D" or shake_on.get("args") != "02":
        raise ValueError("Shake-effect boundary does not start the proven vertical-shake effect")
    if wait.get("name") != "WAIT" or wait.get("args") in {None, "00"}:
        raise ValueError("Shake-effect boundary requires its existing timed WAIT")
    if shake_off.get("name") != "OP_2D" or shake_off.get("args") != "04":
        raise ValueError("Shake-effect boundary does not stop the proven shake effect")
    if not _is_safe_sound_only_returning_call(base_rom, second_call):
        raise ValueError("Shake-effect boundary second call is not a proven sound-only return")

    def complete_source(text: str) -> bool:
        compact = re.sub(r"\s+", " ", text.strip())
        return re.search(r"(?:\.{3}|[.!?…])[”\"»')\]]*$", compact) is not None

    if not complete_source(by_id[snes_ids[0]]["source"]):
        raise ValueError("Shake-effect boundary requires a complete source sentence before the effect")

    french = normalize_android_french(mapping.get("french_display", ""))
    boundaries = _sentence_boundary_positions(french)
    if not boundaries:
        raise ValueError("Shake-effect boundary requires a complete French sentence boundary")

    candidates = []
    for boundary in boundaries:
        pieces = [french[:boundary].strip(), french[boundary:].strip()]
        if any(not piece for piece in pieces):
            continue
        translations: dict[str, str] = {}
        reports: list[dict] = []
        valid = True
        for text_id, piece in zip(snes_ids, pieces, strict=True):
            local = dict(mapping)
            local["snes_ids"] = [text_id]
            local["source_display"] = by_id[text_id]["source"]
            local["french_display"] = piece
            try:
                values, report = format_dialogue_mapping(
                    source_document,
                    local,
                    advances,
                    allow_one_extra_page=True,
                    use_physical_page_capacity=True,
                    prefer_semantic_line_breaks=prefer_semantic_line_breaks,
                    allow_two_extra_pages=True,
                )
            except ValueError:
                valid = False
                break
            translations.update(values)
            reports.append(report)
        if not valid:
            continue
        line_counts = [sum(report.get("page_line_counts", [])) for report in reports]
        score = (max(line_counts, default=0), abs(line_counts[0] - line_counts[1]), boundary)
        candidates.append((score, pieces, translations, reports))

    if not candidates:
        raise ValueError("Shake-effect boundary found no clean sentence distribution")
    _, pieces, translations, reports = min(candidates, key=lambda item: item[0])
    return translations, {
        "event_id": mapping["event_id"],
        "snes_ids": snes_ids,
        "android_ids": mapping.get("android_ids", []),
        "confidence": mapping.get("confidence"),
        "source_display": mapping.get("source_display", ""),
        "android_french_raw": mapping.get("french_display", ""),
        "android_french_normalized": french,
        "existing_shake_effect_sentence_distribution": True,
        "preserved_wait_arg": wait.get("args"),
        "boundary_proof": [
            {"name": token.get("name"), "args": token.get("args")}
            for token in bridge
        ],
        "distributed_french_parts": pieces,
        "shake_effect_parts": reports,
        "formatted_entries": [
            {"id": text_id, "text": translations[text_id]}
            for text_id in snes_ids
        ],
    }


def _format_reviewed_sequence_block_with_android_extra(
    source_document: dict,
    mapping: dict,
    advances: dict[str, int],
    *,
    french: dict[int, str],
    prefer_semantic_line_breaks: bool,
) -> tuple[dict[str, str], dict]:
    """Rebind the reviewed 4-anchor/3-statement sequence-block shape.

    The reviewed mapping explicitly records an Android-only extra anchor and a
    stock SNES newline carrier. This fallback is intentionally shape-driven:
    four SNES IDs must be ``semantic / layout-only / semantic / semantic``, the
    three intervening command bridges must be exactly WAIT $00, actor action,
    and WAIT $00 + TEXT_CLEAR, and the first French Android unit must be only a
    speaker hesitation. In that proven shape, the first two Android French
    units form the first SNES statement, while units three and four populate
    the remaining two semantic slots. The stock layout-only token is untouched.
    """
    if mapping.get("confidence") != "user_validated":
        raise ValueError("Reviewed sequence-block fallback requires user-validated alignment")
    if mapping.get("relation") != "sequence_block_with_android_extra":
        raise ValueError("Reviewed sequence-block fallback requires its explicit relation")
    snes_ids = mapping.get("snes_ids", [])
    android_ids = mapping.get("android_ids", [])
    if len(snes_ids) != 4 or len(android_ids) != 4:
        raise ValueError("Reviewed sequence-block fallback requires four SNES and Android IDs")
    if "%S(" in mapping.get("source_display", "") or "%S(" in mapping.get("french_display", ""):
        raise ValueError("Reviewed sequence-block fallback does not handle PLAYER_NAME")

    by_id, by_event = event_text_index(source_document)
    metas = [by_id.get(text_id) for text_id in snes_ids]
    if any(meta is None for meta in metas):
        raise ValueError("Reviewed sequence-block fallback references an unknown SNES text ID")
    assert all(meta is not None for meta in metas)
    if len({meta["event_id"] for meta in metas}) != 1:
        raise ValueError("Reviewed sequence-block fallback cannot cross events")
    indexes = [meta["token_index"] for meta in metas]
    if indexes != sorted(indexes):
        raise ValueError("Reviewed sequence-block fallback IDs are not in token order")
    if re.search(r"[A-Za-z0-9À-ÖØ-öø-ÿŒœ]", by_id[snes_ids[1]]["source"]):
        raise ValueError("Reviewed sequence-block fallback middle token must be layout-only")

    event = by_event[metas[0]["event_id"]]
    if any(
        token.get("type") == "command"
        and token.get("name") in {"CHOICE_BEGIN", "CHOICE_OPTION", "CHOICE_END"}
        for token in event["tokens"]
    ):
        raise ValueError("Reviewed sequence-block fallback stays disabled in choice events")

    bridges = [event["tokens"][a + 1:b] for a, b in zip(indexes, indexes[1:])]
    signatures = [
        [(token.get("name"), token.get("args")) for token in bridge]
        for bridge in bridges
    ]
    expected = [
        [("WAIT", "00")],
        [("OP_32", "04 4C"), ("COMPLETE_ACTIONS", None)],
        [("WAIT", "00"), ("TEXT_CLEAR", None)],
    ]
    if signatures != expected:
        raise ValueError("Reviewed sequence-block fallback does not match its proven stock command shape")

    def complete_sentence(text: str) -> bool:
        compact = re.sub(r"\s+", " ", text.strip())
        return re.search(r"(?:\.{3}|[.!?…])[”\"»')\]]*$", compact) is not None

    for text_id in (snes_ids[0], snes_ids[2], snes_ids[3]):
        if not complete_sentence(by_id[text_id]["source"]):
            raise ValueError("Reviewed sequence-block fallback requires complete source statements")

    chunks = [normalize_android_french(french[text_id]) for text_id in android_ids]
    if any(not chunk for chunk in chunks):
        raise ValueError("Reviewed sequence-block fallback requires four non-empty French anchors")
    if re.fullmatch(r"[^:\n]{1,30}\s*:\s*(?:\.{3}|…)", chunks[0]) is None:
        raise ValueError("Reviewed sequence-block fallback requires a speaker-only hesitation first anchor")
    if any(not complete_sentence(chunk) for chunk in chunks[1:]):
        raise ValueError("Reviewed sequence-block fallback requires complete remaining French anchors")

    pieces = [f"{chunks[0]} {chunks[1]}", chunks[2], chunks[3]]
    semantic_ids = [snes_ids[0], snes_ids[2], snes_ids[3]]
    translations: dict[str, str] = {}
    reports: list[dict] = []
    for text_id, piece in zip(semantic_ids, pieces, strict=True):
        local = dict(mapping)
        local["snes_ids"] = [text_id]
        local["source_display"] = by_id[text_id]["source"]
        local["french_display"] = piece
        values, report = format_dialogue_mapping(
            source_document,
            local,
            advances,
            allow_one_extra_page=True,
            use_physical_page_capacity=True,
            prefer_semantic_line_breaks=prefer_semantic_line_breaks,
            allow_two_extra_pages=True,
        )
        translations.update(values)
        reports.append(report)

    return translations, {
        "event_id": mapping["event_id"],
        "snes_ids": snes_ids,
        "android_ids": android_ids,
        "confidence": mapping.get("confidence"),
        "relation": mapping.get("relation"),
        "source_display": mapping.get("source_display", ""),
        "android_french_raw": mapping.get("french_display", ""),
        "reviewed_sequence_block_distribution": True,
        "preserved_stock_carrier_id": snes_ids[1],
        "boundary_proof": signatures,
        "distributed_french_parts": pieces,
        "reviewed_sequence_block_parts": reports,
        "formatted_entries": [
            {"id": text_id, "text": translations[text_id]}
            for text_id in semantic_ids
        ],
    }


def _format_mapping_across_nonsemantic_action_carrier(
    source_document: dict,
    mapping: dict,
    advances: dict[str, int],
    *,
    base_rom: bytes,
    prefer_semantic_line_breaks: bool,
) -> tuple[dict[str, str], dict]:
    """Split two complete localized sentences around one stock layout carrier.

    This is for the narrow three-slot shape ``semantic / layout-only / semantic``.
    The middle source token is preserved stock and untranslated. Boundaries may
    contain only proven actor-action commands plus a clean-ROM call whose callee
    is independently text-free, branch-free and returning. No WAIT, PLAYER_NAME
    or choice command is accepted here.
    """
    snes_ids = mapping.get("snes_ids", [])
    if len(snes_ids) != 3:
        raise ValueError("Nonsemantic-action carrier requires exactly three SNES text IDs")
    if "%S(" in mapping.get("source_display", "") or "%S(" in mapping.get("french_display", ""):
        raise ValueError("Nonsemantic-action carrier does not handle PLAYER_NAME")

    by_id, by_event = event_text_index(source_document)
    metas = [by_id.get(text_id) for text_id in snes_ids]
    if any(meta is None for meta in metas):
        raise ValueError("Nonsemantic-action carrier references an unknown SNES text ID")
    assert all(meta is not None for meta in metas)
    if len({meta["event_id"] for meta in metas}) != 1:
        raise ValueError("Nonsemantic-action carrier cannot cross events")
    indexes = [meta["token_index"] for meta in metas]
    if indexes != sorted(indexes):
        raise ValueError("Nonsemantic-action carrier IDs are not in token order")
    if re.search(r"[A-Za-z0-9À-ÖØ-öø-ÿŒœ]", by_id[snes_ids[1]]["source"]):
        raise ValueError("Nonsemantic-action carrier middle token is semantic text")

    event = by_event[metas[0]["event_id"]]
    if any(
        token.get("type") == "command"
        and token.get("name") in {"CHOICE_BEGIN", "CHOICE_OPTION", "CHOICE_END"}
        for token in event["tokens"]
    ):
        raise ValueError("Nonsemantic-action carrier stays disabled in choice events")

    boundary_proof: list[list[dict]] = []
    saw_action = False
    for first, second in zip(indexes, indexes[1:]):
        bridge = event["tokens"][first + 1:second]
        if not bridge:
            raise ValueError("Nonsemantic-action carrier found an empty command boundary")
        proof: list[dict] = []
        for token in bridge:
            if token.get("type") != "command":
                raise ValueError("Nonsemantic-action carrier crosses non-command event data")
            name = token.get("name")
            if name in {"OP_32", "OP_34", "COMPLETE_ACTIONS"}:
                if name in {"OP_32", "OP_34"}:
                    saw_action = True
                proof.append({"name": name, "args": token.get("args")})
            elif _is_safe_text_free_returning_call(base_rom, token):
                saw_action = True
                proof.append({"name": name, "args": token.get("args"), "text_free_returning_call": True})
            else:
                raise ValueError(f"Nonsemantic-action carrier crosses unsupported command {name!r}")
        boundary_proof.append(proof)
    if not saw_action:
        raise ValueError("Nonsemantic-action carrier requires a proven actor action")

    def complete_source(text: str) -> bool:
        compact = re.sub(r"\s+", " ", text.strip())
        return re.search(r"(?:\.{3}|[.!?…])[”\"»')\]]*$", compact) is not None

    if not complete_source(by_id[snes_ids[0]]["source"]) or not complete_source(by_id[snes_ids[2]]["source"]):
        raise ValueError("Nonsemantic-action carrier requires complete source sentences on both semantic slots")

    french = normalize_android_french(mapping.get("french_display", ""))
    boundaries = _sentence_boundary_positions(french)
    if not boundaries:
        raise ValueError("Nonsemantic-action carrier requires a complete French sentence boundary")

    candidates = []
    for boundary in boundaries:
        pieces = [french[:boundary].strip(), french[boundary:].strip()]
        if any(not piece for piece in pieces):
            continue
        translations: dict[str, str] = {}
        reports: list[dict] = []
        valid = True
        for text_id, piece in zip((snes_ids[0], snes_ids[2]), pieces, strict=True):
            local = dict(mapping)
            local["snes_ids"] = [text_id]
            local["source_display"] = by_id[text_id]["source"]
            local["french_display"] = piece
            try:
                values, report = format_dialogue_mapping(
                    source_document,
                    local,
                    advances,
                    allow_one_extra_page=True,
                    use_physical_page_capacity=True,
                    prefer_semantic_line_breaks=prefer_semantic_line_breaks,
                    allow_two_extra_pages=True,
                )
            except ValueError:
                valid = False
                break
            translations.update(values)
            reports.append(report)
        if not valid:
            continue
        line_counts = [sum(report.get("page_line_counts", [])) for report in reports]
        score = (max(line_counts, default=0), abs(line_counts[0] - line_counts[1]), boundary)
        candidates.append((score, pieces, translations, reports))

    if not candidates:
        raise ValueError("Nonsemantic-action carrier found no clean sentence distribution")
    _, pieces, translations, reports = min(candidates, key=lambda item: item[0])
    report = {
        "event_id": mapping["event_id"],
        "snes_ids": snes_ids,
        "android_ids": mapping.get("android_ids", []),
        "confidence": mapping.get("confidence"),
        "source_display": mapping.get("source_display", ""),
        "android_french_raw": mapping.get("french_display", ""),
        "android_french_normalized": french,
        "nonsemantic_action_carrier_distribution": True,
        "preserved_stock_carrier_id": snes_ids[1],
        "boundary_proof": boundary_proof,
        "distributed_french_parts": pieces,
        "nonsemantic_action_carrier_parts": reports,
        "formatted_entries": [
            {"id": text_id, "text": translations[text_id]}
            for text_id in (snes_ids[0], snes_ids[2])
            if text_id in translations
        ],
    }
    return translations, report

def _strip_duplicated_trailing_player_context(
    event: dict,
    event_mappings: list[dict],
    *,
    base_rom: bytes,
) -> tuple[list[dict], list[dict]]:
    """Drop only a PLAYER_NAME placeholder duplicated by the next mapping.

    The aligner's ``source_display`` may use a dynamic name between two text
    tokens as context for *both* neighboring mappings. When the canonical event
    contains only that PLAYER_NAME command between the two mapped token ranges,
    and both source displays prove the same suffix/prefix placeholder, the first
    mapping may ignore the duplicate context if its French does not contain it.
    The actual SNES PLAYER_NAME remains owned by the following mapping and is
    never edited. A bridge may also contain an event call only when the clean-ROM
    callee is independently proven text-free, branch-free and returning.
    """
    if len(event_mappings) < 2:
        return event_mappings, []
    token_index_by_id = {
        token["id"]: index
        for index, token in enumerate(event.get("tokens", []))
        if token.get("type") == "text"
    }
    ordered = sorted(
        event_mappings,
        key=lambda mapping: min(token_index_by_id[text_id] for text_id in mapping["snes_ids"]),
    )
    result = [dict(mapping) for mapping in ordered]
    repairs: list[dict] = []


    def bridge_player_context(bridge: list[dict]) -> tuple[str, list[dict]] | None:
        placeholders: list[str] = []
        proof: list[dict] = []
        all_player = True
        proved_call = False
        for token in bridge:
            if token.get("type") != "command":
                return None
            name = token.get("name")
            if name == "PLAYER_NAME":
                args = token.get("args", "00").split()
                if not args:
                    return None
                placeholders.append(f"%S({int(args[0], 16)},0)")
                proof.append({"name": name, "args": token.get("args")})
                continue
            all_player = False
            if name in {"WAIT", "TEXT_CLEAR", "OP_32", "OP_34", "COMPLETE_ACTIONS"}:
                proof.append({"name": name, "args": token.get("args")})
            elif _is_safe_text_free_returning_call(base_rom, token):
                proved_call = True
                proof.append({"name": name, "args": token.get("args"), "text_free_returning_call": True})
            else:
                return None
        if not placeholders or (not all_player and not proved_call):
            return None
        return "".join(placeholders), proof

    for index in range(len(result) - 1):
        current = result[index]
        following = result[index + 1]
        current_last = max(token_index_by_id[text_id] for text_id in current["snes_ids"])
        following_first = min(token_index_by_id[text_id] for text_id in following["snes_ids"])
        if following_first <= current_last:
            continue
        bridge = event["tokens"][current_last + 1:following_first]
        if not bridge:
            continue
        bridge_context = bridge_player_context(bridge)
        if bridge_context is None:
            continue
        suffix, bridge_proof = bridge_context
        current_source = current.get("source_display", "")
        following_source = following.get("source_display", "")
        if not current_source.endswith(suffix) or not following_source.startswith(suffix):
            continue
        if current.get("french_display", "").rstrip().endswith(suffix):
            continue
        current["source_display"] = current_source[:-len(suffix)]
        current["ignored_duplicated_trailing_player_context"] = suffix
        repairs.append(
            {
                "snes_ids": current.get("snes_ids", []),
                "following_snes_ids": following.get("snes_ids", []),
                "player_context": suffix,
                "bridge_proof": bridge_proof,
            }
        )
    return result, repairs



def _format_structurally_reviewed_choice_prompt(
    source_document: dict,
    mapping: dict,
    advances: dict[str, int],
) -> tuple[dict[str, str], dict]:
    """Format one reviewed Android prompt that precedes a stock choice row.

    Android commonly stores prompt and options as separate localization slots,
    while SNES may keep ``prompt + newline + (`` in one token or place ``(``
    in a tiny stock carrier after ``TEXT_X``. Preserve those stock choice-row
    structures rather than treating the parenthesis as translated prose.

    Compact wrapping is used only for this proven prompt/choice relation. A
    two-line prompt keeps the stock third-line choice row. If official French
    needs exactly three lines, a validated WAIT $00 + TEXT_CLEAR is inserted
    after the complete prompt so the selectable row starts on a fresh page.
    """
    if mapping.get("confidence") != "very_high_structural_review":
        raise ValueError("Choice-prompt split requires structural-review confidence")
    if mapping.get("relation") != "choice_prompt_split":
        raise ValueError("Choice-prompt split requires its explicit relation")
    snes_ids = mapping.get("snes_ids", [])
    if len(snes_ids) != 1:
        raise ValueError("Choice-prompt split requires exactly one SNES text ID")

    by_id, by_event = event_text_index(source_document)
    meta = by_id.get(snes_ids[0])
    if meta is None:
        raise ValueError("Choice-prompt split references an unknown SNES text ID")
    source = meta["source"]
    event = by_event[meta["event_id"]]
    token_index = meta["token_index"]

    embedded_match = re.search(r"(\n[ ]*\()$", source)
    shape: str | None = None
    spaces_and_paren = ""
    structural_suffix = None
    if embedded_match is not None:
        if token_index + 1 >= len(event["tokens"]):
            raise ValueError("Embedded choice prompt has no following token")
        following = event["tokens"][token_index + 1]
        if not (following.get("type") == "command" and following.get("name") == "CHOICE_BEGIN"):
            raise ValueError("Embedded choice prompt is not immediately followed by CHOICE_BEGIN")
        shape = "embedded_parenthesis"
        structural_suffix = embedded_match.group(1)
        spaces_and_paren = structural_suffix[1:]
    elif source.endswith("\n"):
        # Proven alternate SNES shape: prompt token, TEXT_X, tiny '(' carrier,
        # CHOICE_BEGIN. The padding byte emitted after a generated page break is
        # harmless because TEXT_X immediately resets the decoded-row position.
        if token_index + 3 < len(event["tokens"]):
            text_x = event["tokens"][token_index + 1]
            carrier = event["tokens"][token_index + 2]
            choice_begin = event["tokens"][token_index + 3]
            if (
                text_x.get("type") == "command"
                and text_x.get("name") == "TEXT_X"
                and carrier.get("type") in {"text", "ending_text"}
                and re.fullmatch(r"[ ]*\(", carrier.get("source", "")) is not None
                and choice_begin.get("type") == "command"
                and choice_begin.get("name") == "CHOICE_BEGIN"
            ):
                shape = "separate_parenthesis_after_text_x"
                structural_suffix = carrier.get("source", "")
    if shape is None:
        raise ValueError("Choice-prompt split does not match a proven stock choice-row shape")

    values, report = format_dialogue_mapping(
        source_document,
        mapping,
        advances,
        allow_one_extra_page=True,
        use_physical_page_capacity=True,
        prefer_semantic_line_breaks=False,
        allow_two_extra_pages=True,
    )
    text_id = snes_ids[0]
    if text_id not in values:
        raise ValueError("Choice-prompt split did not format its SNES text token")
    line_count = len(report.get("line_widths_pixels", []))
    page_line_counts = report.get("page_line_counts", []) or [line_count]
    final_page_lines = page_line_counts[-1]

    if final_page_lines <= 2:
        if shape == "embedded_parenthesis":
            values[text_id] = values[text_id].rstrip("\n") + "\n" + spaces_and_paren
        choice_transition = "stock_newline"
    elif final_page_lines == 3:
        french = normalize_android_french(mapping.get("french_display", "")).rstrip()
        if re.search(r"(?:\.{3}|[.!?…])[”\"»')\]]*$", french) is None:
            raise ValueError("Full choice-prompt page needs a complete sentence before pagination")
        if shape == "embedded_parenthesis":
            values[text_id] = values[text_id].rstrip("\n") + "\f" + spaces_and_paren
        else:
            # A trailing generated page break is deliberate here: the following
            # stock TEXT_X then starts on a genuinely fresh decoded row before
            # the separate '(' carrier is rendered.
            values[text_id] = values[text_id].rstrip("\n") + "\f"
        choice_transition = "WAIT $00 + TEXT_CLEAR"
    else:
        raise ValueError("Choice prompt final page exceeds the three-line physical capacity")

    report = dict(report)
    report["structural_choice_prompt_split"] = True
    report["choice_prompt_stock_shape"] = shape
    report["preserved_choice_opening_suffix"] = structural_suffix
    report["choice_row_transition"] = choice_transition
    report["formatted_markup"] = values[text_id]
    report["formatted_entries"] = [{"id": text_id, "text": values[text_id]}]
    if choice_transition != "stock_newline":
        report["inserted_page_break_count"] = report.get("inserted_page_break_count", 0) + 1
        report["page_break_encoding"] = "WAIT $00 + TEXT_CLEAR"
        report["page_break_strategy"] = "choice_prompt_complete_sentence"
    return values, report


def _format_structurally_reviewed_choice_destination_list(
    source_document: dict,
    mapping: dict,
    advances: dict[str, int],
    *,
    french: dict[int, str],
) -> tuple[dict[str, str], dict]:
    """Rebuild a SNES numbered destination list from split Android labels.

    Some Cannon Travel scripts store ``1:/2:/3:`` and all destination names in
    one SNES text token, while Android stores the three destination labels in
    adjacent localization records.  The numeric prefixes are layout/selection
    structure, not translated prose, so preserve them from the proven SNES
    shape and insert only the Android French labels.
    """
    if mapping.get("confidence") != "very_high_structural_review":
        raise ValueError("Choice destination list requires structural-review confidence")
    if mapping.get("relation") != "choice_destination_list":
        raise ValueError("Choice destination list requires its explicit relation")
    snes_ids = mapping.get("snes_ids", [])
    android_ids = mapping.get("android_ids", [])
    if len(snes_ids) != 1 or len(android_ids) != 3:
        raise ValueError("Choice destination list requires one SNES ID and three Android IDs")

    by_id, _ = event_text_index(source_document)
    meta = by_id.get(snes_ids[0])
    if meta is None:
        raise ValueError("Choice destination list references an unknown SNES text ID")
    source = meta.get("source", "")
    match = re.fullmatch(r"([ ]*)1:.*\n([ ]*)2:.*\n([ ]*)3:.*", source)
    if match is None:
        raise ValueError("Choice destination list does not match the proven 1:/2:/3: SNES shape")

    labels = [normalize_android_french(french[text_id]).strip() for text_id in android_ids]
    if any(not label or "\n" in label or "\f" in label or "\v" in label for label in labels):
        raise ValueError("Choice destination list requires three single-line French labels")
    rebuilt = "\n".join(
        f"{match.group(index)}{index}:{labels[index - 1]}"
        for index in (1, 2, 3)
    )
    lines = rebuilt.split("\n")
    widths = [sum(advances.get(char, 8) for char in line) for line in lines]
    parser_units = [len(line) for line in lines]
    if any(width > DIALOGUE_WRAP_PIXELS for width in widths):
        raise ValueError("Choice destination list exceeds the 240px line target")
    if any(units > DIALOGUE_WRAP_CHARS for units in parser_units):
        raise ValueError("Choice destination list exceeds parser line capacity")
    text_id = snes_ids[0]
    values = {text_id: rebuilt}
    report = {
        "event_id": mapping["event_id"],
        "snes_ids": snes_ids,
        "android_ids": android_ids,
        "confidence": mapping.get("confidence"),
        "source_display": source,
        "android_french_raw": " ".join(french[text_id] for text_id in android_ids),
        "android_french_normalized": " ".join(labels),
        "layout_markup_before_wrap": rebuilt,
        "layout_hints": [],
        "formatted_markup": rebuilt,
        "line_widths_pixels": widths,
        "line_decoded_character_counts": parser_units,
        "line_parser_unit_counts": parser_units,
        "leading_text_x_position": None,
        "leading_text_x_padding_pixels": 0,
        "leading_text_x_parser_units": 0,
        "source_visible_line_budget": 3,
        "effective_line_budget": 3,
        "physical_page_capacity_mode": True,
        "semantic_line_break_preferences": False,
        "page_line_counts": [3],
        "inserted_page_break_count": 0,
        "inserted_leading_clear": False,
        "page_break_encoding": None,
        "page_break_strategy": None,
        "event_level_forced_page_break": False,
        "formatted_entries": [{"id": text_id, "text": rebuilt}],
        "structural_choice_destination_list": True,
        "preserved_numeric_prefixes": [f"{match.group(i)}{i}:" for i in (1, 2, 3)],
    }
    return values, report



def _format_cannon_travel_piece(
    source_document: dict,
    mapping: dict,
    advances: dict[str, int],
    *,
    prefer_semantic_line_breaks: bool,
) -> tuple[dict[str, str], dict]:
    """Redistribute Android's merged Cannon Travel response over stock SNES slots.

    Android appends the common boarding sentence to each destination response,
    while SNES calls shared sub-event $00FC for that sentence.  Reviewed round20
    mappings therefore format either the response prefix or the common suffix,
    preserving the original event call structure instead of duplicating prose.
    """
    relation = mapping.get("relation")
    if relation not in {"cannon_response_prefix", "cannon_common_boarding_suffix"}:
        raise ValueError("Not a Cannon Travel split relation")
    english = re.sub(r"\s+", " ", mapping.get("android_english_display", "").replace("_", " ")).strip()
    if "Just slide into the cannon!" not in english:
        raise ValueError("Cannon Travel split requires the Android shared boarding sentence")
    french_full = normalize_android_french(mapping.get("french_display", "")).strip()
    suffix_match = re.search(r"On saute dans le canon, et c'est parti\s*!\s*$", french_full)
    if suffix_match is None:
        raise ValueError("Cannon Travel split requires the proven common French boarding suffix")
    prefix = french_full[:suffix_match.start()].rstrip(" _")
    suffix = suffix_match.group(0).strip()
    piece = prefix if relation == "cannon_response_prefix" else suffix
    if not piece:
        raise ValueError("Cannon Travel split produced an empty French piece")
    local = dict(mapping)
    local["french_display"] = piece
    values, report = format_dialogue_mapping(
        source_document,
        local,
        advances,
        allow_one_extra_page=True,
        use_physical_page_capacity=True,
        prefer_semantic_line_breaks=prefer_semantic_line_breaks,
        allow_two_extra_pages=True,
    )
    report = dict(report)
    report["structural_cannon_travel_split"] = relation
    report["android_merged_french"] = french_full
    report["distributed_french_piece"] = piece
    return values, report



def _format_wait_player_resegmentation(
    source_document: dict,
    mapping: dict,
    advances: dict[str, int],
    *,
    prefer_semantic_line_breaks: bool,
) -> tuple[dict[str, str], dict]:
    """Redistribute one Android turn around stock WAIT + PLAYER_NAME.

    The accepted $0167 structure is text, WAIT $00, PLAYER_NAME(1), text.
    Android 1058/1059 puts localized prose on both sides of that dynamic name.
    Keep both SNES commands byte-for-byte and split only the exact normalized
    Android French at its existing %S(1,0) placeholder.
    """
    if mapping.get("confidence") != "very_high_structural_review":
        raise ValueError("WAIT/PLAYER_NAME resegmentation requires structural-review confidence")
    if mapping.get("relation") != "wait_player_resegmentation":
        raise ValueError("WAIT/PLAYER_NAME resegmentation requires its explicit relation")
    snes_ids = mapping.get("snes_ids", [])
    android_ids = mapping.get("android_ids", [])
    if len(snes_ids) != 2 or len(android_ids) != 2:
        raise ValueError("WAIT/PLAYER_NAME resegmentation requires two SNES and two Android IDs")

    by_id, by_event = event_text_index(source_document)
    first = by_id.get(snes_ids[0])
    second = by_id.get(snes_ids[1])
    if first is None or second is None or first["event_id"] != second["event_id"]:
        raise ValueError("WAIT/PLAYER_NAME resegmentation references invalid SNES carriers")
    if first["event_id"] != mapping.get("event_id"):
        raise ValueError("WAIT/PLAYER_NAME resegmentation crosses events")
    event = by_event[first["event_id"]]
    bridge = event["tokens"][first["token_index"] + 1:second["token_index"]]
    if len(bridge) != 2:
        raise ValueError("WAIT/PLAYER_NAME resegmentation requires exactly two bridge commands")
    wait, player = bridge
    if wait.get("type") != "command" or wait.get("name") != "WAIT" or wait.get("args") != "00":
        raise ValueError("WAIT/PLAYER_NAME resegmentation requires stock WAIT $00")
    if player.get("type") != "command" or player.get("name") != "PLAYER_NAME" or player.get("args") != "01":
        raise ValueError("WAIT/PLAYER_NAME resegmentation requires stock PLAYER_NAME 01")

    french_full = normalize_android_french(mapping.get("french_display", "")).strip()
    placeholder = "%S(1,0)"
    if french_full.count(placeholder) != 1:
        raise ValueError("WAIT/PLAYER_NAME resegmentation requires one Android PLAYER_NAME(1) placeholder")
    before, after = (piece.strip() for piece in french_full.split(placeholder, 1))
    if not before or not after:
        raise ValueError("WAIT/PLAYER_NAME resegmentation requires French prose on both sides of the placeholder")

    translations: dict[str, str] = {}
    reports: list[dict] = []
    for index, (text_id, piece) in enumerate(((snes_ids[0], before), (snes_ids[1], after))):
        local = dict(mapping)
        local["snes_ids"] = [text_id]
        if index == 1:
            # The stock PLAYER_NAME command sits immediately before this carrier.
            # Include it in the formatter model so the 9-character worst-case
            # name consumes both VWF width and one parser-safety unit.
            local["source_display"] = placeholder + by_id[text_id]["source"]
            local["french_display"] = placeholder + piece
        else:
            local["source_display"] = by_id[text_id]["source"]
            local["french_display"] = piece
        values, report = format_dialogue_mapping(
            source_document,
            local,
            advances,
            allow_one_extra_page=True,
            use_physical_page_capacity=True,
            prefer_semantic_line_breaks=prefer_semantic_line_breaks,
            allow_two_extra_pages=True,
        )
        translations.update(values)
        reports.append(report)

    return translations, {
        "event_id": mapping["event_id"],
        "snes_ids": snes_ids,
        "android_ids": android_ids,
        "confidence": mapping.get("confidence"),
        "source_display": mapping.get("source_display", ""),
        "android_french_raw": mapping.get("french_display", ""),
        "android_french_normalized": french_full,
        "structural_wait_player_resegmentation": True,
        "preserved_bridge": [
            {"name": wait.get("name"), "args": wait.get("args")},
            {"name": player.get("name"), "args": player.get("args")},
        ],
        "distributed_french_parts": [before, after],
        "resegmentation_parts": reports,
        "formatted_entries": [
            {"id": text_id, "text": translations[text_id]} for text_id in snes_ids
        ],
    }


def _format_timed_wait10_resegmentation(
    source_document: dict,
    mapping: dict,
    advances: dict[str, int],
    *,
    prefer_semantic_line_breaks: bool,
) -> tuple[dict[str, str], dict]:
    """Redistribute one Android localization across the stock $02AE WAIT $10.

    This is deliberately event-specific: Android EN 1630 merges two adjacent
    SNES Amar fragments separated only by WAIT $10. The timing command remains
    untouched; the exact Android French is split only at a complete-sentence
    boundary, with the split chosen to best preserve the source sentence shape.
    """
    if mapping.get("confidence") != "very_high_structural_review":
        raise ValueError("WAIT $10 resegmentation requires structural-review confidence")
    if mapping.get("relation") != "timed_wait10_resegmentation":
        raise ValueError("WAIT $10 resegmentation requires its explicit relation")
    if mapping.get("event_id") != "02AE":
        raise ValueError("WAIT $10 resegmentation is limited to event $02AE")
    snes_ids = mapping.get("snes_ids", [])
    android_ids = mapping.get("android_ids", [])
    if snes_ids != ["C9:B691", "C9:B6B9"] or android_ids != [1630]:
        raise ValueError("WAIT $10 resegmentation no longer matches its reviewed identities")

    by_id, by_event = event_text_index(source_document)
    first = by_id.get(snes_ids[0])
    second = by_id.get(snes_ids[1])
    if first is None or second is None or first["event_id"] != second["event_id"]:
        raise ValueError("WAIT $10 resegmentation references invalid SNES carriers")
    event = by_event[first["event_id"]]
    bridge = event["tokens"][first["token_index"] + 1:second["token_index"]]
    if len(bridge) != 1:
        raise ValueError("WAIT $10 resegmentation requires one untouched bridge command")
    wait = bridge[0]
    if wait.get("type") != "command" or wait.get("name") != "WAIT" or wait.get("args") != "10":
        raise ValueError("WAIT $10 resegmentation requires the stock WAIT $10")

    french_full = normalize_android_french(mapping.get("french_display", "")).strip()
    if not french_full or "%S(" in french_full:
        raise ValueError("WAIT $10 resegmentation requires plain Android French prose")
    boundaries = _sentence_boundary_positions(french_full)
    if not boundaries:
        raise ValueError("WAIT $10 resegmentation requires a complete-sentence split")

    def sentence_count(text: str) -> int:
        compact = re.sub(r"\s+", " ", text.strip())
        return 0 if not compact else len(_sentence_boundary_positions(compact)) + 1

    source_counts = [sentence_count(by_id[text_id]["source"]) for text_id in snes_ids]
    candidates = []
    for boundary in boundaries:
        pieces = [french_full[:boundary].strip(), french_full[boundary:].strip()]
        if any(not piece for piece in pieces):
            continue
        translations: dict[str, str] = {}
        reports: list[dict] = []
        valid = True
        for part_index, (text_id, piece) in enumerate(zip(snes_ids, pieces, strict=True)):
            local = dict(mapping)
            local["snes_ids"] = [text_id]
            local["source_display"] = by_id[text_id]["source"]
            local["french_display"] = piece
            try:
                values, report = format_dialogue_mapping(
                    source_document,
                    local,
                    advances,
                    allow_one_extra_page=True,
                    use_physical_page_capacity=True,
                    prefer_semantic_line_breaks=False if part_index == 0 else prefer_semantic_line_breaks,
                    allow_two_extra_pages=True,
                )
            except ValueError:
                valid = False
                break
            if part_index == 0:
                first_value = values[text_id].rstrip("\n")
                # WAIT does not move the live cursor. Require the pre-WAIT
                # official French piece to fit on one physical line, then move
                # the cursor once before preserving the stock WAIT $10.
                if "\n" in first_value or "\f" in first_value or "\v" in first_value:
                    valid = False
                    break
                values[text_id] = first_value + "\n"
                report = dict(report)
                report["inserted_pre_wait_newline"] = True
                report["formatted_markup"] = values[text_id]
                report["formatted_entries"] = [{"id": text_id, "text": values[text_id]}]
            translations.update(values)
            reports.append(report)
        if not valid:
            continue
        piece_counts = [sentence_count(piece) for piece in pieces]
        score = (
            sum(abs(a - b) for a, b in zip(source_counts, piece_counts, strict=True)),
            sum(report.get("inserted_page_break_count", 0) for report in reports),
            boundary,
        )
        candidates.append((score, pieces, translations, reports))
    if not candidates:
        raise ValueError("WAIT $10 resegmentation found no clean sentence-boundary layout")

    _score, pieces, translations, reports = min(candidates, key=lambda item: item[0])
    return translations, {
        "event_id": mapping["event_id"],
        "snes_ids": snes_ids,
        "android_ids": android_ids,
        "confidence": mapping.get("confidence"),
        "source_display": mapping.get("source_display", ""),
        "android_french_raw": mapping.get("french_display", ""),
        "android_french_normalized": french_full,
        "structural_timed_wait10_resegmentation": True,
        "preserved_bridge": [{"name": wait.get("name"), "args": wait.get("args")}],
        "source_sentence_counts": source_counts,
        "distributed_french_parts": pieces,
        "resegmentation_parts": reports,
        "formatted_entries": [
            {"id": text_id, "text": translations[text_id]} for text_id in snes_ids
        ],
    }


def _format_paired_direction_labels(
    source_document: dict,
    mapping: dict,
    advances: dict[str, int],
    *,
    prefer_semantic_line_breaks: bool,
) -> tuple[dict[str, str], dict]:
    """Split one Android ↑/↓ destination row onto two stock SNES carriers."""
    if mapping.get("confidence") != "very_high_structural_review":
        raise ValueError("Paired direction labels require structural-review confidence")
    if mapping.get("relation") != "paired_direction_labels":
        raise ValueError("Paired direction labels require its explicit relation")
    snes_ids = mapping.get("snes_ids", [])
    android_ids = mapping.get("android_ids", [])
    if len(snes_ids) != 2 or len(android_ids) != 1:
        raise ValueError("Paired direction labels require two SNES IDs and one Android anchor")

    by_id, by_event = event_text_index(source_document)
    first = by_id.get(snes_ids[0])
    second = by_id.get(snes_ids[1])
    if first is None or second is None or first["event_id"] != second["event_id"]:
        raise ValueError("Paired direction labels reference invalid SNES carriers")
    event = by_event[first["event_id"]]
    bridge = event["tokens"][first["token_index"] + 1:second["token_index"]]
    if len(bridge) != 4:
        raise ValueError("Paired direction labels require the proven four-token bridge")
    up, layout, text_x, down = bridge
    if up.get("type") != "glyph" or up.get("code") != "D1":
        raise ValueError("Paired direction labels require stock D1 up-arrow glyph")
    if layout.get("type") != "text" or normalize_alignment_text(layout.get("source", "")):
        raise ValueError("Paired direction labels require one newline-only stock carrier")
    if text_x.get("type") != "command" or text_x.get("name") != "TEXT_X" or text_x.get("args") != "05":
        raise ValueError("Paired direction labels require stock TEXT_X 05")
    if down.get("type") != "glyph" or down.get("code") != "D2":
        raise ValueError("Paired direction labels require stock D2 down-arrow glyph")

    french_full = normalize_android_french(mapping.get("french_display", "")).strip()
    match = re.fullmatch(r"(.+?)\s*↑\s*↓\s*(.+)", french_full)
    if match is None:
        raise ValueError("Paired direction labels require one Android ↑/↓ French row")
    labels = [match.group(1).strip(), match.group(2).strip()]
    if any(not label for label in labels):
        raise ValueError("Paired direction labels produced an empty localized label")

    translations: dict[str, str] = {}
    reports: list[dict] = []
    for text_id, label in zip(snes_ids, labels, strict=True):
        local = dict(mapping)
        local["snes_ids"] = [text_id]
        local["source_display"] = by_id[text_id]["source"]
        local["french_display"] = label
        values, report = format_dialogue_mapping(
            source_document,
            local,
            advances,
            allow_one_extra_page=False,
            use_physical_page_capacity=True,
            prefer_semantic_line_breaks=prefer_semantic_line_breaks,
            allow_two_extra_pages=False,
        )
        value = values[text_id].strip()
        # Preserve the stock one-cell glue around the D1/D2 structural glyphs;
        # localized wording itself comes only from Android French.
        if by_id[text_id]["source"].startswith(" "):
            value = " " + value
        if by_id[text_id]["source"].endswith(" "):
            value = value + " "
        translations[text_id] = value
        reports.append(report)

    return translations, {
        "event_id": mapping["event_id"],
        "snes_ids": snes_ids,
        "android_ids": android_ids,
        "confidence": mapping.get("confidence"),
        "source_display": mapping.get("source_display", ""),
        "android_french_raw": mapping.get("french_display", ""),
        "android_french_normalized": french_full,
        "structural_paired_direction_labels": True,
        "preserved_bridge": [
            {"type": up.get("type"), "code": up.get("code")},
            {"type": layout.get("type"), "id": layout.get("id")},
            {"name": text_x.get("name"), "args": text_x.get("args")},
            {"type": down.get("type"), "code": down.get("code")},
        ],
        "distributed_french_parts": labels,
        "direction_label_parts": reports,
        "formatted_entries": [
            {"id": text_id, "text": translations[text_id]} for text_id in snes_ids
        ],
    }

def _format_mass_mapping(
    source_document: dict,
    mapping: dict,
    advances: dict[str, int],
    *,
    base_rom: bytes,
    french: dict[int, str],
    prefer_semantic_line_breaks: bool,
) -> tuple[dict[str, str], dict]:
    """Format one mass-pass mapping through the conservative fallback chain.

    The first formatter error remains the public rejection reason when no
    structural fallback applies. Each fallback is independently narrow and
    raises ``ValueError`` when its proof requirements are not met.
    """
    common = {
        "allow_one_extra_page": True,
        "use_physical_page_capacity": True,
        "prefer_semantic_line_breaks": prefer_semantic_line_breaks,
        "allow_two_extra_pages": True,
    }
    primary_message: str | None = None
    if mapping.get("relation") == "wait_player_resegmentation":
        return _format_wait_player_resegmentation(
            source_document, mapping, advances, prefer_semantic_line_breaks=prefer_semantic_line_breaks
        )
    if mapping.get("relation") == "timed_wait10_resegmentation":
        return _format_timed_wait10_resegmentation(
            source_document, mapping, advances, prefer_semantic_line_breaks=prefer_semantic_line_breaks
        )
    if mapping.get("relation") == "paired_direction_labels":
        return _format_paired_direction_labels(
            source_document, mapping, advances, prefer_semantic_line_breaks=prefer_semantic_line_breaks
        )
    if mapping.get("relation") in {"cannon_response_prefix", "cannon_common_boarding_suffix"}:
        return _format_cannon_travel_piece(
            source_document, mapping, advances, prefer_semantic_line_breaks=prefer_semantic_line_breaks
        )
    if mapping.get("relation") == "choice_prompt_split":
        try:
            return _format_structurally_reviewed_choice_prompt(
                source_document, mapping, advances
            )
        except ValueError:
            pass
    if mapping.get("relation") == "choice_destination_list":
        try:
            return _format_structurally_reviewed_choice_destination_list(
                source_document, mapping, advances, french=french
            )
        except ValueError:
            pass
    try:
        return format_dialogue_mapping(source_document, mapping, advances, **common)
    except ValueError as exc:
        primary_message = str(exc)

    attempts = (
        lambda: format_mapping_across_existing_wait_boundaries(
            source_document, mapping, advances, **common
        ),
        lambda: format_mapping_across_existing_timed_wait_boundary(
            source_document, mapping, advances, **common
        ),
        lambda: format_mapping_across_existing_action_boundary(
            source_document, mapping, advances, **common
        ),
        lambda: _format_mapping_across_nonsemantic_action_carrier(
            source_document,
            mapping,
            advances,
            base_rom=base_rom,
            prefer_semantic_line_breaks=prefer_semantic_line_breaks,
        ),
        lambda: _format_mapping_across_shake_effect_boundary(
            source_document,
            mapping,
            advances,
            base_rom=base_rom,
            prefer_semantic_line_breaks=prefer_semantic_line_breaks,
        ),
        lambda: _format_reviewed_sequence_block_with_android_extra(
            source_document,
            mapping,
            advances,
            french=french,
            prefer_semantic_line_breaks=prefer_semantic_line_breaks,
        ),
    )
    for attempt in attempts:
        try:
            return attempt()
        except ValueError:
            continue
    assert primary_message is not None
    raise ValueError(primary_message)


def _repair_structural_reaction_page_boundary(
    *,
    base_rom: bytes,
    source_document: dict,
    event: dict,
    event_mappings: list[dict],
    translations: dict[str, str],
    reports: list[dict],
    advances: dict[str, int],
    font,
    simulation,
):
    """Repair a structurally reattributed crowd reaction before its answer.

    The Joch running gag uses a stock ``OP_20`` speaker/action boundary between
    the crowd reaction and Jehk's answer. Android keeps the same ordered scene
    but reattributes the reaction to a dynamic party member. Prefer preserving
    the stock command flow: keep the reaction on the live line and rewrap the
    following answer with the reaction's VWF width as first-line prefix. Only
    the older page-boundary fallback remains below for already-supported shapes.
    """
    from shared.dialogue_simulator import simulate_event

    blocking = [i for i in simulation.issues if i.severity in {"error", "warning"}]
    codes = {i.code for i in blocking}

    by_id, _ = event_text_index(source_document)
    for index in range(len(event_mappings) - 1):
        reaction = event_mappings[index]
        answer = event_mappings[index + 1]
        if reaction.get("relation") != "speaker_reattribution":
            continue
        if reaction.get("confidence") != "very_high_structural_review":
            continue
        reaction_ids = reaction.get("snes_ids", [])
        answer_ids = answer.get("snes_ids", [])
        if len(reaction_ids) != 1 or len(answer_ids) != 1:
            continue
        first_meta = by_id.get(reaction_ids[0])
        second_meta = by_id.get(answer_ids[0])
        if first_meta is None or second_meta is None:
            continue
        bridge = event["tokens"][first_meta["token_index"] + 1:second_meta["token_index"]]
        if len(bridge) != 1 or bridge[0].get("type") != "command" or bridge[0].get("name") != "OP_20":
            continue
        reaction_text = translations.get(reaction_ids[0], "").rstrip(" \n\f\v")
        answer_text = translations.get(answer_ids[0], "")
        if not reaction_text or not answer_text or "\f" in answer_text or "\v" in answer_text:
            continue
        # A space is presentation-only glue between the two stock text tokens;
        # the OP_20 action command remains exactly where it was in the source.
        reaction_text += " "
        answer_flat = " ".join(answer_text.split())
        try:
            wrapped, _widths, _chars, _units = semantic_wrap_markup(
                answer_flat,
                advances,
                first_line_prefix_pixels=_markup_width(reaction_text, advances, 0),
                first_line_prefix_units=len(reaction_text),
            )
        except ValueError:
            continue
        candidate = dict(translations)
        candidate[reaction_ids[0]] = reaction_text
        candidate[answer_ids[0]] = wrapped
        try:
            candidate_simulation = simulate_event(
                base_rom, event, candidate, font=font,
                player_names={0: "000000000", 1: "000000000", 2: "000000000"},
            )
        except ValueError:
            continue
        candidate_blocking = [
            i for i in candidate_simulation.issues
            if i.severity in {"error", "warning"} or i.code == "UNPAUSED_LIVE_LINE_SCROLL_RISK"
        ]
        candidate_wraps = sum(
            line.implicit_wrap for box in candidate_simulation.boxes
            for page in box.pages for line in page.lines
        )
        if candidate_blocking or candidate_wraps:
            continue
        candidate_reports = []
        for report in reports:
            updated = dict(report)
            if report.get("snes_ids") == reaction_ids:
                updated["formatted_markup"] = candidate[reaction_ids[0]]
                updated["formatted_entries"] = [{"id": reaction_ids[0], "text": candidate[reaction_ids[0]]}]
                updated["speaker_reattribution_live_line_prefix"] = True
            elif report.get("snes_ids") == answer_ids:
                updated["formatted_markup"] = candidate[answer_ids[0]]
                updated["formatted_entries"] = [{"id": answer_ids[0], "text": candidate[answer_ids[0]]}]
                updated["speaker_reattribution_prefix_aware_wrap"] = True
            candidate_reports.append(updated)
        repair = {
            "snes_ids": reaction_ids,
            "following_snes_ids": answer_ids,
            "bridge": [{"name": "OP_20", "args": bridge[0].get("args")}],
            "strategy": "speaker_reattribution_prefix_aware_wrap",
        }
        return candidate, candidate_reports, candidate_simulation, [repair]

    if codes not in (
        {"IMPLICIT_RUNTIME_WRAP"},
        {"IMPLICIT_RUNTIME_HARD_WRAP"},
        {"IMPLICIT_RUNTIME_WRAP", "UNPAUSED_SCROLL"},
        {"IMPLICIT_RUNTIME_HARD_WRAP", "UNPAUSED_SCROLL"},
    ):
        return translations, reports, simulation, []

    for index in range(len(event_mappings) - 1):
        reaction = event_mappings[index]
        answer = event_mappings[index + 1]
        if reaction.get("relation") != "speaker_reattribution":
            continue
        if reaction.get("confidence") != "very_high_structural_review":
            continue
        reaction_ids = reaction.get("snes_ids", [])
        answer_ids = answer.get("snes_ids", [])
        if len(reaction_ids) != 1 or not answer_ids:
            continue
        first_meta = by_id.get(reaction_ids[0])
        second_meta = by_id.get(answer_ids[0])
        if first_meta is None or second_meta is None:
            continue
        bridge = event["tokens"][first_meta["token_index"] + 1:second_meta["token_index"]]
        if len(bridge) != 1 or bridge[0].get("type") != "command" or bridge[0].get("name") != "OP_20":
            continue
        text_id = reaction_ids[0]
        current = translations.get(text_id, "").rstrip(" \n\f\v")
        if not current or re.search(r"(?:\.{3}|[.!?…])[”\"»')\]]*$", current) is None:
            continue
        candidate = dict(translations)
        candidate[text_id] = current + "\f "
        try:
            candidate_simulation = simulate_event(
                base_rom,
                event,
                candidate,
                font=font,
                player_names={0: "000000000", 1: "000000000", 2: "000000000"},
            )
        except ValueError:
            continue
        candidate_blocking = [
            i for i in candidate_simulation.issues if i.severity in {"error", "warning"}
        ]
        candidate_wraps = sum(
            line.implicit_wrap
            for box in candidate_simulation.boxes
            for page in box.pages
            for line in page.lines
        )
        if candidate_blocking or candidate_wraps:
            continue
        candidate_reports = []
        for report in reports:
            if report.get("snes_ids") == reaction_ids:
                updated = dict(report)
                updated["formatted_markup"] = candidate[text_id]
                updated["formatted_entries"] = [{"id": text_id, "text": candidate[text_id]}]
                updated["inserted_structural_reaction_page_break"] = True
                candidate_reports.append(updated)
            else:
                candidate_reports.append(report)
        repair = {
            "snes_ids": reaction_ids,
            "following_snes_ids": answer_ids,
            "bridge": [{"name": "OP_20", "args": bridge[0].get("args")}],
            "strategy": "speaker_reattribution_page_boundary",
        }
        return candidate, candidate_reports, candidate_simulation, [repair]
    return translations, reports, simulation, []


def _apply_user_reviewed_fragment_spacing(event_id: str, translations: dict[str, str]) -> list[dict]:
    """Repair exact adjacent-fragment spacing reported in the waterfall scene.

    Event $0106 stores one utterance in four consecutive text fragments. Android
    localizes the fragments separately, and generic per-fragment normalization
    removes the two inter-fragment spaces. Add only those literal spaces; no
    command, wait, or semantic boundary is changed.
    """
    if event_id != "0106":
        return []
    repairs: list[dict] = []
    for left_id, right_id in (("C9:28B7", "C9:28C1"), ("C9:28CB", "C9:28D5")):
        left = translations.get(left_id)
        right = translations.get(right_id)
        if left is None or right is None or left.endswith((" ", "\n", "\v", "\f")) or right.startswith((" ", "\n", "\v", "\f")):
            continue
        translations[left_id] = left + " "
        repairs.append({"left_snes_id": left_id, "right_snes_id": right_id, "strategy": "insert_literal_inter_fragment_space"})
    return repairs



# The corrected WAIT simulator changes candidate scoring in two unrelated
# already-clean events. Keep their previously accepted official-French content
# and page layout byte-for-byte; these are layout compatibility overrides, not
# translation overrides.
DIALOGUE_WAIT_SEMANTICS_LAYOUT_COMPAT = {
    # Runtime review on $0101 exposed a four-line transient that the old
    # simulator missed because WAIT arrived while line 4 was still live.
    # Keep the stock three-line structure: Ouch/Phew share line 1, then the
    # two following sentences each occupy one line.  The official Android FR
    # wording is unchanged; only formatter-inserted line breaks are adjusted.
    "0101": {
        "C9:258F": " : Aïe... Pfiouh.\n",
        "C9:25A1": "Pas moyen de remonter !\nComment je vais faire ?",
    },
    "0022": {
        "C9:0A44": "Encore ?!\f ",
    },
    "02FD": {
        "C9:CB57": "\nMajesté, je vous avais\nparlé de ces jeunes gens.\fIls ont déjoué un attentat !",
    },
}


def _apply_wait_semantics_layout_compat(event_id: str, translations: dict[str, str]) -> list[dict]:
    repairs: list[dict] = []
    for text_id, value in DIALOGUE_WAIT_SEMANTICS_LAYOUT_COMPAT.get(event_id, {}).items():
        if translations.get(text_id) == value:
            continue
        translations[text_id] = value
        repairs.append({
            "layout_text_id": text_id,
            "strategy": "preserve_pre_wait_semantics_clean_layout",
            "validation_status": "static_compatibility",
            "reason": "corrected WAIT simulation must not regress a previously simulator-clean formatted event",
        })
    return repairs



def _strip_canonical_choice_decoration(
    event: dict,
    translations: dict[str, str],
) -> tuple[dict[str, str], dict | None]:
    """Remove one stock outer ``( ... )`` decoration pair from a choice row.

    This is a presentation-only fallback.  It never changes CHOICE_BEGIN,
    CHOICE_OPTION, CHOICE_END, or their coordinates.  The opening/closing
    delimiters are removed only when the canonical USA event proves both sides
    of the pair.  If a delimiter lives in an untranslated punctuation-only
    carrier, an explicit empty/layout-only override is emitted rather than
    copying any stock English prose into the French output.
    """
    tokens = event.get("tokens", [])
    begins = [
        index for index, token in enumerate(tokens)
        if token.get("type") == "command" and token.get("name") == "CHOICE_BEGIN"
    ]
    ends = [
        index for index, token in enumerate(tokens)
        if token.get("type") == "command" and token.get("name") == "CHOICE_END"
    ]
    if len(begins) != 1 or len(ends) != 1 or begins[0] >= ends[0]:
        return translations, None
    begin, end = begins[0], ends[0]
    if not any(
        token.get("type") == "command" and token.get("name") == "CHOICE_OPTION"
        for token in tokens[begin + 1:end]
    ):
        return translations, None

    opening_index = begin - 1
    if opening_index < 0 or tokens[opening_index].get("type") not in {"text", "ending_text"}:
        return translations, None
    opening_token = tokens[opening_index]
    opening_source = opening_token.get("source", "")
    opening_source_match = re.search(r"([ \t]*\()$", opening_source)
    if opening_source_match is None:
        return translations, None

    closing_index = end - 1
    while closing_index > begin and tokens[closing_index].get("type") not in {"text", "ending_text"}:
        closing_index -= 1
    if closing_index <= begin:
        return translations, None
    closing_token = tokens[closing_index]
    closing_source = closing_token.get("source", "")
    closing_source_match = re.search(r"([ \t]*\)[ \t]*)$", closing_source)
    if closing_source_match is None:
        return translations, None

    candidate = dict(translations)

    def strip_token_suffix(token: dict, pattern: str) -> tuple[str, str] | None:
        text_id = token["id"]
        if text_id in candidate:
            current = candidate[text_id]
        else:
            # Only a punctuation/layout-only canonical carrier may be overridden
            # without an existing French value.  Never copy visible stock prose.
            source_without_suffix = re.sub(pattern, "", token.get("source", ""))
            if source_without_suffix.strip(" \t\r\n\f\v"):
                return None
            current = token.get("source", "")
        match = re.search(pattern, current)
        if match is None:
            return None
        removed = match.group(1)
        candidate[text_id] = current[:match.start(1)]
        return text_id, removed

    opening = strip_token_suffix(opening_token, r"([ \t]*\()$")
    if opening is None:
        return translations, None
    closing = strip_token_suffix(closing_token, r"([ \t]*\)[ \t]*)$")
    if closing is None:
        return translations, None

    repair = {
        "strategy": "strip_outer_choice_decoration_for_width",
        "opening_text_id": opening[0],
        "closing_text_id": closing[0],
        "removed_opening_suffix": opening[1],
        "removed_closing_suffix": closing[1],
        "choice_commands_unchanged": True,
    }
    return candidate, repair


def _choice_decoration_reports(
    reports: list[dict],
    translations: dict[str, str],
    repair: dict,
) -> list[dict]:
    """Keep mapping reports synchronized with a stripped choice-decoration fallback."""
    changed_ids = {repair["opening_text_id"], repair["closing_text_id"]}
    updated_reports: list[dict] = []
    for report in reports:
        updated = dict(report)
        entries = [dict(entry) for entry in report.get("formatted_entries", [])]
        touched = False
        for entry in entries:
            text_id = entry.get("id")
            if text_id in changed_ids and text_id in translations:
                entry["text"] = translations[text_id]
                touched = True
        if touched:
            updated["formatted_entries"] = entries
            snes_ids = updated.get("snes_ids", [])
            if len(snes_ids) == 1 and snes_ids[0] in translations:
                updated["formatted_markup"] = translations[snes_ids[0]]
            updated["choice_decoration_mode"] = "stripped_for_width"
            terminal_ids = [
                text_id
                for text_id in (updated.get("preserved_choice_terminal_suffix_ids") or [])
                if text_id != repair["closing_text_id"]
            ]
            updated["preserved_choice_terminal_suffix_ids"] = terminal_ids or None
            if updated.get("preserved_choice_opening_suffix") is not None:
                updated["removed_choice_opening_suffix"] = updated["preserved_choice_opening_suffix"]
                updated["preserved_choice_opening_suffix"] = None
        updated_reports.append(updated)
    return updated_reports


def _try_restore_stock_choice_row_prefix(
    *,
    base_rom: bytes,
    event: dict,
    translations: dict[str, str],
    reports: list[dict],
    font,
    simulation,
) -> tuple[dict[str, str], list[dict], object, list[dict]]:
    """Restore only stock choice-row layout that Android prose reflow removed.

    Two conservative source shapes are supported, and only while the current
    simulator reports an overlap at the *first* CHOICE_OPTION anchor:

    * a translated prompt whose USA carrier ended in ``NEWLINE + spaces + (``;
      append that exact stock suffix when the Android wording omitted it;
    * a standalone decorative ``("` carrier; prefix one NEWLINE so dynamic
      stock output immediately before it cannot consume the choice row.

    No option coordinate changes here.  The candidate is retained only when it
    strictly removes the first-anchor overlap without introducing a new class
    of error/warning or an implicit wrap; later-anchor overlap may remain for
    the separately gated adaptive-anchor pass.
    """
    from shared.dialogue_simulator import simulate_event

    tokens = event.get("tokens", [])
    begins = [
        index for index, token in enumerate(tokens)
        if token.get("type") == "command" and token.get("name") == "CHOICE_BEGIN"
    ]
    if len(begins) != 1 or begins[0] == 0:
        return translations, reports, simulation, []
    begin = begins[0]
    if begin + 1 >= len(tokens):
        return translations, reports, simulation, []
    first_option = tokens[begin + 1]
    if first_option.get("type") != "command" or first_option.get("name") != "CHOICE_OPTION":
        return translations, reports, simulation, []
    args = first_option.get("args", "").split()
    if len(args) != 1:
        return translations, reports, simulation, []
    first_position = int(args[0], 16)
    first_marker = f"CHOICE_OPTION ${first_position:02X} rewinds"
    if not any(
        issue.code == "CHOICE_OPTION_OVERLAP"
        and issue.severity in {"error", "warning"}
        and issue.message.startswith(first_marker)
        for issue in simulation.issues
    ):
        return translations, reports, simulation, []

    previous = tokens[begin - 1]
    if previous.get("type") not in {"text", "ending_text"}:
        return translations, reports, simulation, []
    text_id = previous["id"]
    source = previous.get("source", "")
    current = translations.get(text_id, source)
    candidate = dict(translations)
    repair: dict | None = None

    opening_match = re.search(r"(\n[ ]*\()$", source)
    if opening_match and not re.search(r"(?:\n|\f)[ ]*\($", current):
        suffix = opening_match.group(1)
        candidate[text_id] = current.rstrip(" ") + suffix
        repair = {
            "strategy": "restore_stock_choice_row_suffix",
            "text_id": text_id,
            "restored_suffix": suffix,
            "choice_commands_unchanged": True,
        }
    elif re.fullmatch(r"[ ]*\(", source) and re.fullmatch(r"[ ]*\(", current):
        candidate[text_id] = "\n" + current
        repair = {
            "strategy": "fresh_line_before_standalone_choice_decoration",
            "text_id": text_id,
            "prepended_newline": True,
            "choice_commands_unchanged": True,
        }
    else:
        return translations, reports, simulation, []

    try:
        candidate_simulation = simulate_event(
            base_rom,
            event,
            candidate,
            font=font,
            player_names={0: "000000000", 1: "000000000", 2: "000000000"},
        )
    except ValueError:
        return translations, reports, simulation, []

    candidate_first_overlap = any(
        issue.code == "CHOICE_OPTION_OVERLAP"
        and issue.severity in {"error", "warning"}
        and issue.message.startswith(first_marker)
        for issue in candidate_simulation.issues
    )
    candidate_wraps = sum(
        line.implicit_wrap
        for box in candidate_simulation.boxes
        for page in box.pages
        for line in page.lines
    )
    if candidate_first_overlap or candidate_wraps:
        return translations, reports, simulation, []

    # Do not accept a layout repair that creates an unrelated blocker.  A
    # remaining later-anchor overlap or width warning is allowed to continue to
    # the existing independent choice-layout fallbacks below.
    original_codes = {
        issue.code for issue in simulation.issues if issue.severity in {"error", "warning"}
    }
    candidate_codes = {
        issue.code
        for issue in candidate_simulation.issues
        if issue.severity in {"error", "warning"}
    }
    if candidate_codes - original_codes:
        return translations, reports, simulation, []

    updated_reports = [dict(report) for report in reports]
    for report in updated_reports:
        if text_id not in report.get("snes_ids", []):
            continue
        entries = [dict(entry) for entry in report.get("formatted_entries", [])]
        for entry in entries:
            if entry.get("id") == text_id:
                entry["text"] = candidate[text_id]
        report["formatted_entries"] = entries
        if len(report.get("snes_ids", [])) == 1:
            report["formatted_markup"] = candidate[text_id]
        report["choice_row_layout_repair"] = repair["strategy"]
    return candidate, updated_reports, candidate_simulation, [repair]


def _try_adaptive_choice_anchor_positions(
    *,
    base_rom: bytes,
    event: dict,
    translations: dict[str, str],
    advances: dict[str, int],
    font,
    simulation,
) -> tuple[object, dict[int, int], list[dict]]:
    """Move only later CHOICE_OPTION anchors right to prevent parser overwrite.

    The first option coordinate remains stock.  A later coordinate may move only
    to the minimum decoded-cell position immediately after the previous localized
    label.  The move is tried only for a simple canonical choice row and is kept
    only when the independently serialized/simulated event becomes fully clean.
    Component 06 and the stock highlight then consume the same moved coordinate,
    matching the runtime-validated $03/$11 -> $03/$12 long-label diagnostic.
    """
    from shared.dialogue_simulator import simulate_event

    if not any(
        issue.code == "CHOICE_OPTION_OVERLAP" and issue.severity in {"error", "warning"}
        for issue in simulation.issues
    ):
        return simulation, {}, []

    tokens = event.get("tokens", [])
    begins = [
        index for index, token in enumerate(tokens)
        if token.get("type") == "command" and token.get("name") == "CHOICE_BEGIN"
    ]
    ends = [
        index for index, token in enumerate(tokens)
        if token.get("type") == "command" and token.get("name") == "CHOICE_END"
    ]
    if len(begins) != 1 or len(ends) != 1 or begins[0] >= ends[0]:
        return simulation, {}, []
    begin, end = begins[0], ends[0]

    options: list[tuple[int, int, dict]] = []
    index = begin + 1
    while index < end:
        command = tokens[index]
        if command.get("type") != "command" or command.get("name") != "CHOICE_OPTION":
            return simulation, {}, []
        args = command.get("args", "").split()
        if len(args) != 1:
            return simulation, {}, []
        position = int(args[0], 16)
        if index + 1 >= end:
            return simulation, {}, []
        text_token = tokens[index + 1]
        if text_token.get("type") not in {"text", "ending_text"}:
            return simulation, {}, []
        options.append((index, position, text_token))
        index += 2
    if index != end or len(options) < 2:
        return simulation, {}, []

    positions = [position for _, position, _ in options]
    overrides: dict[int, int] = {}
    repairs: list[dict] = []
    for option_index in range(1, len(options)):
        previous_token = options[option_index - 1][2]
        previous_text = translations.get(previous_token["id"], previous_token.get("source", ""))
        # Choice labels are plain decoded text. Do not infer geometry across any
        # formatter control markup or dynamic structure.
        if any(control in previous_text for control in ("\n", "\f", "\v")):
            return simulation, {}, []
        required = positions[option_index - 1] + len(previous_text)
        source_position = positions[option_index]
        if required <= source_position:
            continue
        if required >= 32:
            return simulation, {}, []
        span_pixels = (required - positions[option_index - 1]) * 8
        if _markup_width(previous_text, advances, 0) > span_pixels:
            return simulation, {}, []
        token_index = options[option_index][0]
        overrides[token_index] = required
        repairs.append({
            "strategy": "shift_choice_option_right_for_decoded_vwf_label",
            "token_index": token_index,
            "source_position": source_position,
            "translated_position": required,
            "previous_text_id": previous_token["id"],
            "decoded_label_cells": len(previous_text),
            "choice_commands_preserved_except_coordinate": True,
        })
        positions[option_index] = required

    if not overrides:
        return simulation, {}, []

    try:
        candidate = simulate_event(
            base_rom,
            event,
            translations,
            font=font,
            player_names={0: "000000000", 1: "000000000", 2: "000000000"},
            choice_option_position_overrides=overrides,
        )
    except ValueError:
        return simulation, {}, []
    blocking = [issue for issue in candidate.issues if issue.severity in {"error", "warning"}]
    wraps = sum(
        line.implicit_wrap
        for box in candidate.boxes
        for page in box.pages
        for line in page.lines
    )
    if blocking or wraps:
        return simulation, {}, []
    return candidate, overrides, repairs


def _try_adaptive_choice_decoration(
    *,
    base_rom: bytes,
    event: dict,
    translations: dict[str, str],
    reports: list[dict],
    font,
    simulation,
) -> tuple[dict[str, str], list[dict], object, list[dict]]:
    """Retry one rejected choice event without its outer stock decoration.

    Decoration is preserved whenever the normal event is already simulator-clean.
    The stripped form is selected only when removing the canonical outer pair is
    sufficient to make the whole event pass the same zero-error/zero-warning/
    zero-implicit-wrap gate.  This keeps the fallback width-driven and avoids a
    global visual rewrite of short choices.
    """
    from shared.dialogue_simulator import simulate_event

    blocking = [issue for issue in simulation.issues if issue.severity in {"error", "warning"}]
    wraps = sum(
        line.implicit_wrap
        for box in simulation.boxes
        for page in box.pages
        for line in page.lines
    )
    if not blocking and not wraps:
        return translations, reports, simulation, []

    candidate, repair = _strip_canonical_choice_decoration(event, translations)
    if repair is None:
        return translations, reports, simulation, []
    try:
        candidate_simulation = simulate_event(
            base_rom,
            event,
            candidate,
            font=font,
            player_names={0: "000000000", 1: "000000000", 2: "000000000"},
        )
    except ValueError:
        return translations, reports, simulation, []
    candidate_blocking = [
        issue for issue in candidate_simulation.issues
        if issue.severity in {"error", "warning"}
    ]
    candidate_wraps = sum(
        line.implicit_wrap
        for box in candidate_simulation.boxes
        for page in box.pages
        for line in page.lines
    )
    if candidate_blocking or candidate_wraps:
        return translations, reports, simulation, []

    candidate_reports = _choice_decoration_reports(reports, candidate, repair)
    return candidate, candidate_reports, candidate_simulation, [repair]


def _try_adaptive_choice_decoration_with_anchor_positions(
    *,
    base_rom: bytes,
    event: dict,
    translations: dict[str, str],
    reports: list[dict],
    advances: dict[str, int],
    font,
    simulation,
) -> tuple[
    dict[str, str],
    list[dict],
    object,
    list[dict],
    dict[int, int],
    list[dict],
]:
    """Strip outer decoration, then retry the validated later-anchor repair.

    This is a composed fallback only: decoration is still preserved whenever a
    less invasive candidate passes.  The first CHOICE_OPTION coordinate remains
    stock; only later coordinates may move right under the existing independent
    simulator gate.
    """
    from shared.dialogue_simulator import simulate_event

    candidate, repair = _strip_canonical_choice_decoration(event, translations)
    if repair is None:
        return translations, reports, simulation, [], {}, []
    try:
        candidate_simulation = simulate_event(
            base_rom,
            event,
            candidate,
            font=font,
            player_names={0: "000000000", 1: "000000000", 2: "000000000"},
        )
    except ValueError:
        return translations, reports, simulation, [], {}, []

    (
        shifted_simulation,
        anchor_overrides,
        anchor_repairs,
    ) = _try_adaptive_choice_anchor_positions(
        base_rom=base_rom,
        event=event,
        translations=candidate,
        advances=advances,
        font=font,
        simulation=candidate_simulation,
    )
    if not anchor_repairs:
        return translations, reports, simulation, [], {}, []

    blocking = [
        issue
        for issue in shifted_simulation.issues
        if issue.severity in {"error", "warning"}
    ]
    wraps = sum(
        line.implicit_wrap
        for box in shifted_simulation.boxes
        for page in box.pages
        for line in page.lines
    )
    if blocking or wraps:
        return translations, reports, simulation, [], {}, []

    candidate_reports = _choice_decoration_reports(reports, candidate, repair)
    for report in candidate_reports:
        report["choice_decoration_anchor_fallback"] = True
    return (
        candidate,
        candidate_reports,
        shifted_simulation,
        [repair],
        anchor_overrides,
        anchor_repairs,
    )


def make_dialogue_format_mass(
    english: dict[int, str],
    french: dict[int, str],
    *,
    english_path: Path,
    french_path: Path,
    base_rom: bytes,
) -> tuple[dict, dict]:
    """Generate the largest conservative complete-event set accepted by the simulator.

    This is deliberately a two-stage gate.  First, every semantic source text
    in an event must already have an accepted Android alignment and every
    mapping must format without crossing an unsupported structural command.
    The formatter may use the full validated three-line physical page capacity
    even when the shorter English source used fewer explicit lines. Ordinary
    overflow may add one validated WAIT $00 + TEXT_CLEAR transition; a longer
    mapping may add two only when both transitions land on complete-sentence
    boundaries and all three pages independently stay within three lines.

    Second, the final serialized event bytes are passed through the independent
    dialogue simulator. Any error, warning, or implicit runtime wrap excludes
    the whole event. Unsupported layout commands therefore remain English until
    the simulator models them explicitly.
    """
    from shared.dialogue_simulator import make_dialogue_font, simulate_event

    validate_base_rom(base_rom)
    alignment = make_dialogue_auto_alignment(
        english,
        french,
        english_path=english_path,
        french_path=french_path,
    )
    source_document = json.loads(DIALOGUE_SOURCE.read_text(encoding="utf-8"))
    manual_supplements_by_event = _load_manual_dialogue_supplements(source_document)
    inn_template = _parameterized_inn_prompt(english, french)
    structural_omission_indexes_by_event = resolve_structural_omission_token_indexes(
        {"user_validated_structural_omissions": list(DIALOGUE_USER_VALIDATED_STRUCTURAL_OMISSIONS)},
        source_document,
    )
    source_text_by_id = {
        token["id"]: token.get("source", "")
        for source_event in source_document["events"]
        for token in source_event["tokens"]
        if token.get("type") == "text"
    }
    advances = make_dialogue_advances(base_rom)
    font = make_dialogue_font(base_rom)

    mappings_by_event: dict[str, list[dict]] = {}
    for mapping in alignment["mappings"]:
        mappings_by_event.setdefault(mapping["event_id"], []).append(mapping)
    unmapped_by_id = {entry["snes_id"]: entry for entry in alignment["unmapped"]}

    translations_by_event: dict[str, dict[str, str]] = {}
    reports_by_event: dict[str, list[dict]] = {}
    wait00_repairs_by_event: dict[str, list[dict]] = {}
    unpaused_scroll_repairs_by_event: dict[str, list[dict]] = {}
    live_line_compact_repairs_by_event: dict[str, list[dict]] = {}
    cross_mapping_sentence_repairs_by_event: dict[str, list[dict]] = {}
    structural_reaction_page_repairs_by_event: dict[str, list[dict]] = {}
    duplicated_player_context_repairs_by_event: dict[str, list[dict]] = {}
    fragment_spacing_repairs_by_event: dict[str, list[dict]] = {}
    targeted_wait00_fresh_page_repairs_by_event: dict[str, list[dict]] = {}
    explicit_post_wait_newline_repairs_by_event: dict[str, list[dict]] = {}
    choice_row_layout_repairs_by_event: dict[str, list[dict]] = {}
    adaptive_choice_decoration_repairs_by_event: dict[str, list[dict]] = {}
    adaptive_choice_anchor_repairs_by_event: dict[str, list[dict]] = {}
    choice_option_position_overrides_by_event: dict[str, dict[int, int]] = {}
    manual_supplement_reports_by_event: dict[str, list[dict]] = {}
    android_extra_reports_by_event: dict[str, list[dict]] = {}
    parameterized_inn_events: set[str] = set()
    accepted_events: list[str] = []
    partial_accepted_events: list[str] = []
    partial_suppressed_semantic_ids_by_event: dict[str, list[str]] = {}
    partial_suppression_reason_by_event: dict[str, str] = {}
    excluded_events: list[dict] = []
    complete_aligned_count = 0
    formatter_candidate_count = 0

    for event in source_document["events"]:
        event_id = event["event_id"]
        semantic_ids = [
            token["id"]
            for token in event["tokens"]
            if token.get("type") == "text" and _auto_semantic(token.get("source", ""))
        ]
        if not semantic_ids:
            continue

        event_mappings = mappings_by_event.get(event_id, [])
        event_mappings, duplicated_player_context_repairs = (
            _strip_duplicated_trailing_player_context(
                event, event_mappings, base_rom=base_rom
            )
        )
        duplicated_player_context_repairs_by_event[event_id] = (
            duplicated_player_context_repairs
        )
        mapped_ids: set[str] = set()
        for mapping in event_mappings:
            mapped_ids.update(mapping["snes_ids"])
        missing_ids = [text_id for text_id in semantic_ids if text_id not in mapped_ids]
        if missing_ids:
            excluded_events.append(
                {
                    "event_id": event_id,
                    "stage": "alignment_incomplete",
                    "semantic_ids": semantic_ids,
                    "missing_semantic_ids": missing_ids,
                    "details": [
                        {
                            "snes_id": text_id,
                            "reason": unmapped_by_id.get(text_id, {}).get("reason", "no accepted automatic mapping"),
                            "note": unmapped_by_id.get(text_id, {}).get("note", ""),
                        }
                        for text_id in missing_ids
                    ],
                }
            )
            continue
        complete_aligned_count += 1

        event_translations: dict[str, str] = {}
        event_reports: list[dict] = []
        formatter_errors: list[dict] = []
        for mapping in event_mappings:
            try:
                values, mapping_report = _format_mass_mapping(
                    source_document,
                    mapping,
                    advances,
                    base_rom=base_rom,
                    french=french,
                    prefer_semantic_line_breaks=True,
                )
            except ValueError as exc:
                formatter_errors.append(
                    {
                        "snes_ids": mapping.get("snes_ids", []),
                        "android_ids": mapping.get("android_ids", []),
                        "message": str(exc),
                    }
                )
                continue
            duplicate = sorted(set(values) & set(event_translations))
            if duplicate:
                formatter_errors.append(
                    {
                        "snes_ids": mapping.get("snes_ids", []),
                        "android_ids": mapping.get("android_ids", []),
                        "message": f"formatter generated duplicate translated source IDs: {duplicate}",
                    }
                )
                continue
            event_translations.update(values)
            event_reports.append(mapping_report)

        if formatter_errors:
            excluded_events.append(
                {
                    "event_id": event_id,
                    "stage": "formatter_rejected",
                    "semantic_ids": semantic_ids,
                    "missing_semantic_ids": [],
                    "details": formatter_errors,
                }
            )
            continue
        formatter_candidate_count += 1

        fragment_spacing_repairs_by_event[event_id] = _apply_user_reviewed_fragment_spacing(
            event_id, event_translations
        )
        targeted_wait00_fresh_page_repairs_by_event[event_id] = _apply_targeted_wait00_fresh_page_clear(
            event_id, event_translations
        )
        explicit_post_wait_newline_repairs_by_event[event_id] = _apply_explicit_post_wait_newlines(
            event_id, event_translations, source_text_by_id=source_text_by_id
        )
        _apply_wait_semantics_layout_compat(event_id, event_translations)
        event_translations, simulation, wait00_repairs = _repair_wait00_page_overlaps(
            base_rom=base_rom,
            event=event,
            translations=event_translations,
            font=font,
        )
        (
            event_translations,
            event_reports,
            simulation,
            live_line_compact_repairs,
        ) = _repair_live_line_scroll_risk_with_compact_wrap(
            base_rom=base_rom,
            source_document=source_document,
            event=event,
            event_mappings=event_mappings,
            translations=event_translations,
            reports=event_reports,
            advances=advances,
            french=french,
            font=font,
            simulation=simulation,
        )
        live_line_compact_repairs_by_event[event_id] = live_line_compact_repairs
        unpaused_scroll_repairs: list[dict] = []
        cross_mapping_sentence_repairs: list[dict] = []
        blocking_issues = [
            issue
            for issue in simulation.issues
            if issue.severity in {"error", "warning"}
        ]
        implicit_wraps = sum(
            line.implicit_wrap
            for box in simulation.boxes
            for page in box.pages
            for line in page.lines
        )
        if blocking_issues or implicit_wraps:
            (
                event_translations,
                event_reports,
                simulation,
                choice_row_layout_repairs,
            ) = _try_restore_stock_choice_row_prefix(
                base_rom=base_rom,
                event=event,
                translations=event_translations,
                reports=event_reports,
                font=font,
                simulation=simulation,
            )
            if choice_row_layout_repairs:
                choice_row_layout_repairs_by_event[event_id] = choice_row_layout_repairs
                blocking_issues = [
                    issue for issue in simulation.issues
                    if issue.severity in {"error", "warning"}
                ]
                implicit_wraps = sum(
                    line.implicit_wrap
                    for box in simulation.boxes
                    for page in box.pages
                    for line in page.lines
                )
        if blocking_issues or implicit_wraps:
            (
                anchor_simulation,
                anchor_overrides,
                anchor_repairs,
            ) = _try_adaptive_choice_anchor_positions(
                base_rom=base_rom,
                event=event,
                translations=event_translations,
                advances=advances,
                font=font,
                simulation=simulation,
            )
            if anchor_repairs:
                simulation = anchor_simulation
                choice_option_position_overrides_by_event[event_id] = anchor_overrides
                adaptive_choice_anchor_repairs_by_event[event_id] = anchor_repairs
                blocking_issues = []
                implicit_wraps = 0
        if blocking_issues or implicit_wraps:
            (
                event_translations,
                event_reports,
                simulation,
                choice_decoration_repairs,
            ) = _try_adaptive_choice_decoration(
                base_rom=base_rom,
                event=event,
                translations=event_translations,
                reports=event_reports,
                font=font,
                simulation=simulation,
            )
            if choice_decoration_repairs:
                adaptive_choice_decoration_repairs_by_event[event_id] = choice_decoration_repairs
                blocking_issues = []
                implicit_wraps = 0
        if blocking_issues or implicit_wraps:
            (
                decorated_translations,
                decorated_reports,
                decorated_simulation,
                choice_decoration_repairs,
                decorated_anchor_overrides,
                decorated_anchor_repairs,
            ) = _try_adaptive_choice_decoration_with_anchor_positions(
                base_rom=base_rom,
                event=event,
                translations=event_translations,
                reports=event_reports,
                advances=advances,
                font=font,
                simulation=simulation,
            )
            if choice_decoration_repairs and decorated_anchor_repairs:
                event_translations = decorated_translations
                event_reports = decorated_reports
                simulation = decorated_simulation
                adaptive_choice_decoration_repairs_by_event[event_id] = choice_decoration_repairs
                choice_option_position_overrides_by_event[event_id] = decorated_anchor_overrides
                adaptive_choice_anchor_repairs_by_event[event_id] = decorated_anchor_repairs
                blocking_issues = []
                implicit_wraps = 0
        if blocking_issues or implicit_wraps:
            # Semantic wrapping is a presentation preference, never a reason to
            # lose an otherwise safe translated event. Retry the whole event
            # with the compact validated wrapper; accept that fallback only if
            # the independent simulator is completely clean.
            compact_translations: dict[str, str] = {}
            compact_reports: list[dict] = []
            compact_errors: list[dict] = []
            for mapping in event_mappings:
                try:
                    values, mapping_report = _format_mass_mapping(
                        source_document,
                        mapping,
                        advances,
                        base_rom=base_rom,
                        french=french,
                        prefer_semantic_line_breaks=False,
                    )
                except ValueError as exc:
                    compact_errors.append({"message": str(exc)})
                    break
                duplicate = sorted(set(values) & set(compact_translations))
                if duplicate:
                    compact_errors.append({"message": f"compact fallback duplicate IDs: {duplicate}"})
                    break
                compact_translations.update(values)
                mapping_report["semantic_layout_fallback"] = True
                compact_reports.append(mapping_report)

            if not compact_errors:
                _apply_targeted_wait00_fresh_page_clear(event_id, compact_translations)
                _apply_explicit_post_wait_newlines(
                    event_id, compact_translations, source_text_by_id=source_text_by_id
                )
                _apply_wait_semantics_layout_compat(event_id, compact_translations)
                compact_translations, compact_simulation, compact_wait00_repairs = _repair_wait00_page_overlaps(
                    base_rom=base_rom,
                    event=event,
                    translations=compact_translations,
                    font=font,
                )
                compact_blocking = [
                    issue for issue in compact_simulation.issues
                    if issue.severity in {"error", "warning"}
                ]
                compact_wraps = sum(
                    line.implicit_wrap
                    for box in compact_simulation.boxes
                    for page in box.pages
                    for line in page.lines
                )
                if compact_blocking or compact_wraps:
                    (
                        compact_translations,
                        compact_reports,
                        compact_simulation,
                        compact_choice_row_layout_repairs,
                    ) = _try_restore_stock_choice_row_prefix(
                        base_rom=base_rom,
                        event=event,
                        translations=compact_translations,
                        reports=compact_reports,
                        font=font,
                        simulation=compact_simulation,
                    )
                    if compact_choice_row_layout_repairs:
                        choice_row_layout_repairs_by_event[event_id] = compact_choice_row_layout_repairs
                        compact_blocking = [
                            issue for issue in compact_simulation.issues
                            if issue.severity in {"error", "warning"}
                        ]
                        compact_wraps = sum(
                            line.implicit_wrap
                            for box in compact_simulation.boxes
                            for page in box.pages
                            for line in page.lines
                        )
                if compact_blocking or compact_wraps:
                    (
                        compact_anchor_simulation,
                        compact_anchor_overrides,
                        compact_anchor_repairs,
                    ) = _try_adaptive_choice_anchor_positions(
                        base_rom=base_rom,
                        event=event,
                        translations=compact_translations,
                        advances=advances,
                        font=font,
                        simulation=compact_simulation,
                    )
                    if compact_anchor_repairs:
                        compact_simulation = compact_anchor_simulation
                        choice_option_position_overrides_by_event[event_id] = compact_anchor_overrides
                        adaptive_choice_anchor_repairs_by_event[event_id] = compact_anchor_repairs
                        compact_blocking = []
                        compact_wraps = 0
                if compact_blocking or compact_wraps:
                    (
                        compact_translations,
                        compact_reports,
                        compact_simulation,
                        compact_choice_decoration_repairs,
                    ) = _try_adaptive_choice_decoration(
                        base_rom=base_rom,
                        event=event,
                        translations=compact_translations,
                        reports=compact_reports,
                        font=font,
                        simulation=compact_simulation,
                    )
                    if compact_choice_decoration_repairs:
                        adaptive_choice_decoration_repairs_by_event[event_id] = compact_choice_decoration_repairs
                        compact_blocking = []
                        compact_wraps = 0
                if compact_blocking or compact_wraps:
                    (
                        compact_decorated_translations,
                        compact_decorated_reports,
                        compact_decorated_simulation,
                        compact_choice_decoration_repairs,
                        compact_decorated_anchor_overrides,
                        compact_decorated_anchor_repairs,
                    ) = _try_adaptive_choice_decoration_with_anchor_positions(
                        base_rom=base_rom,
                        event=event,
                        translations=compact_translations,
                        reports=compact_reports,
                        advances=advances,
                        font=font,
                        simulation=compact_simulation,
                    )
                    if compact_choice_decoration_repairs and compact_decorated_anchor_repairs:
                        compact_translations = compact_decorated_translations
                        compact_reports = compact_decorated_reports
                        compact_simulation = compact_decorated_simulation
                        adaptive_choice_decoration_repairs_by_event[event_id] = compact_choice_decoration_repairs
                        choice_option_position_overrides_by_event[event_id] = compact_decorated_anchor_overrides
                        adaptive_choice_anchor_repairs_by_event[event_id] = compact_decorated_anchor_repairs
                        compact_blocking = []
                        compact_wraps = 0
                if not compact_blocking and not compact_wraps:
                    accepted_events.append(event_id)
                    translations_by_event[event_id] = compact_translations
                    reports_by_event[event_id] = compact_reports
                    wait00_repairs_by_event[event_id] = compact_wait00_repairs
                    unpaused_scroll_repairs_by_event[event_id] = []
                    cross_mapping_sentence_repairs_by_event[event_id] = []
                    continue

            # Preserve every event that the historical compact fallback can
            # already save byte-for-byte. Only after that path fails may a
            # pure four-line rolling-window overflow receive one additional
            # semantic page break.
            (
                repaired_translations,
                repaired_reports,
                repaired_simulation,
                unpaused_scroll_repairs,
            ) = _repair_pure_unpaused_scroll(
                base_rom=base_rom,
                source_document=source_document,
                event=event,
                event_mappings=event_mappings,
                translations=event_translations,
                reports=event_reports,
                advances=advances,
                font=font,
                simulation=simulation,
            )
            if unpaused_scroll_repairs:
                accepted_events.append(event_id)
                translations_by_event[event_id] = repaired_translations
                reports_by_event[event_id] = repaired_reports
                wait00_repairs_by_event[event_id] = wait00_repairs
                unpaused_scroll_repairs_by_event[event_id] = unpaused_scroll_repairs
                cross_mapping_sentence_repairs_by_event[event_id] = []
                continue

            (
                repaired_translations,
                repaired_reports,
                repaired_simulation,
                cross_mapping_sentence_repairs,
            ) = _repair_cross_mapping_sentence_overflow(
                base_rom=base_rom,
                source_document=source_document,
                event=event,
                event_mappings=event_mappings,
                translations=event_translations,
                reports=event_reports,
                advances=advances,
                font=font,
                simulation=simulation,
            )
            if cross_mapping_sentence_repairs:
                accepted_events.append(event_id)
                translations_by_event[event_id] = repaired_translations
                reports_by_event[event_id] = repaired_reports
                wait00_repairs_by_event[event_id] = wait00_repairs
                unpaused_scroll_repairs_by_event[event_id] = []
                cross_mapping_sentence_repairs_by_event[event_id] = (
                    cross_mapping_sentence_repairs
                )
                structural_reaction_page_repairs_by_event[event_id] = []
                continue

            (
                reaction_translations,
                reaction_reports,
                reaction_simulation,
                reaction_repairs,
            ) = _repair_structural_reaction_page_boundary(
                base_rom=base_rom,
                source_document=source_document,
                event=event,
                event_mappings=event_mappings,
                translations=event_translations,
                reports=event_reports,
                advances=advances,
                font=font,
                simulation=simulation,
            )
            if reaction_repairs:
                accepted_events.append(event_id)
                translations_by_event[event_id] = reaction_translations
                reports_by_event[event_id] = reaction_reports
                wait00_repairs_by_event[event_id] = wait00_repairs
                unpaused_scroll_repairs_by_event[event_id] = []
                cross_mapping_sentence_repairs_by_event[event_id] = []
                structural_reaction_page_repairs_by_event[event_id] = reaction_repairs
                continue

            # If newly reviewed structural mappings are correct semantically but
            # still cannot be laid out safely, preserve the previous French-only
            # PARTIEL behavior instead of losing the whole event. Only mappings
            # that predate the current structural reviews are rendered; every newly
            # reviewed semantic token is explicitly suppressed and the direct result
            # must simulate cleanly.
            structural_review = [
                m for m in event_mappings
                if m.get("provenance") in {"round6", "round7", "round8", "round11", "round18", "round20", "round21", "round22"}
            ]
            baseline = [
                m for m in event_mappings
                if m.get("provenance") not in {"round6", "round7", "round8", "round11", "round18", "round20", "round21", "round22"}
            ]
            if structural_review and baseline:
                partial_translations: dict[str, str] = {}
                partial_reports: list[dict] = []
                partial_failed = False
                for baseline_mapping in baseline:
                    try:
                        values, mapping_report = _format_mass_mapping(
                            source_document,
                            baseline_mapping,
                            advances,
                            base_rom=base_rom,
                            french=french,
                            prefer_semantic_line_breaks=True,
                        )
                    except ValueError:
                        partial_failed = True
                        break
                    if set(values) & set(partial_translations):
                        partial_failed = True
                        break
                    partial_translations.update(values)
                    mapping_report = dict(mapping_report)
                    mapping_report["partial_event"] = True
                    partial_reports.append(mapping_report)
                suppressed = sorted({
                    text_id
                    for structural_mapping in structural_review
                    for text_id in structural_mapping.get("snes_ids", [])
                })
                for text_id in suppressed:
                    partial_translations[text_id] = ""
                targeted_wait00_fresh_page_repairs_by_event[event_id] = _apply_targeted_wait00_fresh_page_clear(
                    event_id, partial_translations
                )
                explicit_post_wait_newline_repairs_by_event[event_id] = _apply_explicit_post_wait_newlines(
                    event_id, partial_translations, source_text_by_id=source_text_by_id
                )
                _apply_wait_semantics_layout_compat(event_id, partial_translations)
                if not partial_failed and partial_reports:
                    try:
                        partial_simulation = simulate_event(
                            base_rom,
                            event,
                            partial_translations,
                            font=font,
                            player_names={0: "000000000", 1: "000000000", 2: "000000000"},
                        )
                    except ValueError:
                        partial_simulation = None
                    if partial_simulation is not None:
                        partial_blocking = [
                            i for i in partial_simulation.issues
                            if i.severity in {"error", "warning"}
                        ]
                        partial_wraps = sum(
                            line.implicit_wrap
                            for box in partial_simulation.boxes
                            for page in box.pages
                            for line in page.lines
                        )
                        if not partial_blocking and not partial_wraps:
                            accepted_events.append(event_id)
                            partial_accepted_events.append(event_id)
                            partial_suppressed_semantic_ids_by_event[event_id] = suppressed
                            partial_suppression_reason_by_event[event_id] = "mapped_but_layout_deferred"
                            translations_by_event[event_id] = partial_translations
                            reports_by_event[event_id] = partial_reports
                            wait00_repairs_by_event[event_id] = []
                            unpaused_scroll_repairs_by_event[event_id] = []
                            cross_mapping_sentence_repairs_by_event[event_id] = []
                            structural_reaction_page_repairs_by_event[event_id] = []
                            continue

            details = [
                {
                    "severity": issue.severity,
                    "code": issue.code,
                    "message": issue.message,
                    "box": issue.box,
                    "page": issue.page,
                    "line": issue.line,
                }
                for issue in blocking_issues
            ]
            if implicit_wraps and not any(
                detail.get("code") in {"IMPLICIT_RUNTIME_WRAP", "IMPLICIT_RUNTIME_HARD_WRAP"}
                for detail in details
            ):
                details.append(
                    {
                        "severity": "error",
                        "code": "IMPLICIT_RUNTIME_WRAP_SUMMARY",
                        "message": f"simulator recorded {implicit_wraps} implicit runtime wrap(s)",
                    }
                )
            excluded_events.append(
                {
                    "event_id": event_id,
                    "stage": "simulator_rejected",
                    "semantic_ids": semantic_ids,
                    "missing_semantic_ids": [],
                    "details": details,
                }
            )
            continue

        accepted_events.append(event_id)
        translations_by_event[event_id] = event_translations
        reports_by_event[event_id] = event_reports
        wait00_repairs_by_event[event_id] = wait00_repairs
        unpaused_scroll_repairs_by_event[event_id] = unpaused_scroll_repairs
        cross_mapping_sentence_repairs_by_event[event_id] = cross_mapping_sentence_repairs

    # Second, conservative partial-event pass. An alignment-incomplete event may
    # contribute only its already accepted high-confidence mappings. Every
    # unresolved semantic source token is explicitly translated to empty text so
    # PARTIEL events never expose a visible FR/stock-English mix. Structural
    # commands and layout remain canonical. Unlike complete events, partial events
    # receive no compact/event-level repair: the directly formatted French-only-
    # but-incomplete event must already simulate with no errors, warnings or
    # implicit wraps.
    incomplete_by_event = {
        entry["event_id"]: entry
        for entry in excluded_events
        if entry.get("stage") == "alignment_incomplete"
    }
    for event in source_document["events"]:
        event_id = event["event_id"]
        incomplete = incomplete_by_event.get(event_id)
        if incomplete is None:
            continue
        event_mappings = mappings_by_event.get(event_id, [])
        if not event_mappings:
            continue
        missing_ids = list(incomplete.get("missing_semantic_ids", []))
        missing_set = set(missing_ids)
        event_translations: dict[str, str] = {}
        event_reports: list[dict] = []
        partial_errors: list[dict] = []
        for mapping in event_mappings:
            try:
                values, mapping_report = _format_mass_mapping(
                    source_document,
                    mapping,
                    advances,
                    base_rom=base_rom,
                    french=french,
                    prefer_semantic_line_breaks=True,
                )
            except ValueError as exc:
                partial_errors.append({
                    "snes_ids": mapping.get("snes_ids", []),
                    "android_ids": mapping.get("android_ids", []),
                    "message": str(exc),
                })
                continue
            duplicate = sorted(set(values) & set(event_translations))
            if duplicate:
                partial_errors.append({
                    "snes_ids": mapping.get("snes_ids", []),
                    "android_ids": mapping.get("android_ids", []),
                    "message": f"partial formatter generated duplicate translated source IDs: {duplicate}",
                })
                continue
            forbidden = sorted(set(values) & missing_set)
            if forbidden:
                raise AssertionError(
                    f"partial event ${event_id} attempted to translate unmapped semantic IDs: {forbidden}"
                )
            event_translations.update(values)
            mapping_report["partial_event"] = True
            event_reports.append(mapping_report)
        # User-validated Android-absent carriers may be supplied explicitly by
        # the small manual supplement file.  They stay outside Android identity
        # coverage and keep the event PARTIEL until a separate policy changes
        # that status.
        manual_entries = manual_supplements_by_event.get(event_id, {})
        manual_reports: list[dict] = []
        for missing_id in list(missing_ids):
            manual_entry = manual_entries.get(missing_id)
            if manual_entry is None:
                continue
            value, manual_report = _format_manual_supplement(
                source_document, manual_entry, advances
            )
            # $0278's two controller instructions are separated by WAIT $00 but
            # no stock NEWLINE/TEXT_CLEAR. WAIT does not advance the live cursor;
            # add an explicit formatting-only newline before the second manual
            # supplement so the two validated SNES-only instructions cannot rely
            # on an implicit runtime wrap.
            if event_id == "0278" and missing_id == "C9:A74E":
                value = "\n" + value.lstrip(" ")
                manual_report["layout_adjustment"] = "explicit_newline_after_wait00"
            event_translations[missing_id] = value
            manual_reports.append(manual_report)
        if manual_reports:
            manual_supplement_reports_by_event[event_id] = manual_reports
            event_reports.extend(manual_reports)

        # $0278 resumes the Android sequence after its two SNES-only controller
        # instructions. Android 1349 is a mobile-specific extra page absent from
        # SNES; insert it before the already aligned 1350 page, then continue to
        # 1351 on the stock next carrier.
        if event_id == "0278":
            if set(manual_entries) != {"C9:A730", "C9:A74E"}:
                raise AssertionError("$0278 manual supplement set changed unexpectedly")
            if "C9:A76B" not in event_translations:
                raise AssertionError("$0278 expected aligned carrier C9:A76B")
            extra_text, extra_report = _format_android_extra_page(
                source_document, event_id=event_id, carrier_id="C9:A76B",
                android_id=1349, french=french, advances=advances
            )
            event_translations["C9:A76B"] = extra_text + "\f" + event_translations["C9:A76B"]
            extra_report["distributed_before_android_ids"] = [1350]
            android_extra_reports_by_event[event_id] = [extra_report]
            event_reports.append(extra_report)

        # The common inn prompt is parameterized rather than manually translated.
        # Android EN/FR 110 proves the full 5-GP sentence; the stock caller emits
        # the numeric price between $0330 and $0331, so $0331 receives only the
        # French suffix after that number.
        if event_id == "0331":
            event_translations["C9:CEB3"] = inn_template["suffix_translation"]

        # French-only partial presentation: suppress semantic source text for
        # genuinely unresolved IDs instead of falling back to stock English.
        # Structural commands/tokens remain canonical.
        for missing_id in missing_ids:
            if missing_id in event_translations:
                continue
            preservation = next((
                entry
                for entry in DIALOGUE_USER_VALIDATED_PARTIAL_LAYOUT_PRESERVATIONS
                if entry["event_id"] == event_id
                and entry["suppressed_semantic_id"] == missing_id
            ), None)
            if preservation is None:
                event_translations[missing_id] = ""
                continue
            preserved_text = preservation["preserved_text"]
            if preserved_text.strip():
                raise AssertionError(
                    f"partial event ${event_id}: layout preservation for {missing_id} contains visible text"
                )
            source_text = source_text_by_id.get(missing_id, "")
            if preserved_text.count("\n") > source_text.count("\n"):
                raise AssertionError(
                    f"partial event ${event_id}: layout preservation for {missing_id} invents NEWLINEs"
                )
            event_translations[missing_id] = preserved_text
        if partial_errors or not event_translations:
            incomplete["partial_attempt"] = {
                "status": "formatter_rejected",
                "details": partial_errors,
            }
            continue
        targeted_wait00_fresh_page_repairs_by_event[event_id] = _apply_targeted_wait00_fresh_page_clear(
            event_id, event_translations
        )
        explicit_post_wait_newline_repairs_by_event[event_id] = _apply_explicit_post_wait_newlines(
            event_id, event_translations, source_text_by_id=source_text_by_id
        )
        _apply_wait_semantics_layout_compat(event_id, event_translations)
        try:
            simulation = simulate_event(
                base_rom,
                event,
                event_translations,
                font=font,
                player_names={0: "000000000", 1: "000000000", 2: "000000000"},
                omitted_command_token_indexes=structural_omission_indexes_by_event.get(event_id),
            )
        except ValueError as exc:
            incomplete["partial_attempt"] = {
                "status": "serialization_rejected",
                "details": [{"message": str(exc)}],
            }
            continue
        blocking_issues = [
            issue for issue in simulation.issues
            if issue.severity in {"error", "warning"}
        ]
        implicit_wraps = sum(
            line.implicit_wrap
            for box in simulation.boxes
            for page in box.pages
            for line in page.lines
        )
        if blocking_issues or implicit_wraps:
            (
                event_translations,
                event_reports,
                simulation,
                choice_decoration_repairs,
            ) = _try_adaptive_choice_decoration(
                base_rom=base_rom,
                event=event,
                translations=event_translations,
                reports=event_reports,
                font=font,
                simulation=simulation,
            )
            if choice_decoration_repairs:
                adaptive_choice_decoration_repairs_by_event[event_id] = choice_decoration_repairs
                blocking_issues = []
                implicit_wraps = 0
        if blocking_issues or implicit_wraps:
            incomplete["partial_attempt"] = {
                "status": "simulator_rejected",
                "details": [
                    {
                        "severity": issue.severity,
                        "code": issue.code,
                        "message": issue.message,
                        "box": issue.box,
                        "page": issue.page,
                        "line": issue.line,
                    }
                    for issue in blocking_issues
                ],
                "implicit_wraps": implicit_wraps,
            }
            continue
        accepted_events.append(event_id)
        if event_id == "0331":
            parameterized_inn_events.add(event_id)
        else:
            partial_accepted_events.append(event_id)
            partial_suppressed_semantic_ids_by_event[event_id] = missing_ids
            partial_suppression_reason_by_event[event_id] = (
                "manual_translation_pending" if manual_entries else "alignment_unresolved"
            )
        translations_by_event[event_id] = event_translations
        reports_by_event[event_id] = event_reports
        wait00_repairs_by_event[event_id] = []
        unpaused_scroll_repairs_by_event[event_id] = []
        cross_mapping_sentence_repairs_by_event[event_id] = []
        duplicated_player_context_repairs_by_event.setdefault(event_id, [])
        fragment_spacing_repairs_by_event.setdefault(event_id, [])

    # Materialize the other half of the parameterized inn chain.  The nine
    # caller events contain language-neutral numeric parameters; $0330's English
    # prefix is suppressed so the number becomes the first visible French token.
    inn_price_events = {
        "0320": ("C9:CE3D", "5"),
        "0321": ("C9:CE46", "10"),
        "0322": ("C9:CE50", "15"),
        "0323": ("C9:CE5A", "30"),
        "0324": ("C9:CE64", "50"),
        "0325": ("C9:CE6E", "100"),
        "0326": ("C9:CE79", "120"),
        "0327": ("C9:CE84", "150"),
        "0328": ("C9:CE8F", "200"),
    }
    by_event_id = {event["event_id"]: event for event in source_document["events"]}
    for event_id, (text_id, price) in inn_price_events.items():
        event = by_event_id[event_id]
        text_token = next(token for token in event["tokens"] if token.get("id") == text_id)
        if text_token.get("source") != price:
            raise ValueError(f"Parameterized inn ${event_id}: stock price carrier changed")
        signatures = [
            (token.get("name"), token.get("args"))
            for token in event["tokens"] if token.get("type") == "command"
        ]
        if signatures != [("OP_30", f"F9 {int(event_id,16)-0x320:02X}"), ("OP_23", "30"), ("OP_13", "31"), ("END", None)]:
            raise ValueError(f"Parameterized inn ${event_id}: caller structure changed")
        translations_by_event[event_id] = {text_id: price}
        reports_by_event[event_id] = [{
            "event_id": event_id,
            "snes_ids": [text_id],
            "android_ids": [inn_template["android_id"]],
            "confidence": "user_validated_parameterized_android_template",
            "parameter_value": price,
            "formatted_entries": [{"id": text_id, "text": price}],
        }]
        if event_id not in accepted_events:
            accepted_events.append(event_id)
        parameterized_inn_events.add(event_id)

    prefix_event_id = "0330"
    prefix_event = by_event_id[prefix_event_id]
    prefix_token = next(token for token in prefix_event["tokens"] if token.get("id") == inn_template["prefix_id"])
    if prefix_token.get("source") != " One night is ":
        raise ValueError("Parameterized inn $0330: stock prefix changed")
    translations_by_event[prefix_event_id] = {inn_template["prefix_id"]: inn_template["prefix_translation"]}
    reports_by_event[prefix_event_id] = [{
        "event_id": prefix_event_id,
        "snes_ids": [inn_template["prefix_id"]],
        "android_ids": [inn_template["android_id"]],
        "confidence": "user_validated_parameterized_android_template",
        "suppressed_stock_prefix": True,
        "formatted_entries": [{"id": inn_template["prefix_id"], "text": ""}],
    }]
    if prefix_event_id not in accepted_events:
        accepted_events.append(prefix_event_id)
    parameterized_inn_events.add(prefix_event_id)

    resolved_special_events = set(parameterized_inn_events)
    if partial_accepted_events or resolved_special_events:
        accepted_partial = set(partial_accepted_events) | resolved_special_events
        excluded_events = [
            entry for entry in excluded_events
            if entry.get("event_id") not in accepted_partial
        ]
        accepted_events.sort(key=lambda value: int(value, 16))

    translations: dict[str, str] = {}
    formatted: list[dict] = []
    for event_id in accepted_events:
        for text_id, value in translations_by_event[event_id].items():
            if text_id in translations:
                raise ValueError(f"Mass formatter generated duplicate translation ID {text_id}")
            translations[text_id] = value
        formatted.extend(reports_by_event[event_id])

    source_order = {
        token["id"]: order
        for order, token in enumerate(
            token
            for event in source_document["events"]
            for token in event["tokens"]
            if token.get("type") == "text"
        )
    }
    ordered_entries = sorted(translations.items(), key=lambda item: source_order[item[0]])
    translation_document = make_dialogue_translation_document(
        ordered_entries,
        group="dialogues.android_format_mass_simulator_filtered",
    )
    visible_partial_events = [
        event_id for event_id in partial_accepted_events
        if event_id not in DIALOGUE_USER_VALIDATED_VISUALLY_COMPLETE_EVENTS
    ]
    user_validated_complete_events = [
        event_id for event_id in partial_accepted_events
        if event_id in DIALOGUE_USER_VALIDATED_VISUALLY_COMPLETE_EVENTS
    ]
    def partial_metadata(event_id: str) -> dict:
        reason = partial_suppression_reason_by_event[event_id]
        ids = partial_suppressed_semantic_ids_by_event[event_id]
        result = {"event_id": event_id, "suppression_reason": reason}
        if reason == "manual_translation_pending":
            result["manual_pending_semantic_ids"] = ids
        else:
            result["suppressed_semantic_ids"] = ids
        return result

    translation_document["partial_events"] = [
        partial_metadata(event_id) for event_id in visible_partial_events
    ]
    translation_document["user_validated_visually_complete_events"] = [
        {
            "event_id": event_id,
            "suppressed_semantic_ids": partial_suppressed_semantic_ids_by_event[event_id],
            "reason": "user_validated_android_adaptation_complete",
        }
        for event_id in user_validated_complete_events
    ]
    translation_document["user_validated_structural_omissions"] = list(
        DIALOGUE_USER_VALIDATED_STRUCTURAL_OMISSIONS
    )
    translation_document["user_validated_partial_layout_preservations"] = []
    translation_document["manual_dialogue_supplements"] = [
        {
            "event_id": event_id,
            "id": text_id,
            "status": entry["status"],
            "reason": entry["reason"],
        }
        for event_id in sorted(manual_supplements_by_event)
        for text_id, entry in sorted(manual_supplements_by_event[event_id].items())
    ]
    translation_document["parameterized_android_templates"] = [{
        "kind": "inn_price_prompt",
        "android_id": inn_template["android_id"],
        "android_english": inn_template["android_english"],
        "android_french": inn_template["android_french"],
        "prefix_id": inn_template["prefix_id"],
        "suffix_id": inn_template["suffix_id"],
        "price_event_ids": sorted(
            [event_id for event_id in parameterized_inn_events if event_id not in {"0330", "0331"}],
            key=lambda value: int(value, 16),
        ),
        "reason": "user_validated_dynamic_price_generalization",
    }]
    translation_document["choice_option_position_overrides"] = [
        {"event_id": event_id, **repair}
        for event_id in accepted_events
        for repair in adaptive_choice_anchor_repairs_by_event.get(event_id, [])
    ]

    stage_counts: dict[str, int] = {}
    for entry in excluded_events:
        stage_counts[entry["stage"]] = stage_counts.get(entry["stage"], 0) + 1
    accepted_semantic_ids = sum(
        1
        for event_id in accepted_events
        for token in next(
            event for event in source_document["events"] if event["event_id"] == event_id
        )["tokens"]
        if (
            token.get("type") == "text"
            and _auto_semantic(token.get("source", ""))
            and token.get("id") in translations_by_event[event_id]
            and translations_by_event[event_id][token.get("id")] != ""
            and not any(
                preservation["event_id"] == event_id
                and preservation["suppressed_semantic_id"] == token.get("id")
                for preservation in DIALOGUE_USER_VALIDATED_PARTIAL_LAYOUT_PRESERVATIONS
            )
        )
    )
    report_document = {
        "format_version": 1,
        "status": "simulator_filtered_partial_runtime_candidate",
        "source_alignment": "mappings/android/dialogues_auto.json (regenerated from Android EN/FR)",
        "policy": {
            "event_selection": "complete semantic events plus simulator-clean partial events",
            "alignment_must_already_be_accepted": True,
            "all_semantic_ids_in_complete_event_must_be_mapped": True,
            "partial_event_policy": "translate every accepted Android mapping in an alignment-incomplete event; unresolved IDs are normally suppressed, while user-validated Android-absent manual supplements may remain visible and explicitly keep the event PARTIEL until manually translated; preserve structural commands/layout and require a clean independent simulation",
            "user_validated_visual_complete_policy": "events explicitly validated by the user as complete Android adaptations keep their simulator-clean French-only bytes and are removed from the PARTIEL badge without inventing mappings for omitted SNES-only fragments",
            "user_validated_structural_omission_policy": "a stock command may be omitted only when the user explicitly validates the Android adaptation omission and the command is proven by exact adjacency to an explicitly suppressed semantic ID; $01DC drops only PLAYER_NAME(0) immediately before C9:804A",
            "manual_supplement_policy": "only exact carriers user-validated as absent from Android may appear in translations/dialogues_manual_supplements.json; pending entries must remain byte-faithful USA text, do not count as Android alignment, and keep their event PARTIEL",
            "parameterized_inn_policy": "Android EN/FR 110 is the reviewed template for the common inn prompt: keep each stock numeric caller as the dynamic price, suppress stock C9:CEA3 before it, and render the normalized Android-FR suffix through C9:CEB3; this resolves all shared inn price variants without per-price manual translation",
            "event_0278_android_extra_policy": "after Android 1347/1348 and the two user-validated SNES-only manual controller supplements, insert Android FR 1349 as an extra page before already aligned 1350, then continue with 1351; an explicit newline before C9:A74E materializes the real WAIT!=NEWLINE cursor behavior and avoids an implicit wrap",
            "reviewed_fragment_spacing_policy": "event $0106 may insert only the two user-reported literal spaces between proven adjacent text fragments; no command or layout boundary changes",
            "physical_page_capacity_lines": DIALOGUE_PAGE_LINES,
            "source_english_line_count_is_not_a_layout_limit": True,
            "snes_vwf_wrap_pixels": DIALOGUE_WRAP_PIXELS,
            "snes_parser_max_decoded_characters": DIALOGUE_WRAP_CHARS,
            "dynamic_player_name_width_assumption": "9 characters at worst-case validated glyph advance",
            "dynamic_player_name_character_assumption": "9 visible characters plus 1 conservative parser-safety unit per PLAYER_NAME",
            "maximum_generated_extra_pages_per_mapping": 2,
            "two_extra_pages_policy": "only two complete-sentence boundaries producing three independently <=3-line pages",
            "generated_page_break_encoding": "WAIT $00 + TEXT_CLEAR",
            "simulator_player_name": "000000000",
            "simulator_rejects_errors": True,
            "simulator_rejects_warnings": True,
            "simulator_rejects_implicit_wraps": True,
            "simulator_unsupported_structures_are_rejected": True,
            "semantic_line_break_preferences": "sentence boundaries strong; commas weak when materially better balanced",
            "semantic_layout_simulator_fallback": "retry whole event with compact wrapper before excluding",
            "line_start_text_x_formatter_reservation": "proven fresh-line TEXT_X padding reduces only the first formatted line's pixel/parser capacity",
            "android_leading_player_label_policy": "drop only an exact leading %S(n,0) speaker label when the mapped SNES source has no PLAYER_NAME; localized prose is otherwise unchanged",
            "adjacent_nonsemantic_player_carrier_policy": "a punctuation/whitespace-only SNES text token immediately outside an existing PLAYER_NAME binding may carry localized literal text; no PLAYER_NAME command is moved or created",
            "adjacent_player_through_carrier_policy": "one existing PLAYER_NAME immediately before a punctuation/whitespace carrier may join a binding only when Android French proves that exact extra leading placeholder",
            "duplicated_player_context_policy": "a trailing PLAYER_NAME duplicated as the next mapping's leading alignment context may be ignored only across a proven linear bridge; any called clean-ROM event must be text-free, branch-free and returning, and the SNES PLAYER_NAME remains with the following mapping",
            "existing_wait_sentence_distribution_policy": "multi-slot mappings may be redistributed across existing WAIT $00 + optional TEXT_CLEAR boundaries only at complete French sentence boundaries; timed WAITs and PLAYER_NAME remain excluded and stock commands stay unchanged",
            "existing_timed_wait_sentence_distribution_policy": "exactly one existing WAIT $04/$08 may separate two complete source/French sentences; the timed WAIT is preserved byte-for-byte and no other boundary command is accepted",
            "round22_wait10_resegmentation_policy": "event $02AE only: Android EN/FR 1630 may be split across the exact stock WAIT $10 at a complete French sentence boundary; the pre-WAIT text must fit one physical line, one explicit newline is serialized before the unchanged timed WAIT, and the candidate remains runtime-unvalidated",
            "existing_wait_weak_clause_policy": "for one two-slot WAIT $00 mapping whose source slots are each complete sentences, a French comma may be the split only before an explicit discourse connector such as alors/mais/donc/pourtant/cependant",
            "existing_action_boundary_policy": "two text slots from one Android unit may be redistributed only at a complete sentence boundary across proven OP_32 walk / OP_34 loop-action / COMPLETE_ACTIONS commands, with a complete source sentence before the action; choice events remain excluded and commands remain unchanged",
            "nonsemantic_action_carrier_policy": "one three-slot semantic/layout-only/semantic mapping may preserve the stock middle carrier while distributing two complete French sentences across action-only boundaries and clean-ROM text-free returning calls",
            "shake_effect_boundary_policy": "one two-slot mapping may cross only the proven sound-call + OP_2D $02 + timed WAIT + OP_2D $04 + sound-call sequence; both sound callees must be sound-only returning scripts and every stock effect byte stays unchanged",
            "reviewed_sequence_block_policy": "a user-validated sequence_block_with_android_extra mapping may redistribute four Android French anchors over three semantic SNES slots only in the exact reviewed semantic/layout/action/semantic/WAIT+clear shape; the stock layout carrier remains untouched",
            "cross_mapping_action_sentence_overflow_policy": "one leading newline plus semantic pagination may repair a soft or decoded-capacity parser wrap only across an adjacent OP_32/OP_34 + COMPLETE_ACTIONS boundary after a complete localized sentence; accept only after clean resimulation",
            "pure_unpaused_scroll_policy": "after compact fallback fails, one semantic-boundary extra page may be tried only when UNPAUSED_SCROLL is the sole simulator defect; accept only after clean resimulation",
            "cross_mapping_sentence_overflow_policy": "after all earlier fallbacks fail, a parser-wrap + unpaused-scroll event may add one newline at a proven adjacent sentence boundary and one semantic page break; accept only after clean resimulation",
            "wait00_exact_overlap_policy": "no generic WAIT $00 carry-over cleanup; presentation changes require explicit per-event runtime validation; timed WAITs unchanged",
            "targeted_wait00_fresh_page_policy": "keep stock WAIT $00 bytes unchanged; $0106/C9:2994 is runtime-validated and the eight round13 detector matches are explicitly converted from newline-only carriers to TEXT_CLEAR as a single user-requested runtime-test batch; no generic WAIT carry-over cleanup",
            "wait_semantics_policy": "runtime-validated: WAIT pauses without advancing the text cursor; only explicit $7F NEWLINE or TEXT_CLEAR changes the physical line/page",
            "explicit_post_wait_newline_policy": "materialize only reviewed formatter line boundaries that older simulation had implicitly attributed to WAIT; keep WAIT bytes unchanged; use TEXT_CLEAR instead of NEWLINE when a three-line window would otherwise scroll before the next pause",
            "choice_row_prefix_restore_policy": "when Android prose reflow removes the stock final NEWLINE + optional spaces + '(' immediately before CHOICE_BEGIN and the first stock CHOICE_OPTION would rewind over translated prompt text, restore only that stock row suffix; for a standalone decorative '(' carrier after dynamic stock output, one explicit NEWLINE may be prefixed for the same first-anchor condition; no option coordinate changes are made by this repair and unrelated new simulator defects reject it",
            "adaptive_choice_anchor_policy": "keep the first CHOICE_OPTION stock; when a later stock coordinate would overwrite the preceding localized label in the decoded row, move only that later coordinate right to the minimum cell immediately after the label; accept only a rightward <32 coordinate whose whole event passes the independent zero-error/zero-warning/zero-wrap simulation; runtime validated by the $03/$11 -> $03/$12 Temple de l'Eau/Pandora diagnostic",
            "adaptive_choice_decoration_policy": "preserve the canonical outer ( ... ) decoration whenever the normal choice event is simulator-clean; only after a width/layout rejection, retry by removing the proven opening/closing parenthesis pair plus its adjacent horizontal padding; when stripping alone is insufficient, it may be composed with the already validated later-anchor-only right shift, while the first CHOICE_OPTION remains stock; accept only if the whole event passes the same zero-error/zero-warning/zero-wrap gate",
        },
        "coverage": {
            "semantic_source_event_count": sum(
                1
                for event in source_document["events"]
                if any(
                    token.get("type") == "text" and _auto_semantic(token.get("source", ""))
                    for token in event["tokens"]
                )
            ),
            "complete_aligned_event_count": complete_aligned_count,
            "formatter_candidate_event_count": formatter_candidate_count,
            "accepted_event_count": len(accepted_events),
            "complete_accepted_event_count": len(accepted_events) - len(visible_partial_events),
            "partial_accepted_event_count": len(visible_partial_events),
            "user_validated_visually_complete_event_count": len(user_validated_complete_events),
            "user_validated_structural_omission_event_count": len(structural_omission_indexes_by_event),
            "user_validated_structural_omitted_command_count": sum(
                len(indexes) for indexes in structural_omission_indexes_by_event.values()
            ),
            "manual_supplement_entry_count": sum(len(entries) for entries in manual_supplements_by_event.values()),
            "parameterized_inn_event_count": len(parameterized_inn_events),
            "partial_unresolved_or_manual_id_count": sum(
                len(partial_suppressed_semantic_ids_by_event[event_id]) for event_id in visible_partial_events
            ),
            "accepted_semantic_source_id_count": accepted_semantic_ids,
            "translation_entry_count": len(ordered_entries),
            "fragment_spacing_repaired_event_count": sum(bool(value) for value in fragment_spacing_repairs_by_event.values()),
            "fragment_spacing_repair_count": sum(len(value) for value in fragment_spacing_repairs_by_event.values()),
            "explicit_post_wait_newline_repaired_event_count": sum(bool(value) for value in explicit_post_wait_newline_repairs_by_event.values()),
            "explicit_post_wait_newline_repair_count": sum(len(value) for value in explicit_post_wait_newline_repairs_by_event.values()),
            "wait00_overlap_repaired_event_count": sum(bool(value) for value in wait00_repairs_by_event.values()),
            "wait00_overlap_repair_count": sum(len(value) for value in wait00_repairs_by_event.values()),
            "unpaused_scroll_repaired_event_count": sum(bool(value) for value in unpaused_scroll_repairs_by_event.values()),
            "unpaused_scroll_repair_count": sum(len(value) for value in unpaused_scroll_repairs_by_event.values()),
            "live_line_compact_repaired_event_count": sum(bool(value) for value in live_line_compact_repairs_by_event.values()),
            "live_line_compact_repair_count": sum(len(value) for value in live_line_compact_repairs_by_event.values()),
            "cross_mapping_sentence_repaired_event_count": sum(bool(value) for value in cross_mapping_sentence_repairs_by_event.values()),
            "cross_mapping_sentence_repair_count": sum(len(value) for value in cross_mapping_sentence_repairs_by_event.values()),
            "structural_reaction_page_repaired_event_count": sum(bool(value) for value in structural_reaction_page_repairs_by_event.values()),
            "structural_reaction_page_repair_count": sum(len(value) for value in structural_reaction_page_repairs_by_event.values()),
            "android_leading_player_label_removed_mapping_count": sum(
                any("%S(" in marker for marker in (entry.get("structural_markers_removed") or []))
                for entry in formatted
            ),
            "adjacent_nonsemantic_player_carrier_mapping_count": sum(
                bool(entry.get("adjacent_nonsemantic_carrier_ids")) for entry in formatted
            ),
            "adjacent_nonsemantic_player_carrier_entry_count": sum(
                len(entry.get("adjacent_nonsemantic_carrier_ids") or []) for entry in formatted
            ),
            "adjacent_player_through_carrier_mapping_count": sum(
                bool(entry.get("adjacent_player_carrier_indexes")) for entry in formatted
            ),
            "duplicated_player_context_repaired_event_count": sum(
                bool(duplicated_player_context_repairs_by_event.get(event_id))
                for event_id in accepted_events
            ),
            "duplicated_player_context_repair_count": sum(
                len(duplicated_player_context_repairs_by_event.get(event_id, []))
                for event_id in accepted_events
            ),
            "existing_wait_sentence_distribution_mapping_count": sum(
                bool(entry.get("existing_wait_sentence_distribution")) for entry in formatted
            ),
            "existing_timed_wait_sentence_distribution_mapping_count": sum(
                bool(entry.get("existing_timed_wait_sentence_distribution")) for entry in formatted
            ),
            "round22_wait10_resegmentation_mapping_count": sum(
                bool(entry.get("structural_timed_wait10_resegmentation")) for entry in formatted
            ),
            "existing_wait_weak_clause_boundary_mapping_count": sum(
                bool(entry.get("existing_wait_weak_clause_boundary")) for entry in formatted
            ),
            "existing_action_sentence_split_mapping_count": sum(
                bool(entry.get("existing_action_sentence_split")) for entry in formatted
            ),
            "nonsemantic_action_carrier_mapping_count": sum(
                bool(entry.get("nonsemantic_action_carrier_distribution")) for entry in formatted
            ),
            "shake_effect_sentence_distribution_mapping_count": sum(
                bool(entry.get("existing_shake_effect_sentence_distribution")) for entry in formatted
            ),
            "reviewed_sequence_block_distribution_mapping_count": sum(
                bool(entry.get("reviewed_sequence_block_distribution")) for entry in formatted
            ),
            "action_boundary_line_break_count": sum(
                bool(entry.get("inserted_action_boundary_line_break")) for entry in formatted
            ),
            "choice_row_layout_repaired_event_count": sum(
                bool(choice_row_layout_repairs_by_event.get(event_id))
                for event_id in accepted_events
            ),
            "choice_row_layout_repair_count": sum(
                len(choice_row_layout_repairs_by_event.get(event_id, []))
                for event_id in accepted_events
            ),
            "adaptive_choice_anchor_shifted_event_count": sum(
                bool(adaptive_choice_anchor_repairs_by_event.get(event_id))
                for event_id in accepted_events
            ),
            "adaptive_choice_anchor_shift_count": sum(
                len(adaptive_choice_anchor_repairs_by_event.get(event_id, []))
                for event_id in accepted_events
            ),
            "adaptive_choice_decoration_stripped_event_count": sum(
                bool(adaptive_choice_decoration_repairs_by_event.get(event_id))
                for event_id in accepted_events
            ),
            "adaptive_choice_decoration_stripped_count": sum(
                len(adaptive_choice_decoration_repairs_by_event.get(event_id, []))
                for event_id in accepted_events
            ),
            "excluded_event_count": len(excluded_events),
            "excluded_stage_counts": stage_counts,
        },
        "accepted_events": accepted_events,
        "user_validated_visually_complete_events": [
            {
                "event_id": event_id,
                "suppressed_semantic_ids": partial_suppressed_semantic_ids_by_event[event_id],
                "reason": "user_validated_android_adaptation_complete",
            }
            for event_id in user_validated_complete_events
        ],
        "user_validated_structural_omissions": list(DIALOGUE_USER_VALIDATED_STRUCTURAL_OMISSIONS),
        "manual_dialogue_supplements": translation_document["manual_dialogue_supplements"],
        "parameterized_android_templates": translation_document["parameterized_android_templates"],
        "partial_accepted_events": [
            partial_metadata(event_id) for event_id in visible_partial_events
        ],
        "formatted_mappings": formatted,
        "choice_row_layout_repairs": [
            {"event_id": event_id, **repair}
            for event_id in accepted_events
            for repair in choice_row_layout_repairs_by_event.get(event_id, [])
        ],
        "adaptive_choice_anchor_repairs": [
            {"event_id": event_id, **repair}
            for event_id in accepted_events
            for repair in adaptive_choice_anchor_repairs_by_event.get(event_id, [])
        ],
        "adaptive_choice_decoration_repairs": [
            {"event_id": event_id, **repair}
            for event_id in accepted_events
            for repair in adaptive_choice_decoration_repairs_by_event.get(event_id, [])
        ],
        "wait00_overlap_repairs": [
            {"event_id": event_id, **repair}
            for event_id in accepted_events
            for repair in wait00_repairs_by_event.get(event_id, [])
        ],
        "unpaused_scroll_repairs": [
            {"event_id": event_id, **repair}
            for event_id in accepted_events
            for repair in unpaused_scroll_repairs_by_event.get(event_id, [])
        ],
        "live_line_compact_repairs": [
            {"event_id": event_id, **repair}
            for event_id in accepted_events
            for repair in live_line_compact_repairs_by_event.get(event_id, [])
        ],
        "cross_mapping_sentence_repairs": [
            {"event_id": event_id, **repair}
            for event_id in accepted_events
            for repair in cross_mapping_sentence_repairs_by_event.get(event_id, [])
        ],
        "structural_reaction_page_repairs": [
            {"event_id": event_id, **repair}
            for event_id in accepted_events
            for repair in structural_reaction_page_repairs_by_event.get(event_id, [])
        ],
        "fragment_spacing_repairs": [
            {"event_id": event_id, **repair}
            for event_id, repairs in fragment_spacing_repairs_by_event.items()
            for repair in repairs
        ],
        "explicit_post_wait_newline_repairs": [
            {"event_id": event_id, **repair}
            for event_id in accepted_events
            for repair in explicit_post_wait_newline_repairs_by_event.get(event_id, [])
        ],
        "duplicated_player_context_repairs": [
            {"event_id": event_id, **repair}
            for event_id in accepted_events
            for repair in duplicated_player_context_repairs_by_event.get(event_id, [])
        ],
        "excluded_events": excluded_events,
    }
    return translation_document, report_document


def dialogue_format_mass_excluded_csv(report: dict, source_document: dict) -> str:
    """Render one row per semantic source phrase in an event excluded from mass output."""
    import csv
    import io

    by_event = {event["event_id"]: event for event in source_document["events"]}
    output = io.StringIO(newline="")
    fields = [
        "event_id",
        "stage",
        "snes_id",
        "texte_source_snes_usa",
        "est_non_mappe_alignement",
        "raison_evenement_exclu",
        "commentaire_utilisateur",
    ]
    writer = csv.DictWriter(output, fieldnames=fields, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    writer.writeheader()
    for excluded in report.get("excluded_events", []):
        event_id = excluded["event_id"]
        event = by_event[event_id]
        missing = set(excluded.get("missing_semantic_ids", []))
        detail_messages: list[str] = []
        for detail in excluded.get("details", []):
            if "message" in detail:
                prefix = detail.get("code") or "+".join(detail.get("snes_ids", []))
                detail_messages.append(f"{prefix}: {detail['message']}" if prefix else detail["message"])
            elif "reason" in detail:
                text_id = detail.get("snes_id", "")
                detail_messages.append(f"{text_id}: {detail['reason']}")
        reason = " | ".join(detail_messages)
        semantic = [
            token
            for token in event["tokens"]
            if token.get("type") == "text" and _auto_semantic(token.get("source", ""))
        ]
        for token in semantic:
            writer.writerow(
                {
                    "event_id": event_id,
                    "stage": excluded["stage"],
                    "snes_id": token["id"],
                    "texte_source_snes_usa": token["source"].replace("\r", "").replace("\n", " ⏎ ").strip(),
                    "est_non_mappe_alignement": "oui" if token["id"] in missing else "non",
                    "raison_evenement_exclu": reason,
                    "commentaire_utilisateur": "",
                }
            )
    return output.getvalue()


def dialogue_unmapped_csv(document: dict) -> str:
    """Render the automatic alignment's unresolved semantic source phrases."""
    import csv
    import io

    output = io.StringIO(newline="")
    fieldnames = [
        "event_id",
        "snes_id",
        "texte_source_snes_usa",
        "raison",
        "note",
        "meilleur_id_android_anglais",
        "meilleur_texte_anglais_android",
        "meilleur_score_lexical",
        "meilleure_couverture_source",
        "meilleur_texte_francais_candidat",
        "deuxieme_id_android_anglais",
        "deuxieme_score_lexical",
        "commentaire_utilisateur",
    ]
    writer = csv.DictWriter(
        output,
        fieldnames=fieldnames,
        delimiter=";",
        quoting=csv.QUOTE_MINIMAL,
        lineterminator="\n",
    )
    writer.writeheader()
    for entry in document["unmapped"]:
        candidates = entry.get("top_candidates", [])
        first = candidates[0] if candidates else {}
        second = candidates[1] if len(candidates) > 1 else {}
        writer.writerow(
            {
                "event_id": entry["event_id"],
                "snes_id": entry["snes_id"],
                "texte_source_snes_usa": entry["source"].replace("\r", "").replace("\n", " ⏎ ").strip(),
                "raison": entry["reason"],
                "note": entry["note"],
                "meilleur_id_android_anglais": first.get("android_id", ""),
                "meilleur_texte_anglais_android": first.get("android_english", "").replace("\r", "").replace("\n", " ⏎ ").strip(),
                "meilleur_score_lexical": first.get("lexical_score", ""),
                "meilleure_couverture_source": first.get("source_token_coverage", ""),
                "meilleur_texte_francais_candidat": first.get("french_display", "").replace("\r", "").replace("\n", " ⏎ ").strip(),
                "deuxieme_id_android_anglais": second.get("android_id", ""),
                "deuxieme_score_lexical": second.get("lexical_score", ""),
                "commentaire_utilisateur": "",
            }
        )
    # UTF-8 BOM is added when the caller writes bytes/text to disk.
    return output.getvalue()


def serialized(document: dict) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def write_or_check(output: Path, text: str, *, check: bool, source_label: str) -> None:
    if check:
        try:
            existing = output.read_text(encoding="utf-8")
        except OSError as exc:
            raise SystemExit(f"Cannot read {output}: {exc}") from exc
        if existing != text:
            raise SystemExit(f"{output} is not up to date with {source_label}")
        print(f"Android import/alignment check OK: {output}")
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    print(f"Generated {output} from {source_label}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--only",
        choices=(
            "intro",
            "dialogue-pilot",
            "dialogue-review",
            "dialogue-review-round3",
            "dialogue-review-round4",
            "dialogue-review-round5",
            "dialogue-review-round6",
            "dialogue-review-round7",
            "dialogue-review-round8",
            "dialogue-review-round11",
            "dialogue-review-round18",
            "dialogue-review-round20",
            "dialogue-review-round21",
            "dialogue-review-round22",
            "dialogue-auto",
            "dialogue-format-pilot",
            "dialogue-format-batch1",
            "dialogue-format-page-pilot",
            "dialogue-format-batch2",
            "dialogue-format-mass",
        ),
        default="intro",
        help="generate the intro translation, dialogue alignment reports, or a gated SNES-formatting batch",
    )
    parser.add_argument(
        "--scrtxt",
        type=Path,
        default=DEFAULT_SCRTXT_FR,
        help="Android French scrtxt binary",
    )
    parser.add_argument(
        "--scrtxt-en",
        type=Path,
        default=DEFAULT_SCRTXT_EN,
        help="Android English scrtxt binary (required for dialogue alignment)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="destination JSON; defaults depend on --only",
    )
    parser.add_argument(
        "--unmapped-csv",
        type=Path,
        help="dialogue-auto unresolved CSV destination (default: mappings/android/dialogues_unmapped.csv)",
    )
    parser.add_argument(
        "--rom",
        type=Path,
        help="clean unheadered USA ROM; required for dialogue-format-* VWF metrics",
    )
    parser.add_argument(
        "--format-report",
        type=Path,
        help="dialogue-format report destination; default depends on the selected formatting mode",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify that the destination already equals generated output",
    )
    args = parser.parse_args()

    french_path = args.scrtxt.resolve()
    try:
        french = read_scrtxt(french_path)
        if args.only == "intro":
            document = make_intro_translation(french)
            output = (args.output or DEFAULT_INTRO_OUTPUT).resolve()
            source_label = str(french_path)
        else:
            english_path = args.scrtxt_en.resolve()
            english = read_scrtxt(english_path)
            if args.only == "dialogue-pilot":
                document = make_dialogue_pilot_report(
                    english,
                    french,
                    english_path=english_path,
                    french_path=french_path,
                )
                output = (args.output or DEFAULT_DIALOGUE_PILOT_OUTPUT).resolve()
            elif args.only == "dialogue-review":
                document = make_dialogue_review_round2_report(
                    english,
                    french,
                    english_path=english_path,
                    french_path=french_path,
                )
                output = (args.output or DEFAULT_DIALOGUE_REVIEW_OUTPUT).resolve()
            elif args.only == "dialogue-review-round3":
                document = make_dialogue_review_round3_report(
                    english,
                    french,
                    english_path=english_path,
                    french_path=french_path,
                )
                output = (args.output or DEFAULT_DIALOGUE_REVIEW_ROUND3_OUTPUT).resolve()
            elif args.only == "dialogue-review-round4":
                document = make_dialogue_review_round4_report(
                    english,
                    french,
                    english_path=english_path,
                    french_path=french_path,
                )
                output = (args.output or DEFAULT_DIALOGUE_REVIEW_ROUND4_OUTPUT).resolve()
            elif args.only == "dialogue-review-round5":
                document = make_dialogue_review_round5_report(
                    english,
                    french,
                    english_path=english_path,
                    french_path=french_path,
                )
                output = (args.output or DEFAULT_DIALOGUE_REVIEW_ROUND5_OUTPUT).resolve()
            elif args.only == "dialogue-review-round6":
                document = make_dialogue_review_round6_report(
                    english,
                    french,
                    english_path=english_path,
                    french_path=french_path,
                )
                output = (args.output or DEFAULT_DIALOGUE_REVIEW_ROUND6_OUTPUT).resolve()
            elif args.only == "dialogue-review-round7":
                document = make_dialogue_review_round7_report(
                    english,
                    french,
                    english_path=english_path,
                    french_path=french_path,
                )
                output = (args.output or DEFAULT_DIALOGUE_REVIEW_ROUND7_OUTPUT).resolve()
            elif args.only == "dialogue-review-round8":
                document = make_dialogue_review_round8_report(
                    english,
                    french,
                    english_path=english_path,
                    french_path=french_path,
                )
                output = (args.output or DEFAULT_DIALOGUE_REVIEW_ROUND8_OUTPUT).resolve()
            elif args.only == "dialogue-review-round11":
                document = make_dialogue_review_round11_report(
                    english,
                    french,
                    english_path=english_path,
                    french_path=french_path,
                )
                output = (args.output or DEFAULT_DIALOGUE_REVIEW_ROUND11_OUTPUT).resolve()
            elif args.only == "dialogue-review-round18":
                document = make_dialogue_review_round18_report(
                    english,
                    french,
                    english_path=english_path,
                    french_path=french_path,
                )
                output = (args.output or DEFAULT_DIALOGUE_REVIEW_ROUND18_OUTPUT).resolve()
            elif args.only == "dialogue-review-round20":
                document = make_dialogue_review_round20_report(
                    english,
                    french,
                    english_path=english_path,
                    french_path=french_path,
                )
                output = (args.output or DEFAULT_DIALOGUE_REVIEW_ROUND20_OUTPUT).resolve()
            elif args.only == "dialogue-review-round21":
                document = make_dialogue_review_round21_report(
                    english,
                    french,
                    english_path=english_path,
                    french_path=french_path,
                )
                output = (args.output or DEFAULT_DIALOGUE_REVIEW_ROUND21_OUTPUT).resolve()
            elif args.only == "dialogue-review-round22":
                document = make_dialogue_review_round22_report(
                    english,
                    french,
                    english_path=english_path,
                    french_path=french_path,
                )
                output = (args.output or DEFAULT_DIALOGUE_REVIEW_ROUND22_OUTPUT).resolve()
            elif args.only in ("dialogue-format-pilot", "dialogue-format-batch1", "dialogue-format-page-pilot", "dialogue-format-batch2", "dialogue-format-mass"):
                if args.rom is None:
                    raise ValueError(f"--rom is required for {args.only}")
                rom_path = args.rom.resolve()
                base_rom = rom_path.read_bytes()
                if args.only == "dialogue-format-pilot":
                    document, format_report = make_dialogue_format_pilot(
                        english,
                        french,
                        english_path=english_path,
                        french_path=french_path,
                        base_rom=base_rom,
                    )
                    output = (args.output or DEFAULT_DIALOGUE_FORMAT_PILOT_OUTPUT).resolve()
                elif args.only == "dialogue-format-batch1":
                    document, format_report = make_dialogue_format_batch1(
                        english,
                        french,
                        english_path=english_path,
                        french_path=french_path,
                        base_rom=base_rom,
                    )
                    output = (args.output or DEFAULT_DIALOGUE_FORMAT_BATCH1_OUTPUT).resolve()
                elif args.only == "dialogue-format-page-pilot":
                    document, format_report = make_dialogue_format_page_pilot(
                        english,
                        french,
                        english_path=english_path,
                        french_path=french_path,
                        base_rom=base_rom,
                    )
                    output = (args.output or DEFAULT_DIALOGUE_FORMAT_PAGE_PILOT_OUTPUT).resolve()
                elif args.only == "dialogue-format-batch2":
                    document, format_report = make_dialogue_format_batch2(
                        english,
                        french,
                        english_path=english_path,
                        french_path=french_path,
                        base_rom=base_rom,
                    )
                    output = (args.output or DEFAULT_DIALOGUE_FORMAT_BATCH2_OUTPUT).resolve()
                else:
                    document, format_report = make_dialogue_format_mass(
                        english,
                        french,
                        english_path=english_path,
                        french_path=french_path,
                        base_rom=base_rom,
                    )
                    output = (args.output or DEFAULT_DIALOGUE_FORMAT_MASS_OUTPUT).resolve()
            else:
                document = make_dialogue_auto_alignment(
                    english,
                    french,
                    english_path=english_path,
                    french_path=french_path,
                )
                output = (args.output or DEFAULT_DIALOGUE_AUTO_OUTPUT).resolve()
            source_label = f"{english_path} + {french_path} + assets/dialogues.json"
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc

    write_or_check(output, serialized(document), check=args.check, source_label=source_label)
    if args.only in ("dialogue-format-pilot", "dialogue-format-batch1", "dialogue-format-page-pilot", "dialogue-format-batch2", "dialogue-format-mass"):
        if args.only == "dialogue-format-pilot":
            default_report = DEFAULT_DIALOGUE_FORMAT_PILOT_REPORT
        elif args.only == "dialogue-format-batch1":
            default_report = DEFAULT_DIALOGUE_FORMAT_BATCH1_REPORT
        elif args.only == "dialogue-format-page-pilot":
            default_report = DEFAULT_DIALOGUE_FORMAT_PAGE_PILOT_REPORT
        elif args.only == "dialogue-format-batch2":
            default_report = DEFAULT_DIALOGUE_FORMAT_BATCH2_REPORT
        else:
            default_report = DEFAULT_DIALOGUE_FORMAT_MASS_REPORT
        report_output = (args.format_report or default_report).resolve()
        write_or_check(
            report_output,
            serialized(format_report),
            check=args.check,
            source_label=source_label + " + clean USA ROM VWF metrics",
        )
    if args.only == "dialogue-format-mass":
        excluded_csv_output = DEFAULT_DIALOGUE_FORMAT_MASS_EXCLUDED_CSV.resolve()
        source_document = json.loads(DIALOGUE_SOURCE.read_text(encoding="utf-8"))
        excluded_csv_bytes = ("\ufeff" + dialogue_format_mass_excluded_csv(format_report, source_document)).encode("utf-8")
        if args.check:
            try:
                existing_csv = excluded_csv_output.read_bytes()
            except OSError as exc:
                raise SystemExit(f"Cannot read {excluded_csv_output}: {exc}") from exc
            if existing_csv != excluded_csv_bytes:
                raise SystemExit(f"{excluded_csv_output} is not up to date with mass dialogue formatting")
            print(f"Dialogue mass exclusion CSV check OK: {excluded_csv_output}")
        else:
            excluded_csv_output.parent.mkdir(parents=True, exist_ok=True)
            excluded_csv_output.write_bytes(excluded_csv_bytes)
            print(f"Generated {excluded_csv_output} from mass dialogue formatting")

    if args.only == "dialogue-auto":
        csv_output = (args.unmapped_csv or DEFAULT_DIALOGUE_UNMAPPED_CSV).resolve()
        csv_text = "\ufeff" + dialogue_unmapped_csv(document)
        csv_bytes = csv_text.encode("utf-8")
        if args.check:
            try:
                existing_csv = csv_output.read_bytes()
            except OSError as exc:
                raise SystemExit(f"Cannot read {csv_output}: {exc}") from exc
            if existing_csv != csv_bytes:
                raise SystemExit(f"{csv_output} is not up to date with automatic dialogue alignment")
            print(f"Android alignment CSV check OK: {csv_output}")
        else:
            csv_output.parent.mkdir(parents=True, exist_ok=True)
            csv_output.write_bytes(csv_bytes)
            print(f"Generated {csv_output} from automatic dialogue alignment")

    if not args.check:
        if args.only == "intro":
            print(f"Imported {len(INTRO_ANDROID_IDS)} validated intro entries")
        elif args.only == "dialogue-pilot":
            accepted = sum(len(scene["entries"]) for scene in document["scenes"])
            print(
                f"Dialogue pilot: {accepted} very-high-confidence mappings; "
                f"{len(document['ambiguous'])} explicit manual-review cases; no translation JSON changed"
            )
        elif args.only == "dialogue-auto":
            coverage = document["coverage"]
            print(
                "Dialogue automatic alignment: "
                f"{coverage['mapped_semantic_source_id_count']}/{coverage['semantic_source_id_count']} "
                f"semantic source IDs mapped ({coverage['mapped_semantic_percent']}%); "
                f"{coverage['unmapped_semantic_source_id_count']} unresolved; no translation JSON changed"
            )
        elif args.only in ("dialogue-format-pilot", "dialogue-format-batch1", "dialogue-format-page-pilot", "dialogue-format-batch2", "dialogue-format-mass"):
            if args.only == "dialogue-format-pilot":
                event_key, label = "pilot_events", "pilot"
            elif args.only == "dialogue-format-batch1":
                event_key, label = "batch_events", "batch 1"
            elif args.only == "dialogue-format-page-pilot":
                event_key, label = "page_pilot_events", "extra-page pilot"
            elif args.only == "dialogue-format-batch2":
                event_key, label = "batch2_events", "batch 2"
                print(
                    f"Dialogue format {label}: "
                    f"{format_report['translation_entry_count']} formatted source token(s) in event(s) "
                    + ", ".join(format_report[event_key])
                )
            else:
                coverage = format_report["coverage"]
                print(
                    "Dialogue format mass: "
                    f"{coverage['accepted_event_count']} simulator-clean event(s), "
                    f"{coverage['translation_entry_count']} translated source token(s); "
                    f"{coverage['excluded_event_count']} event(s) excluded"
                )
                event_key = None
            if args.only != "dialogue-format-mass" and args.only != "dialogue-format-batch2":
                print(
                    f"Dialogue format {label}: "
                    f"{format_report['translation_entry_count']} formatted source token(s) in event(s) "
                    + ", ".join(format_report[event_key])
                )
        else:
            units = sum(len(scene["units"]) for scene in document["scenes"])
            state = "user-validated" if document["status"].endswith("user_validated") else "candidate review"
            print(f"Dialogue {document['status'].split('_')[0]}: {units} {state} units; no translation JSON changed")


if __name__ == "__main__":
    main()
