#!/usr/bin/env python3
"""Verify deterministic clean-ROM extraction/reinsertion for root text assets."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shared.dialogue_codec import (  # noqa: E402
    EVENT_COUNT,
    load_document as load_dialogues,
    parse_event,
    verify_source_roundtrip as verify_dialogue_source,
    verify_unedited_reinsertion as verify_dialogue_noop,
)
from shared.battle_text import load_document as load_battle, verify_against_rom as verify_battle  # noqa: E402
from shared.interface_text import load_document as load_interface, verify_against_rom as verify_interface  # noqa: E402
from shared.intro_event_text import load_document as load_intro, make_document as extract_intro  # noqa: E402
from shared.menu_text import load_document as load_menu, verify_against_rom as verify_menu  # noqa: E402
from shared.opening_text import load_document as load_opening, verify_against_rom as verify_opening  # noqa: E402
from shared.shop_text import load_document as load_shop, verify_against_rom as verify_shop  # noqa: E402
from shared.translation_json import load_translation, source_entries  # noqa: E402
from shared.text_resources import (  # noqa: E402
    load_document as load_resources,
    verify_pointer_table_and_blob,
    verify_source_roundtrip as verify_resource_source,
    verify_unedited_reinsertion as verify_resource_noop,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path, help="clean unheadered Secret of Mana (USA) ROM")
    parser.add_argument("--dialogues", type=Path, default=ROOT / "assets" / "dialogues.json")
    parser.add_argument("--resources", type=Path, default=ROOT / "assets" / "text_resources.json")
    parser.add_argument("--interface", type=Path, default=ROOT / "assets" / "interface_text.json")
    parser.add_argument("--menu", type=Path, default=ROOT / "assets" / "menu_text.json")
    parser.add_argument("--battle", type=Path, default=ROOT / "assets" / "battle_text.json")
    parser.add_argument("--opening", type=Path, default=ROOT / "assets" / "opening_text.json")
    parser.add_argument("--shop", type=Path, default=ROOT / "assets" / "shop_text.json")
    parser.add_argument("--intro", type=Path, default=ROOT / "assets" / "intro_event.json")
    parser.add_argument(
        "--scan-all-events",
        action="store_true",
        help="also parse all 2048 stock event scripts",
    )
    args = parser.parse_args()

    rom = args.rom.resolve().read_bytes()

    dialogues = load_dialogues(args.dialogues.resolve())
    if args.scan_all_events:
        for event_id in range(EVENT_COUNT):
            parse_event(rom, event_id)
        print(f"Event structural scan OK: all {EVENT_COUNT} scripts parse")
    count, size = verify_dialogue_source(rom, dialogues)
    print(f"Dialogue source round-trip OK: {count} event(s), {size} bytes")
    count, size = verify_dialogue_noop(rom, dialogues)
    print(f"Dialogue translation-free no-op OK: {count} event(s), {size} bytes")

    resources = load_resources(args.resources.resolve())
    count, size = verify_resource_source(rom, resources)
    print(f"Text-resource source round-trip OK: {count} resource(s), {size} bytes")
    count, size = verify_resource_noop(rom, resources)
    print(f"Text-resource translation-free no-op OK: {count} resource(s), {size} bytes")
    table_size, blob_size = verify_pointer_table_and_blob(rom, resources)
    print(
        f"Text-resource table/blob round-trip OK: {table_size} pointer-table bytes, "
        f"{blob_size} string bytes"
    )

    interface = load_interface(args.interface.resolve())
    group_count, entry_count = verify_interface(rom, interface)
    print(f"Interface-text extraction OK: {group_count} block(s), {entry_count} source line(s)")

    menu = load_menu(args.menu.resolve())
    group_count, entry_count = verify_menu(rom, menu)
    print(f"Menu/status extraction OK: {group_count} group(s), {entry_count} source record(s)")

    battle = load_battle(args.battle.resolve())
    record_count, table_bytes, blob_bytes = verify_battle(rom, battle)
    print(
        f"Battle-text extraction OK: {record_count} record(s), "
        f"{table_bytes} pointer-table bytes, {blob_bytes} string-pool bytes"
    )

    shop = load_shop(args.shop.resolve())
    record_count, reference_count, blob_bytes = verify_shop(rom, shop)
    print(
        f"Shop/forge extraction OK: {record_count} record(s), "
        f"{reference_count} code reference(s), {blob_bytes} mini-script bytes"
    )

    opening = load_opening(args.opening.resolve())
    group_count, entry_count = verify_opening(rom, opening)
    print(f"Opening-text extraction OK: {group_count} group(s), {entry_count} source record(s)")

    intro = load_intro(args.intro.resolve())
    canonical_intro = extract_intro(parse_event(rom, 0x0400))
    if intro != canonical_intro:
        raise ValueError("intro_event.json differs from a fresh event-$0400 extraction")
    print(f"Intro-event extraction OK: {len(intro['entries'])} source text part(s)")

    source_documents = {
        "dialogues.json": dialogues,
        "text_resources.json": resources,
        "interface_text.json": interface,
        "menu_text.json": menu,
        "battle_text.json": battle,
        "shop_text.json": shop,
        "opening_text.json": opening,
        "intro_event.json": intro,
    }
    seen: dict[str, str] = {}
    for asset_name, document in source_documents.items():
        for entry in source_entries(document):
            text_id = entry["id"]
            if text_id in seen:
                raise ValueError(
                    f"Global text ID collision: {text_id} appears in {seen[text_id]} and {asset_name}"
                )
            seen[text_id] = asset_name
    print(f"Global text IDs OK: {len(seen)} unique source element(s)")

    for translation_path in sorted((ROOT / "translations").glob("*_french.json")):
        raw = json.loads(translation_path.read_text(encoding="utf-8"))
        source_asset = raw.get("source_asset")
        if source_asset not in source_documents:
            raise ValueError(f"{translation_path.name}: unknown source_asset {source_asset!r}")
        translations = load_translation(
            translation_path, source_documents[source_asset], source_asset=source_asset
        )
        print(f"Translation binding OK: {translation_path.name}: {len(translations)} entry(s)")


if __name__ == "__main__":
    main()
