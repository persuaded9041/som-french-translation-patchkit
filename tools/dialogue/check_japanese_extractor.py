#!/usr/bin/env python3
"""Regression checks for the Japanese dialogue extraction helper."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shared.dialogue.japanese import (  # noqa: E402
    extract_for_us_carrier,
    parse_japanese_event,
    validate_japanese_rom,
)

SOURCE = ROOT / "assets" / "dialogues.json"

EXPECTED = {
    "C9:916F": "「世界から　マナが失われようと\n　している　しょうこじゃ！",
    "C9:9193": "『‥‥ぼくが剣を抜いてしまった\n　ために　みんなにめいわくが‥‥",
    "C9:9F88": "た、たいへんじゃ、神殿の中に\n帝国のモンスターが！",
    "C9:D1B8": "ドリアード",
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("rom", type=Path, help="clean unheadered Seiken Densetsu 2 (Japan) ROM")
    args = ap.parse_args()
    rom = args.rom.read_bytes()
    validate_japanese_rom(rom)

    for carrier, expected in EXPECTED.items():
        result = extract_for_us_carrier(rom, carrier, source_path=SOURCE)
        if len(result.japanese_matches) != 1:
            raise SystemExit(f"{carrier}: expected one structural Japanese match, got {result.match_kind}")
        actual = result.japanese_matches[0].text
        if actual != expected:
            raise SystemExit(f"{carrier}: Japanese transcription drifted: {actual!r}")

    # $0278 is intentionally a regional resegmentation: the two USA controller
    # carriers live together inside one Japanese text block.  The extractor must
    # expose the block as context and must not fabricate a one-to-one carrier.
    for carrier in ("C9:A730", "C9:A74E"):
        result = extract_for_us_carrier(rom, carrier, source_path=SOURCE)
        if result.match_kind != "resegmented_or_ambiguous" or result.japanese_matches:
            raise SystemExit(f"{carrier}: resegmentation must remain non-one-to-one")
        combined = "\n".join(token.text for token in result.japanese_text_tokens)
        if "（ＳＴＡＲＴ：マップをみる　）" not in combined:
            raise SystemExit(f"{carrier}: missing Japanese START instruction")
        if "（　Ｌ／Ｒ　：モードきりかえ）" not in combined:
            raise SystemExit(f"{carrier}: missing Japanese L/R instruction")

    # Parse every event whose end is established by a following pointer.  This
    # guards both the character tables and command/text discrimination. $03FF
    # is intentionally excluded because the C9 table has no sentinel there.
    parsed = 0
    for event_id in range(0x800):
        if event_id == 0x03FF:
            continue
        parse_japanese_event(rom, event_id)
        parsed += 1

    print(
        "Japanese dialogue extractor OK: "
        f"{len(EXPECTED)} exact regression carriers, 2 resegmented $0278 carriers, "
        f"{parsed} structurally parsed JP events"
    )


if __name__ == "__main__":
    main()
