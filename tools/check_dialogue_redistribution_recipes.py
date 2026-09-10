#!/usr/bin/env python3
"""Verify that dialogue resegmentation recipes contain no translated prose."""
from __future__ import annotations
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECIPES = ROOT / "mappings/android/dialogues_redistribution_recipes.json"
FRENCH = ROOT / "translations/dialogues_french.json"
SCRTXT_FR = ROOT / "sources/android/scrtxt_fr.bin"

EXPECTED_ROUND68 = {"0555", "0429", "05F8"}
EXPECTED_ROUND69 = {"010C", "015A", "01C5", "0204", "0205", "0227", "04E2", "04E5", "04E6", "04E9", "04FD", "0559", "0592", "05B4"}


def die(msg: str) -> None:
    raise SystemExit(f"Dialogue redistribution recipe check failed: {msg}")


def active_entries(document: dict) -> dict[str, str]:
    return {e["id"]: e["text"] for g in document.get("groups", []) for e in g.get("entries", [])}


def main() -> None:
    raw = RECIPES.read_text(encoding="utf-8")
    doc = json.loads(raw)
    if doc.get("format_version") != 1 or doc.get("source") != "sources/android/scrtxt_fr.bin":
        die("recipe header/source drifted")
    events = doc.get("events", {})
    if set(events) != EXPECTED_ROUND68 | EXPECTED_ROUND69:
        die(f"event set drifted: {sorted(events)}")
    if {ev for ev, x in events.items() if x.get("round") == 68} != EXPECTED_ROUND68:
        die("Round-68 event tags drifted")
    if {ev for ev, x in events.items() if x.get("round") == 69} != EXPECTED_ROUND69:
        die("Round-69 event tags drifted")

    for ev, recipe in events.items():
        for sid, carrier in recipe.get("carriers", {}).items():
            parts = carrier.get("parts", [])
            seps = carrier.get("seps", [])
            if len(seps) != len(parts) + 1:
                die(f"{ev}/{sid}: separator count invalid")
            for sep in seps:
                if any(ch not in " \t\r\n\x0b\x0c" for ch in sep):
                    die(f"{ev}/{sid}: non-layout characters stored in separator {sep!r}")
            for part in parts:
                if part[0] == "x" and re.search(r"[A-Za-zÀ-ÿŒœ]", str(part[1])):
                    die(f"{ev}/{sid}: translated prose stored literally in recipe: {part!r}")
                if part[0] not in {"a", "p", "x"}:
                    die(f"{ev}/{sid}: unknown part kind {part!r}")

    spec = importlib.util.spec_from_file_location("import_android_text_recipe_check", ROOT / "tools/import_android_text.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    fr = module.read_scrtxt(SCRTXT_FR)
    rendered, _ = module._load_dialogue_redistribution_recipes(fr)
    active = active_entries(json.loads(FRENCH.read_text(encoding="utf-8")))
    for ev, values in rendered.items():
        for sid, expected in values.items():
            if active.get(sid) != expected:
                die(f"{ev}/{sid}: generated payload drifted")

    print(f"Dialogue redistribution recipes verified: {len(events)} events, no translated prose stored; payload regenerated from scrtxt_fr.bin")


if __name__ == "__main__":
    main()
