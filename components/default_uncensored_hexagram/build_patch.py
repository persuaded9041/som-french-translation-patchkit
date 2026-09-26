#!/usr/bin/env python3
"""Build the Japanese hexagram warp-graphic restoration patch."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from shared.core.ips import apply_ips, make_ips  # noqa: E402
from shared.core.rom import update_checksum, validate_base_rom  # noqa: E402


# Three 8x8 4bpp tiles are split by unrelated data.  The first tile is at
# $DD:B840; the second and third are at $DD:B900-$B93F.  The intervening
# $DD:B860-$B8FF region is intentionally not part of this component.
WARP_TILE_1_ROM = 0x1DB840
WARP_TILE_23_ROM = 0x1DB900
WARP_TILE_1_SIZE = 0x20
WARP_TILE_23_SIZE = 0x40

STOCK_WARP_TILE_1 = bytes.fromhex("9D D6 BB B6 37 AC 7C 6E 7F 40 FF FF 00 00 F7 F7 00 EF 00 CF 00 DF 01 9F 00 BF 00 00 00 FF 08 FF")
STOCK_WARP_TILE_23 = bytes.fromhex(
    "F2 F2 46 C6 4D ED CD CD 99 99 9B DB 17 97 05 B5 "
    "04 F9 28 F1 00 F3 10 E3 40 E7 00 E7 20 CF 32 CF "
    "3D 7D FB FB B3 FA 67 F6 F6 F5 CE EC CC C9 DD D9 "
    "00 FE 00 FC 00 FD 00 F9 00 FB 01 F3 02 F7 02 E7"
)
JAPANESE_WARP_TILES = bytes.fromhex(
    "5D 56 BB B6 37 AC 7C 6E 7F 40 FF FF 00 00 F7 F7 "
    "00 AF 00 CF 00 DF 01 9F 00 BF 00 00 00 FF 08 FF "
    "F2 F2 46 C6 4D ED CD CD 99 99 9A DA 16 96 05 B5 "
    "04 F9 28 F1 00 F2 10 E2 40 E6 00 E7 20 CF 32 CF "
    "3D 7D 03 03 FB FA 07 06 96 95 8E 8C CC C9 5D 59 "
    "00 FE 00 FC 00 05 00 F9 20 7B 21 73 02 37 02 A7"
)


def encode_4bpp_tiles(path: Path) -> bytes:
    """Encode the canonical 24x8 indexed PNG as three SNES 4bpp tiles."""
    with Image.open(path) as source:
        image = source.copy()
    if image.mode != "P" or image.size != (24, 8):
        raise SystemExit(f"{path.name}: expected an indexed 24x8 PNG")

    pixels = list(image.getdata())
    if any(not isinstance(value, int) or not 0 <= value <= 15 for value in pixels):
        raise SystemExit(f"{path.name}: pixel indices must stay within 0..15 for SNES 4bpp")

    out = bytearray()
    for tile_x in range(3):
        for planes in ((0, 1), (2, 3)):
            for row in range(8):
                for plane in planes:
                    value = 0
                    for column in range(8):
                        pixel = pixels[row * 24 + tile_x * 8 + column]
                        value |= ((pixel >> plane) & 1) << (7 - column)
                    out.append(value)
    return bytes(out)


def _guard(rom: bytes, offset: int, expected: bytes, label: str) -> None:
    actual = rom[offset:offset + len(expected)]
    if actual != expected:
        raise SystemExit(
            f"Unexpected clean-USA bytes for {label} at 0x{offset:06X}: "
            f"expected {expected.hex(' ')}, got {actual.hex(' ')}"
        )


def build(us_rom_path: Path, output_path: Path, *, hexagram_png: Path, patched_rom: Path | None = None) -> None:
    original = bytearray(us_rom_path.read_bytes())
    validate_base_rom(original)
    _guard(original, WARP_TILE_1_ROM, STOCK_WARP_TILE_1, "warp hexagram tile 1")
    _guard(original, WARP_TILE_23_ROM, STOCK_WARP_TILE_23, "warp hexagram tiles 2-3")

    replacement = encode_4bpp_tiles(hexagram_png)
    if replacement != JAPANESE_WARP_TILES:
        raise AssertionError("hexagram PNG does not re-encode to the verified Japanese tiles")

    rom = bytearray(original)
    rom[WARP_TILE_1_ROM:WARP_TILE_1_ROM + WARP_TILE_1_SIZE] = replacement[:WARP_TILE_1_SIZE]
    rom[WARP_TILE_23_ROM:WARP_TILE_23_ROM + WARP_TILE_23_SIZE] = replacement[WARP_TILE_1_SIZE:]
    update_checksum(rom)

    patch = make_ips(original, rom)
    if apply_ips(bytearray(original), patch) != rom:
        raise AssertionError("IPS self-application failed")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(patch)
    if patched_rom:
        patched_rom.parent.mkdir(parents=True, exist_ok=True)
        patched_rom.write_bytes(rom)
        print(f"ROM: {patched_rom}")
    print(f"IPS: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Japanese warp-hexagram restoration patch.")
    parser.add_argument("rom", type=Path, help="clean unheadered Secret of Mana (USA) ROM")
    parser.add_argument("-o", "--output", type=Path, default=ROOT / "build" / "patch.ips", help="output IPS path")
    parser.add_argument("--patched-rom", type=Path, help="optional patched ROM output")
    parser.add_argument("--hexagram-png", type=Path, default=ROOT / "assets" / "uncensored_hexagram.png", help="canonical 24x8 indexed hexagram PNG")
    args = parser.parse_args()
    build(args.rom, args.output, hexagram_png=args.hexagram_png, patched_rom=args.patched_rom)


if __name__ == "__main__":
    main()
