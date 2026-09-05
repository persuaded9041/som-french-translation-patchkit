#!/usr/bin/env python3
"""Build the stock-dialogue source/translation data component.

Component 08 deliberately owns dialogue *data*, not the runtime VWF engine.
The root source asset contains every text-bearing stock event script except event
$0400, which is owned by component 05. French edits live separately in
translations/dialogues_french.json. Unchanged text reuses its exact source encoding.

Edited events are rebuilt in place when they still fit their original pointer
span. If an event grows, it is relocated deterministically to the component-08
expanded-ROM pool and a sparse event-dispatch table redirects only that event.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(ROOT))

from dialogue_codec import (  # noqa: E402
    count_edited_text_tokens,
    load_document,
    read_event,
    serialize_event,
    verify_source_roundtrip,
    verify_unedited_reinsertion,
)
from relocation import (  # noqa: E402
    install as install_relocation,
    pack_events,
    validate_stock as validate_relocation_stock,
)
from shared.french_charset import FIRST_CODE, FULL_DTE_THRESHOLD, FULL_FRENCH_CHARS, glyph_bytes  # noqa: E402
from shared.ips import make_ips  # noqa: E402
from shared.rom import ROM_SIZE_OFFSET, expand_rom, update_checksum, validate_base_rom  # noqa: E402
from shared.translation_json import load_translation  # noqa: E402

DIALOGUE_FILE = PROJECT_ROOT / "assets" / "dialogues.json"
TRANSLATION_FILE = PROJECT_ROOT / "translations" / "dialogues_french.json"
DTE_COMPARE_IMMEDIATE_OFFSET = 0x0016F6
DTE_STOCK_THRESHOLD = 0xD3
FONT_BASE = 0x12DC00
INTRO_EVENT_ID = 0x0400

def build(base: bytes, dialogue_file: Path = DIALOGUE_FILE, translation_file: Path = TRANSLATION_FILE) -> tuple[bytes, bytearray, list[str]]:
    validate_base_rom(base)
    document = load_document(dialogue_file)
    try:
        translations = load_translation(translation_file, document, source_asset="dialogues.json")
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    event_count, byte_count = verify_source_roundtrip(base, document)
    reports = [
        f"Source round-trip OK: {event_count} event(s), {byte_count} bytes byte-identical"
    ]

    edits = count_edited_text_tokens(document, translations)
    if edits == 0:
        no_op_events, no_op_bytes = verify_unedited_reinsertion(base, document)
        reports.append(
            f"Editable no-op reinsertion OK: {no_op_events} event(s), "
            f"{no_op_bytes} bytes byte-identical"
        )
    else:
        reports.append(f"Editable text tokens changed: {edits}")

    rebuilt_events: list[tuple[dict, bytes, bytes, int, int]] = []
    relocation_inputs: list[tuple[int, bytes]] = []
    for event in document["events"]:
        event_id = int(event["event_id"], 16)
        if event_id == INTRO_EVENT_ID:
            raise SystemExit(
                "Event $0400 is owned by component 05_intro_vwf_french and must not be rebuilt by component 08"
            )

        source_data, file_start, pointer = read_event(base, event_id)
        rebuilt = serialize_event(base, event, translations=translations, source=False)
        if not source_data or source_data[-1] != 0x00:
            raise SystemExit(
                f"Event ${event_id:04X}: source span must end in END ($00)"
            )
        if not rebuilt or rebuilt[-1] != 0x00:
            raise SystemExit(f"Event ${event_id:04X}: rebuilt event must end in END ($00)")

        if len(rebuilt) > len(source_data):
            relocation_inputs.append((event_id, rebuilt))
        rebuilt_events.append((event, source_data, rebuilt, file_start, pointer))

    relocated = pack_events(relocation_inputs)
    relocated_by_id = {item.event_id: item for item in relocated}
    if relocated:
        validate_relocation_stock(base)
        rom = expand_rom(base)
        rom[ROM_SIZE_OFFSET] = 0x0C
        install_relocation(rom, relocated)
    else:
        rom = bytearray(base)

    # No translated dialogue means no French-font write. Once a future
    # checkpoint changes at least one text token, standalone component 08 installs
    # the same canonical full-French direct glyphs / threshold used by 05/06.
    if edits:
        if base[DTE_COMPARE_IMMEDIATE_OFFSET] != DTE_STOCK_THRESHOLD:
            raise SystemExit(
                f"Unexpected stock DTE threshold at 0x{DTE_COMPARE_IMMEDIATE_OFFSET:06X}: "
                f"${base[DTE_COMPARE_IMMEDIATE_OFFSET]:02X}"
            )
        rom[DTE_COMPARE_IMMEDIATE_OFFSET] = FULL_DTE_THRESHOLD
        french_glyphs = glyph_bytes(FULL_FRENCH_CHARS)
        glyph_start = FONT_BASE + (FIRST_CODE - 0x80) * 12
        rom[glyph_start:glyph_start + len(french_glyphs)] = french_glyphs

    edited_reports: list[str] = []
    for event, source_data, rebuilt, file_start, pointer in rebuilt_events:
        event_id = int(event["event_id"], 16)
        relocated_event = relocated_by_id.get(event_id)
        if relocated_event is not None:
            edited_reports.append(
                f"${event_id:04X}: {len(source_data)} -> {len(rebuilt)} bytes relocated to "
                f"${relocated_event.cpu_address:06X} (growth)"
            )
            continue

        if len(rebuilt) > len(source_data):
            raise AssertionError(f"event ${event_id:04X} growth was not assigned relocation space")

        # Shorter rebuilt events remain in place. Filling the unused tail with
        # END bytes keeps every following stock pointer untouched.
        padded = rebuilt + bytes(len(source_data) - len(rebuilt))
        rom[file_start:file_start + len(source_data)] = padded
        if rebuilt != source_data:
            edited_reports.append(
                f"${event_id:04X}: {len(source_data)} -> {len(rebuilt)} meaningful bytes "
                f"at {'C9' if event_id < 0x400 else 'CA'}:${pointer:04X} "
                f"(in-place, {len(source_data) - len(rebuilt)} END padding bytes)"
            )

    if not edited_reports:
        reports.append("Dialogue event-data writes: none (no French dialogue translations are present)")
    else:
        reports.extend(edited_reports)

    if relocated:
        reports.append(f"Relocated event count: {len(relocated)}")

    update_checksum(rom)
    return make_ips(base, bytes(rom)), rom, reports


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path, help="clean unheadered Secret of Mana (USA) ROM")
    parser.add_argument("-o", "--output", type=Path, default=ROOT / "build" / "patch.ips")
    parser.add_argument("--dialogues", type=Path, default=DIALOGUE_FILE, help="canonical dialogue source JSON")
    parser.add_argument("--translation", type=Path, default=TRANSLATION_FILE, help="sparse French translation JSON")
    parser.add_argument("--patched-rom", type=Path, help="optional local patched ROM output")
    args = parser.parse_args()

    base = args.rom.resolve().read_bytes()
    patch, patched, reports = build(base, args.dialogues.resolve(), args.translation.resolve())

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(patch)
    if args.patched_rom:
        args.patched_rom.parent.mkdir(parents=True, exist_ok=True)
        args.patched_rom.write_bytes(patched)
        print(f"Patched ROM: {args.patched_rom}")

    for report in reports:
        print(report)
    print(f"IPS: {args.output}")


if __name__ == "__main__":
    main()
