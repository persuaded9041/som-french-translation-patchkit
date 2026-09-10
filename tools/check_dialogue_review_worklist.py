#!/usr/bin/env python3
"""Validate the Round-55 user-facing dialogue review queue classification."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATUS = ROOT / "mappings" / "android" / "dialogues_review_round55.json"
HTML = ROOT / "mappings" / "android" / "dialogues_review_worklist.html"
SOURCE = ROOT / "assets" / "dialogues.json"
R53 = ROOT / "mappings" / "android" / "dialogues_review_round53.json"
MANUAL = ROOT / "translations" / "dialogues_manual_supplements.json"

EXPECTED = {
    "001E": ("C9:0970", "covered_contextual_fragment"),
    "0269": ("C9:A49C", "unused_orphan_event"),
    "02DE": ("C9:C4FB", "unused_orphan_event"),
    "0323": ("C9:CE5A", "covered_dynamic_parameter"),
    "0330": ("C9:CEA3", "covered_contextual_template"),
    "0331": ("C9:CEB3", "covered_contextual_template"),
    "035F": ("C9:D1B8", "manual_translation_already_validated"),
    "0603": ("CA:85FC", "unused_orphan_sign"),
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="accepted for symmetry; validation is always read-only")
    ap.parse_args()

    status = load(STATUS)
    if status.get("status") != "round55_review_queue_no_action_classification":
        raise SystemExit("Round-55 review status marker changed")
    if status.get("rom_diff") is not False or status.get("android_identity_set_changed") is not False or status.get("translation_payload_changed") is not False:
        raise SystemExit("Round-55 must remain a zero-ROM/zero-identity/zero-payload classification pass")

    entries = {e["event_id"]: e for e in status.get("entries", [])}
    if set(entries) != set(EXPECTED):
        raise SystemExit(f"Round-55 no-action event set changed: {sorted(entries)}")
    for event_id, (snes_id, classification) in EXPECTED.items():
        entry = entries[event_id]
        if entry.get("snes_id") != snes_id or entry.get("classification") != classification:
            raise SystemExit(f"Round-55 classification drift: ${event_id}")

    source = load(SOURCE)
    by_id = {
        token["id"]: (event["event_id"], token.get("source", ""))
        for event in source["events"]
        for token in event.get("tokens", [])
        if token.get("type") == "text" and token.get("id")
    }
    for event_id, (snes_id, _) in EXPECTED.items():
        if snes_id not in by_id or by_id[snes_id][0] != event_id:
            raise SystemExit(f"Round-55 source carrier moved: {snes_id}")

    residual = {
        e["snes_id"]: e
        for e in load(R53)["residual_semantic_audit"]["entries"]
    }
    for snes_id in ("C9:A49C", "C9:C4FB", "CA:85FC"):
        note = residual[snes_id].get("note", "").lower()
        if "no incoming" not in note and "unreferenced" not in note and "orphan" not in note:
            raise SystemExit(f"Unused routing proof missing for {snes_id}")
    for snes_id in ("C9:CE5A", "C9:CEA3", "C9:CEB3"):
        if snes_id not in residual:
            raise SystemExit(f"Inn-template residual evidence missing for {snes_id}")

    # Round 55 is historical classification evidence. Later manual-review rounds
    # may legitimately supersede the then-current $035F approval state, so this
    # checker must not bind the historical queue to the mutable manual supplement.

    html = HTML.read_text(encoding="utf-8")
    cards = re.findall(r'<details class="eventcard"([^>]*)>\s*<summary><div><code>\$([0-9A-F]{4})</code>', html)
    no_action = {event_id for attrs, event_id in cards if 'data-action="0"' in attrs}
    action = {event_id for attrs, event_id in cards if 'data-action="1"' in attrs}
    if no_action != set(EXPECTED):
        raise SystemExit(f"HTML no-action set changed: {sorted(no_action)}")
    if len(action) != 34 or len(cards) != 42:
        raise SystemExit(f"HTML card counts changed: action={len(action)} total={len(cards)}")
    if html.count('class="issueblock"') != 97:
        raise SystemExit("HTML issue-carrier count changed")
    if "Round 55 est un classement de revue sans changement ROM" not in html:
        raise SystemExit("Round-55 zero-ROM explanatory banner missing")

    counts = status.get("counts", {})
    if counts != {
        "no_action_events": 8,
        "no_action_carriers": 8,
        "action_required_events_in_html": 34,
        "action_required_carriers_in_html": 89,
    }:
        raise SystemExit("Round-55 review counts changed")

    print("Round-55 review worklist verified: 34 action events / 89 action carriers; 8 no-action informational events")


if __name__ == "__main__":
    main()
