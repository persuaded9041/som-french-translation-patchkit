"""Deterministic stock event/dialogue codec used by component 08.

The codec is deliberately structural. The canonical source JSON stores only semantic
command data and readable clean-ROM text; all ROM addresses and exact unchanged text
encoding are recovered from the clean USA ROM at build/check time. An unchanged
extraction therefore still reinserts byte-for-byte, including stock DTE choices,
without carrying redundant raw byte dumps in the asset.
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

from shared.stock_text import decode_text_unit, encode_text
from shared.rom import BASE_SHA256, validate_base_rom
from shared.text_ids import rom_text_id

C9_BASE = 0x090000
CA_BASE = 0x0A0000
C9_POINTER_TABLE = C9_BASE
CA_POINTER_TABLE = CA_BASE

EVENT_COUNT = 0x800
C9_EVENT_COUNT = 0x400
CA_EVENT_COUNT = 0x400
CA_FIRST_NON_EVENT_POINTER_INDEX = 0x400
DEFAULT_EXCLUDED_EVENT_IDS = frozenset({0x0400})
C9_LAST_EVENT_ID = 0x03FF
C9_LAST_EVENT_BYTES = bytes.fromhex("14 FD 00")
# Total encoded lengths, including the opcode. Lengths used by stock scripts are
# established from the event/text command handlers. Commands not established
# here still abort instead of being guessed.
COMMAND_LENGTHS: dict[int, int] = {
    0x00: 1,
    0x01: 1,
    0x02: 1,
    0x03: 1,
    0x04: 1,
    0x05: 1,
    0x06: 1,
    0x07: 1,
    0x08: 1,
    0x09: 1,
    0x0A: 1,
    0x0B: 1,
    0x0C: 1,
    0x0D: 1,
    0x0E: 1,
    0x0F: 1,
    0x1C: 2,
    0x1D: 2,
    0x1E: 2,
    0x1F: 2,
    0x2E: 2,
    0x2F: 2,
    0x30: 3,
    0x31: 3,
    0x32: 3,
    0x33: 3,
    0x34: 3,
    0x35: 1,
    0x36: 3,
    0x37: 3,
    0x38: 2,
    0x39: 4,
    0x3A: 4,
    0x40: 5,
    0x42: 3,
    0x49: 4,
    0x4A: 4,
    0x4B: 4,
    0x4C: 4,
    0x4D: 4,
    0x4E: 4,
    0x4F: 1,
    0x50: 1,
    0x51: 1,
    0x52: 1,
    0x53: 1,
    0x54: 2,
    0x55: 2,
    0x56: 2,
    0x57: 2,
    0x58: 1,
    0x59: 2,
    0x5A: 2,
    0x5B: 1,
    0x5C: 2,
    0x5D: 1,
    0x5E: 1,
    0x5F: 1,
}
for opcode in range(0x10, 0x1C):
    COMMAND_LENGTHS[opcode] = 2
for opcode in range(0x20, 0x2D):
    COMMAND_LENGTHS[opcode] = 2

COMMAND_NAMES = {
    0x00: "END",
    0x01: "OP_01",
    0x02: "RETURN",
    0x03: "BRING_PARTY",
    0x06: "GET_READY",
    0x07: "OP_07",
    0x08: "COMPLETE_ACTIONS",
    0x09: "OP_09",
    0x0A: "OP_0A",
    0x28: "WAIT",
    0x40: "PLAY_SOUND",
    0x50: "TEXT_OPEN",
    0x51: "TEXT_CLOSE",
    0x52: "TEXT_CLEAR",
    0x53: "TEXT_NOP",
    0x54: "ENEMY_NAME",
    0x55: "WEAPON_NAME",
    0x56: "MAGIC_NAME",
    0x57: "PLAYER_NAME",
    0x58: "CHOICE_BEGIN",
    0x59: "TEXT_X",
    0x5A: "CHOICE_OPTION",
    0x5B: "CHOICE_END",
    0x5C: "TEXT_LIST_VALUE",
    0x5D: "MONEY_OPEN",
    0x5E: "MONEY_CLOSE",
    0x5F: "MONEY_PRINT",
}
COMMAND_OPCODES = {name: opcode for opcode, name in COMMAND_NAMES.items()}


def _event_table_entry(event_id: int) -> tuple[int, int]:
    if not 0 <= event_id < EVENT_COUNT:
        raise ValueError(f"Event ID out of stock script range: ${event_id:04X}")
    if event_id < C9_EVENT_COUNT:
        return C9_BASE, C9_POINTER_TABLE + event_id * 2
    return CA_BASE, CA_POINTER_TABLE + (event_id - C9_EVENT_COUNT) * 2


def event_location(rom: bytes, event_id: int) -> tuple[int, int, int]:
    """Return ``(file_start, byte_length, 16-bit bank pointer)``.

    Normal events use the next pointer as their exact physical span. Event
    $07FF can do this too because the CA table continues with non-event text
    pointers. Event $03FF has no C9 sentinel, so its clean-ROM three-byte
    terminal script is validated explicitly.
    """
    bank_base, table_entry = _event_table_entry(event_id)
    pointer = struct.unpack_from("<H", rom, table_entry)[0]
    file_start = bank_base + pointer

    if event_id == C9_LAST_EVENT_ID:
        actual = bytes(rom[file_start:file_start + len(C9_LAST_EVENT_BYTES)])
        if actual != C9_LAST_EVENT_BYTES:
            raise ValueError(
                "Unexpected clean-USA event $03FF terminal bytes: "
                f"{actual.hex(' ').upper()}"
            )
        return file_start, len(C9_LAST_EVENT_BYTES), pointer

    if event_id < C9_LAST_EVENT_ID:
        next_pointer = struct.unpack_from("<H", rom, table_entry + 2)[0]
    else:
        # For $0400-$07FF this is the next CA table entry. At $07FF the
        # following entry is the first non-event text pointer and still gives
        # the exact end of the event span.
        next_pointer = struct.unpack_from("<H", rom, table_entry + 2)[0]

    if next_pointer <= pointer:
        raise ValueError(
            f"Event ${event_id:04X} has a non-forward/aliased next pointer "
            f"(${pointer:04X} -> ${next_pointer:04X})"
        )
    return file_start, next_pointer - pointer, pointer


def read_event(rom: bytes, event_id: int) -> tuple[bytes, int, int]:
    start, size, pointer = event_location(rom, event_id)
    return bytes(rom[start:start + size]), start, pointer


def _command_length(data: bytes, pos: int) -> int:
    opcode = data[pos]
    if opcode == 0x2D:
        if pos + 1 >= len(data):
            raise ValueError("Truncated $2D effect command")
        return 4 if data[pos + 1] in (0x05, 0x06) else 2
    try:
        return COMMAND_LENGTHS[opcode]
    except KeyError as exc:
        raise ValueError(f"Unsupported event opcode ${opcode:02X}") from exc


def decode_ending_text(data: bytes) -> str:
    chars: list[str] = []
    for value in data:
        if value == 0x7F:
            chars.append("\n")
        elif value == 0x20 or 0x41 <= value <= 0x5A:
            chars.append(chr(value))
        else:
            raise ValueError(f"Unsupported ending-text ASCII byte ${value:02X}")
    return "".join(chars)


def encode_ending_text(text: str) -> bytes:
    out = bytearray()
    for char in text:
        if char == "\n":
            out.append(0x7F)
        elif char == " " or "A" <= char <= "Z":
            out.append(ord(char))
        else:
            raise ValueError(
                "Ending-text mode currently supports only A-Z, spaces and newlines; "
                f"got {char!r}"
            )
    return bytes(out)


def _command_opcode(name: str) -> int:
    opcode = COMMAND_OPCODES.get(name)
    if opcode is not None:
        return opcode
    if name.startswith("OP_") and len(name) == 5:
        try:
            return int(name[3:], 16)
        except ValueError:
            pass
    raise ValueError(f"Unknown command name: {name!r}")


def _command_bytes(token: dict) -> bytes:
    opcode = _command_opcode(token["name"])
    args = bytes.fromhex(token.get("args", ""))
    raw = bytes([opcode]) + args
    expected = _command_length(raw, 0)
    if len(raw) != expected:
        raise ValueError(
            f"Command {token['name']} has {len(args)} argument byte(s); "
            f"expected {expected - 1}"
        )
    return raw


def _glyph_byte(token: dict) -> bytes:
    try:
        code = int(token["code"], 16)
    except (KeyError, ValueError) as exc:
        raise ValueError(f"Invalid glyph token: {token!r}") from exc
    if not 0x80 <= code <= 0xD2:
        raise ValueError(f"Glyph code out of direct-glyph range: ${code:02X}")
    return bytes([code])


def parse_event(rom: bytes, event_id: int, *, include_source_bytes: bool = False) -> dict:
    data, file_start, pointer = read_event(rom, event_id)
    tokens: list[dict] = []
    pos = 0

    while pos < len(data):
        opcode = data[pos]

        if opcode == 0x7D:
            start = pos
            pos += 1
            payload_start = pos
            while pos < len(data) and data[pos] != 0x7E:
                pos += 1
            if pos >= len(data):
                raise ValueError(
                    f"Event ${event_id:04X} at +${start:04X}: unterminated ending-text block"
                )
            payload = data[payload_start:pos]
            pos += 1  # consume $7E
            decoded = decode_ending_text(payload)
            token = {
                "type": "ending_text",
                "id": rom_text_id(file_start + payload_start),
                "source": decoded,
            }
            if include_source_bytes:
                token["_source_bytes"] = data[start:pos]
            tokens.append(token)
            continue

        decoded = decode_text_unit(rom, opcode)
        if decoded is not None:
            start = pos
            parts: list[str] = []
            while pos < len(data):
                code = data[pos]
                if code == 0x7D:
                    break
                piece = decode_text_unit(rom, code)
                if piece is None:
                    break
                parts.append(piece)
                pos += 1
            source_text = "".join(parts)
            token = {
                "type": "text",
                "id": rom_text_id(file_start + start),
                "source": source_text,
            }
            if include_source_bytes:
                token["_source_bytes"] = data[start:pos]
            tokens.append(token)
            continue

        # $CE-$D2 are valid stock direct-glyph slots but their visual meanings
        # are not established here. Preserve them as raw glyph tokens rather
        # than inventing a textual mapping.
        if 0x80 <= opcode <= 0xD2:
            tokens.append({"type": "glyph", "code": f"{opcode:02X}"})
            pos += 1
            continue

        try:
            length = _command_length(data, pos)
        except ValueError as exc:
            raise ValueError(
                f"Event ${event_id:04X} at +${pos:04X} (file ${file_start + pos:06X}): {exc}"
            ) from exc
        if pos + length > len(data):
            raise ValueError(f"Event ${event_id:04X}: truncated command at +${pos:04X}")
        raw = data[pos:pos + length]
        token = {
            "type": "command",
            "name": COMMAND_NAMES.get(opcode, f"OP_{opcode:02X}"),
        }
        if len(raw) > 1:
            token["args"] = raw[1:].hex(" ").upper()
        tokens.append(token)
        pos += length

    return {
        "event_id": f"{event_id:04X}",
        "tokens": tokens,
    }


def event_has_text(event: dict) -> bool:
    return any(
        token["type"] in ("text", "ending_text") and token.get("source", "")
        for token in event["tokens"]
    )


def serialize_event(rom: bytes, event: dict, *, translations: dict[str, str] | None = None, source: bool) -> bytes:
    """Serialize one event against its canonical clean-ROM source and optional translations.

    Exact bytes for unchanged text are intentionally recovered from a fresh
    parse of the clean USA ROM rather than duplicated in the JSON. Commands and
    raw glyphs are reconstructed from their compact structured representation.
    """
    event_id = int(event["event_id"], 16)
    canonical = parse_event(rom, event_id, include_source_bytes=True)
    if len(event["tokens"]) != len(canonical["tokens"]):
        raise ValueError(
            f"Event ${event_id:04X}: token count changed; only translation values may differ from canonical source tokens"
        )

    translations = translations or {}
    out = bytearray()
    for index, (token, original_token) in enumerate(zip(event["tokens"], canonical["tokens"])):
        kind = token["type"]
        if kind != original_token["type"]:
            raise ValueError(
                f"Event ${event_id:04X}: token type changed at token {index}"
            )
        if kind == "text":
            text = translations.get(token["id"])
            if source or text is None or text == original_token["source"]:
                out += original_token["_source_bytes"]
            else:
                out += encode_text(text)
        elif kind == "ending_text":
            text = translations.get(token["id"])
            if source or text is None or text == original_token["source"]:
                out += original_token["_source_bytes"]
            else:
                out.append(0x7D)
                out += encode_ending_text(text)
                out.append(0x7E)
        elif kind == "command":
            out += _command_bytes(token)
        elif kind == "glyph":
            out += _glyph_byte(token)
        else:
            raise ValueError(f"Unknown token type: {kind!r}")
    return bytes(out)


def discover_dialogue_event_ids(
    rom: bytes,
    *,
    excluded_event_ids: frozenset[int] = DEFAULT_EXCLUDED_EVENT_IDS,
) -> tuple[int, ...]:
    """Scan all 2048 stock event scripts and return those containing text."""
    validate_base_rom(rom)
    selected: list[int] = []
    for event_id in range(EVENT_COUNT):
        event = parse_event(rom, event_id)
        if event_id not in excluded_event_ids and event_has_text(event):
            selected.append(event_id)
    return tuple(selected)


def extract_document(rom: bytes, event_ids) -> dict:
    validate_base_rom(rom)
    ordered_ids = tuple(sorted(set(event_ids)))
    return {
        "format_version": 4,
        "description": (
            "Canonical stock event text. Translation text lives separately under translations/; "
            "the clean USA ROM supplies canonical spans and unchanged text encoding at build time."
        ),
        "source_rom_sha256": BASE_SHA256,
        "events": [parse_event(rom, event_id) for event_id in ordered_ids],
    }


def extract_default_document(rom: bytes) -> dict:
    event_ids = discover_dialogue_event_ids(rom)
    document = extract_document(rom, event_ids)
    document["selection"] = {
        "scanned_event_range": "0000-07FF",
        "excluded_owned_events": ["0400"],
        "rule": "stock event scripts containing at least one text or ending_text token",
    }
    # Keep selection metadata before events in the committed JSON for humans.
    return {
        "format_version": document["format_version"],
        "description": document["description"],
        "source_rom_sha256": document["source_rom_sha256"],
        "selection": document["selection"],
        "events": document["events"],
    }


def load_document(path: Path) -> dict:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("format_version") != 4:
        raise ValueError("Unsupported dialogue document format (expected format_version 4)")
    if document.get("source_rom_sha256") != BASE_SHA256:
        raise ValueError("Dialogue document targets a different base ROM")

    event_ids = [int(event["event_id"], 16) for event in document.get("events", [])]
    if event_ids != sorted(event_ids):
        raise ValueError("Dialogue events must be sorted by event_id")
    if len(event_ids) != len(set(event_ids)):
        raise ValueError("Dialogue document contains duplicate event IDs")
    return document


def count_edited_text_tokens(document: dict, translations: dict[str, str] | None = None) -> int:
    translations = translations or {}
    return sum(
        1
        for event in document["events"]
        for token in event["tokens"]
        if token["type"] in ("text", "ending_text")
        and token["id"] in translations
        and translations[token["id"]] != token["source"]
    )


def _canonical_source_token(token: dict) -> dict:
    """Return only immutable fields that must match a fresh clean-ROM parse."""
    kind = token["type"]
    if kind in ("text", "ending_text"):
        return {"type": kind, "id": token["id"], "source": token["source"]}
    if kind == "command":
        result = {"type": kind, "name": token["name"]}
        if token.get("args"):
            result["args"] = token["args"]
        return result
    if kind == "glyph":
        return {"type": kind, "code": token["code"]}
    raise ValueError(f"Unknown token type: {kind!r}")


def verify_source_roundtrip(rom: bytes, document: dict) -> tuple[int, int]:
    """Verify canonical token structure and byte-identical source serialization.

    Each event is freshly parsed from the clean ROM and its immutable token
    fields are compared with the document. Derived addresses, span sizes and
    hashes are deliberately not stored in the JSON. This catches accidental
    edits to readable `source`, commands, glyphs or token boundaries while only
    allowing externally supplied translation values to differ.

    Returns ``(event_count, source_byte_count)``.
    """
    validate_base_rom(rom)
    total_bytes = 0
    for event in document["events"]:
        event_id = int(event["event_id"], 16)
        source_data, _, _ = read_event(rom, event_id)
        canonical = parse_event(rom, event_id)
        actual_tokens = [_canonical_source_token(token) for token in event["tokens"]]
        canonical_tokens = [_canonical_source_token(token) for token in canonical["tokens"]]
        if actual_tokens != canonical_tokens:
            mismatch = next(
                (
                    index
                    for index, (actual, expected) in enumerate(zip(actual_tokens, canonical_tokens))
                    if actual != expected
                ),
                min(len(actual_tokens), len(canonical_tokens)),
            )
            raise ValueError(
                f"Event ${event_id:04X}: canonical source token mismatch at token {mismatch}; "
                "only translation values may differ from canonical source tokens from a fresh extraction"
            )

        rebuilt = serialize_event(rom, event, translations=None, source=True)
        if rebuilt != source_data:
            mismatch = next(
                (i for i, (left, right) in enumerate(zip(rebuilt, source_data)) if left != right),
                min(len(rebuilt), len(source_data)),
            )
            raise ValueError(
                f"Event ${event_id:04X}: source round-trip mismatch at +${mismatch:04X}; "
                f"rebuilt {len(rebuilt)} bytes vs source {len(source_data)} bytes"
            )
        total_bytes += len(source_data)
    return len(document["events"]), total_bytes


def verify_unedited_reinsertion(rom: bytes, document: dict) -> tuple[int, int]:
    """Verify the translation-aware serialization path with no translations applied."""
    total_bytes = 0
    for event in document["events"]:
        event_id = int(event["event_id"], 16)
        source_data, _, _ = read_event(rom, event_id)
        rebuilt = serialize_event(rom, event, translations=None, source=False)
        if rebuilt != source_data:
            mismatch = next(
                (i for i, (left, right) in enumerate(zip(rebuilt, source_data)) if left != right),
                min(len(rebuilt), len(source_data)),
            )
            raise ValueError(
                f"Event ${event_id:04X}: translation-free reinsertion mismatch at +${mismatch:04X}"
            )
        total_bytes += len(source_data)
    return len(document["events"]), total_bytes
