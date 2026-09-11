"""Shared Secret of Mana stock text encoding helpers.

This module covers the direct glyph / line-break / stock DTE encoding used by
ordinary event text and the CA non-event text-resource table.  It deliberately
does not know anything about event command layouts or resource ownership.
"""
from __future__ import annotations

from shared.french_charset import CHAR_TO_CODE, CODE_TO_CHAR

DTE_TABLE_FILE = 0x077299  # $C7:7299

CODE_TO_TEXT = {0x80: " "}
CODE_TO_TEXT.update({0x81 + i: chr(ord("a") + i) for i in range(26)})
CODE_TO_TEXT.update({0x9B + i: chr(ord("A") + i) for i in range(26)})
CODE_TO_TEXT.update({0xB5 + i: str(i) for i in range(10)})
CODE_TO_TEXT.update(
    {
        0xBF: ".",
        0xC0: ",",
        0xC1: "/",
        0xC2: "'",
        0xC3: "“",
        0xC4: "”",
        0xC5: ":",
        0xC6: "-",
        0xC7: "%",
        0xC8: "!",
        0xC9: "&",
        0xCA: "?",
        0xCB: "(",
        0xCC: ")",
    }
)
# French direct glyphs are available to edited text.  Clean-USA bytes >= $D3
# are still decoded as stock DTE first, so this does not reinterpret source ROM.
CODE_TO_TEXT.update(CODE_TO_CHAR)
TEXT_TO_CODE = {char: code for code, char in CODE_TO_TEXT.items()}
TEXT_TO_CODE.update(CHAR_TO_CODE)


def is_dte(code: int) -> bool:
    return 0x60 <= code <= 0x7C or 0xD3 <= code <= 0xFF


def decode_dte_pair(rom: bytes, code: int) -> str:
    if 0x60 <= code <= 0x7C:
        pair_index = code - 0x60
    elif 0xD3 <= code <= 0xFF:
        pair_index = code - 0xC3
    else:
        raise ValueError(f"Not a stock DTE code: ${code:02X}")
    pair = rom[DTE_TABLE_FILE + pair_index * 2:DTE_TABLE_FILE + pair_index * 2 + 2]
    try:
        return "".join(CODE_TO_TEXT[value] for value in pair)
    except KeyError as exc:
        raise ValueError(
            f"Stock DTE ${code:02X} expands to an unmapped glyph ${exc.args[0]:02X}"
        ) from exc


def decode_text_unit(rom: bytes, code: int) -> str | None:
    if code == 0x7F:
        return "\n"
    if 0x80 <= code <= 0xD2:
        return CODE_TO_TEXT.get(code)
    if is_dte(code):
        return decode_dte_pair(rom, code)
    return None


def decode_text_bytes(rom: bytes, data: bytes) -> str:
    parts: list[str] = []
    for code in data:
        piece = decode_text_unit(rom, code)
        if piece is None:
            raise ValueError(f"Unsupported stock text byte ${code:02X}")
        parts.append(piece)
    return "".join(parts)


def encode_text(text: str) -> bytes:
    """Encode edited text deterministically as direct glyph bytes."""
    out = bytearray()
    for char in text:
        if char == "\n":
            out.append(0x7F)
            continue
        try:
            out.append(TEXT_TO_CODE[char])
        except KeyError as exc:
            raise ValueError(f"Unsupported editable text character: {char!r}") from exc
    return bytes(out)


def encode_text_with_stock_dte(rom: bytes, text: str, *, upper_dte_threshold: int = 0xE6) -> bytes:
    """Encode edited text using only runtime-safe stock DTE pairs.

    The clean game has lower DTE codes ``$60-$7C`` plus upper DTE codes.  French
    project profiles repurpose part of the original upper-DTE range as direct
    glyphs, so callers must provide the first code that remains DTE at runtime.
    For the ordinary/full French profile used by non-event CA resources this is
    ``$E6``.  The stock DTE table itself is not modified.

    This is a deterministic size optimization only: every chosen DTE byte expands
    to exactly the same two visible characters as the input.
    """
    if not 0xD3 <= upper_dte_threshold <= 0x100:
        raise ValueError(f"Invalid upper DTE threshold: ${upper_dte_threshold:02X}")

    usable_codes = list(range(0x60, 0x7D))
    if upper_dte_threshold <= 0xFF:
        usable_codes.extend(range(upper_dte_threshold, 0x100))
    pair_to_code: dict[str, int] = {}
    for code in usable_codes:
        pair = decode_dte_pair(rom, code)
        # Keep the first code if the stock table ever contains a duplicate pair.
        pair_to_code.setdefault(pair, code)

    out = bytearray()
    pos = 0
    while pos < len(text):
        char = text[pos]
        if char == "\n":
            out.append(0x7F)
            pos += 1
            continue
        if pos + 1 < len(text):
            pair = text[pos:pos + 2]
            code = pair_to_code.get(pair)
            if code is not None:
                out.append(code)
                pos += 2
                continue
        try:
            direct_code = TEXT_TO_CODE[char]
        except KeyError as exc:
            raise ValueError(f"Unsupported editable text character: {char!r}") from exc
        if direct_code >= upper_dte_threshold:
            raise ValueError(
                f"Editable character {char!r} uses direct code ${direct_code:02X}, "
                f"but runtime bytes >= ${upper_dte_threshold:02X} are DTE in this profile"
            )
        out.append(direct_code)
        pos += 1
    return bytes(out)


def decode_text_bytes_with_dte_threshold(
    rom: bytes, data: bytes, *, upper_dte_threshold: int
) -> str:
    """Decode text under a project runtime direct/upper-DTE boundary.

    Lower DTE ``$60-$7C`` is always active. Bytes ``$80`` through the byte before
    ``upper_dte_threshold`` are treated as direct glyphs when a mapping exists;
    bytes at/above the threshold use the stock upper-DTE table.
    """
    parts: list[str] = []
    for code in data:
        if code == 0x7F:
            parts.append("\n")
        elif 0x60 <= code <= 0x7C:
            parts.append(decode_dte_pair(rom, code))
        elif 0x80 <= code < upper_dte_threshold:
            piece = CODE_TO_TEXT.get(code)
            if piece is None:
                raise ValueError(f"Unsupported direct text byte ${code:02X}")
            parts.append(piece)
        elif upper_dte_threshold <= code <= 0xFF:
            parts.append(decode_dte_pair(rom, code))
        else:
            raise ValueError(f"Unsupported text byte ${code:02X}")
    return "".join(parts)
