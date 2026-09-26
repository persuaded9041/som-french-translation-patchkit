#!/usr/bin/env python3
"""Build the standalone full French fixed-font candidate."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from shared.charset import french_font_bytes  # noqa: E402
from shared.core.ips import apply_ips, make_ips  # noqa: E402
from shared.core.rom import update_checksum, validate_base_rom  # noqa: E402


FONT_FILE = 0x12DC00
FONT_SIZE = (0xE7 - 0x80 + 1) * 12


def build_patch(base_rom: bytes) -> bytes:
    validate_base_rom(base_rom)
    replacement = french_font_bytes()
    if len(replacement) != FONT_SIZE:
        raise SystemExit("French global font must contain exactly 1536 bytes")

    patched = bytearray(base_rom)
    patched[FONT_FILE:FONT_FILE + FONT_SIZE] = replacement
    update_checksum(patched)
    patch = make_ips(base_rom, bytes(patched))
    if bytes(apply_ips(bytearray(base_rom), patch)) != bytes(patched):
        raise SystemExit("French global font IPS self-application mismatch")
    return patch


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rom", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args()
    patch = build_patch(args.rom.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(patch)
    print(f"Wrote {args.output} ({len(patch)} bytes)")


if __name__ == "__main__":
    main()
