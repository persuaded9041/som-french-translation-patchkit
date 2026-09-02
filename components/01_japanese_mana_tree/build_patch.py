#!/usr/bin/env python3
"""
Build the Japanese Mana Tree restoration patch for Secret of Mana (USA).

This patch is intentionally separate from any opening-translation patch.

It expands the US ROM to 3 MiB, relocates the original Japanese Mana Tree
resource to $EF:C000, installs the resource-loader helper at
$EF:F800, and redirects one existing JML instruction to that helper.
"""

from pathlib import Path
import hashlib
import sys
import argparse

EXPECTED_TREE_SHA1 = "538458875a43c3562aa27fc34c89d87d09402c54"

OUTPUT_ROM_SIZE = 0x300000

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from shared.rom import validate_base_rom, update_checksum  # noqa: E402

TREE_DEST_ROM = 0x2FC000
TREE_SIZE = 0x3600

ROUTINE_ROM = 0x2FF800
ROUTINE = bytes.fromhex(
    "08c23048afac967ec9a9d2f00668285c0baf7eda5a0b8be220a97e48aba9ef8dad968dc596c220a900c08daa968dc196e220a90d8d53a08d8abea9408df9bea9808d86be8dc7bea9f48d2398a9f78d1398a93f8d0cd3a9f88d5fd3a9088d94d3c220a97bf88d9bade220a9ef8d9dadc230ab2b7afa68285c0baf7e221400c1488baf2e657ec96060f003ab686bda5aa0a664a20665a9bf01547e7e7afaab686b"
)

HOOK_ROM = 0x14CF6
HOOK_ORIGINAL = bytes.fromhex("5c 0b af 7e")
HOOK_PATCHED = bytes.fromhex("5c 00 f8 ef")

ROM_SIZE_BYTE = 0xFFD7

# Filler layout around the relocated resource.
FF_START = 0x2FF5E3
FF_LENGTH = 29
ZERO_START = 0x2FF600
ZERO_LENGTH = 512
POST_ROUTINE_ZERO_START = 0x2FF8A0
POST_ROUTINE_ZERO_LENGTH = 1888


def sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()



def make_ips(original: bytes, modified: bytes) -> bytes:
    out = bytearray(b"PATCH")
    i = 0

    while i < len(modified):
        old = original[i] if i < len(original) else 0

        if old == modified[i]:
            i += 1
            continue

        start = i
        chunk = bytearray()

        while i < len(modified) and len(chunk) < 0xFFFF:
            old = original[i] if i < len(original) else 0

            if old == modified[i]:
                break

            chunk.append(modified[i])
            i += 1

        out.extend(start.to_bytes(3, "big"))
        out.extend(len(chunk).to_bytes(2, "big"))
        out.extend(chunk)

    out.extend(b"EOF")
    return bytes(out)


def build(us_rom_path: Path, tree_path: Path, output_path: Path, patched_rom: Path | None = None):
    original = bytearray(us_rom_path.read_bytes())
    tree = tree_path.read_bytes()

    validate_base_rom(original)

    if len(tree) != TREE_SIZE:
        raise SystemExit(
            f"mana_tree_jp.bin must be exactly {TREE_SIZE} bytes"
        )

    if sha1(tree) != EXPECTED_TREE_SHA1:
        raise SystemExit(
            "mana_tree_jp.bin SHA-1 does not match the expected resource"
        )

    if original[HOOK_ROM:HOOK_ROM+4] != HOOK_ORIGINAL:
        raise SystemExit(
            "Unexpected resource-loader hook bytes in the source ROM"
        )

    rom = bytearray(original)
    rom.extend(b"\x00" * (OUTPUT_ROM_SIZE - len(rom)))

    # Mark the expanded ROM size in the SNES header.
    rom[ROM_SIZE_BYTE] = 0x0C

    # Japanese Mana Tree resource.
    rom[TREE_DEST_ROM:TREE_DEST_ROM+TREE_SIZE] = tree

    # Preserve the resource layout expected by the helper.
    rom[FF_START:FF_START+FF_LENGTH] = b"\xFF" * FF_LENGTH
    rom[ZERO_START:ZERO_START+ZERO_LENGTH] = b"\x00" * ZERO_LENGTH

    # Resource-loader helper.
    rom[ROUTINE_ROM:ROUTINE_ROM+len(ROUTINE)] = ROUTINE

    rom[
        POST_ROUTINE_ZERO_START:
        POST_ROUTINE_ZERO_START+POST_ROUTINE_ZERO_LENGTH
    ] = b"\x00" * POST_ROUTINE_ZERO_LENGTH

    # Redirect the existing stock JML instruction.
    rom[HOOK_ROM:HOOK_ROM+4] = HOOK_PATCHED

    update_checksum(rom)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    patch = make_ips(original, rom)
    output_path.write_bytes(patch)
    if patched_rom:
        patched_rom.parent.mkdir(parents=True, exist_ok=True)
        patched_rom.write_bytes(rom)
        print(f"ROM: {patched_rom}")
    print(f"IPS: {output_path}")


def main():
    root = ROOT
    parser = argparse.ArgumentParser(description="Build the standalone Japanese Mana Tree restoration patch.")
    parser.add_argument("rom", type=Path, help="clean unheadered Secret of Mana (USA) ROM")
    parser.add_argument("-o", "--output", type=Path, default=root / "build" / "patch.ips", help="output IPS path")
    parser.add_argument("--patched-rom", type=Path, help="optional patched ROM output")
    parser.add_argument("--tree", type=Path, default=root / "assets" / "mana_tree_jp.bin", help="Japanese Mana Tree resource")
    args = parser.parse_args()
    build(args.rom, args.tree, args.output, args.patched_rom)


if __name__ == "__main__":
    main()
