#!/usr/bin/env python3
"""Flag full-page breaks that may be better as reviewed one-line rolling scrolls.

This is a review aid, never an automatic formatter rule.  It looks for a
translated carrier where a generated ``\f`` (WAIT $00 + TEXT_CLEAR) splits a
four-line sentence as 2+2 lines.  If the sentence visibly continues across the
page boundary, the event is a candidate for the reviewed pattern::

    line 1
    line 2
    line 3\r\n
    line 4

where ``\r`` is translation-only WAIT $00 markup.  The player sees lines 1-3,
confirms, then NEWLINE scrolls only line 1 away and reveals line 4.

Candidates still require human review: speaker changes, deliberate dramatic
page breaks, choices and event commands may make a full clear preferable.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TRANSLATION = ROOT / "translations" / "dialogues_french.json"
DEFAULT_DIALOGUES = ROOT / "assets" / "dialogues.json"

_SENTENCE_END_RE = re.compile(r"(?:[.!?…]|[.!?…][\"'»”)]*)$")
_CONTINUATION_RE = re.compile(r"^[a-zàâçéèêëîïôùûœ]|^(?:un|une|le|la|les|des|de|du|au|aux|et|mais|ou|qui|que|dont|où)\b", re.I)


def _translations(document: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for group in document.get("groups", []):
        for entry in group.get("entries", []):
            text_id = entry.get("id")
            text = entry.get("text")
            if isinstance(text_id, str) and isinstance(text, str):
                out[text_id] = text
    return out


def _text_to_event(document: dict) -> dict[str, str]:
    result: dict[str, str] = {}
    for event in document.get("events", []):
        event_id = str(event.get("event_id", ""))
        for token in event.get("tokens", []):
            if token.get("type") in {"text", "ending_text"} and isinstance(token.get("id"), str):
                result[token["id"]] = event_id
    return result


def _candidate(text: str, break_index: int) -> tuple[bool, str, str]:
    left = text[:break_index]
    right = text[break_index + 1:]
    left_page = left.rsplit("\f", 1)[-1].split("\n")
    right_page = right.split("\f", 1)[0].split("\n")
    if len(left_page) != 2 or len(right_page) != 2:
        return False, "", ""
    before = left_page[-1].strip()
    after = right_page[0].strip()
    if not before or not after:
        return False, "", ""
    if _SENTENCE_END_RE.search(before):
        return False, "", ""
    # Lowercase/continuation-word starts are a strong signal that the clear
    # interrupted one grammatical sentence.  Uppercase continuation remains a
    # manual visual-audit concern rather than an automatic candidate here.
    if not _CONTINUATION_RE.search(after):
        return False, "", ""
    preview_before = "\n".join(left_page + [right_page[0]])
    preview_after = "\n".join([left_page[-1]] + right_page)
    return True, preview_before, preview_after


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--translation", type=Path, default=DEFAULT_TRANSLATION)
    parser.add_argument("--dialogues", type=Path, default=DEFAULT_DIALOGUES)
    parser.add_argument("--event", action="append", default=[], help="optional event ID filter, repeatable")
    parser.add_argument("--csv", type=Path, help="optional CSV output")
    args = parser.parse_args()

    translations = _translations(json.loads(args.translation.read_text(encoding="utf-8")))
    text_events = _text_to_event(json.loads(args.dialogues.read_text(encoding="utf-8")))
    selected = {value.upper().removeprefix("$") for value in args.event}
    rows: list[dict[str, str | int]] = []

    for text_id, text in translations.items():
        event_id = text_events.get(text_id, "")
        if selected and event_id.upper() not in selected:
            continue
        for break_number, match in enumerate(re.finditer("\f", text), 1):
            ok, before, after = _candidate(text, match.start())
            if not ok:
                continue
            rows.append({
                "event_id": event_id,
                "text_id": text_id,
                "page_break_number": break_number,
                "reason": "2+2 full-page split inside a continuing sentence; review for WAIT-only + NEWLINE rolling scroll",
                "before_press_candidate": before,
                "after_press_candidate": after,
            })

    print(f"Rolling-scroll review candidates: {len(rows)}")
    for row in rows:
        print(f"${row['event_id']} / {row['text_id']}: {row['reason']}")
        print("  before press:")
        for line in str(row["before_press_candidate"]).splitlines():
            print(f"    {line}")
        print("  after press:")
        for line in str(row["after_press_candidate"]).splitlines():
            print(f"    {line}")

    if args.csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        with args.csv.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=[
                "event_id", "text_id", "page_break_number", "reason",
                "before_press_candidate", "after_press_candidate",
            ], delimiter=";")
            writer.writeheader()
            writer.writerows(rows)
        print(f"CSV: {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
