"""Deterministic Android-French -> SNES dialogue formatting helpers.

Alignment and layout are intentionally separate. This module accepts only an
already-established Android/SNES mapping and binds localized prose to existing
SNES text-token slots. Event commands are preserved unless a narrowly validated
layout rule explicitly emits the stock ``WAIT $00 + TEXT_CLEAR`` page transition.

The formatter enforces the runtime-validated 216-pixel safe target, 38-parser-unit
capacity and three-line page limit. Dynamic names and structural boundaries are
handled only when the canonical event stream proves their placement; unsupported
structures are rejected rather than inferred.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
import re
from typing import Iterable

from shared.charset import DIALOGUE_FRENCH_CHARS, glyph_bytes
from shared.text.stock import TEXT_TO_CODE
from shared.vwf.metrics import validated_advance

FONT_BASE = 0x12DC00
FONT_GLYPH_COUNT = 128
FONT_ROWS = 12
DIALOGUE_WRAP_PIXELS = 216
DIALOGUE_WRAP_CHARS = 38
DIALOGUE_PAGE_LINES = 3
MAX_PLAYER_NAME_CHARS = 9
PLAYER_NAME_PARSER_SAFETY_UNITS = 1
TRANSLATION_CLEAR = "\v"

PLAYER_PLACEHOLDER_RE = re.compile(r"%S\((\d+),0\)")

# Formatting-only semantic boundaries inferred from the localized prose. They
# never rewrite words: they only mark places where a speaker/attribution should
# begin on a fresh physical line.
_STRONG_SENTENCE_END = r"(?:\.{3}|[.!?…])[”\"»')\]]*"
_SPEAKER_LABEL = (
    r"(?:%S\(\d+,0\)|[A-ZÀ-ÖØ-ÞŒ][A-Za-zÀ-ÖØ-öø-ÿŒœ'’.-]*)"
    r"(?:\s+[A-ZÀ-ÖØ-ÞŒ][A-Za-zÀ-ÖØ-öø-ÿŒœ'’.-]*){0,2}\s*:"
)
_SPEAKER_AFTER_SENTENCE_RE = re.compile(
    rf"(?P<end>{_STRONG_SENTENCE_END})\s+(?P<label>{_SPEAKER_LABEL})"
)
_ATTRIBUTION_AFTER_QUOTE_RE = re.compile(
    rf"(?P<end>{_STRONG_SENTENCE_END})\s+-\s+"
)
_PUNCTUATION_ATOM_RE = re.compile(r"^[!?;:,.…]+[”\"»')\]]*$")


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


def _normalize_android_quotes(text: str) -> str:
    """Convert Android ASCII quotes to the two stock SNES quote glyphs.

    Android uses straight quotes as presentation punctuation, while the stock
    SNES dialogue font exposes distinct opening/closing quote characters.  The
    conversion is deterministic and alternates within each localized string;
    it never changes apostrophes.
    """
    out: list[str] = []
    opening = True
    for char in text:
        if char != '"':
            out.append(char)
            continue
        out.append("“" if opening else "”")
        opening = not opening
    return "".join(out)


def normalize_android_french(text: str) -> str:
    """Discard Android presentation whitespace without rewriting the prose.

    ``_`` and U+3000 are presentation/layout separators in the Android assets;
    they are not SNES glyphs. Android hard line breaks likewise belong to the
    source presentation and are reflowed against the validated SNES VWF.
    Straight Android quotes are rebound to the stock SNES opening/closing quote
    glyphs. Square brackets are presentation-only choice delimiters and map to
    the stock parentheses used by the SNES interface.
    """
    text = text.replace("\r", " ").replace("\n", " ")
    text = text.replace("_", " ").replace("\u3000", " ")
    text = text.replace("[", "(").replace("]", ")")
    text = _normalize_android_quotes(text)
    return " ".join(text.split())


def apply_semantic_layout_hints(text: str) -> tuple[str, list[str]]:
    """Insert deterministic hard-line hints without changing localized prose.

    Android sometimes flattens speaker changes or attribution lines into one
    string. A new capitalized ``Name :`` label immediately after a completed
    sentence is a new spoken turn and must start on a new SNES line. Likewise,
    a dash attribution after a completed quoted sentence starts on its own
    line. These are line hints only; pagination remains a separate decision.
    """
    hints: list[str] = []

    def speaker(match: re.Match[str]) -> str:
        hints.append("speaker_after_sentence")
        return f"{match.group('end')}\n{match.group('label')}"

    def attribution(match: re.Match[str]) -> str:
        hints.append("attribution_after_quote")
        return f"{match.group('end')}\n- "

    text = _SPEAKER_AFTER_SENTENCE_RE.sub(speaker, text)
    text = _ATTRIBUTION_AFTER_QUOTE_RE.sub(attribution, text)
    return text, hints


def placeholder_sequence(text: str) -> tuple[int, ...]:
    return tuple(int(match.group(1)) for match in PLAYER_PLACEHOLDER_RE.finditer(text))


def _wrap_atoms(text: str) -> list[str]:
    """Return unbreakable word atoms for one semantic line segment.

    French Android strings often store a space before ``! ? ; :``. Treat a
    standalone punctuation token as part of the preceding word so wrapping can
    never strand punctuation on a line by itself (``loin`` / ``!``). The space
    remains inside the atom and therefore still contributes its real VWF width.
    """
    atoms: list[str] = []
    for token in text.split():
        if atoms and _PUNCTUATION_ATOM_RE.fullmatch(token):
            atoms[-1] += " " + token
        else:
            atoms.append(token)
    return atoms


def markup_width(text: str, advances: dict[str, int], placeholder_width: int) -> int:
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
    first_line_prefix_pixels: int = 0,
    first_line_prefix_units: int = 0,
    placeholder_width: int | None = None,
    placeholder_chars: int = MAX_PLAYER_NAME_CHARS,
    placeholder_parser_safety_units: int = PLAYER_NAME_PARSER_SAFETY_UNITS,
) -> tuple[str, list[int], list[int], list[int]]:
    """Word-wrap markup while preserving semantic hard-line hints.

    Ordinary spaces are wrap opportunities. Newlines inserted by
    :func:`apply_semantic_layout_hints` are mandatory line boundaries and are
    never collapsed. Standalone French punctuation tokens are attached to the
    preceding word atom so punctuation cannot become an orphan line.
    """
    if placeholder_width is None:
        placeholder_width = player_placeholder_width(advances)
    if not text.strip():
        return "", [], [], []

    space_width = advances[" "]
    lines: list[str] = []
    line_widths: list[int] = []
    line_char_counts: list[int] = []
    line_parser_unit_counts: list[int] = []
    first_output_line = True

    for segment in text.split("\n"):
        atoms = _wrap_atoms(segment)
        if not atoms:
            # Semantic layout hints never intentionally generate blank lines.
            # Ignore an accidental empty segment rather than creating vertical
            # motion that was not present in the localized prose.
            continue

        line_atoms: list[str] = []
        line_width = 0
        line_chars = 0
        line_parser_units = 0

        def flush() -> None:
            nonlocal line_atoms, line_width, line_chars, line_parser_units, first_output_line
            if not line_atoms:
                return
            lines.append(" ".join(line_atoms))
            line_widths.append(line_width)
            line_char_counts.append(line_chars)
            line_parser_unit_counts.append(line_parser_units)
            line_atoms = []
            line_width = 0
            line_chars = 0
            line_parser_units = 0
            first_output_line = False

        for atom in atoms:
            atom_width = markup_width(atom, advances, placeholder_width)
            atom_chars = _markup_chars(atom, placeholder_chars)
            placeholder_count = len(PLAYER_PLACEHOLDER_RE.findall(atom))
            atom_parser_units = atom_chars + placeholder_count * placeholder_parser_safety_units
            if atom_width > max_pixels:
                raise ValueError(
                    f"Unbreakable dialogue word exceeds {max_pixels}px: {atom!r} ({atom_width}px)"
                )
            if atom_parser_units > max_chars:
                raise ValueError(
                    f"Unbreakable dialogue word exceeds {max_chars} parser units: "
                    f"{atom!r} ({atom_parser_units})"
                )

            candidate_width = atom_width if not line_atoms else line_width + space_width + atom_width
            candidate_chars = atom_chars if not line_atoms else line_chars + 1 + atom_chars
            candidate_units = (
                atom_parser_units if not line_atoms else line_parser_units + 1 + atom_parser_units
            )
            prefix_pixels = first_line_prefix_pixels if first_output_line else 0
            prefix_units = first_line_prefix_units if first_output_line else 0
            if not line_atoms and (
                candidate_width + prefix_pixels > max_pixels
                or candidate_units + prefix_units > max_chars
            ):
                raise ValueError(
                    "First dialogue word does not fit after preserved line-start layout padding: "
                    f"{atom!r}"
                )
            if line_atoms and (
                candidate_width + prefix_pixels > max_pixels
                or candidate_units + prefix_units > max_chars
            ):
                flush()
            if line_atoms:
                line_width += space_width
                line_chars += 1
                line_parser_units += 1
            line_atoms.append(atom)
            line_width += atom_width
            line_chars += atom_chars
            line_parser_units += atom_parser_units

        flush()

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
    first_line_prefix_pixels: int = 0,
    first_line_prefix_units: int = 0,
    placeholder_width: int | None = None,
    placeholder_chars: int = MAX_PLAYER_NAME_CHARS,
    placeholder_parser_safety_units: int = PLAYER_NAME_PARSER_SAFETY_UNITS,
) -> tuple[str, list[int], list[int], list[int]]:
    """Reflow plain prose into an exact number of balanced lines/pages.

    Semantic hard-line hints are intentionally not moved by this optimizer. If
    ``text`` contains such a hint, callers must use :func:`wrap_markup` for the
    relevant page piece instead.
    """
    if "\n" in text:
        raise ValueError("Balanced wrapper cannot move semantic hard-line hints")
    if placeholder_width is None:
        placeholder_width = player_placeholder_width(advances)
    atoms = _wrap_atoms(text)
    if not atoms:
        return "", [], [], []
    if line_count < 1 or line_count > len(atoms):
        raise ValueError(f"Cannot wrap {len(atoms)} atom(s) into exactly {line_count} line(s)")
    if sum(page_line_counts) != line_count:
        raise ValueError("Page-line distribution does not equal requested line count")

    page_break_after: set[int] = set()
    running = 0
    for count in page_line_counts[:-1]:
        running += count
        page_break_after.add(running)

    weak_end_words = {
        "à", "au", "aux", "de", "du", "des", "et", "ou", "un", "une",
        "le", "la", "les", "ce", "ces", "tout", "toute", "tous", "toutes",
        "en", "dans", "sur", "pour", "avec", "sans", "que", "qui", "ne",
        "se", "son", "sa", "ses", "mon", "ma", "mes", "ton", "ta", "tes",
        "notre", "votre",
    }

    def weak_key(atom: str) -> str:
        # Standalone punctuation may be attached inside an atom (``loin !``).
        # The first lexical token is therefore the relevant weak-word test.
        return atom.split()[0].strip(".,!?;:…“”\"'()[]").lower()

    def ends_sentence(atom: str) -> bool:
        return bool(re.search(r"(?:\.{3}|[.!?…])[”\"»')\]]*$", atom))

    total_width = markup_width(text, advances, placeholder_width)
    target_width = min(max_pixels, total_width / line_count)

    metrics_cache: dict[tuple[int, int], tuple[str, int, int, int]] = {}

    def metrics(start: int, end: int) -> tuple[str, int, int, int]:
        key = (start, end)
        cached = metrics_cache.get(key)
        if cached is not None:
            return cached
        value = " ".join(atoms[start:end])
        width = markup_width(value, advances, placeholder_width)
        chars = _markup_chars(value, placeholder_chars)
        placeholders = len(PLAYER_PLACEHOLDER_RE.findall(value))
        parser_units = chars + placeholders * placeholder_parser_safety_units
        result = (value, width, chars, parser_units)
        metrics_cache[key] = result
        return result

    infinity = float("inf")
    memo: dict[tuple[int, int], tuple[float, tuple[tuple[str, int, int, int], ...]]] = {}

    def solve(atom_index: int, line_index: int):
        key = (atom_index, line_index)
        if key in memo:
            return memo[key]
        if line_index == line_count:
            result = (0.0, ()) if atom_index == len(atoms) else (infinity, ())
            memo[key] = result
            return result

        lines_left_after = line_count - line_index - 1
        max_end = len(atoms) - lines_left_after
        best_cost = infinity
        best_path: tuple[tuple[str, int, int, int], ...] = ()
        for end in range(atom_index + 1, max_end + 1):
            value, width, chars, parser_units = metrics(atom_index, end)
            prefix_pixels = first_line_prefix_pixels if line_index == 0 else 0
            prefix_units = first_line_prefix_units if line_index == 0 else 0
            if width + prefix_pixels > max_pixels or parser_units + prefix_units > max_chars:
                break

            first_atom = atoms[atom_index]
            last_atom = atoms[end - 1]
            cost = (width + prefix_pixels - target_width) ** 2
            if _PUNCTUATION_ATOM_RE.fullmatch(first_atom):
                cost += 100_000
            if weak_key(last_atom) in weak_end_words:
                cost += 3_500
            if ends_sentence(last_atom):
                cost -= 700

            one_based_line = line_index + 1
            if one_based_line in page_break_after:
                if weak_key(last_atom) in weak_end_words:
                    cost += 7_000
                if ends_sentence(last_atom):
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
    for count in page_line_counts:
        parts.append("\n".join(lines[cursor:cursor + count]))
        cursor += count
    return "\f".join(parts), widths, char_counts, parser_units



def sentence_boundary_positions(text: str) -> tuple[int, ...]:
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



def _comma_boundary_positions(text: str) -> tuple[int, ...]:
    """Return conservative weak clause boundaries immediately after commas."""
    positions: list[int] = []
    for index, char in enumerate(text):
        if char != ",":
            continue
        end = index + 1
        if end >= len(text) or not text[end].isspace():
            continue
        while end < len(text) and text[end].isspace():
            end += 1
        if end < len(text):
            positions.append(end)
    return tuple(positions)


def _semantic_wrap_plain_segment(
    text: str,
    advances: dict[str, int],
    *,
    max_pixels: int = DIALOGUE_WRAP_PIXELS,
    max_chars: int = DIALOGUE_WRAP_CHARS,
    first_line_prefix_pixels: int = 0,
    first_line_prefix_units: int = 0,
) -> tuple[str, list[int], list[int], list[int]]:
    """Wrap one segment while preferring natural French clause boundaries.

    Strong sentence boundaries are preserved whenever each sentence can be
    laid out independently without exceeding one three-line SNES page. This is
    intentionally allowed to use an otherwise-unused third line: readability
    takes precedence over packing unrelated sentences together. For a single
    sentence that needs exactly two lines, a comma may be used as a weaker
    boundary when it yields a substantially better-balanced pair of lines.
    """
    baseline = wrap_markup(
        text,
        advances,
        max_pixels=max_pixels,
        max_chars=max_chars,
        first_line_prefix_pixels=first_line_prefix_pixels,
        first_line_prefix_units=first_line_prefix_units,
    )
    if not text.strip() or "\n" in text:
        return baseline

    def wrap_one_sentence(sentence: str, *, preserve_prefix: bool):
        prefix_pixels = first_line_prefix_pixels if preserve_prefix else 0
        prefix_units = first_line_prefix_units if preserve_prefix else 0
        result = wrap_markup(
            sentence,
            advances,
            max_pixels=max_pixels,
            max_chars=max_chars,
            first_line_prefix_pixels=prefix_pixels,
            first_line_prefix_units=prefix_units,
        )
        if len(result[1]) != 2:
            return result
        baseline_balance = abs(result[1][0] - result[1][1])
        best = None
        comma_boundaries = _comma_boundary_positions(sentence)
        # Multiple commas often encode discourse rhythm or parenthetical
        # phrasing (``Pendant ce temps, toi, file...``). Do not guess which
        # comma is semantic in that case; keep weak comma optimization limited
        # to a single unambiguous clause boundary.
        if len(comma_boundaries) != 1:
            return result
        for boundary in comma_boundaries:
            first = sentence[:boundary].strip()
            second = sentence[boundary:].strip()
            if not first or not second:
                continue
            first_result = wrap_markup(
                first,
                advances,
                max_pixels=max_pixels,
                max_chars=max_chars,
                first_line_prefix_pixels=prefix_pixels,
                first_line_prefix_units=prefix_units,
            )
            second_result = wrap_markup(second, advances, max_pixels=max_pixels, max_chars=max_chars)
            if len(first_result[1]) != 1 or len(second_result[1]) != 1:
                continue
            # Avoid turning a tiny tail/head into a decorative line. The comma
            # boundary is only a soft preference when both clauses have enough
            # visual substance and materially improve balance.
            w1, w2 = first_result[1][0], second_result[1][0]
            if min(w1, w2) < 72:
                continue
            balance = abs(w1 - w2)
            improvement = baseline_balance - balance
            if improvement < 24:
                continue
            candidate = (
                first_result[0] + "\n" + second_result[0],
                first_result[1] + second_result[1],
                first_result[2] + second_result[2],
                first_result[3] + second_result[3],
            )
            if best is None or balance < best[0]:
                best = (balance, candidate)
        return best[1] if best is not None else result

    boundaries = sentence_boundary_positions(text)
    if boundaries:
        starts = (0,) + boundaries
        ends = boundaries + (len(text),)
        sentence_results = []
        for sentence_index, (start, end) in enumerate(zip(starts, ends, strict=True)):
            sentence = text[start:end].strip()
            if not sentence:
                continue
            sentence_results.append(
                wrap_one_sentence(sentence, preserve_prefix=sentence_index == 0)
            )
        semantic_line_count = sum(len(result[1]) for result in sentence_results)
        # Never create an extra page just for aesthetics. Within an already
        # available three-line page, however, preserving sentence starts is a
        # deliberate readability preference.
        if sentence_results and semantic_line_count <= DIALOGUE_PAGE_LINES:
            lines: list[str] = []
            widths: list[int] = []
            chars: list[int] = []
            units: list[int] = []
            for wrapped, part_widths, part_chars, part_units in sentence_results:
                lines.extend(wrapped.split("\n"))
                widths.extend(part_widths)
                chars.extend(part_chars)
                units.extend(part_units)
            return "\n".join(lines), widths, chars, units

    return wrap_one_sentence(text, preserve_prefix=True)


def semantic_wrap_markup(
    text: str,
    advances: dict[str, int],
    *,
    max_pixels: int = DIALOGUE_WRAP_PIXELS,
    max_chars: int = DIALOGUE_WRAP_CHARS,
    first_line_prefix_pixels: int = 0,
    first_line_prefix_units: int = 0,
) -> tuple[str, list[int], list[int], list[int]]:
    """Wrap localized prose with semantic sentence/clause line preferences.

    Explicit hard-line hints (speaker changes and attributions) remain
    mandatory. Each side of such a hint is optimized independently, then the
    original hard boundary is restored.
    """
    if "\n" not in text:
        return _semantic_wrap_plain_segment(
            text,
            advances,
            max_pixels=max_pixels,
            max_chars=max_chars,
            first_line_prefix_pixels=first_line_prefix_pixels,
            first_line_prefix_units=first_line_prefix_units,
        )

    all_lines: list[str] = []
    widths: list[int] = []
    chars: list[int] = []
    units: list[int] = []
    emitted_segment = False
    for segment in text.split("\n"):
        if not segment.strip():
            continue
        wrapped, part_widths, part_chars, part_units = _semantic_wrap_plain_segment(
            segment,
            advances,
            max_pixels=max_pixels,
            max_chars=max_chars,
            first_line_prefix_pixels=first_line_prefix_pixels if not emitted_segment else 0,
            first_line_prefix_units=first_line_prefix_units if not emitted_segment else 0,
        )
        emitted_segment = True
        all_lines.extend(wrapped.split("\n"))
        widths.extend(part_widths)
        chars.extend(part_chars)
        units.extend(part_units)
    return "\n".join(all_lines), widths, chars, units

def _sentence_aware_extra_page_wrap(
    text: str,
    advances: dict[str, int],
    *,
    max_pixels: int = DIALOGUE_WRAP_PIXELS,
    max_chars: int = DIALOGUE_WRAP_CHARS,
    prefer_semantic_line_breaks: bool = True,
    first_line_prefix_pixels: int = 0,
    first_line_prefix_units: int = 0,
) -> tuple[str, list[int], list[int], list[int], tuple[int, int], str]:
    """Wrap one overflowing prose block onto at most two pages.

    Semantic hard-line hints (speaker changes / dash attributions) are the
    strongest page-boundary candidates: if the text cannot stay on one page and
    one of those boundaries leaves both sides within three lines, page there.
    Otherwise prefer the latest complete-sentence boundary. The old balanced
    fallback remains only for prose without a usable semantic boundary.
    """

    def wrap_piece(
        piece: str, *, preserve_prefix: bool
    ) -> tuple[str, list[int], list[int], list[int]]:
        wrapper = semantic_wrap_markup if prefer_semantic_line_breaks else wrap_markup
        return wrapper(
            piece,
            advances,
            max_pixels=max_pixels,
            max_chars=max_chars,
            first_line_prefix_pixels=first_line_prefix_pixels if preserve_prefix else 0,
            first_line_prefix_units=first_line_prefix_units if preserve_prefix else 0,
        )

    # First honor explicit semantic line boundaries inserted by the formatter.
    hard_candidates: list[tuple[int, str, str, tuple, tuple]] = []
    for index, char in enumerate(text):
        if char != "\n":
            continue
        first = text[:index].strip()
        second = text[index + 1:].strip()
        if not first or not second:
            continue
        try:
            first_result = wrap_piece(first, preserve_prefix=True)
            second_result = wrap_piece(second, preserve_prefix=False)
        except ValueError:
            continue
        if not (1 <= len(first_result[1]) <= DIALOGUE_PAGE_LINES):
            continue
        if not (1 <= len(second_result[1]) <= DIALOGUE_PAGE_LINES):
            continue
        hard_candidates.append((index, first, second, first_result, second_result))

    if hard_candidates:
        # Keep as much complete dialogue as possible on page 1 while ensuring
        # the new speaker/attribution begins at the top of page 2.
        _, first, second, first_result, second_result = max(hard_candidates, key=lambda item: item[0])
        first_wrapped, first_widths, first_chars, first_units = first_result
        second_wrapped, second_widths, second_chars, second_units = second_result
        return (
            first_wrapped + "\f" + second_wrapped,
            first_widths + second_widths,
            first_chars + second_chars,
            first_units + second_units,
            (len(first_widths), len(second_widths)),
            "semantic_hard_boundary",
        )

    candidates: list[tuple[int, str, str, tuple, tuple]] = []
    for boundary in sentence_boundary_positions(text):
        first = text[:boundary].strip()
        second = text[boundary:].strip()
        if not first or not second:
            continue
        try:
            first_result = wrap_piece(first, preserve_prefix=True)
            second_result = wrap_piece(second, preserve_prefix=False)
        except ValueError:
            continue
        if not (1 <= len(first_result[1]) <= DIALOGUE_PAGE_LINES):
            continue
        if not (1 <= len(second_result[1]) <= DIALOGUE_PAGE_LINES):
            continue
        candidates.append((boundary, first, second, first_result, second_result))

    if candidates:
        boundary, first, second, first_result, second_result = max(candidates, key=lambda item: item[0])

        def balanced_or_greedy(
            piece: str,
            result: tuple[str, list[int], list[int], list[int]],
            *,
            preserve_prefix: bool,
        ):
            wrapped, widths, chars, units = result
            if "\n" in piece:
                return wrapped, widths, chars, units
            return _balanced_wrap_markup(
                piece,
                advances,
                line_count=len(widths),
                page_line_counts=(len(widths),),
                max_pixels=max_pixels,
                max_chars=max_chars,
                first_line_prefix_pixels=first_line_prefix_pixels if preserve_prefix else 0,
                first_line_prefix_units=first_line_prefix_units if preserve_prefix else 0,
            )

        first_wrapped, first_widths, first_chars, first_units = balanced_or_greedy(
            first, first_result, preserve_prefix=True
        )
        second_wrapped, second_widths, second_chars, second_units = balanced_or_greedy(
            second, second_result, preserve_prefix=False
        )
        return (
            first_wrapped + "\f" + second_wrapped,
            first_widths + second_widths,
            first_chars + second_chars,
            first_units + second_units,
            (len(first_widths), len(second_widths)),
            "sentence_boundary",
        )

    greedy, widths, chars, units = wrap_piece(text, preserve_prefix=True)
    page_line_counts = _page_line_counts(len(widths))
    if len(page_line_counts) != 2:
        raise ValueError("Extra-page formatter inserts exactly one additional page")

    # If semantic hard-line hints exist but none can be used as a safe page
    # boundary, never rebalance across them. Preserve the hinted lines and only
    # divide the already-wrapped output into the deterministic 2-page fallback.
    if "\n" in text:
        greedy_lines = greedy.split("\n")
        first_count, second_count = page_line_counts
        first = "\n".join(greedy_lines[:first_count])
        second = "\n".join(greedy_lines[first_count:first_count + second_count])
        return greedy and (
            first + "\f" + second,
            widths,
            chars,
            units,
            page_line_counts,
            "semantic_preserving_fallback",
        )

    wrapped, widths, chars, units = _balanced_wrap_markup(
        text,
        advances,
        line_count=sum(page_line_counts),
        page_line_counts=page_line_counts,
        max_pixels=max_pixels,
        max_chars=max_chars,
        first_line_prefix_pixels=first_line_prefix_pixels,
        first_line_prefix_units=first_line_prefix_units,
    )
    return wrapped, widths, chars, units, page_line_counts, "balanced_fallback"



def _sentence_aware_three_page_wrap(
    text: str,
    advances: dict[str, int],
    *,
    max_pixels: int = DIALOGUE_WRAP_PIXELS,
    max_chars: int = DIALOGUE_WRAP_CHARS,
    prefer_semantic_line_breaks: bool = True,
    first_line_prefix_pixels: int = 0,
    first_line_prefix_units: int = 0,
) -> tuple[str, list[int], list[int], list[int], tuple[int, int, int], str]:
    """Wrap one long prose block onto exactly three sentence-bounded pages.

    This is deliberately narrower than the two-page fallback: both generated
    transitions must coincide with complete-sentence boundaries, and every
    resulting page must independently fit the validated three-line capacity.
    No balanced arbitrary split is permitted.
    """
    wrapper = semantic_wrap_markup if prefer_semantic_line_breaks else wrap_markup
    candidates = []
    boundaries = sentence_boundary_positions(text)
    for first_boundary_index, first_boundary in enumerate(boundaries):
        for second_boundary in boundaries[first_boundary_index + 1:]:
            pieces = (
                text[:first_boundary].strip(),
                text[first_boundary:second_boundary].strip(),
                text[second_boundary:].strip(),
            )
            if not all(pieces):
                continue
            results = []
            valid = True
            for piece_index, piece in enumerate(pieces):
                try:
                    result = wrapper(
                        piece,
                        advances,
                        max_pixels=max_pixels,
                        max_chars=max_chars,
                        first_line_prefix_pixels=(
                            first_line_prefix_pixels if piece_index == 0 else 0
                        ),
                        first_line_prefix_units=(
                            first_line_prefix_units if piece_index == 0 else 0
                        ),
                    )
                except ValueError:
                    valid = False
                    break
                if not (1 <= len(result[1]) <= DIALOGUE_PAGE_LINES):
                    valid = False
                    break
                results.append(result)
            if not valid:
                continue
            counts = tuple(len(result[1]) for result in results)
            # Prefer the most even valid page distribution; then retain as much
            # complete prose as possible on earlier pages.
            score = (max(counts) - min(counts), -min(counts), -first_boundary, -second_boundary)
            candidates.append((score, results))

    if candidates:
        _, results = min(candidates, key=lambda item: item[0])
        wrapped_parts = [result[0] for result in results]
        widths = [value for result in results for value in result[1]]
        chars = [value for result in results for value in result[2]]
        units = [value for result in results for value in result[3]]
        counts = tuple(len(result[1]) for result in results)
        return (
            "\f".join(wrapped_parts),
            widths,
            chars,
            units,
            counts,
            "sentence_boundaries_three_pages",
        )

    # A sentence can itself require more than one physical page. In that case
    # insisting that *both* page transitions end a sentence makes otherwise
    # legal Android-FR prose impossible to serialize. Fall back to the same
    # deterministic word-boundary optimizer used by the two-page formatter,
    # while keeping every physical page within the validated three-line limit.
    # Existing hard semantic NEWLINE hints are not movable by the balanced
    # optimizer; leave those cases to the caller/simulator rather than silently
    # discarding them.
    if "\n" not in text:
        balanced_candidates = []
        for first_count in range(1, DIALOGUE_PAGE_LINES + 1):
            for second_count in range(1, DIALOGUE_PAGE_LINES + 1):
                for third_count in range(1, DIALOGUE_PAGE_LINES + 1):
                    page_counts = (first_count, second_count, third_count)
                    line_count = sum(page_counts)
                    try:
                        result = _balanced_wrap_markup(
                            text,
                            advances,
                            line_count=line_count,
                            page_line_counts=page_counts,
                            max_pixels=max_pixels,
                            max_chars=max_chars,
                            first_line_prefix_pixels=first_line_prefix_pixels,
                            first_line_prefix_units=first_line_prefix_units,
                        )
                    except ValueError:
                        continue
                    wrapped, widths, chars, units = result
                    # Prefer fewer total lines, then the most even distribution,
                    # then retain more material on earlier pages.
                    score = (
                        line_count,
                        max(page_counts) - min(page_counts),
                        -first_count,
                        -second_count,
                    )
                    balanced_candidates.append(
                        (score, wrapped, widths, chars, units, page_counts)
                    )
        if balanced_candidates:
            _, wrapped, widths, chars, units, page_counts = min(
                balanced_candidates, key=lambda item: item[0]
            )
            lines = wrapped.split("\n")
            first_end = page_counts[0]
            second_end = first_end + page_counts[1]
            wrapped_pages = (
                "\n".join(lines[:first_end]),
                "\n".join(lines[first_end:second_end]),
                "\n".join(lines[second_end:]),
            )
            return (
                "\f".join(wrapped_pages),
                widths,
                chars,
                units,
                page_counts,
                "balanced_word_boundaries_three_pages",
            )

    raise ValueError(
        "Three-page formatter found no safe sentence- or word-boundary layout "
        "that keeps every page within 3 lines"
    )

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


_FORMAT_INDEX_DOCUMENT: dict | None = None
_FORMAT_INDEX_VALUE: tuple[dict[str, dict], dict[str, dict]] | None = None


def format_event_text_index(document: dict) -> tuple[dict[str, dict], dict[str, dict]]:
    """Reuse the canonical source index during one formatting process.

    Dialogue formatting treats its parsed source document as immutable.  Keep a
    one-document identity cache for that hot path without changing the public
    ``event_text_index`` semantics used by extraction/checking tools.  Supplying
    any other document object rebuilds the index immediately.
    """
    global _FORMAT_INDEX_DOCUMENT, _FORMAT_INDEX_VALUE
    if document is not _FORMAT_INDEX_DOCUMENT or _FORMAT_INDEX_VALUE is None:
        _FORMAT_INDEX_DOCUMENT = document
        _FORMAT_INDEX_VALUE = event_text_index(document)
    return _FORMAT_INDEX_VALUE


def mapping_leading_text_x_position(document: dict, mapping: dict) -> int:
    """Return a proven line-start ``TEXT_X`` padding before this mapping.

    The independent simulator validates ``TEXT_X $nn`` only when the command
    starts a fresh decoded line.  Keep the formatter equally conservative: a
    mapping receives a first-line capacity reservation only when its first
    source text token immediately follows ``TEXT_X`` and the canonical token
    immediately before that command proves a fresh line (TEXT_OPEN/CLEAR/WAIT
    or a text token ending in an explicit newline).

    Other placements remain unmodeled here and are left to the simulator's
    unsupported-structure gate rather than inferred.
    """
    by_id, by_event = format_event_text_index(document)
    source_ids = mapping.get("snes_ids", [])
    if not source_ids:
        return 0
    first = by_id.get(source_ids[0])
    if first is None:
        return 0
    event = by_event[first["event_id"]]
    token_index = first["token_index"]
    tokens = event.get("tokens", [])
    if token_index <= 0:
        return 0
    text_token = tokens[token_index]
    if text_token.get("source", "").startswith("\n"):
        return 0
    text_x = tokens[token_index - 1]
    if not (
        text_x.get("type") == "command"
        and text_x.get("name") == "TEXT_X"
    ):
        return 0
    if token_index < 2:
        return 0
    before = tokens[token_index - 2]
    fresh_line = False
    if before.get("type") == "text":
        fresh_line = before.get("source", "").endswith("\n")
    elif before.get("type") == "command":
        fresh_line = before.get("name") in {"TEXT_OPEN", "TEXT_CLEAR", "WAIT"}
    if not fresh_line:
        return 0
    args = text_x.get("args", "").strip().split()
    if len(args) != 1:
        return 0
    try:
        position = int(args[0], 16)
    except ValueError:
        return 0
    if not 0 <= position <= DIALOGUE_WRAP_CHARS:
        return 0
    return position


def strip_proven_structural_android_markers(
    document: dict, mapping: dict, text: str
) -> tuple[str, list[str]]:
    """Remove Android-only arrow markers only when the SNES event proves them.

    Android sign strings sometimes include ``←``/``→`` in the localized text
    even though the SNES event emits the same arrow as a separate structural
    glyph immediately before the editable text area.  In that exact case the
    marker must not be encoded a second time as dialogue prose.  Android also
    uses ``▽`` as a presentation marker immediately before some interactive
    choice prompts.  Once the event itself proves a CHOICE_BEGIN/CHOICE_END
    structure, that marker is structural too: keep any stock $CE glyph already
    present in the SNES event, but never encode the Android marker as prose.
    """
    event_id = mapping.get("event_id")
    if not event_id:
        return text, []
    _, by_event = format_event_text_index(document)
    event = by_event.get(event_id)
    if event is None:
        return text, []

    # Android French occasionally adds a leading dynamic speaker label even
    # though the matched SNES text span has no PLAYER_NAME command at all.
    # In that exact presentation-only case, drop only the leading ``%S(n,0) :``
    # label. The prose is kept verbatim and no SNES command is invented.
    leading_speaker = re.match(r"^\s*(%S\(\d+,0\))\s*:\s*", text)
    if leading_speaker and not PLAYER_PLACEHOLDER_RE.search(mapping.get("source_display", "")):
        removed_label = leading_speaker.group(0).strip()
        text = text[leading_speaker.end():]
        removed = [removed_label]
    else:
        removed = []


    glyph_codes = {
        token.get("code", "").upper()
        for token in event.get("tokens", [])
        if token.get("type") == "glyph"
    }
    marker_codes = {"←": "CF", "→": "D0"}
    for marker, code in marker_codes.items():
        if code not in glyph_codes or text.count(marker) != 1:
            continue
        text = text.replace(marker, "")
        removed.append(marker)

    has_choice = any(
        token.get("type") == "command" and token.get("name") == "CHOICE_BEGIN"
        for token in event.get("tokens", [])
    ) and any(
        token.get("type") == "command" and token.get("name") == "CHOICE_END"
        for token in event.get("tokens", [])
    )
    if has_choice and text.count("▽") == 1:
        text = text.replace("▽", "")
        removed.append("▽")

    return text, removed


def binding_slots(document: dict, mapping: dict) -> list[BindingSlot]:
    """Recover the exact mapped text/PLAYER_NAME stream from canonical tokens.

    Mappings may begin or end immediately next to a ``PLAYER_NAME`` command.
    The aligner includes that placeholder in ``source_display`` even when the
    position-derived SNES text ID itself lies only on one side of the command.
    Search only those adjacent PLAYER_NAME boundaries and accept a span only
    when its canonical rendering equals the established alignment exactly.

    Any other command, glyph, or unmapped text crossed by a mapping is still
    rejected. This preserves the conservative structural contract.
    """
    by_id, by_event = format_event_text_index(document)
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
    tokens = event["tokens"]
    token_indexes = [by_id[text_id]["token_index"] for text_id in snes_ids]
    if token_indexes != sorted(token_indexes):
        raise ValueError(f"Dialogue mapping SNES IDs are not in token order: {snes_ids}")
    selected = set(snes_ids)

    def is_player(index: int) -> bool:
        if not (0 <= index < len(tokens)):
            return False
        token = tokens[index]
        return token.get("type") == "command" and token.get("name") == "PLAYER_NAME"

    starts = [token_indexes[0]]
    cursor = token_indexes[0] - 1
    while is_player(cursor):
        starts.append(cursor)
        cursor -= 1
    ends = [token_indexes[-1]]
    cursor = token_indexes[-1] + 1
    while is_player(cursor):
        ends.append(cursor)
        cursor += 1

    def slots_for_span(span_start: int, span_end: int) -> list[BindingSlot] | None:
        slots: list[BindingSlot] = []
        for token in tokens[span_start:span_end + 1]:
            kind = token.get("type")
            if kind == "text":
                if token["id"] not in selected:
                    return None
                slots.append(TextSlot(token["id"], token["source"]))
            elif kind == "command" and token.get("name") == "PLAYER_NAME":
                args = token.get("args", "00").split()
                if not args:
                    raise ValueError("PLAYER_NAME command has no index")
                slots.append(PlayerSlot(int(args[0], 16)))
            else:
                return None
        return slots

    expected = mapping.get("source_display", "")
    matches: list[tuple[int, int, list[BindingSlot]]] = []
    for span_start in starts:
        for span_end in ends:
            if span_start > token_indexes[0] or span_end < token_indexes[-1]:
                continue
            slots = slots_for_span(span_start, span_end)
            if slots is None:
                continue
            rendered = "".join(
                slot.source if isinstance(slot, TextSlot) else f"%S({slot.index},0)"
                for slot in slots
            )
            if rendered == expected:
                matches.append((span_start, span_end, slots))

    if not matches:
        # The semantic aligner can carry the next speaker placeholder at the
        # end of ``source_display`` even when that PLAYER_NAME command lies
        # beyond a WAIT/TEXT_CLEAR or other event-side-effect boundary and is
        # therefore outside the mapped SNES text IDs.  Accept that suffix only
        # when the canonical event tokens prove the exact same PLAYER_NAME
        # lookahead before the next text token.  The command itself remains in
        # its original event position and is never rebound into this mapping.
        for span_start in starts:
            span_end = token_indexes[-1]
            slots = slots_for_span(span_start, span_end)
            if slots is None:
                continue
            rendered = "".join(
                slot.source if isinstance(slot, TextSlot) else f"%S({slot.index},0)"
                for slot in slots
            )
            if not expected.startswith(rendered):
                continue
            suffix = expected[len(rendered):]
            if not suffix or re.fullmatch(r"(?:%S\(\d+,0\))+", suffix) is None:
                continue

            context: list[str] = []
            context_valid = True
            # Only tolerate the proven linear lookahead shapes seen in the
            # alignment corpus. Branching/choice/unknown commands must never
            # make a future PLAYER_NAME look adjacent to the current mapping.
            # OP_32 and OP_34 are the same already-proven actor-action
            # family for this linear lookahead; neither command emits text.
            safe_context_commands = {"WAIT", "TEXT_CLEAR", "OP_32", "OP_34", "COMPLETE_ACTIONS"}
            for token in tokens[span_end + 1:]:
                if token.get("type") == "text":
                    break
                if token.get("type") != "command":
                    context_valid = False
                    break
                name = token.get("name")
                if name == "PLAYER_NAME":
                    args = token.get("args", "00").split()
                    if not args:
                        context_valid = False
                        break
                    context.append(f"%S({int(args[0], 16)},0)")
                elif name not in safe_context_commands:
                    context_valid = False
                    break
            if context_valid and "".join(context) == suffix:
                matches.append((span_start, span_end, slots))

    if not matches:
        # Keep structural failures specific when the canonical event stream no
        # longer reproduces the established alignment.
        base_slots = slots_for_span(token_indexes[0], token_indexes[-1])
        if base_slots is None:
            for token in tokens[token_indexes[0]:token_indexes[-1] + 1]:
                kind = token.get("type")
                if kind == "text" and token.get("id") not in selected:
                    raise ValueError(
                        f"Mapping {snes_ids} crosses unmapped text token {token['id']}; defer structural binding"
                    )
                if kind != "text" and not (kind == "command" and token.get("name") == "PLAYER_NAME"):
                    raise ValueError(
                        f"Mapping {snes_ids} crosses {kind} {token.get('name', '')!r}; defer structural binding"
                    )
        raise ValueError(
            f"Canonical binding stream for {snes_ids} no longer equals alignment source_display"
        )

    # Prefer the narrowest exact canonical span. More than one equally narrow
    # exact span would be structurally ambiguous and is therefore rejected.
    width = min(end - start for start, end, _ in matches)
    narrow = [entry for entry in matches if entry[1] - entry[0] == width]
    if len(narrow) != 1:
        raise ValueError(f"Ambiguous adjacent PLAYER_NAME binding for {snes_ids}")
    span_start, span_end, slots = narrow[0]

    def nonsemantic_text_carrier(index: int) -> TextSlot | None:
        if not (0 <= index < len(tokens)):
            return None
        token = tokens[index]
        if token.get("type") != "text" or token.get("id") in selected:
            return None
        source = token.get("source", "")
        # These carrier slots are punctuation/layout fragments, never prose.
        # They already exist in the canonical event and can safely hold a
        # localized literal run moved across an adjacent PLAYER_NAME command.
        if re.search(r"[A-Za-z0-9À-ÖØ-öø-ÿŒœ]", source):
            return None
        return TextSlot(token["id"], source)

    # The semantic aligner deliberately excludes punctuation-only text tokens
    # from ``snes_ids``.  If such a token sits immediately outside a mapped
    # PLAYER_NAME boundary, retain it as a carrier so Android FR
    # may place literal text on both sides of the *existing* dynamic-name
    # command without moving or creating any event command.
    if slots and isinstance(slots[0], PlayerSlot):
        carrier = nonsemantic_text_carrier(span_start - 1)
        if carrier is not None:
            slots = [carrier, *slots]
    if slots and isinstance(slots[-1], PlayerSlot):
        carrier = nonsemantic_text_carrier(span_end + 1)
        if carrier is not None:
            slots = [*slots, carrier]

    return slots



def _leading_newlines(text: str) -> int:
    return len(text) - len(text.lstrip("\n"))


def _trailing_newlines(text: str) -> int:
    return len(text) - len(text.rstrip("\n"))


def _leading_newline_follows_wait(document: dict, text_id: str) -> bool:
    """Return whether a text token starts immediately after an existing WAIT.

    Stock scripts often combine ``WAIT`` with a leading newline in the next
    text chunk to scroll the previous three-line window away. For localized
    chunks we can keep the existing WAIT, emit one TEXT_CLEAR, and drop that
    synthetic blank line instead.
    """
    by_id, by_event = format_event_text_index(document)
    meta = by_id[text_id]
    tokens = by_event[meta["event_id"]]["tokens"]
    index = meta["token_index"]
    if index <= 0:
        return False
    previous = tokens[index - 1]
    return previous.get("type") == "command" and previous.get("name") == "WAIT"


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
        # Adjacent text tokens have no intervening event side effect: their
        # serialized bytes are one continuous source stream. Put the localized
        # literal run in the first token and explicitly empty the remaining
        # contiguous tokens. This is byte-equivalent to concatenating them and
        # avoids inventing an arbitrary sentence-to-token split.
        translations[text_slots[0].text_id] = run
        for slot in text_slots[1:]:
            translations[slot.text_id] = ""
    return translations



def _extend_slots_through_adjacent_nonsemantic_player_carrier(
    document: dict,
    mapping: dict,
    slots: list[BindingSlot],
    french_placeholders: tuple[int, ...],
) -> tuple[list[BindingSlot], list[int]]:
    """Expose an existing speaker PLAYER_NAME through one punctuation carrier.

    Some SNES scripts encode ``PLAYER_NAME(a)`` + punctuation-only text +
    ``PLAYER_NAME(b)`` + mapped prose, while the semantic aligner intentionally
    starts the mapping at ``PLAYER_NAME(b)``. Android French may retain both
    dynamic names. If the already-bound slots begin with exactly that
    punctuation carrier followed by ``PLAYER_NAME(b)``, allow the immediately
    preceding canonical ``PLAYER_NAME(a)`` to participate as well. No command
    is created, removed, reordered, or moved.
    """
    current = tuple(slot.index for slot in slots if isinstance(slot, PlayerSlot))
    if len(french_placeholders) != len(current) + 1:
        return slots, []
    if french_placeholders[1:] != current:
        return slots, []
    if len(slots) < 2 or not isinstance(slots[0], TextSlot) or not isinstance(slots[1], PlayerSlot):
        return slots, []
    carrier = slots[0]
    if re.search(r"[A-Za-z0-9À-ÖØ-öø-ÿŒœ]", carrier.source):
        return slots, []

    by_id, by_event = format_event_text_index(document)
    meta = by_id.get(carrier.text_id)
    if meta is None:
        return slots, []
    tokens = by_event[meta["event_id"]]["tokens"]
    index = meta["token_index"]
    if index <= 0:
        return slots, []
    previous = tokens[index - 1]
    if previous.get("type") != "command" or previous.get("name") != "PLAYER_NAME":
        return slots, []
    args = previous.get("args", "00").split()
    if not args:
        return slots, []
    player_index = int(args[0], 16)
    if player_index != french_placeholders[0]:
        return slots, []
    return [PlayerSlot(player_index), *slots], [player_index]


def format_mapping(
    document: dict,
    mapping: dict,
    advances: dict[str, int],
    *,
    max_pixels: int = DIALOGUE_WRAP_PIXELS,
    allow_one_extra_page: bool = False,
    use_physical_page_capacity: bool = False,
    prefer_semantic_line_breaks: bool = True,
    force_one_extra_page: bool = False,
    allow_two_extra_pages: bool = False,
) -> tuple[dict[str, str], dict]:
    """Format one already accepted mapping into existing SNES text-token values."""
    slots = binding_slots(document, mapping)
    source_display = mapping["source_display"]
    french_raw = mapping.get("french_display", "")
    if not french_raw:
        raise ValueError("Accepted dialogue mapping has no French Android text")

    source_placeholders = tuple(slot.index for slot in slots if isinstance(slot, PlayerSlot))
    bound_source_display = "".join(
        slot.source if isinstance(slot, TextSlot) else f"%S({slot.index},0)"
        for slot in slots
    )
    ignored_alignment_trailing_player_context = (
        source_display[len(bound_source_display):]
        if source_display.startswith(bound_source_display)
        else ""
    )
    french_without_structural_markers, structural_markers_removed = (
        strip_proven_structural_android_markers(document, mapping, french_raw)
    )
    french_normalized = normalize_android_french(french_without_structural_markers)
    french_layout, layout_hints = apply_semantic_layout_hints(french_normalized)
    french_placeholders = placeholder_sequence(french_layout)
    preserved_static_speaker_dynamic_addressee = None

    # Android FR can omit a dynamic addressee from ``STATIC_SPEAKER:%S(n)!``
    # even though Android EN and the canonical SNES span both prove it.  Keep
    # the existing SNES PLAYER_NAME exactly where it already sits: immediately
    # after the localized static speaker label.  This requires one PlayerSlot,
    # text carriers on both sides, the same shape in Android EN, and a French
    # leading ``label:``.  No command is created, removed, moved, or reordered.
    if source_placeholders != french_placeholders and not french_placeholders:
        source_addressee = re.match(
            r"^\s*[^%\n:]{2,30}:\s*%S\((\d+),0\)\s*([!?])",
            source_display,
        )
        android_addressee = re.match(
            r"^\s*[^%\n:]{2,30}:\s*%S\((\d+),0\)\s*([!?])",
            mapping.get("android_english_display", ""),
        )
        french_speaker = re.match(r"^(\s*[^%\n:]{2,30}\s*:\s*)(.+)$", french_layout, re.S)
        player_slots = [slot for slot in slots if isinstance(slot, PlayerSlot)]
        if (
            source_addressee
            and android_addressee
            and source_addressee.groups() == android_addressee.groups()
            and french_speaker
            and len(player_slots) == 1
            and player_slots[0].index == int(source_addressee.group(1))
            and isinstance(slots[0], TextSlot)
            and isinstance(slots[-1], TextSlot)
        ):
            player_index = int(source_addressee.group(1))
            punctuation = source_addressee.group(2)
            french_layout = (
                f"{french_speaker.group(1)}%S({player_index},0) {punctuation} "
                f"{french_speaker.group(2).lstrip()}"
            )
            french_placeholders = placeholder_sequence(french_layout)
            preserved_static_speaker_dynamic_addressee = {
                "player_index": player_index,
                "punctuation": punctuation,
            }

    preserved_leading_snes_player_prefix = None

    # Android FR can omit an explicit dynamic addressee/speaker that both the
    # canonical SNES span and Android EN place at the very start.  The SNES
    # PLAYER_NAME command cannot safely be removed, so preserve that proven
    # leading placeholder and only its immediately following punctuation.  No
    # name command is invented or moved; this is a formatting fallback for an
    # already-existing first PlayerSlot.
    if source_placeholders != french_placeholders and not french_placeholders and slots:
        source_leading_player = re.match(r"^\s*%S\((\d+),0\)\s*([!?])\s*", source_display)
        android_leading_player = re.match(
            r"^\s*%S\((\d+),0\)\s*([!?])\s*",
            mapping.get("android_english_display", ""),
        )
        if (
            source_leading_player
            and android_leading_player
            and source_leading_player.groups() == android_leading_player.groups()
            and isinstance(slots[0], PlayerSlot)
            and slots[0].index == int(source_leading_player.group(1))
        ):
            player_index = int(source_leading_player.group(1))
            punctuation = source_leading_player.group(2)
            separator = f" {punctuation} "
            french_layout = f"%S({player_index},0){separator}{french_layout.lstrip()}"
            french_placeholders = placeholder_sequence(french_layout)
            preserved_leading_snes_player_prefix = {
                "player_index": player_index,
                "punctuation": punctuation,
            }

    adjacent_player_carrier_indexes: list[int] = []
    if source_placeholders != french_placeholders:
        slots, adjacent_player_carrier_indexes = (
            _extend_slots_through_adjacent_nonsemantic_player_carrier(
                document, mapping, slots, french_placeholders
            )
        )
        source_placeholders = tuple(
            slot.index for slot in slots if isinstance(slot, PlayerSlot)
        )
    positional_player_rebindings: list[dict[str, int]] = []
    if (
        source_placeholders != french_placeholders
        and source_placeholders
        and len(source_placeholders) == len(french_placeholders)
    ):
        # Android occasionally assigns the same spoken line to a different
        # party slot than the SNES script.  The English identity layer already
        # proves the prose correspondence independently of placeholder number;
        # for SNES serialization, preserve the existing PLAYER_NAME commands
        # and rebind French placeholders positionally to those canonical slots.
        # No event command is created, removed, moved, or reordered.
        replacements = iter(source_placeholders)

        def _rebind_player(match: re.Match[str]) -> str:
            target = next(replacements)
            source = int(match.group(1))
            positional_player_rebindings.append({"android_index": source, "snes_index": target})
            return f"%S({target},0)"

        french_layout = PLAYER_PLACEHOLDER_RE.sub(_rebind_player, french_layout)
        french_placeholders = placeholder_sequence(french_layout)
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
    inserted_leading_clear = bool(lead and _leading_newline_follows_wait(document, text_slots[0].text_id))
    if inserted_leading_clear:
        lead = 0

    leading_text_x_position = mapping_leading_text_x_position(document, mapping)
    first_line_prefix_pixels = leading_text_x_position * advances[" "]
    first_line_prefix_units = leading_text_x_position

    wrapper = semantic_wrap_markup if prefer_semantic_line_breaks else wrap_markup
    wrapped, widths, char_counts, parser_unit_counts = wrapper(
        french_layout,
        advances,
        max_pixels=max_pixels,
        first_line_prefix_pixels=first_line_prefix_pixels,
        first_line_prefix_units=first_line_prefix_units,
    )
    source_line_budget = source_visible_line_budget(source_display)
    line_budget = DIALOGUE_PAGE_LINES if use_physical_page_capacity else source_line_budget
    inserted_page_breaks = 0
    page_line_counts = (len(widths),)
    page_break_strategy: str | None = None
    if len(widths) > line_budget or force_one_extra_page:
        if not allow_one_extra_page:
            raise ValueError(
                f"French VWF needs {len(widths)} line(s), available page budget is {line_budget}: {mapping['snes_ids']}"
            )
        if not use_physical_page_capacity and line_budget != DIALOGUE_PAGE_LINES:
            raise ValueError(
                f"Extra-page pilot requires a {DIALOGUE_PAGE_LINES}-line source page; "
                f"source span exposes {line_budget}: {mapping['snes_ids']}"
            )
        if len(widths) > DIALOGUE_PAGE_LINES * 2 and allow_two_extra_pages:
            (
                wrapped,
                widths,
                char_counts,
                parser_unit_counts,
                page_line_counts,
                page_break_strategy,
            ) = _sentence_aware_three_page_wrap(
                french_layout,
                advances,
                max_pixels=max_pixels,
                max_chars=DIALOGUE_WRAP_CHARS,
                prefer_semantic_line_breaks=prefer_semantic_line_breaks,
                first_line_prefix_pixels=first_line_prefix_pixels,
                first_line_prefix_units=first_line_prefix_units,
            )
        else:
            (
                wrapped,
                widths,
                char_counts,
                parser_unit_counts,
                page_line_counts,
                page_break_strategy,
            ) = _sentence_aware_extra_page_wrap(
                french_layout,
                advances,
                max_pixels=max_pixels,
                max_chars=DIALOGUE_WRAP_CHARS,
                prefer_semantic_line_breaks=prefer_semantic_line_breaks,
                first_line_prefix_pixels=first_line_prefix_pixels,
                first_line_prefix_units=first_line_prefix_units,
            )
        if force_one_extra_page and page_break_strategy not in {
            "semantic_hard_boundary",
            "sentence_boundary",
        }:
            raise ValueError(
                "Forced event-level pagination requires a proven semantic sentence boundary"
            )
        inserted_page_breaks = len(page_line_counts) - 1

    translations = bind_wrapped_markup(slots, wrapped)

    # The stock choice UI often stores its closing parenthesis inside the last
    # option text token rather than as a separate control/glyph token. Android
    # choice labels intentionally omit that SNES presentation delimiter. Keep
    # the exact stock whitespace + `)` suffix only when this text token is
    # immediately followed by CHOICE_END; this preserves the stock frame and
    # CHOICE_END terminal-boundary semantics without translating or inventing
    # prose.
    preserved_choice_terminal_suffix_ids: list[str] = []
    _, by_event = format_event_text_index(document)
    event = by_event.get(mapping.get("event_id", ""))
    if event is not None:
        token_index_by_id = {
            token.get("id"): index
            for index, token in enumerate(event.get("tokens", []))
            if token.get("type") in {"text", "ending_text"}
        }
        for slot in text_slots:
            match = re.search(r"(\s*\))$", slot.source)
            if not match:
                continue
            token_index = token_index_by_id.get(slot.text_id)
            if token_index is None or token_index + 1 >= len(event["tokens"]):
                continue
            following = event["tokens"][token_index + 1]
            if not (following.get("type") == "command" and following.get("name") == "CHOICE_END"):
                continue
            if translations.get(slot.text_id, "").rstrip().endswith(")"):
                continue
            suffix = match.group(1)
            translations[slot.text_id] = translations[slot.text_id].rstrip() + suffix
            preserved_choice_terminal_suffix_ids.append(slot.text_id)

    first_id = text_slots[0].text_id
    last_id = text_slots[-1].text_id
    translations[first_id] = "\n" * lead + translations[first_id]
    if inserted_leading_clear:
        translations[first_id] = TRANSLATION_CLEAR + translations[first_id]
    translations[last_id] = translations[last_id] + "\n" * trail

    # Final byte-level charset check before the translation JSON reaches 08.
    for text_id, text in translations.items():
        for char in text:
            if char in ("\n", "\f", TRANSLATION_CLEAR):
                continue
            if char not in TEXT_TO_CODE:
                raise ValueError(f"{text_id}: unsupported formatted character {char!r}")

    adjacent_nonsemantic_carrier_ids = [
        slot.text_id
        for slot in text_slots
        if slot.text_id not in set(mapping["snes_ids"])
    ]

    report = {
        "event_id": mapping["event_id"],
        "snes_ids": mapping["snes_ids"],
        "android_ids": mapping.get("android_ids", []),
        "confidence": mapping.get("confidence"),
        "source_display": source_display,
        "android_french_raw": french_raw,
        "structural_markers_removed": structural_markers_removed,
        "preserved_choice_terminal_suffix_ids": preserved_choice_terminal_suffix_ids or None,
        "adjacent_nonsemantic_carrier_ids": adjacent_nonsemantic_carrier_ids or None,
        "adjacent_player_carrier_indexes": adjacent_player_carrier_indexes or None,
        "preserved_static_speaker_dynamic_addressee": preserved_static_speaker_dynamic_addressee,
        "preserved_leading_snes_player_prefix": preserved_leading_snes_player_prefix,
        "positional_player_rebindings": positional_player_rebindings or None,
        "ignored_alignment_trailing_player_context": ignored_alignment_trailing_player_context or None,
        "android_french_normalized": french_normalized,
        "layout_markup_before_wrap": french_layout,
        "layout_hints": layout_hints,
        "formatted_markup": "\n" * lead + wrapped + "\n" * trail,
        "line_widths_pixels": widths,
        "line_decoded_character_counts": char_counts,
        "line_parser_unit_counts": parser_unit_counts,
        "leading_text_x_position": leading_text_x_position or None,
        "leading_text_x_padding_pixels": first_line_prefix_pixels,
        "leading_text_x_parser_units": first_line_prefix_units,
        "source_visible_line_budget": source_line_budget,
        "effective_line_budget": line_budget,
        "physical_page_capacity_mode": use_physical_page_capacity,
        "semantic_line_break_preferences": prefer_semantic_line_breaks,
        "page_line_counts": list(page_line_counts),
        "inserted_page_break_count": inserted_page_breaks,
        "inserted_leading_clear": inserted_leading_clear,
        "page_break_encoding": "WAIT $00 + TEXT_CLEAR" if inserted_page_breaks else None,
        "page_break_strategy": page_break_strategy,
        "event_level_forced_page_break": force_one_extra_page,
        "formatted_entries": [
            {"id": text_id, "text": translations[text_id]} for text_id in mapping["snes_ids"]
        ],
    }
    return translations, report



def format_mapping_across_existing_wait_boundaries(
    document: dict,
    mapping: dict,
    advances: dict[str, int],
    *,
    max_pixels: int = DIALOGUE_WRAP_PIXELS,
    allow_one_extra_page: bool = True,
    use_physical_page_capacity: bool = True,
    prefer_semantic_line_breaks: bool = True,
    allow_two_extra_pages: bool = True,
) -> tuple[dict[str, str], dict]:
    """Distribute localized sentences across proven stock WAIT $00 boundaries.

    This fallback is intentionally structural rather than editorial. It applies
    only when one accepted Android mapping owns two or more existing SNES text
    tokens separated by one interactive ``WAIT $00``, optional ``TEXT_CLEAR``,
    and optionally the already-validated pure actor-action pair ``OP_32/OP_34``
    + ``COMPLETE_ACTIONS``. A single ``PLAYER_NAME`` is also allowed only as
    an identical leading placeholder immediately before the first mapped text
    carrier; no dynamic name may occur at or across a WAIT boundary. The existing
    event commands remain byte-for-byte in place; French is cut only at complete
    sentence boundaries and each resulting piece is formatted independently by
    the normal validated formatter.

    Timed WAITs are deliberately rejected. A candidate is chosen to preserve
    the source token's sentence distribution first, then to minimize local
    layout pressure. If no complete-sentence distribution formats cleanly, the
    mapping stays excluded.
    """
    snes_ids = mapping.get("snes_ids", [])
    if len(snes_ids) < 2:
        raise ValueError("Existing-WAIT distribution requires at least two SNES text IDs")

    source_display = mapping.get("source_display", "")
    french_display = mapping.get("french_display", "")
    source_players = tuple(int(match.group(1)) for match in PLAYER_PLACEHOLDER_RE.finditer(source_display))
    french_players = tuple(int(match.group(1)) for match in PLAYER_PLACEHOLDER_RE.finditer(french_display))
    leading_player_index: int | None = None
    if source_players or french_players:
        source_leading = re.match(r"^\s*%S\((\d+),0\)", source_display)
        french_leading = re.match(r"^\s*%S\((\d+),0\)", french_display)
        if (
            source_players != french_players
            or len(source_players) != 1
            or source_leading is None
            or french_leading is None
            or source_leading.group(1) != french_leading.group(1)
        ):
            raise ValueError(
                "Existing-WAIT distribution handles only one identical leading PLAYER_NAME"
            )
        leading_player_index = source_players[0]

    by_id, by_event = format_event_text_index(document)
    metas = []
    for text_id in snes_ids:
        meta = by_id.get(text_id)
        if meta is None:
            raise ValueError(f"Existing-WAIT distribution references unknown SNES text ID {text_id}")
        metas.append(meta)
    event_ids = {meta["event_id"] for meta in metas}
    if len(event_ids) != 1:
        raise ValueError("Existing-WAIT distribution cannot cross events")
    token_indexes = [meta["token_index"] for meta in metas]
    if token_indexes != sorted(token_indexes) or len(set(token_indexes)) != len(token_indexes):
        raise ValueError("Existing-WAIT distribution IDs are not in strict token order")

    event = by_event[metas[0]["event_id"]]
    if leading_player_index is not None:
        first_index = token_indexes[0]
        if first_index <= 0:
            raise ValueError("Existing-WAIT leading PLAYER_NAME has no canonical predecessor")
        player = event["tokens"][first_index - 1]
        if (
            player.get("type") != "command"
            or player.get("name") != "PLAYER_NAME"
            or int(player.get("args", "00").split()[0], 16) != leading_player_index
        ):
            raise ValueError(
                "Existing-WAIT leading PLAYER_NAME is not immediately before the first mapped carrier"
            )

    boundary_commands: list[list[dict]] = []
    for first_index, second_index in zip(token_indexes, token_indexes[1:]):
        between = event["tokens"][first_index + 1:second_index]
        if not between:
            raise ValueError("Existing-WAIT distribution found no command at a mapped boundary")
        wait00_count = 0
        rendered_commands: list[dict] = []
        action_commands: list[str] = []
        for token in between:
            if token.get("type") != "command":
                raise ValueError("Existing-WAIT distribution crosses non-command event data")
            name = token.get("name")
            if name == "WAIT":
                if token.get("args", "").strip().upper() != "00":
                    raise ValueError("Existing-WAIT distribution never crosses timed WAITs")
                wait00_count += 1
            elif name == "TEXT_CLEAR":
                pass
            elif name in {"OP_32", "OP_34", "COMPLETE_ACTIONS"}:
                action_commands.append(name)
            else:
                raise ValueError(
                    f"Existing-WAIT distribution crosses unsupported command {name!r}"
                )
            rendered_commands.append({"name": name, "args": token.get("args")})
        if wait00_count != 1:
            raise ValueError("Existing-WAIT distribution requires exactly one WAIT $00 per boundary")
        if action_commands and (
            not ({"OP_32", "OP_34"} & set(action_commands))
            or "COMPLETE_ACTIONS" not in action_commands
        ):
            raise ValueError(
                "Existing-WAIT action bridge requires an actor action and COMPLETE_ACTIONS"
            )
        boundary_commands.append(rendered_commands)

    french_without_structural_markers, structural_markers_removed = (
        strip_proven_structural_android_markers(document, mapping, mapping.get("french_display", ""))
    )
    french_normalized = normalize_android_french(french_without_structural_markers)
    if not french_normalized:
        raise ValueError("Existing-WAIT distribution has no French prose")
    boundaries = sentence_boundary_positions(french_normalized)
    split_count = len(snes_ids) - 1
    weak_clause_boundary = False
    if len(boundaries) < split_count:
        # Android FR occasionally merges the two complete source sentences on
        # either side of an existing interactive WAIT into one sentence joined
        # by a discourse conjunction (for example ``, alors ...``). Reuse that
        # stock pause without editing it only for the exact two-slot shape and
        # only at such an explicit comma+connector boundary. A bare internal
        # comma is never enough.
        if len(snes_ids) == 2 and split_count == 1:
            connector_boundaries = []
            for boundary in _comma_boundary_positions(french_normalized):
                following = french_normalized[boundary:].lstrip()
                if re.match(r"(?:alors|mais|donc|pourtant|cependant)\b", following, re.IGNORECASE):
                    connector_boundaries.append(boundary)
            source_complete = all(
                re.search(r"(?:\.{3}|[.!?…])[”\"»')\]]*$", re.sub(r"\s+", " ", by_id[text_id]["source"].strip()))
                for text_id in snes_ids
            )
            if source_complete and connector_boundaries:
                boundaries = tuple(connector_boundaries)
                weak_clause_boundary = True
        if len(boundaries) < split_count:
            raise ValueError(
                "Existing-WAIT distribution requires enough complete-sentence boundaries for every stock WAIT"
            )

    def sentence_count(text: str) -> int:
        compact = re.sub(r"\\s+", " ", text.strip())
        if not compact:
            return 0
        return len(sentence_boundary_positions(compact)) + 1

    source_sentence_counts = [sentence_count(by_id[text_id]["source"]) for text_id in snes_ids]
    candidates = []
    for chosen in combinations(boundaries, split_count):
        positions = (0, *chosen, len(french_normalized))
        pieces = [
            french_normalized[positions[index]:positions[index + 1]].strip()
            for index in range(len(snes_ids))
        ]
        if any(not piece for piece in pieces):
            continue

        translations: dict[str, str] = {}
        local_reports: list[dict] = []
        valid = True
        for part_index, (text_id, french_piece) in enumerate(zip(snes_ids, pieces, strict=True)):
            local_mapping = dict(mapping)
            local_mapping["snes_ids"] = [text_id]
            if part_index == 0 and leading_player_index is not None:
                placeholder = f"%S({leading_player_index},0)"
                local_mapping["source_display"] = placeholder + by_id[text_id]["source"]
                local_mapping["french_display"] = french_piece
            else:
                local_mapping["source_display"] = by_id[text_id]["source"]
                local_mapping["french_display"] = french_piece
            try:
                values, report = format_mapping(
                    document,
                    local_mapping,
                    advances,
                    max_pixels=max_pixels,
                    allow_one_extra_page=allow_one_extra_page,
                    use_physical_page_capacity=use_physical_page_capacity,
                    prefer_semantic_line_breaks=prefer_semantic_line_breaks,
                    allow_two_extra_pages=allow_two_extra_pages,
                )
            except ValueError:
                valid = False
                break
            if set(values) & set(translations):
                valid = False
                break
            translations.update(values)
            local_reports.append(report)
        if not valid:
            continue

        french_sentence_counts = [sentence_count(piece) for piece in pieces]
        sentence_mismatch = sum(
            abs(source_count - french_count)
            for source_count, french_count in zip(
                source_sentence_counts, french_sentence_counts, strict=True
            )
        )
        page_breaks = sum(report.get("inserted_page_break_count", 0) for report in local_reports)
        line_counts = [sum(report.get("page_line_counts", [])) for report in local_reports]
        score = (
            sentence_mismatch,
            page_breaks,
            max(line_counts, default=0),
            max(line_counts, default=0) - min(line_counts, default=0),
            chosen,
        )
        candidates.append((score, pieces, translations, local_reports))

    if not candidates:
        raise ValueError(
            "Existing-WAIT distribution found no complete-sentence split whose parts format cleanly"
        )

    _, pieces, translations, local_reports = min(candidates, key=lambda item: item[0])
    report = {
        "event_id": mapping["event_id"],
        "snes_ids": snes_ids,
        "android_ids": mapping.get("android_ids", []),
        "confidence": mapping.get("confidence"),
        "source_display": mapping.get("source_display", ""),
        "android_french_raw": mapping.get("french_display", ""),
        "structural_markers_removed": structural_markers_removed,
        "android_french_normalized": french_normalized,
        "existing_wait_sentence_distribution": True,
        "existing_wait_leading_player_index": leading_player_index,
        "existing_wait_weak_clause_boundary": weak_clause_boundary,
        "existing_wait_boundary_commands": boundary_commands,
        "source_sentence_counts": source_sentence_counts,
        "distributed_french_parts": pieces,
        "existing_wait_parts": local_reports,
        "formatted_entries": [
            {"id": text_id, "text": translations[text_id]}
            for text_id in snes_ids
            if text_id in translations
        ],
    }
    return translations, report



def format_mapping_across_existing_timed_wait_boundary(
    document: dict,
    mapping: dict,
    advances: dict[str, int],
    *,
    max_pixels: int = DIALOGUE_WRAP_PIXELS,
    allow_one_extra_page: bool = True,
    use_physical_page_capacity: bool = True,
    prefer_semantic_line_breaks: bool = True,
    allow_two_extra_pages: bool = True,
) -> tuple[dict[str, str], dict]:
    """Distribute one mapping across one existing timed WAIT without editing it.

    This path is intentionally narrower than the interactive-WAIT distributor.
    It accepts exactly two mapped SNES text tokens separated only by one stock
    ``WAIT $04`` or ``WAIT $08``.  Both the first source token and the chosen
    first French piece must end at a complete sentence boundary.  Dynamic names,
    choices and every other intervening command remain excluded.  The timed WAIT
    is preserved byte-for-byte; this function only chooses which already-mapped
    localized sentence is emitted on each side of it.
    """
    snes_ids = mapping.get("snes_ids", [])
    if len(snes_ids) != 2:
        raise ValueError("Existing timed-WAIT distribution requires exactly two SNES text IDs")
    if PLAYER_PLACEHOLDER_RE.search(mapping.get("source_display", "")):
        raise ValueError("Existing timed-WAIT distribution does not handle source PLAYER_NAME")
    if PLAYER_PLACEHOLDER_RE.search(mapping.get("french_display", "")):
        raise ValueError("Existing timed-WAIT distribution does not handle French PLAYER_NAME")

    by_id, by_event = format_event_text_index(document)
    first_meta = by_id.get(snes_ids[0])
    second_meta = by_id.get(snes_ids[1])
    if first_meta is None or second_meta is None:
        raise ValueError("Existing timed-WAIT distribution references an unknown SNES text ID")
    if first_meta["event_id"] != second_meta["event_id"]:
        raise ValueError("Existing timed-WAIT distribution cannot cross events")
    first_index = first_meta["token_index"]
    second_index = second_meta["token_index"]
    if first_index >= second_index:
        raise ValueError("Existing timed-WAIT distribution IDs are not in token order")

    event = by_event[first_meta["event_id"]]
    if any(
        token.get("type") == "command"
        and token.get("name") in {"CHOICE_BEGIN", "CHOICE_OPTION", "CHOICE_END"}
        for token in event["tokens"]
    ):
        raise ValueError("Existing timed-WAIT distribution stays disabled in events containing choices")
    between = event["tokens"][first_index + 1:second_index]
    if len(between) != 1 or between[0].get("type") != "command" or between[0].get("name") != "WAIT":
        raise ValueError("Existing timed-WAIT distribution requires one WAIT and no other boundary command")
    wait_arg = between[0].get("args", "").strip().upper()
    if wait_arg not in {"04", "08"}:
        raise ValueError("Existing timed-WAIT distribution handles only stock WAIT $04/$08")

    first_source = re.sub(r"\s+", " ", first_meta["source"].strip())
    if not re.search(r"(?:\.{3}|[.!?…])[”\"»')\]]*$", first_source):
        raise ValueError("Existing timed-WAIT distribution requires a complete source sentence before the WAIT")

    french_without_structural_markers, structural_markers_removed = (
        strip_proven_structural_android_markers(document, mapping, mapping.get("french_display", ""))
    )
    french_normalized = normalize_android_french(french_without_structural_markers)
    boundaries = sentence_boundary_positions(french_normalized)
    if not boundaries:
        raise ValueError("Existing timed-WAIT distribution requires a complete French sentence boundary")

    candidates = []
    for boundary in boundaries:
        pieces = [french_normalized[:boundary].strip(), french_normalized[boundary:].strip()]
        if any(not piece for piece in pieces):
            continue
        translations: dict[str, str] = {}
        local_reports: list[dict] = []
        valid = True
        for text_id, french_piece in zip(snes_ids, pieces, strict=True):
            local_mapping = dict(mapping)
            local_mapping["snes_ids"] = [text_id]
            local_mapping["source_display"] = by_id[text_id]["source"]
            local_mapping["french_display"] = french_piece
            try:
                values, report = format_mapping(
                    document,
                    local_mapping,
                    advances,
                    max_pixels=max_pixels,
                    allow_one_extra_page=allow_one_extra_page,
                    use_physical_page_capacity=use_physical_page_capacity,
                    prefer_semantic_line_breaks=prefer_semantic_line_breaks,
                    allow_two_extra_pages=allow_two_extra_pages,
                )
            except ValueError:
                valid = False
                break
            if set(values) & set(translations):
                valid = False
                break
            translations.update(values)
            local_reports.append(report)
        if not valid:
            continue
        line_counts = [sum(report.get("page_line_counts", [])) for report in local_reports]
        page_breaks = sum(report.get("inserted_page_break_count", 0) for report in local_reports)
        score = (
            page_breaks,
            max(line_counts, default=0),
            abs(line_counts[0] - line_counts[1]),
            boundary,
        )
        candidates.append((score, pieces, translations, local_reports))

    if not candidates:
        raise ValueError("Existing timed-WAIT distribution found no clean sentence-boundary split")
    _, pieces, translations, local_reports = min(candidates, key=lambda item: item[0])
    report = {
        "event_id": mapping["event_id"],
        "snes_ids": snes_ids,
        "android_ids": mapping.get("android_ids", []),
        "confidence": mapping.get("confidence"),
        "source_display": mapping.get("source_display", ""),
        "android_french_raw": mapping.get("french_display", ""),
        "structural_markers_removed": structural_markers_removed,
        "android_french_normalized": french_normalized,
        "existing_timed_wait_sentence_distribution": True,
        "existing_timed_wait_arg": wait_arg,
        "distributed_french_parts": pieces,
        "existing_timed_wait_parts": local_reports,
        "formatted_entries": [
            {"id": text_id, "text": translations[text_id]}
            for text_id in snes_ids
            if text_id in translations
        ],
    }
    return translations, report

def format_mapping_across_existing_action_boundary(
    document: dict,
    mapping: dict,
    advances: dict[str, int],
    *,
    max_pixels: int = DIALOGUE_WRAP_PIXELS,
    allow_one_extra_page: bool = True,
    use_physical_page_capacity: bool = True,
    prefer_semantic_line_breaks: bool = True,
    allow_two_extra_pages: bool = True,
) -> tuple[dict[str, str], dict]:
    """Split one localized Android unit across a proven stock action boundary.

    `vwf_dialogues` runtime work established the event interruption sequence where
    ``OP_32`` schedules actor movement/action and ``COMPLETE_ACTIONS`` waits for
    scheduled actions to finish before text parsing resumes in the same box.
    This formatter fallback therefore handles only two mapped text tokens from
    one Android localization unit, separated exclusively by ``OP_32`` walk,
    ``OP_34`` loop-action and ``COMPLETE_ACTIONS`` commands. The source token
    before the action must already end a complete sentence, and French is split
    only at a complete-sentence boundary. Events containing interactive choice
    commands, PLAYER_NAME, WAIT, or any other boundary command remain excluded.
    """
    snes_ids = mapping.get("snes_ids", [])
    if len(snes_ids) != 2:
        raise ValueError("Existing-action split requires exactly two SNES text IDs")
    if len(mapping.get("android_ids", [])) != 1:
        raise ValueError("Existing-action split requires one Android localization unit")
    source_player_indexes = placeholder_sequence(mapping.get("source_display", ""))
    french_player_indexes = placeholder_sequence(mapping.get("french_display", ""))
    if source_player_indexes != french_player_indexes or len(source_player_indexes) > 1:
        raise ValueError("Existing-action split requires at most one unchanged PLAYER_NAME")

    by_id, by_event = format_event_text_index(document)
    first_meta = by_id.get(snes_ids[0])
    second_meta = by_id.get(snes_ids[1])
    if first_meta is None or second_meta is None:
        raise ValueError("Existing-action split references an unknown SNES text ID")
    if first_meta["event_id"] != second_meta["event_id"]:
        raise ValueError("Existing-action split cannot cross events")
    first_index = first_meta["token_index"]
    second_index = second_meta["token_index"]
    if first_index >= second_index:
        raise ValueError("Existing-action split IDs are not in token order")

    event = by_event[first_meta["event_id"]]
    leading_player_prefix = ""
    if source_player_indexes:
        player_index = source_player_indexes[0]
        if first_index <= 0:
            raise ValueError("Existing-action split cannot prove the leading PLAYER_NAME")
        previous = event["tokens"][first_index - 1]
        args = previous.get("args", "00").split() if previous.get("type") == "command" else []
        if (
            previous.get("name") != "PLAYER_NAME"
            or not args
            or int(args[0], 16) != player_index
        ):
            raise ValueError("Existing-action split PLAYER_NAME is not immediately before the first text")
        leading_player_prefix = f"%S({player_index},0)"
        if not mapping.get("source_display", "").startswith(leading_player_prefix):
            raise ValueError("Existing-action split source PLAYER_NAME is not a leading placeholder")

    if any(
        token.get("type") == "command"
        and token.get("name") in {"CHOICE_BEGIN", "CHOICE_OPTION", "CHOICE_END"}
        for token in event["tokens"]
    ):
        raise ValueError("Existing-action split stays disabled in events containing choices")
    between = event["tokens"][first_index + 1:second_index]
    if not between:
        raise ValueError("Existing-action split found no event command")
    names = []
    for token in between:
        if token.get("type") != "command":
            raise ValueError("Existing-action split crosses non-command event data")
        name = token.get("name")
        if name not in {"OP_32", "OP_34", "COMPLETE_ACTIONS"}:
            raise ValueError(f"Existing-action split crosses unsupported command {name!r}")
        names.append(name)
    if not ({"OP_32", "OP_34"} & set(names)):
        raise ValueError("Existing-action split requires at least one actor action command")

    first_source = re.sub(r"\s+", " ", first_meta["source"].strip())
    if not re.search(r"(?:\.{3}|[.!?…])[”\"»')\]]*$", first_source):
        raise ValueError("Existing-action split requires a complete source sentence before the action")

    french_without_structural_markers, structural_markers_removed = (
        strip_proven_structural_android_markers(document, mapping, mapping.get("french_display", ""))
    )
    french_normalized = normalize_android_french(french_without_structural_markers)
    boundaries = sentence_boundary_positions(french_normalized)
    if not boundaries:
        raise ValueError("Existing-action split requires a complete French sentence boundary")

    candidates = []
    for boundary in boundaries:
        pieces = [french_normalized[:boundary].strip(), french_normalized[boundary:].strip()]
        if any(not piece for piece in pieces):
            continue
        translations: dict[str, str] = {}
        local_reports: list[dict] = []
        valid = True
        for text_id, french_piece in zip(snes_ids, pieces, strict=True):
            local_mapping = dict(mapping)
            local_mapping["snes_ids"] = [text_id]
            local_mapping["source_display"] = (
                leading_player_prefix + by_id[text_id]["source"]
                if text_id == snes_ids[0] else by_id[text_id]["source"]
            )
            local_mapping["french_display"] = french_piece
            try:
                values, report = format_mapping(
                    document,
                    local_mapping,
                    advances,
                    max_pixels=max_pixels,
                    allow_one_extra_page=allow_one_extra_page,
                    use_physical_page_capacity=use_physical_page_capacity,
                    prefer_semantic_line_breaks=prefer_semantic_line_breaks,
                    allow_two_extra_pages=allow_two_extra_pages,
                )
            except ValueError:
                valid = False
                break
            if set(values) & set(translations):
                valid = False
                break
            translations.update(values)
            local_reports.append(report)
        if not valid:
            continue
        inserted_boundary_newline = False
        if not by_id[snes_ids[0]]["source"].endswith("\n"):
            first_value = translations.get(snes_ids[0], "")
            if first_value and not first_value.endswith(("\n", "\f", TRANSLATION_CLEAR)):
                translations[snes_ids[0]] = first_value + "\n"
                inserted_boundary_newline = True
        line_counts = [sum(report.get("page_line_counts", [])) for report in local_reports]
        page_breaks = sum(report.get("inserted_page_break_count", 0) for report in local_reports)
        score = (
            page_breaks,
            max(line_counts, default=0),
            abs(line_counts[0] - line_counts[1]),
            boundary,
        )
        candidates.append((score, pieces, translations, local_reports, inserted_boundary_newline))

    if not candidates:
        raise ValueError("Existing-action split found no clean sentence-boundary distribution")
    _, pieces, translations, local_reports, inserted_boundary_newline = min(
        candidates, key=lambda item: item[0]
    )
    report = {
        "event_id": mapping["event_id"],
        "snes_ids": snes_ids,
        "android_ids": mapping.get("android_ids", []),
        "confidence": mapping.get("confidence"),
        "source_display": mapping.get("source_display", ""),
        "android_french_raw": mapping.get("french_display", ""),
        "structural_markers_removed": structural_markers_removed,
        "android_french_normalized": french_normalized,
        "existing_action_sentence_split": True,
        "existing_action_boundary_commands": [
            {"name": token.get("name"), "args": token.get("args")} for token in between
        ],
        "inserted_action_boundary_line_break": inserted_boundary_newline,
        "distributed_french_parts": pieces,
        "existing_action_parts": local_reports,
        "formatted_entries": [
            {"id": text_id, "text": translations[text_id]}
            for text_id in snes_ids
            if text_id in translations
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
