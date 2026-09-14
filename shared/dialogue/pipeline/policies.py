from __future__ import annotations

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


DIALOGUE_REVIEWED_AUTO_OVERRIDES = frozenset({"CA:696C", "C9:E5BF"})


DIALOGUE_VALIDATED_ALTERNATIVE_GROUPS = {
    "C9:089B": ((3314,), (3360,)),
    "C9:0C19": ((2667,), (2793,)),
    "C9:0B03": ((2449, 2450), (2463, 2464)),
    "C9:392C": ((792,), (796,)),
}


DIALOGUE_USER_VALIDATED_VISUALLY_COMPLETE_SUPPRESSIONS = {
    "0103": frozenset({"C9:2627", "C9:26A8", "C9:2728", "C9:2735", "C9:2745"}),
    "013A": frozenset({"C9:40D7"}),
    "017F": frozenset({"C9:55FC"}),
    "01DC": frozenset({"C9:804A"}),
}


DIALOGUE_USER_VALIDATED_PARTIAL_SUPPRESSIONS = {
    "010C": frozenset({"C9:30F5"}),
    "02FC": frozenset({"C9:CB28"}),
    "0558": frozenset({"CA:6629"}),
}


DIALOGUE_USER_VALIDATED_SEMANTICALLY_COMPLETE_EVENTS = frozenset({
    "001E", "0042", "00EE", "00F1", "00F3", "0207", "0208", "024F",
    "0278", "02E1", "02FC", "035F", "04E1", "04E8", "0558",
})


DIALOGUE_USER_VALIDATED_VISUALLY_COMPLETE_EVENTS = frozenset(
    set(DIALOGUE_USER_VALIDATED_VISUALLY_COMPLETE_SUPPRESSIONS)
    | set(DIALOGUE_USER_VALIDATED_SEMANTICALLY_COMPLETE_EVENTS)
)


DIALOGUE_USER_VALIDATED_VISUALLY_COMPLETE_STATUS_OVERRIDES = frozenset({"0602"})


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

)


DIALOGUE_FINAL_USER_VALIDATED_STRUCTURAL_COMMAND_OVERRIDES = ({'event_id': '0112',
  'commands': [{'name': 'PLAYER_NAME',
                'args': '00',
                'immediately_before_text_id': 'C9:339F',
                'omit': True},
               {'name': 'PLAYER_NAME',
                'args': '00',
                'immediately_before_text_id': 'C9:3450',
                'omit': True},
               {'name': 'PLAYER_NAME',
                'args': '00',
                'immediately_before_text_id': 'C9:34E5',
                'omit': True}],
  'reason': 'round85_55_user_requested_fresh_page_at_player_speaker_turn'},
 {'event_id': '01DD',
  'commands': [{'name': 'PLAYER_NAME',
                'args': '01',
                'immediately_before_text_id': 'C9:80A1',
                'omit': True}],
  'reason': 'round85_55_user_requested_fresh_page_at_player_speaker_turn'},
 {'event_id': '02EE',
  'commands': [{'name': 'PLAYER_NAME',
                'args': '02',
                'immediately_before_text_id': 'C9:C84D',
                'omit': True}],
  'reason': 'round85_55_user_requested_fresh_page_at_player_speaker_turn'},
 {'event_id': '03AA',
  'commands': [{'name': 'PLAYER_NAME',
                'args': '00',
                'immediately_before_text_id': 'C9:E165',
                'omit': True},
               {'name': 'PLAYER_NAME',
                'args': '00',
                'immediately_before_text_id': 'C9:E1BB',
                'omit': True},
               {'name': 'PLAYER_NAME',
                'args': '01',
                'immediately_before_text_id': 'C9:E20B',
                'omit': True},
               {'name': 'PLAYER_NAME',
                'args': '01',
                'immediately_before_text_id': 'C9:E253',
                'omit': True}],
  'reason': 'round85_55_user_requested_fresh_page_at_player_speaker_turn'},
 {'event_id': '04A1',
  'commands': [{'name': 'PLAYER_NAME',
                'args': '00',
                'immediately_before_text_id': 'CA:17EF',
                'omit': True}],
  'reason': 'round85_55_user_requested_fresh_page_at_player_speaker_turn'})

