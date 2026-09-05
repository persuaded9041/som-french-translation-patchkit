#!/usr/bin/env python3
"""Generate sparse French translation JSONs from the original Android text files.

For now only the new-game intro is mapped. The scrtxt reader is generic so more
Android-script families can be added without changing the binary parser.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shared.intro_event_text import load_document as load_intro_source  # noqa: E402

DEFAULT_SCRTXT = ROOT / "sources" / "android" / "scrtxt_fr.bin"
DEFAULT_INTRO_OUTPUT = ROOT / "translations" / "intro_event_french.json"
INTRO_ANDROID_IDS = tuple(range(3445, 3453))
INTRO_TARGET_IDS = (
    "CA:0C0D",
    "CA:0C59",
    "CA:0CB3",
    "CA:0D0C",
    "CA:0D5C",
    "CA:0DAB",
    "CA:0DFF",
    "CA:0E21",
)


def read_scrtxt(path: Path) -> dict[int, str]:
    """Read an Android scrtxt binary into ``android_id -> UTF-8 text``."""
    data = path.read_bytes()
    if len(data) < 8:
        raise ValueError(f"{path}: file is too small to be a scrtxt binary")

    entry_count, pool_size = struct.unpack_from("<II", data, 0)
    table_end = 8 + entry_count * 8
    if table_end > len(data):
        raise ValueError(f"{path}: entry table extends beyond end of file")
    if table_end + pool_size != len(data):
        raise ValueError(
            f"{path}: declared pool size does not match file size "
            f"({pool_size} bytes declared, {len(data) - table_end} available)"
        )

    pool = data[table_end:]
    result: dict[int, str] = {}
    for index in range(entry_count):
        text_id, offset = struct.unpack_from("<II", data, 8 + index * 8)
        if text_id in result:
            raise ValueError(f"{path}: duplicate Android text ID {text_id}")
        if offset >= len(pool):
            raise ValueError(f"{path}: text ID {text_id} has invalid offset {offset:#x}")
        end = pool.find(b"\x00", offset)
        if end < 0:
            raise ValueError(f"{path}: text ID {text_id} is not NUL-terminated")
        try:
            result[text_id] = pool[offset:end].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"{path}: text ID {text_id} is not valid UTF-8") from exc
    return result


def normalize_android_prose(text: str) -> str:
    """Remove source-layout whitespace while preserving the translated prose."""
    return " ".join(text.replace("\r", " ").replace("\n", " ").split())


def make_intro_translation(scrtxt: dict[int, str]) -> dict:
    source = load_intro_source(ROOT / "assets" / "intro_event.json")
    source_ids = tuple(entry["id"] for entry in source["entries"])
    if source_ids != INTRO_TARGET_IDS:
        raise ValueError(
            "assets/intro_event.json IDs/order no longer match the validated Android intro mapping"
        )

    missing = [text_id for text_id in INTRO_ANDROID_IDS if text_id not in scrtxt]
    if missing:
        raise ValueError("Missing Android intro text ID(s): " + ", ".join(map(str, missing)))

    entries = [
        {
            "id": target_id,
            "text": normalize_android_prose(scrtxt[android_id]),
        }
        for android_id, target_id in zip(INTRO_ANDROID_IDS, INTRO_TARGET_IDS, strict=True)
    ]
    return {
        "format_version": 1,
        "language": "fr",
        "source_asset": "intro_event.json",
        "groups": [
            {
                "group": "intro.event_0400",
                "entries": entries,
            }
        ],
    }


def serialized(document: dict) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--only",
        choices=("intro",),
        default="intro",
        help="translation family to generate (currently only: intro)",
    )
    parser.add_argument(
        "--scrtxt",
        type=Path,
        default=DEFAULT_SCRTXT,
        help="Android French scrtxt binary",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_INTRO_OUTPUT,
        help="destination JSON (for --only intro)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify that the destination already equals generated output",
    )
    args = parser.parse_args()

    try:
        scrtxt = read_scrtxt(args.scrtxt.resolve())
        document = make_intro_translation(scrtxt)
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc

    output = args.output.resolve()
    text = serialized(document)
    if args.check:
        try:
            existing = output.read_text(encoding="utf-8")
        except OSError as exc:
            raise SystemExit(f"Cannot read {output}: {exc}") from exc
        if existing != text:
            raise SystemExit(f"{output} is not up to date with {args.scrtxt.resolve()}")
        print(f"Android translation import OK: {output}")
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    print(
        f"Generated {output} from {args.scrtxt.resolve()} "
        f"({len(INTRO_ANDROID_IDS)} intro entries)"
    )


if __name__ == "__main__":
    main()
