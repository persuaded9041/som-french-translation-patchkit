#!/usr/bin/env python3
"""Build the generic extended Name Entry component from the clean USA ROM.

This component owns only the functional extension: 9-character names, a
three-row layout with uppercase/lowercase/symbol rows. Localized content and
additional rows belong to dependent components such as
``french_name_entry_extended``.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from src.patch_data import STATIC_EDITS

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from shared.ips import make_ips  # noqa: E402
from shared.interface_text import (  # noqa: E402
    NAME_HELP_GROUP,
    group_entries,
    extract_document as extract_interface_text,
)
from shared.rom import expand_rom, update_checksum, validate_base_rom  # noqa: E402

NAMED_CHARACTER_TOKENS = {
    "<QUOTE_OPEN>": 0xC3,
    "<QUOTE_CLOSE>": 0xC4,
    "<SPACE>": 0x80,
    "<GLYPH_CF>": 0xCF,
    "<GLYPH_D0>": 0xD0,
    "<GLYPH_D1>": 0xD1,
    "<GLYPH_D2>": 0xD2,
}

ASCII_TO_SOM = {" ": 0x80}
ASCII_TO_SOM.update({chr(ord("a") + i): 0x81 + i for i in range(26)})
ASCII_TO_SOM.update({chr(ord("A") + i): 0x9B + i for i in range(26)})
ASCII_TO_SOM.update({str(i): 0xB5 + i for i in range(10)})
ASCII_TO_SOM.update({
    ".": 0xBF, ",": 0xC0, "/": 0xC1, "'": 0xC2,
    "-": 0xC6, "%": 0xC7, "!": 0xC8, "&": 0xC9,
    "?": 0xCA, "(": 0xCB, ")": 0xCC, "#": 0xCD,
})

ROW_SIZE = 60
HELP_OFFSET = ROW_SIZE * 3
MAX_RESOURCE_SIZE = 0x200
GENERIC_HELP_MAX_BYTES = 153  # must not outgrow the French dependency overlay


def parse_sections(path: Path) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1].strip().lower()
            if current in sections:
                raise SystemExit(f"Duplicate section [{current}] in {path.name}")
            sections[current] = []
            continue
        if current is None:
            raise SystemExit(f"Content outside a section in {path.name}: {raw_line}")
        sections[current].append(line)
    return {name: "".join(lines) for name, lines in sections.items()}


def encode_page_entries(source: str, section_name: str) -> list[int]:
    result: list[int] = []
    token_re = re.compile(r"<[^>]+>")
    pos = 0
    while pos < len(source):
        if source[pos] == "<":
            match = token_re.match(source, pos)
            if not match:
                raise SystemExit(f"Malformed token in [{section_name}] at character {pos}")
            token = match.group(0)
            if token not in NAMED_CHARACTER_TOKENS:
                raise SystemExit(f"Unknown token {token} in [{section_name}]")
            result.append(NAMED_CHARACTER_TOKENS[token])
            pos = match.end()
            continue
        char = source[pos]
        if char not in ASCII_TO_SOM:
            raise SystemExit(f"Unsupported character {char!r} in [{section_name}]")
        result.append(ASCII_TO_SOM[char])
        pos += 1

    if len(result) != 26:
        raise SystemExit(f"[{section_name}] has {len(result)} entries; exactly 26 are required")
    return result


def frame_row(entries: list[int]) -> bytes:
    if len(entries) != 26:
        raise AssertionError("Name Entry rows must have 26 selectable cells")
    framed = [0x80, 0x80] + entries + [0x80, 0x7F]
    out = bytearray()
    for value in framed:
        out += bytes((0x80, value))
    assert len(out) == ROW_SIZE
    return bytes(out)


def build_character_rows(path: Path) -> bytes:
    sections = parse_sections(path)
    required = ("uppercase", "lowercase", "symbols")
    missing = [name for name in required if name not in sections]
    extra = sorted(set(sections) - set(required))
    if missing:
        raise SystemExit(f"Missing section(s) in {path.name}: {', '.join(missing)}")
    if extra:
        raise SystemExit(f"Unexpected section(s) in {path.name}: {', '.join(extra)}")

    output = bytearray()
    for name in required:
        output += frame_row(encode_page_entries(sections[name], name))
    assert len(output) == HELP_OFFSET
    return bytes(output)


def encode_help_text(interface_text: dict) -> bytes:
    entries = group_entries(interface_text, NAME_HELP_GROUP)
    if len(entries) != 3:
        raise SystemExit(f"Expected 3 Name Entry help rows, got {len(entries)}")
    texts = [entry["source"] for entry in entries]
    old = "NAMES CAN BE UP TO 6 LETTERS LONG."
    new = "NAMES CAN BE UP TO 9 LETTERS LONG."
    if old not in texts[1]:
        raise SystemExit("Unexpected clean-USA Name Entry length help text")
    texts[1] = texts[1].replace(old, new, 1)

    encoded_lines: list[bytes] = []
    for line_number, text in enumerate(texts, 1):
        out = bytearray((0x80,))
        for char in text:
            if char in {"“", "”"}:
                # The generic relocated help drops the decorative quotes around
                # ATTACK. This keeps the generic help no longer than the French
                # overlay it may later receive, avoiding stale tail bytes in a
                # dependency-composed IPS while preserving the instruction.
                continue
            elif char in ASCII_TO_SOM:
                out.append(ASCII_TO_SOM[char])
            else:
                raise SystemExit(
                    f"Unsupported character {char!r} in USA Name Entry help, row {line_number}"
                )
        encoded_lines.append(bytes(out))
    return b"\x7f".join(encoded_lines)


def build_naming_resource(base: bytes) -> bytes:
    # Generic English help is read directly from the clean USA ROM.  No JSON
    # asset or translation source owns stock text in this component.
    try:
        interface_text = extract_interface_text(base)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    rows = build_character_rows(ROOT / "assets" / "naming_characters.txt")
    help_text = encode_help_text(interface_text)
    if len(help_text) > GENERIC_HELP_MAX_BYTES:
        raise SystemExit(
            f"Generic Name Entry help is {len(help_text)} bytes; dependency overlay limit is {GENERIC_HELP_MAX_BYTES}"
        )
    resource = rows + help_text + bytes(16)
    if len(resource) > MAX_RESOURCE_SIZE:
        raise SystemExit(f"Naming resource is {len(resource)} bytes; maximum is {MAX_RESOURCE_SIZE}")
    return resource


def apply_source_edits(base: bytes, resource: bytes) -> bytearray:
    rom = expand_rom(base)
    for edit in STATIC_EDITS:
        actual = base[edit.offset:edit.offset + len(edit.expected)]
        if actual != edit.expected:
            raise SystemExit(
                f"Unexpected stock bytes for {edit.description} at {edit.offset:#08x}: "
                f"expected {edit.expected.hex(' ')}, got {actual.hex(' ')}"
            )
        rom[edit.offset:edit.offset + len(edit.payload)] = edit.payload

    # Expanded-ROM metadata and generated generic Name Entry resource.
    rom[0x00FFD7:0x00FFDC] = bytes.fromhex("0C0301C300")
    rom[0x244000:0x244000 + len(resource)] = resource
    update_checksum(rom)
    return rom


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the generic extended Secret of Mana Name Entry component.")
    parser.add_argument("rom", type=Path, help="clean unheadered Secret of Mana (USA) ROM")
    parser.add_argument("-o", "--output", type=Path, default=Path("build/patch.ips"), help="output IPS path")
    parser.add_argument("--patched-rom", type=Path, help="optional patched ROM output")
    args = parser.parse_args()

    base = args.rom.read_bytes()
    validate_base_rom(base)
    resource = build_naming_resource(base)
    patched = apply_source_edits(base, resource)
    ips = make_ips(base, patched)

    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(ips)
    if args.patched_rom:
        patched_path = args.patched_rom if args.patched_rom.is_absolute() else ROOT / args.patched_rom
        patched_path.parent.mkdir(parents=True, exist_ok=True)
        patched_path.write_bytes(patched)
        print(f"Patched ROM: {patched_path}")

    print(f"Base ROM verified: {args.rom}")
    print(f"Generic naming resource: {len(resource)} bytes")
    print(f"IPS: {output}")
    print(f"IPS size: {len(ips)} bytes")


if __name__ == "__main__":
    main()
