"""Shared font-geometry helpers for the patchkit's VWF builders.

This module intentionally contains no renderer policy.  Components 05 and 06
have different runtime integrations, but both need the same primitive operations
for measuring 8x12 glyph ink and deriving compact left-aligned glyph rows.
"""

from __future__ import annotations


def ink_bounds(rows: bytes | bytearray) -> tuple[int, int] | None:
    """Return inclusive left/right ink columns for an 8-pixel glyph."""
    columns = [
        x
        for row in rows
        for x in range(8)
        if row & (0x80 >> x)
    ]
    if not columns:
        return None
    return min(columns), max(columns)


def left_compact_glyph(rows: bytes | bytearray) -> tuple[bytes, int]:
    """Left-align one 8x12 glyph and return ``(rows, ink_width)``.

    Empty glyphs are returned as twelve zero rows with an ink width of zero.
    """
    bounds = ink_bounds(rows)
    if bounds is None:
        return bytes(len(rows)), 0
    left, right = bounds
    return bytes(((row << left) & 0xFF) for row in rows), right - left + 1
