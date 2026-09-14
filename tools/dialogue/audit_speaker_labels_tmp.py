#!/usr/bin/env python3
"""Audit translated dialogue speaker labels that are followed by a hard newline.

This is a review-only guardrail. A speaker/addressee label written as ``Nom :``
or a dynamic ``%S(...) :`` is expected to keep the first phrase on the same
line. Findings are reported for manual review; the tool never rewrites text and
does not replace simulation/layout checks.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DIALOGUES = ROOT / "assets" / "dialogues.json"
DEFAULT_TRANSLATIONS = ROOT / "translations" / "dialogues_french.json"

# Conservative by design: beginning of a carrier/page/line, short label, colon,
# then a hard newline. Dynamic labels are always eligible; literal labels must
# look like a short name/title rather than a prose clause.
DYNAMIC = re.compile(r"(?m)(^|[\v\f\n])(?P<label>%S\([^\n:]{1,32}\)\s*:)\s*\n")
LITERAL = re.compile(
    r"(?m)(^|[\v\f\n])(?P<label>[A-ZÀÂÇÉÈÊËÎÏÔÙÛŒ][A-Za-zÀ-ÖØ-öø-ÿŒœ'’.-]*(?:[ ][A-Za-zÀ-ÖØ-öø-ÿŒœ'’.-]+){0,2}\s*:)\s*\n"
)


def entry_map(document: dict) -> dict[str, str]:
    return {
        entry["id"]: entry["text"]
        for group in document.get("groups", [])
        for entry in group.get("entries", [])
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dialogues", type=Path, default=DEFAULT_DIALOGUES)
    ap.add_argument("--translation", type=Path, default=DEFAULT_TRANSLATIONS)
    ap.add_argument("--event", action="append", default=[], help="event ID; repeatable")
    args = ap.parse_args()

    source = json.loads(args.dialogues.read_text("utf-8"))
    translations = entry_map(json.loads(args.translation.read_text("utf-8")))
    selected = {x.upper().replace("$", "").zfill(4) for x in args.event}
    findings: list[tuple[str, str, str, str]] = []

    for event in source.get("events", []):
        event_id = event.get("event_id", "")
        if selected and event_id not in selected:
            continue
        seen: set[str] = set()
        for token in event.get("tokens", []):
            text_id = token.get("id")
            if not text_id or text_id in seen or text_id not in translations:
                continue
            seen.add(text_id)
            value = translations[text_id]
            for kind, pattern in (("dynamic", DYNAMIC), ("literal", LITERAL)):
                for match in pattern.finditer(value):
                    findings.append((event_id, text_id, kind, match.group("label")))

    for event_id, text_id, kind, label in findings:
        print(f"${event_id} {text_id} {kind}: {label!r} followed by NEWLINE")
    print(f"Speaker-label newline findings: {len(findings)}")
    raise SystemExit(1 if findings else 0)


if __name__ == "__main__":
    main()
