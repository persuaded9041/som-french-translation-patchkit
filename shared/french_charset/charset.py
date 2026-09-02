from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFINITION_FILE = ROOT / "charset.json"
GLYPH_FILE = ROOT / "french_glyphs.png"


def _load_definition() -> dict:
    data = json.loads(DEFINITION_FILE.read_text(encoding="utf-8"))
    if data.get("format_version") != 1:
        raise RuntimeError("Unsupported shared French charset format")
    chars = data.get("characters")
    if not isinstance(chars, list) or not chars:
        raise RuntimeError("shared/french_charset/charset.json has no characters")
    return data


DEFINITION = _load_definition()
CHAR_TO_CODE = {entry["char"]: int(entry["code"], 16) for entry in DEFINITION["characters"]}
CODE_TO_CHAR = {code: char for char, code in CHAR_TO_CODE.items()}
FIRST_CODE = int(DEFINITION["first_code"], 16)
def profile_chars(name: str) -> str:
    try:
        return "".join(DEFINITION["profiles"][name]["chars"])
    except KeyError as exc:
        raise KeyError(f"Unknown French charset profile: {name}") from exc


def profile_threshold(name: str) -> int:
    try:
        return int(DEFINITION["profiles"][name]["dte_threshold"], 16)
    except KeyError as exc:
        raise KeyError(f"Unknown French charset profile: {name}") from exc


FULL_FRENCH_CHARS = profile_chars("full_french")
BASIC_FRENCH_CHARS = profile_chars("basic_french")
FULL_DTE_THRESHOLD = profile_threshold("full_french")
BASIC_DTE_THRESHOLD = profile_threshold("basic_french")



def profile_mapping(name: str) -> dict[str, int]:
    return {char: CHAR_TO_CODE[char] for char in profile_chars(name)}


def glyph_bytes(chars: str | None = None) -> bytes:
    """Return SNES 1bpp rows for the requested canonical glyph sequence.

    The shared PNG is an 18-glyph 8x12 RGBA atlas in the exact order defined
    by the full_french profile. Any non-transparent pixel is ink. Consumers may
    request a subset, but every character must belong to the canonical atlas.
    """
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError(
            "Pillow is required to read shared/french_charset/french_glyphs.png"
        ) from exc

    atlas_chars = FULL_FRENCH_CHARS
    wanted = atlas_chars if chars is None else chars
    image = Image.open(GLYPH_FILE).convert("RGBA")
    expected = (len(atlas_chars) * 8, 12)
    if image.size != expected:
        raise RuntimeError(
            f"{GLYPH_FILE} must be {expected[0]}x{expected[1]} pixels, got "
            f"{image.size[0]}x{image.size[1]}"
        )

    out = bytearray()
    for char in wanted:
        if char not in CHAR_TO_CODE or char not in atlas_chars:
            raise RuntimeError(f"No canonical French glyph for {char!r}")
        glyph_index = atlas_chars.index(char)
        for y in range(12):
            row = 0
            for x in range(8):
                if image.getpixel((glyph_index * 8 + x, y))[3] != 0:
                    row |= 0x80 >> x
            out.append(row)
    return bytes(out)
