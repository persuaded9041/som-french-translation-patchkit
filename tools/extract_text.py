#!/usr/bin/env python3
"""Extract the patchkit's canonical text JSON assets from a clean USA ROM."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
COMPONENT_08 = ROOT / "components" / "08_dialogue_text"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(COMPONENT_08))

from dialogue_codec import EVENT_COUNT, extract_default_document, extract_document, parse_event  # noqa: E402
from shared.battle_text import extract_document as extract_battle_document  # noqa: E402
from shared.interface_text import extract_document as extract_interface_document  # noqa: E402
from shared.intro_event_text import make_document as extract_intro_document  # noqa: E402
from shared.menu_text import extract_document as extract_menu_document  # noqa: E402
from shared.opening_text import extract_document as extract_opening_document  # noqa: E402
from shared.shop_text import extract_document as extract_shop_document  # noqa: E402
from shared.text_resources import extract_document as extract_resource_document  # noqa: E402

DEFAULT_ASSETS = ROOT / "assets"
KINDS = ("dialogues", "resources", "interface", "menu", "battle", "shop", "opening", "intro")


def write_json(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path, help="clean unheadered Secret of Mana (USA) ROM")
    parser.add_argument(
        "--assets-dir",
        type=Path,
        default=DEFAULT_ASSETS,
        help="canonical output directory (default: <repo>/assets)",
    )
    parser.add_argument(
        "--only",
        choices=KINDS,
        help="extract only one canonical JSON instead of the full inventory",
    )
    parser.add_argument(
        "--event",
        action="append",
        default=[],
        help="research mode: dialogue event ID in hex; repeat as needed (requires --only dialogues)",
    )
    parser.add_argument(
        "--all-events",
        action="store_true",
        help="research mode: extract all 2048 event scripts (requires --only dialogues)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="research/single-kind output path; otherwise canonical filenames are used",
    )
    args = parser.parse_args()

    if (args.event or args.all_events) and args.only != "dialogues":
        parser.error("--event/--all-events require --only dialogues")
    if args.event and args.all_events:
        parser.error("--event and --all-events are mutually exclusive")
    if args.output and args.only is None:
        parser.error("--output requires --only")

    rom = args.rom.resolve().read_bytes()
    assets_dir = args.assets_dir.resolve()

    if args.only in (None, "dialogues"):
        if args.event:
            event_ids = tuple(int(value, 16) for value in args.event)
            document = extract_document(rom, event_ids)
            label = f"{len(document['events'])} explicit dialogue event(s)"
        elif args.all_events:
            document = extract_document(rom, range(EVENT_COUNT))
            label = f"all {EVENT_COUNT} stock event scripts"
        else:
            document = extract_default_document(rom)
            label = f"{len(document['events'])} component-08 text-bearing event(s)"
        output = args.output.resolve() if args.output else assets_dir / "dialogues.json"
        write_json(output, document)
        print(f"Dialogues: {label} -> {output}")

    if args.only in (None, "resources"):
        document = extract_resource_document(rom)
        output = args.output.resolve() if args.output else assets_dir / "text_resources.json"
        write_json(output, document)
        print(f"Text resources: {len(document['resources'])} entries -> {output}")

    if args.only in (None, "interface"):
        document = extract_interface_document(rom)
        output = args.output.resolve() if args.output else assets_dir / "interface_text.json"
        write_json(output, document)
        entry_count = sum(len(group["entries"]) for group in document["groups"])
        print(
            f"Interface text: {len(document['groups'])} block(s), "
            f"{entry_count} source line(s) -> {output}"
        )

    if args.only in (None, "menu"):
        document = extract_menu_document(rom)
        output = args.output.resolve() if args.output else assets_dir / "menu_text.json"
        write_json(output, document)
        entry_count = sum(len(group["entries"]) for group in document["groups"])
        print(f"Menu/status text: {entry_count} source record(s) -> {output}")

    if args.only in (None, "battle"):
        document = extract_battle_document(rom)
        output = args.output.resolve() if args.output else assets_dir / "battle_text.json"
        write_json(output, document)
        print(f"Battle text: {len(document['records'])} source record(s) -> {output}")

    if args.only in (None, "shop"):
        document = extract_shop_document(rom)
        output = args.output.resolve() if args.output else assets_dir / "shop_text.json"
        write_json(output, document)
        print(f"Shop/forge text: {len(document['records'])} source record(s) -> {output}")

    if args.only in (None, "opening"):
        document = extract_opening_document(rom)
        output = args.output.resolve() if args.output else assets_dir / "opening_text.json"
        write_json(output, document)
        entry_count = sum(len(group["entries"]) for group in document["groups"])
        print(f"Opening text: {entry_count} source record(s) -> {output}")

    if args.only in (None, "intro"):
        document = extract_intro_document(parse_event(rom, 0x0400))
        output = args.output.resolve() if args.output else assets_dir / "intro_event.json"
        write_json(output, document)
        print(f"Intro event: {len(document['entries'])} source text part(s) -> {output}")


if __name__ == "__main__":
    main()
