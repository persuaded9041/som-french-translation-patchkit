#!/usr/bin/env python3
"""Build the French new-game intro VWF IPS patch.

Text comes from assets/text/scrtxt_fr.bin (Android IDs 3445-3452).
Line/page breaks are defined by numeric word counts in intro_layout.json.
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
GLYPH_CPU = 0xC744C0
PARSER_HELPER_CPU = 0xC743D0
BUFFER_INIT_HELPER_CPU = 0xC74AC0
BUFFER_INIT_HELPER_FILE = CODE_FILE + (BUFFER_INIT_HELPER_CPU - CODE_CPU)
PREV_CHAR_HELPER_CPU = 0xC74B40
PREV_CHAR_HELPER_FILE = CODE_FILE + (PREV_CHAR_HELPER_CPU - CODE_CPU)
CAPACITY_HELPER_CPU = 0xC74BC0
CAPACITY_HELPER_FILE = CODE_FILE + (CAPACITY_HELPER_CPU - CODE_CPU)

# Stock text/font locations.
DTE_COMPARE_IMMEDIATE_OFFSET = 0x0016F6
DTE_STOCK_THRESHOLD = 0xD3
FONT_BASE = 0x12DC00

# Direct character codes reserved for French glyphs.
ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from shared.rom import validate_base_rom, update_checksum  # noqa: E402
from shared.ips import make_ips  # noqa: E402
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

SCRTXT_FILE = ROOT / "assets" / "text" / "scrtxt_fr.bin"
INTRO_ANDROID_IDS = tuple(range(3445, 3453))
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


class MiniAssembler:
    """Small label-aware assembler used by the generated 65816 routines."""

    def __init__(self, origin: int):
        self.origin = origin
        self.data = bytearray()
        self.labels: dict[str, int] = {}
        self.fixups: list[tuple[int, str, int]] = []

    @property
    def pc(self) -> int:
        return self.origin + len(self.data)

    def emit(self, *values: int) -> None:
        self.data.extend(values)

    def label(self, name: str) -> None:
        self.labels[name] = self.pc

    def rel8(self, opcode: int, label: str) -> None:
        self.emit(opcode, 0)
        self.fixups.append((len(self.data) - 1, label, 1))

    def rel16(self, opcode: int, label: str) -> None:
        self.emit(opcode, 0, 0)
        self.fixups.append((len(self.data) - 2, label, 2))

    def resolve(self) -> bytes:
        for pos, label, size in self.fixups:
            target = self.labels[label]
            operand_cpu = self.origin + pos
            next_cpu = operand_cpu + size
            displacement = target - next_cpu
            if size == 1:
                if not -128 <= displacement <= 127:
                    raise ValueError(f"8-bit branch to {label} is out of range: {displacement}")
                self.data[pos] = displacement & 0xFF
            else:
                if not -32768 <= displacement <= 32767:
                    raise ValueError(f"16-bit branch to {label} is out of range: {displacement}")
                self.data[pos : pos + 2] = struct.pack("<h", displacement)
        return bytes(self.data)


def lo16(value: int) -> tuple[int, int]:
    return value & 0xFF, (value >> 8) & 0xFF


def lo24(value: int) -> tuple[int, int, int]:
    return value & 0xFF, (value >> 8) & 0xFF, (value >> 16) & 0xFF


def load_android_intro_texts() -> list[str]:
    """Read Android French intro entries 3445-3452 from scrtxt_fr.bin."""
    data = SCRTXT_FILE.read_bytes()
    if len(data) < 8:
        raise SystemExit("assets/scrtxt_fr.bin is too small")
    count, pool_size = struct.unpack_from("<II", data, 0)
    table_end = 8 + count * 8
    if table_end > len(data):
        raise SystemExit("Invalid scrtxt_fr.bin entry table")
    pool = data[table_end:]
    if pool_size > len(pool):
        raise SystemExit("Invalid scrtxt_fr.bin string pool size")

    wanted = set(INTRO_ANDROID_IDS)
    found: dict[int, str] = {}
    for index in range(count):
        text_id, offset = struct.unpack_from("<II", data, 8 + index * 8)
        if text_id not in wanted or text_id in found:
            continue
        if offset >= len(pool):
            raise SystemExit(f"Invalid scrtxt_fr.bin offset for ID {text_id}")
        end = pool.find(b"\x00", offset)
        if end < 0:
            raise SystemExit(f"Unterminated scrtxt_fr.bin string for ID {text_id}")
        found[text_id] = pool[offset:end].decode("utf-8")

    missing = [text_id for text_id in INTRO_ANDROID_IDS if text_id not in found]
    if missing:
        raise SystemExit("Missing Android intro IDs: " + ", ".join(map(str, missing)))
    return [found[text_id] for text_id in INTRO_ANDROID_IDS]



def load_layout_metadata(android_texts: list[str]) -> list[list[str]]:
    """Apply numeric line/page metadata to text read from scrtxt_fr.bin.

    The JSON file stores only word counts. For each Android entry, words are
    consumed sequentially according to those counts. This keeps the translation
    source exclusively in the binary asset while preserving an editor-controlled
    page and line layout.
    """
    try:
        metadata = json.loads(LAYOUT_METADATA_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Cannot read layout metadata: {exc}") from exc

    if metadata.get("format_version") != 1:
        raise SystemExit("Unsupported intro layout metadata version")
    entries = metadata.get("entries")
    if not isinstance(entries, dict):
        raise SystemExit("intro_layout.json must contain an 'entries' object")

    expected_ids = [str(text_id) for text_id in INTRO_ANDROID_IDS]
    if sorted(entries, key=int) != expected_ids:
        raise SystemExit(
            "intro_layout.json must contain exactly IDs " + ", ".join(expected_ids)
        )

    result: list[list[str]] = []
    for text_id, source in zip(INTRO_ANDROID_IDS, android_texts):
        normalized = " ".join(source.replace("\r", " ").replace("\n", " ").split())
        words = normalized.split(" ") if normalized else []
        page_spec = entries[str(text_id)]
        if not isinstance(page_spec, list) or not page_spec:
            raise SystemExit(f"Android ID {text_id} has invalid page metadata")

        cursor = 0
        pages: list[str] = []
        for page_index, line_counts in enumerate(page_spec, 1):
            if not isinstance(line_counts, list) or not 1 <= len(line_counts) <= 3:
                raise SystemExit(
                    f"Android ID {text_id} page {page_index} must contain 1-3 line counts"
                )
            lines: list[str] = []
            for line_index, count in enumerate(line_counts, 1):
                if not isinstance(count, int) or count <= 0:
                    raise SystemExit(
                        f"Android ID {text_id} page {page_index} line {line_index} "
                        "has an invalid word count"
                    )
                end = cursor + count
                if end > len(words):
                    raise SystemExit(
                        f"Android ID {text_id} layout consumes more words than the BIN text"
                    )
                line = " ".join(words[cursor:end])
                cursor = end
                if len(line) > LINE_CHAR_LIMIT:
                    raise SystemExit(
                        f"Android ID {text_id} page {page_index} line {line_index} "
                        f"exceeds {LINE_CHAR_LIMIT} visible characters ({len(line)})"
                    )
                lines.append(line)
            pages.append("\n".join(lines))

        if cursor != len(words):
            raise SystemExit(
                f"Android ID {text_id} layout consumes {cursor} of {len(words)} words"
            )
        result.append(pages)
    return result

# Wait inserted between two pages of the same paragraph.
SUBPAGE_WAIT = {
    3446: 0x18,
    3447: 0x1C,
    3448: 0x18,
    3449: 0x12,
}

# Stock/new WAIT after each paragraph. The command is stored in the gap before
# the following text run.
PARAGRAPH_END_WAIT = {
    3445: (0x30, 0x18),
    3446: (0x38, 0x1C),
    3447: (0x40, 0x18),
    3448: (0x38, 0x14),
    3449: (0x30, 0x12),
}


def encode_french(text: str) -> bytes:
    try:
        return bytes(0x7F if ch == "\n" else ASCII_TO_SOM[ch] for ch in text)
    except KeyError as exc:
        raise SystemExit(f"Unsupported French character from scrtxt_fr.bin: {exc.args[0]!r}") from exc


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
            previous_id = INTRO_ANDROID_IDS[index - 1]
            if previous_id in PARAGRAPH_END_WAIT:
                stock_wait, new_wait = PARAGRAPH_END_WAIT[previous_id]
                if len(gap) < 2 or gap[0] != 0x28 or gap[1] != stock_wait:
                    raise SystemExit(
                        f"Expected WAIT ${stock_wait:02X} after Android ID "
                        f"{previous_id}, got: {gap[:4].hex(' ')}"
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

    # Convert direct text code ($80-based) to compact-font glyph index.
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
    a.emit(0x8D, *lo16(0x9386))        # temporary glyph_index * 4
    a.emit(0x0A)                       # * 8
    a.emit(0x18)
    a.emit(0x6D, *lo16(0x9386))        # + *4 = *12
    a.emit(0xAA)                       # X = glyph row pointer

    # Convert pixel cursor into tile-major destination + bit shift.
    a.emit(0xE2, 0x20)
    a.emit(0xAD, *lo16(0x9382))
    a.emit(0x29, 0x07)
    a.emit(0x8D, *lo16(0x9383))        # $9383 = cursor & 7

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
    a.emit(0x8D, *lo16(0x9384))        # $9384 = 12 rows

    a.label("row_loop")
    # Build a 16-bit row stream, shift it by the current pixel offset, then OR
    # its left/right halves into the current tile and the next tile.
    a.emit(0xBF, *lo24(GLYPH_CPU))      # LDA compact_font,X
    a.emit(0xE8)
    a.emit(0xC2, 0x20)
    a.emit(0x29, *lo16(0x00FF))
    a.emit(0xEB)                       # XBA: glyph row becomes high byte
    a.emit(0x8D, *lo16(0x9388))        # $9388/$9389 = shifted row word
    a.emit(0xDA)                       # PHX: save glyph pointer

    a.emit(0xE2, 0x20)
    a.emit(0xAD, *lo16(0x9383))
    a.emit(0xC2, 0x20)
    a.emit(0x29, *lo16(0x00FF))
    a.emit(0xAA)                       # X = shift count
    a.emit(0xAD, *lo16(0x9388))

    a.label("shift_loop")
    a.emit(0xE0, *lo16(0x0000))
    a.rel8(0xF0, "shift_done")
    a.emit(0x4A)
    a.emit(0xCA)
    a.rel8(0x80, "shift_loop")

    a.label("shift_done")
    a.emit(0x8D, *lo16(0x9388))
    a.emit(0xE2, 0x20)

    # The bitmap is tile-major: each tile stores 12 consecutive row bytes.
    # Therefore right-side spill belongs at +$0C, not +1.
    a.emit(0xAD, *lo16(0x9389))
    a.emit(0x19, *lo16(0x9000))
    a.emit(0x99, *lo16(0x9000))
    a.emit(0xAD, *lo16(0x9388))
    a.emit(0x19, *lo16(0x900C))
    a.emit(0x99, *lo16(0x900C))

    a.emit(0xFA)                       # PLX: restore glyph pointer
    a.emit(0xC8)                       # INY: next row in current tile
    a.emit(0xCE, *lo16(0x9384))
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



def assemble_parser_private_write(intro_end_ptr: int) -> bytes:
    """Redirect decoded intro bytes to the private $7E:9390 buffer.

    During event $0400, the intercepted parser store writes only to $7E:9390,X.
    Outside the intro, the stock $7E:A1A4,X destination is reproduced exactly.
    """
    a = MiniAssembler(PARSER_HELPER_CPU)

    # Preserve the decoded byte while we test whether event $0400 is active.
    a.emit(0x48)                       # PHA

    a.emit(0xAF, *lo24(0x001D03))      # LDA.l event text bank
    a.emit(0xC9, 0xCA)                 # CMP #$CA
    a.rel8(0xD0, "stock_only")

    a.emit(0xC2, 0x20)                 # REP #$20
    a.emit(0xAF, *lo24(0x001D01))      # LDA.l event text pointer
    a.emit(0xC9, *lo16(0x0C02))
    a.rel8(0x90, "stock_only_16")      # BCC
    a.emit(0xC9, *lo16(intro_end_ptr))
    a.rel8(0xB0, "stock_only_16")      # BCS

    # Intro path: restore the decoded byte and write ONLY to the private buffer.
    a.emit(0xE2, 0x20)                 # SEP #$20
    a.emit(0x68)                       # PLA
    a.emit(0x9D, *lo16(0x9390))        # STA $9390,X
    a.emit(0xE8)                       # INX (overwritten stock instruction)
    a.emit(0x5C, *lo24(0xC017D2))      # JML after original INX

    # Non-intro path: reproduce the stock store exactly.
    a.label("stock_only_16")
    a.emit(0xE2, 0x20)                 # SEP #$20
    a.label("stock_only")
    a.emit(0x68)                       # PLA
    a.emit(0x9D, *lo16(0xA1A4))        # STA $A1A4,X
    a.emit(0xE8)                       # INX
    a.emit(0x5C, *lo24(0xC017D2))

    return a.resolve()

def assemble_buffer_init_private(intro_end_ptr: int) -> bytes:
    """Initialize the private 44-byte decoded-text buffer for event $0400.

    During the intro, $7E:9390-$93BB is filled with $80. Outside the intro, the
    original 33-byte $7E:A1A4-$A1C4 initialization is reproduced exactly.
    """
    a = MiniAssembler(BUFFER_INIT_HELPER_CPU)

    # Detect event $0400 by bank and pointer range.
    a.emit(0xAF, *lo24(0x001D03))      # LDA.l event text bank
    a.emit(0xC9, 0xCA)                 # CMP #$CA
    a.rel8(0xD0, "stock_init")

    a.emit(0xC2, 0x20)                 # REP #$20
    a.emit(0xAF, *lo24(0x001D01))      # LDA.l event text pointer
    a.emit(0xC9, *lo16(0x0C02))
    a.rel8(0x90, "stock_init_16")      # BCC
    a.emit(0xC9, *lo16(intro_end_ptr))
    a.rel8(0xB0, "stock_init_16")      # BCS

    # Intro: initialize the full private 44-byte area.
    a.emit(0xE2, 0x20)                 # SEP #$20
    a.emit(0xA2, *lo16(0x0000))        # LDX #$0000
    a.emit(0xA9, 0x80)                 # LDA #$80
    a.label("private_loop")
    a.emit(0x9D, *lo16(0x9390))        # STA $9390,X
    a.emit(0xE8)                       # INX
    a.emit(0xE0, *lo16(0x002C))        # CPX #$002C (44 bytes)
    a.rel8(0xD0, "private_loop")
    a.emit(0x5C, *lo24(0xC016C6))      # continue after stock init loop

    # Non-intro: reproduce the original 33-byte initialization exactly.
    a.label("stock_init_16")
    a.emit(0xE2, 0x20)                 # SEP #$20
    a.label("stock_init")
    a.emit(0xA2, *lo16(0x0000))        # LDX #$0000
    a.emit(0xA9, 0x80)                 # LDA #$80
    a.label("stock_loop")
    a.emit(0x9D, *lo16(0xA1A4))
    a.emit(0xE8)
    a.emit(0xE0, *lo16(0x0021))
    a.rel8(0xD0, "stock_loop")
    a.emit(0x5C, *lo24(0xC016C6))

    return a.resolve()



def assemble_previous_char_private_read(intro_end_ptr: int) -> bytes:
    """Read the previous decoded intro byte from the private buffer.

    Event $0400 reads from $7E:9390,X; all other events keep the original
    $7E:A1A4,X source.
    """
    a = MiniAssembler(PREV_CHAR_HELPER_CPU)

    # The overwritten stock LDA is 16-bit at this point. Temporarily switch to
    # 8-bit A only for the event-bank test, then restore 16-bit A before the
    # actual character load.
    a.emit(0xE2, 0x20)                 # SEP #$20
    a.emit(0xAF, *lo24(0x001D03))      # LDA.l event text bank
    a.emit(0xC9, 0xCA)                 # CMP #$CA
    a.rel8(0xD0, "stock_from_8")

    a.emit(0xC2, 0x20)                 # REP #$20
    a.emit(0xAF, *lo24(0x001D01))      # LDA.l event text pointer
    a.emit(0xC9, *lo16(0x0C02))
    a.rel8(0x90, "stock_from_16")      # BCC
    a.emit(0xC9, *lo16(intro_end_ptr))
    a.rel8(0xB0, "stock_from_16")      # BCS

    # Intro: source the previous decoded character from the private buffer.
    a.emit(0xBF, *lo24(0x7E9390))      # LDA.l $7E9390,X
    a.emit(0x5C, *lo24(0xC018E2))      # resume after stock LDA

    a.label("stock_from_8")
    a.emit(0xC2, 0x20)                 # REP #$20
    a.label("stock_from_16")
    a.emit(0xBF, *lo24(0x7EA1A4))      # LDA.l $7EA1A4,X
    a.emit(0x5C, *lo24(0xC018E2))

    return a.resolve()

def assemble_intro_capacity(intro_end_ptr: int) -> bytes:
    """Use 38-visible-character capacity throughout intro event $0400.

    A1CA is set to 39 parser units: up to 38 stored glyph bytes plus a following
    explicit $7F newline control in the same pass. Shorter lines terminate on
    their explicit newline before the capacity is exhausted. Outside the intro,
    reproduce the original stock calculation exactly.
    """
    a = MiniAssembler(CAPACITY_HELPER_CPU)

    a.emit(0xC2, 0x20)                 # REP #$20
    a.emit(0xAF, *lo24(0x001D01))      # LDA.l event text pointer
    a.emit(0xC9, *lo16(INTRO_EVENT_START))
    a.rel8(0x90, "stock16")
    a.emit(0xC9, *lo16(intro_end_ptr))
    a.rel8(0xB0, "stock16")

    a.emit(0xE2, 0x20)                 # SEP #$20
    a.emit(0xA9, 0x27)                 # LDA #39 = 38 glyphs + newline control
    a.emit(0x8D, *lo16(0xA1CA))
    a.emit(0x6B)                       # RTL

    a.label("stock16")
    a.emit(0xE2, 0x20)                 # SEP #$20
    a.emit(0xAD, *lo16(0xA16A))
    a.emit(0x38)                       # SEC
    a.emit(0xED, *lo16(0xA181))
    a.emit(0x8D, *lo16(0xA1CA))
    a.emit(0x6B)                       # RTL
    return a.resolve()


def make_compact_font(rom: bytearray) -> tuple[bytes, bytes]:
    """Build proportional advances + left-compacted 8×12 glyph data."""
    font = rom[FONT_BASE : FONT_BASE + 128 * 12]
    compact = bytearray()
    advances = bytearray()

    for glyph_index in range(128):
        rows = font[glyph_index * 12 : (glyph_index + 1) * 12]
        ink_columns = [
            x
            for row in rows
            for x in range(8)
            if row & (0x80 >> x)
        ]

        if ink_columns:
            left = min(ink_columns)
            right = max(ink_columns)
            ink_width = right - left + 1
            compact.extend(((row << left) & 0xFF) for row in rows)
            advance = min(8, ink_width + 1)
        else:
            compact.extend(bytes(12))
            advance = 4

        advances.append(advance)

    return bytes(advances), bytes(compact)



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

    # Extract and prepare French text directly from the Android binary.
    android_texts = load_android_intro_texts()
    paragraph_pages = load_layout_metadata(android_texts)

    # Validate logical and pixel line widths.
    check_advances, _check_font = make_compact_font(rom)
    for text_id, pages in zip(INTRO_ANDROID_IDS, paragraph_pages):
        for page in pages:
            if len(page.split("\n")) > 3:
                raise SystemExit(f"Android ID {text_id} page exceeds three lines")
            for line in page.split("\n"):
                if len(line) > LINE_CHAR_LIMIT:
                    raise SystemExit(
                        f"Wrapped line for Android ID {text_id} exceeds {LINE_CHAR_LIMIT} chars: {line!r}"
                    )
                pixel_width = sum(check_advances[ASCII_TO_SOM[ch] - 0x80] for ch in line)
                if pixel_width > 252:
                    raise SystemExit(
                        f"Wrapped line for Android ID {text_id} exceeds 252 pixels: "
                        f"{pixel_width}px: {line!r}"
                    )

    # Compress text only; event control bytes stay outside DTE input.
    direct_pages = [encode_french(page) for pages in paragraph_pages for page in pages]
    compressed_pages, custom_dte, dte_pairs = choose_dte_pairs(direct_pages)

    compressed_chunks = []
    page_cursor = 0
    for text_id, pages in zip(INTRO_ANDROID_IDS, paragraph_pages):
        encoded_pages = compressed_pages[page_cursor : page_cursor + len(pages)]
        page_cursor += len(pages)

        if len(encoded_pages) == 1:
            compressed_chunks.append(encoded_pages[0])
            continue

        if len(encoded_pages) != 2 or text_id not in SUBPAGE_WAIT:
            raise SystemExit(
                f"Unexpected multi-page timing configuration for Android ID {text_id}"
            )

        separator = bytes((0x28, SUBPAGE_WAIT[text_id], 0x52))  # WAIT, CLEAR
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

    # Build the intro-only private-buffer VWF pipeline.
    code = assemble_vwf(intro_end_ptr)
    parser_helper = assemble_parser_private_write(intro_end_ptr)
    buffer_init_helper = assemble_buffer_init_private(intro_end_ptr)
    prev_char_helper = assemble_previous_char_private_read(intro_end_ptr)
    capacity_helper = assemble_intro_capacity(intro_end_ptr)
    dte_loader = assemble_dte_loader(intro_end_ptr)
    advances, compact_font = make_compact_font(rom)

    if CODE_CPU + len(code) > PARSER_HELPER_CPU:
        raise SystemExit(f"VWF code overlaps parser helper: {len(code):#x} bytes")
    if PARSER_HELPER_CPU + len(parser_helper) > WIDTH_CPU:
        raise SystemExit(f"Parser helper is too large: {len(parser_helper):#x} bytes")

    payload = code
    payload += bytes([0xFF]) * (PARSER_HELPER_CPU - (CODE_CPU + len(code)))
    payload += parser_helper
    payload += bytes([0xFF]) * (WIDTH_CPU - (PARSER_HELPER_CPU + len(parser_helper)))
    payload += advances
    payload += bytes([0xFF]) * (GLYPH_CPU - (WIDTH_CPU + len(advances)))
    payload += compact_font

    if any(value != 0xFF for value in rom[CODE_FILE : CODE_FILE + len(payload)]):
        raise SystemExit("Expected VWF free-space area at $C7:4285 to be empty")
    for file_offset, helper, label in (
        (BUFFER_INIT_HELPER_FILE, buffer_init_helper, "buffer-init helper"),
        (PREV_CHAR_HELPER_FILE, prev_char_helper, "previous-char helper"),
        (CAPACITY_HELPER_FILE, capacity_helper, "capacity helper"),
        (DTE_LOADER_FILE, dte_loader, "DTE loader"),
    ):
        if any(value != 0xFF for value in rom[file_offset : file_offset + len(helper)]):
            raise SystemExit(f"Expected free space for {label} is not empty")
    if any(value != 0xFF for value in rom[CUSTOM_DTE_FILE : CUSTOM_DTE_FILE + len(custom_dte)]):
        raise SystemExit("Expected free space for private DTE table is not empty")

    # Install hooks.
    if rom[0x1664:0x1668] != bytes.fromhex("ad ce a1 29"):
        raise SystemExit("Stock renderer signature mismatch at ROM $001664")
    rom[0x1664:0x1668] = bytes.fromhex("5c 85 42 c7")

    if rom[0x17CE:0x17D2] != bytes.fromhex("9d a4 a1 e8"):
        raise SystemExit("Stock parser write signature mismatch at ROM $0017CE")
    rom[0x17CE:0x17D2] = bytes([0x5C, *lo24(PARSER_HELPER_CPU)])

    if rom[0x16B8:0x16BC] != bytes.fromhex("a2 00 00 a9"):
        raise SystemExit("Stock buffer-init signature mismatch at ROM $0016B8")
    rom[0x16B8:0x16BC] = bytes([0x5C, *lo24(BUFFER_INIT_HELPER_CPU)])

    if rom[0x18DE:0x18E2] != bytes.fromhex("bf a4 a1 7e"):
        raise SystemExit("Stock previous-character read signature mismatch at ROM $0018DE")
    rom[0x18DE:0x18E2] = bytes([0x5C, *lo24(PREV_CHAR_HELPER_CPU)])

    if rom[0x16C6:0x16D0] != bytes.fromhex("ad 6a a1 38 ed 81 a1 8d ca a1"):
        raise SystemExit("Stock decoder-capacity signature mismatch at ROM $0016C6")
    rom[0x16C6:0x16D0] = bytes([0x22, *lo24(CAPACITY_HELPER_CPU), 0xEA, 0xEA, 0xEA, 0xEA, 0xEA, 0xEA])

    if rom[0x1719:0x171D] != bytes.fromhex("bf 99 72 c7"):
        raise SystemExit("Stock DTE table-load signature mismatch at ROM $001719")
    rom[0x1719:0x171D] = bytes([0x22, *lo24(DTE_LOADER_CPU)])

    # Prevent row-to-row carry injection in the stock outline shift.
    if rom[0x163D] != 0x2A:
        raise SystemExit("Stock outline ROL signature mismatch at ROM $00163D")
    rom[0x163D] = 0x0A

    rom[CODE_FILE : CODE_FILE + len(payload)] = payload
    rom[BUFFER_INIT_HELPER_FILE : BUFFER_INIT_HELPER_FILE + len(buffer_init_helper)] = buffer_init_helper
    rom[PREV_CHAR_HELPER_FILE : PREV_CHAR_HELPER_FILE + len(prev_char_helper)] = prev_char_helper
    rom[CAPACITY_HELPER_FILE : CAPACITY_HELPER_FILE + len(capacity_helper)] = capacity_helper
    rom[DTE_LOADER_FILE : DTE_LOADER_FILE + len(dte_loader)] = dte_loader
    rom[CUSTOM_DTE_FILE : CUSTOM_DTE_FILE + len(custom_dte)] = custom_dte

    checksum = update_checksum(rom)
    complement = checksum ^ 0xFFFF

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(make_ips(base, rom))
    if patched_rom:
        patched_rom.parent.mkdir(parents=True, exist_ok=True)
        patched_rom.write_bytes(rom)

    print(f"Android IDs: {INTRO_ANDROID_IDS[0]}-{INTRO_ANDROID_IDS[-1]}")
    for text_id, pages in zip(INTRO_ANDROID_IDS, paragraph_pages):
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
