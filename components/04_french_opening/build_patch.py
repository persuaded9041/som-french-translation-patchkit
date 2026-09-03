#!/usr/bin/env python3
"""
Build the final French opening patch for Secret of Mana (USA).

The patch keeps the fixed-width opening renderer and remains independent from
the intro VWF component.

Main changes:
- 12 visible French prologue lines, preceded by the required blank startup row;
- original accent-overlay system: $7D acute, $7E grave, $7F circumflex;
- compact $02 markers, each rendered as "e " (two cells), chosen as needed to preserve the stock prologue block size;
- literal three-period sequence for "Masamune...";
- French startup credits sourced from CSV, including a dedicated one-cell É at $7A;
- original copyright-year tile workaround;
- title arrangement relocated to ROM 0x2E8000 / CPU $EE:8000;
- 3 MiB ROM expansion.

Base ROM:
Secret of Mana (USA), headerless
"""

from pathlib import Path
import csv
import sys
import argparse
from PIL import Image

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from shared.rom import validate_base_rom, update_checksum, expand_rom, EXPANDED_SIZE, ROM_SIZE_OFFSET  # noqa: E402
from shared.ips import apply_ips, make_ips  # noqa: E402

TITLE_CODE_ROM = 0x077C00
TITLE_ARR_ROM = 0x07B480
TITLE_FONT_ROM = 0x07C1C0

CUSTOM_CODE_ROM = 0x2E9000

RELOCATED_ARR_ROM = 0x2E8000

