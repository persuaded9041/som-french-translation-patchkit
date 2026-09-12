#!/usr/bin/env python3
"""Guard Round-85 post-audit changes across a fresh dialogue-format-mass regeneration."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRANS = ROOT / "translations" / "dialogues_french.json"
REPORT = ROOT / "mappings" / "android" / "dialogues_format_mass.json"
RECIPES = ROOT / "mappings" / "android" / "dialogues_coverage_repair_recipes.json"
MANUAL = ROOT / "translations" / "dialogues_manual_supplements.json"


def die(msg: str) -> None:
    raise SystemExit(f"ERROR: {msg}")


def main() -> None:
    recipes = json.loads(RECIPES.read_text(encoding="utf-8"))
    lot6 = [r for r in recipes.get("repairs", []) if r.get("event_id") == "0559" and r.get("carrier_id") == "CA:6787"]
    if len(lot6) != 1:
        die("expected exactly one $0559/CA:6787 coverage recipe")
    r = lot6[0]
    if r.get("android_ids") != [2151, 2152, 2153, 2154, 2155] or r.get("separator") != "\f" or r.get("android_separator") != "\f" or not r.get("wrap_android_units"):
        die("$0559/CA:6787 recipe drifted")

    manual = json.loads(MANUAL.read_text(encoding="utf-8"))
    active_0204 = [e for e in manual.get("entries", []) if e.get("event_id") == "0204" and e.get("id") == "C9:902F"]
    if active_0204:
        die("$0204/C9:902F unexpectedly returned to manual supplements")

    report = json.loads(REPORT.read_text(encoding="utf-8"))
    lot6_reports = [
        x for x in report.get("formatted_mappings", [])
        if x.get("event_id") == "0559" and x.get("coverage_repair") and x.get("android_ids") == [2151, 2152, 2153, 2154, 2155]
    ]
    if len(lot6_reports) != 1:
        die("fresh format report does not prove application of Android 2151..2155 to $0559")

    trans = json.loads(TRANS.read_text(encoding="utf-8"))
    entry = None
    for group in trans.get("groups", []):
        for item in group.get("entries", []):
            if item.get("id") == "CA:6787":
                entry = item
                break
    if not entry or entry.get("text", "").count("\f") < 5 or "%S(0,0)" not in entry.get("text", ""):
        die("generated CA:6787 lost the Round-85 mini-transition")

    migrated = trans.get("migrated_manual_dialogue_supplements", [])
    if not any(x.get("event_id") == "0204" and x.get("id") == "C9:902F" and not x.get("active_manual_supplement", True) for x in migrated):
        die("generated metadata does not record $0204 manual->Android migration")

    print("Round-85 post-audit reproducibility: OK")


if __name__ == "__main__":
    main()
