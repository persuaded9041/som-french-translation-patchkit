"""Insertion-side helpers for Android-derived CA text-resource translations."""
from __future__ import annotations


def normalize_for_snes(text: str) -> tuple[str, list[str]]:
    """Normalize representation-only Android differences for the SNES charset.

    This does not alter lexical wording.  U+3000 is used by Android as a blank
    placeholder; straight double quotes are represented with the stock SNES
    opening/closing quote glyphs.
    """
    notes: list[str] = []
    if "\u3000" in text:
        text = text.replace("\u3000", " ")
        notes.append("U+3000→space")
    if '"' in text:
        chars: list[str] = []
        opening = True
        for ch in text:
            if ch == '"':
                chars.append("“" if opening else "”")
                opening = not opening
            else:
                chars.append(ch)
        text = "".join(chars)
        notes.append('straight quotes→“…”')
    return text, notes
