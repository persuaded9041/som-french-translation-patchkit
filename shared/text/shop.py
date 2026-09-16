"""Extract stock shop/forge response mini-event scripts from bank D9.

The shop/forge code in bank C0 loads nine 16-bit pointers into X and dispatches
them through the normal event engine after setting the live script bank to D9.
Each target is a tiny script of the form ``$7F $52 <stock text> $00``.  The
records are physically contiguous at D9:FE20-D9:FEF3.

The clean-USA asset remains source-only.  French payloads are owned by ``french_resources``; keeping the script wrapper
out of the source JSON makes
the text readable while the clean ROM remains authoritative for pointers,
opcodes and terminators.
"""
from __future__ import annotations

import json
from pathlib import Path

from shared.core.rom import BASE_SHA256, validate_base_rom
from shared.text.stock import decode_text_bytes, encode_text_with_stock_dte
from shared.text.ids import rom_text_id
from shared.charset import DIALOGUE_DTE_THRESHOLD

FORMAT_VERSION = 3
D9_BASE = 0x190000
SCRIPT_PREFIX = bytes((0x7F, 0x52))  # newline, TEXT_CLEAR
EXPECTED_RECORD_COUNT = 9
EXPECTED_BLOB_START = 0xFE20
EXPECTED_BLOB_END = 0xFEF4  # exclusive

# C0 sites containing ``LDX #$xxxx``.  These are the actual static references
# used by the shop/forge logic; reading the operands keeps extraction tied to
# the code mechanism rather than to an arbitrary list of D9 addresses.
REFERENCE_SITES = (
    (0x007AFA, 0xFE20),
    (0x007B0D, 0xFE2D),
    (0x007B12, 0xFE49),
    (0x007B7A, 0xFE65),
    (0x007B84, 0xFE96),
    (0x007B8B, 0xFEB5),
    (0x007B90, 0xFED1),
    (0x007C37, 0xFE7E),
    (0x007E43, 0xFEEC),
)

# Both static-display paths set $1D03 to D9, copy X to $1D01 and invoke the
# stock event engine ($C0:0092).  These exact sequences are cheap guardrails
# against accidentally classifying unrelated D9 data as text.
DISPATCH_SITES = (0x007EA6, 0x007FB9)
DISPATCH_BYTES = bytes.fromhex("A9 D9 8D 03 1D 8E 01 1D 22 92 00 C0")


def _referenced_pointers(rom: bytes) -> list[int]:
    refs: list[int] = []
    for site, expected_pointer in REFERENCE_SITES:
        if rom[site] != 0xA2:  # LDX #imm16 in the stock 16-bit-index context
            raise ValueError(f"Expected LDX immediate at C0:${site:04X}")
        pointer = int.from_bytes(rom[site + 1:site + 3], "little")
        if pointer != expected_pointer:
            raise ValueError(
                f"Unexpected shop/forge pointer at C0:${site:04X}: "
                f"${pointer:04X} (expected ${expected_pointer:04X})"
            )
        refs.append(pointer)

    pointers = refs
    if len(set(pointers)) != EXPECTED_RECORD_COUNT:
        raise ValueError("Shop/forge code references do not resolve to nine unique scripts")
    return refs


def _validate_dispatch(rom: bytes) -> None:
    for site in DISPATCH_SITES:
        actual = bytes(rom[site:site + len(DISPATCH_BYTES)])
        if actual != DISPATCH_BYTES:
            raise ValueError(
                f"Unexpected shop/forge event dispatch at C0:${site:04X}: "
                f"{actual.hex(' ').upper()}"
            )


def _read_script(rom: bytes, pointer: int) -> tuple[bytes, int]:
    start = D9_BASE + pointer
    if bytes(rom[start:start + len(SCRIPT_PREFIX)]) != SCRIPT_PREFIX:
        raise ValueError(f"D9:${pointer:04X} is not a stock shop/forge mini-event script")
    try:
        end = rom.index(0x00, start + len(SCRIPT_PREFIX), D9_BASE + 0x10000)
    except ValueError as exc:
        raise ValueError(f"Unterminated shop/forge mini-event at D9:${pointer:04X}") from exc
    payload = bytes(rom[start + len(SCRIPT_PREFIX):end])
    if not payload:
        raise ValueError(f"Empty shop/forge text payload at D9:${pointer:04X}")
    return payload, end + 1


def _physical_records(rom: bytes) -> list[tuple[int, bytes, int]]:
    refs = _referenced_pointers(rom)
    by_pointer = sorted(refs)
    records: list[tuple[int, bytes, int]] = []
    for pointer in by_pointer:
        payload, end = _read_script(rom, pointer)
        records.append((pointer, payload, end))

    if records[0][0] != EXPECTED_BLOB_START:
        raise ValueError(
            f"Unexpected first shop/forge script pointer ${records[0][0]:04X}"
        )
    for current, following in zip(records, records[1:]):
        current_end_pointer = current[2] - D9_BASE
        if current_end_pointer != following[0]:
            raise ValueError(
                "Shop/forge scripts are no longer physically contiguous: "
                f"${current[0]:04X} ends at ${current_end_pointer:04X}, "
                f"next is ${following[0]:04X}"
            )
    final_end = records[-1][2] - D9_BASE
    if final_end != EXPECTED_BLOB_END:
        raise ValueError(
            f"Unexpected shop/forge script-pool end ${final_end:04X} "
            f"(expected ${EXPECTED_BLOB_END:04X})"
        )
    return records


