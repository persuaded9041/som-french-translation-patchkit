#!/usr/bin/env python3
"""Lock Round-67 targeted $013A/$04E1/$04E2 review and serialization decisions."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANUAL = ROOT / "translations" / "dialogues_manual_supplements.json"
FRENCH = ROOT / "translations" / "dialogues_french.json"
MASS = ROOT / "mappings" / "android" / "dialogues_format_mass.json"
FOCUSED = ROOT / "mappings" / "android" / "dialogue_04E2_android_fr_round67.html"


def die(msg: str) -> None:
    raise SystemExit(f"Round-67 targeted-dialogue check failed: {msg}")


def active_entries(document: dict) -> dict[str, str]:
    return {
        e["id"]: e["text"]
        for group in document.get("groups", [])
        for e in group.get("entries", [])
    }


def main() -> None:
    manual = json.loads(MANUAL.read_text(encoding="utf-8"))
    entries = {e["id"]: e for e in manual["entries"]}
    c40d7 = entries.get("C9:40D7")
    if not c40d7 or c40d7.get("event_id") != "013A":
        die("$013A/C9:40D7 manual review missing/moved")
    if c40d7.get("status") != "suppressed" or c40d7.get("reason") != "user_validated_snes_jp_absent_suppression":
        die("$013A/C9:40D7 must remain the validated SNES-JP-absent suppression")
    if c40d7.get("original_jp") is not None or c40d7.get("original_jp_status") != "no_distinct_snes_jp_counterpart_confirmed":
        die("$013A/C9:40D7 JP-absence provenance drifted")
    if c40d7.get("original_jp_context_event_id") != "013A" or c40d7.get("original_jp_context_carrier_id") != "C9:4F39":
        die("$013A/C9:40D7 JP context binding drifted")
    if c40d7.get("translation_fr") != "":
        die("$013A/C9:40D7 suppression proposal must not invent a French payload")

    french = json.loads(FRENCH.read_text(encoding="utf-8"))
    active = active_entries(french)
    if active.get("C9:40D7") != "":
        die("validated $013A/C9:40D7 suppression must serialize as empty text")
    structural_omissions = french.get("user_validated_structural_omissions", [])
    e013a_omission = next((x for x in structural_omissions if x.get("event_id") == "013A"), None)
    if e013a_omission != {
        "event_id": "013A",
        "suppressed_semantic_ids": ["C9:40D7"],
        "suppressed_commands": [{
            "name": "WAIT",
            "args": "00",
            "immediately_after_text_id": "C9:40D7",
        }],
        "reason": "round67_user_validated_snes_jp_absent_android_fr_adaptation_suppression",
    }:
        die(f"$013A structural suppression drifted: {e013a_omission!r}")

    expected_04e1 = {
        "CA:2BED": "Mon corps actuel est sur le point de\nse corrompre.\nIl me faut un nouveau corps...",
        "CA:2C3A": "Un être humain ordinaire est incapable\nde contenir longtemps mon énergie.\fIl me faut donc le corps d'un être\nd'exception.\fOr, une ou deux fois par siècle, un\nhumain naît avec le Sang des ténèbres\ndans les veines.",
        "CA:2C84": "",
        "CA:2C93": "Lorsque je me transfère dans ce corps\nexceptionnel, mon pouvoir se trouve\ndécuplé.\fUn corps... comme celui de Durac !\fSon pouvoir maléfique a dû être scellé\nquand il était jeune... Il n'en est\ndevenu que plus droit et juste !\fAvec mon nouveau corps et la\nForteresse de Mana, je forgerai un\nmonde à mon image !",
    }
    for sid, text in expected_04e1.items():
        if active.get(sid) != text:
            die(f"$04E1 {sid} payload drifted: {active.get(sid)!r}")

    expected_04e2 = {
        "CA:32C5": " : Non !\nC'est pas possible !\n",
        "CA:32D7": "Ils se sont sûrement échappés !",
    }
    for sid, text in expected_04e2.items():
        if active.get(sid) != text:
            die(f"$04E2 {sid} payload drifted: {active.get(sid)!r}")

    overrides = french.get("user_validated_structural_command_overrides", [])
    expected_overrides = [{
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
    }]
    if overrides != expected_overrides:
        die(f"$04E2 PLAYER_NAME resegmentation drifted: {overrides!r}")

    mass = json.loads(MASS.read_text(encoding="utf-8"))
    cov = mass["coverage"]
    expected_cov = {
        "accepted_event_count": 695,
        "complete_accepted_event_count": 669,
        "partial_accepted_event_count": 26,
        "manual_supplement_entry_count": 18,
        "accepted_semantic_source_id_count": 1687,
        "translation_entry_count": 1783,
        "user_validated_visually_complete_event_count": 5,
        "user_validated_structural_omission_event_count": 6,
        "user_validated_structural_omitted_command_count": 7,
        "excluded_event_count": 9,
    }
    for key, value in expected_cov.items():
        if cov.get(key) != value:
            die(f"coverage {key} drifted: {cov.get(key)!r} != {value!r}")
    if cov.get("excluded_stage_counts") != {
        "alignment_incomplete": 6,
        "formatter_rejected": 2,
        "simulator_rejected": 1,
    }:
        die(f"exclusion counts drifted: {cov.get('excluded_stage_counts')!r}")

    partial = {x["event_id"]: x for x in mass.get("partial_accepted_events", [])}
    if partial.get("04E1") != {
        "event_id": "04E1",
        "partial_reason": "manual_resegmented_page_suppression",
        "manual_suppressed_semantic_ids": ["CA:2C84"],
    }:
        die(f"$04E1 should now be PARTIEL only for the deliberate CA:2C84 suppression: {partial.get('04E1')!r}")
    expected_04e2_deferred = ["CA:3335", "CA:3359", "CA:3362", "CA:33E4", "CA:3423"]
    p04e2 = partial.get("04E2")
    if not p04e2 or p04e2.get("unresolved_semantic_ids") != expected_04e2_deferred or p04e2.get("layout_deferred_semantic_ids") != expected_04e2_deferred:
        die(f"$04E2 remaining deferred set drifted: {p04e2!r}")

    reports_04e1 = [x for x in mass.get("formatted_mappings", []) if x.get("event_id") == "04E1"]
    r04e1 = next((x for x in reports_04e1 if x.get("round67_user_reviewed_scene_redistribution")), None)
    if not r04e1 or r04e1.get("android_ids") != [3252, 3253, 3254, 3255, 3256, 3257]:
        die("$04E1 Android-FR 3252-3257 redistribution report missing")
    reports_04e2 = [x for x in mass.get("formatted_mappings", []) if x.get("event_id") == "04E2"]
    r04e2 = next((x for x in reports_04e2 if x.get("snes_ids") == ["CA:32C5", "CA:32D7"]), None)
    if not r04e2 or not r04e2.get("translated_player_name_resegmentation") or not r04e2.get("android_fr_1280_intentionally_omitted"):
        die("$04E2 user-reviewed speaker redistribution report missing")

    html = FOCUSED.read_text(encoding="utf-8")
    for android_id in range(1274, 1309):
        if f'<td class="id">{android_id}</td>' not in html:
            die(f"focused $04E2 HTML no longer exposes Android {android_id}")
    for sid in expected_04e2_deferred:
        if sid not in html:
            die(f"focused $04E2 HTML no longer highlights {sid}")

    print("Round-67 targeted dialogues verified: $013A suppression + $04E1 monologue + $04E2 speaker redistribution user-validated and locked")


if __name__ == "__main__":
    main()
