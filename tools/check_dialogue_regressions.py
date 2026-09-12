#!/usr/bin/env python3
"""Validate locked dialogue decisions and current playable-dialogue coverage."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.dialogue_pipeline.alignment import make_dialogue_auto_alignment  # noqa: E402
from tools.dialogue_pipeline.common import DEFAULT_SCRTXT_EN, DEFAULT_SCRTXT_FR, read_scrtxt  # noqa: E402
from tools.dialogue_pipeline.formatter import make_dialogue_format_mass  # noqa: E402

MANUAL = ROOT / "translations/dialogues_manual_supplements.json"
RECIPES = ROOT / "mappings/android/dialogues_redistribution_recipes.json"
COVERAGE_RECIPES = ROOT / "mappings/android/dialogues_coverage_repair_recipes.json"

ROUND69_EVENTS = {
    "010C", "015A", "01C5", "0204", "0205", "0227", "04E2", "04E5", "04E6",
    "04E9", "04FD", "0559", "0592", "05B4",
}
ORPHANS = {"0269": "C9:A49C", "02DE": "C9:C4FB", "0603": "CA:85FC"}


def die(msg: str) -> None:
    raise SystemExit(f"Dialogue regression check failed: {msg}")


def active_entries(document: dict) -> dict[str, str]:
    return {e["id"]: e["text"] for group in document.get("groups", []) for e in group.get("entries", [])}


def semantic_layout_normalized(text: str) -> str:
    return " ".join(text.replace("\n", " ").replace("\f", " ").replace("\v", " ").split())


def check_targeted_reviews(manual: dict, french: dict, mass: dict) -> None:
    entries = {e["id"]: e for e in manual["entries"]}
    c40d7 = entries.get("C9:40D7")
    if not c40d7 or c40d7.get("event_id") != "013A":
        die("$013A/C9:40D7 manual review missing/moved")
    if c40d7.get("status") != "suppressed" or c40d7.get("reason") != "user_validated_snes_jp_absent_suppression":
        die("$013A/C9:40D7 suppression provenance drifted")
    if c40d7.get("original_jp") is not None or c40d7.get("original_jp_status") != "no_distinct_snes_jp_counterpart_confirmed":
        die("$013A/C9:40D7 JP-absence provenance drifted")
    if c40d7.get("original_jp_context_event_id") != "013A" or c40d7.get("original_jp_context_carrier_id") != "C9:4F39":
        die("$013A/C9:40D7 JP context binding drifted")
    if c40d7.get("translation_fr") != "":
        die("$013A/C9:40D7 suppression must not invent French prose")

    active = active_entries(french)
    if active.get("C9:40D7") != "":
        die("$013A/C9:40D7 must serialize as empty text")
    expected_omission = {
        "event_id": "013A",
        "suppressed_semantic_ids": ["C9:40D7"],
        "suppressed_commands": [{"name": "WAIT", "args": "00", "immediately_after_text_id": "C9:40D7"}],
        "reason": "round67_user_validated_snes_jp_absent_android_fr_adaptation_suppression",
    }
    omission = next((x for x in french.get("user_validated_structural_omissions", []) if x.get("event_id") == "013A"), None)
    if omission != expected_omission:
        die(f"$013A structural suppression drifted: {omission!r}")

    expected_04e1 = {
        "CA:2BED": "Mon corps actuel est sur le point de\nse corrompre.\nIl me faut un nouveau corps...",
        "CA:2C3A": "Un être humain ordinaire est incapable\nde contenir longtemps mon énergie.\fIl me faut donc le corps d'un être\nd'exception.\fOr, une ou deux fois par siècle, un\nhumain naît avec le Sang des ténèbres\ndans les veines.",
        "CA:2C84": "",
        "CA:2C93": "Lorsque je me transfère dans ce corps\nexceptionnel, mon pouvoir se trouve\ndécuplé.\fUn corps... comme celui de Durac !\fSon pouvoir maléfique a dû être scellé\nquand il était jeune... Il n'en est\ndevenu que plus droit et juste !\fAvec mon nouveau corps et la\nForteresse de Mana, je forgerai un\nmonde à mon image !",
    }
    for sid, text in expected_04e1.items():
        if semantic_layout_normalized(active.get(sid, "")) != semantic_layout_normalized(text):
            die(f"$04E1 {sid} semantic payload drifted")

    expected_04e2 = {"CA:32C5": " : Non !\nC'est pas possible !\n", "CA:32D7": "Ils se sont sûrement échappés !"}
    for sid, text in expected_04e2.items():
        if semantic_layout_normalized(active.get(sid, "")) != semantic_layout_normalized(text):
            die(f"$04E2 {sid} semantic payload drifted")

    expected_override = {
        "event_id": "04E2",
        "commands": [
            {"name": "PLAYER_NAME", "args": "01", "immediately_before_text_id": "CA:32C5", "translated_args": "02"},
            {"name": "PLAYER_NAME", "args": "02", "immediately_before_text_id": "CA:32D7", "omit": True},
        ],
        "reason": "round67_user_validated_android_fr_1281_speaker_resegmentation",
    }
    if expected_override not in french.get("user_validated_structural_command_overrides", []):
        die("$04E2 PLAYER_NAME resegmentation drifted/missing")

    cov = mass["coverage"]
    if cov.get("user_validated_visually_complete_event_count", 0) < 5:
        die("validated visually-complete event count regressed")
    if cov.get("user_validated_structural_omission_event_count") != 6 or cov.get("user_validated_structural_omitted_command_count") != 7:
        die("validated structural omission coverage drifted")

    partial = {x["event_id"]: x for x in mass.get("partial_accepted_events", [])}
    if "04E1" in partial:
        if partial["04E1"] != {"event_id": "04E1", "partial_reason": "manual_resegmented_page_suppression", "manual_suppressed_semantic_ids": ["CA:2C84"]}:
            die("$04E1 suppression provenance drifted")
    else:
        complete = {x["event_id"]: x for x in mass.get("user_validated_visually_complete_events", [])}
        if complete.get("04E1") != {"event_id": "04E1", "manual_suppressed_semantic_ids": ["CA:2C84"], "reason": "user_validated_complete_with_manual_resegmentation"}:
            die("$04E1 completion provenance drifted/missing")

    deferred = ["CA:3335", "CA:3359", "CA:3362", "CA:33E4", "CA:3423"]
    p04e2 = partial.get("04E2")
    if p04e2 is not None and (p04e2.get("unresolved_semantic_ids") != deferred or p04e2.get("layout_deferred_semantic_ids") != deferred):
        die("$04E2 historical deferred set drifted")

    reports_04e1 = [x for x in mass.get("formatted_mappings", []) if x.get("event_id") == "04E1"]
    r04e1 = next((x for x in reports_04e1 if x.get("round67_user_reviewed_scene_redistribution")), None)
    if not r04e1 or r04e1.get("android_ids") != [3252, 3253, 3254, 3255, 3256, 3257]:
        die("$04E1 Android-FR redistribution report missing")

    reports_04e2 = [x for x in mass.get("formatted_mappings", []) if x.get("event_id") == "04E2"]
    r04e2 = next((x for x in reports_04e2 if x.get("snes_ids") == ["CA:32C5", "CA:32D7"]), None)
    r69 = next((x for x in reports_04e2 if x.get("round69_targeted_redistribution")), None)
    if r04e2 is not None:
        if not r04e2.get("translated_player_name_resegmentation") or not r04e2.get("android_fr_1280_intentionally_omitted"):
            die("$04E2 reviewed speaker redistribution report drifted")
    elif r69 is None:
        die("$04E2 reviewed redistribution report missing")


def check_scene_recipes(french: dict, mass: dict, auto: dict, recipes: dict) -> None:
    round68 = {eid: r for eid, r in recipes.items() if r.get("round") == 68}
    if set(round68) != {"0555", "0429", "05F8"}:
        die(f"Round-68 scene set drifted: {sorted(round68)}")
    for key, value in {"accepted_event_count": 697, "complete_accepted_event_count": 672, "accepted_semantic_source_id_count": 1780, "translation_entry_count": 1909}.items():
        if mass["coverage"].get(key, 0) < value:
            die(f"coverage {key} regressed below historical minimum")
    reports = mass.get("formatted_mappings", [])
    for eid in ("0555", "0429", "05F8"):
        if not any(r.get("event_id") == eid and r.get("round68_user_validated_android_fr_scene") for r in reports):
            die(f"{eid} validated scene report flag missing")

    round69 = {eid: r for eid, r in recipes.items() if r.get("round") == 69}
    if set(round69) != ROUND69_EVENTS:
        die(f"targeted redistribution set drifted: {sorted(round69)}")

    expected_cov = {
        "accepted_event_count": 701,
        "complete_accepted_event_count": 701,
        "partial_accepted_event_count": 0,
        "accepted_semantic_source_id_count": 1815,
        "translation_entry_count": 1947,
        "excluded_event_count": 3,
    }
    for key, value in expected_cov.items():
        if mass["coverage"].get(key) != value:
            die(f"coverage {key}: {mass['coverage'].get(key)!r} != {value!r}")
    if mass["coverage"].get("excluded_stage_counts") != {"alignment_incomplete": 3}:
        die("exclusion stages drifted")

    excluded = {x["event_id"]: x for x in mass.get("excluded_events", [])}
    if set(excluded) != set(ORPHANS):
        die(f"excluded events drifted: {sorted(excluded)}")
    for eid, sid in ORPHANS.items():
        x = excluded[eid]
        if x.get("missing_semantic_ids") != [sid]:
            die(f"{eid} orphan carrier drifted")
        if not any(d.get("snes_id") == sid and d.get("reason") == "validated_no_equivalent" for d in x.get("details", [])):
            die(f"{eid} lost validated_no_equivalent provenance")

    for eid in ROUND69_EVENTS:
        if not any(r.get("event_id") == eid and r.get("round69_targeted_redistribution") for r in reports):
            die(f"{eid} targeted redistribution report missing")

    if auto.get("coverage", {}).get("mapped_semantic_source_id_count") != 1798 or auto.get("coverage", {}).get("unmapped_semantic_source_id_count") != 40:
        die("Android semantic identity changed from 1798/1838")

    if french.get("partial_events"):
        die("PARTIEL should remain empty")
    complete_meta = {x["event_id"]: x for x in french.get("user_validated_visually_complete_events", [])}
    promoted = {"001E", "0042", "00EE", "00F1", "00F3", "0207", "0208", "024F", "0278", "02E1", "02FC", "035F", "04E1", "04E8", "0558"}
    if not promoted.issubset(complete_meta):
        die(f"completion provenance missing: {sorted(promoted - set(complete_meta))}")


def check_postaudit(french: dict, mass: dict, manual: dict) -> None:
    coverage_recipes = json.loads(COVERAGE_RECIPES.read_text(encoding="utf-8"))
    lot6 = [r for r in coverage_recipes.get("repairs", []) if r.get("event_id") == "0559" and r.get("carrier_id") == "CA:6787"]
    if len(lot6) != 1:
        die("expected exactly one $0559/CA:6787 coverage recipe")
    r = lot6[0]
    if r.get("android_ids") != [2151, 2152, 2153, 2154, 2155] or r.get("separator") != "\f" or r.get("android_separator") != "\f" or not r.get("wrap_android_units"):
        die("$0559/CA:6787 coverage recipe drifted")

    if any(e.get("event_id") == "0204" and e.get("id") == "C9:902F" for e in manual.get("entries", [])):
        die("$0204/C9:902F unexpectedly returned to manual supplements")

    lot6_reports = [x for x in mass.get("formatted_mappings", []) if x.get("event_id") == "0559" and x.get("coverage_repair") and x.get("android_ids") == [2151, 2152, 2153, 2154, 2155]]
    if len(lot6_reports) != 1:
        die("format report does not prove application of Android 2151..2155 to $0559")

    entry = next((item for group in french.get("groups", []) for item in group.get("entries", []) if item.get("id") == "CA:6787"), None)
    if not entry or entry.get("text", "").count("\f") < 5 or "%S(0,0)" not in entry.get("text", ""):
        die("generated CA:6787 lost the post-audit mini-transition")
    if not any(x.get("event_id") == "0204" and x.get("id") == "C9:902F" and not x.get("active_manual_supplement", True) for x in french.get("migrated_manual_dialogue_supplements", [])):
        die("generated metadata does not record $0204 manual->Android migration")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rom",
        type=Path,
        required=True,
        help="clean unheadered Secret of Mana (USA) ROM used by the mass formatter/simulator",
    )
    args = parser.parse_args()

    manual = json.loads(MANUAL.read_text(encoding="utf-8"))
    recipes = json.loads(RECIPES.read_text(encoding="utf-8"))["events"]
    english = read_scrtxt(DEFAULT_SCRTXT_EN)
    french_android = read_scrtxt(DEFAULT_SCRTXT_FR)
    base_rom = args.rom.resolve().read_bytes()

    auto = make_dialogue_auto_alignment(
        english,
        french_android,
        english_path=DEFAULT_SCRTXT_EN,
        french_path=DEFAULT_SCRTXT_FR,
    )
    french, mass = make_dialogue_format_mass(
        english,
        french_android,
        english_path=DEFAULT_SCRTXT_EN,
        french_path=DEFAULT_SCRTXT_FR,
        base_rom=base_rom,
        alignment=auto,
    )

    check_targeted_reviews(manual, french, mass)
    check_scene_recipes(french, mass, auto, recipes)
    check_postaudit(french, mass, manual)
    print("Dialogue regressions verified from canonical inputs: targeted reviews, scene redistributions, 701/701 completion, 3 validated exclusions, Android identity 1798/1838, post-audit coverage repairs")


if __name__ == "__main__":
    main()
