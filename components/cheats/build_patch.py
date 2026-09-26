#!/usr/bin/env python3
"""Build the standalone test-cheats IPS patch."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from shared.core.asm import MiniAssembler  # noqa: E402
from shared.core.ips import apply_ips, make_ips  # noqa: E402
from shared.core.rom import update_checksum, validate_base_rom  # noqa: E402


# These are the two stock final-damage additions. Both paths continue with the
# untouched STA $E1F1,X immediately after the six displaced bytes.
DAMAGE_HOOKS = {
    0x0051AC: bytes.fromhex("A5 89 18 7D F1 E1"),
    0x0051DB: bytes.fromhex("A5 89 18 7D F1 E1"),
    # C8's magic-damage calculation has its own final addition.
    0x08E9F0: bytes.fromhex("85 89 18 7D F1 E1"),
}

# C1:B710 converts each party controller/AI direction into the signed
# movement vector. Stock magnitude 2 becomes 4; the high bit remains the
# negative-direction marker. This changes walking speed without setting the
# dash/action state or touching the direction input.
WALK_SPEED_EDITS = {
    0x00B719: (bytes.fromhex("A2 02"), bytes.fromhex("A2 04")),
    0x00B71F: (bytes.fromhex("A2 82"), bytes.fromhex("A2 84")),
    0x00B727: (bytes.fromhex("A0 02"), bytes.fromhex("A0 04")),
    0x00B72D: (bytes.fromhex("A0 82"), bytes.fromhex("A0 84")),
}

# C7:4E80 is stock-$FF space left free by the aggregate's C7 allocations.
HELPER_SNES = 0xC74E80
HELPER_FILE = 0x074E80
HELPER_RESERVED_END = 0x074E9F
PLAYER_STRUCTURE_END = 0x0600


def build_helper() -> bytes:
    """Return the common final-damage override, preserving caller flags."""
    a = MiniAssembler(HELPER_SNES)
    a.emit(0x08)                    # PHP
    a.emit(0xC2, 0x30)              # REP #$30: 16-bit A/X for the range test
    a.emit(0xE0, PLAYER_STRUCTURE_END & 0xFF, PLAYER_STRUCTURE_END >> 8)
    a.rel8(0x90, "player")         # BCC: player structures are before enemies
    a.emit(0xA9, 0xE7, 0x03)        # LDA #$03E7 (999)
    a.rel8(0x80, "done")
    a.label("player")
    a.emit(0xA9, 0x01, 0x00)        # LDA #$0001
    a.label("done")
    a.emit(0x28)                    # PLP
    a.emit(0x6B)                    # RTL
    return a.resolve()


def build_patch(base_rom: bytes) -> bytes:
    validate_base_rom(base_rom)

    helper = build_helper()
    if HELPER_FILE + len(helper) - 1 > HELPER_RESERVED_END:
        raise SystemExit("Combat-cheat helper exceeded its reserved C7:4E80 range")
    if base_rom[HELPER_FILE:HELPER_FILE + len(helper)] != bytes([0xFF]) * len(helper):
        raise SystemExit("Combat-cheat helper destination C7:4E80 is not stock $FF free space")
    records: dict[int, bytes] = {HELPER_FILE: helper}
    hook = bytes.fromhex("22 80 4E C7 EA EA")
    for offset, stock in DAMAGE_HOOKS.items():
        if base_rom[offset:offset + len(stock)] != stock:
            raise SystemExit(f"Stock final-damage hook changed at file offset 0x{offset:06X}")
        records[offset] = hook
    for offset, (stock, replacement) in WALK_SPEED_EDITS.items():
        if base_rom[offset:offset + len(stock)] != stock:
            raise SystemExit(f"Stock walking-speed literal changed at file offset 0x{offset:06X}")
        records[offset] = replacement

    patched = bytearray(base_rom)
    for offset, data in records.items():
        patched[offset:offset + len(data)] = data
    update_checksum(patched)
    patch = make_ips(base_rom, bytes(patched))

    if bytes(apply_ips(bytearray(base_rom), patch)) != bytes(patched):
        raise SystemExit("Combat-cheat IPS self-application mismatch")
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
