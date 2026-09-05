"""Stable identifiers for text extracted from the clean HiROM image."""
from __future__ import annotations


def rom_offset_to_snes(offset: int) -> int:
    """Convert an unheadered HiROM file offset to its canonical C0-FF address."""
    if offset < 0:
        raise ValueError("ROM offset must be non-negative")
    bank = 0xC0 + (offset >> 16)
    if bank > 0xFF:
        raise ValueError(f"ROM offset ${offset:06X} is outside canonical HiROM C0-FF")
    return (bank << 16) | (offset & 0xFFFF)


def rom_text_id(offset: int) -> str:
    address = rom_offset_to_snes(offset)
    return f"{address >> 16:02X}:{address & 0xFFFF:04X}"


def decompressed_text_id(container_offset: int, decoded_offset: int) -> str:
    """ID for text that only has a stable position after a ROM block is decompressed."""
    return f"{rom_text_id(container_offset)}+{decoded_offset:04X}"