ACUTE_TILE_CODE = 0x7D
GRAVE_TILE_CODE = 0x7E
CIRC_TILE_CODE = 0x7F
BLANK_TILE_CODE = 0x60
COMPACT_E_SPACE_MARKER = 0x02
CREDIT_E_ACUTE_TILE_CODE = 0x7A  # Z slot, unused by the current French opening

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

    if len(rows) != 5:
        raise ValueError("Expected exactly five startup credit lines")

    result = []
    for expected, row in enumerate(rows, 1):
        if int(row["line"]) != expected:
            raise ValueError("Credit line numbers must run from 1 to 5")
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

    As many occurrences of the visible pair "e " as required are replaced,
    in reading order across the whole prologue, with byte $02. The renderer
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

    def build_blob(compact_count):
        blob = bytearray()
        compact_remaining = compact_count
        report = []

        for index, line in enumerate(lines):
            width = len(line)
            if width > 27:
                raise ValueError(f"Line {index + 1} is {width} cells wide (max 27)")

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
                by_x = {indent + pos: tile for pos, tile in accent_list}
                first, last = min(by_x), max(by_x)
                prefix = bytes(
                    [first]
                    + [by_x.get(x, BLANK_TILE_CODE) for x in range(first, last + 1)]
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
        return bytes(blob), report, compact_remaining

    uncompressed_blob, _, _ = build_blob(0)
    compact_count = len(uncompressed_blob) - 332
    if compact_count < 0:
        raise ValueError(
            f"Final 13-record block is already only {len(uncompressed_blob)} bytes; "
            "translation must be adjusted to preserve the 332-byte layout"
        )

    blob, report, compact_remaining = build_blob(compact_count)
    if compact_remaining:
        raise ValueError(
            f"Need {compact_count} compact 'e ' markers to preserve the 332-byte layout, "
            f"but only {compact_count - compact_remaining} are available"
        )
    if len(blob) != 332:
        raise ValueError(f"Final 13-record block must be exactly 332 bytes; found {len(blob)}")

    out = bytearray(arr)
    out[start:end] = blob
    if out[end:technical_blank_end] != arr[end:technical_blank_end]:
        raise AssertionError("Post-scroll blank records moved or changed")

    return bytes(out), report, start, end, technical_blank_end

def encode_credit_text(text):
    out = bytearray()

    for ch in text:
        if ch in "éÉ":
            out.append(CREDIT_E_ACUTE_TILE_CODE)
        elif ch == " ":
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


TEXT_TABLE_BASE_OFFSET = 0x09F8
CREDIT_LIST_START_SIGNATURE = bytes.fromhex("a2 be 01 86 08")
CREDIT_DWELL_SIGNATURE = bytes.fromhex("a2 f0 00 20 00 8b")
CREDIT_DWELL_FRAMES = 180


def append_startup_credit_list(arrangement, credits):
    """Append a private 5-credit list without moving any stock arrangement data.

    The title text renderer addresses records as X offsets relative to
    $7E:59F8 (arrangement offset $09F8).  Appending the list preserves every
    existing arrangement offset and gives us a safe new X value.

    Each record is: indent byte $06, encoded text, $00 terminator.
    A final standalone $00 is the list sentinel used by the stock loop.
    """
    blob = bytearray()
    for text in credits:
        blob.append(0x06)
        blob.extend(encode_credit_text(text))
        blob.append(0x00)
    blob.append(0x00)

    start_offset = len(arrangement)
    relative_x = start_offset - TEXT_TABLE_BASE_OFFSET
    if not 0 <= relative_x <= 0xFFFF:
        raise ValueError("Appended startup-credit list is outside renderer range")

    return arrangement + bytes(blob), relative_x, bytes(blob)


def patch_startup_credit_sequence(code, relative_x):
    """Redirect the stock credit loop and shorten the real visible dwell.

    Stock credit routine (CPU $8DD0 area):
      - X=$01BE selects the original 4-credit list.
      - each record is faded in (~31 frames), held for $00F0 = 240 frames,
        then faded out (~31 frames).

    With five credits, a 180-frame hold keeps the complete section almost
    exactly the same duration:
        4 * (31 + 240 + 31) = 1208 frames
        5 * (31 + 180 + 31) = 1210 frames
    """
    out = bytearray(code)

    pos = out.find(CREDIT_LIST_START_SIGNATURE)
    if pos < 0 or out.find(CREDIT_LIST_START_SIGNATURE, pos + 1) >= 0:
        raise ValueError("Startup-credit list pointer signature missing/ambiguous")
    out[pos:pos+3] = bytes((0xA2, relative_x & 0xFF, relative_x >> 8))

    dwell = out.find(CREDIT_DWELL_SIGNATURE)
    if dwell < 0 or out.find(CREDIT_DWELL_SIGNATURE, dwell + 1) >= 0:
        raise ValueError("Startup-credit dwell signature missing/ambiguous")
    out[dwell:dwell+3] = bytes((0xA2, CREDIT_DWELL_FRAMES & 0xFF, CREDIT_DWELL_FRAMES >> 8))

    return bytes(out)


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

    # A-Y must remain byte-identical to the original US opening font.
    # Z ($7A) is intentionally replaced by the one-cell startup-credit É
    # directly in opening_font.png.
    for idx in range(1, 26):
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


def main():
    root = ROOT
    parser = argparse.ArgumentParser(description="Build the standalone French opening patch.")
    parser.add_argument("rom", type=Path, help="clean unheadered Secret of Mana (USA) ROM")
    parser.add_argument("-o", "--output", type=Path, default=root / "build" / "patch.ips", help="output IPS path")
    parser.add_argument("--patched-rom", type=Path, help="optional patched ROM output")
    parser.add_argument("--layout", type=Path, help="optional generated layout report")
    parser.add_argument("--text", type=Path, default=root / "assets" / "opening_text.csv")
    parser.add_argument("--credits", type=Path, default=root / "assets" / "opening_credits.csv")
    parser.add_argument("--font", type=Path, default=root / "assets" / "opening_font.png")
    args = parser.parse_args()

    src = args.rom
    text_path = args.text
    credits_path = args.credits
    font_path = args.font
    output_path = args.output

    original = bytearray(src.read_bytes())

    validate_base_rom(original)

    lines = read_lines(text_path)
    credits = read_credits(credits_path)
    if any("z" in text.lower() for text in lines + credits):
        raise ValueError("Opening tile $7A is reserved for startup-credit É; literal Z is unavailable")

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


    if new_arr.count(US_YEAR) != 2:
        raise ValueError("Unexpected copyright-year references")

    new_arr = new_arr.replace(US_YEAR, FR_STYLE_1993)

    # Append the five-credit list only after all fixed-offset arrangement
    # edits. No existing byte is inserted/moved.
    new_arr, credit_relative_x, credit_blob = append_startup_credit_list(
        new_arr, credits
    )
    new_code = patch_startup_credit_sequence(new_code, credit_relative_x)

    new_font = load_font_png(font_path, font)
    if new_font[26*32:27*32] == font[26*32:27*32]:
        raise ValueError(
            "opening_font.png tile $7A must contain the dedicated startup-credit É"
        )

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

    if RELOCATED_ARR_ROM + len(arr_cmp) > EXPANDED_SIZE:
        raise ValueError("Relocated arrangement exceeds expanded ROM")

    rom = expand_rom(original)

    # 3 MiB / expanded-ROM size header.
    rom[ROM_SIZE_OFFSET] = 0x0C

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

    rendered_arr = decompress_block(rom, RELOCATED_ARR_ROM)[0]
    appended_start = TEXT_TABLE_BASE_OFFSET + credit_relative_x
    if rendered_arr[appended_start:appended_start+len(credit_blob)] != credit_blob:
        raise AssertionError("Appended five-credit list changed during build")

    if rom[TITLE_ARR_ROM:TITLE_ARR_ROM+16] != original[
        TITLE_ARR_ROM:TITLE_ARR_ROM+16
    ]:
        raise AssertionError("Original arrangement block was modified")

    # Verify literal "..." in the final stored prologue. No $01 ellipsis
    # marker is used by this final version.
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

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(patch)
    if args.patched_rom:
        args.patched_rom.parent.mkdir(parents=True, exist_ok=True)
        args.patched_rom.write_bytes(rom)
        print("ROM:", args.patched_rom)

    if args.layout:
        args.layout.parent.mkdir(parents=True, exist_ok=True)
        with args.layout.open("w", encoding="utf-8") as f:
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

    print("IPS:", output_path)
    print("Arrangement:", len(arr_cmp), "bytes compressed")
    print("Title code:", len(code_cmp), "/", code_capacity)
    print("Opening font:", len(font_cmp), "/", font_capacity)
    print("Checksum:", f"{checksum:04X}")


if __name__ == "__main__":
    main()
