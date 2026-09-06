"""Deterministic Android-French -> SNES dialogue formatting helpers.

Alignment and layout are intentionally separate.  This module accepts only an
already-established Android/SNES mapping and converts the localized prose into
existing SNES text-token slots. The normal path preserves every event command.
A separately gated extra-page path may insert only the stock WAIT $00 +
TEXT_CLEAR transition when a validated translation needs one additional page.

The first runtime checkpoint was deliberately narrow (event $0107); later
complete-event batches reuse the same binding and VWF primitives. The explicit
extra-page transition and sentence-aware boundary placement are runtime-validated
on $010F; later batches reuse that rule and prefer page boundaries after complete
sentences.
The offline formatter uses a conservative 240-pixel VWF target and also enforces
component 06's runtime-validated 38-decoded-character parser capacity. The renderer bitmap itself is 32 cells / 256 pixels; that physical
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
DIALOGUE_PAGE_LINES = 3
MAX_PLAYER_NAME_CHARS = 9
PLAYER_NAME_PARSER_SAFETY_UNITS = 1

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
    placeholder_parser_safety_units: int = PLAYER_NAME_PARSER_SAFETY_UNITS,
) -> tuple[str, list[int], list[int], list[int]]:
    """Word-wrap text containing ``%S(index,0)`` placeholders.

    Wrapping is performed only at ordinary spaces. A line must satisfy both the
    conservative pixel budget and the runtime-validated 38-unit parser
    capacity. Dynamic names are measured as unbreakable 9-character worst-case
    spans. Runtime batch-1 testing showed that an exact-capacity line containing
    PLAYER_NAME is not safe, so each placeholder reserves one additional parser
    safety unit for the temporary-source switch. The returned markup still
    contains the placeholders; callers bind them back to existing PLAYER_NAME
    commands.
    """
    if placeholder_width is None:
        placeholder_width = player_placeholder_width(advances)
    words = text.split()
    if not words:
        return "", [], [], []

    space_width = advances[" "]
    lines: list[str] = []
    line_words: list[str] = []
    line_width = 0
    line_chars = 0
    line_parser_units = 0
    line_widths: list[int] = []
    line_char_counts: list[int] = []
    line_parser_unit_counts: list[int] = []

    for word in words:
        word_width = _markup_width(word, advances, placeholder_width)
        word_chars = _markup_chars(word, placeholder_chars)
        placeholder_count = len(PLAYER_PLACEHOLDER_RE.findall(word))
        word_parser_units = word_chars + placeholder_count * placeholder_parser_safety_units
        if word_width > max_pixels:
            raise ValueError(
                f"Unbreakable dialogue word exceeds {max_pixels}px: {word!r} ({word_width}px)"
            )
        if word_parser_units > max_chars:
            raise ValueError(
                f"Unbreakable dialogue word exceeds {max_chars} parser units: "
                f"{word!r} ({word_parser_units})"
            )
        candidate_width = word_width if not line_words else line_width + space_width + word_width
        candidate_chars = word_chars if not line_words else line_chars + 1 + word_chars
        candidate_parser_units = (
            word_parser_units if not line_words else line_parser_units + 1 + word_parser_units
        )
        if line_words and (candidate_width > max_pixels or candidate_parser_units > max_chars):
            lines.append(" ".join(line_words))
            line_widths.append(line_width)
            line_char_counts.append(line_chars)
            line_parser_unit_counts.append(line_parser_units)
            line_words = [word]
            line_width = word_width
            line_chars = word_chars
            line_parser_units = word_parser_units
        else:
            if line_words:
                line_width += space_width
                line_chars += 1
                line_parser_units += 1
            line_words.append(word)
            line_width += word_width
            line_chars += word_chars
            line_parser_units += word_parser_units

    if line_words:
        lines.append(" ".join(line_words))
        line_widths.append(line_width)
        line_char_counts.append(line_chars)
        line_parser_unit_counts.append(line_parser_units)
    return "\n".join(lines), line_widths, line_char_counts, line_parser_unit_counts


def _page_line_counts(line_count: int, *, page_lines: int = DIALOGUE_PAGE_LINES) -> tuple[int, ...]:
    """Fallback distribution when no safe sentence-boundary page split exists.

    The stock box safely exposes three physical text lines. The preferred
    extra-page path breaks between complete sentences. Only when that cannot be
    done safely do we balance four lines as 2+2, five as 3+2 and six as 3+3 to
    avoid a one-line orphan page.
    """
    if line_count <= page_lines:
        return (line_count,)
    if line_count > page_lines * 2:
        raise ValueError(
            f"Extra-page pilot supports at most {page_lines * 2} wrapped lines; got {line_count}"
        )
    first = page_lines
    second = line_count - first
    if second == 1:
        first -= 1
        second += 1
    return (first, second)


def _balanced_wrap_markup(
    text: str,
    advances: dict[str, int],
    *,
    line_count: int,
    page_line_counts: tuple[int, ...],
    max_pixels: int = DIALOGUE_WRAP_PIXELS,
    max_chars: int = DIALOGUE_WRAP_CHARS,
    placeholder_width: int | None = None,
    placeholder_chars: int = MAX_PLAYER_NAME_CHARS,
    placeholder_parser_safety_units: int = PLAYER_NAME_PARSER_SAFETY_UNITS,
) -> tuple[str, list[int], list[int], list[int]]:
    """Reflow into an exact number of balanced lines and explicit pages.

    This path is used only when the ordinary greedy wrapper proves that an
    accepted Android translation needs one additional dialogue page. It keeps
    the same validated pixel/parser constraints, but balances the fixed number
    of lines to avoid pathological orphan lines such as a lone ``?``.
    """
    if placeholder_width is None:
        placeholder_width = player_placeholder_width(advances)
    words = text.split()
    if not words:
        return "", [], [], []
    if line_count < 1 or line_count > len(words):
        raise ValueError(f"Cannot wrap {len(words)} word(s) into exactly {line_count} line(s)")
    if sum(page_line_counts) != line_count:
        raise ValueError("Page-line distribution does not equal requested line count")

    # Page breaks occur after these 1-based line numbers.
    page_break_after: set[int] = set()
    running = 0
    for count in page_line_counts[:-1]:
        running += count
        page_break_after.add(running)

    # Short French glue words make especially poor line/page endings. This is a
    # layout heuristic only; it never changes, drops or rewrites source words.
    weak_end_words = {
        "à", "au", "aux", "de", "du", "des", "et", "ou", "un", "une",
        "le", "la", "les", "ce", "ces", "tout", "toute", "tous", "toutes",
        "en", "dans", "sur", "pour", "avec", "sans", "que", "qui", "ne",
        "se", "son", "sa", "ses", "mon", "ma", "mes", "ton", "ta", "tes",
        "notre", "votre",
    }
    punctuation_only = {"?", "!", ";", ":", ",", ".", "…"}

    # The average rendered width gives a deterministic balancing target. The
    # dynamic-name width assumption is the same worst-case value used by the
    # ordinary wrapper.
    total_width = _markup_width(text, advances, placeholder_width)
    target_width = min(max_pixels, total_width / line_count)

    metrics_cache: dict[tuple[int, int], tuple[str, int, int, int]] = {}

    def metrics(start: int, end: int) -> tuple[str, int, int, int]:
        key = (start, end)
        cached = metrics_cache.get(key)
        if cached is not None:
            return cached
        value = " ".join(words[start:end])
        width = _markup_width(value, advances, placeholder_width)
        chars = _markup_chars(value, placeholder_chars)
        placeholders = len(PLAYER_PLACEHOLDER_RE.findall(value))
        parser_units = chars + placeholders * placeholder_parser_safety_units
        result = (value, width, chars, parser_units)
        metrics_cache[key] = result
        return result

    # Dynamic programming over word boundaries and exact line count.
    infinity = float("inf")
    memo: dict[tuple[int, int], tuple[float, tuple[tuple[str, int, int, int], ...]]] = {}

    def solve(word_index: int, line_index: int):
        key = (word_index, line_index)
        if key in memo:
            return memo[key]
        if line_index == line_count:
            result = (0.0, ()) if word_index == len(words) else (infinity, ())
            memo[key] = result
            return result

        lines_left_after = line_count - line_index - 1
        max_end = len(words) - lines_left_after
        best_cost = infinity
        best_path: tuple[tuple[str, int, int, int], ...] = ()
        for end in range(word_index + 1, max_end + 1):
            value, width, chars, parser_units = metrics(word_index, end)
            if width > max_pixels or parser_units > max_chars:
                # Adding more words cannot reduce either metric.
                break

            first_word = words[word_index]
            last_word = words[end - 1]
            cost = (width - target_width) ** 2
            if first_word in punctuation_only:
                cost += 100_000
            if last_word.lower() in weak_end_words:
                cost += 3_500
            if last_word in punctuation_only or last_word.endswith((".", "!", "?", "…")):
                cost -= 700

            one_based_line = line_index + 1
            if one_based_line in page_break_after:
                if last_word.lower() in weak_end_words:
                    cost += 7_000
                if last_word in punctuation_only or last_word.endswith((".", "!", "?", "…")):
                    cost -= 1_200

            child_cost, child_path = solve(end, line_index + 1)
            total_cost = cost + child_cost
            if total_cost < best_cost:
                best_cost = total_cost
                best_path = ((value, width, chars, parser_units),) + child_path

        memo[key] = (best_cost, best_path)
        return memo[key]

    cost, path = solve(0, 0)
    if cost == infinity or len(path) != line_count:
        raise ValueError(f"No valid balanced {line_count}-line wrapping exists")

    lines = [entry[0] for entry in path]
    widths = [entry[1] for entry in path]
    char_counts = [entry[2] for entry in path]
    parser_units = [entry[3] for entry in path]

    parts: list[str] = []
    cursor = 0
    for page_index, count in enumerate(page_line_counts):
        page = "\n".join(lines[cursor:cursor + count])
        parts.append(page)
        cursor += count
    return "\f".join(parts), widths, char_counts, parser_units



def _sentence_boundary_positions(text: str) -> tuple[int, ...]:
    """Return conservative page-break positions after complete sentences.

    Android prose is already normalized to single spaces before this helper is
    called. ``!``, ``?`` and the Unicode ellipsis are always strong boundaries.
    A full stop is accepted when it terminates a normal word (rather than a
    one/two-letter abbreviation); for ``...`` only the final dot is considered.
    Closing quote/bracket punctuation remains attached to the sentence.
    """
    positions: list[int] = []
    closers = "\"”»')]"
    for index, char in enumerate(text):
        if char not in ".!?…":
            continue
        # For an ellipsis written as three dots, consider only the final dot.
        if char == "." and index + 1 < len(text) and text[index + 1] == ".":
            continue
        if char == "." and not (index >= 2 and text[index - 1] == "." and text[index - 2] == "."):
            # Avoid treating short abbreviations such as ``M. Dupont`` as a
            # semantic page boundary. This is deliberately conservative.
            start = index - 1
            while start >= 0 and (text[start].isalpha() or text[start] in "'-"):
                start -= 1
            word = text[start + 1:index]
            if 0 < len(word) <= 2:
                continue

        end = index + 1
        while end < len(text) and text[end] in closers:
            end += 1
        if end == len(text):
            continue  # no following page
        if not text[end].isspace():
            continue
        while end < len(text) and text[end].isspace():
            end += 1
        if end < len(text):
            positions.append(end)
    return tuple(positions)


def _sentence_aware_extra_page_wrap(
    text: str,
    advances: dict[str, int],
    *,
    max_pixels: int = DIALOGUE_WRAP_PIXELS,
    max_chars: int = DIALOGUE_WRAP_CHARS,
) -> tuple[str, list[int], list[int], list[int], tuple[int, int], str]:
    """Wrap one overflowing prose block onto at most two pages.

    Prefer the latest complete-sentence boundary for which both the prefix and
    suffix fit independently within the stock three-line page. Each page is then
    balanced internally while preserving the same pixel/parser constraints. A
    3+1 layout is therefore preferred over an artificial 2+2 split when the
    first three lines end on a complete sentence. If no safe sentence boundary
    exists, retain the earlier deterministic balanced fallback.
    """
    candidates: list[tuple[int, str, str, int, int]] = []
    for boundary in _sentence_boundary_positions(text):
        first = text[:boundary].strip()
        second = text[boundary:].strip()
        if not first or not second:
            continue
        try:
            _, first_widths, _, _ = wrap_markup(
                first, advances, max_pixels=max_pixels, max_chars=max_chars
            )
            _, second_widths, _, _ = wrap_markup(
                second, advances, max_pixels=max_pixels, max_chars=max_chars
            )
        except ValueError:
            continue
        if not (1 <= len(first_widths) <= DIALOGUE_PAGE_LINES):
            continue
        if not (1 <= len(second_widths) <= DIALOGUE_PAGE_LINES):
            continue
        candidates.append((boundary, first, second, len(first_widths), len(second_widths)))

    if candidates:
        # The latest safe sentence boundary keeps as much complete prose as
        # possible on the current page and minimizes unnecessary page changes.
        boundary, first, second, first_lines, second_lines = max(candidates, key=lambda item: item[0])
        first_wrapped, first_widths, first_chars, first_units = _balanced_wrap_markup(
            first,
            advances,
            line_count=first_lines,
            page_line_counts=(first_lines,),
            max_pixels=max_pixels,
            max_chars=max_chars,
        )
        second_wrapped, second_widths, second_chars, second_units = _balanced_wrap_markup(
            second,
            advances,
            line_count=second_lines,
            page_line_counts=(second_lines,),
            max_pixels=max_pixels,
            max_chars=max_chars,
        )
        return (
            first_wrapped + "\f" + second_wrapped,
            first_widths + second_widths,
            first_chars + second_chars,
            first_units + second_units,
            (first_lines, second_lines),
            "sentence_boundary",
        )

    greedy, widths, chars, units = wrap_markup(
        text, advances, max_pixels=max_pixels, max_chars=max_chars
    )
    del greedy
    page_line_counts = _page_line_counts(len(widths))
    if len(page_line_counts) != 2:
        raise ValueError("Extra-page formatter inserts exactly one additional page")
    wrapped, widths, chars, units = _balanced_wrap_markup(
        text,
        advances,
        line_count=sum(page_line_counts),
        page_line_counts=page_line_counts,
        max_pixels=max_pixels,
        max_chars=max_chars,
    )
    return wrapped, widths, chars, units, page_line_counts, "balanced_fallback"


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
    allow_one_extra_page: bool = False,
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

    wrapped, widths, char_counts, parser_unit_counts = wrap_markup(
        french_normalized, advances, max_pixels=max_pixels
    )
    line_budget = source_visible_line_budget(source_display)
    inserted_page_breaks = 0
    page_line_counts = (len(widths),)
    page_break_strategy: str | None = None
    if len(widths) > line_budget:
        if not allow_one_extra_page:
            raise ValueError(
                f"French VWF needs {len(widths)} line(s), source span exposes {line_budget}: {mapping['snes_ids']}"
            )
        if line_budget != DIALOGUE_PAGE_LINES:
            raise ValueError(
                f"Extra-page pilot requires a {DIALOGUE_PAGE_LINES}-line source page; "
                f"source span exposes {line_budget}: {mapping['snes_ids']}"
            )
        (
            wrapped,
            widths,
            char_counts,
            parser_unit_counts,
            page_line_counts,
            page_break_strategy,
        ) = _sentence_aware_extra_page_wrap(
            french_normalized,
            advances,
            max_pixels=max_pixels,
            max_chars=DIALOGUE_WRAP_CHARS,
        )
        inserted_page_breaks = 1

    translations = bind_wrapped_markup(slots, wrapped)
    first_id = text_slots[0].text_id
    last_id = text_slots[-1].text_id
    translations[first_id] = "\n" * lead + translations[first_id]
    translations[last_id] = translations[last_id] + "\n" * trail

    # Final byte-level charset check before the translation JSON reaches 08.
    for text_id, text in translations.items():
        for char in text:
            if char in ("\n", "\f"):
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
        "line_parser_unit_counts": parser_unit_counts,
        "source_visible_line_budget": line_budget,
        "page_line_counts": list(page_line_counts),
        "inserted_page_break_count": inserted_page_breaks,
        "page_break_encoding": "WAIT $00 + TEXT_CLEAR" if inserted_page_breaks else None,
        "page_break_strategy": page_break_strategy,
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
