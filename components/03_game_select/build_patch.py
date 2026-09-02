#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import struct
import zlib
import sys
from pathlib import Path

BASE_SIZE = 0x200000
EXPANDED_SIZE = 0x300000
BASE_CRC32 = 0xD0176B24
BASE_MD5 = "10a894199a9adc50ff88815fd9853e19"
BASE_SHA1 = "8133041a363e3cc68cedef40b49b6d20d03c505d"
BASE_SHA256 = "4c15013131351e694e05f22e38bb1b3e4031dedac77ec75abecebe8520d82d5f"

# Stock GAME SELECT label resource in bank C7.
# Step 3 relocates the resource inside bank C7 because the descriptor stores
# only a 16-bit pointer and the translated fields no longer fit the stock blob.
MENU_RESOURCE_RELOC_OFFSET = 0x074400  # C7:4400, stock free space
MENU_RESOURCE_RELOC_PTR = 0x4400
MENU_DESCRIPTOR_TEXT_PTR_OFFSET = 0x07780A

# Stock-only extraction map (used by --extract on the clean US ROM).
STOCK_LABEL_FIELDS = {
    "SELECT":      (0x077314, 6),
    "GAME_SELECT": (0x07731C, 12),
    "NEW_GAME":    (0x07732A, 8),
    "GAME_FILE":   (0x077334, 10),
}

# The D-pad label occupies eight decoded cells after the initial prefix.
# Keeping this segment at eight preserves its two stock placements.
SELECT_SLOT_CELLS = 8

# Three type-1 records in menu #0 describe the framed text fields.  The high
# byte of their packed size is the horizontal size; each unit corresponds to
# two decoded character cells.
FRAME_WIDTH_OFFSETS = {
    "GAME_SELECT": 0x07756D,
    "NEW_GAME":    0x077572,
    "GAME_FILE":   0x077577,
}
STOCK_FRAME_WIDTHS = {
    "GAME_SELECT": 0x07,
    "NEW_GAME":    0x05,
    "GAME_FILE":   0x06,
}

# The native menu resource is exactly 45 source bytes including its final $00.
# Runtime testing showed that changing this physical size desynchronizes the
# help-text rendering, so step 3 preserves the 45-byte layout exactly.
MENU_RESOURCE_SAFE_SOURCE_SIZE = 45
WELCOME_POINTER_OFFSET = 0x0033B5       # stock pointer = C0:33F0
WELCOME_RELOC_OFFSET = 0x2D8000         # SNES ED:8000
WELCOME_RELOC_SNES = 0xED8000

ROM_SIZE_OFFSET = 0x00FFD7
CHECKSUM_COMPLEMENT_OFFSET = 0x00FFDC
CHECKSUM_OFFSET = 0x00FFDE

ASCII_TO_SOM = {" ": 0x80}
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
from shared.french_charset import GAME_SELECT_CHARS, glyph_bytes, profile_mapping

ACCENT_TO_SOM = profile_mapping("game_select")
ASCII_TO_SOM.update(ACCENT_TO_SOM)
ASCII_TO_SOM.update({chr(ord("a") + i): 0x81 + i for i in range(26)})
ASCII_TO_SOM.update({chr(ord("A") + i): 0x9B + i for i in range(26)})
ASCII_TO_SOM.update({str(i): 0xB5 + i for i in range(10)})
ASCII_TO_SOM.update({
    ".": 0xBF, ",": 0xC0, "/": 0xC1, "'": 0xC2,
    '"': 0xC3,  # handled specially below to alternate opening/closing quote
    "-": 0xC6, "%": 0xC7, "!": 0xC8, "&": 0xC9,
    "?": 0xCA, "(": 0xCB, ")": 0xCC, "#": 0xCD,
})
SOM_TO_ASCII = {v: k for k, v in ASCII_TO_SOM.items() if k != '"'}
SOM_TO_ASCII[0xC3] = '"'
SOM_TO_ASCII[0xC4] = '"'
SOM_TO_ASCII.update({v: k for k, v in ACCENT_TO_SOM.items()})


