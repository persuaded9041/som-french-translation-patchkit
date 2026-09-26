#!/usr/bin/env python3
"""Build French localized graphics for Secret of Mana (USA).

Current scope: French-localized stock graphics, including controller buttons,
direction markers, menu indicators, and the two inn-sign variants. The button
shape is sourced from an indexed PNG; the other resources are exact, guarded
French-ROM replacements because their native storage formats differ.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent.parent
ASSET_DIR = ROOT / "assets"
sys.path.insert(0, str(PROJECT_ROOT))

from shared.core.ips import apply_ips, make_ips  # noqa: E402
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

# (label, file offset, clean-USA bytes, French replacement bytes).  The two
# alternate inn-sign ranges are deliberately separate: 0x1D1540-0x1D157F is
# unrelated tile data and must remain untouched.
GRAPHIC_REPLACEMENTS = (
    (
        "direction-west graphic",
        0x07FB20,
        bytes.fromhex("AD427BC67BD67BC63BD67DAA3B446600C600C600D600D600FE00EE0044000000"),
        bytes.fromhex("7844F986E742E742E74223C6867C7C007C00C600C600C600C600C6007C000000"),
    ),
    (
        "HP indicator variant 1",
        0x128A00,
        bytes.fromhex(
            "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFEFFFEFDFEFFF1FFFBEEF1FFD6"
            "E1FFAEC1DF7D83FFFB07FF778FFFAFDFFFF9FDFFF1FBFFE8FDFFE8FDECD3ECDD"
            "AADDFD1ABDFF3DFFFF9FFFFF23FFFB05A3BD42AD2DD22DA35DA3AF53AFFFAFFF"
        ),
        bytes.fromhex(
            "FFFFFFFF8585E7007AF5004A860079BE0445BF1E5EFFBCBCFFF1F1FFCEC0FF86"
            "A8DF8EA0BF1D41BF1B437F3787FF2F0FFFF9FBFFF3F7FFE6EEFFEDEDEFD3C3DF"
            "AF8FBF5F1FFF3F3FFF9F9FFF7F7FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"
        ),
    ),
    (
        "HP indicator variant 2",
        0x128A60,
        bytes.fromhex(
            "FFB4FFFF00B4F700BD8500FFB400FFB500FFFFB4FFFEFDFEFF71FF7B2EF1BF16"
            "E1BF0EE15F3DC3FF7B87FF778FFFAFDFFFF9FDFFF3FBFFEEFFFFEDFFEFD3EFDF"
            "AFDFFF1FBFFF3FFFFF9FFFFF7FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"
        ),
        bytes.fromhex(
            "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFEFFFEFEFFFCFDFFF1F1FFEEE0FFD6"
            "C8FFAE90FF5D21FFBB43FF7707FFAF8FFFF9FBFFF0F0FEE0E7FFE0E4E8D0C7DB"
            "A084BB5115FF3B3BFF9F9FFF1D1D7F08AA5D08AA6B0195EB4155F7E3EBFFF7F7"
        ),
    ),
    (
        "MP indicator variant 1",
        0x129B40,
        bytes.fromhex(
            "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFEFFFEFCFFFFF1FFF3E2FDEBC2"
            "F5D786E98F0DF39F9B67FF778FFFAFDFFFF9FDFFF1FFFFE0F9FCE3F8EAC5FADA"
            "85FAFB14BBFF3BFFFF9FFFFF23FFBB45233DC22DAD52ADA35DA3AF53AFFFAFFF"
        ),
        bytes.fromhex(
            "FF8484E7007BF6004B85007ABD0042BD185AFF3C3CFFFDFDFF9191DD0E601D06"
            "E8590EA0530DA1D70B23EF1707DFAF8FFFF9FBFFF3F7FFE6EEFFEDEDFFD3C3FF"
            "AF8FFF5F1FFF3F3FFF9F9FFF7F7FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"
        ),
    ),
    (
        "MP indicator variant 2",
        0x129BA0,
        bytes.fromhex(
            "FF92FFFB0096C300BEAA00FFAA00FFBA00FFFFB8FFFEFCFFFF31FFB3027DDB02"
            "F5D706F92F0DF3DF1BE7FF778FFFAFDFFFF9FDFFF3FBF7E6FFFFEDFFEFC3FFDF"
            "8FFFFF1FBFFF3FFFFF9FFFFF7FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"
        ),
        bytes.fromhex(
            "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFEFFFEFEFFFCFDFFF1F1FDEEE0FDD6"
            "C8F9AE90F35D2167FB038F7707DFAF8FFFF9FBFFF0F0FEE0E7FFE0E4F8D0C7FB"
            "A084FB5115FF3B3BFF9F9FFF09097D00B66100BE5500AAD5002ADD80A2FFDDDD"
        ),
    ),
    (
        "level indicator",
        0x12C420,
        bytes.fromhex(
            "FFFFFFFF2065FF246DFF2465FF246DFF0026FF26FF3FFF3FFFFFFFFF014BFF01"
            "5BFF014BFF095BFF40C9FFC1FFF1E7E95F7F9FAFBFCFD6DFE6E9EFF0F5F1FFF2"
            "F8F7ECFDE6FFFFFFB7DF87FBE9E7F7D3CFAFDF87F7E3EFEFDFCFFFBFBFFFFFFF"
        ),
        bytes.fromhex(
            "FFC8DAFFC0CAFFC0D2FFC0DAFFC8DAFFDAFFFFFFFF3FFF3FFF07AFFF07AFFF07"
            "AFFF07AFFF09DBFFDBFFFFFFFFF1E7E95F7F9FAFBFCFD6DFE6E9EFF0F5F1FFF2"
            "F8F7ECFDE6FFFFFFB7DF87FBE9E7F7D3CFAFDF87F7E3EFEFDFCFFFBFBFFFFFFF"
        ),
    ),
    (
        "alternate inn-sign tiles 0-1",
        0x1D1500,
        bytes.fromhex(
            "2C00807F3FFFC7405FC07FC05DF65FF6FF00FF00FF00FF00FF00FF00FF00FF00"
            "FE0000FFFEFFF103F903FD03EDB7FDB7FF00FF00FF00FF00FF00FF00FF00FF00"
        ),
        bytes.fromhex(
            "2C00807F3FFFC7405FC06FD857FC57FCFF00FF00FF00FF00FF00FF00FF00FF00"
            "FE0000FFFEFFF103F903FD03DD33DD33FF00FF00FF00FF00FF00FF00FF00FF00"
        ),
    ),
    (
        "alternate inn-sign tiles 2-3",
        0x1D1580,
        bytes.fromhex(
            "5DF75DF65DF65FC05FC046C0C07F3FFFFF00FF00FF00FF00FF00FF00FF00FF00"
            "EDBFEDB7EDB7FD03F90311030FF1FFFEFF00FF00FF00FF00FF00FF00FF00FF00"
        ),
        bytes.fromhex(
            "5DFF55FF55FF5FC05FC046C0C07F3FFFFF00FF00FF00FF00FF00FF00FF00FF00"
            "5DFF55FFDFFFFD03F90311030FF1FFFEFF00FF00FF00FF00FF00FF00FF00FF00"
        ),
    ),
    (
        "Potos inn sign",
        0x1F5460,
        bytes.fromhex(
            "E01088271A483F9F7FBF7FFF7FDB59FF000F3F7F54FFBFE0FFFFFF81DB80D980"
            "070811E44812FCF9FEFDFEFFFE5B4AFF00F0FCFE3AFFFD07FFFFFF095B014B01"
            "7FFF5ADA5BFF7FFF3FBF3F9F1A488867D880FF80DB80FF82FFFFBFF054FF3F3F"
            "FEFF52537AFFFEFFFCFDFCF9581211E64301FF015B01FF11FFFFFD0F2AFFFCFC"
        ),
        bytes.fromhex(
            "E01088271A483F9F7FBF7FFF7FCF37FF000F3F7F54FFBFE0FFFFFFCFCF87B781"
            "070811E44812FCF9FEFDFEFFFEDFDEFF00F0FCFE3AFFFD07FFFFFFDDDF8FDF07"
            "7FFF35B534FF7FFF3FBF3F9F1A4888678580FF80B480FFB4FFFFBFF054FF3F3F"
            "FEFF565744FFFEFFFCFDFCF9581211E64703FF014501FF45FFFFFD0F2AFFFCFC"
        ),
    ),
)


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


def _indexed_pixels(path: Path, size: tuple[int, int], max_index: int) -> list[int]:
    with Image.open(path) as source:
        image = source.copy()

    if image.size != size:
        raise SystemExit(f"{path.name}: expected {size[0]}x{size[1]} PNG, got {image.width}x{image.height}")
    if image.mode != "P":
        raise SystemExit(f"{path.name}: expected indexed PNG mode 'P', got {image.mode!r}")
    pixels = list(image.getdata())
    if any(not isinstance(value, int) or not 0 <= value <= max_index for value in pixels):
        raise SystemExit(f"{path.name}: pixel indices must stay within 0..{max_index}")
    return pixels


def encode_4bpp(path: Path, size: tuple[int, int]) -> bytes:
    """Encode indexed 8x8-multiple PNG tiles in SNES 4bpp TL/TR/BL/BR order."""
    width, height = size
    pixels = _indexed_pixels(path, size, 15)
    out = bytearray()
    for tile_y in range(height // 8):
        for tile_x in range(width // 8):
            for planes in ((0, 1), (2, 3)):
                for row in range(8):
                    for plane in planes:
                        value = 0
                        base_y = tile_y * 8 + row
                        for column in range(8):
                            pixel = pixels[base_y * width + tile_x * 8 + column]
                            value |= ((pixel >> plane) & 1) << (7 - column)
                        out.append(value)
    return bytes(out)


def encode_compressed_icon(path: Path) -> bytes:
    """Encode one 16x16 menu icon in the stock 3bpp compressed layout.

    Index 7 is the format's transparent source value.  Keeping it distinct in
    the PNG preserves the exact original compressed bytes instead of merely a
    visually equivalent icon.
    """
    pixels = _indexed_pixels(path, (16, 16), 7)
    out = bytearray()
    for tile_y in range(2):
        for tile_x in range(2):
            for row in range(8):
                base_y = tile_y * 8 + row
                for plane in range(3):
                    value = 0
                    for column in range(8):
                        pixel = pixels[base_y * 16 + tile_x * 8 + column]
                        value |= ((pixel >> plane) & 1) << (7 - column)
                    out.append(value)
    return bytes(out)


def load_graphic_assets() -> dict[str, bytes]:
    """Return exact French graphic payloads generated from canonical PNGs."""
    alternate = encode_4bpp(ASSET_DIR / "inn_sign_1_fr.png", (16, 16))
    return {
        "direction-west graphic": encode_4bpp(ASSET_DIR / "direction_west_fr.png", (8, 8)),
        "HP indicator variant 1": encode_compressed_icon(ASSET_DIR / "hp_indicator_1_fr.png"),
        "HP indicator variant 2": encode_compressed_icon(ASSET_DIR / "hp_indicator_2_fr.png"),
        "MP indicator variant 1": encode_compressed_icon(ASSET_DIR / "mp_indicator_1_fr.png"),
        "MP indicator variant 2": encode_compressed_icon(ASSET_DIR / "mp_indicator_2_fr.png"),
        "level indicator": encode_compressed_icon(ASSET_DIR / "level_indicator_fr.png"),
        "alternate inn-sign tiles 0-1": alternate[:0x40],
        "alternate inn-sign tiles 2-3": alternate[0x40:],
        "Potos inn sign": encode_4bpp(ASSET_DIR / "inn_sign_2_fr.png", (16, 16)),
    }


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
    generated_graphics = load_graphic_assets()
    for label, offset, usa_bytes, french_bytes in GRAPHIC_REPLACEMENTS:
        if len(usa_bytes) != len(french_bytes):
            raise AssertionError(f"internal size mismatch for {label}")
        _guard(original, offset, usa_bytes, label)
        generated = generated_graphics.get(label)
        if generated is None:
            raise AssertionError(f"missing PNG encoder for {label}")
        if generated != french_bytes:
            raise AssertionError(f"{label} PNG does not re-encode to the verified French bytes")

    button_gfx = encode_2bpp_16x16(button_png)
    if len(button_gfx) != BUTTON_GFX_SIZE:
        raise AssertionError("internal controller-button graphics size mismatch")
    palettes = load_palettes(palettes_json)

    rom = bytearray(original)
    rom[BUTTON_GFX_ROM:BUTTON_GFX_ROM + BUTTON_GFX_SIZE] = button_gfx
    rom[BUTTON_PALETTES_ROM:BUTTON_PALETTES_ROM + BUTTON_PALETTES_SIZE] = palettes
    rom[USA_PALETTE_OVERRIDE_ROM:USA_PALETTE_OVERRIDE_ROM + 3] = SKIP_PALETTE_OVERRIDE
    for label, offset, _, french_bytes in GRAPHIC_REPLACEMENTS:
        rom[offset:offset + len(french_bytes)] = generated_graphics[label]
    update_checksum(rom)

    patch = make_ips(original, rom)
    if apply_ips(original, patch) != rom:
        raise AssertionError("IPS self-application failed")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(patch)
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
