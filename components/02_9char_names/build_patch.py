#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import re
import sys
import zlib
from pathlib import Path

BASE_SIZE = 0x200000
EXPANDED_SIZE = 0x300000
HEADER_OFFSET = 0x00FFC0
CHECKSUM_COMPLEMENT_OFFSET = HEADER_OFFSET + 0x1C
CHECKSUM_OFFSET = HEADER_OFFSET + 0x1E

BASE_CRC32 = 0xD0176B24
BASE_MD5 = "10a894199a9adc50ff88815fd9853e19"
BASE_SHA1 = "8133041a363e3cc68cedef40b49b6d20d03c505d"
BASE_SHA256 = "4c15013131351e694e05f22e38bb1b3e4031dedac77ec75abecebe8520d82d5f"

REFERENCE_PATCH_SHA256 = "dc20f8994d78968863311543212dde5c9c8ee9befa97d58f79dd834d8156e77f"
REFERENCE_RESOURCE_SHA256 = "948b8977b4a9ae84ac1cd4518da65a587143c799a3f00fb4ad585360f3d830ee"

# Static code/data edits. The internal header/checksum record and the generated
# naming resource are added separately by the build pipeline.
STATIC_EDITS = [
    (0x00319C, bytes.fromhex("09"), "maximum name length"),
    (0x00334D, bytes.fromhex("8335"), "Name Edit Up handler -> C0:3583"),
    (0x003363, bytes.fromhex("9535"), "Name Edit Down handler -> C0:3595"),
    (0x0033BE, bytes.fromhex("0040E4"), "Name Entry resource pointer -> E4:4000"),
    (0x003583, bytes.fromhex(
        "204A32AD5AA138E910C951B002A9804CA435"
        "204A32AD5AA1186910C9819002A9608D5AA1"
        "223D50C720AA1B60"
    ), "three-page naming-screen navigation handlers"),
    (0x07502A, bytes.fromhex("0C"), "naming-screen character-grid parameter"),
    (0x0750A6, bytes.fromhex("CC00BD0090DA38E94E204AAAE220BF0040E4"), "character lookup path -> E4:4000"),
    (0x07759D, bytes.fromhex("02061E01C004061E818A00020A"), "naming-screen layout/control data"),
    (0x07781C, bytes.fromhex("EA749B75EA"), "naming-screen table/pointer data"),
]

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
    ".": 0xBF,
    ",": 0xC0,
    "/": 0xC1,
    "'": 0xC2,
    "-": 0xC6,
    "%": 0xC7,
    "!": 0xC8,
    "&": 0xC9,
    "?": 0xCA,
    "(": 0xCB,
    ")": 0xCC,
    "#": 0xCD,
})


