#!/usr/bin/env python3
"""Build the French localization overlay for ``name_entry_extended``.

The generic component owns the 9-character engine/layout and the first three
rows. This dependent overlay owns only the French extension row, French help,
French glyphs, and the Name Entry / PLAYER_NAME DTE routing needed by those
extended bytes.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.patch_data import (
    FOUR_ROW_LAYOUT_SCRIPT,
    FOUR_ROW_NAVIGATION_CODE,
    STOCK_NAVIGATION_BYTES,
)

from shared.charset import (  # noqa: E402
    BASIC_FRENCH_CHARS,
    CHAR_TO_CODE,
    glyph_bytes,
    profile_mapping,
)
from shared.text.interface import (  # noqa: E402
    NAME_HELP_GROUP,
    group_entries,
    load_document as load_interface_text,
    verify_against_rom as verify_interface_text,
)
from shared.core.ips import make_ips  # noqa: E402
from shared.name_entry.dte import (  # noqa: E402
    install as install_name_dte_router,
    validate_stock as validate_name_dte_stock,
)
from shared.core.rom import expand_rom, update_checksum, validate_base_rom  # noqa: E402
from shared.text.translation_json import load_translation, require  # noqa: E402

FONT_BASE = 0x12DC00
GLYPH_HEIGHT = 12
ACCENT_TO_SOM = profile_mapping("basic_french")
ACCENT_FIRST = ACCENT_TO_SOM[BASIC_FRENCH_CHARS[0]]
ACCENT_FONT_OFFSET = FONT_BASE + (ACCENT_FIRST - 0x80) * GLYPH_HEIGHT
EXTRA_NAME_CHARS = "♪°;"

ASCII_TO_SOM = {" ": 0x80}
ASCII_TO_SOM.update(ACCENT_TO_SOM)
ASCII_TO_SOM.update({char: CHAR_TO_CODE[char] for char in EXTRA_NAME_CHARS})
ASCII_TO_SOM.update({chr(ord("a") + i): 0x81 + i for i in range(26)})
ASCII_TO_SOM.update({chr(ord("A") + i): 0x9B + i for i in range(26)})
ASCII_TO_SOM.update({str(i): 0xB5 + i for i in range(10)})
ASCII_TO_SOM.update({
    ".": 0xBF, ",": 0xC0, "/": 0xC1, "'": 0xC2,
    "-": 0xC6, "%": 0xC7, "!": 0xC8, "&": 0xC9,
    "?": 0xCA, "(": 0xCB, ")": 0xCC, "#": 0xCD,
})

RESOURCE_BASE = 0x244000
ROW_SIZE = 60
EXTENSION_ROW_OFFSET = ROW_SIZE * 3
RESOURCE_LIMIT = 0x200



def load_extension_row(path: Path) -> str:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Cannot read {path}: {exc}") from exc
    if not isinstance(raw, dict) or set(raw) != {"row"} or not isinstance(raw["row"], str):
        raise SystemExit(f"{path} must contain exactly one string field: row")
    return raw["row"]


def encode_extension_row(source: str) -> bytes:
    entries: list[int] = []
    for char in source:
        if char not in ASCII_TO_SOM:
            raise SystemExit(f"Unsupported French Name Entry character: {char!r}")
        entries.append(ASCII_TO_SOM[char])
    if len(entries) > 26:
        raise SystemExit(f"French extension row has {len(entries)} entries; at most 26 are allowed")
    entries.extend([0x80] * (26 - len(entries)))
    framed = [0x80, 0x80] + entries + [0x80, 0x7F]
    out = bytearray()
    for value in framed:
        out += bytes((0x80, value))
    assert len(out) == ROW_SIZE
    return bytes(out)


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
        out = bytearray((0x80,))
        quote_open = True
        for char in text:
            if char == '"':
                out.append(0xC3 if quote_open else 0xC4)
                quote_open = not quote_open
            elif char in ASCII_TO_SOM:
                out.append(ASCII_TO_SOM[char])
            else:
                raise SystemExit(
                    f"Unsupported character {char!r} in French Name Entry translation, row {line_number}"
                )
        if not quote_open:
            raise SystemExit(f"Unbalanced double quote in French Name Entry translation, row {line_number}")
        encoded_lines.append(bytes(out))
    return b"\x7f".join(encoded_lines)


def build_overlay(base: bytes) -> bytes:
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

    row = encode_extension_row(load_extension_row(ROOT / "assets" / "name_entry_extension.json"))
    help_text = encode_help_text(interface_text, translations)
    payload = row + help_text + bytes(16)
    if EXTENSION_ROW_OFFSET + len(payload) > RESOURCE_LIMIT:
        raise SystemExit(
            f"French Name Entry overlay ends at {EXTENSION_ROW_OFFSET + len(payload):#x}; "
            f"resource limit is {RESOURCE_LIMIT:#x}"
        )
    # Keep the in-memory resource window deterministic through $E4:41FF.
    # IPS generation omits trailing zero bytes that already match clean expanded
    # ROM. The current localized row/help payload itself extends beyond the
    # generic resource payload, so no stale generic help survives composition.
    return payload + bytes(RESOURCE_LIMIT - EXTENSION_ROW_OFFSET - len(payload))


def apply(base: bytes, overlay: bytes) -> bytearray:
    rom = expand_rom(base)

    # Convert the generic three-row Name Entry into the historical validated
    # four-row geometry/navigation used by the French extension.  The IPS is
    # still built from the clean USA ROM, so validate the underlying stock
    # bytes before writing the dependent override.
    actual_nav = base[0x003583:0x003583 + len(STOCK_NAVIGATION_BYTES)]
    if actual_nav != STOCK_NAVIGATION_BYTES:
        raise SystemExit(
            "Unexpected clean-USA bytes at C0:3583 for French four-row navigation"
        )
    rom[0x003583:0x003583 + len(FOUR_ROW_NAVIGATION_CODE)] = FOUR_ROW_NAVIGATION_CODE

    # The generic three-row geometry retains the stock first-row selector $60.
    # The validated French four-row geometry adds a row above it, so it owns
    # the $50 initial-selector override.
    if base[0x075019] != 0x60:
        raise SystemExit("Unexpected clean-USA initial Name Entry selector at C7:5019")
    rom[0x075019] = 0x50

    layout_start = 0x074E00
    actual_layout = base[layout_start:layout_start + len(FOUR_ROW_LAYOUT_SCRIPT)]
    if actual_layout != bytes((0xFF,)) * len(FOUR_ROW_LAYOUT_SCRIPT):
        raise SystemExit("Unexpected clean-USA bytes at C7:4E00 for French four-row layout")
    rom[layout_start:layout_start + len(FOUR_ROW_LAYOUT_SCRIPT)] = FOUR_ROW_LAYOUT_SCRIPT

    accent_glyphs = glyph_bytes(BASIC_FRENCH_CHARS)
    rom[ACCENT_FONT_OFFSET:ACCENT_FONT_OFFSET + len(accent_glyphs)] = accent_glyphs
    for char in EXTRA_NAME_CHARS:
        code = CHAR_TO_CODE[char]
        offset = FONT_BASE + (code - 0x80) * GLYPH_HEIGHT
        rom[offset:offset + GLYPH_HEIGHT] = glyph_bytes(char)

    validate_name_dte_stock(base)
    install_name_dte_router(rom)

    start = RESOURCE_BASE + EXTENSION_ROW_OFFSET
    rom[start:RESOURCE_BASE + RESOURCE_LIMIT] = overlay
    update_checksum(rom)
    return rom


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the French overlay for extended Secret of Mana Name Entry.")
    parser.add_argument("rom", type=Path, help="clean unheadered Secret of Mana (USA) ROM")
    parser.add_argument("-o", "--output", type=Path, default=Path("build/patch.ips"), help="output IPS path")
    parser.add_argument("--patched-rom", type=Path, help="optional overlay-only patched ROM output (dependency not included)")
    args = parser.parse_args()

    base = args.rom.read_bytes()
    validate_base_rom(base)
    overlay = build_overlay(base)
    patched = apply(base, overlay)
    ips = make_ips(base, patched)

    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(ips)
    if args.patched_rom:
        patched_path = args.patched_rom if args.patched_rom.is_absolute() else ROOT / args.patched_rom
        patched_path.parent.mkdir(parents=True, exist_ok=True)
        patched_path.write_bytes(patched)
        print(f"Overlay-only ROM (requires name_entry_extended for use): {patched_path}")

    print(f"Base ROM verified: {args.rom}")
    print("Dependency: name_entry_extended")
    print(f"French resource overlay: {len(overlay)} bytes")
    print(f"IPS: {output}")
    print(f"IPS size: {len(ips)} bytes")


if __name__ == "__main__":
    main()
