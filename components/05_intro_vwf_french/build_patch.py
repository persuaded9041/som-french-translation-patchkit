#!/usr/bin/env python3
"""Build the French new-game intro VWF IPS patch.

French text comes from root translations/intro_event_french.json and is bound
to the clean-USA event-$0400 source by ROM-position IDs. Line/page breaks are
defined by numeric word counts in intro_layout.json.
"""

from __future__ import annotations

from pathlib import Path
import json
import struct
import sys
import argparse


# VWF code/data locations.
CODE_FILE = 0x074285
CODE_CPU = 0xC74285
WIDTH_CPU = 0xC74440

# Stock text/font locations.
DTE_COMPARE_IMMEDIATE_OFFSET = 0x0016F6
DTE_STOCK_THRESHOLD = 0xD3
FONT_BASE = 0x12DC00

# Direct character codes reserved for French glyphs.
ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
COMPONENT_08 = PROJECT_ROOT / "components" / "08_dialogue_text"
sys.path.insert(0, str(COMPONENT_08))
from shared.rom import validate_base_rom, update_checksum  # noqa: E402
from shared.ips import make_ips  # noqa: E402
from shared.intro_event_text import load_document as load_intro_source, make_document as make_intro_source  # noqa: E402
from shared.translation_json import load_translation, require  # noqa: E402
from dialogue_codec import parse_event  # noqa: E402
from shared.asm65816 import MiniAssembler, lo16, lo24  # noqa: E402
from shared.vwf_geometry import left_compact_glyph  # noqa: E402
from shared.vwf_metrics import apply_validated_framing, validated_advance  # noqa: E402
from shared.vwf_framing import (  # noqa: E402
    SHARED_FRAMING_CPU,
    validate_stock as validate_shared_framing_stock,
    install as install_shared_framing,
)
from shared.vwf_compositor import (  # noqa: E402
    validate_stock as validate_shared_compositor_stock,
    install as install_shared_compositor,
)
from shared.vwf_row_renderer import (  # noqa: E402
    ROW_RENDERER_CALL,
    validate_stock as validate_shared_row_renderer_stock,
    install as install_shared_row_renderer,
)
from shared.vwf_outline import (  # noqa: E402
    validate_stock as validate_shared_outline_stock,
    install as install_shared_outline,
)
from shared.vwf_text_buffer import (  # noqa: E402
    PARSER_WRITE_CPU,
    PARSER_WRITE_HELPER,
    validate_stock as validate_shared_text_buffer_stock,
    install_common as install_shared_text_buffer,
    enable_intro as enable_intro_private_buffer,
)
from shared.french_charset import (
    CHAR_TO_CODE,
    FIRST_CODE,
    FULL_DTE_THRESHOLD,
    FULL_FRENCH_CHARS,
    glyph_bytes,
)

DTE_NEW_THRESHOLD = FULL_DTE_THRESHOLD
ACCENT_FIRST = FIRST_CODE
FRENCH_CHARS = FULL_FRENCH_CHARS

ASCII_TO_SOM = {" ": 0x80}
ASCII_TO_SOM.update({chr(ord("a") + i): 0x81 + i for i in range(26)})
ASCII_TO_SOM.update({chr(ord("A") + i): 0x9B + i for i in range(26)})
ASCII_TO_SOM.update({".": 0xBF, ",": 0xC0, "'": 0xC2})
ASCII_TO_SOM.update(CHAR_TO_CODE)
INTRO_RENDER_CODES = frozenset(ASCII_TO_SOM.values())

INTRO_EVENT_START = 0x0C02
INTRO_EVENT_END_STOCK = 0x0E44
INTRO_EVENT_FILE = 0x0A0000 + INTRO_EVENT_START
EVENT_POINTER_TABLE = 0x09F800
RELOC_FIRST_EVENT = 0x0401
RELOC_LAST_EVENT = 0x040F
RELOC_SOURCE_START = 0x0E44
RELOC_SOURCE_END = 0x0E8C
RELOC_TARGET_START = 0xFF70
DTE_LOADER_CPU = 0xC74C40
DTE_LOADER_FILE = CODE_FILE + (DTE_LOADER_CPU - CODE_CPU)
CUSTOM_DTE_CPU = 0xC74D00
CUSTOM_DTE_FILE = CODE_FILE + (CUSTOM_DTE_CPU - CODE_CPU)
STOCK_DTE_CPU = 0xC77299
LINE_CHAR_LIMIT = 38
LAYOUT_METADATA_FILE = ROOT / "assets" / "text" / "intro_layout.json"



