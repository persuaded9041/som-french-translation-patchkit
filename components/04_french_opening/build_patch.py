#!/usr/bin/env python3
"""
Build the final French opening patch for Secret of Mana (USA).

The patch keeps the fixed-width opening renderer and is independent from the
future game-wide VWF.

Main changes:
- 12 visible French prologue lines, preceded by the required blank startup row;
- original accent-overlay system: $7D acute, $7E grave, $7F circumflex;
- seven compact $02 markers, each rendered as "e " (two cells);
- literal three-period sequence for "Masamune...";
- French startup credits;
- original copyright-year tile workaround;
- title arrangement relocated to ROM 0x2E8000 / CPU $EE:8000;
- 3 MiB ROM expansion.

Base ROM:
Secret of Mana (USA), headerless
SHA-1 8133041a363e3cc68cedef40b49b6d20d03c505d
"""

from pathlib import Path
import csv
import hashlib
import struct
import sys
import argparse
from PIL import Image

EXPECTED_US_SHA1 = "8133041a363e3cc68cedef40b49b6d20d03c505d"
BASE_ROM_SIZE = 0x200000
EXPANDED_ROM_SIZE = 0x300000

TITLE_CODE_ROM = 0x077C00
TITLE_ARR_ROM = 0x07B480
TITLE_FONT_ROM = 0x07C1C0

CUSTOM_CODE_ROM = 0x2E9000
CUSTOM_CODE_CPU = 0xEE9000

RELOCATED_ARR_ROM = 0x2E8000
RELOCATED_ARR_BANK = 0xEE
RELOCATED_ARR_ADDR = 0x8000

ACUTE_TILE_CODE = 0x7D
GRAVE_TILE_CODE = 0x7E
CIRC_TILE_CODE = 0x7F
BLANK_TILE_CODE = 0x60
COMPACT_E_SPACE_MARKER = 0x02
COMPACT_E_SPACE_COUNT = 7

COMPRESSION_TYPES = {
    0: 0x1F, 1: 0x0F, 2: 0x07,
    3: 0x03, 4: 0x01, 5: 0x00,
}

# Existing title renderer fragment, decompressed title-code offset 0x0845.
RENDERER_HOOK_OFFSET = 0x0845
RENDERER_ORIGINAL = bytes.fromhex(
    "c9 20 d0 02 a9 60 99 00 00 c8 c8 e6 02 80 ea"
)

# JSL $EE9000 ; BRA $883E ; NOP padding
RENDERER_HOOK = bytes.fromhex("22 00 90 ee 80 f3") + b"\xEA" * 9

# Arrangement loader fragment, decompressed title-code offset 0x2D8D.
ARR_LOADER_OFFSET = 0x2D8D
ARR_LOADER_ORIGINAL = bytes.fromhex(
    "a9 7e 00 a0 00 50 eb 09 c7 00 a2 80 b4 22 14 00 c1"
)
ARR_LOADER_RELOCATED = bytes.fromhex(
    "a9 7e 00 a0 00 50 eb 09 ee 00 a2 00 80 22 14 00 c1"
)

US_YEAR = bytes.fromhex("7d 7e 7f")
FR_STYLE_1993 = bytes.fromhex("5b 5c 5d")


def sha1(data):
    return hashlib.sha1(data).hexdigest()


