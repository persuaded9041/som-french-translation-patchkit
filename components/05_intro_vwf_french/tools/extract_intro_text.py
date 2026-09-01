#!/usr/bin/env python3
"""Extract the new-game introduction entries from the Android French scrtxt binary.

The Android text file starts with:
    uint32 entry_count
    uint32 string_pool_size

It is followed by `entry_count` records of:
    uint32 text_id
    uint32 string_offset

Offsets are relative to the UTF-8, NUL-terminated string pool that follows
that table.

For the Secret of Mana new-game introduction, the relevant Android text IDs
are 3445 through 3452 inclusive.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
import struct

INTRO_IDS = tuple(range(3445, 3453))


def read_scrtxt(path: Path) -> dict[int, str]:
    data = path.read_bytes()
    if len(data) < 8:
        raise ValueError("File is too small to be a scrtxt binary")

    entry_count, pool_size = struct.unpack_from("<II", data, 0)
    table_end = 8 + entry_count * 8
    if table_end > len(data):
        raise ValueError("Entry table extends beyond end of file")

    pool = data[table_end:]
    if pool_size > len(pool):
        raise ValueError(
            f"Declared string pool size ({pool_size}) exceeds available data ({len(pool)})"
        )

    result: dict[int, str] = {}
    for index in range(entry_count):
        text_id, offset = struct.unpack_from("<II", data, 8 + index * 8)
        if text_id not in INTRO_IDS:
            continue
        if offset >= len(pool):
            raise ValueError(f"Text ID {text_id}: invalid string offset {offset:#x}")
        end = pool.find(b"\x00", offset)
        if end < 0:
            raise ValueError(f"Text ID {text_id}: unterminated UTF-8 string")
        result[text_id] = pool[offset:end].decode("utf-8")

    missing = [text_id for text_id in INTRO_IDS if text_id not in result]
    if missing:
        raise ValueError(f"Missing introduction text IDs: {missing}")
    return result


def write_csv(texts: dict[int, str], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["android_id", "french"])
        for text_id in INTRO_IDS:
            writer.writerow([text_id, texts[text_id]])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract Secret of Mana's French new-game introduction from scrtxt_fr.bin"
    )
    parser.add_argument("input", type=Path, help="Path to scrtxt_fr.bin")
    parser.add_argument("output", type=Path, help="Destination CSV file")
    args = parser.parse_args()

    texts = read_scrtxt(args.input)
    write_csv(texts, args.output)
    print(f"Extracted {len(INTRO_IDS)} entries to {args.output}")


if __name__ == "__main__":
    main()
