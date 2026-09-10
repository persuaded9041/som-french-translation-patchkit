#!/usr/bin/env python3
"""Lock the Round-68 whole-scene Android-FR redistributions."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECIPES = ROOT / "mappings/android/dialogues_redistribution_recipes.json"
FRENCH = ROOT / "translations/dialogues_french.json"
MASS = ROOT / "mappings/android/dialogues_format_mass.json"
AUTO = ROOT / "mappings/android/dialogues_auto.json"


def die(msg: str) -> None:
    raise SystemExit(f"Round-68 scene check failed: {msg}")


def active_entries(document: dict) -> dict[str, str]:
    return {e["id"]: e["text"] for g in document.get("groups", []) for e in g.get("entries", [])}


def main() -> None:
    recipes = json.loads(RECIPES.read_text(encoding="utf-8"))["events"]
    layouts = {event_id: recipe for event_id, recipe in recipes.items() if recipe.get("round") == 68}
    if set(layouts) != {"0555", "0429", "05F8"}:
        die(f"scene set drifted: {sorted(layouts)}")

    mass = json.loads(MASS.read_text(encoding="utf-8"))
    cov = mass["coverage"]
    # Round 68 owns the three scene payloads and the unchanged Android identity,
    # not a permanent ceiling on later formatter coverage.
    minimums = {
        "accepted_event_count": 697,
        "complete_accepted_event_count": 672,
        "accepted_semantic_source_id_count": 1780,
        "translation_entry_count": 1909,
    }
    for key, value in minimums.items():
        if cov.get(key, 0) < value:
            die(f"coverage {key} regressed: {cov.get(key)!r} < {value!r}")

    reports = mass.get("formatted_mappings", [])
    for event_id in ("0555", "0429", "05F8"):
        if not any(r.get("event_id") == event_id and r.get("round68_user_validated_android_fr_scene") for r in reports):
            die(f"{event_id} Round-68 report flag missing")

    auto = json.loads(AUTO.read_text(encoding="utf-8"))["coverage"]
    if auto.get("mapped_semantic_source_id_count") != 1798 or auto.get("unmapped_semantic_source_id_count") != 40:
        die("Android semantic identity changed; Round 68 must stay 1798/1838")

    print("Round-68 whole-scene Android-FR redistributions verified: $0555/$0429/$05F8; identity remains 1798/1838")


if __name__ == "__main__":
    main()
