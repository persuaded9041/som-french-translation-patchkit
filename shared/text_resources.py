"""Deterministic codec for the 513 non-event CA text resources."""
from __future__ import annotations

import json
import struct
from pathlib import Path

from shared.rom import BASE_SHA256, validate_base_rom
from shared.stock_text import decode_text_bytes, encode_text
from shared.text_ids import rom_text_id

CA_BASE = 0x0A0000
RESOURCE_POINTER_TABLE = CA_BASE + 0x0800  # CA table entry $0400
RESOURCE_COUNT = 0x201  # IDs $000-$200 inclusive
FIRST_RESOURCE_POINTER = 0x98E1

# These ranges are established from the stock lookup tables / ordered contents.
# End values are exclusive.
CATEGORY_RANGES = (
    (0x000, 0x02A, "magic_name"),
    (0x02A, 0x032, "mana_spirit_name"),
    (0x032, 0x07A, "weapon_name"),
    (0x07A, 0x08F, "helmet_name"),
    (0x08F, 0x0A4, "armor_name"),
    (0x0A4, 0x0B9, "accessory_name"),
    (0x0B9, 0x0C6, "item_name"),
    (0x0C6, 0x0CF, "menu_label"),
    (0x0CF, 0x14F, "enemy_name"),
    (0x14F, 0x197, "weapon_description"),
    (0x197, 0x1C1, "magic_description"),
    (0x1C1, 0x1E0, "location_name"),
    (0x1E0, 0x1FF, "unused"),
    (0x1FF, 0x201, "system_message"),
)


def category_for(resource_id: int) -> str:
    for start, end, name in CATEGORY_RANGES:
        if start <= resource_id < end:
            return name
    raise ValueError(f"Text resource ID out of range: ${resource_id:03X}")


def resource_pointer(rom: bytes, resource_id: int) -> int:
    if not 0 <= resource_id < RESOURCE_COUNT:
        raise ValueError(f"Text resource ID out of range: ${resource_id:03X}")
    return struct.unpack_from("<H", rom, RESOURCE_POINTER_TABLE + resource_id * 2)[0]


def read_resource(rom: bytes, resource_id: int) -> tuple[bytes, int]:
    """Return ``(payload_without_terminator, 16-bit_pointer)``."""
    pointer = resource_pointer(rom, resource_id)
    start = CA_BASE + pointer
    try:
        end = rom.index(0x00, start, CA_BASE + 0x10000)
    except ValueError as exc:
        raise ValueError(f"Text resource ${resource_id:03X} has no $00 terminator") from exc
    return bytes(rom[start:end]), pointer


def validate_stock_layout(rom: bytes) -> None:
    validate_base_rom(rom)
    first = resource_pointer(rom, 0)
    if first != FIRST_RESOURCE_POINTER:
        raise ValueError(
            f"Unexpected first CA text-resource pointer ${first:04X}; "
            f"expected ${FIRST_RESOURCE_POINTER:04X}"
        )

    # Every stock string immediately follows the previous terminator.  This
    # proves the full table/blob boundary instead of merely finding 513 strings.
    for resource_id in range(RESOURCE_COUNT - 1):
        payload, pointer = read_resource(rom, resource_id)
        next_pointer = resource_pointer(rom, resource_id + 1)
        expected = pointer + len(payload) + 1
        if next_pointer != expected:
            raise ValueError(
                f"Text resource ${resource_id:03X}: next pointer ${next_pointer:04X} "
                f"does not follow terminator at ${expected:04X}"
            )


def parse_resource(rom: bytes, resource_id: int) -> dict:
    payload, pointer = read_resource(rom, resource_id)
    return {
        "id": rom_text_id(CA_BASE + pointer),
        "resource_id": f"{resource_id:03X}",
        "category": category_for(resource_id),
        "source": decode_text_bytes(rom, payload),
    }


def extract_document(rom: bytes) -> dict:
    validate_stock_layout(rom)
    return {
        "format_version": 2,
        "description": (
            "Canonical non-event CA text resources. Translation text lives separately under "
            "translations/; pointers and exact source bytes are derived from the clean USA ROM."
        ),
        "source_rom_sha256": BASE_SHA256,
        "resources": [parse_resource(rom, resource_id) for resource_id in range(RESOURCE_COUNT)],
    }


