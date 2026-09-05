"""Canonical extraction for stock interface/help text blocks.

The stock game references this family through one 24-bit pointer table beginning
at C0:33B5.  The clean USA table contains nine valid HiROM text pointers: five
into C0 followed by four into C7.  The following three bytes are ordinary data,
not another valid HiROM pointer, which gives the family a structural end.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from shared.rom import BASE_SHA256, validate_base_rom
from shared.stock_text import decode_text_bytes
from shared.text_ids import rom_text_id

FORMAT_VERSION = 3
INTERFACE_POINTER_TABLE = 0x0033B5
POINTER_SIZE = 3
EXPECTED_POINTER_COUNT = 9

GAME_SELECT_WELCOME_GROUP = "game_select.welcome"
GAME_FILE_SAVE_HELP_GROUP = "game_file.save_help"
WINDOW_SETTINGS_HELP_GROUP = "window_settings.help"
NAME_HELP_GROUP = "name_entry.help"
ACTION_SETTINGS_HELP_GROUP = "action_settings.help"
WEAPON_SKILL_HELP_GROUP = "weapon_skill.help"
MAGIC_SKILL_HELP_GROUP = "magic_skill.help"
CONTROLLER_EDIT_HELP_GROUP = "controller_edit.help"
STATUS_LABELS_GROUP = "status.labels"


@dataclass(frozen=True)
class BlockSpec:
    group: str
    category: str
    row_count: int
    strip_leading_margin: bool = False


BLOCK_SPECS = (
    BlockSpec(
        GAME_SELECT_WELCOME_GROUP,
        "game_select_help",
        4,
    ),
    BlockSpec(
        GAME_FILE_SAVE_HELP_GROUP,
        "game_file_help",
        2,
    ),
    BlockSpec(
        WINDOW_SETTINGS_HELP_GROUP,
        "window_settings_help",
        3,
    ),
    BlockSpec(
        NAME_HELP_GROUP,
        "name_entry_help",
        3,
        strip_leading_margin=True,
    ),
    BlockSpec(
        ACTION_SETTINGS_HELP_GROUP,
        "action_settings_help",
        3,
    ),
    BlockSpec(
        WEAPON_SKILL_HELP_GROUP,
        "weapon_skill_help",
        3,
    ),
    BlockSpec(
        MAGIC_SKILL_HELP_GROUP,
        "magic_skill_help",
        3,
    ),
    BlockSpec(
        CONTROLLER_EDIT_HELP_GROUP,
        "controller_edit_help",
        4,
    ),
    BlockSpec(
        STATUS_LABELS_GROUP,
        "status_labels",
        2,
    ),
)


def _hirom_pointer_to_offset(pointer: int) -> int:
    bank = (pointer >> 16) & 0xFF
    address = pointer & 0xFFFF
    if not 0xC0 <= bank <= 0xFF:
        raise ValueError(f"Unsupported HiROM pointer ${pointer:06X}")
    return ((bank - 0xC0) << 16) | address


def _looks_like_text_pointer(rom: bytes, pointer: int) -> bool:
    bank = (pointer >> 16) & 0xFF
    if not 0xC0 <= bank <= 0xFF:
        return False
    start = _hirom_pointer_to_offset(pointer)
    if not 0 <= start < len(rom):
        return False
    try:
        end = rom.index(0x00, start)
        decode_text_bytes(rom, bytes(rom[start:end]))
    except (ValueError, IndexError):
        return False
    return True


def _read_interface_pointers(rom: bytes) -> tuple[int, ...]:
    pointers: list[int] = []
    offset = INTERFACE_POINTER_TABLE
    while offset + POINTER_SIZE <= len(rom):
        pointer = int.from_bytes(rom[offset:offset + POINTER_SIZE], "little")
        if not _looks_like_text_pointer(rom, pointer):
            break
        pointers.append(pointer)
        offset += POINTER_SIZE

    if len(pointers) != EXPECTED_POINTER_COUNT or len(pointers) != len(BLOCK_SPECS):
        raise ValueError(
            "Unexpected stock interface pointer-table layout: "
            f"expected {EXPECTED_POINTER_COUNT} text pointers, found {len(pointers)}"
        )
    return tuple(pointers)


def _extract_block(rom: bytes, pointer: int, spec: BlockSpec) -> dict:
    start = _hirom_pointer_to_offset(pointer)
    try:
        end = rom.index(0x00, start)
    except ValueError as exc:
        raise ValueError(f"{spec.group}: unterminated stock text block") from exc

    raw_rows = bytes(rom[start:end]).split(b"\x7f")
    rows = [row for row in raw_rows if row]
    if len(rows) != spec.row_count:
        raise ValueError(
            f"{spec.group}: expected {spec.row_count} visible rows, found {len(rows)}"
        )

    entries: list[dict[str, str]] = []
    cursor = start
    raw = bytes(rom[start:end])
    for row_index, encoded in enumerate(rows, 1):
        row_start = raw.find(encoded, cursor - start)
        if row_start < 0:
            raise ValueError(f"{spec.group} row {row_index}: could not recover row position")
        visible_start = start + row_start
        visible = encoded
        if spec.strip_leading_margin:
            if not visible or visible[0] != 0x80:
                raise ValueError(f"{spec.group} row {row_index}: expected stock leading $80 margin space")
            visible_start += 1
            visible = visible[1:]
        entries.append({
            "id": rom_text_id(visible_start),
            "source": decode_text_bytes(rom, visible),
        })
        cursor = start + row_start + len(encoded)

    return {"group": spec.group, "category": spec.category, "entries": entries}


def extract_document(rom: bytes) -> dict:
    validate_base_rom(rom)
    pointers = _read_interface_pointers(rom)
    groups = [
        _extract_block(rom, pointer, spec)
        for pointer, spec in zip(pointers, BLOCK_SPECS, strict=True)
    ]
    return {
        "format_version": FORMAT_VERSION,
        "description": (
            "Stock help/status source rows referenced by the C0:33B5 24-bit interface pointer table. "
            "ROM pointers, terminators and layout framing are derived from the clean USA ROM."
        ),
        "source_rom_sha256": BASE_SHA256,
        "groups": groups,
    }


def load_document(path: Path) -> dict:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("format_version") != FORMAT_VERSION:
        raise ValueError(
            f"Unsupported interface-text document format (expected format_version {FORMAT_VERSION})"
        )
    if document.get("source_rom_sha256") != BASE_SHA256:
        raise ValueError("Interface-text document targets a different base ROM")
    groups = document.get("groups")
    if not isinstance(groups, list):
        raise ValueError("Interface-text document has no groups list")
    group_names = [group.get("group") for group in groups]
    if len(group_names) != len(set(group_names)):
        raise ValueError("Interface-text document contains duplicate group IDs")
    return document


def group_entries(document: dict, group_name: str) -> list[dict]:
    matches = [group for group in document["groups"] if group.get("group") == group_name]
    if len(matches) != 1:
        raise ValueError(f"Interface-text group {group_name!r} is missing or duplicated")
    entries = matches[0].get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"Interface-text group {group_name!r} has no entries")
    ids = [entry.get("id") for entry in entries]
    if len(ids) != len(set(ids)):
        raise ValueError(f"Interface-text group {group_name!r} contains duplicate IDs")
    return entries


def verify_against_rom(rom: bytes, document: dict) -> tuple[int, int]:
    canonical = extract_document(rom)
    if document != canonical:
        raise ValueError("interface_text.json differs from a fresh clean-ROM extraction")
    groups = canonical["groups"]
    return len(groups), sum(len(group["entries"]) for group in groups)