def decompress_block(data, offset):
    key = int.from_bytes(data[offset:offset+2], "little")
    if key not in COMPRESSION_TYPES:
        raise ValueError(f"Unknown compression key {key}")
    mask = COMPRESSION_TYPES[key]
    out_size = (data[offset+2] << 8) | data[offset+3]
    i = offset + 4
    out = bytearray()

    while len(out) < out_size:
        token = data[i]
        i += 1
        if token < 0x80:
            n = token + 1
            out.extend(data[i:i+n])
            i += n
        else:
            b2 = data[i]
            i += 1
            distance = (((token - 0x80) & mask) * 0x100) + b2 + 1
            read_pos = len(out) - distance
            run_len = ((token - 0x80) // (mask + 1)) + 3
            for _ in range(run_len):
                if len(out) >= out_size:
                    break
                if not 0 <= read_pos < len(out):
                    raise ValueError("Invalid back-reference")
                out.append(out[read_pos])
                read_pos += 1

    return bytes(out[:out_size]), i - offset, key


def compress_payload(data, mask):
    divisor = mask + 1
    max_match_length = (127 // divisor) + 3
    max_offset = 0x100 * divisor
    n = len(data)
    inf = 1 << 30
    best = [inf] * (n + 1)
    choice = [None] * (n + 1)
    best[n] = 0

    for index in range(n - 1, -1, -1):
        remaining = n - index

        for lit_len in range(1, min(0x80, remaining) + 1):
            cost = 1 + lit_len + best[index + lit_len]
            if cost < best[index]:
                best[index] = cost
                choice[index] = ("lit", lit_len, 0)

        window_start = max(0, index - max_offset)
        max_search = min(max_match_length, remaining)

        for candidate in range(index - 1, window_start - 1, -1):
            if data[candidate] != data[index]:
                continue
            match_len = 1
            while (
                match_len < max_search
                and data[candidate + match_len] == data[index + match_len]
            ):
                match_len += 1
            if match_len < 3:
                continue

            distance = index - candidate
            high = (distance - 1) // 0x100

            for length in range(3, match_len + 1):
                token = 0x80 + (length - 3) * divisor + high
                if token > 0xFF:
                    break
                cost = 2 + best[index + length]
                if cost < best[index]:
                    best[index] = cost
                    choice[index] = ("match", length, distance)

    out = bytearray()
    index = 0

    while index < n:
        kind, length, distance = choice[index]

        if kind == "lit":
            out.append(length - 1)
            out.extend(data[index:index + length])
        else:
            out.append(
                0x80
                + (length - 3) * divisor
                + (distance - 1) // 0x100
            )
            out.append((distance - 1) & 0xFF)

        index += length

    return bytes(out)


def compress_block(data, key):
    payload = compress_payload(data, COMPRESSION_TYPES[key])
    return (
        key.to_bytes(2, "little")
        + bytes([len(data) >> 8, len(data) & 0xFF])
        + payload
    )


def read_lines(path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    if len(rows) != 13:
        raise ValueError("Expected exactly 13 opening rows")

    result = []
    for expected, row in enumerate(rows, 1):
        if int(row["line"]) != expected:
            raise ValueError("Opening line numbers must run from 1 to 13")
        result.append(row["text"])

    if result[0] != "":
        raise ValueError(
            "Line 1 must remain blank because it uses the special 01 02 record"
        )

    return result


def read_credits(path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    if len(rows) != 4:
        raise ValueError("Expected exactly four startup credit lines")

    result = []
    for expected, row in enumerate(rows, 1):
        if int(row["line"]) != expected:
            raise ValueError("Credit line numbers must run from 1 to 4")
        result.append(row["text"])

    return result


def encode_char(ch):
    if ch in "éÉèÈêÊ":
        return ord("e")
    if ch == "'":
        return 0x5E
    if ch == ":":
        return 0x5F
    if ch == ".":
        return 0x7B
    if ch == ",":
        return 0x7C
    if ch == " ":
        return 0x20
    if ch.isascii() and ch.isalpha():
        return ord(ch.lower())
    raise ValueError(f"Unsupported opening character {ch!r}")


def encode_line_compact(line, compact_remaining):
    """
    Encode one visible line.

    Exactly seven occurrences of the visible pair "e " are replaced, in
    reading order across the whole prologue, with byte $02. The renderer
    expands $02 back to an E tile followed by a blank tile.

    Literal "..." stays three literal period bytes.
    """
    out = bytearray()
    i = 0
    used = 0

    while i < len(line):
        if (
            compact_remaining > 0
            and line[i:i+2].lower() == "e "
        ):
            out.append(COMPACT_E_SPACE_MARKER)
            compact_remaining -= 1
            used += 1
            i += 2
            continue

        out.append(encode_char(line[i]))
        i += 1

    return bytes(out), compact_remaining, used


def accents(line):
    result = []
    for pos, ch in enumerate(line):
        if ch in "éÉ":
            result.append((pos, ACUTE_TILE_CODE))
        elif ch in "èÈ":
            result.append((pos, GRAVE_TILE_CODE))
        elif ch in "êÊ":
            result.append((pos, CIRC_TILE_CODE))
    return result


def find_original_prologue(arr):
    marker = b"darkness sweeps the"
    p = arr.find(marker)
    if p < 0:
        raise ValueError("US opening text signature not found")

    start = p - 3
    q = start

    for index in range(13):
        expected = b"\x01\x02" if index == 0 else b"\x01\x00"
        if arr[q:q+2] != expected:
            raise ValueError(f"Unexpected US opening record {index + 1}")
        end = arr.find(b"\x00", q + 3)
        if end < 0:
            raise ValueError("Unterminated US opening record")
        q = end + 1

    if q - start != 332:
        raise ValueError(
            f"Unexpected US 13-record area: {q-start} bytes instead of 332"
        )

    # These two records are part of the scrolling termination behavior.
    if arr[q:q+8] != bytes.fromhex("01 00 01 00 01 00 01 00"):
        raise ValueError("Expected two post-scroll blank records")

    return start, q, q + 8


def build_prologue(arr, lines):
    start, end, technical_blank_end = find_original_prologue(arr)

    blob = bytearray()
    compact_remaining = COMPACT_E_SPACE_COUNT
    report = []

    for index, line in enumerate(lines):
        width = len(line)
        if width > 27:
            raise ValueError(
                f"Line {index + 1} is {width} cells wide (max 27)"
            )

        indent = (32 - width) // 2

        encoded, compact_remaining, used_compact = encode_line_compact(
            line, compact_remaining
        )

        accent_list = accents(line)

        if index == 0:
            if line or accent_list:
                raise ValueError("Special first record must be empty")
            prefix = b"\x01\x02"
        elif accent_list:
            by_x = {
                indent + pos: tile
                for pos, tile in accent_list
            }
            first, last = min(by_x), max(by_x)
            prefix = bytes(
                [first]
                + [by_x.get(x, BLANK_TILE_CODE)
                   for x in range(first, last + 1)]
                + [0]
            )
        else:
            prefix = b"\x01\x00"

        record = prefix + bytes([indent]) + encoded + b"\x00"
        blob.extend(record)

        report.append(
            (index + 1, width, len(encoded), indent,
             len(prefix), len(record), used_compact, line)
        )

    if compact_remaining != 0:
        raise ValueError(
            f"Only {COMPACT_E_SPACE_COUNT-compact_remaining} of "
            f"{COMPACT_E_SPACE_COUNT} compact markers were used"
        )

    if len(blob) != 332:
        raise ValueError(
            f"Final 13-record block must be exactly 332 bytes; "
            f"found {len(blob)}"
        )

    out = bytearray(arr)
    out[start:end] = blob

    # Critical: preserve the two technical blank records byte-for-byte.
    if out[end:technical_blank_end] != arr[end:technical_blank_end]:
        raise AssertionError("Post-scroll blank records moved or changed")

    return bytes(out), report, start, end, technical_blank_end


def encode_credit_text(text):
    out = bytearray()

    for ch in text:
        if ch == " ":
            out.append(0x20)
        elif ch == ".":
            out.append(0x7B)
        elif ch == ",":
            out.append(0x7C)
        elif ch == ":":
            out.append(0x5F)
        elif ch == "'":
            out.append(0x5E)
        elif ch.isascii() and ch.isalpha():
            out.append(ord(ch.lower()))
        else:
            raise ValueError(f"Unsupported startup-credit character {ch!r}")

    return bytes(out)


def patch_startup_credits(arrangement, credits):
    signatures = [
        b"\x06programmed by nasir\x00",
        b"\x06composed by h\x7Bkikuta\x00",
        b"\x06directed by k\x7Bishii\x00",
        b"\x06produced by h\x7Btanaka\x00",
    ]

    start = arrangement.find(signatures[0])
    if start < 0:
        raise ValueError("Could not locate startup credits")

    original = b"".join(signatures)
    if arrangement[start:start+len(original)] != original:
        raise ValueError("Unexpected US startup-credit layout")

    replacement = bytearray()

    for text in credits:
        replacement.append(0x06)
        replacement.extend(encode_credit_text(text))
        replacement.append(0x00)

    if len(replacement) != len(original):
        raise ValueError(
            "Startup credits must preserve their original total length"
        )

    return (
        arrangement[:start]
        + bytes(replacement)
        + arrangement[start+len(original):]
    )


def encode_4bpp_tile(px):
    out = bytearray(32)

    for y in range(8):
        planes = [0, 0, 0, 0]

        for x in range(8):
            value = px[y][x]
            bit = 7 - x
            for plane in range(4):
                if value & (1 << plane):
                    planes[plane] |= 1 << bit

        out[y*2] = planes[0]
        out[y*2+1] = planes[1]
        out[16+y*2] = planes[2]
        out[16+y*2+1] = planes[3]

    return bytes(out)


def load_font_png(path, original_font):
    image = Image.open(path).convert("RGB")

    if image.size != (128, 16):
        raise ValueError("opening_font.png must be exactly 128x16")

    tiles = bytearray()

    for tile_index in range(32):
        tx = (tile_index % 16) * 8
        ty = (tile_index // 16) * 8
        px = [[0] * 8 for _ in range(8)]

        for y in range(8):
            for x in range(8):
                r, g, b = image.getpixel((tx+x, ty+y))
                if not (r == g == b and r % 17 == 0):
                    raise ValueError(
                        "opening_font.png must use grayscale "
                        "values 0,17,34,...,255"
                    )
                px[y][x] = r // 17

        tiles.extend(encode_4bpp_tile(px))

    result = bytes(tiles)

    if len(result) != 0x400:
        raise AssertionError("Unexpected encoded font size")

    # A-Z must remain byte-identical to the original US opening font.
    for idx in range(1, 27):
        if (
            result[idx*32:(idx+1)*32]
            != original_font[idx*32:(idx+1)*32]
        ):
            raise ValueError(
                f"opening_font.png changes alphabet tile {idx:02X}"
            )

    return result


def build_renderer_helper():
    """
    Return the 65C816 helper called by the title renderer.

    $02 expands to:
        E tile ($65)
        blank tile ($60)

    Every other byte follows the stock behavior.
    """
    code = bytearray()
    labels = {}
    fixups = []

    def emit(*values):
        code.extend(values)

    def label(name):
        labels[name] = len(code)

    def branch(opcode, name):
        emit(opcode, 0)
        fixups.append((len(code) - 1, name))

    # CMP #$02 ; BEQ e_space
    emit(0xC9, COMPACT_E_SPACE_MARKER)
    branch(0xF0, "e_space")

    # Stock behavior: space maps to blank tile; other bytes pass through.
    emit(0xC9, 0x20)
    branch(0xD0, "normal")
    emit(0xA9, 0x60)

    label("normal")
    emit(0x99, 0x00, 0x00)  # STA $0000,Y
    emit(0xC8, 0xC8)        # INY / INY
    emit(0xE6, 0x02)        # INC $02
    emit(0x6B)              # RTL

    label("e_space")
    emit(0xA9, 0x65)        # E tile
    emit(0x99, 0x00, 0x00)
    emit(0xC8, 0xC8)
    emit(0xA9, 0x60)        # blank tile
    emit(0x99, 0x00, 0x00)
    emit(0xC8, 0xC8)
    emit(0xE6, 0x02)
    emit(0xE6, 0x02)
    emit(0x6B)

    for pos, name in fixups:
        rel = labels[name] - (pos + 1)
        if not -128 <= rel <= 127:
            raise AssertionError("Helper branch out of range")
        code[pos] = rel & 0xFF

    return bytes(code)


def build_title_code(code):
    if (
        code[RENDERER_HOOK_OFFSET:
             RENDERER_HOOK_OFFSET+len(RENDERER_ORIGINAL)]
        != RENDERER_ORIGINAL
    ):
        raise ValueError("Unexpected title renderer signature")

    if code[0x0843:0x0845] != bytes.fromhex("f0 0f"):
        raise ValueError("Unexpected renderer terminator branch")

    if (
        code[ARR_LOADER_OFFSET:
             ARR_LOADER_OFFSET+len(ARR_LOADER_ORIGINAL)]
        != ARR_LOADER_ORIGINAL
    ):
        raise ValueError("Unexpected title-arrangement loader signature")

    out = bytearray(code)

    out[
        RENDERER_HOOK_OFFSET:
        RENDERER_HOOK_OFFSET+len(RENDERER_HOOK)
    ] = RENDERER_HOOK

    out[
        ARR_LOADER_OFFSET:
        ARR_LOADER_OFFSET+len(ARR_LOADER_RELOCATED)
    ] = ARR_LOADER_RELOCATED

    return bytes(out)


def update_checksum(rom):
    rom[0xFFDC:0xFFE0] = b"\xFF\xFF\x00\x00"
    chk = sum(rom) & 0xFFFF
    rom[0xFFDC:0xFFE0] = struct.pack("<HH", chk ^ 0xFFFF, chk)
    return chk


def make_ips(original, modified):
    """
    Create an IPS patch, treating bytes beyond the original ROM as zero.

    This keeps the expanded area sparse: only actual non-zero/new data is
    emitted, plus the explicit ROM-size/header changes.
    """
    out = bytearray(b"PATCH")
    i = 0

    while i < len(modified):
        old_byte = original[i] if i < len(original) else 0

        if old_byte == modified[i]:
            i += 1
            continue

        start = i
        chunk = bytearray()

        while i < len(modified) and len(chunk) < 0xFFFF:
            old_byte = original[i] if i < len(original) else 0
            if old_byte == modified[i]:
                break
            chunk.append(modified[i])
            i += 1

        out.extend(start.to_bytes(3, "big"))
        out.extend(len(chunk).to_bytes(2, "big"))
        out.extend(chunk)

    # Force the IPS result to the full expanded size even when the final
    # bytes are zero. A one-byte zero record at the last ROM offset is safe
    # and makes standalone patchers produce an exact 3 MiB file.
    if len(modified) > len(original):
        out.extend((len(modified) - 1).to_bytes(3, "big"))
        out.extend((1).to_bytes(2, "big"))
        out.append(modified[-1])

    out.extend(b"EOF")
    return bytes(out)


def apply_ips(base, patch):
    if not patch.startswith(b"PATCH"):
        raise ValueError("Not an IPS patch")

    out = bytearray(base)
    p = 5

    while patch[p:p+3] != b"EOF":
        offset = int.from_bytes(patch[p:p+3], "big")
        p += 3
        size = int.from_bytes(patch[p:p+2], "big")
        p += 2

        if size:
            data = patch[p:p+size]
            p += size
        else:
            rle_size = int.from_bytes(patch[p:p+2], "big")
            p += 2
            value = patch[p]
            p += 1
            data = bytes([value]) * rle_size

        end = offset + len(data)
        if len(out) < end:
            out.extend(b"\x00" * (end - len(out)))

        out[offset:end] = data

    return bytes(out)


def main():
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Build the standalone French opening patch.")
    parser.add_argument("rom", type=Path, help="clean unheadered Secret of Mana (USA) ROM")
    parser.add_argument("-o", "--output-dir", type=Path, default=root / "build", help="output directory")
    parser.add_argument("--text", type=Path, default=root / "assets" / "opening_text.csv")
    parser.add_argument("--credits", type=Path, default=root / "assets" / "opening_credits.csv")
    parser.add_argument("--font", type=Path, default=root / "assets" / "opening_font.png")
    args = parser.parse_args()

    src = args.rom
    text_path = args.text
    credits_path = args.credits
    font_path = args.font
    out_dir = args.output_dir

    original = bytearray(src.read_bytes())

    if (
        len(original) != BASE_ROM_SIZE
        or sha1(original) != EXPECTED_US_SHA1
    ):
        raise SystemExit(
            "Wrong ROM. Use the unheadered US ROM with SHA-1 "
            + EXPECTED_US_SHA1
        )

    lines = read_lines(text_path)
    credits = read_credits(credits_path)

    code, code_capacity, code_key = decompress_block(
        original, TITLE_CODE_ROM
    )
    arr, _, arr_key = decompress_block(original, TITLE_ARR_ROM)
    font, font_capacity, font_key = decompress_block(
        original, TITLE_FONT_ROM
    )

    helper = build_renderer_helper()

    new_code = build_title_code(code)

    new_arr, layout, prologue_start, prologue_end, technical_blank_end = (
        build_prologue(arr, lines)
    )

    new_arr = patch_startup_credits(new_arr, credits)

    if new_arr.count(US_YEAR) != 2:
        raise ValueError("Unexpected copyright-year references")

    new_arr = new_arr.replace(US_YEAR, FR_STYLE_1993)

    new_font = load_font_png(font_path, font)

    code_cmp = compress_block(new_code, code_key)
    arr_cmp = compress_block(new_arr, arr_key)
    font_cmp = compress_block(new_font, font_key)

    # Keep the relocated arrangement and compact-marker helper disjoint.
    if RELOCATED_ARR_ROM + len(arr_cmp) > CUSTOM_CODE_ROM:
        raise ValueError("Relocated arrangement overlaps the opening helper at $EE:9000")
    if CUSTOM_CODE_ROM + len(helper) > 0x2F0000:
        raise ValueError("Opening helper exceeds its reserved $EE:9000 allocation")

    if len(code_cmp) > code_capacity:
        raise ValueError(
            f"Title code no longer fits: {len(code_cmp)} > {code_capacity}"
        )

    if len(font_cmp) > font_capacity:
        raise ValueError(
            f"Opening font no longer fits: {len(font_cmp)} > {font_capacity}"
        )

    if RELOCATED_ARR_ROM + len(arr_cmp) > EXPANDED_ROM_SIZE:
        raise ValueError("Relocated arrangement exceeds expanded ROM")

    rom = bytearray(original)
    rom.extend(b"\x00" * (EXPANDED_ROM_SIZE - len(rom)))

    # 3 MiB / expanded-ROM size header used by the validated tests.
    rom[0xFFD7] = 0x0C

    rom[
        TITLE_CODE_ROM:TITLE_CODE_ROM+code_capacity
    ] = code_cmp + b"\xFF" * (code_capacity - len(code_cmp))

    rom[
        TITLE_FONT_ROM:TITLE_FONT_ROM+font_capacity
    ] = font_cmp + b"\xFF" * (font_capacity - len(font_cmp))

    # Keep the original arrangement block untouched. The modified full
    # arrangement lives only in expanded space.
    rom[
        RELOCATED_ARR_ROM:RELOCATED_ARR_ROM+len(arr_cmp)
    ] = arr_cmp

    rom[
        CUSTOM_CODE_ROM:CUSTOM_CODE_ROM+len(helper)
    ] = helper

    checksum = update_checksum(rom)

    # Structural validation.
    if decompress_block(rom, TITLE_CODE_ROM)[0] != new_code:
        raise AssertionError("Title-code round trip failed")

    if decompress_block(rom, TITLE_FONT_ROM)[0] != new_font:
        raise AssertionError("Opening-font round trip failed")

    if decompress_block(rom, RELOCATED_ARR_ROM)[0] != new_arr:
        raise AssertionError("Relocated-arrangement round trip failed")

    if rom[TITLE_ARR_ROM:TITLE_ARR_ROM+16] != original[
        TITLE_ARR_ROM:TITLE_ARR_ROM+16
    ]:
        raise AssertionError("Original arrangement block was modified")

    # Verify literal "..." in the final stored prologue. No $01 ellipsis
    # marker is used by this final version.
    rendered_arr = decompress_block(rom, RELOCATED_ARR_ROM)[0]
    masamune = b"masamune"
    m = rendered_arr.find(masamune)
    if m < 0 or rendered_arr[m+8:m+11] != b"\x7B\x7B\x7B":
        raise AssertionError("Masamune... is not stored as three literal periods")

    # Technical post-scroll blanks must survive exactly.
    if rendered_arr[prologue_end:technical_blank_end] != bytes.fromhex(
        "01 00 01 00 01 00 01 00"
    ):
        raise AssertionError("Post-scroll blank records changed")

    patch = make_ips(original, rom)

    if apply_ips(original, patch) != bytes(rom):
        raise AssertionError("IPS self-application failed")

    out_dir.mkdir(parents=True, exist_ok=True)
    rom_path = out_dir / "Secret of Mana (USA) - French Opening Final.sfc"
    ips_path = out_dir / "patch.ips"
    layout_path = out_dir / "layout.txt"

    rom_path.write_bytes(rom)
    ips_path.write_bytes(patch)

    with layout_path.open("w", encoding="utf-8") as f:
        for row in layout:
            (
                number, width, stored, indent,
                prefix_size, record_size, compact_used, text
            ) = row
            f.write(
                f"{number:02d}: visible={width:2d} stored={stored:2d} "
                f"indent={indent:2d} prefix={prefix_size:2d} "
                f"record={record_size:2d} compact02={compact_used}  "
                f"{text}\n"
            )

    print("ROM:", rom_path)
    print("ROM SHA-1:", sha1(rom))
    print("IPS:", ips_path)
    print("IPS SHA-1:", sha1(patch))
    print("Arrangement:", len(arr_cmp), "bytes compressed")
    print("Title code:", len(code_cmp), "/", code_capacity)
    print("Opening font:", len(font_cmp), "/", font_capacity)
    print("Checksum:", f"{checksum:04X}")


if __name__ == "__main__":
    main()
