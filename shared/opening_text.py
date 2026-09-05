"""Extract user-visible text from the compressed startup/title arrangement.

The title/opening uses its own fixed-width byte encoding, separate from the
normal event/DTE text codec.  This module only reads the stock compressed
arrangement at ROM $07B480; component 04 remains the canonical writer.
"""
from __future__ import annotations

import json
from pathlib import Path

from shared.rom import BASE_SHA256, validate_base_rom
from shared.text_ids import decompressed_text_id

FORMAT_VERSION = 3
TITLE_ARR_ROM = 0x07B480
COMPRESSION_TYPES = {0: 0x1F, 1: 0x0F, 2: 0x07, 3: 0x03, 4: 0x01, 5: 0x00}
US_YEAR = bytes.fromhex("7D 7E 7F")


def _decompress_block(data: bytes, offset: int) -> bytes:
    key = int.from_bytes(data[offset:offset + 2], "little")
    if key not in COMPRESSION_TYPES:
        raise ValueError(f"Unknown opening compression key {key}")
    mask = COMPRESSION_TYPES[key]
    out_size = (data[offset + 2] << 8) | data[offset + 3]
    i = offset + 4
    out = bytearray()
    while len(out) < out_size:
        token = data[i]
        i += 1
        if token < 0x80:
            count = token + 1
            out.extend(data[i:i + count])
            i += count
            continue
        b2 = data[i]
        i += 1
        distance = (((token - 0x80) & mask) * 0x100) + b2 + 1
        read_pos = len(out) - distance
        run_len = ((token - 0x80) // (mask + 1)) + 3
        for _ in range(run_len):
            if len(out) >= out_size:
                break
            if not 0 <= read_pos < len(out):
                raise ValueError("Invalid opening back-reference")
            out.append(out[read_pos])
            read_pos += 1
    return bytes(out[:out_size])


def _decode(data: bytes) -> str:
    out: list[str] = []
    mapping = {0x20: " ", 0x60: " ", 0x5E: "'", 0x5F: ":", 0x7B: ".", 0x7C: ","}
    for code in data:
        if 0x61 <= code <= 0x7A:
            out.append(chr(code))
        elif code in mapping:
            out.append(mapping[code])
        else:
            raise ValueError(f"Unsupported opening text tile ${code:02X}")
    return "".join(out)


def _find_prologue(arr: bytes) -> list[tuple[int, str]]:
    marker = b"darkness sweeps the"
    p = arr.find(marker)
    if p < 0:
        raise ValueError("US opening prologue signature not found")
    pos = p - 3
    start = pos
    lines: list[tuple[int, str]] = []
    for index in range(13):
        expected = b"\x01\x02" if index == 0 else b"\x01\x00"
        if arr[pos:pos + 2] != expected:
            raise ValueError(f"Unexpected opening prologue record {index + 1}")
        end = arr.find(b"\x00", pos + 3)
        if end < 0:
            raise ValueError("Unterminated opening prologue record")
        lines.append((pos + 3, _decode(arr[pos + 3:end])))
        pos = end + 1
    if pos - start != 332:
        raise ValueError(f"Unexpected stock prologue size: {pos - start} bytes")
    if arr[pos:pos + 8] != bytes.fromhex("01 00 01 00 01 00 01 00"):
        raise ValueError("Opening technical post-scroll blank records changed")
    return lines


def _encode_marker(text: str) -> bytes:
    mapping = {" ": 0x20, "'": 0x5E, ":": 0x5F, ".": 0x7B, ",": 0x7C}
    out = bytearray()
    for char in text:
        if "a" <= char <= "z":
            out.append(ord(char))
        elif char in mapping:
            out.append(mapping[char])
        else:
            raise ValueError(f"Unsupported opening marker character: {char!r}")
    return bytes(out)


def _indented_record(arr: bytes, source: str) -> tuple[int, str]:
    marker = _encode_marker(source)
    text_start = arr.find(marker)
    if text_start < 1:
        raise ValueError(f"Opening marker not found: {source!r}")
    end = arr.find(b"\x00", text_start)
    if end < 0:
        raise ValueError(f"Unterminated opening marker: {source!r}")
    # Byte immediately preceding the string is the horizontal indent.
    indent = arr[text_start - 1]
    if indent > 0x1F:
        raise ValueError(f"Unexpected opening indent ${indent:02X} before {source!r}")
    return text_start, _decode(arr[text_start:end])


def _copyright_source(arr: bytes) -> tuple[int, str]:
    year = arr.find(US_YEAR)
    if year < 2:
        raise ValueError("Stock opening copyright-year tiles not found")
    # Stock record: indent 06, copyright tile 50, 3-tile 1993, blank 60,
    # six dedicated SQUARE tiles 51-56, blank, then ordinary "co., ltd.".
    expected_prefix = bytes.fromhex("06 50 7D 7E 7F 60 51 52 53 54 55 56 60")
    start = year - 2
    if arr[start:start + len(expected_prefix)] != expected_prefix:
        raise ValueError("Unexpected stock copyright tile record")
    suffix_start = start + len(expected_prefix)
    end = arr.find(b"\x00", suffix_start)
    if end < 0 or _decode(arr[suffix_start:end]) != "co., ltd.":
        raise ValueError("Unexpected stock copyright suffix")
    return start + 1, "© 1993 SQUARE CO., LTD."


def extract_document(rom: bytes) -> dict:
    validate_base_rom(rom)
    arr = _decompress_block(rom, TITLE_ARR_ROM)
    prologue = _find_prologue(arr)

    legal = (
        _copyright_source(arr),
        _indented_record(arr, "all rights reserved."),
        _indented_record(arr, "licensed by nintendo"),
    )
    system = (_indented_record(arr, "multi player adapter error"),)
    credits = tuple(
        _indented_record(arr, marker)
        for marker in (
            "programmed by nasir",
            "composed by h.kikuta",
            "directed by k.ishii",
            "produced by h.tanaka",
        )
    )
    compatibility = tuple(
        _indented_record(arr, marker)
        for marker in (
            "this game pak is not designed",
            "for your super famicom",
            "or super nes.",
        )
    )

    groups = [
        {
            "group": "opening.prologue",
            "entries": [
                {
                    "id": decompressed_text_id(TITLE_ARR_ROM, offset),
                    "source": source,
                }
                for offset, source in prologue
            ],
        },
        {
            "group": "opening.legal",
            "entries": [
                {"id": decompressed_text_id(TITLE_ARR_ROM, offset), "source": value}
                for offset, value in legal
            ],
        },
        {
            "group": "opening.system",
            "entries": [
                {"id": decompressed_text_id(TITLE_ARR_ROM, offset), "source": value}
                for offset, value in system
            ],
        },
        {
            "group": "opening.credits",
            "entries": [
                {"id": decompressed_text_id(TITLE_ARR_ROM, offset), "source": value}
                for offset, value in credits
            ],
        },
        {
            "group": "opening.compatibility",
            "entries": [
                {"id": decompressed_text_id(TITLE_ARR_ROM, offset), "source": value}
                for offset, value in compatibility
            ],
        },
    ]
    return {
        "format_version": FORMAT_VERSION,
        "description": (
            "Stock user-visible strings extracted from the compressed startup/title arrangement. "
            "Renderer/layout bytes and graphic-only tiles are not duplicated in this source asset."
        ),
        "source_rom_sha256": BASE_SHA256,
        "groups": groups,
    }


def load_document(path: Path) -> dict:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("format_version") != FORMAT_VERSION:
        raise ValueError("Unsupported opening-text document format")
    if document.get("source_rom_sha256") != BASE_SHA256:
        raise ValueError("Opening-text document targets a different base ROM")
    groups = document.get("groups")
    if not isinstance(groups, list) or len(groups) != 5:
        raise ValueError("opening_text.json has an unexpected group layout")
    return document


def verify_against_rom(rom: bytes, document: dict) -> tuple[int, int]:
    canonical = extract_document(rom)
    if document != canonical:
        raise ValueError("opening_text.json differs from a fresh clean-ROM extraction")
    return len(canonical["groups"]), sum(len(group["entries"]) for group in canonical["groups"])
