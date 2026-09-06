"""Deterministic Android-French -> SNES dialogue formatting helpers.

Alignment and layout are intentionally separate.  This module accepts only an
already-established Android/SNES mapping and converts the localized prose into
existing SNES text-token slots without adding, removing or reordering event
commands.

The first runtime checkpoint is deliberately narrow (event $0107), but the
binding and VWF wrapping primitives are generic enough to extend after runtime
validation. The offline formatter uses a conservative 240-pixel VWF target and
also enforces component 06's runtime-validated 38-decoded-character parser
capacity. The renderer bitmap itself is 32 cells / 256 pixels; that physical
capacity is a separate runtime concern, not the only offline wrapping limit.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from shared.french_charset import DIALOGUE_FRENCH_CHARS, glyph_bytes
from shared.stock_text import TEXT_TO_CODE
from shared.vwf_metrics import validated_advance

FONT_BASE = 0x12DC00
FONT_GLYPH_COUNT = 128
FONT_ROWS = 12
DIALOGUE_WRAP_PIXELS = 240
DIALOGUE_WRAP_CHARS = 38
MAX_PLAYER_NAME_CHARS = 9

PLAYER_PLACEHOLDER_RE = re.compile(r"%S\((\d+),0\)")


@dataclass(frozen=True)
class TextSlot:
    text_id: str
    source: str


@dataclass(frozen=True)
class PlayerSlot:
    index: int


BindingSlot = TextSlot | PlayerSlot


def make_dialogue_advances(base: bytes) -> dict[str, int]:
    """Return validated VWF advances for every editable SNES text character."""
    font = bytearray(base[FONT_BASE:FONT_BASE + FONT_GLYPH_COUNT * FONT_ROWS])
    if len(font) != FONT_GLYPH_COUNT * FONT_ROWS:
        raise ValueError("Reference ROM is too small for the stock dialogue font")

    french = glyph_bytes(DIALOGUE_FRENCH_CHARS)
    french_first = min(TEXT_TO_CODE[ch] for ch in DIALOGUE_FRENCH_CHARS)
    french_start = (french_first - 0x80) * FONT_ROWS
    font[french_start:french_start + len(french)] = french

    by_code: dict[int, int] = {}
    for code in range(0x80, 0x100):
        rows = font[(code - 0x80) * FONT_ROWS:(code - 0x80 + 1) * FONT_ROWS]
        by_code[code] = validated_advance(code, rows)

    advances: dict[str, int] = {}
    for char, code in TEXT_TO_CODE.items():
        if 0x80 <= code <= 0xFF:
            advances[char] = by_code[code]
    return advances


def player_placeholder_width(advances: dict[str, int]) -> int:
    """Conservative width for a dynamic name after the validated 9-char patch."""
    # Names use the same direct glyph set as dialogue.  Use the maximum editable
    # glyph advance so wrapping remains safe for every possible 9-character name.
    max_advance = max(advances.values())
    return MAX_PLAYER_NAME_CHARS * max_advance


def normalize_android_french(text: str) -> str:
    """Discard Android presentation whitespace without rewriting the prose.

    ``_`` and U+3000 are presentation/layout separators in the Android assets;
    they are not SNES glyphs. Android hard line breaks likewise belong to the
    source presentation and are reflowed against the validated SNES VWF.
    """
    text = text.replace("\r", " ").replace("\n", " ")
    text = text.replace("_", " ").replace("\u3000", " ")
    return " ".join(text.split())


def placeholder_sequence(text: str) -> tuple[int, ...]:
    return tuple(int(match.group(1)) for match in PLAYER_PLACEHOLDER_RE.finditer(text))


def _markup_width(text: str, advances: dict[str, int], placeholder_width: int) -> int:
    width = 0
    cursor = 0
    for match in PLAYER_PLACEHOLDER_RE.finditer(text):
        for char in text[cursor:match.start()]:
            try:
                width += advances[char]
            except KeyError as exc:
                raise ValueError(f"Unsupported editable dialogue character: {char!r}") from exc
        width += placeholder_width
        cursor = match.end()
    for char in text[cursor:]:
        try:
            width += advances[char]
        except KeyError as exc:
            raise ValueError(f"Unsupported editable dialogue character: {char!r}") from exc
    return width


def _markup_chars(text: str, placeholder_chars: int = MAX_PLAYER_NAME_CHARS) -> int:
    """Count decoded visible characters, expanding PLAYER_NAME conservatively."""
    count = 0
    cursor = 0
    for match in PLAYER_PLACEHOLDER_RE.finditer(text):
        count += len(text[cursor:match.start()])
        count += placeholder_chars
        cursor = match.end()
    count += len(text[cursor:])
    return count


def wrap_markup(
    text: str,
    advances: dict[str, int],
    *,
    max_pixels: int = DIALOGUE_WRAP_PIXELS,
    max_chars: int = DIALOGUE_WRAP_CHARS,
    placeholder_width: int | None = None,
    placeholder_chars: int = MAX_PLAYER_NAME_CHARS,
) -> tuple[str, list[int], list[int]]:
    """Word-wrap text containing ``%S(index,0)`` placeholders.

    Wrapping is performed only at ordinary spaces. A line must satisfy both the
    conservative pixel budget and the runtime-validated 38-decoded-character
    parser capacity. Dynamic names are measured as unbreakable 9-character
    worst-case spans for both constraints. The returned markup still contains
    the placeholders; callers bind them back to existing PLAYER_NAME commands.
    """
    if placeholder_width is None:
        placeholder_width = player_placeholder_width(advances)
    words = text.split()
    if not words:
        return "", []

    space_width = advances[" "]
    lines: list[str] = []
    line_words: list[str] = []
    line_width = 0
    line_chars = 0
    line_widths: list[int] = []
    line_char_counts: list[int] = []

    for word in words:
        word_width = _markup_width(word, advances, placeholder_width)
        word_chars = _markup_chars(word, placeholder_chars)
        if word_width > max_pixels:
            raise ValueError(
                f"Unbreakable dialogue word exceeds {max_pixels}px: {word!r} ({word_width}px)"
            )
        if word_chars > max_chars:
            raise ValueError(
                f"Unbreakable dialogue word exceeds {max_chars} decoded characters: "
                f"{word!r} ({word_chars})"
            )
        candidate_width = word_width if not line_words else line_width + space_width + word_width
        candidate_chars = word_chars if not line_words else line_chars + 1 + word_chars
        if line_words and (candidate_width > max_pixels or candidate_chars > max_chars):
            lines.append(" ".join(line_words))
            line_widths.append(line_width)
            line_char_counts.append(line_chars)
            line_words = [word]
            line_width = word_width
            line_chars = word_chars
        else:
            if line_words:
                line_width += space_width
                line_chars += 1
            line_words.append(word)
            line_width += word_width
            line_chars += word_chars

    if line_words:
        lines.append(" ".join(line_words))
        line_widths.append(line_width)
        line_char_counts.append(line_chars)
    return "\n".join(lines), line_widths, line_char_counts


def event_text_index(document: dict) -> tuple[dict[str, dict], dict[str, dict]]:
    """Return ``(text-id -> token metadata, event-id -> event)``."""
    by_id: dict[str, dict] = {}
    by_event: dict[str, dict] = {}
    for event in document.get("events", []):
        event_id = event["event_id"]
        by_event[event_id] = event
        for token_index, token in enumerate(event.get("tokens", [])):
            if token.get("type") != "text":
                continue
            text_id = token["id"]
            if text_id in by_id:
                raise ValueError(f"Duplicate dialogue source ID {text_id}")
            by_id[text_id] = {
                "event_id": event_id,
                "token_index": token_index,
                "source": token["source"],
            }
    return by_id, by_event


def binding_slots(document: dict, mapping: dict) -> list[BindingSlot]:
    """Recover the exact mapped text/PLAYER_NAME stream from canonical tokens.

    The current formatter intentionally rejects mappings that cross any command
    other than PLAYER_NAME. This prevents localized prose from being moved across
    WAITs, animations, choices or other event side effects before that behavior
    has been runtime-validated.
    """
    by_id, by_event = event_text_index(document)
    snes_ids = mapping.get("snes_ids", [])
    if not snes_ids:
        raise ValueError("Dialogue mapping has no SNES text IDs")
    try:
        event_id = by_id[snes_ids[0]]["event_id"]
    except KeyError as exc:
        raise ValueError(f"Unknown dialogue source ID {snes_ids[0]}") from exc
    if any(by_id[text_id]["event_id"] != event_id for text_id in snes_ids):
        raise ValueError("One dialogue mapping spans multiple SNES events")
    if mapping.get("event_id") != event_id:
        raise ValueError(
            f"Dialogue mapping event mismatch for {snes_ids[0]}: {mapping.get('event_id')} vs {event_id}"
        )

    event = by_event[event_id]
    token_indexes = [by_id[text_id]["token_index"] for text_id in snes_ids]
    if token_indexes != sorted(token_indexes):
        raise ValueError(f"Dialogue mapping SNES IDs are not in token order: {snes_ids}")
    selected = set(snes_ids)
    slots: list[BindingSlot] = []
    for token in event["tokens"][token_indexes[0]:token_indexes[-1] + 1]:
        kind = token.get("type")
        if kind == "text":
            if token["id"] not in selected:
                raise ValueError(
                    f"Mapping {snes_ids} crosses unmapped text token {token['id']}; defer structural binding"
                )
            slots.append(TextSlot(token["id"], token["source"]))
        elif kind == "command" and token.get("name") == "PLAYER_NAME":
            args = token.get("args", "00").split()
            if not args:
                raise ValueError("PLAYER_NAME command has no index")
            slots.append(PlayerSlot(int(args[0], 16)))
        else:
            raise ValueError(
                f"Mapping {snes_ids} crosses {kind} {token.get('name', '')!r}; defer structural binding"
            )

    rendered = "".join(
        slot.source if isinstance(slot, TextSlot) else f"%S({slot.index},0)"
        for slot in slots
    )
    if rendered != mapping.get("source_display", ""):
        raise ValueError(
            f"Canonical binding stream for {snes_ids} no longer equals alignment source_display"
        )
    return slots


def _leading_newlines(text: str) -> int:
    return len(text) - len(text.lstrip("\n"))


def _trailing_newlines(text: str) -> int:
    return len(text) - len(text.rstrip("\n"))


def source_visible_line_budget(source_display: str) -> int:
    """Return the explicit source-line budget used by the first format pilot.

    This deliberately handles only source spans that already carry explicit
    line structure. Later expansion can add a validated stock auto-wrap simulator
    for long no-newline source spans.
    """
    lines = [line for line in source_display.split("\n") if line.strip()]
    return max(1, len(lines))


def bind_wrapped_markup(slots: list[BindingSlot], wrapped: str) -> dict[str, str]:
    """Replace placeholders with existing PLAYER_NAME slots and return text values.

    Each literal run between placeholders must map to exactly one existing text
    token. Multi-text runs are intentionally deferred until a later validated
    structural-distribution step.
    """
    placeholders = list(PLAYER_PLACEHOLDER_RE.finditer(wrapped))
    literal_runs: list[str] = []
    cursor = 0
    for match in placeholders:
        literal_runs.append(wrapped[cursor:match.start()])
        cursor = match.end()
    literal_runs.append(wrapped[cursor:])

    slot_runs: list[list[TextSlot]] = [[]]
    player_indexes: list[int] = []
    for slot in slots:
        if isinstance(slot, TextSlot):
            slot_runs[-1].append(slot)
        else:
            player_indexes.append(slot.index)
            slot_runs.append([])

    markup_indexes = [int(match.group(1)) for match in placeholders]
    if tuple(markup_indexes) != tuple(player_indexes):
        raise ValueError(
            f"French PLAYER_NAME sequence {tuple(markup_indexes)} does not match SNES {tuple(player_indexes)}"
        )
    if len(literal_runs) != len(slot_runs):
        raise AssertionError("Placeholder/literal run accounting mismatch")

    translations: dict[str, str] = {}
    for run, text_slots in zip(literal_runs, slot_runs, strict=True):
        if not text_slots:
            if run:
                raise ValueError(
                    "Localized literal text exists where the SNES stream has no text token around PLAYER_NAME"
                )
            continue
        if len(text_slots) != 1:
            raise ValueError(
                "Localized literal run spans multiple SNES text tokens; defer deterministic distribution"
            )
        translations[text_slots[0].text_id] = run
    return translations


def format_mapping(
    document: dict,
    mapping: dict,
    advances: dict[str, int],
    *,
    max_pixels: int = DIALOGUE_WRAP_PIXELS,
) -> tuple[dict[str, str], dict]:
    """Format one already accepted mapping into existing SNES text-token values."""
    slots = binding_slots(document, mapping)
    source_display = mapping["source_display"]
    french_raw = mapping.get("french_display", "")
    if not french_raw:
        raise ValueError("Accepted dialogue mapping has no French Android text")

    source_placeholders = tuple(slot.index for slot in slots if isinstance(slot, PlayerSlot))
    french_normalized = normalize_android_french(french_raw)
    french_placeholders = placeholder_sequence(french_normalized)
    if source_placeholders != french_placeholders:
        raise ValueError(
            f"French PLAYER_NAME sequence {french_placeholders} does not match SNES {source_placeholders}"
        )

    # Preserve only hard leading/trailing line motion from the canonical SNES
    # token stream. Android presentation wraps are discarded and recreated from
    # validated VWF widths.
    text_slots = [slot for slot in slots if isinstance(slot, TextSlot)]
    lead = _leading_newlines(text_slots[0].source)
    trail = _trailing_newlines(text_slots[-1].source)

    wrapped, widths, char_counts = wrap_markup(french_normalized, advances, max_pixels=max_pixels)
    line_budget = source_visible_line_budget(source_display)
    if len(widths) > line_budget:
        raise ValueError(
            f"French VWF needs {len(widths)} line(s), source span exposes {line_budget}: {mapping['snes_ids']}"
        )

    translations = bind_wrapped_markup(slots, wrapped)
    first_id = text_slots[0].text_id
    last_id = text_slots[-1].text_id
    translations[first_id] = "\n" * lead + translations[first_id]
    translations[last_id] = translations[last_id] + "\n" * trail

    # Final byte-level charset check before the translation JSON reaches 08.
    for text_id, text in translations.items():
        for char in text:
            if char == "\n":
                continue
            if char not in TEXT_TO_CODE:
                raise ValueError(f"{text_id}: unsupported formatted character {char!r}")

    report = {
        "event_id": mapping["event_id"],
        "snes_ids": mapping["snes_ids"],
        "android_ids": mapping.get("android_ids", []),
        "confidence": mapping.get("confidence"),
        "source_display": source_display,
        "android_french_raw": french_raw,
        "android_french_normalized": french_normalized,
        "formatted_markup": "\n" * lead + wrapped + "\n" * trail,
        "line_widths_pixels": widths,
        "line_decoded_character_counts": char_counts,
        "source_visible_line_budget": line_budget,
        "formatted_entries": [
            {"id": text_id, "text": translations[text_id]} for text_id in mapping["snes_ids"]
        ],
    }
    return translations, report


def make_translation_document(entries: Iterable[tuple[str, str]], *, group: str) -> dict:
    ordered = [{"id": text_id, "text": text} for text_id, text in entries]
    return {
        "format_version": 1,
        "language": "fr",
        "source_asset": "dialogues.json",
        "groups": [{"group": group, "entries": ordered}],
    }
