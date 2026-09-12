#!/usr/bin/env python3
"""Extract original SFC Japanese dialogue from a canonical USA carrier ID."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shared.dialogue.japanese import (  # noqa: E402
    extraction_to_json,
    extract_for_us_carrier,
    parse_japanese_event,
    validate_japanese_rom,
)


def _print_text_block(label: str, token: dict) -> None:
    print(f"{label}: {token['id']}  [file ${token['file_offset']}]")
    print(f"  raw: {token['raw_hex']}")
    print(token["text"])


def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Map a position-based USA dialogue carrier (for example C9:916F) "
            "to the same event in the clean Japanese SFC ROM and decode its original text."
        )
    )
    ap.add_argument("rom", type=Path, help="clean unheadered Seiken Densetsu 2 (Japan) ROM")
    ap.add_argument("carrier", nargs="?", help="canonical USA carrier ID, e.g. C9:916F")
    ap.add_argument("--event", metavar="HHHH", help="decode a complete Japanese event instead of mapping a USA carrier")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ap.add_argument(
        "--source",
        type=Path,
        default=ROOT / "assets" / "dialogues.json",
        help="canonical USA dialogue asset (default: assets/dialogues.json)",
    )
    args = ap.parse_args()

    if bool(args.carrier) == bool(args.event):
        ap.error("provide exactly one USA carrier or --event HHHH")

    rom = args.rom.read_bytes()
    try:
        validate_japanese_rom(rom)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    if args.event is not None:
        value = args.event.strip().upper().removeprefix("$")
        try:
            event_id = int(value, 16)
        except ValueError as exc:
            raise SystemExit(f"invalid event ID: {args.event!r}") from exc
        try:
            event = parse_japanese_event(rom, event_id)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        text = [
            {
                "id": token["id"],
                "file_offset": f"{token['file_offset']:06X}",
                "raw_hex": token["raw"].hex(" ").upper(),
                "text": token["source"],
            }
            for token in event["tokens"]
            if token.get("type") == "text"
        ]
        if args.json:
            print(json.dumps({"event_id": event["event_id"], "japanese_event_text": text}, ensure_ascii=False, indent=2))
            return
        print(f"Japanese event: ${event['event_id']}  start {event['jp_event_start']}  pointer ${event['jp_pointer']}")
        for index, token in enumerate(text, 1):
            print()
            _print_text_block(f"JP text {index}", token)
        return

    try:
        result = extract_for_us_carrier(rom, args.carrier, source_path=args.source)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    payload = extraction_to_json(result)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print(f"USA carrier : {payload['us_carrier']}")
    print(f"Event       : ${payload['event_id']}")
    print(f"USA text    : {payload['us_text']!r}")
    print(f"Match       : {payload['match_kind']}")
    print(f"Note        : {payload['note']}")
    if payload["japanese_matches"]:
        for index, token in enumerate(payload["japanese_matches"], 1):
            print()
            _print_text_block("Japanese match" if index == 1 else f"Japanese match {index}", token)
    else:
        print("\nNo single Japanese carrier is asserted. Complete Japanese text for this event:")
        for index, token in enumerate(payload["japanese_event_text"], 1):
            print()
            _print_text_block(f"JP text {index}", token)


if __name__ == "__main__":
    main()
