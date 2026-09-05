#!/usr/bin/env python3
"""Build the standalone 9-character French Name Entry component from the clean USA ROM.
Editable character rows remain component-local; shared source/translation text
lives at repository root and is bound by ROM-position ID. 65C816/data edits are
centralized in src/patch_data.py and mirrored as readable assembly in src/*.asm.
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
from shared.french_charset import BASIC_FRENCH_CHARS, glyph_bytes, profile_mapping, profile_threshold  # noqa: E402
from shared.rom import validate_base_rom, update_checksum, expand_rom  # noqa: E402
from shared.ips import make_ips  # noqa: E402
from shared.interface_text import (  # noqa: E402
    NAME_HELP_GROUP,
    group_entries,
    load_document as load_interface_text,
    verify_against_rom as verify_interface_text,
)
from shared.translation_json import load_translation, require  # noqa: E402

# Naming screen can safely use the original French-ROM range $D4-$E0. The
# extended $E1-$E5 slots are still used by graphics on this screen.
FONT_BASE = 0x12DC00
GLYPH_HEIGHT = 12
DTE_COMPARE_IMMEDIATE_OFFSET = 0x0016F6
DTE_NEW_THRESHOLD = profile_threshold("basic_french")
ACCENT_TO_SOM = profile_mapping("basic_french")
ACCENT_FIRST = ACCENT_TO_SOM[BASIC_FRENCH_CHARS[0]]
ACCENT_FONT_OFFSET = FONT_BASE + (ACCENT_FIRST - 0x80) * GLYPH_HEIGHT

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
ASCII_TO_SOM.update(ACCENT_TO_SOM)
ASCII_TO_SOM.update({chr(ord("a") + i): 0x81 + i for i in range(26)})
ASCII_TO_SOM.update({chr(ord("A") + i): 0x9B + i for i in range(26)})
ASCII_TO_SOM.update({str(i): 0xB5 + i for i in range(10)})
ASCII_TO_SOM.update({
    ".": 0xBF, ",": 0xC0, "/": 0xC1, "'": 0xC2,
    "-": 0xC6, "%": 0xC7, "!": 0xC8, "&": 0xC9,
    "?": 0xCA, "(": 0xCB, ")": 0xCC, "#": 0xCD,
})

MAX_RESOURCE_SIZE = 0x200



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


def encode_page_entries(source: str, section_name: str, *, allow_padding: bool = False) -> list[int]:
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

    if allow_padding:
        if len(result) > 26:
            raise SystemExit(f"[{section_name}] has {len(result)} entries; at most 26 are allowed")
        result.extend([0x80] * (26 - len(result)))
    elif len(result) != 26:
        raise SystemExit(f"[{section_name}] has {len(result)} entries; exactly 26 are required")
    return result


def build_character_rows(path: Path) -> bytes:
    sections = parse_sections(path)
    required = ("uppercase", "lowercase", "symbols", "accents")
    missing = [name for name in required if name not in sections]
    if missing:
        raise SystemExit(f"Missing section(s) in {path.name}: {', '.join(missing)}")

    output = bytearray()
    for name in required:
        entries = encode_page_entries(sections[name], name, allow_padding=(name == "accents"))
        # 30 16-bit cells: two leading blanks, 26 selectable cells, one blank,
        # then the $7F row terminator. Every cell begins with $80.
        framed = [0x80, 0x80] + entries + [0x80, 0x7F]
        assert len(framed) == 30
        for value in framed:
            output += bytes((0x80, value))
    return bytes(output)


def encode_help_text(interface_text: dict, translations: dict[str, str]) -> bytes:
    source_entries = group_entries(interface_text, NAME_HELP_GROUP)
    try:
        texts = require(
            translations, [entry["id"] for entry in source_entries], context="Name Entry help"
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    encoded_lines: list[bytes] = []
    for line_number, text in enumerate(texts, 1):
        out = bytearray((0x80,))  # stock resource begins each displayed line with a blank
        quote_open = True
        for char in text:
            if char == '"':
                out.append(0xC3 if quote_open else 0xC4)
                quote_open = not quote_open
            elif char in ASCII_TO_SOM:
                out.append(ASCII_TO_SOM[char])
            else:
                raise SystemExit(f"Unsupported character {char!r} in French Name Entry translation, row {line_number}")
        if not quote_open:
            raise SystemExit(f"Unbalanced double quote in French Name Entry translation, row {line_number}")
        encoded_lines.append(bytes(out))
    return b"\x7f".join(encoded_lines)


def build_naming_resource(base: bytes) -> bytes:
    interface_text = load_interface_text(PROJECT_ROOT / "assets" / "interface_text.json")
    try:
        verify_interface_text(base, interface_text)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    try:
        translations = load_translation(
            PROJECT_ROOT / "translations" / "interface_text_french.json",
            interface_text,
            source_asset="interface_text.json",
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    rows = build_character_rows(ROOT / "assets" / "naming_characters.txt")
    help_text = encode_help_text(interface_text, translations)
    # Explicit terminator/guard bytes complete the relocated resource.
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

    # Install the shared naming-safe French glyph range $D4-$E0.
    rom[DTE_COMPARE_IMMEDIATE_OFFSET] = DTE_NEW_THRESHOLD
    accent_glyphs = glyph_bytes(BASIC_FRENCH_CHARS)
    rom[ACCENT_FONT_OFFSET:ACCENT_FONT_OFFSET + len(accent_glyphs)] = accent_glyphs

    # Expanded-ROM metadata and generated Name Entry resource.
    rom[0x00FFD7:0x00FFDC] = bytes.fromhex("0C0301C300")
    rom[0x244000:0x244000 + len(resource)] = resource
    update_checksum(rom)
    return rom



def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Secret of Mana French Name Entry component.")
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
    print(f"Naming resource: {len(resource)} bytes")
    print(f"IPS: {output}")
    print(f"IPS size: {len(ips)} bytes")


if __name__ == "__main__":
    main()
