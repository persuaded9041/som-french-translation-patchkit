#!/usr/bin/env python3
"""Lock Round-69 targeted resegmentations and playable-dialogue completion status."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECIPES = ROOT / "mappings/android/dialogues_redistribution_recipes.json"
FRENCH = ROOT / "translations/dialogues_french.json"
MASS = ROOT / "mappings/android/dialogues_format_mass.json"
AUTO = ROOT / "mappings/android/dialogues_auto.json"
EXCLUDED = ROOT / "mappings/android/dialogues_format_mass_excluded.csv"

EXPECTED_EVENTS = {
    "010C", "015A", "01C5", "0204", "0205", "0227", "04E2", "04E5", "04E6",
    "04E9", "04FD", "0559", "0592", "05B4",
}
EXPECTED_ORPHANS = {
    "0269": "C9:A49C",
    "02DE": "C9:C4FB",
    "0603": "CA:85FC",
}


def die(msg: str) -> None:
    raise SystemExit(f"Round-69 dialogue completion check failed: {msg}")


def active_entries(document: dict) -> dict[str, str]:
    return {e["id"]: e["text"] for g in document.get("groups", []) for e in g.get("entries", [])}


def main() -> None:
    recipes = json.loads(RECIPES.read_text(encoding="utf-8"))["events"]
    layouts = {event_id: recipe for event_id, recipe in recipes.items() if recipe.get("round") == 69}
    if set(layouts) != EXPECTED_EVENTS:
        die(f"targeted event set drifted: {sorted(layouts)}")

    french = json.loads(FRENCH.read_text(encoding="utf-8"))

    mass = json.loads(MASS.read_text(encoding="utf-8"))
    cov = mass["coverage"]
    expected_cov = {
        "accepted_event_count": 701,
        "complete_accepted_event_count": 701,
        "partial_accepted_event_count": 0,
        "accepted_semantic_source_id_count": 1810,
        "translation_entry_count": 1946,
        "excluded_event_count": 3,
    }
    for key, value in expected_cov.items():
        if cov.get(key) != value:
            die(f"coverage {key}: {cov.get(key)!r} != {value!r}")
    if cov.get("excluded_stage_counts") != {"alignment_incomplete": 3}:
        die(f"exclusion stages drifted: {cov.get('excluded_stage_counts')!r}")

    excluded = {x["event_id"]: x for x in mass.get("excluded_events", [])}
    if set(excluded) != set(EXPECTED_ORPHANS):
        die(f"excluded events drifted: {sorted(excluded)}")
    for event_id, sid in EXPECTED_ORPHANS.items():
        x = excluded[event_id]
        if x.get("missing_semantic_ids") != [sid]:
            die(f"{event_id} orphan carrier drifted: {x!r}")
        if not any(d.get("snes_id") == sid and d.get("reason") == "validated_no_equivalent" for d in x.get("details", [])):
            die(f"{event_id} lost validated_no_equivalent provenance")

    reports = mass.get("formatted_mappings", [])
    for event_id in EXPECTED_EVENTS:
        if not any(r.get("event_id") == event_id and r.get("round69_targeted_redistribution") for r in reports):
            die(f"{event_id} targeted redistribution report missing")

    auto = json.loads(AUTO.read_text(encoding="utf-8"))["coverage"]
    if auto.get("mapped_semantic_source_id_count") != 1798 or auto.get("unmapped_semantic_source_id_count") != 40:
        die("Android identity changed; Round 69 must remain 1798/1838")

    csv_text = EXCLUDED.read_text(encoding="utf-8-sig")
    for event_id in EXPECTED_ORPHANS:
        if event_id not in csv_text:
            die(f"{event_id} missing from exclusion CSV")

    if french.get("partial_events"):
        die(f"PARTIEL should be empty after semantic-completion review: {french.get('partial_events')!r}")
    complete_meta = {x["event_id"]: x for x in french.get("user_validated_visually_complete_events", [])}
    expected_promoted = {"001E", "0042", "00EE", "00F1", "00F3", "0207", "0208", "024F", "0278", "02E1", "02FC", "035F", "04E1", "04E8", "0558"}
    if not expected_promoted.issubset(complete_meta):
        die(f"promoted completion provenance missing: {sorted(expected_promoted - set(complete_meta))}")

    print("Round-69 dialogue completion verified: 701 clean events, 0 PARTIEL, 15 promoted completion-provenance events, 3 unreachable/orphan exclusions; Android identity 1798/1838")


if __name__ == "__main__":
    main()
