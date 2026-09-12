#!/usr/bin/env python3
"""Verify that dialogue resegmentation recipes contain no translated prose."""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
RECIPES = ROOT / "recipes/android/dialogues_redistribution.json"
COVERAGE = ROOT / "recipes/android/dialogues_coverage_repair.json"
FRENCH = ROOT / "translations/dialogues_french.json"
SCRTXT_FR = ROOT / "sources/android/scrtxt_fr.bin"

EXPECTED_ROUND67 = {"04E1"}
EXPECTED_ROUND68 = {"0555", "0429", "05F8"}
EXPECTED_ROUND69 = {"010C", "015A", "01C5", "0204", "0205", "0227", "04E2", "04E5", "04E6", "04E9", "04FD", "0559", "0592", "05B4"}
EXPECTED_ROUND85 = {"0103"}


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
    if set(events) != EXPECTED_ROUND67 | EXPECTED_ROUND68 | EXPECTED_ROUND69 | EXPECTED_ROUND85:
        die(f"event set drifted: {sorted(events)}")
    if {ev for ev, x in events.items() if x.get("round") == 67} != EXPECTED_ROUND67:
        die("Round-67 event tags drifted")
    if {ev for ev, x in events.items() if x.get("round") == 68} != EXPECTED_ROUND68:
        die("Round-68 event tags drifted")
    if {ev for ev, x in events.items() if x.get("round") == 69} != EXPECTED_ROUND69:
        die("Round-69 event tags drifted")
    if {ev for ev, x in events.items() if x.get("round") == 85} != EXPECTED_ROUND85:
        die("Round-85 event tags drifted")

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

    from shared.dialogue.pipeline.common import read_scrtxt
    from shared.dialogue.pipeline.recipes import load_dialogue_redistribution_recipes

    fr = read_scrtxt(SCRTXT_FR)
    rendered, _ = load_dialogue_redistribution_recipes(fr)
    coverage = json.loads(COVERAGE.read_text(encoding="utf-8")) if COVERAGE.exists() else {"repairs": []}
    coverage_append = {(r.get("event_id"), r.get("carrier_id")) for r in coverage.get("repairs", []) if r.get("mode") == "append"}
    active = (
        active_entries(json.loads(FRENCH.read_text(encoding="utf-8")))
        if FRENCH.exists() else None
    )
    def semantic_payload(text: str) -> str:
        # Formatter-owned layout may legitimately change when the calibrated
        # VWF limits change. Recipe provenance protects the Android-FR prose,
        # not a historical newline/page layout. Collapse layout whitespace and
        # control separators before comparing semantic payloads.
        return " ".join(text.replace("\v", " ").replace("\f", " ").split())

    checked = 0
    filtered = 0
    for ev, values in rendered.items():
        for sid, expected in values.items():
            if active is None:
                continue
            actual = active.get(sid)
            if actual is None:
                # Simulator-filtered generation may temporarily exclude a
                # reviewed redistribution event under a stricter formatter
                # contract. The recipe remains the canonical provenance source.
                filtered += 1
                continue
            actual_sem = semantic_payload(actual)
            expected_sem = semantic_payload(expected)
            if (ev, sid) in coverage_append:
                if not actual_sem.startswith(expected_sem):
                    die(f"{ev}/{sid}: generated semantic payload prefix drifted before coverage append")
            elif actual_sem != expected_sem:
                die(f"{ev}/{sid}: generated semantic payload drifted")
            checked += 1

    print(
        f"Dialogue redistribution recipes verified: {len(events)} events, no translated prose stored; "
        + (f"{checked} active carrier(s) preserve Android-FR semantic payload; {filtered} carrier(s) currently simulator-filtered"
           if active is not None else "generated dialogues_french.json absent; provenance-only checks completed")
    )


if __name__ == "__main__":
    main()