def extract_document(rom: bytes) -> dict:
    validate_base_rom(rom)
    _validate_dispatch(rom)
    records = _physical_records(rom)
    return {
        "format_version": FORMAT_VERSION,
        "description": (
            "Stock D9 shop/forge response text executed as tiny event scripts. "
            "Pointers, script commands and terminators are derived from the clean USA ROM."
        ),
        "source_rom_sha256": BASE_SHA256,
        "records": [
            {"id": rom_text_id(D9_BASE + pointer + len(SCRIPT_PREFIX)), "source": decode_text_bytes(rom, payload)}
            for pointer, payload, _ in records
        ],
    }


def load_document(path: Path) -> dict:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("format_version") != FORMAT_VERSION:
        raise ValueError("Unsupported shop-text document format")
    if document.get("source_rom_sha256") != BASE_SHA256:
        raise ValueError("Shop-text document targets a different base ROM")
    records = document.get("records")
    if not isinstance(records, list) or len(records) != EXPECTED_RECORD_COUNT:
        raise ValueError(f"shop_text.json must contain {EXPECTED_RECORD_COUNT} records")
    return document


def verify_against_rom(rom: bytes, document: dict) -> tuple[int, int, int]:
    canonical = extract_document(rom)
    if document != canonical:
        raise ValueError("shop_text.json differs from a fresh clean-ROM extraction")
    records = _physical_records(rom)
    # Reconstruct the complete physical mini-script blob byte-for-byte from the
    # clean structural wrapper plus the exact clean payload slices.
    reconstructed = b"".join(
        SCRIPT_PREFIX + payload + b"\x00" for _, payload, _ in records
    )
    source = bytes(
        rom[D9_BASE + EXPECTED_BLOB_START:D9_BASE + EXPECTED_BLOB_END]
    )
    if reconstructed != source:
        raise ValueError("Shop/forge mini-event blob round-trip mismatch")
    return len(records), len(REFERENCE_SITES), len(source)


def serialize_translated_pool(
    rom: bytes,
    document: dict,
    translations: dict[str, str],
    *,
    max_visible_chars: int = 28,
) -> tuple[bytes, dict[int, int], dict[str, dict[str, int]]]:
    """Rebuild the nine D9 mini-event scripts inside their stock allocation.

    The clean-ROM scripts remain the structural source: wrappers, record order and
    all bank-C0 reference sites are validated before any translated payload is
    serialized.  Text is compressed with runtime-safe stock DTE pairs using the
    event-dialogue ``$E8`` threshold installed by ``french_resources``.

    Returns ``(blob, reference_pointers, stats)`` where ``reference_pointers``
    maps each C0 ``LDX`` site to its rebuilt D9 script pointer.
    """
    verify_against_rom(rom, document)
    canonical = {record["id"]: record for record in document["records"]}
    unknown = sorted(set(translations) - set(canonical))
    if unknown:
        raise ValueError("Unknown shop/forge translation ID(s): " + ", ".join(unknown))

    physical = _physical_records(rom)
    new_pointer_by_old: dict[int, int] = {}
    stats: dict[str, dict[str, int]] = {}
    blob = bytearray()
    cursor = EXPECTED_BLOB_START

    for old_pointer, source_payload, _end in physical:
        text_id = rom_text_id(D9_BASE + old_pointer + len(SCRIPT_PREFIX))
        if text_id in translations:
            text = translations[text_id]
            if "\n" in text or "\r" in text:
                raise ValueError(f"{text_id}: shop/forge response must stay on one line")
            visible = len(text)
            if visible > max_visible_chars:
                raise ValueError(
                    f"{text_id}: {visible} visible characters exceed stock line capacity "
                    f"{max_visible_chars}"
                )
            payload = encode_text_with_stock_dte(
                rom, text, upper_dte_threshold=DIALOGUE_DTE_THRESHOLD
            )
        else:
            # Sparse translation support remains available even though the promoted
            # French component currently translates all nine responses.
            text = canonical[text_id]["source"]
            visible = len(text)
            payload = source_payload

        new_pointer_by_old[old_pointer] = cursor
        record = SCRIPT_PREFIX + payload + b"\x00"
        blob.extend(record)
        stats[text_id] = {
            "visible_chars": visible,
            "encoded_bytes": len(payload),
            "script_bytes": len(record),
            "script_pointer": cursor,
        }
        cursor += len(record)

    capacity = EXPECTED_BLOB_END - EXPECTED_BLOB_START
    if len(blob) > capacity:
        raise ValueError(
            f"Translated shop/forge pool is {len(blob)} bytes, exceeding stock allocation {capacity}"
        )

    reference_pointers = {
        site: new_pointer_by_old[old_pointer]
        for site, old_pointer in REFERENCE_SITES
    }
    return bytes(blob), reference_pointers, stats
