#!/usr/bin/env python3
"""Build the stock-dialogue source/translation data component.

`french_dialogues` deliberately owns dialogue *data*, not the runtime VWF engine.
The root source asset contains every text-bearing stock event script except event
$0400, whose translated payload is owned by `french_intro`. The normal build regenerates
French dialogue data in memory from canonical Android/source inputs; an explicit
`--translation` JSON is only a diagnostic override. Unchanged text reuses its exact
source encoding.

Edited events are rebuilt in place when they still fit their original pointer
span. If an event grows, it is relocated deterministically to the `french_dialogues`
expanded-ROM pool and a sparse event-dispatch table redirects only that event.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from shared.dialogue.codec import (  # noqa: E402
    count_edited_text_tokens,
    load_document,
    read_event,
    serialize_event,
    verify_source_roundtrip,
    verify_unedited_reinsertion,
)
from shared.dialogue.relocation import (  # noqa: E402
    install as install_relocation,
    pack_events,
    validate_stock as validate_relocation_stock,
)
from shared.charset import CHAR_TO_CODE, DIALOGUE_FRENCH_CHARS, glyph_bytes  # noqa: E402
from shared.dialogue.dte import (  # noqa: E402
    enable_extended_dialogue as enable_extended_dialogue_dte,
    install as install_dialogue_dte_router,
    validate_stock as validate_dialogue_dte_stock,
)
from shared.core.ips import make_ips  # noqa: E402
from shared.core.rom import ROM_SIZE_OFFSET, expand_rom, update_checksum, validate_base_rom  # noqa: E402
from shared.dialogue.structure import (  # noqa: E402
    load_structural_omission_token_indexes,
    load_structural_command_overrides,
    load_choice_option_position_overrides,
    resolve_choice_option_position_overrides,
    resolve_structural_command_overrides,
    resolve_structural_omission_token_indexes,
)
from shared.text.translation_json import load_translation, resolve_translation  # noqa: E402
from shared.dialogue.pipeline.common import (  # noqa: E402
    DEFAULT_SCRTXT_EN,
    DEFAULT_SCRTXT_FR,
    read_scrtxt,
)
from shared.dialogue.pipeline.formatter import make_dialogue_format_mass  # noqa: E402
from shared.dialogue.pipeline.cache import load as load_translation_cache, store as store_translation_cache  # noqa: E402
from shared.extracted.assets import load_or_extract_dialogues  # noqa: E402

DIALOGUE_FILE = PROJECT_ROOT / "assets" / "dialogues.json"
FONT_BASE = 0x12DC00
DIALOGUE_CHARS = DIALOGUE_FRENCH_CHARS
GLYPH_FIRST = min(CHAR_TO_CODE[ch] for ch in DIALOGUE_CHARS)
INTRO_EVENT_ID = 0x0400

def _load_or_generate_translation_document(base: bytes, source_document: dict) -> tuple[dict, dict | None, bool]:
    """Load a valid local cache or regenerate and persist it atomically."""
    cached = load_translation_cache(base, source_document)
    if cached is not None:
        return cached, None, True

    english = read_scrtxt(DEFAULT_SCRTXT_EN)
    french = read_scrtxt(DEFAULT_SCRTXT_FR)
    document, report = make_dialogue_format_mass(
        english,
        french,
        english_path=DEFAULT_SCRTXT_EN,
        french_path=DEFAULT_SCRTXT_FR,
        base_rom=base,
        source_document=source_document,
    )
    store_translation_cache(document, base, source_document)
    return document, report, False


def build(
    base: bytes,
    dialogue_file: Path = DIALOGUE_FILE,
    translation_file: Path | None = None,
) -> tuple[bytes, bytearray, list[str]]:
    validate_base_rom(base)
    document = load_or_extract_dialogues(base, dialogue_file)
    try:
        if translation_file is None:
            translation_document, format_report, cache_hit = _load_or_generate_translation_document(base, document)
            translations = resolve_translation(
                translation_document, document, source_asset="dialogues.json", label="generated dialogue translation"
            )
            structural_omissions = resolve_structural_omission_token_indexes(
                translation_document, document, translations=translations
            )
            structural_command_overrides = resolve_structural_command_overrides(
                translation_document, document
            )
            choice_option_overrides = resolve_choice_option_position_overrides(
                translation_document, document
            )
            if cache_hit:
                translation_source_report = (
                    "Dialogue translation cache reused: translations/dialogues_french.json"
                )
            else:
                assert format_report is not None
                translation_source_report = (
                    "Dialogue translation regenerated from canonical Android/source inputs and cached: "
                    f"{len(format_report.get('accepted_events', []))} accepted event(s)"
                )
        else:
            translations = load_translation(translation_file, document, source_asset="dialogues.json")
            structural_omissions = load_structural_omission_token_indexes(
                translation_file, document, translations=translations
            )
            structural_command_overrides = load_structural_command_overrides(
                translation_file, document
            )
            choice_option_overrides = load_choice_option_position_overrides(
                translation_file, document
            )
            translation_source_report = f"Dialogue translation override: {translation_file}"
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc

    event_count, byte_count = verify_source_roundtrip(base, document)
    reports = [
        translation_source_report,
        f"Source round-trip OK: {event_count} event(s), {byte_count} bytes byte-identical",
    ]

    edits = count_edited_text_tokens(document, translations)
    generated_page_breaks = sum(text.count("\f") for text in translations.values())
    if edits == 0:
        no_op_events, no_op_bytes = verify_unedited_reinsertion(base, document)
        reports.append(
            f"Editable no-op reinsertion OK: {no_op_events} event(s), "
            f"{no_op_bytes} bytes byte-identical"
        )
    else:
        reports.append(f"Editable text tokens changed: {edits}")
        if generated_page_breaks:
            reports.append(
                f"Generated explicit dialogue page break(s): {generated_page_breaks} "
                "(WAIT $00 + TEXT_CLEAR)"
            )
    omitted_commands = sum(len(indexes) for indexes in structural_omissions.values())
    structural_command_override_count = sum(len(indexes) for indexes in structural_command_overrides.values())
    choice_override_count = sum(len(indexes) for indexes in choice_option_overrides.values())
    if omitted_commands:
        reports.append(
            f"User-validated Android structural command omission(s): {omitted_commands} "
            f"across {len(structural_omissions)} event(s)"
        )

    if structural_command_override_count:
        reports.append(
            f"User-validated translated command override(s): {structural_command_override_count} "
            f"across {len(structural_command_overrides)} event(s)"
        )

    if choice_override_count:
        reports.append(
            f"VWF-safe CHOICE_OPTION position override(s): {choice_override_count} "
            f"across {len(choice_option_overrides)} event(s)"
        )

    rebuilt_events: list[tuple[dict, bytes, bytes, int, int]] = []
    relocation_inputs: list[tuple[int, bytes]] = []
    for event in document["events"]:
        event_id = int(event["event_id"], 16)
        if event_id == INTRO_EVENT_ID:
            raise SystemExit(
                "Event $0400 is owned by component french_intro and must not be rebuilt by `french_dialogues`"
            )

        source_data, file_start, pointer = read_event(base, event_id)
        rebuilt = serialize_event(
            base,
            event,
            translations=translations,
            source=False,
            omitted_command_token_indexes=structural_omissions.get(event["event_id"]),
            structural_command_overrides=structural_command_overrides.get(event["event_id"]),
            choice_option_position_overrides=choice_option_overrides.get(event["event_id"]),
        )
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

    # No translated dialogue means no French-font write. Whenever at least one
    # text token changes, standalone `french_dialogues` installs the same canonical
    # full-French direct glyphs / threshold used by `french_intro` / `vwf_dialogues`.
    if edits:
        validate_dialogue_dte_stock(base)
        install_dialogue_dte_router(rom)
        enable_extended_dialogue_dte(rom)
        dialogue_glyphs = glyph_bytes(DIALOGUE_CHARS)
        glyph_start = FONT_BASE + (GLYPH_FIRST - 0x80) * 12
        rom[glyph_start:glyph_start + len(dialogue_glyphs)] = dialogue_glyphs

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
    parser.add_argument(
        "--translation",
        type=Path,
        help=(
            "explicit sparse French translation JSON override; by default the canonical "
            "Android-FR dialogue translation is regenerated in memory"
        ),
    )
    parser.add_argument("--patched-rom", type=Path, help="optional local patched ROM output")
    args = parser.parse_args()

    base = args.rom.resolve().read_bytes()
    translation = args.translation.resolve() if args.translation else None
    patch, patched, reports = build(base, args.dialogues.resolve(), translation)

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
