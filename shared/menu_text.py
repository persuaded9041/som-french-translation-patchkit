"""Extract native C7 menu/status strings outside the CA resource table.

Packed menu resources are represented as logical translatable fragments rather
than whole layout blobs.  Each entry ID is the canonical SNES address of the
first source byte. Layout padding, dynamic placeholders and button glyphs stay
in the clean ROM and are not duplicated as translation entries.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from shared.rom import BASE_SHA256, validate_base_rom
from shared.stock_text import decode_text_unit, decode_text_bytes
from shared.text_ids import rom_text_id

FORMAT_VERSION = 3
MENU_BLOB_START = 0x077313
MENU_BLOB_END = 0x0774EA
MENU_DESCRIPTOR_TABLE = 0x07780A
MENU_DESCRIPTOR_COUNT = 11
EMPTY_LABEL = 0x077805
STATUS_START = 0x077A8E
STATUS_COUNT = 16
TEMPLATE_START = 0x077B24
TEMPLATE_COUNT = 8
WEAPON_START = 0x077B6D
WEAPON_COUNT = 8
MISC_START = 0x077BA5
MISC_COUNT = 3
WEAPON_POINTER_TABLE = 0x077BB7

# Two code paths print the single-cell stock level prefix directly.
GAME_FILE_LEVEL_LABEL_OFFSETS = (0x0753C9, 0x075AF1)

MENU_RESOURCE_STARTS = (
    0x077313, 0x077340, 0x07734F, 0x0773BC, 0x0773DF,
    0x077400, 0x07745B, 0x077484, 0x0774AD,
)


@dataclass(frozen=True)
class Segment:
    group: str
    offset: int
    length: int


MENU_SEGMENTS = (
    # GAME SELECT
    Segment("menu.game_select", 0x077314, 6),
    Segment("menu.game_select", 0x07731C, 12),
    Segment("menu.game_select", 0x07732A, 8),
    Segment("menu.game_select", 0x077334, 10),
    # GAME FILE
    Segment("menu.game_file", 0x077341, 6),
    Segment("menu.game_file", 0x077349, 4),
    Segment("menu.game_file", 0x077350, 11),
    Segment("menu.game_file", 0x077374, 5),
    Segment("menu.game_file", 0x077394, 2),
    Segment("menu.game_file", 0x077398, 7),
    Segment("menu.game_file", 0x0773AA, 10),
    Segment("menu.game_file", EMPTY_LABEL, 5),
    Segment("menu.game_file", GAME_FILE_LEVEL_LABEL_OFFSETS[0], 1),
    Segment("menu.game_file", GAME_FILE_LEVEL_LABEL_OFFSETS[1], 1),
    # Window/action/controller menus
    Segment("menu.window_edit", 0x0773C9, 6),
    Segment("menu.window_edit", 0x0773D1, 12),
    Segment("menu.action_settings", 0x0773E0, 6),
    Segment("menu.action_settings", 0x0773E7, 9),
    Segment("menu.action_settings", 0x0773F1, 8),
    Segment("menu.action_settings", 0x0773F9, 5),
    Segment("menu.controller_edit", 0x077409, 6),
    Segment("menu.controller_edit", 0x077411, 16),
    Segment("menu.controller_edit", 0x077423, 10),
    Segment("menu.controller_edit", 0x077431, 12),
    Segment("menu.controller_edit", 0x07743F, 6),
    Segment("menu.controller_edit", 0x07744D, 4),
    Segment("menu.weapon_skill", 0x07745E, 12),
    Segment("menu.weapon_skill", 0x077478, 11),
    Segment("menu.magic_skill", 0x077486, 12),
    Segment("menu.magic_skill", 0x07749F, 12),
    Segment("menu.name_entry", 0x0774B2, 51),
)


def _read_null_records(rom: bytes, start: int, count: int) -> list[tuple[int, bytes]]:
    records: list[tuple[int, bytes]] = []
    pos = start
    for _ in range(count):
        try:
            end = rom.index(0x00, pos)
        except ValueError as exc:
            raise ValueError(f"Unterminated C7 menu text at ROM ${pos:06X}") from exc
        records.append((pos, bytes(rom[pos:end])))
        pos = end + 1
    return records


def _decode_with_controls(rom: bytes, data: bytes) -> str:
    out: list[str] = []
    i = 0
    while i < len(data):
        code = data[i]
        piece = decode_text_unit(rom, code)
        if piece is not None:
            out.append(piece)
            i += 1
            continue
        if code == 0x5C and i + 1 < len(data):
            out.append(f"{{5C{data[i + 1]:02X}}}")
            i += 2
            continue
        out.append(f"{{{code:02X}}}")
        i += 1
    return "".join(out)


def _menu_resources(rom: bytes) -> list[tuple[int, bytes]]:
    records: list[tuple[int, bytes]] = []
    pos = MENU_BLOB_START
    while pos < MENU_BLOB_END:
        end = rom.index(0x00, pos, MENU_BLOB_END)
        records.append((pos, bytes(rom[pos:end])))
        pos = end + 1
    if pos != MENU_BLOB_END or tuple(offset for offset, _ in records) != MENU_RESOURCE_STARTS:
        raise ValueError("Unexpected native C7 menu-resource layout")
    return records


def _validate_descriptor_table(rom: bytes, resources: list[tuple[int, bytes]]) -> None:
    text_offsets = {offset & 0xFFFF for offset, _ in resources}
    first_words = [
        int.from_bytes(rom[MENU_DESCRIPTOR_TABLE + index * 6:MENU_DESCRIPTOR_TABLE + index * 6 + 2], "little")
        for index in range(MENU_DESCRIPTOR_COUNT)
    ]
    valid = text_offsets | {0x74EA}
    if any(value not in valid for value in first_words):
        raise ValueError("Menu descriptor table contains an unexpected text pointer")
    if text_offsets - set(first_words):
        raise ValueError("A native menu text resource is not referenced by the descriptor table")


def _validate_weapon_table(rom: bytes, weapons: list[tuple[int, bytes]]) -> None:
    expected = [offset & 0xFFFF for offset, _ in weapons]
    actual = [
        int.from_bytes(rom[WEAPON_POINTER_TABLE + i * 2:WEAPON_POINTER_TABLE + i * 2 + 2], "little")
        for i in range(WEAPON_COUNT)
    ]
    if actual != expected:
        raise ValueError("Unexpected C7 weapon-type pointer table")


def _segment_entry(rom: bytes, spec: Segment) -> dict:
    data = bytes(rom[spec.offset:spec.offset + spec.length])
    return {"id": rom_text_id(spec.offset), "source": decode_text_bytes(rom, data).rstrip(" ")}


def _record_entries(rom: bytes, records: list[tuple[int, bytes]], *, controls: bool = False) -> list[dict]:
    entries = []
    for offset, data in records:
        source = _decode_with_controls(rom, data) if controls else decode_text_bytes(rom, data)
        entries.append({"id": rom_text_id(offset), "source": source})
    return entries


def extract_document(rom: bytes) -> dict:
    validate_base_rom(rom)
    resources = _menu_resources(rom)
    _validate_descriptor_table(rom, resources)

    statuses = _read_null_records(rom, STATUS_START, STATUS_COUNT)
    templates = _read_null_records(rom, TEMPLATE_START, TEMPLATE_COUNT)
    weapons = _read_null_records(rom, WEAPON_START, WEAPON_COUNT)
    misc = _read_null_records(rom, MISC_START, MISC_COUNT)
    _validate_weapon_table(rom, weapons)

    groups: list[dict] = []
    for group_name in dict.fromkeys(spec.group for spec in MENU_SEGMENTS):
        groups.append({
            "group": group_name,
            "entries": [_segment_entry(rom, spec) for spec in MENU_SEGMENTS if spec.group == group_name],
        })
    groups.extend([
        {"group": "status.conditions", "entries": _record_entries(rom, statuses)},
        {"group": "status.templates", "entries": _record_entries(rom, templates, controls=True)},
        {"group": "status.weapon_types", "entries": _record_entries(rom, weapons)},
        {"group": "status.misc", "entries": _record_entries(rom, misc)},
    ])

    return {
        "format_version": FORMAT_VERSION,
        "description": (
            "Native C7 menu/status source text outside the CA text-resource table. "
            "IDs are source SNES addresses; packed layout bytes and dynamic placeholders are omitted."
        ),
        "source_rom_sha256": BASE_SHA256,
        "groups": groups,
    }


def load_document(path: Path) -> dict:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("format_version") != FORMAT_VERSION:
        raise ValueError(f"Unsupported menu-text document format (expected {FORMAT_VERSION})")
    if document.get("source_rom_sha256") != BASE_SHA256:
        raise ValueError("Menu-text document targets a different base ROM")
    groups = document.get("groups")
    if not isinstance(groups, list):
        raise ValueError("menu_text.json has no groups list")
    return document


def group_entries(document: dict, group_name: str) -> list[dict]:
    matches = [group for group in document["groups"] if group.get("group") == group_name]
    if len(matches) != 1:
        raise ValueError(f"Menu-text group {group_name!r} is missing or duplicated")
    return matches[0]["entries"]


def verify_against_rom(rom: bytes, document: dict) -> tuple[int, int]:
    canonical = extract_document(rom)
    if document != canonical:
        raise ValueError("menu_text.json differs from a fresh clean-ROM extraction")
    count = sum(len(group["entries"]) for group in canonical["groups"])
    return len(canonical["groups"]), count
