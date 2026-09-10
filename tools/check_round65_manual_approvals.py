#!/usr/bin/env python3
"""Lock Round-65 user approvals and Android-FR canonical terminology."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.import_android_text import read_scrtxt  # noqa: E402

MANUAL = ROOT / "translations" / "dialogues_manual_supplements.json"
FRENCH = ROOT / "translations" / "dialogues_french.json"
MASS = ROOT / "mappings" / "android" / "dialogues_format_mass.json"
ANDROID_FR = ROOT / "sources" / "android" / "scrtxt_fr.bin"

APPROVED = {
    "C9:2179": ("00EE", "Départ pour Pandora !"),
    "C9:2208": ("00F1", "Pour Pandora !"),
    "C9:2268": ("00F3", "Pays de glace ! Bon voyage !"),
    "CA:437D": ("04E8", "Héhéhéhé !"),
}
PENDING_ALLOWED = ({"C9:902F"}, set())


def die(message: str) -> None:
    raise SystemExit(f"Round-65 manual approval check failed: {message}")


def main() -> None:
    manual = json.loads(MANUAL.read_text(encoding="utf-8"))
    entries = {entry["id"]: entry for entry in manual["entries"]}
    for sid, (event_id, text) in APPROVED.items():
        entry = entries.get(sid)
        if not entry or entry.get("event_id") != event_id:
            die(f"missing/moved {sid}")
        if entry.get("status") != "translated" or entry.get("translation_fr") != text:
            die(f"approval drifted for {sid}: {entry!r}")
        if entry.get("reason") != "user_requested_unmapped_carrier_review":
            die(f"identity policy drifted for {sid}")
    pending = {e["id"] for e in manual["entries"] if e.get("status") == "needs_manual_translation"}
    if pending not in PENDING_ALLOWED:
        die(f"pending set drifted: {sorted(pending)}")
    round66_active = not pending
    final_entry = entries.get("C9:902F")
    if round66_active:
        if not final_entry or final_entry.get("status") != "translated" or final_entry.get("translation_fr") != "Où que tu sois, le pouvoir de la Graine atteindra ton Épée.":
            die("later $0204 approval drifted")

    android_fr = read_scrtxt(ANDROID_FR)
    if android_fr.get(422, "").strip() != "Pandora":
        die(f"Android FR ID 422 is no longer canonical Pandora: {android_fr.get(422)!r}")
    if android_fr.get(1328, "").strip() != "Pays de glace" or android_fr.get(1655, "").strip() != "Pays de glace":
        die("Android FR Ice Country terminology changed")

    french = json.loads(FRENCH.read_text(encoding="utf-8"))
    active = {
        e["id"]: e["text"]
        for g in french.get("groups", [])
        for e in g.get("entries", [])
    }
    expected_active = {
        "C9:2179": "Départ pour Pandora !\n",
        "C9:2208": "Pour Pandora !\n",
        "C9:2268": "Pays de glace !\nBon voyage !\n",
        "CA:437D": "Héhéhéhé !",
    }
    for sid, text in expected_active.items():
        if active.get(sid) != text:
            die(f"active payload drifted for {sid}: {active.get(sid)!r}")
    round69_0204 = active.get("C9:902F") == "Il existe sept autres temples comme\ncelui-ci dans le monde. Trouve-les et\nreçois la force de leur Graine."
    if round66_active:
        if active.get("C9:902F") != "Où que tu sois, le pouvoir de la\nGraine atteindra ton Épée." and not round69_0204:
            die(f"later $0204 active payload drifted: {active.get('C9:902F')!r}")
    elif "C9:902F" in active:
        die("pending $0204/C9:902F leaked into active payload")

    mass = json.loads(MASS.read_text(encoding="utf-8"))
    coverage = mass["coverage"]
    # Global corpus totals are mutable after Round 65. Accept the exact Round-65/66
    # checkpoint or the later Round-67 state, while keeping the four Round-65
    # approved payloads and terminology assertions above immutable.
    if round66_active:
        # Later rounds may increase coverage and reduce exclusions while preserving
        # these approved manual payloads. Round 65/66 must only guard against regression.
        if coverage.get("accepted_event_count", 0) < 695:
            die(f"accepted corpus regressed: {coverage.get('accepted_event_count')!r}")
        if coverage.get("manual_supplement_entry_count", 0) < 17:
            die(f"manual supplement coverage regressed: {coverage.get('manual_supplement_entry_count')!r}")
    else:
        observed = tuple(coverage.get(k) for k in (
            "accepted_event_count", "complete_accepted_event_count",
            "partial_accepted_event_count", "manual_supplement_entry_count",
            "accepted_semantic_source_id_count", "translation_entry_count",
            "excluded_event_count",
        ))
        if observed != (694, 668, 26, 17, 1682, 1777, 10):
            die(f"Round-65 corpus totals drifted: {observed!r}")

    partial = {x["event_id"]: x for x in mass.get("partial_accepted_events", [])}
    for event_id, sid in [("00EE", "C9:2179"), ("00F1", "C9:2208"), ("00F3", "C9:2268"), ("04E8", "CA:437D")]:
        expected = {
            "event_id": event_id,
            "partial_reason": "manual_translation_without_android_identity",
            "manual_translated_semantic_ids": [sid],
        }
        if partial.get(event_id) != expected:
            die(f"partial metadata drifted for ${event_id}: {partial.get(event_id)!r}")

    excluded = {x["event_id"]: x for x in mass.get("excluded_events", [])}
    x = excluded.get("0204")
    if round66_active:
        if x is not None:
            die(f"later $0204 approval unexpectedly remains excluded: {x!r}")
        p0204 = partial.get("0204")
        if p0204 is not None and p0204 != {
            "event_id": "0204",
            "partial_reason": "manual_translation_without_android_identity",
            "manual_translated_semantic_ids": ["C9:902F"],
        }:
            die(f"later $0204 partial metadata drifted: {p0204!r}")
        if p0204 is None and not any(r.get("event_id") == "0204" and r.get("round69_targeted_redistribution") for r in mass.get("formatted_mappings", [])):
            die("$0204 is complete but no Round-69 superseding redistribution report exists")
    elif not x or x.get("stage") != "alignment_incomplete" or "C9:902F" not in x.get("missing_semantic_ids", []):
        die(f"$0204 pending exclusion drifted: {x!r}")

    reports = [x for x in mass.get("formatted_mappings", []) if x.get("event_id") == "04E8"]
    # The exact manual carrier must be applied after the ordinary PARTIEL repair,
    # never at the cost of the already-proven surrounding formatting.
    manual_reports = [x for x in reports if x.get("manual_supplement") and x.get("snes_ids") == ["CA:437D"]]
    if not manual_reports or manual_reports[-1].get("payload_policy") != "apply_after_validated_partial_repairs":
        die("$04E8 post-repair manual payload policy missing")

    print("Round-65 approvals verified; later $0204 approval is accepted when present")


if __name__ == "__main__":
    main()