def load_french_intro_texts(base: bytes) -> tuple[list[str], list[str]]:
    source_document = load_intro_source(PROJECT_ROOT / "assets" / "intro_event.json")
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
    """Apply numeric line/page metadata to the root French intro translation."""
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
                    raise SystemExit(f"Intro text {text_id} page {page_index} line {line_index} exceeds {LINE_CHAR_LIMIT} visible characters ({len(line)})")
                lines.append(line)
            pages.append("\n".join(lines))

        if cursor != len(words):
            raise SystemExit(f"Intro text {text_id} layout consumes {cursor} of {len(words)} words")
        result.append(pages)
    return result

# Wait inserted between two pages of the same paragraph.
SUBPAGE_WAIT_BY_INDEX = {1: 0x18, 2: 0x1C, 3: 0x18, 4: 0x12}

# Stock/new WAIT after each paragraph. The command is stored in the gap before
# the following text run.
PARAGRAPH_END_WAIT_BY_INDEX = {
    0: (0x30, 0x18), 1: (0x38, 0x1C), 2: (0x40, 0x18),
    3: (0x38, 0x14), 4: (0x30, 0x12),
}


def encode_french(text: str) -> bytes:
    try:
        return bytes(0x7F if ch == "\n" else ASCII_TO_SOM[ch] for ch in text)
    except KeyError as exc:
        raise SystemExit(f"Unsupported French intro character: {exc.args[0]!r}") from exc


def choose_dte_pairs(encoded_texts: list[bytes], max_pairs: int = 0xFF - DTE_NEW_THRESHOLD):
    """Generate a non-recursive private DTE table for the translated intro only."""
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


def rebuild_intro_event(base: bytes, french_chunks: list[bytes]) -> bytes:
    """Replace the eight intro text runs and update paragraph-end waits."""
    stock = bytes(base[INTRO_EVENT_FILE : 0x0A0000 + INTRO_EVENT_END_STOCK])
    output = bytearray()
    cursor = INTRO_EVENT_START

    for index, ((start, end), translated) in enumerate(
        zip(INTRO_TEXT_RUNS, french_chunks)
    ):
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

        # Keep the stock WAIT $10 before the final run; start it on a new line.
        if index == 7:
            output.append(0x7F)

        output += translated
        cursor = end

    output += stock[cursor - INTRO_EVENT_START :]
    return bytes(output)


def assemble_dte_loader(intro_end_ptr: int) -> bytes:
    """Load private DTE pairs only while translated intro event $0400 is active."""
    a = MiniAssembler(DTE_LOADER_CPU)
    a.emit(0xE2, 0x20)                 # SEP #$20
    a.emit(0xAF, *lo24(0x001D03))      # event text bank
    a.emit(0xC9, 0xCA)
    a.rel8(0xD0, "stock8")
    a.emit(0xC2, 0x20)                 # REP #$20
    a.emit(0xAF, *lo24(0x001D01))      # event text pointer
    a.emit(0xC9, *lo16(INTRO_EVENT_START))
    a.rel8(0x90, "stock16")
    a.emit(0xC9, *lo16(intro_end_ptr))
    a.rel8(0xB0, "stock16")

    # X is stock (code-$C3)*2. Rebase so $E6 maps to private pair 0.
    a.emit(0x8A)                       # TXA
    a.emit(0x38)                       # SEC
    a.emit(0xE9, *lo16((DTE_NEW_THRESHOLD - 0xC3) * 2))
    a.emit(0xAA)                       # TAX
    a.emit(0xBF, *lo24(CUSTOM_DTE_CPU))
    a.emit(0x6B)                       # RTL

    a.label("stock8")
    a.emit(0xC2, 0x20)
    a.label("stock16")
    a.emit(0xBF, *lo24(STOCK_DTE_CPU))
    a.emit(0x6B)
    return a.resolve()


def load_french_glyphs() -> bytes:
    """Load the canonical shared 18-glyph French atlas as SNES 1bpp rows."""
    try:
        return glyph_bytes(FRENCH_CHARS)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc


