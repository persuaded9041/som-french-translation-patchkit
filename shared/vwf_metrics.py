"""Shared validated VWF framing and advance policy.

Components 05 and 06 integrate with different runtime paths, but they can use
one canonical glyph geometry policy.  The policy here matches the currently
runtime-validated dialogue renderer:

* letters and the shared French charset are compacted to their validated frame;
* punctuation keeps the validated one-pixel bearings (with the dedicated colon
  case);
* digits and unvalidated symbols retain the conservative stock-geometry path;
* space advances by four pixels.

The runtime compositor itself remains in :mod:`shared.vwf_compositor`.
"""

from __future__ import annotations

from shared.vwf_geometry import ink_bounds


def validated_left_shift(code: int) -> int:
    """Return the validated number of pixels to shift a stock glyph row left."""
    # Lowercase a-z.
    if 0x81 <= code <= 0x9A:
        if code in (0x89, 0x8C):  # i, l
            return 3
        if code in (0x8A, 0x94):  # j, t
            return 2
        return 1

    # Uppercase A-Z.
    if 0x9B <= code <= 0xB4:
        return 3 if code == 0xA3 else 1  # I vs A-H/J-Z

    # Runtime-validated punctuation framing.
    if code in (0xC4, 0xC5, 0xCC):
        return 1
    if code in (0xC8, 0xCB):
        return 2

    # Canonical French glyphs: $D4-$E3 have a one-pixel stock left bearing;
    # full-width Œ/œ at $E4/$E5 remain unshifted.
    if 0xD4 <= code <= 0xE3:
        return 1

    return 0


def validated_advance(code: int, rows: bytes | bytearray) -> int:
    """Return the runtime-validated dialogue advance for one 8x12 glyph."""
    if code == 0x80:
        return 4

    bounds = ink_bounds(rows)
    if bounds is None:
        return 8

    left, right = bounds

    # Letters and canonical French glyphs use ink width + one separator pixel.
    if 0x81 <= code <= 0xB4 or 0xD4 <= code <= 0xE5:
        return min(8, (right - left + 1) + 1)

    # Colon is the validated isolated 2-left / 3-right framing case.
    if code == 0xC5:
        return min(8, (right - left + 1) + 5)

    # Validated punctuation keeps one black pixel before and after the ink.
    # $CD is intentionally excluded and remains generic/conservative.
    if 0xBF <= code <= 0xC4 or code in (0xC6, 0xC7, 0xC8, 0xC9, 0xCA, 0xCB, 0xCC):
        return min(8, (right - left + 1) + 2)

    # Digits and remaining symbols retain the conservative stock baseline.
    return min(8, right + 2)


def apply_validated_framing(code: int, rows: bytes | bytearray) -> bytes:
    """Bake the validated runtime left shift into one glyph bitmap."""
    shift = validated_left_shift(code)
    if not shift:
        return bytes(rows)
    return bytes(((row << shift) & 0xFF) for row in rows)
