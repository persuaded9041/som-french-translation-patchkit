#!/usr/bin/env python3
"""Build French localized graphics for Secret of Mana (USA).

Current scope: the shared 16x16 controller-button icon and the four PAL/Japanese
button palettes (X/A/Y/B). The shape is sourced from an indexed PNG; palette
values are component-owned JSON data derived from the official French release.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from shared.core.ips import make_ips  # noqa: E402
from shared.core.rom import update_checksum, validate_base_rom  # noqa: E402

BUTTON_GFX_ROM = 0x12D8F0       # SNES $D2:D8F0
BUTTON_GFX_SIZE = 0x40           # 4 * 8x8 2bpp tiles = one 16x16 icon
BUTTON_PALETTES_ROM = 0x12DBCC  # SNES $D2:DBCC
BUTTON_PALETTES_SIZE = 0x18     # X/A/Y/B, 3 BGR15 colors each
USA_PALETTE_OVERRIDE_ROM = 0x002116  # SNES $C0:2116

STOCK_BUTTON_GFX = bytes.fromhex(
    "07 00 18 07 20 1F 40 3F 40 3F 40 3F 60 3F 60 3F "
    "FF 00 00 FF 00 FF 00 FF 00 FF 00 FF 00 FF 00 FF "
    "60 3F 70 3F 78 1F 7F 27 77 38 30 1F 18 07 07 00 "
    "00 FF 00 FF 00 FF FF FF FF 00 00 FF 00 FF FF 00"
)
STOCK_BUTTON_PALETTES = bytes.fromhex(
    "00 00 08 3C 0C 70 "  # X
    "00 00 12 00 1F 00 "  # A
    "00 00 A3 09 C3 0A "  # Y
    "00 00 99 01 9F 03"   # B
)
STOCK_PALETTE_OVERRIDE_CALL = bytes.fromhex("20 2F 21")  # JSR $212F
SKIP_PALETTE_OVERRIDE = bytes.fromhex("EA EA EA")


def encode_2bpp_16x16(path: Path) -> bytes:
    """Encode a 16x16 indexed PNG as TL/TR/BL/BR SNES 2bpp tiles."""
    with Image.open(path) as source:
        image = source.copy()

    if image.size != (16, 16):
        raise SystemExit(f"{path.name}: expected 16x16 PNG, got {image.width}x{image.height}")
    if image.mode != "P":
        raise SystemExit(f"{path.name}: expected indexed PNG mode 'P', got {image.mode!r}")

    pixels = list(image.getdata())
    if any(not isinstance(value, int) or not 0 <= value <= 3 for value in pixels):
        raise SystemExit(f"{path.name}: pixel indices must stay within 0..3 for SNES 2bpp")

    out = bytearray()
    for tile_y in range(2):
        for tile_x in range(2):
            for row in range(8):
                plane0 = 0
                plane1 = 0
                base_y = tile_y * 8 + row
                for column in range(8):
                    value = pixels[base_y * 16 + tile_x * 8 + column]
                    bit = 7 - column
                    plane0 |= (value & 1) << bit
                    plane1 |= ((value >> 1) & 1) << bit
                out.extend((plane0, plane1))
    return bytes(out)


def load_palettes(path: Path) -> bytes:
    data = json.loads(path.read_text(encoding="utf-8"))
    order = data.get("order")
    palettes = data.get("palettes")
    if order != ["X", "A", "Y", "B"] or not isinstance(palettes, dict):
        raise SystemExit(f"{path.name}: expected X/A/Y/B palette order")

    out = bytearray()
    for button in order:
        values = palettes.get(button)
        if not isinstance(values, list) or len(values) != 3:
            raise SystemExit(f"{path.name}: {button} must define exactly three visible colors")
        for raw in values:
            try:
                value = int(raw, 0) if isinstance(raw, str) else int(raw)
            except (TypeError, ValueError) as exc:
                raise SystemExit(f"{path.name}: invalid {button} BGR15 value {raw!r}") from exc
            if not 0 <= value <= 0x7FFF:
                raise SystemExit(f"{path.name}: {button} BGR15 value out of range: 0x{value:X}")
            out.extend(value.to_bytes(2, "little"))
    if len(out) != BUTTON_PALETTES_SIZE:
        raise AssertionError("internal palette-size mismatch")
    return bytes(out)


def _guard(rom: bytes, offset: int, expected: bytes, label: str) -> None:
    actual = rom[offset:offset + len(expected)]
    if actual != expected:
        raise SystemExit(
            f"Unexpected clean-USA bytes for {label} at 0x{offset:06X}: "
            f"expected {expected.hex(' ')}, got {actual.hex(' ')}"
        )


def build(
    us_rom_path: Path,
    output_path: Path,
    *,
    button_png: Path,
    palettes_json: Path,
    patched_rom: Path | None = None,
) -> None:
    original = bytearray(us_rom_path.read_bytes())
    validate_base_rom(original)

    _guard(original, BUTTON_GFX_ROM, STOCK_BUTTON_GFX, "controller-button graphics")
    _guard(original, BUTTON_PALETTES_ROM, STOCK_BUTTON_PALETTES, "controller-button palettes")
    _guard(original, USA_PALETTE_OVERRIDE_ROM, STOCK_PALETTE_OVERRIDE_CALL, "USA controller palette override")

    button_gfx = encode_2bpp_16x16(button_png)
    if len(button_gfx) != BUTTON_GFX_SIZE:
        raise AssertionError("internal controller-button graphics size mismatch")
    palettes = load_palettes(palettes_json)

    rom = bytearray(original)
    rom[BUTTON_GFX_ROM:BUTTON_GFX_ROM + BUTTON_GFX_SIZE] = button_gfx
    rom[BUTTON_PALETTES_ROM:BUTTON_PALETTES_ROM + BUTTON_PALETTES_SIZE] = palettes
    rom[USA_PALETTE_OVERRIDE_ROM:USA_PALETTE_OVERRIDE_ROM + 3] = SKIP_PALETTE_OVERRIDE
    update_checksum(rom)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(make_ips(original, rom))
    if patched_rom:
        patched_rom.parent.mkdir(parents=True, exist_ok=True)
        patched_rom.write_bytes(rom)
        print(f"ROM: {patched_rom}")
    print(f"IPS: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the standalone French localized-graphics patch.")
    parser.add_argument("rom", type=Path, help="clean unheadered Secret of Mana (USA) ROM")
    parser.add_argument("-o", "--output", type=Path, default=ROOT / "build" / "patch.ips", help="output IPS path")
    parser.add_argument("--patched-rom", type=Path, help="optional patched ROM output")
    parser.add_argument("--button-png", type=Path, default=ROOT / "assets" / "controller_button.png", help="16x16 indexed controller-button PNG")
    parser.add_argument("--palettes", type=Path, default=ROOT / "assets" / "controller_button_palettes.json", help="controller-button BGR15 palette JSON")
    args = parser.parse_args()
    build(
        args.rom,
        args.output,
        button_png=args.button_png,
        palettes_json=args.palettes,
        patched_rom=args.patched_rom,
    )


if __name__ == "__main__":
    main()