def assemble_vwf(intro_end_ptr: int) -> bytes:
    """Assemble the intro-only VWF routine.

    See src/intro_vwf.asm for a readable 65816 representation of the same code.
    """
    a = MiniAssembler(CODE_CPU)

    # Enable the VWF only while the event text pointer belongs to event $0400.
    a.emit(0xAF, *lo24(0x001D03))      # LDA.l $001D03 (event text bank)
    a.emit(0xC9, 0xCA)                 # CMP #$CA
    a.rel8(0xF0, "bank_ok")           # BEQ bank_ok
    a.emit(0xAD, *lo16(0xA1CE))
    a.emit(0x29, 0x7F)
    a.emit(0x5C, *lo24(0xC01669))      # JML stock renderer continuation

    a.label("bank_ok")
    a.emit(0xC2, 0x20)                 # REP #$20
    a.emit(0xAF, *lo24(0x001D01))      # LDA.l $001D01 (event text pointer)
    a.emit(0xC9, *lo16(0x0C02))        # CMP #$0C02
    a.rel8(0xB0, "low_ok")            # BCS low_ok
    a.emit(0xE2, 0x20)
    a.emit(0xAD, *lo16(0xA1CE))
    a.emit(0x29, 0x7F)
    a.emit(0x5C, *lo24(0xC01669))

    a.label("low_ok")
    a.emit(0xC9, *lo16(intro_end_ptr))        # CMP #$0E44
    a.rel8(0x90, "range_ok")          # BCC range_ok
    a.emit(0xE2, 0x20)
    a.emit(0xAD, *lo16(0xA1CE))
    a.emit(0x29, 0x7F)
    a.emit(0x5C, *lo24(0xC01669))

    a.label("range_ok")
    a.emit(0xE2, 0x20)                 # SEP #$20

    # Preserve the stock character count and line-end flag.
    a.emit(0xAD, *lo16(0xA1CE))
    a.emit(0x29, 0x7F)
    a.rel8(0xD0, "have_count")
    a.emit(0xAD, *lo16(0xA1CE))
    a.emit(0x29, 0x7F)
    a.emit(0x5C, *lo24(0xC01669))

    a.label("have_count")
    a.emit(0x8D, *lo16(0x9380))        # $9380 = count
    a.emit(0xAD, *lo16(0xA1CE))
    a.emit(0x29, 0x80)
    a.emit(0x8D, *lo16(0x9381))        # $9381 = line-end bit

    # The intro parser writes decoded bytes directly to the private $7E:9390
    # buffer; no render-time mirror copy is required.

    # Clear the stock 32-cell × 12-row bitmap buffer ($7E:9000-$7E:917F).
    a.emit(0xA2, *lo16(0x0000))
    a.label("clear")
    a.emit(0x9E, *lo16(0x9000))
    a.emit(0xE8)
    a.emit(0xE0, *lo16(0x0180))
    a.rel8(0xD0, "clear")

    a.emit(0x9C, *lo16(0x9382))        # $9382 = VWF pixel cursor
    a.emit(0xA2, *lo16(0x0000))        # X = character index

    a.label("char_loop")
    a.emit(0x8A)                       # TXA
    a.emit(0xCD, *lo16(0x9380))        # CMP character count
    a.rel8(0xD0, "char_body")
    a.rel16(0x82, "done")

    a.label("char_body")
    a.emit(0xBD, *lo16(0x9390))        # LDA mirrored decoded_chars,X
    a.emit(0xE8)                       # INX
    a.emit(0xDA)                       # PHX: save character index

    # Convert direct text code ($80-based) to stock-font glyph index.
    a.emit(0xC2, 0x20)                 # REP #$20
    a.emit(0x29, *lo16(0x00FF))
    a.emit(0x38)                       # SEC
    a.emit(0xE9, *lo16(0x0080))        # SBC #$0080
    a.emit(0xAA)                       # TAX = glyph index
    a.emit(0xE2, 0x20)                 # SEP #$20

    # Read proportional advance for this glyph.
    a.emit(0xBF, *lo24(WIDTH_CPU))
    a.emit(0x8D, *lo16(0x9385))        # $9385 = glyph advance

    # glyph byte offset = glyph_index * 12.
    a.emit(0xC2, 0x20)
    a.emit(0x8A)                       # TXA
    a.emit(0x0A)
    a.emit(0x0A)
    a.emit(0x8D, *lo16(0x9386))        # glyph_index * 4 scratch
    a.emit(0x0A)                       # * 8
    a.emit(0x18)
    a.emit(0x6D, *lo16(0x9386))        # + *4 = *12
    a.emit(0xAA)                       # X = glyph row pointer

    # Convert pixel cursor into the tile-major destination. The shared row
    # compositor derives the sub-cell shift directly from $9382.
    a.emit(0xC2, 0x20)
    a.emit(0xAD, *lo16(0x9382))
    a.emit(0x29, *lo16(0x00FF))
    a.emit(0x4A)
    a.emit(0x4A)
    a.emit(0x4A)                       # tile_index = cursor / 8
    a.emit(0x0A)
    a.emit(0x0A)
    a.emit(0x8D, *lo16(0x9386))        # tile_index * 4
    a.emit(0x0A)                       # * 8
    a.emit(0x18)
    a.emit(0x6D, *lo16(0x9386))        # * 12
    a.emit(0xA8)                       # Y = destination tile byte offset

    a.emit(0xE2, 0x20)
    a.emit(0xA9, 0x0C)
    # $9384 belongs to the shared compositor as shift-count scratch. The
    # intro can safely reuse $9386 as its 12-row counter after Y is computed.
    a.emit(0x8D, *lo16(0x9386))        # $9386 = 12 rows

    a.label("row_loop")
    a.emit(*ROW_RENDERER_CALL)          # shared stock row + framing + compositor
    a.emit(0xE8)
    a.emit(*([0xEA] * 8))               # preserve validated renderer layout
    a.emit(0x99, *lo16(0x9000))         # shared helper returns current-cell half
    a.emit(0xC8)                        # INY: next row in current tile
    a.emit(0xCE, *lo16(0x9386))
    a.rel8(0xD0, "row_loop")

    a.emit(0xFA)                       # PLX: restore character index
    a.emit(0xAD, *lo16(0x9382))
    a.emit(0x18)
    a.emit(0x6D, *lo16(0x9385))
    a.emit(0x8D, *lo16(0x9382))        # pixel_cursor += glyph_advance
    a.rel16(0x82, "char_loop")

    a.label("done")
    # Intro VWF behavior:
    # Normally leave $A1CE untouched. The intro contains a WAIT command ($28)
    # in the middle of the final logical line (`river...` / `and history`).
    # When the next event opcode is WAIT, convert the VWF pixel cursor to an
    # 8-pixel cell position so resuming after the wait does not create a large
    # fixed-width gap.
    a.emit(0xC2, 0x20)                 # REP #$20
    a.emit(0xAF, *lo24(0x001D01))      # LDA.l event pointer
    a.emit(0xAA)                       # TAX
    a.emit(0xE2, 0x20)                 # SEP #$20
    a.emit(0xBF, *lo24(0xCA0000))      # LDA.l $CA0000,X
    a.emit(0xC9, 0x28)                 # CMP #$28 (WAIT)
    a.rel8(0xD0, "done_return")

    a.emit(0xAD, *lo16(0x9382))        # LDA pixel cursor
    a.emit(0x18)
    a.emit(0x69, 0x07)                 # ceil(pixel_cursor / 8)
    a.emit(0x4A)
    a.emit(0x4A)
    a.emit(0x4A)
    a.emit(0x09, 0x00)                 # harmless no-op kept for byte identity
    a.emit(0x0D, *lo16(0x9381))        # restore line-end bit
    a.emit(0x8D, *lo16(0xA1CE))

    a.label("done_return")
    a.emit(0x5C, *lo24(0xC016B7))      # JML to stock RTS path

    return a.resolve()