# Stock US 8x12 font. Character $80 begins at ROM $12DC00.
FONT_BASE = 0x12DC00
GLYPH_WIDTH = 8
GLYPH_HEIGHT = 12
ACCENT_FIRST = ACCENT_TO_SOM[GAME_SELECT_CHARS[0]]
ACCENT_CHARS = GAME_SELECT_CHARS
ROOT = Path(__file__).resolve().parent

# The stock text decoder treats $D3-$FF as DTE dictionary bytes.
# For this project, $D4-$E0 become ordinary glyph codes, so the DTE
# threshold moves to $E1. The original US script does not use these
# DTE values as text.
DTE_COMPARE_IMMEDIATE_OFFSET = 0x0016F6
DTE_STOCK_THRESHOLD = 0xD3
DTE_NEW_THRESHOLD = 0xE1

def load_accent_glyphs() -> bytes:
    """Load the canonical shared GAME SELECT French glyph profile."""
    try:
        return glyph_bytes(ACCENT_CHARS)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc


REQUIRED_IDS = [
    "SELECT", "GAME_SELECT", "NEW_GAME", "GAME_FILE",
    "WELCOME_1", "WELCOME_2", "WELCOME_3", "WELCOME_4",
]


def digest(data: bytes) -> dict[str, str]:
    return {
        "crc32": f"{zlib.crc32(data) & 0xFFFFFFFF:08x}",
        "md5": hashlib.md5(data).hexdigest(),
        "sha1": hashlib.sha1(data).hexdigest(),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def verify_base_rom(data: bytes) -> None:
    expected = {
        "crc32": f"{BASE_CRC32:08x}",
        "md5": BASE_MD5,
        "sha1": BASE_SHA1,
        "sha256": BASE_SHA256,
    }
    got = digest(data)
    errors = []
    if len(data) != BASE_SIZE:
        errors.append(f"size {len(data):#x}, expected {BASE_SIZE:#x}")
    for key, value in expected.items():
        if got[key] != value:
            errors.append(f"{key.upper()} {got[key]}, expected {value}")
    if errors:
        raise SystemExit("Base ROM verification failed:\n  " + "\n  ".join(errors))


def encode_text(text: str, context: str) -> bytes:
    out = bytearray()
    quote_open = True
    for pos, ch in enumerate(text):
        if ch == '"':
            out.append(0xC3 if quote_open else 0xC4)
            quote_open = not quote_open
            continue
        if ch not in ASCII_TO_SOM:
            raise SystemExit(
                f"Unsupported character {ch!r} in {context} at position {pos}. "
                "The GAME SELECT builder supports ASCII plus the shared game_select French profile."
            )
        out.append(ASCII_TO_SOM[ch])
    if not quote_open:
        raise SystemExit(f"Unbalanced double quote in {context}")
    return bytes(out)


def decode_text(data: bytes) -> str:
    chars = []
    for b in data:
        if b not in SOM_TO_ASCII:
            raise ValueError(f"Unsupported stock text byte ${b:02X}")
        chars.append(SOM_TO_ASCII[b])
    return "".join(chars)


def read_csv(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows or "id" not in rows[0] or "text" not in rows[0]:
        raise SystemExit(f"{path.name} must contain columns: id,text")
    result: dict[str, str] = {}
    for row in rows:
        key = (row.get("id") or "").strip()
        if not key:
            continue
        if key in result:
            raise SystemExit(f"Duplicate id {key!r} in {path.name}")
        result[key] = row.get("text") or ""
    missing = [key for key in REQUIRED_IDS if key not in result]
    if missing:
        raise SystemExit("Missing CSV id(s): " + ", ".join(missing))
    return result


def _min_even_width(text: str, context: str) -> tuple[bytes, int]:
    """Encode a framed label and reserve at least one cell on its right."""
    payload = encode_text(text, context)
    cells = len(payload) + 1
    if cells & 1:
        cells += 1
    return payload, cells


def build_menu_resource(rows: dict[str, str]) -> tuple[bytes, dict[str, int]]:
    """Build the native 45-byte GAME SELECT resource, without DTE.

    The stock resource is structurally 45 bytes.  Its first nine bytes are the
    leading blank plus the fixed 8-cell SELECT segment.  The three framed
    fields then occupy 36 logical cells in total.  The final $00 terminator
    doubles as the last logical cell of GAME_FILE, exactly as in the stock US
    resource.  Keeping this invariant prevents the following help-text buffer
    from being desynchronised.
    """
    select = encode_text(rows["SELECT"], "SELECT")
    if len(select) > SELECT_SLOT_CELLS - 1:
        raise SystemExit(
            f"SELECT encodes to {len(select)} cells; at most {SELECT_SLOT_CELLS - 1} "
            "visible cells are supported while preserving the stock D-pad layout."
        )
    select_slot = select + b"\x80" * (SELECT_SLOT_CELLS - len(select))

    payloads: dict[str, bytes] = {}
    width_cells: dict[str, int] = {}
    for key in ("GAME_SELECT", "NEW_GAME", "GAME_FILE"):
        payload, cells = _min_even_width(rows[key], key)
        payloads[key] = payload
        width_cells[key] = cells

    # The native source layout requires the three framed widths to total 36
    # logical cells.  Keep the resource at exactly 45 bytes, but spend any spare
    # pair first on GAME_SELECT: its 11-character French label otherwise fills
    # the 11-cell usable interior of a $06 frame and visually touches the right
    # edge. NEW_GAME already has one usable blank cell at $06. GAME_FILE is the
    # least sensitive field and can safely use its minimum width.
    TARGET_TOTAL_CELLS = 36
    used = sum(width_cells.values())
    if used > TARGET_TOTAL_CELLS:
        raise SystemExit(
            f"GAME SELECT framed fields require {used} cells; the native no-DTE layout "
            f"supports {TARGET_TOTAL_CELLS}. Choose shorter labels."
        )
    spare = TARGET_TOTAL_CELLS - used
    if spare & 1:
        raise SystemExit("Internal error: framed width spare space is not even")
    priority = ("GAME_SELECT", "NEW_GAME", "GAME_FILE")
    i = 0
    while spare:
        width_cells[priority[i % 3]] += 2
        spare -= 2
        i += 1

    widths = {key: width_cells[key] // 2 for key in width_cells}

    game_select = payloads["GAME_SELECT"] + b"\x80" * (width_cells["GAME_SELECT"] - len(payloads["GAME_SELECT"]))
    new_game = payloads["NEW_GAME"] + b"\x80" * (width_cells["NEW_GAME"] - len(payloads["NEW_GAME"]))

    # Stock quirk: GAME_FILE contributes one source byte fewer than its logical
    # width; the final $00 resource terminator is its last cell.
    gf_source_cells = width_cells["GAME_FILE"] - 1
    if len(payloads["GAME_FILE"]) > gf_source_cells:
        raise SystemExit("GAME_FILE does not leave room for the native final terminator cell")
    game_file = payloads["GAME_FILE"] + b"\x80" * (gf_source_cells - len(payloads["GAME_FILE"]))

    resource = b"\x80" + select_slot + game_select + new_game + game_file + b"\x00"
    if len(resource) != MENU_RESOURCE_SAFE_SOURCE_SIZE:
        raise SystemExit(
            f"Internal error: GAME SELECT resource is {len(resource)} bytes, expected exactly "
            f"{MENU_RESOURCE_SAFE_SOURCE_SIZE}."
        )
    return resource, widths


def build_welcome(rows: dict[str, str]) -> bytes:
    # Stock layout is intentionally preserved:
    # line 1, blank line, lines 2-4, then one final blank line, then $00.
    encoded = [encode_text(rows[f"WELCOME_{i}"], f"WELCOME_{i}") for i in range(1, 5)]
    return encoded[0] + b"\x7F\x7F" + encoded[1] + b"\x7F" + encoded[2] + b"\x7F" + encoded[3] + b"\x7F\x7F\x00"


def update_checksum(rom: bytearray) -> int:
    # Same physical-3-MiB method used by the validated opening/tree builders.
    rom[CHECKSUM_COMPLEMENT_OFFSET:CHECKSUM_OFFSET + 2] = b"\xFF\xFF\x00\x00"
    checksum = sum(rom) & 0xFFFF
    complement = checksum ^ 0xFFFF
    rom[CHECKSUM_COMPLEMENT_OFFSET:CHECKSUM_OFFSET + 2] = struct.pack("<HH", complement, checksum)
    return checksum


def apply_sources(base: bytes, rows: dict[str, str]) -> tuple[bytearray, int]:
    rom = bytearray(base)
    rom.extend(b"\x00" * (EXPANDED_SIZE - len(rom)))

    # Step 2: turn $D4-$E0 into normal character codes for the stock text
    # decoder, while keeping $E1-$FF on the original DTE path.
    if base[DTE_COMPARE_IMMEDIATE_OFFSET] != DTE_STOCK_THRESHOLD:
        raise SystemExit(
            f"Unexpected stock DTE threshold at ${DTE_COMPARE_IMMEDIATE_OFFSET:06X}: "
            f"${base[DTE_COMPARE_IMMEDIATE_OFFSET]:02X}"
        )
    rom[DTE_COMPARE_IMMEDIATE_OFFSET] = DTE_NEW_THRESHOLD

    # Replace the 13 otherwise-unused direct-glyph slots $D4-$E0 with the
    # editable 8x12 glyph atlas in shared/french_charset/french_glyphs.png.
    glyph_start = FONT_BASE + (ACCENT_FIRST - 0x80) * GLYPH_HEIGHT
    glyph_blob = load_accent_glyphs()
    rom[glyph_start:glyph_start + len(glyph_blob)] = glyph_blob

    # Step 3: relocate the label resource and derive the three frame widths
    # directly from the CSV text.  Unlike the failed v1 experiment, the field
    # segmentation and the window geometry are changed together.
    menu_resource, frame_widths = build_menu_resource(rows)
    if MENU_RESOURCE_RELOC_OFFSET + len(menu_resource) > 0x075000:
        raise SystemExit("Relocated GAME SELECT resource exceeded reserved C7:4400-C7:4FFF")
    rom[MENU_RESOURCE_RELOC_OFFSET:MENU_RESOURCE_RELOC_OFFSET + len(menu_resource)] = menu_resource
    rom[MENU_DESCRIPTOR_TEXT_PTR_OFFSET:MENU_DESCRIPTOR_TEXT_PTR_OFFSET + 2] = MENU_RESOURCE_RELOC_PTR.to_bytes(2, "little")

    for key, offset in FRAME_WIDTH_OFFSETS.items():
        if base[offset] != STOCK_FRAME_WIDTHS[key]:
            raise SystemExit(
                f"Unexpected stock {key} frame width at ${offset:06X}: ${base[offset]:02X}"
            )
        rom[offset] = frame_widths[key]

    # Relocate the long help text now, so its translation will no longer be
    # constrained by the 156-byte stock allocation at C0:33F0.
    welcome = build_welcome(rows)
    if WELCOME_RELOC_OFFSET + len(welcome) > 0x2E0000:
        raise SystemExit("WELCOME text exceeded the reserved ED:8000-ED:FFFF region")
    rom[WELCOME_RELOC_OFFSET:WELCOME_RELOC_OFFSET + len(welcome)] = welcome
    rom[WELCOME_POINTER_OFFSET:WELCOME_POINTER_OFFSET + 3] = WELCOME_RELOC_SNES.to_bytes(3, "little")

    rom[ROM_SIZE_OFFSET] = 0x0C  # 3 MiB physical ROM
    checksum = update_checksum(rom)
    return rom, checksum


def diff_records(original: bytes, modified: bytes) -> list[tuple[int, bytes]]:
    # Treat bytes beyond the original ROM as zero and group adjacent changes.
    records: list[tuple[int, bytes]] = []
    i = 0
    n = len(modified)
    while i < n:
        old = original[i] if i < len(original) else 0
        if modified[i] == old:
            i += 1
            continue
        start = i
        buf = bytearray()
        while i < n:
            old = original[i] if i < len(original) else 0
            if modified[i] == old:
                # Keep very small unchanged gaps inside a record, but avoid
                # broad writes around unrelated tables (important at C0:33BE).
                gap = 0
                j = i
                while j < n and gap < 2:
                    oldj = original[j] if j < len(original) else 0
                    if modified[j] != oldj:
                        break
                    gap += 1
                    j += 1
                if gap >= 2 or j >= n:
                    break
            buf.append(modified[i])
            i += 1
        records.append((start, bytes(buf)))
    return records


def make_ips(original: bytes, modified: bytes) -> bytes:
    out = bytearray(b"PATCH")
    for offset, payload in diff_records(original, modified):
        # IPS record length is 16-bit; split if necessary.
        pos = 0
        while pos < len(payload):
            chunk = payload[pos:pos + 0xFFFF]
            out += (offset + pos).to_bytes(3, "big")
            out += len(chunk).to_bytes(2, "big")
            out += chunk
            pos += len(chunk)
    out += b"EOF"
    out += len(modified).to_bytes(3, "big")
    return bytes(out)


def pointer_to_rom(ptr: int) -> int:
    bank = (ptr >> 16) & 0xFF
    addr = ptr & 0xFFFF
    if not 0xC0 <= bank <= 0xEF:
        raise ValueError(f"Pointer ${ptr:06X} is outside expected HiROM banks")
    return ((bank - 0xC0) << 16) | addr


def extract_rows(rom: bytes) -> dict[str, str]:
    rows: dict[str, str] = {}
    for key, (offset, content_capacity) in STOCK_LABEL_FIELDS.items():
        raw = rom[offset:offset + content_capacity]
        rows[key] = decode_text(raw).rstrip(" ")

    ptr = int.from_bytes(rom[WELCOME_POINTER_OFFSET:WELCOME_POINTER_OFFSET + 3], "little")
    start = pointer_to_rom(ptr)
    end = rom.index(0x00, start)
    raw = rom[start:end]
    # $7F is the stock line-control code. Empty segments are layout spacing.
    parts = raw.split(b"\x7F")
    visible = [decode_text(part) for part in parts if part]
    if len(visible) != 4:
        raise SystemExit(f"Expected 4 visible WELCOME lines, found {len(visible)} at ${ptr:06X}")
    for i, text in enumerate(visible, 1):
        rows[f"WELCOME_{i}"] = text
    return rows


def write_csv(path: Path, rows: dict[str, str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["id", "text"])
        for key in REQUIRED_IDS:
            writer.writerow([key, rows[key]])


def main() -> None:
    parser = argparse.ArgumentParser(description="Secret of Mana (USA) GAME SELECT text source builder - validated step 3")
    parser.add_argument("rom", type=Path, help="clean unheadered Secret of Mana (USA) ROM")
    parser.add_argument("--csv", type=Path, default=ROOT / "assets" / "game_select_text.csv")
    parser.add_argument("--extract", type=Path, metavar="CSV", help="extract the stock GAME SELECT texts to CSV and exit")
    parser.add_argument("-o", "--output", type=Path, default=Path("build/patch.ips"), help="output IPS")
    parser.add_argument("--patched-rom", type=Path, help="optional output ROM for local testing")
    args = parser.parse_args()

    base = args.rom.read_bytes()
    verify_base_rom(base)

    if args.extract:
        rows = extract_rows(base)
        args.extract.parent.mkdir(parents=True, exist_ok=True)
        write_csv(args.extract, rows)
        print(f"Extracted: {args.extract}")
        return

    rows = read_csv(args.csv)
    patched, checksum = apply_sources(base, rows)
    patch = make_ips(base, bytes(patched))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(patch)
    if args.patched_rom:
        args.patched_rom.parent.mkdir(parents=True, exist_ok=True)
        args.patched_rom.write_bytes(patched)

    print(f"Patch: {args.output}")
    print(f"IPS SHA-256: {hashlib.sha256(patch).hexdigest()}")
    print(f"Expanded ROM size: {len(patched):#x}")
    print(f"SNES checksum: ${checksum:04X}")
    print(f"WELCOME pointer: ${int.from_bytes(patched[WELCOME_POINTER_OFFSET:WELCOME_POINTER_OFFSET+3], 'little'):06X}")
    print(f"WELCOME payload: {len(build_welcome(rows))} bytes at ROM ${WELCOME_RELOC_OFFSET:06X}")
    menu_resource, widths = build_menu_resource(rows)
    print(f"GAME SELECT resource: {len(menu_resource)} bytes at C7:${MENU_RESOURCE_RELOC_PTR:04X}")
    print("GAME SELECT layout: native 45-byte resource; no additional DTE compression")
    for key in ("GAME_SELECT", "NEW_GAME", "GAME_FILE"):
        print(f"{key} frame width: ${widths[key]:02X} ({widths[key] * 2} text cells)")


if __name__ == "__main__":
    main()
