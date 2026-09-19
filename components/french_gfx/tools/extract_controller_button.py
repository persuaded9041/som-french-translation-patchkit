#!/usr/bin/env python3
"""Extract the canonical French 16x16 controller-button shape as indexed PNG."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from PIL import Image

EXPECTED_FR_SHA256 = "b730adcbb34a19f8fd1c2abe27455cc3256329a9b8a021291e3009ea33004127"
BUTTON_GFX_ROM = 0x12D8F0
BUTTON_GFX_SIZE = 0x40


def decode(blob: bytes) -> list[int]:
    pixels = [0] * (16 * 16)
    for tile_index in range(4):
        tile = blob[tile_index * 16:(tile_index + 1) * 16]
        tile_x = tile_index % 2
        tile_y = tile_index // 2
        for row in range(8):
            p0, p1 = tile[row * 2:row * 2 + 2]
            for column in range(8):
                bit = 7 - column
                value = ((p0 >> bit) & 1) | (((p1 >> bit) & 1) << 1)
                x = tile_x * 8 + column
                y = tile_y * 8 + row
                pixels[y * 16 + x] = value
    return pixels


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path, help="clean unheadered Secret of Mana (France) (Rev 1) ROM")
    parser.add_argument("-o", "--output", type=Path, default=Path("controller_button.png"))
    args = parser.parse_args()

    rom = args.rom.read_bytes()
    digest = hashlib.sha256(rom).hexdigest()
    if digest != EXPECTED_FR_SHA256:
        raise SystemExit(f"Unexpected French ROM SHA-256: {digest}")

    blob = rom[BUTTON_GFX_ROM:BUTTON_GFX_ROM + BUTTON_GFX_SIZE]
    image = Image.new("P", (16, 16))
    image.putdata(decode(blob))
    # Preview colors use the official French A-button ramp; index 0 is transparent.
    image.putpalette([0, 0, 0, 49, 0, 0, 197, 0, 0, 230, 98, 98] + [0, 0, 0] * 252)
    image.info["transparency"] = 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    image.save(args.output)
    print(args.output)


if __name__ == "__main__":
    main()
