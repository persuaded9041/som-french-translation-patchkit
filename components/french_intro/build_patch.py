#!/usr/bin/env python3
"""Build the standalone French new-game intro payload IPS patch.

This component owns only the French event-$0400 payload side of the intro:
translation binding, line/page metadata, private intro DTE, French glyphs, and
the stock-event relocation required by the larger translated event. The VWF
renderer/parser runtime is owned by `vwf_intro`.
"""

from __future__ import annotations

from pathlib import Path
import argparse
import json
import struct
import sys

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from shared.core.asm import MiniAssembler, lo16, lo24  # noqa: E402
from shared.dialogue.codec import parse_event  # noqa: E402
from shared.charset import (  # noqa: E402
    CHAR_TO_CODE,
    FULL_DTE_THRESHOLD,
    FULL_FRENCH_CHARS,
    glyph_bytes,
)
from shared.text.intro_event import load_document as load_intro_source, make_document as make_intro_source  # noqa: E402
from shared.core.ips import make_ips  # noqa: E402
from shared.core.rom import update_checksum, validate_base_rom  # noqa: E402
from shared.text.translation_json import load_translation, require  # noqa: E402
from shared.extracted.assets import load_or_extract_intro_event  # noqa: E402

DTE_COMPARE_IMMEDIATE_OFFSET = 0x0016F6
DTE_STOCK_THRESHOLD = 0xD3
DTE_NEW_THRESHOLD = FULL_DTE_THRESHOLD
FONT_BASE = 0x12DC00
FRENCH_CHARS = FULL_FRENCH_CHARS
ACCENT_FIRST = min(CHAR_TO_CODE[ch] for ch in FRENCH_CHARS)

ASCII_TO_SOM = {" ": 0x80}
ASCII_TO_SOM.update({chr(ord("a") + i): 0x81 + i for i in range(26)})
ASCII_TO_SOM.update({chr(ord("A") + i): 0x9B + i for i in range(26)})
ASCII_TO_SOM.update({".": 0xBF, ",": 0xC0, "'": 0xC2})
ASCII_TO_SOM.update({ch: CHAR_TO_CODE[ch] for ch in FRENCH_CHARS})

INTRO_EVENT_START = 0x0C02
INTRO_EVENT_END_STOCK = 0x0E44
INTRO_EVENT_FILE = 0x0A0000 + INTRO_EVENT_START
EVENT_POINTER_TABLE = 0x09F800
RELOC_FIRST_EVENT = 0x0401
RELOC_LAST_EVENT = 0x040F
RELOC_SOURCE_START = INTRO_EVENT_END_STOCK
RELOC_SOURCE_END = 0x0E8C
RELOC_TARGET_START = 0xFF70
RELOC_TARGET_LIMIT = 0xFFC0  # intro_skip begins here

# Runtime-validated payload endpoint from the pre-split Round 75/76 component.
VALIDATED_FRENCH_INTRO_END = 0x0E8B

DTE_LOADER_CPU = 0xC74C40
DTE_LOADER_FILE = 0x074C40
DTE_LOADER_LIMIT = 0x074C80  # shared VWF config begins here
CUSTOM_DTE_CPU = 0xC74D00
CUSTOM_DTE_FILE = 0x074D00
CUSTOM_DTE_LIMIT = 0x074D40  # relocated GAME FILE begins here
STOCK_DTE_CPU = 0xC77299

LINE_CHAR_LIMIT = 38
LAYOUT_METADATA_FILE = ROOT / "assets" / "text" / "intro_layout.json"

SUBPAGE_WAIT_BY_INDEX = {1: 0x18, 2: 0x1C, 3: 0x18, 4: 0x12}
PARAGRAPH_END_WAIT_BY_INDEX = {
    0: (0x30, 0x18), 1: (0x38, 0x1C), 2: (0x40, 0x18),
    3: (0x38, 0x14), 4: (0x30, 0x12),
}
INTRO_TEXT_RUNS = (
    (0x0C0D, 0x0C4B),
    (0x0C59, 0x0CA5),
    (0x0CB3, 0x0CFE),
    (0x0D0C, 0x0D4E),
    (0x0D5C, 0x0DA4),
    (0x0DAB, 0x0DF6),
    (0x0E00, 0x0E1F),
    (0x0E21, 0x0E38),
)


