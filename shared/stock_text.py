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
