"""Extract the stock C0 battle/status message string pool.

Battle text is a contiguous pool at C0:5E6B-C0:6380.  An 88-entry 16-bit
pointer table at C0:5DBB references most records; another 21 records are
addressed directly by battle code.  The JSON keeps the 109 physical records in
ROM order.  Rare embedded control bytes are rendered as ``{XX}`` placeholders.
"""
from __future__ import annotations

import json
from pathlib import Path

from shared.rom import BASE_SHA256, validate_base_rom
from shared.text_ids import rom_text_id
from shared.stock_text import decode_text_unit

FORMAT_VERSION = 3
POINTER_TABLE = 0x005DBB
POINTER_COUNT = 88
BLOB_START = POINTER_TABLE + POINTER_COUNT * 2
BLOB_END = 0x006381
EXPECTED_RECORD_COUNT = 109


def _decode_record(rom: bytes, data: bytes) -> str:
    out: list[str] = []
    for code in data:
        piece = decode_text_unit(rom, code)
        if piece is None:
            out.append(f"{{{code:02X}}}")
        else:
            out.append(piece)
    return "".join(out)


def _physical_records(rom: bytes) -> list[tuple[int, bytes]]:
    records: list[tuple[int, bytes]] = []
    pos = BLOB_START
    while pos < BLOB_END:
        try:
            end = rom.index(0x00, pos, BLOB_END)
        except ValueError as exc:
            raise ValueError("Unterminated stock battle-text record") from exc
        records.append((pos, bytes(rom[pos:end])))
        pos = end + 1
    if pos != BLOB_END:
        raise ValueError("Battle-text blob did not end on a record boundary")
    if len(records) != EXPECTED_RECORD_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_RECORD_COUNT} battle-text records, found {len(records)}"
        )
    return records


def _validate_pointer_table(rom: bytes, records: list[tuple[int, bytes]]) -> None:
    starts = {offset for offset, _ in records}
    pointers = [
        int.from_bytes(rom[POINTER_TABLE + i * 2:POINTER_TABLE + i * 2 + 2], "little")
        for i in range(POINTER_COUNT)
    ]
    if len(set(pointers)) != POINTER_COUNT:
        raise ValueError("Battle-text pointer table unexpectedly contains aliases")
    if any(pointer not in starts for pointer in pointers):
        raise ValueError("Battle-text pointer table targets outside the physical string pool")
    if BLOB_START != POINTER_TABLE + POINTER_COUNT * 2:
        raise AssertionError("Battle-text table/blob boundary invariant failed")


def extract_document(rom: bytes) -> dict:
    validate_base_rom(rom)
    records = _physical_records(rom)
    _validate_pointer_table(rom, records)
    return {
        "format_version": FORMAT_VERSION,
        "description": (
            "Stock battle/status message pool. Records are kept in physical ROM order; "
            "embedded non-text bytes use {XX} placeholders."
        ),
        "source_rom_sha256": BASE_SHA256,
        "records": [
            {"id": rom_text_id(offset), "source": _decode_record(rom, data)}
            for offset, data in records
        ],
    }


def load_document(path: Path) -> dict:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("format_version") != FORMAT_VERSION:
        raise ValueError("Unsupported battle-text document format")
    if document.get("source_rom_sha256") != BASE_SHA256:
        raise ValueError("Battle-text document targets a different base ROM")
    records = document.get("records")
    if not isinstance(records, list) or len(records) != EXPECTED_RECORD_COUNT:
        raise ValueError(f"battle_text.json must contain {EXPECTED_RECORD_COUNT} records")
    return document


def verify_against_rom(rom: bytes, document: dict) -> tuple[int, int, int]:
    canonical = extract_document(rom)
    if document != canonical:
        raise ValueError("battle_text.json differs from a fresh clean-ROM extraction")
    records = _physical_records(rom)
    _validate_pointer_table(rom, records)
    return len(records), POINTER_COUNT * 2, BLOB_END - BLOB_START
