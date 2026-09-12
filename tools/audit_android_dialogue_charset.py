#!/usr/bin/env python3
"""Audit unsupported characters in accepted Android-French dialogue mappings."""
from __future__ import annotations

import argparse
import csv
import io
import json
from collections import Counter, defaultdict
from pathlib import Path
import sys
import unicodedata

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shared.dialogue.codec import parse_event  # noqa: E402
from shared.dialogue.translation import PLAYER_PLACEHOLDER_RE, normalize_android_french  # noqa: E402
from shared.core.rom import validate_base_rom  # noqa: E402
from shared.text.stock import TEXT_TO_CODE  # noqa: E402
from tools.dialogue_pipeline.alignment import make_dialogue_auto_alignment  # noqa: E402
from tools.dialogue_pipeline.common import DEFAULT_SCRTXT_EN, DEFAULT_SCRTXT_FR, read_scrtxt  # noqa: E402

DEFAULT_OUTPUT = ROOT / "reports" / "android" / "dialogue_charset_audit.csv"

ACTIONS = {
    '"': (
        "typography_normalization",
        "Use existing stock opening/closing quotes (`“`/`”`, codes $C3/$C4). "
        "Pair quote state across consecutive mappings in the same event; event $04E3 proves a pair can span two mappings.",
    ),
    "→": (
        "snes_structural_glyph",
        "Do not encode as prose. Events $0605/$0606 already contain raw SNES right-arrow glyph $D0; preserve that token and remove the Android presentation arrow from localized prose.",
    ),
    "←": (
        "snes_structural_glyph",
        "Do not encode as prose. Event $0607 already contains raw SNES left-arrow glyph $CF; preserve that token and remove the Android presentation arrow from localized prose.",
    ),
    "▽": (
        "android_ui_marker_or_snes_structural_glyph",
        "Do not add a new glyph. Event $0081 already has raw SNES glyph $CE before the prompt; event $05DA has no equivalent source glyph, so the Android-only prompt marker should be dropped.",
    ),
    "[": (
        "presentation_normalization",
        "Normalize to `(`. In event $04E4 the canonical SNES choice text already uses parentheses around the same choices.",
    ),
    "]": (
        "presentation_normalization",
        "Normalize to `)`. In event $04E4 the canonical SNES choice text already uses parentheses around the same choices.",
    ),
}



def make_csv(mapping: dict) -> tuple[bytes, int, int]:
    occurrences: Counter[str] = Counter()
    mapping_units: Counter[str] = Counter()
    examples: dict[str, list[str]] = defaultdict(list)

    for entry in mapping["mappings"]:
        text = normalize_android_french(entry.get("french_display", ""))
        text = PLAYER_PLACEHOLDER_RE.sub("", text)
        seen: set[str] = set()
        for char in text:
            if char in TEXT_TO_CODE:
                continue
            occurrences[char] += 1
            seen.add(char)
            if len(examples[char]) < 3:
                rendered = entry.get("french_display", "").strip().replace("\r", "").replace("\n", " ⏎ ")
                examples[char].append(
                    f"${entry['event_id']} / {' + '.join(entry['snes_ids'])}: {rendered}"
                )
        for char in seen:
            mapping_units[char] += 1

    output = io.StringIO(newline="")
    fields = [
        "character",
        "unicode",
        "unicode_name",
        "occurrences",
        "mapping_units",
        "classification",
        "proposed_action",
        "examples",
    ]
    writer = csv.DictWriter(
        output,
        fieldnames=fields,
        delimiter=";",
        quoting=csv.QUOTE_MINIMAL,
        lineterminator="\n",
    )
    writer.writeheader()
    for char in sorted(occurrences, key=lambda value: (-occurrences[value], ord(value))):
        classification, action = ACTIONS.get(char, ("unclassified", "Review manually before formatting."))
        writer.writerow(
            {
                "character": char,
                "unicode": f"U+{ord(char):04X}",
                "unicode_name": unicodedata.name(char, ""),
                "occurrences": occurrences[char],
                "mapping_units": mapping_units[char],
                "classification": classification,
                "proposed_action": action,
                "examples": " || ".join(examples[char]),
            }
        )
    return ("\ufeff" + output.getvalue()).encode("utf-8"), len(occurrences), sum(occurrences.values())


def scan_stock_high_dte(rom: bytes) -> Counter[int]:
    """Count raw $D3-$FF bytes in ordinary text tokens across all stock events."""
    usage: Counter[int] = Counter()
    for event_id in range(0x800):
        event = parse_event(rom, event_id, include_source_bytes=True)
        for token in event["tokens"]:
            if token.get("type") != "text":
                continue
            for value in token.get("_source_bytes", b""):
                if 0xD3 <= value <= 0xFF:
                    usage[value] += 1
    return usage


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mapping",
        type=Path,
        help="optional pre-generated alignment JSON; default regenerates alignment from canonical Android EN/FR inputs",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--rom", type=Path, help="optional clean unheadered USA ROM for stock $D3-$FF event-text scan")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if args.mapping is not None:
        mapping = json.loads(args.mapping.read_text(encoding="utf-8"))
        mapping_source = str(args.mapping)
    else:
        english = read_scrtxt(DEFAULT_SCRTXT_EN)
        french = read_scrtxt(DEFAULT_SCRTXT_FR)
        mapping = make_dialogue_auto_alignment(
            english,
            french,
            english_path=DEFAULT_SCRTXT_EN,
            french_path=DEFAULT_SCRTXT_FR,
        )
        mapping_source = "canonical Android EN/FR + reviewed alignment recipes"
    csv_bytes, unique_count, occurrence_count = make_csv(mapping)

    if args.check:
        if args.output.read_bytes() != csv_bytes:
            raise SystemExit(f"{args.output} is not up to date")
        print(f"Charset audit CSV check OK: {args.output}")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(csv_bytes)
        print(f"Generated {args.output}")

    print(f"Alignment source: {mapping_source}")
    print(f"Unsupported after layout/placeholder normalization: {unique_count} unique / {occurrence_count} occurrences")

    if args.rom:
        rom = args.rom.read_bytes()
        validate_base_rom(rom)
        usage = scan_stock_high_dte(rom)
        if usage:
            rendered = ", ".join(f"${code:02X}:{count}" for code, count in sorted(usage.items()))
            print(f"Stock ordinary event text uses upper DTE bytes: {rendered}")
        else:
            print("Stock ordinary event text scan: no raw $D3-$FF bytes in any of 2048 events")


if __name__ == "__main__":
    main()
