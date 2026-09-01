#!/usr/bin/env python3
"""
Extract the original Japanese Mana Tree resource from Seiken Densetsu 2.

The extracted file is the 0x3600-byte resource used by the title-screen
restoration patch.
"""

from pathlib import Path
import hashlib
import sys

EXPECTED_JP_SHA1 = "b78a9a844d165345631cea1b5246c8fcbcdbc162"
TREE_OFFSET = 0x07C500
TREE_SIZE = 0x3600
EXPECTED_TREE_SHA1 = "538458875a43c3562aa27fc34c89d87d09402c54"


def sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def main():
    if len(sys.argv) not in (2, 3):
        raise SystemExit(
            'Usage: python3 extract_mana_tree.py '
            '"Seiken Densetsu 2 (Japan).sfc" [mana_tree_jp.bin]'
        )

    rom_path = Path(sys.argv[1])
    output_path = (
        Path(sys.argv[2])
        if len(sys.argv) == 3
        else Path("mana_tree_jp.bin")
    )

    rom = rom_path.read_bytes()

    if sha1(rom) != EXPECTED_JP_SHA1:
        raise SystemExit(
            "Unexpected Japanese ROM SHA-1. "
            "Use the same clean, unheadered Japanese ROM used by this project."
        )

    end = TREE_OFFSET + TREE_SIZE

    if end > len(rom):
        raise SystemExit("ROM is too small")

    tree = rom[TREE_OFFSET:end]

    if sha1(tree) != EXPECTED_TREE_SHA1:
        raise SystemExit("Extracted tree resource failed SHA-1 validation")

    output_path.write_bytes(tree)

    print(f"Written: {output_path}")
    print(f"Size: {len(tree)} bytes")
    print(f"SHA-1: {sha1(tree)}")


if __name__ == "__main__":
    main()