def digest(data: bytes) -> dict[str, str]:
    return {
        "crc32": f"{zlib.crc32(data) & 0xFFFFFFFF:08x}",
        "md5": hashlib.md5(data).hexdigest(),
        "sha1": hashlib.sha1(data).hexdigest(),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def verify_base_rom(data: bytes) -> None:
    hashes = digest(data)
    expected = {
        "crc32": f"{BASE_CRC32:08x}",
        "md5": BASE_MD5,
        "sha1": BASE_SHA1,
        "sha256": BASE_SHA256,
    }
    errors = []
    if len(data) != BASE_SIZE:
        errors.append(f"size {len(data):#x}, expected {BASE_SIZE:#x}")
    for key, expected_value in expected.items():
        if hashes[key] != expected_value:
            errors.append(f"{key.upper()} {hashes[key]}, expected {expected_value}")
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


def encode_page_entries(source: str, section_name: str) -> list[int]:
    result: list[int] = []
    pos = 0
    token_re = re.compile(r"<[^>]+>")
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
        raise SystemExit(
            f"[{section_name}] resolves to {len(result)} entries; exactly 26 are required"
        )
    return result


def build_character_pages(path: Path) -> bytes:
    sections = parse_sections(path)
    required = ("uppercase", "lowercase", "symbols")
    missing = [name for name in required if name not in sections]
    if missing:
        raise SystemExit(f"Missing section(s) in {path.name}: {', '.join(missing)}")

    output = bytearray()
    for name in required:
        entries = encode_page_entries(sections[name], name)
        # The renderer expects 30 16-bit cells per page. Each cell is stored as
        # $80 followed by the encoded glyph. Two leading cells and one trailing
        # cell are blank; the last cell contains the $7F row terminator.
        framed = [0x80, 0x80] + entries + [0x80, 0x7F]
        if len(framed) != 30:
            raise AssertionError("internal page framing error")
        for value in framed:
            output += bytes((0x80, value))
    return bytes(output)


def encode_help_text(path: Path) -> bytes:
    # splitlines() intentionally discards the final file newline. The in-ROM
    # resource has $7F only between display lines, not after the final line.
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise SystemExit(f"{path.name} is empty")

    encoded_lines: list[bytes] = []
    for line_number, line in enumerate(lines, 1):
        out = bytearray((0x80,))  # stock resource starts every line with one space
        quote_open = True
        for char in line:
            if char == '"':
                out.append(0xC3 if quote_open else 0xC4)
                quote_open = not quote_open
                continue
            if char not in ASCII_TO_SOM:
                raise SystemExit(
                    f"Unsupported character {char!r} in {path.name}, line {line_number}"
                )
            out.append(ASCII_TO_SOM[char])
        if not quote_open:
            raise SystemExit(f"Unbalanced double quote in {path.name}, line {line_number}")
        encoded_lines.append(bytes(out))
    return b"\x7f".join(encoded_lines)


def build_naming_resource(root: Path) -> bytes:
    pages = build_character_pages(root / "assets" / "naming_characters.txt")
    help_text = encode_help_text(root / "assets" / "naming_help.txt")
    return pages + help_text


def update_snes_checksum(rom: bytearray) -> None:
    # Preserve the checksum convention used by the runtime-validated reference
    # IPS: sum the physical 3 MiB image after clearing the checksum fields.
    # This is intentionally kept for byte-for-byte reproducibility of the
    # validated checkpoint. Emulators do not depend on this header checksum.
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

    for offset, payload, _description in STATIC_EDITS:
        rom[offset:offset + len(payload)] = payload

    # ROM size / SRAM size / region / developer / version. Checksum fields are
    # filled after every other edit so customized text builds remain valid.
    rom[0x00FFD7:0x00FFDC] = bytes.fromhex("0C0301C300")
    rom[0x244000:0x244000 + len(resource)] = resource
    update_snes_checksum(rom)
    return rom


def make_ips(base: bytes, patched: bytes, resource_length: int) -> bytes:
    records = [(offset, len(payload)) for offset, payload, _ in STATIC_EDITS]
    records.append((0x00FFD7, 9))
    records.append((0x244000, resource_length))
    records.sort(key=lambda item: item[0])

    out = bytearray(b"PATCH")
    for offset, length in records:
        payload = bytes(patched[offset:offset + length])
        out += offset.to_bytes(3, "big")
        out += length.to_bytes(2, "big")
        out += payload
    out += b"EOF"
    out += EXPANDED_SIZE.to_bytes(3, "big")
    return bytes(out)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the Secret of Mana (USA) 9-character mixed-case naming patch from a clean ROM."
    )
    parser.add_argument("rom", type=Path, help="clean unheadered Secret of Mana (USA) ROM")
    parser.add_argument("-o", "--output", type=Path, default=Path("build/patch.ips"), help="output IPS path")
    parser.add_argument("--patched-rom", type=Path, help="optional path for the generated patched ROM")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    base = args.rom.read_bytes()
    verify_base_rom(base)
    resource = build_naming_resource(root)
    patched = apply_source_edits(base, resource)
    ips = make_ips(base, patched, len(resource))

    resource_sha256 = hashlib.sha256(resource).hexdigest()
    patch_sha256 = hashlib.sha256(ips).hexdigest()
    canonical = resource_sha256 == REFERENCE_RESOURCE_SHA256

    if canonical and patch_sha256 != REFERENCE_PATCH_SHA256:
        raise SystemExit(
            "Canonical sources did not reproduce the validated reference patch.\n"
            f"  built:    {patch_sha256}\n"
            f"  expected: {REFERENCE_PATCH_SHA256}"
        )

    output = args.output if args.output.is_absolute() else root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(ips)

    if args.patched_rom:
        patched_path = args.patched_rom if args.patched_rom.is_absolute() else root / args.patched_rom
        patched_path.parent.mkdir(parents=True, exist_ok=True)
        patched_path.write_bytes(patched)
        print(f"Patched ROM: {patched_path}")
        print(f"Patched ROM SHA-256: {hashlib.sha256(patched).hexdigest()}")

    print(f"Base ROM verified: {args.rom}")
    print(f"Naming resource: {len(resource)} bytes")
    print(f"Naming resource SHA-256: {resource_sha256}")
    print(f"IPS: {output}")
    print(f"IPS size: {len(ips)} bytes")
    print(f"IPS SHA-256: {patch_sha256}")
    print("Reference build: yes" if canonical else "Reference build: no (text/character sources customized)")


if __name__ == "__main__":
    main()
