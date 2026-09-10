#!/usr/bin/env python3
"""Lock Round-66 approval of the exact $0204/C9:902F manual carrier."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANUAL = ROOT / "translations" / "dialogues_manual_supplements.json"
FRENCH = ROOT / "translations" / "dialogues_french.json"
MASS = ROOT / "mappings" / "android" / "dialogues_format_mass.json"
SID = "C9:902F"
TEXT = "Où que tu sois, le pouvoir de la Graine atteindra ton Épée."
FORMATTED = "Où que tu sois, le pouvoir de la\nGraine atteindra ton Épée."


def die(msg: str) -> None:
    raise SystemExit(f"Round-66 $0204 approval check failed: {msg}")


def main() -> None:
    manual = json.loads(MANUAL.read_text(encoding="utf-8"))
    entries = {e["id"]: e for e in manual["entries"]}
    e = entries.get(SID)
    if not e or e.get("event_id") != "0204" or e.get("status") != "translated":
        die(f"manual status/ownership drifted: {e!r}")
    if e.get("translation_fr") != TEXT:
        die(f"approved text drifted: {e.get('translation_fr')!r}")
    if e.get("original_jp_status") != "exact_snes_jp_transcription_resegmented_block_confirmed":
        die("JP resegmentation provenance was weakened")
    if any(x.get("status") == "needs_manual_translation" for x in manual["entries"]):
        die("a manual supplement unexpectedly remains pending")
    if sum(x.get("status") == "translated" for x in manual["entries"]) != 16 or sum(x.get("status") == "suppressed" for x in manual["entries"]) not in {1, 2}:
        die("manual supplement totals drifted")

    french = json.loads(FRENCH.read_text(encoding="utf-8"))
    active = {x["id"]: x["text"] for g in french.get("groups", []) for x in g.get("entries", [])}
    round69_formatted = "Il existe sept autres temples comme\ncelui-ci dans le monde. Trouve-les et\nreçois la force de leur Graine."
    if active.get(SID) not in {FORMATTED, round69_formatted}:
        die(f"active payload drifted: {active.get(SID)!r}")

    mass = json.loads(MASS.read_text(encoding="utf-8"))
    cov = mass["coverage"]
    if cov.get("accepted_event_count", 0) < 695:
        die(f"accepted corpus regressed: {cov.get('accepted_event_count')!r}")
    if cov.get("manual_supplement_entry_count", 0) < 17:
        die(f"manual supplement coverage regressed: {cov.get('manual_supplement_entry_count')!r}")
    if any(x.get("event_id") == "0204" for x in mass.get("excluded_events", [])):
        die("$0204 unexpectedly remains excluded")
    p = next((x for x in mass.get("partial_accepted_events", []) if x.get("event_id") == "0204"), None)
    reports = [x for x in mass.get("formatted_mappings", []) if x.get("event_id") == "0204"]
    round69 = next((x for x in reports if x.get("round69_targeted_redistribution")), None)
    if p is not None:
        if p != {"event_id": "0204", "partial_reason": "manual_translation_without_android_identity", "manual_translated_semantic_ids": [SID]}:
            die(f"PARTIEL metadata drifted: {p!r}")
        legacy = [x for x in reports if x.get("snes_ids") == [SID]]
        if len(legacy) != 1 or legacy[0].get("payload_policy") != "manual_only_on_resegmented_partial_event":
            die(f"manual-only safety policy missing/drifted: {legacy!r}")
    elif round69 is None:
        die("$0204 is no longer PARTIEL but no Round-69 superseding scene redistribution exists")
    print("Round-66 $0204 approval provenance verified; later whole-scene redistribution may supersede its active carrier placement")

if __name__ == "__main__":
    main()
