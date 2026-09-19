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

def normalize_weapon_description_for_snes(text: str) -> tuple[str | None, list[str]]:
    """Normalize Android weapon-description layout to the validated SNES record geometry.

    Runtime validation proved that this panel consumes 30-character segments
    separated by ``$7F``.  Android line breaks/indentation are presentation-only;
    collapse them to the exact prose, prepend the stock one-cell inset, then
    slice at fixed 30-character boundaries.  A whitespace-only Android record
    returns ``None`` so the stock blank payload (four $7F bytes) is preserved
    byte-for-byte instead of being replaced with an empty record.
    """
    if not text.strip(" \t\r\n\u3000"):
        return None, ["blank→preserve stock payload"]
    logical = " " + " ".join(text.replace("\u3000", " ").split())
    if len(logical) > 150:
        raise ValueError(f"weapon description exceeds validated 5x30 cells: {len(logical)}")
    chunks = [logical[i:i + 30] for i in range(0, len(logical), 30)]
    return "\n".join(chunks), ["Android whitespace→fixed 30-cell SNES segments"]

