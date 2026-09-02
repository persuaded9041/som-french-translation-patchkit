#!/usr/bin/env python3
"""Build the standalone 9-character French Name Entry IPS.

The module remains self-contained from the clean unheadered US ROM. Editable
character rows and help text live in assets/. 65C816/data edits are centralized
in src/patch_data.py and mirrored as commented assembly in src/*.asm.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
import zlib
from pathlib import Path

from src.patch_data import STATIC_EDITS

BASE_SIZE = 0x200000
EXPANDED_SIZE = 0x300000
HEADER_OFFSET = 0x00FFC0
CHECKSUM_COMPLEMENT_OFFSET = HEADER_OFFSET + 0x1C
CHECKSUM_OFFSET = HEADER_OFFSET + 0x1E

BASE_CRC32 = 0xD0176B24
BASE_MD5 = "10a894199a9adc50ff88815fd9853e19"
BASE_SHA1 = "8133041a363e3cc68cedef40b49b6d20d03c505d"
BASE_SHA256 = "4c15013131351e694e05f22e38bb1b3e4031dedac77ec75abecebe8520d82d5f"

# Runtime-validated four-row Name Entry checkpoint.
REFERENCE_PATCH_SHA256 = "31cdc4c829130194a54020c87c2d1bb56cc908372d2024aac1aaebb230196f9f"
REFERENCE_RESOURCE_SHA256 = "c80dc4bc038eda52c046bee1cf1026fe32bd5646bc90dd25cf8dab6254a8f96f"

# Find shared/ both in the full repository and in a standalone component pack.
def find_shared_root(component_root: Path) -> Path:
    candidates = (
        component_root.parent.parent,  # repository/components/02_9char_names
        component_root.parent,         # standalone pack/02_9char_names
    )
    for candidate in candidates:
        if (candidate / "shared" / "french_charset").is_dir():
            return candidate
    raise SystemExit("Could not locate shared/french_charset")


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = find_shared_root(ROOT)
sys.path.insert(0, str(PROJECT_ROOT))
from shared.french_charset import GAME_SELECT_CHARS, glyph_bytes, profile_mapping  # noqa: E402

# Naming screen can safely use the original French-ROM range $D4-$E0. The
# extended $E1-$E5 slots are still used by graphics on this screen.
FONT_BASE = 0x12DC00
GLYPH_HEIGHT = 12
DTE_COMPARE_IMMEDIATE_OFFSET = 0x0016F6
DTE_NEW_THRESHOLD = 0xE1
ACCENT_TO_SOM = profile_mapping("game_select")
ACCENT_FIRST = ACCENT_TO_SOM[GAME_SELECT_CHARS[0]]
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


def digest(data: bytes) -> dict[str, str]:
    return {
        "crc32": f"{zlib.crc32(data) & 0xFFFFFFFF:08x}",
        "md5": hashlib.md5(data).hexdigest(),
        "sha1": hashlib.sha1(data).hexdigest(),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def verify_base_rom(data: bytes) -> None:
    expected = {
        "crc32": f"{BASE_CRC32:08x}", "md5": BASE_MD5,
        "sha1": BASE_SHA1, "sha256": BASE_SHA256,
    }
    actual = digest(data)
    errors = []
    if len(data) != BASE_SIZE:
        errors.append(f"size {len(data):#x}, expected {BASE_SIZE:#x}")
    for key, expected_value in expected.items():
        if actual[key] != expected_value:
            errors.append(f"{key.upper()} {actual[key]}, expected {expected_value}")
    if errors:
        raise SystemExit("Base ROM verification failed:\n  " + "\n  ".join(errors))


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


def encode_help_text(path: Path) -> bytes:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["id", "text"]:
            raise SystemExit(f"{path.name} must use exactly the columns: id,text")
        rows = list(reader)
    if not rows:
        raise SystemExit(f"{path.name} is empty")

    expected_ids = [f"NAME_HELP_{i}" for i in range(1, len(rows) + 1)]
    actual_ids = [row["id"].strip() for row in rows]
    if actual_ids != expected_ids:
        raise SystemExit(f"{path.name} IDs must be sequential: {', '.join(expected_ids)}")

    encoded_lines: list[bytes] = []
    for line_number, row in enumerate(rows, 1):
        out = bytearray((0x80,))  # stock resource begins each displayed line with a blank
        quote_open = True
        for char in row["text"]:
            if char == '"':
                out.append(0xC3 if quote_open else 0xC4)
                quote_open = not quote_open
            elif char in ASCII_TO_SOM:
                out.append(ASCII_TO_SOM[char])
            else:
                raise SystemExit(f"Unsupported character {char!r} in {path.name}, row {line_number}")
        if not quote_open:
            raise SystemExit(f"Unbalanced double quote in {path.name}, row {line_number}")
        encoded_lines.append(bytes(out))
    return b"\x7f".join(encoded_lines)


def build_naming_resource() -> bytes:
    rows = build_character_rows(ROOT / "assets" / "naming_characters.txt")
    help_text = encode_help_text(ROOT / "assets" / "naming_help.csv")
    # Explicit terminator/guard bytes are part of the runtime-validated checkpoint.
    resource = rows + help_text + bytes(16)
    if len(resource) > MAX_RESOURCE_SIZE:
        raise SystemExit(f"Naming resource is {len(resource)} bytes; maximum is {MAX_RESOURCE_SIZE}")
    return resource


def update_snes_checksum(rom: bytearray) -> None:
    if len(rom) != EXPANDED_SIZE:
        raise ValueError("checksum helper expects the 3 MiB expanded ROM")
    rom[CHECKSUM_COMPLEMENT_OFFSET:CHECKSUM_COMPLEMENT_OFFSET + 2] = b"\xff\xff"
    rom[CHECKSUM_OFFSET:CHECKSUM_OFFSET + 2] = b"\x00\x00"
    checksum = sum(rom) & 0xFFFF
    complement = checksum ^ 0xFFFF
    rom[CHECKSUM_COMPLEMENT_OFFSET:CHECKSUM_COMPLEMENT_OFFSET + 2] = complement.to_bytes(2, "little")
    rom[CHECKSUM_OFFSET:CHECKSUM_OFFSET + 2] = checksum.to_bytes(2, "little")


def apply_source_edits(base: bytes, resource: bytes) -> bytearray:
    rom = bytearray(base)
    rom.extend(b"\x00" * (EXPANDED_SIZE - len(rom)))

    for edit in STATIC_EDITS:
        rom[edit.offset:edit.offset + len(edit.payload)] = edit.payload

    # Install the shared naming-safe French glyph range $D4-$E0.
    rom[DTE_COMPARE_IMMEDIATE_OFFSET] = DTE_NEW_THRESHOLD
    accent_glyphs = glyph_bytes(GAME_SELECT_CHARS)
    rom[ACCENT_FONT_OFFSET:ACCENT_FONT_OFFSET + len(accent_glyphs)] = accent_glyphs

    # Expanded-ROM metadata and generated Name Entry resource.
    rom[0x00FFD7:0x00FFDC] = bytes.fromhex("0C0301C300")
    rom[0x244000:0x244000 + len(resource)] = resource
    update_snes_checksum(rom)
    return rom


def make_ips(patched: bytes, resource_length: int) -> bytes:
    records = [(edit.offset, len(edit.payload)) for edit in STATIC_EDITS]
    records += [
        (DTE_COMPARE_IMMEDIATE_OFFSET, 1),
        (ACCENT_FONT_OFFSET, len(glyph_bytes(GAME_SELECT_CHARS))),
        (0x00FFD7, 9),
        (0x244000, resource_length),
    ]
    records.sort()

    out = bytearray(b"PATCH")
    for offset, length in records:
        out += offset.to_bytes(3, "big")
        out += length.to_bytes(2, "big")
        out += patched[offset:offset + length]
    out += b"EOF" + EXPANDED_SIZE.to_bytes(3, "big")
    return bytes(out)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Secret of Mana French Name Entry component.")
    parser.add_argument("rom", type=Path, help="clean unheadered Secret of Mana (USA) ROM")
    parser.add_argument("-o", "--output", type=Path, default=Path("build/patch.ips"), help="output IPS path")
    parser.add_argument("--patched-rom", type=Path, help="optional patched ROM output")
    args = parser.parse_args()

    base = args.rom.read_bytes()
    verify_base_rom(base)
    resource = build_naming_resource()
    patched = apply_source_edits(base, resource)
    ips = make_ips(patched, len(resource))

    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(ips)
    if args.patched_rom:
        patched_path = args.patched_rom if args.patched_rom.is_absolute() else ROOT / args.patched_rom
        patched_path.parent.mkdir(parents=True, exist_ok=True)
        patched_path.write_bytes(patched)
        print(f"Patched ROM: {patched_path}")
        print(f"Patched ROM SHA-256: {hashlib.sha256(patched).hexdigest()}")

    resource_sha = hashlib.sha256(resource).hexdigest()
    patch_sha = hashlib.sha256(ips).hexdigest()
    print(f"Base ROM verified: {args.rom}")
    print(f"Naming resource: {len(resource)} bytes")
    print(f"Naming resource SHA-256: {resource_sha}")
    print(f"IPS: {output}")
    print(f"IPS size: {len(ips)} bytes")
    print(f"IPS SHA-256: {patch_sha}")
    if patch_sha == REFERENCE_PATCH_SHA256 and resource_sha == REFERENCE_RESOURCE_SHA256:
        print("Runtime-validated Name Entry checkpoint: exact match")
    else:
        print("Custom build: differs from the runtime-validated Name Entry checkpoint")


if __name__ == "__main__":
    main()
