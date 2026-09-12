"""Common ROM helpers for the Secret of Mana French patchkit."""
from __future__ import annotations

import hashlib
import struct

BASE_SIZE = 0x200000
EXPANDED_SIZE = 0x300000
BASE_SHA256 = "4c15013131351e694e05f22e38bb1b3e4031dedac77ec75abecebe8520d82d5f"
CHECKSUM_COMPLEMENT_OFFSET = 0xFFDC
CHECKSUM_OFFSET = 0xFFDE
CHECKSUM_RANGE = range(CHECKSUM_COMPLEMENT_OFFSET, CHECKSUM_OFFSET + 2)
ROM_SIZE_OFFSET = 0xFFD7


def validate_base_rom(data: bytes) -> None:
    """Require the clean, unheadered Secret of Mana (USA) ROM."""
    digest = hashlib.sha256(data).hexdigest()
    if len(data) != BASE_SIZE or digest != BASE_SHA256:
        raise SystemExit(
            "Wrong base ROM. Expected clean unheadered Secret of Mana (USA) "
            f"({BASE_SIZE:#x} bytes, SHA-256 {BASE_SHA256})."
        )


def expand_rom(data: bytes | bytearray, size: int = EXPANDED_SIZE, fill: int = 0x00) -> bytearray:
    """Return a bytearray expanded to *size* without shrinking larger input."""
    rom = bytearray(data)
    if len(rom) < size:
        rom.extend(bytes((fill,)) * (size - len(rom)))
    return rom


def update_checksum(rom: bytearray) -> int:
    """Recompute the SNES checksum/complement in-place and return the checksum."""
    rom[CHECKSUM_COMPLEMENT_OFFSET:CHECKSUM_OFFSET + 2] = b"\xFF\xFF\x00\x00"
    checksum = sum(rom) & 0xFFFF
    rom[CHECKSUM_COMPLEMENT_OFFSET:CHECKSUM_OFFSET + 2] = struct.pack(
        "<HH", checksum ^ 0xFFFF, checksum
    )
    return checksum