def load_document(path: Path) -> dict:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("format_version") != 2:
        raise ValueError("Unsupported text-resource document format (expected format_version 2)")
    if document.get("source_rom_sha256") != BASE_SHA256:
        raise ValueError("Text-resource document targets a different base ROM")
    resources = document.get("resources", [])
    ids = [int(resource["resource_id"], 16) for resource in resources]
    if ids != list(range(RESOURCE_COUNT)):
        raise ValueError(
            f"Text-resource document must contain IDs $000-$200 in order ({RESOURCE_COUNT} entries)"
        )
    return document


def _verify_immutable_fields(rom: bytes, document: dict) -> None:
    for resource in document["resources"]:
        resource_id = int(resource["resource_id"], 16)
        canonical = parse_resource(rom, resource_id)
        for field in ("id", "category", "source"):
            if resource.get(field) != canonical[field]:
                raise ValueError(
                    f"Text resource ${resource_id:03X}: {field} differs from canonical extraction"
                )


def serialize_resource(rom: bytes, resource: dict, *, text: str | None = None, source: bool = False) -> bytes:
    resource_id = int(resource["resource_id"], 16)
    original_payload, _ = read_resource(rom, resource_id)
    canonical = parse_resource(rom, resource_id)
    for field in ("id", "category", "source"):
        if resource.get(field) != canonical[field]:
            raise ValueError(f"Text resource ${resource_id:03X}: {field} changed")
    if source or text is None or text == canonical["source"]:
        payload = original_payload
    else:
        payload = encode_text(text)
    return payload + b"\x00"


def verify_source_roundtrip(rom: bytes, document: dict) -> tuple[int, int]:
    validate_stock_layout(rom)
    _verify_immutable_fields(rom, document)
    total = 0
    for resource in document["resources"]:
        resource_id = int(resource["resource_id"], 16)
        payload, _ = read_resource(rom, resource_id)
        expected = payload + b"\x00"
        rebuilt = serialize_resource(rom, resource, source=True)
        if rebuilt != expected:
            raise ValueError(f"Text resource ${resource_id:03X}: source round-trip mismatch")
        total += len(expected)
    return RESOURCE_COUNT, total


def verify_unedited_reinsertion(rom: bytes, document: dict) -> tuple[int, int]:
    """Verify the translation-free serialization path."""
    total = 0
    for resource in document["resources"]:
        resource_id = int(resource["resource_id"], 16)
        payload, _ = read_resource(rom, resource_id)
        expected = payload + b"\x00"
        rebuilt = serialize_resource(rom, resource, text=None, source=False)
        if rebuilt != expected:
            raise ValueError(f"Text resource ${resource_id:03X}: no-translation reinsertion mismatch")
        total += len(expected)
    return RESOURCE_COUNT, total


def serialize_table_and_blob(
    rom: bytes, document: dict, *, translations: dict[str, str] | None = None, source: bool = False
) -> tuple[bytes, bytes]:
    """Serialize all 513 pointers and strings in deterministic resource-ID order."""
    validate_stock_layout(rom)
    _verify_immutable_fields(rom, document)
    translations = translations or {}

    pointer = FIRST_RESOURCE_POINTER
    table = bytearray()
    blob = bytearray()
    for resource in document["resources"]:
        table += struct.pack("<H", pointer)
        encoded = serialize_resource(
            rom, resource, text=translations.get(resource["id"]), source=source
        )
        blob += encoded
        pointer += len(encoded)
        if pointer > 0x10000:
            raise ValueError("Rebuilt text-resource blob crosses the CA bank")
    return bytes(table), bytes(blob)


def verify_pointer_table_and_blob(rom: bytes, document: dict) -> tuple[int, int]:
    """Rebuild the stock 513-entry table/blob and compare both byte-for-byte."""
    table, blob = serialize_table_and_blob(rom, document, source=True)
    source_table = rom[RESOURCE_POINTER_TABLE:RESOURCE_POINTER_TABLE + RESOURCE_COUNT * 2]
    if table != source_table:
        raise ValueError("CA text-resource pointer table round-trip mismatch")
    blob_start = CA_BASE + FIRST_RESOURCE_POINTER
    source_blob = rom[blob_start:blob_start + len(blob)]
    if blob != source_blob:
        raise ValueError("CA text-resource blob round-trip mismatch")
    return len(table), len(blob)
