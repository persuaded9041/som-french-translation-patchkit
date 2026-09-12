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
        raise RuntimeError("shared/charset/charset.json has no characters")

    decoded: list[tuple[str, int]] = []
    for entry in chars:
        if not isinstance(entry, dict) or not isinstance(entry.get("char"), str):
            raise RuntimeError("shared/charset/charset.json has a malformed character entry")
        try:
            code = int(entry["code"], 16)
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("shared/charset/charset.json has a malformed character code") from exc
        if len(entry["char"]) != 1 or not 0 <= code <= 0xFF:
            raise RuntimeError("shared/charset/charset.json character entries must be one glyph / one byte")
        decoded.append((entry["char"], code))

    glyphs = [char for char, _ in decoded]
    codes = [code for _, code in decoded]
    if len(glyphs) != len(set(glyphs)):
        raise RuntimeError("shared/charset/charset.json contains duplicate characters")
    if len(codes) != len(set(codes)):
        raise RuntimeError("shared/charset/charset.json contains duplicate character codes")
    if codes != sorted(codes):
        raise RuntimeError("shared/charset/charset.json characters must be ordered by code")

    try:
        first_code = int(data["first_code"], 16)
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("shared/charset/charset.json has an invalid first_code") from exc
    if first_code != codes[0]:
        raise RuntimeError("shared/charset/charset.json first_code does not match the first character")

    profiles = data.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        raise RuntimeError("shared/charset/charset.json has no profiles")
    known = set(glyphs)
    for name, profile in profiles.items():
        if not isinstance(profile, dict) or not isinstance(profile.get("chars"), list):
            raise RuntimeError(f"French charset profile {name!r} is malformed")
        profile_chars = profile["chars"]
        if not profile_chars or any(not isinstance(char, str) or char not in known for char in profile_chars):
            raise RuntimeError(f"French charset profile {name!r} contains unknown characters")
        if len(profile_chars) != len(set(profile_chars)):
            raise RuntimeError(f"French charset profile {name!r} contains duplicate characters")
        try:
            threshold = int(profile["dte_threshold"], 16)
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(f"French charset profile {name!r} has an invalid dte_threshold") from exc
        if not 0 <= threshold <= 0xFF:
            raise RuntimeError(f"French charset profile {name!r} has an invalid dte_threshold")
    return data


DEFINITION = _load_definition()
CHAR_TO_CODE = {entry["char"]: int(entry["code"], 16) for entry in DEFINITION["characters"]}
CODE_TO_CHAR = {code: char for char, code in CHAR_TO_CODE.items()}
FIRST_CODE = int(DEFINITION["first_code"], 16)
ATLAS_CHARS = "".join(entry["char"] for entry in DEFINITION["characters"])
ATLAS_INDEX = {char: index for index, char in enumerate(ATLAS_CHARS)}


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


def profile_first_code(name: str) -> int:
    chars = profile_chars(name)
    if not chars:
        raise ValueError(f"French charset profile {name!r} is empty")
    codes = [CHAR_TO_CODE[char] for char in chars]
    first = min(codes)
    if codes != list(range(first, first + len(codes))):
        raise RuntimeError(f"French charset profile {name!r} must be contiguous and code-ordered")
    return first


FULL_FRENCH_CHARS = profile_chars("full_french")
BASIC_FRENCH_CHARS = profile_chars("basic_french")
DIALOGUE_FRENCH_CHARS = profile_chars("dialogue_french")
FULL_DTE_THRESHOLD = profile_threshold("full_french")
BASIC_DTE_THRESHOLD = profile_threshold("basic_french")
DIALOGUE_DTE_THRESHOLD = profile_threshold("dialogue_french")


def profile_mapping(name: str) -> dict[str, int]:
    return {char: CHAR_TO_CODE[char] for char in profile_chars(name)}


def glyph_bytes(chars: str | None = None) -> bytes:
    """Return SNES 1bpp rows for the requested canonical glyph sequence.

    The shared PNG is one contiguous 8x12 atlas ordered by direct character
    code. Profiles may request contiguous subsets (for example the legacy
    French-only D4-E5 range or the dialogue D3-E7 range). Any non-transparent
    PNG pixel is ink.
    """
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError(
            "Pillow is required to read shared/charset/french_glyphs.png"
        ) from exc

    wanted = ATLAS_CHARS if chars is None else chars
    unknown = [char for char in wanted if char not in ATLAS_INDEX]
    if unknown:
        raise RuntimeError(f"No canonical direct glyph for {unknown[0]!r}")

    with Image.open(GLYPH_FILE) as source:
        image = source.convert("RGBA")
        expected = (len(ATLAS_CHARS) * 8, 12)
        if image.size != expected:
            raise RuntimeError(
                f"{GLYPH_FILE} must be {expected[0]}x{expected[1]} pixels, got "
                f"{image.size[0]}x{image.size[1]}"
            )

        out = bytearray()
        for char in wanted:
            glyph_index = ATLAS_INDEX[char]
            for y in range(12):
                row = 0
                for x in range(8):
                    if image.getpixel((glyph_index * 8 + x, y))[3] != 0:
                        row |= 0x80 >> x
                out.append(row)
    return bytes(out)