def make_vwf_font(rom: bytearray) -> tuple[bytes, bytes]:
    """Build advances plus the expected framed rows used for static validation.

    The framed rows are no longer installed as a private runtime glyph table.
    Component 05 now reads the stock font directly and calls the shared runtime
    framing selector; this generated copy exists only to prove byte-equivalent
    row geometry for every intro-emittable code.
    """
    font = rom[FONT_BASE : FONT_BASE + 128 * 12]
    framed = bytearray()
    advances = bytearray()

    for glyph_index in range(128):
        code = glyph_index + 0x80
        rows = font[glyph_index * 12 : (glyph_index + 1) * 12]
        if code in INTRO_RENDER_CODES:
            # All glyphs the intro can actually emit follow the same canonical
            # policy as component 06. Keep legacy data for unreachable table
            # entries so this checkpoint changes the smallest possible runtime
            # surface.
            framed.extend(apply_validated_framing(code, rows))
            advances.append(validated_advance(code, rows))
        else:
            compact_rows, ink_width = left_compact_glyph(rows)
            framed.extend(compact_rows)
            advances.append(min(8, ink_width + 1) if ink_width else 4)

    return bytes(advances), bytes(framed)



def main(source_rom: Path, output_path: Path, patched_rom: Path | None = None) -> None:
    base = bytearray(source_rom.read_bytes())
    validate_base_rom(base)
    rom = bytearray(base)

    # Reserve $D4-$E5 for direct French glyph codes.
    if rom[DTE_COMPARE_IMMEDIATE_OFFSET] != DTE_STOCK_THRESHOLD:
        raise SystemExit(
            f"Unexpected DTE threshold byte: {rom[DTE_COMPARE_IMMEDIATE_OFFSET]:02X}"
        )
    rom[DTE_COMPARE_IMMEDIATE_OFFSET] = DTE_NEW_THRESHOLD

    # Install French glyphs.
    french_glyphs = load_french_glyphs()
    glyph_start = FONT_BASE + (ACCENT_FIRST - 0x80) * 12
    rom[glyph_start : glyph_start + len(french_glyphs)] = french_glyphs

    # Load the sparse French translation bound to the canonical event-$0400 source.
    text_ids, french_texts = load_french_intro_texts(base)
    paragraph_pages = load_layout_metadata(text_ids, french_texts)

    # Validate logical and pixel line widths.
    check_advances, _check_font = make_vwf_font(rom)
    for text_id, pages in zip(text_ids, paragraph_pages, strict=True):
        for page in pages:
            if len(page.split("\n")) > 3:
                raise SystemExit(f"Intro text {text_id} page exceeds three lines")
            for line in page.split("\n"):
                if len(line) > LINE_CHAR_LIMIT:
                    raise SystemExit(
                        f"Wrapped line for Intro text {text_id} exceeds {LINE_CHAR_LIMIT} chars: {line!r}"
                    )
                pixel_width = sum(check_advances[ASCII_TO_SOM[ch] - 0x80] for ch in line)
                if pixel_width > 252:
                    raise SystemExit(
                        f"Wrapped line for Intro text {text_id} exceeds 252 pixels: "
                        f"{pixel_width}px: {line!r}"
                    )

    # Compress text only; event control bytes stay outside DTE input.
    direct_pages = [encode_french(page) for pages in paragraph_pages for page in pages]
    compressed_pages, custom_dte, dte_pairs = choose_dte_pairs(direct_pages)

    compressed_chunks = []
    page_cursor = 0
    for text_index, (text_id, pages) in enumerate(zip(text_ids, paragraph_pages, strict=True)):
        encoded_pages = compressed_pages[page_cursor : page_cursor + len(pages)]
        page_cursor += len(pages)

        if len(encoded_pages) == 1:
            compressed_chunks.append(encoded_pages[0])
            continue

        if len(encoded_pages) != 2 or text_index not in SUBPAGE_WAIT_BY_INDEX:
            raise SystemExit(f"Unexpected multi-page timing configuration for intro text {text_id}")

        separator = bytes((0x28, SUBPAGE_WAIT_BY_INDEX[text_index], 0x52))  # WAIT, CLEAR
        compressed_chunks.append(separator.join(encoded_pages))

    # Rebuild event $0400 with the configured page and paragraph waits.
    new_event = rebuild_intro_event(base, compressed_chunks)
    intro_end_ptr = INTRO_EVENT_START + len(new_event)
    if intro_end_ptr > RELOC_SOURCE_END:
        raise SystemExit(
            f"Translated intro is too large ({len(new_event)} bytes, ends at ${intro_end_ptr:04X}); "
            f"maximum supported end is ${RELOC_SOURCE_END:04X}"
        )

    # The translated event overlaps the small contiguous $0401-$040F block.
    # Move that block unchanged to unused CA:FF70 and update only its pointers.
    relocate_len = RELOC_SOURCE_END - RELOC_SOURCE_START
    source_file = 0x0A0000 + RELOC_SOURCE_START
    target_file = 0x0A0000 + RELOC_TARGET_START
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

    rom[INTRO_EVENT_FILE : INTRO_EVENT_FILE + len(new_event)] = new_event

    # Build the intro-only VWF renderer plus the shared private-buffer parser bridge.
    code = assemble_vwf(intro_end_ptr)
    dte_loader = assemble_dte_loader(intro_end_ptr)
    advances, expected_framed_font = make_vwf_font(rom)

    # Component 06 uses exact value $01 as its persistent renderer-active tag.
    # During translated intro rendering this same mutually-exclusive byte stores
    # a glyph advance. The validated post-outline gate depends on these scopes
    # remaining distinguishable: every intro-emittable glyph must stay >= 2 px.
    if any(advances[code - 0x80] == 1 for code in INTRO_RENDER_CODES):
        raise SystemExit("Intro glyph advance collides with component-06 active tag value $01")

    if CODE_CPU + len(code) > PARSER_WRITE_CPU:
        raise SystemExit(f"VWF code overlaps shared parser helper: {len(code):#x} bytes")
    if PARSER_WRITE_CPU + len(PARSER_WRITE_HELPER) > WIDTH_CPU:
        raise SystemExit(f"Shared parser helper is too large: {len(PARSER_WRITE_HELPER):#x} bytes")

    payload = code
    payload += bytes([0xFF]) * (PARSER_WRITE_CPU - (CODE_CPU + len(code)))
    payload += PARSER_WRITE_HELPER
    payload += bytes([0xFF]) * (WIDTH_CPU - (PARSER_WRITE_CPU + len(PARSER_WRITE_HELPER)))
    payload += advances

    if WIDTH_CPU + len(advances) != SHARED_FRAMING_CPU:
        raise SystemExit("Intro width table no longer ends at shared framing selector")

    # The old private preframed 128x12 glyph table is no longer installed.
    # Verify that the stock-font + shared runtime framing path is byte-equivalent
    # for every character code the intro can emit.
    stock_font = rom[FONT_BASE : FONT_BASE + 128 * 12]
    for code_value in INTRO_RENDER_CODES:
        glyph_index = code_value - 0x80
        start = glyph_index * 12
        expected = expected_framed_font[start:start + 12]
        actual = apply_validated_framing(code_value, stock_font[start:start + 12])
        if actual != expected:
            raise SystemExit(f"Shared runtime framing mismatch for intro code ${code_value:02X}")

    if any(value != 0xFF for value in rom[CODE_FILE : CODE_FILE + len(payload)]):
        raise SystemExit("Expected VWF free-space area at $C7:4285 to be empty")
    validate_shared_text_buffer_stock(base)
    validate_shared_framing_stock(base)
    validate_shared_compositor_stock(base)
    validate_shared_row_renderer_stock(base)
    validate_shared_outline_stock(base)
    if any(value != 0xFF for value in rom[DTE_LOADER_FILE : DTE_LOADER_FILE + len(dte_loader)]):
        raise SystemExit("Expected free space for DTE loader is not empty")
    if any(value != 0xFF for value in rom[CUSTOM_DTE_FILE : CUSTOM_DTE_FILE + len(custom_dte)]):
        raise SystemExit("Expected free space for private DTE table is not empty")

    # Install hooks.
    if rom[0x1664:0x1668] != bytes.fromhex("ad ce a1 29"):
        raise SystemExit("Stock renderer signature mismatch at ROM $001664")
    rom[0x1664:0x1668] = bytes.fromhex("5c 85 42 c7")

    if rom[0x1719:0x171D] != bytes.fromhex("bf 99 72 c7"):
        raise SystemExit("Stock DTE table-load signature mismatch at ROM $001719")
    rom[0x1719:0x171D] = bytes([0x22, *lo24(DTE_LOADER_CPU)])

    rom[CODE_FILE : CODE_FILE + len(payload)] = payload
    install_shared_text_buffer(rom)
    install_shared_framing(rom)
    install_shared_compositor(rom)
    install_shared_row_renderer(rom)
    install_shared_outline(rom)
    enable_intro_private_buffer(rom, intro_end_ptr)
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
    print(f"Intro event: ${INTRO_EVENT_START:04X}-${intro_end_ptr:04X} ({len(new_event)} bytes)")
    print(f"Checksum: {checksum:04X}; complement: {complement:04X}")
    print(f"Patch written to: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the standalone French intro VWF patch.")
    parser.add_argument("rom", type=Path, help="clean unheadered Secret of Mana (USA) ROM")
    parser.add_argument("-o", "--output", type=Path, default=ROOT / "build" / "patch.ips", help="output IPS path")
    parser.add_argument("--patched-rom", type=Path, help="optional patched ROM output")
    args = parser.parse_args()
    main(args.rom, args.output, args.patched_rom)