DIALOGUE_USER_VALIDATED_STRUCTURAL_COMMAND_INSERTIONS = ({'event_id': '0020',
  'insertions': [{'before_command': {'name': 'OP_20', 'args': '1E', 'immediately_before_text_id': 'C9:09B9'},
                  'commands': [{'name': 'WAIT', 'args': '00'}, {'name': 'TEXT_CLEAR', 'args': ''}]}],
  'reason': 'dialogue_audit_lot1_0020_fresh_page_after_dynamic_speaker'},
{'event_id': '0021',
  'insertions': [{'before_command': {'name': 'OP_20', 'args': '1E', 'immediately_before_text_id': 'C9:0A04'},
                  'commands': [{'name': 'WAIT', 'args': '00'}, {'name': 'TEXT_CLEAR', 'args': ''}]}],
  'reason': 'dialogue_audit_lot1_0021_fresh_page_after_dynamic_speaker'},
{'event_id': '0022',
  'insertions': [{'before_command': {'name': 'OP_20', 'args': '1E', 'immediately_before_text_id': 'C9:0A58'},
                  'commands': [{'name': 'WAIT', 'args': '00'}, {'name': 'TEXT_CLEAR', 'args': ''}]}],
  'reason': 'dialogue_second_pass_lot1_0022_fresh_page_after_dynamic_speaker'},
{'event_id': '0592',
  'insertions': [{'before_command': {'name': 'PLAYER_NAME',
                                     'args': '00',
                                     'immediately_before_text_id': 'CA:7565'},
                  'commands': [{'name': 'WAIT', 'args': '00'},
                               {'name': 'TEXT_CLEAR', 'args': ''}]}],
  'reason': 'dialogue_audit_lot12_validated_fresh_page_after_complete_android_fr_sentence'},
{'event_id': '02B7',
  'insertions': [{'before_command': {'name': 'OP_12',
                                     'args': 'AF',
                                     'immediately_before_text_id': 'C9:BA6C'},
                  'commands': [{'name': 'WAIT', 'args': '00'},
                               {'name': 'TEXT_CLEAR', 'args': ''}]}],
  'reason': 'dialogue_audit_validated_page_boundary_before_second_unit'},
 {'event_id': '038D',
  'insertions': [{'before_command': {'name': 'COMPLETE_ACTIONS',
                                     'args': '',
                                     'immediately_before_text_id': 'C9:DBA9'},
                  'commands': [{'name': 'TEXT_CLEAR', 'args': ''}]}],
  'reason': 'dialogue_audit_validated_clear_after_fire_seed_wait'},
 {'event_id': '038C',
  'insertions': [{'before_command': {'name': 'TEXT_X',
                                     'args': '03',
                                     'immediately_before_text_id': 'C9:DAB5'},
                  'commands': [{'name': 'WAIT', 'args': '00'},
                               {'name': 'TEXT_CLEAR', 'args': ''}]}],
  'reason': 'dialogue_audit_validated_fresh_choice_page_after_dynamic_prompt'},
 {'event_id': '036F',
  'insertions': [{'before_command': {'name': 'OP_20',
                                     'args': '52',
                                     'immediately_before_text_id': 'C9:D563'},
                  'commands': [{'name': 'WAIT', 'args': '00'},
                               {'name': 'TEXT_CLEAR', 'args': ''}]},
                 {'before_command': {'name': 'COMPLETE_ACTIONS',
                                     'args': '',
                                     'immediately_before_text_id': 'C9:D591'},
                  'commands': [{'name': 'TEXT_CLEAR', 'args': ''}]}],
  'reason': 'dialogue_audit_validated_scopion_scene_page_boundaries'},
 {'event_id': '0023',
  'insertions': [{'before_command': {'name': 'OP_20',
                                     'args': '1E',
                                     'immediately_before_text_id': 'C9:0A9F'},
                  'commands': [{'name': 'WAIT', 'args': '00'},
                               {'name': 'TEXT_CLEAR', 'args': ''}]}],
  'reason': 'dialogue_audit_restore_android_fr_dynamic_speaker_without_unpaused_scroll'},
{'event_id': '04E2',
  'insertions': [{'before_command': {'name': 'PLAYER_NAME',
                                     'args': '02',
                                     'immediately_before_text_id': 'CA:32D7'},
                  'commands': [{'name': 'WAIT', 'args': '00'},
                               {'name': 'TEXT_CLEAR', 'args': ''}]}],
  'reason': 'round85_dialogue_audit_restore_android_fr_1280_before_1281'},
 {'event_id': '0112',
  'insertions': [{'before_command': {'name': 'PLAYER_NAME',
                                     'args': '00',
                                     'immediately_before_text_id': 'C9:339F'},
                  'commands': [{'name': 'WAIT', 'args': '00'}]},
                 {'before_command': {'name': 'PLAYER_NAME',
                                     'args': '00',
                                     'immediately_before_text_id': 'C9:34E5'},
                  'commands': [{'name': 'WAIT', 'args': '00'}]}],
  'reason': 'round85_55_user_requested_interactive_pause_before_new_player_speaker_page'},
 {'event_id': '01DD',
  'insertions': [{'before_command': {'name': 'PLAYER_NAME',
                                     'args': '01',
                                     'immediately_before_text_id': 'C9:80A1'},
                  'commands': [{'name': 'WAIT', 'args': '00'}]}],
  'reason': 'round85_55_user_requested_interactive_pause_before_new_player_speaker_page'},
 {'event_id': '02EE',
  'insertions': [{'before_command': {'name': 'PLAYER_NAME',
                                     'args': '02',
                                     'immediately_before_text_id': 'C9:C84D'},
                  'commands': [{'name': 'WAIT', 'args': '00'}]}],
  'reason': 'round85_55_user_requested_interactive_pause_before_new_player_speaker_page'},
 {'event_id': '03AA',
  'insertions': [{'before_command': {'name': 'PLAYER_NAME',
                                     'args': '00',
                                     'immediately_before_text_id': 'C9:E165'},
                  'commands': [{'name': 'WAIT', 'args': '00'}]},
                 {'before_command': {'name': 'PLAYER_NAME',
                                     'args': '01',
                                     'immediately_before_text_id': 'C9:E20B'},
                  'commands': [{'name': 'WAIT', 'args': '00'}]},
                 {'before_command': {'name': 'PLAYER_NAME',
                                     'args': '01',
                                     'immediately_before_text_id': 'C9:E253'},
                  'commands': [{'name': 'WAIT', 'args': '00'}]}],
  'reason': 'round85_55_user_requested_interactive_pause_before_new_player_speaker_page'},
 {'event_id': '04A1',
  'insertions': [{'before_command': {'name': 'PLAYER_NAME',
                                     'args': '00',
                                     'immediately_before_text_id': 'CA:17EF'},
                  'commands': [{'name': 'WAIT', 'args': '00'}]}],
  'reason': 'round85_55_user_requested_interactive_pause_before_new_player_speaker_page'},
 {'event_id': '05F8',
  'insertions': [{'before_command': {'name': 'PLAYER_NAME',
                                     'args': '00',
                                     'immediately_before_text_id': 'CA:7AEC'},
                  'commands': [{'name': 'TEXT_CLEAR', 'args': ''}]},
                 {'before_command': {'name': 'PLAYER_NAME',
                                     'args': '02',
                                     'immediately_before_text_id': 'CA:839E'},
                  'commands': [{'name': 'WAIT', 'args': '00'},
                               {'name': 'TEXT_CLEAR', 'args': ''}]}],
  'reason': 'round85_55_user_requested_keep_dynamic_speaker_name_with_colon_and_reply'},
 {'event_id': '028A',
  'insertions': [{'before_command': {'name': 'PLAYER_NAME',
                                     'args': '01',
                                     'immediately_before_text_id': 'C9:A9CE'},
                  'commands': [{'name': 'TEXT_CLEAR', 'args': ''}]}],
  'reason': 'second_pass_lot6_validated_fresh_page_after_wait00_before_new_speaker'},
 {'event_id': '04B6',
  'insertions': [{'before_command': {'name': 'PLAYER_NAME',
                                     'args': '02',
                                     'immediately_before_text_id': 'CA:237E'},
                  'commands': [{'name': 'TEXT_CLEAR', 'args': ''}]}],
  'reason': 'second_pass_lot10_validated_fresh_page_after_dryad_wait00'},
 {'event_id': '04E1',
  'insertions': [{'before_command': {'name': 'PLAYER_NAME',
                                     'args': '01',
                                     'immediately_before_text_id': 'CA:2E98'},
                  'commands': [{'name': 'TEXT_CLEAR', 'args': ''}]}],
  'reason': 'second_pass_lot11_validated_fresh_page_after_thanatos_wait00'},
 {'event_id': '04EA',
  'insertions': [{'before_command': {'name': 'PLAYER_NAME',
                                     'args': '00',
                                     'immediately_before_text_id': 'CA:49D3'},
                  'commands': [{'name': 'TEXT_CLEAR', 'args': ''}]},
                 {'before_command': {'name': 'OP_32',
                                     'args': '0C 00',
                                     'immediately_before_text_id': 'CA:4B1E'},
                  'commands': [{'name': 'TEXT_CLEAR', 'args': ''}]}],
  'reason': 'second_pass_lot11_validated_fresh_pages_after_luka_wait00'})


