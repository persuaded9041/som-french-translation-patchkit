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
import csv
from difflib import SequenceMatcher
import hashlib
from itertools import combinations
import json
import math
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
    player_placeholder_width,
    MAX_PLAYER_NAME_CHARS,
    make_translation_document as make_dialogue_translation_document,
)
from shared.dialogue_codec import (  # noqa: E402
    TRANSLATION_CLEAR, TRANSLATION_TRAILING_PAGE_BREAK_ALLOWLIST, parse_event,
)
from shared.translation_json import (  # noqa: E402
    resolve_structural_omission_token_indexes,
    resolve_structural_command_overrides,
)
from shared.rom import validate_base_rom  # noqa: E402

DEFAULT_SCRTXT_EN = ROOT / "sources" / "android" / "scrtxt_en.bin"
DEFAULT_SCRTXT_FR = ROOT / "sources" / "android" / "scrtxt_fr.bin"
DEFAULT_SYSTXT_EN = ROOT / "sources" / "android" / "systxt_en.bin"
DEFAULT_SYSTXT_FR = ROOT / "sources" / "android" / "systxt_fr.bin"
DEFAULT_INTRO_OUTPUT = ROOT / "translations" / "intro_event_french.json"
DEFAULT_DIALOGUE_PILOT_OUTPUT = ROOT / "mappings" / "android" / "dialogues_pilot.json"
DEFAULT_DIALOGUE_REVIEW_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round2.json"
DEFAULT_DIALOGUE_REVIEW_ROUND3_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round3.json"
DEFAULT_DIALOGUE_REVIEW_ROUND4_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round4.json"
DEFAULT_DIALOGUE_REVIEW_ROUND5_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round5.json"
DEFAULT_DIALOGUE_REVIEW_ROUND6_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round6.json"
DEFAULT_DIALOGUE_REVIEW_ROUND7_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round7.json"
DEFAULT_DIALOGUE_REVIEW_ROUND8_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round8.json"
DIALOGUE_REDISTRIBUTION_RECIPES = ROOT / "mappings" / "android" / "dialogues_redistribution_recipes.json"
DIALOGUE_CHOICE_LAYOUT_RECIPES = ROOT / "mappings" / "android" / "dialogues_choice_layout_recipes.json"
DEFAULT_DIALOGUE_REVIEW_ROUND11_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round11.json"
DEFAULT_DIALOGUE_REVIEW_ROUND18_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round18.json"
DEFAULT_DIALOGUE_REVIEW_ROUND20_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round20.json"
DEFAULT_DIALOGUE_REVIEW_ROUND21_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round21.json"
DEFAULT_DIALOGUE_REVIEW_ROUND22_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round22.json"
DEFAULT_DIALOGUE_REVIEW_ROUND25_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round25.json"
DEFAULT_DIALOGUE_REVIEW_ROUND31_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round31.json"
DEFAULT_DIALOGUE_REVIEW_ROUND33_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round33.json"
DEFAULT_DIALOGUE_REVIEW_ROUND34_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round34.json"
DEFAULT_DIALOGUE_REVIEW_ROUND39_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round39.json"
DEFAULT_DIALOGUE_REVIEW_ROUND40_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round40.json"
DEFAULT_DIALOGUE_REVIEW_ROUND41_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round41.json"
DEFAULT_DIALOGUE_REVIEW_ROUND42_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round42.json"
DEFAULT_DIALOGUE_REVIEW_ROUND43_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round43.json"
DEFAULT_DIALOGUE_REVIEW_ROUND44_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round44.json"
DEFAULT_DIALOGUE_REVIEW_ROUND45_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round45.json"
DEFAULT_DIALOGUE_REVIEW_ROUND46_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round46.json"
DEFAULT_DIALOGUE_REVIEW_ROUND47_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round47.json"
DEFAULT_DIALOGUE_REVIEW_ROUND48_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round48.json"
DEFAULT_DIALOGUE_REVIEW_ROUND49_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round49.json"
DEFAULT_DIALOGUE_REVIEW_ROUND50_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round50.json"
DEFAULT_DIALOGUE_REVIEW_ROUND51_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round51.json"
DEFAULT_DIALOGUE_REVIEW_ROUND52_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round52.json"
DEFAULT_DIALOGUE_REVIEW_ROUND53_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round53.json"
DEFAULT_DIALOGUE_REVIEW_ROUND54_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round54.json"
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


# Round 25 is the second high-leverage structural pass.  It targets only
# nearly-complete events where Android English proves the missing SNES carrier
# through an exact local merge/continuation or a uniquely bracketed scene line.
# Android French remains payload only.
DIALOGUE_REVIEW_ROUND25 = (
    {
        "event_id": "01B5",
        "label": "Watts axe explanation split across two SNES carriers",
        "units": (
            (("C9:6921", "C9:6954"), (577,), "many_snes_to_one_android", "very_high_structural", "Android EN 577 is exactly the concatenation of the two consecutive SNES thoughts: 'Wait! I know! Try holding this axe!' followed by the already aligned Mana-power explanation."),
        ),
    },
    {
        "event_id": "04FD",
        "label": "Ending girl response between Ever and Dyluck",
        "units": (
            (("CA:4E59",), (3372,), "ordered_scene_equivalence", "very_high_structural", "SNES '...Me too!' is the girl's response in the unique slot directly between already aligned Android 3371 'Ever!' and 3374 'And Dyluck too...'; Android EN renders the same response as '...Me neither!'."),
        ),
    },
    {
        "event_id": "028B",
        "label": "Sandship commander move order",
        "units": (
            (("C9:ABBE",), (1535,), "ordered_scene_equivalence", "very_high_structural", "Android EN 1535 'Hey! Didn't you hear what I just said? Move!' is the immediate continuation of already aligned 1534 and is semantically identical to SNES 'You heard him! Move!'."),
        ),
    },
    {
        "event_id": "01E7",
        "label": "Elinee Thanatos explanation",
        "units": (
            (("C9:8512",), (779,), "ordered_scene_equivalence", "very_high_structural", "Android EN 779 is the unique Thanatos-description line directly between already aligned 778 and 780 in the same Elinee confrontation; both versions explain that Thanatos is the agent who will overthrow/crush the kingdom from within."),
        ),
    },
    {
        "event_id": "04B6",
        "label": "Dryad palace failure reaction",
        "units": (
            (("CA:2237",), (2702,), "ordered_scene_equivalence", "very_high_structural", "Android EN 2702 'Oh no! It's not working!' is the unique reaction between already aligned 2700 seal failure and 2704 evacuation order; SNES expresses the same failed attempt as 'No good! It's too late!'."),
        ),
    },
    {
        "event_id": "0133",
        "label": "Luka speaker prefix merged into question",
        "units": (
            (("C9:3C90", ("player_name", 0), "C9:3C97"), (811,), "speaker_prefix_join", "very_high_structural", "SNES stores 'LUKA:' separately from the already aligned question; Android EN 811 stores the same speaker label and question in one record."),
        ),
    },
    {
        "event_id": "0180",
        "label": "Jema speaker prefix merged into greeting",
        "units": (
            (("C9:5634", ("player_name", 0), "C9:563B"), (372,), "speaker_prefix_join", "very_high_structural", "SNES stores 'JEMA:' separately from the already aligned greeting; Android EN 372 stores the same speaker label and greeting in one record."),
        ),
    },
    {
        "event_id": "002F",
        "label": "Phanna speaker prefix merged into thanks",
        "units": (
            (("C9:0D94", ("player_name", 1), "C9:0D9D"), (2697,), "speaker_prefix_join", "very_high_structural", "SNES stores 'PHANNA:' separately from the already aligned thanks line; Android EN 2697 stores the same speaker label and line in one record."),
        ),
    },
)


# Round 31 is a narrow second-pass follow-up on nearly-complete events.  Every
# added identity is justified by ordered Android-English structure; Android
# French remains localization payload only.
DIALOGUE_REVIEW_ROUND31 = (
    {
        "event_id": "0186",
        "label": "Girl recognition and swordsman question merged into one SNES carrier",
        "units": (
            (("C9:591B",), (343, 344), "ordered_scene_segmentation", "very_high_structural", "Android EN 343/344 are the two consecutive recognition/question anchors immediately before already accepted 345-352. SNES stores the same exchange in one carrier; 344 is an exact 'You're a swordsman?' match and 343 is the localized adaptation of the preceding recognition line."),
            ((("player_name", 0), "C9:5A85", ("player_name", 0), "C9:5A8C"), (351, 352), "player_name_presentation_join", "very_high_structural", "Android EN 351/352 is exactly the final name-presentation exchange. SNES stores the period after the second PLAYER_NAME in the following carrier, so bind both existing text carriers together while preserving both PLAYER_NAME commands in place."),
        ),
    },
    {
        "event_id": "0384",
        "label": "Stove introduction boundary shifted by Android segmentation",
        "units": (
            (("C9:D913",), (1796,), "ordered_scene_resegmentation", "very_high_structural", "Android EN 1796 exactly covers the greeting/recognition portion of the first SNES carrier. Its trailing SNES sentence 'Watch this stove.' is the opening of already accepted Android 1797, so identity is preserved by assigning only 1796 here and leaving the existing C9:D951 -> 1797 mapping unchanged."),
        ),
    },
    {
        "event_id": "042D",
        "label": "Thanatos escape reaction split around stock WAIT $10",
        "units": (
            ((('player_name', 0), "CA:14AB", "CA:14BA"), (3306,), "timed_wait10_resegmentation", "very_high_structural", "Android EN 3306 is the exact combined player-name reaction 'What the...!? Let's get out of here!'. SNES stores it in two consecutive carriers separated only by the stock WAIT $10; preserve the PLAYER_NAME, WAIT and the second carrier's stock leading newline."),
            ((("player_name", 2), "CA:14D7"), (3307,), "trim_distant_player_context", "very_high_structural", "Android EN 3307 is exactly PLAYER_NAME(2): 'Uwaa!'. The automatic alignment had borrowed the later PLAYER_NAME(0) only as look-ahead context across a long action/effect bridge; keep that later name with the following mapping instead of treating it as part of this identity."),
        ),
    },
)


# Round 33 continues the high-leverage second pass.  The first three scenes
# were established by local Android-English structure and then shown to the
# user in the dedicated validation HTML together with the remaining short
# candidates.  The complete batch below is user-validated.  Android English
# remains the identity layer; Android French is payload only.
DIALOGUE_REVIEW_ROUND33 = (
    {
        "event_id": "04E6",
        "label": "Potos banishment scene resegmented across Android anchors",
        "units": (
            (("CA:3E7B", "CA:3EA8"), (76,), "ordered_scene_resegmentation", "very_high_structural", "Android EN 76 contains the two consecutive villager protests that SNES stores in two carriers."),
            (("CA:3F11",), (80,), "contained_android_extension", "very_high_structural", "SNES begins the elder accusation; Android EN 80 contains the same opening followed by the sword explanation continued by the next mapped SNES carrier."),
            (("CA:3F97",), (82,), "contained_android_extension", "very_high_structural", "SNES 'VILLAGER: It's settled.' is the exact opening of Android EN 82 before the already aligned continuation."),
        ),
    },
    {
        "event_id": "04E2",
        "label": "Sprite village elder scene local resegmentation",
        "units": (
            (("CA:32F6",), (1282, 1283), "ordered_scene_resegmentation", "very_high_structural", "Android EN 1282/1283 is the same elder response/reaction block; French legitimately redistributes the reaction into the following localization record."),
            (("CA:3335", "CA:3359"), (1285,), "ordered_scene_resegmentation", "very_high_structural", "Between exact anchors 1284 and 1286, Android EN has only 1285; SNES splits the elder's transition into 'Okay, okay!' and 'Tyke!'."),
            (("CA:34DD",), (1297, 1298), "preserve_accepted_mapping", "very_high_structural", "Freeze the previously accepted Sylphid/Grandpa mapping byte-for-byte while adding the adjacent 1299 identity."),
            (("CA:352B",), (1299,), "contained_android_equivalence", "very_high_structural", "SNES 'Sylphid: It is so!' and Android EN 1299 'Sylphid: As you wish!' are the same response in the tightly bracketed Sylphid exchange."),
        ),
    },
    {
        "event_id": "04E1",
        "label": "Thanatos and Dyluck final scene high-confidence local identities",
        "units": (
            (("CA:2E21",), (3283,), "ordered_scene_equivalence", "very_high_structural", "Unique local Thanatos laugh immediately before the already aligned body-transfer speech."),
            (("CA:2FDA",), (3294,), "contained_android_equivalence", "very_high_structural", "Both versions explain that Thanatos' spirit/life is eternal but each inhabited body is mortal."),
            (("CA:301C",), (3295,), "contained_android_equivalence", "very_high_structural", "Both versions state that each new host makes Thanatos darker and that he feeds on hatred/destruction."),
            (("CA:30F8",), (3302, 3303), "ordered_scene_resegmentation", "very_high_structural", "SNES combines the girl's plea and Thanatos' cry; Android EN stores them in consecutive 3302/3303."),
            (("CA:3190",), (3305,), "ordered_scene_equivalence", "very_high_structural", "Exact local demand for the heroes' bodies immediately before the already aligned escape reaction."),
        ),
    },
    {
        "event_id": "02F1",
        "label": "Single-line greeting between consecutive Android anchors",
        "units": (
            (("C9:C8A2",), (2287,), "user_validated_contextual_short_exact", "user_validated", "Exact 'Hello!' bracketed by event $02F0 -> 2286 and $02F2 -> 2288."),
        ),
    },
    {
        "event_id": "02F2",
        "label": "Single-line cry between consecutive Android anchors",
        "units": (
            (("C9:C8AC",), (2288,), "user_validated_contextual_short_exact", "user_validated", "Exact 'Aieeee!' bracketed by $02F1 -> 2287 and $02F3 -> 2289."),
        ),
    },
    {
        "event_id": "066F",
        "label": "Validated short command in local scene",
        "units": (
            (("CA:8E0B",), (1844,), "user_validated_contextual_short_exact", "user_validated", "User validated the local ...SCRAM...! identity after reviewing Android EN/FR context."),
        ),
    },
    {
        "event_id": "059D",
        "label": "Validated locked-door line",
        "units": (
            (("CA:7731",), (2513,), "user_validated_contextual_short_exact", "user_validated", "User validated the exact Locked! identity in its local Android context."),
        ),
    },
    {
        "event_id": "0194",
        "label": "Validated Papa cry",
        "units": (
            (("C9:5FA5",), (371,), "user_validated_contextual_short_exact", "user_validated", "User validated Papa!! -> Android EN 371 Papa!!! in the local Pandora scene."),
        ),
    },
    {
        "event_id": "0111",
        "label": "Validated silent man label",
        "units": (
            (("C9:32EF",), (105,), "user_validated_contextual_short_exact", "user_validated", "User validated MAN: ... -> Android EN 105 Man: ... in the local Potos sequence."),
        ),
    },
    {
        "event_id": "04AB",
        "label": "Imperial troop hold-off instruction",
        "units": (
            (("CA:1BED",), (2746,), "user_validated_contextual_duplicate", "user_validated", "User validated Android EN 2746 for the SNES two-line hold-off/catch-up instruction; 2747 is a duplicate localization record."),
        ),
    },
    {
        "event_id": "03A6",
        "label": "Password 634 call separated from Enter tail",
        "units": (
            (("C9:E0FA",), (1889,), "user_validated_event_segmentation", "user_validated", "User validated the separated Android anchor 1889 for the standalone 634! event."),
        ),
    },
    {
        "event_id": "03A7",
        "label": "Password Enter tail",
        "units": (
            (("C9:E113",), (1890,), "user_validated_event_segmentation", "user_validated", "User validated Android EN 1890 for the Enter! tail after reviewing the combined and separated Android variants."),
        ),
    },
    {
        "event_id": "05B1",
        "label": "Password failure response",
        "units": (
            (("CA:781E",), (1874,), "user_validated_password_sequence", "user_validated", "User validated the first Go away! anchor in the password-entry block."),
        ),
    },
    {
        "event_id": "05B2",
        "label": "Password progress 6 ? ?",
        "units": (
            (("CA:7833",), (1877,), "user_validated_password_sequence", "user_validated", "User validated the exact 6 ? ? progress anchor in the password-entry block."),
        ),
    },
    {
        "event_id": "05B3",
        "label": "Password progress 6 3 ?",
        "units": (
            (("CA:784E",), (1878,), "user_validated_password_sequence", "user_validated", "User validated the exact 6 3 ? progress anchor in the password-entry block."),
        ),
    },
    {
        "event_id": "05B4",
        "label": "Password 634 plus shared Enter tail",
        "units": (
            (("CA:7864",), (1887,), "shared_called_tail_combined_anchor", "user_validated", "Identity is user-validated: Android EN 1887 combines 634 with the Enter! tail supplied on SNES by called event $03A7. Keep the identity, but do not inject the combined French payload into CA:7864 or it would duplicate the translated $03A7 tail."),
        ),
    },
)


# Round 34 continues the second high-leverage pass with only explicit
# Android-English identities supported by tight local scene context.  No new
# generic matcher rule is introduced here.
DIALOGUE_REVIEW_ROUND34 = (
    {
        "event_id": "00B6",
        "label": "Gold City residence/hotel sign between adjacent local anchors",
        "units": (
            (("C9:1832",), (2478,), "tight_local_scene_anchor", "very_high_structural", "Android EN 2478 is the unique King Mammon residence/hotel line, directly bracketed by the same Gold City block: $00B7 -> 2477 and $00B3 -> 2479-2481."),
        ),
    },
    {
        "event_id": "00BC",
        "label": "Gold City Watts shop line",
        "units": (
            (("C9:1984",), (2494,), "unique_local_scene_equivalence", "very_high_structural", "Android EN 2494 is the unique Watts line in the same Gold City localization block and closely matches the complete SNES carrier; the following Watts forge prompt is Android 2496."),
        ),
    },
    {
        "event_id": "013B",
        "label": "Luka Jema status line in ordered Water Palace sequence",
        "units": (
            (("C9:4123",), (874,), "exact_duplicate_resolved_by_scene", "very_high_structural", "The SNES line has two exact Android-EN duplicates (479/874); 874 is fixed by the local Luka sequence, immediately after $0139 -> 872-873 and before the adjacent 875/876 continuation."),
        ),
    },
    {
        "event_id": "013F",
        "label": "Luka hope line immediately before stolen-seed scene",
        "units": (
            (("C9:4437",), (875,), "contained_local_scene_anchor", "very_high_structural", "Android EN 875 contains the complete SNES sentence and sits directly between the resolved Luka anchors 874 and $013C -> 876."),
        ),
    },
    {
        "event_id": "0151",
        "label": "Pandora family anti-war line",
        "units": (
            (("C9:4881",), (311,), "tight_local_scene_anchor", "very_high_structural", "Android EN 311 is the unique close equivalent in the local Pandora family block, between $0150 -> 309 and $0152 -> 312; Android 310 is only an ellipsis."),
        ),
    },
    {
        "event_id": "0158",
        "label": "Pandora missing-family line",
        "units": (
            (("C9:4A76",), (296,), "unique_local_scene_equivalence", "very_high_structural", "Android EN 296 uniquely matches the missing wife/Phanna line inside the same local family/NPC block already occupied by 297-307 in neighboring SNES events."),
        ),
    },
    {
        "event_id": "01C0",
        "label": "Dwarf Village location line",
        "units": (
            (("C9:6FA4",), (482,), "tight_local_scene_anchor", "very_high_structural", "Android EN 482 is the unique village-location line and immediately precedes the already aligned Dwarf Village run $01C1-$01C4 -> 483-487."),
        ),
    },
    {
        "event_id": "02E2",
        "label": "Tasnica Serin settlement history line",
        "units": (
            (("C9:C58C",), (2548,), "unique_local_scene_equivalence", "very_high_structural", "Android EN 2548 uniquely carries the Serin/fifteen-years-ago castle history inside the Tasnica 2539-2565 scene block used by the neighboring events."),
        ),
    },
    {
        "event_id": "0390",
        "label": "Ice Country resident moved from Gold City",
        "units": (
            (("C9:DC7A",), (1811,), "tight_local_scene_anchor", "very_high_structural", "Android EN 1811 is the unique near-exact line, directly between the local resident anchors 1808-1810 and $0391 -> 1812."),
        ),
    },
    {
        "event_id": "03E7",
        "label": "Lofty Mountains meditation NPC",
        "units": (
            (("C9:EF61",), (2343,), "tight_local_scene_anchor", "very_high_structural", "Android EN 2343 is the unique meditation complaint, directly bracketed by $03E4 -> 2340-2342 and $03E8 -> 2344."),
        ),
    },
)


# Round 39 records the user's validation of the four contextual cases reviewed
# with full SNES-US call-site/object evidence.  Three choose a concrete Android
# provenance/payload for a SNES carrier reused or duplicated by Android.  $0689
# keeps Android EN 769 as the proven identity but intentionally rejects the bad
# Android-FR payload and routes the exact stock-USA source text through the
# ordinary `french_dialogues` translation/relocation pipeline.
DIALOGUE_REVIEW_ROUND39 = (
    {
        "event_id": "019C",
        "label": "Pandora Castle guard - equivalent duplicated Android carrier",
        "units": (
            (("C9:61D3",), (385,), "equivalent_duplicate_positional_tiebreak", "user_validated", "Android EN/FR 381 and 385 are strictly identical guard lines. Full SNES context shows the shared Pandora guard carrier; choose 385 because it belongs to the adjacent 386-388 Pandora block while retaining 381 as documented equivalent provenance."),
        ),
    },
    {
        "event_id": "01EA",
        "label": "Elinee treasure-chest reused SNES subevent",
        "units": (
            (("C9:86C6",), (759,), "reused_snes_subevent_primary_payload", "user_validated", "The same SNES subevent is called from two contexts that Android materializes as 759 and 762. Both Android EN strings are identical; choose FR payload 759 because it carries the shared utterance without the Android-only 'Elinice :' speaker prefix duplicated by the second call-site entry."),
        ),
    },
    {
        "event_id": "02A9",
        "label": "Sandship Kakkara directions reused SNES subevent",
        "units": (
            (("C9:B5CE",), (1583,), "reused_snes_subevent_primary_payload", "user_validated", "The same SNES subevent is called twice and Android materializes the two call sites as 1577 and 1583. User accepts 1583 as the shared payload; it preserves 'Royaume de Kakkara' rather than changing Kakkara into a city."),
        ),
    },
    {
        "event_id": "0689",
        "label": "Leather Whip chest - Android-FR localization error",
        "units": (
            (("CA:8F20",), (769,), "user_validated_stock_english_override", "user_validated", "Android EN 769 is structurally proven by the event item command: $0689 executes OP_1E A4, i.e. weapon $24 = Whip/Leather Whip. The true Magic Rope chest is $0687 with OP_1E 46, item $06. Android FR incorrectly gives the same 'Fouet en cuir' text to both 469 (Magic Rope) and 769. Keep exact stock-USA 'Found the Whip!' instead of importing that bad localization."),
        ),
    },
)

# Round 40 accepts only structurally locked resegmentation cases discovered
# after the Round-39 full-context audit.  These are explicit reviewed mappings,
# not a new generic fuzzy rule: Android EN identity is fixed by contiguous local
# scene order and the SNES carrier/call structure.
DIALOGUE_REVIEW_ROUND40 = (
    {
        "event_id": "00C0",
        "label": "Gold City Mammon boast - unique missing anchor in reconstructed block",
        "units": (
            (("C9:1A33",), (2508,), "contiguous_scene_gap", "very_high_structural", "SNES events $00BB/$00BA/$00B9/$00B8/$00BD/$00BE already map to Android 2505/2506/2507/2509/2510/2511/2512. Mammon's Money...MONEY / all MINE boast is the only missing Gold City utterance and Android EN 2508 is the unique intervening Mammon: Gold... GOLD! / all MINE line."),
        ),
    },
    {
        "event_id": "011B",
        "label": "Potos final banishment - second call-site after departure prompt",
        "units": (
            (("C9:3801",), (35,), "callsite_duplicate_disambiguation", "very_high_structural", "Android EN 31 and 35 repeat the same banishment sentence with different FR payloads. SNES $011B follows $011A Have everything you need? / Yes / No, exactly matching Android 32-34 followed by the second banishment at 35; therefore 35 is the correct call-site localization."),
        ),
    },
    {
        "event_id": "023C",
        "label": "Neko save-buy-sell block - lines immediately before proven choices",
        "units": (
            (("C9:9D5F",), (1205,), "equivalent_duplicate_same_block_tiebreak", "very_high_structural", "Android EN/FR 1184 and 1205 are strict equivalent copies of Neko: Purrrfect weather!. The stock $023C choice carriers Save/Buy/Sell are already concretely aligned to 1207/1208/1209, so the copy in that exact block is 1205."),
            (("C9:9D7C",), (1206,), "contiguous_prompt_replacement", "very_high_structural", "SNES What can I do for you? is the prompt immediately before Save/Buy/Sell. Android 1206 occupies exactly the same slot immediately before the already proven 1207-1209 choices; Android rewrites the generic prompt as Neko: Meow, busy travelers! I'll even save the game!. Identity is structural block position, not French wording."),
        ),
    },
    {
        "event_id": "0114",
        "label": "Potos elder banishment apology - two SNES carriers to one Android line",
        "units": (
            (("C9:364B", "C9:369A"), (90,), "multi_carrier_android_extension", "very_high_structural", "The two SNES carriers form one continuous Elder speech. Android EN 90 contains the whole speech with minor wording expansion and sits in the same Potos banishment block immediately before the already aligned $0115-$0118 lines 99/98/96/97."),
        ),
    },
    {
        "event_id": "02C0",
        "label": "Karon ferry sign - split SNES sign to one Android anchor",
        "units": (
            (("C9:BC60", "C9:BC72"), (2629,), "exact_split_sign_resegmentation", "very_high_structural", "The two positioned SNES carriers concatenate to Karon's Ferry / Out to lunch; Android EN 2629 is the unique combined sign and is bracketed by the adjacent Karon ferry events $02C1/$02C2."),
        ),
    },
    {
        "event_id": "03ED",
        "label": "Mandala video - Mana-energy debate contiguous Android block",
        "units": (
            (("C9:F13C",), (2364, 2365, 2366), "contiguous_android_resegmentation", "very_high_structural", "The preceding carrier is already Android 2362-2363; this carrier contains the next three debate utterances in order and therefore maps to the immediately contiguous Android EN 2364-2366."),
            (("C9:F18D",), (2367,), "contiguous_android_transition_extension", "very_high_structural", "This is the terminal static/noise carrier of the same video. Android EN 2367 is the immediately following static transition before the already aligned $03EB/$03EC material; the Android version spells out more of the static/beep sequence."),
        ),
    },
    {
        "event_id": "0555",
        "label": "Dyluck confrontation - contiguous call-structured Android scene",
        "units": (
            (("CA:632B", ("player_name", 1), "CA:6337"), (2157,), "placeholder_join", "very_high_structural", "The SNES Dyluck prefix, PLAYER_NAME(1), and At last continuation are one utterance; Android EN 2157 is exactly the corresponding line between the already aligned 2156 and 2158 anchors."),
            (("CA:63F1",), (2165,), "contained_local_scene_anchor", "very_high_structural", "Android EN 2165 is the unique Dyluck/Thanatos continuation immediately after the already aligned 2164 line. Android expands the explanation but preserves the same scene identity."),
            (("CA:6423",), (2166, 2167), "contiguous_android_resegmentation", "very_high_structural", "The SNES carrier contains both You can't be serious / She LOVES you and I can't handle this; Android EN splits those clauses across the consecutive anchors 2166 and 2167, directly before the already aligned 2170 Dyluck recovery line."),
        ),
    },
)



# Round 41 records the user's validation of the determinate candidates from the
# Round-40 contextual HTML.  The two genuinely unresolved HTML cases ($0235 and
# $03CF) are intentionally not included here: no unique identity was proposed.
DIALOGUE_REVIEW_ROUND41 = (
    {
        "event_id": "0013",
        "label": "Pandora troops sent against the witch - mobile paraphrase in locked scene block",
        "units": (
            (("C9:0923",), (389,), "user_validated_scene_paraphrase", "user_validated", "Full SNES-US context and the Pandora/Elinee Android block identify 389 as the same state dialogue: the SNES says the troops sent to fight the witch were captured, while Android EN paraphrases them as soundly defeated. User validated this identity from the contextual HTML."),
        ),
    },
    {
        "event_id": "028E",
        "label": "Republic secret sandship - Android extension in the same Sandship block",
        "units": (
            (("C9:AC32",), (1505,), "user_validated_android_extension", "user_validated", "Android EN 1505 begins with the exact Republic secret sandship identity and extends it with the Fire Palace mission. It sits directly in the Sandship block whose adjacent SNES events map to 1503-1507. User validated using the full-context HTML."),
        ),
    },
    {
        "event_id": "060A",
        "label": "Cannon Travel reusable destination label - Water Palace",
        "units": (
            (("CA:86B5",), (421,), "user_validated_reused_label_anchor", "user_validated", "This RETURN subevent is the reusable Water Palace destination label. Android 421 is the Water Palace label paired with 422 Pandora in the same Cannon Travel destination block; the same anchor may legitimately be reused by another SNES caller. User validated this provenance."),
        ),
    },
    {
        "event_id": "060B",
        "label": "Cannon Travel reusable destination label - Pandora",
        "units": (
            (("CA:86C3",), (422,), "user_validated_reused_label_anchor", "user_validated", "This RETURN subevent is the reusable Kingdom of Pandora/Pandora destination label. Android 422 is the paired Pandora label immediately after Water Palace 421 in the same Cannon Travel block. User validated using the full-context HTML."),
        ),
    },
)


# Round 42 records the user's validation of four contextually reconstructed
# identities from the dedicated full-context HTML.  These remain explicit local
# review evidence: no generic short-exact/fuzzy matcher is added or weakened.
DIALOGUE_REVIEW_ROUND42 = (
    {
        "event_id": "0235",
        "label": "Tonpole/Biting Lizard aftermath - trigger/map/reward locked short reaction",
        "units": (
            (("C9:9B74",), (951,), "user_validated_trigger_scene_duplicate", "user_validated", "The short SNES reaction is textually ambiguous, but map $0115's walk-on trigger enters $0232 -> $0235 on the Tonpole/Biting Lizard boss map; Android EN 951 is the matching reaction immediately before 952 Received Gloves Orb. Android FR adds a presentation-only %S(0,0) speaker label absent from the SNES carrier; the existing formatter policy removes only that label without inventing PLAYER_NAME."),
        ),
    },
    {
        "event_id": "03CF",
        "label": "Phanna at the doctor's house - direct map-object/state provenance",
        "units": (
            (("C9:E993",), (1976,), "user_validated_map_object_state_duplicate", "user_validated", "SNES $03CF is the direct event of map $007E object #4, visible only for event flag $3A == 2. The same map object set contains $03B5/$03B6/$03B7 already aligned to Android 1972/1973/1971, while doctor event $03BD is 1974+1975; Android EN 1976 is therefore the unique Phanna ellipsis in this exact scene state."),
        ),
    },
    {
        "event_id": "0521",
        "label": "Emperor guard - called welcome prefix merged into Android record",
        "units": (
            (("CA:5CE6",), (2203,), "called_prefix_android_merge_suffix", "user_validated", "SNES $0521 first calls $04D4, which renders 'Welcome. The Emperor awaits you.', then its own carrier renders 'To your right, please.'. Their normalized concatenation is exactly Android EN 2203; Android 2204 is a strict EN+FR duplicate. Serialize only the official French suffix after the Android presentation separator so the already translated $04D4 welcome is not duplicated."),
        ),
    },
    {
        "event_id": "01D5",
        "label": "Sprite-village elder reusable positive-response subevent",
        "units": (
            (("C9:7C25",), (605,), "user_validated_reused_subevent_equivalent_extension", "user_validated", "SNES $01D5 is reused by three call-sites. Android EN 605 and 608 are strict duplicate copies of the same elder response and their French payloads are identical; 605 is the representative anchor. Android extends the SNES wording with one short instruction sentence, which fits the existing three-line carrier safely."),
        ),
    },
)


# Round 43 records the user's validation of the high-leverage structural
# families from the dedicated contextual HTML.  These are explicit local
# identities/resegmentations, not a new automatic matcher rule.  Dryad is
# deliberately absent here because Android has no matching English anchor; its
# user-authorized temporary French payload lives in the manual supplements file
# and therefore remains outside Android identity coverage.
DIALOGUE_REVIEW_ROUND43 = (
    {
        "event_id": "022F",
        "label": "Game-over rescue line - PLAYER_NAME(2) joins two SNES carriers",
        "units": (
            (("C9:9B1B", ("player_name", 2), "C9:9B2C"), (1005,), "round43_player_name_resegmentation", "user_validated", "The two SNES carriers plus the unchanged PLAYER_NAME(2) command reconstruct exactly 'We can't leave %S(2,0) like this.'. Android EN 1005 is therefore exact; Android FR adds one official explanatory sentence. The reviewed formatter keeps PLAYER_NAME in place and adds an explicit page boundary so the maximum player name remains parser-safe."),
        ),
    },
    {
        "event_id": "02B9",
        "label": "Salamando missing - shared prefix before a branch",
        "units": (
            (("C9:BAD6", "C9:BAE8"), (1618,), "round43_shared_branch_prefix_redistribution", "user_validated", "C9:BAD6 'Salamando is ' is shared by a conditional branch: the jump path continues in already-aligned $02BD -> Android 1619 ('Salamando's my friend...'), while the fallthrough combines C9:BAD6+C9:BAE8 into Android 1618 ('Salamando is gone!...'). Android FR restructures both lines, so the shared prefix must become empty and the complete 1618 French payload belongs only to the fallthrough carrier."),
        ),
    },
    {
        "event_id": "0358",
        "label": "Gnome orb reaction - composed shared suffix",
        "units": (
            (("C9:D12C",), (2839,), "round43_shared_magic_prefix", "user_validated", "$0358 renders 'Gnome' then jumps to shared $0360 " + '"\'s magic / will work!"' + ", reconstructing exactly Android EN 2839. The full French sentence fits in the spirit-name carrier; $0360 is handled separately as shared layout-only suffix."),
        ),
    },
    {
        "event_id": "0359",
        "label": "Undine orb reaction - composed shared suffix",
        "units": (
            (("C9:D13F",), (2844,), "round43_shared_magic_prefix", "user_validated", "$0359 + shared $0360 reconstruct exactly Android EN 2844 'Undine's magic will work!'. The full official French sentence is serialized in the name carrier."),
        ),
    },
    {
        "event_id": "035A",
        "label": "Sylphid orb reaction - composed shared suffix",
        "units": (
            (("C9:D153",), (2852,), "round43_shared_magic_prefix", "user_validated", "$035A + shared $0360 reconstruct exactly Android EN 2852 'Sylphid's magic will work!'. The full official French sentence is serialized in the name carrier."),
        ),
    },
    {
        "event_id": "035B",
        "label": "Salamando orb reaction - composed shared suffix",
        "units": (
            (("C9:D168",), (2857,), "round43_shared_magic_prefix", "user_validated", "$035B + shared $0360 reconstruct exactly Android EN 2857 'Salamando's magic will work!'. Android FR's established spirit name is Athanor."),
        ),
    },
    {
        "event_id": "035C",
        "label": "Lumina orb reaction - composed shared suffix",
        "units": (
            (("C9:D17F",), (2865,), "round43_shared_magic_prefix", "user_validated", "$035C + shared $0360 reconstruct exactly Android EN 2865 'Lumina's magic will work!'. The full official French sentence is serialized in the name carrier."),
        ),
    },
    {
        "event_id": "035D",
        "label": "Shade orb reaction - composed shared suffix",
        "units": (
            (("C9:D193",), (2870,), "round43_shared_magic_prefix", "user_validated", "$035D + shared $0360 reconstruct exactly Android EN 2870 'Shade's magic will work!'. Android FR's established spirit name is Ombre."),
        ),
    },
    {
        "event_id": "035E",
        "label": "Luna orb reaction - composed shared suffix",
        "units": (
            (("C9:D1A6",), (2881,), "round43_shared_magic_prefix", "user_validated", "$035E + shared $0360 reconstruct exactly Android EN 2881 'Luna's magic will work!'. The full official French sentence is serialized in the name carrier."),
        ),
    },
    {
        "event_id": "0360",
        "label": "Shared spirit-orb suffix - represented by Gnome anchor",
        "units": (
            (("C9:D1C0", "C9:D1CB"), (2839,), "round43_shared_magic_suffix_layout", "user_validated", "$0360 is the shared suffix called by the eight spirit-name events. Android stores each complete '[Spirit]'s magic will work!' sentence separately; 2839 is the representative proven composition. Because the full localized sentence is moved into each validated prefix (and Dryad uses a temporary manual supplement), these two carriers retain layout only and no duplicated words."),
        ),
    },
    {
        "event_id": "0500",
        "label": "Gloves Orb gain - shared $0509 suffix",
        "units": ((("CA:58B9",), (952,), "round43_weapon_orb_prefix", "user_validated", "$0500 renders 'Got Glove' then jumps to shared $0509 " + '"\'s Orb!"' + ", reconstructing the Gloves Orb message. Android EN 952 is a representative of strict EN+FR duplicates; the French terminal punctuation is left to the shared suffix."),),
    },
    {
        "event_id": "0501",
        "label": "Sword Orb gain - shared $0509 suffix",
        "units": ((("CA:58D5",), (122,), "round43_weapon_orb_prefix", "user_validated", "$0501 + shared $0509 reconstructs the Sword Orb message; Android EN 122 represents strict EN+FR duplicate copies. The shared suffix owns the final French exclamation."),),
    },
    {
        "event_id": "0502",
        "label": "Axe Orb gain - shared $0509 suffix",
        "units": ((("CA:58F1",), (1008,), "round43_weapon_orb_prefix", "user_validated", "$0502 + shared $0509 reconstructs the Axe Orb message; Android EN 1008 represents strict EN+FR duplicate copies. The shared suffix owns the final French exclamation."),),
    },
    {
        "event_id": "0503",
        "label": "Spear Orb gain - shared $0509 suffix",
        "units": ((("CA:590B",), (631,), "round43_weapon_orb_prefix", "user_validated", "$0503 + shared $0509 reconstructs the Spear Orb message; Android EN 631 represents strict EN+FR duplicate copies. The shared suffix owns the final French exclamation."),),
    },
    {
        "event_id": "0504",
        "label": "Whip Orb gain - shared $0509 suffix",
        "units": ((("CA:5927",), (901,), "round43_weapon_orb_prefix", "user_validated", "$0504 + shared $0509 reconstructs the Whip Orb message; Android EN 901 represents strict EN+FR duplicate copies. The shared suffix owns the final French exclamation."),),
    },
    {
        "event_id": "0505",
        "label": "Bow Orb gain - shared $0509 suffix",
        "units": ((("CA:5942",), (934,), "round43_weapon_orb_prefix", "user_validated", "$0505 + shared $0509 reconstructs the Bow/Arrow Orb message; Android EN 934 represents strict EN+FR duplicate copies. The shared suffix owns the final French exclamation."),),
    },
    {
        "event_id": "0506",
        "label": "Boomerang Orb gain - shared $0509 suffix",
        "units": ((("CA:595C",), (786,), "round43_weapon_orb_prefix", "user_validated", "$0506 + shared $0509 reconstructs the Boomerang Orb message; Android EN 786 represents strict EN+FR duplicate copies. The shared suffix owns the final French exclamation."),),
    },
    {
        "event_id": "0507",
        "label": "Javelin Orb gain - shared $0509 suffix",
        "units": ((("CA:597C",), (1164,), "round43_weapon_orb_prefix", "user_validated", "$0507 + shared $0509 reconstructs the Javelin Orb message; Android EN 1164 represents strict EN+FR duplicate copies. The shared suffix owns the final French exclamation."),),
    },
    {
        "event_id": "0509",
        "label": "Shared weapon-orb suffix - represented by Gloves Orb anchor",
        "units": ((("CA:598C",), (952,), "round43_weapon_orb_suffix", "user_validated", "$0509 contributes the same terminal " + '"\'s Orb!"' + " to all eight weapon-specific events. Android stores complete messages, so 952 is a representative proven composition; only the common French terminal ' !' remains in this shared subevent."),),
    },
    {
        "event_id": "07FA",
        "label": "Game-over plural dynamic slot - first helper",
        "units": ((("CA:979D",), (6,), "round43_gameover_plural_slot", "user_validated", "$07FA returns literal 'them' on a non-single-character game-over branch. Android EN 6/7 are identical dynamic frames, while FR 6 is the plural realization and FR 7 is the PLAYER_NAME realization. The non-text branch therefore selects the plural middle phrase from FR 6."),),
    },
    {
        "event_id": "07FB",
        "label": "Game-over plural dynamic slot - second helper",
        "units": ((("CA:97A8",), (6,), "round43_gameover_plural_slot", "user_validated", "$07FB returns literal 'them' on the other non-single-character game-over branch. As for $07FA, the event flags select Android FR 6's plural middle phrase; PLAYER_NAME remains owned by the separate $07F3 path."),),
    },
    {
        "event_id": "07FF",
        "label": "Game-over dynamic frame around $07FB/$07FA/$07F3 result",
        "units": (
            (("CA:98B2", "CA:98C8"), (7,), "round43_gameover_dynamic_frame", "user_validated", "$07FF supplies the fixed frame around a call to $07FB, which eventually returns either literal 'them' or the unchanged $07F3 PLAYER_NAME(0). Android EN 6/7 are 546 strict duplicate frame copies arranged as 273 FR plural/name pairs. Anchor 7 provides the PLAYER_NAME frame; the reviewed redistribution serializes only its fixed prefix/suffix and leaves the dynamic slot to the existing SNES call chain."),
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



_REDISTRIBUTION_TOKEN_RE = re.compile(r"%S\(\d+,0\)|[\wÀ-ÿŒœ’'-]+|[^\w\s]", re.UNICODE)


def _redistribution_tokens(text: str) -> list[str]:
    """Tokenize Android prose for index-based redistribution recipes.

    Recipes store only Android ID/token references plus layout punctuation and
    whitespace. They never store translated prose: the words are read from
    scrtxt_fr.bin on every deterministic generation.
    """
    return _REDISTRIBUTION_TOKEN_RE.findall(text.replace("_", " "))


def _load_dialogue_redistribution_recipes(french: dict[int, str]) -> tuple[dict[str, dict[str, str]], dict[str, dict]]:
    document = json.loads(DIALOGUE_REDISTRIBUTION_RECIPES.read_text(encoding="utf-8"))
    if document.get("format_version") != 1:
        raise ValueError("Unsupported dialogue redistribution recipe format")
    if document.get("source") != "sources/android/scrtxt_fr.bin":
        raise ValueError("Dialogue redistribution recipes must source Android FR directly")

    rendered: dict[str, dict[str, str]] = {}
    event_meta: dict[str, dict] = {}
    android_token_cache: dict[int, list[str]] = {}

    for event_id, event_recipe in document.get("events", {}).items():
        android_ids = [int(x) for x in event_recipe.get("android_ids", [])]
        missing = [x for x in android_ids if x not in french]
        if missing:
            raise ValueError(f"Redistribution ${event_id}: missing Android FR IDs {missing}")
        for android_id in android_ids:
            android_token_cache.setdefault(android_id, _redistribution_tokens(french[android_id]))

        values: dict[str, str] = {}
        for sid, recipe in event_recipe.get("carriers", {}).items():
            parts = recipe.get("parts", [])
            seps = recipe.get("seps", [])
            if len(seps) != len(parts) + 1:
                raise ValueError(f"Redistribution ${event_id}/{sid}: invalid separator count")
            chunks = [seps[0]]
            for index, part in enumerate(parts):
                if not isinstance(part, list) or not part:
                    raise ValueError(f"Redistribution ${event_id}/{sid}: invalid part {part!r}")
                kind = part[0]
                if kind == "a":
                    if len(part) != 3:
                        raise ValueError(f"Redistribution ${event_id}/{sid}: invalid Android token ref {part!r}")
                    android_id, token_index = int(part[1]), int(part[2])
                    if android_id not in android_ids:
                        raise ValueError(f"Redistribution ${event_id}/{sid}: undeclared Android ID {android_id}")
                    tokens = android_token_cache[android_id]
                    if not 0 <= token_index < len(tokens):
                        raise ValueError(f"Redistribution ${event_id}/{sid}: token index out of range {part!r}")
                    token = tokens[token_index]
                elif kind == "p":
                    if len(part) != 2 or int(part[1]) not in {0, 1, 2}:
                        raise ValueError(f"Redistribution ${event_id}/{sid}: invalid PLAYER_NAME ref {part!r}")
                    token = f"%S({int(part[1])},0)"
                elif kind == "x":
                    if len(part) != 2 or re.search(r"[A-Za-zÀ-ÿŒœ]", str(part[1])):
                        raise ValueError(f"Redistribution ${event_id}/{sid}: literal prose forbidden in recipe {part!r}")
                    token = str(part[1])
                else:
                    raise ValueError(f"Redistribution ${event_id}/{sid}: unknown part kind {kind!r}")
                chunks.append(token)
                chunks.append(seps[index + 1])
            value = "".join(chunks)
            values[sid] = value
        rendered[event_id] = values
        event_meta[event_id] = {"android_ids": android_ids, "round": int(event_recipe.get("round", 0) or 0)}
    return rendered, event_meta


def _load_reviewed_choice_layout_recipes(source_document: dict) -> dict[str, dict]:
    """Load structural-only reviewed choice presentation decisions.

    These recipes deliberately contain no localized prose.  They only pin the
    exact canonical SNES event/carrier pair whose outer stock parentheses were
    reviewed away during Round 72.  Source-shape validation prevents a stale
    recipe from silently applying after extraction changes.
    """
    document = json.loads(DIALOGUE_CHOICE_LAYOUT_RECIPES.read_text(encoding="utf-8"))
    if document.get("format_version") != 1:
        raise ValueError("Unsupported dialogue choice-layout recipe format")

    events = {event["event_id"]: event for event in source_document.get("events", [])}
    recipes: dict[str, dict] = {}
    for recipe in document.get("recipes", []):
        event_id = str(recipe.get("event_id", "")).upper()
        if not event_id or event_id in recipes:
            raise ValueError(f"Duplicate/invalid reviewed choice-layout event {event_id!r}")
        if recipe.get("strategy") != "strip_outer_choice_decoration":
            raise ValueError(f"Unsupported reviewed choice-layout strategy for ${event_id}")
        event = events.get(event_id)
        if event is None:
            raise ValueError(f"Reviewed choice-layout recipe references unknown event ${event_id}")
        token_ids = {
            token.get("id") for token in event.get("tokens", [])
            if token.get("type") in {"text", "ending_text"}
        }
        opening_id = recipe.get("opening_text_id")
        closing_id = recipe.get("closing_text_id")
        if opening_id not in token_ids or closing_id not in token_ids:
            raise ValueError(
                f"Reviewed choice-layout recipe ${event_id} carrier IDs no longer match source"
            )
        recipes[event_id] = {
            "event_id": event_id,
            "strategy": recipe["strategy"],
            "opening_text_id": opening_id,
            "closing_text_id": closing_id,
        }
    return recipes


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


def make_dialogue_review_round25_report(
    english: dict[int, str],
    french: dict[int, str],
    *,
    english_path: Path,
    french_path: Path,
) -> dict:
    """Regenerate the second high-leverage structural alignment pass."""
    return make_dialogue_review_report(
        english, french, english_path=english_path, french_path=french_path,
        batch=DIALOGUE_REVIEW_ROUND25, round_name="round25", user_validated=False,
    )


def make_dialogue_review_round31_report(
    english: dict[int, str],
    french: dict[int, str],
    *,
    english_path: Path,
    french_path: Path,
) -> dict:
    """Regenerate the Round-31 high-leverage structural follow-up."""
    return make_dialogue_review_report(
        english, french, english_path=english_path, french_path=french_path,
        batch=DIALOGUE_REVIEW_ROUND31, round_name="round31", user_validated=False,
    )



def make_dialogue_review_round33_report(
    english: dict[int, str],
    french: dict[int, str],
    *,
    english_path: Path,
    french_path: Path,
) -> dict:
    """Regenerate the user-validated Round-33 high-leverage review."""
    return make_dialogue_review_report(
        english, french, english_path=english_path, french_path=french_path,
        batch=DIALOGUE_REVIEW_ROUND33, round_name="round33", user_validated=True,
    )


def make_dialogue_review_round34_report(
    english: dict[int, str],
    french: dict[int, str],
    *,
    english_path: Path,
    french_path: Path,
) -> dict:
    """Regenerate the Round-34 high-leverage structural follow-up."""
    return make_dialogue_review_report(
        english, french, english_path=english_path, french_path=french_path,
        batch=DIALOGUE_REVIEW_ROUND34, round_name="round34", user_validated=False,
    )


# Round 44 promotes only structurally determinate identities recovered after
# Round 43. The user authorized marking no-doubt cases as validated. These are
# explicit local/parameterized identities, not a new automatic matching rule.
DIALOGUE_REVIEW_ROUND44 = (
    {
        "event_id": "0012",
        "label": "Jema Pandora departure - exact local sequence gap",
        "units": ((('C9:090A',), (378,), "round44_local_sequence_anchor", "user_validated", "Within caller $0180, the surrounding sequence is already locked to Android 372-376; after $0011 -> 376 'Head for Gaia's Navel!', Android 377 is a mobile-only warning and 378 is exactly 'And don't follow me!'. The SNES carrier says 'Don't come with me!', so 378 is the unique scene identity."),),
    },
    {
        "event_id": "001F",
        "label": "Jehk reusable rejection - Sage is out",
        "units": ((('C9:0983',), (2451,), "round44_jehk_out_with_return_layout", "user_validated", "The reusable subevent precedes four already-aligned party reactions and destination reports 2452-2462. Android 2451 is exactly 'The Sage is out!'; the older SNES 'Go away!' clause is redundant with the separately mapped Jehk rejection line $03DD -> 2445. Preserve one terminal SNES newline so the caller reaction begins on the next physical line."),),
    },
    {
        "event_id": "0126",
        "label": "Sword-cut follow-up - direct PLAYER_NAME scene",
        "units": ((('C9:3A39',), (3438,), "round44_player_name_followup_layout", "user_validated", "Immediately after the already-aligned sword-pull sequence, Android 3437 says the village is blocked and 3438 is '%S(0,0): I can cut through with this!'. The SNES event contains PLAYER_NAME(0) followed by ':I can cut through with this sword!', making 3438 unique. Keep PLAYER_NAME in stock command ownership and add explicit layout so a maximum nine-character name cannot wrap implicitly."),),
    },
    {
        "event_id": "025F",
        "label": "Matango castle guard - king inside",
        "units": ((('C9:A255',), (1362,), "round44_local_sequence_anchor", "user_validated", "The local NPC block already maps $025D -> 1363 'Get the king's permission first!' and $025E -> 1364 'You may pass!'. Android 1362 'The king is in his chambers.' is the unique missing predecessor for SNES 'The king's inside.'."),),
    },
    {
        "event_id": "02E6",
        "label": "Tasnica citizen - Emperor after the king",
        "units": ((('C9:C68A',), (2567,), "round44_local_sequence_anchor", "user_validated", "Tasnica neighbors are already locked around Android 2562-2565. Android 2567 'Emperor Vandole's after our king! That scoundrel!' is the unique scene expansion of SNES 'The Emperor's after our King!'."),),
    },
    {
        "event_id": "03AC",
        "label": "Northtown citizen - Republic war memory",
        "units": ((('C9:E32D',), (1950,), "round44_local_sequence_anchor", "user_validated", "The surrounding Northtown NPCs are already locked to Android 1948, 1949, 1951, 1952 and 1953. Android 1950 is the sole missing slot and expands SNES 'We once fought the Republic.' into the citizen's personal wartime memory."),),
    },
    {
        "event_id": "0320", "label": "Parameterized inn - 5 GP",
        "units": ((('C9:CE3D',), (110,), "round44_parameterized_inn_price_identity", "user_validated", "The stock caller supplies numeric price 5 between shared $0330/$0331; Android 110 is exactly the complete 5-GP standard inn prompt. Identity belongs to this parameterized path while serialization keeps the existing shared French template."),),
    },
    {
        "event_id": "0321", "label": "Parameterized inn - 10 GP",
        "units": ((('C9:CE46',), (229,), "round44_parameterized_inn_price_identity", "user_validated", "The stock caller supplies numeric price 10 between shared $0330/$0331; Android 229 is a strict EN+FR copy of the complete 10-GP standard prompt (272 is an equivalent duplicate)."),),
    },
    {
        "event_id": "0322", "label": "Parameterized inn - 15 GP",
        "units": ((('C9:CE50',), (502,), "round44_parameterized_inn_price_identity", "user_validated", "The stock caller supplies numeric price 15 between shared $0330/$0331; Android 502 is exactly the complete 15-GP standard prompt."),),
    },
    {
        "event_id": "0324", "label": "Parameterized inn - 50 GP",
        "units": ((('C9:CE64',), (1365,), "round44_parameterized_inn_price_identity", "user_validated", "The stock caller supplies numeric price 50 between shared $0330/$0331; Android 1365 is a representative strict EN+FR duplicate of the complete 50-GP standard prompt (1644/1750 are equivalent copies)."),),
    },
    {
        "event_id": "0325", "label": "Parameterized inn - 100 GP",
        "units": ((('C9:CE6E',), (1907,), "round44_parameterized_inn_price_identity", "user_validated", "The stock caller supplies numeric price 100 between shared $0330/$0331; Android 1907 is exactly the complete 100-GP standard prompt."),),
    },
    {
        "event_id": "0326", "label": "Parameterized inn - 120 GP",
        "units": ((('C9:CE79',), (1961,), "round44_parameterized_inn_price_identity", "user_validated", "The stock caller supplies numeric price 120 between shared $0330/$0331; Android 1961 is exactly the complete 120-GP standard prompt."),),
    },
    {
        "event_id": "0327", "label": "Parameterized inn - 150 GP",
        "units": ((('C9:CE84',), (2319,), "round44_parameterized_inn_price_identity", "user_validated", "The stock caller supplies numeric price 150 between shared $0330/$0331; Android 2319 is exactly the complete 150-GP standard prompt."),),
    },
    {
        "event_id": "0328", "label": "Parameterized inn - 200 GP",
        "units": ((('C9:CE8F',), (2498,), "round44_parameterized_inn_price_identity", "user_validated", "The stock caller supplies numeric price 200 between shared $0330/$0331; Android 2498 is exactly the complete 200-GP standard prompt."),),
    },
)

# Round 45 continues the explicit structural pass. No generic matcher is added:
# each identity below is accepted only because its scene/object/resegmentation
# provenance is determinate under the standing user authorization for no-doubt cases.
DIALOGUE_REVIEW_ROUND45 = (
    {
        "event_id": "00C4",
        "label": "Kakkara vanished-place reaction - exact duplicate disambiguated by scene",
        "units": ((("C9:1A62",), (1626,), "round45_exact_duplicate_scene_position", "user_validated", "SNES 'Huh!? All gone?' has two exact Android-English copies (1626/1689). Android 1626 sits in the Kakkara/Amar block immediately after the Ice Country/warm-town discussion and before King Amar, whereas 1689 belongs to the unrelated game-over block. The French payloads are semantically identical apart from leading layout, so 1626 is the unique scene identity."),),
    },
    {
        "event_id": "01B6",
        "label": "Watts shortcut - Android 583/584/585 redistribution",
        "units": ((("C9:6AD2", "C9:6B5A"), (584,), "round45_watts_shortcut_redistribution", "user_validated", "The two SNES carriers combine exactly to Android EN 584: 'And only I can do it!...shortcut...This will make it a lot easier for you!'. Android FR redistributes the shortcut introduction into already-owned slot 583 and the post-movement continuation into FR-only slot 585. Keep C9:6AD2 empty because existing C9:6A8A already renders the official shortcut introduction, then place slot 585 on C9:6B5A after the unchanged movement sequence."),),
    },
    {
        "event_id": "01DA",
        "label": "Girl naming scene - Android identity with PLAYER_NAME layout deferred",
        "units": (
            ((("player_name", 0), "C9:7E64", ("player_name", 0), "C9:7E72", ("player_name", 0), "C9:7E81"), (676, 677), "round45_girl_name_resegmentation", "user_validated", "The complete naming exchange is locked between Android 675 and the young-lady naming prompt 679. Android 676 owns '%S(0,0): My name is %S(0,0).' and 677 owns the intervening Girl response ending on 'I'm'. Android FR 677 deliberately removes the third boy-name repetition. Preserve the first two PLAYER_NAME(0) commands, omit only the third command immediately before C9:7E81, and serialize the official 676+677 French across the three SNES carriers."),
        ),
    },
    {
        "event_id": "04F0",
        "label": "Tasnica entrance guard - map-object state proof",
        "units": ((("CA:4D71",), (2541,), "round45_tasnica_object_state", "user_validated", "ROM map-object table $0018 contains two $02E0 guards ('This is the castle of Tasnica.' -> Android 2539) and object #2 -> $04F0. Android 2540-2541 is the same entrance anti-spy gate; 2541 says nobody is being let in and uniquely expands SNES 'No one's allowed now!'."),),
    },
)


# Round 50 refines one already-proven Android/SNES many-to-many unit. It adds
# no Android identity: the existing $01CE mapping [536,537] is split according
# to the stock CHOICE_BEGIN boundary, with 536 owning the donation prompt and
# 537 owning the affirmative option. Android EN 538 already owns the following
# stock No option, making the three-slot prompt/Yes/No structure determinate.
DIALOGUE_REVIEW_ROUND50 = (
    {
        "event_id": "01CE",
        "label": "Dwarf show donation prompt / Yes choice segmentation",
        "units": (
            (("C9:7827",), (536,), "choice_prompt_split", "very_high_structural", "Android EN 536 is exactly the donation prompt and ends immediately before Android EN 537 'Yes'. SNES C9:7827 contains the prompt plus the stock opening '(' immediately before CHOICE_BEGIN, so 536 owns this carrier without crossing the choice command."),
            (("C9:7856",), (537,), "choice_option_split", "very_high_structural", "Android EN 537 is the affirmative 'Yes' slot between prompt 536 and already-aligned No 538. SNES C9:7856 is exactly the first CHOICE_OPTION label ('Okay'), so this is a structure-proven segmentation of the already-owned 536+537 unit."),
        ),
    },
)


# Round 46 introduces a deliberately separate Android ``systxt`` identity
# namespace for the stock chest-message family.  These records are explicit
# structural reviews only; ``systxt`` is never added to the generic scrtxt
# candidate index.  The 101254-101256 block is uniquely chest-specific and
# matches the SNES $067E/$067F money subevents plus $0689/$0687 item grants.
DIALOGUE_REVIEW_ROUND46_SYSTEM = (
    {
        "event_id": "067E",
        "label": "Chest reward - 1000 GP via system-text template",
        "snes_ids": ("CA:8E72",),
        "android_ids": (101254,),
        "relation": "round46_systxt_chest_money",
        "note": "All callers $068A-$068E invoke $067E as the generic 1000-GP chest subevent. Android systxt 101254 is the chest-specific 'Found $0d GP!' entry, adjacent to the Leather Whip and Magic Rope chest records 101255-101256; this adjacency disambiguates it from the unrelated duplicate systxt 100177.",
    },
    {
        "event_id": "067F",
        "label": "Chest reward - 50 GP via system-text template",
        "snes_ids": ("CA:8E8F",),
        "android_ids": (101254,),
        "relation": "round46_systxt_chest_money",
        "note": "The many $0680-$069F chest callers invoke $067F as the generic 50-GP reward subevent. Android systxt 101254 is the same parameterized chest-money message; the SNES hard-coded amount is substituted into the official French template.",
    },
    {
        "event_id": "0687",
        "label": "Magic Rope chest - scrtxt English identity, systxt French correction",
        "snes_ids": ("CA:8EEF",),
        "android_ids": (469,),
        "identity_namespace": "scrtxt",
        "localization_systxt_id": 101256,
        "relation": "round46_systxt_chest_localization_override",
        "note": "$0687 grants item $06 via OP_1E 46, proving Magic Rope and retaining scrtxt EN 469 as the identity layer. scrtxt FR 469 is wrong (Fouet); the chest-specific systxt 101256 payload says Corde magique and is used only as localization-correction evidence, not as Android-English identity.",
    },
    {
        "event_id": "0689",
        "label": "Leather Whip chest - scrtxt English identity, systxt French correction",
        "snes_ids": ("CA:8F20",),
        "android_ids": (769,),
        "identity_namespace": "scrtxt",
        "localization_systxt_id": 101255,
        "relation": "round46_systxt_chest_localization_override",
        "note": "$0689 grants weapon $24 via OP_1E A4, proving Whip/Leather Whip and retaining scrtxt EN 769 as the identity layer. The older Round-39 stock-English workaround is superseded because chest-specific systxt 101255 supplies the correct official French Fouet en cuir payload.",
    },
)



def make_dialogue_review_round39_report(
    english: dict[int, str],
    french: dict[int, str],
    *,
    english_path: Path,
    french_path: Path,
) -> dict:
    """Regenerate the user-validated Round-39 contextual/object review."""
    return make_dialogue_review_report(
        english, french, english_path=english_path, french_path=french_path,
        batch=DIALOGUE_REVIEW_ROUND39, round_name="round39", user_validated=True,
    )

def make_dialogue_review_round40_report(
    english: dict[int, str],
    french: dict[int, str],
    *,
    english_path: Path,
    french_path: Path,
) -> dict:
    """Regenerate the Round-40 structurally locked resegmentation review."""
    return make_dialogue_review_report(
        english, french, english_path=english_path, french_path=french_path,
        batch=DIALOGUE_REVIEW_ROUND40, round_name="round40", user_validated=False,
    )


def make_dialogue_review_round41_report(
    english: dict[int, str],
    french: dict[int, str],
    *,
    english_path: Path,
    french_path: Path,
) -> dict:
    """Regenerate the user-validated Round-41 contextual follow-up."""
    return make_dialogue_review_report(
        english, french, english_path=english_path, french_path=french_path,
        batch=DIALOGUE_REVIEW_ROUND41, round_name="round41", user_validated=True,
    )



def make_dialogue_review_round42_report(
    english: dict[int, str],
    french: dict[int, str],
    *,
    english_path: Path,
    french_path: Path,
) -> dict:
    """Regenerate the user-validated Round-42 structural/contextual follow-up."""
    return make_dialogue_review_report(
        english, french, english_path=english_path, french_path=french_path,
        batch=DIALOGUE_REVIEW_ROUND42, round_name="round42", user_validated=True,
    )


def make_dialogue_review_round43_report(
    english: dict[int, str],
    french: dict[int, str],
    *,
    english_path: Path,
    french_path: Path,
) -> dict:
    """Regenerate the user-validated Round-43 structural-family follow-up."""
    return make_dialogue_review_report(
        english, french, english_path=english_path, french_path=french_path,
        batch=DIALOGUE_REVIEW_ROUND43, round_name="round43", user_validated=True,
    )


def make_dialogue_review_round44_report(
    english: dict[int, str],
    french: dict[int, str],
    *,
    english_path: Path,
    french_path: Path,
) -> dict:
    """Regenerate the user-authorized no-doubt Round-44 structural follow-up."""
    return make_dialogue_review_report(
        english, french, english_path=english_path, french_path=french_path,
        batch=DIALOGUE_REVIEW_ROUND44, round_name="round44", user_validated=True,
    )


def make_dialogue_review_round45_report(
    english: dict[int, str],
    french: dict[int, str],
    *,
    english_path: Path,
    french_path: Path,
) -> dict:
    """Regenerate the user-authorized no-doubt Round-45 structural follow-up."""
    return make_dialogue_review_report(
        english, french, english_path=english_path, french_path=french_path,
        batch=DIALOGUE_REVIEW_ROUND45, round_name="round45", user_validated=True,
    )


def make_dialogue_review_round50_report(
    english: dict[int, str],
    french: dict[int, str],
    *,
    english_path: Path,
    french_path: Path,
) -> dict:
    """Regenerate the Round-50 exact choice-boundary resegmentation review."""
    report = make_dialogue_review_report(
        english, french, english_path=english_path, french_path=french_path,
        batch=DIALOGUE_REVIEW_ROUND50, round_name="round50", user_validated=True,
    )
    report["policy"] = {
        "automatic_identity_rule_added": False,
        "android_identity_set_changed": False,
        "segmentation_only": True,
        "note": (
            "The already-owned Android 536+537 unit is split only at the canonical SNES "
            "CHOICE_BEGIN boundary; Android 538 remains the independently accepted No option."
        ),
    }
    return report



def make_dialogue_review_round51_report() -> dict:
    """Regenerate the Round-51 residual unresolved-classification audit."""
    source = load_dialogue_text_entries()
    omission_ids = ("C9:A730", "C9:A74E", "C9:CE5A")
    template_ids = ("C9:CEA3", "C9:CEB3")
    expected_events = {
        "C9:A730": "0278",
        "C9:A74E": "0278",
        "C9:CE5A": "0323",
        "C9:CEA3": "0330",
        "C9:CEB3": "0331",
    }
    entries = []
    for snes_id in omission_ids:
        item = source.get(snes_id)
        if item is None or item.get("event_id") != expected_events[snes_id]:
            raise ValueError(f"Round-51 omission carrier changed: {snes_id}")
        note = DIALOGUE_VALIDATED_ANDROID_OMISSIONS.get(snes_id)
        if not note or not note.startswith("Round-51"):
            raise ValueError(f"Round-51 omission note missing: {snes_id}")
        entries.append({
            "event_id": item["event_id"],
            "snes_id": snes_id,
            "source": item["source"],
            "classification": "validated_android_omission",
            "note": note,
        })
    for snes_id in template_ids:
        item = source.get(snes_id)
        if item is None or item.get("event_id") != expected_events[snes_id]:
            raise ValueError(f"Round-51 template carrier changed: {snes_id}")
        note = DIALOGUE_VALIDATED_CONTEXTUAL_TEMPLATES.get(snes_id)
        if not note or not note.startswith("Round-51"):
            raise ValueError(f"Round-51 template note missing: {snes_id}")
        entries.append({
            "event_id": item["event_id"],
            "snes_id": snes_id,
            "source": item["source"],
            "classification": "validated_contextual_template",
            "note": note,
        })

    english = read_scrtxt(DEFAULT_SCRTXT_EN)
    french = read_scrtxt(DEFAULT_SCRTXT_FR)
    require_parallel_scrtxt(english, french)
    standard_inn = {
        text_id: english[text_id]
        for text_id in (110, 229, 502, 1365, 1907, 1961, 2319, 2498)
    }
    expected_prices = ("5", "10", "15", "50", "100", "120", "150", "200")
    for text_id, price in zip(standard_inn, expected_prices):
        if standard_inn[text_id] != f"One night is {price} GP. Want to stay?":
            raise ValueError(f"Round-51 standard inn Android record changed: {text_id}")
    if english.get(194) != "30 GP a night would be purrrfect. Meow?":
        raise ValueError("Round-51 Neko 30-GP Android record changed")
    if any(text == "One night is 30 GP. Want to stay?" for text in english.values()):
        raise ValueError("Round-51 expected standard 30-GP Android omission no longer holds")
    controller_hits = {
        "START": [text_id for text_id, text in english.items() if "start" in text.lower()],
        "L/R": [text_id for text_id, text in english.items() if "l/r" in text.lower()],
        "button": [text_id for text_id, text in english.items() if "button" in text.lower()],
        "mode": [text_id for text_id, text in english.items() if "mode" in text.lower()],
    }
    if controller_hits["L/R"] or controller_hits["button"] or controller_hits["mode"]:
        raise ValueError("Round-51 controller-term omission proof changed in Android scrtxt")

    return {
        "format_version": 1,
        "status": "round51_residual_unresolved_audit",
        "source_asset": "dialogues.json",
        "android_english": {
            "path": "sources/android/scrtxt_en.bin",
            "sha256": sha256(DEFAULT_SCRTXT_EN),
        },
        "policy": {
            "automatic_identity_rule_added": False,
            "android_identity_assigned": False,
            "translation_payload_changed": False,
            "semantic_alignment_count_changed": False,
            "notes": [
                "The two $0278 controller lines were already user-validated as absent from Android; Round 51 formalizes that negative evidence.",
                "$0323 is the missing standard 30-GP inn caller. Android 194 is a distinct Neko/meow prompt and remains forbidden as a substitute.",
                "$0330/$0331 are shared runtime template fragments, not independently ownable Android records. The existing parameterized French serialization is unchanged.",
                "These five records close the residual unclassified set without increasing 1798/1838 or changing ROM bytes.",
            ],
        },
        "evidence": {
            "standard_inn_android_records": [
                {"android_id": text_id, "english": english[text_id], "french": french[text_id]}
                for text_id in standard_inn
            ],
            "distinct_30gp_neko_record": {
                "android_id": 194,
                "english": english[194],
                "french": french[194],
            },
            "standard_30gp_prompt_present": False,
            "controller_term_hits": controller_hits,
        },
        "counts": {
            "validated_android_omission": len(omission_ids),
            "validated_contextual_template": len(template_ids),
            "total_carriers": len(entries),
        },
        "entries": entries,
        "scenes": [
            {
                "event_id": entry["event_id"],
                "label": entry["classification"],
                "status": "audited",
                "units": [entry],
            }
            for entry in entries
        ],
    }



def make_dialogue_review_round52_report() -> dict:
    """Regenerate the Round-52 exact formatter-bridge candidate review."""
    source_document = json.loads(DIALOGUE_SOURCE.read_text(encoding="utf-8"))
    by_id, by_event = event_text_index(source_document)
    english = read_scrtxt(DEFAULT_SCRTXT_EN)
    french = read_scrtxt(DEFAULT_SCRTXT_FR)
    require_parallel_scrtxt(english, french)

    scenes = []
    for (event_id, snes_ids, android_ids), expected in DIALOGUE_ROUND52_STRUCTURAL_DISTRIBUTIONS.items():
        if len(android_ids) != 1:
            raise ValueError("Round-52 review currently expects one Android identity per bridge")
        android_id = android_ids[0]
        actual_en = normalize_android_prose(english[android_id]).strip()
        actual_fr = normalize_android_french(french[android_id]).strip()
        if actual_en != normalize_android_prose(expected["android_en"]).strip():
            raise ValueError(f"Round-52 Android EN changed at {android_id}")
        if actual_fr != normalize_android_french(expected["android_fr"]).strip():
            raise ValueError(f"Round-52 Android FR changed at {android_id}")
        event = by_event.get(event_id)
        if event is None:
            raise ValueError(f"Round-52 source event missing: ${event_id}")
        for text_id, source in zip(snes_ids, expected["sources"], strict=True):
            meta = by_id.get(text_id)
            if meta is None or meta.get("event_id") != event_id or meta.get("source") != source:
                raise ValueError(f"Round-52 source carrier changed: {text_id}")
        first_index = by_id[snes_ids[0]]["token_index"]
        second_index = by_id[snes_ids[1]]["token_index"]
        bridge = event["tokens"][first_index + 1:second_index]
        actual_bridge = [
            {"name": token.get("name"), "args": token.get("args", "")}
            for token in bridge
            if token.get("type") == "command"
        ]
        if len(actual_bridge) != len(bridge):
            raise ValueError(f"Round-52 bridge unexpectedly contains text: ${event_id}")
        if tuple((x["name"], x["args"]) for x in actual_bridge) != tuple(expected["bridge"]):
            raise ValueError(f"Round-52 bridge changed: ${event_id}")
        scenes.append({
            "event_id": event_id,
            "status": "user_validated",
            "strategy": expected["strategy"],
            "snes_ids": list(snes_ids),
            "snes_sources": list(expected["sources"]),
            "android_ids": list(android_ids),
            "android_english": english[android_id],
            "android_french": french[android_id],
            "localized_parts": list(expected["localized_parts"]),
            "stock_bridge_commands": actual_bridge,
            "note": expected["note"],
            "units": [{
                "snes_ids": list(snes_ids),
                "android_ids": list(android_ids),
                "strategy": expected["strategy"],
                "status": "user_validated",
                "note": expected["note"],
            }],
        })

    return {
        "format_version": 1,
        "status": "round52_exact_structural_formatter_user_validated",
        "source_asset": "dialogues.json",
        "android_english": {
            "path": "sources/android/scrtxt_en.bin",
            "sha256": sha256(DEFAULT_SCRTXT_EN),
        },
        "android_french": {
            "path": "sources/android/scrtxt_fr.bin",
            "sha256": sha256(DEFAULT_SCRTXT_FR),
        },
        "policy": {
            "automatic_identity_rule_added": False,
            "android_identity_set_changed": False,
            "generic_formatter_rule_widened": False,
            "stock_wait_action_commands_moved": False,
            "wait_is_newline": False,
            "note": (
                "Only six exact already-identified mappings are serialized around their canonical "
                "stock WAIT/action bridges. Ambiguous neighboring PARTIEL mappings remain deferred."
            ),
        },
        "counts": {
            "reviewed_mappings": len(scenes),
            "events_touched": len({scene["event_id"] for scene in scenes}),
        },
        "scenes": scenes,
    }


def make_dialogue_review_round53_report() -> dict:
    """Audit Android-FR-only residual text after the Round-52 runtime checkpoint.

    This round deliberately changes no identity and no translation payload.  It
    combines the already-exhaustive Android-English residual audit with an
    explicit scan of every scrtxt entry whose English slot is empty but French
    is non-empty.  The goal is to prove that no hidden Android-FR-only payload
    remains safely assignable to the 40 residual semantic SNES carriers.
    """
    english = read_scrtxt(DEFAULT_SCRTXT_EN)
    french = read_scrtxt(DEFAULT_SCRTXT_FR)
    require_parallel_scrtxt(english, french)

    auto_path = ROOT / "mappings" / "android" / "dialogues_auto.json"
    auto_document = json.loads(auto_path.read_text(encoding="utf-8"))
    owners: dict[int, list[dict]] = {}
    for mapping in auto_document.get("mappings", []):
        android_ids = mapping.get("android_unit_ids", mapping.get("android_ids", []))
        for android_id in android_ids:
            owners.setdefault(int(android_id), []).append({
                "event_id": mapping["event_id"],
                "snes_ids": list(mapping["snes_ids"]),
            })

    fr_only_ids = sorted(
        android_id
        for android_id in english
        if not english[android_id].strip() and french[android_id].strip()
    )
    fr_only_entries = []
    for android_id in fr_only_ids:
        fr_only_entries.append({
            "android_id": android_id,
            "french": french[android_id],
            "owners": owners.get(android_id, []),
            "owned": android_id in owners,
        })

    expected_unowned = {1688, 2155, 3260, 3261}
    actual_unowned = {entry["android_id"] for entry in fr_only_entries if not entry["owned"]}
    if actual_unowned != expected_unowned:
        raise ValueError(
            "Round-53 Android-FR-only residual set changed: "
            f"expected {sorted(expected_unowned)}, got {sorted(actual_unowned)}"
        )

    unowned_notes = {
        1688: {
            "classification": "android_fr_only_no_snes_residual",
            "note": (
                "French-only Kakkara embellishment 'Ça fait rêver !' follows Android 1687. "
                "No residual SNES semantic carrier belongs to this Android scene, so it is Android-only localization prose, not a recoverable SNES identity."
            ),
        },
        2155: {
            "classification": "android_fr_only_no_snes_residual",
            "note": (
                "French-only player interjection '%S(0,0) : Allons-y !' follows Android 2154 in the Dyluck scene. "
                "It has no residual SNES carrier in that scene; the superficially similar unresolved '$0042 Well, let's go!' belongs to a different naming branch and cannot reuse it."
            ),
        },
        3260: {
            "classification": "android_fr_only_locked_04e1_redistribution",
            "note": (
                "French-only Thanatos transition inside the explicitly locked $04E1 redistribution. Android EN is empty here, so this may not create a new identity; do not assign it to either locked SNES carrier."
            ),
        },
        3261: {
            "classification": "android_fr_only_locked_04e1_redistribution",
            "note": (
                "French-only Thanatos body-collapse prose inside the explicitly locked $04E1 redistribution. Android EN is empty here, so this may not create a new identity; do not assign it to either locked SNES carrier."
            ),
        },
    }
    for entry in fr_only_entries:
        if entry["android_id"] in unowned_notes:
            entry.update(unowned_notes[entry["android_id"]])

    visual_adaptation_ids = {
        "C9:2627", "C9:2728", "C9:2735", "C9:2745",  # $0103
        "C9:55FC",  # $017F
        "C9:804A",  # $01DC
        "CA:85DD",  # $0602
    }
    explicit_lock_ids = {
        "C9:0970",  # $001E
        "C9:4B36",  # $015A
        "C9:7140",  # $01C5
        "C9:D1B8",  # $035F
        "CA:2BED", "CA:2C3A",  # $04E1
        "CA:7C98", "CA:8323", "CA:833E",  # $05F8
    }
    lock_notes = {
        "C9:0970": "Shared Joch/Jehk prefix; Android FR repeats Maître Jach inside the destination-specific owned records, so no standalone identity is created.",
        "C9:4B36": "Elman return greeting remains a validated adaptation gap; do not reopen the rejected remap.",
        "C9:7140": "Choice-tail wording diverges structurally from Android; keep the explicit handoff lock.",
        "C9:D1B8": "No Android-English Dryad identity was found; retain the approved manual French supplement without inflating Android alignment.",
        "CA:2BED": "Known Thanatos Android block 3252-3256 redistributes the concepts across five Android records; explicit handoff lock remains in force.",
        "CA:2C3A": "Known Thanatos Android block 3252-3256 redistributes Dyluck/body-weakness concepts across several records; explicit handoff lock remains in force.",
        "CA:7C98": "Finale event $05F8 is explicitly frozen; nearby Android FR redistributes speaker turns and may not be rebound.",
        "CA:8323": "Finale event $05F8 is explicitly frozen; FR-only Android 3111 is part of the neighboring owned 3110 localization and is not a new English identity.",
        "CA:833E": "Finale event $05F8 is explicitly frozen; the mother/plea sequence is redistributed across Android 3104/3110/3111.",
    }
    visual_notes = {
        "C9:2627": "Runtime-validated $0103 adaptation; Android 3413 owns a larger dots/name/remove-sword unit and must not be split merely to raise alignment.",
        "C9:2728": "Runtime-validated $0103 timed-ellipsis adaptation; Android 3420-3430 repartitions the ghost voice over multiple punctuation/name records.",
        "C9:2735": "Runtime-validated $0103 timed-ellipsis adaptation; no new carrier-level identity is required for the already-correct visible French sequence.",
        "C9:2745": "Runtime-validated $0103 timed-ellipsis adaptation; Android 'I entrust the sword to you' is segmented differently across 3425-3429.",
        "C9:55FC": "Runtime-validated $017F adaptation. Android 392 is the scene-equivalent soldier rebuke, but the event is intentionally frozen as visually complete rather than remapped for bookkeeping.",
        "C9:804A": "Runtime-validated $01DC adaptation. Android 727-728 condenses the wounded-soldier/platform exchange; the suppressed SNES carrier remains intentionally identity-unassigned.",
        "CA:85DD": "Runtime-validated visually complete $0602 status override; no visible English remains, so identity bookkeeping is intentionally left unresolved.",
    }

    with (ROOT / "mappings" / "android" / "dialogues_unmapped.csv").open(encoding="utf-8-sig", newline="") as fh:
        unresolved_rows = list(csv.DictReader(fh, delimiter=";"))
    if len(unresolved_rows) != 40:
        raise ValueError(f"Round-53 expected 40 residual semantic carriers, found {len(unresolved_rows)}")

    residual_entries = []
    counts: dict[str, int] = {}
    for row in unresolved_rows:
        snes_id = row["snes_id"]
        reason = row["raison"]
        if reason == "validated_android_omission":
            final_state = "ANDROID_ABSENT_VALIDATED"
            note = row["note"]
        elif reason == "validated_no_equivalent":
            final_state = "NO_UNIQUE_ANDROID_EQUIVALENT"
            note = row["note"]
        elif reason == "validated_contextual_template":
            final_state = "CONTEXTUAL_TEMPLATE_NO_SINGLE_ID"
            note = row["note"]
        elif snes_id in visual_adaptation_ids:
            final_state = "VISUALLY_COMPLETE_ANDROID_ADAPTATION"
            note = visual_notes[snes_id]
        elif snes_id in explicit_lock_ids:
            final_state = "EXPLICIT_HANDOFF_LOCK"
            note = lock_notes[snes_id]
        else:
            raise ValueError(f"Round-53 residual carrier lacks final classification: {row['event_id']}/{snes_id}")
        counts[final_state] = counts.get(final_state, 0) + 1
        residual_entries.append({
            "event_id": row["event_id"],
            "snes_id": snes_id,
            "source": row["texte_source_snes_usa"],
            "previous_reason": reason,
            "final_state": final_state,
            "note": note,
            "best_android_english_id": int(row["meilleur_id_android_anglais"]) if row["meilleur_id_android_anglais"] else None,
            "best_android_english": row["meilleur_texte_anglais_android"],
            "best_android_french_candidate": row["meilleur_texte_francais_candidat"],
        })

    expected_counts = {
        "ANDROID_ABSENT_VALIDATED": 14,
        "NO_UNIQUE_ANDROID_EQUIVALENT": 8,
        "CONTEXTUAL_TEMPLATE_NO_SINGLE_ID": 2,
        "VISUALLY_COMPLETE_ANDROID_ADAPTATION": 7,
        "EXPLICIT_HANDOFF_LOCK": 9,
    }
    if counts != expected_counts:
        raise ValueError(f"Round-53 residual classification counts changed: {counts}")

    return {
        "format_version": 1,
        "status": "round53_android_fr_residual_exhaustion_audit",
        "source_asset": "dialogues.json",
        "android_english": {"path": "sources/android/scrtxt_en.bin", "sha256": sha256(DEFAULT_SCRTXT_EN)},
        "android_french": {"path": "sources/android/scrtxt_fr.bin", "sha256": sha256(DEFAULT_SCRTXT_FR)},
        "policy": {
            "automatic_identity_rule_added": False,
            "android_identity_assigned": False,
            "translation_payload_changed": False,
            "rom_bytes_changed": False,
            "english_identity_remains_primary": True,
            "generic_namespace_expanded": False,
            "systxt_policy_changed": False,
            "note": (
                "Round 51 already exhausted the scrtxt English identity pool. Round 53 scans every "
                "scrtxt ID with empty English and non-empty French plus the residual 40 carriers. "
                "No additional provenance-safe SNES identity or French payload is admitted."
            ),
        },
        "android_fr_only_audit": {
            "total_nonempty_fr_with_empty_en": len(fr_only_entries),
            "already_owned_by_existing_mappings": sum(1 for entry in fr_only_entries if entry["owned"]),
            "unowned": sum(1 for entry in fr_only_entries if not entry["owned"]),
            "entries": fr_only_entries,
        },
        "residual_semantic_audit": {
            "total": len(residual_entries),
            "counts": counts,
            "entries": residual_entries,
        },
        "conclusion": {
            "new_android_identities": 0,
            "new_french_payloads": 0,
            "semantic_alignment": "1798/1838 (97.8%)",
            "unresolved_semantic_ids": 40,
            "android_scrtxt_search_exhausted_under_current_policy": True,
            "next_phase": "Defer PARTIEL cleanup until requested; keep the residual 40 visible by final-state category in the dedicated HTML review.",
        },
        "scenes": [
            {
                "event_id": entry["event_id"],
                "label": entry["final_state"],
                "status": "audited",
                "units": [entry],
            }
            for entry in residual_entries
        ],
    }



def make_dialogue_review_round54_report() -> dict:
    """Document the exact PARTIEL recoveries attempted after Android exhaustion."""
    source_document = json.loads(DIALOGUE_SOURCE.read_text(encoding="utf-8"))
    english = read_scrtxt(DEFAULT_SCRTXT_EN)
    french = read_scrtxt(DEFAULT_SCRTXT_FR)
    require_parallel_scrtxt(english, french)
    by_id, by_event = event_text_index(source_document)

    scenes = []
    for (event_id, snes_ids, android_ids), expected in DIALOGUE_ROUND54_STRUCTURAL_RECOVERIES.items():
        if len(android_ids) != 1:
            raise ValueError("Round-54 review expects one Android ID per structural recovery")
        android_id = android_ids[0]
        if normalize_android_prose(english[android_id]).strip() != normalize_android_prose(expected["android_en"]).strip():
            raise ValueError(f"Round-54 Android EN {android_id} changed")
        if normalize_android_french(french[android_id]).strip() != normalize_android_french(expected["android_fr"]).strip():
            raise ValueError(f"Round-54 Android FR {android_id} changed")
        event = by_event[event_id]
        _round54_require_unique_window(event, tuple(expected["window"]), f"${event_id}")
        scenes.append({
            "event_id": event_id,
            "status": "runtime_candidate",
            "kind": "mapped_structural_recovery",
            "snes_ids": list(snes_ids),
            "android_ids": list(android_ids),
            "android_english": english[android_id],
            "android_french": french[android_id],
            "strategy": expected["strategy"],
            "stock_window": [list(item) for item in expected["window"]],
            "serialized_entries": [{"id": k, "text": v} for k, v in expected["values"].items()],
            "note": expected["note"],
            "units": [{
                "snes_ids": list(snes_ids), "android_ids": list(android_ids),
                "status": "runtime_candidate", "strategy": expected["strategy"],
                "note": expected["note"],
            }],
        })

    for event_id, expected in DIALOGUE_ROUND54_NONSEMANTIC_ANDROID_SUPPLEMENTS.items():
        android_id = expected["android_id"]
        if normalize_android_prose(english[android_id]).strip() != normalize_android_prose(expected["android_en"]).strip():
            raise ValueError(f"Round-54 Android EN {android_id} changed")
        if normalize_android_french(french[android_id]).strip() != normalize_android_french(expected["android_fr"]).strip():
            raise ValueError(f"Round-54 Android FR {android_id} changed")
        _round54_require_unique_window(by_event[event_id], tuple(expected["window"]), f"${event_id} Android {android_id}")
        scenes.append({
            "event_id": event_id,
            "status": "runtime_candidate",
            "kind": "nonsemantic_android_bridge",
            "snes_ids": list(expected["values"]),
            "android_ids": [android_id],
            "android_english": english[android_id],
            "android_french": french[android_id],
            "strategy": "exact_android_dynamic_name_bridge_on_nonsemantic_snes_carriers",
            "stock_window": [list(item) for item in expected["window"]],
            "serialized_entries": [{"id": k, "text": v} for k, v in expected["values"].items()],
            "note": expected["note"],
            "units": [{
                "snes_ids": list(expected["values"]), "android_ids": [android_id],
                "status": "runtime_candidate",
                "strategy": "exact_android_dynamic_name_bridge_on_nonsemantic_snes_carriers",
                "note": expected["note"],
            }],
        })

    return {
        "format_version": 1,
        "status": "round54_exact_partial_recovery_runtime_candidate",
        "source_asset": "dialogues.json",
        "android_english": {"path": "sources/android/scrtxt_en.bin", "sha256": sha256(DEFAULT_SCRTXT_EN)},
        "android_french": {"path": "sources/android/scrtxt_fr.bin", "sha256": sha256(DEFAULT_SCRTXT_FR)},
        "policy": {
            "android_search_reopened": False,
            "automatic_identity_rule_added": False,
            "generic_formatter_rule_widened": False,
            "stock_player_name_commands_moved": False,
            "stock_wait_action_commands_moved": False,
            "wait_is_newline": False,
            "note": "Round 53 exhausted Android discovery. Round 54 only serializes exact already-proven Android content across canonical stock structures.",
        },
        "counts": {
            "recoveries": len(scenes),
            "events_touched": len({scene["event_id"] for scene in scenes}),
            "mapped_structural_recoveries": len(DIALOGUE_ROUND54_STRUCTURAL_RECOVERIES),
            "nonsemantic_android_bridges": len(DIALOGUE_ROUND54_NONSEMANTIC_ANDROID_SUPPLEMENTS),
        },
        "known_deferrals": [
            {"event_id": "013A", "android_id": 848, "snes_id": "C9:40D7", "reason": "Android EN 848 identifies the two-sentence SNES unit, but official Android FR translates only the first sentence; keep the second SNES instruction stock rather than inventing French text"},
            {"event_id": "0592", "android_id": 1031, "reason": "official FR needs more than the two lines available before the following stock reaction unless a new pause/page is invented"},
            {"event_id": "0559", "android_id": 2147, "reason": "Android FR introduces PLAYER_NAME(1) after PLAYER_NAME(2), absent from the stock command stream"},
            {"event_id": "04E3", "android_ids": [1384, 1385], "reason": "first French Truffaut unit needs three lines before the existing PLAYER_NAME(0) reaction, which would become an unpaused fourth line"},
            {"event_id": "04FD", "android_ids": [3369, 3370], "reason": "Android identity contains a leading PLAYER_NAME(0) speaker marker absent from the stock SNES sequence"},
            {"event_id": "0227", "android_ids": [217, 218], "reason": "Android FR moves PLAYER_NAME(1) from the first maternal line into the following reassurance"},
        ],
        "scenes": scenes,
    }


def make_dialogue_review_round46_report() -> dict:
    """Regenerate the user-authorized Round-46 chest namespace review."""
    scr_en = read_scrtxt(DEFAULT_SCRTXT_EN)
    scr_fr = read_scrtxt(DEFAULT_SCRTXT_FR)
    sys_en = read_scrtxt(DEFAULT_SYSTXT_EN)
    sys_fr = read_scrtxt(DEFAULT_SYSTXT_FR)
    require_parallel_scrtxt(scr_en, scr_fr)
    require_parallel_scrtxt(sys_en, sys_fr)
    source = load_dialogue_text_entries()
    scenes = []
    for item in DIALOGUE_REVIEW_ROUND46_SYSTEM:
        snes_ids = list(item["snes_ids"])
        android_ids = list(item["android_ids"])
        identity_namespace = item.get("identity_namespace", "systxt")
        id_en, id_fr = (scr_en, scr_fr) if identity_namespace == "scrtxt" else (sys_en, sys_fr)
        for snes_id in snes_ids:
            if snes_id not in source or source[snes_id]["event_id"] != item["event_id"]:
                raise ValueError(f"Round-46 review references invalid SNES carrier {snes_id}")
        for android_id in android_ids:
            if not id_en.get(android_id):
                raise ValueError(f"Round-46 {identity_namespace} English ID {android_id} is missing/empty")
        unit_ids = android_anchor_units(tuple(android_ids), id_en)
        french_ids = [text_id for text_id in unit_ids if id_fr[text_id]]
        unit = {
            "snes_ids": snes_ids,
            "source_display": " ".join(source[text_id]["source"] for text_id in snes_ids),
            "android_identity_namespace": identity_namespace,
            "android_anchor_ids": android_ids,
            "android_unit_ids": unit_ids,
            "android_english_display": " ".join(id_en[text_id] for text_id in android_ids),
            "identity_french_display": " ".join(id_fr[text_id] for text_id in french_ids),
            "relation": item["relation"],
            "proposed_confidence": "user_validated",
            "note": item["note"],
            "user_validation": "accepted",
        }
        override_id = item.get("localization_systxt_id")
        if override_id is not None:
            unit["localization_override_namespace"] = "systxt"
            unit["localization_override_id"] = override_id
            unit["localization_override_source_en"] = sys_en[override_id]
            unit["french_display"] = sys_fr[override_id]
        else:
            unit["french_nonempty_ids"] = french_ids
            unit["french_display"] = " ".join(id_fr[text_id] for text_id in french_ids)
        scenes.append({"event_id": item["event_id"], "label": item["label"], "status": "user_validated", "units": [unit]})
    return {
        "format_version": 1,
        "status": "round46_user_validated",
        "source_asset": "dialogues.json",
        "android_sources": {
            "scrtxt_en": {"path": "sources/android/scrtxt_en.bin", "sha256": sha256(DEFAULT_SCRTXT_EN)},
            "scrtxt_fr": {"path": "sources/android/scrtxt_fr.bin", "sha256": sha256(DEFAULT_SCRTXT_FR)},
            "systxt_en": {"path": "sources/android/systxt_en.bin", "sha256": sha256(DEFAULT_SYSTXT_EN)},
            "systxt_fr": {"path": "sources/android/systxt_fr.bin", "sha256": sha256(DEFAULT_SYSTXT_FR)},
        },
        "policy": {
            "automatic_translation_generation": False,
            "english_identity_is_primary": True,
            "generic_candidate_index_extended": False,
            "notes": [
                "Only 067E/067F use systxt 101254 as Android-English identity.",
                "0687/0689 retain scrtxt English identities 469/769; systxt 101256/101255 is localization-correction evidence only because those systxt_en records are not English.",
                "The generic dialogue aligner continues to search scrtxt only.",
                "Parameterized $0d is materialized from the fixed SNES chest reward amount; no new runtime variable is invented.",
            ],
        },
        "scenes": scenes,
    }



def make_dialogue_review_round47_report() -> dict:
    """Regenerate the Round-47 non-text routing/omission audit."""
    source = load_dialogue_text_entries()
    groups = (
        (
            "validated_no_equivalent",
            ("C9:2179", "C9:2208", "C9:2268", "C9:A49C", "C9:C4FB", "CA:85FC"),
            DIALOGUE_FORCED_UNMAPPED,
        ),
        (
            "validated_android_omission",
            ("C9:1057", "C9:916F", "C9:9193", "C9:9F88", "C9:CAA6", "C9:CAC2", "C9:CB0C", "C9:CB28"),
            DIALOGUE_VALIDATED_ANDROID_OMISSIONS,
        ),
    )
    entries = []
    for status, ids, notes in groups:
        for snes_id in ids:
            item = source.get(snes_id)
            if item is None:
                raise ValueError(f"Round-47 audit references missing SNES carrier {snes_id}")
            note = notes.get(snes_id)
            if not note or not note.startswith("Round-47"):
                raise ValueError(f"Round-47 audit note missing for {snes_id}")
            entries.append(
                {
                    "event_id": item["event_id"],
                    "snes_id": snes_id,
                    "source": item["source"],
                    "classification": status,
                    "note": note,
                }
            )
    return {
        "format_version": 1,
        "status": "round47_routing_audit",
        "source_asset": "dialogues.json",
        "routing_evidence": {
            "map_trigger_table": "ROM $084000",
            "map_object_pointer_table": "ROM $087000",
            "event_call_graph": "OP_10..27 event references",
        },
        "policy": {
            "automatic_translation_generation": False,
            "android_identity_assigned": False,
            "translation_payload_changed": False,
            "notes": [
                "validated_no_equivalent means routing/provenance was audited and no unique Android-English identity may be assigned.",
                "validated_android_omission means the SNES scene/branch is proven but the corresponding Android scene omits the carrier.",
                "These classifications are negative evidence only: they do not increase the 1798/1838 semantic alignment count and do not authorize manual translation.",
            ],
        },
        "counts": {
            "validated_no_equivalent": sum(1 for entry in entries if entry["classification"] == "validated_no_equivalent"),
            "validated_android_omission": sum(1 for entry in entries if entry["classification"] == "validated_android_omission"),
            "total_carriers": len(entries),
        },
        "entries": entries,
        "scenes": [
            {
                "event_id": entry["event_id"],
                "label": entry["classification"],
                "status": "audited",
                "units": [entry],
            }
            for entry in entries
        ],
    }


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


def make_dialogue_review_round48_report() -> dict:
    """Regenerate the Round-48 formatter repair + Tasnica omission audit."""
    source = load_dialogue_text_entries()
    tasnica_id = "C9:C56C"
    tasnica = source.get(tasnica_id)
    if tasnica is None or tasnica.get("event_id") != "02E1":
        raise ValueError("Round-48 Tasnica audit carrier changed")
    omission_note = DIALOGUE_VALIDATED_ANDROID_OMISSIONS.get(tasnica_id)
    if not omission_note or not omission_note.startswith("Round-48"):
        raise ValueError("Round-48 Tasnica omission note missing")

    vocatives = []
    for (event_id, snes_id, android_id), expected in sorted(
        DIALOGUE_ROUND48_ANDROID_ONLY_VOCATIVES.items(),
        key=lambda item: (int(item[0][0], 16), item[0][1]),
    ):
        item = source.get(snes_id)
        if item is None or item.get("event_id") != event_id or item.get("source") != expected["source"]:
            raise ValueError(f"Round-48 vocative audit carrier changed: {snes_id}")
        vocatives.append({
            "event_id": event_id,
            "snes_id": snes_id,
            "android_id": android_id,
            "android_english": expected["android_en"],
            "android_french_before": expected["android_fr"],
            "french_after_vocative_removal": expected["localized"],
            "identity_unchanged": True,
            "snes_player_name_commands_unchanged": True,
            "status": "reviewed_exact_formatter_repair",
        })

    return {
        "format_version": 1,
        "status": "round48_formatter_and_tasnica_audit",
        "source_asset": "dialogues.json",
        "policy": {
            "automatic_identity_rule_added": False,
            "android_identity_changed": False,
            "vocative_rule_generic": False,
            "notes": [
                "The seven Android-FR-only vocatives are exact carrier/Android-ID allow-list entries. Android EN and the canonical SNES carrier contain no dynamic addressee; no PLAYER_NAME command is created or moved.",
                "$0127 pagination is exact-token-gated: two sentence-boundary WAIT $00 + TEXT_CLEAR transitions plus one TEXT_CLEAR-only after the existing WAIT $08. All actor actions, timed WAIT and PLAYER_NAME commands remain in stock order.",
                "$02E1/C9:C56C is negative evidence only: it becomes validated_android_omission and receives no Android ID or French payload.",
            ],
        },
        "tasnica_omission": {
            "event_id": "02E1",
            "snes_id": tasnica_id,
            "source": tasnica["source"],
            "classification": "validated_android_omission",
            "map_id": "001A",
            "object_index": 0,
            "object_rom_offset": "089538",
            "object_raw": "3C 0E 8C 16 50 B7 E1 C2",
            "android_scene_block": "2539-2577",
            "note": omission_note,
        },
        "android_fr_only_vocative_repairs": vocatives,
        "event_0127_pagination": {
            "event_id": "0127",
            "status": "reviewed_exact_formatter_repair",
            "page_break_after": ["ici...", "Quoi ?!"],
            "text_clear_only_before": "C9:3ADC",
            "stock_wait08_unchanged": True,
            "player_name_commands_unchanged": True,
        },
        "counts": {
            "validated_android_omission": 1,
            "exact_android_fr_only_vocative_repairs": len(vocatives),
            "exact_pagination_events": 1,
        },
        "scenes": [
            {
                "event_id": "02E1",
                "label": "Tasnica live NPC omission",
                "status": "audited",
                "units": [{
                    "event_id": "02E1",
                    "snes_id": tasnica_id,
                    "classification": "validated_android_omission",
                }],
            },
            *[
                {
                    "event_id": item["event_id"],
                    "label": "Android-FR-only vocative formatter repair",
                    "status": "reviewed_exact_formatter_repair",
                    "units": [item],
                }
                for item in vocatives
            ],
            {
                "event_id": "0127",
                "label": "exact pagination repair",
                "status": "reviewed_exact_formatter_repair",
                "units": [{
                    "event_id": "0127",
                    "strategy": "round48_exact_multi_boundary_pagination",
                }],
            },
        ],
    }


def make_dialogue_review_round49_report() -> dict:
    """Regenerate the Round-49 exact formatter-only recovery audit."""
    source = load_dialogue_text_entries()

    speaker_repairs = []
    for (event_id, snes_id, android_ids), expected in sorted(
        DIALOGUE_ROUND49_ANDROID_ONLY_SPEAKER_LABELS.items(),
        key=lambda item: (int(item[0][0], 16), item[0][1]),
    ):
        item = source.get(snes_id)
        if item is None or item.get("event_id") != event_id or item.get("source") != expected["source"]:
            raise ValueError(f"Round-49 speaker-label audit carrier changed: {snes_id}")
        speaker_repairs.append({
            "event_id": event_id,
            "snes_id": snes_id,
            "android_ids": list(android_ids),
            "android_english": expected["android_en"],
            "android_french_before": expected["android_fr"],
            "french_after_label_removal": expected["localized"],
            "identity_unchanged": True,
            "snes_player_name_commands_unchanged": True,
            "status": "reviewed_exact_formatter_repair",
        })

    sound = DIALOGUE_ROUND49_SOUND_SEQUENCE
    sound_units = []
    for snes_id, source_text, localized in zip(
        sound["snes_ids"], sound["sources"], sound["localized_parts"], strict=True
    ):
        item = source.get(snes_id)
        if item is None or item.get("event_id") != sound["event_id"] or item.get("source") != source_text:
            raise ValueError(f"Round-49 sound-sequence audit carrier changed: {snes_id}")
        sound_units.append({
            "snes_id": snes_id,
            "source": source_text,
            "localized_part": localized,
        })

    blocked = {
        "event_id": "0205",
        "snes_ids": ["C9:90DE", "C9:910D"],
        "android_ids": [825],
        "status": "TO_REVIEW",
        "reason": (
            "Android FR condenses the two SNES carriers into one sentence while the canonical SNES stream "
            "keeps PLAYER_NAME(0), then WAIT $00 + TEXT_CLEAR between the carriers. No complete-sentence "
            "redistribution preserves both stock pages without inventing or moving structure, so the event remains excluded."
        ),
    }
    partial_04e9 = {
        "event_id": "04E9",
        "status": "PARTIEL",
        "french_carriers": ["CA:46AC", "CA:46F5", "CA:4745", "CA:4797", "CA:47E7", "CA:4837", "CA:4886"],
        "layout_deferred_carriers": ["CA:48DC", "CA:4925"],
        "text_clear_before": ["CA:4745", "CA:4797"],
        "reason": (
            "The two three-line Android-FR paragraphs start immediately after existing WAIT $00 commands. "
            "Exact TEXT_CLEAR-only resets make those pages simulator-clean without adding another pause. "
            "The final Android-FR sentence jointly condenses CA:48DC+CA:4925 across WAIT $00, so that mapping stays stock/deferred."
        ),
    }

    return {
        "format_version": 1,
        "status": "round49_exact_formatter_recovery_audit",
        "source_asset": "dialogues.json",
        "policy": {
            "automatic_identity_rule_added": False,
            "android_identity_changed": False,
            "generic_formatter_rule_added": False,
            "notes": [
                "$02CD removes only the exact Android-FR-only %S(0,0) speaker label; Android EN and the entire SNES event contain no PLAYER_NAME command.",
                "$03F0 distributes one already accepted Android unit across the exact three stock noise carriers. PLAY_SOUND and WAIT $10 remain byte-for-byte in place; one layout-only newline is inserted before the existing WAIT $10 so WAIT remains a pause, not a newline.",
                "$04E9 becomes PARTIEL: seven mappings render in French; two exact TEXT_CLEAR-only resets follow existing WAIT $00 pauses; the final condensed two-carrier mapping remains stock/layout-deferred.",
                "$0205 is deliberately left unresolved at the formatter layer because Android FR collapses two SNES pages into one sentence across PLAYER_NAME + WAIT $00 + TEXT_CLEAR.",
            ],
        },
        "android_fr_only_speaker_label_repairs": speaker_repairs,
        "sound_sequence_repair": {
            "event_id": sound["event_id"],
            "snes_ids": list(sound["snes_ids"]),
            "android_ids": list(sound["android_ids"]),
            "android_english": sound["android_en"],
            "android_french": sound["android_fr"],
            "units": sound_units,
            "preserved_commands": [
                "PLAY_SOUND 02 D5 00 88",
                "PLAY_SOUND 02 B3 0F 88",
                "WAIT 10",
                "PLAY_SOUND 02 17 00 88",
            ],
            "inserted_layout_newline_before_existing_wait10": True,
            "identity_unchanged": True,
            "status": "reviewed_exact_formatter_repair",
        },
        "partial_event_recovery": partial_04e9,
        "deferred": [blocked],
        "counts": {
            "exact_android_fr_only_speaker_label_repairs": len(speaker_repairs),
            "exact_sound_sequence_repairs": 1,
            "exact_wait00_clear_only_repairs": 2,
            "formatter_or_simulator_events_recovered": 3,
            "formatter_events_deferred": 1,
        },
        "scenes": [
            *[
                {
                    "event_id": item["event_id"],
                    "label": "Android-FR-only speaker label formatter repair",
                    "status": item["status"],
                    "units": [item],
                }
                for item in speaker_repairs
            ],
            {
                "event_id": sound["event_id"],
                "label": "exact machine-noise sound bridge",
                "status": "reviewed_exact_formatter_repair",
                "units": sound_units,
            },
            {
                "event_id": partial_04e9["event_id"],
                "label": "exact WAIT $00 clear-only PARTIEL recovery",
                "status": "PARTIEL",
                "units": [partial_04e9],
            },
            {
                "event_id": blocked["event_id"],
                "label": "condensed two-page Android-FR mapping",
                "status": "TO_REVIEW",
                "units": [blocked],
            },
        ],
    }


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
    "C9:2179": "Round-47 trigger-proven Cannon route with no unique Android equivalent: $00EE is used by map triggers $0049/$011C, but Android reorganizes the Cannon network and has no provenance-safe standalone counterpart for SNES 'All aboard for Pandora!'. Do not recycle another Pandora response.",
    "C9:2208": "Round-47 trigger-proven Cannon route with no unique Android equivalent: $00F1 is used by map trigger $0121, but Android has no provenance-safe standalone counterpart for SNES 'For Pandora!'. Do not recycle another Pandora response.",
    "C9:2268": "Round-47 trigger-proven Cannon route with no unique Android equivalent: $00F3 is used by map trigger $011F, while Android contains multiple Ice Country Cannon responses belonging to other scene blocks. Do not force one by destination text alone.",
    "C9:A49C": "Round-47 unreferenced duplicate audit: $0269 has no incoming OP_10..27 event reference, no map trigger and no map-object event reference in the canonical routing tables. The actually used Truffle line $0276 is called from $04E3 and already owns Android 1400. Keep $0269 as an orphan stock duplicate instead of forcing reuse of 1400.",
    "C9:C4FB": "Round-47 unreferenced stock audit: $02DE has no incoming OP_10..27 event reference, no map trigger and no map-object event reference, unlike the surrounding live Tasnica NPC scripts. No Android-English identity is established; do not force a loose medicine-line candidate.",
    "CA:85FC": "Round-47 unreferenced sign audit: $0603 ('Topaz Falls') is the only $0600-$0609 sign event with no incoming event reference, map trigger or map-object reference in the canonical routing tables, and Android scrtxt/systxt contains no Topaz Falls anchor. Preserve it as an orphan stock sign rather than inventing an identity.",
}

# A stronger omission proof: an already accepted neighboring mapping explicitly
# documents that Android EN drops this standalone SNES fragment rather than
# translating/resegmenting it elsewhere.  Keep the carrier unmapped, but this
# status may admit a conservative PARTIEL event around it.
DIALOGUE_VALIDATED_ANDROID_OMISSIONS = {
    "C9:1057": (
        "Round-47 sprite-naming branch omission: $0041 conditionally transfers to $0042 after Android-aligned naming response 625, and both paths rejoin at the already aligned join message 628. Android 623-628 contains no counterpart for the alternate SNES 'Well, let's go!' line."
    ),
    "C9:916F": (
        "Round-47 Water Palace trigger omission: map $0053 directly selects $0207 on the same trigger pair that selects $0206 ('That's impossible!' -> Android 837). The Water Palace Android scene has no standalone counterpart for SNES 'Proof that Mana is fading!'; superficially similar Android 2310 belongs to Mandala and 890 is already the distinct $04E9 dialogue."
    ),
    "C9:9193": (
        "Round-47 Water Palace trigger omission: map $004B directly selects $0208 in the same stateful trigger set as $020A (Android 938-942). The corresponding Android Water Palace material omits the boy's standalone reflection that everyone is angry because he pulled the Sword; the Potos elder line about pulling the Sword is a different scene."
    ),
    "C9:9F88": (
        "Round-47 Wind Palace branch omission: $04E2 conditionally branches to $024F before its already aligned Grandpa/Sylphid sequence. Android 1274-1308 covers the same Wind Palace aftermath but contains no standalone counterpart for SNES 'The Empire sent monsters into the palace!'."
    ),
    "C9:CAA6": (
        "Round-47 Tasnica diary omission: non-text event $02FB conditionally transfers to optional diary event $02FC immediately before the already aligned Tasnica spy aftermath. Android 2578-2605 contains the king/spy sequence but omits this diary interaction entirely."
    ),
    "C9:CAC2": (
        "Round-47 Tasnica diary omission: this is the diary body in optional event $02FC reached from $02FB; Android's corresponding Tasnica spy block 2578-2605 has no diary text."
    ),
    "C9:CB0C": (
        "Round-47 Tasnica diary omission: this '(Text suddenly stops)' carrier belongs to optional event $02FC, absent from Android's corresponding Tasnica spy block 2578-2605."
    ),
    "C9:CB28": (
        "Round-47 Tasnica diary omission: the player's 'What does this mean?' closes optional event $02FC, which is absent from Android's corresponding Tasnica spy block 2578-2605."
    ),
    "C9:C56C": (
        "Round-48 Tasnica live-NPC omission: map $001A object #0 at ROM $089538 (raw 3C 0E 8C 16 50 B7 E1 C2) directly selects event $02E1 under the same $3C state family as live Tasnica NPCs $02E2-$02E7. Android 2539-2577 covers the corresponding Tasnica castle NPC block and anchors all surrounding live scripts, but contains no counterpart for SNES 'We'll smash the Empire!'. Keep it unmapped rather than borrowing another Empire line."
    ),
    "C9:30F5": (
        "Round-2 validated omission: Android 62 covers only the following player line; "
        "its accepted mapping explicitly records that the standalone SNES 'ELLIOTT:You!' fragment is absent."
    ),
    "CA:6629": (
        "Round-31 validated omission: accepted Android EN 2188 is followed only by empty slot 2189, "
        "then the scene resumes at accepted 2190; there is no Android-English anchor for the standalone "
        "SNES PLAYER_NAME(2) ':We can too!' fragment."
    ),
    "C9:A730": (
        "Round-51 residual audit: the controller instruction 'Press START to see the map.' was already "
        "user-validated as absent from Android and retained as a manual supplement. Exhaustive scrtxt EN "
        "inspection contains no START/map controller instruction counterpart; keep it outside Android identity."
    ),
    "C9:A74E": (
        "Round-51 residual audit: the controller instruction 'L/R buttons change modes.' was already "
        "user-validated as absent from Android and retained as a manual supplement. Exhaustive scrtxt EN "
        "inspection contains no L/R/button/mode counterpart; keep it outside Android identity."
    ),
    "C9:CE5A": (
        "Round-51 residual audit: the stock 30-GP caller belongs to the standard shared inn path $0330/$0331. "
        "Android scrtxt has exact standard prompts for 5, 10, 15, 50, 100, 120, 150 and 200 GP, but no "
        "standard 30-GP prompt. Android 194 is a distinct Neko/meow localization and must not be reused."
    ),
}

# Round 57 compares the reviewed Android omissions against the original
# Japanese SNES ROM supplied by the user. This is provenance/serialization
# evidence only; it never creates Android identity.
DIALOGUE_ROUND57_SNES_JP_PROVENANCE = {
    "C9:1057": "jp_snes_present_manual_supplement",
    "C9:916F": "jp_snes_present_manual_supplement",
    "C9:9193": "jp_snes_present_manual_supplement",
    "C9:9F88": "jp_snes_present_manual_supplement",
    "C9:A730": "jp_snes_present_resegmented_manual_supplement",
    "C9:A74E": "jp_snes_present_resegmented_manual_supplement",
    "C9:C56C": "jp_snes_present_manual_supplement",
    "C9:CAA6": "jp_snes_present_manual_supplement",
    "C9:CAC2": "jp_snes_present_manual_supplement",
    "C9:CB0C": "jp_snes_present_manual_supplement",
    "C9:30F5": "jp_snes_absent_distinct_line_user_suppressed",
    "C9:CB28": "jp_snes_absent_user_suppressed",
    "CA:6629": "jp_snes_absent_distinct_line_user_suppressed",
    "C9:CE5A": "jp_snes_present_covered_dynamic_parameter",
}


# These semantic carriers are real stock prose fragments, but they are shared
# subroutine templates whose Android identity is determined by the numeric
# caller.  No single Android scrtxt record owns them independently: executions
# correspond to the reviewed per-price prompt family (110/229/502/1365/1907/
# 1961/2319/2498, with equivalent duplicates).  Keep them unresolved in the
# 1798/1838 one-carrier identity count while recording that this is deliberate,
# not an unreviewed lexical hole.
DIALOGUE_VALIDATED_CONTEXTUAL_TEMPLATES = {
    "C9:CEA3": (
        "Round-51 residual audit: shared $0330 prefix 'One night is' has no single Android identity. "
        "Its runtime meaning is completed by the caller-supplied price before shared $0331; Android stores "
        "the resulting complete prompt as separate per-price records. Serialization remains the validated "
        "parameterized inn template and must not assign this carrier to representative Android 110."
    ),
    "C9:CEB3": (
        "Round-51 residual audit: shared $0331 suffix 'GP. Want to stay?' has no single Android identity. "
        "It is reused after every caller-supplied price, while Android stores complete per-price prompts. "
        "Serialization remains the validated parameterized inn template and must not inflate semantic alignment "
        "by assigning the shared suffix to representative Android 110."
    ),
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
# though the Android adaptation intentionally omits some stock SNES semantic
# fragments. Keep their exact simulator-clean French-only bytes, but do not
# count them as PARTIEL in the preview/report. Alignment may later prove an
# identity for an omitted source fragment; that new identity must not silently
# change the already runtime-validated translated serialization.
DIALOGUE_USER_VALIDATED_VISUALLY_COMPLETE_SUPPRESSIONS = {
    "0103": frozenset({"C9:2627", "C9:26A8", "C9:2728", "C9:2735", "C9:2745"}),
    "013A": frozenset({"C9:40D7"}),
    "017F": frozenset({"C9:55FC"}),
    "01DC": frozenset({"C9:804A"}),
}

# User-approved Android omissions that are safe to suppress locally even though
# the containing event remains PARTIEL for unrelated mapped/layout-deferred
# carriers.  These IDs do not make the whole event visually complete.
DIALOGUE_USER_VALIDATED_PARTIAL_SUPPRESSIONS = {
    "010C": frozenset({"C9:30F5"}),
    "02FC": frozenset({"C9:CB28"}),
    "0558": frozenset({"CA:6629"}),
}
# Round 69: after scene-level semantic review, the following former PARTIEL
# events are considered fully translated/complete. They remain traceable below
# through user_validated_visually_complete_events, preserving whether completion
# came from a manual supplement, a shared-prefix resegmentation, or a validated
# SNES/JP-absent suppression.
DIALOGUE_USER_VALIDATED_SEMANTICALLY_COMPLETE_EVENTS = frozenset({
    "001E", "0042", "00EE", "00F1", "00F3", "0207", "0208", "024F",
    "0278", "02E1", "02FC", "035F", "04E1", "04E8", "0558",
})
DIALOGUE_USER_VALIDATED_VISUALLY_COMPLETE_EVENTS = frozenset(
    set(DIALOGUE_USER_VALIDATED_VISUALLY_COMPLETE_SUPPRESSIONS)
    | set(DIALOGUE_USER_VALIDATED_SEMANTICALLY_COMPLETE_EVENTS)
)

# These events remain semantically alignment-incomplete and keep their exact
# mixed/stock serialization, but runtime review confirmed that no missing or
# English content is visibly exposed to the player. They therefore remain
# traceable as unresolved alignment without carrying the PARTIEL badge.
DIALOGUE_USER_VALIDATED_VISUALLY_COMPLETE_STATUS_OVERRIDES = frozenset({"0602"})

# $01DC has one Android-adaptation omission that includes a structural speaker
# carrier, not just semantic text. The user explicitly validated dropping the
# final stock PLAYER_NAME(0) together with C9:804A because Android 729 begins
# the following Niccolo scene directly after Android 728. The source asset stays
# canonical; this exact command is omitted only in translated serialization.
DIALOGUE_USER_VALIDATED_STRUCTURAL_OMISSIONS = (
    {
        "event_id": "013A",
        "suppressed_semantic_ids": ["C9:40D7"],
        "suppressed_commands": [
            {
                "name": "WAIT",
                "args": "00",
                "immediately_after_text_id": "C9:40D7",
            }
        ],
        "reason": "round67_user_validated_snes_jp_absent_android_fr_adaptation_suppression",
    },
    {
        "event_id": "04E1",
        "suppressed_semantic_ids": ["CA:2C84"],
        "suppressed_commands": [
            {
                "name": "WAIT",
                "args": "00",
                "immediately_after_text_id": "CA:2C84",
            }
        ],
        "reason": "round63_user_validated_resegmented_snes_jp_page_suppression",
    },
    {
        "event_id": "02FC",
        "suppressed_semantic_ids": ["C9:CB28"],
        "suppressed_commands": [
            {
                "name": "PLAYER_NAME",
                "args": "00",
                "immediately_before_text_id": "C9:CB28",
            },
            {
                "name": "WAIT",
                "args": "00",
                "immediately_after_text_id": "C9:CB28",
            },
        ],
        "reason": "round57_user_validated_snes_jp_absent_line",
    },
    {
        "event_id": "0558",
        "suppressed_semantic_ids": ["CA:6629"],
        "suppressed_commands": [
            {
                "name": "PLAYER_NAME",
                "args": "02",
                "immediately_before_text_id": "CA:6629",
            }
        ],
        "reason": "round57_user_validated_snes_jp_absent_line",
    },
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
    {
        "event_id": "01DA",
        "suppressed_semantic_ids": ["C9:7E81"],
        "suppressed_commands": [
            {
                "name": "PLAYER_NAME",
                "args": "00",
                "immediately_before_text_id": "C9:7E81",
            }
        ],
        "reason": "round45_user_authorized_android_fr_name_resegmentation",
    },
)


# Round 67: Android FR $04E2 assigns the complete reaction to PLAYER_NAME(2),
# while stock SNES splits the same region between PLAYER_NAME(1) and
# PLAYER_NAME(2). The user explicitly approved redistributing Android 1281 over
# CA:32C5/CA:32D7. Keep the canonical source untouched; translated serialization
# changes only the first adjacent PLAYER_NAME index and omits the now-redundant
# second identical speaker command.
DIALOGUE_USER_VALIDATED_STRUCTURAL_COMMAND_OVERRIDES = (
    {
        "event_id": "01C5",
        "commands": [
            {
                "name": "CHOICE_OPTION",
                "args": "08",
                "immediately_before_text_id": "C9:7140",
                "translated_args": "0D",
            },
        ],
        "reason": "round69_android_fr_continue_exit_choice_anchor",
    },
    {
        "event_id": "0205",
        "commands": [
            {
                "name": "PLAYER_NAME",
                "args": "00",
                "immediately_before_text_id": "C9:90DE",
                "omit": True,
            },
        ],
        "reason": "round69_whole_scene_android_fr_0204_0205_continuation",
    },
    {
        "event_id": "0227",
        "commands": [
            {
                "name": "PLAYER_NAME",
                "args": "01",
                "immediately_before_text_id": "C9:9827",
                "omit": True,
            },
        ],
        "reason": "round69_user_requested_move_player_name_inside_C9_9827",
    },
    {
        "event_id": "04E6",
        "commands": [
            {
                "name": "PLAYER_NAME",
                "args": "00",
                "immediately_before_text_id": "CA:3FC1",
                "omit": True,
            },
            {
                "name": "WAIT",
                "args": "00",
                "immediately_before_text_id": "CA:3FE4",
                "omit": True,
            },
        ],
        "reason": "round69_user_requested_move_player_name_inside_CA_3FC1",
    },
    {
        "event_id": "0559",
        "commands": [
            {
                "name": "PLAYER_NAME",
                "args": "00",
                "immediately_before_text_id": "CA:6741",
                "omit": True,
            },
            {
                "name": "PLAYER_NAME",
                "args": "01",
                "immediately_before_text_id": "CA:6744",
                "omit": True,
            },
        ],
        "reason": "round69_android_fr_2147_player_name_resegmentation",
    },
    {
        "event_id": "0592",
        "commands": [
            {
                "name": "PLAYER_NAME",
                "args": "02",
                "immediately_before_text_id": "CA:748F",
                "omit": True,
            },
        ],
        "reason": "round69_android_fr_1023_omits_sprite_name_label",
    },
    {
        "event_id": "04E2",
        "commands": [
            {
                "name": "PLAYER_NAME",
                "args": "01",
                "immediately_before_text_id": "CA:32C5",
                "translated_args": "02",
            },
            {
                "name": "PLAYER_NAME",
                "args": "02",
                "immediately_before_text_id": "CA:32D7",
                "omit": True,
            },
        ],
        "reason": "round67_user_validated_android_fr_1281_speaker_resegmentation",
    },
)


# $0331 remains semantically PARTIEL because the generic inn prompt carrier
# C9:CEB3 has no single proven Android identity. Suppressing its visible stock
# English must nevertheless preserve its two stock NEWLINEs: runtime testing
# proved that the choice row must stay on its original third physical line for
# the stock selection/highlight geometry to target the rendered Oui/Non row.
# This is layout-only metadata, never localized prose.
DIALOGUE_USER_VALIDATED_PARTIAL_LAYOUT_PRESERVATIONS = ()

# Reviewed PARTIEL-only layout deferrals. These do not weaken Android-English
# identity: the listed mapping remains accepted, but its stock SNES carrier is
# deliberately left untranslated because official Android French cannot be
# serialized without changing the canonical PLAYER_NAME/text ownership. The
# event remains visibly PARTIEL/TO REVIEW, and admission still requires a clean
# independent simulation.
DIALOGUE_REVIEWED_PARTIAL_LAYOUT_DEFERRALS = {}

# Generic structural safe-subset PARTIEL is deliberately disabled for the two
# alignment-incomplete scenes whose handoff already records a semantic/resegmentation
# hazard. Their problem is not merely layout, so leaving a few mapped carriers stock
# would give a misleadingly usable mixed scene.
DIALOGUE_GENERIC_PARTIAL_LAYOUT_DEFERRAL_BLOCKLIST = frozenset({"015A", "0204"})


# Manual supplements never create Android identity. Most are exact SNES carriers
# whose complete absence from Android was explicitly reviewed; Round 62 also
# allows one exact already-mapped carrier as a provenance-rich layout-review
# surcharge. Pending entries always keep the stock USA payload active.
DIALOGUE_USER_VALIDATED_ANDROID_ABSENT_MANUAL_IDS = {
    # Round 57: direct comparison with the original Japanese SNES ROM proves
    # these lines/scenes are genuine SNES content omitted by the Android port.
    # They stay outside Android identity and are routed through the manual
    # supplement file until a human-approved French translation is supplied.
    "0042": frozenset({"C9:1057"}),
    "0207": frozenset({"C9:916F"}),
    "0208": frozenset({"C9:9193"}),
    "024F": frozenset({"C9:9F88"}),
    "0278": frozenset({"C9:A730", "C9:A74E"}),
    "02E1": frozenset({"C9:C56C"}),
    "02FC": frozenset({"C9:CAA6", "C9:CAC2", "C9:CB0C"}),
    # Round 43: Android has no Dryad "magic will work" anchor. The user
    # explicitly authorizes a temporary French payload while keeping the
    # semantic identity unresolved/reviewable.
    "035F": frozenset({"C9:D1B8"}),
}

# Round 64 stages the remaining user-facing "NON TROUVÉ — PAS D’ÉQUIVALENT
# UNIQUE" carriers in the same provenance-rich manual-review schema. These
# entries never create Android identity. Round 65 explicitly approves four of
# the five JP-led proposals; Round 66 explicitly approves the final $0204
# carrier too, while preserving the event's broader resegmentation block.
DIALOGUE_USER_REQUESTED_UNMAPPED_MANUAL_REVIEW_IDS = {
    "00EE": frozenset({"C9:2179"}),
    "013A": frozenset({"C9:40D7"}),
    "00F1": frozenset({"C9:2208"}),
    "00F3": frozenset({"C9:2268"}),
    "0204": frozenset({"C9:902F"}),
    "04E8": frozenset({"CA:437D"}),
}

# $04E8 already needed an ordinary PARTIEL layout repair before its unresolved
# stock carrier was manually approved. Apply that one validated manual carrier
# only *after* the existing mixed-event repair pipeline has succeeded, then
# re-simulate. This exact deferral prevents the new approval from disabling or
# replacing unrelated, already-proven PARTIEL formatting repairs.
DIALOGUE_PARTIAL_MANUAL_POST_REPAIR_IDS = {
    "04E8": frozenset({"CA:437D"}),
}

# Round 66: $0204 remains deliberately blocked from the generic PARTIEL
# formatter because its Android-FR material is semantically resegmented and
# two mapped carriers still cross unsupported PLAYER_NAME ownership. The user
# nevertheless approved the exact JP-led manual carrier C9:902F. Admit only
# that carrier on top of the otherwise stock USA event, then require a clean
# whole-event simulation. Do not use this as permission to release any of the
# other $0204 Android mappings.
DIALOGUE_MANUAL_ONLY_RESEGMENTED_PARTIAL_IDS = {
    "0204": frozenset({"C9:902F"}),
}

# Round 62 also uses the same provenance-rich review schema for one already
# identified Android carrier whose official French cannot be serialized through
# the canonical USA WAIT split. This is a review surcharge, not an Android
# omission. Round 63 subsequently validated suppressing the standalone page.
DIALOGUE_USER_REQUESTED_MAPPED_MANUAL_REVIEW_IDS = {
    "04E1": frozenset({"CA:2C84"}),
}

# Exact unresolved shared-prefix redistributions. These preserve Android identity
# honesty: no Android ID is assigned, but a redundant SNES-English prefix may be
# reduced to layout-only bytes when every already-proven Android destination owns
# the localized subject itself. The event remains PARTIEL/alignment-unresolved.
DIALOGUE_REVIEWED_UNMAPPED_LAYOUT_RESEGMENTATIONS = {
    "001E": {
        "C9:0970": {
            "text": "\n",
            "reason": "shared Jehk/Jach subject prefix is absorbed by Android 2453/2455/2458/2461; preserve the stock leading NEWLINE after WAIT $00",
        },
    },
}

# Exact payload exceptions where Android English identity is accepted but the
# user has explicitly rejected the corresponding Android French localization.
# Keep this allow-list exact: this is not a generic preference for stock English.
DIALOGUE_USER_VALIDATED_STOCK_ENGLISH_OVERRIDES = {
    ("0689", "CA:8F20", 769): (
        "Android FR duplicates the Leather-Whip chest text onto the Magic Rope; "
        "$0689 OP_1E A4 proves the Whip/Leather Whip identity, while $0687 OP_1E 46 "
        "is the actual Magic Rope chest."
    ),
}

# Every alignment-incomplete event is reconsidered on each mass pass. Accepted
# mappings are rendered in French while unresolved semantic carriers remain
# untouched, so their stock SNES English stays visible in-game. The event is
# admitted only when that mixed FR/EN serialization is simulator-clean and is
# always marked PARTIEL. User-validated visually complete adaptations keep their
# separate frozen-omission policy.


def _load_manual_dialogue_supplements(source_document: dict) -> dict[str, dict[str, dict]]:
    document = json.loads(DIALOGUE_MANUAL_SUPPLEMENTS.read_text(encoding="utf-8"))
    format_version = document.get("format_version")
    if format_version not in {1, 2} or document.get("language") != "fr":
        raise ValueError("dialogues_manual_supplements.json: unsupported format/language")
    if document.get("source_asset") != "assets/dialogues.json":
        raise ValueError("dialogues_manual_supplements.json: invalid source_asset")
    by_id, _ = event_text_index(source_document)
    result: dict[str, dict[str, dict]] = {}
    for source_entry in document.get("entries", []):
        if not isinstance(source_entry, dict):
            raise ValueError("dialogues_manual_supplements.json: entries must be objects")
        entry = dict(source_entry)
        event_id = entry.get("event_id")
        text_id = entry.get("id")
        status = entry.get("status")
        reason = entry.get("reason")
        if format_version == 1:
            original_en = entry.get("source_en")
            translation_fr = entry.get("text")
            if status == "needs_manual_translation" and translation_fr != original_en:
                raise ValueError(
                    f"Manual supplement ${event_id}/{text_id}: legacy pending entries must retain stock USA text"
                )
            entry.setdefault("original_jp", None)
            entry.setdefault("original_fr", None)
            entry["original_en"] = original_en
            entry["translation_fr"] = translation_fr
        else:
            missing_fields = [
                key for key in ("original_jp", "original_en", "original_fr", "translation_fr")
                if key not in entry
            ]
            if missing_fields:
                raise ValueError(
                    f"Manual supplement ${event_id}/{text_id}: missing v2 fields {missing_fields}"
                )
            original_en = entry.get("original_en")
            translation_fr = entry.get("translation_fr")
            original_jp = entry.get("original_jp")
            original_fr = entry.get("original_fr")
            if original_jp is not None and not isinstance(original_jp, str):
                raise ValueError(f"Manual supplement ${event_id}/{text_id}: original_jp must be string or null")
            if original_fr is not None and not isinstance(original_fr, str):
                raise ValueError(f"Manual supplement ${event_id}/{text_id}: original_fr must be string or null")
            proposal_action = entry.get("proposal_action")
            if not isinstance(translation_fr, str):
                raise ValueError(f"Manual supplement ${event_id}/{text_id}: translation_fr must be a string")
            if not translation_fr and not (
                (status == "needs_manual_translation" and proposal_action == "suppress")
                or status == "suppressed"
            ):
                raise ValueError(
                    f"Manual supplement ${event_id}/{text_id}: empty translation_fr is allowed only "
                    "for a pending explicit suppression proposal or a validated suppression"
                )
        absent_allowed = DIALOGUE_USER_VALIDATED_ANDROID_ABSENT_MANUAL_IDS.get(event_id, frozenset())
        unmapped_review_allowed = DIALOGUE_USER_REQUESTED_UNMAPPED_MANUAL_REVIEW_IDS.get(event_id, frozenset())
        mapped_review_allowed = DIALOGUE_USER_REQUESTED_MAPPED_MANUAL_REVIEW_IDS.get(event_id, frozenset())
        if (
            text_id not in absent_allowed
            and text_id not in unmapped_review_allowed
            and text_id not in mapped_review_allowed
        ):
            raise ValueError(
                f"Manual supplement ${event_id}/{text_id}: carrier is outside the exact manual-review allow-lists"
            )
        meta = by_id.get(text_id)
        if meta is None or meta.get("event_id") != event_id:
            raise ValueError(f"Manual supplement ${event_id}/{text_id}: unknown/mismatched source carrier")
        if original_en != meta.get("source"):
            raise ValueError(
                f"Manual supplement ${event_id}/{text_id}: original_en is not byte-faithful to assets/dialogues.json"
            )
        if status not in {"needs_manual_translation", "translated", "suppressed"}:
            raise ValueError(f"Manual supplement ${event_id}/{text_id}: invalid status")
        if status == "suppressed":
            allowed_suppressions = {
                ("04E1", "CA:2C84"): "user_validated_resegmented_snes_jp_suppression",
                ("013A", "C9:40D7"): "user_validated_snes_jp_absent_suppression",
            }
            expected_reason = allowed_suppressions.get((event_id, text_id))
            if expected_reason is None:
                raise ValueError(f"Manual supplement ${event_id}/{text_id}: suppression is not allow-listed")
        else:
            expected_reason = (
                "user_validated_absent_from_android"
                if text_id in absent_allowed
                else (
                    "user_requested_unmapped_carrier_review"
                    if text_id in unmapped_review_allowed
                    else "user_requested_mapped_carrier_review"
                )
            )
        if reason != expected_reason:
            raise ValueError(
                f"Manual supplement ${event_id}/{text_id}: invalid reason {reason!r}; expected {expected_reason!r}"
            )
        # Round 58: proposals are review-only until explicit user approval.  A
        # pending entry therefore serializes the canonical USA carrier even when
        # translation_fr contains a proposed JP-led French wording.
        entry["_active_text"] = (
            original_en if status == "needs_manual_translation"
            else "" if status == "suppressed"
            else translation_fr
        )
        if text_id in result.setdefault(event_id, {}):
            raise ValueError(f"Manual supplement ${event_id}/{text_id}: duplicate entry")
        result[event_id][text_id] = entry
    expected_by_event: dict[str, set[str]] = {}
    for allow_map in (
        DIALOGUE_USER_VALIDATED_ANDROID_ABSENT_MANUAL_IDS,
        DIALOGUE_USER_REQUESTED_UNMAPPED_MANUAL_REVIEW_IDS,
        DIALOGUE_USER_REQUESTED_MAPPED_MANUAL_REVIEW_IDS,
    ):
        for event_id, allowed in allow_map.items():
            expected_by_event.setdefault(event_id, set()).update(allowed)
    for event_id, expected in expected_by_event.items():
        actual = frozenset(result.get(event_id, {}))
        if actual != frozenset(expected):
            raise ValueError(
                f"Manual supplement ${event_id}: expected {sorted(expected)}, got {sorted(actual)}"
            )
    extra_events = set(result) - set(expected_by_event)
    if extra_events:
        raise ValueError(f"Manual supplement unexpected event(s): {sorted(extra_events)}")
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
        "confidence": (
            "user_requested_unmapped_manual_review"
            if entry.get("reason") == "user_requested_unmapped_carrier_review"
            else "user_validated_android_absent_manual"
        ),
        "source_display": source_token.get("source", ""),
        "french_display": entry["_active_text"],
    }
    values, report = format_dialogue_mapping(
        source_document, mapping, advances,
        allow_one_extra_page=False,
        use_physical_page_capacity=True,
        prefer_semantic_line_breaks=True,
    )
    # $0208 has a stock PLAYER_NAME immediately before the manual carrier.
    # The generic isolated-carrier formatter does not count the worst-case
    # expanded player name in its first-line capacity, so its otherwise valid
    # two-line compaction would trigger a runtime parser wrap. Preserve the
    # explicit three-line supplement layout for both review and approved text;
    # this keeps PLAYER_NAME capacity honest instead of compacting the carrier
    # in isolation.
    if entry["event_id"] == "0208" and text_id == "C9:9193":
        values[text_id] = entry["_active_text"]
        report["manual_layout_policy"] = "preserve_stock_three_line_layout_for_player_name_capacity"
        report["formatted_entries"] = [{"id": text_id, "text": values[text_id]}]
    report["manual_supplement"] = True
    report["manual_status"] = entry["status"]
    report["manual_reason"] = entry["reason"]
    if entry["status"] == "needs_manual_translation":
        report["manual_translation_proposal"] = entry.get("translation_fr", "")
        report["manual_proposal_basis"] = entry.get("proposal_basis", "")
    if entry.get("temporary"):
        report["manual_temporary"] = True
        report["manual_review_note"] = entry.get("review_note", "")
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
        ("round25", DIALOGUE_REVIEW_ROUND25),
        ("round31", DIALOGUE_REVIEW_ROUND31),
        ("round33", DIALOGUE_REVIEW_ROUND33),
        ("round34", DIALOGUE_REVIEW_ROUND34),
        ("round39", DIALOGUE_REVIEW_ROUND39),
        ("round40", DIALOGUE_REVIEW_ROUND40),
        ("round41", DIALOGUE_REVIEW_ROUND41),
        ("round42", DIALOGUE_REVIEW_ROUND42),
        ("round43", DIALOGUE_REVIEW_ROUND43),
        ("round44", DIALOGUE_REVIEW_ROUND44),
        ("round45", DIALOGUE_REVIEW_ROUND45),
        ("round50", DIALOGUE_REVIEW_ROUND50),
    ):
        for scene in batch:
            for parts, android_ids, relation, _candidate_confidence, note in scene["units"]:
                snes_ids, source_display = render_snes_review_parts(parts, source, event_id=scene["event_id"])
                records.append(
                    {
                        "event_id": scene["event_id"],
                        "snes_ids": snes_ids,
                        "android_ids": list(android_ids),
                        "confidence": "very_high_structural_review" if round_name in {"round6", "round7", "round8", "round11", "round18", "round20", "round21", "round22", "round25", "round31", "round33", "round34", "round39", "round40", "round41", "round42", "round43", "round44", "round45", "round50"} else "user_validated",
                        "provenance": round_name,
                        "relation": relation,
                        "note": note,
                        "source_display": source_display,
                    }
                )
    # Round 46 is a separate reviewed Android system-text namespace.  Append
    # these records after every scrtxt round so they supersede earlier scrtxt
    # ownership for the same chest carriers without entering generic matching.
    for item in DIALOGUE_REVIEW_ROUND46_SYSTEM:
        records.append(
            {
                "event_id": item["event_id"],
                "snes_ids": list(item["snes_ids"]),
                "android_ids": list(item["android_ids"]),
                "android_namespace": item.get("identity_namespace", "systxt"),
                **({"localization_systxt_id": item["localization_systxt_id"]} if item.get("localization_systxt_id") else {}),
                "confidence": "very_high_structural_review",
                "provenance": "round46",
                "relation": item["relation"],
                "note": item["note"],
                "source_display": " ".join(source[text_id]["source"] for text_id in item["snes_ids"]),
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


def _auto_enrich_record(
    record: dict,
    english: dict[int, str],
    french: dict[int, str],
    *,
    system_english: dict[int, str] | None = None,
    system_french: dict[int, str] | None = None,
) -> dict:
    namespace = record.get("android_namespace", "scrtxt")
    if namespace == "scrtxt":
        local_en, local_fr = english, french
    elif namespace == "systxt":
        if system_english is None or system_french is None:
            raise ValueError("systxt reviewed mapping requires system-text sources")
        local_en, local_fr = system_english, system_french
    else:
        raise ValueError(f"unsupported Android dialogue namespace: {namespace}")
    android_ids = record.get("android_ids", [])
    unit_ids = android_anchor_units(tuple(android_ids), local_en) if android_ids else []
    french_ids = [text_id for text_id in unit_ids if local_fr[text_id]]
    result = dict(record)
    result["android_namespace"] = namespace
    result["android_unit_ids"] = unit_ids
    result["android_english_display"] = " ".join(local_en[text_id] for text_id in android_ids)
    result["french_nonempty_ids"] = french_ids
    identity_french_display = " ".join(local_fr[text_id] for text_id in french_ids)
    result["identity_french_display"] = identity_french_display
    override_id = record.get("localization_systxt_id")
    if override_id is not None:
        if system_english is None or system_french is None or override_id not in system_french:
            raise ValueError("systxt localization override requires valid system-text sources")
        result["localization_override_namespace"] = "systxt"
        result["localization_override_id"] = override_id
        result["localization_override_source_en"] = system_english[override_id]
        result["french_display"] = system_french[override_id]
    else:
        result["french_display"] = identity_french_display
    return result


def _auto_drop_trailing_french_only_player_turns(
    records: list[dict],
    english: dict[int, str],
    french: dict[int, str],
) -> list[dict]:
    """Drop only a new French-only player turn trailing an English anchor.

    Android localization may continue one English anchor through English-empty
    French slots.  Those prose continuations remain owned by the anchor.  A
    later English-empty slot can instead begin a new mobile-only spoken turn as
    ``%S(n,0) : ...``.  If removing that new turn (and only the suffix after it)
    restores the exact SNES placeholder sequence, exclude the mobile-only turn
    from this SNES mapping.  Android English remains the identity layer.
    """
    placeholder_re = re.compile(r"%S\(\d+,0\)")
    repairs: list[dict] = []
    for record in records:
        if record.get("android_namespace", "scrtxt") != "scrtxt":
            continue
        unit_ids = list(record.get("android_unit_ids", []))
        french_ids = list(record.get("french_nonempty_ids", []))
        if not unit_ids or not french_ids:
            continue
        source_placeholders = tuple(placeholder_re.findall(record.get("source_display", "")))
        full_placeholders = tuple(
            placeholder_re.findall(normalize_android_french(record.get("french_display", "")))
        )
        if full_placeholders == source_placeholders:
            continue

        # Only inspect French-bearing slots whose Android-English counterpart is
        # empty and which occur after the final non-empty English anchor owned by
        # this record.  Preserve any preceding French-only prose continuation.
        last_english_pos = max(
            (pos for pos, text_id in enumerate(unit_ids) if english.get(text_id, "").strip()),
            default=-1,
        )
        for pos in range(last_english_pos + 1, len(unit_ids)):
            text_id = unit_ids[pos]
            if english.get(text_id, "").strip() or not french.get(text_id, "").strip():
                continue
            french_text = normalize_android_french(french[text_id]).lstrip()
            if not re.match(r"^%S\(\d+,0\)\s*:", french_text):
                continue
            suffix_ids = set(unit_ids[pos:])
            kept_ids = [candidate for candidate in french_ids if candidate not in suffix_ids]
            kept_display = " ".join(french[candidate] for candidate in kept_ids)
            kept_placeholders = tuple(
                placeholder_re.findall(normalize_android_french(kept_display))
            )
            if kept_placeholders != source_placeholders:
                continue
            dropped_ids = [candidate for candidate in french_ids if candidate in suffix_ids]
            record["french_nonempty_ids"] = kept_ids
            record["french_display"] = kept_display
            record["dropped_trailing_french_only_player_turn_ids"] = dropped_ids
            repairs.append(
                {
                    "event_id": record.get("event_id"),
                    "snes_ids": list(record.get("snes_ids", [])),
                    "android_ids": list(record.get("android_ids", [])),
                    "dropped_french_ids": dropped_ids,
                }
            )
            break
    return repairs


def _auto_reattribute_forward_player_french_slots(
    records: list[dict],
    english: dict[int, str],
    french: dict[int, str],
) -> list[dict]:
    """Move an English-empty French PLAYER_NAME continuation to the next anchor.

    Android normally stores localized spill text in English-empty slots owned by
    the preceding non-empty English anchor.  One stronger structural shape can
    prove the opposite ownership: an intervening French-only slot starts with a
    PLAYER_NAME placeholder absent from the preceding English anchor, the next
    English anchor starts with that exact placeholder, and the next anchor's
    French text omits it.  If the resulting placeholder sequences exactly match
    the two already-aligned SNES mappings, reattribute only that French slot to
    the following mapping.  Android English remains the identity layer and no
    SNES command is created, removed, or moved.
    """
    placeholder_re = re.compile(r"%S\(\d+,0\)")
    repairs: list[dict] = []
    for left, right in zip(records, records[1:]):
        if left.get("event_id") != right.get("event_id"):
            continue
        if left.get("session_id") is None or left.get("session_id") != right.get("session_id"):
            continue
        left_android = left.get("android_ids", [])
        right_android = right.get("android_ids", [])
        if len(left_android) != 1 or len(right_android) != 1:
            continue
        left_anchor = left_android[0]
        right_anchor = right_android[0]
        interval = english_anchor_interval(left_anchor, english)
        if not interval or interval[-1] + 1 != right_anchor or not english.get(right_anchor):
            continue
        spill_ids = [text_id for text_id in interval[1:] if french.get(text_id)]
        if len(spill_ids) != 1:
            continue
        spill_id = spill_ids[0]
        spill_text = normalize_android_french(french[spill_id]).strip()
        match = re.match(r"(%S\(\d+,0\))", spill_text)
        if match is None:
            continue
        placeholder = match.group(1)
        left_en_placeholders = tuple(placeholder_re.findall(normalize_android_french(english[left_anchor])))
        if placeholder in left_en_placeholders:
            continue
        right_en = normalize_android_french(english[right_anchor]).strip()
        right_fr = normalize_android_french(french[right_anchor]).strip()
        if not right_en.startswith(placeholder) or right_fr.startswith(placeholder):
            continue

        left_fr_ids = [text_id for text_id in left.get("french_nonempty_ids", []) if text_id != spill_id]
        right_fr_ids = [spill_id, *right.get("french_nonempty_ids", [])]
        left_display = " ".join(french[text_id] for text_id in left_fr_ids)
        right_display = " ".join(french[text_id] for text_id in right_fr_ids)
        if tuple(placeholder_re.findall(normalize_android_french(left_display))) != tuple(
            placeholder_re.findall(left.get("source_display", ""))
        ):
            continue
        if tuple(placeholder_re.findall(normalize_android_french(right_display))) != tuple(
            placeholder_re.findall(right.get("source_display", ""))
        ):
            continue

        left["french_nonempty_ids"] = left_fr_ids
        left["french_display"] = left_display
        left["forward_reattributed_french_ids"] = [spill_id]
        right["french_nonempty_ids"] = right_fr_ids
        right["french_display"] = right_display
        right["backward_reattributed_french_ids"] = [spill_id]
        repairs.append(
            {
                "event_id": left["event_id"],
                "from_android_anchor": left_anchor,
                "french_slot_id": spill_id,
                "to_android_anchor": right_anchor,
                "player_placeholder": placeholder,
            }
        )
    return repairs


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


def _auto_add_placeholder_index_equivalent_duplicates(
    sessions: list[dict],
    records: list[dict],
    index: _AutoCandidateIndex,
    english: dict[int, str],
    french: dict[int, str],
) -> list[dict]:
    """Resolve still-free exact duplicates equivalent only by PLAYER_NAME index.

    Android EN remains the identity proof: every candidate occurrence must be
    an exact normalized English duplicate of the SNES span. Android FR is used
    only to establish that choosing among those already-identical English copies
    cannot change the localized prose: every complete French unit must be
    identical after canonicalizing only ``%S(n,0)`` indexes. Running this pass
    after all pre-existing rules prevents it from replacing an already-owned
    mapping with a different duplicate occurrence.

    Calibration against the pre-rule accepted corpus finds 1/1 historical
    mapping eligible for this index-only extension and zero conflicts. The
    narrow sample is supplemented by the stronger invariant that every Android
    EN candidate is an exact duplicate and every complete FR unit is identical
    after changing only the dynamic PLAYER_NAME index.
    """
    owner = {snes_id: record for record in records for snes_id in record["snes_ids"]}

    def accepted_android_ids(record: dict) -> set[int]:
        result = set(record.get("android_ids", []))
        for group in record.get("android_alternative_anchor_groups", []):
            result.update(group)
        return result

    calibration_attempts = 0
    calibration_conflicts: list[tuple[str, list[int], list[int]]] = []
    for session in sessions:
        for element_index, element in enumerate(session["elements"]):
            snes_id = element["id"]
            accepted = owner.get(snes_id)
            if accepted is None or len(accepted.get("snes_ids", [])) != 1:
                continue
            source = _auto_render_span(session, element_index, element_index)
            exact_ids = index.exact.get(normalize_alignment_text(source), [])
            if len(exact_ids) < 2:
                continue
            french_units = [_auto_french_unit(text_id, english, french) for text_id in exact_ids]
            if not all(french_units) or len(set(french_units)) == 1:
                continue
            canonical_units = {
                tuple(re.sub(r"%S\(\d+,0\)", "%S(#,0)", part) for part in unit)
                for unit in french_units
            }
            if len(canonical_units) != 1:
                continue
            calibration_attempts += 1
            accepted_ids = accepted_android_ids(accepted)
            if not accepted_ids.intersection(exact_ids):
                calibration_conflicts.append(
                    (snes_id, list(exact_ids), sorted(accepted_ids))
                )
    if calibration_conflicts:
        raise ValueError(
            "PLAYER_NAME-index duplicate alignment contradicts accepted mappings: "
            + ", ".join(item[0] for item in calibration_conflicts[:10])
        )
    if calibration_attempts != 1:
        raise ValueError(
            "PLAYER_NAME-index duplicate calibration corpus changed unexpectedly: "
            f"expected 1 eligible accepted mapping, found {calibration_attempts}"
        )

    additions: list[dict] = []
    for session in sessions:
        for element_index, element in enumerate(session["elements"]):
            snes_id = element["id"]
            if snes_id in owner or snes_id in DIALOGUE_FORCED_UNMAPPED:
                continue
            source = _auto_render_span(session, element_index, element_index)
            exact_ids = index.exact.get(normalize_alignment_text(source), [])
            if len(exact_ids) < 2:
                continue
            french_units = [_auto_french_unit(text_id, english, french) for text_id in exact_ids]
            if not all(french_units):
                continue
            # Literal-equivalent duplicates are already handled by the original
            # exact-equivalence pass. This rule is only for placeholder-index
            # variants that would otherwise remain unresolved.
            if len(set(french_units)) == 1:
                continue
            canonical_units = {
                tuple(re.sub(r"%S\(\d+,0\)", "%S(#,0)", part) for part in unit)
                for unit in french_units
            }
            if len(canonical_units) != 1:
                continue
            chosen_french = french_units[0]
            record = {
                "event_id": session["event_id"],
                "session_id": session["session_id"],
                "snes_ids": [snes_id],
                "android_ids": [],
                "android_alternative_anchor_groups": [[text_id] for text_id in exact_ids],
                "confidence": "very_high_equivalent_duplicate_player_index",
                "provenance": "automatic_equivalent_duplicate",
                "relation": "exact_duplicate_equivalent_french_player_index",
                "source_display": source,
                "french_display": " ".join(chosen_french),
            }
            records.append(record)
            additions.append(record)
            owner[snes_id] = record
    return additions


def _auto_add_raw_unique_exact_player_context_neighbor(
    sessions: list[dict],
    records: list[dict],
    index: _AutoCandidateIndex,
    english: dict[int, str],
    french: dict[int, str],
) -> list[dict]:
    """Recover a raw-carrier exact obscured only by adjacent PLAYER_NAME context.

    ``_auto_render_span()`` deliberately includes nearby PLAYER_NAME commands so
    structural context is available to later binding.  In a small set of cases
    that context makes an otherwise unique Android-English exact look non-exact.
    Accept the raw carrier only when it is at least ten normalized characters,
    removing PLAYER_NAME markup from the rendered span restores the exact raw
    text, and the unique Android occurrence is immediately adjacent to an
    already-owned Android anchor in the same SNES session.  Decisions are
    non-cascading.

    Calibration against the pre-rule accepted corpus reproduces 36/36 eligible
    mappings with zero conflicts.
    """
    owner = {snes_id: record for record in records for snes_id in record["snes_ids"]}
    player_markup_re = re.compile(r"%S\(\d+,0\)")

    def accepted_android_ids(record: dict) -> set[int]:
        result = set(record.get("android_ids", []))
        for group in record.get("android_alternative_anchor_groups", []):
            result.update(group)
        return result

    calibration_attempts = 0
    calibration_conflicts: list[tuple[str, int, list[int]]] = []
    for session in sessions:
        elements = session["elements"]
        for element_index, element in enumerate(elements):
            snes_id = element["id"]
            accepted = owner.get(snes_id)
            if accepted is None or len(accepted.get("snes_ids", [])) != 1:
                continue
            raw_source = element.get("source", "")
            normalized = normalize_alignment_text(raw_source)
            if len(normalized) < 10:
                continue
            exact_ids = index.exact.get(normalized, [])
            if len(exact_ids) != 1:
                continue
            android_id = exact_ids[0]
            if not _auto_french_unit(android_id, english, french):
                continue
            rendered = _auto_render_span(session, element_index, element_index)
            if normalize_alignment_text(rendered) == normalized:
                continue
            if normalize_alignment_text(player_markup_re.sub("", rendered)) != normalized:
                continue

            previous_position = None
            following_position = None
            for search in range(element_index - 1, -1, -1):
                record = owner.get(elements[search]["id"])
                android_ids = record.get("android_ids", []) if record else []
                positions = [
                    index.anchor_pos[text_id]
                    for text_id in android_ids
                    if text_id in index.anchor_pos
                ]
                if positions:
                    previous_position = max(positions)
                    break
            for search in range(element_index + 1, len(elements)):
                record = owner.get(elements[search]["id"])
                android_ids = record.get("android_ids", []) if record else []
                positions = [
                    index.anchor_pos[text_id]
                    for text_id in android_ids
                    if text_id in index.anchor_pos
                ]
                if positions:
                    following_position = min(positions)
                    break
            candidate_position = index.anchor_pos[android_id]
            immediate = (
                previous_position is not None
                and candidate_position == previous_position + 1
            ) or (
                following_position is not None
                and candidate_position == following_position - 1
            )
            if not immediate:
                continue
            calibration_attempts += 1
            accepted_ids = accepted_android_ids(accepted)
            if android_id not in accepted_ids:
                calibration_conflicts.append(
                    (snes_id, android_id, sorted(accepted_ids))
                )
    if calibration_conflicts:
        raise ValueError(
            "Raw unique exact PLAYER_NAME-context alignment contradicts accepted mappings: "
            + ", ".join(item[0] for item in calibration_conflicts[:10])
        )
    if calibration_attempts != 36:
        raise ValueError(
            "Raw unique exact PLAYER_NAME-context calibration corpus changed unexpectedly: "
            f"expected 36 eligible accepted mappings, found {calibration_attempts}"
        )

    proposals: list[dict] = []
    for session in sessions:
        elements = session["elements"]
        for element_index, element in enumerate(elements):
            snes_id = element["id"]
            if snes_id in owner or snes_id in DIALOGUE_FORCED_UNMAPPED:
                continue
            raw_source = element.get("source", "")
            normalized = normalize_alignment_text(raw_source)
            if len(normalized) < 10:
                continue
            exact_ids = index.exact.get(normalized, [])
            if len(exact_ids) != 1:
                continue
            android_id = exact_ids[0]
            if not _auto_french_unit(android_id, english, french):
                continue

            rendered = _auto_render_span(session, element_index, element_index)
            if normalize_alignment_text(rendered) == normalized:
                continue
            if normalize_alignment_text(player_markup_re.sub("", rendered)) != normalized:
                continue

            previous_position = None
            following_position = None
            for search in range(element_index - 1, -1, -1):
                record = owner.get(elements[search]["id"])
                android_ids = record.get("android_ids", []) if record else []
                positions = [
                    index.anchor_pos[text_id]
                    for text_id in android_ids
                    if text_id in index.anchor_pos
                ]
                if positions:
                    previous_position = max(positions)
                    break
            for search in range(element_index + 1, len(elements)):
                record = owner.get(elements[search]["id"])
                android_ids = record.get("android_ids", []) if record else []
                positions = [
                    index.anchor_pos[text_id]
                    for text_id in android_ids
                    if text_id in index.anchor_pos
                ]
                if positions:
                    following_position = min(positions)
                    break

            candidate_position = index.anchor_pos[android_id]
            immediate = (
                previous_position is not None
                and candidate_position == previous_position + 1
            ) or (
                following_position is not None
                and candidate_position == following_position - 1
            )
            if not immediate:
                continue
            proposals.append(
                {
                    "event_id": session["event_id"],
                    "session_id": session["session_id"],
                    "snes_id": snes_id,
                    "android_id": android_id,
                    "source_display": raw_source,
                }
            )

    additions: list[dict] = []
    for proposal in proposals:
        snes_id = proposal["snes_id"]
        if snes_id in owner:
            continue
        android_id = proposal["android_id"]
        record = {
            "event_id": proposal["event_id"],
            "session_id": proposal["session_id"],
            "snes_ids": [snes_id],
            "android_ids": [android_id],
            "confidence": "very_high_raw_unique_exact_player_context_neighbor",
            "provenance": "automatic_exact_context",
            "relation": "raw_unique_exact_player_context_immediate_neighbor",
            "source_display": proposal["source_display"],
            "lexical_evidence": _auto_metrics(proposal["source_display"], english[android_id]),
        }
        records.append(record)
        additions.append(record)
        owner[snes_id] = record
    return additions

def _auto_add_exact_segmentation_equivalences(
    sessions: list[dict],
    records: list[dict],
    index: _AutoCandidateIndex,
    english: dict[int, str],
    french: dict[int, str],
) -> list[dict]:
    """Recover exact English identities whose SNES/Android segmentation differs.

    Compare contiguous spans of one to three semantic SNES elements with one to
    three consecutive non-empty Android-English anchors.  Ordinary 1:1 exact
    identities remain owned by the simpler exact-equivalence pass.  Every other
    segmentation is accepted only on exact normalized English equality and only
    when all duplicate Android segmentations yield one identical, non-empty
    complete French localization.  Overlapping source-span proposals are left
    unresolved rather than choosing between equally exact segmentations.
    """
    owner = {snes_id: record for record in records for snes_id in record["snes_ids"]}

    exact_android_segments: dict[str, list[tuple[int, ...]]] = {}
    for position in range(len(index.anchor_ids)):
        for width in (1, 2, 3):
            if position + width > len(index.anchor_ids):
                continue
            group = tuple(index.anchor_ids[position : position + width])
            normalized = normalize_alignment_text(" ".join(english[text_id] for text_id in group))
            if normalized:
                exact_android_segments.setdefault(normalized, []).append(group)

    def french_group(group: tuple[int, ...]) -> tuple[str, ...]:
        return tuple(
            french[text_id]
            for text_id in android_anchor_units(group, english)
            if french[text_id]
        )

    proposals: list[dict] = []
    for session in sessions:
        elements = session["elements"]
        for first in range(len(elements)):
            for source_width in (1, 2, 3):
                last = first + source_width - 1
                if last >= len(elements):
                    continue
                snes_ids = tuple(element["id"] for element in elements[first : last + 1])
                if any(snes_id in owner or snes_id in DIALOGUE_FORCED_UNMAPPED for snes_id in snes_ids):
                    continue
                source_display = _auto_render_span(session, first, last)
                normalized = normalize_alignment_text(source_display)
                groups = list(exact_android_segments.get(normalized, []))
                if not groups:
                    continue
                if source_width == 1:
                    # A competing one-anchor exact identity is either already
                    # handled by the ordinary pass or intentionally ambiguous;
                    # do not use a wider Android segmentation to override it.
                    if any(len(group) == 1 for group in groups):
                        continue
                    groups = [group for group in groups if len(group) > 1]
                    if not groups:
                        continue
                french_versions = {french_group(group) for group in groups}
                if len(french_versions) != 1 or not next(iter(french_versions), ()):
                    continue
                proposals.append(
                    {
                        "event_id": session["event_id"],
                        "session_id": session["session_id"],
                        "snes_ids": snes_ids,
                        "android_groups": groups,
                        "source_display": source_display,
                        "french_version": next(iter(french_versions)),
                    }
                )

    source_spans_by_id: dict[str, set[tuple[str, ...]]] = {}
    for proposal in proposals:
        span = tuple(proposal["snes_ids"])
        for snes_id in span:
            source_spans_by_id.setdefault(snes_id, set()).add(span)

    additions: list[dict] = []
    for proposal in proposals:
        snes_ids = tuple(proposal["snes_ids"])
        if any(len(source_spans_by_id[snes_id]) != 1 for snes_id in snes_ids):
            continue
        if any(snes_id in owner for snes_id in snes_ids):
            continue
        groups = proposal["android_groups"]
        if len(groups) == 1:
            android_ids = list(groups[0])
            record = {
                "event_id": proposal["event_id"],
                "session_id": proposal["session_id"],
                "snes_ids": list(snes_ids),
                "android_ids": android_ids,
                "confidence": "very_high_exact_segmentation",
                "provenance": "automatic_exact_segmentation",
                "relation": "exact_segmentation",
                "source_display": proposal["source_display"],
                "lexical_evidence": _auto_metrics(
                    proposal["source_display"],
                    " ".join(english[text_id] for text_id in android_ids),
                ),
            }
        else:
            record = {
                "event_id": proposal["event_id"],
                "session_id": proposal["session_id"],
                "snes_ids": list(snes_ids),
                "android_ids": [],
                "android_alternative_anchor_groups": [list(group) for group in groups],
                "confidence": "very_high_exact_segmentation_equivalent_duplicate",
                "provenance": "automatic_exact_segmentation",
                "relation": "exact_segmentation",
                "source_display": proposal["source_display"],
                "french_display": " ".join(proposal["french_version"]),
            }
        records.append(record)
        additions.append(record)
        for snes_id in snes_ids:
            owner[snes_id] = record
    return additions


def _auto_add_contextual_exact_duplicates(
    source_document: dict,
    sessions: list[dict],
    records: list[dict],
    index: _AutoCandidateIndex,
    english: dict[int, str],
    french: dict[int, str],
) -> list[dict]:
    """Disambiguate divergent exact duplicates from tight event-local context.

    Exact Android-English duplicates may carry different French localizations,
    so equality alone cannot choose an occurrence.  Accept one occurrence only
    when already-owned semantic neighbors make it structurally unique: either
    exactly one duplicate lies strictly between two nearby monotonic anchors,
    or exactly one duplicate is the immediately adjacent non-empty Android
    anchor to an established neighbor.  The pass is intentionally non-
    cascading: every decision uses ownership that existed on entry.
    """
    owner = {snes_id: record for record in records for snes_id in record["snes_ids"]}
    rendered_by_id: dict[str, str] = {}
    session_by_id: dict[str, int] = {}
    for session in sessions:
        for element_index, element in enumerate(session["elements"]):
            rendered_by_id[element["id"]] = _auto_render_span(session, element_index, element_index)
            session_by_id[element["id"]] = session["session_id"]

    proposals: list[dict] = []
    for event in source_document.get("events", []):
        semantic_tokens = [
            token
            for token in event.get("tokens", [])
            if token.get("type") == "text" and _auto_semantic(token.get("source", ""))
        ]
        semantic_ids = [token["id"] for token in semantic_tokens]
        for token_index, token in enumerate(semantic_tokens):
            snes_id = token["id"]
            if snes_id in owner or snes_id in DIALOGUE_FORCED_UNMAPPED:
                continue
            source_display = rendered_by_id.get(snes_id, token.get("source", ""))
            exact_ids = index.exact.get(normalize_alignment_text(source_display), [])
            if len(exact_ids) < 2:
                continue
            french_versions = {_auto_french_unit(text_id, english, french) for text_id in exact_ids}
            if len(french_versions) <= 1:
                continue

            previous_position = None
            following_position = None
            for search in range(token_index - 1, -1, -1):
                record = owner.get(semantic_ids[search])
                android_ids = record.get("android_ids", []) if record else []
                positions = [index.anchor_pos[text_id] for text_id in android_ids if text_id in index.anchor_pos]
                if positions:
                    previous_position = max(positions)
                    break
            for search in range(token_index + 1, len(semantic_ids)):
                record = owner.get(semantic_ids[search])
                android_ids = record.get("android_ids", []) if record else []
                positions = [index.anchor_pos[text_id] for text_id in android_ids if text_id in index.anchor_pos]
                if positions:
                    following_position = min(positions)
                    break

            chosen: int | None = None
            context = None
            if (
                previous_position is not None
                and following_position is not None
                and previous_position < following_position
                and following_position - previous_position <= 12
            ):
                bracketed = [
                    text_id
                    for text_id in exact_ids
                    if previous_position < index.anchor_pos[text_id] < following_position
                ]
                if len(bracketed) == 1:
                    chosen = bracketed[0]
                    context = "tight_bracket"

            if chosen is None:
                adjacent: list[int] = []
                if previous_position is not None:
                    adjacent.extend(
                        text_id
                        for text_id in exact_ids
                        if index.anchor_pos[text_id] == previous_position + 1
                    )
                if following_position is not None:
                    adjacent.extend(
                        text_id
                        for text_id in exact_ids
                        if index.anchor_pos[text_id] == following_position - 1
                    )
                adjacent = list(dict.fromkeys(adjacent))
                if len(adjacent) == 1:
                    chosen = adjacent[0]
                    context = "immediate_neighbor"

            if chosen is None or not _auto_french_unit(chosen, english, french):
                continue
            proposals.append(
                {
                    "event_id": event["event_id"],
                    "session_id": session_by_id.get(snes_id),
                    "snes_id": snes_id,
                    "android_id": chosen,
                    "context": context,
                    "source_display": source_display,
                }
            )

    additions: list[dict] = []
    for proposal in proposals:
        snes_id = proposal["snes_id"]
        if snes_id in owner:
            continue
        android_id = proposal["android_id"]
        record = {
            "event_id": proposal["event_id"],
            "session_id": proposal["session_id"],
            "snes_ids": [snes_id],
            "android_ids": [android_id],
            "confidence": (
                "very_high_exact_context_bracket"
                if proposal["context"] == "tight_bracket"
                else "very_high_exact_context_adjacent"
            ),
            "provenance": "automatic_exact_context",
            "relation": "exact_duplicate_context",
            "source_display": proposal["source_display"],
            "lexical_evidence": _auto_metrics(proposal["source_display"], english[android_id]),
        }
        records.append(record)
        additions.append(record)
        owner[snes_id] = record
    return additions


def _auto_add_tight_single_gap_context(
    source_document: dict,
    records: list[dict],
    index: _AutoCandidateIndex,
    english: dict[int, str],
    french: dict[int, str],
) -> list[dict]:
    """Fill a single free semantic Android anchor inside a tight owned bracket.

    When the nearest mapped semantic SNES neighbors define a monotonic Android
    interval of at most 12 semantic anchors, accept the unresolved carrier only
    if exactly one semantic Android anchor in that interval is still unowned,
    its French is non-empty, source-token coverage is >=80%, and lexical score
    is >=60. Proposals competing for the same Android anchor are rejected as a
    group. Decisions are non-cascading.

    Calibration against the pre-rule accepted corpus reproduces 495/495
    eligible historical single-anchor mappings with zero conflicts.
    """
    owner = {snes_id: record for record in records for snes_id in record["snes_ids"]}
    android_owned = {
        text_id
        for record in records
        for text_id in record.get("android_ids", [])
        if text_id in index.anchor_pos
    }
    proposals: list[dict] = []
    for event in source_document.get("events", []):
        semantic_tokens = [
            token
            for token in event.get("tokens", [])
            if token.get("type") == "text" and _auto_semantic(token.get("source", ""))
        ]
        semantic_ids = [token["id"] for token in semantic_tokens]
        for token_index, token in enumerate(semantic_tokens):
            snes_id = token["id"]
            if snes_id in owner or snes_id in DIALOGUE_FORCED_UNMAPPED:
                continue
            previous_position = None
            following_position = None
            for search in range(token_index - 1, -1, -1):
                record = owner.get(semantic_ids[search])
                android_ids = record.get("android_ids", []) if record else []
                positions = [index.anchor_pos[text_id] for text_id in android_ids if text_id in index.anchor_pos]
                if positions:
                    previous_position = max(positions)
                    break
            for search in range(token_index + 1, len(semantic_ids)):
                record = owner.get(semantic_ids[search])
                android_ids = record.get("android_ids", []) if record else []
                positions = [index.anchor_pos[text_id] for text_id in android_ids if text_id in index.anchor_pos]
                if positions:
                    following_position = min(positions)
                    break
            if (
                previous_position is None
                or following_position is None
                or not previous_position < following_position
                or following_position - previous_position > 12
            ):
                continue
            candidates = [
                text_id
                for text_id in index.anchor_ids[previous_position + 1 : following_position]
                if text_id not in android_owned and _auto_french_unit(text_id, english, french)
            ]
            if len(candidates) != 1:
                continue
            android_id = candidates[0]
            source_display = token.get("source", "")
            evidence = _auto_metrics(source_display, english[android_id])
            if evidence["source_token_coverage"] < 80 or evidence["lexical_score"] < 60:
                continue
            proposals.append(
                {
                    "event_id": event["event_id"],
                    "snes_id": snes_id,
                    "android_id": android_id,
                    "source_display": source_display,
                    "lexical_evidence": evidence,
                }
            )

    proposal_counts: dict[int, int] = {}
    for proposal in proposals:
        proposal_counts[proposal["android_id"]] = proposal_counts.get(proposal["android_id"], 0) + 1

    additions: list[dict] = []
    for proposal in proposals:
        snes_id = proposal["snes_id"]
        android_id = proposal["android_id"]
        if snes_id in owner or proposal_counts[android_id] != 1:
            continue
        record = {
            "event_id": proposal["event_id"],
            "snes_ids": [snes_id],
            "android_ids": [android_id],
            "confidence": "very_high_tight_single_gap",
            "provenance": "automatic_exact_context",
            "relation": "tight_single_gap_context",
            "source_display": proposal["source_display"],
            "lexical_evidence": proposal["lexical_evidence"],
        }
        records.append(record)
        additions.append(record)
        owner[snes_id] = record
    return additions


def _auto_add_isolated_high_coverage_global(
    source_document: dict,
    records: list[dict],
    index: _AutoCandidateIndex,
    english: dict[int, str],
    french: dict[int, str],
) -> list[dict]:
    """Accept a long isolated global candidate with very high lexical coverage.

    This rule is deliberately unavailable to short/generic strings. The raw
    normalized SNES carrier must be at least 40 characters, the global best
    Android-English candidate must have lexical score >=82, source-token
    coverage >=92%, character similarity >=80%, and a >=20-point margin over
    the runner-up. The Android anchor must be currently unowned and proposals
    must be unique. Calibration reproduces 483/483 eligible historical mappings
    with zero conflicts.
    """
    owner = {snes_id: record for record in records for snes_id in record["snes_ids"]}
    android_owned = {text_id for record in records for text_id in record.get("android_ids", [])}
    proposals: list[dict] = []
    for event in source_document.get("events", []):
        for token in event.get("tokens", []):
            if token.get("type") != "text" or not _auto_semantic(token.get("source", "")):
                continue
            snes_id = token["id"]
            if snes_id in owner or snes_id in DIALOGUE_FORCED_UNMAPPED:
                continue
            source_display = token.get("source", "")
            if len(normalize_alignment_text(source_display)) < 40:
                continue
            ranked = index.rank(source_display, limit=5)
            if len(ranked) < 2:
                continue
            top, second = ranked[0], ranked[1]
            android_id = top["android_id"]
            if android_id in android_owned or not _auto_french_unit(android_id, english, french):
                continue
            if (
                top["lexical_score"] < 82
                or top["source_token_coverage"] < 92
                or top["character_similarity"] < 80
                or top["lexical_score"] - second["lexical_score"] < 20
            ):
                continue
            proposals.append(
                {
                    "event_id": event["event_id"],
                    "snes_id": snes_id,
                    "android_id": android_id,
                    "source_display": source_display,
                    "lexical_evidence": {
                        key: top[key]
                        for key in ("character_similarity", "source_token_coverage", "lexical_score")
                    },
                    "candidate_margin": round(top["lexical_score"] - second["lexical_score"], 1),
                }
            )

    proposal_counts: dict[int, int] = {}
    for proposal in proposals:
        proposal_counts[proposal["android_id"]] = proposal_counts.get(proposal["android_id"], 0) + 1
    additions: list[dict] = []
    for proposal in proposals:
        snes_id = proposal["snes_id"]
        android_id = proposal["android_id"]
        if snes_id in owner or proposal_counts[android_id] != 1:
            continue
        record = {
            "event_id": proposal["event_id"],
            "snes_ids": [snes_id],
            "android_ids": [android_id],
            "confidence": "very_high_isolated_global_coverage",
            "provenance": "automatic_global_coverage",
            "relation": "isolated_high_coverage_global",
            "source_display": proposal["source_display"],
            "lexical_evidence": proposal["lexical_evidence"],
            "candidate_margin": proposal["candidate_margin"],
        }
        records.append(record)
        additions.append(record)
        owner[snes_id] = record
    return additions



def _auto_add_isolated_contained_extension(
    source_document: dict,
    records: list[dict],
    index: _AutoCandidateIndex,
    english: dict[int, str],
    french: dict[int, str],
) -> list[dict]:
    """Accept a long SNES carrier verbatim-contained in a longer Android line.

    This handles version adaptations where Android English preserves the whole
    SNES wording in order but adds one clause before or after it.  The source
    must be at least 35 normalized characters, all normalized SNES tokens must
    occur as one contiguous token sequence inside the best Android-English
    candidate, token coverage must be 100%, lexical score >=76, character
    similarity >=68%, and the best candidate must lead the runner-up by >=30
    points.  The Android anchor must be free and each proposed anchor unique.

    Calibration against the accepted mapping corpus reproduces 535/535
    eligible historical mappings with zero conflicts.
    """
    owner = {snes_id: record for record in records for snes_id in record["snes_ids"]}
    android_owned = {text_id for record in records for text_id in record.get("android_ids", [])}

    def is_contained(source_display: str, android_display: str) -> bool:
        source_tokens = normalize_alignment_text(source_display).split()
        android_tokens = normalize_alignment_text(android_display).split()
        if not source_tokens or len(source_tokens) > len(android_tokens):
            return False
        width = len(source_tokens)
        return any(
            android_tokens[start:start + width] == source_tokens
            for start in range(len(android_tokens) - width + 1)
        )

    # Measure the rule against mappings that are already accepted before it is
    # allowed to propose anything new.  Only one-carrier records with concrete
    # Android provenance are comparable here; multi-carrier structural mappings
    # are intentionally outside this global lexical rule.
    calibration_attempts = 0
    calibration_conflicts: list[tuple[str, int, list[int]]] = []
    for event in source_document.get("events", []):
        for token in event.get("tokens", []):
            if token.get("type") != "text" or not _auto_semantic(token.get("source", "")):
                continue
            snes_id = token["id"]
            accepted = owner.get(snes_id)
            if (
                accepted is None
                or len(accepted.get("snes_ids", [])) != 1
                or not accepted.get("android_ids")
            ):
                continue
            source_display = token.get("source", "")
            if len(normalize_alignment_text(source_display)) < 35:
                continue
            ranked = index.rank(source_display, limit=5)
            if len(ranked) < 2:
                continue
            top, second = ranked[0], ranked[1]
            if (
                not is_contained(source_display, english[top["android_id"]])
                or top["source_token_coverage"] < 100
                or top["lexical_score"] < 76
                or top["character_similarity"] < 68
                or top["lexical_score"] - second["lexical_score"] < 30
            ):
                continue
            calibration_attempts += 1
            if top["android_id"] not in accepted["android_ids"]:
                calibration_conflicts.append(
                    (snes_id, top["android_id"], list(accepted["android_ids"]))
                )
    if calibration_conflicts:
        raise ValueError(
            "Contained-extension alignment contradicts accepted mappings: "
            + ", ".join(item[0] for item in calibration_conflicts[:10])
        )

    proposals: list[dict] = []
    for event in source_document.get("events", []):
        for token in event.get("tokens", []):
            if token.get("type") != "text" or not _auto_semantic(token.get("source", "")):
                continue
            snes_id = token["id"]
            if snes_id in owner or snes_id in DIALOGUE_FORCED_UNMAPPED:
                continue
            source_display = token.get("source", "")
            if len(normalize_alignment_text(source_display)) < 35:
                continue
            ranked = index.rank(source_display, limit=5)
            if len(ranked) < 2:
                continue
            top, second = ranked[0], ranked[1]
            android_id = top["android_id"]
            if android_id in android_owned or not _auto_french_unit(android_id, english, french):
                continue
            if not is_contained(source_display, english[android_id]):
                continue
            if (
                top["source_token_coverage"] < 100
                or top["lexical_score"] < 76
                or top["character_similarity"] < 68
                or top["lexical_score"] - second["lexical_score"] < 30
            ):
                continue
            proposals.append(
                {
                    "event_id": event["event_id"],
                    "snes_id": snes_id,
                    "android_id": android_id,
                    "source_display": source_display,
                    "lexical_evidence": {
                        key: top[key]
                        for key in ("character_similarity", "source_token_coverage", "lexical_score")
                    },
                    "candidate_margin": round(top["lexical_score"] - second["lexical_score"], 1),
                }
            )

    proposal_counts: dict[int, int] = {}
    for proposal in proposals:
        proposal_counts[proposal["android_id"]] = proposal_counts.get(proposal["android_id"], 0) + 1
    additions: list[dict] = []
    for proposal in proposals:
        snes_id = proposal["snes_id"]
        android_id = proposal["android_id"]
        if snes_id in owner or proposal_counts[android_id] != 1:
            continue
        record = {
            "event_id": proposal["event_id"],
            "snes_ids": [snes_id],
            "android_ids": [android_id],
            "confidence": "very_high_isolated_contained_extension",
            "provenance": "automatic_global_containment",
            "relation": "isolated_contained_android_extension",
            "source_display": proposal["source_display"],
            "lexical_evidence": proposal["lexical_evidence"],
            "candidate_margin": proposal["candidate_margin"],
        }
        records.append(record)
        additions.append(record)
        owner[snes_id] = record
    return additions

def _auto_add_raw_contextual_exact_duplicates(
    source_document: dict,
    records: list[dict],
    index: _AutoCandidateIndex,
    english: dict[int, str],
    french: dict[int, str],
) -> list[dict]:
    """Disambiguate divergent exact duplicates using the raw SNES text carrier.

    This complements the rendered-span exact-context pass for cases where a
    following PLAYER_NAME/staging command is structurally attached to the SNES
    carrier by the session renderer but belongs to the next Android record.
    Identity is accepted only when the raw carrier has divergent exact Android
    duplicates and already-owned semantic neighbors make exactly one occurrence
    unique inside a tight bracket or as the sole immediate neighbor. Decisions
    are non-cascading. Calibration reproduces 27/27 eligible historical mappings
    with zero conflicts.
    """
    owner = {snes_id: record for record in records for snes_id in record["snes_ids"]}
    proposals: list[dict] = []
    for event in source_document.get("events", []):
        semantic_tokens = [
            token
            for token in event.get("tokens", [])
            if token.get("type") == "text" and _auto_semantic(token.get("source", ""))
        ]
        semantic_ids = [token["id"] for token in semantic_tokens]
        for token_index, token in enumerate(semantic_tokens):
            snes_id = token["id"]
            if snes_id in owner or snes_id in DIALOGUE_FORCED_UNMAPPED:
                continue
            source_display = token.get("source", "")
            exact_ids = index.exact.get(normalize_alignment_text(source_display), [])
            if len(exact_ids) < 2:
                continue
            french_versions = {
                _auto_french_unit(text_id, english, french)
                for text_id in exact_ids
                if _auto_french_unit(text_id, english, french)
            }
            if len(french_versions) <= 1:
                continue

            previous_position = None
            following_position = None
            for search in range(token_index - 1, -1, -1):
                record = owner.get(semantic_ids[search])
                android_ids = record.get("android_ids", []) if record else []
                positions = [index.anchor_pos[text_id] for text_id in android_ids if text_id in index.anchor_pos]
                if positions:
                    previous_position = max(positions)
                    break
            for search in range(token_index + 1, len(semantic_ids)):
                record = owner.get(semantic_ids[search])
                android_ids = record.get("android_ids", []) if record else []
                positions = [index.anchor_pos[text_id] for text_id in android_ids if text_id in index.anchor_pos]
                if positions:
                    following_position = min(positions)
                    break

            chosen = None
            context = None
            if (
                previous_position is not None
                and following_position is not None
                and previous_position < following_position
                and following_position - previous_position <= 12
            ):
                bracketed = [
                    text_id
                    for text_id in exact_ids
                    if previous_position < index.anchor_pos[text_id] < following_position
                ]
                if len(bracketed) == 1:
                    chosen = bracketed[0]
                    context = "tight_bracket"
            if chosen is None:
                adjacent: list[int] = []
                if previous_position is not None:
                    adjacent.extend(
                        text_id
                        for text_id in exact_ids
                        if index.anchor_pos[text_id] == previous_position + 1
                    )
                if following_position is not None:
                    adjacent.extend(
                        text_id
                        for text_id in exact_ids
                        if index.anchor_pos[text_id] == following_position - 1
                    )
                adjacent = list(dict.fromkeys(adjacent))
                if len(adjacent) == 1:
                    chosen = adjacent[0]
                    context = "immediate_neighbor"
            if chosen is None or not _auto_french_unit(chosen, english, french):
                continue
            proposals.append(
                {
                    "event_id": event["event_id"],
                    "snes_id": snes_id,
                    "android_id": chosen,
                    "context": context,
                    "source_display": source_display,
                }
            )

    additions: list[dict] = []
    for proposal in proposals:
        snes_id = proposal["snes_id"]
        if snes_id in owner:
            continue
        android_id = proposal["android_id"]
        record = {
            "event_id": proposal["event_id"],
            "snes_ids": [snes_id],
            "android_ids": [android_id],
            "confidence": (
                "very_high_raw_exact_context_bracket"
                if proposal["context"] == "tight_bracket"
                else "very_high_raw_exact_context_adjacent"
            ),
            "provenance": "automatic_exact_context",
            "relation": "raw_exact_duplicate_context",
            "source_display": proposal["source_display"],
            "lexical_evidence": _auto_metrics(proposal["source_display"], english[android_id]),
        }
        records.append(record)
        additions.append(record)
        owner[snes_id] = record
    return additions


def _auto_add_short_unique_immediate_neighbor(
    sessions: list[dict],
    records: list[dict],
    index: _AutoCandidateIndex,
    english: dict[int, str],
    french: dict[int, str],
) -> list[dict]:
    """Accept a very short globally-unique exact only beside an owned anchor.

    Generic short exacts remain unsafe even when globally unique.  This narrower
    rule additionally requires the sole Android-English exact occurrence to be
    immediately adjacent to the nearest already-owned Android anchor on either
    side inside the same SNES dialogue session.  Decisions are non-cascading.

    Calibration against the pre-rule accepted corpus reproduces 37/37 eligible
    historical mappings with zero conflicts.
    """
    owner = {snes_id: record for record in records for snes_id in record["snes_ids"]}
    proposals: list[dict] = []
    for session in sessions:
        elements = session["elements"]
        for element_index, element in enumerate(elements):
            snes_id = element["id"]
            if snes_id in owner or snes_id in DIALOGUE_FORCED_UNMAPPED:
                continue
            source_display = _auto_render_span(session, element_index, element_index)
            normalized = normalize_alignment_text(source_display)
            if not normalized or len(normalized) >= 8:
                continue
            exact_ids = index.exact.get(normalized, [])
            if len(exact_ids) != 1:
                continue
            android_id = exact_ids[0]
            if not _auto_french_unit(android_id, english, french):
                continue

            previous_record = None
            following_record = None
            for search in range(element_index - 1, -1, -1):
                candidate = owner.get(elements[search]["id"])
                if candidate and candidate.get("android_ids"):
                    previous_record = candidate
                    break
            for search in range(element_index + 1, len(elements)):
                candidate = owner.get(elements[search]["id"])
                if candidate and candidate.get("android_ids"):
                    following_record = candidate
                    break

            candidate_position = index.anchor_pos[android_id]
            immediate = False
            if previous_record:
                positions = [
                    index.anchor_pos[text_id]
                    for text_id in previous_record["android_ids"]
                    if text_id in index.anchor_pos
                ]
                immediate = bool(positions) and candidate_position == max(positions) + 1
            if not immediate and following_record:
                positions = [
                    index.anchor_pos[text_id]
                    for text_id in following_record["android_ids"]
                    if text_id in index.anchor_pos
                ]
                immediate = bool(positions) and candidate_position == min(positions) - 1
            if not immediate:
                continue

            proposals.append(
                {
                    "event_id": session["event_id"],
                    "session_id": session["session_id"],
                    "snes_id": snes_id,
                    "android_id": android_id,
                    "source_display": source_display,
                }
            )

    additions: list[dict] = []
    for proposal in proposals:
        snes_id = proposal["snes_id"]
        if snes_id in owner:
            continue
        android_id = proposal["android_id"]
        record = {
            "event_id": proposal["event_id"],
            "session_id": proposal["session_id"],
            "snes_ids": [snes_id],
            "android_ids": [android_id],
            "confidence": "very_high_short_unique_immediate",
            "provenance": "automatic_exact_context",
            "relation": "short_unique_exact_immediate_neighbor",
            "source_display": proposal["source_display"],
            "lexical_evidence": _auto_metrics(proposal["source_display"], english[android_id]),
        }
        records.append(record)
        additions.append(record)
        owner[snes_id] = record
    return additions


def _auto_add_short_exact_punctuation_bracket(
    source_document: dict,
    sessions: list[dict],
    records: list[dict],
    index: _AutoCandidateIndex,
    english: dict[int, str],
    french: dict[int, str],
) -> list[dict]:
    """Accept a short globally-unique exact only inside a tight semantic bracket.

    Short exact strings are unsafe globally (validated counterexamples include
    generic labels/cries such as Kakkara, Sure!, and Okay).  This pass therefore
    requires both neighboring semantic SNES elements to already own monotonic
    Android anchors no more than 12 non-empty anchors apart.  The exact Android
    occurrence must be unique, lie strictly inside that bracket, and every other
    Android anchor inside the bracket must be punctuation/layout-only after the
    same normalization used by the identity layer.  Decisions are non-cascading.

    Calibration against the pre-rule accepted corpus reproduces 35/35 eligible
    historical mappings with zero conflicts.
    """
    owner = {snes_id: record for record in records for snes_id in record["snes_ids"]}
    rendered_by_id: dict[str, str] = {}
    session_by_id: dict[str, int] = {}
    for session in sessions:
        for element_index, element in enumerate(session["elements"]):
            rendered_by_id[element["id"]] = _auto_render_span(session, element_index, element_index)
            session_by_id[element["id"]] = session["session_id"]

    proposals: list[dict] = []
    for event in source_document.get("events", []):
        semantic_tokens = [
            token
            for token in event.get("tokens", [])
            if token.get("type") == "text" and _auto_semantic(token.get("source", ""))
        ]
        semantic_ids = [token["id"] for token in semantic_tokens]
        for token_index, token in enumerate(semantic_tokens):
            snes_id = token["id"]
            if snes_id in owner or snes_id in DIALOGUE_FORCED_UNMAPPED:
                continue
            # Use the text carrier itself here rather than _auto_render_span():
            # a following PLAYER_NAME/action belongs to layout/staging and can
            # be rendered into the preceding alignment span even when Android
            # places that command context on the next record. The two-sided
            # semantic bracket below is the identity proof; formatter/simulator
            # remain the independent structural/layout gate.
            source_display = token.get("source", "")
            normalized = normalize_alignment_text(source_display)
            if not normalized or len(normalized) >= 12:
                continue
            exact_ids = index.exact.get(normalized, [])
            if len(exact_ids) != 1:
                continue
            android_id = exact_ids[0]
            if not _auto_french_unit(android_id, english, french):
                continue

            previous_position = None
            following_position = None
            for search in range(token_index - 1, -1, -1):
                record = owner.get(semantic_ids[search])
                android_ids = record.get("android_ids", []) if record else []
                positions = [index.anchor_pos[text_id] for text_id in android_ids if text_id in index.anchor_pos]
                if positions:
                    previous_position = max(positions)
                    break
            for search in range(token_index + 1, len(semantic_ids)):
                record = owner.get(semantic_ids[search])
                android_ids = record.get("android_ids", []) if record else []
                positions = [index.anchor_pos[text_id] for text_id in android_ids if text_id in index.anchor_pos]
                if positions:
                    following_position = min(positions)
                    break

            candidate_position = index.anchor_pos.get(android_id)
            if (
                previous_position is None
                or following_position is None
                or candidate_position is None
                or not previous_position < candidate_position < following_position
                or following_position - previous_position > 12
            ):
                continue
            interior = index.anchor_ids[previous_position + 1 : following_position]
            if any(
                text_id != android_id and normalize_alignment_text(english[text_id])
                for text_id in interior
            ):
                continue
            proposals.append(
                {
                    "event_id": event["event_id"],
                    "session_id": session_by_id.get(snes_id),
                    "snes_id": snes_id,
                    "android_id": android_id,
                    "source_display": source_display,
                }
            )

    additions: list[dict] = []
    for proposal in proposals:
        snes_id = proposal["snes_id"]
        if snes_id in owner:
            continue
        android_id = proposal["android_id"]
        record = {
            "event_id": proposal["event_id"],
            "session_id": proposal["session_id"],
            "snes_ids": [snes_id],
            "android_ids": [android_id],
            "confidence": "very_high_short_exact_punctuation_bracket",
            "provenance": "automatic_exact_context",
            "relation": "short_exact_punctuation_bracket",
            "source_display": proposal["source_display"],
            "lexical_evidence": _auto_metrics(proposal["source_display"], english[android_id]),
        }
        records.append(record)
        additions.append(record)
        owner[snes_id] = record
    return additions



def _auto_source_rom_position(snes_id: str) -> int | None:
    """Return a linear C9/CA ROM position for one canonical dialogue text ID."""
    match = re.fullmatch(r"([0-9A-F]{2}):([0-9A-F]{4})", snes_id)
    if match is None:
        return None
    return (int(match.group(1), 16) << 16) + int(match.group(2), 16)


def _auto_rom_neighborhood_duplicate_prediction(
    snes_id: str,
    records: list[dict],
    source: dict[str, dict],
    index: _AutoCandidateIndex,
    english: dict[int, str],
    *,
    exclude_record: dict | None = None,
) -> dict | None:
    """Choose an exact duplicate only when nearby ROM carriers form one Android cluster.

    This intentionally does not require strict Android monotonicity: adjacent SNES
    events can be reordered locally on Android.  Instead, the twelve closest
    already-aligned source carriers within 0x300 bytes vote for the Android
    neighborhood that best fits each exact-English duplicate.  Close SNES
    carriers count more heavily; a carrier from the same SNES event receives a
    small additional weight.  The rule abstains unless the best duplicate has a
    >=20% score margin over the runner-up.
    """
    target_position = _auto_source_rom_position(snes_id)
    if target_position is None or snes_id not in source:
        return None
    normalized = normalize_alignment_text(source[snes_id]["source"])
    exact_ids = list(index.exact.get(normalized, ()))
    if len(exact_ids) < 2:
        return None

    occurrences: list[dict] = []
    for record in records:
        if record is exclude_record or not record.get("android_ids"):
            continue
        android_positions = [
            index.anchor_pos[text_id]
            for text_id in record["android_ids"]
            if text_id in index.anchor_pos
        ]
        if not android_positions:
            continue
        for neighbor_id in record.get("snes_ids", []):
            neighbor_position = _auto_source_rom_position(neighbor_id)
            if neighbor_position is None:
                continue
            snes_distance = abs(neighbor_position - target_position)
            if snes_distance > 0x300:
                continue
            occurrences.append(
                {
                    "snes_id": neighbor_id,
                    "event_id": source[neighbor_id]["event_id"],
                    "snes_distance": snes_distance,
                    "android_ids": list(record["android_ids"]),
                    "android_min": min(android_positions),
                    "android_max": max(android_positions),
                }
            )
    occurrences.sort(key=lambda item: item["snes_distance"])
    neighbors = occurrences[:12]
    if len(neighbors) < 4:
        return None

    scores: dict[int, float] = {}
    target_event = source[snes_id]["event_id"]
    for android_id in exact_ids:
        candidate_position = index.anchor_pos[android_id]
        score = 0.0
        for neighbor in neighbors:
            if neighbor["android_min"] <= candidate_position <= neighbor["android_max"]:
                android_distance = 0
            else:
                android_distance = min(
                    abs(candidate_position - neighbor["android_min"]),
                    abs(candidate_position - neighbor["android_max"]),
                )
            weight = 1.0 / (1.0 + neighbor["snes_distance"] / 64.0)
            if neighbor["event_id"] == target_event:
                weight *= 1.5
            score += weight * math.exp(-android_distance / 12.0)
        scores[android_id] = score

    ranked = sorted(scores, key=scores.get, reverse=True)
    if len(ranked) < 2 or scores[ranked[0]] <= 0:
        return None
    best, second = ranked[0], ranked[1]
    relative_margin = (scores[best] - scores[second]) / max(scores[best], 1.0e-9)
    if relative_margin < 0.20:
        return None
    return {
        "android_id": best,
        "candidate_android_ids": exact_ids,
        "relative_score_margin": round(relative_margin, 3),
        "neighbor_count": len(neighbors),
        "neighbors": neighbors,
    }


def _auto_add_rom_neighborhood_exact_duplicates(
    records: list[dict],
    source: dict[str, dict],
    index: _AutoCandidateIndex,
    english: dict[int, str],
    french: dict[int, str],
) -> tuple[list[dict], dict]:
    """Resolve substantive divergent exact duplicates from nearby ROM provenance.

    Calibration is leave-one-out over every already-accepted simple exact
    duplicate whose Android copies have different French localization units.
    The scoring model may abstain, but every confident calibration prediction
    must reproduce the accepted Android identity.  Application is narrower than
    calibration: at least three normalized source words are required so generic
    labels/short replies such as Water Palace, Sure!, Okay, or What the...!
    remain outside this rule even if their physical neighborhood looks suggestive.
    """
    claimed_context_ids: set[str] = set()
    context_records: list[dict] = []
    for record in records:
        if any(snes_id in claimed_context_ids for snes_id in record.get("snes_ids", [])):
            continue
        context_records.append(record)
        claimed_context_ids.update(record.get("snes_ids", []))

    calibration_attempts = 0
    calibration_matches = 0
    calibration_conflicts: list[dict] = []
    for record in context_records:
        if len(record.get("snes_ids", [])) != 1 or len(record.get("android_ids", [])) != 1:
            continue
        snes_id = record["snes_ids"][0]
        if snes_id not in source:
            continue
        accepted_android_id = record["android_ids"][0]
        normalized = normalize_alignment_text(source[snes_id]["source"])
        if normalized != normalize_alignment_text(english.get(accepted_android_id, "")):
            continue
        exact_ids = list(index.exact.get(normalized, ()))
        if len(exact_ids) < 2:
            continue
        french_units = {_auto_french_unit(text_id, english, french) for text_id in exact_ids}
        if len(french_units) <= 1:
            continue
        prediction = _auto_rom_neighborhood_duplicate_prediction(
            snes_id,
            context_records,
            source,
            index,
            english,
            exclude_record=record,
        )
        if prediction is None:
            continue
        calibration_attempts += 1
        if prediction["android_id"] == accepted_android_id:
            calibration_matches += 1
        else:
            calibration_conflicts.append(
                {
                    "snes_id": snes_id,
                    "accepted_android_id": accepted_android_id,
                    "predicted_android_id": prediction["android_id"],
                }
            )
    if calibration_conflicts:
        raise ValueError(
            "ROM-neighborhood exact-duplicate alignment contradicts accepted mappings: "
            + ", ".join(item["snes_id"] for item in calibration_conflicts[:10])
        )

    owner = {snes_id for record in context_records for snes_id in record.get("snes_ids", [])}
    additions: list[dict] = []
    proposals: list[dict] = []
    for snes_id, entry in source.items():
        if snes_id in owner or snes_id in DIALOGUE_FORCED_UNMAPPED:
            continue
        normalized = normalize_alignment_text(entry["source"])
        if len(normalized.split()) < 3:
            continue
        exact_ids = list(index.exact.get(normalized, ()))
        if len(exact_ids) < 2:
            continue
        french_units = {_auto_french_unit(text_id, english, french) for text_id in exact_ids}
        if len(french_units) <= 1:
            continue
        prediction = _auto_rom_neighborhood_duplicate_prediction(
            snes_id,
            context_records,
            source,
            index,
            english,
        )
        if prediction is None:
            continue
        android_id = prediction["android_id"]
        record = {
            "event_id": entry["event_id"],
            "snes_ids": [snes_id],
            "android_ids": [android_id],
            "confidence": "very_high_rom_neighborhood_exact_duplicate",
            "provenance": "automatic_rom_neighborhood",
            "relation": "exact_duplicate_resolved_by_rom_neighborhood",
            "source_display": entry["source"],
            "lexical_evidence": _auto_metrics(entry["source"], english[android_id]),
            "rom_neighborhood_evidence": prediction,
        }
        proposals.append(record)
        owner.add(snes_id)

    records.extend(proposals)
    additions.extend(proposals)
    return additions, {
        "accepted_mapping_attempts": calibration_attempts,
        "accepted_mapping_reproductions": calibration_matches,
        "conflicts": 0,
    }


def _auto_android_group_raw_payload(
    group: tuple[int, ...] | list[int],
    english: dict[int, str],
    french: dict[int, str],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return the strict Android EN/FR payload represented by one anchor group."""
    french_ids: list[int] = []
    for android_id in group:
        for text_id in android_anchor_units((android_id,), english):
            if text_id not in french_ids:
                french_ids.append(text_id)
    return (
        tuple(english[android_id] for android_id in group),
        tuple(french[text_id] for text_id in french_ids if french[text_id]),
    )


def _auto_equivalent_group_position_prediction(
    snes_ids: list[str] | tuple[str, ...],
    android_groups: list[list[int]] | tuple[tuple[int, ...], ...],
    context_records: list[dict],
    source: dict[str, dict],
    index: _AutoCandidateIndex,
) -> dict | None:
    """Pick one translation-equivalent Android occurrence from frozen context.

    This is only a provenance tie-breaker.  It is deliberately evaluated from
    records that were concrete before this rule runs, so positionally chosen
    equivalent duplicates never become evidence for another mapping in the same
    pass.  Nearby carriers from the same SNES event receive a strong preference;
    otherwise the broader ROM-neighborhood cloud acts as the fallback.
    """
    target_positions = [
        position
        for snes_id in snes_ids
        if (position := _auto_source_rom_position(snes_id)) is not None
    ]
    if not target_positions:
        return None
    target_events = {
        source[snes_id]["event_id"] for snes_id in snes_ids if snes_id in source
    }
    target_set = set(snes_ids)

    occurrences: list[dict] = []
    for record in context_records:
        if not record.get("android_ids") or target_set.intersection(record.get("snes_ids", [])):
            continue
        android_positions = [
            index.anchor_pos[text_id]
            for text_id in record["android_ids"]
            if text_id in index.anchor_pos
        ]
        if not android_positions:
            continue
        for neighbor_id in record.get("snes_ids", []):
            neighbor_position = _auto_source_rom_position(neighbor_id)
            if neighbor_position is None or neighbor_id not in source:
                continue
            snes_distance = min(abs(neighbor_position - target) for target in target_positions)
            if snes_distance > 0x300:
                continue
            occurrences.append(
                {
                    "snes_id": neighbor_id,
                    "event_id": source[neighbor_id]["event_id"],
                    "snes_distance": snes_distance,
                    "android_ids": list(record["android_ids"]),
                    "android_min": min(android_positions),
                    "android_max": max(android_positions),
                }
            )
    occurrences.sort(key=lambda item: item["snes_distance"])
    neighbors = occurrences[:12]
    if not neighbors:
        return None

    scores: list[tuple[float, float, list[int]]] = []
    for group in android_groups:
        positions = [index.anchor_pos[text_id] for text_id in group if text_id in index.anchor_pos]
        if not positions:
            continue
        candidate_min = min(positions)
        candidate_max = max(positions)
        candidate_center = (candidate_min + candidate_max) / 2.0
        score = 0.0
        weighted_distance = 0.0
        total_weight = 0.0
        for neighbor in neighbors:
            if neighbor["android_min"] <= candidate_center <= neighbor["android_max"]:
                android_distance = 0.0
            else:
                android_distance = min(
                    abs(candidate_center - neighbor["android_min"]),
                    abs(candidate_center - neighbor["android_max"]),
                )
            weight = 1.0 / (1.0 + neighbor["snes_distance"] / 64.0)
            if neighbor["event_id"] in target_events:
                # Same-event dialogue structure outranks the looser physical-ROM
                # cloud. This preserves proven prompt/choice and scene runs.
                weight *= 6.0
            score += weight * math.exp(-android_distance / 12.0)
            weighted_distance += weight * android_distance
            total_weight += weight
        mean_distance = weighted_distance / total_weight if total_weight else float("inf")
        scores.append((score, -mean_distance, list(group)))
    if not scores:
        return None
    scores.sort(key=lambda item: (item[0], item[1], -min(item[2])), reverse=True)
    best_score, best_negative_distance, best_group = scores[0]
    runner_score = scores[1][0] if len(scores) > 1 else 0.0
    return {
        "android_ids": best_group,
        "candidate_android_groups": [list(group) for group in android_groups],
        "score": round(best_score, 6),
        "runner_up_score": round(runner_score, 6),
        "mean_android_anchor_distance": round(-best_negative_distance, 3),
        "neighbor_count": len(neighbors),
        "neighbors": neighbors,
    }


def _auto_add_equivalent_duplicate_positional_tiebreak(
    records: list[dict],
    source: dict[str, dict],
    index: _AutoCandidateIndex,
    english: dict[int, str],
    french: dict[int, str],
) -> tuple[list[dict], dict]:
    """Resolve strict EN+FR-equivalent duplicates without cascading evidence.

    Two separate operations are intentionally performed from the same frozen
    context. First, a strong fuzzy identity may ignore repeated copies of the
    *same raw Android EN+FR payload* when measuring its margin against the next
    genuinely different candidate. Second, mappings whose translation was
    already accepted through equivalent alternative groups receive one concrete
    Android provenance chosen by the neighboring dialogue block.

    Chosen equivalent occurrences are never fed back into any other alignment
    rule in this pass. Android French establishes equivalence only after Android
    English has identified the candidate payload; it never proves identity.
    """
    frozen_context = [record for record in records if record.get("android_ids")]

    payload_groups: dict[tuple[str, tuple[str, ...]], list[int]] = {}
    for android_id in index.anchor_ids:
        french_unit = _auto_french_unit(android_id, english, french)
        if not french_unit:
            continue
        payload_groups.setdefault((english[android_id], french_unit), []).append(android_id)

    def ranked_payloads(source_display: str) -> list[dict]:
        ranked = index.rank(source_display, limit=100)
        result: list[dict] = []
        seen: set[tuple[str, tuple[str, ...]]] = set()
        for candidate in ranked:
            android_id = candidate["android_id"]
            key = (english[android_id], _auto_french_unit(android_id, english, french))
            if not key[1] or key in seen:
                continue
            seen.add(key)
            result.append(
                {
                    "android_ids": list(payload_groups.get(key, [android_id])),
                    "metrics": candidate,
                }
            )
        return result

    def qualified_payload(source_display: str) -> dict | None:
        normalized = normalize_alignment_text(source_display)
        if len(normalized) < 24:
            return None
        ranked = ranked_payloads(source_display)
        if len(ranked) < 2 or len(ranked[0]["android_ids"]) < 2:
            return None
        top = ranked[0]
        second = ranked[1]
        metrics = top["metrics"]
        margin = metrics["lexical_score"] - second["metrics"]["lexical_score"]
        if (
            metrics["lexical_score"] < 90
            or metrics["source_token_coverage"] < 80
            or metrics["character_similarity"] < 90
            or margin < 20
        ):
            return None
        return {
            "android_ids": top["android_ids"],
            "metrics": metrics,
            "candidate_margin": round(margin, 1),
        }

    # Calibrate semantic recognition against the complete already-accepted
    # one-carrier corpus, including mappings that intentionally stored several
    # equivalent Android alternatives. Round 35 yields 35/35 reproductions.
    calibration_attempts = 0
    calibration_matches = 0
    calibration_conflicts: list[str] = []
    for record in records:
        if len(record.get("snes_ids", [])) != 1:
            continue
        snes_id = record["snes_ids"][0]
        accepted_ids = set(record.get("android_ids", []))
        for group in record.get("android_alternative_anchor_groups", []):
            accepted_ids.update(group)
        if not accepted_ids or snes_id not in source:
            continue
        qualified = qualified_payload(source[snes_id]["source"])
        if qualified is None:
            continue
        calibration_attempts += 1
        if accepted_ids.intersection(qualified["android_ids"]):
            calibration_matches += 1
        else:
            calibration_conflicts.append(snes_id)
    if calibration_conflicts:
        raise ValueError(
            "Equivalent-duplicate semantic grouping contradicts accepted mappings: "
            + ", ".join(calibration_conflicts[:10])
        )
    if calibration_attempts != 35 or calibration_matches != 35:
        raise ValueError(
            "Equivalent-duplicate semantic calibration corpus changed unexpectedly: "
            f"expected 35/35, found {calibration_matches}/{calibration_attempts}"
        )

    owner = {snes_id for record in records for snes_id in record.get("snes_ids", [])}
    additions: list[dict] = []
    for snes_id, entry in source.items():
        if snes_id in owner or snes_id in DIALOGUE_FORCED_UNMAPPED:
            continue
        if not _auto_semantic(entry["source"]):
            continue
        qualified = qualified_payload(entry["source"])
        if qualified is None:
            continue
        android_groups = [[android_id] for android_id in qualified["android_ids"]]
        prediction = _auto_equivalent_group_position_prediction(
            [snes_id], android_groups, frozen_context, source, index
        )
        if prediction is None:
            continue
        android_ids = prediction["android_ids"]
        record = {
            "event_id": entry["event_id"],
            "snes_ids": [snes_id],
            "android_ids": android_ids,
            "confidence": "very_high_equivalent_duplicate_positional_tiebreak",
            "provenance": "automatic_equivalent_duplicate_positional_tiebreak",
            "relation": "equivalent_duplicate_resolved_by_positional_tiebreak",
            "source_display": entry["source"],
            "lexical_evidence": {
                key: qualified["metrics"][key]
                for key in ("character_similarity", "source_token_coverage", "lexical_score")
            },
            "candidate_margin": qualified["candidate_margin"],
            "equivalent_android_ids": list(qualified["android_ids"]),
            "positional_tiebreak_evidence": prediction,
        }
        records.append(record)
        additions.append(record)
        owner.add(snes_id)

    # Resolve old translation-equivalent alternatives to one concrete origin.
    # Use only the pre-rule concrete context above: neither the new additions nor
    # another resolved alternative can influence the next choice.
    resolved_records = 0
    resolved_source_ids = 0
    for record in records:
        alternatives = record.get("android_alternative_anchor_groups")
        if not alternatives:
            continue
        payloads = [
            _auto_android_group_raw_payload(group, english, french)
            for group in alternatives
        ]
        if not payloads or len(set(payloads)) != 1 or not payloads[0][1]:
            continue
        prediction = _auto_equivalent_group_position_prediction(
            record.get("snes_ids", []), alternatives, frozen_context, source, index
        )
        if prediction is None:
            continue
        original_alternatives = [list(group) for group in alternatives]
        record["android_ids"] = list(prediction["android_ids"])
        record["android_equivalent_alternative_anchor_groups"] = original_alternatives
        record["provenance_resolution"] = "equivalent_duplicate_positional_tiebreak"
        record["positional_tiebreak_evidence"] = prediction
        del record["android_alternative_anchor_groups"]
        resolved_records += 1
        resolved_source_ids += len(record.get("snes_ids", []))

    return additions, {
        "semantic_group_calibration_attempts": calibration_attempts,
        "semantic_group_calibration_reproductions": calibration_matches,
        "conflicts": 0,
        "new_mapping_count": len(additions),
        "resolved_alternative_record_count": resolved_records,
        "resolved_alternative_source_id_count": resolved_source_ids,
        "non_cascading": True,
    }


def _auto_add_isolated_event_rom_neighborhood_fuzzy(
    source_document: dict,
    records: list[dict],
    source: dict[str, dict],
    index: _AutoCandidateIndex,
    english: dict[int, str],
    french: dict[int, str],
) -> tuple[list[dict], dict]:
    """Resolve one-carrier events from strong lexical + frozen ROM-neighborhood evidence.

    This Round-37 rule deliberately targets only events containing exactly one
    semantic SNES carrier.  The best distinct Android-English payload must be
    substantially better than the runner-up and must also sit inside the
    Android cluster independently suggested by already accepted nearby ROM
    carriers.  Translation-equivalent duplicate provenances accepted in Round
    36 are allowed as prior-pass anchors, but additions made by this rule are
    evaluated from one frozen context and therefore cannot cascade.

    Exact Android-English duplicates whose complete French localization differs
    remain outside this rule.  Android FR is never used to establish identity.
    """
    frozen_context = [record for record in records if record.get("android_ids")]
    owner = {snes_id for record in records for snes_id in record.get("snes_ids", [])}
    android_owned = {
        android_id
        for record in records
        for android_id in record.get("android_ids", [])
    }
    semantic_by_event: dict[str, list[str]] = {}
    for event in source_document.get("events", []):
        semantic_by_event[event["event_id"]] = [
            token["id"]
            for token in event.get("tokens", [])
            if token.get("type") == "text" and _auto_semantic(token.get("source", ""))
        ]

    def ranked_distinct(source_display: str) -> list[dict]:
        result: list[dict] = []
        seen: set[str] = set()
        for candidate in index.rank(source_display, limit=100):
            key = normalize_alignment_text(english[candidate["android_id"]])
            if key in seen:
                continue
            seen.add(key)
            result.append(candidate)
        return result

    def evaluate(snes_id: str) -> dict | None:
        source_display = source[snes_id]["source"]
        if len(normalize_alignment_text(source_display)) < 20:
            return None
        ranked = ranked_distinct(source_display)
        if len(ranked) < 2:
            return None
        top, second = ranked[0], ranked[1]
        android_id = top["android_id"]

        # Preserve the stronger duplicate policy: if the SNES carrier itself is
        # an exact duplicate whose Android copies localize differently, this
        # fuzzy/positional rule is not allowed to choose between them.
        exact_ids = index.exact.get(normalize_alignment_text(source_display), [])
        if len(exact_ids) > 1:
            french_units = {_auto_french_unit(text_id, english, french) for text_id in exact_ids}
            if len(french_units) > 1:
                return None

        positional = _auto_equivalent_group_position_prediction(
            [snes_id], [[android_id]], frozen_context, source, index
        )
        if positional is None or positional["neighbor_count"] < 4:
            return None
        margin = top["lexical_score"] - second["lexical_score"]
        standard = (
            top["lexical_score"] >= 75
            and top["source_token_coverage"] >= 70
            and top["character_similarity"] >= 70
            and margin >= 20
            and positional["score"] >= 0.25
            and positional["mean_android_anchor_distance"] <= 160
        )
        close_paraphrase = (
            top["lexical_score"] >= 80
            and top["source_token_coverage"] >= 65
            and top["character_similarity"] >= 85
            and margin >= 20
            and positional["score"] >= 0.5
            and positional["mean_android_anchor_distance"] <= 80
        )
        if not (standard or close_paraphrase):
            return None
        return {
            "android_id": android_id,
            "metrics": top,
            "candidate_margin": round(margin, 1),
            "positional_evidence": positional,
            "threshold_branch": "standard" if standard else "close_paraphrase",
        }

    # Calibrate only against already accepted one-carrier events of the same
    # structural class. Round 43's orb-family context removed C9:D239/C9:D31C
    # from positional eligibility. Round 44's new local-sequence/inn anchors remove one additional historical
    # probe from eligibility. Round 45's Kakkara scene anchor restores enough
    # local context for C9:1984 to re-enter the historical probe set; it still
    # reproduces its accepted mapping, so the calibrated corpus is 188/188.
    calibration_attempts = 0
    calibration_matches = 0
    calibration_conflicts: list[str] = []
    for record in frozen_context:
        if len(record.get("snes_ids", [])) != 1:
            continue
        snes_id = record["snes_ids"][0]
        if snes_id not in source:
            continue
        event_id = source[snes_id]["event_id"]
        if len(semantic_by_event.get(event_id, [])) != 1:
            continue
        candidate = evaluate(snes_id)
        if candidate is None:
            continue
        calibration_attempts += 1
        predicted = normalize_alignment_text(english[candidate["android_id"]])
        accepted = {
            normalize_alignment_text(english[android_id])
            for android_id in record.get("android_ids", [])
            if android_id in english
        }
        if predicted in accepted:
            calibration_matches += 1
        else:
            calibration_conflicts.append(snes_id)
    if calibration_conflicts:
        raise ValueError(
            "Isolated-event ROM-neighborhood fuzzy alignment contradicts accepted mappings: "
            + ", ".join(calibration_conflicts[:10])
        )
    if calibration_attempts != 188 or calibration_matches != 188:
        raise ValueError(
            "Isolated-event ROM-neighborhood fuzzy calibration corpus changed unexpectedly: "
            f"expected 188/188, found {calibration_matches}/{calibration_attempts}"
        )

    additions: list[dict] = []
    for event_id, semantic_ids in semantic_by_event.items():
        if len(semantic_ids) != 1:
            continue
        snes_id = semantic_ids[0]
        if snes_id in owner or snes_id in DIALOGUE_FORCED_UNMAPPED:
            continue
        candidate = evaluate(snes_id)
        if candidate is None:
            continue
        android_id = candidate["android_id"]
        # A free Android anchor is required here. Re-use across unrelated SNES
        # carriers needs explicit structural review rather than a generic fuzzy rule.
        if android_id in android_owned or not _auto_french_unit(android_id, english, french):
            continue
        record = {
            "event_id": event_id,
            "snes_ids": [snes_id],
            "android_ids": [android_id],
            "confidence": "very_high_isolated_rom_neighborhood_fuzzy",
            "provenance": "automatic_isolated_rom_neighborhood_fuzzy",
            "relation": "isolated_single_carrier_resolved_by_lexical_and_rom_neighborhood",
            "source_display": source[snes_id]["source"],
            "lexical_evidence": {
                key: candidate["metrics"][key]
                for key in ("character_similarity", "source_token_coverage", "lexical_score")
            },
            "candidate_margin": candidate["candidate_margin"],
            "threshold_branch": candidate["threshold_branch"],
            "rom_neighborhood_evidence": candidate["positional_evidence"],
        }
        additions.append(record)
        owner.add(snes_id)
        android_owned.add(android_id)

    records.extend(additions)
    return additions, {
        "accepted_mapping_attempts": calibration_attempts,
        "accepted_mapping_reproductions": calibration_matches,
        "conflicts": 0,
        "new_mapping_count": len(additions),
        "non_cascading": True,
    }


def _auto_add_isolated_event_local_extension(
    source_document: dict,
    records: list[dict],
    source: dict[str, dict],
    index: _AutoCandidateIndex,
    english: dict[int, str],
    french: dict[int, str],
) -> tuple[list[dict], dict]:
    """Resolve a unique longer Android line from exceptionally tight local context.

    This Round-38 rule is intentionally narrower than ordinary fuzzy matching.
    It targets one-semantic-carrier events where Android English expands the SNES
    line, but the candidate has very high source-token coverage and lies almost
    exactly inside a dense block of already accepted neighboring dialogue.  The
    Android-English payload must be globally unique; divergent duplicate copies
    are therefore outside this rule by construction.

    Round-37 mappings are accepted prior-pass context for this rule. Additions
    made here are still evaluated from one frozen context and cannot cascade.
    Android French never participates in semantic candidate selection.
    """
    frozen_context = [record for record in records if record.get("android_ids")]
    owner = {snes_id for record in records for snes_id in record.get("snes_ids", [])}
    android_owned = {
        android_id for record in records for android_id in record.get("android_ids", [])
    }
    semantic_by_event: dict[str, list[str]] = {}
    for event in source_document.get("events", []):
        semantic_by_event[event["event_id"]] = [
            token["id"]
            for token in event.get("tokens", [])
            if token.get("type") == "text" and _auto_semantic(token.get("source", ""))
        ]

    def ranked_distinct(source_display: str) -> list[dict]:
        result: list[dict] = []
        seen: set[str] = set()
        for candidate in index.rank(source_display, limit=100):
            key = normalize_alignment_text(english[candidate["android_id"]])
            if key in seen:
                continue
            seen.add(key)
            result.append(candidate)
        return result

    def evaluate(snes_id: str) -> dict | None:
        source_display = source[snes_id]["source"]
        source_norm = normalize_alignment_text(source_display)
        source_words = source_norm.split()
        if len(source_norm) < 25 or len(source_words) < 6:
            return None
        ranked = ranked_distinct(source_display)
        if len(ranked) < 2:
            return None
        top, second = ranked[0], ranked[1]
        android_id = top["android_id"]
        android_norm = normalize_alignment_text(english[android_id])
        # The semantic Android-English line must itself be unique. This keeps
        # duplicate-provenance/relocalization decisions in their dedicated rules.
        if len(index.exact.get(android_norm, [])) != 1:
            return None
        if len(android_norm.split()) <= len(source_words):
            return None
        positional = _auto_equivalent_group_position_prediction(
            [snes_id], [[android_id]], frozen_context, source, index
        )
        if positional is None:
            return None
        margin = top["lexical_score"] - second["lexical_score"]
        if not (
            top["lexical_score"] >= 65
            and top["source_token_coverage"] >= 85
            and margin >= 8
            and positional["score"] >= 1.5
            and positional["mean_android_anchor_distance"] <= 40
            and positional["neighbor_count"] >= 8
        ):
            return None
        return {
            "android_id": android_id,
            "metrics": top,
            "candidate_margin": round(margin, 1),
            "positional_evidence": positional,
        }

    calibration_attempts = 0
    calibration_matches = 0
    calibration_conflicts: list[str] = []
    for record in frozen_context:
        if len(record.get("snes_ids", [])) != 1:
            continue
        snes_id = record["snes_ids"][0]
        if snes_id not in source:
            continue
        event_id = source[snes_id]["event_id"]
        if len(semantic_by_event.get(event_id, [])) != 1:
            continue
        candidate = evaluate(snes_id)
        if candidate is None:
            continue
        calibration_attempts += 1
        predicted = normalize_alignment_text(english[candidate["android_id"]])
        accepted = {
            normalize_alignment_text(english[android_id])
            for android_id in record.get("android_ids", [])
            if android_id in english
        }
        if predicted in accepted:
            calibration_matches += 1
        else:
            calibration_conflicts.append(snes_id)
    if calibration_conflicts:
        raise ValueError(
            "Isolated-event local-extension alignment contradicts accepted mappings: "
            + ", ".join(calibration_conflicts[:10])
        )
    if calibration_attempts != 5 or calibration_matches != 5:
        raise ValueError(
            "Isolated-event local-extension calibration corpus changed unexpectedly: "
            f"expected 5/5, found {calibration_matches}/{calibration_attempts}"
        )

    additions: list[dict] = []
    for event_id, semantic_ids in semantic_by_event.items():
        if len(semantic_ids) != 1:
            continue
        snes_id = semantic_ids[0]
        if snes_id in owner or snes_id in DIALOGUE_FORCED_UNMAPPED:
            continue
        candidate = evaluate(snes_id)
        if candidate is None:
            continue
        android_id = candidate["android_id"]
        if android_id in android_owned or not _auto_french_unit(android_id, english, french):
            continue
        record = {
            "event_id": event_id,
            "snes_ids": [snes_id],
            "android_ids": [android_id],
            "confidence": "very_high_isolated_local_extension",
            "provenance": "automatic_isolated_local_extension",
            "relation": "isolated_android_extension_resolved_by_dense_local_context",
            "source_display": source[snes_id]["source"],
            "lexical_evidence": {
                key: candidate["metrics"][key]
                for key in ("character_similarity", "source_token_coverage", "lexical_score")
            },
            "candidate_margin": candidate["candidate_margin"],
            "rom_neighborhood_evidence": candidate["positional_evidence"],
        }
        additions.append(record)
        owner.add(snes_id)
        android_owned.add(android_id)

    records.extend(additions)
    return additions, {
        "accepted_mapping_attempts": calibration_attempts,
        "accepted_mapping_reproductions": calibration_matches,
        "conflicts": 0,
        "new_mapping_count": len(additions),
        "non_cascading": True,
        "uses_round37_as_prior_pass_context": True,
    }

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
    if snes_id in DIALOGUE_VALIDATED_ANDROID_OMISSIONS:
        return {
            "reason": "validated_android_omission",
            "note": DIALOGUE_VALIDATED_ANDROID_OMISSIONS[snes_id],
            "top_candidates": index.rank(source_text, limit=3),
        }
    if snes_id in DIALOGUE_VALIDATED_CONTEXTUAL_TEMPLATES:
        return {
            "reason": "validated_contextual_template",
            "note": DIALOGUE_VALIDATED_CONTEXTUAL_TEMPLATES[snes_id],
            "top_candidates": index.rank(source_text, limit=3),
        }
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
    system_english = read_scrtxt(DEFAULT_SYSTXT_EN)
    system_french = read_scrtxt(DEFAULT_SYSTXT_FR)
    require_parallel_scrtxt(system_english, system_french)
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
        for snes_id in overlap:
            reviewed_record = reviewed_by_id[snes_id]
            if reviewed_record.get("android_namespace", "scrtxt") != "scrtxt":
                # Generic automatic matching intentionally indexes scrtxt only;
                # a reviewed systxt ownership is outside this calibration domain.
                continue
            calibration_attempts += 1
            expected = set(reviewed_record["android_ids"])
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
    _auto_add_exact_segmentation_equivalences(sessions, records, index, english, french)

    # Exact segmentation can establish a new local anchor in sessions that had
    # no usable single-fragment seed. Re-run the existing conservative context
    # expansion once; thresholds and ordering rules are unchanged.
    _auto_same_session_context_expand(sessions, records, index, english)
    _auto_event_context_expand(sessions, records, index, english)
    _auto_add_contextual_exact_duplicates(document, sessions, records, index, english, french)
    _auto_add_raw_contextual_exact_duplicates(document, records, index, english, french)
    _auto_add_short_exact_punctuation_bracket(document, sessions, records, index, english, french)
    _auto_add_tight_single_gap_context(document, records, index, english, french)
    _auto_add_isolated_high_coverage_global(document, records, index, english, french)
    _auto_add_isolated_contained_extension(document, records, index, english, french)
    _auto_add_short_unique_immediate_neighbor(sessions, records, index, english, french)
    # New high-leverage rules run last so they can fill only genuinely free
    # identities and never replace a mapping already accepted by older passes.
    _auto_add_placeholder_index_equivalent_duplicates(
        sessions, records, index, english, french
    )
    _auto_add_raw_unique_exact_player_context_neighbor(
        sessions, records, index, english, french
    )
    _rom_neighborhood_additions, rom_neighborhood_calibration = (
        _auto_add_rom_neighborhood_exact_duplicates(
            records, source, index, english, french
        )
    )
    _equivalent_tiebreak_additions, equivalent_tiebreak_calibration = (
        _auto_add_equivalent_duplicate_positional_tiebreak(
            records, source, index, english, french
        )
    )
    _isolated_rom_fuzzy_additions, isolated_rom_fuzzy_calibration = (
        _auto_add_isolated_event_rom_neighborhood_fuzzy(
            document, records, source, index, english, french
        )
    )
    _isolated_local_extension_additions, isolated_local_extension_calibration = (
        _auto_add_isolated_event_local_extension(
            document, records, source, index, english, french
        )
    )

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
            record = _auto_enrich_record(
                record, english, french,
                system_english=system_english, system_french=system_french,
            )
        enriched_records.append(record)
    enriched_records.sort(key=lambda record: min(source_order[snes_id] for snes_id in record["snes_ids"]))
    dropped_trailing_french_only_player_turns = _auto_drop_trailing_french_only_player_turns(
        enriched_records, english, french
    )
    french_slot_reattributions = _auto_reattribute_forward_player_french_slots(
        enriched_records, english, french
    )

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
        "android_system_english": {
            "path": "sources/android/systxt_en.bin",
            "sha256": sha256(DEFAULT_SYSTXT_EN),
        },
        "android_system_french": {
            "path": "sources/android/systxt_fr.bin",
            "sha256": sha256(DEFAULT_SYSTXT_FR),
        },
        "policy": {
            "english_identity_is_primary": True,
            "automatic_translation_generation": False,
            "accepted_automatic_confidence": "very_high only",
            "notes": [
                "Alignment operates on TEXT_OPEN/TEXT_CLOSE-local dialogue sessions rather than assuming whole-event Android monotonicity.",
                "Dynamic PLAYER_NAME commands are normalized to Android %S(index,0) placeholders for comparison only.",
                "French is recovered through complete English-anchor localization intervals after English identity is established.",
                "Strictly identical Android EN+FR duplicate payloads may use neighboring dialogue blocks as a non-cascading provenance tie-breaker; the original equivalent alternatives remain traceable in metadata.",
                "Unmatched or ambiguous SNES prose is retained as unmapped and is never forced onto the nearest candidate.",
                "SNES wrapping/page/layout formatting is a separate later step; Android French prose is not written to translations/dialogues_french.json here.",
            ],
        },
        "calibration": {
            "reviewed_source_id_count": len(reviewed_ids) + len(DIALOGUE_VALIDATED_ALTERNATIVE_GROUPS),
            "automatic_attempts_on_reviewed_ids": calibration_attempts,
            "automatic_matches_on_reviewed_ids": calibration_matches,
            "automatic_conflicts": 0,
            "rom_neighborhood_exact_duplicates": rom_neighborhood_calibration,
            "equivalent_duplicate_positional_tiebreak": equivalent_tiebreak_calibration,
            "isolated_event_rom_neighborhood_fuzzy": isolated_rom_fuzzy_calibration,
            "isolated_event_local_extension": isolated_local_extension_calibration,
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
        "dropped_trailing_french_only_player_turns": dropped_trailing_french_only_player_turns,
        "french_slot_reattributions": french_slot_reattributions,
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
            "round48_android_only_vocative_policy": "exact reviewed allow-list only: when Android EN and the canonical SNES carrier contain no PLAYER_NAME but Android FR adds a pure addressee vocative, remove only that exact Android-FR-only placeholder phrase; identity and all SNES commands remain unchanged",
            "round48_0127_pagination_policy": "exact source/token-gated event repair: two sentence-boundary WAIT $00 + TEXT_CLEAR page transitions plus one TEXT_CLEAR-only after the existing WAIT $08; no actor action, timed WAIT or PLAYER_NAME command moves",
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

def _repair_unique_post_wait_sentence_newline(
    *,
    base_rom: bytes,
    event: dict,
    translations: dict[str, str],
    font,
    simulation,
) -> tuple[dict[str, str], object, list[dict]]:
    """Insert one proven post-WAIT newline for a localized sentence boundary.

    This fallback is intentionally narrower than the reviewed per-event table.
    It runs only after compact formatting when the sole blocking defect is one
    decoded-capacity wrap.  The canonical event must contain an immediate
    ``text -> WAIT $00 -> text`` boundary where both English and localized text
    end/start complete sentence prose, the stock continuation begins with a
    space (there is no stock newline), and exactly one possible leading NEWLINE
    makes the entire event simulator-clean.  WAIT itself is never changed.
    """
    from shared.dialogue_simulator import simulate_event

    blocking = [
        issue for issue in simulation.issues
        if issue.severity in {"error", "warning"}
    ]
    if {issue.code for issue in blocking} != {"IMPLICIT_RUNTIME_WRAP"}:
        return translations, simulation, []
    if not any(issue.code == "WAIT_SAME_LINE_CONTINUATION" for issue in simulation.issues):
        return translations, simulation, []

    tokens = event.get("tokens", [])
    clean_candidates: list[tuple[dict[str, str], object, dict]] = []
    sentence_end = re.compile(r"[.!?…][\"'”’)]*$")
    sentence_start = re.compile(r"[A-ZÀ-ÖØ-ÞŒ]")
    for index in range(1, len(tokens) - 1):
        wait = tokens[index]
        if wait.get("type") != "command" or wait.get("name") != "WAIT" or wait.get("args") != "00":
            continue
        previous = tokens[index - 1]
        following = tokens[index + 1]
        if previous.get("type") != "text" or following.get("type") != "text":
            continue
        previous_id = previous.get("id")
        following_id = following.get("id")
        if previous_id not in translations or following_id not in translations:
            continue
        source_before = previous.get("source", "").rstrip()
        source_after = following.get("source", "")
        if not sentence_end.search(source_before):
            continue
        if not source_after.startswith(" ") or source_after.startswith(("\n", "\v", "\f")):
            continue

        localized_before = translations[previous_id].rstrip(" \n\v\f")
        localized_after = translations[following_id]
        if not sentence_end.search(localized_before):
            continue
        if localized_after.startswith(("\n", "\v", "\f")):
            continue
        visible_after = localized_after.lstrip()
        if not visible_after or sentence_start.match(visible_after) is None:
            continue

        candidate = dict(translations)
        candidate[following_id] = "\n" + localized_after
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
        clean_candidates.append((
            candidate,
            candidate_simulation,
            {
                "layout_text_id": following_id,
                "previous_text_id": previous_id,
                "strategy": "unique_simulator_clean_sentence_newline_after_wait00",
                "validation_status": "to_review",
                "reason": "localized complete sentences need one explicit line boundary because WAIT does not advance the cursor",
            },
        ))

    if len(clean_candidates) != 1:
        return translations, simulation, []
    candidate, candidate_simulation, repair = clean_candidates[0]
    return candidate, candidate_simulation, [repair]


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
        # event-interruption family already proven for `vwf_dialogues`: actor
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


def _format_mapping_across_sound_effect_action_boundary(
    source_document: dict,
    mapping: dict,
    advances: dict[str, int],
    *,
    base_rom: bytes,
    prefer_semantic_line_breaks: bool,
) -> tuple[dict[str, str], dict]:
    """Split one localized unit across an existing sound/effect action bridge.

    The accepted shape is intentionally tiny: two semantic text carriers with
    exactly ``OP_20..OP_27`` -> ``OP_2D`` -> ``COMPLETE_ACTIONS`` between them.
    The call must independently decode as sound-only + RETURN + END.  Android EN
    and the SNES mapping must contain no dynamic name; Android FR may add exactly
    one comma-delimited ``%S(n,0),`` vocative.  That Android-only vocative is
    dropped because the SNES has no PLAYER_NAME command to carry it.  The
    remaining French is split only at a complete sentence boundary, while every
    stock event command remains byte-for-byte in place.
    """
    snes_ids = mapping.get("snes_ids", [])
    if len(snes_ids) != 2:
        raise ValueError("Sound/effect action boundary requires exactly two SNES text IDs")
    if len(mapping.get("android_ids", [])) != 1:
        raise ValueError("Sound/effect action boundary requires one Android localization unit")
    if "%S(" in mapping.get("source_display", "") or "%S(" in mapping.get("android_english_display", ""):
        raise ValueError("Sound/effect action boundary requires no SNES/Android-EN PLAYER_NAME")

    by_id, by_event = event_text_index(source_document)
    first = by_id.get(snes_ids[0])
    second = by_id.get(snes_ids[1])
    if first is None or second is None or first["event_id"] != second["event_id"]:
        raise ValueError("Sound/effect action boundary references invalid SNES carriers")
    if first["token_index"] >= second["token_index"]:
        raise ValueError("Sound/effect action boundary IDs are not in token order")
    event = by_event[first["event_id"]]
    bridge = event["tokens"][first["token_index"] + 1:second["token_index"]]
    if len(bridge) != 3 or any(token.get("type") != "command" for token in bridge):
        raise ValueError("Sound/effect action boundary requires exactly three bridge commands")
    call, effect, complete = bridge
    if not _is_safe_sound_only_returning_call(base_rom, call):
        raise ValueError("Sound/effect action boundary call is not proven sound-only returning")
    if effect.get("name") != "OP_2D" or len(effect.get("args", "").split()) != 1:
        raise ValueError("Sound/effect action boundary requires one stock OP_2D effect byte")
    if complete.get("name") != "COMPLETE_ACTIONS":
        raise ValueError("Sound/effect action boundary requires COMPLETE_ACTIONS")

    first_source = re.sub(r"\s+", " ", first["source"].strip())
    if not re.search(r"(?:\.{3}|[.!?…])[”\"»')\]]*$", first_source):
        raise ValueError("Sound/effect action boundary requires a complete source sentence before the bridge")

    french = normalize_android_french(mapping.get("french_display", ""))
    vocatives = list(re.finditer(r"%S\((\d+),0\)\s*,\s*", french))
    if len(vocatives) != 1:
        raise ValueError("Sound/effect action boundary requires exactly one Android-only comma vocative")
    vocative = vocatives[0]
    before = french[:vocative.start()].rstrip()
    after = french[vocative.end():].lstrip()
    if not before or not after:
        raise ValueError("Sound/effect action boundary vocative must be internal to localized prose")
    # Once a sentence-initial vocative is removed, capitalize the first cased
    # character of the following clause mechanically; no wording is rewritten.
    if before[-1] in ".!?:…":
        chars = list(after)
        for index, char in enumerate(chars):
            if char.isalpha():
                chars[index] = char.upper()
                break
        after = "".join(chars)
    french_without_vocative = f"{before} {after}".strip()
    if "%S(" in french_without_vocative:
        raise ValueError("Sound/effect action boundary leaves an unsupported PLAYER_NAME")

    boundaries = _sentence_boundary_positions(french_without_vocative)
    candidates = []
    for boundary in boundaries:
        pieces = [
            french_without_vocative[:boundary].strip(),
            french_without_vocative[boundary:].strip(),
        ]
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
            if set(values) & set(translations):
                valid = False
                break
            translations.update(values)
            reports.append(report)
        if not valid:
            continue
        line_counts = [sum(report.get("page_line_counts", [])) for report in reports]
        page_breaks = sum(report.get("inserted_page_break_count", 0) for report in reports)
        score = (page_breaks, max(line_counts, default=0), abs(line_counts[0] - line_counts[1]), boundary)
        candidates.append((score, pieces, translations, reports))

    if not candidates:
        raise ValueError("Sound/effect action boundary found no clean sentence distribution")
    _, pieces, translations, reports = min(candidates, key=lambda item: item[0])
    inserted_boundary_newline = False
    # These event-side effect/action commands do not advance the dialogue
    # cursor.  If the two localized pieces would therefore exceed the same-line
    # parser/pixel budget when concatenated, materialize one explicit newline
    # after the proven complete first sentence.  This is the same conservative
    # presentation repair already accepted across OP_32/OP_34 action boundaries.
    combined = pieces[0] + pieces[1]
    if (
        len(combined) > DIALOGUE_WRAP_CHARS
        or _markup_width(combined, advances) > DIALOGUE_WRAP_PIXELS
    ):
        second_id = snes_ids[1]
        if translations[second_id].startswith(("\n", "\f", "\v")):
            raise ValueError("Sound/effect action boundary already begins with layout control")
        translations[second_id] = "\n" + translations[second_id]
        inserted_boundary_newline = True
        second_report = reports[1]
        second_report["formatted_markup"] = "\n" + second_report.get("formatted_markup", "")
        second_report["formatted_entries"] = [
            {
                "id": entry["id"],
                "text": translations.get(entry["id"], entry["text"]),
            }
            for entry in second_report.get("formatted_entries", [])
        ]
    report = {
        "event_id": mapping["event_id"],
        "snes_ids": snes_ids,
        "android_ids": mapping.get("android_ids", []),
        "confidence": mapping.get("confidence"),
        "source_display": mapping.get("source_display", ""),
        "android_french_raw": mapping.get("french_display", ""),
        "android_french_normalized": french,
        "sound_effect_action_sentence_distribution": True,
        "removed_android_only_vocative_player_index": int(vocative.group(1)),
        "inserted_action_boundary_line_break": inserted_boundary_newline,
        "preserved_bridge": [
            {"name": token.get("name"), "args": token.get("args")}
            for token in bridge
        ],
        "sound_call_proof": {"sound_only_returning": True},
        "distributed_french_parts": pieces,
        "sound_effect_action_parts": reports,
        "formatted_entries": [
            {"id": text_id, "text": translations[text_id]}
            for text_id in snes_ids
            if text_id in translations
        ],
    }
    return translations, report


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


def _strip_trailing_player_context_owned_by_reviewed_hole(
    event: dict,
    event_mappings: list[dict],
    *,
    missing_ids: set[str],
    unmapped_by_id: dict[str, dict],
) -> tuple[list[dict], list[dict]]:
    """Return a trailing PLAYER_NAME to the immediately following hole.

    Automatic alignment may borrow a following dynamic name as context for the
    preceding mapped carrier.  In a PARTIEL event, if that PLAYER_NAME belongs
    immediately to an explicitly reviewed unmapped carrier, it must remain with
    the stock-English hole instead of becoming part of the mapped French unit.
    No command or text carrier is moved: only the alignment-only suffix is
    removed from ``source_display`` before formatting.
    """
    token_index_by_id = {
        token["id"]: index
        for index, token in enumerate(event.get("tokens", []))
        if token.get("type") == "text"
    }
    tokens = event.get("tokens", [])
    result: list[dict] = []
    repairs: list[dict] = []
    reviewed_reasons = {"validated_no_equivalent", "validated_android_omission"}

    for original in event_mappings:
        mapping = dict(original)
        snes_ids = mapping.get("snes_ids", [])
        if not snes_ids:
            result.append(mapping)
            continue
        last_index = max(token_index_by_id[text_id] for text_id in snes_ids)
        if last_index + 2 >= len(tokens):
            result.append(mapping)
            continue
        player = tokens[last_index + 1]
        following = tokens[last_index + 2]
        if (
            player.get("type") != "command"
            or player.get("name") != "PLAYER_NAME"
            or following.get("type") != "text"
            or following.get("id") not in missing_ids
        ):
            result.append(mapping)
            continue
        hole = unmapped_by_id.get(following["id"], {})
        if hole.get("reason") not in reviewed_reasons:
            result.append(mapping)
            continue
        args = player.get("args", "00").split()
        if not args:
            result.append(mapping)
            continue
        placeholder = f"%S({int(args[0], 16)},0)"
        source_display = mapping.get("source_display", "")
        french_display = mapping.get("french_display", "")
        if not source_display.endswith(placeholder):
            result.append(mapping)
            continue
        if french_display.rstrip().endswith(placeholder):
            result.append(mapping)
            continue
        mapping["source_display"] = source_display[:-len(placeholder)]
        mapping["ignored_trailing_player_context_owned_by_reviewed_hole"] = placeholder
        repairs.append({
            "snes_ids": list(snes_ids),
            "hole_snes_id": following["id"],
            "player_context": placeholder,
            "hole_reason": hole.get("reason"),
        })
        result.append(mapping)
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
        raise ValueError("Choice destination list exceeds the 216px safe line target")
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
    """Redistribute one reviewed Android localization across stock WAIT $10.

    The accepted shape is exactly two semantic SNES text carriers separated by
    one untouched WAIT $10 and one Android-English identity.  French is split
    only at a complete-sentence boundary.  A leading canonical PLAYER_NAME may
    be preserved when the reviewed source/Android unit proves the same dynamic
    speaker.  Cursor movement stays SNES-authoritative: if the second stock
    carrier owns a leading newline, keep it there; otherwise materialize the
    already-established pre-WAIT newline used by $02AE.
    """
    if mapping.get("confidence") != "very_high_structural_review":
        raise ValueError("WAIT $10 resegmentation requires structural-review confidence")
    if mapping.get("relation") != "timed_wait10_resegmentation":
        raise ValueError("WAIT $10 resegmentation requires its explicit relation")
    snes_ids = mapping.get("snes_ids", [])
    android_ids = mapping.get("android_ids", [])
    if len(snes_ids) != 2 or len(android_ids) != 1:
        raise ValueError("WAIT $10 resegmentation requires exactly two SNES carriers and one Android anchor")

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
    if not french_full:
        raise ValueError("WAIT $10 resegmentation requires Android French prose")

    leading_player_index: int | None = None
    leading_player = re.match(r"^%S\((\d+),0\)", french_full)
    if leading_player is not None:
        leading_player_index = int(leading_player.group(1))
        source_display = normalize_android_french(mapping.get("source_display", "")).strip()
        if not source_display.startswith(f"%S({leading_player_index},0)"):
            raise ValueError("WAIT $10 resegmentation PLAYER_NAME differs between source and Android French")
        previous_index = first["token_index"] - 1
        if previous_index < 0:
            raise ValueError("WAIT $10 resegmentation requires canonical leading PLAYER_NAME")
        previous = event["tokens"][previous_index]
        if (
            previous.get("type") != "command"
            or previous.get("name") != "PLAYER_NAME"
            or previous.get("args") != f"{leading_player_index:02X}"
        ):
            raise ValueError("WAIT $10 resegmentation requires canonical leading PLAYER_NAME")
        french_full = french_full[leading_player.end():].lstrip()
    elif "%S(" in french_full:
        raise ValueError("WAIT $10 resegmentation supports only one proven leading PLAYER_NAME")

    boundaries = _sentence_boundary_positions(french_full)
    if not boundaries:
        raise ValueError("WAIT $10 resegmentation requires a complete-sentence split")

    second_owns_leading_newline = by_id[snes_ids[1]]["source"].startswith("\n")

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
                # WAIT does not move the live cursor. Require the first French
                # piece to fit one physical line.  $02AE owns the newline on
                # the pre-WAIT carrier; $042D owns it on the post-WAIT carrier.
                if "\n" in first_value or "\f" in first_value or "\v" in first_value:
                    valid = False
                    break
                values[text_id] = first_value if second_owns_leading_newline else first_value + "\n"
                report = dict(report)
                report["inserted_pre_wait_newline"] = not second_owns_leading_newline
                report["formatted_markup"] = values[text_id]
                report["formatted_entries"] = [{"id": text_id, "text": values[text_id]}]
            elif second_owns_leading_newline:
                second_value = values[text_id]
                # The generic single-carrier formatter promotes a canonical
                # leading newline here to TRANSLATION_CLEAR because it cannot
                # see the preceding timed WAIT.  In this reviewed two-carrier
                # shape that would invent a page clear.  Restore the exact
                # stock newline ownership instead.
                if second_value.startswith("\v"):
                    second_value = second_value[1:]
                else:
                    second_value = second_value.lstrip("\n")
                if "\f" in second_value or "\v" in second_value:
                    valid = False
                    break
                values[text_id] = "\n" + second_value
                report = dict(report)
                report["preserved_stock_post_wait_newline"] = True
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
        "preserved_leading_player_name_index": leading_player_index,
        "post_wait_stock_newline_preserved": second_owns_leading_newline,
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


def _format_mapping_across_single_text_x(
    source_document: dict,
    mapping: dict,
    advances: dict[str, int],
    *,
    french: dict[int, str],
    prefer_semantic_line_breaks: bool,
) -> tuple[dict[str, str], dict]:
    """Preserve one stock fresh-line TEXT_X between two semantic carriers.

    This narrow formatter applies only when one Android anchor has exactly one
    explicit localization line break and the canonical SNES source has exactly
    two text carriers separated solely by one TEXT_X.  The first stock carrier
    must already end in NEWLINE, proving that TEXT_X is a fresh-line layout
    command rather than a semantic boundary.  The Android line break therefore
    supplies the two localized pieces while the stock newline/TEXT_X ownership
    stays byte-for-byte unchanged.
    """
    snes_ids = mapping.get("snes_ids", [])
    android_ids = mapping.get("android_ids", [])
    if len(snes_ids) != 2 or len(android_ids) != 1:
        raise ValueError("single TEXT_X distribution requires two SNES carriers and one Android anchor")

    by_id, by_event = event_text_index(source_document)
    first = by_id.get(snes_ids[0])
    second = by_id.get(snes_ids[1])
    if first is None or second is None or first["event_id"] != second["event_id"]:
        raise ValueError("single TEXT_X distribution references invalid SNES carriers")
    if first["event_id"] != mapping.get("event_id"):
        raise ValueError("single TEXT_X distribution crosses events")
    event = by_event[first["event_id"]]
    bridge = event["tokens"][first["token_index"] + 1:second["token_index"]]
    if len(bridge) != 1:
        raise ValueError("single TEXT_X distribution requires exactly one bridge command")
    text_x = bridge[0]
    if text_x.get("type") != "command" or text_x.get("name") != "TEXT_X":
        raise ValueError("single TEXT_X distribution requires stock TEXT_X")
    if not by_id[snes_ids[0]]["source"].endswith("\n"):
        raise ValueError("single TEXT_X distribution requires a stock newline before TEXT_X")

    raw_french = french.get(android_ids[0], "")
    raw_lines = [line for line in raw_french.replace("\r\n", "\n").split("\n") if line.strip()]
    if len(raw_lines) != 2:
        raise ValueError("single TEXT_X distribution requires exactly two non-empty Android-French lines")
    pieces = [normalize_android_french(line).strip() for line in raw_lines]
    if any(not piece or "%S(" in piece for piece in pieces):
        raise ValueError("single TEXT_X distribution requires two plain localized text lines")

    common = {
        "allow_one_extra_page": True,
        "use_physical_page_capacity": True,
        "prefer_semantic_line_breaks": prefer_semantic_line_breaks,
        "allow_two_extra_pages": True,
    }
    translations: dict[str, str] = {}
    reports: list[dict] = []
    for index, (text_id, piece) in enumerate(zip(snes_ids, pieces, strict=True)):
        local = dict(mapping)
        local["snes_ids"] = [text_id]
        local["source_display"] = by_id[text_id]["source"]
        local["french_display"] = piece
        values, report = format_dialogue_mapping(source_document, local, advances, **common)
        value = values[text_id]
        if index == 0:
            stripped = value.rstrip("\n")
            if "\n" in stripped or "\f" in stripped or "\v" in stripped:
                raise ValueError("single TEXT_X distribution first localized line no longer fits one physical line")
            value = stripped + "\n"
            values[text_id] = value
            report = dict(report)
            report["preserved_pre_text_x_newline"] = True
            report["formatted_markup"] = value
            report["formatted_entries"] = [{"id": text_id, "text": value}]
        translations.update(values)
        reports.append(report)

    return translations, {
        "event_id": mapping["event_id"],
        "snes_ids": snes_ids,
        "android_ids": android_ids,
        "confidence": mapping.get("confidence"),
        "source_display": mapping.get("source_display", ""),
        "android_french_raw": raw_french,
        "structural_single_text_x_distribution": True,
        "preserved_bridge": [{"name": "TEXT_X", "args": text_x.get("args")}],
        "distributed_french_parts": pieces,
        "text_x_parts": reports,
        "formatted_entries": [
            {"id": text_id, "text": translations[text_id]} for text_id in snes_ids
        ],
    }

def _partial_layout_deferable_formatter_error(message: str) -> bool:
    """Return whether a proven mapping can safely remain stock in PARTIEL.

    This is intentionally narrower than a generic formatter fallback.  It only
    recognizes cases where serializing Android FR would require crossing a
    command boundary that the canonical binder refuses, would require a
    different PLAYER_NAME command stream, or needs literal text on the opposite
    side of a canonical PLAYER_NAME boundary. Leaving the whole mapped carrier
    untranslated preserves the exact stock SNES bytes and does not weaken the
    semantic mapping.
    """
    return (
        "defer structural binding" in message
        or message.startswith("French PLAYER_NAME sequence ")
        or message.startswith(
            "Localized literal text exists where the SNES stream has no text token around PLAYER_NAME"
        )
        or message == "Translated dialogue page break cannot be trailing"
    )


def _reviewed_partial_layout_defer(
    event_id: str, mapping: dict, message: str
) -> str | None:
    """Return review rationale for one exact PARTIEL layout deferral."""
    if not _partial_layout_deferable_formatter_error(message):
        return None
    key = tuple(mapping.get("snes_ids", []))
    return DIALOGUE_REVIEWED_PARTIAL_LAYOUT_DEFERRALS.get(event_id, {}).get(key)


def _collapse_trailing_page_break_into_stock_transition(
    source_document: dict,
    mapping: dict,
    values: dict[str, str],
    report: dict,
) -> tuple[dict[str, str], dict, list[dict]]:
    """Reuse an immediately following stock WAIT $00 + TEXT_CLEAR.

    A formatter may need a page break after the final word of a translated
    carrier. If the canonical SNES stream already supplies exactly WAIT $00
    followed by TEXT_CLEAR immediately after that carrier, serializing another
    generated ``\f`` would duplicate the transition. Remove only that trailing
    layout marker and let the unchanged stock commands own the page change.
    Printable payload and command order are untouched.
    """
    event = next(
        event for event in source_document["events"]
        if event["event_id"] == mapping["event_id"]
    )
    token_indexes = {
        token.get("id"): index
        for index, token in enumerate(event["tokens"])
        if token.get("type") in {"text", "ending_text"}
    }
    out = dict(values)
    repairs: list[dict] = []
    for text_id, value in list(out.items()):
        if not value.endswith("\f"):
            continue
        index = token_indexes.get(text_id)
        if index is None or index + 2 >= len(event["tokens"]):
            continue
        wait, clear = event["tokens"][index + 1:index + 3]
        if not (
            wait.get("type") == "command" and wait.get("name") == "WAIT"
            and wait.get("args") == "00"
            and clear.get("type") == "command" and clear.get("name") == "TEXT_CLEAR"
        ):
            continue
        out[text_id] = value[:-1]
        repairs.append({
            "strategy": "reuse_immediate_stock_wait00_text_clear",
            "text_id": text_id,
            "semantic_payload_changed": False,
            "stock_commands_preserved": True,
        })
    if not repairs:
        return values, report, []
    updated = dict(report)
    updated["formatted_entries"] = [
        {"id": text_id, "text": out[text_id]}
        for text_id in out
    ]
    updated["trailing_page_break_stock_transition_repairs"] = repairs
    return out, updated, repairs


def _mapping_has_unserializable_trailing_page_break(
    source_document: dict, mapping: dict, values: dict[str, str]
) -> bool:
    """Detect a generated trailing page break outside the two choice-safe shapes.

    ``dialogue_codec`` permits a trailing generated page break only immediately
    before CHOICE_BEGIN, or before TEXT_X + the stock decorative ``(`` carrier +
    CHOICE_BEGIN. Everywhere else it would require inventing/moving a structural
    command. A PARTIEL safe-subset may therefore keep the whole mapping stock.
    """
    trailing_ids = {text_id for text_id, value in values.items() if value.endswith("\f")}
    if not trailing_ids:
        return False
    event_id = mapping["event_id"]
    event = next(
        event for event in source_document["events"]
        if event["event_id"] == event_id
    )
    token_indexes = {
        token.get("id"): index
        for index, token in enumerate(event["tokens"])
        if token.get("type") == "text"
    }
    for text_id in trailing_ids:
        if (event_id, text_id) in TRANSLATION_TRAILING_PAGE_BREAK_ALLOWLIST:
            continue
        index = token_indexes.get(text_id)
        if index is None:
            return True
        tokens = event["tokens"]
        allowed = False
        if index + 1 < len(tokens):
            next_token = tokens[index + 1]
            allowed = (
                next_token.get("type") == "command"
                and next_token.get("name") == "CHOICE_BEGIN"
            )
        if not allowed and index + 3 < len(tokens):
            text_x, carrier, choice_begin = tokens[index + 1:index + 4]
            allowed = (
                text_x.get("type") == "command"
                and text_x.get("name") == "TEXT_X"
                and carrier.get("type") in {"text", "ending_text"}
                and carrier.get("source", "").strip() == "("
                and choice_begin.get("type") == "command"
                and choice_begin.get("name") == "CHOICE_BEGIN"
            )
        if not allowed:
            return True
    return False


def _format_user_validated_stock_english_override(
    source_document: dict, mapping: dict
) -> tuple[dict[str, str], dict]:
    """Preserve exact stock-USA text for a proven Android identity with bad FR.

    This is not an unresolved/manual translation. Android English still proves
    semantic identity; the user has explicitly rejected the corresponding
    Android French localization. The exact canonical USA source string is sent
    through the ordinary `french_dialogues` translation serializer, so existing
    in-place/relocation behavior remains authoritative.
    """
    snes_ids = mapping.get("snes_ids", [])
    android_ids = mapping.get("android_ids", [])
    if len(snes_ids) != 1 or len(android_ids) != 1:
        raise ValueError("stock-English localization override requires one SNES carrier and one Android anchor")
    text_id = snes_ids[0]
    override_key = (mapping.get("event_id"), text_id, android_ids[0])
    reviewed_reason = DIALOGUE_USER_VALIDATED_STOCK_ENGLISH_OVERRIDES.get(override_key)
    if reviewed_reason is None:
        raise ValueError(
            "stock-English localization override is not in the exact user-validated allow-list"
        )
    by_id, _ = event_text_index(source_document)
    meta = by_id.get(text_id)
    if meta is None or meta.get("event_id") != mapping.get("event_id"):
        raise ValueError("stock-English localization override references an invalid SNES carrier")
    value = meta.get("source", "")
    if not value:
        raise ValueError("stock-English localization override requires non-empty USA source text")
    return {text_id: value}, {
        "event_id": mapping["event_id"],
        "snes_ids": [text_id],
        "android_ids": list(android_ids),
        "confidence": mapping.get("confidence"),
        "source_display": mapping.get("source_display", value),
        "android_english_display": mapping.get("android_english_display", ""),
        "android_french_rejected": mapping.get("french_display", ""),
        "user_validated_stock_english_override": True,
        "override_reason": (
            "user-validated Android-FR localization error; preserve exact canonical USA source text "
            "while retaining the proven Android-English identity. " + reviewed_reason
        ),
        "formatted_entries": [{"id": text_id, "text": value}],
    }



def _format_called_prefix_android_merge_suffix(
    source_document: dict,
    mapping: dict,
    advances: dict[str, int],
    *,
    prefer_semantic_line_breaks: bool,
) -> tuple[dict[str, str], dict]:
    """Format the exact $0521 Android merge without duplicating called $04D4.

    The SNES event executes $04D4 first, then renders CA:5CE6 in the same live
    dialogue. Android stores both clauses in one localization record separated
    by its presentation ``_`` marker. Identity is already user-validated; this
    formatter only redistributes the official payload over the proven SNES call
    boundary and is deliberately restricted to this one event/carrier/anchor.
    """
    if mapping.get("confidence") != "very_high_structural_review":
        raise ValueError("called-prefix Android merge requires structural-review confidence")
    if mapping.get("relation") != "called_prefix_android_merge_suffix":
        raise ValueError("called-prefix Android merge requires its explicit relation")
    if (mapping.get("event_id"), tuple(mapping.get("snes_ids", [])), tuple(mapping.get("android_ids", []))) != (
        "0521", ("CA:5CE6",), (2203,)
    ):
        raise ValueError("called-prefix Android merge is outside the exact Round-42 allow-list")

    by_id, by_event = event_text_index(source_document)
    meta = by_id.get("CA:5CE6")
    if meta is None or meta.get("event_id") != "0521":
        raise ValueError("Round-42 $0521 carrier changed")
    event = by_event["0521"]
    index = meta["token_index"]
    if index != 1 or index <= 0:
        raise ValueError("Round-42 $0521 carrier position changed")
    call = event["tokens"][index - 1]
    if call.get("type") != "command" or call.get("name") != "OP_24" or call.get("args") != "D4":
        raise ValueError("Round-42 $0521 no longer calls $04D4 immediately before its carrier")

    called = by_event.get("04D4")
    if called is None:
        raise ValueError("Round-42 called event $04D4 missing from canonical source")
    called_texts = [
        token for token in called.get("tokens", [])
        if token.get("type") == "text"
    ]
    if len(called_texts) != 1 or called_texts[0].get("id") != "CA:281B":
        raise ValueError("Round-42 $04D4 text shape changed")
    called_source = called_texts[0].get("source", "")
    local_source = meta.get("source", "")
    if normalize_alignment_text(called_source + " " + local_source) != normalize_alignment_text(
        mapping.get("android_english_display", "")
    ):
        raise ValueError("Round-42 $0521 called-prefix English identity no longer reproduces Android EN")

    french_raw = mapping.get("french_display", "")
    if french_raw.count("_") != 1:
        raise ValueError("Round-42 $0521 Android FR no longer has the single proven merge separator")
    _prefix, suffix = french_raw.split("_", 1)
    if not _prefix.strip() or not suffix.strip():
        raise ValueError("Round-42 $0521 Android FR merge has an empty side")

    local_mapping = dict(mapping)
    local_mapping["french_display"] = suffix.strip()
    values, report = format_dialogue_mapping(
        source_document,
        local_mapping,
        advances,
        allow_one_extra_page=True,
        use_physical_page_capacity=True,
        prefer_semantic_line_breaks=prefer_semantic_line_breaks,
        allow_two_extra_pages=True,
    )
    report = dict(report)
    report["called_prefix_android_merge_suffix"] = True
    report["called_event_id"] = "04D4"
    report["called_prefix_snes_id"] = "CA:281B"
    report["android_french_prefix_not_serialized_here"] = _prefix.strip()
    report["android_french_suffix_serialized_here"] = suffix.strip()
    return values, report



def _format_round62_user_reviewed_redistribution(
    source_document: dict,
    mapping: dict,
) -> tuple[dict[str, str], dict]:
    """Serialize the exact user-reviewed Round-62 dialogue redistributions.

    These cases were previously kept PARTIEL solely because official Android FR
    needs a different page/carrier distribution than the canonical USA stream.
    The user supplied the exact target wording and page boundaries. No Android
    identity changes and no stock commands are moved or removed; ``\f`` only
    materializes WAIT $00 + TEXT_CLEAR at the three exact allow-listed carrier
    boundaries accepted by ``shared.dialogue_codec``.
    """
    event_id = mapping.get("event_id")
    snes_ids = tuple(mapping.get("snes_ids", []))
    android_ids = tuple(mapping.get("android_ids", []))
    key = (event_id, snes_ids, android_ids)
    _, by_event = event_text_index(source_document)

    if key == ("038D", ("C9:DAF5", "C9:DB09"), (1815, 1816)):
        values = {
            "C9:DAF5": "Scorpion : Quoi ! Encore vous ?\n",
            "C9:DB09": "Et toi, imbécile, tu ne les as pas\nreconnus ?! Sbire : Désolé, chef...",
        }
        expected_fr = "Scorpion : Quoi ! Encore vous ? Et toi, imbécile, tu ne les as pas reconnus ?! Sbire : Désolé, chef..."
        note = "User-reviewed speaker redistribution across the existing actor-action bridge; no new page is inserted."
    elif key == ("03EA", ("C9:F04C", "C9:F07D"), (2354,)):
        values = {
            "C9:F04C": "♪ Mon cœur, mon amour (la la la),\fma gorge se noue quand je te vois\n(la la la),\f",
            "C9:F07D": "et tout bouillonne dans ma tête... ♪",
        }
        expected_fr = '"♪ Mon cœur, mon amour (la la la), ma gorge se noue quand je te vois (la la la), et tout bouillonne dans ma tête... ♪ "'
        note = "User-reviewed three-page song distribution; the two generated page boundaries are explicit WAIT $00 + TEXT_CLEAR and the stock OP_27 sound bridge stays in place."
    elif key == ("04E2", ("CA:31EE", "CA:3218"), (1275, 1276)):
        values = {
            "CA:31EE": " : Papy !\f",
            "CA:3218": "Cette voix... C'est toi, mon petit ?",
        }
        expected_fr = "%S(2,0) : Papy ! Cette voix... C'est toi, mon petit ?"
        note = "Keep canonical PLAYER_NAME(2); add one explicit page boundary before Grandpa's reply while preserving the stock OP_32/COMPLETE_ACTIONS bridge."
    elif key == ("04E3", ("CA:36C7",), (1384, 1385)):
        # Android 1385 corresponds to the canonical PLAYER_NAME(0) + CA:36F6
        # reaction, even though the punctuation-only USA carrier is not part of
        # the semantic mapping's snes_ids list. Keep PLAYER_NAME(0) untouched.
        tokens = by_event["04E3"]["tokens"]
        if not (
            len(tokens) > 9
            and tokens[7].get("id") == "CA:36C7"
            and tokens[8].get("type") == "command"
            and tokens[8].get("name") == "PLAYER_NAME"
            and tokens[8].get("args") == "00"
            and tokens[9].get("id") == "CA:36F6"
        ):
            raise ValueError("Round-62 $04E3 Truffaut/PLAYER_NAME structure changed")
        values = {
            "CA:36C7": "Truffaut : Vous voilà enfin !\nLes héros de la légende !\fNous vous attendions !\f",
            "CA:36F6": " : Pardon ?",
        }
        expected_fr = "Truffaut : Vous voilà enfin ! Les héros de la légende ! Nous vous attendions ! %S(0,0) : Pardon ?"
        note = "User-reviewed three-page Truffaut/reaction distribution; PLAYER_NAME(0) stays canonical between the trailing page break and CA:36F6."
    else:
        raise ValueError("Round-62 redistribution outside exact allow-list")

    actual_fr = normalize_android_french(mapping.get("french_display", "")).strip()
    expected_normalized = normalize_android_french(expected_fr).strip()
    if actual_fr != expected_normalized:
        raise ValueError(
            f"Round-62 reviewed Android FR changed for ${event_id}: {actual_fr!r} != {expected_normalized!r}"
        )
    return values, {
        "event_id": event_id,
        "snes_ids": list(snes_ids),
        "android_ids": list(android_ids),
        "confidence": mapping.get("confidence"),
        "source_display": mapping.get("source_display", ""),
        "android_english_display": mapping.get("android_english_display", ""),
        "android_french_raw": mapping.get("french_display", ""),
        "round62_user_reviewed_redistribution": True,
        "round62_note": note,
        "formatted_entries": [
            {"id": text_id, "text": value} for text_id, value in values.items()
        ],
    }


def _format_round43_reviewed_redistribution(
    source_document: dict,
    mapping: dict,
) -> tuple[dict[str, str], dict]:
    """Serialize the exact user-reviewed Round-43 cross-event redistributions.

    These shapes cannot be represented by the generic per-event formatter
    because part of the English sentence lives in a shared subevent or in an
    unchanged dynamic PLAYER_NAME/call branch.  Every case is exact-allowlisted
    by event, source IDs, Android anchor and relation; no generic matcher or
    command rewrite is introduced here.
    """
    if mapping.get("confidence") != "very_high_structural_review":
        raise ValueError("Round-43 redistribution requires structural-review confidence")
    event_id = mapping.get("event_id")
    snes_ids = tuple(mapping.get("snes_ids", []))
    android_ids = tuple(mapping.get("android_ids", []))
    relation = mapping.get("relation")
    key = (event_id, snes_ids, android_ids, relation)

    by_id, by_event = event_text_index(source_document)
    for text_id in snes_ids:
        meta = by_id.get(text_id)
        if meta is None or meta.get("event_id") != event_id:
            raise ValueError("Round-43 redistribution references a moved/unknown SNES carrier")

    values: dict[str, str]
    expected_fr: str
    note: str

    if key == (
        "022F", ("C9:9B1B", "C9:9B2C"), (1005,),
        "round43_player_name_resegmentation",
    ):
        tokens = by_event["022F"]["tokens"]
        if not (
            len(tokens) >= 3
            and tokens[0].get("id") == "C9:9B1B"
            and tokens[1].get("type") == "command"
            and tokens[1].get("name") == "PLAYER_NAME"
            and tokens[1].get("args") == "02"
            and tokens[2].get("id") == "C9:9B2C"
        ):
            raise ValueError("Round-43 $022F PLAYER_NAME structure changed")
        expected_fr = "On ne peut pas laisser %S(2,0) comme ça ! Il faut l'aider à retrouver la mémoire !"
        values = {
            "C9:9B1B": "On ne peut pas laisser\n",
            "C9:9B2C": " comme ça !\fIl faut l'aider à retrouver\nla mémoire !",
        }
        note = "Keep PLAYER_NAME(2) in place; explicit page boundary prevents max-name overflow."
    elif key == (
        "02B9", ("C9:BAD6", "C9:BAE8"), (1618,),
        "round43_shared_branch_prefix_redistribution",
    ):
        tokens = by_event["02B9"]["tokens"]
        if not (
            tokens[1].get("id") == "C9:BAD6"
            and tokens[2].get("name") == "OP_42"
            and tokens[3].get("name") == "OP_12"
            and tokens[3].get("args") == "BD"
            and tokens[4].get("id") == "C9:BAE8"
        ):
            raise ValueError("Round-43 $02B9 shared-prefix branch structure changed")
        expected_fr = "Athanor a disparu ! Il jouait tout le temps avec moi, avant..."
        values = {
            "C9:BAD6": "",
            "C9:BAE8": "Athanor a disparu !\nIl jouait tout le temps avec moi,\navant...",
        }
        note = "Remove only the shared pre-branch prefix; localize the fallthrough branch with Android 1618."
    elif key == (
        "0360", ("C9:D1C0", "C9:D1CB"), (2839,),
        "round43_shared_magic_suffix_layout",
    ):
        tokens = by_event["0360"]["tokens"]
        if not (
            tokens[0].get("id") == "C9:D1C0"
            and tokens[1].get("name") == "TEXT_X"
            and tokens[1].get("args") == "07"
            and tokens[2].get("id") == "C9:D1CB"
        ):
            raise ValueError("Round-43 $0360 shared magic suffix structure changed")
        expected_fr = "Gnome fera réagir l'orbe !"
        values = {"C9:D1C0": "\n", "C9:D1CB": ""}
        note = "Full localized spirit sentence is carried by each prefix; preserve only reviewed layout here."
    elif relation == "round43_weapon_orb_prefix":
        expected = {
            ("0500", "CA:58B9", 952): "Vous obtenez\nune sphère de Poing",
            ("0501", "CA:58D5", 122): "Vous obtenez\nune sphère d'Épée",
            ("0502", "CA:58F1", 1008): "Vous obtenez\nune sphère de Hache",
            ("0503", "CA:590B", 631): "Vous obtenez\nune sphère de Lance",
            ("0504", "CA:5927", 901): "Vous obtenez\nune sphère de Fouet",
            ("0505", "CA:5942", 934): "Vous obtenez\nune sphère d'Arc",
            ("0506", "CA:595C", 786): "Vous obtenez\nune sphère de Boomerang",
            ("0507", "CA:597C", 1164): "Vous obtenez\nune sphère de Javelot",
        }
        if len(snes_ids) != 1 or len(android_ids) != 1:
            raise ValueError("Round-43 weapon-orb prefix must be one carrier/anchor")
        local_key = (event_id, snes_ids[0], android_ids[0])
        if local_key not in expected:
            raise ValueError("Round-43 weapon-orb prefix outside exact allow-list")
        tokens = by_event[event_id]["tokens"]
        carrier_index = next(i for i, token in enumerate(tokens) if token.get("id") == snes_ids[0])
        if carrier_index + 1 >= len(tokens) or tokens[carrier_index + 1].get("name") != "OP_15" or tokens[carrier_index + 1].get("args") != "09":
            raise ValueError("Round-43 weapon-orb prefix no longer jumps to $0509")
        value = expected[local_key]
        expected_fr = value.replace("\n", " ") + " !"
        values = {snes_ids[0]: value}
        note = "Serialize the official weapon-specific phrase without terminal punctuation; shared $0509 owns ' !'."
    elif key == (
        "0509", ("CA:598C",), (952,),
        "round43_weapon_orb_suffix",
    ):
        if by_id["CA:598C"].get("source") != "'s Orb!":
            raise ValueError("Round-43 $0509 shared weapon suffix changed")
        expected_fr = "Vous obtenez une sphère de Poing !"
        values = {"CA:598C": " !"}
        note = "Shared weapon-orb subevent keeps only the common French terminal punctuation."
    elif relation == "round43_gameover_plural_slot":
        if (event_id, snes_ids, android_ids) not in {
            ("07FA", ("CA:979D",), (6,)),
            ("07FB", ("CA:97A8",), (6,)),
        }:
            raise ValueError("Round-43 game-over plural slot outside exact allow-list")
        if by_id[snes_ids[0]].get("source") != "them":
            raise ValueError("Round-43 game-over plural carrier changed")
        expected_fr = "... Hélas, l'histoire de ces courageux jeunes gens devait s'achever là..."
        values = {snes_ids[0]: "ces courageux\njeunes gens"}
        note = "Use only Android FR 6's plural dynamic slot; fixed frame remains in $07FF."
    elif key == (
        "07FF", ("CA:98B2", "CA:98C8"), (7,),
        "round43_gameover_dynamic_frame",
    ):
        tokens = by_event["07FF"]["tokens"]
        first_index = next(i for i, token in enumerate(tokens) if token.get("id") == "CA:98B2")
        if not (
            tokens[first_index + 1].get("name") == "OP_27"
            and tokens[first_index + 1].get("args") == "FB"
            and tokens[first_index + 2].get("id") == "CA:98C8"
        ):
            raise ValueError("Round-43 $07FF dynamic game-over call frame changed")
        expected_fr = "... Hélas, l'histoire de %S(0,0) devait s'achever là..."
        values = {
            "CA:98B2": "... Hélas,\fL'histoire de ",
            "CA:98C8": "\ndevait s'achever là...",
        }
        note = "Serialize only Android FR 7's fixed frame; existing $07FB/$07FA/$07F3 call chain supplies plural text or PLAYER_NAME(0)."
    else:
        raise ValueError("Round-43 redistribution outside exact allow-list")

    actual_fr = normalize_android_french(mapping.get("french_display", "")).strip()
    if actual_fr != expected_fr:
        raise ValueError(
            f"Round-43 reviewed Android FR changed for ${event_id}: {actual_fr!r} != {expected_fr!r}"
        )
    return values, {
        "event_id": event_id,
        "snes_ids": list(snes_ids),
        "android_ids": list(android_ids),
        "confidence": mapping.get("confidence"),
        "source_display": mapping.get("source_display", ""),
        "android_english_display": mapping.get("android_english_display", ""),
        "android_french_raw": mapping.get("french_display", ""),
        "round43_reviewed_redistribution": True,
        "round43_relation": relation,
        "round43_note": note,
        "formatted_entries": [
            {"id": text_id, "text": values[text_id]} for text_id in snes_ids
        ],
    }


def _format_round44_reviewed_redistribution(
    source_document: dict,
    mapping: dict,
) -> tuple[dict[str, str], dict]:
    """Serialize exact Round-44 identities whose SNES carrier owns only part/layout of Android prose."""
    if mapping.get("confidence") != "very_high_structural_review":
        raise ValueError("Round-44 redistribution requires structural-review confidence")
    event_id = mapping.get("event_id")
    snes_ids = tuple(mapping.get("snes_ids", []))
    android_ids = tuple(mapping.get("android_ids", []))
    relation = mapping.get("relation")
    by_id, by_event = event_text_index(source_document)

    if relation == "round44_jehk_out_with_return_layout":
        if (event_id, snes_ids, android_ids) != ("001F", ("C9:0983",), (2451,)):
            raise ValueError("Round-44 Jehk layout case outside exact allow-list")
        if by_id["C9:0983"].get("source") != "JEHK:Go away!\n The Sage is out!\n":
            raise ValueError("Round-44 $001F stock text changed")
        actual_fr = normalize_android_french(mapping.get("french_display", "")).strip()
        if actual_fr != "Le maître est absent.":
            raise ValueError("Round-44 Android FR 2451 changed")
        values = {"C9:0983": "Le maître est absent.\n"}
        note = "Keep one terminal NEWLINE before returning to the caller reaction; Android drops the redundant older 'Go away!' clause."
    elif relation == "round44_player_name_followup_layout":
        if (event_id, snes_ids, android_ids) != ("0126", ("C9:3A39",), (3438,)):
            raise ValueError("Round-44 PLAYER_NAME follow-up outside exact allow-list")
        tokens = by_event["0126"]["tokens"]
        carrier_index = next(i for i, token in enumerate(tokens) if token.get("id") == "C9:3A39")
        if carrier_index == 0 or tokens[carrier_index - 1].get("name") != "PLAYER_NAME" or tokens[carrier_index - 1].get("args") != "00":
            raise ValueError("Round-44 $0126 PLAYER_NAME(0) ownership changed")
        actual_fr = normalize_android_french(mapping.get("french_display", "")).strip()
        if actual_fr != "%S(0,0) : Avec cette épée, je vais pouvoir me frayer un chemin.":
            raise ValueError("Round-44 Android FR 3438 changed")
        values = {"C9:3A39": " :\nAvec cette épée, je vais pouvoir\nme frayer un chemin."}
        note = "Keep stock PLAYER_NAME(0), then serialize the official spaced colon and an explicit NEWLINE so a maximum nine-character name remains wrap-free."
    elif relation == "round44_parameterized_inn_price_identity":
        expected = {
            ("0320", "C9:CE3D", 110): ("5", "5 pièces d'or la nuit. Voulez-vous rester dormir ?"),
            ("0321", "C9:CE46", 229): ("10", "10 pièces d'or la nuit. Voulez-vous rester dormir ?"),
            ("0322", "C9:CE50", 502): ("15", "15 pièces d'or la nuit. Voulez-vous rester dormir ?"),
            ("0324", "C9:CE64", 1365): ("50", "50 pièces d'or la nuit. Voulez-vous rester dormir ?"),
            ("0325", "C9:CE6E", 1907): ("100", "100 pièces d'or la nuit. Voulez-vous rester dormir ?"),
            ("0326", "C9:CE79", 1961): ("120", "120 pièces d'or la nuit. Voulez-vous rester dormir ?"),
            ("0327", "C9:CE84", 2319): ("150", "150 pièces d'or la nuit. Voulez-vous rester dormir ?"),
            ("0328", "C9:CE8F", 2498): ("200", "200 pièces d'or la nuit. Voulez-vous rester dormir ?"),
        }
        if len(snes_ids) != 1 or len(android_ids) != 1:
            raise ValueError("Round-44 parameterized inn identity shape changed")
        key = (event_id, snes_ids[0], android_ids[0])
        if key not in expected:
            raise ValueError("Round-44 parameterized inn identity outside exact allow-list")
        price, expected_fr = expected[key]
        if by_id[snes_ids[0]].get("source") != price:
            raise ValueError(f"Round-44 ${event_id} numeric inn carrier changed")
        commands = [(t.get("name"), t.get("args")) for t in by_event[event_id]["tokens"] if t.get("type") == "command"]
        if commands != [("OP_30", f"F9 {int(event_id,16)-0x320:02X}"), ("OP_23", "30"), ("OP_13", "31"), ("END", None)]:
            raise ValueError(f"Round-44 ${event_id} parameterized inn call chain changed")
        actual_fr = normalize_android_french(mapping.get("french_display", "")).strip()
        if actual_fr != expected_fr:
            raise ValueError(f"Round-44 Android FR {android_ids[0]} changed")
        values = {snes_ids[0]: price}
        note = "Identity is the complete Android standard inn prompt; serialization keeps only the stock dynamic numeric parameter because shared $0330/$0331 already render the reviewed French template."
    else:
        raise ValueError("Round-44 redistribution outside exact allow-list")

    return values, {
        "event_id": event_id,
        "snes_ids": list(snes_ids),
        "android_ids": list(android_ids),
        "confidence": mapping.get("confidence"),
        "source_display": mapping.get("source_display", ""),
        "android_english_display": mapping.get("android_english_display", ""),
        "android_french_raw": mapping.get("french_display", ""),
        "round44_reviewed_redistribution": True,
        "round44_relation": relation,
        "round44_note": note,
        "formatted_entries": [{"id": text_id, "text": values[text_id]} for text_id in snes_ids],
    }

def _format_round45_reviewed_redistribution(
    source_document: dict,
    mapping: dict,
) -> tuple[dict[str, str], dict]:
    """Serialize exact Round-45 structural redistributions."""
    if mapping.get("confidence") != "very_high_structural_review":
        raise ValueError("Round-45 redistribution requires structural-review confidence")
    event_id = mapping.get("event_id")
    snes_ids = tuple(mapping.get("snes_ids", []))
    android_ids = tuple(mapping.get("android_ids", []))
    relation = mapping.get("relation")
    by_id, by_event = event_text_index(source_document)

    if (event_id, snes_ids, android_ids, relation) == (
        "01B6", ("C9:6AD2", "C9:6B5A"), (584,), "round45_watts_shortcut_redistribution"
    ):
        if by_id["C9:6AD2"].get("source") != "\n And only I can do it!\n Now, let me show you a\n short cut.":
            raise ValueError("Round-45 $01B6 first stock carrier changed")
        if by_id["C9:6B5A"].get("source") != "WATTS:This will make it\n a lot easier for you!":
            raise ValueError("Round-45 $01B6 second stock carrier changed")
        tokens = by_event["01B6"]["tokens"]
        first = next(i for i,t in enumerate(tokens) if t.get("id") == "C9:6AD2")
        second = next(i for i,t in enumerate(tokens) if t.get("id") == "C9:6B5A")
        bridge = [t for t in tokens[first+1:second] if t.get("type") == "command"]
        if not any(t.get("name") == "TEXT_CLOSE" for t in bridge) or not any(t.get("name") == "TEXT_OPEN" for t in bridge):
            raise ValueError("Round-45 $01B6 movement/text bridge changed")
        actual_fr = normalize_android_french(mapping.get("french_display", "")).strip()
        expected_fr = "Watts : Tu verras, c'est beaucoup plus rapide par ce chemin !"
        if actual_fr != expected_fr:
            raise ValueError("Round-45 Android FR 584/585 redistribution changed")
        values = {
            "C9:6AD2": "",
            "C9:6B5A": "Watts : Tu verras, c'est beaucoup\nplus rapide par ce chemin !",
        }
        note = (
            "Android FR moved the shortcut introduction into already-rendered slot 583; "
            "leave the pre-movement carrier empty and serialize FR-only slot 585 after "
            "the unchanged movement sequence."
        )
    elif (event_id, snes_ids, android_ids, relation) == (
        "01DA", ("C9:7E64", "C9:7E72", "C9:7E81"), (676, 677), "round45_girl_name_resegmentation"
    ):
        tokens = by_event["01DA"]["tokens"]
        indexes = {t.get("id"): i for i,t in enumerate(tokens) if t.get("type") == "text"}
        if [tokens[indexes["C9:7E64"]-1].get("name"), tokens[indexes["C9:7E72"]-1].get("name"), tokens[indexes["C9:7E81"]-1].get("name")] != ["PLAYER_NAME", "PLAYER_NAME", "PLAYER_NAME"]:
            raise ValueError("Round-45 $01DA PLAYER_NAME ownership changed")
        if any(tokens[indexes[text_id]-1].get("args") != "00" for text_id in snes_ids):
            raise ValueError("Round-45 $01DA PLAYER_NAME index changed")
        if indexes["C9:7E81"] + 1 >= len(tokens) or tokens[indexes["C9:7E81"]+1].get("type") != "glyph" or tokens[indexes["C9:7E81"]+1].get("code") != "CE":
            raise ValueError("Round-45 $01DA terminal naming glyph changed")
        actual_fr = normalize_android_french(mapping.get("french_display", "")).strip()
        expected_fr = "%S(0,0) : Je m'appelle %S(0,0). Hum... Drôle de nom. Moi, c'est..."
        if normalize_alignment_text(actual_fr) != normalize_alignment_text(expected_fr):
            raise ValueError("Round-45 Android FR 676+677 changed")
        values = {
            "C9:7E64": " : Je m'appelle ",
            "C9:7E72": ".\nHum... Drôle de nom.\nMoi, c'est... ",
            "C9:7E81": "",
        }
        note = (
            "Keep the first two PLAYER_NAME(0) commands for Android FR 676, omit only the "
            "third PLAYER_NAME immediately before the empty C9:7E81 carrier, and let the "
            "existing terminal $CE naming glyph follow official FR 677."
        )
    else:
        raise ValueError("Round-45 redistribution outside exact allow-list")

    return values, {
        "event_id": event_id,
        "snes_ids": list(snes_ids),
        "android_ids": list(android_ids),
        "confidence": mapping.get("confidence"),
        "source_display": mapping.get("source_display", ""),
        "android_english_display": mapping.get("android_english_display", ""),
        "android_french_raw": mapping.get("french_display", ""),
        "round45_reviewed_redistribution": True,
        "round45_relation": relation,
        "round45_note": note,
        "formatted_entries": [{"id": text_id, "text": values[text_id]} for text_id in snes_ids],
    }


def _format_round46_system_chest(
    source_document: dict,
    mapping: dict,
    advances: dict[str, int],
    *,
    prefer_semantic_line_breaks: bool,
) -> tuple[dict[str, str], dict]:
    """Serialize the exact reviewed Android ``systxt`` chest-message family."""
    if mapping.get("confidence") != "very_high_structural_review":
        raise ValueError("Round-46 systxt chest mapping requires structural-review confidence")
    relation = mapping.get("relation")
    namespace = mapping.get("android_namespace", "scrtxt")
    if relation == "round46_systxt_chest_money" and namespace != "systxt":
        raise ValueError("Round-46 money chest identity must remain in systxt")
    if relation == "round46_systxt_chest_localization_override" and namespace != "scrtxt":
        raise ValueError("Round-46 item chest identity must remain in scrtxt")
    event_id = mapping.get("event_id")
    snes_ids = tuple(mapping.get("snes_ids", []))
    android_ids = tuple(mapping.get("android_ids", []))
    if len(snes_ids) != 1 or len(android_ids) != 1:
        raise ValueError("Round-46 systxt chest mapping requires one SNES carrier and one system anchor")
    text_id = snes_ids[0]
    by_id, by_event = event_text_index(source_document)
    if text_id not in by_id or by_id[text_id].get("event_id") != event_id:
        raise ValueError("Round-46 systxt chest mapping references an invalid SNES carrier")

    expected = {
        ("067E", "CA:8E72", 101254): ("  Found 1000 GP!", "Vous trouvez $0d pièces d'or dans le coffre !", "1000"),
        ("067F", "CA:8E8F", 101254): ("  Found 50 GP!", "Vous trouvez $0d pièces d'or dans le coffre !", "50"),
        ("0687", "CA:8EEF", 469): ("Found the Magic Rope!", "Vous trouvez la Corde magique dans le coffre !", None),
        ("0689", "CA:8F20", 769): ("Found the Whip!", "Vous trouvez le Fouet en cuir dans le coffre !", None),
    }
    key = (event_id, text_id, android_ids[0])
    if key not in expected:
        raise ValueError("Round-46 systxt chest mapping is outside the exact allow-list")
    expected_source, expected_fr, amount = expected[key]
    if by_id[text_id].get("source") != expected_source:
        raise ValueError(f"Round-46 ${event_id} stock chest text changed")
    actual_fr = normalize_android_french(mapping.get("french_display", "")).strip()
    if actual_fr != expected_fr:
        raise ValueError(f"Round-46 systxt French {android_ids[0]} changed")

    # Prove the stock event semantics that distinguish the chest records.
    tokens = by_event[event_id]["tokens"]
    if event_id in {"067E", "067F"}:
        expected_money = "E8 03" if event_id == "067E" else "32 00"
        if not any(t.get("name") == "OP_36" and t.get("args") == expected_money for t in tokens):
            raise ValueError(f"Round-46 ${event_id} money-add command changed")
        localized = actual_fr.replace("$0d", amount)
    elif event_id == "0687":
        if not any(t.get("name") == "OP_1E" and t.get("args") == "46" for t in tokens):
            raise ValueError("Round-46 $0687 Magic Rope item grant changed")
        localized = actual_fr
    else:
        if not any(t.get("name") == "OP_1E" and t.get("args") == "A4" for t in tokens):
            raise ValueError("Round-46 $0689 Leather Whip grant changed")
        localized = actual_fr

    local_mapping = dict(mapping)
    local_mapping["french_display"] = localized
    values, report = format_dialogue_mapping(
        source_document,
        local_mapping,
        advances,
        allow_one_extra_page=True,
        use_physical_page_capacity=True,
        prefer_semantic_line_breaks=prefer_semantic_line_breaks,
        allow_two_extra_pages=True,
    )
    report = dict(report)
    report["android_namespace"] = namespace
    report["round46_system_chest"] = True
    report["round46_relation"] = relation
    report["system_template_parameter"] = amount
    report["android_french_raw"] = mapping.get("french_display", "")
    report["android_french_materialized"] = localized
    return values, report



# Round 48 exact formatter allow-list.  Android FR occasionally adds a dynamic
# vocative that neither Android EN nor the canonical SNES carrier contains.
# These are reviewed localization embellishments, not missing PLAYER_NAME
# commands.  Keep the identity mapping unchanged and remove only the exact
# vocative; never generalize this from punctuation or placeholder position.
DIALOGUE_ROUND48_ANDROID_ONLY_VOCATIVES = {
    ("0119", "C9:37AF", 109): {
        "source": "Heading out? See you later!",
        "android_en": "Heading out? See you later!",
        "android_fr": "Oh, tu t'en vas, %S(0,0) ? À plus tard !",
        "localized": "Oh, tu t'en vas ? À plus tard !",
    },
    ("0127", "C9:3AC3", 914): {
        "source": "JEMA:Hey! How rude!",
        "android_en": "Jema: Hey! How rude!_",
        "android_fr": "Gemma : Voyons, %S(0,0) ! Un peu de respect !_",
        "localized": "Gemma : Voyons ! Un peu de respect !_",
    },
    ("01B5", "C9:68BA", 574): {
        "source": "WATTS:Well...I tried making\n an axe, but it's no good.\n Wonder why...",
        "android_en": "Watts: Well... I tried making an axe, but it's no good. Wonder why...",
        "android_fr": "%S_PLACEHOLDER%",
        "localized": "Watts : J'ai essayé de fabriquer une hache, mais elle n'a rien de spécial. Je me demande pourquoi...",
    },
    ("0227", "C9:9827", 218): {
        "source": "...\n I'm sure he's fine.",
        "android_en": "I'm sure he's fine.",
        "android_fr": "Non ! Je suis sûre qu'il va bien, %S(1,0).",
        "localized": "Non ! Je suis sûre qu'il va bien.",
    },
    ("0295", "C9:AF50", 1518): {
        "source": " Just like paradise in here, eh, buddy?",
        "android_en": "Just like paradise in here, eh, buddy?",
        "android_fr": "Hé, salut %S(0,0) ! J'suis au paradis, ici !",
        "localized": "Hé, salut ! J'suis au paradis, ici !",
    },
    ("04E6", "CA:40AF", 87): {
        "source": " I'm going to have to ask\n you to leave the village.",
        "android_en": "I'm going to have to ask you to leave the village.",
        "android_fr": "Je vais devoir te demander de quitter le village, %S(0,0).",
        "localized": "Je vais devoir te demander de quitter le village.",
    },
    ("04E7", "CA:4126", 91): {
        "source": " I know I've told you this\n before, but...",
        "android_en": "I know I've told you this before, but...",
        "android_fr": "%S(0,0), tu ne dois pas t'en souvenir, mais...",
        "localized": "Tu ne dois pas t'en souvenir, mais...",
    },
}

# Fill the one long literal separately to keep the source table readable while
# still proving the exact Android-FR input byte-for-byte after normalization.
DIALOGUE_ROUND48_ANDROID_ONLY_VOCATIVES[("01B5", "C9:68BA", 574)]["android_fr"] = (
    "Watts : %S(0,0) ! J'ai essayé de fabriquer une hache, mais elle n'a rien de spécial. "
    "Je me demande pourquoi..."
)


def _round48_without_android_only_vocative(source_document: dict, mapping: dict) -> tuple[dict, dict | None]:
    """Return an exact reviewed mapping with only an Android-FR vocative removed."""
    snes_ids = tuple(mapping.get("snes_ids", []))
    android_ids = tuple(mapping.get("android_ids", []))
    if len(snes_ids) != 1 or len(android_ids) != 1:
        return mapping, None
    key = (mapping.get("event_id"), snes_ids[0], android_ids[0])
    expected = DIALOGUE_ROUND48_ANDROID_ONLY_VOCATIVES.get(key)
    if expected is None:
        return mapping, None
    if mapping.get("android_namespace", "scrtxt") != "scrtxt":
        raise ValueError("Round-48 Android-only vocative review requires scrtxt identity")

    by_id, _ = event_text_index(source_document)
    text_id = snes_ids[0]
    if text_id not in by_id or by_id[text_id].get("event_id") != key[0]:
        raise ValueError("Round-48 Android-only vocative review references an invalid SNES carrier")
    if by_id[text_id].get("source") != expected["source"]:
        raise ValueError(f"Round-48 ${key[0]} canonical SNES source changed")

    actual_en = normalize_android_prose(mapping.get("android_english_display", "")).strip()
    expected_en = normalize_android_prose(expected["android_en"]).strip()
    if actual_en != expected_en or "%S(" in actual_en:
        raise ValueError(f"Round-48 ${key[0]} Android-English identity context changed")
    actual_fr = normalize_android_french(mapping.get("french_display", "")).strip()
    expected_fr = normalize_android_french(expected["android_fr"]).strip()
    if actual_fr != expected_fr:
        raise ValueError(f"Round-48 ${key[0]} Android-French vocative source changed")
    if "%S(" not in actual_fr or "%S(" in expected["localized"]:
        raise ValueError(f"Round-48 ${key[0]} reviewed vocative shape changed")

    reviewed = dict(mapping)
    reviewed["french_display"] = expected["localized"]
    reviewed["identity_french_display"] = expected["localized"]
    repair = {
        "event_id": key[0],
        "snes_id": text_id,
        "android_id": android_ids[0],
        "strategy": "remove_exact_android_fr_only_vocative",
        "android_identity_unchanged": True,
        "snes_player_name_commands_unchanged": True,
        "localized": expected["localized"],
    }
    reviewed["round48_android_only_vocative_repair"] = repair
    return reviewed, repair



# Round 49 exact formatter-only recoveries. These do not change Android-English
# identity and are intentionally event-specific: one Android-FR-only speaker
# label can be removed where the SNES event has no PLAYER_NAME command at all,
# and one three-part machine-noise line can be distributed across its exact
# stock PLAY_SOUND/WAIT bridge without moving or inventing commands.
DIALOGUE_ROUND49_ANDROID_ONLY_SPEAKER_LABELS = {
    ("02CD", "C9:BE42", (1735, 1736)): {
        "source": "The seed's on the stage!\nHold up the sword!",
        "android_en": "The Seed's on the stage! Hold up the Sword!",
        "android_fr": "Vous replacez la Graine sur son autel. %S(0,0) : Je dois aligner l'Épée sur la Graine !",
        "localized": "Vous replacez la Graine sur son autel. Je dois aligner l'Épée sur la Graine !",
    },
}

DIALOGUE_ROUND49_SOUND_SEQUENCE = {
    "event_id": "03F0",
    "snes_ids": ("C9:F29A", "C9:F2AC", "C9:F2BA"),
    "android_ids": (2361,),
    "sources": ("...Gzzzaza...", "zzzz...", " Beeeep!"),
    "android_en": "...Gzzzaza... zzzz... Beeeep!",
    "android_fr": "... Krrr... bzzz... biiip !",
    "localized_parts": ("... Krrr...", "bzzz...", "biiip !"),
}


def _round49_without_android_only_speaker_label(
    source_document: dict, mapping: dict
) -> tuple[dict, dict | None]:
    """Remove one exact Android-FR-only speaker label absent from SNES/Android EN."""
    snes_ids = tuple(mapping.get("snes_ids", []))
    android_ids = tuple(mapping.get("android_ids", []))
    if len(snes_ids) != 1:
        return mapping, None
    key = (mapping.get("event_id"), snes_ids[0], android_ids)
    expected = DIALOGUE_ROUND49_ANDROID_ONLY_SPEAKER_LABELS.get(key)
    if expected is None:
        return mapping, None
    if mapping.get("android_namespace", "scrtxt") != "scrtxt":
        raise ValueError("Round-49 Android-only speaker-label review requires scrtxt identity")

    by_id, by_event = event_text_index(source_document)
    text_id = snes_ids[0]
    meta = by_id.get(text_id)
    if meta is None or meta.get("event_id") != key[0] or meta.get("source") != expected["source"]:
        raise ValueError("Round-49 Android-only speaker-label canonical carrier changed")
    event = by_event[key[0]]
    if any(
        token.get("type") == "command" and token.get("name") == "PLAYER_NAME"
        for token in event.get("tokens", [])
    ):
        raise ValueError("Round-49 $02CD unexpectedly gained a SNES PLAYER_NAME command")

    actual_en = normalize_android_prose(mapping.get("android_english_display", "")).strip()
    expected_en = normalize_android_prose(expected["android_en"]).strip()
    if actual_en != expected_en or "%S(" in actual_en:
        raise ValueError("Round-49 $02CD Android-English identity context changed")
    actual_fr = normalize_android_french(mapping.get("french_display", "")).strip()
    expected_fr = normalize_android_french(expected["android_fr"]).strip()
    localized = normalize_android_french(expected["localized"]).strip()
    if actual_fr != expected_fr:
        raise ValueError("Round-49 $02CD Android-French speaker-label source changed")
    if actual_fr.count("%S(0,0)") != 1 or "%S(" in localized:
        raise ValueError("Round-49 $02CD reviewed speaker-label shape changed")

    reviewed = dict(mapping)
    reviewed["french_display"] = localized
    reviewed["identity_french_display"] = localized
    repair = {
        "event_id": key[0],
        "snes_id": text_id,
        "android_ids": list(android_ids),
        "strategy": "remove_exact_android_fr_only_speaker_label",
        "android_identity_unchanged": True,
        "snes_player_name_commands_unchanged": True,
        "localized": localized,
    }
    reviewed["round49_android_only_speaker_label_repair"] = repair
    return reviewed, repair


def _format_round49_sound_sequence(
    source_document: dict,
    mapping: dict,
    advances: dict[str, int],
) -> tuple[dict[str, str], dict]:
    """Distribute the exact $03F0 Android-FR machine noises across stock sound commands."""
    expected = DIALOGUE_ROUND49_SOUND_SEQUENCE
    if mapping.get("event_id") != expected["event_id"]:
        raise ValueError("Round-49 sound sequence applies only to $03F0")
    if tuple(mapping.get("snes_ids", [])) != expected["snes_ids"]:
        raise ValueError("Round-49 $03F0 SNES carrier sequence changed")
    if tuple(mapping.get("android_ids", [])) != expected["android_ids"]:
        raise ValueError("Round-49 $03F0 Android identity changed")
    if mapping.get("android_namespace", "scrtxt") != "scrtxt":
        raise ValueError("Round-49 $03F0 requires scrtxt identity")
    if normalize_android_prose(mapping.get("android_english_display", "")).strip() != normalize_android_prose(expected["android_en"]).strip():
        raise ValueError("Round-49 $03F0 Android-English source changed")
    if normalize_android_french(mapping.get("french_display", "")).strip() != normalize_android_french(expected["android_fr"]).strip():
        raise ValueError("Round-49 $03F0 Android-French source changed")

    by_id, by_event = event_text_index(source_document)
    event = by_event.get("03F0")
    if event is None:
        raise ValueError("Round-49 $03F0 event missing")
    for text_id, source in zip(expected["snes_ids"], expected["sources"], strict=True):
        meta = by_id.get(text_id)
        if meta is None or meta.get("event_id") != "03F0" or meta.get("source") != source:
            raise ValueError(f"Round-49 $03F0 canonical source changed at {text_id}")

    exact_tokens = {
        0: ("command", "TEXT_OPEN", ""),
        1: ("text", "C9:F294", "\n"),
        2: ("command", "PLAY_SOUND", "02 D5 00 88"),
        3: ("text", "C9:F29A", "...Gzzzaza..."),
        4: ("command", "PLAY_SOUND", "02 B3 0F 88"),
        5: ("text", "C9:F2AC", "zzzz..."),
        6: ("command", "WAIT", "10"),
        7: ("command", "PLAY_SOUND", "02 17 00 88"),
        8: ("text", "C9:F2BA", " Beeeep!"),
        9: ("command", "WAIT", "00"),
        10: ("command", "RETURN", ""),
        11: ("command", "END", ""),
    }
    tokens = event.get("tokens", [])
    if len(tokens) != len(exact_tokens):
        raise ValueError("Round-49 $03F0 canonical token count changed")
    for index, (kind, identity, payload) in exact_tokens.items():
        token = tokens[index]
        if token.get("type") != kind:
            raise ValueError(f"Round-49 $03F0 token {index} type changed")
        if kind == "text":
            if token.get("id") != identity or token.get("source") != payload:
                raise ValueError(f"Round-49 $03F0 text token {index} changed")
        elif token.get("name") != identity or token.get("args", "") != payload:
            raise ValueError(f"Round-49 $03F0 command token {index} changed")

    translations: dict[str, str] = {}
    subreports: list[dict] = []
    for text_id, piece in zip(expected["snes_ids"], expected["localized_parts"], strict=True):
        local = dict(mapping)
        local["snes_ids"] = [text_id]
        local["source_display"] = by_id[text_id]["source"]
        local["french_display"] = piece
        values, report = format_dialogue_mapping(
            source_document,
            local,
            advances,
            allow_one_extra_page=False,
            use_physical_page_capacity=True,
            prefer_semantic_line_breaks=False,
            allow_two_extra_pages=False,
        )
        value = values[text_id]
        if any(marker in value for marker in ("\n", "\f", "\v")):
            raise ValueError(f"Round-49 $03F0 localized part unexpectedly wrapped at {text_id}")
        translations[text_id] = value
        subreports.append(report)

    # Preserve the localized spaces between the first two sound fragments, then
    # materialize one layout-only NEWLINE before the existing timed WAIT $10.
    # This prevents same-line continuation from becoming a simulator warning;
    # WAIT itself remains byte-for-byte unchanged and still does not advance the cursor.
    translations["C9:F2AC"] = " " + translations["C9:F2AC"] + "\n"

    return translations, {
        "event_id": "03F0",
        "snes_ids": list(expected["snes_ids"]),
        "android_ids": list(expected["android_ids"]),
        "confidence": mapping.get("confidence"),
        "source_display": mapping.get("source_display", ""),
        "android_french_raw": mapping.get("french_display", ""),
        "round49_exact_sound_sequence": True,
        "android_identity_unchanged": True,
        "stock_commands_unchanged": True,
        "preserved_bridge": [
            {"name": "PLAY_SOUND", "args": "02 D5 00 88"},
            {"name": "PLAY_SOUND", "args": "02 B3 0F 88"},
            {"name": "WAIT", "args": "10"},
            {"name": "PLAY_SOUND", "args": "02 17 00 88"},
        ],
        "inserted_layout_newline_before_existing_wait10": True,
        "distributed_french_parts": list(expected["localized_parts"]),
        "subreports": subreports,
        "formatted_entries": [
            {"id": text_id, "text": translations[text_id]}
            for text_id in expected["snes_ids"]
        ],
    }



# Round 52 formatter-only structural distributions.  These mappings already
# have Android-English identity; the allow-list only decides where the official
# Android-French text can safely resume around commands that are already present
# in the stock SNES event stream.  No generic action/WAIT rule is widened.
DIALOGUE_ROUND52_STRUCTURAL_DISTRIBUTIONS = {
    ("01B5", ("C9:6921", "C9:6954"), (577,)): {
        "sources": (
            "Wait! I know...!\n Try holding this axe!",
            " That's it! Mana power in\n these weapons doesn't work\n until you hold them!",
        ),
        "android_en": "Wait! I know! Try holding this axe! That's it! Mana power in these weapons doesn't work until you hold them!",
        "android_fr": "J'ai compris !\nTant que ces armes n'ont pas été en contact avec l'Épée sacrée, leur potentiel est scellé !",
        "localized_parts": (
            "J'ai compris !",
            "Tant que ces armes n'ont pas été en contact avec l'Épée sacrée, leur potentiel est scellé !",
        ),
        "bridge": (
            ("WAIT", "00"),
            ("TEXT_CLOSE", ""),
            ("OP_2D", "06 FF 43"),
            ("WAIT", "08"),
            ("OP_2D", "07"),
            ("TEXT_OPEN", ""),
        ),
        "strategy": "round52_scene_bridge_sentence_distribution",
        "note": (
            "Android FR already moves the axe instruction into the preceding owned slot 575. "
            "The remaining 577 payload therefore splits at the complete sentence 'J'ai compris !' "
            "around the unchanged stock WAIT/TEXT_CLOSE/action/WAIT/TEXT_OPEN bridge."
        ),
    },
    ("01B9", ("C9:6C0F", "C9:6C21"), (593,)): {
        "sources": ("\nELDER:Hey!\n", " Sorry about that."),
        "android_en": "Elder: Hey! Sorry about that.",
        "android_fr": "Chef : Dis donc, toi ! Jeune ingrat !\nExcusez-le...",
        "localized_parts": (
            "Chef : Dis donc, toi ! Jeune ingrat !",
            "Excusez-le...",
        ),
        "bridge": (
            ("OP_32", "05 00"),
            ("COMPLETE_ACTIONS", ""),
            ("WAIT", "04"),
        ),
        "strategy": "round52_timed_wait_sentence_distribution",
        "preserve_first_leading_newline": True,
        "note": (
            "The apology remains after the stock actor action + WAIT $04. The first French unit "
            "contains only the elder's reprimand; 'Excusez-le...' resumes after the same pause."
        ),
    },
    ("01B9", ("C9:6CDD", "C9:6D0D"), (596,)): {
        "sources": (
            "\nSPRITE:Come on old timer!\n Give me a break.\n",
            " Take it easy!",
        ),
        "android_en": "Sprite: Come on, old timer! Give me a break. Take it easy!",
        "android_fr": "Lutin : Bah, ma mémoire finira bien par revenir !\nFaut être positif dans la vie, hé hé hé !",
        "localized_parts": (
            "Lutin : Bah, ma mémoire finira bien par revenir !",
            "Faut être positif dans la vie, hé hé hé !",
        ),
        "bridge": (("OP_34", "04 A5"),),
        "strategy": "round52_action_sentence_distribution",
        "note": (
            "Both Android languages contain a complete thought boundary. The stock OP_34 remains "
            "between the two French sentences; the formatter's leading page clear replaces only "
            "the stock newline immediately after the already-existing WAIT $00."
        ),
    },
    ("01B9", ("C9:6DC1", "C9:6DD9"), (599,)): {
        "sources": ("SPRITE:What? Really?\n", " I'll go now, right now!!!"),
        "android_en": "Sprite: What? Really? I'll go now, right now!!!",
        "android_fr": "Lutin : Quoi ! Fallait le dire ! J'y vais tout de suite ! ",
        "localized_parts": (
            "Lutin : Quoi ! Fallait le dire !",
            "J'y vais tout de suite !",
        ),
        "bridge": (("OP_34", "04 82"),),
        "leading_layout_clear_id": "C9:6DBC",
        "leading_layout_clear_source": "\n",
        "leading_layout_prefix": (("WAIT", "00"),),
        "leading_layout_suffix": (("OP_32", "04 40"), ("COMPLETE_ACTIONS", "")),
        "strategy": "round52_action_reaction_page_distribution",
        "note": (
            "The stock newline-only C9:6DBC follows WAIT $00 and precedes the unchanged OP_32 + "
            "COMPLETE_ACTIONS reaction. Replacing only that layout carrier with TEXT_CLEAR starts a "
            "fresh page before the Sprite speaks; the unchanged OP_34 then remains between the two "
            "complete French reaction sentences."
        ),
    },
    ("04E6", ("CA:4074", "CA:4095"), (86,)): {
        "sources": ("ELDER:I don't want to do\n this", ", but I have no choice."),
        "android_en": "Elder: I don't want to do this, but I have no choice._",
        "android_fr": "Chef : ...\nJe regrette, mais je n'ai pas le choix._",
        "localized_parts": ("Chef : ...", "Je regrette, mais je n'ai pas le choix."),
        "bridge": (("OP_32", "08 C0"),),
        "strategy": "round52_action_hesitation_distribution",
        "note": (
            "Android FR turns the stock mid-sentence actor action into an explicit hesitation. "
            "The unchanged OP_32 sits exactly between 'Chef : ...' and the following regret."
        ),
    },
    ("04E7", ("CA:4211", "CA:4249"), (95,)): {
        "sources": (
            "\n I truly hope you can find\n your mother someday.\n ...",
            "Good bye, ",
        ),
        "tail_id": "CA:4255",
        "tail_source": ".",
        "android_en": "I truly hope you can find your mother someday.\n...Good bye, %S(0,0).",
        "android_fr": "Je prie pour qu'un jour tu retrouves ta mère.\nAdieu, %S(0,0), prends bien soin de toi.",
        "localized_parts": (
            "Je prie pour qu'un jour tu retrouves ta mère.",
            "Adieu, %S(0,0), prends bien soin de toi.",
        ),
        "bridge": (("WAIT", "08"),),
        "strategy": "round52_timed_wait_page_clear_distribution",
        "note": (
            "The two French sentences align exactly around the stock timed WAIT $08. The first "
            "carrier keeps its stock leading newline. A single TEXT_CLEAR is materialized at the "
            "start of the goodbye carrier after WAIT $08 so the longer French farewell cannot "
            "continue on the live line; PLAYER_NAME(0) stays in its stock position."
        ),
    },
}


def _format_round52_structural_distribution(
    source_document: dict,
    mapping: dict,
    advances: dict[str, int],
) -> tuple[dict[str, str], dict]:
    """Serialize one exact Round-52 WAIT/action bridge without widening generic rules."""
    key = (
        mapping.get("event_id"),
        tuple(mapping.get("snes_ids", [])),
        tuple(mapping.get("android_ids", [])),
    )
    expected = DIALOGUE_ROUND52_STRUCTURAL_DISTRIBUTIONS.get(key)
    if expected is None:
        raise ValueError("Round-52 structural distribution is not allow-listed")
    if mapping.get("android_namespace", "scrtxt") != "scrtxt":
        raise ValueError("Round-52 structural distribution requires scrtxt identity")

    by_id, by_event = event_text_index(source_document)
    event = by_event.get(key[0])
    if event is None:
        raise ValueError(f"Round-52 event ${key[0]} is missing")
    snes_ids = key[1]
    for text_id, source in zip(snes_ids, expected["sources"], strict=True):
        meta = by_id.get(text_id)
        if meta is None or meta.get("event_id") != key[0] or meta.get("source") != source:
            raise ValueError(f"Round-52 canonical SNES source changed at {text_id}")

    actual_en = normalize_android_prose(mapping.get("android_english_display", "")).strip()
    expected_en = normalize_android_prose(expected["android_en"]).strip()
    if actual_en != expected_en:
        raise ValueError(f"Round-52 ${key[0]} Android-English identity context changed")
    actual_fr = normalize_android_french(mapping.get("french_display", "")).strip()
    expected_fr = normalize_android_french(expected["android_fr"]).strip()
    if actual_fr != expected_fr:
        raise ValueError(f"Round-52 ${key[0]} Android-French payload changed")

    first_index = by_id[snes_ids[0]]["token_index"]
    second_index = by_id[snes_ids[1]]["token_index"]
    between = event["tokens"][first_index + 1:second_index]
    actual_bridge = []
    for token in between:
        if token.get("type") != "command":
            raise ValueError(f"Round-52 ${key[0]} bridge unexpectedly contains text")
        actual_bridge.append((token.get("name"), token.get("args", "")))
    if tuple(actual_bridge) != tuple(expected["bridge"]):
        raise ValueError(f"Round-52 ${key[0]} canonical command bridge changed")

    common = dict(
        allow_one_extra_page=False,
        use_physical_page_capacity=True,
        prefer_semantic_line_breaks=True,
        allow_two_extra_pages=False,
    )
    translations: dict[str, str] = {}
    subreports: list[dict] = []

    if key[0] != "04E7":
        for text_id, french_piece in zip(snes_ids, expected["localized_parts"], strict=True):
            local = dict(mapping)
            local["snes_ids"] = [text_id]
            local["source_display"] = by_id[text_id]["source"]
            local["french_display"] = french_piece
            values, report = format_dialogue_mapping(source_document, local, advances, **common)
            translations.update(values)
            subreports.append(report)
        if expected.get("preserve_first_leading_newline"):
            first_id = snes_ids[0]
            value = translations[first_id]
            if not value.startswith(TRANSLATION_CLEAR) or not by_id[first_id]["source"].startswith("\n"):
                raise ValueError(f"Round-52 ${key[0]} expected formatter page clear shape changed")
            translations[first_id] = "\n" + value[len(TRANSLATION_CLEAR):]
        if expected.get("leading_layout_clear_id"):
            layout_id = expected["leading_layout_clear_id"]
            layout_meta = by_id.get(layout_id)
            if (
                layout_meta is None
                or layout_meta.get("event_id") != key[0]
                or layout_meta.get("source") != expected["leading_layout_clear_source"]
            ):
                raise ValueError(f"Round-52 ${key[0]} leading layout carrier changed")
            layout_index = layout_meta["token_index"]
            if layout_index >= first_index:
                raise ValueError(f"Round-52 ${key[0]} leading layout carrier moved")
            prefix_tokens = event["tokens"][layout_index - len(expected["leading_layout_prefix"]):layout_index]
            suffix_tokens = event["tokens"][layout_index + 1:first_index]
            def _command_pairs(tokens):
                if any(token.get("type") != "command" for token in tokens):
                    raise ValueError(f"Round-52 ${key[0]} leading layout context gained text")
                return tuple((token.get("name"), token.get("args", "")) for token in tokens)
            if _command_pairs(prefix_tokens) != tuple(expected["leading_layout_prefix"]):
                raise ValueError(f"Round-52 ${key[0]} leading layout prefix changed")
            if _command_pairs(suffix_tokens) != tuple(expected["leading_layout_suffix"]):
                raise ValueError(f"Round-52 ${key[0]} leading layout suffix changed")
            translations[layout_id] = TRANSLATION_CLEAR
    else:
        first_id, goodbye_id = snes_ids
        first_local = dict(mapping)
        first_local["snes_ids"] = [first_id]
        first_local["source_display"] = by_id[first_id]["source"]
        first_local["french_display"] = expected["localized_parts"][0]
        first_values, first_report = format_dialogue_mapping(
            source_document, first_local, advances, **common
        )
        first_value = first_values[first_id]
        if not first_value.startswith(TRANSLATION_CLEAR) or not by_id[first_id]["source"].startswith("\n"):
            raise ValueError("Round-52 $04E7 first-page formatter shape changed")
        translations[first_id] = "\n" + first_value[len(TRANSLATION_CLEAR):]
        subreports.append(first_report)

        tail_id = expected["tail_id"]
        tail_meta = by_id.get(tail_id)
        if (
            tail_meta is None
            or tail_meta.get("event_id") != "04E7"
            or tail_meta.get("source") != expected["tail_source"]
            or tail_meta.get("token_index") != by_id[goodbye_id]["token_index"] + 2
        ):
            raise ValueError("Round-52 $04E7 punctuation tail changed")
        player_token = event["tokens"][by_id[goodbye_id]["token_index"] + 1]
        if player_token.get("type") != "command" or player_token.get("name") != "PLAYER_NAME" or player_token.get("args") != "00":
            raise ValueError("Round-52 $04E7 PLAYER_NAME(0) position changed")

        goodbye_local = dict(mapping)
        goodbye_local["snes_ids"] = [goodbye_id, tail_id]
        goodbye_local["source_display"] = "Good bye, %S(0,0)."
        goodbye_local["french_display"] = expected["localized_parts"][1]
        goodbye_values, goodbye_report = format_dialogue_mapping(
            source_document, goodbye_local, advances, **common
        )
        if set(goodbye_values) != {goodbye_id, tail_id}:
            raise ValueError("Round-52 $04E7 goodbye serialization shape changed")
        goodbye_values[goodbye_id] = TRANSLATION_CLEAR + goodbye_values[goodbye_id]
        translations.update(goodbye_values)
        subreports.append(goodbye_report)

    return translations, {
        "event_id": key[0],
        "snes_ids": list(snes_ids),
        "android_ids": list(key[2]),
        "confidence": mapping.get("confidence"),
        "source_display": mapping.get("source_display", ""),
        "android_french_raw": mapping.get("french_display", ""),
        "round52_exact_structural_distribution": True,
        "round52_strategy": expected["strategy"],
        "android_identity_unchanged": True,
        "stock_bridge_commands_unchanged": True,
        "note": expected["note"],
        "distributed_french_parts": list(expected["localized_parts"]),
        "subreports": subreports,
        "formatted_entries": [
            {"id": text_id, "text": translations[text_id]}
            for text_id in translations
        ],
    }


# Round 54 exact recoveries from already-proven Android identities. These are
# event-specific serialization rules only; no generic matcher/formatter is widened.
DIALOGUE_ROUND54_STRUCTURAL_RECOVERIES = {
    ("0040", ("C9:0F75",), (681,)): {
        "android_en": "%S(1,0): Okay! You can call me %S(1,0)!",
        "android_fr": "Moi, c'est %S(1,0) !",
        "window": (
            ("command", "PLAYER_NAME", "01"),
            ("text", "C9:0F75", ":Okay!\n You can call me "),
            ("command", "PLAYER_NAME", "01"),
            ("text", "C9:0F8F", "!"),
            ("command", "WAIT", "00"),
        ),
        "values": {"C9:0F75": " : Moi, c'est ", "C9:0F8F": " !"},
        "strategy": "preserve_two_stock_player_name_commands",
        "note": "Keep both stock PLAYER_NAME(1) commands; serialize only the official French literals around the second name.",
    },
    ("0041", ("C9:0FF1", "C9:1011"), (625,)): {
        "android_en": "%S(2,0)?\nWhat kinda name is that? Like, ah,\nnice to meet ya!_",
        "android_fr": "%S(2,0)... Bof, drôle de nom. Enfin, pourquoi pas,_",
        "window": (
            ("command", "PLAYER_NAME", "02"),
            ("text", "C9:0FEE", ":"),
            ("command", "PLAYER_NAME", "02"),
            ("text", "C9:0FF1", "? What kinda\n name is that?\n"),
            ("command", "OP_38", "01"),
            ("command", "OP_10", "42"),
            ("text", "C9:1011", " Like, ah, nice to meet ya!"),
            ("command", "WAIT", "00"),
        ),
        "values": {"C9:0FF1": "...\nBof, drôle de nom.\n", "C9:1011": "Enfin, pourquoi pas,"},
        "strategy": "split_fr_at_exact_stock_action_subevent_bridge",
        "note": "Split at the complete French sentence boundary on the unchanged OP_38 01 + OP_10 42 bridge.",
    },
    ("013A", ("C9:4094", "C9:40D7"), (848,)): {
        "android_en": "It will grow and regain its power just like your Mana Sword. There must be more weapons like this spear in the world. Find them!",
        "android_fr": "Rusalka : Tout comme l\'Épée, elle gagnera en puissance à mesure que tu l\'utiliseras.",
        "window": (
            ("text", "C9:4094", " It will grow and regain\n it\'s power just like your\n Mana Sword."),
            ("command", "WAIT", "00"),
            ("command", "TEXT_CLEAR", ""),
            ("text", "C9:40D7", " There must be more weapons\n like this spear in the\n world. Find them!"),
            ("command", "WAIT", "00"),
            ("command", "TEXT_CLEAR", ""),
        ),
        "values": {
            "C9:4094": "Rusalka : Tout comme l\'Épée, elle\ngagnera en puissance à mesure que\ntu l\'utiliseras."
        },
        "strategy": "serialize_android_fr_first_sentence_only_keep_omitted_snes_sentence_stock",
        "note": "Android 848 identifies both SNES sentences, but official FR translates only the first. Serialize the complete FR payload on the first stock carrier and leave C9:40D7 stock because Android FR omits that instruction.",
    },
    ("0592", ("CA:750D",), (1030,)): {
        "android_en": "You've got to take me there!",
        "android_fr": "Faut que tu me ramènes là-bas !",
        "window": (
            ("text", "CA:74E5", " We live in the Upper Land\n forest!"),
            ("command", "WAIT", "18"),
            ("command", "OP_32", "03 C0"),
            ("text", "CA:750D", " You've got\n to take me there!"),
            ("command", "WAIT", "00"),
            ("command", "TEXT_CLEAR", ""),
            ("text", "CA:752E", " I'll let you hang out with\n me until we arrive!\n"),
        ),
        "values": {"CA:750D": "\nFaut que tu me ramènes là-bas !"},
        "strategy": "resume_fr_on_available_third_line_after_wait18",
        "note": "Use the available third physical line after stock WAIT $18; keep the following stock WAIT $00 + TEXT_CLEAR. Android 1031 remains deferred.",
    },
}

DIALOGUE_ROUND54_ANDROID_FR_OMISSION_PARTIALS = {
    "013A": ("C9:40D7",),
}

DIALOGUE_ROUND54_NONSEMANTIC_ANDROID_SUPPLEMENTS = {
    "0559": {
        "android_id": 2146,
        "android_en": "%S(0,0): %S(1,0)...",
        "android_fr": "%S(0,0) : %S(1,0)...",
        "window": (
            ("command", "TEXT_CLEAR", ""),
            ("command", "PLAYER_NAME", "00"),
            ("text", "CA:6741", ":"),
            ("command", "PLAYER_NAME", "01"),
            ("text", "CA:6744", "...\n"),
            ("command", "PLAYER_NAME", "02"),
            ("text", "CA:674A", ":...Let's go..."),
        ),
        "values": {"CA:6741": " : ", "CA:6744": "...\n"},
        "note": "Android 2146 maps exactly onto stock PLAYER_NAME(0)/(1) plus punctuation-only carriers. Android 2147 remains deferred because FR introduces a second PLAYER_NAME(1) absent from the stock stream.",
    },
}

def _round54_token_signature(token: dict) -> tuple[str, str, str]:
    if token.get("type") == "text":
        return ("text", token.get("id", ""), token.get("source", ""))
    if token.get("type") == "command":
        return ("command", token.get("name", ""), token.get("args", ""))
    return (token.get("type", ""), token.get("code", ""), token.get("args", ""))

def _round54_require_unique_window(event: dict, window: tuple, label: str) -> None:
    tokens = event.get("tokens", [])
    count = 0
    for offset in range(len(tokens) - len(window) + 1):
        if tuple(_round54_token_signature(t) for t in tokens[offset:offset + len(window)]) == window:
            count += 1
    if count != 1:
        raise ValueError(f"Round-54 {label} canonical token window changed")

def _format_round54_structural_recovery(source_document: dict, mapping: dict) -> tuple[dict[str, str], dict]:
    key = (mapping.get("event_id"), tuple(mapping.get("snes_ids", [])), tuple(mapping.get("android_ids", [])))
    expected = DIALOGUE_ROUND54_STRUCTURAL_RECOVERIES.get(key)
    if expected is None:
        raise ValueError("Round-54 structural recovery is not allow-listed")
    if mapping.get("android_namespace", "scrtxt") != "scrtxt":
        raise ValueError("Round-54 structural recovery requires scrtxt identity")
    if normalize_android_prose(mapping.get("android_english_display", "")).strip() != normalize_android_prose(expected["android_en"]).strip():
        raise ValueError(f"Round-54 ${key[0]} Android-English context changed")
    if normalize_android_french(mapping.get("french_display", "")).strip() != normalize_android_french(expected["android_fr"]).strip():
        raise ValueError(f"Round-54 ${key[0]} Android-French payload changed")
    by_id, by_event = event_text_index(source_document)
    event = by_event.get(key[0])
    if event is None:
        raise ValueError(f"Round-54 event ${key[0]} missing")
    _round54_require_unique_window(event, tuple(expected["window"]), f"${key[0]}")
    for text_id in expected["values"]:
        if text_id not in by_id or by_id[text_id].get("event_id") != key[0]:
            raise ValueError(f"Round-54 ${key[0]} output carrier {text_id} changed")
    values = dict(expected["values"])
    return values, {
        "event_id": key[0], "snes_ids": list(key[1]), "android_ids": list(key[2]),
        "confidence": mapping.get("confidence"), "source_display": mapping.get("source_display", ""),
        "android_english_display": mapping.get("android_english_display", ""),
        "android_french_raw": mapping.get("french_display", ""),
        "round54_exact_structural_recovery": True, "round54_strategy": expected["strategy"],
        "android_identity_unchanged": True, "stock_commands_unchanged": True,
        "note": expected["note"],
        "formatted_entries": [{"id": k, "text": v} for k, v in values.items()],
    }

def _apply_round54_nonsemantic_android_supplement(event: dict, translations: dict[str, str], *, english: dict[int, str], french: dict[int, str]) -> list[dict]:
    expected = DIALOGUE_ROUND54_NONSEMANTIC_ANDROID_SUPPLEMENTS.get(event.get("event_id"))
    if expected is None:
        return []
    android_id = expected["android_id"]
    if normalize_android_prose(english[android_id]).strip() != normalize_android_prose(expected["android_en"]).strip():
        raise ValueError(f"Round-54 ${event['event_id']} Android-English nonsemantic bridge changed")
    if normalize_android_french(french[android_id]).strip() != normalize_android_french(expected["android_fr"]).strip():
        raise ValueError(f"Round-54 ${event['event_id']} Android-French nonsemantic bridge changed")
    _round54_require_unique_window(event, tuple(expected["window"]), f"${event['event_id']} Android {android_id}")
    for text_id, value in expected["values"].items():
        if text_id in translations:
            raise ValueError(f"Round-54 ${event['event_id']} carrier {text_id} already translated")
        translations[text_id] = value
    return [{
        "event_id": event["event_id"], "android_id": android_id,
        "strategy": "exact_android_dynamic_name_bridge_on_nonsemantic_snes_carriers",
        "semantic_alignment_count_changed": False, "stock_player_name_commands_unchanged": True,
        "note": expected["note"],
        "formatted_entries": [{"id": k, "text": v} for k, v in expected["values"].items()],
    }]



def _apply_round67_user_reviewed_scene_redistributions(
    event: dict,
    translations: dict[str, str],
    *,
    english: dict[int, str],
    french: dict[int, str],
    layout_deferred_ids: list[str],
    missing_ids: list[str],
) -> tuple[list[dict], set[str]]:
    """Apply exact Round-67 user-reviewed cross-carrier scene layouts.

    These are presentation redistributions only. They do not create new Android
    identity. The $04E1 block uses Android FR 3252-3257 across the three
    surviving SNES carriers after the already validated CA:2C84 page suppression.
    The $04E2 reaction deliberately redistributes Android FR 1281 across two SNES
    carriers; translated-only command metadata rebinds both pieces to PLAYER_NAME(2)
    and omits Android FR 1280 per explicit user instruction.
    """
    event_id = event.get("event_id")
    reports: list[dict] = []
    resolved_missing: set[str] = set()

    if event_id == "04E1":
        expected_fr = {
            3252: "Mon corps actuel est sur le point de se corrompre. Il me faut un nouveau corps...",
            3253: "Un être humain ordinaire est incapable de contenir longtemps mon énergie. Il me faut donc le corps d'un être d'exception.",
            3254: "Or, une ou deux fois par siècle, un humain naît avec le Sang des ténèbres dans les veines.",
            3255: "Lorsque je me transfère dans ce corps exceptionnel, mon pouvoir se trouve décuplé. \nUn corps... comme celui de Durac !",
            3256: "Son pouvoir maléfique a dû être scellé quand il était jeune... Il n'en est devenu que plus droit et juste !",
            3257: "Avec mon nouveau corps et la Forteresse de Mana, je forgerai un monde à mon image !",
        }
        # read_scrtxt preserves one source newline in 3255; compare normalized prose.
        for android_id, expected in expected_fr.items():
            if normalize_android_french(french.get(android_id, "")).strip() != normalize_android_french(expected).strip():
                raise ValueError(f"Round-67 $04E1 Android FR {android_id} changed")
        expected_en_ids = {3252, 3253, 3254, 3255, 3256, 3257}
        if any(not english.get(i, "").strip() for i in expected_en_ids):
            raise ValueError("Round-67 $04E1 Android-English scene anchors changed")
        tokens = event.get("tokens", [])
        ids = [t.get("id") for t in tokens if t.get("type") == "text"]
        for required in ("CA:2BED", "CA:2C3A", "CA:2C84", "CA:2C93"):
            if required not in ids:
                raise ValueError(f"Round-67 $04E1 carrier {required} moved")
        if translations.get("CA:2C84") != "":
            raise ValueError("Round-67 $04E1 requires the validated empty CA:2C84 suppression")

        values = {
            "CA:2BED": (
                "Mon corps actuel est sur le point de\n"
                "se corrompre.\n"
                "Il me faut un nouveau corps..."
            ),
            "CA:2C3A": (
                "Un être humain ordinaire est incapable\n"
                "de contenir longtemps mon énergie.\f"
                "Il me faut donc le corps d'un être\n"
                "d'exception.\f"
                "Or, une ou deux fois par siècle, un\n"
                "humain naît avec le Sang des ténèbres\n"
                "dans les veines."
            ),
            "CA:2C93": (
                "Lorsque je me transfère dans ce corps\n"
                "exceptionnel, mon pouvoir se trouve\n"
                "décuplé.\f"
                "Un corps... comme celui de Durac !\f"
                "Son pouvoir maléfique a dû être scellé\n"
                "quand il était jeune... Il n'en est\n"
                "devenu que plus droit et juste !\f"
                "Avec mon nouveau corps et la\n"
                "Forteresse de Mana, je forgerai un\n"
                "monde à mon image !"
            ),
        }
        for text_id, value in values.items():
            if text_id in translations and translations[text_id] not in {"", value}:
                raise ValueError(f"Round-67 $04E1 would overwrite translated carrier {text_id}")
            translations[text_id] = value
        resolved_missing.update({"CA:2BED", "CA:2C3A"})
        layout_deferred_ids[:] = [x for x in layout_deferred_ids if x != "CA:2C93"]
        reports.append({
            "event_id": "04E1",
            "snes_ids": ["CA:2BED", "CA:2C3A", "CA:2C93"],
            "android_ids": [3252, 3253, 3254, 3255, 3256, 3257],
            "confidence": "user_reviewed_scene_redistribution",
            "semantic_alignment_count_changed": False,
            "stock_player_name_commands_unchanged": True,
            "round67_user_reviewed_scene_redistribution": True,
            "note": (
                "Use the complete official Android-FR Thanatos monologue across newly paginated "
                "surviving SNES carriers. CA:2C84 remains the separately validated suppressed page."
            ),
            "formatted_entries": [{"id": k, "text": v} for k, v in values.items()],
        })

    if event_id == "04E2":
        if normalize_android_french(french.get(1280, "")).strip() != normalize_android_french(
            "%S(1,0) : Quelle horreur ! C'est terrible !"
        ).strip():
            raise ValueError("Round-67 $04E2 Android FR 1280 changed")
        if normalize_android_french(french.get(1281, "")).strip() != normalize_android_french(
            "%S(2,0) : Non ! C'est pas possible ! Ils se sont sûrement échappés !"
        ).strip():
            raise ValueError("Round-67 $04E2 Android FR 1281 changed")
        # Android 1281 is entirely PLAYER_NAME(2). Canonical SNES has
        # PLAYER_NAME(1) before CA:32C5 and PLAYER_NAME(2) before CA:32D7; the
        # translated-only structural command override rebinds the first to 2 and
        # removes the redundant second speaker command. Keep the visible text
        # split exactly as requested by the user.
        values = {
            "CA:32C5": " : Non !\nC'est pas possible !\n",
            "CA:32D7": "Ils se sont sûrement échappés !",
        }
        for text_id, value in values.items():
            translations[text_id] = value
        layout_deferred_ids[:] = [x for x in layout_deferred_ids if x not in {"CA:32C5", "CA:32D7"}]
        reports.append({
            "event_id": "04E2",
            "snes_ids": ["CA:32C5", "CA:32D7"],
            "android_ids": [1280, 1281],
            "confidence": "user_reviewed_speaker_redistribution",
            "semantic_alignment_count_changed": False,
            "translated_player_name_resegmentation": True,
            "android_fr_1280_intentionally_omitted": True,
            "round67_user_reviewed_scene_redistribution": True,
            "note": (
                "User-directed Android-FR 1281 split: PLAYER_NAME(2) owns both carriers; "
                "the first stock PLAYER_NAME is rebound 1→2 and the redundant second 2 is omitted."
            ),
            "formatted_entries": [{"id": k, "text": v} for k, v in values.items()],
        })
    return reports, resolved_missing

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
    mapping, _round48_vocative_repair = _round48_without_android_only_vocative(
        source_document, mapping
    )
    mapping, _round49_speaker_label_repair = _round49_without_android_only_speaker_label(
        source_document, mapping
    )
    if (
        mapping.get("event_id") == DIALOGUE_ROUND49_SOUND_SEQUENCE["event_id"]
        and tuple(mapping.get("snes_ids", [])) == DIALOGUE_ROUND49_SOUND_SEQUENCE["snes_ids"]
        and tuple(mapping.get("android_ids", [])) == DIALOGUE_ROUND49_SOUND_SEQUENCE["android_ids"]
    ):
        return _format_round49_sound_sequence(source_document, mapping, advances)
    round62_key = (
        mapping.get("event_id"),
        tuple(mapping.get("snes_ids", [])),
        tuple(mapping.get("android_ids", [])),
    )
    if round62_key in {
        ("038D", ("C9:DAF5", "C9:DB09"), (1815, 1816)),
        ("03EA", ("C9:F04C", "C9:F07D"), (2354,)),
        ("04E2", ("CA:31EE", "CA:3218"), (1275, 1276)),
        ("04E3", ("CA:36C7",), (1384, 1385)),
    }:
        return _format_round62_user_reviewed_redistribution(source_document, mapping)
    round52_key = (
        mapping.get("event_id"),
        tuple(mapping.get("snes_ids", [])),
        tuple(mapping.get("android_ids", [])),
    )
    if round52_key in DIALOGUE_ROUND52_STRUCTURAL_DISTRIBUTIONS:
        return _format_round52_structural_distribution(source_document, mapping, advances)
    if round52_key in DIALOGUE_ROUND54_STRUCTURAL_RECOVERIES:
        return _format_round54_structural_recovery(source_document, mapping)
    common = {
        "allow_one_extra_page": True,
        "use_physical_page_capacity": True,
        "prefer_semantic_line_breaks": prefer_semantic_line_breaks,
        "allow_two_extra_pages": True,
    }
    primary_message: str | None = None
    if mapping.get("relation") == "user_validated_stock_english_override":
        return _format_user_validated_stock_english_override(source_document, mapping)
    if mapping.get("relation") == "called_prefix_android_merge_suffix":
        return _format_called_prefix_android_merge_suffix(
            source_document, mapping, advances,
            prefer_semantic_line_breaks=prefer_semantic_line_breaks,
        )
    if mapping.get("relation") in {"round46_systxt_chest_money", "round46_systxt_chest_localization_override"}:
        return _format_round46_system_chest(
            source_document, mapping, advances,
            prefer_semantic_line_breaks=prefer_semantic_line_breaks,
        )
    if mapping.get("relation") in {"round45_watts_shortcut_redistribution", "round45_girl_name_resegmentation"}:
        return _format_round45_reviewed_redistribution(source_document, mapping)
    if mapping.get("relation") in {
        "round44_jehk_out_with_return_layout",
        "round44_player_name_followup_layout",
        "round44_parameterized_inn_price_identity",
    }:
        return _format_round44_reviewed_redistribution(source_document, mapping)
    if mapping.get("relation") in {
        "round43_player_name_resegmentation",
        "round43_shared_branch_prefix_redistribution",
        "round43_shared_magic_suffix_layout",
        "round43_weapon_orb_prefix",
        "round43_weapon_orb_suffix",
        "round43_gameover_plural_slot",
        "round43_gameover_dynamic_frame",
    }:
        return _format_round43_reviewed_redistribution(source_document, mapping)
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
        lambda: _format_mapping_across_single_text_x(
            source_document,
            mapping,
            advances,
            french=french,
            prefer_semantic_line_breaks=prefer_semantic_line_breaks,
        ),
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
        lambda: _format_mapping_across_sound_effect_action_boundary(
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



def _apply_round48_0127_pagination(event: dict, translations: dict[str, str]) -> list[dict]:
    """Apply the exact reviewed multi-boundary pagination for event $0127.

    Android FR expands three consecutive conversation windows beyond the stock
    rolling three-line box.  The repair keeps every stock actor action, timed
    WAIT and PLAYER_NAME command in place:

    * split the first player thought at an existing complete sentence;
    * after the stock WAIT $08, clear the retained lines before Rusalka speaks
      (``\v`` = TEXT_CLEAR only, so no second interactive WAIT is invented);
    * split the final dynamic-player line after its complete ``Quoi ?!``
      sentence, after the existing PLAYER_NAME has already rendered.

    The exact source token indexes and exact formatted strings are gates.  Any
    future wording/structure change disables the repair loudly rather than
    moving a command implicitly.
    """
    if event.get("event_id") != "0127":
        return []
    tokens = event.get("tokens", [])
    expected_structure = {
        18: ("command", "TEXT_OPEN", ""),
        19: ("command", "PLAYER_NAME", "00"),
        20: ("text", "C9:3A8C", None),
        21: ("command", "OP_32", "00 D0"),
        22: ("command", "OP_32", "05 80"),
        23: ("text", "C9:3AA1", None),
        24: ("command", "WAIT", "00"),
        25: ("command", "TEXT_CLEAR", ""),
        29: ("text", "C9:3AC3", None),
        30: ("command", "WAIT", "08"),
        31: ("text", "C9:3AD8", None),
        32: ("command", "OP_32", "06 00"),
        33: ("text", "C9:3ADC", None),
        34: ("command", "WAIT", "00"),
        35: ("text", "C9:3B01", None),
        36: ("command", "OP_32", "05 44"),
        37: ("text", "C9:3B05", None),
        38: ("command", "OP_34", "00 A4"),
        39: ("command", "PLAYER_NAME", "00"),
        40: ("text", "C9:3B23", None),
    }
    if len(tokens) <= max(expected_structure):
        raise ValueError("Round-48 $0127 canonical token structure shortened")
    for index, (kind, identity, args) in expected_structure.items():
        token = tokens[index]
        if token.get("type") != kind:
            raise ValueError(f"Round-48 $0127 token {index} type changed")
        if kind == "text":
            if token.get("id") != identity:
                raise ValueError(f"Round-48 $0127 token {index} text carrier changed")
        else:
            if token.get("name") != identity or token.get("args", "") != args:
                raise ValueError(f"Round-48 $0127 token {index} command changed")

    expected = {
        "C9:3A8C": " : Où est Rusalka ? Hum...\nbizarre, il n'y a aucune vieille dame\nici... Demandons à cette fille.\n",
        "C9:3ADC": "Rusalka, je suis heureux de vous\nrevoir.",
        "C9:3B23": " : Quoi ?!\nC'est elle, la prêtresse âgée de 200\nans ?!",
    }
    if not all(text_id in translations for text_id in expected):
        return []
    # The 216px formatter may already have reflowed/paginated this scene.
    # In that case do not force the historical 240px byte layout back onto it;
    # the generic simulator gate below will validate the newly generated form.
    if any(translations[text_id] != value for text_id, value in expected.items()):
        return []

    translations["C9:3A8C"] = expected["C9:3A8C"].replace(
        "ici... Demandons à cette fille.\n",
        "ici...\fDemandons à cette fille.\n",
    )
    translations["C9:3ADC"] = "\v" + expected["C9:3ADC"]
    translations["C9:3B23"] = expected["C9:3B23"].replace(
        " : Quoi ?!\n", " : Quoi ?!\f"
    )
    return [
        {
            "strategy": "round48_exact_multi_boundary_pagination",
            "event_id": "0127",
            "sentence_page_break_after": "ici...",
            "clear_after_existing_wait08_before": "C9:3ADC",
            "sentence_page_break_after_dynamic_player_line": "Quoi ?!",
            "player_name_commands_unchanged": True,
            "stock_wait08_unchanged": True,
            "added_interactive_wait_count": 2,
            "added_text_clear_only_count": 1,
        }
    ]



def _apply_round49_04e9_wait00_clears(event: dict, translations: dict[str, str]) -> list[dict]:
    """Clear two exact full-page Luka/Jema paragraphs after existing WAIT $00.

    In $04E9, Android FR expands the consecutive Luka explanation paragraphs to
    three physical lines each. The stock stream already pauses with WAIT $00
    between them, but WAIT retains the live cursor. Add TEXT_CLEAR only after
    those existing pauses so the next three-line paragraph starts on a fresh
    page. No interactive wait is added and every stock command remains in place.
    """
    if event.get("event_id") != "04E9":
        return []
    tokens = event.get("tokens", [])
    expected_structure = {
        6: ("text", "CA:46F5", None),
        7: ("command", "WAIT", "00"),
        8: ("text", "CA:4745", None),
        9: ("command", "WAIT", "00"),
        10: ("text", "CA:4797", None),
        11: ("command", "WAIT", "00"),
        12: ("text", "CA:47E7", None),
    }
    if len(tokens) <= max(expected_structure):
        raise ValueError("Round-49 $04E9 canonical token structure shortened")
    for index, (kind, identity, args) in expected_structure.items():
        token = tokens[index]
        if token.get("type") != kind:
            raise ValueError(f"Round-49 $04E9 token {index} type changed")
        if kind == "text":
            if token.get("id") != identity:
                raise ValueError(f"Round-49 $04E9 token {index} carrier changed")
        elif token.get("name") != identity or token.get("args", "") != args:
            raise ValueError(f"Round-49 $04E9 token {index} command changed")

    expected = {
        "CA:4745": "Le pouvoir de Mana s'affaiblit.\nC'est sans doute pour cela que ce\ngarçon a pu retirer l'Épée sacrée.",
        "CA:4797": "L'équilibre de Mana s'en est trouvé\ntroublé, et les monstres ont commencé\nà s'agiter.",
    }
    if not all(text_id in translations for text_id in expected):
        return []
    for text_id, value in expected.items():
        if translations[text_id] != value:
            raise ValueError(f"Round-49 $04E9 formatted carrier {text_id} changed")

    repairs = []
    for text_id in ("CA:4745", "CA:4797"):
        translations[text_id] = "\v" + expected[text_id]
        repairs.append({
            "text_id": text_id,
            "strategy": "clear_after_existing_wait00_before_full_page_paragraph",
            "existing_wait00_unchanged": True,
            "added_interactive_wait_count": 0,
            "added_text_clear_only_count": 1,
        })
    return repairs


def _apply_round50_01ce_choice_page_clear(event: dict, translations: dict[str, str]) -> list[dict]:
    """Start the exact $01CE donation-choice unit on a fresh page.

    Android EN 536/537/538 is the determinate prompt/Yes/No triplet and the
    reviewed Round-50 mapping splits 536/537 at the stock CHOICE_BEGIN.  The
    stock event already has WAIT $00 before a one-byte newline carrier at
    C9:7824; WAIT does not advance the live cursor.  Replace only that empty
    layout carrier with TEXT_CLEAR so the translated three-line prompt starts
    at the top of a fresh page.  Every money/choice command and the existing
    WAIT $00 remain byte-for-byte in their canonical position.
    """
    if event.get("event_id") != "01CE":
        return []

    tokens = event.get("tokens", [])
    expected_structure = {
        82: ("text", "C9:7808", None),
        83: ("command", "WAIT", "00"),
        84: ("text", "C9:7824", None),
        85: ("command", "MONEY_OPEN", ""),
        86: ("command", "MONEY_PRINT", ""),
        87: ("text", "C9:7827", None),
        88: ("command", "CHOICE_BEGIN", ""),
        89: ("command", "CHOICE_OPTION", "04"),
        90: ("text", "C9:7856", None),
        91: ("command", "CHOICE_OPTION", "0B"),
        92: ("text", "C9:785C", None),
        93: ("command", "CHOICE_END", ""),
    }
    if len(tokens) <= max(expected_structure):
        raise ValueError("Round-50 $01CE canonical token structure shortened")
    for index, (kind, identity, args) in expected_structure.items():
        token = tokens[index]
        if token.get("type") != kind:
            raise ValueError(f"Round-50 $01CE token {index} type changed")
        if kind == "text":
            if token.get("id") != identity:
                raise ValueError(f"Round-50 $01CE token {index} carrier changed")
        elif token.get("name") != identity or token.get("args", "") != args:
            raise ValueError(f"Round-50 $01CE token {index} command changed")

    if tokens[84].get("source") != "\n":
        raise ValueError("Round-50 $01CE C9:7824 is no longer the stock newline-only carrier")

    required_translations = {"C9:7808", "C9:7827", "C9:7856", "C9:785C"}
    if not required_translations.issubset(translations):
        return []
    if "C9:7824" in translations:
        raise ValueError("Round-50 $01CE C9:7824 unexpectedly already translated")

    translations["C9:7824"] = TRANSLATION_CLEAR
    return [
        {
            "text_id": "C9:7824",
            "strategy": "exact_newline_only_carrier_to_clear_after_existing_wait00",
            "existing_wait00_unchanged": True,
            "money_commands_unchanged": True,
            "choice_commands_unchanged": True,
            "added_interactive_wait_count": 0,
            "added_text_clear_only_count": 1,
            "android_identity_added": False,
        }
    ]


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



def _apply_reviewed_choice_layout_recipe(
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
    recipe: dict,
) -> tuple[dict[str, str], list[dict], object, list[dict], list[dict], list[dict]]:
    """Reapply one reviewed Round-72 choice presentation decision.

    The recipe contains only canonical event/carrier identities.  No French
    prose is stored here.  If restoring the canonical choice-row newline would
    otherwise force a fresh page, retry only the mapped opening prompt with the
    already-supported compact wrapper before restoring the row.  Finally strip
    the exact canonical outer parentheses and resimulate.  Later CHOICE_OPTION
    anchor repair remains the responsibility of the ordinary generic pass.
    """
    from shared.dialogue_simulator import simulate_event

    event_id = event.get("event_id")
    if recipe.get("event_id") != event_id:
        raise ValueError(f"Reviewed choice-layout recipe/event mismatch: {event_id}")

    original_translations = dict(translations)
    original_reports = [dict(report) for report in reports]

    row_translations, row_reports, row_simulation, row_repairs = (
        _try_restore_stock_choice_row_prefix(
            base_rom=base_rom,
            event=event,
            translations=translations,
            reports=reports,
            font=font,
            simulation=simulation,
        )
    )
    compact_repairs: list[dict] = []

    # A reviewed stripped row needs only the canonical NEWLINE before the first
    # option, not a new page containing an opening parenthesis.  When semantic
    # wrapping made the prompt three lines and therefore forced the helper onto
    # a fresh page, retry that one Android-backed mapping with the compact VWF
    # wrapper.  This is deterministic source reflow, not a text override.
    if row_repairs and any(
        repair.get("strategy") == "restore_stock_choice_row_suffix_on_fresh_page"
        for repair in row_repairs
    ):
        opening_id = recipe["opening_text_id"]
        owner = [mapping for mapping in event_mappings if opening_id in mapping.get("snes_ids", [])]
        if len(owner) == 1:
            mapping = owner[0]
            try:
                compact_values, compact_report = _format_mass_mapping(
                    source_document,
                    mapping,
                    advances,
                    base_rom=base_rom,
                    french=french,
                    prefer_semantic_line_breaks=False,
                )
                compact_values, compact_report, _ = _collapse_trailing_page_break_into_stock_transition(
                    source_document, mapping, compact_values, compact_report
                )
            except ValueError:
                compact_values = {}
                compact_report = None

            if compact_values and compact_report is not None:
                compact_translations = dict(original_translations)
                compact_translations.update(compact_values)
                compact_reports: list[dict] = []
                replaced = False
                for report in original_reports:
                    if (
                        report.get("snes_ids") == mapping.get("snes_ids")
                        and report.get("android_ids") == mapping.get("android_ids")
                    ):
                        compact_reports.append(compact_report)
                        replaced = True
                    else:
                        compact_reports.append(report)
                if replaced:
                    try:
                        compact_simulation = simulate_event(
                            base_rom,
                            event,
                            compact_translations,
                            font=font,
                            player_names={0: "000000000", 1: "000000000", 2: "000000000"},
                        )
                    except ValueError:
                        compact_simulation = None
                    if compact_simulation is not None:
                        (
                            compact_row_translations,
                            compact_row_reports,
                            compact_row_simulation,
                            compact_row_repairs,
                        ) = _try_restore_stock_choice_row_prefix(
                            base_rom=base_rom,
                            event=event,
                            translations=compact_translations,
                            reports=compact_reports,
                            font=font,
                            simulation=compact_simulation,
                        )
                        if compact_row_repairs and not any(
                            repair.get("strategy") == "restore_stock_choice_row_suffix_on_fresh_page"
                            for repair in compact_row_repairs
                        ):
                            row_translations = compact_row_translations
                            row_reports = compact_row_reports
                            row_simulation = compact_row_simulation
                            row_repairs = compact_row_repairs
                            compact_repairs = [{
                                "event_id": event_id,
                                "strategy": "compact_android_prompt_before_reviewed_choice_row",
                                "snes_ids": list(mapping.get("snes_ids", [])),
                                "android_ids": list(mapping.get("android_ids", [])),
                                "localized_prose_unchanged": True,
                            }]

    stripped, decoration_repair = _strip_canonical_choice_decoration(
        event, row_translations
    )
    if decoration_repair is None:
        raise ValueError(f"Reviewed choice-layout recipe ${event_id} no longer matches canonical decoration")
    if (
        decoration_repair.get("opening_text_id") != recipe.get("opening_text_id")
        or decoration_repair.get("closing_text_id") != recipe.get("closing_text_id")
    ):
        raise ValueError(f"Reviewed choice-layout recipe ${event_id} resolved different carriers")

    stripped_reports = _choice_decoration_reports(
        row_reports, stripped, decoration_repair
    )
    stripped_simulation = simulate_event(
        base_rom,
        event,
        stripped,
        font=font,
        player_names={0: "000000000", 1: "000000000", 2: "000000000"},
    )
    decoration_repair = dict(decoration_repair)
    decoration_repair["reviewed_layout_recipe"] = True
    return (
        stripped,
        stripped_reports,
        stripped_simulation,
        row_repairs,
        [decoration_repair],
        compact_repairs,
    )


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

    # If restoring the canonical NEWLINE + '(' would create a fourth visible
    # line before the choice, reuse the same proven choice-row boundary as a
    # generated page transition instead. This is still source-derived: only the
    # stock suffix is restored and no printable Android-FR prose changes.
    if (
        repair is not None
        and repair.get("strategy") == "restore_stock_choice_row_suffix"
        and any(
            issue.code == "UNPAUSED_SCROLL"
            and issue.severity in {"error", "warning"}
            for issue in candidate_simulation.issues
        )
    ):
        suffix = repair["restored_suffix"]
        page_suffix = "\f" + suffix.lstrip("\n")
        page_candidate = dict(translations)
        page_candidate[text_id] = current.rstrip(" ") + page_suffix
        try:
            page_simulation = simulate_event(
                base_rom, event, page_candidate, font=font,
                player_names={0: "000000000", 1: "000000000", 2: "000000000"},
            )
        except ValueError:
            page_simulation = None
        if page_simulation is not None:
            candidate = page_candidate
            candidate_simulation = page_simulation
            repair = {
                "strategy": "restore_stock_choice_row_suffix_on_fresh_page",
                "text_id": text_id,
                "restored_suffix": suffix,
                "generated_page_transition": True,
                "choice_commands_unchanged": True,
            }

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
    `vwf_dialogues` and the stock highlight then consume the same moved coordinate,
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



def _simulation_blocking_score(simulation) -> tuple[int, int, int]:
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
    return (len(blocking) + wraps, len(blocking), wraps)


def _try_single_carrier_boundary_newline(
    *,
    base_rom: bytes,
    event: dict,
    translations: dict[str, str],
    font,
    structural_command_overrides: dict[int, tuple[str, str] | None] | None = None,
) -> tuple[dict[str, str], object | None, list[dict]]:
    """Try one deterministic presentation NEWLINE at a translated carrier edge.

    This is a generic layout candidate, never a prose exception. Candidate order
    follows canonical event token order and tries appending to the preceding
    carrier before prepending to the following carrier. A candidate is accepted
    only when the independent simulator reports zero errors, zero warnings and
    zero implicit wraps. Existing control bytes and carrier assignments remain
    otherwise unchanged.
    """
    from shared.dialogue_simulator import simulate_event

    if not translations:
        return translations, None, []

    token_ids = [
        token.get("id")
        for token in event.get("tokens", [])
        if token.get("type") in {"text", "ending_text"}
        and token.get("id") in translations
    ]
    if len(token_ids) < 2:
        return translations, None, []

    player_names = {0: "000000000", 1: "000000000", 2: "000000000"}
    # A boundary is defined between consecutive translated carriers in canonical
    # token order. The commands between them are intentionally left untouched.
    for index in range(len(token_ids) - 1):
        previous_id = token_ids[index]
        next_id = token_ids[index + 1]
        previous = translations[previous_id]
        following = translations[next_id]
        candidates = []
        if previous and not previous.endswith(("\n", "\v", "\f")):
            candidates.append(("append", previous_id, previous + "\n"))
        if following and not following.startswith(("\n", "\v", "\f")):
            candidates.append(("prepend", next_id, "\n" + following))
        for mode, text_id, replacement in candidates:
            candidate = dict(translations)
            candidate[text_id] = replacement
            try:
                simulation = simulate_event(
                    base_rom,
                    event,
                    candidate,
                    font=font,
                    player_names=player_names,
                    structural_command_overrides=structural_command_overrides,
                )
            except ValueError:
                continue
            if _simulation_blocking_score(simulation)[0] != 0:
                continue
            return candidate, simulation, [{
                "strategy": "single_carrier_boundary_newline",
                "boundary_after_id": previous_id,
                "boundary_before_id": next_id,
                "modified_id": text_id,
                "mode": mode,
                "semantic_payload_changed": False,
            }]

    return translations, None, []


def _automatic_layout_search_score(simulation) -> tuple[int, int, int, int]:
    """Rank rejected layouts for the bounded source-derived fallback search."""
    if simulation is None:
        return (999, 9999, 999, 999)
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
    width_excess = 0
    unpaused_scroll = 0
    for issue in blocking:
        match = re.search(r"Line advance is (\d+)px \(> (\d+)px", issue.message)
        if match:
            width_excess += int(match.group(1)) - int(match.group(2))
        if issue.code == "UNPAUSED_SCROLL":
            unpaused_scroll += 1
    return (len(blocking) + wraps, width_excess, unpaused_scroll, len(blocking))


def _try_unpaused_scroll_page_repairs(
    *,
    base_rom: bytes,
    event: dict,
    translations: dict[str, str],
    font,
    structural_command_overrides: dict[int, tuple[str, str] | None] | None = None,
) -> tuple[dict[str, str], object | None, list[dict]]:
    """Repair pure pagination overflow with deterministic generated page breaks.

    This fallback is intentionally narrow. It runs only when every blocking
    simulator issue is ``UNPAUSED_SCROLL``. It tests a generated WAIT $00 +
    TEXT_CLEAR marker (``\f`` in translation markup) at ordinary word
    boundaries inside already-multiline translated carriers, and keeps only a
    candidate that *strictly* reduces the blocking score. Printable Android-FR
    payload and carrier ownership are unchanged. The process repeats at most
    once per initial scroll defect and returns only a completely clean event.

    Restricting candidates to multiline carriers keeps very long scenes
    tractable while targeting the actual cause: four visible lines accumulated
    between pauses. If no strictly improving boundary exists, the event remains
    rejected for later review rather than guessing.
    """
    from shared.dialogue_simulator import simulate_event

    player_names = {0: "000000000", 1: "000000000", 2: "000000000"}
    try:
        simulation = simulate_event(
            base_rom, event, translations, font=font, player_names=player_names,
            structural_command_overrides=structural_command_overrides,
        )
    except ValueError:
        return translations, None, []

    blocking = [
        issue for issue in simulation.issues
        if issue.severity in {"error", "warning"}
    ]
    if not blocking or any(issue.code != "UNPAUSED_SCROLL" for issue in blocking):
        return translations, None, []

    current = dict(translations)
    current_simulation = simulation
    current_score = _automatic_layout_search_score(simulation)
    repairs: list[dict] = []
    max_steps = len(blocking)

    canonical_ids = [
        token.get("id")
        for token in event.get("tokens", [])
        if token.get("type") in {"text", "ending_text"}
        and token.get("id") in current
    ]
    canonical_ids.extend(sorted(set(current) - set(canonical_ids)))

    for step in range(1, max_steps + 1):
        best = None
        for carrier_order, text_id in enumerate(canonical_ids):
            value = current[text_id]
            # A page break can only solve a rolling four-line defect if the
            # carrier contributes multiple visible lines. This also prevents a
            # combinatorial scan across every word in a long scripted scene.
            if value.count("\n") < 2:
                continue
            for match in reversed(list(re.finditer(r"(?<=\S) (?=[^\s:;!?])", value))):
                pos = match.start()
                replacement = value[:pos] + "\f" + value[pos + 1:]
                candidate = dict(current)
                candidate[text_id] = replacement
                try:
                    candidate_simulation = simulate_event(
                        base_rom, event, candidate, font=font,
                        player_names=player_names,
                        structural_command_overrides=structural_command_overrides,
                    )
                except ValueError:
                    continue
                candidate_score = _automatic_layout_search_score(candidate_simulation)
                if candidate_score >= current_score:
                    continue
                # Stable tie-break: best simulator score, canonical carrier,
                # then latest word boundary to preserve as much preceding layout
                # as possible.
                key = (candidate_score, carrier_order, -pos)
                if best is None or key < best[0]:
                    best = (
                        key, candidate, candidate_simulation,
                        {
                            "strategy": "unpaused_scroll_word_page_boundary",
                            "text_id": text_id,
                            "source_offset": pos,
                            "step": step,
                            "semantic_payload_changed": False,
                        },
                    )
        if best is None:
            break
        _, current, current_simulation, repair = best
        current_score = _automatic_layout_search_score(current_simulation)
        repairs.append(repair)
        if _simulation_blocking_score(current_simulation)[0] == 0:
            return current, current_simulation, repairs

    return translations, None, []


def _try_source_derived_layout_search(
    *,
    base_rom: bytes,
    event: dict,
    translations: dict[str, str],
    font,
    structural_command_overrides: dict[int, tuple[str, str] | None] | None = None,
    max_steps: int = 3,
    max_translated_carriers: int = 40,
) -> tuple[dict[str, str], object | None, list[dict]]:
    """Search a tiny deterministic layout-only neighborhood around Android FR.

    The search never changes printable characters or carrier ownership. It may
    replace one inter-word space by NEWLINE, or one existing sentence/word
    boundary by the already-supported generated WAIT $00 + TEXT_CLEAR page
    marker. Sentence page boundaries are preferred; arbitrary word-boundary page
    breaks are considered only on the final search step. At each step the whole
    event is independently simulated, and the best non-worsening candidate is
    retained. A result is returned only if the final event is completely clean.

    The carrier-count bound deliberately keeps very large scripted scenes out of
    this brute-force fallback; those need a more structural solver rather than a
    costly exhaustive presentation search.
    """
    from shared.dialogue_simulator import simulate_event

    if not translations or len(translations) > max_translated_carriers:
        return translations, None, []

    player_names = {0: "000000000", 1: "000000000", 2: "000000000"}
    try:
        simulation = simulate_event(
            base_rom, event, translations, font=font, player_names=player_names,
            structural_command_overrides=structural_command_overrides,
        )
    except ValueError:
        return translations, None, []
    if _simulation_blocking_score(simulation)[0] == 0:
        return translations, simulation, []

    canonical_ids = [
        token.get("id")
        for token in event.get("tokens", [])
        if token.get("type") in {"text", "ending_text"}
        and token.get("id") in translations
    ]
    # Keep dictionary-only generated carriers deterministic as well.
    canonical_ids.extend(sorted(set(translations) - set(canonical_ids)))

    current = dict(translations)
    current_simulation = simulation
    current_score = _automatic_layout_search_score(simulation)
    repairs: list[dict] = []

    for step in range(1, max_steps + 1):
        allow_word_page = step == max_steps
        best = None
        for carrier_order, text_id in enumerate(canonical_ids):
            value = current[text_id]
            operations: list[tuple[str, int, int, str]] = []

            # Ordinary word-boundary line break. Never strand punctuation such
            # as a speaker colon at the beginning of the next line.
            for match in reversed(list(re.finditer(r"(?<=\S) (?=[^\s:;!?])", value))):
                pos = match.start()
                operations.append(("newline_word_boundary", 1, pos, value[:pos] + "\n" + value[pos + 1:]))

            # Prefer a generated page transition after complete sentences.
            for match in reversed(list(re.finditer(r"(?<=[.!?…])(?: +|\n)(?=\S)", value))):
                pos, end = match.start(), match.end()
                operations.append(("page_sentence_boundary", 0, pos, value[:pos] + "\f" + value[end:]))

            # If two earlier layout operations still cannot serialize the event,
            # permit the already-proven word-boundary page fallback used by the
            # three-page formatter. This remains presentation-only.
            if allow_word_page:
                for match in reversed(list(re.finditer(r"(?<=\S) (?=[^\s:;!?])", value))):
                    pos = match.start()
                    operations.append(("page_word_boundary", 2, pos, value[:pos] + "\f" + value[pos + 1:]))

            for strategy, strategy_rank, pos, replacement in operations:
                candidate = dict(current)
                candidate[text_id] = replacement
                try:
                    candidate_simulation = simulate_event(
                        base_rom, event, candidate, font=font, player_names=player_names,
                        structural_command_overrides=structural_command_overrides,
                    )
                except ValueError:
                    continue
                candidate_score = _automatic_layout_search_score(candidate_simulation)
                # Stable tie-break: semantic page boundaries, then NEWLINE, then
                # word-page fallback; canonical carrier order; latest boundary.
                key = (candidate_score, strategy_rank, carrier_order, -pos)
                if best is None or key < best[0]:
                    best = (
                        key, candidate, candidate_simulation,
                        {
                            "strategy": strategy,
                            "text_id": text_id,
                            "source_offset": pos,
                            "step": step,
                            "semantic_payload_changed": False,
                        },
                    )

        if best is None:
            break
        best_score = best[0][0]
        # Allow an equal-score bridge operation because two layout boundaries
        # can jointly remove a rolling-window defect even when the first one is
        # neutral in isolation. Never accept a worsening intermediate state.
        if best_score > current_score:
            break
        _, current, current_simulation, repair = best
        current_score = best_score
        repairs.append(repair)
        if _simulation_blocking_score(current_simulation)[0] == 0:
            return current, current_simulation, repairs

    return translations, None, []


def _try_direct_simulator_safe_subset(
    *,
    base_rom: bytes,
    event: dict,
    event_mappings: list[dict],
    translations: dict[str, str],
    reports: list[dict],
    font,
    structural_command_overrides: dict[int, tuple[str, str] | None] | None = None,
    max_deferred_mappings: int = 3,
) -> tuple[dict[str, str], list[dict], object | None, list[dict]]:
    """Keep a minimal whole-mapping subset stock when direct simulation proves it.

    This is a deliberately narrow second-stage PARTIEL fallback.  It is tried
    only after the normal complete-event formatting path fails.  The stock
    event itself must simulate cleanly; each candidate mapping must improve the
    direct defect count on its own; and a combination of at most three whole
    mappings must make the remaining already-formatted French directly clean.
    No command, identity, line layout, compact wrapper, or adaptive repair is
    changed by this helper.
    """
    from shared.dialogue_simulator import simulate_event

    if not translations or max_deferred_mappings < 1:
        return translations, reports, None, []

    player_names = {0: "000000000", 1: "000000000", 2: "000000000"}
    try:
        stock_simulation = simulate_event(
            base_rom, event, {}, font=font, player_names=player_names,
            structural_command_overrides=structural_command_overrides,
        )
        base_simulation = simulate_event(
            base_rom, event, translations, font=font, player_names=player_names,
            structural_command_overrides=structural_command_overrides,
        )
    except ValueError:
        return translations, reports, None, []

    if _simulation_blocking_score(stock_simulation)[0] != 0:
        return translations, reports, None, []
    base_score = _simulation_blocking_score(base_simulation)
    if base_score[0] == 0:
        return translations, reports, base_simulation, []

    candidate_mappings: list[dict] = []
    for mapping in event_mappings:
        ids = [text_id for text_id in mapping.get("snes_ids", []) if text_id in translations]
        if not ids or len(ids) == len(translations):
            continue
        candidate_translations = {
            text_id: value for text_id, value in translations.items()
            if text_id not in set(ids)
        }
        try:
            candidate_simulation = simulate_event(
                base_rom, event, candidate_translations,
                font=font, player_names=player_names,
                structural_command_overrides=structural_command_overrides,
            )
        except ValueError:
            continue
        if _simulation_blocking_score(candidate_simulation) < base_score:
            candidate_mappings.append(mapping)

    # Search the smallest deterministic set first.  Candidate order follows
    # the canonical event mapping order, so ties are stable across runs.
    for count in range(1, min(max_deferred_mappings, len(candidate_mappings)) + 1):
        for subset in combinations(candidate_mappings, count):
            deferred_ids = {
                text_id
                for mapping in subset
                for text_id in mapping.get("snes_ids", [])
                if text_id in translations
            }
            remaining = {
                text_id: value for text_id, value in translations.items()
                if text_id not in deferred_ids
            }
            if not remaining:
                continue
            try:
                simulation = simulate_event(
                    base_rom, event, remaining,
                    font=font, player_names=player_names,
                    structural_command_overrides=structural_command_overrides,
                )
            except ValueError:
                continue
            if _simulation_blocking_score(simulation)[0] != 0:
                continue

            deferred_reports: list[dict] = []
            subset_ids = set(deferred_ids)
            kept_reports = [
                report for report in reports
                if not subset_ids.intersection(report.get("snes_ids", []))
            ]
            for mapping in subset:
                ids = [text_id for text_id in mapping.get("snes_ids", []) if text_id in translations]
                deferred_reports.append({
                    "event_id": event["event_id"],
                    "snes_ids": ids,
                    "android_ids": mapping.get("android_ids", []),
                    "confidence": mapping.get("confidence"),
                    "partial_event": True,
                    "layout_deferred": True,
                    "layout_deferred_policy": "direct_simulator_safe_subset",
                    "layout_deferred_formatter_error": (
                        "whole mapping kept stock: minimal direct-simulation safe subset"
                    ),
                    "formatted_entries": [],
                })
            return remaining, kept_reports + deferred_reports, simulation, deferred_reports

    return translations, reports, None, []


def _auto_reflow_fixed_translation_carriers(
    values: dict[str, str],
    advances: dict[str, int],
) -> tuple[dict[str, str], list[dict]]:
    """Reflow already-proven carrier text to the current VWF line contract.

    This is deliberately presentation-only. Existing carrier boundaries,
    explicit NEWLINEs and translation control markers (TEXT_CLEAR / page
    controls) are preserved. Only an individual visible line that no longer
    fits the current ``DIALOGUE_WRAP_PIXELS`` / ``DIALOGUE_WRAP_CHARS`` limits
    is word-wrapped. No prose, identity, command order or carrier assignment is
    changed here; any resulting page/command incompatibility is left for the
    independent simulator to reject.
    """
    out: dict[str, str] = {}
    reports: list[dict] = []

    for text_id, value in values.items():
        # Preserve translation control markers byte-for-byte. Reflow each
        # visible segment independently so an existing TEXT_CLEAR cannot move.
        control_parts = re.split(r'([\v\f])', value)
        rebuilt_parts: list[str] = []
        changed = False
        line_reports: list[dict] = []
        for part in control_parts:
            if part in {"\v", "\f"}:
                rebuilt_parts.append(part)
                continue
            # Preserve every explicit hard newline. Only rewrap the text that
            # lies between two already-reviewed hard boundaries.
            hard_lines = part.split("\n")
            rebuilt_lines: list[str] = []
            for line in hard_lines:
                if not line.strip():
                    rebuilt_lines.append(line)
                    continue
                width = _markup_width(line, advances, 0)
                # PLAYER_NAME markup, when present, must use the conservative
                # dynamic-name wrapper rather than raw-width measurement.
                needs_wrap = width > DIALOGUE_WRAP_PIXELS or len(line) > DIALOGUE_WRAP_CHARS
                if "%S(" in line:
                    try:
                        wrapped, widths, chars, units = semantic_wrap_markup(line, advances)
                    except ValueError:
                        raise
                    needs_wrap = len(widths) > 1 or any(
                        w > DIALOGUE_WRAP_PIXELS or u > DIALOGUE_WRAP_CHARS
                        for w, u in zip(widths, units, strict=True)
                    )
                elif needs_wrap:
                    wrapped, widths, chars, units = semantic_wrap_markup(line, advances)
                else:
                    wrapped = line
                    widths = [width]
                    chars = [len(line)]
                    units = [len(line)]
                rebuilt_lines.append(wrapped)
                if wrapped != line:
                    changed = True
                    line_reports.append({
                        "source_line": line,
                        "wrapped": wrapped,
                        "widths_pixels": widths,
                        "decoded_characters": chars,
                        "parser_units": units,
                    })
            rebuilt_parts.append("\n".join(rebuilt_lines))
        rebuilt = "".join(rebuilt_parts)
        out[text_id] = rebuilt
        if changed:
            reports.append({"id": text_id, "reflowed_lines": line_reports})
    return out, reports



def _try_live_player_prefix_reflow(
    *,
    base_rom: bytes,
    event: dict,
    translations: dict[str, str],
    advances: dict[str, int],
    font,
    structural_command_overrides: dict[int, tuple[str, str] | None] | None = None,
) -> tuple[dict[str, str], object | None, list[dict]]:
    """Reflow only carriers that continue directly after ``PLAYER_NAME``.

    Android-FR carrier payload does not include stock PLAYER_NAME commands.  A
    carrier immediately following one therefore has less live first-line room
    than its standalone string suggests.  Generate a conservative candidate
    using the validated 9-character worst-case name width.  Keep the candidate
    only when whole-event simulation strictly improves; printable text and
    carrier ownership are unchanged.
    """
    from shared.dialogue_simulator import simulate_event

    tokens = event.get("tokens", [])
    candidate = dict(translations)
    repairs: list[dict] = []
    prefix_pixels = player_placeholder_width(advances)
    for index, token in enumerate(tokens):
        if token.get("type") not in {"text", "ending_text"} or index == 0:
            continue
        text_id = token.get("id")
        if text_id not in candidate:
            continue
        previous = tokens[index - 1]
        if previous.get("type") != "command" or previous.get("name") != "PLAYER_NAME":
            continue
        value = candidate[text_id]
        # A leading page/clear control resets the live prefix before prose.
        if not value or value.startswith(("\v", "\f")):
            continue
        parts = value.split("\n")
        first = parts[0]
        if not first.strip():
            continue
        try:
            wrapped, widths, chars, units = semantic_wrap_markup(
                first,
                advances,
                first_line_prefix_pixels=prefix_pixels,
                first_line_prefix_units=MAX_PLAYER_NAME_CHARS,
            )
        except ValueError:
            continue
        if wrapped == first:
            continue
        replacement = "\n".join([wrapped, *parts[1:]])
        candidate[text_id] = replacement
        repairs.append({
            "strategy": "live_player_name_prefix_reflow",
            "text_id": text_id,
            "prefix_pixels": prefix_pixels,
            "prefix_parser_units": MAX_PLAYER_NAME_CHARS,
            "semantic_payload_changed": False,
        })

    if not repairs:
        return translations, None, []
    player_names = {0: "000000000", 1: "000000000", 2: "000000000"}
    try:
        before = simulate_event(
            base_rom, event, translations, font=font, player_names=player_names,
            structural_command_overrides=structural_command_overrides,
        )
        after = simulate_event(
            base_rom, event, candidate, font=font, player_names=player_names,
            structural_command_overrides=structural_command_overrides,
        )
    except ValueError:
        return translations, None, []
    if _automatic_layout_search_score(after) >= _automatic_layout_search_score(before):
        return translations, None, []
    return candidate, after, repairs

def _repack_fixed_translation_carriers(
    values: dict[str, str],
    advances: dict[str, int],
) -> tuple[dict[str, str], list[dict]]:
    """Repack historical hard NEWLINE layout inside fixed carrier segments.

    Secondary candidate generator only: preserve carrier assignments and page
    controls, normalize old hard NEWLINEs inside each visible segment to spaces,
    then reapply the calibrated 216px / 38-unit wrapper. The whole event must
    independently simulate clean before callers may accept the candidate.
    """
    out: dict[str, str] = {}
    reports: list[dict] = []
    for text_id, value in values.items():
        parts = re.split(r'([\v\f])', value)
        rebuilt: list[str] = []
        changes: list[dict] = []
        for part in parts:
            if part in {"\v", "\f"}:
                rebuilt.append(part)
                continue
            if not part:
                rebuilt.append(part)
                continue
            logical = re.sub(r"[ \t]*\n[ \t]*", " ", part)
            logical = re.sub(r"[ \t]+", " ", logical)
            if not logical.strip():
                rebuilt.append(logical)
                continue
            wrapped, widths, chars, units = semantic_wrap_markup(logical, advances)
            rebuilt.append(wrapped)
            if wrapped != part:
                changes.append({
                    "source_segment": part,
                    "logical_segment": logical,
                    "wrapped": wrapped,
                    "widths_pixels": widths,
                    "decoded_characters": chars,
                    "parser_units": units,
                })
        out[text_id] = "".join(rebuilt)
        if changes:
            reports.append({"id": text_id, "repacked_segments": changes})
    return out, reports


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
    structural_command_overrides_by_event = resolve_structural_command_overrides(
        {"user_validated_structural_command_overrides": list(DIALOGUE_USER_VALIDATED_STRUCTURAL_COMMAND_OVERRIDES)},
        source_document,
    )
    redistribution_values, redistribution_meta = _load_dialogue_redistribution_recipes(french)
    reviewed_choice_layout_recipes = _load_reviewed_choice_layout_recipes(source_document)
    round68_events = {"0555", "0429", "05F8"}
    round69_events = {
        "010C", "015A", "01C5", "0204", "0205", "0227", "04E2", "04E5", "04E6", "04E9", "04FD", "0559", "0592", "05B4"
    }
    if set(redistribution_values) != round68_events | round69_events:
        raise ValueError("Dialogue redistribution recipe event set changed")
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
    reviewed_hole_player_context_repairs_by_event: dict[str, list[dict]] = {}
    fragment_spacing_repairs_by_event: dict[str, list[dict]] = {}
    targeted_wait00_fresh_page_repairs_by_event: dict[str, list[dict]] = {}
    explicit_post_wait_newline_repairs_by_event: dict[str, list[dict]] = {}
    round48_pagination_repairs_by_event: dict[str, list[dict]] = {}
    round49_04e9_wait00_clear_repairs_by_event: dict[str, list[dict]] = {}
    round50_01ce_choice_page_clear_repairs_by_event: dict[str, list[dict]] = {}
    round54_nonsemantic_android_supplements_by_event: dict[str, list[dict]] = {}
    automatic_216px_reflows_by_event: dict[str, list[dict]] = {}
    carrier_boundary_newline_repairs_by_event: dict[str, list[dict]] = {}
    carrier_repack_repairs_by_event: dict[str, list[dict]] = {}
    live_player_prefix_reflow_repairs_by_event: dict[str, list[dict]] = {}
    source_derived_layout_search_repairs_by_event: dict[str, list[dict]] = {}
    choice_row_layout_repairs_by_event: dict[str, list[dict]] = {}
    adaptive_choice_decoration_repairs_by_event: dict[str, list[dict]] = {}
    adaptive_choice_anchor_repairs_by_event: dict[str, list[dict]] = {}
    reviewed_choice_compact_repairs_by_event: dict[str, list[dict]] = {}
    choice_option_position_overrides_by_event: dict[str, dict[int, int]] = {}
    manual_supplement_reports_by_event: dict[str, list[dict]] = {}
    android_extra_reports_by_event: dict[str, list[dict]] = {}
    parameterized_inn_events: set[str] = set()
    accepted_events: list[str] = []
    partial_accepted_events: list[str] = []
    partial_unresolved_semantic_ids_by_event: dict[str, list[str]] = {}
    partial_layout_deferred_semantic_ids_by_event: dict[str, list[str]] = {}
    generic_layout_deferred_semantic_ids_by_event: dict[str, list[str]] = {}
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

        if event_id in round68_events:
            values = dict(redistribution_values[event_id])
            values, automatic_reflow = _auto_reflow_fixed_translation_carriers(values, advances)
            canonical_ids = {
                token.get("id") for token in event["tokens"]
                if token.get("type") in {"text", "ending_text"}
            }
            unknown = sorted(set(values) - canonical_ids)
            if unknown:
                raise ValueError(f"Round-68 ${event_id} unknown carrier(s): {unknown}")
            simulation = simulate_event(
                base_rom, event, values, font=font,
                player_names={0: "000000000", 1: "000000000", 2: "000000000"},
            )
            blocking = [issue for issue in simulation.issues if issue.severity in {"error", "warning"}]
            wraps = sum(
                line.implicit_wrap
                for box in simulation.boxes for page in box.pages for line in page.lines
            )
            if blocking or wraps:
                candidate_values, candidate_simulation, boundary_repairs = _try_single_carrier_boundary_newline(
                    base_rom=base_rom, event=event, translations=values, font=font
                )
                if boundary_repairs:
                    values = candidate_values
                    simulation = candidate_simulation
                    blocking = []
                    wraps = 0
                    carrier_boundary_newline_repairs_by_event[event_id] = boundary_repairs
            if blocking or wraps:
                repacked_values, repack_repairs = _repack_fixed_translation_carriers(
                    dict(redistribution_values[event_id]), advances
                )
                try:
                    repacked_simulation = simulate_event(
                        base_rom, event, repacked_values, font=font,
                        player_names={0: "000000000", 1: "000000000", 2: "000000000"},
                    )
                except ValueError:
                    repacked_simulation = None
                if repacked_simulation is not None and _simulation_blocking_score(repacked_simulation)[0] == 0:
                    values = repacked_values
                    simulation = repacked_simulation
                    blocking = []
                    wraps = 0
                    carrier_repack_repairs_by_event[event_id] = repack_repairs
                elif repacked_simulation is not None:
                    candidate_values, candidate_simulation, boundary_repairs = _try_single_carrier_boundary_newline(
                        base_rom=base_rom, event=event, translations=repacked_values, font=font
                    )
                    if boundary_repairs:
                        values = candidate_values
                        simulation = candidate_simulation
                        blocking = []
                        wraps = 0
                        carrier_repack_repairs_by_event[event_id] = repack_repairs
                        carrier_boundary_newline_repairs_by_event[event_id] = boundary_repairs
            if blocking or wraps:
                prefix_values, prefix_simulation, prefix_repairs = _try_live_player_prefix_reflow(
                    base_rom=base_rom, event=event, translations=values, advances=advances, font=font
                )
                if prefix_repairs:
                    values = prefix_values
                    simulation = prefix_simulation
                    live_player_prefix_reflow_repairs_by_event[event_id] = prefix_repairs
                    blocking = [issue for issue in simulation.issues if issue.severity in {"error", "warning"}]
                    wraps = sum(line.implicit_wrap for box in simulation.boxes for page in box.pages for line in page.lines)
            if blocking or wraps:
                page_values, page_simulation, page_repairs = _try_unpaused_scroll_page_repairs(
                    base_rom=base_rom, event=event, translations=values, font=font
                )
                if page_repairs:
                    values = page_values
                    simulation = page_simulation
                    blocking = []
                    wraps = 0
                    source_derived_layout_search_repairs_by_event[event_id] = page_repairs
            if blocking or wraps:
                searched_values, searched_simulation, search_repairs = _try_source_derived_layout_search(
                    base_rom=base_rom, event=event, translations=values, font=font
                )
                if search_repairs:
                    values = searched_values
                    simulation = searched_simulation
                    blocking = []
                    wraps = 0
                    source_derived_layout_search_repairs_by_event[event_id] = search_repairs
            if blocking or wraps:
                excluded_events.append({
                    "event_id": event_id,
                    "stage": "reviewed_redistribution_automatic_reflow",
                    "reason": "automatic_216px_reflow_not_simulator_clean",
                    "reviewed_redistribution_round": 68,
                    "blocking_issue_codes": [issue.code for issue in blocking],
                    "implicit_wraps": wraps,
                    "automatic_216px_reflow": automatic_reflow,
                })
                continue
            accepted_events.append(event_id)
            formatter_candidate_count += 1
            if event_id != "05F8":
                complete_aligned_count += 1
            translations_by_event[event_id] = values
            reports_by_event[event_id] = [{
                "event_id": event_id,
                "snes_ids": list(values),
                "android_ids": redistribution_meta[event_id]["android_ids"],
                "confidence": "user_validated_scene_semantic_redistribution",
                "round68_user_validated_android_fr_scene": True,
                "android_identity_count_changed": False,
                "note": "Keep the original Android-FR scene semantics verbatim; only SNES carriers/pages and translated-only dynamic PLAYER_NAME placement are redistributed.",
                "formatted_entries": [{"id": k, "text": v} for k, v in values.items()],
                "automatic_216px_reflow": automatic_reflow,
            }]
            continue

        if event_id in round69_events:
            values = dict(redistribution_values[event_id])
            values, automatic_reflow = _auto_reflow_fixed_translation_carriers(values, advances)
            canonical_ids = {
                token.get("id") for token in event["tokens"]
                if token.get("type") in {"text", "ending_text"}
            }
            unknown = sorted(set(values) - canonical_ids)
            if unknown:
                raise ValueError(f"Round-69 ${event_id} unknown carrier(s): {unknown}")
            structural_overrides = structural_command_overrides_by_event.get(event_id)
            simulation = simulate_event(
                base_rom, event, values, font=font,
                player_names={0: "000000000", 1: "000000000", 2: "000000000"},
                structural_command_overrides=structural_overrides,
            )
            blocking = [issue for issue in simulation.issues if issue.severity in {"error", "warning"}]
            wraps = sum(
                line.implicit_wrap
                for box in simulation.boxes for page in box.pages for line in page.lines
            )
            if blocking or wraps:
                candidate_values, candidate_simulation, boundary_repairs = _try_single_carrier_boundary_newline(
                    base_rom=base_rom, event=event, translations=values, font=font,
                    structural_command_overrides=structural_overrides,
                )
                if boundary_repairs:
                    values = candidate_values
                    simulation = candidate_simulation
                    blocking = []
                    wraps = 0
                    carrier_boundary_newline_repairs_by_event[event_id] = boundary_repairs
            if blocking or wraps:
                repacked_values, repack_repairs = _repack_fixed_translation_carriers(
                    dict(redistribution_values[event_id]), advances
                )
                try:
                    repacked_simulation = simulate_event(
                        base_rom, event, repacked_values, font=font,
                        player_names={0: "000000000", 1: "000000000", 2: "000000000"},
                        structural_command_overrides=structural_overrides,
                    )
                except ValueError:
                    repacked_simulation = None
                if repacked_simulation is not None and _simulation_blocking_score(repacked_simulation)[0] == 0:
                    values = repacked_values
                    simulation = repacked_simulation
                    blocking = []
                    wraps = 0
                    carrier_repack_repairs_by_event[event_id] = repack_repairs
                elif repacked_simulation is not None:
                    candidate_values, candidate_simulation, boundary_repairs = _try_single_carrier_boundary_newline(
                        base_rom=base_rom, event=event, translations=repacked_values, font=font,
                        structural_command_overrides=structural_overrides,
                    )
                    if boundary_repairs:
                        values = candidate_values
                        simulation = candidate_simulation
                        blocking = []
                        wraps = 0
                        carrier_repack_repairs_by_event[event_id] = repack_repairs
                        carrier_boundary_newline_repairs_by_event[event_id] = boundary_repairs
            if blocking or wraps:
                searched_values, searched_simulation, search_repairs = _try_source_derived_layout_search(
                    base_rom=base_rom, event=event, translations=values, font=font,
                    structural_command_overrides=structural_overrides,
                )
                if search_repairs:
                    values = searched_values
                    simulation = searched_simulation
                    blocking = []
                    wraps = 0
                    source_derived_layout_search_repairs_by_event[event_id] = search_repairs
            if blocking or wraps:
                excluded_events.append({
                    "event_id": event_id,
                    "stage": "reviewed_redistribution_automatic_reflow",
                    "reason": "automatic_216px_reflow_not_simulator_clean",
                    "reviewed_redistribution_round": 69,
                    "blocking_issue_codes": [issue.code for issue in blocking],
                    "blocking_issue_messages": [issue.message for issue in blocking[:8]],
                    "implicit_wraps": wraps,
                    "automatic_216px_reflow": automatic_reflow,
                })
                continue
            accepted_events.append(event_id)
            formatter_candidate_count += 1
            complete_aligned_count += 1
            translations_by_event[event_id] = values
            reports_by_event[event_id] = [{
                "event_id": event_id,
                "snes_ids": list(values),
                "android_ids": redistribution_meta[event_id]["android_ids"],
                "confidence": "user_authorized_targeted_scene_redistribution",
                "round69_targeted_redistribution": True,
                "android_identity_count_changed": False,
                "note": "Reviewed Android-FR/SNES resegmentation; no new weak Android identity is created.",
                "formatted_entries": [{"id": k, "text": v} for k, v in values.items()],
                "automatic_216px_reflow": automatic_reflow,
            }]
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
        complete_layout_deferred_ids: list[str] = []
        for mapping in event_mappings:
            if mapping.get("relation") == "shared_called_tail_combined_anchor":
                formatter_errors.append({
                    "snes_ids": mapping.get("snes_ids", []),
                    "android_ids": mapping.get("android_ids", []),
                    "message": (
                        "reviewed shared-tail identity: Android anchor combines text "
                        "owned by a called SNES event; keep carrier stock to avoid duplicate insertion"
                    ),
                })
                continue
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
                message = str(exc)
                reviewed_defer_note = _reviewed_partial_layout_defer(
                    event_id, mapping, message
                )
                generic_defer = _partial_layout_deferable_formatter_error(message)
                if reviewed_defer_note is not None or generic_defer:
                    deferred = list(mapping.get("snes_ids", []))
                    complete_layout_deferred_ids.extend(deferred)
                    if generic_defer and reviewed_defer_note is None:
                        generic_layout_deferred_semantic_ids_by_event.setdefault(event_id, []).extend(deferred)
                    event_reports.append({
                        "event_id": event_id,
                        "snes_ids": deferred,
                        "android_ids": mapping.get("android_ids", []),
                        "confidence": mapping.get("confidence"),
                        "partial_event": True,
                        "layout_deferred": True,
                        "layout_deferred_formatter_error": message,
                        "layout_deferred_policy": (
                            "reviewed_exact" if reviewed_defer_note is not None
                            else "generic_structural_safe_subset"
                        ),
                        "reviewed_partial_layout_defer_note": reviewed_defer_note,
                        "formatted_entries": [],
                    })
                    continue
                formatter_errors.append(
                    {
                        "snes_ids": mapping.get("snes_ids", []),
                        "android_ids": mapping.get("android_ids", []),
                        "message": str(exc),
                    }
                )
                continue
            values, mapping_report, trailing_transition_repairs = _collapse_trailing_page_break_into_stock_transition(
                source_document, mapping, values, mapping_report
            )
            if _mapping_has_unserializable_trailing_page_break(
                source_document, mapping, values
            ):
                # A generated page transition that is not one of the two
                # serializer-proven choice shapes would require structural
                # rebinding. Keep this entire mapped carrier stock and let the
                # same direct PARTIEL simulation gate decide the event.
                deferred = list(mapping.get("snes_ids", []))
                complete_layout_deferred_ids.extend(deferred)
                generic_layout_deferred_semantic_ids_by_event.setdefault(event_id, []).extend(deferred)
                event_reports.append({
                    "event_id": event_id,
                    "snes_ids": deferred,
                    "android_ids": mapping.get("android_ids", []),
                    "confidence": mapping.get("confidence"),
                    "partial_event": True,
                    "layout_deferred": True,
                    "layout_deferred_formatter_error": "generated trailing page break is not serializable in the canonical command shape",
                    "layout_deferred_policy": "generic_structural_safe_subset",
                    "formatted_entries": [],
                })
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

        if event_id == "04E2":
            round67_reports, _ = _apply_round67_user_reviewed_scene_redistributions(
                event, event_translations, english=english, french=french,
                layout_deferred_ids=complete_layout_deferred_ids, missing_ids=[],
            )
            event_reports = [
                report for report in event_reports
                if not (report.get("layout_deferred") and {"CA:32C5", "CA:32D7"}.intersection(report.get("snes_ids", [])))
            ]
            generic_layout_deferred_semantic_ids_by_event[event_id] = [
                x for x in generic_layout_deferred_semantic_ids_by_event.get(event_id, [])
                if x not in {"CA:32C5", "CA:32D7"}
            ]
            event_reports.extend(round67_reports)

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
        if complete_layout_deferred_ids and not event_translations:
            excluded_events.append(
                {
                    "event_id": event_id,
                    "stage": "formatter_rejected",
                    "semantic_ids": semantic_ids,
                    "missing_semantic_ids": [],
                    "details": [
                        {
                            "snes_ids": sorted(set(complete_layout_deferred_ids)),
                            "android_ids": [],
                            "message": (
                                "all mapped carriers require structural layout deferral; "
                                "PARTIEL would release no French text"
                            ),
                        }
                    ],
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
        round48_pagination_repairs_by_event[event_id] = _apply_round48_0127_pagination(
            event, event_translations
        )
        round49_04e9_wait00_clear_repairs_by_event[event_id] = _apply_round49_04e9_wait00_clears(
            event, event_translations
        )
        round50_01ce_choice_page_clear_repairs_by_event[event_id] = _apply_round50_01ce_choice_page_clear(
            event, event_translations
        )
        round54_nonsemantic_android_supplements_by_event[event_id] = _apply_round54_nonsemantic_android_supplement(
            event, event_translations, english=english, french=french
        )
        # Final presentation-only pass: legacy/manual/redistributed inserts may
        # have bypassed the ordinary mapping wrapper. Reflow each existing
        # carrier line to the current 216px / 38-unit contract before the
        # independent simulator decides whether the event remains admissible.
        event_translations, automatic_reflow = _auto_reflow_fixed_translation_carriers(
            event_translations, advances
        )
        automatic_216px_reflows_by_event[event_id] = automatic_reflow
        direct_subset_translations = dict(event_translations)
        direct_subset_reports = [dict(report) for report in event_reports]
        if complete_layout_deferred_ids:
            # Generic structural safe-subset PARTIEL gets no adaptive/compact
            # rescue. The remaining mapped French must be clean exactly as
            # formatted while every deferred carrier and every stock command
            # stays untouched.
            try:
                simulation = simulate_event(
                    base_rom,
                    event,
                    event_translations,
                    font=font,
                    player_names={0: "000000000", 1: "000000000", 2: "000000000"},
                    structural_command_overrides=structural_command_overrides_by_event.get(event_id),
                )
            except ValueError as exc:
                excluded_events.append(
                    {
                        "event_id": event_id,
                        "stage": "simulator_rejected",
                        "semantic_ids": semantic_ids,
                        "missing_semantic_ids": [],
                        "details": [{"message": f"direct PARTIEL simulation failed: {exc}"}],
                    }
                )
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
                    subset_translations,
                    subset_reports,
                    subset_simulation,
                    subset_deferred_reports,
                ) = _try_direct_simulator_safe_subset(
                    base_rom=base_rom,
                    event=event,
                    event_mappings=event_mappings,
                    translations=event_translations,
                    reports=event_reports,
                    font=font,
                    structural_command_overrides=structural_command_overrides_by_event.get(event_id),
                    max_deferred_mappings=3,
                )
                if subset_deferred_reports:
                    extra_deferred_ids = sorted({
                        text_id
                        for report in subset_deferred_reports
                        for text_id in report.get("snes_ids", [])
                    })
                    all_deferred_ids = sorted(set(complete_layout_deferred_ids) | set(extra_deferred_ids))
                    accepted_events.append(event_id)
                    partial_accepted_events.append(event_id)
                    partial_unresolved_semantic_ids_by_event[event_id] = all_deferred_ids
                    partial_layout_deferred_semantic_ids_by_event[event_id] = all_deferred_ids
                    partial_suppression_reason_by_event[event_id] = "mapped_but_direct_simulator_deferred"
                    translations_by_event[event_id] = subset_translations
                    reports_by_event[event_id] = subset_reports
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
                    details.append({
                        "severity": "error",
                        "code": "IMPLICIT_RUNTIME_WRAP_SUMMARY",
                        "message": f"simulator recorded {implicit_wraps} implicit runtime wrap(s)",
                    })
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
            partial_accepted_events.append(event_id)
            deferred_ids = sorted(set(complete_layout_deferred_ids))
            partial_unresolved_semantic_ids_by_event[event_id] = deferred_ids
            partial_layout_deferred_semantic_ids_by_event[event_id] = deferred_ids
            partial_suppression_reason_by_event[event_id] = "mapped_but_layout_deferred"
            translations_by_event[event_id] = event_translations
            reports_by_event[event_id] = event_reports
            wait00_repairs_by_event[event_id] = []
            unpaused_scroll_repairs_by_event[event_id] = []
            cross_mapping_sentence_repairs_by_event[event_id] = []
            structural_reaction_page_repairs_by_event[event_id] = []
            continue

        try:
            event_translations, simulation, wait00_repairs = _repair_wait00_page_overlaps(
                base_rom=base_rom,
                event=event,
                translations=event_translations,
                font=font,
            )
        except ValueError as exc:
            excluded_events.append(
                {
                    "event_id": event_id,
                    "stage": "formatter_rejected",
                    "semantic_ids": semantic_ids,
                    "missing_semantic_ids": [],
                    "details": [
                        {
                            "snes_ids": [],
                            "android_ids": [],
                            "message": f"serialized layout rejected before simulation: {exc}",
                        }
                    ],
                }
            )
            continue
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
        if event_id in reviewed_choice_layout_recipes:
            (
                event_translations,
                event_reports,
                simulation,
                reviewed_row_repairs,
                reviewed_decoration_repairs,
                reviewed_compact_repairs,
            ) = _apply_reviewed_choice_layout_recipe(
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
                recipe=reviewed_choice_layout_recipes[event_id],
            )
            if reviewed_row_repairs:
                choice_row_layout_repairs_by_event[event_id] = reviewed_row_repairs
            if reviewed_decoration_repairs:
                adaptive_choice_decoration_repairs_by_event[event_id] = reviewed_decoration_repairs
            if reviewed_compact_repairs:
                reviewed_choice_compact_repairs_by_event[event_id] = reviewed_compact_repairs
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
                (
                    compact_translations,
                    compact_simulation,
                    compact_post_wait_sentence_repairs,
                ) = _repair_unique_post_wait_sentence_newline(
                    base_rom=base_rom,
                    event=event,
                    translations=compact_translations,
                    font=font,
                    simulation=compact_simulation,
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
                    if compact_post_wait_sentence_repairs:
                        explicit_post_wait_newline_repairs_by_event.setdefault(event_id, []).extend(
                            compact_post_wait_sentence_repairs
                        )
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

            (
                boundary_translations,
                boundary_simulation,
                boundary_repairs,
            ) = _try_single_carrier_boundary_newline(
                base_rom=base_rom,
                event=event,
                translations=event_translations,
                font=font,
                structural_command_overrides=structural_command_overrides_by_event.get(event_id),
            )
            if boundary_repairs:
                accepted_events.append(event_id)
                translations_by_event[event_id] = boundary_translations
                reports_by_event[event_id] = event_reports
                wait00_repairs_by_event[event_id] = wait00_repairs
                unpaused_scroll_repairs_by_event[event_id] = []
                cross_mapping_sentence_repairs_by_event[event_id] = []
                structural_reaction_page_repairs_by_event[event_id] = []
                carrier_boundary_newline_repairs_by_event[event_id] = boundary_repairs
                continue

            searched_translations, searched_simulation, search_repairs = _try_source_derived_layout_search(
                base_rom=base_rom,
                event=event,
                translations=event_translations,
                font=font,
                structural_command_overrides=structural_command_overrides_by_event.get(event_id),
            )
            if search_repairs:
                accepted_events.append(event_id)
                translations_by_event[event_id] = searched_translations
                reports_by_event[event_id] = event_reports
                wait00_repairs_by_event[event_id] = wait00_repairs
                unpaused_scroll_repairs_by_event[event_id] = []
                cross_mapping_sentence_repairs_by_event[event_id] = []
                structural_reaction_page_repairs_by_event[event_id] = []
                source_derived_layout_search_repairs_by_event[event_id] = search_repairs
                continue

            page_translations, page_simulation, page_repairs = _try_unpaused_scroll_page_repairs(
                base_rom=base_rom,
                event=event,
                translations=event_translations,
                font=font,
                structural_command_overrides=structural_command_overrides_by_event.get(event_id),
            )
            if page_repairs:
                accepted_events.append(event_id)
                translations_by_event[event_id] = page_translations
                reports_by_event[event_id] = event_reports
                wait00_repairs_by_event[event_id] = wait00_repairs
                unpaused_scroll_repairs_by_event[event_id] = []
                cross_mapping_sentence_repairs_by_event[event_id] = []
                structural_reaction_page_repairs_by_event[event_id] = []
                source_derived_layout_search_repairs_by_event[event_id] = page_repairs
                continue

            (
                subset_translations,
                subset_reports,
                subset_simulation,
                subset_deferred_reports,
            ) = _try_direct_simulator_safe_subset(
                base_rom=base_rom,
                event=event,
                event_mappings=event_mappings,
                translations=direct_subset_translations,
                reports=direct_subset_reports,
                font=font,
                structural_command_overrides=structural_command_overrides_by_event.get(event_id),
                max_deferred_mappings=3,
            )
            if subset_deferred_reports:
                deferred_ids = sorted({
                    text_id
                    for report in subset_deferred_reports
                    for text_id in report.get("snes_ids", [])
                })
                accepted_events.append(event_id)
                partial_accepted_events.append(event_id)
                partial_unresolved_semantic_ids_by_event[event_id] = deferred_ids
                partial_layout_deferred_semantic_ids_by_event[event_id] = deferred_ids
                partial_suppression_reason_by_event[event_id] = "mapped_but_direct_simulator_deferred"
                translations_by_event[event_id] = subset_translations
                reports_by_event[event_id] = subset_reports
                wait00_repairs_by_event[event_id] = []
                unpaused_scroll_repairs_by_event[event_id] = []
                cross_mapping_sentence_repairs_by_event[event_id] = []
                structural_reaction_page_repairs_by_event[event_id] = []
                continue

            # If newly reviewed structural mappings are correct semantically but
            # still cannot be laid out safely, preserve the previous French-only
            # PARTIEL behavior instead of losing the whole event. Only mappings
            # that predate the current structural reviews are rendered; every newly
            # reviewed semantic token is explicitly suppressed and the direct result
            # must simulate cleanly.
            structural_review = [
                m for m in event_mappings
                if m.get("provenance") in {"round6", "round7", "round8", "round11", "round18", "round20", "round21", "round22", "round25"}
            ]
            baseline = [
                m for m in event_mappings
                if m.get("provenance") not in {"round6", "round7", "round8", "round11", "round18", "round20", "round21", "round22", "round25"}
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
                # Keep layout-deferred mapped carriers absent from the sparse
                # French translation map so their stock SNES English remains
                # visible in a PARTIEL event.
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
                            partial_unresolved_semantic_ids_by_event[event_id] = suppressed
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

        # Round 67: C9:40D7 belongs to a fully aligned Android-848 mapping, but
        # official Android FR intentionally omits this Western-only second sentence
        # and the SNES-JP event has no distinct counterpart. The user validated
        # suppressing the standalone final page. Apply that exact mapped-carrier
        # suppression only after the ordinary complete-event layout is proven clean,
        # then re-simulate with the immediately following WAIT $00 omitted.
        if event_id == "013A":
            manual_entry = manual_supplements_by_event.get("013A", {}).get("C9:40D7")
            if manual_entry is None or manual_entry.get("status") != "suppressed":
                raise AssertionError("Round-67 $013A/C9:40D7 validated suppression metadata missing")
            if event_translations.get("C9:40D7") not in {None, ""}:
                raise AssertionError("Round-67 $013A/C9:40D7 would overwrite visible translated text")
            event_translations["C9:40D7"] = ""
            suppression_report = {
                "event_id": "013A",
                "snes_ids": ["C9:40D7"],
                "android_ids": [848],
                "confidence": "user_validated_snes_jp_absent_android_fr_adaptation_suppression",
                "manual_supplement": True,
                "manual_status": "suppressed",
                "manual_reason": manual_entry["reason"],
                "android_identity_unchanged": True,
                "formatted_entries": [{"id": "C9:40D7", "text": ""}],
                "payload_policy": "validated_empty_mapped_carrier_with_adjacent_wait_omission",
            }
            event_reports.append(suppression_report)
            manual_supplement_reports_by_event.setdefault("013A", []).append(suppression_report)
            try:
                suppression_simulation = simulate_event(
                    base_rom,
                    event,
                    event_translations,
                    font=font,
                    player_names={0: "000000000", 1: "000000000", 2: "000000000"},
                    omitted_command_token_indexes=structural_omission_indexes_by_event.get(event_id),
                    structural_command_overrides=structural_command_overrides_by_event.get(event_id),
                )
            except ValueError as exc:
                excluded_events.append({
                    "event_id": event_id,
                    "stage": "simulator_rejected",
                    "semantic_ids": semantic_ids,
                    "missing_semantic_ids": [],
                    "details": [{"message": f"Round-67 validated $013A suppression failed serialization: {exc}"}],
                })
                continue
            suppression_blocking = [
                issue for issue in suppression_simulation.issues
                if issue.severity in {"error", "warning"}
            ]
            suppression_wraps = sum(
                line.implicit_wrap
                for box in suppression_simulation.boxes
                for page in box.pages
                for line in page.lines
            )
            if suppression_blocking or suppression_wraps:
                excluded_events.append({
                    "event_id": event_id,
                    "stage": "simulator_rejected",
                    "semantic_ids": semantic_ids,
                    "missing_semantic_ids": [],
                    "details": [
                        {
                            "severity": issue.severity,
                            "code": issue.code,
                            "message": issue.message,
                            "box": issue.box,
                            "page": issue.page,
                            "line": issue.line,
                        }
                        for issue in suppression_blocking
                    ] + ([{
                        "severity": "error",
                        "code": "IMPLICIT_RUNTIME_WRAP_SUMMARY",
                        "message": f"Round-67 validated $013A suppression recorded {suppression_wraps} implicit wrap(s)",
                    }] if suppression_wraps else []),
                })
                continue
            simulation = suppression_simulation

        accepted_events.append(event_id)
        if complete_layout_deferred_ids:
            partial_accepted_events.append(event_id)
            deferred_ids = sorted(set(complete_layout_deferred_ids))
            partial_unresolved_semantic_ids_by_event[event_id] = deferred_ids
            partial_layout_deferred_semantic_ids_by_event[event_id] = deferred_ids
            partial_suppression_reason_by_event[event_id] = "mapped_but_layout_deferred"
        translations_by_event[event_id] = event_translations
        reports_by_event[event_id] = event_reports
        wait00_repairs_by_event[event_id] = wait00_repairs
        unpaused_scroll_repairs_by_event[event_id] = unpaused_scroll_repairs
        cross_mapping_sentence_repairs_by_event[event_id] = cross_mapping_sentence_repairs

    # Second, conservative partial-event pass. Every alignment-incomplete event
    # is reconsidered on each run. Already accepted high-confidence mappings are
    # rendered in French; genuinely unresolved semantic carriers are deliberately
    # left untranslated so their stock SNES English remains visible during
    # playtesting. Structural commands/layout remain canonical. Unlike complete
    # events, partial events receive no compact/event-level repair: the directly
    # formatted mixed FR/EN event must already simulate with no errors, warnings
    # or implicit wraps.
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
        manual_only_ids = DIALOGUE_MANUAL_ONLY_RESEGMENTED_PARTIAL_IDS.get(event_id)
        if manual_only_ids:
            manual_entries_for_policy = manual_supplements_by_event.get(event_id, {})
            if set(manual_entries_for_policy) != set(manual_only_ids):
                raise AssertionError(
                    f"manual-only resegmented PARTIEL ${event_id} supplement set changed: "
                    f"{sorted(manual_entries_for_policy)}"
                )
            if any(
                manual_entries_for_policy[text_id].get("status") != "translated"
                for text_id in manual_only_ids
            ):
                # Until the user explicitly approves the exact manual carrier,
                # preserve the historical Round-64/65 exclusion unchanged.
                manual_only_ids = None
            else:
                # Exact Round-66 policy: do not let the presence of one approved
                # manual carrier reopen any Android mapping in this resegmented
                # event. Everything except the manual carrier stays stock USA.
                event_mappings = []
        # A user-validated Android-absent manual supplement may intentionally be
        # the only French payload in an otherwise alignment-incomplete event
        # (Round 43 Dryad). Keep it outside semantic alignment but still let the
        # normal PARTIEL simulator gate decide whether the translation is safe.
        if (
            not event_mappings
            and event_id not in manual_supplements_by_event
            and event_id not in DIALOGUE_REVIEWED_UNMAPPED_LAYOUT_RESEGMENTATIONS
        ):
            continue
        # The complete-event pass already removes a trailing PLAYER_NAME that
        # was borrowed only as duplicate alignment context by the preceding
        # mapping. PARTIEL must apply the same ownership rule before deciding
        # whether proven French can coexist with unresolved stock carriers.
        event_mappings, duplicated_player_context_repairs = (
            _strip_duplicated_trailing_player_context(
                event, event_mappings, base_rom=base_rom
            )
        )
        if duplicated_player_context_repairs:
            duplicated_player_context_repairs_by_event[event_id] = (
                duplicated_player_context_repairs
            )
        missing_ids = list(incomplete.get("missing_semantic_ids", []))
        missing_set = set(missing_ids)
        event_mappings, reviewed_hole_player_context_repairs = (
            _strip_trailing_player_context_owned_by_reviewed_hole(
                event,
                event_mappings,
                missing_ids=missing_set,
                unmapped_by_id=unmapped_by_id,
            )
        )
        reviewed_hole_player_context_repairs_by_event[event_id] = (
            reviewed_hole_player_context_repairs
        )
        frozen_suppressions = set(
            DIALOGUE_USER_VALIDATED_VISUALLY_COMPLETE_SUPPRESSIONS.get(event_id, ())
        )
        partial_user_suppressions = set(
            DIALOGUE_USER_VALIDATED_PARTIAL_SUPPRESSIONS.get(event_id, ())
        )
        if not partial_user_suppressions <= missing_set:
            raise AssertionError(
                f"partial event ${event_id}: user suppression is not an unresolved semantic hole: "
                f"{sorted(partial_user_suppressions - missing_set)}"
            )
        effective_suppressed_ids = sorted(
            missing_set | frozen_suppressions | partial_user_suppressions
        )
        validated_android_omission_hole = any(
            unmapped_by_id.get(missing_id, {}).get("reason") == "validated_android_omission"
            for missing_id in missing_ids
        )
        event_translations: dict[str, str] = {}
        event_reports: list[dict] = []
        partial_errors: list[dict] = []
        layout_deferred_ids: list[str] = []
        generic_layout_deferred_ids: list[str] = []
        layout_deferred_reports: list[dict] = []
        round67_resolved_missing_ids: set[str] = set()
        for mapping in event_mappings:
            mapping_semantic_ids = set(mapping.get("snes_ids", []))
            frozen_overlap = mapping_semantic_ids & frozen_suppressions
            if frozen_overlap:
                if frozen_overlap != mapping_semantic_ids:
                    raise AssertionError(
                        f"partial event ${event_id}: mapping mixes frozen validated omissions "
                        f"with visible semantic IDs: {sorted(mapping_semantic_ids)}"
                    )
                continue
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
                message = str(exc)
                reviewed_defer_note = _reviewed_partial_layout_defer(
                    event_id, mapping, message
                )
                generic_defer = (
                    event_id not in DIALOGUE_GENERIC_PARTIAL_LAYOUT_DEFERRAL_BLOCKLIST
                    and _partial_layout_deferable_formatter_error(message)
                )
                if (
                    (validated_android_omission_hole and _partial_layout_deferable_formatter_error(message))
                    or reviewed_defer_note is not None
                    or generic_defer
                ):
                    deferred = list(mapping.get("snes_ids", []))
                    layout_deferred_ids.extend(deferred)
                    if generic_defer and reviewed_defer_note is None and not validated_android_omission_hole:
                        generic_layout_deferred_ids.extend(deferred)
                        generic_layout_deferred_semantic_ids_by_event.setdefault(event_id, []).extend(deferred)
                    layout_deferred_reports.append({
                        "event_id": event_id,
                        "snes_ids": deferred,
                        "android_ids": mapping.get("android_ids", []),
                        "confidence": mapping.get("confidence"),
                        "partial_event": True,
                        "layout_deferred": True,
                        "layout_deferred_formatter_error": message,
                        "layout_deferred_policy": (
                            "reviewed_exact"
                            if reviewed_defer_note is not None
                            else (
                                "validated_android_omission"
                                if validated_android_omission_hole
                                else "generic_structural_safe_subset"
                            )
                        ),
                        "reviewed_partial_layout_defer_note": reviewed_defer_note,
                        "formatted_entries": [],
                    })
                    continue
                partial_errors.append({
                    "snes_ids": mapping.get("snes_ids", []),
                    "android_ids": mapping.get("android_ids", []),
                    "message": message,
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
        post_repair_manual_ids = set(
            DIALOGUE_PARTIAL_MANUAL_POST_REPAIR_IDS.get(event_id, frozenset())
        )
        active_manual_entries = {
            text_id: entry for text_id, entry in manual_entries.items()
            if entry.get("status") != "needs_manual_translation"
            and text_id not in post_repair_manual_ids
        }
        deferred_manual_entries: dict[str, dict] = {}
        manual_reports: list[dict] = []
        for missing_id in list(missing_ids):
            manual_entry = manual_entries.get(missing_id)
            if manual_entry is None:
                continue
            # A pending manual supplement is provenance/review data only. Keep
            # the canonical USA carrier completely untouched: do not feed its
            # English through the French formatter, because reflowing identical
            # prose could change simulation/admission despite the user not yet
            # approving any payload. This is the strict meaning of “pending
            # serializes original_en”: `french_dialogues` falls back to the source ROM
            # bytes exactly.
            if manual_entry.get("status") == "suppressed":
                if (event_id, missing_id) != ("013A", "C9:40D7"):
                    raise AssertionError(f"unexpected unresolved manual suppression ${event_id}/{missing_id}")
                if missing_id not in frozen_suppressions:
                    raise AssertionError(
                        f"manual suppression ${event_id}/{missing_id} must be a visually-complete frozen omission"
                    )
                event_translations[missing_id] = ""
                manual_reports.append({
                    "event_id": event_id,
                    "snes_ids": [missing_id],
                    "android_ids": [],
                    "confidence": "user_validated_snes_jp_absent_suppression",
                    "manual_supplement": True,
                    "manual_status": "suppressed",
                    "manual_reason": manual_entry["reason"],
                    "formatted_entries": [{"id": missing_id, "text": ""}],
                    "payload_policy": "validated_empty_carrier_with_adjacent_wait_omission",
                })
                continue
            if manual_entry.get("status") == "needs_manual_translation":
                manual_reports.append({
                    "event_id": event_id,
                    "snes_ids": [missing_id],
                    "android_ids": [],
                    "confidence": (
                        "user_requested_unmapped_manual_review"
                        if manual_entry.get("reason") == "user_requested_unmapped_carrier_review"
                        else "user_validated_android_absent_manual"
                    ),
                    "source_display": manual_entry.get("original_en", ""),
                    "french_display": manual_entry.get("original_en", ""),
                    "manual_supplement": True,
                    "manual_status": "needs_manual_translation",
                    "manual_reason": manual_entry.get("reason", ""),
                    "manual_translation_proposal": manual_entry.get("translation_fr", ""),
                    "formatted_entries": [],
                    "payload_policy": "canonical_usa_source_bytes_unchanged_until_approval",
                })
                continue
            if missing_id in post_repair_manual_ids:
                if manual_entry.get("status") != "translated":
                    raise AssertionError(
                        f"post-repair manual ${event_id}/{missing_id} must be translated"
                    )
                deferred_manual_entries[missing_id] = manual_entry
                continue
            value, manual_report = _format_manual_supplement(
                source_document, manual_entry, advances
            )
            if manual_only_ids and missing_id in manual_only_ids:
                manual_report["payload_policy"] = "manual_only_on_resegmented_partial_event"
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
        # A mapped carrier may also be explicitly suppressed after human review when
        # regional resegmentation proves that the standalone USA page does not exist
        # as a distinct SNES-JP unit. This is intentionally exact and currently only
        # applies to the mapped suppression $04E1/CA:2C84. Unmapped $013A/C9:40D7
        # is handled in the missing-carrier branch above. The mapped carrier must already be layout-deferred; the
        # adjacent WAIT omission is independently guarded by the structural-omission table.
        for manual_id, manual_entry in manual_entries.items():
            if manual_entry.get("status") != "suppressed":
                continue
            if (event_id, manual_id) != ("04E1", "CA:2C84"):
                raise AssertionError(f"unexpected mapped manual suppression ${event_id}/{manual_id}")
            if manual_id not in layout_deferred_ids:
                raise AssertionError(
                    f"mapped manual suppression ${event_id}/{manual_id} is no longer layout-deferred"
                )
            event_translations[manual_id] = ""
            layout_deferred_ids = [text_id for text_id in layout_deferred_ids if text_id != manual_id]
            manual_reports.append({
                "event_id": event_id,
                "snes_ids": [manual_id],
                "android_ids": [],
                "confidence": "user_validated_snes_jp_resegmentation_suppression",
                "manual_supplement": True,
                "manual_status": "suppressed",
                "manual_reason": manual_entry["reason"],
                "formatted_entries": [{"id": manual_id, "text": ""}],
            })
        if manual_reports:
            manual_supplement_reports_by_event[event_id] = manual_reports
            event_reports.extend(manual_reports)

        if event_id == "04E1":
            round67_reports, round67_resolved_missing_ids = _apply_round67_user_reviewed_scene_redistributions(
                event, event_translations, english=english, french=french,
                layout_deferred_ids=layout_deferred_ids, missing_ids=missing_ids,
            )
            event_reports = [
                report for report in event_reports
                if not (report.get("layout_deferred") and "CA:2C93" in report.get("snes_ids", []))
            ]
            event_reports.extend(round67_reports)

        layout_resegmentations = DIALOGUE_REVIEWED_UNMAPPED_LAYOUT_RESEGMENTATIONS.get(event_id, {})
        for missing_id in missing_ids:
            entry = layout_resegmentations.get(missing_id)
            if entry is None:
                continue
            by_id_check, _ = event_text_index(source_document)
            if by_id_check[missing_id].get("event_id") != event_id:
                raise AssertionError(f"reviewed unresolved layout ${event_id}/{missing_id} moved")
            event_translations[missing_id] = entry["text"]
            event_reports.append({
                "event_id": event_id,
                "snes_ids": [missing_id],
                "android_ids": [],
                "confidence": "very_high_structural_review_without_android_identity",
                "unresolved_layout_resegmentation": True,
                "reason": entry["reason"],
                "formatted_entries": [{"id": missing_id, "text": entry["text"]}],
            })

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

        # Mixed-language PARTIEL presentation: genuinely unresolved IDs are not
        # emitted into the sparse French JSON. Their stock SNES English therefore
        # remains byte-for-byte intact and visible in-game, making missing
        # alignment easy to spot during tests. Frozen user-validated omissions are
        # the only unresolved carriers that may still be explicitly suppressed.
        for missing_id in effective_suppressed_ids:
            if missing_id in event_translations:
                continue
            if missing_id not in frozen_suppressions:
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
        if layout_deferred_reports:
            event_reports.extend(layout_deferred_reports)
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
        # Alignment-incomplete/locked reviewed scenes use the same calibrated
        # presentation wrapper as complete events before their independent
        # mixed-event simulation. This changes layout only; unresolved carriers
        # remain absent and reviewed Android-FR payload remains source-derived.
        event_translations, partial_automatic_reflow = _auto_reflow_fixed_translation_carriers(
            event_translations, advances
        )
        if partial_automatic_reflow:
            automatic_216px_reflows_by_event.setdefault(event_id, []).extend(partial_automatic_reflow)
        try:
            simulation = simulate_event(
                base_rom,
                event,
                event_translations,
                font=font,
                player_names={0: "000000000", 1: "000000000", 2: "000000000"},
                omitted_command_token_indexes=structural_omission_indexes_by_event.get(event_id),
                structural_command_overrides=structural_command_overrides_by_event.get(event_id),
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
        if generic_layout_deferred_ids and (blocking_issues or implicit_wraps):
            # The generic safe-subset rule is intentionally stricter than the
            # reviewed omission families below: if the direct mixed event is
            # not already clean, do not add pagination/choice/compact repairs.
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

        # A validated-no-equivalent carrier is a deliberate identity hole, not
        # a reason to reject all surrounding proven French.  For that exact
        # PARTIEL family, reuse the same whole-event compact wrapper already
        # accepted for complete events when the direct semantic wrapper alone
        # causes a simulator failure.  Compact mode only removes formatter-added
        # presentation breaks; it does not add/move/remove any SNES command and
        # the unresolved carrier remains absent from the sparse translation map.
        if (
            (blocking_issues or implicit_wraps)
            and any(
                unmapped_by_id.get(missing_id, {}).get("reason")
                in {"validated_no_equivalent", "validated_android_omission"}
                for missing_id in missing_ids
            )
            and not active_manual_entries
            and not frozen_suppressions
        ):
            compact_translations: dict[str, str] = {}
            compact_reports: list[dict] = list(layout_deferred_reports)
            compact_failed = False
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
                    compact_message = str(exc)
                    if (
                        (validated_android_omission_hole and _partial_layout_deferable_formatter_error(compact_message))
                        or _reviewed_partial_layout_defer(event_id, mapping, compact_message) is not None
                    ):
                        continue
                    compact_failed = True
                    break
                if set(values) & set(compact_translations):
                    compact_failed = True
                    break
                if set(values) & missing_set:
                    raise AssertionError(
                        f"partial compact event ${event_id} attempted to translate unmapped semantic IDs"
                    )
                compact_translations.update(values)
                mapping_report = dict(mapping_report)
                mapping_report["partial_event"] = True
                mapping_report["semantic_layout_fallback"] = True
                compact_reports.append(mapping_report)
            if not compact_failed and compact_translations:
                _apply_targeted_wait00_fresh_page_clear(event_id, compact_translations)
                _apply_explicit_post_wait_newlines(
                    event_id, compact_translations, source_text_by_id=source_text_by_id
                )
                _apply_wait_semantics_layout_compat(event_id, compact_translations)
                try:
                    compact_simulation = simulate_event(
                        base_rom,
                        event,
                        compact_translations,
                        font=font,
                        player_names={0: "000000000", 1: "000000000", 2: "000000000"},
                        omitted_command_token_indexes=structural_omission_indexes_by_event.get(event_id),
                    )
                except ValueError:
                    compact_simulation = None
                if compact_simulation is not None:
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
                    if not compact_blocking and not compact_wraps:
                        event_translations = compact_translations
                        event_reports = compact_reports
                        simulation = compact_simulation
                        blocking_issues = []
                        implicit_wraps = 0

        # A reviewed omission/no-equivalent hole may leave otherwise proven
        # French in a four-line rolling-window state. Reuse the same generic
        # semantic extra-page repair as complete events, but only when the
        # simulator defect is pure UNPAUSED_SCROLL and the repair touches
        # mapped carriers only. The unresolved stock-English carrier remains
        # absent from the sparse translation map.
        if (
            (blocking_issues or implicit_wraps)
            and (
                bool(layout_deferred_ids)
                and event_id in DIALOGUE_REVIEWED_PARTIAL_LAYOUT_DEFERRALS
                or any(
                    unmapped_by_id.get(missing_id, {}).get("reason")
                    in {"validated_no_equivalent", "validated_android_omission"}
                    for missing_id in missing_ids
                )
            )
            and not active_manual_entries
            and not frozen_suppressions
        ):
            (
                repaired_translations,
                repaired_reports,
                repaired_simulation,
                partial_unpaused_scroll_repairs,
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
            if partial_unpaused_scroll_repairs:
                if set(repaired_translations) & missing_set:
                    raise AssertionError(
                        f"partial event ${event_id}: unpaused-scroll repair translated a reviewed hole"
                    )
                event_translations = repaired_translations
                event_reports = repaired_reports
                simulation = repaired_simulation
                unpaused_scroll_repairs_by_event[event_id] = partial_unpaused_scroll_repairs
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
        # Round 65 exact post-repair manual approval. $04E8 already required
        # ordinary PARTIEL formatting repairs while CA:437D was stock English.
        # Preserve those repairs first, then add the approved Japanese-led laugh
        # and re-simulate the complete mixed event. This is deliberately limited
        # by DIALOGUE_PARTIAL_MANUAL_POST_REPAIR_IDS.
        if not blocking_issues and not implicit_wraps and deferred_manual_entries:
            late_reports: list[dict] = []
            for manual_id, manual_entry in sorted(deferred_manual_entries.items()):
                if manual_id in event_translations:
                    raise AssertionError(
                        f"post-repair manual ${event_id}/{manual_id} already has payload"
                    )
                value, manual_report = _format_manual_supplement(
                    source_document, manual_entry, advances
                )
                event_translations[manual_id] = value
                manual_report["payload_policy"] = "apply_after_validated_partial_repairs"
                late_reports.append(manual_report)
            if late_reports:
                manual_supplement_reports_by_event.setdefault(event_id, []).extend(late_reports)
                event_reports.extend(late_reports)
            simulation = simulate_event(
                base_rom,
                event,
                event_translations,
                font=font,
                player_names={0: "000000000", 1: "000000000", 2: "000000000"},
                omitted_command_token_indexes=structural_omission_indexes_by_event.get(event_id),
                structural_command_overrides=structural_command_overrides_by_event.get(event_id),
            )
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

        # A user-approved omission inside an event that remains PARTIEL for
        # unrelated reasons is applied only after the ordinary mixed-event
        # formatter/simulator repairs have succeeded. This preserves the exact
        # previously validated layout strategy, then proves that removing the
        # selected stock phrase does not introduce a new runtime defect.
        if not blocking_issues and not implicit_wraps and partial_user_suppressions:
            for suppressed_id in sorted(partial_user_suppressions):
                if suppressed_id in event_translations:
                    raise AssertionError(
                        f"partial event ${event_id}: user-suppressed hole {suppressed_id} "
                        "was unexpectedly translated"
                    )
                event_translations[suppressed_id] = ""
            simulation = simulate_event(
                base_rom,
                event,
                event_translations,
                font=font,
                player_names={0: "000000000", 1: "000000000", 2: "000000000"},
                omitted_command_token_indexes=structural_omission_indexes_by_event.get(event_id),
                structural_command_overrides=structural_command_overrides_by_event.get(event_id),
            )
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
            partial_unresolved_semantic_ids_by_event[event_id] = sorted(
                set(effective_suppressed_ids) - round67_resolved_missing_ids
            )
            partial_layout_deferred_semantic_ids_by_event[event_id] = sorted(set(layout_deferred_ids))
            if manual_entries:
                statuses = {entry.get("status") for entry in manual_entries.values()}
                if "needs_manual_translation" in statuses:
                    partial_suppression_reason_by_event[event_id] = "manual_translation_pending"
                elif "suppressed" in statuses:
                    partial_suppression_reason_by_event[event_id] = "manual_resegmented_page_suppression"
                else:
                    partial_suppression_reason_by_event[event_id] = "manual_translation_without_android_identity"
            elif event_id in DIALOGUE_REVIEWED_UNMAPPED_LAYOUT_RESEGMENTATIONS:
                partial_suppression_reason_by_event[event_id] = "android_resegmented_shared_prefix_without_single_identity"
            elif partial_user_suppressions:
                partial_suppression_reason_by_event[event_id] = "user_validated_snes_jp_absent_suppression"
            elif layout_deferred_ids:
                partial_suppression_reason_by_event[event_id] = (
                    "validated_android_omission_with_layout_deferred"
                    if validated_android_omission_hole
                    else "alignment_unresolved_with_layout_deferred"
                )
            else:
                partial_suppression_reason_by_event[event_id] = "alignment_unresolved"
        translations_by_event[event_id] = event_translations
        reports_by_event[event_id] = event_reports
        wait00_repairs_by_event[event_id] = []
        unpaused_scroll_repairs_by_event.setdefault(event_id, [])
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

    # Round 54 may serialize every official Android-FR word available for a
    # mapped unit while still leaving a stock SNES sentence whose Android-FR
    # counterpart is genuinely absent. Keep those events visibly PARTIEL so
    # the remaining English carrier is easy to find later rather than being
    # mistaken for a fully localized event.
    for event_id, omitted_ids in DIALOGUE_ROUND54_ANDROID_FR_OMISSION_PARTIALS.items():
        if event_id not in accepted_events:
            raise ValueError(f"Round-54 FR-omission PARTIEL ${event_id} was not accepted")
        if event_id not in partial_accepted_events:
            partial_accepted_events.append(event_id)
        partial_unresolved_semantic_ids_by_event[event_id] = list(omitted_ids)
        partial_layout_deferred_semantic_ids_by_event[event_id] = []
        partial_suppression_reason_by_event[event_id] = "official_android_fr_omission"

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
    visually_complete_events = (
        DIALOGUE_USER_VALIDATED_VISUALLY_COMPLETE_EVENTS
        | DIALOGUE_USER_VALIDATED_VISUALLY_COMPLETE_STATUS_OVERRIDES
    )
    visible_partial_events = [
        event_id for event_id in partial_accepted_events
        if event_id not in visually_complete_events
    ]
    user_validated_complete_events = [
        event_id for event_id in partial_accepted_events
        if event_id in visually_complete_events
    ]
    def partial_metadata(event_id: str) -> dict:
        reason = partial_suppression_reason_by_event[event_id]
        ids = partial_unresolved_semantic_ids_by_event[event_id]
        layout_deferred_ids = partial_layout_deferred_semantic_ids_by_event.get(event_id, [])
        result = {"event_id": event_id, "partial_reason": reason}
        if reason == "manual_translation_pending":
            result["manual_pending_semantic_ids"] = sorted(
                text_id for text_id, entry in manual_supplements_by_event.get(event_id, {}).items()
                if entry.get("status") == "needs_manual_translation"
            )
            suppressed = sorted(set(ids) - set(result["manual_pending_semantic_ids"]))
            if suppressed:
                result["suppressed_semantic_ids"] = suppressed
            if layout_deferred_ids:
                result["layout_deferred_semantic_ids"] = layout_deferred_ids
        elif reason == "manual_translation_without_android_identity":
            result["manual_translated_semantic_ids"] = sorted(
                text_id for text_id, entry in manual_supplements_by_event.get(event_id, {}).items()
                if entry.get("status") == "translated"
            )
            suppressed = sorted(set(ids) - set(result["manual_translated_semantic_ids"]))
            if suppressed:
                result["suppressed_semantic_ids"] = suppressed
        elif reason == "manual_resegmented_page_suppression":
            result["manual_suppressed_semantic_ids"] = sorted(
                text_id for text_id, entry in manual_supplements_by_event.get(event_id, {}).items()
                if entry.get("status") == "suppressed"
            )
            if ids:
                result["unresolved_semantic_ids"] = ids
            if layout_deferred_ids:
                result["layout_deferred_semantic_ids"] = layout_deferred_ids
        elif reason == "mapped_but_layout_deferred":
            result["layout_deferred_semantic_ids"] = ids
        elif reason == "user_validated_snes_jp_absent_suppression":
            result["suppressed_semantic_ids"] = ids
        else:
            result["unresolved_semantic_ids"] = ids
            if layout_deferred_ids:
                result["layout_deferred_semantic_ids"] = layout_deferred_ids
        return result

    translation_document["partial_events"] = [
        partial_metadata(event_id) for event_id in visible_partial_events
    ]
    def complete_event_metadata(event_id: str) -> dict:
        ids = partial_unresolved_semantic_ids_by_event[event_id]
        if event_id in DIALOGUE_USER_VALIDATED_VISUALLY_COMPLETE_STATUS_OVERRIDES:
            return {
                "event_id": event_id,
                "unresolved_semantic_ids": ids,
                "reason": "user_validated_runtime_complete_with_unresolved_alignment",
            }
        reason = partial_suppression_reason_by_event.get(event_id)
        result = {"event_id": event_id}
        if reason == "manual_translation_without_android_identity":
            result["manual_translated_semantic_ids"] = sorted(
                text_id for text_id, entry in manual_supplements_by_event.get(event_id, {}).items()
                if entry.get("status") == "translated"
            )
            suppressed = sorted(set(ids) - set(result["manual_translated_semantic_ids"]))
            if suppressed:
                result["suppressed_semantic_ids"] = suppressed
            result["reason"] = "user_validated_complete_with_manual_jp_supplement"
        elif reason == "manual_resegmented_page_suppression":
            result["manual_suppressed_semantic_ids"] = sorted(
                text_id for text_id, entry in manual_supplements_by_event.get(event_id, {}).items()
                if entry.get("status") == "suppressed"
            )
            result["reason"] = "user_validated_complete_with_manual_resegmentation"
        elif reason == "android_resegmented_shared_prefix_without_single_identity":
            result["unresolved_semantic_ids"] = ids
            result["reason"] = "user_validated_complete_shared_prefix_resegmentation"
        elif reason == "user_validated_snes_jp_absent_suppression":
            result["suppressed_semantic_ids"] = ids
            result["reason"] = "user_validated_complete_snes_jp_absent_suppression"
        else:
            result["suppressed_semantic_ids"] = ids
            result["reason"] = "user_validated_android_adaptation_complete"
        return result

    translation_document["user_validated_visually_complete_events"] = [
        complete_event_metadata(event_id) for event_id in user_validated_complete_events
    ]
    accepted_event_set = set(accepted_events)
    translation_document["user_validated_structural_omissions"] = [
        entry for entry in DIALOGUE_USER_VALIDATED_STRUCTURAL_OMISSIONS
        if entry.get("event_id") in accepted_event_set
    ]
    translation_document["user_validated_structural_command_overrides"] = [
        entry for entry in DIALOGUE_USER_VALIDATED_STRUCTURAL_COMMAND_OVERRIDES
        if entry.get("event_id") in accepted_event_set
    ]
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
    translation_document["user_validated_stock_english_overrides"] = [
        {
            "event_id": report["event_id"],
            "id": report["snes_ids"][0],
            "android_id": report["android_ids"][0],
            "reason": report["override_reason"],
        }
        for report in formatted
        if report.get("user_validated_stock_english_override")
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
            "partial_event_policy": "reconsider every alignment-incomplete event on every run; translate every accepted Android mapping, leave unresolved semantic carriers untouched so stock SNES English remains visible, keep the event explicitly PARTIEL, preserve structural commands/layout, and require a clean independent simulation. A structurally incompatible mapped carrier may remain wholly stock under the generic safe-subset rule only when the formatter failure is an already-recognized command/PLAYER_NAME binding refusal, at least one independent French mapping remains, and the direct mixed event passes with zero errors/warnings/wraps and no adaptive repair; $015A/$0204 are explicitly excluded because their handoff records semantic resegmentation hazards. Reviewed Android-omission/no-equivalent families retain their narrower existing fallbacks. Future alignment/formatter improvements are therefore picked up automatically",
            "generic_structural_safe_subset_policy": "for a semantically accepted mapping, a recognized unsupported command/PLAYER_NAME boundary or an unserializable generated trailing page break may defer the whole mapping to stock; no command or identity changes, zero-gain events are rejected, and generic candidates receive no adaptive/compact repair before the independent clean simulation gate",
            "direct_simulator_safe_subset_policy": "second-stage fallback only after ordinary formatting or the generic structural safe-subset still fails direct simulation: the clean stock event must itself simulate without defects; at most three whole mapped carriers may be deferred; each candidate must individually reduce the direct simulator defect score; the deterministic smallest subset is accepted only when the remaining mixed event directly reaches zero errors, zero warnings and zero implicit wraps. No command, identity, layout bridge or adaptive repair is changed by this helper",
            "user_validated_visual_complete_policy": "events explicitly validated by the user as complete Android adaptations keep their simulator-clean French-only bytes and are removed from the PARTIEL badge without inventing mappings for omitted SNES-only fragments",
            "user_validated_structural_omission_policy": "a stock command may be omitted only when the user explicitly validates the omission and the command is proven by exact adjacency to an explicitly suppressed semantic ID; Round 63 additionally suppresses the standalone $04E1/CA:2C84 page and its immediately following WAIT $00 because SNES-JP resegments that meaning into the following unit; Round 67 suppresses the Western-only $013A/C9:40D7 instruction and its immediately following WAIT $00 because no distinct SNES-JP line exists and Android FR omits it; Round 57 removes PLAYER_NAME(0)+post-line WAIT with $02FC/C9:CB28 and PLAYER_NAME(2) with $0558/CA:6629, while $010C/C9:30F5 remains text-only",
            "manual_supplement_policy": "only exact allow-listed carriers may appear in translations/dialogues_manual_supplements.json: reviewed Android omissions, user-requested no-unique-equivalent carriers, plus the exact Round-62/63 mapped suppression carrier; pending entries may carry a review-only translation_fr proposal but never alter the visible payload until explicitly approved; manual entries never create Android identity",
            "user_validated_stock_english_override_policy": "when Android English identity is proven but the corresponding Android French is user-validated as a localization error, keep the semantic mapping accepted but serialize the exact canonical USA source text through the ordinary `french_dialogues` pipeline; this is non-cascading evidence and does not count as an unresolved/manual translation",
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
            "reviewed_hole_player_context_policy": "in a PARTIEL event, a trailing PLAYER_NAME borrowed only as alignment context may be returned to the immediately following reviewed no-equivalent/Android-omission stock carrier when that exact PLAYER_NAME command and hole are adjacent in the canonical SNES stream; no command or carrier moves",
            "static_speaker_dynamic_addressee_policy": "when SNES and Android EN both prove STATIC_SPEAKER:%S(n)!/? but Android FR omits only the dynamic addressee, preserve the existing SNES PLAYER_NAME in its original slot and attach only the proven punctuation after the localized static speaker label; no command is created, removed, moved or reordered",
            "existing_wait_sentence_distribution_policy": "multi-slot mappings may be redistributed at complete French sentence boundaries across one existing WAIT $00, optional TEXT_CLEAR, and optionally an already-validated pure actor-action OP_32/OP_34 + COMPLETE_ACTIONS bridge; timed WAITs and PLAYER_NAME at/across a boundary remain excluded, while one identical leading PLAYER_NAME is allowed only when it sits immediately before the first mapped carrier; every stock command stays unchanged",
            "existing_timed_wait_sentence_distribution_policy": "exactly one existing WAIT $04/$08 may separate two complete source/French sentences; the timed WAIT is preserved byte-for-byte and no other boundary command is accepted",
            "reviewed_wait10_resegmentation_policy": "a structurally reviewed two-SNES/one-Android unit may split official French at a complete sentence boundary across one exact stock WAIT $10; the timed WAIT stays byte-for-byte, a proven leading PLAYER_NAME stays in place, and cursor movement preserves the canonical newline owner ($02AE before WAIT, $042D after WAIT)",
            "single_text_x_distribution_policy": "one Android anchor may distribute over exactly two SNES text carriers separated solely by one stock TEXT_X when the first stock carrier already ends in NEWLINE and Android French itself has exactly two non-empty lines; preserve the newline and TEXT_X byte-for-byte and require both localized lines to fit independently",
            "existing_wait_weak_clause_policy": "for one two-slot WAIT $00 mapping whose source slots are each complete sentences, a French comma may be the split only before an explicit discourse connector such as alors/mais/donc/pourtant/cependant",
            "existing_action_boundary_policy": "two text slots from one Android unit may be redistributed only at a complete sentence boundary across proven OP_32 walk / OP_34 loop-action / COMPLETE_ACTIONS commands, with a complete source sentence before the action; choice events remain excluded and commands remain unchanged",
            "nonsemantic_action_carrier_policy": "one three-slot semantic/layout-only/semantic mapping may preserve the stock middle carrier while distributing two complete French sentences across action-only boundaries and clean-ROM text-free returning calls",
            "shake_effect_boundary_policy": "one two-slot mapping may cross only the proven sound-call + OP_2D $02 + timed WAIT + OP_2D $04 + sound-call sequence; both sound callees must be sound-only returning scripts and every stock effect byte stays unchanged",
            "sound_effect_action_boundary_policy": "one two-slot mapping may cross only an exact proven sound-only returning OP_20..OP_27 call + one unchanged OP_2D effect + COMPLETE_ACTIONS bridge; SNES and Android EN must contain no PLAYER_NAME, Android FR may contribute exactly one comma vocative that is removed because no SNES PLAYER_NAME exists to carry it, the remaining FR is split only at a complete sentence boundary, and one newline may be materialized only when the unchanged bridge would otherwise exceed the same-line parser/pixel budget",
            "reviewed_sequence_block_policy": "a user-validated sequence_block_with_android_extra mapping may redistribute four Android French anchors over three semantic SNES slots only in the exact reviewed semantic/layout/action/semantic/WAIT+clear shape; the stock layout carrier remains untouched",
            "cross_mapping_action_sentence_overflow_policy": "one leading newline plus semantic pagination may repair a soft or decoded-capacity parser wrap only across an adjacent OP_32/OP_34 + COMPLETE_ACTIONS boundary after a complete localized sentence; accept only after clean resimulation",
            "pure_unpaused_scroll_policy": "after compact fallback fails, one semantic-boundary extra page may be tried only when UNPAUSED_SCROLL is the sole simulator defect; accept only after clean resimulation",
            "cross_mapping_sentence_overflow_policy": "after all earlier fallbacks fail, a parser-wrap + unpaused-scroll event may add one newline at a proven adjacent sentence boundary and one semantic page break; accept only after clean resimulation",
            "wait00_exact_overlap_policy": "no generic WAIT $00 carry-over cleanup; presentation changes require explicit per-event runtime validation; timed WAITs unchanged",
            "targeted_wait00_fresh_page_policy": "keep stock WAIT $00 bytes unchanged; $0106/C9:2994 is runtime-validated and the eight round13 detector matches are explicitly converted from newline-only carriers to TEXT_CLEAR as a single user-requested runtime-test batch; no generic WAIT carry-over cleanup",
            "wait_semantics_policy": "runtime-validated: WAIT pauses without advancing the text cursor; only explicit $7F NEWLINE or TEXT_CLEAR changes the physical line/page",
            "explicit_post_wait_newline_policy": "materialize reviewed formatter line boundaries that older simulation had implicitly attributed to WAIT; after compact formatting, a sole decoded-capacity wrap may additionally receive one leading NEWLINE only at an immediate text -> WAIT $00 -> text complete-sentence boundary when exactly one such candidate makes the whole event simulator-clean; keep WAIT bytes unchanged; use TEXT_CLEAR instead of NEWLINE when a three-line window would otherwise scroll before the next pause",
            "choice_row_prefix_restore_policy": "when Android prose reflow removes the stock final NEWLINE + optional spaces + '(' immediately before CHOICE_BEGIN and the first stock CHOICE_OPTION would rewind over translated prompt text, restore only that stock row suffix; for a standalone decorative '(' carrier after dynamic stock output, one explicit NEWLINE may be prefixed for the same first-anchor condition; no option coordinate changes are made by this repair and unrelated new simulator defects reject it",
            "adaptive_choice_anchor_policy": "keep the first CHOICE_OPTION stock; when a later stock coordinate would overwrite the preceding localized label in the decoded row, move only that later coordinate right to the minimum cell immediately after the label; accept only a rightward <32 coordinate whose whole event passes the independent zero-error/zero-warning/zero-wrap simulation; runtime validated by the $03/$11 -> $03/$12 Temple de l'Eau/Pandora diagnostic",
            "adaptive_choice_decoration_policy": "preserve the canonical outer ( ... ) decoration whenever the normal choice event is simulator-clean; only after a width/layout rejection, retry by removing the proven opening/closing parenthesis pair plus its adjacent horizontal padding; when stripping alone is insufficient, it may be composed with the already validated later-anchor-only right shift, while the first CHOICE_OPTION remains stock; accept only if the whole event passes the same zero-error/zero-warning/zero-wrap gate",
            "reviewed_choice_layout_recipe_policy": "Round-72 reviewed decoration removals are stored as structural event/carrier recipes with no French prose. They are reapplied deterministically after Android-FR formatting; if restoring the choice-row newline would otherwise force a fresh page, only the owning Android-backed prompt is retried with the existing compact wrapper before the reviewed decoration is stripped.",
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
                len(partial_unresolved_semantic_ids_by_event[event_id]) for event_id in visible_partial_events
            ),
            "partial_layout_deferred_id_count": sum(
                len(partial_layout_deferred_semantic_ids_by_event.get(event_id, []))
                for event_id in visible_partial_events
            ),
            "generic_structural_safe_subset_event_count": sum(
                event_id in generic_layout_deferred_semantic_ids_by_event
                for event_id in visible_partial_events
            ),
            "generic_structural_safe_subset_deferred_id_count": sum(
                len(set(generic_layout_deferred_semantic_ids_by_event.get(event_id, [])))
                for event_id in visible_partial_events
            ),
            "direct_simulator_safe_subset_event_count": len({
                report.get("event_id")
                for report in formatted
                if report.get("layout_deferred_policy") == "direct_simulator_safe_subset"
            }),
            "direct_simulator_safe_subset_deferred_id_count": sum(
                1
                for report in formatted
                if report.get("layout_deferred_policy") == "direct_simulator_safe_subset"
            ),
            "accepted_semantic_source_id_count": accepted_semantic_ids,
            "translation_entry_count": len(ordered_entries),
            "fragment_spacing_repaired_event_count": sum(bool(value) for value in fragment_spacing_repairs_by_event.values()),
            "fragment_spacing_repair_count": sum(len(value) for value in fragment_spacing_repairs_by_event.values()),
            "explicit_post_wait_newline_repaired_event_count": sum(bool(value) for value in explicit_post_wait_newline_repairs_by_event.values()),
            "explicit_post_wait_newline_repair_count": sum(len(value) for value in explicit_post_wait_newline_repairs_by_event.values()),
            "round48_pagination_repaired_event_count": sum(bool(value) for value in round48_pagination_repairs_by_event.values()),
            "round48_pagination_repair_count": sum(len(value) for value in round48_pagination_repairs_by_event.values()),
            "round49_04e9_wait00_clear_repaired_event_count": sum(bool(value) for value in round49_04e9_wait00_clear_repairs_by_event.values()),
            "round49_04e9_wait00_clear_repair_count": sum(len(value) for value in round49_04e9_wait00_clear_repairs_by_event.values()),
            "round50_01ce_choice_page_clear_repaired_event_count": sum(bool(value) for value in round50_01ce_choice_page_clear_repairs_by_event.values()),
            "round50_01ce_choice_page_clear_repair_count": sum(len(value) for value in round50_01ce_choice_page_clear_repairs_by_event.values()),
            "round54_nonsemantic_android_supplement_event_count": sum(bool(value) for value in round54_nonsemantic_android_supplements_by_event.values()),
            "round54_nonsemantic_android_supplement_count": sum(len(value) for value in round54_nonsemantic_android_supplements_by_event.values()),
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
            "reviewed_hole_player_context_repaired_event_count": sum(
                bool(reviewed_hole_player_context_repairs_by_event.get(event_id))
                for event_id in accepted_events
            ),
            "reviewed_hole_player_context_repair_count": sum(
                len(reviewed_hole_player_context_repairs_by_event.get(event_id, []))
                for event_id in accepted_events
            ),
            "preserved_static_speaker_dynamic_addressee_mapping_count": sum(
                bool(entry.get("preserved_static_speaker_dynamic_addressee"))
                for entry in formatted
            ),
            "existing_wait_sentence_distribution_mapping_count": sum(
                bool(entry.get("existing_wait_sentence_distribution")) for entry in formatted
            ),
            "existing_wait_leading_player_mapping_count": sum(
                entry.get("existing_wait_leading_player_index") is not None for entry in formatted
            ),
            "partial_semantic_layout_fallback_event_count": sum(
                any(report.get("semantic_layout_fallback") for report in reports_by_event.get(event_id, []))
                for event_id in visible_partial_events
            ),
            "existing_timed_wait_sentence_distribution_mapping_count": sum(
                bool(entry.get("existing_timed_wait_sentence_distribution")) for entry in formatted
            ),
            "reviewed_wait10_resegmentation_mapping_count": sum(
                bool(entry.get("structural_timed_wait10_resegmentation")) for entry in formatted
            ),
            "single_text_x_distribution_mapping_count": sum(
                bool(entry.get("structural_single_text_x_distribution")) for entry in formatted
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
            "sound_effect_action_sentence_distribution_mapping_count": sum(
                bool(entry.get("sound_effect_action_sentence_distribution")) for entry in formatted
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
            "reviewed_choice_layout_recipe_event_count": len(reviewed_choice_layout_recipes),
            "reviewed_choice_compact_reflow_event_count": sum(
                bool(reviewed_choice_compact_repairs_by_event.get(event_id))
                for event_id in accepted_events
            ),
            "excluded_event_count": len(excluded_events),
            "excluded_stage_counts": stage_counts,
        },
        "accepted_events": accepted_events,
        "user_validated_visually_complete_events": [
            complete_event_metadata(event_id) for event_id in user_validated_complete_events
        ],
        "user_validated_structural_omissions": list(DIALOGUE_USER_VALIDATED_STRUCTURAL_OMISSIONS),
        "user_validated_structural_command_overrides": list(DIALOGUE_USER_VALIDATED_STRUCTURAL_COMMAND_OVERRIDES),
        "manual_dialogue_supplements": translation_document["manual_dialogue_supplements"],
        "user_validated_stock_english_overrides": translation_document["user_validated_stock_english_overrides"],
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
        "reviewed_choice_layout_recipes": [
            reviewed_choice_layout_recipes[event_id]
            for event_id in sorted(reviewed_choice_layout_recipes, key=lambda value: int(value, 16))
        ],
        "reviewed_choice_compact_repairs": [
            {"event_id": event_id, **repair}
            for event_id in accepted_events
            for repair in reviewed_choice_compact_repairs_by_event.get(event_id, [])
        ],
        "wait00_overlap_repairs": [
            {"event_id": event_id, **repair}
            for event_id in accepted_events
            for repair in wait00_repairs_by_event.get(event_id, [])
        ],
        "round48_pagination_repairs": [
            {"event_id": event_id, **repair}
            for event_id in accepted_events
            for repair in round48_pagination_repairs_by_event.get(event_id, [])
        ],
        "round49_04e9_wait00_clear_repairs": [
            {"event_id": event_id, **repair}
            for event_id in accepted_events
            for repair in round49_04e9_wait00_clear_repairs_by_event.get(event_id, [])
        ],
        "round50_01ce_choice_page_clear_repairs": [
            {"event_id": event_id, **repair}
            for event_id in accepted_events
            for repair in round50_01ce_choice_page_clear_repairs_by_event.get(event_id, [])
        ],
        "automatic_216px_reflows": [
            {"event_id": event_id, "reflows": repairs}
            for event_id, repairs in automatic_216px_reflows_by_event.items()
            if repairs
        ],
        "carrier_boundary_newline_repairs": [
            {"event_id": event_id, "repairs": repairs}
            for event_id, repairs in carrier_boundary_newline_repairs_by_event.items()
            if repairs
        ],
        "carrier_repack_repairs": [
            {"event_id": event_id, "repairs": repairs}
            for event_id, repairs in carrier_repack_repairs_by_event.items()
            if repairs
        ],
        "live_player_prefix_reflow_repairs": [
            {"event_id": event_id, "repairs": repairs}
            for event_id, repairs in live_player_prefix_reflow_repairs_by_event.items()
            if repairs
        ],
        "source_derived_layout_search_repairs": [
            {"event_id": event_id, "repairs": repairs}
            for event_id, repairs in source_derived_layout_search_repairs_by_event.items()
            if repairs
        ],
        "round54_nonsemantic_android_supplements": [
            repair
            for event_id in accepted_events
            for repair in round54_nonsemantic_android_supplements_by_event.get(event_id, [])
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
        "reviewed_hole_player_context_repairs": [
            {"event_id": event_id, **repair}
            for event_id in accepted_events
            for repair in reviewed_hole_player_context_repairs_by_event.get(event_id, [])
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
            "dialogue-review-round25",
            "dialogue-review-round31",
            "dialogue-review-round33",
            "dialogue-review-round34",
            "dialogue-review-round39",
            "dialogue-review-round40",
            "dialogue-review-round41",
            "dialogue-review-round42",
            "dialogue-review-round43",
            "dialogue-review-round44",
            "dialogue-review-round45",
            "dialogue-review-round46",
            "dialogue-review-round47",
            "dialogue-review-round48",
            "dialogue-review-round49",
            "dialogue-review-round50",
            "dialogue-review-round51",
            "dialogue-review-round52",
            "dialogue-review-round53",
            "dialogue-review-round54",
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
            elif args.only == "dialogue-review-round25":
                document = make_dialogue_review_round25_report(
                    english,
                    french,
                    english_path=english_path,
                    french_path=french_path,
                )
                output = (args.output or DEFAULT_DIALOGUE_REVIEW_ROUND25_OUTPUT).resolve()
            elif args.only == "dialogue-review-round31":
                document = make_dialogue_review_round31_report(
                    english,
                    french,
                    english_path=english_path,
                    french_path=french_path,
                )
                output = (args.output or DEFAULT_DIALOGUE_REVIEW_ROUND31_OUTPUT).resolve()
            elif args.only == "dialogue-review-round33":
                document = make_dialogue_review_round33_report(
                    english,
                    french,
                    english_path=english_path,
                    french_path=french_path,
                )
                output = (args.output or DEFAULT_DIALOGUE_REVIEW_ROUND33_OUTPUT).resolve()
            elif args.only == "dialogue-review-round34":
                document = make_dialogue_review_round34_report(
                    english,
                    french,
                    english_path=english_path,
                    french_path=french_path,
                )
                output = (args.output or DEFAULT_DIALOGUE_REVIEW_ROUND34_OUTPUT).resolve()
            elif args.only == "dialogue-review-round39":
                document = make_dialogue_review_round39_report(
                    english,
                    french,
                    english_path=english_path,
                    french_path=french_path,
                )
                output = (args.output or DEFAULT_DIALOGUE_REVIEW_ROUND39_OUTPUT).resolve()
            elif args.only == "dialogue-review-round40":
                document = make_dialogue_review_round40_report(
                    english,
                    french,
                    english_path=english_path,
                    french_path=french_path,
                )
                output = (args.output or DEFAULT_DIALOGUE_REVIEW_ROUND40_OUTPUT).resolve()
            elif args.only == "dialogue-review-round41":
                document = make_dialogue_review_round41_report(
                    english,
                    french,
                    english_path=english_path,
                    french_path=french_path,
                )
                output = (args.output or DEFAULT_DIALOGUE_REVIEW_ROUND41_OUTPUT).resolve()
            elif args.only == "dialogue-review-round42":
                document = make_dialogue_review_round42_report(
                    english,
                    french,
                    english_path=english_path,
                    french_path=french_path,
                )
                output = (args.output or DEFAULT_DIALOGUE_REVIEW_ROUND42_OUTPUT).resolve()
            elif args.only == "dialogue-review-round43":
                document = make_dialogue_review_round43_report(
                    english,
                    french,
                    english_path=english_path,
                    french_path=french_path,
                )
                output = (args.output or DEFAULT_DIALOGUE_REVIEW_ROUND43_OUTPUT).resolve()
            elif args.only == "dialogue-review-round44":
                document = make_dialogue_review_round44_report(
                    english,
                    french,
                    english_path=english_path,
                    french_path=french_path,
                )
                output = (args.output or DEFAULT_DIALOGUE_REVIEW_ROUND44_OUTPUT).resolve()
            elif args.only == "dialogue-review-round45":
                document = make_dialogue_review_round45_report(
                    english,
                    french,
                    english_path=english_path,
                    french_path=french_path,
                )
                output = (args.output or DEFAULT_DIALOGUE_REVIEW_ROUND45_OUTPUT).resolve()
            elif args.only == "dialogue-review-round46":
                document = make_dialogue_review_round46_report()
                output = (args.output or DEFAULT_DIALOGUE_REVIEW_ROUND46_OUTPUT).resolve()
            elif args.only == "dialogue-review-round47":
                document = make_dialogue_review_round47_report()
                output = (args.output or DEFAULT_DIALOGUE_REVIEW_ROUND47_OUTPUT).resolve()
            elif args.only == "dialogue-review-round48":
                document = make_dialogue_review_round48_report()
                output = (args.output or DEFAULT_DIALOGUE_REVIEW_ROUND48_OUTPUT).resolve()
            elif args.only == "dialogue-review-round49":
                document = make_dialogue_review_round49_report()
                output = (args.output or DEFAULT_DIALOGUE_REVIEW_ROUND49_OUTPUT).resolve()
            elif args.only == "dialogue-review-round50":
                document = make_dialogue_review_round50_report(
                    english, french,
                    english_path=english_path, french_path=french_path,
                )
                output = (args.output or DEFAULT_DIALOGUE_REVIEW_ROUND50_OUTPUT).resolve()
            elif args.only == "dialogue-review-round51":
                document = make_dialogue_review_round51_report()
                output = (args.output or DEFAULT_DIALOGUE_REVIEW_ROUND51_OUTPUT).resolve()
            elif args.only == "dialogue-review-round52":
                document = make_dialogue_review_round52_report()
                output = (args.output or DEFAULT_DIALOGUE_REVIEW_ROUND52_OUTPUT).resolve()
            elif args.only == "dialogue-review-round53":
                document = make_dialogue_review_round53_report()
                output = (args.output or DEFAULT_DIALOGUE_REVIEW_ROUND53_OUTPUT).resolve()
            elif args.only == "dialogue-review-round54":
                document = make_dialogue_review_round54_report()
                output = (args.output or DEFAULT_DIALOGUE_REVIEW_ROUND54_OUTPUT).resolve()
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