def load_french_intro_texts(base: bytes) -> tuple[list[str], list[str]]:
    source_document = load_or_extract_intro_event(base, PROJECT_ROOT / "assets" / "intro_event.json")
    canonical = make_intro_source(parse_event(base, 0x0400))
    if source_document != canonical:
        raise SystemExit("intro_event.json differs from a fresh clean-ROM extraction")
    try:
        translations = load_translation(
            PROJECT_ROOT / "translations" / "intro_event_french.json",
            source_document,
            source_asset="intro_event.json",
        )
        ids = [entry["id"] for entry in source_document["entries"]]
        texts = require(translations, ids, context="French intro event $0400")
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    return ids, texts


def load_layout_metadata(text_ids: list[str], french_texts: list[str]) -> list[list[str]]:
    try:
        metadata = json.loads(LAYOUT_METADATA_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Cannot read layout metadata: {exc}") from exc

    if metadata.get("format_version") != 2:
        raise SystemExit("Unsupported intro layout metadata version")
    entries = metadata.get("entries")
    if not isinstance(entries, dict):
        raise SystemExit("intro_layout.json must contain an 'entries' object")
    if list(entries) != text_ids:
        raise SystemExit("intro_layout.json IDs/order must match assets/intro_event.json")

    result: list[list[str]] = []
    for text_id, source in zip(text_ids, french_texts, strict=True):
        normalized = " ".join(source.replace("\r", " ").replace("\n", " ").split())
        words = normalized.split(" ") if normalized else []
        page_spec = entries[text_id]
        if not isinstance(page_spec, list) or not page_spec:
            raise SystemExit(f"Intro text {text_id} has invalid page metadata")

        cursor = 0
        pages: list[str] = []
        for page_index, line_counts in enumerate(page_spec, 1):
            if not isinstance(line_counts, list) or not 1 <= len(line_counts) <= 3:
                raise SystemExit(f"Intro text {text_id} page {page_index} must contain 1-3 line counts")
            lines: list[str] = []
            for line_index, count in enumerate(line_counts, 1):
                if not isinstance(count, int) or count <= 0:
                    raise SystemExit(f"Intro text {text_id} page {page_index} line {line_index} has an invalid word count")
                word_end = cursor + count
                if word_end > len(words):
                    raise SystemExit(f"Intro text {text_id} layout consumes more words than its translation")
                line = " ".join(words[cursor:word_end])
                cursor = word_end
                if len(line) > LINE_CHAR_LIMIT:
                    raise SystemExit(
                        f"Intro text {text_id} page {page_index} line {line_index} exceeds "
                        f"{LINE_CHAR_LIMIT} visible characters ({len(line)})"
                    )
                lines.append(line)
            pages.append("\n".join(lines))

        if cursor != len(words):
            raise SystemExit(f"Intro text {text_id} layout consumes {cursor} of {len(words)} words")
        result.append(pages)
    return result


def encode_french(text: str) -> bytes:
    try:
        return bytes(0x7F if ch == "\n" else ASCII_TO_SOM[ch] for ch in text)
    except KeyError as exc:
        raise SystemExit(f"Unsupported French intro character: {exc.args[0]!r}") from exc


def choose_dte_pairs(encoded_texts: list[bytes], max_pairs: int = 0xFF - DTE_NEW_THRESHOLD):
    from collections import Counter

    sequences = [list(data) for data in encoded_texts]
    pairs: list[tuple[int, int]] = []
    for slot in range(max_pairs):
        counts = Counter()
        for seq in sequences:
            for left, right in zip(seq, seq[1:]):
                if left < 0x100 and right < 0x100 and left != 0x7F and right != 0x7F:
                    counts[(left, right)] += 1

        best = None
        best_count = 0
        for pair, _frequency in counts.most_common():
            non_overlapping = 0
            for seq in sequences:
                i = 0
                while i + 1 < len(seq):
                    if seq[i] == pair[0] and seq[i + 1] == pair[1]:
                        non_overlapping += 1
                        i += 2
                    else:
                        i += 1
            if non_overlapping > best_count:
                best, best_count = pair, non_overlapping

        if best is None or best_count < 2:
            break

        token = 0x100 + slot
        replaced: list[list[int]] = []
        for seq in sequences:
            out: list[int] = []
            i = 0
            while i < len(seq):
                if i + 1 < len(seq) and seq[i] == best[0] and seq[i + 1] == best[1]:
                    out.append(token)
                    i += 2
                else:
                    out.append(seq[i])
                    i += 1
            replaced.append(out)
        sequences = replaced
        pairs.append(best)

    compressed = [
        bytes(DTE_NEW_THRESHOLD + (value - 0x100) if value >= 0x100 else value for value in seq)
        for seq in sequences
    ]
    table = bytearray()
    for left, right in pairs:
        table += bytes((left, right))
    while len(table) < max_pairs * 2:
        table += bytes((ASCII_TO_SOM[" "], ASCII_TO_SOM[" "]))
    return compressed, bytes(table), pairs


def rebuild_intro_event(base: bytes, french_chunks: list[bytes]) -> bytes:
    stock = bytes(base[INTRO_EVENT_FILE : 0x0A0000 + INTRO_EVENT_END_STOCK])
    output = bytearray()
    cursor = INTRO_EVENT_START

    for index, ((start, end), translated) in enumerate(zip(INTRO_TEXT_RUNS, french_chunks, strict=True)):
        gap = bytearray(stock[cursor - INTRO_EVENT_START : start - INTRO_EVENT_START])
        if index:
            previous_index = index - 1
            if previous_index in PARAGRAPH_END_WAIT_BY_INDEX:
                stock_wait, new_wait = PARAGRAPH_END_WAIT_BY_INDEX[previous_index]
                if len(gap) < 2 or gap[0] != 0x28 or gap[1] != stock_wait:
                    raise SystemExit(
                        f"Expected WAIT ${stock_wait:02X} after intro part {previous_index + 1}, "
                        f"got: {gap[:4].hex(' ')}"
                    )
                gap[1] = new_wait
        output += gap
        if index == 7:
            output.append(0x7F)
        output += translated
        cursor = end

    output += stock[cursor - INTRO_EVENT_START :]
    return bytes(output)


def relocate_following_events(base: bytes, rom: bytearray) -> None:
    relocate_len = RELOC_SOURCE_END - RELOC_SOURCE_START
    source_file = 0x0A0000 + RELOC_SOURCE_START
    target_file = 0x0A0000 + RELOC_TARGET_START
    if RELOC_TARGET_START + relocate_len > RELOC_TARGET_LIMIT:
        raise SystemExit("Relocated intro-following events exceed the reserved CA:$FF70-$FFBF window")
    if any(value != 0xFF for value in rom[target_file : target_file + relocate_len]):
        raise SystemExit("Expected CA:$FF70 relocation area to be empty")
    rom[target_file : target_file + relocate_len] = rom[source_file : source_file + relocate_len]
    delta = RELOC_TARGET_START - RELOC_SOURCE_START
    for event_id in range(RELOC_FIRST_EVENT, RELOC_LAST_EVENT + 1):
        pointer_offset = EVENT_POINTER_TABLE + event_id * 2
        old_pointer = struct.unpack_from("<H", base, pointer_offset)[0]
        if not (RELOC_SOURCE_START <= old_pointer < RELOC_SOURCE_END):
            raise SystemExit(f"Unexpected event ${event_id:04X} pointer: ${old_pointer:04X}")
        struct.pack_into("<H", rom, pointer_offset, old_pointer + delta)


def assemble_dte_loader(intro_end_ptr: int) -> bytes:
    a = MiniAssembler(DTE_LOADER_CPU)
    a.emit(0xE2, 0x20)
    a.emit(0xAF, *lo24(0x001D03))
    a.emit(0xC9, 0xCA)
    a.rel8(0xD0, "stock8")
    a.emit(0xC2, 0x20)
    a.emit(0xAF, *lo24(0x001D01))
    a.emit(0xC9, *lo16(INTRO_EVENT_START))
    a.rel8(0x90, "stock16")
    a.emit(0xC9, *lo16(intro_end_ptr))
    a.rel8(0xB0, "stock16")
    a.emit(0x8A)
    a.emit(0x38)
    a.emit(0xE9, *lo16((DTE_NEW_THRESHOLD - 0xC3) * 2))
    a.emit(0xAA)
    a.emit(0xBF, *lo24(CUSTOM_DTE_CPU))
    a.emit(0x6B)
    a.label("stock8")
    a.emit(0xC2, 0x20)
    a.label("stock16")
    a.emit(0xBF, *lo24(STOCK_DTE_CPU))
    a.emit(0x6B)
    return a.resolve()


def load_french_glyphs() -> bytes:
    try:
        return glyph_bytes(FRENCH_CHARS)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc


def main(source_rom: Path, output_path: Path, patched_rom: Path | None = None) -> None:
    base = bytearray(source_rom.read_bytes())
    validate_base_rom(base)
    rom = bytearray(base)

    if rom[DTE_COMPARE_IMMEDIATE_OFFSET] != DTE_STOCK_THRESHOLD:
        raise SystemExit(f"Unexpected DTE threshold byte: {rom[DTE_COMPARE_IMMEDIATE_OFFSET]:02X}")
    rom[DTE_COMPARE_IMMEDIATE_OFFSET] = DTE_NEW_THRESHOLD

    french_glyphs = load_french_glyphs()
    glyph_start = FONT_BASE + (ACCENT_FIRST - 0x80) * 12
    rom[glyph_start : glyph_start + len(french_glyphs)] = french_glyphs

    text_ids, french_texts = load_french_intro_texts(base)
    paragraph_pages = load_layout_metadata(text_ids, french_texts)
    direct_pages = [encode_french(page) for pages in paragraph_pages for page in pages]
    compressed_pages, custom_dte, dte_pairs = choose_dte_pairs(direct_pages)

    compressed_chunks: list[bytes] = []
    page_cursor = 0
    for text_index, (text_id, pages) in enumerate(zip(text_ids, paragraph_pages, strict=True)):
        encoded_pages = compressed_pages[page_cursor : page_cursor + len(pages)]
        page_cursor += len(pages)
        if len(encoded_pages) == 1:
            compressed_chunks.append(encoded_pages[0])
            continue
        if len(encoded_pages) != 2 or text_index not in SUBPAGE_WAIT_BY_INDEX:
            raise SystemExit(f"Unexpected multi-page timing configuration for intro text {text_id}")
        separator = bytes((0x28, SUBPAGE_WAIT_BY_INDEX[text_index], 0x52))
        compressed_chunks.append(separator.join(encoded_pages))

    new_event = rebuild_intro_event(base, compressed_chunks)
    intro_end_ptr = INTRO_EVENT_START + len(new_event)
    if intro_end_ptr != VALIDATED_FRENCH_INTRO_END:
        raise SystemExit(
            f"French intro payload endpoint changed: expected ${VALIDATED_FRENCH_INTRO_END:04X}, "
            f"got ${intro_end_ptr:04X}; update/revalidate vwf_intro before accepting this change"
        )

    relocate_following_events(base, rom)
    rom[INTRO_EVENT_FILE : INTRO_EVENT_FILE + len(new_event)] = new_event

    dte_loader = assemble_dte_loader(intro_end_ptr)
    if DTE_LOADER_FILE + len(dte_loader) > DTE_LOADER_LIMIT:
        raise SystemExit("Intro DTE loader exceeds its reserved $C7:4C40-$4C7F window")
    if CUSTOM_DTE_FILE + len(custom_dte) > CUSTOM_DTE_LIMIT:
        raise SystemExit("Private intro DTE table exceeds its reserved $C7:4D00-$4D3F window")
    if any(value != 0xFF for value in rom[DTE_LOADER_FILE : DTE_LOADER_FILE + len(dte_loader)]):
        raise SystemExit("Expected free space for intro DTE loader is not empty")
    if any(value != 0xFF for value in rom[CUSTOM_DTE_FILE : CUSTOM_DTE_FILE + len(custom_dte)]):
        raise SystemExit("Expected free space for private intro DTE table is not empty")

    if rom[0x1719:0x171D] != bytes.fromhex("bf 99 72 c7"):
        raise SystemExit("Stock DTE table-load signature mismatch at ROM $001719")
    rom[0x1719:0x171D] = bytes([0x22, *lo24(DTE_LOADER_CPU)])
    rom[DTE_LOADER_FILE : DTE_LOADER_FILE + len(dte_loader)] = dte_loader
    rom[CUSTOM_DTE_FILE : CUSTOM_DTE_FILE + len(custom_dte)] = custom_dte

    checksum = update_checksum(rom)
    complement = checksum ^ 0xFFFF
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(make_ips(base, rom))
    if patched_rom:
        patched_rom.parent.mkdir(parents=True, exist_ok=True)
        patched_rom.write_bytes(rom)

    for text_id, pages in zip(text_ids, paragraph_pages, strict=True):
        lengths = [[len(line) for line in page.split("\n")] for page in pages]
        print(f"{text_id}: pages {lengths}")
    print(f"Private DTE pairs: {len(dte_pairs)}")
    print(f"French intro event: ${INTRO_EVENT_START:04X}-${intro_end_ptr:04X} ({len(new_event)} bytes)")
    print(f"Checksum: {checksum:04X}; complement: {complement:04X}")
    print(f"Patch written to: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the standalone French intro payload patch.")
    parser.add_argument("rom", type=Path, help="clean unheadered Secret of Mana (USA) ROM")
    parser.add_argument("-o", "--output", type=Path, default=ROOT / "build" / "patch.ips", help="output IPS path")
    parser.add_argument("--patched-rom", type=Path, help="optional patched ROM output")
    args = parser.parse_args()
    main(args.rom, args.output, args.patched_rom)