DIALOGUE_USER_VALIDATED_PARTIAL_LAYOUT_PRESERVATIONS = ()


DIALOGUE_REVIEWED_PARTIAL_LAYOUT_DEFERRALS = {}


DIALOGUE_GENERIC_PARTIAL_LAYOUT_DEFERRAL_BLOCKLIST = frozenset({"015A", "0204"})


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


DIALOGUE_USER_REQUESTED_UNMAPPED_MANUAL_REVIEW_IDS = {
    "00EE": frozenset({"C9:2179"}),
    "013A": frozenset({"C9:40D7"}),
    "00F1": frozenset({"C9:2208"}),
    "00F3": frozenset({"C9:2268"}),
    "04E8": frozenset({"CA:437D"}),
}


DIALOGUE_PARTIAL_MANUAL_POST_REPAIR_IDS = {
    "04E8": frozenset({"CA:437D"}),
}


DIALOGUE_MANUAL_ONLY_RESEGMENTED_PARTIAL_IDS = {
}


DIALOGUE_USER_REQUESTED_MAPPED_MANUAL_REVIEW_IDS = {
    "04E1": frozenset({"CA:2C84"}),
}


DIALOGUE_REVIEWED_UNMAPPED_LAYOUT_RESEGMENTATIONS = {
    "001E": {
        "C9:0970": {
            "text": "\n",
            "reason": "shared Jehk/Jach subject prefix is absorbed by Android 2453/2455/2458/2461; preserve the stock leading NEWLINE after WAIT $00",
        },
    },
}


DIALOGUE_USER_VALIDATED_STOCK_ENGLISH_OVERRIDES = {
    ("0689", "CA:8F20", 769): (
        "Android FR duplicates the Leather-Whip chest text onto the Magic Rope; "
        "$0689 OP_1E A4 proves the Whip/Leather Whip identity, while $0687 OP_1E 46 "
        "is the actual Magic Rope chest."
    ),
}


